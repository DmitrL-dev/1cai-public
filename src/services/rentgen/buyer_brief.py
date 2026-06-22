"""Fast first-minute buyer brief for the Home screen."""

from __future__ import annotations

from typing import Any

from src.services.rentgen.buyer_pulse import (
    ARCHIVE_VERIFICATION_PACKET_ENDPOINT,
    ARCHIVE_VERIFICATION_PACKET_HASH_HEADER,
    ARCHIVE_VERIFICATION_PACKET_ZIP,
    BUYER_ROOM_PACKET_ENDPOINT,
    BUYER_ROOM_PACKET_HASH_HEADER,
    BUYER_ROOM_PACKET_ZIP,
    build_buyer_pulse,
)
from src.services.rentgen.coverage_ledger import build_coverage_ledger
from src.services.rentgen.open_first_path import build_open_first_path


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _status_for_count(count: int, *, ok_when_zero: bool = True) -> str:
    if ok_when_zero and count == 0:
        return "ready"
    if count >= 3:
        return "risk"
    return "watch"


def _primary_motion(*, pulse: dict[str, Any]) -> dict[str, Any]:
    status = str(pulse.get("status") or "watch")
    purchase_status = str(pulse.get("purchase_status") or "watch")
    executive = pulse.get("executive") or {}
    if status == "blocked":
        return {
            "label": "Connect configuration",
            "route": "/configurations",
            "status": "blocked",
            "ask": "Build the local Rentgen store before any buyer claim.",
            "reason": "The buyer story needs local graph and evidence before purchase proof is credible.",
        }
    if purchase_status == "risk":
        return {
            "label": "Sell proof sprint",
            "route": "/launch-room",
            "status": "risk",
            "ask": "Turn current risk into a paid proof or hardening sprint.",
            "reason": str(
                executive.get("headline")
                or "Current signals need owner-visible proof before rollout."
            ),
        }
    if purchase_status == "ready":
        return {
            "label": "Ask for local license",
            "route": "/board-pack",
            "status": "ready",
            "ask": "Move from demo proof to a local product purchase.",
            "reason": "Buyer pulse is ready; board, offer and evidence routes can support the close.",
        }
    return {
        "label": "Open buyer route",
        "route": "/launch-room",
        "status": "watch",
        "ask": "Show the buyer one route, one proof packet and one next paid step.",
        "reason": str(
            executive.get("headline")
            or "Use the Launch Room to keep watch items visible."
        ),
    }


def _role_cards(*, pulse: dict[str, Any]) -> list[dict[str, Any]]:
    executive = pulse.get("executive") or {}
    red_areas = _int(executive.get("red_areas"))
    review_queue = _int(executive.get("review_queue"))
    high_hotspots = _int(executive.get("high_hotspots"))
    purchase_status = str(pulse.get("purchase_status") or "watch")
    return [
        {
            "role": "developer",
            "title": "Developer",
            "route": "/change",
            "status": "risk" if high_hotspots else "ready",
            "spark": (
                f"{high_hotspots} high-risk hotspots need impact/tests before commit."
                if high_hotspots
                else "Show impact, risky query proof and test route before code review."
            ),
            "proof_file": "rentgen-developer-report.md",
        },
        {
            "role": "architect",
            "title": "Architect",
            "route": "/architecture" if red_areas else "/platform-doctor",
            "status": "risk" if red_areas else "ready",
            "spark": (
                f"{red_areas} red areas need topology, platform and update proof."
                if red_areas
                else "Show topology, platform caveats and update readiness without source-code wandering."
            ),
            "proof_file": "rentgen-architect-report.md",
        },
        {
            "role": "director",
            "title": "Director",
            "route": "/board-pack",
            "status": purchase_status,
            "spark": f"Compare local license with {((pulse.get('commercial') or {}).get('three_year_ai_rent') or 'AI rent')} and attach checkout gates.",
            "proof_file": "board-pack.md",
        },
        {
            "role": "security",
            "title": "Security",
            "route": "/enterprise-trust-center",
            "status": "watch" if purchase_status == "risk" else "ready",
            "spark": "Show security questionnaire, SBOM/offline posture, approvals, audit chain and SIEM handoff.",
            "proof_file": "rentgen-security-questionnaire.md",
        },
        {
            "role": "vendor",
            "title": "Vendor",
            "route": "/vendor-portfolio",
            "status": "watch" if review_queue else "ready",
            "spark": (
                f"{review_queue} review items can become scoped audit and release-gate work."
                if review_queue
                else "Turn one scan into a buyer-safe audit, work packages and evidence bundle."
            ),
            "proof_file": "vendor-portfolio.md",
        },
    ]


