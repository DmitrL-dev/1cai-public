"""Fast first-screen buyer pulse built from executive signals only."""

from __future__ import annotations

from typing import Any

BUYER_ROOM_PACKET_ZIP = "rentgen-buyer-room-packet.zip"
BUYER_ROOM_PACKET_ENDPOINT = "/api/v1/management/buyer-room-packet"
BUYER_ROOM_PACKET_HASH_HEADER = "X-Buyer-Room-Packet-Sha256"
ARCHIVE_VERIFICATION_PACKET_ZIP = "archive-verification-packet.zip"
ARCHIVE_VERIFICATION_PACKET_ENDPOINT = (
    "/api/v1/evidence-bundle/archive/verification-packet"
)
ARCHIVE_VERIFICATION_PACKET_HASH_HEADER = "X-Verification-Packet-Sha256"
EVIDENCE_ARCHIVE_HASH_HEADER = "X-Archive-Sha256"
KILLER_DEMO_ARCHIVE_HASH_HEADER = "X-Killer-Demo-Archive-Sha256"
KILLER_DEMO_MANIFEST_HASH_HEADER = "X-Killer-Demo-Manifest-Sha256"


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _money(value: Any, currency: str = "RUB") -> str:
    return f"{_int(value):,}".replace(",", " ") + f" {currency}"


def _pulse_status(status: str, score: int) -> str:
    if status in {"blocked", "critical", "fail"}:
        return "risk"
    if score >= 78:
        return "ready"
    return "watch"


def _purchase_path(*, purchase_status: str) -> dict[str, Any]:
    steps = [
        {
            "step": 1,
            "label": "Start",
            "route": "/launch-room",
            "artifact": "buyer-brief.md",
            "file": "buyer-brief.md",
            "line": "Open one cockpit before the buyer sees the full workbench.",
        },
        {
            "step": 2,
            "label": "Prove",
            "route": "/killer-demo",
            "artifact": "Killer Demo ZIP",
            "file": "OPEN_FIRST_KILLER_DEMO.md",
            "line": "Show one role/pain path and prepare the buyer-forwardable proof archive.",
        },
        {
            "step": 3,
            "label": "Close",
            "route": "/killer-demo",
            "artifact": "Meeting Close Receipt",
            "file": "MEETING_CLOSE_RECEIPT.md",
            "line": "Capture accepted roles, blockers, send files and the next paid step.",
        },
        {
            "step": 4,
            "label": "Activate",
            "route": "/pilot-launchpad",
            "artifact": "Post-Demo Activation Handoff",
            "file": "POST_DEMO_ACTIVATION_HANDOFF.md",
            "line": "Turn the receipt into paid start, invoice trigger and Day 7 proof.",
        },
        {
            "step": 5,
            "label": "Realize",
            "route": "/outcome-ledger",
            "artifact": "Outcome Ledger",
            "file": "rentgen-outcome-ledger.md",
            "line": "Track Day 30 acceptance, rollout value and next paid package.",
        },
    ]
    return {
        "status": purchase_status,
        "headline": "Launch -> Killer Demo -> Receipt -> Activation -> Outcome.",
        "buyer_line": "The first screen now points to the same artifacts the buyer receives after the demo.",
        "primary_route": "/killer-demo",
        "procurement_handoff": _procurement_handoff(purchase_status=purchase_status),
        "buyer_room_packet_artifact": {
            "title": "Buyer Room Packet ZIP",
            "route": "/",
            "endpoint": BUYER_ROOM_PACKET_ENDPOINT,
            "file": BUYER_ROOM_PACKET_ZIP,
            "hash_header": BUYER_ROOM_PACKET_HASH_HEADER,
            "line": "Open-first ZIP with Buyer Brief, Buyer Pulse, Buyer Room Plan, Purchase Path and Procurement Handoff.",
        },
        "verification_packet_artifact": {
            "title": "Verification Packet ZIP",
            "route": "/evidence-bundle",
            "endpoint": ARCHIVE_VERIFICATION_PACKET_ENDPOINT,
            "file": ARCHIVE_VERIFICATION_PACKET_ZIP,
            "hash_header": ARCHIVE_VERIFICATION_PACKET_HASH_HEADER,
            "line": "One procurement ZIP verifies Evidence and Killer Demo archives with receipts and hash table.",
        },
        "steps": steps,
        "send_files": [
            BUYER_ROOM_PACKET_ZIP,
            "buyer-brief.md",
            "buyer-pulse.md",
            "OPEN_FIRST_KILLER_DEMO.md",
            "MEETING_CLOSE_RECEIPT.md",
            "POST_DEMO_ACTIVATION_HANDOFF.md",
            "archive-acceptance-receipt.md",
            "archive-acceptance-receipt.json",
            ARCHIVE_VERIFICATION_PACKET_ZIP,
            "killer-demo-manifest.json",
        ],
    }


