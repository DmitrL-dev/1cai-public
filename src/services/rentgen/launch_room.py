"""Launch room that compresses the growing Rentgen surface into one start cockpit."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.services.rentgen.open_first_path import build_open_first_path

BUYER_ROOM_PACKET_ZIP = "rentgen-buyer-room-packet.zip"
BUYER_ROOM_PACKET_ENDPOINT = "/api/v1/management/buyer-room-packet"
BUYER_ROOM_PACKET_HASH_HEADER = "X-Buyer-Room-Packet-Sha256"
ARCHIVE_ACCEPTANCE_RECEIPT_MD = "archive-acceptance-receipt.md"
ARCHIVE_ACCEPTANCE_RECEIPT_JSON = "archive-acceptance-receipt.json"
ARCHIVE_VERIFICATION_PACKET_ZIP = "archive-verification-packet.zip"
ARCHIVE_VERIFICATION_PACKET_ENDPOINT = (
    "/api/v1/evidence-bundle/archive/verification-packet"
)
ARCHIVE_VERIFICATION_PACKET_HASH_HEADER = "X-Verification-Packet-Sha256"
EVIDENCE_ARCHIVE_HASH_HEADER = "X-Archive-Sha256"
KILLER_DEMO_ARCHIVE_HASH_HEADER = "X-Killer-Demo-Archive-Sha256"
KILLER_DEMO_MANIFEST_HASH_HEADER = "X-Killer-Demo-Manifest-Sha256"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _money(value: Any, currency: str) -> str:
    return f"{_int(value):,}".replace(",", " ") + f" {currency}"


def _score(report: dict[str, Any] | None, default: int = 0) -> int:
    if not report:
        return default
    if "score" in report:
        return _int(report.get("score"), default)
    return _int((report.get("decision") or {}).get("score"), default)


def _status(report: dict[str, Any] | None, default: str = "watch") -> str:
    if not report:
        return default
    return str(
        (report.get("decision") or {}).get("status") or report.get("status") or default
    )


def _phase_status(*reports: dict[str, Any]) -> str:
    statuses = {_status(report) for report in reports}
    if statuses & {"blocked", "critical", "fail", "risk"}:
        return "risk"
    if statuses & {"watch", "warn", "partial"}:
        return "watch"
    return "ready"


def _phase_score(*reports: dict[str, Any]) -> int:
    scores = [_score(report) for report in reports if report]
    if not scores:
        return 0
    return round(sum(scores) / len(scores))


def _journey_status(ready: bool, fallback: str = "watch") -> str:
    return "ready" if ready else fallback


def _next_best_action(
    *,
    buyer_concierge: dict[str, Any],
    board_pack: dict[str, Any],
    outcome_ledger: dict[str, Any],
    enterprise_trust_center: dict[str, Any],
    commercial_offer_studio: dict[str, Any],
) -> dict[str, str]:
    if _status(enterprise_trust_center) == "risk":
        return {
            "label": "Start with Trust Center",
            "route": "/enterprise-trust-center",
            "reason": "Trust/productization caveats are visible; reduce rollout anxiety before the buyer sees a price.",
        }
    if _status(board_pack) == "ready" and _score(commercial_offer_studio) >= 82:
        return {
            "label": "Open Board Pack",
            "route": "/board-pack",
            "reason": "The buying motion is strong enough to discuss approval and proof packet.",
        }
    if _status(outcome_ledger) in {"ready", "watch"} and _score(outcome_ledger) >= 70:
        return {
            "label": "Show Outcome Ledger",
            "route": "/outcome-ledger",
            "reason": "The buyer can see what changes after purchase, not just what the demo shows.",
        }
    action = buyer_concierge.get("default_next_action") or {}
    return {
        "label": str(action.get("label") or "Open Buyer Concierge"),
        "route": str(action.get("route") or "/buyer-concierge"),
        "reason": str(
            action.get("reason") or "Start from role or pain to avoid menu overload."
        ),
    }


def _launch_summary(
    *,
    buyer_concierge: dict[str, Any],
    board_pack: dict[str, Any],
    outcome_ledger: dict[str, Any],
    business_case: dict[str, Any],
    enterprise_trust_center: dict[str, Any],
) -> dict[str, Any]:
    board_summary = board_pack.get("summary") or {}
    outcome_summary = outcome_ledger.get("summary") or {}
    business_summary = business_case.get("summary") or {}
    currency = str(
        outcome_summary.get("currency")
        or business_summary.get("currency")
        or (business_case.get("assumptions") or {}).get("currency")
        or "RUB"
    )
    first_year_value = _int(
        outcome_summary.get("first_year_visible_value")
        or board_summary.get("first_year_visible_value")
        or business_summary.get("first_year_visible_value")
    )
    return {
        "one_line": "Start from role or pain, prove one 1C scenario, handle trust, approve a buying motion, then track outcomes.",
        "current_truth": (
            "Launch Room is a cockpit over implemented proof surfaces; it does not hide caveats or replace deep reports."
        ),
        "first_year_visible_value": first_year_value,
        "currency": currency,
        "value_anchor": f"{first_year_value:,}".replace(",", " ") + f" {currency}",
        "trust_status": _status(enterprise_trust_center),
        "board_status": _status(board_pack),
        "outcome_status": _status(outcome_ledger),
        "persona_cards": _int(
            (buyer_concierge.get("summary") or {}).get("persona_cards")
        ),
        "recommended_motion": str(
            outcome_summary.get("recommended_motion")
            or board_summary.get("recommended_offer")
            or ""
        ),
    }


def _purchase_spine(
    *,
    business_case: dict[str, Any],
    commercial_offer_studio: dict[str, Any],
    board_pack: dict[str, Any],
) -> dict[str, Any]:
    assumptions = business_case.get("assumptions") or {}
    business_summary = business_case.get("summary") or {}
    escape = business_case.get("subscription_escape_plan") or {}
    close_packet = commercial_offer_studio.get("close_packet") or {}
    one_page_order = close_packet.get("one_page_order") or {}
    dossier_escape = (commercial_offer_studio.get("procurement_dossier") or {}).get(
        "subscription_escape"
    ) or {}
    board_snapshot = board_pack.get("board_snapshot") or {}
    board_close = board_pack.get("board_close_packet") or {}
    board_order = board_close.get("one_page_order") or {}
    currency = str(
        escape.get("currency")
        or assumptions.get("currency")
        or board_snapshot.get("currency")
        or "RUB"
    )
    monthly_ai = _int(assumptions.get("monthly_ai_subscription_cost"))
    annual_ai = _int(
        escape.get("annual_ai_rent")
        or business_summary.get("ai_subscription_year")
        or monthly_ai * 12
    )
    three_year_ai = _int(
        escape.get("three_year_ai_rent")
        or business_summary.get("three_year_ai_subscription")
        or annual_ai * 3
    )
    local_license = _int(
        escape.get("local_license_anchor")
        or business_summary.get("local_license_anchor")
    )
    break_even = _int(
        escape.get("break_even_months")
        or business_summary.get("subscription_break_even_months")
    )
    ai_rent_months = _int(
        escape.get("ai_rent_equivalent_months")
        or business_summary.get("subscription_escape_months")
    )
    value_anchor = (
        str(
            one_page_order.get("value_anchor")
            or board_snapshot.get("value_anchor")
            or ""
        )
        or f"{_money(_int(business_summary.get('first_year_visible_value')), currency)} first-year visible value"
    )
    recommended_purchase = str(
        one_page_order.get("recommended_purchase")
        or board_order.get("recommended_purchase")
        or "Enterprise local license"
    )
    route = str(
        one_page_order.get("route")
        or board_order.get("route")
        or "/commercial-offer-studio"
    )
    core_evidence_files = [
        {
            "title": "Buyer Room Packet ZIP",
            "filename": BUYER_ROOM_PACKET_ZIP,
            "route": "/",
            "endpoint": BUYER_ROOM_PACKET_ENDPOINT,
            "hash_header": BUYER_ROOM_PACKET_HASH_HEADER,
        },
        {
            "title": "Killer Demo ZIP",
            "filename": "OPEN_FIRST_KILLER_DEMO.md",
            "route": "/killer-demo",
        },
        {
            "title": "Meeting Close Receipt",
            "filename": "MEETING_CLOSE_RECEIPT.md",
            "route": "/killer-demo",
        },
        {
            "title": "Post-Demo Activation Handoff",
            "filename": "POST_DEMO_ACTIVATION_HANDOFF.md",
            "route": "/pilot-launchpad",
        },
        {
            "title": "Archive Acceptance Receipt",
            "filename": ARCHIVE_ACCEPTANCE_RECEIPT_MD,
            "route": "/evidence-bundle",
        },
        {
            "title": "Verification Packet ZIP",
            "filename": ARCHIVE_VERIFICATION_PACKET_ZIP,
            "route": "/evidence-bundle",
            "endpoint": ARCHIVE_VERIFICATION_PACKET_ENDPOINT,
            "hash_header": ARCHIVE_VERIFICATION_PACKET_HASH_HEADER,
        },
    ]
    business_evidence_files = list(
        escape.get("evidence_files")
        or [
            {
                "title": "Business Case",
                "filename": "business-case.md",
                "route": "/business-case",
            },
            {
                "title": "Board Pack",
                "filename": "board-pack.md",
                "route": "/board-pack",
            },
            {
                "title": "Outcome Ledger",
                "filename": "rentgen-outcome-ledger.md",
                "route": "/outcome-ledger",
            },
            {
                "title": "Evidence Bundle",
                "filename": "OPEN_FIRST.md",
                "route": "/evidence-bundle",
            },
        ]
    )
    evidence_files: list[dict[str, str]] = []
    seen_evidence: set[tuple[str, str]] = set()
    for item in [*core_evidence_files, *business_evidence_files]:
        filename = str(item.get("filename") or "")
        item_route = str(item.get("route") or "")
        key = (filename, item_route)
        if not filename or key in seen_evidence:
            continue
        seen_evidence.add(key)
        evidence_files.append(
            {
                "title": str(item.get("title") or filename),
                "filename": filename,
                "route": item_route or "/evidence-bundle",
            }
        )
    proof_routes = list(
        dict.fromkeys(
            [
                "/killer-demo",
                "/",
                "/business-case",
                "/commercial-offer-studio",
                "/board-pack",
                "/pilot-launchpad",
                "/outcome-ledger",
                "/evidence-bundle",
                route,
            ]
        )
    )
    purchase_status = "ready" if local_license and three_year_ai else "watch"
    return {
        "status": purchase_status,
        "headline": "Buy a local 1C evidence asset, not another endless AI rent line.",
        "buyer_line": str(
            escape.get("decision_line")
            or dossier_escape.get("decision_line")
            or (
                f"At {monthly_ai:,}".replace(",", " ")
                + f" {currency}/month, three-year AI rent is {_money(three_year_ai, currency)}; "
                + f"anchor the purchase to local license value at {_money(local_license, currency)}."
            )
        ),
        "value_anchor": value_anchor,
        "monthly_ai_rent": _money(monthly_ai, currency),
        "annual_ai_rent": str(
            dossier_escape.get("annual_ai_rent") or _money(annual_ai, currency)
        ),
        "three_year_ai_rent": str(
            dossier_escape.get("three_year_ai_rent")
            or one_page_order.get("three_year_ai_rent")
            or board_snapshot.get("three_year_ai_rent")
            or _money(three_year_ai, currency)
        ),
        "local_license_anchor": str(
            dossier_escape.get("local_license_anchor")
            or one_page_order.get("local_license_anchor")
            or board_snapshot.get("local_license_anchor")
            or _money(local_license, currency)
        ),
        "break_even": str(
            one_page_order.get("break_even")
            or board_snapshot.get("break_even")
            or (
                f"{break_even} months by visible value"
                if break_even
                else "review Business Case"
            )
        ),
        "ai_rent_equivalent_months": ai_rent_months,
        "recommended_purchase": recommended_purchase,
        "commercial_frame": str(
            one_page_order.get("commercial_frame")
            or board_order.get("commercial_frame")
            or "fixed local license"
        ),
        "first_invoice_trigger": str(
            one_page_order.get("first_invoice_trigger")
            or board_order.get("first_invoice_trigger")
            or "Buyer names owner, scope, date and accepted proof artifacts."
        ),
        "route": route,
        "proof_routes": proof_routes,
        "evidence_files": evidence_files,
        "procurement_handoff": _procurement_handoff(purchase_status=purchase_status),
        "guardrails": list(
            escape.get("guardrails") or dossier_escape.get("guardrails") or []
        ),
    }


def _procurement_handoff(*, purchase_status: str) -> dict[str, Any]:
    return {
        "status": purchase_status,
        "title": "Procurement-ready handoff",
        "owner_line": (
            "Use the same order as the first screen: Buyer Room Packet, Evidence ZIP, Killer Demo ZIP, "
            "Verification Packet ZIP, then close receipt and activation handoff."
        ),
        "acceptance": (
            "Launch Room is procurement-ready only when Buyer Room Packet hash, both archive hashes, "
            "the verification packet hash, close receipt and activation handoff are recorded together."
        ),
        "open_order": [
            {
                "step": 1,
                "label": "Buyer Room Packet ZIP",
                "route": "/",
                "endpoint": BUYER_ROOM_PACKET_ENDPOINT,
                "file": BUYER_ROOM_PACKET_ZIP,
                "hash_header": BUYER_ROOM_PACKET_HASH_HEADER,
                "check": "Open the room packet first and record its packet hash.",
            },
            {
                "step": 2,
                "label": "Evidence Bundle ZIP",
                "route": "/evidence-bundle",
                "file": "Evidence Bundle ZIP",
                "hash_header": EVIDENCE_ARCHIVE_HASH_HEADER,
                "check": "Record the source evidence archive hash.",
            },
            {
                "step": 3,
                "label": "Killer Demo ZIP",
                "route": "/killer-demo",
                "file": "Killer Demo ZIP",
                "hash_header": KILLER_DEMO_ARCHIVE_HASH_HEADER,
                "check": "Record the close-room archive hash.",
            },
            {
                "step": 4,
                "label": "Verification Packet ZIP",
                "route": "/evidence-bundle",
                "endpoint": ARCHIVE_VERIFICATION_PACKET_ENDPOINT,
                "file": ARCHIVE_VERIFICATION_PACKET_ZIP,
                "hash_header": ARCHIVE_VERIFICATION_PACKET_HASH_HEADER,
                "check": "Attach the pair-level verification packet.",
            },
            {
                "step": 5,
                "label": "Close Receipt",
                "route": "/killer-demo",
                "file": "MEETING_CLOSE_RECEIPT.md",
                "hash_header": "",
                "check": "Record accepted roles and the next paid step.",
            },
            {
                "step": 6,
                "label": "Activation Handoff",
                "route": "/pilot-launchpad",
                "file": "POST_DEMO_ACTIVATION_HANDOFF.md",
                "hash_header": "",
                "check": "Start Day 0/7 activation from the accepted handoff.",
            },
        ],
        "attachments": [
            {
                "title": "Buyer Room Packet",
                "route": "/",
                "endpoint": BUYER_ROOM_PACKET_ENDPOINT,
                "file": BUYER_ROOM_PACKET_ZIP,
                "hash_header": BUYER_ROOM_PACKET_HASH_HEADER,
                "why": "Open-first room packet aligned with Home and Buyer Brief.",
            },
            {
                "title": "Archive acceptance receipt",
                "route": "/evidence-bundle",
                "file": ARCHIVE_ACCEPTANCE_RECEIPT_MD,
                "why": "Records Evidence and Killer Demo archive boundaries.",
            },
            {
                "title": "Archive acceptance JSON",
                "route": "/evidence-bundle",
                "file": ARCHIVE_ACCEPTANCE_RECEIPT_JSON,
                "why": "Machine-readable procurement receipt.",
            },
            {
                "title": "Killer Demo manifest",
                "route": "/killer-demo",
                "file": "killer-demo-manifest.json",
                "hash_header": KILLER_DEMO_MANIFEST_HASH_HEADER,
                "why": "Verifies close-room overlay files.",
            },
            {
                "title": "Verification Packet ZIP",
                "route": "/evidence-bundle",
                "endpoint": ARCHIVE_VERIFICATION_PACKET_ENDPOINT,
                "file": ARCHIVE_VERIFICATION_PACKET_ZIP,
                "hash_header": ARCHIVE_VERIFICATION_PACKET_HASH_HEADER,
                "why": "Proves the two archives as one checked pair.",
            },
        ],
        "routes": [
            "/",
            "/evidence-bundle",
            "/killer-demo",
            "/pilot-launchpad",
            "/outcome-ledger",
        ],
    }


def _path_phases(
    *,
    buyer_concierge: dict[str, Any],
    scenario_hub: dict[str, Any],
    demo_command_center: dict[str, Any],
    enterprise_trust_center: dict[str, Any],
    commercial_offer_studio: dict[str, Any],
    board_pack: dict[str, Any],
    outcome_ledger: dict[str, Any],
    evidence_bundle_artifacts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            "id": "orient",
            "title": "Orient",
            "route": "/buyer-concierge",
            "status": _phase_status(buyer_concierge),
            "score": _phase_score(buyer_concierge),
            "question": "Who is in the room and what pain do they recognize?",
            "exit_criteria": "Role or pain selected; shortest path is visible.",
            "proof": f"{_int((buyer_concierge.get('summary') or {}).get('persona_cards'))} role cards and default next action.",
        },
        {
            "id": "prove",
            "title": "Prove",
            "route": "/scenario-hub",
            "status": _phase_status(scenario_hub, demo_command_center),
            "score": _phase_score(scenario_hub, demo_command_center),
            "question": "Which 1C pain can we prove in minutes?",
            "exit_criteria": "One scenario, one proof route and one expected reaction are chosen.",
            "proof": f"{_int((scenario_hub.get('summary') or {}).get('scenarios'))} scenarios; Demo Command status {_status(demo_command_center)}.",
        },
        {
            "id": "trust",
            "title": "Trust",
            "route": "/enterprise-trust-center",
            "status": _phase_status(enterprise_trust_center),
            "score": _phase_score(enterprise_trust_center),
            "question": "Can security and architecture approve a local pilot or hardening scope?",
            "exit_criteria": "Install mode, caveats and approval artifacts have owners.",
            "proof": f"{_int((enterprise_trust_center.get('summary') or {}).get('controls'))} trust controls.",
        },
        {
            "id": "approve",
            "title": "Approve",
            "route": "/board-pack",
            "status": _phase_status(board_pack, commercial_offer_studio),
            "score": _phase_score(board_pack, commercial_offer_studio),
            "question": "What exact buying motion should the board approve?",
            "exit_criteria": "Board Pack and Offer Studio agree on next paid step.",
            "proof": f"{_int((board_pack.get('summary') or {}).get('decision_items'))} board decisions; {_int((commercial_offer_studio.get('summary') or {}).get('offers'))} offers.",
        },
        {
            "id": "adopt",
            "title": "Adopt",
            "route": "/outcome-ledger",
            "status": _phase_status(outcome_ledger),
            "score": _phase_score(outcome_ledger),
            "question": "What changes after the buyer says yes?",
            "exit_criteria": "7/30/90-day outcomes and risk burndown are visible.",
            "proof": f"{_int((outcome_ledger.get('summary') or {}).get('success_metrics'))} success metrics.",
        },
        {
            "id": "export",
            "title": "Export",
            "route": "/evidence-bundle",
            "status": "ready" if evidence_bundle_artifacts else "watch",
            "score": min(100, 60 + len(evidence_bundle_artifacts) * 3),
            "question": "Which artifacts survive the meeting?",
            "exit_criteria": "Hashed JSON/Markdown packet contains buyer, trust, offer and outcome proof.",
            "proof": f"{len(evidence_bundle_artifacts)} artifacts available for bundle context.",
        },
    ]


def _role_switchboard(
    *,
    buyer_concierge: dict[str, Any],
    board_pack: dict[str, Any],
    outcome_ledger: dict[str, Any],
) -> list[dict[str, str]]:
    role_outcomes = {
        str(item.get("role")): item
        for item in outcome_ledger.get("role_scorecards", [])
        if item.get("role")
    }
    board_roles = {
        str(item.get("role")): item
        for item in board_pack.get("committee_map", [])
        if item.get("role")
    }
    rows: list[dict[str, str]] = []
    for card in buyer_concierge.get("persona_cards", []):
        role = str(card.get("role") or "Stakeholder")
        outcome = role_outcomes.get(role) or {}
        board = board_roles.get(role) or {}
        rows.append(
            {
                "role": role,
                "first_click": str(
                    card.get("start_route")
                    or outcome.get("proof_route")
                    or "/buyer-concierge"
                ),
                "second_click": str(card.get("second_route") or "/scenario-hub"),
                "spark": str(
                    card.get("spark")
                    or outcome.get("spark")
                    or card.get("first_question")
                    or ""
                ),
                "must_believe": str(
                    board.get("must_believe") or card.get("proof") or ""
                ),
                "close": str(
                    outcome.get("owner_action")
                    or board.get("close_line")
                    or card.get("buy_trigger")
                    or ""
                ),
            }
        )
    return rows


def _meeting_modes(
    *,
    board_pack: dict[str, Any],
    outcome_ledger: dict[str, Any],
) -> list[dict[str, Any]]:
    board_script = board_pack.get("board_room_script") or []
    adoption = outcome_ledger.get("adoption_timeline") or []
    return [
        {
            "id": "three-minute",
            "title": "3-minute rescue",
            "audience": "buyer is confused or meeting is cut short",
            "minutes": 3,
            "steps": [
                {"route": "/buyer-concierge", "label": "Pick role/pain"},
                {"route": "/board-pack", "label": "Show buying motion"},
                {"route": "/enterprise-trust-center", "label": "Name trust caveat"},
            ],
            "close": "Ask which proof artifact is required before a paid next step.",
        },
        {
            "id": "eight-minute-board",
            "title": "8-minute board route",
            "audience": "director + mixed room",
            "minutes": 8,
            "steps": [
                {
                    "route": str(item.get("route") or "/board-pack"),
                    "label": str(item.get("speaker") or item.get("minute") or "step"),
                }
                for item in board_script[:5]
            ]
            or [
                {"route": "/buyer-concierge", "label": "orient"},
                {"route": "/scenario-hub", "label": "prove"},
                {"route": "/board-pack", "label": "approve"},
            ],
            "close": "Approve proof, hardening or local pilot and attach Evidence Bundle.",
        },
        {
            "id": "security-first",
            "title": "Security-first route",
            "audience": "CIO / security / architecture",
            "minutes": 6,
            "steps": [
                {"route": "/enterprise-trust-center", "label": "trust controls"},
                {"route": "/productization", "label": "SBOM/offline"},
                {"route": "/rights-rls", "label": "rights/RLS"},
                {"route": "/evidence-bundle", "label": "hash manifest"},
            ],
            "close": "Convert blockers into hardening scope or accepted pilot risk.",
        },
        {
            "id": "post-purchase",
            "title": "Post-purchase adoption route",
            "audience": "sponsor + delivery lead",
            "minutes": 10,
            "steps": [
                {
                    "route": str(item.get("route") or "/outcome-ledger"),
                    "label": str(item.get("window") or "outcome"),
                }
                for item in adoption[:6]
            ],
            "close": "Book Day 7 proof and Day 30 acceptance refresh.",
        },
    ]


def _buyer_journey(
    *,
    commercial_offer_studio: dict[str, Any],
    board_pack: dict[str, Any],
    pilot_launchpad: dict[str, Any],
    outcome_ledger: dict[str, Any],
) -> dict[str, Any]:
    close_packet = commercial_offer_studio.get("close_packet") or {}
    board_close = board_pack.get("board_close_packet") or {}
    activation = pilot_launchpad.get("activation_contract") or {}
    governance = outcome_ledger.get("governance_refresh") or {}
    acceptance = outcome_ledger.get("acceptance_rollup") or {}
    outcome_summary = outcome_ledger.get("summary") or {}
    outcome_proof_routes = len(
        governance.get("proof_routes") or outcome_ledger.get("proof_routes") or []
    )
    acceptance_items = _int(
        outcome_summary.get("acceptance_rollup_items")
        or len(acceptance.get("items") or [])
    )
    acceptance_blocked = _int(
        outcome_summary.get("acceptance_rollup_blocked")
        or acceptance.get("blocked_items")
    )
    acceptance_watch = _int(
        outcome_summary.get("acceptance_rollup_watch") or acceptance.get("watch_items")
    )

    close_ready = bool(
        board_close.get(
            "ready_to_close",
            close_packet.get("ready_to_close", _status(board_pack) == "ready"),
        )
    )
    activation_ready = bool(
        activation.get("ready_to_activate", _status(pilot_launchpad) == "ready")
    )
    governance_ready = bool(governance.get("ready", _status(outcome_ledger) == "ready"))
    claim_ready = bool(
        outcome_summary.get(
            "acceptance_rollup_ready", acceptance.get("ready_to_claim", False)
        )
    )
    realize_status = "risk" if acceptance_blocked else _status(outcome_ledger)
    steps = [
        {
            "id": "close",
            "title": "Close",
            "route": "/board-pack",
            "status": _journey_status(close_ready),
            "signal": str(
                board_close.get("primary_ask")
                or close_packet.get("primary_ask")
                or "Approve the paid motion with proof attached."
            ),
            "action": str(
                (board_close.get("one_page_order") or {}).get("recommended_purchase")
                or (close_packet.get("one_page_order") or {}).get(
                    "recommended_purchase"
                )
                or "Selected paid next step"
            ),
            "proof": f"{len(board_close.get('checkout') or close_packet.get('checkout') or [])} checkout gates.",
        },
        {
            "id": "activate",
            "title": "Activate",
            "route": "/pilot-launchpad",
            "status": _journey_status(activation_ready),
            "signal": str(
                activation.get("primary_ask")
                or "Start the paid pilot with owner, date and acceptance gates."
            ),
            "action": str(
                activation.get("selected_offer_title") or "Pilot Launchpad activation"
            ),
            "proof": f"{len(activation.get('gates') or [])} activation gates.",
        },
        {
            "id": "govern",
            "title": "Govern",
            "route": "/approvals",
            "status": _journey_status(governance_ready),
            "signal": str(
                governance.get("refresh_line")
                or "Refresh approvals, audit and evidence before claiming rollout outcomes."
            ),
            "action": "Verify approvals, audit chain and Evidence Bundle.",
            "proof": f"{len(governance.get('gates') or [])} governance gates and {len(governance.get('windows') or [])} proof windows.",
        },
        {
            "id": "realize",
            "title": "Realize",
            "route": "/outcome-ledger",
            "status": realize_status,
            "signal": str(
                (outcome_ledger.get("value_realization") or {}).get(
                    "recommended_motion"
                )
                or outcome_summary.get("recommended_motion")
                or "Track adoption outcomes."
            ),
            "action": "Use Day 7/30/60/90 outcomes for rollout, renewal, hardening or expansion.",
            "proof": f"{_int(outcome_summary.get('success_metrics'))} success metrics, {acceptance_items} acceptance rows and {outcome_proof_routes} proof routes.",
        },
    ]
    return {
        "steps": steps,
        "ready_steps": len([item for item in steps if item["status"] == "ready"]),
        "risk_steps": len([item for item in steps if item["status"] == "risk"]),
        "checkout_gates": len(
            board_close.get("checkout") or close_packet.get("checkout") or []
        ),
        "activation_gates": len(activation.get("gates") or []),
        "governance_gates": len(governance.get("gates") or []),
        "acceptance_items": acceptance_items,
        "acceptance_watch": acceptance_watch,
        "acceptance_blocked": acceptance_blocked,
        "claim_ready": claim_ready,
        "next_route": next(
            (item["route"] for item in steps if item["status"] != "ready"),
            "/outcome-ledger",
        ),
        "buyer_line": "One path now connects purchase, paid activation, governance proof, acceptance sign-off and measurable outcomes.",
    }


def _route_health(
    *,
    buyer_concierge: dict[str, Any],
    scenario_hub: dict[str, Any],
    enterprise_trust_center: dict[str, Any],
    commercial_offer_studio: dict[str, Any],
    board_pack: dict[str, Any],
    outcome_ledger: dict[str, Any],
    evidence_bundle_artifacts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    reports = [
        ("Buyer Concierge", "/buyer-concierge", buyer_concierge),
        ("Scenario Hub", "/scenario-hub", scenario_hub),
        ("Trust Center", "/enterprise-trust-center", enterprise_trust_center),
        ("Offer Studio", "/commercial-offer-studio", commercial_offer_studio),
        ("Board Pack", "/board-pack", board_pack),
        ("Outcome Ledger", "/outcome-ledger", outcome_ledger),
    ]
    rows = [
        {
            "title": title,
            "route": route,
            "status": _status(report),
            "score": _score(report),
            "headline": str((report.get("decision") or {}).get("headline") or ""),
        }
        for title, route, report in reports
    ]
    rows.append(
        {
            "title": "Evidence Bundle",
            "route": "/evidence-bundle",
            "status": "ready" if evidence_bundle_artifacts else "watch",
            "score": min(100, 60 + len(evidence_bundle_artifacts) * 3),
            "headline": f"{len(evidence_bundle_artifacts)} upstream artifacts available.",
        }
    )
    return rows


def _anti_confusion_cards(buyer_concierge: dict[str, Any]) -> list[dict[str, str]]:
    cards = [
        {
            "signal": "Buyer sees many routes and asks what to open.",
            "response": "Stay in Launch Room and follow next best action.",
            "route": "/launch-room",
        },
        {
            "signal": "Director wants price before proof.",
            "response": "Open Board Pack, then Offer Studio; keep value and proof packet together.",
            "route": "/board-pack",
        },
        {
            "signal": "Security concern dominates the room.",
            "response": "Switch to Trust Center and convert caveats into hardening scope.",
            "route": "/enterprise-trust-center",
        },
        {
            "signal": "Someone asks what happens after purchase.",
            "response": "Open Outcome Ledger and show 7/30/90-day proof windows.",
            "route": "/outcome-ledger",
        },
        {
            "signal": "Procurement asks who approved and how it is audited.",
            "response": "Open Approvals, Audit and Evidence Bundle as one governance proof path.",
            "route": "/approvals",
        },
    ]
    for item in buyer_concierge.get("confusion_guardrails", [])[:4]:
        cards.append(
            {
                "signal": str(item.get("signal") or ""),
                "response": str(item.get("response") or ""),
                "route": str(item.get("route") or "/buyer-concierge"),
            }
        )
    return cards


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
        {
            "title": "Killer Demo ZIP open-first",
            "filename": "OPEN_FIRST_KILLER_DEMO.md",
            "route": "/killer-demo",
        },
        {
            "title": "Meeting Close Receipt",
            "filename": "MEETING_CLOSE_RECEIPT.md",
            "route": "/killer-demo",
        },
        {
            "title": "Post-Demo Activation Handoff",
            "filename": "POST_DEMO_ACTIVATION_HANDOFF.md",
            "route": "/pilot-launchpad",
        },
        {
            "title": "Archive Acceptance Receipt",
            "filename": ARCHIVE_ACCEPTANCE_RECEIPT_MD,
            "route": "/evidence-bundle",
        },
        {
            "title": "Archive Acceptance Receipt JSON",
            "filename": ARCHIVE_ACCEPTANCE_RECEIPT_JSON,
            "route": "/evidence-bundle",
        },
        {
            "title": "Verification Packet ZIP",
            "filename": ARCHIVE_VERIFICATION_PACKET_ZIP,
            "route": "/evidence-bundle",
            "endpoint": ARCHIVE_VERIFICATION_PACKET_ENDPOINT,
            "hash_header": ARCHIVE_VERIFICATION_PACKET_HASH_HEADER,
        },
        {
            "title": "Killer Demo manifest",
            "filename": "killer-demo-manifest.json",
            "route": "/killer-demo",
        },
        {
            "title": "Launch Room markdown",
            "filename": "rentgen-launch-room.md",
            "route": "/launch-room",
        },
        {
            "title": "Buyer Concierge markdown",
            "filename": "rentgen-buyer-concierge.md",
            "route": "/buyer-concierge",
        },
        {
            "title": "Board Pack markdown",
            "filename": "rentgen-board-pack.md",
            "route": "/board-pack",
        },
        {
            "title": "Outcome Ledger markdown",
            "filename": "rentgen-outcome-ledger.md",
            "route": "/outcome-ledger",
        },
        {
            "title": "Enterprise Trust Center markdown",
            "filename": "rentgen-enterprise-trust-center.md",
            "route": "/enterprise-trust-center",
        },
        {
            "title": "Governance Proof markdown",
            "filename": "governance-proof.md",
            "route": "/approvals",
        },
        {
            "title": "Audit verification/export",
            "filename": "rentgen-audit-log.jsonl",
            "route": "/audit",
        },
        {
            "title": "Evidence Bundle manifest",
            "filename": "evidence-bundle-manifest.json",
            "route": "/evidence-bundle",
        },
    ]


def _buyer_room_bridge(
    *,
    buyer_brief: dict[str, Any] | None,
    next_best_action: dict[str, str],
    purchase_spine: dict[str, Any],
    role_switchboard: list[dict[str, str]],
) -> dict[str, Any]:
    brief = buyer_brief or {}
    primary = dict(brief.get("primary_motion") or {})
    if not primary:
        primary = {
            "label": next_best_action["label"],
            "route": next_best_action["route"],
            "status": purchase_spine.get("status") or "watch",
            "ask": "Show the buyer one route, one proof packet and one next paid step.",
            "reason": next_best_action["reason"],
        }
    role_cards = list(brief.get("role_cards") or [])
    if not role_cards:
        role_cards = [
            {
                "role": item["role"].casefold(),
                "title": item["role"],
                "route": item["first_click"],
                "status": "watch",
                "spark": item["spark"],
                "proof_file": "rentgen-launch-room.md",
            }
            for item in role_switchboard[:5]
        ]
    proof_readiness = list(brief.get("proof_readiness") or [])
    if not proof_readiness:
        proof_readiness = [
            {
                "id": "evidence-bundle",
                "title": "Forwardable evidence",
                "route": "/evidence-bundle",
                "status": purchase_spine.get("status") or "watch",
                "signal": "Hashed launch, commercial and governance files are ready to assemble.",
                "file": "OPEN_FIRST.md",
            },
            {
                "id": "governance",
                "title": "Approval gates",
                "route": "/approvals",
                "status": "ready",
                "signal": "Approval and audit routes are visible before paid work starts.",
                "file": "governance-proof.md",
            },
        ]
    meeting_flow = list(brief.get("meeting_flow") or [])
    if not meeting_flow:
        meeting_flow = [
            {
                "step": 1,
                "label": "Orient",
                "route": "/buyer-concierge",
                "line": "Pick the role in the room.",
            },
            {
                "step": 2,
                "label": "Prove",
                "route": "/killer-demo",
                "line": "Show one proof path.",
            },
            {
                "step": 3,
                "label": "Ask",
                "route": primary["route"],
                "line": str(primary.get("ask") or ""),
            },
            {
                "step": 4,
                "label": "Forward",
                "route": "/evidence-bundle",
                "line": "Attach the proof packet.",
            },
        ]
    open_first_path = build_open_first_path(
        existing_path=brief.get("open_first_path"),
        proof_readiness=proof_readiness,
        primary=primary,
        meeting_flow=meeting_flow,
        source="launch-room-fallback",
        orient_title="Launch Room",
        orient_route="/launch-room",
        orient_line="Open one buyer cockpit.",
        orient_status=str(
            primary.get("status") or purchase_spine.get("status") or "watch"
        ),
        prove_line="Show one proof path.",
        prove_status=str(purchase_spine.get("status") or "watch"),
        close_route=str(primary.get("route") or "/killer-demo"),
        close_line=str(primary.get("ask") or "Name the next paid step."),
        close_status=str(purchase_spine.get("status") or "watch"),
        verify_line="Attach the pair-level archive verification packet.",
    )
    routes = sorted(
        {
            str(primary.get("route") or "/launch-room"),
            *[str(item.get("route") or "") for item in role_cards],
            *[str(item.get("route") or "") for item in proof_readiness],
            *[str(item.get("route") or "") for item in meeting_flow],
            *[str(item.get("route") or "") for item in open_first_path],
        }
        - {""}
    )
    fallback_score = 82 if purchase_spine.get("status") == "ready" else 70
    return {
        "status": str(
            brief.get("purchase_status")
            or primary.get("status")
            or purchase_spine.get("status")
            or "watch"
        ),
        "score": _int(brief.get("score"), fallback_score),
        "source": str(brief.get("source") or "launch-room-derived"),
        "room_line": str(
            brief.get("room_line")
            or f"{primary.get('label', next_best_action['label'])}: {primary.get('ask', next_best_action['reason'])}"
        ),
        "primary_motion": {
            "label": str(primary.get("label") or next_best_action["label"]),
            "route": str(primary.get("route") or next_best_action["route"]),
            "status": str(
                primary.get("status") or purchase_spine.get("status") or "watch"
            ),
            "ask": str(primary.get("ask") or "Name the next paid step."),
            "reason": str(primary.get("reason") or next_best_action["reason"]),
        },
        "role_cards": role_cards[:5],
        "proof_readiness": proof_readiness[:4],
        "meeting_flow": meeting_flow[:4],
        "open_first_path": open_first_path[:4],
        "files": [
            BUYER_ROOM_PACKET_ZIP,
            "buyer-brief.md",
            "buyer-pulse.md",
            "open-first-path.md",
            "OPEN_FIRST_KILLER_DEMO.md",
            "MEETING_CLOSE_RECEIPT.md",
            "POST_DEMO_ACTIVATION_HANDOFF.md",
            ARCHIVE_ACCEPTANCE_RECEIPT_MD,
            ARCHIVE_VERIFICATION_PACKET_ZIP,
            "rentgen-launch-room.md",
            "OPEN_FIRST.md",
        ],
        "routes": routes,
    }


def _launch_status(*, score: int, phases: list[dict[str, Any]]) -> str:
    if any(item["status"] == "risk" for item in phases):
        return "risk"
    if score >= 82 and all(item["status"] == "ready" for item in phases[:5]):
        return "ready"
    return "watch"


def _markdown(report: dict[str, Any]) -> str:
    purchase = report.get("purchase_spine") or {}
    buyer_room = report.get("buyer_room_bridge") or {}
    lines = [
        "# 1C Rentgen Launch Room",
        "",
        f"Client: **{report['client']['name']}**",
        f"Status: **{report['decision']['status'].upper()}** / score **{report['decision']['score']}**",
        f"Next best action: **{report['next_best_action']['label']}** (`{report['next_best_action']['route']}`)",
        "",
        "## Purchase Spine",
        "",
        f"- Status: **{purchase.get('status', 'unknown')}**",
        f"- Recommended purchase: **{purchase.get('recommended_purchase', '')}** (`{purchase.get('route', '/commercial-offer-studio')}`)",
        f"- AI/month: **{purchase.get('monthly_ai_rent', 'n/a')}**",
        f"- Three-year AI rent: **{purchase.get('three_year_ai_rent', 'n/a')}**",
        f"- Local license anchor: **{purchase.get('local_license_anchor', 'n/a')}**",
        f"- Break-even: **{purchase.get('break_even', 'n/a')}**",
        f"- Buyer line: {purchase.get('buyer_line', '')}",
        "",
        "## Purchase Artifacts",
        "",
    ]
    for item in purchase.get("evidence_files", []):
        lines.append(
            f"- **{item.get('title', '')}** (`{item.get('route', '/launch-room')}`): `{item.get('filename', '')}`"
        )
    handoff = purchase.get("procurement_handoff") or {}
    if handoff:
        lines.extend(
            [
                "",
                "## Procurement Handoff",
                "",
                f"- Status: **{handoff.get('status', 'unknown')}**",
                f"- Owner line: {handoff.get('owner_line', '')}",
                f"- Acceptance: {handoff.get('acceptance', '')}",
            ]
        )
        for item in handoff.get("open_order", []):
            header = (
                f" / `{item.get('hash_header')}`" if item.get("hash_header") else ""
            )
            lines.append(
                f"- **{item.get('step')}. {item.get('label', '')}** (`{item.get('route', '/launch-room')}`): "
                f"`{item.get('file', '')}`{header} - {item.get('check', '')}"
            )
    lines.extend(
        [
            "",
            "## Buyer Room Bridge",
            "",
            f"- Status: **{buyer_room.get('status', 'unknown')}** / score **{buyer_room.get('score', 0)}**",
            f"- Room line: {buyer_room.get('room_line', '')}",
            f"- Primary motion: **{(buyer_room.get('primary_motion') or {}).get('label', '')}** (`{(buyer_room.get('primary_motion') or {}).get('route', '/launch-room')}`)",
            f"- Files: {', '.join(buyer_room.get('files', []))}",
            "",
            "### Open-First Path",
            "",
        ]
    )
    for item in buyer_room.get("open_first_path", []):
        lines.append(
            f"- **{item.get('step', '')}. {item.get('label', '')}** (`{item.get('route', '/launch-room')}`): "
            f"`{item.get('file', '')}` - {item.get('line', '')}"
        )
    lines.extend(
        [
            "",
            "## Path Phases",
            "",
        ]
    )
    for item in report["path_phases"]:
        lines.append(
            f"- **{item['title']}**: {item['status']} / {item['score']} (`{item['route']}`) - {item['exit_criteria']}"
        )
    lines.extend(["", "## Role Switchboard", ""])
    for item in report["role_switchboard"]:
        lines.append(
            f"- **{item['role']}**: first `{item['first_click']}`, then `{item['second_click']}`. {item['spark']}"
        )
    lines.extend(["", "## Meeting Modes", ""])
    for item in report["meeting_modes"]:
        lines.append(f"- **{item['title']}** ({item['minutes']} min): {item['close']}")
    journey = report.get("buyer_journey") or {}
    if journey:
        lines.extend(["", "## Buyer Journey", ""])
        lines.append(f"- {journey.get('buyer_line', '')}")
        lines.append(
            f"- Claim ready: **{bool(journey.get('claim_ready'))}**; "
            f"acceptance rows/watch/blocked: **{journey.get('acceptance_items', 0)}** / "
            f"**{journey.get('acceptance_watch', 0)}** / **{journey.get('acceptance_blocked', 0)}**"
        )
        for item in journey.get("steps", []):
            lines.append(
                f"- **{item.get('title', '')}** ({item.get('status', '')}, `{item.get('route', '/launch-room')}`): {item.get('signal', '')}"
            )
    lines.extend(["", "## Anti-confusion", ""])
    for item in report["anti_confusion_cards"]:
        lines.append(
            f"- **{item['signal']}** -> {item['response']} (`{item['route']}`)"
        )
    lines.extend(["", "## Caveats", ""])
    lines.extend(f"- {item}" for item in report["caveats"])
    return "\n".join(lines)


def build_launch_room(
    *,
    executive: dict[str, Any],
    buyer_concierge: dict[str, Any],
    scenario_hub: dict[str, Any],
    demo_command_center: dict[str, Any],
    enterprise_trust_center: dict[str, Any],
    commercial_offer_studio: dict[str, Any],
    board_pack: dict[str, Any],
    outcome_ledger: dict[str, Any],
    business_case: dict[str, Any],
    pilot_launchpad: dict[str, Any] | None = None,
    buyer_brief: dict[str, Any] | None = None,
    evidence_bundle_artifacts: list[dict[str, Any]] | None = None,
    client_name: str = "Demo client",
    config_path: str | None = None,
    target_platform_version: str | None = None,
) -> dict[str, Any]:
    """Build a single launch cockpit over buyer path, trust, approval and outcomes."""

    artifacts = list(evidence_bundle_artifacts or [])
    path_phases = _path_phases(
        buyer_concierge=buyer_concierge,
        scenario_hub=scenario_hub,
        demo_command_center=demo_command_center,
        enterprise_trust_center=enterprise_trust_center,
        commercial_offer_studio=commercial_offer_studio,
        board_pack=board_pack,
        outcome_ledger=outcome_ledger,
        evidence_bundle_artifacts=artifacts,
    )
    score = max(
        0,
        min(
            100,
            round(
                _score(buyer_concierge) * 0.14
                + _score(scenario_hub) * 0.12
                + _score(demo_command_center) * 0.10
                + _score(enterprise_trust_center) * 0.18
                + _score(commercial_offer_studio) * 0.14
                + _score(board_pack) * 0.18
                + _score(outcome_ledger) * 0.14
            ),
        ),
    )
    status = _launch_status(score=score, phases=path_phases)
    next_best_action = _next_best_action(
        buyer_concierge=buyer_concierge,
        board_pack=board_pack,
        outcome_ledger=outcome_ledger,
        enterprise_trust_center=enterprise_trust_center,
        commercial_offer_studio=commercial_offer_studio,
    )
    role_switchboard = _role_switchboard(
        buyer_concierge=buyer_concierge,
        board_pack=board_pack,
        outcome_ledger=outcome_ledger,
    )
    buyer_journey = _buyer_journey(
        commercial_offer_studio=commercial_offer_studio,
        board_pack=board_pack,
        pilot_launchpad=pilot_launchpad or {},
        outcome_ledger=outcome_ledger,
    )
    purchase_spine = _purchase_spine(
        business_case=business_case,
        commercial_offer_studio=commercial_offer_studio,
        board_pack=board_pack,
    )
    meeting_modes = _meeting_modes(
        board_pack=board_pack,
        outcome_ledger=outcome_ledger,
    )
    route_health = _route_health(
        buyer_concierge=buyer_concierge,
        scenario_hub=scenario_hub,
        enterprise_trust_center=enterprise_trust_center,
        commercial_offer_studio=commercial_offer_studio,
        board_pack=board_pack,
        outcome_ledger=outcome_ledger,
        evidence_bundle_artifacts=artifacts,
    )
    anti_confusion_cards = _anti_confusion_cards(buyer_concierge)
    proof_packet = _proof_packet()
    buyer_room_bridge = _buyer_room_bridge(
        buyer_brief=buyer_brief,
        next_best_action=next_best_action,
        purchase_spine=purchase_spine,
        role_switchboard=role_switchboard,
    )
    proof_routes = sorted(
        {item["route"] for item in path_phases}
        | {item["first_click"] for item in role_switchboard}
        | {item["second_click"] for item in role_switchboard}
        | {step["route"] for mode in meeting_modes for step in mode["steps"]}
        | {item["route"] for item in route_health}
        | {item["route"] for item in proof_packet}
        | {item["route"] for item in anti_confusion_cards}
        | {item["route"] for item in buyer_journey["steps"]}
        | {item for item in purchase_spine["proof_routes"]}
        | {item for item in buyer_room_bridge["routes"]}
        | {"/approvals", "/audit"}
    )
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
                "Launch Room is ready: the buyer can start from one cockpit and follow proof, trust, approval and outcome phases."
                if status == "ready"
                else "Launch Room is usable, but trust or rollout caveats should stay visible before pushing approval."
            ),
        },
        "summary": {
            "phases": len(path_phases),
            "ready_phases": len(
                [item for item in path_phases if item["status"] == "ready"]
            ),
            "risk_phases": len(
                [item for item in path_phases if item["status"] == "risk"]
            ),
            "role_paths": len(role_switchboard),
            "meeting_modes": len(meeting_modes),
            "route_health_items": len(route_health),
            "proof_items": len(proof_packet),
            "proof_routes": len(proof_routes),
            "journey_steps": len(buyer_journey["steps"]),
            "journey_ready": buyer_journey["ready_steps"],
            "checkout_gates": buyer_journey["checkout_gates"],
            "activation_gates": buyer_journey["activation_gates"],
            "governance_gates": buyer_journey["governance_gates"],
            "acceptance_items": buyer_journey["acceptance_items"],
            "acceptance_watch": buyer_journey["acceptance_watch"],
            "acceptance_blocked": buyer_journey["acceptance_blocked"],
            "claim_ready": buyer_journey["claim_ready"],
            "purchase_spine_status": purchase_spine["status"],
            "procurement_handoff_steps": len(
                (purchase_spine.get("procurement_handoff") or {}).get("open_order")
                or []
            ),
            "buyer_room_roles": len(buyer_room_bridge["role_cards"]),
            "buyer_room_proofs": len(buyer_room_bridge["proof_readiness"]),
            "buyer_room_steps": len(buyer_room_bridge["meeting_flow"]),
            "buyer_room_open_first": len(buyer_room_bridge["open_first_path"]),
        },
        "launch_summary": _launch_summary(
            buyer_concierge=buyer_concierge,
            board_pack=board_pack,
            outcome_ledger=outcome_ledger,
            business_case=business_case,
            enterprise_trust_center=enterprise_trust_center,
        ),
        "next_best_action": next_best_action,
        "purchase_spine": purchase_spine,
        "buyer_room_bridge": buyer_room_bridge,
        "path_phases": path_phases,
        "buyer_journey": buyer_journey,
        "role_switchboard": role_switchboard,
        "meeting_modes": meeting_modes,
        "route_health": route_health,
        "anti_confusion_cards": anti_confusion_cards,
        "proof_packet": proof_packet,
        "exports": proof_packet,
        "proof_routes": proof_routes,
        "source_signals": {
            "executive_status": _status(executive),
            "buyer_concierge_status": _status(buyer_concierge),
            "scenario_hub_status": _status(scenario_hub),
            "demo_command_center_status": _status(demo_command_center),
            "trust_center_status": _status(enterprise_trust_center),
            "commercial_offer_status": _status(commercial_offer_studio),
            "board_pack_status": _status(board_pack),
            "outcome_ledger_status": _status(outcome_ledger),
            "buyer_journey_ready": buyer_journey["ready_steps"],
            "purchase_spine_status": purchase_spine["status"],
            "purchase_spine_route": purchase_spine["route"],
            "evidence_artifacts": len(artifacts),
            "buyer_room_source": buyer_room_bridge["source"],
        },
        "caveats": [
            "Launch Room is a navigation and meeting cockpit; deep module reports remain the source of details.",
            "If Trust Center or Outcome Ledger is risky, keep the next action as proof or hardening, not full rollout.",
            "Evidence Bundle should be refreshed before forwarding final buyer artifacts.",
        ],
        "download_name": "rentgen-launch-room.md",
    }
    report["markdown"] = _markdown(report)
    return report