def _proof_readiness(*, pulse: dict[str, Any]) -> list[dict[str, Any]]:
    executive = pulse.get("executive") or {}
    purchase_status = str(pulse.get("purchase_status") or "watch")
    red_areas = _int(executive.get("red_areas"))
    return [
        {
            "id": "evidence-bundle",
            "title": "Forwardable evidence",
            "route": "/evidence-bundle",
            "status": purchase_status,
            "signal": f"{((pulse.get('evidence') or {}).get('proof_routes') or 0)} proof routes and hashed JSON/Markdown files.",
            "file": "OPEN_FIRST.md",
        },
        {
            "id": "governance",
            "title": "Approval gates",
            "route": "/approvals",
            "status": "ready",
            "signal": f"{((pulse.get('evidence') or {}).get('governance_gates') or 0)} governance gates for paid motion and write-like work.",
            "file": "governance-proof.md",
        },
        {
            "id": "audit-siem",
            "title": "Audit / SIEM handoff",
            "route": "/audit",
            "status": "ready",
            "signal": "Hash-chain verification and rentgen.audit.siem.v1 export are available.",
            "file": "rentgen-audit-siem.jsonl",
        },
        {
            "id": "trust",
            "title": "Enterprise trust",
            "route": "/enterprise-trust-center",
            "status": _status_for_count(red_areas),
            "signal": "Security questionnaire, locality, SBOM/offline and Rights/RLS proof have one route.",
            "file": "rentgen-security-questionnaire.md",
        },
    ]


def _meeting_flow(*, primary: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "step": 1,
            "label": "Orient",
            "route": "/buyer-concierge",
            "line": "Pick the role in the room and open the shortest proof path.",
        },
        {
            "step": 2,
            "label": "Prove",
            "route": "/killer-demo",
            "line": "Show one 1C pain, role sparks, proof packet and close question.",
        },
        {
            "step": 3,
            "label": "Ask",
            "route": str(primary.get("route") or "/launch-room"),
            "line": str(primary.get("ask") or "Name the next paid step."),
        },
        {
            "step": 4,
            "label": "Forward",
            "route": "/evidence-bundle",
            "line": "Send hashed files, role packets, governance proof and procurement handoff.",
        },
    ]


