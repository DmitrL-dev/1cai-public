"""Operations incident-to-code workflow for the Rentgen graph."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.services.rentgen.change_plan import dedupe
from src.services.rentgen.team_governance import build_team_governance
from src.services.rentgen.test_coverage_matrix import build_test_coverage_matrix


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hotspot_dict(item: Any) -> dict[str, Any]:
    return {
        "module": item.module,
        "line": item.line,
        "code_fragment": item.code_fragment,
        "sdbl": item.sdbl,
        "total_calls": item.total_calls,
        "total_duration_ms": item.total_duration_ms,
        "max_duration_us": item.max_duration_us,
        "avg_rows": item.avg_rows,
        "is_in_loop": item.is_in_loop,
    }


def _tj_report_dict(report: Any | None, error: str | None = None) -> dict[str, Any]:
    if report is None:
        return {
            "available": False,
            "error": error,
            "total_events": 0,
            "total_duration_ms": 0.0,
            "hotspots": [],
            "n_plus_one": [],
            "lock_waits_count": 0,
            "deadlocks_count": 0,
        }
    return {
        "available": True,
        "error": None,
        "total_events": report.total_events,
        "total_duration_ms": report.total_duration_ms,
        "hotspots": [_hotspot_dict(item) for item in report.hotspots],
        "n_plus_one": [_hotspot_dict(item) for item in report.n_plus_one],
        "lock_waits_count": len(report.lock_waits),
        "deadlocks_count": len(report.deadlocks),
    }


def _analyze_tj(
    log_path: str | None, min_duration_ms: float, top_n: int
) -> tuple[Any | None, list[str]]:
    if not log_path:
        return None, [
            "No Technology Journal path was provided; report is based on symptoms and supplied modules."
        ]

    path = Path(log_path)
    if not path.exists():
        return None, [f"Technology Journal path does not exist: {log_path}"]

    from src.services.tj_parser.analyzer import TJPerformanceAnalyzer

    try:
        analyzer = TJPerformanceAnalyzer(min_duration_ms=min_duration_ms)
        return analyzer.analyze(str(path), top_n=top_n), []
    except (OSError, ValueError) as exc:
        return None, [f"Technology Journal analysis failed: {exc}"]


_SYMPTOM_RULES = (
    ("deadlock", "critical", "Deadlock or mutual lock symptom"),
    ("lock", "high", "Lock wait symptom"),
    ("timeout", "high", "Timeout symptom"),
    ("slow", "high", "Slow operation symptom"),
    ("performance", "high", "Performance degradation symptom"),
    ("query", "medium", "Query degradation symptom"),
    ("error", "medium", "Application error symptom"),
    ("failure", "medium", "Business operation failure symptom"),
    ("data", "medium", "Data consistency symptom"),
)


def _symptom_signals(
    description: str | None, symptoms: list[str] | None
) -> list[dict[str, Any]]:
    text = " ".join([description or "", *(symptoms or [])]).casefold()
    signals = []
    seen = set()
    for token, severity, title in _SYMPTOM_RULES:
        if token in text and token not in seen:
            seen.add(token)
            signals.append(
                {
                    "kind": "symptom",
                    "severity": severity,
                    "title": title,
                    "evidence": {"token": token},
                }
            )
    return signals


def _module_from_stack_line(line: str) -> str | None:
    module = line.split(":", 1)[0].strip()
    return module or None


def _candidate_modules(
    changed_modules: list[str] | None,
    tj_report: Any | None,
    *,
    limit: int,
) -> tuple[list[str], dict[str, list[str]], dict[str, list[dict[str, Any]]]]:
    sources: dict[str, list[str]] = defaultdict(list)
    hotspot_by_module: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for module in dedupe(changed_modules or []):
        sources[module].append("operator")

    if tj_report is not None:
        for hotspot in tj_report.hotspots:
            sources[hotspot.module].append("tj_hotspot")
            hotspot_by_module[hotspot.module].append(_hotspot_dict(hotspot))
        for hotspot in tj_report.n_plus_one:
            sources[hotspot.module].append("n_plus_one")
            hotspot_by_module[hotspot.module].append(_hotspot_dict(hotspot))
        for lock in [*tj_report.lock_waits, *tj_report.deadlocks]:
            for stack_line in lock.get("context", []):
                module = _module_from_stack_line(str(stack_line))
                if module:
                    sources[module].append("lock_context")

    modules = list(sources.keys())[:limit]
    return (
        modules,
        {key: dedupe(value) for key, value in sources.items()},
        hotspot_by_module,
    )


def _build_team_context(
    store: Any, include_team: bool
) -> tuple[dict[str, Any] | None, dict[str, dict[str, Any]], list[str]]:
    if store is None or not include_team:
        return None, {}, []
    try:
        governance = build_team_governance(store, limit=40)
    except Exception as exc:  # pragma: no cover - defensive integration guard
        return None, {}, [f"Team governance context failed: {exc}"]
    owners = {
        area["domain"]: area.get("owner", {}) for area in governance.get("areas", [])
    }
    return governance, owners, []


def _owner_for_quality(
    quality: dict[str, Any] | None, owners: dict[str, dict[str, Any]]
) -> dict[str, Any] | None:
    if not quality:
        return None
    return owners.get(str(quality.get("domain") or ""))


def _module_plan(
    store: Any,
    modules: list[str],
    sources: dict[str, list[str]],
    hotspot_by_module: dict[str, list[dict[str, Any]]],
    owners: dict[str, dict[str, Any]],
    *,
    max_depth: int,
    max_edges: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    if store is None:
        return [], [
            "Rentgen store is unavailable; module impact and owner routing are skipped."
        ]

    rows = []
    caveats = []
    for module in modules:
        try:
            impact = store.module_impact(
                module, max_depth=max_depth, max_edges=max_edges
            )
            quality = store.get_module_risk(module)
            graph_modules = [
                item.get("name")
                for item in impact.get("graph_modules", [])
                if item.get("name")
            ]
            impacted_hotspots = (
                store.hotspots_for_graph_modules(graph_modules, limit=8)
                if graph_modules
                else []
            )
        except Exception as exc:  # pragma: no cover - defensive per-module guard
            caveats.append(f"Impact analysis failed for {module}: {exc}")
            continue

        rows.append(
            {
                "module_ref": module,
                "sources": sources.get(module, []),
                "canonical": impact.get("canonical", {}),
                "graph_modules": impact.get("graph_modules", []),
                "entry_subroutines": impact.get("entry_subroutines", 0),
                "impact_total": int(impact.get("total") or 0),
                "impacted_modules": impact.get("impacted_modules", [])[:30],
                "quality": quality,
                "owner": _owner_for_quality(quality, owners),
                "tj_hotspots": hotspot_by_module.get(module, []),
                "impacted_hotspots": impacted_hotspots,
            }
        )

    rows.sort(
        key=lambda item: (
            int((item.get("quality") or {}).get("risk") or 0),
            int(item.get("impact_total") or 0),
            len(item.get("tj_hotspots") or []),
        ),
        reverse=True,
    )
    return rows, caveats


def _build_test_context(
    store: Any,
    modules: list[str],
    *,
    max_depth: int,
    max_edges: int,
) -> tuple[dict[str, Any] | None, list[str]]:
    if store is None or not modules:
        return None, []
    try:
        return (
            build_test_coverage_matrix(
                store,
                changed_modules=modules,
                max_depth=max_depth,
                max_edges=max_edges,
                hotspot_limit=8,
                match_limit=8,
            ),
            [],
        )
    except Exception as exc:  # pragma: no cover - defensive integration guard
        return None, [f"Test coverage matrix failed: {exc}"]


def _score_and_status(
    tj: dict[str, Any],
    signals: list[dict[str, Any]],
    module_rows: list[dict[str, Any]],
    test_matrix: dict[str, Any] | None,
) -> dict[str, Any]:
    max_risk = max(
        (int((row.get("quality") or {}).get("risk") or 0) for row in module_rows),
        default=0,
    )
    total_impact = sum(int(row.get("impact_total") or 0) for row in module_rows)
    gaps = int(((test_matrix or {}).get("summary") or {}).get("gaps") or 0)

    score = 0
    score += min(30, len(tj.get("hotspots") or []) * 7)
    score += 25 if tj.get("n_plus_one") else 0
    score += 35 if int(tj.get("deadlocks_count") or 0) else 0
    score += min(25, int(tj.get("lock_waits_count") or 0) * 5)
    score += min(30, int(total_impact / 12))
    score += min(35, int(max_risk * 0.35))
    score += min(15, gaps * 5)
    for signal in signals:
        score += {"critical": 25, "high": 15, "medium": 8, "low": 3}.get(
            signal.get("severity"), 3
        )
    score = min(score, 100)

    if score >= 80:
        status = "critical"
    elif score >= 60:
        status = "high"
    elif score >= 35:
        status = "medium"
    else:
        status = "low"

    return {
        "status": status,
        "severity_score": score,
        "max_module_risk": max_risk,
        "total_impact_edges": total_impact,
        "test_gaps": gaps,
    }


def _tj_signals(tj: dict[str, Any]) -> list[dict[str, Any]]:
    signals = []
    if int(tj.get("deadlocks_count") or 0):
        signals.append(
            {
                "kind": "tj_deadlock",
                "severity": "critical",
                "title": "Deadlocks detected in Technology Journal",
                "evidence": {"count": tj["deadlocks_count"]},
            }
        )
    if int(tj.get("lock_waits_count") or 0):
        signals.append(
            {
                "kind": "tj_lock",
                "severity": "high",
                "title": "Lock waits detected in Technology Journal",
                "evidence": {"count": tj["lock_waits_count"]},
            }
        )
    if tj.get("n_plus_one"):
        signals.append(
            {
                "kind": "tj_n_plus_one",
                "severity": "high",
                "title": "N+1 query pattern detected",
                "evidence": {"count": len(tj["n_plus_one"])},
            }
        )
    if tj.get("hotspots"):
        signals.append(
            {
                "kind": "tj_hotspot",
                "severity": "high",
                "title": "Slow query hotspots detected",
                "evidence": {"count": len(tj["hotspots"])},
            }
        )
    return signals


def _recommended_actions(
    tj: dict[str, Any],
    module_rows: list[dict[str, Any]],
    test_matrix: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    if int(tj.get("deadlocks_count") or 0):
        actions.append(
            {
                "owner": "ops",
                "severity": "critical",
                "kind": "stabilize",
                "title": "Freeze conflicting scheduled jobs and capture lock context",
                "target": None,
                "details": {"deadlocks": tj["deadlocks_count"]},
            }
        )
    if int(tj.get("lock_waits_count") or 0):
        actions.append(
            {
                "owner": "ops",
                "severity": "high",
                "kind": "lock-triage",
                "title": "Identify blocking sessions and long transactions",
                "target": None,
                "details": {"lock_waits": tj["lock_waits_count"]},
            }
        )
    for hotspot in tj.get("hotspots", [])[:5]:
        actions.append(
            {
                "owner": "developer",
                "severity": "high" if hotspot.get("is_in_loop") else "medium",
                "kind": "query-fix",
                "title": "Review slow query hotspot",
                "target": f"{hotspot.get('module')}:{hotspot.get('line')}",
                "details": {
                    "total_duration_ms": hotspot.get("total_duration_ms"),
                    "total_calls": hotspot.get("total_calls"),
                    "avg_rows": hotspot.get("avg_rows"),
                },
            }
        )

    for row in module_rows[:8]:
        risk = int((row.get("quality") or {}).get("risk") or 0)
        impact = int(row.get("impact_total") or 0)
        if risk >= 70 or impact >= 300:
            owner = (row.get("owner") or {}).get("name") or "lead"
            actions.append(
                {
                    "owner": owner,
                    "severity": "high" if risk >= 80 or impact >= 300 else "medium",
                    "kind": "code-owner",
                    "title": "Route incident fix through owner review",
                    "target": row.get("module_ref"),
                    "details": {"risk": risk, "impact_edges": impact},
                }
            )

    for item in ((test_matrix or {}).get("modules") or [])[:8]:
        if item.get("coverage_status") != "covered":
            actions.append(
                {
                    "owner": "qa",
                    "severity": "high" if item.get("priority") == "high" else "medium",
                    "kind": "regression-test",
                    "title": "Create or run focused incident regression",
                    "target": item.get("module_path"),
                    "details": {
                        "coverage_status": item.get("coverage_status"),
                        "commands": item.get("commands", [])[:2],
                    },
                }
            )

    if not actions:
        actions.append(
            {
                "owner": "ops",
                "severity": "low",
                "kind": "baseline",
                "title": "Keep incident watch and compare next baseline",
                "target": None,
                "details": {},
            }
        )
    return actions[:20]


def _runbook(decision: dict[str, Any]) -> list[dict[str, str]]:
    status = decision["status"]
    return [
        {
            "phase": "0-15 min",
            "owner": "ops",
            "action": "Preserve TJ/log bundle, active sessions, cluster counters and exact user scenario.",
        },
        {
            "phase": "15-45 min",
            "owner": "developer",
            "action": "Open top impacted module, reproduce focused path and prepare minimal fix or rollback toggle.",
        },
        {
            "phase": "45-90 min",
            "owner": "qa",
            "action": "Run risk-driven test commands and one scenario under Technology Journal.",
        },
        {
            "phase": "postmortem",
            "owner": "lead",
            "action": f"Record status {status}, owner route, root cause, preventive test and release gate change.",
        },
    ]


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 1cAI Incident Response",
        "",
        f"Incident: **{report['incident']['title']}**",
        f"Severity: **{report['decision']['status'].upper()}** ({report['decision']['severity_score']}/100)",
        "",
        "## Summary",
        "",
        f"- TJ events: {report['summary']['tj_events']}",
        f"- Hotspots: {report['summary']['hotspots']}",
        f"- Deadlocks: {report['summary']['deadlocks']}",
        f"- Modules in plan: {report['summary']['modules']}",
        f"- Impact edges: {report['summary']['total_impact_edges']}",
        f"- Test gaps: {report['summary']['test_gaps']}",
        "",
        "## Actions",
        "",
    ]
    for action in report["recommended_actions"][:10]:
        target = f" `{action['target']}`" if action.get("target") else ""
        lines.append(
            f"- **{action['severity']}** {action['owner']}: {action['title']}{target}"
        )
    if report["module_plan"]:
        lines.extend(["", "## Top Modules", ""])
        for row in report["module_plan"][:8]:
            risk = (row.get("quality") or {}).get("risk", "n/a")
            lines.append(
                f"- `{row['module_ref']}`: risk {risk}, impact {row['impact_total']}"
            )
    return "\n".join(lines)


def build_incident_report(
    store: Any,
    *,
    incident_title: str = "Production incident",
    description: str | None = None,
    symptoms: list[str] | None = None,
    log_path: str | None = None,
    changed_modules: list[str] | None = None,
    min_duration_ms: float = 100.0,
    top_n: int = 20,
    module_limit: int = 12,
    max_depth: int = 5,
    max_edges: int = 300,
    include_team: bool = True,
) -> dict[str, Any]:
    """Build an incident-to-code report from TJ logs, symptoms and module hints."""

    caveats: list[str] = []
    tj_report, tj_caveats = _analyze_tj(log_path, min_duration_ms, top_n)
    caveats.extend(tj_caveats)
    tj = _tj_report_dict(tj_report, tj_caveats[0] if tj_caveats else None)

    modules, sources, hotspot_by_module = _candidate_modules(
        changed_modules,
        tj_report,
        limit=max(1, module_limit),
    )
    governance, owners, team_caveats = _build_team_context(store, include_team)
    caveats.extend(team_caveats)
    module_rows, module_caveats = _module_plan(
        store,
        modules,
        sources,
        hotspot_by_module,
        owners,
        max_depth=max_depth,
        max_edges=max_edges,
    )
    caveats.extend(module_caveats)
    test_matrix, test_caveats = _build_test_context(
        store,
        modules,
        max_depth=max_depth,
        max_edges=max_edges,
    )
    caveats.extend(test_caveats)

    signals = [*_symptom_signals(description, symptoms), *_tj_signals(tj)]
    decision = _score_and_status(tj, signals, module_rows, test_matrix)
    actions = _recommended_actions(tj, module_rows, test_matrix)
    owner_counts = Counter(
        (row.get("owner") or {}).get("name") or "unassigned" for row in module_rows
    )

    report = {
        "generated_at": _now(),
        "incident": {
            "title": incident_title,
            "description": description or "",
            "symptoms": symptoms or [],
            "log_path": log_path,
        },
        "decision": decision,
        "summary": {
            "tj_events": tj["total_events"],
            "tj_duration_ms": tj["total_duration_ms"],
            "hotspots": len(tj["hotspots"]),
            "n_plus_one": len(tj["n_plus_one"]),
            "lock_waits": tj["lock_waits_count"],
            "deadlocks": tj["deadlocks_count"],
            "modules": len(module_rows),
            "owner_areas": len(owner_counts),
            "total_impact_edges": decision["total_impact_edges"],
            "test_actions": len(((test_matrix or {}).get("modules") or [])),
            "test_gaps": decision["test_gaps"],
        },
        "signals": signals,
        "tj_report": tj,
        "module_plan": module_rows,
        "test_matrix": test_matrix,
        "team_governance": {
            "included": governance is not None,
            "summary": (governance or {}).get("summary", {}),
            "owner_counts": dict(owner_counts),
        },
        "recommended_actions": actions,
        "runbook": _runbook(decision),
        "caveats": caveats,
    }
    report["markdown"] = _markdown(report)
    return report
