"""Shared change-planning logic for API, MCP and CI gate flows."""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

from src.services.rentgen.test_inventory import match_tests_for_module


ROOT = Path(__file__).resolve().parents[3]
YAXUNIT_ROOT = ROOT / "tools" / "yaxunit"

_TOKEN_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9_]{4,}")
_COMMON_TERMS = {
    "commonmodules",
    "documents",
    "catalogs",
    "module",
    "bsl",
    "ext",
    "forms",
    "form",
    "objectmodule",
    "managermodule",
    "commandmodule",
    "модуль",
    "документ",
    "справочник",
    "форма",
    "объект",
    "данные",
}


def dedupe(values: list[str]) -> list[str]:
    """Stable de-duplication for user-supplied module paths."""
    return list(dict.fromkeys(value.strip() for value in values if value and value.strip()))


def strip_diff_path(path: str) -> str | None:
    path = path.strip().split("\t", 1)[0]
    if path == "/dev/null":
        return None
    if path.startswith(("a/", "b/")):
        path = path[2:]
    if ".bsl" not in path.lower():
        return None
    marker_idx = path.lower().find(".bsl")
    return path[: marker_idx + 4].replace("\\", "/")


def extract_diff_modules(diff: str | None) -> list[str]:
    if not diff:
        return []
    modules = []
    for line in diff.splitlines():
        if line.startswith("+++ ") or line.startswith("--- "):
            path = strip_diff_path(line[4:])
            if path:
                modules.append(path)
    return dedupe(modules)


def extract_added_code(diff: str | None) -> dict[str, str]:
    if not diff:
        return {}
    current: str | None = None
    added: dict[str, list[str]] = {}
    for line in diff.splitlines():
        if line.startswith("+++ "):
            current = strip_diff_path(line[4:])
            if current:
                added.setdefault(current, [])
            continue
        if line.startswith("--- "):
            continue
        if current and line.startswith("+") and not line.startswith("+++"):
            added[current].append(line[1:])
    return {path: "\n".join(lines) for path, lines in added.items() if lines}


def performance_risks(module_path: str, quality: dict | None) -> list[dict[str, str]]:
    if not quality:
        return []
    risks = []
    if quality.get("has_n_plus_one"):
        risks.append(
            {
                "module_path": module_path,
                "factor": "has_n_plus_one",
                "severity": "high",
                "detail": "В модуле есть признак запроса в цикле (N+1).",
            }
        )
    if quality.get("has_select_star"):
        risks.append(
            {
                "module_path": module_path,
                "factor": "has_select_star",
                "severity": "medium",
                "detail": "В модуле есть ВЫБРАТЬ *: проверьте лишние поля и план запроса.",
            }
        )
    return risks


def dedupe_risks(risks: list[dict[str, str]]) -> list[dict[str, str]]:
    seen = set()
    result = []
    for risk in risks:
        key = (risk.get("module_path"), risk.get("factor"))
        if key in seen:
            continue
        seen.add(key)
        result.append(risk)
    return result


# Honest blast-radius coverage. A changed module that does not resolve to any
# call-graph node has an *unmeasured* radius — NOT a zero one. Forms (≈44% of
# modules) are the dominant case: the Go scanner does not emit form-module
# subroutines into the call graph, so they have no graph node to traverse from.
# Reporting impact_total=0 for them as "safe to change" is a silent false-zero;
# we surface coverage="no_graph_data" + a caveat instead.
COVERAGE_IN_GRAPH = "in_graph"
COVERAGE_NO_GRAPH_DATA = "no_graph_data"

_NO_GRAPH_CAVEAT = (
    "Радиус поражения НЕ измерен: модуль не найден в графе вызовов "
    "(это не ноль). impact_total=0 здесь означает «нет данных», а не «безопасно»."
)


def impact_coverage(impact: dict[str, Any]) -> tuple[str, str | None]:
    """Classify whether a module's blast radius was actually measured.

    Returns (coverage_flag, caveat_or_None). ``no_graph_data`` means the changed
    module could not be resolved to a graph node, so impact_total is unmeasured
    and must never be presented as a safe zero.
    """
    if impact.get("graph_modules"):
        return COVERAGE_IN_GRAPH, None
    return COVERAGE_NO_GRAPH_DATA, _NO_GRAPH_CAVEAT


def _yaxunit_available() -> bool:
    return YAXUNIT_ROOT.exists()


def _yaxunit_command(selector: str) -> str:
    return f"YAxUnit/Vanessa: run tests matching selector '{selector}'"