def _buyer_room_plan(
    *,
    pulse: dict[str, Any],
    primary: dict[str, Any],
    role_cards: list[dict[str, Any]],
    proof_readiness: list[dict[str, Any]],
    purchase_path: dict[str, Any],
) -> dict[str, Any]:
    executive = pulse.get("executive") or {}
    status = str(pulse.get("status") or "watch")
    purchase_status = str(pulse.get("purchase_status") or "watch")
    red_areas = _int(executive.get("red_areas"))
    high_hotspots = _int(executive.get("high_hotspots"))
    review_queue = _int(executive.get("review_queue"))

    role_by_id = {str(item.get("role")): item for item in role_cards}
    proof_by_id = {str(item.get("id")): item for item in proof_readiness}

    if status == "blocked":
        selected = {
            "mode": "connect-evidence",
            "role": "operator",
            "title": "Connect configuration first",
            "route": "/configurations",
            "status": "blocked",
            "start_with": "Run the intake plan before showing buyer claims.",
            "show": "Source path, detected EDT/Git/XML coverage, missing platform evidence.",
            "proof_file": "intake-plan.json",
            "close_question": "Can we run a local intake on your configuration now?",
            "why": "Buyer trust starts with local evidence, not a generic demo.",
        }
    elif high_hotspots:
        developer = role_by_id.get("developer", {})
        selected = {
            "mode": "developer-spark",
            "role": "developer",
            "title": "Show the developer a real risky change path",
            "route": str(developer.get("route") or "/change"),
            "status": str(developer.get("status") or "risk"),
            "start_with": "Open impact, risky query proof and test route.",
            "show": str(
                developer.get("spark")
                or "Hotspots, affected tests and safe fix evidence."
            ),
            "proof_file": str(
                developer.get("proof_file") or "rentgen-developer-report.md"
            ),
            "close_question": "Would this remove one risky manual review from your release?",
            "why": f"{high_hotspots} high-risk hotspots are visible now.",
        }
    elif red_areas:
        architect = role_by_id.get("architect", {})
        selected = {
            "mode": "architect-trust",
            "role": "architect",
            "title": "Show architecture and platform blockers",
            "route": str(architect.get("route") or "/platform-doctor"),
            "status": str(architect.get("status") or "risk"),
            "start_with": "Open topology, platform caveats and update readiness.",
            "show": str(
                architect.get("spark")
                or "Architecture boundaries, platform and update proof."
            ),
            "proof_file": str(
                architect.get("proof_file") or "rentgen-architect-report.md"
            ),
            "close_question": "Which blocker should become paid hardening scope first?",
            "why": f"{red_areas} red architecture/platform areas need proof before rollout.",
        }
    elif purchase_status == "ready":
        director = role_by_id.get("director", {})
        selected = {
            "mode": "director-close",
            "role": "director",
            "title": "Move from proof to local license ask",
            "route": str(director.get("route") or "/board-pack"),
            "status": str(director.get("status") or "ready"),
            "start_with": "Open board pack and local-license commercial line.",
            "show": str(
                director.get("spark") or "Value, governance and purchase files."
            ),
            "proof_file": str(director.get("proof_file") or "board-pack.md"),
            "close_question": "Can we approve the local proof sprint or license package today?",
            "why": "Buyer pulse is ready and purchase artifacts are available.",
        }
    elif review_queue:
        vendor = role_by_id.get("vendor", {})
        selected = {
            "mode": "vendor-scope",
            "role": "vendor",
            "title": "Turn review queue into scoped vendor work",
            "route": str(vendor.get("route") or "/vendor-portfolio"),
            "status": str(vendor.get("status") or "watch"),
            "start_with": "Open vendor portfolio and package the review queue.",
            "show": str(
                vendor.get("spark") or "Audit scope, work packages and evidence bundle."
            ),
            "proof_file": str(vendor.get("proof_file") or "vendor-portfolio.md"),
            "close_question": "Which review item should become the first paid work package?",
            "why": f"{review_queue} review items can be converted into scoped work.",
        }
    else:
        selected = {
            "mode": "guided-proof",
            "role": "all",
            "title": "Start with the guided proof route",
            "route": str(primary.get("route") or "/launch-room"),
            "status": str(primary.get("status") or purchase_status),
            "start_with": "Open one buyer cockpit before deep workbench navigation.",
            "show": str(
                primary.get("reason") or "Role cards, proof packet and next paid step."
            ),
            "proof_file": "buyer-brief.md",
            "close_question": str(primary.get("ask") or "What is the next paid step?"),
            "why": "No single risk dominates; keep the room on one proof route.",
        }

    send_files = [
        "buyer-brief.md",
        str(selected["proof_file"]),
        str((proof_by_id.get("evidence-bundle") or {}).get("file") or "OPEN_FIRST.md"),
        "MEETING_CLOSE_RECEIPT.md",
    ]
    for filename in list(purchase_path.get("send_files") or []):
        if filename in {
            BUYER_ROOM_PACKET_ZIP,
            "archive-acceptance-receipt.md",
            ARCHIVE_VERIFICATION_PACKET_ZIP,
            "killer-demo-manifest.json",
        }:
            send_files.append(str(filename))

    sequence = [
        {
            "step": 1,
            "label": "Start",
            "route": selected["route"],
            "line": selected["start_with"],
        },
        {
            "step": 2,
            "label": "Prove",
            "route": "/killer-demo",
            "line": selected["show"],
        },
        {
            "step": 3,
            "label": "Forward",
            "route": "/evidence-bundle",
            "line": "Send files and capture receipt.",
        },
    ]

    return {
        **selected,
        "sequence": sequence,
        "send_files": list(dict.fromkeys(send_files)),
        "evidence_contract": "buyer_room_plan_v1",
    }