def _procurement_handoff(*, purchase_status: str) -> dict[str, Any]:
    open_order = [
        {
            "step": 1,
            "label": "Buyer Room Packet ZIP",
            "route": "/",
            "endpoint": BUYER_ROOM_PACKET_ENDPOINT,
            "file": BUYER_ROOM_PACKET_ZIP,
            "hash_header": BUYER_ROOM_PACKET_HASH_HEADER,
            "check": "Open the room packet first and record its packet hash before routing specialists.",
        },
        {
            "step": 2,
            "label": "Evidence Bundle ZIP",
            "route": "/evidence-bundle",
            "file": "Evidence Bundle ZIP",
            "hash_header": EVIDENCE_ARCHIVE_HASH_HEADER,
            "check": "Download the Evidence Bundle ZIP and record its archive hash.",
        },
        {
            "step": 3,
            "label": "Killer Demo ZIP",
            "route": "/killer-demo",
            "file": "Killer Demo ZIP",
            "hash_header": KILLER_DEMO_ARCHIVE_HASH_HEADER,
            "check": "Download the close-room ZIP and record the demo archive hash.",
        },
        {
            "step": 4,
            "label": "Verification Packet ZIP",
            "route": "/evidence-bundle",
            "endpoint": ARCHIVE_VERIFICATION_PACKET_ENDPOINT,
            "file": ARCHIVE_VERIFICATION_PACKET_ZIP,
            "hash_header": ARCHIVE_VERIFICATION_PACKET_HASH_HEADER,
            "check": "Attach the pair-level verification packet before accepting the two archives.",
        },
        {
            "step": 5,
            "label": "Close Receipt",
            "route": "/killer-demo",
            "file": "MEETING_CLOSE_RECEIPT.md",
            "hash_header": "",
            "check": "Record accepted roles, blockers, send files and the next paid step.",
        },
        {
            "step": 6,
            "label": "Activation Handoff",
            "route": "/pilot-launchpad",
            "file": "POST_DEMO_ACTIVATION_HANDOFF.md",
            "hash_header": "",
            "check": "Use the signed close receipt to start Day 0/7 pilot activation.",
        },
    ]
    return {
        "status": purchase_status,
        "title": "Procurement-ready handoff",
        "owner_line": (
            "Security/procurement should open the Buyer Room Packet, then two full archives, "
            "then the small verification packet, close receipt and activation handoff."
        ),
        "acceptance": (
            "Ticket is acceptable only when Buyer Room Packet hash, Evidence hash, Killer Demo hash, "
            "Verification Packet hash, close receipt and activation handoff are recorded together."
        ),
        "open_order": open_order,
        "attachments": [
            {
                "title": "Buyer Room Packet",
                "route": "/",
                "endpoint": BUYER_ROOM_PACKET_ENDPOINT,
                "file": BUYER_ROOM_PACKET_ZIP,
                "hash_header": BUYER_ROOM_PACKET_HASH_HEADER,
                "why": "Open-first room packet for director, architect, developer and procurement.",
            },
            {
                "title": "Archive acceptance receipt",
                "route": "/evidence-bundle",
                "file": "archive-acceptance-receipt.md",
                "why": "Human-readable procurement receipt for both archive hashes.",
            },
            {
                "title": "Archive acceptance JSON",
                "route": "/evidence-bundle",
                "file": "archive-acceptance-receipt.json",
                "why": "Machine-readable receipt for ticket systems.",
            },
            {
                "title": "Killer Demo manifest",
                "route": "/killer-demo",
                "file": "killer-demo-manifest.json",
                "hash_header": KILLER_DEMO_MANIFEST_HASH_HEADER,
                "why": "Verifies close-room overlay files inside the Killer Demo ZIP.",
            },
            {
                "title": "Verification Packet ZIP",
                "route": "/evidence-bundle",
                "endpoint": ARCHIVE_VERIFICATION_PACKET_ENDPOINT,
                "file": ARCHIVE_VERIFICATION_PACKET_ZIP,
                "hash_header": ARCHIVE_VERIFICATION_PACKET_HASH_HEADER,
                "why": "Proves Evidence and Killer Demo archives as one checked pair.",
            },
        ],
        "routes": [
            "/evidence-bundle",
            "/killer-demo",
            "/pilot-launchpad",
            "/outcome-ledger",
        ],
    }