def select_tests_for_change(
    module_path: str,
    quality: dict | None,
    impact: dict[str, Any],
    impacted_hotspots: list[dict],
    performance: list[dict[str, str]],
) -> list[dict[str, Any]]:
    """Build a deterministic risk-driven test plan.

    The selector is intentionally conservative: when exact test ownership is not
    known yet, it emits run-plan entries with explicit confidence and reasons
    instead of pretending a precise YAxUnit mapping exists.
    """
    object_name = impact.get("canonical", {}).get("object_name") or Path(module_path).stem
    impact_total = int(impact.get("total") or 0)
    risk = int((quality or {}).get("risk") or 0)
    has_graph = bool(impact.get("graph_modules"))
    tests: list[dict[str, Any]] = []
    mapped_tests = match_tests_for_module(module_path, object_name=object_name, limit=5)

    for mapped in mapped_tests:
        tests.append(
            {
                "id": f"mapped:{mapped['id']}",
                "framework": mapped["framework"],
                "selector": mapped["selector"],
                "priority": "high" if risk >= 60 or impact_total >= 100 else "medium",
                "confidence": mapped["confidence"],
                "status": "mapped",
                "reason": mapped["reason"],
                "command": _yaxunit_command(mapped["selector"]),
                "path": mapped["path"],
                "line": mapped["line"],
                "matched_terms": mapped["matched_terms"],
            }
        )

    tests.append(
        {
            "id": "unit-local",
            "framework": "YAxUnit",
            "selector": object_name,
            "priority": "high" if risk >= 60 else "medium",
            "confidence": 0.75 if mapped_tests else (0.55 if has_graph else 0.25),
            "status": "recommended" if _yaxunit_available() else "framework_missing",
            "reason": "Проверить тесты, явно связанные с измененным объектом/модулем.",
            "command": _yaxunit_command(object_name),
        }
    )

    if impact_total >= 100 or impacted_hotspots:
        tests.append(
            {
                "id": "impact-regression",
                "framework": "YAxUnit/Vanessa",
                "selector": f"impact:{object_name}",
                "priority": "high",
                "confidence": 0.65 if impacted_hotspots else 0.45,
                "status": "recommended" if _yaxunit_available() else "framework_missing",
                "reason": (
                    f"Blast radius затрагивает {impact_total} ребер"
                    + (f" и {len(impacted_hotspots)} hotspot(ов)." if impacted_hotspots else ".")
                ),
                "command": _yaxunit_command(f"impact:{object_name}"),
            }
        )

    if performance:
        tests.append(
            {
                "id": "performance-regression",
                "framework": "ТЖ + YAxUnit",
                "selector": f"perf:{object_name}",
                "priority": "high",
                "confidence": 0.6,
                "status": "recommended",
                "reason": "В изменении или затронутых hotspot есть performance-флаги.",
                "command": "Run focused scenario under ТЖ and compare query/N+1 baseline.",
            }
        )

    if impact_total >= 300 or not has_graph:
        tests.append(
            {
                "id": "smoke-critical-path",
                "framework": "Vanessa/YAxUnit",
                "selector": f"smoke:{object_name}",
                "priority": "high" if impact_total >= 300 else "medium",
                "confidence": 0.4,
                "status": "recommended",
                "reason": "Нужен дымовой прогон критического бизнес-сценария вокруг правки.",
                "command": _yaxunit_command(f"smoke:{object_name}"),
            }
        )

    return tests


def build_change_plan(
    store,
    changed_modules: list[str],
    *,
    max_depth: int = 5,
    max_edges: int = 600,
    hotspot_limit: int = 10,
) -> dict[str, Any]:
    modules = dedupe(changed_modules)
    items: list[dict[str, Any]] = []
    all_impacted: set[str] = set()
    total_edges = 0
    unmeasured: list[str] = []

    for module_path in modules:
        quality = store.get_module_risk(module_path)
        impact = store.module_impact(module_path, max_depth=max_depth, max_edges=max_edges)
        coverage, coverage_caveat = impact_coverage(impact)
        if coverage == COVERAGE_NO_GRAPH_DATA:
            unmeasured.append(module_path)
        impacted_module_names = [m["module"] for m in impact["impacted_modules"]]
        impacted_hotspots = store.hotspots_for_graph_modules(
            impacted_module_names,
            limit=hotspot_limit,
        )

        performance = performance_risks(module_path, quality)
        for hotspot in impacted_hotspots:
            performance.extend(performance_risks(hotspot["module_path"], hotspot))
        performance = dedupe_risks(performance)

        covering_tests = select_tests_for_change(
            module_path,
            quality,
            impact,
            impacted_hotspots,
            performance,
        )

        all_impacted.update(impacted_module_names)
        total_edges += int(impact["total"])

        items.append(
            {
                "module_path": module_path,
                "canonical": impact["canonical"],
                "graph_modules": impact["graph_modules"],
                "entry_subroutines": impact["entry_subroutines"],
                "impact_total": impact["total"],
                "impact_measured": coverage == COVERAGE_IN_GRAPH,
                "coverage": coverage,
                "coverage_caveat": coverage_caveat,
                "impacted_modules": impact["impacted_modules"][:50],
                "impacted_hotspots": impacted_hotspots,
                "quality": quality,
                "changed_hotspot": quality if quality and int(quality.get("risk", 0)) >= 40 else None,
                "performance_risks": performance,
                "covering_tests": covering_tests,
            }
        )

    caveats = [
        "Call resolution favours precision over recall; dynamic Выполнить() calls are not guaranteed.",
        "Test selector uses local tests/bsl inventory when available and falls back to risk-driven recommendations.",
    ]
    if unmeasured:
        shown = ", ".join(unmeasured[:5]) + ("…" if len(unmeasured) > 5 else "")
        caveats.append(
            f"Радиус поражения НЕ измерен для {len(unmeasured)} модул(я/ей) "
            f"(нет узла в графе вызовов — обычно это формы): {shown}. "
            f"impact_total=0 для них означает «нет данных», НЕ «безопасно»."
        )

    return {
        "changed_modules": modules,
        "modules": items,
        "total_impact_edges": total_edges,
        "total_impacted_modules": len(all_impacted),
        "unmeasured_modules": unmeasured,
        "caveats": caveats,
    }