def _purchase_path(*, pulse: dict[str, Any], primary: dict[str, Any]) -> dict[str, Any]:
    path = dict(pulse.get("purchase_path") or {})
    steps = list(path.get("steps") or [])
    if not steps:
        steps = [
            {
                "step": 1,
                "label": "Start",
                "route": "/launch-room",
                "artifact": "buyer-brief.md",
                "file": "buyer-brief.md",
                "line": "Start from one cockpit.",
            },
            {
                "step": 2,
                "label": "Prove",
                "route": "/killer-demo",
                "artifact": "Killer Demo ZIP",
                "file": "OPEN_FIRST_KILLER_DEMO.md",
                "line": "Show one proof route.",
            },
            {
                "step": 3,
                "label": "Close",
                "route": "/killer-demo",
                "artifact": "Meeting Close Receipt",
                "file": "MEETING_CLOSE_RECEIPT.md",
                "line": "Capture accepted roles and next paid step.",
            },
            {
                "step": 4,
                "label": "Activate",
                "route": "/pilot-launchpad",
                "artifact": "Post-Demo Activation Handoff",
                "file": "POST_DEMO_ACTIVATION_HANDOFF.md",
                "line": "Start paid proof with Day 7 acceptance.",
            },
            {
                "step": 5,
                "label": "Realize",
                "route": "/outcome-ledger",
                "artifact": "Outcome Ledger",
                "file": "rentgen-outcome-ledger.md",
                "line": "Refresh Day 30 outcome evidence.",
            },
        ]
    close_step = next(
        (item for item in steps if str(item.get("label") or "").casefold() == "close"),
        {},
    )
    activation_step = next(
        (
            item
            for item in steps
            if str(item.get("label") or "").casefold() == "activate"
        ),
        {},
    )
    send_files = list(
        dict.fromkeys(str(item) for item in list(path.get("send_files") or []) if item)
    )
    for filename in [
        BUYER_ROOM_PACKET_ZIP,
        "archive-acceptance-receipt.md",
        "archive-acceptance-receipt.json",
        ARCHIVE_VERIFICATION_PACKET_ZIP,
    ]:
        if filename not in send_files:
            send_files.append(filename)
    verification_artifact = dict(path.get("verification_packet_artifact") or {})
    procurement_handoff = dict(path.get("procurement_handoff") or {})
    if not procurement_handoff:
        procurement_handoff = {
            "status": str(
                path.get("status") or pulse.get("purchase_status") or "watch"
            ),
            "title": "Procurement-ready handoff",
            "owner_line": "Open the Buyer Room Packet, Evidence Bundle, Killer Demo archive and verification packet before forwarding files.",
            "acceptance": "Ticket is accepted when buyer-room, archive and verification packet hashes are recorded.",
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
                    "hash_header": "X-Archive-Sha256",
                    "check": "Record the Evidence archive hash.",
                },
                {
                    "step": 3,
                    "label": "Killer Demo ZIP",
                    "route": "/killer-demo",
                    "file": "Killer Demo ZIP",
                    "hash_header": "X-Killer-Demo-Archive-Sha256",
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
            ],
            "attachments": [],
            "routes": ["/evidence-bundle", "/killer-demo", "/pilot-launchpad"],
        }
    return {
        "status": str(path.get("status") or pulse.get("purchase_status") or "watch"),
        "headline": str(
            path.get("headline")
            or "Launch -> Killer Demo -> Receipt -> Activation -> Outcome."
        ),
        "buyer_line": str(
            path.get("buyer_line")
            or f"{primary.get('label', 'Buyer path')}: proof must turn into a receipt and activation handoff."
        ),
        "primary_route": str(path.get("primary_route") or "/killer-demo"),
        "procurement_handoff": procurement_handoff,
        "buyer_room_packet_artifact": {
            "title": str(
                (path.get("buyer_room_packet_artifact") or {}).get("title")
                or "Buyer Room Packet ZIP"
            ),
            "route": str(
                (path.get("buyer_room_packet_artifact") or {}).get("route") or "/"
            ),
            "endpoint": str(
                (path.get("buyer_room_packet_artifact") or {}).get("endpoint")
                or BUYER_ROOM_PACKET_ENDPOINT
            ),
            "file": str(
                (path.get("buyer_room_packet_artifact") or {}).get("file")
                or BUYER_ROOM_PACKET_ZIP
            ),
            "hash_header": str(
                (path.get("buyer_room_packet_artifact") or {}).get("hash_header")
                or BUYER_ROOM_PACKET_HASH_HEADER
            ),
            "line": str(
                (path.get("buyer_room_packet_artifact") or {}).get("line")
                or "Open-first ZIP with Buyer Brief, Buyer Pulse, Buyer Room Plan, Purchase Path and Procurement Handoff."
            ),
        },
        "close_artifact": {
            "title": str(close_step.get("artifact") or "Meeting Close Receipt"),
            "route": str(close_step.get("route") or "/killer-demo"),
            "file": str(close_step.get("file") or "MEETING_CLOSE_RECEIPT.md"),
            "line": str(
                close_step.get("line")
                or "Capture accepted roles, blockers and next paid step."
            ),
        },
        "activation_artifact": {
            "title": str(
                activation_step.get("artifact") or "Post-Demo Activation Handoff"
            ),
            "route": str(activation_step.get("route") or "/pilot-launchpad"),
            "file": str(
                activation_step.get("file") or "POST_DEMO_ACTIVATION_HANDOFF.md"
            ),
            "line": str(
                activation_step.get("line")
                or "Turn close into paid start and Day 7 proof."
            ),
        },
        "archive_receipt_artifact": {
            "title": "Archive Acceptance Receipt",
            "route": "/evidence-bundle",
            "file": "archive-acceptance-receipt.md",
            "line": "Record Evidence Bundle ZIP and linked Killer Demo ZIP hashes in procurement.",
        },
        "verification_packet_artifact": {
            "title": str(
                verification_artifact.get("title") or "Verification Packet ZIP"
            ),
            "route": str(verification_artifact.get("route") or "/evidence-bundle"),
            "endpoint": str(
                verification_artifact.get("endpoint")
                or ARCHIVE_VERIFICATION_PACKET_ENDPOINT
            ),
            "file": str(
                verification_artifact.get("file") or ARCHIVE_VERIFICATION_PACKET_ZIP
            ),
            "hash_header": str(
                verification_artifact.get("hash_header")
                or ARCHIVE_VERIFICATION_PACKET_HASH_HEADER
            ),
            "line": str(
                verification_artifact.get("line")
                or "One procurement ZIP verifies Evidence and Killer Demo archives with receipts and hash table."
            ),
        },
        "steps": steps,
        "send_files": send_files,
    }


