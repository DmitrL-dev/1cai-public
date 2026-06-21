"""Executive management cockpit over the local 1C delivery signals."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Callable

from src.services.rentgen.coverage_ledger import build_coverage_ledger
from src.services.rentgen.offline_readiness import build_offline_readiness
from src.services.rentgen.team_governance import build_team_governance


STATUS_SCORES = {"done": 1.0, "partial": 0.55, "planned": 0.12}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe(default: Any, fn: Callable[[], Any]) -> Any:
    try:
        return fn()
    except Exception as exc:  # pragma: no cover - defensive executive cockpit
        return {**default, "error": str(exc)} if isinstance(default, dict) else default


def _coverage_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    by_status = Counter(str(item.get("status") or "planned") for item in items)
    by_stage = Counter(str(item.get("stage") or "unknown") for item in items)
    p0 = [item for item in items if item.get("priority") == "P0"]
    # HONESTY: with no coverage items there is no real signal -> score is None
    # ("n/a"), never a fabricated 0 or 100.
    if items:
        score: int | None = round(
            sum(STATUS_SCORES.get(str(item.get("status")), 0.0) for item in items)
            / len(items) * 100
        )
    else:
        score = None
    p0_score = (
        round(sum(STATUS_SCORES.get(str(item.get("status")), 0.0) for item in p0) / len(p0) * 100)
        if p0
        else None
    )
    return {
        "total": len(items),
        "done": by_status.get("done", 0),
        "partial": by_status.get("partial", 0),
        "planned": by_status.get("planned", 0),
        "score": score,
        "p0_score": p0_score,
        "by_stage": dict(by_stage),
        "available": bool(items),
    }


def _governance_score(summary: dict[str, Any]) -> int:
    red = int(summary.get("red_areas") or 0)
    yellow = int(summary.get("yellow_areas") or 0)
    queue = int(summary.get("review_queue") or 0)
    return max(0, 100 - red * 18 - yellow * 7 - min(queue, 25))


def _status(score: int, *, store_available: bool, red_areas: int, high_hotspots: int, offline_status: str) -> str:
    if not store_available:
        return "blocked"
    if offline_status == "fail" or red_areas >= 3 or high_hotspots >= 5:
        return "critical"
    if score >= 86 and red_areas == 0:
        return "ready"
    if score >= 72:
        return "watch"
    return "risk"


def _headline(status: str) -> str:
    return {
        "ready": "Release control is healthy; keep governance snapshots current.",
        "watch": "Delivery is usable, but managers should track yellow areas and offline warnings.",
        "risk": "Management attention is required before broad release expansion.",
        "critical": "Release leadership should stop high-risk areas until owners close the queue.",
        "blocked": "Build the local Rentgen store before using executive decisions.",
    }.get(status, "Executive state is unknown.")


def _top_risks(hotspots: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    rows = []
    for item in hotspots[:limit]:
        rows.append(
            {
                "module_path": item.get("module_path"),
                "domain": item.get("domain") or "Unassigned",
                "risk": int(item.get("risk") or 0),
                "fan_in": int(item.get("fan_in") or 0),
                "maintainability": item.get("maintainability_score"),
                "reasons": item.get("reasons", []),
            }
        )
    return rows


def _workstreams(
    *,
    quality_score: int,
    governance_score: int,
    offline_score: int,
    coverage_score: int | None,
    high_hotspots: int,
) -> list[dict[str, Any]]:
    if coverage_score is None:
        coverage_status = "unknown"
    elif coverage_score >= 100:
        # "ready" only when every internal workflow is genuinely done; any open
        # (partial/planned) item keeps this at "watch" so the cockpit never reads
        # green while real gaps remain.
        coverage_status = "ready"
    else:
        coverage_status = "watch"
    return [
        {
            "id": "quality",
            "title": "Code quality",
            "score": quality_score,
            "status": "risk" if high_hotspots else ("watch" if quality_score < 70 else "ready"),
            "signal": f"{high_hotspots} high-risk hotspots",
        },
        {
            "id": "governance",
            "title": "Team governance",
            "score": governance_score,
            "status": "risk" if governance_score < 70 else ("watch" if governance_score < 86 else "ready"),
            "signal": "Ownership, SLA and release queue",
        },
        {
            "id": "offline",
            "title": "Closed contour",
            "score": offline_score,
            "status": "ready" if offline_score >= 90 else "watch",
            "signal": "Local store, metadata, ITS and external env",
        },
        {
            "id": "coverage",
            "title": "Subscription escape coverage",
            "score": coverage_score,
            "status": coverage_status,
            "signal": "Internal workflow coverage map",
        },
    ]


def _actions(
    *,
    store_available: bool,
    governance: dict[str, Any],
    offline: dict[str, Any],
    coverage: dict[str, Any],
    high_hotspots: int,
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    summary = governance.get("summary") or {}
    if not store_available:
        actions.append(
            {
                "severity": "critical",
                "owner": "platform",
                "title": "Build the local Rentgen store",
                "impact": "Executive metrics cannot be trusted without graph and quality data.",
            }
        )
    if int(summary.get("red_areas") or 0):
        actions.append(
            {
                "severity": "high",
                "owner": "delivery lead",
                "title": "Freeze red areas at the next release gate",
                "impact": "Managers get an explicit stop/go lever instead of raw code findings.",
            }
        )
    if high_hotspots:
        actions.append(
            {
                "severity": "high",
                "owner": "team leads",
                "title": "Assign high-risk hotspots to owners",
                "impact": "Reduces release regression and production incident probability.",
            }
        )
    if (offline.get("decision") or {}).get("status") != "pass":
        actions.append(
            {
                "severity": "medium",
                "owner": "platform",
                "title": "Seal the offline profile",
                "impact": "Closed-contour customers need predictable local operation.",
            }
        )
    if int(coverage.get("score") or 0) < 100:
        actions.append(
            {
                "severity": "medium",
                "owner": "product",
                "title": "Close remaining internal workflow coverage",
                "impact": "Keeps management promises aligned with implemented capabilities.",
            }
        )
    if int((governance.get("trend") or {}).get("total") or 0) == 0 and store_available:
        actions.append(
            {
                "severity": "medium",
                "owner": "delivery lead",
                "title": "Create the first governance baseline snapshot",
                "impact": "Enables trend review without external ALM dependency.",
            }
        )
    if not actions:
        actions.append(
            {
                "severity": "low",
                "owner": "management",
                "title": "Keep the weekly executive checkpoint",
                "impact": "Review score, red areas, release queue and offline warnings together.",
            }
        )
    return actions[:8]


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 1cAI Executive Dashboard",
        "",
        f"Status: **{report['decision']['status'].upper()}**",
        f"Score: **{report['decision']['score']}**",
        "",
        "## Manager Actions",
        "",
    ]
    for item in report["manager_actions"]:
        lines.append(f"- **{item['severity']}** {item['owner']}: {item['title']}")
    return "\n".join(lines)


def build_executive_dashboard(
    store: Any,
    *,
    coverage_items: list[dict[str, Any]] | None = None,
    governance_limit: int = 40,
    hotspot_limit: int = 12,
    save_snapshot: bool = False,
) -> dict[str, Any]:
    """Build a manager-facing portfolio cockpit from internal product signals."""

    store_available = store is not None
    quality = _safe(
        {"total_modules": 0, "avg_maintainability": 0, "modules_with_issues": 0, "by_domain": []},
        lambda: store.summary() if store_available else {"total_modules": 0, "avg_maintainability": 0, "modules_with_issues": 0, "by_domain": []},
    )
    stats = _safe({}, lambda: store.get_stats() if store_available else {})
    hotspots = _safe([], lambda: store.hotspots(limit=hotspot_limit, min_fan_in=0) if store_available else [])
    governance = build_team_governance(store, limit=governance_limit, save_snapshot=save_snapshot)
    offline = build_offline_readiness(strict=False, include_metadata=False)
    coverage = _coverage_summary(coverage_items or [])

    governance_summary = governance.get("summary") or {}
    offline_decision = offline.get("decision") or {}
    high_hotspots = sum(1 for item in hotspots if int(item.get("risk") or 0) >= 70)
    quality_score = max(0, min(100, round(float(quality.get("avg_maintainability") or 0))))
    gov_score = _governance_score(governance_summary)
    offline_score = int(offline_decision.get("score") or 0)
    raw_coverage = coverage.get("score")
    coverage_available = raw_coverage is not None
    coverage_score = int(raw_coverage) if coverage_available else None
    # Weighted executive score. Coverage contributes its REAL computed value
    # (never a fixed +25). When there is no coverage signal we drop its weight and
    # re-normalise the rest, instead of counting coverage as a fabricated 0/100.
    weighted = quality_score * 0.30 + gov_score * 0.25 + offline_score * 0.20
    weight_sum = 0.75
    if coverage_available:
        weighted += coverage_score * 0.25
        weight_sum += 0.25
    score = round(weighted / weight_sum)
    status = _status(
        score,
        store_available=store_available,
        red_areas=int(governance_summary.get("red_areas") or 0),
        high_hotspots=high_hotspots,
        offline_status=str(offline_decision.get("status") or "unknown"),
    )

    report = {
        "generated_at": _now(),
        "available": store_available,
        "decision": {
            "status": status,
            "score": score if store_available else 0,
            "headline": _headline(status),
            "release_policy": "Red areas are release-gate blockers; yellow areas need owner SLA.",
        },
        "kpis": {
            "modules": int(quality.get("total_modules") or 0),
            "modules_with_issues": int(quality.get("modules_with_issues") or 0),
            "avg_maintainability": quality_score,
            "red_areas": int(governance_summary.get("red_areas") or 0),
            "yellow_areas": int(governance_summary.get("yellow_areas") or 0),
            "review_queue": int(governance_summary.get("review_queue") or 0),
            "call_edges": int(stats.get("call_edges") or 0),
            "offline_score": offline_score,
            "coverage_score": coverage_score,
        },
        "risk_summary": {
            "high_hotspots": high_hotspots,
            "top_risk": max((int(item.get("risk") or 0) for item in hotspots), default=0),
            "top_risks": _top_risks(hotspots),
            "domains": quality.get("by_domain", [])[:8],
        },
        "workstreams": _workstreams(
            quality_score=quality_score,
            governance_score=gov_score,
            offline_score=offline_score,
            coverage_score=coverage_score,
            high_hotspots=high_hotspots,
        ),
        "governance": {
            "summary": governance_summary,
            "status_counts": (governance.get("release_board") or {}).get("status_counts", {}),
            "review_queue": (governance.get("release_board") or {}).get("review_queue", [])[:8],
            "trend": governance.get("trend", {}),
        },
        "coverage": coverage,
        "offline": {
            "decision": offline_decision,
            "summary": offline.get("summary", {}),
            "runtime": offline.get("runtime", {}),
        },
        "manager_actions": _actions(
            store_available=store_available,
            governance=governance,
            offline=offline,
            coverage=coverage,
            high_hotspots=high_hotspots,
        ),
        "caveats": [
            "This cockpit uses internal 1cAI signals; external ALM integration is optional customer-specific adaptation.",
            "Scores are deterministic management signals, not a substitute for formal release approval.",
        ],
    }
    report["coverage_ledger"] = build_coverage_ledger(executive=report)
    report["markdown"] = _markdown(report)
    return report