# Floor used to anchor a local-license conversation in the fast pulse. The deep
# builder (business_case._local_license_anchor) computes the real figure as
# max(1_800_000, min(12_000_000, round(first_year_visible_value * 0.22))); the
# fast path has no money map, so this is the FLOOR of that band, never a computed
# result. It is surfaced as an explicit assumption, not as analysis output.
LOCAL_LICENSE_ANCHOR_FLOOR = 1_800_000


def _purchase_path_proof_routes(purchase_path: dict[str, Any]) -> list[str]:
    """Collect the distinct routes the pulse actually emits in its purchase path.

    This counts a real structure the fast pulse builds (purchase-path steps,
    artifacts and the procurement handoff) instead of a hardcoded integer, so the
    number tracks the routes that are genuinely present in the response.
    """

    routes: set[str] = set()

    def _add(value: Any) -> None:
        if isinstance(value, str) and value.startswith("/"):
            routes.add(value)

    _add(purchase_path.get("primary_route"))
    for step in purchase_path.get("steps") or []:
        _add(step.get("route"))
    for key in ("buyer_room_packet_artifact", "verification_packet_artifact"):
        _add((purchase_path.get(key) or {}).get("route"))

    handoff = purchase_path.get("procurement_handoff") or {}
    for step in handoff.get("open_order") or []:
        _add(step.get("route"))
    for item in handoff.get("attachments") or []:
        _add(item.get("route"))
    for route in handoff.get("routes") or []:
        _add(route)

    return sorted(routes)


