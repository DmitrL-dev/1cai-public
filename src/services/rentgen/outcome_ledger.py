"""Outcome ledger that turns a Rentgen purchase into measurable adoption proof."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.services.rentgen.open_first_path import build_open_first_path


BUYER_ROOM_PACKET_ZIP = "rentgen-buyer-room-packet.zip"
BUYER_ROOM_PACKET_ENDPOINT = "/api/v1/management/buyer-room-packet"
BUYER_ROOM_PACKET_HASH_HEADER = "X-Buyer-Room-Packet-Sha256"
MEETING_CLOSE_RECEIPT_MD = "MEETING_CLOSE_RECEIPT.md"
POST_DEMO_ACTIVATION_MD = "POST_DEMO_ACTIVATION_HANDOFF.md"
ARCHIVE_ACCEPTANCE_RECEIPT_MD = "archive-acceptance-receipt.md"
ARCHIVE_ACCEPTANCE_RECEIPT_JSON = "archive-acceptance-receipt.json"
ARCHIVE_VERIFICATION_PACKET_ZIP = "archive-verification-packet.zip"
ARCHIVE_VERIFICATION_PACKET_ENDPOINT = "/api/v1/evidence-bundle/archive/verification-packet"
ARCHIVE_VERIFICATION_PACKET_HASH_HEADER = "X-Verification-Packet-Sha256"
KILLER_DEMO_MANIFEST_JSON = "killer-demo-manifest.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _score(report: dict[str, Any] | None, default: int = 0) -> int:
    if not report:
        return default
    if "score" in report:
        return _int(report.get("score"), default)
    return _int((report.get("decision") or {}).get("score"), default)


def _status(report: dict[str, Any] | None, default: str = "watch") -> str:
    if not report:
        return default
    return str((report.get("decision") or {}).get("status") or report.get("status") or default)


def _money(value: Any, currency: str) -> str:
    return f"{_int(value):,}".replace(",", " ") + f" {currency}"


def _route_set(items: list[dict[str, Any]], key: str = "route") -> set[str]:
    return {str(item.get(key) or "") for item in items if item.get(key)}


def _business_summary(business_case: dict[str, Any]) -> tuple[dict[str, Any], str]:
    summary = business_case.get("summary") or {}
    assumptions = business_case.get("assumptions") or {}
    currency = str(summary.get("currency") or assumptions.get("currency") or "RUB")
    return summary, currency


def _recommended_motion(
    *,
    board_pack: dict[str, Any],
    commercial_offer_studio: dict[str, Any],
) -> dict[str, Any]:
    offer = board_pack.get("recommended_offer") or {}
    if offer.get("id"):
        return offer
    recommended_id = (board_pack.get("summary") or {}).get("recommended_offer")
    for item in commercial_offer_studio.get("offers", []):
        if item.get("id") == recommended_id:
            return item
    offers = commercial_offer_studio.get("offers") or []
    return dict(offers[0]) if offers else {}


def _value_realization(
    *,
    business_case: dict[str, Any],
    board_pack: dict[str, Any],
    recommended_motion: dict[str, Any],
) -> dict[str, Any]:
    summary, currency = _business_summary(business_case)
    first_year_value = _int(summary.get("first_year_visible_value"))
    ai_year = _int(summary.get("ai_subscription_year"))
    manual_review_year = _int(summary.get("manual_review_year"))
    release_exposure = _int(summary.get("release_delay_exposure"))
    risk_exposure = _int(summary.get("risk_exposure"))
    return {
        "first_year_visible_value": first_year_value,
        "currency": currency,
        "value_anchor": _money(first_year_value, currency),
        "ai_subscription_year": ai_year,
        "ai_subscription_baseline": _money(ai_year, currency) if ai_year else "not provided",
        "manual_review_year": manual_review_year,
        "manual_review_baseline": _money(manual_review_year, currency),
        "release_delay_exposure": release_exposure,
        "release_delay_baseline": _money(release_exposure, currency),
        "risk_exposure": risk_exposure,
        "risk_exposure_baseline": _money(risk_exposure, currency),
        "recommended_motion": str(recommended_motion.get("title") or (board_pack.get("board_snapshot") or {}).get("recommended_motion") or "Select proof sprint"),
        "commercial_frame": str(recommended_motion.get("commercial_frame") or (board_pack.get("board_snapshot") or {}).get("commercial_frame") or "fixed next step"),
        "first_measurement_window": "7 days",
        "proof_standard": "Every claimed outcome must link to a route, owner, acceptance check and exportable artifact.",
    }


def _outcome_tiles(
    *,
    business_case: dict[str, Any],
    enterprise_trust_center: dict[str, Any],
    scenario_hub: dict[str, Any],
    vendor_portfolio: dict[str, Any],
) -> list[dict[str, Any]]:
    summary, currency = _business_summary(business_case)
    trust_summary = enterprise_trust_center.get("summary") or {}
    scenarios = {item.get("id"): item for item in scenario_hub.get("scenarios", []) if item.get("id")}
    work_packages = vendor_portfolio.get("work_packages") or []
    return [
        {
            "id": "review-proof",
            "role": "Developer / QA",
            "outcome": "Cut review waste with one deterministic 1C finding and regression expectation.",
            "baseline": _money(summary.get("manual_review_year"), currency),
            "target": "First proof sprint shows one real review-saving defect path.",
            "owner": "tech lead",
            "route": "/quality",
            "acceptance": "Developer can explain the finding, fix route and test expectation without a generic AI prompt.",
            "evidence": (scenarios.get("left-join-null") or {}).get("proof", "LEFT JOIN/NULL proof route"),
        },
        {
            "id": "release-proof",
            "role": "QA / release board",
            "outcome": "Move release discussion from screenshots to go/no-go artifacts.",
            "baseline": _money(summary.get("release_delay_exposure"), currency),
            "target": "One release meeting uses gates, owners and evidence bundle.",
            "owner": "release owner",
            "route": "/release-readiness",
            "acceptance": "Release board names go/no-go, caveats and required tests from one artifact.",
            "evidence": (scenarios.get("release-go-no-go") or {}).get("proof", "Release readiness and Evidence Bundle"),
        },
        {
            "id": "trust-proof",
            "role": "Security / CIO",
            "outcome": "Turn local-contour concern into a controlled approval checklist.",
            "baseline": f"{_int(trust_summary.get('failed_controls'))} failed controls",
            "target": "Security accepts proof or hardening scope before rollout.",
            "owner": "security owner",
            "route": "/enterprise-trust-center",
            "acceptance": "Locality, SBOM/offline, rights/RLS and platform caveats have owner or accepted risk.",
            "evidence": f"{_int(trust_summary.get('controls'))} trust controls tracked.",
        },
        {
            "id": "platform-proof",
            "role": "Architect",
            "outcome": "Make platform/update risk visible before it becomes expert anxiety.",
            "baseline": _money(summary.get("platform_exposure"), currency),
            "target": "First platform or extension decision links to caveats and owner actions.",
            "owner": "architect",
            "route": "/platform-doctor",
            "acceptance": "Upgrade, compatibility, DBMS and extension caveats are attached to pilot decision.",
            "evidence": (scenarios.get("platform-upgrade") or {}).get("proof", "Platform Doctor route"),
        },
        {
            "id": "vendor-proof",
            "role": "Vendor / franchisee",
            "outcome": "Convert audit evidence into repeatable paid work packages.",
            "baseline": f"{len(work_packages)} work packages visible",
            "target": "One customer report becomes a scoped proof sprint or hardening offer.",
            "owner": "vendor owner",
            "route": "/vendor-portfolio",
            "acceptance": "Partner sends buyer-safe report and maps at least one risk to a priced package.",
            "evidence": ", ".join(str(item.get("title")) for item in work_packages[:3] if item.get("title")) or "Vendor Portfolio",
        },
    ]


def _adoption_timeline(
    *,
    pilot_launchpad: dict[str, Any],
    recommended_motion: dict[str, Any],
) -> list[dict[str, str]]:
    pilot_offers = pilot_launchpad.get("pilot_offers") or []
    first_offer = pilot_offers[0] if pilot_offers else {}
    return [
        {
            "window": "Day 0",
            "owner": "sponsor",
            "route": "/board-pack",
            "goal": "Approve the buying motion and name the owner.",
            "artifact": "Board Pack markdown",
            "exit_criteria": f"Motion selected: {recommended_motion.get('title') or 'proof sprint'}.",
        },
        {
            "window": "Day 1",
            "owner": "security / architect",
            "route": "/enterprise-trust-center",
            "goal": "Confirm install mode and hardening caveats.",
            "artifact": "Trust Center risk register",
            "exit_criteria": "Every high trust risk has owner, accepted risk or hardening scope.",
        },
        {
            "window": "Day 7",
            "owner": "tech lead",
            "route": "/scenario-hub",
            "goal": "Run the first role-led proof on customer evidence.",
            "artifact": "Scenario proof markdown",
            "exit_criteria": "Developer, architect and director can repeat the value in their own words.",
        },
        {
            "window": "Day 30",
            "owner": "pilot owner",
            "route": "/pilot-launchpad",
            "goal": str(first_offer.get("why_buy") or "Complete paid pilot acceptance."),
            "artifact": "Pilot acceptance matrix",
            "exit_criteria": str(first_offer.get("acceptance") or "Owner, acceptance and next rollout step are selected."),
        },
        {
            "window": "Day 60",
            "owner": "delivery lead",
            "route": "/evidence-bundle",
            "goal": "Refresh the proof packet with measured outcomes and caveats.",
            "artifact": "Evidence Bundle manifest",
            "exit_criteria": "Hashed packet contains Board Pack, Outcome Ledger, Trust and Offer artifacts.",
        },
        {
            "window": "Day 90",
            "owner": "director / vendor owner",
            "route": "/commercial-offer-studio",
            "goal": "Convert measured outcomes into rollout, renewal or vendor portfolio expansion.",
            "artifact": "Commercial Offer Studio proposal",
            "exit_criteria": "Next paid package is selected or explicitly deferred with reasons.",
        },
    ]


def _success_metrics(
    *,
    business_case: dict[str, Any],
    enterprise_trust_center: dict[str, Any],
    board_pack: dict[str, Any],
) -> list[dict[str, str]]:
    summary, currency = _business_summary(business_case)
    board_summary = board_pack.get("summary") or {}
    trust_summary = enterprise_trust_center.get("summary") or {}
    return [
        {
            "metric": "Manual review tax exposed",
            "baseline": _money(summary.get("manual_review_year"), currency),
            "target": "One repeatable defect class removed from manual review.",
            "measurement": "Compare before/after review findings and regression expectations.",
            "route": "/quality",
            "buyer_line": "Developers see saved review time, not another chat window.",
        },
        {
            "metric": "Release delay exposure",
            "baseline": _money(summary.get("release_delay_exposure"), currency),
            "target": "One release meeting uses go/no-go evidence instead of ad-hoc screenshots.",
            "measurement": "Track selected gates, owners and unresolved caveats in release artifact.",
            "route": "/release-readiness",
            "buyer_line": "QA and director get a decision artifact they can forward.",
        },
        {
            "metric": "Trust blockers under control",
            "baseline": f"{_int(trust_summary.get('failed_controls'))} failed / {_int(trust_summary.get('warning_controls'))} warning controls",
            "target": "Every high blocker has fix, accepted risk or paid hardening scope.",
            "measurement": "Trust Center risk register burndown.",
            "route": "/enterprise-trust-center",
            "buyer_line": "Security gets named artifacts before rollout pressure.",
        },
        {
            "metric": "AI subscription displacement",
            "baseline": _money(summary.get("ai_subscription_year"), currency),
            "target": "Core value is purchased as local product capability; AI credits remain optional.",
            "measurement": "Board Pack and Business Case keep local license value separate from usage credits.",
            "route": "/business-case",
            "buyer_line": "Finance sees asset value instead of endless AI rent.",
        },
        {
            "metric": "Board proof completeness",
            "baseline": f"{_int(board_summary.get('proof_items'))} proof items",
            "target": "Board Pack and Evidence Bundle include role, trust, offer and outcome proof.",
            "measurement": "Evidence Bundle manifest contains markdown/JSON with hashes.",
            "route": "/evidence-bundle",
            "buyer_line": "The decision survives the meeting because proof is portable.",
        },
    ]


def _role_scorecards(
    *,
    board_pack: dict[str, Any],
    buyer_concierge: dict[str, Any],
) -> list[dict[str, str]]:
    committee = board_pack.get("committee_map") or []
    by_role = {str(item.get("role")): item for item in committee if item.get("role")}
    scorecards: list[dict[str, str]] = []
    for card in buyer_concierge.get("persona_cards", []):
        role = str(card.get("role") or "Stakeholder")
        committee_item = by_role.get(role) or {}
        scorecards.append(
            {
                "role": role,
                "spark": str(card.get("spark") or card.get("first_question") or ""),
                "adoption_signal": str(card.get("buy_trigger") or committee_item.get("buy_trigger") or ""),
                "proof_route": str(card.get("start_route") or committee_item.get("proof_route") or "/buyer-concierge"),
                "owner_action": str(committee_item.get("close_line") or "Pick the first outcome they want measured."),
            }
        )
    return scorecards


def _risk_burndown(board_pack: dict[str, Any]) -> list[dict[str, str]]:
    risks = []
    for item in board_pack.get("risk_to_decision", [])[:10]:
        risks.append(
            {
                "risk": str(item.get("risk") or "Board risk"),
                "owner": str(item.get("owner") or "lead"),
                "severity": str(item.get("severity") or "medium"),
                "route": str(item.get("route") or "/board-pack"),
                "day_7": str(item.get("decision") or "Name mitigation."),
                "day_30": "Close, accept or convert into paid hardening scope.",
            }
        )
    if not risks:
        risks.append(
            {
                "risk": "No blocking board risks were supplied.",
                "owner": "lead",
                "severity": "low",
                "route": "/outcome-ledger",
                "day_7": "Keep caveats visible.",
                "day_30": "Refresh Evidence Bundle with measured outcomes.",
            }
        )
    return risks


def _expansion_paths(
    *,
    commercial_offer_studio: dict[str, Any],
    value_packs: dict[str, Any],
    vendor_portfolio: dict[str, Any],
) -> list[dict[str, Any]]:
    offers = commercial_offer_studio.get("offers") or []
    packs = value_packs.get("packs") or []
    work_packages = vendor_portfolio.get("work_packages") or []
    return [
        {
            "id": "enterprise-rollout",
            "title": "Enterprise rollout",
            "route": "/commercial-offer-studio",
            "trigger": "Pilot acceptance and Trust Center caveats are closed or scoped.",
            "offer": next((item.get("title") for item in offers if item.get("id") == "enterprise-local-license"), "Enterprise local license"),
            "proof": "Board Pack + Outcome Ledger + Evidence Bundle.",
        },
        {
            "id": "platform-hardening",
            "title": "Platform and trust hardening",
            "route": "/enterprise-trust-center",
            "trigger": "Trust or platform risk blocks full rollout.",
            "offer": next((item.get("title") for item in offers if item.get("id") == "platform-trust-pack"), "Platform and trust hardening pack"),
            "proof": "Trust Center risk register and Platform Doctor caveats.",
        },
        {
            "id": "developer-pack",
            "title": "Developer productivity pack",
            "route": "/value-packs",
            "trigger": "Developer spark route proves a repeatable defect or review-saving path.",
            "offer": next((item.get("title") for item in packs if "Developer" in str(item.get("title"))), "Developer proof pack"),
            "proof": "Quality, Change Impact and Testing route evidence.",
        },
        {
            "id": "vendor-portfolio",
            "title": "Vendor portfolio rollout",
            "route": "/vendor-portfolio",
            "trigger": "Partner can sell proof sprint from one buyer-safe audit.",
            "offer": next((item.get("title") for item in offers if item.get("id") == "vendor-portfolio-rollout"), "Vendor portfolio rollout"),
            "proof": next((item.get("title") for item in work_packages if item.get("title")), "Vendor Portfolio work packages"),
        },
    ]


def _governance_refresh(
    *,
    board_pack: dict[str, Any],
    pilot_launchpad: dict[str, Any],
) -> dict[str, Any]:
    board_close = board_pack.get("board_close_packet") or {}
    activation = pilot_launchpad.get("activation_contract") or {}
    ready = bool(board_close.get("ready_to_close", _status(board_pack) == "ready")) and bool(
        activation.get("ready_to_activate", _status(pilot_launchpad) == "ready")
    )
    gates = [
        {
            "gate": "Approval decisions remain scoped",
            "route": "/approvals",
            "evidence": "Approval records show owner, reason, scope and decision for risky/write-capable actions.",
        },
        {
            "gate": "Audit chain remains valid",
            "route": "/audit",
            "evidence": "Audit verification is valid before Day 30 acceptance and Day 60 packet refresh.",
        },
        {
            "gate": "Evidence Bundle is refreshed",
            "route": "/evidence-bundle",
            "evidence": "Outcome Ledger, Board Pack, Pilot Launchpad and Governance Proof are exported with hashes.",
        },
        {
            "gate": "Trust caveats are burned down or scoped",
            "route": "/enterprise-trust-center",
            "evidence": "Trust risks have owner, fix, accepted risk or paid hardening scope.",
        },
    ]
    windows = [
        {
            "window": "Day 7",
            "owner": "tech lead + security",
            "route": "/approvals",
            "acceptance": "First proof action has scoped approval or explicit read-only evidence path.",
        },
        {
            "window": "Day 30",
            "owner": "sponsor",
            "route": "/audit",
            "acceptance": "Audit chain verifies cleanly before paid pilot acceptance.",
        },
        {
            "window": "Day 60",
            "owner": "delivery lead",
            "route": "/evidence-bundle",
            "acceptance": "Evidence Bundle refresh includes measured outcomes and governance proof.",
        },
        {
            "window": "Day 90",
            "owner": "director / vendor owner",
            "route": "/commercial-offer-studio",
            "acceptance": "Expansion, renewal or hardening motion references the refreshed proof packet.",
        },
    ]
    proof_routes = sorted(
        _route_set(gates)
        | _route_set(windows)
        | set(board_close.get("proof_routes") or [])
        | set(activation.get("proof_routes") or [])
    )
    return {
        "ready": ready,
        "gates": gates,
        "windows": windows,
        "proof_routes": proof_routes,
        "refresh_line": (
            "Governance proof is ready to travel with outcome acceptance."
            if ready
            else "Refresh approvals, audit and evidence before claiming rollout outcomes."
        ),
    }


def _acceptance_rollup(
    *,
    pilot_launchpad: dict[str, Any],
    adoption_timeline: list[dict[str, str]],
) -> dict[str, Any]:
    register = pilot_launchpad.get("acceptance_register") or {}
    activation = pilot_launchpad.get("activation_contract") or {}
    rows = list(register.get("items") or [])
    if not rows:
        rows = [
            {
                "id": "pilot-activation",
                "role": "Sponsor",
                "owner": "sponsor",
                "window": "Day 0",
                "decision": "Pilot activation is accepted and owner is named.",
                "acceptance": "Activation contract is ready and proof routes are attached.",
                "evidence_route": "/pilot-launchpad",
                "evidence_file": "rentgen-pilot-launchpad.md",
                "required_routes": list(activation.get("proof_routes") or ["/pilot-launchpad"]),
                "status": "ready" if activation.get("ready_to_activate", _status(pilot_launchpad) == "ready") else "watch",
                "blocker": "",
                "next_action": "Refresh Pilot Launchpad with named owner, scope and proof recipient.",
            }
        ]
    if not any(
        row.get("id") == "day0-activation-baseline"
        or row.get("id") == "day0-close-packet"
        or row.get("evidence_file") == ARCHIVE_ACCEPTANCE_RECEIPT_MD
        for row in rows
    ):
        handoff_routes = sorted(
            set(activation.get("proof_routes") or [])
            | {"/killer-demo", "/pilot-launchpad", "/evidence-bundle", "/outcome-ledger"}
        )
        rows.insert(
            0,
            {
                "id": "day0-activation-baseline",
                "role": "Sponsor / Procurement",
                "owner": "sponsor",
                "window": "Day 0",
                "decision": "Post-demo close packet is accepted as the measurement baseline.",
                "acceptance": (
                    f"`{ARCHIVE_ACCEPTANCE_RECEIPT_MD}` records archive boundaries and hash headers; "
                    f"`{MEETING_CLOSE_RECEIPT_MD}` and `{POST_DEMO_ACTIVATION_MD}` are attached."
                ),
                "evidence_route": "/evidence-bundle",
                "evidence_file": ARCHIVE_ACCEPTANCE_RECEIPT_MD,
                "required_routes": handoff_routes,
                "status": "ready"
                if activation.get("ready_to_activate", _status(pilot_launchpad) == "ready")
                else "watch",
                "blocker": "",
                "next_action": "Use the accepted close packet as Day 0 before claiming Day 30 outcomes.",
            },
        )
    if not any(row.get("id") == "day0-verification-packet" or row.get("evidence_file") == ARCHIVE_VERIFICATION_PACKET_ZIP for row in rows):
        handoff_routes = sorted(
            set(activation.get("proof_routes") or [])
            | {"/killer-demo", "/pilot-launchpad", "/evidence-bundle", "/outcome-ledger"}
        )
        rows.insert(
            1 if rows else 0,
            {
                "id": "day0-verification-packet",
                "role": "Security / Procurement",
                "owner": "security",
                "window": "Day 0",
                "decision": "Archive pair verification is accepted before outcome measurement starts.",
                "acceptance": f"`{ARCHIVE_VERIFICATION_PACKET_ZIP}` is attached and `{ARCHIVE_VERIFICATION_PACKET_HASH_HEADER}` is recorded.",
                "evidence_route": "/evidence-bundle",
                "evidence_file": ARCHIVE_VERIFICATION_PACKET_ZIP,
                "required_routes": handoff_routes,
                "status": "ready"
                if activation.get("ready_to_activate", _status(pilot_launchpad) == "ready")
                else "watch",
                "blocker": "",
                "next_action": "Use the verification packet as the pair-level Day 0 control before claiming Day 30 outcomes.",
            },
        )

    timeline_by_window = {str(item.get("window") or ""): item for item in adoption_timeline}

    def outcome_route(row: dict[str, Any]) -> str:
        role = str(row.get("role") or "").lower()
        row_id = str(row.get("id") or "").lower()
        if "developer" in role or "tech" in role:
            return "/quality"
        if "qa" in role or "release" in role:
            return "/release-readiness"
        if "security" in role:
            return "/enterprise-trust-center"
        if "architect" in role:
            return "/platform-doctor"
        if "finance" in role:
            return "/business-case"
        if "day30" in row_id or "procurement" in role:
            return "/commercial-offer-studio"
        return "/outcome-ledger"

    items: list[dict[str, Any]] = []
    for row in rows:
        window = str(row.get("window") or "Day 30")
        timeline = timeline_by_window.get(window) or {}
        status = str(row.get("status") or "watch")
        required_routes = [str(route) for route in row.get("required_routes") or [] if route]
        evidence_route = str(row.get("evidence_route") or timeline.get("route") or "/outcome-ledger")
        result_route = outcome_route(row)
        items.append(
            {
                "id": str(row.get("id") or f"acceptance-{len(items) + 1}"),
                "role": str(row.get("role") or "Owner"),
                "owner": str(row.get("owner") or timeline.get("owner") or "owner"),
                "window": window,
                "status": status,
                "decision": str(row.get("decision") or "Acceptance decision is named."),
                "acceptance": str(row.get("acceptance") or timeline.get("exit_criteria") or ""),
                "evidence_route": evidence_route,
                "evidence_file": str(row.get("evidence_file") or "rentgen-pilot-launchpad.md"),
                "outcome_route": result_route,
                "outcome_signal": str(timeline.get("exit_criteria") or timeline.get("goal") or "Measure and refresh proof."),
                "required_routes": required_routes,
                "blocker": str(row.get("blocker") or ""),
                "next_action": str(row.get("next_action") or "Refresh outcome evidence and owner action."),
            }
        )

    ready_items = [item for item in items if item["status"] == "ready"]
    watch_items = [item for item in items if item["status"] == "watch"]
    blocked_items = [item for item in items if item["status"] == "blocked"]
    next_item = next((item for item in items if item["status"] != "ready"), items[0] if items else {})
    proof_routes = sorted(
        {item["evidence_route"] for item in items}
        | {item["outcome_route"] for item in items}
        | {route for item in items for route in item["required_routes"]}
    )
    return {
        "ready_to_claim": not watch_items and not blocked_items,
        "ready_to_continue": not blocked_items,
        "owner_line": "Pilot sign-off rows are now tied to outcome routes, proof files and Day 7/30/60/90 refresh.",
        "items": items,
        "ready_items": len(ready_items),
        "watch_items": len(watch_items),
        "blocked_items": len(blocked_items),
        "next_window": str(next_item.get("window") or "Day 30"),
        "next_owner": str(next_item.get("owner") or "owner"),
        "proof_routes": proof_routes,
    }


def _post_purchase_proof_spine(
    *,
    pilot_launchpad: dict[str, Any],
    acceptance_rollup: dict[str, Any],
    governance_refresh: dict[str, Any],
) -> dict[str, Any]:
    activation = pilot_launchpad.get("activation_contract") or {}
    activation_ready = bool(activation.get("ready_to_activate", _status(pilot_launchpad) == "ready"))
    files = [
        {
            "title": "Buyer Room Packet ZIP",
            "filename": BUYER_ROOM_PACKET_ZIP,
            "route": "/",
            "owner": "sponsor / procurement",
            "purpose": f"Open-first room packet generated by {BUYER_ROOM_PACKET_ENDPOINT}; record {BUYER_ROOM_PACKET_HASH_HEADER} before Day 0 claims.",
        },
        {
            "title": "Meeting Close Receipt",
            "filename": MEETING_CLOSE_RECEIPT_MD,
            "route": "/killer-demo",
            "owner": "presenter / sponsor",
            "purpose": "Records accepted roles, blockers, next paid step and close-room archive verification.",
        },
        {
            "title": "Post-Demo Activation Handoff",
            "filename": POST_DEMO_ACTIVATION_MD,
            "route": "/pilot-launchpad",
            "owner": "pilot owner",
            "purpose": "Turns the accepted demo into owner, invoice trigger, activation gates and Day 30 outcome path.",
        },
        {
            "title": "Archive Acceptance Receipt",
            "filename": ARCHIVE_ACCEPTANCE_RECEIPT_MD,
            "route": "/evidence-bundle",
            "owner": "procurement",
            "purpose": "Records Evidence Bundle and linked Killer Demo ZIP boundaries, filenames and hash headers.",
        },
        {
            "title": "Archive Acceptance Receipt JSON",
            "filename": ARCHIVE_ACCEPTANCE_RECEIPT_JSON,
            "route": "/evidence-bundle",
            "owner": "procurement / audit",
            "purpose": "Machine-readable receipt for ticket systems, audit evidence and archive hash checks.",
        },
        {
            "title": "Verification Packet ZIP",
            "filename": ARCHIVE_VERIFICATION_PACKET_ZIP,
            "route": "/evidence-bundle",
            "owner": "security / procurement",
            "purpose": f"Pair-level control ZIP generated by {ARCHIVE_VERIFICATION_PACKET_ENDPOINT}; record {ARCHIVE_VERIFICATION_PACKET_HASH_HEADER} before outcome claims.",
        },
        {
            "title": "Killer Demo Manifest",
            "filename": KILLER_DEMO_MANIFEST_JSON,
            "route": "/killer-demo",
            "owner": "presenter / procurement",
            "purpose": "Lists close-room ZIP files and role packet hashes used to verify the handoff archive.",
        },
    ]
    filenames = {item["filename"] for item in files}
    for item in activation.get("handoff_files") or []:
        filename = str(item.get("filename") or "")
        if not filename or filename in filenames:
            continue
        files.append(
            {
                "title": str(item.get("title") or filename),
                "filename": filename,
                "route": str(item.get("route") or "/pilot-launchpad"),
                "owner": str(item.get("owner") or "owner"),
                "purpose": str(item.get("purpose") or item.get("note") or "Activation handoff artifact."),
            }
        )
        filenames.add(filename)

    required_routes = sorted(
        _route_set(files)
        | set(activation.get("proof_routes") or [])
        | set(acceptance_rollup.get("proof_routes") or [])
        | {"/outcome-ledger"}
    )
    ready_to_measure = activation_ready and bool(acceptance_rollup.get("ready_to_continue"))
    ready_to_claim = ready_to_measure and bool(governance_refresh.get("ready"))
    status = "ready" if ready_to_claim else "blocked" if not ready_to_measure else "watch"
    return {
        "status": status,
        "ready_to_measure": ready_to_measure,
        "ready_to_claim": ready_to_claim,
        "buyer_line": (
            "Day 30 outcomes are claimable only when the Buyer Room Packet, accepted post-demo close packet, "
            "activation handoff, dual-archive receipt and verification packet are visible together."
        ),
        "measurement_rule": (
            f"Use `{BUYER_ROOM_PACKET_ZIP}` as the Day 0 room packet, "
            f"`{ARCHIVE_ACCEPTANCE_RECEIPT_MD}` as the archive receipt, "
            f"`{ARCHIVE_VERIFICATION_PACKET_ZIP}` as the pair-level verification control, "
            f"`{MEETING_CLOSE_RECEIPT_MD}` as the accepted-close record and "
            f"`{POST_DEMO_ACTIVATION_MD}` as the paid-activation contract."
        ),
        "files": files,
        "required_routes": required_routes,
        "buyer_room_packet": {
            "title": "Buyer Room Packet ZIP",
            "filename": BUYER_ROOM_PACKET_ZIP,
            "route": "/",
            "endpoint": BUYER_ROOM_PACKET_ENDPOINT,
            "hash_header": BUYER_ROOM_PACKET_HASH_HEADER,
            "check": "Record open-first packet hash before Day 0 and Day 30 outcome claims.",
        },
        "archive_receipt": {
            "title": "Dual-archive acceptance receipt",
            "filename": ARCHIVE_ACCEPTANCE_RECEIPT_MD,
            "route": "/evidence-bundle",
            "check": "Record Evidence Bundle ZIP hash and linked Killer Demo ZIP hash before outcome claims.",
        },
        "verification_packet": {
            "title": "Verification Packet ZIP",
            "filename": ARCHIVE_VERIFICATION_PACKET_ZIP,
            "route": "/evidence-bundle",
            "hash_header": ARCHIVE_VERIFICATION_PACKET_HASH_HEADER,
            "check": "Record pair-level verification packet hash before Day 30 outcome claims.",
        },
        "activation_gate": {
            "ready": activation_ready,
            "source": "pilot-launchpad.activation_contract",
            "invoice_trigger": str(activation.get("invoice_trigger") or "Named owner, scope and evidence packet accepted."),
        },
    }


def _outcome_room_bridge(
    *,
    buyer_brief: dict[str, Any] | None,
    value_realization: dict[str, Any],
    role_scorecards: list[dict[str, str]],
    acceptance_rollup: dict[str, Any],
    governance_refresh: dict[str, Any],
) -> dict[str, Any]:
    brief = buyer_brief or {}
    ready_to_claim = bool(acceptance_rollup.get("ready_to_claim")) and bool(governance_refresh.get("ready"))
    primary = dict(brief.get("primary_motion") or {})
    outcome_motion = {
        "label": "Claim measured outcomes",
        "route": "/outcome-ledger",
        "status": "ready" if ready_to_claim else "watch",
        "ask": (
            "Use the refreshed proof packet to claim rollout value, renewal or expansion."
            if ready_to_claim
            else "Refresh acceptance, governance and evidence before claiming rollout value."
        ),
        "reason": str(value_realization.get("proof_standard") or "Every outcome needs route, owner and exportable proof."),
        "value_anchor": str(value_realization.get("value_anchor") or "n/a"),
    }
    if not primary:
        primary = {
            "label": str(value_realization.get("recommended_motion") or "Select paid motion"),
            "route": "/board-pack",
            "status": "ready" if ready_to_claim else "watch",
            "ask": str(outcome_motion["ask"]),
            "reason": str(value_realization.get("commercial_frame") or outcome_motion["reason"]),
        }

    role_cards = list(brief.get("role_cards") or [])
    if not role_cards:
        role_cards = [
            {
                "role": item["role"].casefold(),
                "title": item["role"],
                "route": item["proof_route"],
                "status": "ready" if ready_to_claim else "watch",
                "spark": item["adoption_signal"] or item["spark"],
                "proof_file": "rentgen-outcome-ledger.md",
                "owner_action": item["owner_action"],
            }
            for item in role_scorecards[:5]
        ]

    route_to_file = {
        "/approvals": "governance-proof.md",
        "/audit": "rentgen-audit-log.jsonl",
        "/evidence-bundle": "OPEN_FIRST.md",
        "/enterprise-trust-center": "rentgen-security-questionnaire.md",
        "/outcome-ledger": "rentgen-outcome-ledger.md",
    }
    proof_readiness = list(brief.get("proof_readiness") or [])
    if not proof_readiness:
        proof_readiness = [
            {
                "id": str(item.get("gate") or item.get("route") or "outcome-proof").lower().replace(" ", "-"),
                "title": str(item.get("gate") or "Outcome proof"),
                "route": str(item.get("route") or "/outcome-ledger"),
                "status": "ready" if ready_to_claim else "watch",
                "signal": str(item.get("evidence") or "Required before the buyer can claim outcomes."),
                "file": route_to_file.get(str(item.get("route") or ""), "rentgen-outcome-ledger.md"),
            }
            for item in governance_refresh.get("gates", [])[:4]
        ]

    meeting_flow = list(brief.get("meeting_flow") or [])
    if not meeting_flow:
        meeting_flow = [
            {"step": 1, "label": "Orient", "route": "/buyer-concierge", "line": "Remind the room which role needs which proof."},
            {"step": 2, "label": "Prove", "route": "/killer-demo", "line": "Replay the accepted proof and objection answers."},
            {"step": 3, "label": "Measure", "route": "/outcome-ledger", "line": str(outcome_motion["ask"])},
            {"step": 4, "label": "Refresh", "route": "/evidence-bundle", "line": "Attach refreshed outcome, governance and trust proof with hashes."},
        ]
    open_first_path = build_open_first_path(
        existing_path=brief.get("open_first_path"),
        proof_readiness=proof_readiness,
        primary=primary,
        meeting_flow=meeting_flow,
        source="outcome-ledger-fallback",
        orient_title="Outcome room",
        orient_route="/outcome-ledger",
        orient_line="Remind the room which proof matters.",
        orient_status=str(primary.get("status") or outcome_motion["status"]),
        prove_title="Accepted proof",
        prove_line="Replay the accepted proof and objection answers.",
        prove_file="OPEN_FIRST.md",
        prove_status=str(outcome_motion["status"]),
        close_label="Claim",
        close_title="Outcome Ledger",
        close_route="/outcome-ledger",
        close_line=str(outcome_motion["ask"]),
        close_file="rentgen-outcome-ledger.md",
        close_status=str(outcome_motion["status"]),
        verify_line="Record pair-level verification before claiming Day 30 outcomes.",
    )

    routes = sorted(
        {
            "/",
            "/outcome-ledger",
            str(primary.get("route") or "/board-pack"),
            str(outcome_motion["route"]),
            *[str(item.get("route") or "") for item in role_cards],
            *[str(item.get("route") or "") for item in proof_readiness],
            *[str(item.get("route") or "") for item in meeting_flow],
            *[str(item.get("route") or "") for item in open_first_path],
            *[str(item) for item in acceptance_rollup.get("proof_routes", [])],
            *[str(item) for item in governance_refresh.get("proof_routes", [])],
        }
        - {""}
    )
    fallback_score = 86 if ready_to_claim else 70
    return {
        "status": str(brief.get("purchase_status") or primary.get("status") or ("ready" if ready_to_claim else "watch")),
        "score": _int(brief.get("score"), fallback_score),
        "source": str(brief.get("source") or "outcome-ledger-derived"),
        "room_line": str(
            brief.get("room_line")
            or f"{primary.get('label', value_realization.get('recommended_motion', 'Select paid motion'))}: "
            f"{primary.get('ask', outcome_motion['ask'])} "
            f"Value anchor: {outcome_motion['value_anchor']}."
        ),
        "primary_motion": {
            "label": str(primary.get("label") or value_realization.get("recommended_motion") or "Select paid motion"),
            "route": str(primary.get("route") or "/board-pack"),
            "status": str(primary.get("status") or outcome_motion["status"]),
            "ask": str(primary.get("ask") or outcome_motion["ask"]),
            "reason": str(primary.get("reason") or value_realization.get("commercial_frame") or outcome_motion["reason"]),
        },
        "outcome_motion": outcome_motion,
        "role_cards": role_cards[:5],
        "proof_readiness": proof_readiness[:4],
        "meeting_flow": meeting_flow[:4],
        "open_first_path": open_first_path[:4],
        "files": [
            BUYER_ROOM_PACKET_ZIP,
            "open-first-path.md",
            "buyer-brief.md",
            "buyer-pulse.md",
            MEETING_CLOSE_RECEIPT_MD,
            POST_DEMO_ACTIVATION_MD,
            ARCHIVE_ACCEPTANCE_RECEIPT_MD,
            ARCHIVE_VERIFICATION_PACKET_ZIP,
            "rentgen-outcome-ledger.md",
            "governance-proof.md",
            "OPEN_FIRST.md",
        ],
        "routes": routes,
        "outcome_question": (
            "Can we claim the measured outcome and select rollout, renewal or expansion?"
            if ready_to_claim
            else "Which acceptance or governance proof must refresh before claiming outcomes?"
        ),
    }


def _proof_packet() -> list[dict[str, str]]:
    return [
        {
            "title": "Buyer Room Packet ZIP",
            "filename": BUYER_ROOM_PACKET_ZIP,
            "route": "/",
            "endpoint": BUYER_ROOM_PACKET_ENDPOINT,
            "hash_header": BUYER_ROOM_PACKET_HASH_HEADER,
        },
        {"title": "Buyer Brief markdown", "filename": "buyer-brief.md", "route": "/"},
        {"title": "Buyer Pulse markdown", "filename": "buyer-pulse.md", "route": "/"},
        {"title": "Meeting Close Receipt", "filename": MEETING_CLOSE_RECEIPT_MD, "route": "/killer-demo"},
        {"title": "Post-Demo Activation Handoff", "filename": POST_DEMO_ACTIVATION_MD, "route": "/pilot-launchpad"},
        {"title": "Archive Acceptance Receipt", "filename": ARCHIVE_ACCEPTANCE_RECEIPT_MD, "route": "/evidence-bundle"},
        {"title": "Archive Acceptance Receipt JSON", "filename": ARCHIVE_ACCEPTANCE_RECEIPT_JSON, "route": "/evidence-bundle"},
        {"title": "Verification Packet ZIP", "filename": ARCHIVE_VERIFICATION_PACKET_ZIP, "route": "/evidence-bundle"},
        {"title": "Killer Demo Manifest", "filename": KILLER_DEMO_MANIFEST_JSON, "route": "/killer-demo"},
        {"title": "Outcome Ledger markdown", "filename": "rentgen-outcome-ledger.md", "route": "/outcome-ledger"},
        {"title": "Board Pack markdown", "filename": "rentgen-board-pack.md", "route": "/board-pack"},
        {"title": "Pilot Launchpad markdown", "filename": "rentgen-pilot-launchpad.md", "route": "/pilot-launchpad"},
        {"title": "Business Case markdown", "filename": "rentgen-business-case.md", "route": "/business-case"},
        {"title": "Enterprise Trust Center markdown", "filename": "rentgen-enterprise-trust-center.md", "route": "/enterprise-trust-center"},
        {"title": "Governance Proof markdown", "filename": "governance-proof.md", "route": "/approvals"},
        {"title": "Audit verification/export", "filename": "rentgen-audit-log.jsonl", "route": "/audit"},
        {"title": "Evidence Bundle manifest", "filename": "evidence-bundle-manifest.json", "route": "/evidence-bundle"},
    ]


def _exports() -> list[dict[str, str]]:
    return [
        {
            "title": "Buyer Room Packet ZIP",
            "filename": BUYER_ROOM_PACKET_ZIP,
            "route": "/",
            "endpoint": BUYER_ROOM_PACKET_ENDPOINT,
            "hash_header": BUYER_ROOM_PACKET_HASH_HEADER,
        },
        {"title": "Buyer Brief markdown", "filename": "buyer-brief.md", "route": "/"},
        {"title": "Buyer Pulse markdown", "filename": "buyer-pulse.md", "route": "/"},
        {"title": "Meeting Close Receipt", "filename": MEETING_CLOSE_RECEIPT_MD, "route": "/killer-demo"},
        {"title": "Post-Demo Activation Handoff", "filename": POST_DEMO_ACTIVATION_MD, "route": "/pilot-launchpad"},
        {"title": "Archive Acceptance Receipt", "filename": ARCHIVE_ACCEPTANCE_RECEIPT_MD, "route": "/evidence-bundle"},
        {"title": "Archive Acceptance Receipt JSON", "filename": ARCHIVE_ACCEPTANCE_RECEIPT_JSON, "route": "/evidence-bundle"},
        {"title": "Verification Packet ZIP", "filename": ARCHIVE_VERIFICATION_PACKET_ZIP, "route": "/evidence-bundle"},
        {"title": "Killer Demo Manifest", "filename": KILLER_DEMO_MANIFEST_JSON, "route": "/killer-demo"},
        {"title": "Outcome Ledger markdown", "filename": "rentgen-outcome-ledger.md", "route": "/outcome-ledger"},
        {"title": "Board Pack markdown", "filename": "rentgen-board-pack.md", "route": "/board-pack"},
        {"title": "Commercial Offer Studio markdown", "filename": "rentgen-commercial-offer-studio.md", "route": "/commercial-offer-studio"},
        {"title": "Governance Proof markdown", "filename": "governance-proof.md", "route": "/approvals"},
        {"title": "Audit verification/export", "filename": "rentgen-audit-log.jsonl", "route": "/audit"},
        {"title": "Evidence Bundle manifest", "filename": "evidence-bundle-manifest.json", "route": "/evidence-bundle"},
    ]


def _ledger_status(*, score: int, statuses: set[str], severe_risks: int) -> str:
    if statuses & {"blocked", "critical", "fail"}:
        return "risk"
    if "risk" in statuses and severe_risks:
        return "risk"
    if severe_risks >= 3:
        return "risk"
    if score >= 82 and severe_risks == 0:
        return "ready"
    return "watch"


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 1C Rentgen Outcome Ledger",
        "",
        f"Client: **{report['client']['name']}**",
        f"Status: **{report['decision']['status'].upper()}** / score **{report['decision']['score']}**",
        f"Value anchor: **{report['value_realization']['value_anchor']}**",
        f"Recommended motion: **{report['value_realization']['recommended_motion']}**",
        "",
        "## Outcome Tiles",
        "",
    ]
    for item in report["outcome_tiles"]:
        lines.append(f"- **{item['role']}** (`{item['route']}`): {item['outcome']} Target: {item['target']}")
    lines.extend(["", "## Adoption Timeline", ""])
    for item in report["adoption_timeline"]:
        lines.append(f"- **{item['window']}** / {item['owner']} (`{item['route']}`): {item['goal']} Exit: {item['exit_criteria']}")
    lines.extend(["", "## Success Metrics", ""])
    for item in report["success_metrics"]:
        lines.append(f"- **{item['metric']}**: baseline {item['baseline']}; target {item['target']} (`{item['route']}`)")
    lines.extend(["", "## Risk Burndown", ""])
    for item in report["risk_burndown"]:
        lines.append(f"- **{item['severity']}** {item['owner']} (`{item['route']}`): {item['risk']} Day 30: {item['day_30']}")
    rollup = report.get("acceptance_rollup") or {}
    if rollup:
        lines.extend(["", "## Acceptance Rollup", ""])
        lines.append(f"- Ready to claim: **{bool(rollup.get('ready_to_claim'))}**")
        lines.append(f"- Ready/watch/blocked: **{rollup.get('ready_items', 0)}** / **{rollup.get('watch_items', 0)}** / **{rollup.get('blocked_items', 0)}**")
        lines.append(f"- Next: **{rollup.get('next_window', '')}** / {rollup.get('next_owner', '')}")
        lines.append(f"- {rollup.get('owner_line', '')}")
        for item in rollup.get("items", []):
            lines.append(
                f"- **{item.get('window', '')}** / {item.get('role', '')} / {item.get('owner', '')}: "
                f"{item.get('status', '')}. Evidence `{item.get('evidence_route', '')}` -> outcome `{item.get('outcome_route', '')}`"
            )
    governance = report.get("governance_refresh") or {}
    if governance:
        lines.extend(["", "## Governance Refresh", ""])
        lines.append(f"- Ready: **{bool(governance.get('ready'))}**")
        lines.append(f"- {governance.get('refresh_line', '')}")
        for item in governance.get("gates", []):
            lines.append(f"- Gate `{item.get('route', '/outcome-ledger')}`: {item.get('gate', '')} - {item.get('evidence', '')}")
        for item in governance.get("windows", []):
            lines.append(f"- **{item.get('window', '')}** / {item.get('owner', '')}: {item.get('acceptance', '')}")
    spine = report.get("post_purchase_proof_spine") or {}
    if spine:
        lines.extend(["", "## Post-Purchase Proof Spine", ""])
        lines.append(f"- Status: **{spine.get('status', 'watch')}**")
        lines.append(f"- Ready to measure: **{bool(spine.get('ready_to_measure'))}**")
        lines.append(f"- Ready to claim: **{bool(spine.get('ready_to_claim'))}**")
        lines.append(f"- {spine.get('buyer_line', '')}")
        lines.append(f"- Rule: {spine.get('measurement_rule', '')}")
        receipt = spine.get("archive_receipt") or {}
        if receipt:
            lines.append(f"- Archive receipt `{receipt.get('filename', '')}` (`{receipt.get('route', '')}`): {receipt.get('check', '')}")
        verification = spine.get("verification_packet") or {}
        if verification:
            lines.append(
                f"- Verification packet `{verification.get('filename', '')}` "
                f"(`{verification.get('route', '')}` / `{verification.get('hash_header', '')}`): {verification.get('check', '')}"
            )
        for item in spine.get("files", []):
            lines.append(
                f"- **{item.get('title', 'Proof file')}** `{item.get('filename', '')}` "
                f"({item.get('route', '')}): {item.get('purpose', '')}"
            )
    bridge = report.get("outcome_room_bridge") or {}
    if bridge:
        lines.extend(["", "## Outcome Room Bridge", ""])
        lines.append(f"- Source: **{bridge.get('source', 'n/a')}**; status **{bridge.get('status', 'watch')}** / score **{bridge.get('score', 0)}**")
        lines.append(f"- Room line: {bridge.get('room_line', '')}")
        motion = bridge.get("primary_motion") or {}
        lines.append(f"- Primary motion: **{motion.get('label', 'n/a')}** (`{motion.get('route', '/board-pack')}`): {motion.get('ask', '')}")
        outcome_motion = bridge.get("outcome_motion") or {}
        lines.append(
            f"- Outcome motion: **{outcome_motion.get('label', 'n/a')}** "
            f"(`{outcome_motion.get('route', '/outcome-ledger')}`): {outcome_motion.get('ask', '')}"
        )
        for item in bridge.get("open_first_path", []):
            lines.append(
                f"- Open-first {item.get('step', '')} **{item.get('label', 'step')}** "
                f"`{item.get('route', '')}` -> `{item.get('file', '')}`: {item.get('line', '')}"
            )
        for item in bridge.get("role_cards", []):
            lines.append(f"- **{item.get('title', item.get('role', 'role'))}** `{item.get('route', '')}`: {item.get('spark', '')}")
        for item in bridge.get("proof_readiness", []):
            lines.append(f"- Proof **{item.get('title', 'proof')}** `{item.get('route', '')}` -> {item.get('file', '')}: {item.get('signal', '')}")
        for item in bridge.get("meeting_flow", []):
            lines.append(f"- Step {item.get('step', '')} **{item.get('label', 'step')}** `{item.get('route', '')}`: {item.get('line', '')}")
    lines.extend(["", "## Caveats", ""])
    lines.extend(f"- {item}" for item in report["caveats"])
    return "\n".join(lines)


def build_outcome_ledger(
    *,
    executive: dict[str, Any],
    board_pack: dict[str, Any],
    buyer_concierge: dict[str, Any],
    commercial_offer_studio: dict[str, Any],
    enterprise_trust_center: dict[str, Any],
    business_case: dict[str, Any],
    scenario_hub: dict[str, Any],
    pilot_launchpad: dict[str, Any],
    demo_command_center: dict[str, Any],
    productization: dict[str, Any],
    value_packs: dict[str, Any],
    vendor_portfolio: dict[str, Any],
    buyer_brief: dict[str, Any] | None = None,
    client_name: str = "Demo client",
    config_path: str | None = None,
    target_platform_version: str | None = None,
) -> dict[str, Any]:
    """Build a post-purchase outcome ledger with adoption and proof metrics."""

    recommended_motion = _recommended_motion(
        board_pack=board_pack,
        commercial_offer_studio=commercial_offer_studio,
    )
    value_realization = _value_realization(
        business_case=business_case,
        board_pack=board_pack,
        recommended_motion=recommended_motion,
    )
    outcome_tiles = _outcome_tiles(
        business_case=business_case,
        enterprise_trust_center=enterprise_trust_center,
        scenario_hub=scenario_hub,
        vendor_portfolio=vendor_portfolio,
    )
    adoption_timeline = _adoption_timeline(
        pilot_launchpad=pilot_launchpad,
        recommended_motion=recommended_motion,
    )
    success_metrics = _success_metrics(
        business_case=business_case,
        enterprise_trust_center=enterprise_trust_center,
        board_pack=board_pack,
    )
    role_scorecards = _role_scorecards(
        board_pack=board_pack,
        buyer_concierge=buyer_concierge,
    )
    risk_burndown = _risk_burndown(board_pack)
    expansion_paths = _expansion_paths(
        commercial_offer_studio=commercial_offer_studio,
        value_packs=value_packs,
        vendor_portfolio=vendor_portfolio,
    )
    governance_refresh = _governance_refresh(
        board_pack=board_pack,
        pilot_launchpad=pilot_launchpad,
    )
    acceptance_rollup = _acceptance_rollup(
        pilot_launchpad=pilot_launchpad,
        adoption_timeline=adoption_timeline,
    )
    post_purchase_proof_spine = _post_purchase_proof_spine(
        pilot_launchpad=pilot_launchpad,
        acceptance_rollup=acceptance_rollup,
        governance_refresh=governance_refresh,
    )
    outcome_room_bridge = _outcome_room_bridge(
        buyer_brief=buyer_brief,
        value_realization=value_realization,
        role_scorecards=role_scorecards,
        acceptance_rollup=acceptance_rollup,
        governance_refresh=governance_refresh,
    )
    proof_packet = _proof_packet()
    proof_routes = sorted(
        {item["route"] for item in outcome_tiles}
        | {item["route"] for item in adoption_timeline}
        | {item["route"] for item in success_metrics}
        | {item["proof_route"] for item in role_scorecards}
        | {item["route"] for item in risk_burndown}
        | {item["route"] for item in expansion_paths}
        | {item["route"] for item in governance_refresh["gates"]}
        | {item["route"] for item in governance_refresh["windows"]}
        | set(governance_refresh["proof_routes"])
        | set(acceptance_rollup["proof_routes"])
        | set(post_purchase_proof_spine["required_routes"])
        | {item["route"] for item in post_purchase_proof_spine["files"]}
        | set(outcome_room_bridge["routes"])
        | {item["route"] for item in proof_packet}
    )
    score = max(
        0,
        min(
            100,
            round(
                _score(board_pack) * 0.22
                + _score(commercial_offer_studio) * 0.18
                + _score(business_case) * 0.16
                + _score(pilot_launchpad) * 0.16
                + _score(enterprise_trust_center) * 0.14
                + _score(scenario_hub) * 0.08
                + _score(buyer_concierge) * 0.06
            ),
        ),
    )
    statuses = {
        _status(executive),
        _status(board_pack),
        _status(commercial_offer_studio),
        _status(enterprise_trust_center),
        _status(pilot_launchpad),
        _status(productization),
    }
    severe_risks = len([item for item in risk_burndown if item["severity"] in {"high", "critical"}])
    status = _ledger_status(score=score, statuses=statuses, severe_risks=severe_risks)
    report: dict[str, Any] = {
        "generated_at": _now(),
        "client": {
            "name": client_name,
            "config_path": config_path or "",
            "target_platform_version": target_platform_version or "",
        },
        "decision": {
            "status": status,
            "score": score,
            "headline": (
                "Outcome Ledger is ready: the purchase has measurable adoption metrics, proof windows and expansion paths."
                if status == "ready"
                else "Outcome Ledger is usable, but trust, pilot or productization caveats must be burned down before claiming rollout outcomes."
            ),
        },
        "summary": {
            "outcome_tiles": len(outcome_tiles),
            "adoption_steps": len(adoption_timeline),
            "success_metrics": len(success_metrics),
            "role_scorecards": len(role_scorecards),
            "risk_items": len(risk_burndown),
            "severe_risks": severe_risks,
            "expansion_paths": len(expansion_paths),
            "proof_items": len(proof_packet),
            "proof_routes": len(proof_routes),
            "governance_gates": len(governance_refresh["gates"]),
            "governance_windows": len(governance_refresh["windows"]),
            "acceptance_rollup_items": len(acceptance_rollup["items"]),
            "acceptance_rollup_ready": bool(acceptance_rollup["ready_to_claim"]),
            "acceptance_rollup_watch": acceptance_rollup["watch_items"],
            "acceptance_rollup_blocked": acceptance_rollup["blocked_items"],
            "post_purchase_ready": bool(post_purchase_proof_spine["ready_to_claim"]),
            "post_purchase_files": len(post_purchase_proof_spine["files"]),
            "outcome_room_roles": len(outcome_room_bridge["role_cards"]),
            "outcome_room_proofs": len(outcome_room_bridge["proof_readiness"]),
            "outcome_room_steps": len(outcome_room_bridge["meeting_flow"]),
            "outcome_room_open_first": len(outcome_room_bridge["open_first_path"]),
            "first_year_visible_value": value_realization["first_year_visible_value"],
            "ai_subscription_year": value_realization["ai_subscription_year"],
            "currency": value_realization["currency"],
            "recommended_motion": str(recommended_motion.get("id") or ""),
        },
        "value_realization": value_realization,
        "outcome_tiles": outcome_tiles,
        "adoption_timeline": adoption_timeline,
        "success_metrics": success_metrics,
        "role_scorecards": role_scorecards,
        "risk_burndown": risk_burndown,
        "expansion_paths": expansion_paths,
        "acceptance_rollup": acceptance_rollup,
        "governance_refresh": governance_refresh,
        "post_purchase_proof_spine": post_purchase_proof_spine,
        "outcome_room_bridge": outcome_room_bridge,
        "proof_packet": proof_packet,
        "exports": _exports(),
        "proof_routes": proof_routes,
        "source_signals": {
            "executive_status": _status(executive),
            "board_pack_status": _status(board_pack),
            "buyer_concierge_status": _status(buyer_concierge),
            "commercial_offer_status": _status(commercial_offer_studio),
            "trust_center_status": _status(enterprise_trust_center),
            "business_case_score": _score(business_case),
            "scenario_hub_status": _status(scenario_hub),
            "pilot_launchpad_status": _status(pilot_launchpad),
            "governance_refresh_ready": governance_refresh["ready"],
            "demo_command_center_status": _status(demo_command_center),
            "productization_status": _status(productization),
        },
        "caveats": [
            "Outcome Ledger v1 defines measurable outcomes and proof windows; real measured values require customer pilot data.",
            "Do not claim production ROI until acceptance checks and Evidence Bundle refresh are completed.",
            "If Trust Center or Board Pack is risky, position the next step as proof or hardening rather than full rollout success.",
        ],
        "download_name": "rentgen-outcome-ledger.md",
    }
    report["markdown"] = _markdown(report)
    return report
