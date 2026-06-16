"""BSL standards catalog, deterministic review and local finding storage."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.services.bsl_diagnostics import analyze_bsl

ROOT = Path(__file__).resolve().parents[3]
STORE_PATH = ROOT / "data" / "standards_findings.json"
BSL_LS_HOME = Path.home() / ".bsl-language-server"

STANDARDS_CATALOG: dict[str, dict[str, Any]] = {
    "select-star": {
        "standard": "1c:query-fields-explicit",
        "title": "Query fields must be explicit",
        "severity": "medium",
        "autofix": "Replace SELECT * with explicit fields from metadata/query context.",
        "autofix_confidence": 0.35,
    },
    "query-in-loop": {
        "standard": "1c:query-performance",
        "title": "Do not construct or execute queries inside loops",
        "severity": "high",
        "autofix": "Move query construction outside the loop or batch input values into one query.",
        "autofix_confidence": 0.25,
    },
    "privileged-mode": {
        "standard": "1c:security-privileged-mode",
        "title": "Privileged mode needs explicit security justification",
        "severity": "high",
        "autofix": "Replace broad privileged mode with a narrow service operation and documented reason.",
        "autofix_confidence": 0.2,
    },
    "dynamic-execute": {
        "standard": "1c:security-no-dynamic-execute",
        "title": "Dynamic Execute complicates security and impact analysis",
        "severity": "high",
        "autofix": "Replace dynamic code execution with explicit procedure/function calls.",
        "autofix_confidence": 0.15,
    },
    "empty-catch": {
        "standard": "1c:errors-observable",
        "title": "Exception handlers must be observable",
        "severity": "high",
        "autofix": "Log the exception and return an explicit failure result.",
        "autofix_confidence": 0.55,
    },
    "undocumented-export": {
        "standard": "1c:export-contract-docs",
        "title": "Exported procedures/functions need contract comments",
        "severity": "low",
        "autofix": "Add a short contract comment with purpose, parameters and return value.",
        "autofix_confidence": 0.75,
    },
    "deep-nesting": {
        "standard": "1c:maintainability-flat-flow",
        "title": "Deep nesting should be decomposed",
        "severity": "medium",
        "autofix": "Extract nested branches into named helper procedures/functions.",
        "autofix_confidence": 0.4,
    },
    "magic-numbers": {
        "standard": "1c:readability-named-constants",
        "title": "Numeric literals should be named or explained",
        "severity": "low",
        "autofix": "Introduce named constants or comments for business thresholds.",
        "autofix_confidence": 0.65,
    },
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _graph_resolution(module_path: str | None) -> dict[str, Any]:
    """Check whether a module reference resolves in the real Рентген graph.

    HONESTY guard: standards findings must never be presented for a module that
    does not exist in the analysed configuration. We resolve the path against the
    live SQLite graph; ``resolved`` is only ``True`` when the graph actually
    contains matching modules (``graph_modules > 0``). When the store is not
    built we return ``resolved=None`` (unknown) and refuse to persist named-module
    findings rather than fabricate a positive result.
    """

    result: dict[str, Any] = {
        "module_path": module_path,
        "resolved": None,
        "graph_modules": 0,
        "source": "no-store",
    }
    if not module_path:
        # Ad-hoc pasted code has no module identity; it is never persisted as a
        # configuration finding, so resolution does not apply.
        result["source"] = "pasted-code"
        return result
    try:
        # Imported lazily so this module stays importable without tools/ on the
        # path (e.g. pure-diagnostics usage) and to avoid a heavy import cycle.
        from src.api._rentgen_store import store_or_none
    except Exception:  # pragma: no cover - defensive import guard
        return result
    store = store_or_none()
    if store is None:
        return result
    try:
        resolved = store.resolve_module(module_path)
    except Exception as exc:  # pragma: no cover - defensive runtime guard
        result["source"] = "resolve-error"
        result["error"] = str(exc)
        return result
    graph_modules = resolved.get("graph_modules") or []
    result["graph_modules"] = len(graph_modules)
    result["resolved"] = len(graph_modules) > 0
    result["source"] = (resolved.get("canonical") or {}).get("source", "graph")
    return result


def _bsl_language_server_probe() -> dict[str, Any]:
    candidates = [
        Path(str(path))
        for path in [
            ROOT / "tools" / "bsl-language-server" / "bsl-language-server.jar",
            BSL_LS_HOME / "bsl-language-server.jar",
            BSL_LS_HOME / "cache",
        ]
    ]
    existing = [path for path in candidates if path.exists()]
    return {
        "available": any(path.suffix == ".jar" for path in existing),
        "home": str(BSL_LS_HOME),
        "detected_paths": [str(path) for path in existing],
        "mode": "fallback" if not any(path.suffix == ".jar" for path in existing) else "detected",
    }


def _catalog_item(code: str) -> dict[str, Any]:
    return STANDARDS_CATALOG.get(
        code,
        {
            "standard": f"1c:{code}",
            "title": code,
            "severity": "medium",
            "autofix": "Review manually.",
            "autofix_confidence": 0.1,
        },
    )


def _finding(module_path: str | None, diagnostic: dict[str, Any]) -> dict[str, Any]:
    code = diagnostic["code"]
    item = _catalog_item(code)
    return {
        "module_path": module_path or "",
        "source": diagnostic["source"],
        "rule_id": code,
        "standard": item["standard"],
        "severity": diagnostic.get("severity") or item["severity"],
        "line": diagnostic.get("line"),
        "message": diagnostic.get("message") or item["title"],
        "title": item["title"],
        "details": diagnostic.get("details", {}),
        "autofix": {
            "available": item["autofix_confidence"] >= 0.3,
            "confidence": item["autofix_confidence"],
            "description": item["autofix"],
        },
    }


def _summary(findings: list[dict[str, Any]], metrics: dict[str, Any]) -> dict[str, Any]:
    by_severity = Counter(item["severity"] for item in findings)
    by_standard = Counter(item["standard"] for item in findings)
    return {
        "findings": len(findings),
        "by_severity": dict(by_severity),
        "by_standard": dict(by_standard),
        "autofixable": sum(1 for item in findings if item.get("autofix", {}).get("available")),
        "loc": metrics.get("loc", 0),
        "functions": metrics.get("functions", 0),
        "procedures": metrics.get("procedures", 0),
        "metadata_refs": metrics.get("metadata_refs", 0),
    }


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# BSL Standards Review",
        "",
        f"Module: `{report['module_path'] or 'pasted-code'}`",
        f"Findings: **{report['summary']['findings']}**",
        f"Autofixable: **{report['summary']['autofixable']}**",
        "",
    ]
    if report["findings"]:
        lines.extend(["## Findings", ""])
        for item in report["findings"]:
            line = f":{item['line']}" if item.get("line") else ""
            lines.append(
                f"- **{item['severity']}** `{item['rule_id']}`{line}: {item['message']} "
                f"({item['standard']})"
            )
    else:
        lines.append("No standards findings.")
    return "\n".join(lines)


def review_bsl_standards(
    code: str,
    *,
    module_path: str | None = None,
    max_nesting_threshold: int = 5,
) -> dict[str, Any]:
    """Run offline deterministic standards review with catalog metadata."""

    diagnostics = analyze_bsl(
        code,
        module_path=module_path,
        max_nesting_threshold=max_nesting_threshold,
    )
    findings = [_finding(module_path, diagnostic) for diagnostic in diagnostics["diagnostics"]]
    resolution = _graph_resolution(module_path)
    caveats = [
        "Fallback standards review is deterministic and offline.",
        "Install bsl-language-server jar to add full 1C-Syntax diagnostics.",
    ]
    if module_path and resolution["resolved"] is False:
        caveats.append(
            "Module does not resolve in the Рентген graph (graph_modules=0); "
            "findings are not persisted as configuration analysis."
        )
    elif module_path and resolution["resolved"] is None:
        caveats.append(
            "Рентген graph store is unavailable; module resolution could not be "
            "verified, so findings are not persisted as configuration analysis."
        )
    report = {
        "generated_at": _now(),
        "module_path": module_path,
        "engine": "fallback",
        "bsl_language_server": _bsl_language_server_probe(),
        "resolution": resolution,
        "catalog": list(STANDARDS_CATALOG.values()),
        "findings": findings,
        "diagnostics": diagnostics,
        "summary": _summary(findings, diagnostics["metrics"]),
        "caveats": caveats,
    }
    report["markdown"] = _markdown(report)
    return report


def _load(path: Path | None = None) -> list[dict[str, Any]]:
    target = path or STORE_PATH
    if not target.exists():
        return []
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    items = payload.get("items", []) if isinstance(payload, dict) else payload
    return items if isinstance(items, list) else []


def _write(items: list[dict[str, Any]], path: Path | None = None) -> None:
    target = path or STORE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(json.dumps({"items": items}, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(target)


def save_standards_review(report: dict[str, Any], path: Path | None = None) -> dict[str, Any]:
    """Persist findings by module path for team review dashboards.

    HONESTY guard: refuse to store findings for a module that does not resolve in
    the Рентген graph (``graph_modules == 0``) or that cannot be verified because
    the graph store is unavailable. Persisting such findings would surface them in
    the team dashboard as real configuration analysis for a module that does not
    exist in the analysed code — exactly the fabricated-data failure we forbid.
    """

    module_path = report.get("module_path")
    resolution = report.get("resolution") or _graph_resolution(module_path)

    if module_path and resolution.get("resolved") is not True:
        # Do NOT write anything; return a transparent skipped result.
        reason = (
            "module_not_in_graph"
            if resolution.get("resolved") is False
            else "graph_store_unavailable"
        )
        return {
            "module_path": module_path,
            "persisted": False,
            "status": "not_available",
            "reason": reason,
            "resolution": resolution,
            "message": (
                f"Findings for '{module_path}' were not stored: the module does not "
                f"resolve in the Рентген graph (graph_modules="
                f"{resolution.get('graph_modules', 0)}). Standards findings are only "
                "persisted for modules that exist in the analysed configuration."
            ),
        }

    items = _load(path)
    stored = {
        "module_path": module_path or "pasted-code",
        "updated_at": report["generated_at"],
        "persisted": True,
        "resolution": resolution,
        "summary": report["summary"],
        "findings": report["findings"],
        "markdown": report["markdown"],
    }
    for index, item in enumerate(items):
        if item.get("module_path") == stored["module_path"]:
            items[index] = stored
            break
    else:
        items.insert(0, stored)
    items.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
    _write(items, path)
    return stored


def list_standards_findings(
    *, module_path: str | None = None, limit: int = 100, path: Path | None = None
) -> dict[str, Any]:
    """List persisted standards findings, optionally filtered by module."""

    items = _load(path)
    if module_path:
        needle = module_path.casefold()
        items = [item for item in items if needle in str(item.get("module_path", "")).casefold()]
    return {
        "items": items[: max(1, limit)],
        "total": len(items),
        "path": str(path or STORE_PATH),
        "source": "locally_persisted_reviews",
        "note": (
            "Empty until a standards review is run and saved for a module that "
            "resolves in the Рентген graph; no seed/fabricated findings are served."
            if not items
            else "Findings are persisted only for modules that resolve in the Рентген graph."
        ),
    }
