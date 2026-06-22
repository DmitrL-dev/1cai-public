#!/usr/bin/env python
"""Backtest harness for the 1С:Рентген risk score — makes the explainable heuristic VALIDATABLE.

The risk score (``store._risk``: ``quality_risk × blast(fan_in)``) is a *transparent but
UNVALIDATED* heuristic — its weights are expert-set, not calibrated against real defects (see the
"Что факт, что эвристика" section in docs/RENTGEN.md). The honest way to answer "is the risk score
any good?" is to backtest it against ground-truth defect labels per module. This tool does exactly
that: it measures how well the risk ranking separates modules that actually had defects from those
that didn't.

--------------------------------------------------------------------------------
WHERE THE LABELS COME FROM  (a JSON: {module_path: defect_count_or_0_1})
--------------------------------------------------------------------------------
You need a defect signal per BSL module. Two practical sources:

  1. The 1C configuration's own VCS (EDT/XML export under git): count bug-fix commits that touch
     each module. A defect proxy that needs no extra tooling, e.g.:
         git -C <config-repo> log --name-only --pretty=format: \
             --grep='fix\\|bug\\|hotfix\\|ошибк\\|исправл\\|дефект' \
             | sort | uniq -c
     then map the touched file paths to store module paths
     (e.g. CommonModules/<Name>/Ext/Module.bsl) and write {module_path: count}.

  2. An incident / bug tracker: number of tickets implicating each module.

Example labels.json:
    {"CommonModules/Sales/Ext/Module.bsl": 7, "Documents/Order/Ext/ObjectModule.bsl": 0}

--------------------------------------------------------------------------------
USAGE
    C:\\Python311\\python.exe -m tools.rentgen.validate_risk --labels labels.json [--top 50]

Outputs Spearman correlation (risk vs defect count), ROC-AUC (risk as a had-defect classifier),
precision@K + lift over the base rate, and coverage. It is HONEST: low overlap or AUC≈0.5 /
Spearman≈0 means the heuristic is NOT calibrated for this configuration — keep selling it as
"explainable prioritization", not a validated probability of failure.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def spearman(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 2:
        return None

    def ranks(v: list[float]) -> list[float]:
        order = sorted(range(n), key=lambda i: v[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r

    rx, ry = ranks(xs), ranks(ys)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    dx = sum((rx[i] - mx) ** 2 for i in range(n)) ** 0.5
    dy = sum((ry[i] - my) ** 2 for i in range(n)) ** 0.5
    return num / (dx * dy) if dx and dy else None


def roc_auc(scores: list[float], labels: list[int]) -> float | None:
    pos = [scores[i] for i in range(len(labels)) if labels[i]]
    neg = [scores[i] for i in range(len(labels)) if not labels[i]]
    if not pos or not neg:
        return None
    wins = 0.0
    for p in pos:
        for ng in neg:
            wins += 1.0 if p > ng else (0.5 if p == ng else 0.0)
    return wins / (len(pos) * len(neg))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Validate the 1С:Рентген risk heuristic against ground-truth defect labels."
    )
    ap.add_argument("--labels", required=True, help="JSON file: {module_path: defect_count}")
    ap.add_argument("--top", type=int, default=50, help="K for precision@K (default 50)")
    args = ap.parse_args(argv)

    labels = json.loads(Path(args.labels).read_text(encoding="utf-8"))
    if not isinstance(labels, dict) or not labels:
        print("labels file must be a non-empty JSON object {module_path: count}")
        return 2

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.rentgen.store import get_store

    store = get_store()
    if store is None:
        print("No store available (data/rentgen.db not built). Build it first; see README.")
        return 2

    risks: list[float] = []
    defects: list[float] = []
    matched = 0
    for module_path, count in labels.items():
        info = store.get_module_risk(module_path)
        if not info or info.get("risk") is None:
            continue
        matched += 1
        risks.append(float(info["risk"]))
        defects.append(float(count))

    print(f"Labeled modules: {len(labels)} | matched in store: {matched}")
    if matched < 5:
        print(
            "INSUFFICIENT OVERLAP (<5) — cannot validate. Check that label keys match the store's "
            "module paths (e.g. 'CommonModules/<Name>/Ext/Module.bsl'). "
            "Until validated, the risk score is an UNVALIDATED explainable heuristic."
        )
        return 2

    binary = [1 if d > 0 else 0 for d in defects]
    sp = spearman(risks, defects)
    auc = roc_auc(risks, binary)
    order = sorted(range(matched), key=lambda i: risks[i], reverse=True)
    k = min(args.top, matched)
    prec = sum(binary[i] for i in order[:k]) / k
    base = sum(binary) / matched

    print("\n=== Risk-heuristic validation ===")
    print(f"Spearman(risk, defect_count): {sp:.3f}" if sp is not None else "Spearman: n/a")
    print(f"ROC-AUC(risk -> had_defect):  {auc:.3f}" if auc is not None else "ROC-AUC: n/a (need both classes)")
    lift = f", lift {prec / base:.2f}x over base {base:.3f}" if base else ""
    print(f"precision@{k}: {prec:.3f}{lift}")

    good = auc is not None and auc >= 0.65 and (sp or 0) >= 0.2
    print(
        "\nVerdict: "
        + (
            "the risk ranking separates defect-prone modules better than chance for this config."
            if good
            else "NOT validated for this config (AUC≈0.5 / Spearman≈0 = no better than chance). "
            "Keep it framed as explainable prioritization, not a calibrated predictor."
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