def build_buyer_pulse(
    *,
    executive: dict[str, Any],
    monthly_ai_subscription_cost: int = 120_000,
    currency: str = "RUB",
) -> dict[str, Any]:
    """Return a fast buyer pulse without building deep deal artifacts."""

    decision = executive.get("decision") or {}
    kpis = executive.get("kpis") or {}
    risk_summary = executive.get("risk_summary") or {}
    status = str(decision.get("status") or "watch")
    score = _int(decision.get("score"))
    purchase_status = _pulse_status(status, score)
    annual_ai_rent = monthly_ai_subscription_cost * 12
    three_year_ai_rent = annual_ai_rent * 3
    purchase_path = _purchase_path(purchase_status=purchase_status)

    # Imported lazily: buyer_concierge -> open_first_path -> buyer_pulse is a module
    # import cycle, so a top-level import here would fail to initialize. By call
    # time every module is fully loaded.
    from src.services.rentgen.buyer_concierge import _persona_cards, _shortest_paths

    # Honest counts derived from the real structures they claim to count, so they
    # update automatically if those structures change.
    persona_card_count = len(
        _persona_cards(
            business_case={},
            enterprise_trust_center={},
            commercial_offer_studio={},
            scenario_hub={},
        )
    )
    shortest_path_count = len(_shortest_paths())
    journey_steps = purchase_path.get("steps") or []
    journey_step_count = len(journey_steps)
    journey_ready_count = journey_step_count if purchase_status == "ready" else 0
    proof_route_list = _purchase_path_proof_routes(purchase_path)
    proof_route_count = len(proof_route_list)

    return {
        "status": status,
        "score": score,
        "purchase_status": purchase_status,
        "source": "management-fast-pulse",
        "purchase_path": purchase_path,
        "launch": {
            "status": status,
            "score": score,
            "purchase_spine_status": purchase_status,
            # Counted from the real purchase-path steps this pulse emits (not the
            # deep Launch Room buyer_journey, which the fast path never builds).
            "journey_ready": journey_ready_count,
            "journey_steps": journey_step_count,
            # The deep builders count len(governance["gates"]); the fast pulse has
            # no governance gate list, so report it as not measured rather than a
            # fabricated integer.
            "governance_gates": None,
            "proof_routes": proof_route_count,
            "route": "/launch-room",
        },
        "concierge": {
            "status": status,
            "score": score,
            "purchase_router_status": purchase_status,
            "persona_cards": persona_card_count,
            "shortest_paths": shortest_path_count,
            "route": "/buyer-concierge",
        },
        "commercial": {
            "monthly_ai_rent": _money(monthly_ai_subscription_cost, currency),
            "annual_ai_rent": _money(annual_ai_rent, currency),
            "three_year_ai_rent": _money(three_year_ai_rent, currency),
            # Key kept stable for the 11 consumers, but it is the floor of the
            # local-license band, not a computed money-map figure. The
            # "_basis" sibling and the buyer_line make that explicit.
            "local_license_anchor": _money(LOCAL_LICENSE_ANCHOR_FLOOR, currency),
            "local_license_anchor_basis": "assumption-floor",
            "buyer_line": (
                f"Baseline AI rent is {_money(monthly_ai_subscription_cost, currency)}/month; "
                f"three-year AI rent is {_money(three_year_ai_rent, currency)}. "
                f"Local-license anchor floor is {_money(LOCAL_LICENSE_ANCHOR_FLOOR, currency)} "
                "(assumption floor; the computed anchor is materialized in Business Case / Offer Studio)."
            ),
            "route": "/commercial-offer-studio",
        },
        "evidence": {
            "proof_routes": proof_route_count,
            # Not measured in the fast pulse (see launch.governance_gates note).
            "governance_gates": None,
            "route": "/evidence-bundle",
        },
        "executive": {
            "red_areas": _int(kpis.get("red_areas")),
            "review_queue": _int(kpis.get("review_queue")),
            "high_hotspots": _int(risk_summary.get("high_hotspots")),
            "headline": str(decision.get("headline") or ""),
        },
        "assumptions": {
            "basis": "management-fast-pulse",
            "computed": [
                "persona_cards (len of buyer_concierge persona roster)",
                "shortest_paths (len of buyer_concierge shortest paths)",
                "journey_steps / journey_ready (from real purchase-path steps)",
                "proof_routes (distinct routes emitted in purchase_path)",
                "commercial AI-rent figures (from monthly_ai_subscription_cost)",
            ],
            "assumption_floors": [
                "commercial.local_license_anchor is the floor of the local-license band "
                "(local_license_anchor_basis=assumption-floor), not a computed money-map "
                "figure (deep value lives in Business Case / Offer Studio)",
            ],
            "not_measured": [
                "governance_gates (no governance gate list exists in the fast path; "
                "the deep Launch Room / Outcome Ledger reports count the real gates)",
            ],
        },
    }
