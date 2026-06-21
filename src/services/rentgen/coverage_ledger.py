"""Shared evidence coverage ledger for buyer-facing Rentgen reports."""

from __future__ import annotations

from typing import Any


GOOD_STATUSES = {"ready", "pass", "ok", "covered", "done"}
PARTIAL_STATUSES = {"watch", "partial", "warn", "planned"}
BAD_STATUSES = {"risk", "critical", "blocked", "fail", "missing", "unknown"}


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _score_for_status(status: str) -> int:
    folded = status.casefold()
    if folded in GOOD_STATUSES:
        return 100
    if folded in PARTIAL_STATUSES:
        return 55
    if folded in BAD_STATUSES:
        return 0
    return 35


def _status_for_score(score: int) -> str:
    if score >= 86:
        return "ready"
    if score >= 55:
        return "partial"
    return "unknown"


def _add_item(
    items: list[dict[str, Any]],
    *,
    id: str,
    title: str,
    status: str,
    score: int | None = None,
    source: str,
    evidence: str,
    caveat: str | None = None,
) -> None:
    actual_score = _score_for_status(status) if score is None else max(0, min(100, score))
    normalized_status = status or _status_for_score(actual_score)
    items.append(
        {
            "id": id,
            "title": title,
            "status": normalized_status,
            "score": actual_score,
            "measured": normalized_status.casefold() in GOOD_STATUSES | PARTIAL_STATUSES,
            "source": source,
            "evidence": evidence,
            "caveat": caveat,
        }
    )


def _executive_items(executive: dict[str, Any], items: list[dict[str, Any]]) -> None:
    available = bool(executive.get("available", True))
    kpis = executive.get("kpis") or {}
    coverage = executive.get("coverage") or {}
    offline = executive.get("offline") or {}
    decision = executive.get("decision") or {}
    risk_summary = executive.get("risk_summary") or {}

    _add_item(
        items,
        id="local-store",
        title="Local Rentgen store",
        status="ready" if available else "blocked",
        source="executive.available",
        evidence=f"{_int(kpis.get('modules'))} modules, {_int(kpis.get('call_edges'))} call edges",
        caveat=None if available else "Local graph/quality store is not built; buyer claims must stay blocked.",
    )
    coverage_score = coverage.get("score")
    _add_item(
        items,
        id="workflow-coverage",
        title="Product workflow coverage",
        status="ready" if coverage_score == 100 else "partial" if coverage_score is not None else "unknown",
        score=coverage_score if coverage_score is not None else 0,
        source="executive.coverage",
        evidence=f"{coverage.get('done', 0)}/{coverage.get('total', 0)} workflow items done",
        caveat=None if coverage_score == 100 else "Some product workflows are partial/planned; show caveat before purchase or release claim.",
    )
    offline_decision = offline.get("decision") or {}
    offline_status = str(offline_decision.get("status") or "unknown")
    _add_item(
        items,
        id="offline-profile",
        title="Closed-contour profile",
        status="ready" if offline_status == "pass" else offline_status,
        score=_int(offline_decision.get("score")),
        source="executive.offline",
        evidence=f"offline status {offline_status}",
        caveat=None if offline_status == "pass" else "Offline readiness is not fully green; keep external dependency caveats visible.",
    )
    decision_status = str(decision.get("status") or "unknown")
    _add_item(
        items,
        id="release-decision",
        title="Executive release decision",
        status=decision_status,
        score=_int(decision.get("score")),
        source="executive.decision",
        evidence=str(decision.get("headline") or "No headline"),
        caveat=None if decision_status == "ready" else "Release decision is not ready; route buyer to proof or hardening motion.",
    )
    high_hotspots = _int(risk_summary.get("high_hotspots"))
    _add_item(
        items,
        id="risk-hotspots",
        title="High-risk hotspots",
        status="ready" if high_hotspots == 0 else "risk",
        score=max(0, 100 - high_hotspots * 20),
        source="executive.risk_summary",
        evidence=f"{high_hotspots} high-risk hotspots",
        caveat=None if high_hotspots == 0 else "High-risk code hotspots must stay visible in role reports and release gates.",
    )


def _intake_items(intake: dict[str, Any], items: list[dict[str, Any]]) -> None:
    if not intake:
        return
    decision = intake.get("decision") or {}
    _add_item(
        items,
        id="configuration-intake",
        title="Configuration intake",
        status=str(decision.get("status") or "unknown"),
        score=_int(decision.get("score")),
        source="intake.decision",
        evidence=str(decision.get("headline") or "No intake headline"),
        caveat=None if decision.get("status") == "ready" else "Configuration intake is partial; source coverage limits all downstream claims.",
    )
    for row in list(intake.get("coverage") or [])[:8]:
        caveat = row.get("caveat")
        _add_item(
            items,
            id=f"intake-{row.get('id')}",
            title=str(row.get("title") or row.get("id") or "Intake source"),
            status=str(row.get("status") or "unknown"),
            source="intake.coverage",
            evidence=f"{row.get('count', 0)} source files",
            caveat=str(caveat) if caveat else None,
        )


def _platform_items(platform: dict[str, Any], items: list[dict[str, Any]]) -> None:
    if not platform:
        return
    decision = platform.get("decision") or {}
    _add_item(
        items,
        id="platform-doctor",
        title="Platform Doctor",
        status=str(decision.get("status") or "unknown"),
        score=_int(decision.get("score")),
        source="platform.decision",
        evidence=str(decision.get("headline") or "No platform headline"),
        caveat=None if decision.get("status") == "ready" else "Platform facts are incomplete or risky; do not sell upgrade readiness as green.",
    )
    for row in list(platform.get("checks") or [])[:8]:
        caveat = None if row.get("status") == "pass" else row.get("action")
        _add_item(
            items,
            id=f"platform-{row.get('id')}",
            title=str(row.get("title") or row.get("id") or "Platform check"),
            status=str(row.get("status") or "unknown"),
            source="platform.checks",
            evidence=str(row.get("evidence") or ""),
            caveat=str(caveat) if caveat else None,
        )


def build_coverage_ledger(
    *,
    executive: dict[str, Any] | None = None,
    intake: dict[str, Any] | None = None,
    platform: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return one normalized coverage/caveat ledger for buyer-facing surfaces."""

    items: list[dict[str, Any]] = []
    if executive:
        _executive_items(executive, items)
    if intake:
        _intake_items(intake, items)
    if platform:
        _platform_items(platform, items)

    if not items:
        _add_item(
            items,
            id="no-inputs",
            title="No coverage inputs",
            status="unknown",
            source="coverage-ledger",
            evidence="No executive, intake or platform report was provided.",
            caveat="Coverage is not measured; do not treat missing data as safe.",
        )

    measured = sum(1 for item in items if item["measured"])
    unknown = len(items) - measured
    ready = sum(1 for item in items if item["status"] in GOOD_STATUSES)
    partial = sum(1 for item in items if item["status"] in PARTIAL_STATUSES)
    risk = len(items) - ready - partial
    score = round(sum(_int(item.get("score")) for item in items) / len(items))
    caveats = [str(item["caveat"]) for item in items if item.get("caveat")]
    status = "ready" if risk == 0 and partial == 0 else "partial" if measured else "unknown"
    if risk:
        status = "risk"

    return {
        "status": status,
        "score": score,
        "summary": {
            "items": len(items),
            "measured": measured,
            "unknown": unknown,
            "ready": ready,
            "partial": partial,
            "risk": risk,
            "caveats": len(caveats),
        },
        "items": items,
        "caveats": caveats[:12],
    }