def build_buyer_brief(
    *,
    executive: dict[str, Any],
    monthly_ai_subscription_cost: int = 120_000,
    currency: str = "RUB",
) -> dict[str, Any]:
    """Build a fast first-minute buyer brief without deep report generation."""

    pulse = build_buyer_pulse(
        executive=executive,
        monthly_ai_subscription_cost=monthly_ai_subscription_cost,
        currency=currency,
    )
    coverage_ledger = build_coverage_ledger(executive=executive)
    primary = _primary_motion(pulse=pulse)
    role_cards = _role_cards(pulse=pulse)
    proof_readiness = _proof_readiness(pulse=pulse)
    purchase_path = _purchase_path(pulse=pulse, primary=primary)
    buyer_room_plan = _buyer_room_plan(
        pulse=pulse,
        primary=primary,
        role_cards=role_cards,
        proof_readiness=proof_readiness,
        purchase_path=purchase_path,
    )
    open_first_path = build_open_first_path(
        buyer_room_plan=buyer_room_plan,
        proof_readiness=proof_readiness,
        purchase_path=purchase_path,
        source="buyer-brief",
        verify_line="Verify Evidence and Killer Demo archives with one procurement control ZIP.",
    )
    return {
        "status": pulse["status"],
        "score": pulse["score"],
        "purchase_status": pulse["purchase_status"],
        "source": "management-buyer-brief",
        "pulse": pulse,
        "primary_motion": primary,
        "room_line": (
            f"{primary['label']}: {primary['ask']} "
            f"AI baseline: {(pulse.get('commercial') or {}).get('three_year_ai_rent')} over three years."
        ),
        "commercial": pulse["commercial"],
        "coverage_ledger": coverage_ledger,
        "buyer_room_plan": buyer_room_plan,
        "purchase_path": purchase_path,
        "open_first_path": open_first_path,
        "role_cards": role_cards,
        "proof_readiness": proof_readiness,
        "meeting_flow": _meeting_flow(primary=primary),
        "routes": sorted(
            {
                str(primary.get("route") or "/launch-room"),
                "/buyer-concierge",
                "/killer-demo",
                "/pilot-launchpad",
                "/outcome-ledger",
                "/evidence-bundle",
                str(buyer_room_plan.get("route") or ""),
                *[str(item["route"]) for item in role_cards],
                *[str(item["route"]) for item in proof_readiness],
                *[str(item.get("route") or "") for item in open_first_path],
                *[str(item.get("route") or "") for item in purchase_path["steps"]],
                *[
                    str(item.get("route") or "")
                    for item in (
                        purchase_path["procurement_handoff"].get("open_order") or []
                    )
                ],
            }
        ),
        "summary": {
            "roles": len(role_cards),
            "proof_items": len(proof_readiness),
            "meeting_steps": 4,
            "open_first_steps": len(open_first_path),
            "purchase_path_steps": len(purchase_path["steps"]),
            "purchase_path_files": len(purchase_path["send_files"]),
            "procurement_handoff_steps": len(
                purchase_path["procurement_handoff"].get("open_order") or []
            ),
            "room_plan_files": len(buyer_room_plan["send_files"]),
            "red_areas": _int((pulse.get("executive") or {}).get("red_areas")),
            "review_queue": _int((pulse.get("executive") or {}).get("review_queue")),
            "high_hotspots": _int((pulse.get("executive") or {}).get("high_hotspots")),
            "coverage_caveats": coverage_ledger["summary"]["caveats"],
        },
    }