def _tokens(text: str) -> list[str]:
    values = []
    for raw in _TOKEN_RE.findall(text):
        token = raw.strip("_")
        lowered = token.lower()
        if len(token) < 4 or lowered in _COMMON_TERMS:
            continue
        values.append(token)
        if lowered != token:
            values.append(lowered)
        for suffix in ("ами", "ями", "ого", "ему", "ыми", "ими", "ая", "яя", "ое", "ые", "ий", "ый", "ов", "ев"):
            if lowered.endswith(suffix) and len(lowered) - len(suffix) >= 4:
                values.append(lowered[: -len(suffix)])
                break
    return dedupe(values)


def candidate_modules_for_requirement(store, text: str, limit: int = 8) -> list[dict[str, Any]]:
    """Find likely BSL modules touched by a business requirement."""
    scores: dict[str, dict[str, Any]] = {}
    terms = _tokens(text)
    for term in terms[:16]:
        for row in store.search(term, limit=20):
            path = row["module_path"]
            haystack = f"{path} {row.get('domain', '')}".lower()
            lexical = haystack.count(term.lower())
            if lexical <= 0:
                lexical = 1
            score = lexical * 10 + max(0, 60 - int(row.get("maintainability_score") or 0)) / 6
            current = scores.setdefault(
                path,
                {
                    "module_path": path,
                    "match_terms": set(),
                    "score": 0.0,
                    "quality": row,
                },
            )
            current["match_terms"].add(term)
            current["score"] += score

    ranked = sorted(scores.values(), key=lambda item: item["score"], reverse=True)[:limit]
    result = []
    for item in ranked:
        risk = store.get_module_risk(item["module_path"])
        result.append(
            {
                "module_path": item["module_path"],
                "match_terms": sorted(item["match_terms"]),
                "score": round(float(item["score"]), 2),
                "quality": risk or item["quality"],
            }
        )
    return result


def build_requirement_impact(
    store,
    text: str,
    *,
    limit: int = 6,
    max_depth: int = 3,
    max_edges: int = 200,
) -> dict[str, Any]:
    candidates = candidate_modules_for_requirement(store, text, limit=limit)
    modules = [item["module_path"] for item in candidates]
    plan = build_change_plan(
        store,
        modules,
        max_depth=max_depth,
        max_edges=max_edges,
        hotspot_limit=8,
    ) if modules else {
        "changed_modules": [],
        "modules": [],
        "total_impact_edges": 0,
        "total_impacted_modules": 0,
        "caveats": [],
    }
    return {
        "requirement": text,
        "candidate_modules": candidates,
        "change_plan": plan,
        "caveats": [
            "Requirement impact is lexical/local-first until requirement-to-metadata trace links are stored.",
            "Use this as a starting set for BA/architect review, not as a complete proof of scope.",
        ],
    }


