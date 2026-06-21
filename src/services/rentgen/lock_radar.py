"""Technology Journal lock, timeout and deadlock radar for 1C operations."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.services.rentgen.change_plan import dedupe
from src.services.rentgen.path_safety import collect_files, confine_path
from src.services.rentgen.test_coverage_matrix import build_test_coverage_matrix
from src.services.tj_parser.parser import TJEvent, TJParser


LOCK_EVENTS = {"TLOCK", "TTIMEOUT", "TDEADLOCK"}
LOCK_EVENT_RANK = {"TDEADLOCK": 3, "TTIMEOUT": 2, "TLOCK": 1}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _context_line(frame: Any) -> str:
    return f"{frame.module}:{frame.line} -> {frame.code_fragment}"


def _module_refs(event: TJEvent) -> list[str]:
    return dedupe([frame.module for frame in event.context if frame.module])


def _severity_for_kind(kind: str) -> str:
    if kind == "TDEADLOCK":
        return "critical"
    if kind == "TTIMEOUT":
        return "high"
    return "medium"


def _event_dict(event: TJEvent) -> dict[str, Any]:
    kind = event.event_type
    modules = _module_refs(event)
    return {
        "timestamp": event.timestamp,
        "kind": kind,
        "severity": _severity_for_kind(kind),
        "duration_ms": round(event.duration_us / 1000, 3),
        "user": event.user,
        "process": event.process,
        "module_refs": modules,
        "top_module": modules[-1] if modules else "",
        "context": [_context_line(frame) for frame in event.context],
        "extra": event.extra,
    }


def _load_events(log_path: str | None) -> tuple[list[TJEvent], list[str], bool]:
    if not log_path:
        return [], ["Technology Journal path was not provided; Lock Radar is waiting for local TJ evidence."], False

    # Confine the caller-supplied path to the allowed data roots before any
    # filesystem access. A path outside them (C:\Windows, secrets, .. traversal)
    # raises ValueError, which the API maps to HTTP 400.
    path = confine_path(log_path, label="log_path")

    parser = TJParser()
    caveats: list[str] = []
    try:
        # path.exists() can itself raise PermissionError on an existing but
        # unreadable path; keep it inside the guard so it never leaks as a 500
        # existence oracle. Treat it as "no readable journal", a caveat.
        if not path.exists():
            return [], [f"Technology Journal path does not exist: {log_path}"], False
        if path.is_file():
            return parser.parse_file(path, event_filter=LOCK_EVENTS), [], True
        files, truncated = collect_files(path, suffixes={".log"}, max_files=10_000)
        if truncated:
            caveats.append(
                f"Technology Journal directory had more than 10000 .log files; "
                f"analysis was truncated and coverage is partial."
            )
        events: list[TJEvent] = []
        for log_file in sorted(files):
            events.extend(parser.parse_file(log_file, event_filter=LOCK_EVENTS))
        return events, caveats, True
    except (OSError, ValueError) as exc:
        return [], [f"Technology Journal lock analysis failed: {exc}"], False


def _module_sources(
    events: list[dict[str, Any]],
    changed_modules: list[str] | None,
    limit: int,
) -> tuple[list[str], dict[str, list[str]], dict[str, int]]:
    sources: dict[str, list[str]] = defaultdict(list)
    counts: Counter[str] = Counter()

    for module in dedupe(changed_modules or []):
        sources[module].append("operator")
        counts[module] += 0

    for item in events:
        source = str(item.get("kind") or "tj_lock").lower()
        for module in item.get("module_refs") or []:
            sources[module].append(source)
            counts[module] += 1

    ordered = sorted(sources, key=lambda module: (counts[module], module), reverse=True)
    modules = ordered[:limit]
    return modules, {module: dedupe(sources[module]) for module in modules}, dict(counts)


def _max_duration_ms(events: list[dict[str, Any]]) -> float:
    return max((float(item.get("duration_ms") or 0) for item in events), default=0.0)


def _module_plan(
    store: Any,
    modules: list[str],
    sources: dict[str, list[str]],
    event_counts: dict[str, int],
    *,
    max_depth: int,
    max_edges: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    if store is None:
        return [], ["Rentgen store is unavailable; module impact and test links are skipped."]

    rows = []
    caveats = []
    for module in modules:
        try:
            impact = store.module_impact(module, max_depth=max_depth, max_edges=max_edges)
            quality = store.get_module_risk(module)
            graph_modules = [item.get("name") for item in impact.get("graph_modules", []) if item.get("name")]
            hotspots = store.hotspots_for_graph_modules(graph_modules, limit=8) if graph_modules else []
        except Exception as exc:  # pragma: no cover - defensive integration guard
            caveats.append(f"Impact analysis failed for {module}: {exc}")
            continue

        rows.append(
            {
                "module_ref": module,
                "sources": sources.get(module, []),
                "lock_events": int(event_counts.get(module) or 0),
                "canonical": impact.get("canonical", {}),
                "graph_modules": impact.get("graph_modules", []),
                "entry_subroutines": impact.get("entry_subroutines", 0),
                "impact_total": int(impact.get("total") or 0),
                "impacted_modules": impact.get("impacted_modules", [])[:30],
                "quality": quality,
                "impacted_hotspots": hotspots,
            }
        )

    rows.sort(
        key=lambda item: (
            int(item.get("lock_events") or 0),
            int((item.get("quality") or {}).get("risk") or 0),
            int(item.get("impact_total") or 0),
        ),
        reverse=True,
    )
    return rows, caveats


def _test_matrix(
    store: Any,
    modules: list[str],
    *,
    max_depth: int,
    max_edges: int,
) -> tuple[dict[str, Any] | None, list[str]]:
    if store is None or not modules:
        return None, []
    try:
        return build_test_coverage_matrix(
            store,
            changed_modules=modules,
            max_depth=max_depth,
            max_edges=max_edges,
            hotspot_limit=8,
            match_limit=8,
        ), []
    except Exception as exc:  # pragma: no cover - defensive integration guard
        return None, [f"Test coverage matrix failed: {exc}"]


def _decision(
    *,
    available: bool,
    events: list[dict[str, Any]],
    module_plan: list[dict[str, Any]],
    test_matrix: dict[str, Any] | None,
) -> dict[str, Any]:
    locks = sum(1 for item in events if item["kind"] == "TLOCK")
    timeouts = sum(1 for item in events if item["kind"] == "TTIMEOUT")
    deadlocks = sum(1 for item in events if item["kind"] == "TDEADLOCK")
    max_duration = _max_duration_ms(events)
    max_module_risk = max((int((row.get("quality") or {}).get("risk") or 0) for row in module_plan), default=0)
    gaps = int(((test_matrix or {}).get("summary") or {}).get("gaps") or 0)

    risk_score = 0
    risk_score += min(35, locks * 5)
    risk_score += min(35, timeouts * 12)
    risk_score += 45 if deadlocks else 0
    risk_score += min(15, int(max_duration / 1000))
    risk_score += min(25, int(max_module_risk * 0.25))
    risk_score += min(15, gaps * 5)
    risk_score = min(risk_score, 100)

    if not available:
        status = "watch"
        headline = "Lock Radar is waiting for Technology Journal evidence."
    elif deadlocks:
        status = "critical"
        headline = f"Deadlocks detected: {deadlocks}; freeze risky release paths until owner review."
    elif timeouts or risk_score >= 60:
        status = "risk"
        headline = f"Lock pressure is visible: {locks} waits, {timeouts} timeouts."
    elif locks:
        status = "watch"
        headline = f"Lock waits found: {locks}; validate affected modules and tests."
    else:
        status = "ready"
        headline = "No lock waits, timeouts or deadlocks found in the supplied TJ slice."

    return {
        "status": status,
        "score": max(0, 100 - risk_score),
        "risk_score": risk_score,
        "headline": headline,
        "max_duration_ms": round(max_duration, 3),
        "max_module_risk": max_module_risk,
        "test_gaps": gaps,
    }


def _actions(
    decision: dict[str, Any],
    events: list[dict[str, Any]],
    module_plan: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    deadlocks = [item for item in events if item["kind"] == "TDEADLOCK"]
    timeouts = [item for item in events if item["kind"] == "TTIMEOUT"]
    locks = [item for item in events if item["kind"] == "TLOCK"]

    if deadlocks:
        actions.append(
            {
                "owner": "architect",
                "severity": "critical",
                "kind": "deadlock",
                "title": "Stop release gate for deadlock path",
                "target": deadlocks[0].get("top_module") or None,
                "details": {
                    "events": len(deadlocks),
                    "first_timestamp": deadlocks[0].get("timestamp"),
                    "context": deadlocks[0].get("context", [])[:3],
                },
            }
        )

    if timeouts:
        actions.append(
            {
                "owner": "platform",
                "severity": "high",
                "kind": "timeout",
                "title": "Correlate DB/platform timeout with release window and long transactions",
                "target": timeouts[0].get("top_module") or None,
                "details": {
                    "events": len(timeouts),
                    "max_duration_ms": _max_duration_ms(timeouts),
                },
            }
        )

    if locks:
        actions.append(
            {
                "owner": "developer",
                "severity": "high" if decision.get("risk_score", 0) >= 60 else "medium",
                "kind": "lock-wait",
                "title": "Review transaction scope and write order for lock wait contexts",
                "target": locks[0].get("top_module") or None,
                "details": {
                    "events": len(locks),
                    "max_duration_ms": _max_duration_ms(locks),
                },
            }
        )

    for row in module_plan[:3]:
        if int(row.get("impact_total") or 0) or int((row.get("quality") or {}).get("risk") or 0):
            actions.append(
                {
                    "owner": "qa",
                    "severity": "high" if int((row.get("quality") or {}).get("risk") or 0) >= 70 else "medium",
                    "kind": "module-impact",
                    "title": "Add regression checks around locked module impact radius",
                    "target": row.get("module_ref"),
                    "details": {
                        "impact_total": row.get("impact_total"),
                        "lock_events": row.get("lock_events"),
                        "sources": row.get("sources", []),
                    },
                }
            )

    if not actions:
        actions.append(
            {
                "owner": "ops",
                "severity": "low",
                "kind": "evidence",
                "title": "Attach a production-like TJ slice before signing operational readiness",
                "target": None,
                "details": {"reason": "No blocking evidence was supplied or detected."},
            }
        )
    return actions


def _runbook(decision: dict[str, Any]) -> list[dict[str, str]]:
    status = str(decision.get("status") or "watch")
    qa_action = "Replay concurrent write scenarios before approving the release."
    if status == "ready":
        qa_action = "Keep TJ evidence attached to the release bundle."

    return [
        {
            "phase": "Triage",
            "owner": "ops",
            "action": "Collect the same time window from rphost TJ, DB wait stats and release timeline.",
        },
        {
            "phase": "Code",
            "owner": "developer",
            "action": "Shorten transactions, make write order deterministic and isolate background jobs in affected modules.",
        },
        {
            "phase": "Architecture",
            "owner": "architect",
            "action": "Check shared registers/documents touched by the lock chain and add an explicit release gate when status is critical/risk.",
        },
        {
            "phase": "QA",
            "owner": "qa",
            "action": qa_action,
        },
    ]


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 1C Rentgen Lock Radar",
        "",
        f"Generated: {report['generated_at']}",
        f"Status: **{report['decision']['status'].upper()}** / risk **{report['decision']['risk_score']}**",
        f"Log path: `{report['source']['path']}`",
        "",
        "## Summary",
        "",
    ]
    for key, value in report["summary"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Top Events", ""])
    for item in report["events"][:10]:
        module = item.get("top_module") or "unknown"
        lines.append(f"- **{item['kind']}** {item['timestamp']} {item['duration_ms']} ms `{module}`")
    lines.extend(["", "## Actions", ""])
    for item in report["recommended_actions"]:
        lines.append(f"- **{item['severity']}** {item['owner']}: {item['title']}")
    if report["caveats"]:
        lines.extend(["", "## Caveats", ""])
        lines.extend(f"- {item}" for item in report["caveats"])
    return "\n".join(lines)


def build_lock_radar(
    store: Any = None,
    *,
    log_path: str | None = None,
    changed_modules: list[str] | None = None,
    module_limit: int = 12,
    max_depth: int = 5,
    max_edges: int = 300,
) -> dict[str, Any]:
    """Build a deterministic lock radar report from local Technology Journal logs."""

    raw_events, caveats, available = _load_events(log_path)
    events = [_event_dict(event) for event in raw_events]
    events.sort(
        key=lambda item: (
            LOCK_EVENT_RANK.get(str(item.get("kind")), 0),
            float(item.get("duration_ms") or 0),
        ),
        reverse=True,
    )
    modules, sources, event_counts = _module_sources(events, changed_modules, module_limit)
    module_rows, module_caveats = _module_plan(
        store,
        modules,
        sources,
        event_counts,
        max_depth=max_depth,
        max_edges=max_edges,
    )
    test_matrix, test_caveats = _test_matrix(store, modules, max_depth=max_depth, max_edges=max_edges)
    caveats.extend(module_caveats)
    caveats.extend(test_caveats)
    if available and not events:
        caveats.append("The supplied TJ slice contains no TLOCK, TTIMEOUT or TDEADLOCK events.")

    event_kinds = Counter(item["kind"] for item in events)
    decision = _decision(
        available=available,
        events=events,
        module_plan=module_rows,
        test_matrix=test_matrix,
    )
    report: dict[str, Any] = {
        "generated_at": _now(),
        "source": {
            "path": log_path or "",
            "available": available,
            "changed_modules": list(changed_modules or []),
        },
        "decision": decision,
        "summary": {
            "total_events": len(events),
            "lock_waits": int(event_kinds.get("TLOCK") or 0),
            "timeouts": int(event_kinds.get("TTIMEOUT") or 0),
            "deadlocks": int(event_kinds.get("TDEADLOCK") or 0),
            "modules": len(modules),
            "module_plan": len(module_rows),
            "test_gaps": decision["test_gaps"],
        },
        "modules": [
            {"module_ref": module, "sources": sources.get(module, []), "lock_events": event_counts.get(module, 0)}
            for module in modules
        ],
        "events": events[:50],
        "module_plan": module_rows,
        "test_matrix": test_matrix,
        "recommended_actions": _actions(decision, events, module_rows),
        "runbook": _runbook(decision),
        "caveats": dedupe(caveats),
    }
    report["markdown"] = _markdown(report)
    return report