def assess_ci_gate(
    plan: dict[str, Any],
    *,
    risk_threshold: int = 70,
    impact_threshold: int = 300,
    fail_on_high: bool = True,
) -> dict[str, Any]:
    violations = []
    for item in plan["modules"]:
        risk = int((item.get("quality") or {}).get("risk") or 0)
        impact = int(item.get("impact_total") or 0)
        high_perf = [
            r for r in item.get("performance_risks", [])
            if r.get("severity") == "high"
        ]
        if risk >= risk_threshold:
            violations.append(
                {
                    "module_path": item["module_path"],
                    "kind": "risk",
                    "severity": "high",
                    "value": risk,
                    "threshold": risk_threshold,
                    "message": "Высокий explainable risk измененного модуля.",
                }
            )
        if impact >= impact_threshold:
            violations.append(
                {
                    "module_path": item["module_path"],
                    "kind": "impact",
                    "severity": "high",
                    "value": impact,
                    "threshold": impact_threshold,
                    "message": "Большой blast radius для правки.",
                }
            )
        for risk_item in high_perf:
            violations.append(
                {
                    "module_path": risk_item.get("module_path") or item["module_path"],
                    "kind": risk_item.get("factor", "performance"),
                    "severity": "high",
                    "value": risk_item.get("detail", ""),
                    "threshold": "no high performance flags",
                    "message": "Performance-флаг требует focused regression.",
                }
            )
        # Unmeasured blast radius: the gate cannot assert this change is safe.
        # Surfaced as a warning (not a hard fail) so a low/zero impact_total for
        # an unresolved module is never silently read as "safe to merge".
        if item.get("coverage") == COVERAGE_NO_GRAPH_DATA:
            violations.append(
                {
                    "module_path": item["module_path"],
                    "kind": "coverage",
                    "severity": "warning",
                    "value": "no_graph_data",
                    "threshold": "module resolved to a call-graph node",
                    "message": (
                        "Радиус поражения НЕ измерен (модуль не в графе вызовов): "
                        "impact_total нельзя считать нулевым/безопасным."
                    ),
                }
            )

    has_high = any(v.get("severity") == "high" for v in violations)
    status = "pass"
    if has_high:
        status = "fail" if fail_on_high else "warn"
    elif violations:
        status = "warn"

    return {
        "status": status,
        "violations": violations,
        "summary": {
            "changed_modules": len(plan.get("changed_modules", [])),
            "total_impact_edges": plan.get("total_impact_edges", 0),
            "total_impacted_modules": plan.get("total_impacted_modules", 0),
            "violation_count": len(violations),
        },
    }


def render_markdown_report(plan: dict[str, Any], gate: dict[str, Any]) -> str:
    unmeasured = plan.get("unmeasured_modules") or []
    edges_line = f"- Impact edges (measured): {gate['summary']['total_impact_edges']}"
    if unmeasured:
        edges_line += (
            f" — внимание: {len(unmeasured)} модул(ь/я/ей) НЕ в графе вызовов, "
            f"их радиус НЕ измерен (не считать нулевым)"
        )
    lines = [
        "# 1cAI Rentgen Change Gate",
        "",
        f"Status: **{gate['status'].upper()}**",
        "",
        "## Summary",
        "",
        f"- Changed modules: {gate['summary']['changed_modules']}",
        edges_line,
        f"- Impacted modules: {gate['summary']['total_impacted_modules']}",
        f"- Gate violations: {gate['summary']['violation_count']}",
        "",
    ]

    if gate["violations"]:
        lines.extend(["## Violations", ""])
        for violation in gate["violations"]:
            severity = violation.get("severity", "high")
            if severity == "warning":
                detail = f"({violation['value']})"
            else:
                detail = f"({violation['value']} >= {violation['threshold']})"
            lines.append(
                f"- **{violation['kind']}** [{severity}] `{violation['module_path']}`: "
                f"{violation['message']} {detail}"
            )
        lines.append("")

    lines.extend(["## Module Plan", ""])
    for item in plan["modules"]:
        risk = (item.get("quality") or {}).get("risk", "n/a")
        if item.get("coverage") == COVERAGE_NO_GRAPH_DATA:
            impact_line = (
                f"- Impact edges: НЕ ИЗМЕРЕНО — {item.get('coverage_caveat') or _NO_GRAPH_CAVEAT}"
            )
        else:
            impact_line = f"- Impact edges: {item['impact_total']}"
        lines.extend(
            [
                f"### `{item['module_path']}`",
                "",
                f"- Risk: {risk}",
                impact_line,
                f"- Impacted hotspots: {len(item['impacted_hotspots'])}",
                f"- Performance risks: {len(item['performance_risks'])}",
                "- Test plan:",
            ]
        )
        for test in item["covering_tests"]:
            confidence = math.floor(float(test.get("confidence", 0)) * 100)
            lines.append(
                f"  - {test['priority']} `{test['selector']}` "
                f"({test['framework']}, confidence {confidence}%): {test['reason']}"
            )
        lines.append("")

    if plan.get("caveats"):
        lines.extend(["## Caveats", ""])
        lines.extend(f"- {caveat}" for caveat in plan["caveats"])
        lines.append("")

    return "\n".join(lines)
