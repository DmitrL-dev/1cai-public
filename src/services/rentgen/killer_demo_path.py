"""Killer demo path that turns Rentgen surfaces into one buyer-ready presentation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from src.services.rentgen.open_first_path import build_open_first_path, open_first_path_markdown_lines


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


def _is_risky(report: dict[str, Any] | None) -> bool:
    return _status(report) in {"blocked", "critical", "fail", "risk"}


def _summary(report: dict[str, Any]) -> dict[str, Any]:
    return report.get("summary") or {}


def _weighted_score(reports: list[tuple[dict[str, Any], float]]) -> int:
    total = sum(_score(report) * weight for report, weight in reports)
    return max(0, min(100, round(total)))


def _decision_status(*reports: dict[str, Any], score: int) -> str:
    if any(_is_risky(report) for report in reports):
        return "risk"
    if score >= 84:
        return "ready"
    return "watch"


def _primary_route(
    *,
    launch_room: dict[str, Any],
    enterprise_trust_center: dict[str, Any],
    test_factory: dict[str, Any],
    board_pack: dict[str, Any],
    outcome_ledger: dict[str, Any],
) -> dict[str, str]:
    if _is_risky(enterprise_trust_center):
        return {
            "label": "Security-first killer path",
            "route": "/enterprise-trust-center",
            "reason": "Trust is the visible blocker; win the room by naming controls, caveats and hardening scope first.",
        }
    if _is_risky(test_factory):
        return {
            "label": "Developer spark path",
            "route": "/testing",
            "reason": "Test gaps are visible; convert the technical audience with run-now tests and generated skeletons.",
        }
    next_action = launch_room.get("next_best_action") or {}
    if _status(board_pack) == "ready":
        return {
            "label": "Board approval path",
            "route": str(next_action.get("route") or "/board-pack"),
            "reason": "Approval, price anchor and proof packet are strong enough for a decision-room route.",
        }
    if _score(outcome_ledger) >= 70:
        return {
            "label": "Outcome proof path",
            "route": "/outcome-ledger",
            "reason": "Show what changes after purchase: 7/30/90-day outcomes, risk burndown and expansion proof.",
        }
    return {
        "label": str(next_action.get("label") or "Launch Room path"),
        "route": str(next_action.get("route") or "/launch-room"),
        "reason": str(next_action.get("reason") or "Start from one cockpit and follow the next best action."),
    }


def _killer_stages(
    *,
    launch_room: dict[str, Any],
    demo_command_center: dict[str, Any],
    test_factory: dict[str, Any],
    enterprise_trust_center: dict[str, Any],
    board_pack: dict[str, Any],
    outcome_ledger: dict[str, Any],
) -> list[dict[str, Any]]:
    launch_summary = launch_room.get("launch_summary") or {}
    board_snapshot = board_pack.get("board_snapshot") or {}
    value_anchor = launch_summary.get("value_anchor") or board_snapshot.get("value_anchor") or ""
    first_stage = (demo_command_center.get("live_stages") or [{}])[0]
    return [
        {
            "id": "single-door",
            "title": "Single-door orientation",
            "minutes": 0.75,
            "route": "/launch-room",
            "audience": "all",
            "spark": "The product opens as one guided cockpit, not a menu of reports.",
            "proof": str(first_stage.get("proof") or launch_summary.get("current_truth") or ""),
            "close_question": "Which role or pain should we prove first?",
        },
        {
            "id": "developer-proof",
            "title": "Developer spark",
            "minutes": 1.25,
            "route": "/testing",
            "audience": "developer / QA",
            "spark": "A changed module becomes run-now tests, generated YAxUnit/Vanessa skeletons and manual checks.",
            "proof": f"{_summary(test_factory).get('run_now', 0)} run-now tests, {_summary(test_factory).get('generation_tasks', 0)} generation tasks.",
            "close_question": "Would this have shortened your last review or release regression discussion?",
        },
        {
            "id": "trust-proof",
            "title": "Enterprise trust",
            "minutes": 1.25,
            "route": "/enterprise-trust-center",
            "audience": "CIO / security / architect",
            "spark": "Security sees local contour, SBOM/offline, rights and platform caveats before procurement asks.",
            "proof": f"Trust status {_status(enterprise_trust_center)} / {_score(enterprise_trust_center)}.",
            "close_question": "Which approval artifact is required before a pilot install?",
        },
        {
            "id": "board-proof",
            "title": "Board decision",
            "minutes": 1.25,
            "route": "/board-pack",
            "audience": "director / sponsor",
            "spark": "Technical proof turns into a buying motion, committee answers and risk-to-decision map.",
            "proof": f"Value anchor {value_anchor}; decision items {_summary(board_pack).get('decision_items', 0)}.",
            "close_question": "Is the next paid step proof, hardening or local pilot?",
        },
        {
            "id": "outcome-proof",
            "title": "After-purchase proof",
            "minutes": 1.0,
            "route": "/outcome-ledger",
            "audience": "sponsor / delivery lead",
            "spark": "The buyer sees adoption windows, success metrics and risk burndown before signing.",
            "proof": f"{_summary(outcome_ledger).get('success_metrics', 0)} success metrics and {_summary(outcome_ledger).get('expansion_paths', 0)} expansion paths.",
            "close_question": "Can we book Day 7 proof and Day 30 acceptance now?",
        },
        {
            "id": "evidence-close",
            "title": "Artifact close",
            "minutes": 0.75,
            "route": "/evidence-bundle",
            "audience": "all",
            "spark": "The meeting leaves behind hashed JSON/Markdown artifacts, not screenshots.",
            "proof": "Evidence Bundle carries Launch Room, Test Factory, Board Pack, Trust Center and Outcome Ledger.",
            "close_question": "Who receives the proof packet today?",
        },
    ]


def _demo_modes(stages: list[dict[str, Any]], board_pack: dict[str, Any]) -> list[dict[str, Any]]:
    board_script = board_pack.get("board_room_script") or []
    return [
        {
            "id": "three-minute",
            "title": "3-minute spark",
            "minutes": 3,
            "steps": [
                {"route": "/launch-room", "label": "single door"},
                {"route": "/testing", "label": "developer spark"},
                {"route": "/board-pack", "label": "buying motion"},
            ],
            "close": "Ask whether the buyer wants proof, hardening or pilot as the next paid step.",
        },
        {
            "id": "five-minute",
            "title": "5-minute killer path",
            "minutes": 5,
            "steps": [{"route": item["route"], "label": item["title"]} for item in stages[:5]],
            "close": "Open Evidence Bundle and assign recipient.",
        },
        {
            "id": "eight-minute-board",
            "title": "8-minute board route",
            "minutes": 8,
            "steps": [
                {"route": str(item.get("route") or "/board-pack"), "label": str(item.get("speaker") or item.get("minute") or "board")}
                for item in board_script[:5]
            ] or [{"route": item["route"], "label": item["title"]} for item in stages],
            "close": "Approve the pilot/hardening motion and proof packet.",
        },
        {
            "id": "security-first",
            "title": "Security-first route",
            "minutes": 6,
            "steps": [
                {"route": "/enterprise-trust-center", "label": "trust"},
                {"route": "/productization", "label": "SBOM/offline"},
                {"route": "/rights-rls", "label": "rights"},
                {"route": "/evidence-bundle", "label": "manifest"},
            ],
            "close": "Turn blockers into accepted pilot risk or hardening scope.",
        },
    ]


def _role_sparks(
    *,
    buyer_concierge: dict[str, Any],
    test_factory: dict[str, Any],
    board_pack: dict[str, Any],
    outcome_ledger: dict[str, Any],
) -> list[dict[str, str]]:
    roles: list[dict[str, str]] = []
    outcome_by_role = {
        str(item.get("role")): item
        for item in outcome_ledger.get("role_scorecards", [])
        if item.get("role")
    }
    board_by_role = {
        str(item.get("role")): item
        for item in board_pack.get("committee_map", [])
        if item.get("role")
    }
    for card in buyer_concierge.get("persona_cards", []):
        role = str(card.get("role") or "Stakeholder")
        outcome = outcome_by_role.get(role) or {}
        board = board_by_role.get(role) or {}
        route = str(card.get("start_route") or outcome.get("proof_route") or "/launch-room")
        if role.lower().startswith(("developer", "qa")):
            route = "/testing"
        roles.append(
            {
                "role": role,
                "first_route": route,
                "spark": str(card.get("spark") or outcome.get("spark") or "Open the proof route."),
                "proof": str(card.get("proof") or board.get("must_believe") or ""),
                "close": str(outcome.get("owner_action") or board.get("close_line") or card.get("buy_trigger") or ""),
            }
        )
    if not any(item["role"] == "QA / Release" for item in roles):
        roles.append(
            {
                "role": "QA / Release",
                "first_route": "/testing",
                "spark": "Changed modules become exact/planned/gap tests and generated skeletons.",
                "proof": f"{_summary(test_factory).get('run_now', 0)} run-now tests in Test Factory.",
                "close": "Confirm the first release smoke and missing test owner.",
            }
        )
    return roles


def _proof_moments(
    *,
    test_factory: dict[str, Any],
    enterprise_trust_center: dict[str, Any],
    commercial_offer_studio: dict[str, Any],
    outcome_ledger: dict[str, Any],
) -> list[dict[str, str]]:
    return [
        {
            "title": "Developer sees a concrete next action",
            "route": "/testing",
            "signal": f"{_summary(test_factory).get('run_now', 0)} run-now tests, {_summary(test_factory).get('generation_tasks', 0)} skeleton tasks.",
        },
        {
            "title": "Security sees locality and caveats",
            "route": "/enterprise-trust-center",
            "signal": f"Trust status {_status(enterprise_trust_center)} / {_score(enterprise_trust_center)}.",
        },
        {
            "title": "Director sees buyable offers",
            "route": "/commercial-offer-studio",
            "signal": f"{_summary(commercial_offer_studio).get('offers', 0)} offers and {_summary(commercial_offer_studio).get('pricing_tiers', 0)} price anchors.",
        },
        {
            "title": "Sponsor sees outcome ownership",
            "route": "/outcome-ledger",
            "signal": f"{_summary(outcome_ledger).get('success_metrics', 0)} metrics and {_summary(outcome_ledger).get('risk_items', 0)} risk items.",
        },
        {
            "title": "Everybody leaves with proof",
            "route": "/evidence-bundle",
            "signal": "Artifacts are exportable as JSON/Markdown with SHA-256 manifest.",
        },
    ]


def _route_set(items: list[dict[str, Any]], key: str = "route") -> set[str]:
    return {str(item.get(key) or "") for item in items if item.get(key)}


def _commercial_close_routes(commercial_offer_studio: dict[str, Any]) -> set[str]:
    close_packet = commercial_offer_studio.get("close_packet") or {}
    one_page_order = close_packet.get("one_page_order") or {}
    return (
        {str(one_page_order.get("route") or "")}
        | _route_set(list(close_packet.get("mutual_action_plan") or []))
        | _route_set(list(close_packet.get("buyer_commitments") or []))
        | _route_set(list(close_packet.get("evidence_requirements") or []))
        | _route_set(list(close_packet.get("checkout") or []))
    ) - {""}


def _commercial_close_packet(
    *,
    commercial_offer_studio: dict[str, Any],
    proof_packet: dict[str, Any],
) -> dict[str, Any]:
    close_packet = commercial_offer_studio.get("close_packet") or {}
    one_page_order = close_packet.get("one_page_order") or {}
    checkout = list(close_packet.get("checkout") or [])
    evidence_requirements = list(close_packet.get("evidence_requirements") or [])
    mutual_action_plan = list(close_packet.get("mutual_action_plan") or [])
    buyer_commitments = list(close_packet.get("buyer_commitments") or [])
    close_script = list(close_packet.get("close_script") or [])

    if not checkout:
        checkout = [
            {
                "gate": "Proof archive is exportable",
                "route": "/evidence-bundle",
                "evidence": "Evidence Bundle has bundle id, files and SHA-256 manifest.",
            },
            {
                "gate": "Verification packet is downloadable",
                "route": "/evidence-bundle",
                "evidence": f"{ARCHIVE_VERIFICATION_PACKET_ZIP} is created from Evidence and Killer Demo archives with hash receipts.",
            },
            {
                "gate": "Approval scope is visible",
                "route": "/approvals",
                "evidence": "Risky write/action records name actor, reason, tool and constraints.",
            },
            {
                "gate": "Audit chain is valid",
                "route": "/audit",
                "evidence": "Audit verification reports a valid hash chain.",
            },
            {
                "gate": "Trust caveats are visible",
                "route": "/enterprise-trust-center",
                "evidence": "Security and architecture caveats are named before quote.",
            },
        ]
    if not evidence_requirements:
        evidence_requirements = [
            {"artifact": "Evidence Bundle ZIP", "route": "/evidence-bundle", "why": "Forwardable proof with SHA-256 manifest."},
            {"artifact": "Governance proof", "route": "/approvals", "why": "Approval records, scope constraints and audit trail."},
            {"artifact": "Audit verify", "route": "/audit", "why": "Tamper-evident hash-chain status."},
        ]
    if not any(str(item.get("artifact") or "") == "Buyer Room Packet ZIP" for item in evidence_requirements):
        evidence_requirements = [
            {
                "artifact": "Buyer Room Packet ZIP",
                "route": "/",
                "why": "Open-first room packet with Buyer Brief, Buyer Pulse, room plan, purchase path and procurement handoff.",
            },
            *evidence_requirements,
        ]
    killer_archive = proof_packet.get("killer_archive") or {}
    if killer_archive and not any(str(item.get("artifact") or "") == "Killer Demo ZIP" for item in evidence_requirements):
        killer_requirement = {
            "artifact": "Killer Demo ZIP",
            "route": "/killer-demo",
            "why": "One buyer-forwardable archive with Evidence Bundle, current demo proof, proof-packet JSON, role packets and demo manifest.",
        }
        insert_at = 1 if evidence_requirements and str(evidence_requirements[0].get("artifact") or "") == "Buyer Room Packet ZIP" else 0
        evidence_requirements = [
            *evidence_requirements[:insert_at],
            killer_requirement,
            *evidence_requirements[insert_at:],
        ]
    if not any(str(item.get("artifact") or "") == "Meeting Close Receipt" for item in evidence_requirements):
        receipt_requirement = {
            "artifact": "Meeting Close Receipt",
            "route": "/killer-demo",
            "why": "One-page post-demo receipt with accepted roles, blockers, next paid step and proof files to forward.",
        }
        if evidence_requirements and str(evidence_requirements[0].get("artifact") or "") == "Killer Demo ZIP":
            evidence_requirements = [evidence_requirements[0], receipt_requirement, *evidence_requirements[1:]]
        else:
            evidence_requirements = [receipt_requirement, *evidence_requirements]
    if not any(str(item.get("artifact") or "") == "Post-Demo Activation Handoff" for item in evidence_requirements):
        activation_requirement = {
            "artifact": "Post-Demo Activation Handoff",
            "route": "/killer-demo",
            "why": "Connects close receipt, paid start, Day 7 proof and Day 30 acceptance so the buyer knows what happens after the ZIP.",
        }
        insert_at = 2 if len(evidence_requirements) >= 2 else len(evidence_requirements)
        evidence_requirements = [*evidence_requirements[:insert_at], activation_requirement, *evidence_requirements[insert_at:]]
    verification_packet = proof_packet.get("verification_packet") or {}
    if verification_packet and not any(
        str(item.get("artifact") or "") == "Verification Packet ZIP" for item in evidence_requirements
    ):
        verification_requirement = {
            "artifact": "Verification Packet ZIP",
            "route": "/evidence-bundle",
            "why": "Procurement can verify both archive hashes, receipts and packet files without trusting screenshots.",
        }
        insert_at = 3 if len(evidence_requirements) >= 3 else len(evidence_requirements)
        evidence_requirements = [
            *evidence_requirements[:insert_at],
            verification_requirement,
            *evidence_requirements[insert_at:],
        ]
    evidence_priority = {
        "Buyer Room Packet ZIP": 0,
        "Killer Demo ZIP": 1,
        "Meeting Close Receipt": 2,
        "Post-Demo Activation Handoff": 3,
        "Verification Packet ZIP": 4,
    }
    evidence_requirements = [
        item
        for _, item in sorted(
            enumerate(evidence_requirements),
            key=lambda pair: (evidence_priority.get(str(pair[1].get("artifact") or ""), 1000), pair[0]),
        )
    ]
    if not mutual_action_plan:
        mutual_action_plan = [
            {
                "window": "Today",
                "owner": "sponsor + seller",
                "action": "Choose paid proof, hardening, pilot or enterprise local-license motion.",
                "artifact": "Commercial Offer Studio",
                "route": "/commercial-offer-studio",
                "exit": "Buyer names one paid next step and owner.",
            },
            {
                "window": "24 hours",
                "owner": "tech lead",
                "action": "Attach the strongest proof archive and role handoff.",
                "artifact": "Evidence Bundle",
                "route": "/evidence-bundle",
                "exit": "Buyer can forward one archive with hashes and caveats.",
            },
        ]
    if not buyer_commitments:
        buyer_commitments = [
            {"role": "finance", "commitment": "Accept local value anchor and separate optional AI credits.", "route": "/business-case"},
            {"role": "security", "commitment": "Confirm required approval and audit evidence.", "route": "/approvals"},
            {"role": "sponsor", "commitment": "Approve paid next step or explicit hardening scope.", "route": "/commercial-offer-studio"},
        ]
    if not close_script:
        close_script = [
            "We can keep discussing features, or we can buy proof of one real 1C pain today.",
            "The price is anchored to local evidence value, not token usage.",
            "If security blocks rollout, we sell hardening scope instead of pretending the risk is gone.",
        ]

    close_ready = bool(close_packet.get("ready_to_close", _status(commercial_offer_studio) == "ready"))
    forward_ready = bool(proof_packet.get("ready_to_forward"))
    proof_routes = sorted(
        _commercial_close_routes(commercial_offer_studio)
        | _route_set(checkout)
        | _route_set(evidence_requirements)
        | _route_set(mutual_action_plan)
        | _route_set(buyer_commitments)
    )
    return {
        "ready_to_close": close_ready,
        "forward_ready": forward_ready,
        "ready_to_ask": close_ready and forward_ready,
        "close_mode": str(close_packet.get("close_mode") or "open_enterprise_purchase"),
        "primary_ask": str(close_packet.get("primary_ask") or "Open enterprise local-license procurement with the proof packet attached."),
        "one_page_order": {
            "product": str(one_page_order.get("product") or "1C Rentgen local evidence control plane"),
            "recommended_purchase": str(one_page_order.get("recommended_purchase") or "Enterprise local license"),
            "commercial_frame": str(one_page_order.get("commercial_frame") or "fixed paid next step"),
            "value_anchor": str(one_page_order.get("value_anchor") or "Business Case"),
            "ai_rent_baseline": str(one_page_order.get("ai_rent_baseline") or "optional AI credits"),
            "three_year_ai_rent": str(one_page_order.get("three_year_ai_rent") or "not provided"),
            "local_license_anchor": str(one_page_order.get("local_license_anchor") or "Business Case"),
            "break_even": str(one_page_order.get("break_even") or "review Business Case"),
            "first_invoice_trigger": str(one_page_order.get("first_invoice_trigger") or "Buyer names owner, scope, date and accepted proof artifacts."),
            "route": str(one_page_order.get("route") or "/commercial-offer-studio"),
        },
        "checkout": checkout,
        "evidence_requirements": evidence_requirements,
        "mutual_action_plan": mutual_action_plan,
        "buyer_commitments": buyer_commitments,
        "close_script": close_script,
        "proof_routes": proof_routes,
        "buyer_line": (
            "Close is ready with a forwardable proof packet."
            if close_ready and forward_ready
            else "Use the checkout gates and procurement handoff to turn interest into paid proof, hardening or pilot scope."
        ),
    }


def _close_scripts(board_pack: dict[str, Any], outcome_ledger: dict[str, Any]) -> list[dict[str, str]]:
    offer = board_pack.get("recommended_offer") or {}
    motion = str((outcome_ledger.get("summary") or {}).get("recommended_motion") or offer.get("id") or "local pilot")
    return [
        {
            "audience": "developer",
            "line": "Pick one changed module; we will show the test package and missing proof before the next review.",
            "route": "/testing",
        },
        {
            "audience": "security",
            "line": "Name the artifact you need for pilot approval; we will attach it to the Evidence Bundle.",
            "route": "/enterprise-trust-center",
        },
        {
            "audience": "director",
            "line": f"Approve {motion} as the next step and use the proof packet for finance/security forwarding.",
            "route": "/board-pack",
        },
        {
            "audience": "sponsor",
            "line": "Book Day 7 proof and Day 30 acceptance before the meeting ends.",
            "route": "/outcome-ledger",
        },
    ]


def _exports() -> list[dict[str, str]]:
    return [
        {"title": "Killer Demo Path markdown", "filename": "rentgen-killer-demo-path.md", "route": "/killer-demo"},
        {"title": "Launch Room markdown", "filename": "rentgen-launch-room.md", "route": "/launch-room"},
        {"title": "Test Factory markdown", "filename": "rentgen-test-factory.md", "route": "/testing"},
        {"title": "Safe Autopilot markdown", "filename": "rentgen-safe-autopilot.md", "route": "/safe-autopilot"},
        {"title": "Board Pack markdown", "filename": "rentgen-board-pack.md", "route": "/board-pack"},
        {"title": "Outcome Ledger markdown", "filename": "rentgen-outcome-ledger.md", "route": "/outcome-ledger"},
        {"title": "Governance Proof markdown", "filename": "governance-proof.md", "route": "/approvals"},
        {"title": "Audit verification/export", "filename": "rentgen-audit-log.jsonl", "route": "/audit"},
        {"title": "Evidence Bundle manifest", "filename": "evidence-bundle-manifest.json", "route": "/evidence-bundle"},
    ]


def role_packet_filename(recipient: str) -> str:
    slug_chars: list[str] = []
    previous_separator = False
    for char in recipient.upper():
        if "A" <= char <= "Z" or char.isdigit():
            slug_chars.append(char)
            previous_separator = False
        elif not previous_separator:
            slug_chars.append("_")
            previous_separator = True
    slug = "".join(slug_chars).strip("_") or "STAKEHOLDER"
    return f"ROLE_{slug}.md"


MEETING_CLOSE_RECEIPT_MD = "MEETING_CLOSE_RECEIPT.md"
MEETING_CLOSE_RECEIPT_JSON = "meeting-close-receipt.json"
POST_DEMO_ACTIVATION_MD = "POST_DEMO_ACTIVATION_HANDOFF.md"
POST_DEMO_ACTIVATION_JSON = "post-demo-activation-handoff.json"
BUYER_ROOM_PACKET_ZIP = "rentgen-buyer-room-packet.zip"
BUYER_ROOM_PACKET_ENDPOINT = "/api/v1/management/buyer-room-packet"
BUYER_ROOM_PACKET_HASH_HEADER = "X-Buyer-Room-Packet-Sha256"
KILLER_DEMO_ARCHIVE_HASH_HEADER = "X-Killer-Demo-Archive-Sha256"
ARCHIVE_VERIFICATION_PACKET_ZIP = "archive-verification-packet.zip"
ARCHIVE_VERIFICATION_PACKET_ENDPOINT = "/api/v1/evidence-bundle/archive/verification-packet"
ARCHIVE_VERIFICATION_PACKET_HASH_HEADER = "X-Verification-Packet-Sha256"
ARCHIVE_VERIFICATION_PACKET_OPEN_FIRST = "OPEN_FIRST_VERIFICATION_PACKET.md"


def _role_file_availability(send_files: list[str], available_filenames: set[str]) -> dict[str, Any]:
    available: list[str] = []
    missing: list[str] = []
    for filename in send_files:
        if filename in available_filenames:
            available.append(filename)
        elif filename == "killer-demo.md" and "rentgen-killer-demo-path.md" in available_filenames:
            available.append("rentgen-killer-demo-path.md")
        else:
            missing.append(filename)
    return {
        "available_files": available,
        "missing_files": missing,
        "availability_status": "ready" if not missing else "partial" if available else "missing",
    }


def _role_packet_rollup(handoff: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(handoff)
    ready = len([item for item in handoff if item.get("availability_status") == "ready"])
    partial = len([item for item in handoff if item.get("availability_status") == "partial"])
    missing = len([item for item in handoff if item.get("availability_status") == "missing"])
    available_names = sorted({str(file) for item in handoff for file in item.get("available_files", []) if file})
    missing_names = sorted({str(file) for item in handoff for file in item.get("missing_files", []) if file})
    status = "ready" if total and ready == total else "partial" if ready or partial else "missing"
    if not total:
        status = "missing"
    return {
        "status": status,
        "total": total,
        "ready": ready,
        "partial": partial,
        "missing": missing,
        "available_files": len(available_names),
        "missing_files": len(missing_names),
        "missing_file_names": missing_names[:20],
        "line": (
            f"{ready}/{total} role packets fully covered; {partial} partial; {len(missing_names)} unique files missing."
            if total
            else "No role packets were produced for this proof packet."
        ),
    }


def _packet_file(item: dict[str, Any], route_by_id: dict[str, str]) -> dict[str, str]:
    artifact_id = str(item.get("id") or "")
    return {
        "id": artifact_id,
        "filename": str(item.get("filename") or ""),
        "media_type": str(item.get("media_type") or ""),
        "sha256": str(item.get("sha256") or ""),
        "route": route_by_id.get(artifact_id, "/evidence-bundle" if artifact_id == "procurement-handoff" else ""),
    }


_PACKET_FILE_PRIORITY = {
    "buyer-brief.md": 0,
    "buyer-pulse.md": 1,
    "open-first-path.md": 1,
    "buyer-room-plan.md": 1,
    "rentgen-killer-demo-path.md": 2,
    "killer-demo.md": 2,
    "rentgen-security-questionnaire.md": 3,
    "enterprise-trust-center.md": 4,
    "productization-readiness.md": 5,
    "rights-rls.md": 6,
    "update-war-room.md": 7,
    "lock-radar.md": 8,
    "extension-safety.md": 9,
    "test-factory.md": 10,
    "safe-autopilot.md": 11,
    "governance-proof.md": 12,
    "rentgen-developer-report.md": 13,
    "rentgen-architect-report.md": 14,
    "rentgen-director-report.md": 15,
    "rentgen-qa-report.md": 16,
    "board-pack.md": 17,
    "commercial-offer-studio.md": 18,
    "outcome-ledger.md": 19,
    "launch-room.md": 20,
    "procurement-handoff.md": 21,
}

_PACKET_ID_PRIORITY = {
    "buyer-brief": 0,
    "buyer-pulse": 1,
    "open-first-path": 2,
    "buyer-room-plan": 3,
    "killer-demo": 2,
    "security-questionnaire": 3,
    "enterprise-trust-center": 4,
    "productization": 5,
    "rights-rls": 6,
    "update-war-room": 7,
    "lock-radar": 8,
    "extension-safety": 9,
    "test-factory": 10,
    "safe-autopilot": 11,
    "governance-proof": 12,
    "role-report-developer": 13,
    "role-report-architect": 14,
    "role-report-director": 15,
    "role-report-qa": 16,
    "board-pack": 17,
    "commercial-offer-studio": 18,
    "outcome-ledger": 19,
    "launch-room": 20,
    "evidence-bundle": 21,
    "procurement-handoff": 22,
}


def _packet_file_rank(item: dict[str, str]) -> tuple[int, int, int, str]:
    filename = str(item.get("filename") or "")
    media_type = str(item.get("media_type") or "")
    media_rank = 0 if media_type == "text/markdown" else 1 if media_type == "application/json" else 2
    return (
        _PACKET_FILE_PRIORITY.get(filename, 1000),
        media_rank,
        _PACKET_ID_PRIORITY.get(str(item.get("id") or ""), 1000),
        filename,
    )


def _packet_artifact_rank(item: dict[str, Any]) -> tuple[int, str]:
    artifact_id = str(item.get("id") or "")
    return (_PACKET_ID_PRIORITY.get(artifact_id, 1000), artifact_id)


def _json_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _open_first_path_from_artifacts(artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for artifact_id in ("open-first-path", "buyer-brief"):
        artifact = next((item for item in artifacts if str(item.get("id") or "") == artifact_id), None)
        if not artifact:
            continue
        payload = _json_dict(artifact.get("json") or artifact.get("report"))
        direct_path = payload.get("open_first_path")
        if isinstance(direct_path, list):
            return [dict(item) for item in direct_path if isinstance(item, dict)]
        brief_path = (payload.get("buyer_brief") or {}).get("open_first_path") if isinstance(payload.get("buyer_brief"), dict) else None
        if isinstance(brief_path, list):
            return [dict(item) for item in brief_path if isinstance(item, dict)]
    return []


def _proof_packet(
    *,
    evidence_bundle: dict[str, Any] | None,
    exports: list[dict[str, str]],
    proof_routes: list[str],
) -> dict[str, Any]:
    bundle = evidence_bundle or {}
    manifest = bundle.get("manifest") or {}
    procurement_handoff = bundle.get("procurement_handoff") or {}
    recipient_packets = [
        {
            "role": str(item.get("role") or ""),
            "filename": str(item.get("filename") or ""),
            "forwarding_subject": str(item.get("forwarding_subject") or ""),
            "attachments": [str(file) for file in item.get("attachments", []) if file],
            "routes": [str(route) for route in item.get("routes", []) if route],
        }
        for item in procurement_handoff.get("recipient_packets", [])
    ]
    artifacts = list(bundle.get("artifacts") or [])
    files = list(manifest.get("files") or [])
    route_by_id = {str(item.get("id")): str(item.get("route") or "") for item in artifacts}

    selected_ids = {
        "buyer-brief",
        "buyer-pulse",
        "open-first-path",
        "buyer-room-plan",
        "killer-demo",
        "launch-room",
        "test-factory",
        "safe-autopilot",
        "enterprise-trust-center",
        "security-questionnaire",
        "productization",
        "rights-rls",
        "update-war-room",
        "lock-radar",
        "extension-safety",
        "board-pack",
        "outcome-ledger",
        "commercial-offer-studio",
        "governance-proof",
        "evidence-bundle",
        "procurement-handoff",
        "role-report-developer",
        "role-report-architect",
        "role-report-director",
        "role-report-qa",
        "role-report-ops",
        "role-report-vendor",
    }
    if not files:
        files = [
            {
                "id": item["route"].strip("/").replace("/", "-") or "killer-demo",
                "filename": item["filename"],
                "media_type": "text/markdown",
                "sha256": "",
            }
            for item in exports
        ]
    else:
        existing_file_ids = {str(item.get("id") or "") for item in files}
        files.extend(
            {
                "id": item["route"].strip("/").replace("/", "-") or "killer-demo",
                "filename": item["filename"],
                "media_type": "text/markdown",
                "sha256": "",
            }
            for item in exports
            if (item["route"].strip("/").replace("/", "-") or "killer-demo") in selected_ids
            and (item["route"].strip("/").replace("/", "-") or "killer-demo") not in existing_file_ids
        )
    selected_artifacts = [
        {
            "id": str(item.get("id") or ""),
            "title": str(item.get("title") or item.get("id") or ""),
            "route": str(item.get("route") or ""),
            "filename": str(item.get("filename") or ""),
            "status": str(item.get("status") or ""),
            "score": item.get("score"),
            "json_sha256": str(item.get("json_sha256") or ""),
            "markdown_sha256": str(item.get("markdown_sha256") or ""),
        }
        for item in artifacts
        if str(item.get("id") or "") in selected_ids
    ]
    selected_files = [_packet_file(item, route_by_id) for item in files if str(item.get("id") or "") in selected_ids]
    if not selected_files:
        selected_files = [_packet_file(item, route_by_id) for item in files[:12]]
    selected_files = sorted(selected_files, key=_packet_file_rank)
    selected_artifacts = sorted(selected_artifacts, key=_packet_artifact_rank)
    buyer_brief_file = next((item for item in selected_files if item["filename"] == "buyer-brief.md"), None)
    buyer_pulse_file = next((item for item in selected_files if item["filename"] == "buyer-pulse.md"), None)
    open_first_path_file = next((item for item in selected_files if item["filename"] == "open-first-path.md"), None)
    buyer_room_plan_file = next((item for item in selected_files if item["filename"] == "buyer-room-plan.md"), None)
    bundle_sha = str(manifest.get("bundle_sha256") or "")
    bundle_id = str(bundle.get("bundle_id") or "")
    archive_ready = bool(bundle_id and bundle_sha)
    archive_endpoint = str(procurement_handoff.get("archive_endpoint") or "/api/v1/evidence-bundle/archive")
    archive_filename = str(
        procurement_handoff.get("archive_filename")
        or (f"{bundle_id}-evidence-archive.zip" if bundle_id else "evidence-archive.zip")
    )
    killer_archive_filename = f"{bundle_id}-killer-demo-archive.zip" if bundle_id else "killer-demo-archive.zip"
    archive_hash_header = str(procurement_handoff.get("archive_hash_header") or "X-Archive-Sha256")
    self_demo_attached = any(
        item["filename"] in {"killer-demo.md", "rentgen-killer-demo-path.md"}
        for item in selected_files
    )
    missing_files = list(procurement_handoff.get("missing_files") or [])
    blockers = list(procurement_handoff.get("blockers") or [])
    review_items = list(procurement_handoff.get("review_items") or [])
    covered_by_current_demo = [
        str(item.get("filename") or "killer-demo.md")
        for item in missing_files
        if self_demo_attached and str(item.get("filename") or "") == "killer-demo.md"
    ]
    effective_missing_files = [
        item
        for item in missing_files
        if not (self_demo_attached and str(item.get("filename") or "") == "killer-demo.md")
    ]
    effective_blockers = [
        item
        for item in blockers
        if not (self_demo_attached and "killer-demo.md" in str(item))
    ]
    risk_reviews = [
        item
        for item in review_items
        if str(item.get("status") or "").casefold() in {"risk", "blocked", "critical", "fail"}
    ]
    raw_handoff_ready = bool(procurement_handoff.get("ready_to_forward")) if procurement_handoff else archive_ready
    effective_handoff_ready = raw_handoff_ready or (
        bool(procurement_handoff)
        and not effective_missing_files
        and not effective_blockers
        and not risk_reviews
    )
    ready_to_forward = archive_ready and effective_handoff_ready
    handoff_status = str(procurement_handoff.get("status") or "")
    if procurement_handoff and not raw_handoff_ready and ready_to_forward:
        handoff_status = "ready_with_current_demo"
    elif not handoff_status:
        handoff_status = "ready_to_forward" if ready_to_forward else "demo_checklist"
    open_first_path = build_open_first_path(
        existing_path=_open_first_path_from_artifacts(artifacts),
        source="killer-demo-proof-packet",
        orient_title="Buyer Room Map",
        orient_route=str((buyer_brief_file or {}).get("route") or "/"),
        orient_line="Open Buyer Brief, Buyer Pulse and Buyer Room Packet before role-specific proof.",
        orient_file=str((buyer_brief_file or {}).get("filename") or "buyer-brief.md"),
        orient_status="ready" if buyer_brief_file else "watch",
        prove_title="Killer Demo Proof Packet",
        prove_route="/killer-demo",
        prove_line="Show role-ready proof, archive controls and the close-room packet.",
        prove_file="OPEN_FIRST_KILLER_DEMO.md" if self_demo_attached else "killer-demo.md",
        prove_status="ready" if self_demo_attached else "watch",
        close_title="Meeting Close Receipt",
        close_route="/killer-demo",
        close_line="Capture accepted roles, blockers and next paid step.",
        close_file=MEETING_CLOSE_RECEIPT_MD,
        close_status="ready" if ready_to_forward else "watch",
        verify_title="Verification Packet ZIP",
        verify_route="/evidence-bundle",
        verify_line="Attach the pair-level archive verification packet and hash table.",
        verify_file=ARCHIVE_VERIFICATION_PACKET_ZIP,
        verify_status="ready" if archive_ready else "watch",
    )
    procurement_open_order = [
        {
            "step": 1,
            "label": "Buyer Room Packet ZIP",
            "route": "/",
            "endpoint": BUYER_ROOM_PACKET_ENDPOINT,
            "file": BUYER_ROOM_PACKET_ZIP,
            "hash_header": BUYER_ROOM_PACKET_HASH_HEADER,
            "check": "Open the room packet first and record its packet hash before forwarding close-room files.",
        },
        {
            "step": 2,
            "label": "Evidence Bundle ZIP",
            "route": "/evidence-bundle",
            "file": archive_filename,
            "hash_header": archive_hash_header,
            "check": "Record the source Evidence Bundle archive hash.",
        },
        {
            "step": 3,
            "label": "Killer Demo ZIP",
            "route": "/killer-demo",
            "file": killer_archive_filename,
            "hash_header": KILLER_DEMO_ARCHIVE_HASH_HEADER,
            "check": "Record the close-room archive hash and manifest header.",
        },
        {
            "step": 4,
            "label": "Verification Packet ZIP",
            "route": "/evidence-bundle",
            "endpoint": ARCHIVE_VERIFICATION_PACKET_ENDPOINT,
            "file": ARCHIVE_VERIFICATION_PACKET_ZIP,
            "hash_header": ARCHIVE_VERIFICATION_PACKET_HASH_HEADER,
            "check": "Attach the pair-level verification packet and hash table.",
        },
        {
            "step": 5,
            "label": "Meeting Close Receipt",
            "route": "/killer-demo",
            "file": MEETING_CLOSE_RECEIPT_MD,
            "hash_header": "",
            "check": "Record accepted roles, blockers, send files and next paid step.",
        },
        {
            "step": 6,
            "label": "Post-Demo Activation Handoff",
            "route": "/pilot-launchpad",
            "file": POST_DEMO_ACTIVATION_MD,
            "hash_header": "",
            "check": "Start paid activation from the accepted close-room receipt.",
        },
    ]
    procurement_attachments = [
        {
            "title": "Buyer Room Packet",
            "route": "/",
            "endpoint": BUYER_ROOM_PACKET_ENDPOINT,
            "file": BUYER_ROOM_PACKET_ZIP,
            "hash_header": BUYER_ROOM_PACKET_HASH_HEADER,
            "why": "Open-first room packet aligned with Home, Launch Room and Buyer Brief.",
        },
        {
            "title": "Archive acceptance receipt",
            "route": "/evidence-bundle",
            "file": "archive-acceptance-receipt.md",
            "why": "Records Evidence and Killer Demo archive boundaries.",
        },
        {
            "title": "Archive acceptance JSON",
            "route": "/evidence-bundle",
            "file": "archive-acceptance-receipt.json",
            "why": "Machine-readable procurement receipt.",
        },
        {
            "title": "Killer Demo manifest",
            "route": "/killer-demo",
            "file": "killer-demo-manifest.json",
            "hash_header": "X-Killer-Demo-Manifest-Sha256",
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
    ]
    available_filenames = {str(item.get("filename") or "") for item in files if item.get("filename")}
    available_filenames.add(BUYER_ROOM_PACKET_ZIP)
    if archive_ready:
        available_filenames.add(ARCHIVE_VERIFICATION_PACKET_ZIP)

    def role_handoff(
        *,
        recipient: str,
        route: str,
        send: list[str],
        why: str,
    ) -> dict[str, Any]:
        return {
            "recipient": recipient,
            "role_packet": role_packet_filename(recipient),
            "route": route,
            "send": send,
            **_role_file_availability(send, available_filenames),
            "why": why,
        }

    return {
        "bundle_id": bundle_id,
        "bundle_sha256": bundle_sha,
        "artifact_count": len(artifacts),
        "file_count": len(files),
        "ready_to_forward": ready_to_forward,
        "open_first_path": open_first_path,
        "room_map": {
            "ready": bool(buyer_brief_file),
            "route": str((buyer_brief_file or {}).get("route") or "/"),
            "filename": str((buyer_brief_file or {}).get("filename") or "buyer-brief.md"),
            "sha256": str((buyer_brief_file or {}).get("sha256") or ""),
            "packet_filename": BUYER_ROOM_PACKET_ZIP,
            "packet_endpoint": BUYER_ROOM_PACKET_ENDPOINT,
            "packet_hash_header": BUYER_ROOM_PACKET_HASH_HEADER,
            "plan_ready": bool(buyer_room_plan_file),
            "plan_route": str((buyer_room_plan_file or {}).get("route") or "/"),
            "plan_filename": str((buyer_room_plan_file or {}).get("filename") or "buyer-room-plan.md"),
            "plan_sha256": str((buyer_room_plan_file or {}).get("sha256") or ""),
            "open_first_path_ready": bool(open_first_path_file),
            "open_first_path_filename": str((open_first_path_file or {}).get("filename") or "open-first-path.md"),
            "open_first_path_route": str((open_first_path_file or {}).get("route") or "/"),
            "open_first_path_sha256": str((open_first_path_file or {}).get("sha256") or ""),
            "pulse_filename": str((buyer_pulse_file or {}).get("filename") or "buyer-pulse.md"),
            "pulse_sha256": str((buyer_pulse_file or {}).get("sha256") or ""),
            "why": "First-minute room map plus single live-room route, proof file, close question and local-license ask.",
        },
        "archive": {
            "ready": archive_ready,
            "route": "/evidence-bundle",
            "endpoint": archive_endpoint,
            "filename": archive_filename,
            "sha256_header": archive_hash_header,
            "why": "Downloads the same proof packet as a portable ZIP with manifest, artifact files and archive SHA-256.",
        },
        "killer_archive": {
            "ready": ready_to_forward,
            "route": "/killer-demo",
            "endpoint": "/api/v1/killer-demo/archive",
            "filename": killer_archive_filename,
            "sha256_header": KILLER_DEMO_ARCHIVE_HASH_HEADER,
            "evidence_sha256_header": "X-Evidence-Archive-Sha256",
            "manifest": "killer-demo-manifest.json",
            "open_first": "OPEN_FIRST_KILLER_DEMO.md",
            "role_packets": [
                role_packet_filename("developer / QA"),
                role_packet_filename("architect / security"),
                role_packet_filename("director / sponsor"),
            ],
            "why": "Downloads the one-action buyer ZIP: Evidence Bundle plus current Killer Demo markdown, proof-packet JSON, role packets and SHA-256 manifest.",
        },
        "verification_packet": {
            "ready": archive_ready,
            "route": "/evidence-bundle",
            "endpoint": ARCHIVE_VERIFICATION_PACKET_ENDPOINT,
            "filename": ARCHIVE_VERIFICATION_PACKET_ZIP,
            "sha256_header": ARCHIVE_VERIFICATION_PACKET_HASH_HEADER,
            "open_first": ARCHIVE_VERIFICATION_PACKET_OPEN_FIRST,
            "contains": [
                "dual-archive-verification-packet.json",
                "dual-archive-verification-packet.md",
                "evidence-archive-verification-receipt.json",
                "killer-demo-archive-verification-receipt.json",
                "hash-table.json",
            ],
            "why": "Creates the procurement control ZIP: both archives are regenerated, receipts are attached and the hash table lets the buyer verify files offline.",
        },
        "procurement_handoff": {
            "present": bool(procurement_handoff),
            "ready": ready_to_forward,
            "status": handoff_status,
            "title": "Close-room procurement handoff",
            "owner_line": (
                "After the live proof, open the Buyer Room Packet first, then the two full archives, "
                "then the verification packet, close receipt and activation handoff."
            ),
            "acceptance": (
                "Meeting close is buyer-forwardable only when Buyer Room Packet hash, Evidence hash, "
                "Killer Demo hash, Verification Packet hash, close receipt and activation handoff are recorded together."
            ),
            "open_order": procurement_open_order,
            "attachments": procurement_attachments,
            "missing_files": len(effective_missing_files),
            "raw_missing_files": len(missing_files),
            "blockers": len(effective_blockers),
            "raw_blockers": len(blockers),
            "review_items": len(review_items),
            "risk_review_items": len(risk_reviews),
            "recipients": len(procurement_handoff.get("recipients") or []),
            "verification_steps": len(procurement_handoff.get("verification_steps") or []),
            "covered_by_current_demo": covered_by_current_demo,
            "archive_filename": archive_filename,
            "endpoint": archive_endpoint,
            "hash_header": archive_hash_header,
            "verification_packet_filename": ARCHIVE_VERIFICATION_PACKET_ZIP,
            "verification_packet_endpoint": ARCHIVE_VERIFICATION_PACKET_ENDPOINT,
            "verification_packet_hash_header": ARCHIVE_VERIFICATION_PACKET_HASH_HEADER,
            "buyer_room_packet_filename": BUYER_ROOM_PACKET_ZIP,
            "buyer_room_packet_endpoint": BUYER_ROOM_PACKET_ENDPOINT,
            "buyer_room_packet_hash_header": BUYER_ROOM_PACKET_HASH_HEADER,
            "open_first_file": str(procurement_handoff.get("open_first_file") or "OPEN_FIRST.md"),
            "first_file": "procurement-handoff.md",
            "buyer_line": str(
                procurement_handoff.get("buyer_line")
                or "Forward the ZIP archive with manifest, procurement handoff and role files after SHA-256 is recorded."
            ),
            "why": (
                "Procurement handoff names recipients, required files, blockers and verification steps; "
                "Killer Demo treats the packet as forwardable only when this handoff is effectively clear."
            ),
        },
        "forwarding_kit": {
            "ready": bool(recipient_packets),
            "source": "Evidence Bundle",
            "packets": recipient_packets,
            "packet_count": len(recipient_packets),
            "first_packet": str((recipient_packets[0] if recipient_packets else {}).get("filename") or ""),
            "why": "Role forwarding notes from Evidence Bundle travel into the close receipt and activation handoff.",
        },
        "files": selected_files[:18],
        "artifacts": selected_artifacts[:14],
        "handoff": [
            role_handoff(
                recipient="developer / QA",
                route="/testing",
                send=[
                    "open-first-path.md",
                    "buyer-brief.md",
                    "buyer-room-plan.md",
                    "rentgen-developer-report.md",
                    "rentgen-qa-report.md",
                    "killer-demo.md",
                    "test-factory.md",
                    "safe-autopilot.md",
                    "lock-radar.md",
                    "extension-safety.md",
                    ARCHIVE_VERIFICATION_PACKET_ZIP,
                ],
                why="Shows role-specific proof, changed modules, run-now tests, safe diff blueprint, generated skeletons and missing proof.",
            ),
            role_handoff(
                recipient="architect / security",
                route="/enterprise-trust-center",
                send=[
                    "open-first-path.md",
                    "buyer-brief.md",
                    "buyer-room-plan.md",
                    "enterprise-trust-center.md",
                    "rentgen-security-questionnaire.md",
                    "rentgen-architect-report.md",
                    "platform-doctor.md",
                    "productization-readiness.md",
                    "rights-rls.md",
                    "update-war-room.md",
                    "extension-safety.md",
                    "governance-proof.md",
                    ARCHIVE_VERIFICATION_PACKET_ZIP,
                ],
                why="Shows locality, buyer-forwardable questionnaire, SBOM/offline posture, rights caveats, approval scope and audit proof.",
            ),
            role_handoff(
                recipient="director / sponsor",
                route="/board-pack",
                send=[
                    "open-first-path.md",
                    "buyer-brief.md",
                    "buyer-room-plan.md",
                    "rentgen-director-report.md",
                    "board-pack.md",
                    "outcome-ledger.md",
                    "commercial-offer-studio.md",
                    "governance-proof.md",
                    ARCHIVE_VERIFICATION_PACKET_ZIP,
                ],
                why="Turns technical proof into buying motion, success metrics, checkout gates and next paid step.",
            ),
        ],
        "routes": proof_routes,
        "caveat": (
            "Proof packet is forwardable when archive hash and procurement handoff are ready; otherwise it is a demo route checklist."
        ),
    }


def _opening_brief(
    *,
    primary_route: dict[str, str],
    deal_readiness: dict[str, Any],
    role_sparks: list[dict[str, str]],
    proof_packet: dict[str, Any],
) -> dict[str, Any]:
    next_paid_step = deal_readiness.get("next_paid_step") or {}
    role_entries = [
        {
            "role": item["role"],
            "route": item["first_route"],
            "question": item["spark"],
            "proof": item.get("proof") or item.get("close") or "Open the role proof route.",
        }
        for item in role_sparks[:6]
    ]
    packet_state = "forwardable" if proof_packet.get("ready_to_forward") else "demo"
    return {
        "headline": "Start with one route, not the whole product.",
        "one_sentence": (
            "Rentgen turns a 1C configuration into local evidence: risk, tests, trust, buying motion and proof packet."
        ),
        "first_30_seconds": [
            f"Open {primary_route['label']} ({primary_route['route']}) and name the visible blocker or buying motion.",
            "Show one role proof: developer tests, security trust or director value.",
            f"Close with {next_paid_step.get('label') or 'the next paid step'} and the {packet_state} proof packet.",
        ],
        "first_click": {
            "label": primary_route["label"],
            "route": primary_route["route"],
            "reason": primary_route["reason"],
        },
        "role_entries": role_entries,
        "anti_confusion": [
            {
                "signal": "Too many screens",
                "response": "Use Killer Demo and Launch Room as the single door.",
                "route": "/killer-demo",
            },
            {
                "signal": "Security concern",
                "response": "Lead with Trust Center instead of hiding the risk.",
                "route": "/enterprise-trust-center",
            },
            {
                "signal": "Director asks why buy",
                "response": "Use Local Asset Case and Board Pack as the buying motion.",
                "route": "/board-pack",
            },
            {
                "signal": "Developer wants concrete proof",
                "response": "Open Test Factory and show changed-module tests.",
                "route": "/testing",
            },
        ],
        "success_signal": (
            "Buyer can repeat three pains, owner, next paid step and proof packet recipient."
        ),
    }


def _objection_router(
    *,
    launch_room: dict[str, Any],
    test_factory: dict[str, Any],
    enterprise_trust_center: dict[str, Any],
    commercial_offer_studio: dict[str, Any],
    board_pack: dict[str, Any],
    outcome_ledger: dict[str, Any],
    proof_packet: dict[str, Any],
    deal_readiness: dict[str, Any],
) -> dict[str, Any]:
    close_packet = deal_readiness.get("commercial_close_packet") or {}
    committee = deal_readiness.get("committee_close_board") or {}
    local_asset = deal_readiness.get("local_asset_case") or {}
    board_objections = {
        str(item.get("objection") or "").lower(): item
        for item in board_pack.get("objection_answers", [])
        if item.get("objection")
    }
    ai_answer = next(
        (
            str(item.get("answer") or "")
            for key, item in board_objections.items()
            if "ai" in key or "subscription" in key
        ),
        str(local_asset.get("finance_line") or "Buy local 1C evidence; keep optional AI credits separate from the core product."),
    )
    proof_ready = bool(proof_packet.get("ready_to_forward"))
    close_ready = bool(close_packet.get("ready_to_ask") or deal_readiness.get("status") == "ready_to_ask")
    test_gaps = _int(_summary(test_factory).get("gaps"))
    committee_blocked = _int(committee.get("blocked_roles"))
    committee_scope_first = str(committee.get("status") or "") == "scope_first"
    outcome_summary = _summary(outcome_ledger)
    claim_ready = bool(outcome_summary.get("acceptance_rollup_ready") or (outcome_ledger.get("acceptance_rollup") or {}).get("ready_to_claim"))

    def route_status(*, blocked: bool = False, watch: bool = False) -> str:
        if blocked:
            return "blocked"
        if watch:
            return "watch"
        return "ready"

    items = [
        {
            "id": "too-large",
            "audience": "all",
            "objection": "This looks too large; where do we start?",
            "answer": "Start with one route, one role and one proof. Launch Room and Killer Demo are the single door; deep reports stay behind the first click.",
            "route": "/launch-room",
            "proof_file": "rentgen-launch-room.md",
            "owner": "presenter",
            "status": route_status(watch=_status(launch_room) not in {"ready", "watch"}),
            "close_question": "Which role should we prove first: developer, security or director?",
        },
        {
            "id": "ai-subscription",
            "audience": "director / finance",
            "objection": "Why not just keep paying for AI subscriptions?",
            "answer": ai_answer,
            "route": "/business-case",
            "proof_file": "rentgen-business-case.md",
            "owner": "sponsor + finance",
            "status": "ready",
            "close_question": "Can finance evaluate this as local 1C evidence value with optional AI credits separated?",
        },
        {
            "id": "security",
            "audience": "security / architect",
            "objection": "Security or architecture will block this.",
            "answer": "Do not hide the blocker. Open Trust Center, show the security questionnaire, locality, SBOM/offline, rights, platform caveats, approvals and audit evidence.",
            "route": "/enterprise-trust-center",
            "proof_file": "rentgen-security-questionnaire.md",
            "owner": "security owner",
            "status": route_status(blocked=_is_risky(enterprise_trust_center)),
            "close_question": "Which caveat becomes accepted pilot risk and which becomes paid hardening scope?",
        },
        {
            "id": "developer-proof",
            "audience": "developer / QA",
            "objection": "Developers will not care unless it touches real code.",
            "answer": "Open Test Factory and Safe Autopilot: changed modules become run-now tests, generated skeletons, gaps and safe diff blueprints.",
            "route": "/testing",
            "proof_file": "test-factory.md",
            "owner": "tech lead",
            "status": route_status(blocked=_is_risky(test_factory), watch=test_gaps > 0),
            "close_question": "Which changed module should become the first proof and test owner?",
        },
        {
            "id": "proof-forwarding",
            "audience": "procurement / security",
            "objection": "Can we forward proof after the meeting?",
            "answer": "Use Evidence Bundle: Buyer Room Plan, Buyer Brief, ZIP archive, manifest SHA-256, security questionnaire, governance proof, procurement handoff and role files travel together.",
            "route": "/evidence-bundle",
            "proof_file": "buyer-room-plan.md",
            "owner": "procurement + security",
            "status": route_status(watch=not proof_ready),
            "close_question": "Who receives the archive and records the archive SHA-256 today?",
        },
        {
            "id": "price-before-proof",
            "audience": "director / sponsor",
            "objection": "We need price before looking at all this proof.",
            "answer": "Use Board Pack and Offer Studio: value anchor, recommended purchase, checkout gates and proof packet stay in one paid motion.",
            "route": "/commercial-offer-studio",
            "proof_file": "commercial-offer-studio.md",
            "owner": "sponsor + seller",
            "status": route_status(watch=not close_ready),
            "close_question": str(committee.get("final_question") or "Can we approve proof, hardening or local pilot as the next paid step?"),
        },
        {
            "id": "after-purchase",
            "audience": "sponsor / delivery lead",
            "objection": "What happens after the demo?",
            "answer": "Use Pilot Launchpad and Outcome Ledger: Day 0/7/30 sign-off, acceptance rollup, governance refresh and measured outcomes.",
            "route": "/outcome-ledger",
            "proof_file": "rentgen-outcome-ledger.md",
            "owner": "pilot owner",
            "status": route_status(blocked=committee_scope_first, watch=(committee_blocked > 0 or not claim_ready)),
            "close_question": "Can we book Day 7 proof and Day 30 acceptance owner now?",
        },
    ]
    blocked = [item for item in items if item["status"] == "blocked"]
    watch = [item for item in items if item["status"] == "watch"]
    first = blocked[0] if blocked else watch[0] if watch else items[0]
    return {
        "status": "blocked" if blocked else "watch" if watch else "ready",
        "ready_items": len([item for item in items if item["status"] == "ready"]),
        "watch_items": len(watch),
        "blocked_items": len(blocked),
        "primary_objection": first,
        "items": items,
        "proof_routes": sorted({str(item["route"]) for item in items} | {"/approvals", "/audit", "/evidence-bundle"}),
        "presenter_line": "Do not debate from memory: pick the objection, open the route, show the file and ask the close question.",
    }


def _deal_readiness(
    *,
    score: int,
    launch_room: dict[str, Any],
    test_factory: dict[str, Any],
    enterprise_trust_center: dict[str, Any],
    commercial_offer_studio: dict[str, Any],
    board_pack: dict[str, Any],
    outcome_ledger: dict[str, Any],
    role_sparks: list[dict[str, str]],
    proof_packet: dict[str, Any],
) -> dict[str, Any]:
    blockers: list[dict[str, str]] = []
    if _is_risky(enterprise_trust_center):
        blockers.append(
            {
                "id": "trust",
                "severity": "high",
                "title": "Trust approval is the visible blocker.",
                "route": "/enterprise-trust-center",
                "action": "Name required locality, SBOM/offline, rights and platform artifacts before quoting rollout.",
            }
        )
    if _is_risky(test_factory) or _int(_summary(test_factory).get("gaps")) > 0:
        blockers.append(
            {
                "id": "tests",
                "severity": "medium",
                "title": "Developer proof still has test gaps.",
                "route": "/testing",
                "action": "Use a paid proof sprint or generate the missing YAxUnit/Vanessa skeletons before enterprise close.",
            }
        )
    if not proof_packet.get("ready_to_forward"):
        handoff = proof_packet.get("procurement_handoff") or {}
        missing = _int(handoff.get("missing_files"))
        blockers_count = _int(handoff.get("blockers"))
        reviews = _int(handoff.get("risk_review_items") or handoff.get("review_items"))
        action = (
            f"Resolve procurement handoff before the ask: {missing} missing files, "
            f"{blockers_count} blockers and {reviews} review items; then attach archive SHA-256."
            if handoff
            else "Build Evidence Bundle and attach bundle id plus SHA-256 manifest."
        )
        blockers.append(
            {
                "id": "packet",
                "severity": "medium",
                "title": "Proof packet is not forwardable yet.",
                "route": "/evidence-bundle",
                "action": action,
            }
        )
    if _status(board_pack) not in {"ready", "watch"}:
        blockers.append(
            {
                "id": "board",
                "severity": "medium",
                "title": "Board motion is not buyer-ready.",
                "route": "/board-pack",
                "action": "Refresh Board Pack before asking for a commercial decision.",
            }
        )

    close_packet = commercial_offer_studio.get("close_packet") or {}
    close_mode = str(close_packet.get("close_mode") or "")
    if close_packet and not bool(close_packet.get("ready_to_close")) and not any(item["id"] == "trust" for item in blockers):
        blockers.append(
            {
                "id": "commercial-close",
                "severity": "high" if close_mode == "sell_hardening_before_rollout" else "medium",
                "title": "Commercial close is not ready without explicit scope.",
                "route": "/commercial-offer-studio",
                "action": str(close_packet.get("primary_ask") or "Convert the blocker into paid proof, hardening or pilot scope."),
            }
        )

    offer_summary = _summary(commercial_offer_studio)
    outcome_summary = _summary(outcome_ledger)
    launch_summary = launch_room.get("launch_summary") or {}
    first_year_value = _int(
        launch_summary.get("first_year_visible_value")
        or (board_pack.get("summary") or {}).get("first_year_visible_value")
        or (outcome_ledger.get("summary") or {}).get("first_year_visible_value")
    )
    value_anchor = str(launch_summary.get("value_anchor") or (board_pack.get("board_snapshot") or {}).get("value_anchor") or "")
    one_page_order = close_packet.get("one_page_order") or {}
    three_year_ai_rent = str(one_page_order.get("three_year_ai_rent") or (board_pack.get("board_snapshot") or {}).get("three_year_ai_rent") or "not provided")
    local_license_anchor = str(one_page_order.get("local_license_anchor") or (board_pack.get("board_snapshot") or {}).get("local_license_anchor") or "Business Case")
    break_even = str(one_page_order.get("break_even") or (board_pack.get("board_snapshot") or {}).get("break_even") or "review Business Case")
    primary_ask = str(close_packet.get("primary_ask") or "")
    next_paid_step = {
        "label": str(one_page_order.get("recommended_purchase") or "Enterprise local license"),
        "route": str(one_page_order.get("route") or "/commercial-offer-studio"),
        "owner": "director / CIO",
        "acceptance": primary_ask or "Finance, security and architecture accept value, install mode and proof packet.",
    }
    if any(item["id"] == "trust" for item in blockers):
        next_paid_step = {
            "label": "Platform and trust hardening pack",
            "route": "/enterprise-trust-center",
            "owner": "security / architect",
            "acceptance": "Every high trust/platform blocker has owner, artifact, fix or accepted risk.",
        }
    elif any(item["id"] == "tests" for item in blockers):
        next_paid_step = {
            "label": "24-hour proof sprint",
            "route": "/testing",
            "owner": "developer / QA lead",
            "acceptance": "One changed module has run-now tests, missing tests and proof artifact.",
        }
    elif any(item["id"] == "commercial-close" for item in blockers):
        next_paid_step = {
            "label": str(one_page_order.get("recommended_purchase") or "Commercial close scope"),
            "route": "/commercial-offer-studio",
            "owner": "director / security / architect",
            "acceptance": primary_ask or "Paid proof, hardening or pilot scope is explicit before rollout is quoted.",
        }
    elif _score(board_pack) < 80:
        next_paid_step = {
            "label": "30-day local license pilot",
            "route": "/pilot-launchpad",
            "owner": "sponsor / delivery lead",
            "acceptance": "Pilot owner, date and Day 7/Day 30 acceptance are selected.",
        }

    role_acceptance = [
        {
            "role": item["role"],
            "status": "ready" if item.get("proof") and item.get("close") else "watch",
            "route": item["first_route"],
            "must_hear": item["spark"],
            "proof": item["proof"],
            "close": item["close"],
        }
        for item in role_sparks
    ][:8]

    def _role_blocker(role: str) -> dict[str, str] | None:
        role_lower = role.casefold()
        for blocker in blockers:
            blocker_id = blocker["id"]
            if blocker_id == "trust" and any(token in role_lower for token in ("architect", "security", "cio")):
                return blocker
            if blocker_id == "tests" and any(token in role_lower for token in ("developer", "qa", "release")):
                return blocker
            if blocker_id in {"packet", "commercial-close", "board"} and any(
                token in role_lower for token in ("director", "sponsor", "finance", "cio")
            ):
                return blocker
        return None

    def _role_send(role: str) -> list[str]:
        role_lower = role.casefold()
        if any(token in role_lower for token in ("developer", "qa", "release")):
            return ["buyer-brief.md", "buyer-room-plan.md", "safe-autopilot.md", "test-factory.md", "change-plan.md"]
        if any(token in role_lower for token in ("architect", "security", "cio")):
            return [
                "buyer-brief.md",
                "buyer-room-plan.md",
                "enterprise-trust-center.md",
                "rentgen-security-questionnaire.md",
                "platform-doctor.md",
                "governance-proof.md",
                "audit-log.jsonl",
            ]
        if any(token in role_lower for token in ("director", "sponsor", "finance")):
            return [
                "buyer-brief.md",
                "buyer-room-plan.md",
                "board-pack.md",
                "commercial-offer-studio.md",
                "outcome-ledger.md",
                "evidence-bundle-manifest.json",
            ]
        return ["buyer-brief.md", "buyer-room-plan.md", "killer-demo.md", "launch-room.md", "evidence-bundle-manifest.json"]

    committee_roles: list[dict[str, Any]] = []
    for item in role_acceptance:
        blocker = _role_blocker(item["role"])
        status_for_role = "blocked" if blocker else ("accepted" if item["status"] == "ready" else "watch")
        committee_roles.append(
            {
                "role": item["role"],
                "status": status_for_role,
                "route": item["route"],
                "accepted_proof": item["proof"],
                "send": _role_send(item["role"]),
                "remaining_question": blocker["action"] if blocker else item["close"],
                "blocker": blocker["id"] if blocker else "",
            }
        )

    accepted_roles = len([item for item in committee_roles if item["status"] == "accepted"])
    blocked_roles = len([item for item in committee_roles if item["status"] == "blocked"])
    committee_status = "ready_to_ask" if blocked_roles == 0 and proof_packet.get("ready_to_forward") else "proof_first"
    if any(item["severity"] == "high" for item in blockers):
        committee_status = "scope_first"
    readiness_score = max(0, min(100, score - 10 * len([item for item in blockers if item["severity"] == "high"]) - 5 * len(blockers)))
    status = "ready" if readiness_score >= 82 and not blockers else "watch"
    if any(item["severity"] == "high" for item in blockers):
        status = "risk"
    return {
        "status": status,
        "score": readiness_score,
        "decision_line": (
            "Ask for the next paid step now."
            if status == "ready"
            else "Lead with the blockers, convert them into paid proof or hardening scope, then close."
        ),
        "next_paid_step": next_paid_step,
        "blockers": blockers,
        "role_acceptance": role_acceptance,
        "committee_close_board": {
            "status": committee_status,
            "accepted_roles": accepted_roles,
            "blocked_roles": blocked_roles,
            "total_roles": len(committee_roles),
            "headline": (
                "Buying committee is ready for the paid ask."
                if committee_status == "ready_to_ask"
                else "Buying committee needs proof or scoped hardening before the paid ask."
            ),
            "final_question": (
                "Can we open procurement for the selected local-license motion with these owners and artifacts?"
                if committee_status == "ready_to_ask"
                else "Which blocker becomes paid proof, hardening or pilot scope before procurement?"
            ),
            "roles": committee_roles,
            "handoff": proof_packet.get("handoff", []),
        },
        "customer_can_repeat": [
            "This is a local 1C evidence product, not another AI subscription.",
            f"Proof packet is {'forwardable' if proof_packet.get('ready_to_forward') else 'not forwardable yet'} with {proof_packet.get('file_count', 0)} files.",
            f"Offer Studio has {_int(offer_summary.get('offers'))} offers; Outcome Ledger has {_int(outcome_summary.get('success_metrics'))} success metrics.",
            str(launch_summary.get("one_line") or "One guided route connects role, proof, trust, approval and outcomes."),
        ],
        "local_asset_case": {
            "headline": "Buy local 1C evidence, not endless generic AI rent.",
            "value_anchor": value_anchor or (f"{first_year_value} visible first-year value" if first_year_value else "visible first-year value is calculated in Business Case"),
            "ai_rent_baseline": str(one_page_order.get("ai_rent_baseline") or (board_pack.get("board_snapshot") or {}).get("ai_rent_baseline") or "optional AI credits"),
            "three_year_ai_rent": three_year_ai_rent,
            "local_license_anchor": local_license_anchor,
            "break_even": break_even,
            "why_it_is_asset": [
                "Configuration graph, risks, tests, approvals and evidence stay in the customer's contour.",
                "Core reports work without external AI; AI becomes optional capacity, not the source of truth.",
                "SHA-256 proof packet can be forwarded to finance, security and architecture without screenshots.",
            ],
            "proof_routes": [
                "/business-case",
                "/commercial-offer-studio",
                "/approvals",
                "/audit",
                "/enterprise-trust-center",
                "/productization",
                "/evidence-bundle",
            ],
            "finance_line": (
                "Use local first-year value and avoided manual/release risk as the price anchor; keep AI credits separate."
            ),
            "security_line": (
                "Use Trust Center, Security Questionnaire, Productization and Evidence Bundle to prove locality, SBOM/offline posture and artifact hashes."
            ),
        },
        "close_checklist": [
            "Can the buyer name three pains the demo covered?",
            "Is the proof packet forwardable with a bundle hash?",
            "Is the next paid step named with owner and acceptance?",
            "Are trust/test blockers converted into explicit scope instead of hidden risk?",
        ],
    }


def _meeting_close_receipt(
    *,
    client_name: str,
    decision: dict[str, Any],
    proof_packet: dict[str, Any],
    commercial_close_packet: dict[str, Any],
    deal_readiness: dict[str, Any],
    objection_router: dict[str, Any],
) -> dict[str, Any]:
    committee = deal_readiness.get("committee_close_board") or {}
    next_paid_step = deal_readiness.get("next_paid_step") or {}
    order = commercial_close_packet.get("one_page_order") or {}
    procurement = proof_packet.get("procurement_handoff") or {}
    killer_archive = proof_packet.get("killer_archive") or {}
    verification_packet = proof_packet.get("verification_packet") or {}
    role_rollup = proof_packet.get("role_packet_rollup") or {}
    forwarding_kit = proof_packet.get("forwarding_kit") or {}
    primary_objection = objection_router.get("primary_objection") or {}
    blockers = [
        {
            "id": str(item.get("id") or ""),
            "severity": str(item.get("severity") or ""),
            "title": str(item.get("title") or ""),
            "route": str(item.get("route") or "/killer-demo"),
            "action": str(item.get("action") or ""),
        }
        for item in deal_readiness.get("blockers", [])
    ]
    roles = [
        {
            "role": str(item.get("role") or ""),
            "status": str(item.get("status") or ""),
            "route": str(item.get("route") or "/killer-demo"),
            "accepted_proof": str(item.get("accepted_proof") or ""),
            "send": [str(file) for file in item.get("send", []) if file],
            "remaining_question": str(item.get("remaining_question") or ""),
            "blocker": str(item.get("blocker") or ""),
        }
        for item in committee.get("roles", [])
    ]
    role_packets = [
        {
            "recipient": str(item.get("recipient") or ""),
            "filename": str(item.get("role_packet") or role_packet_filename(str(item.get("recipient") or "stakeholder"))),
            "status": str(item.get("availability_status") or ""),
            "route": str(item.get("route") or "/killer-demo"),
            "missing_files": [str(file) for file in item.get("missing_files", []) if file],
        }
        for item in proof_packet.get("handoff", [])
    ]
    ready_to_ask = bool(commercial_close_packet.get("ready_to_ask"))
    ready_to_send = bool(proof_packet.get("ready_to_forward"))
    status = "ready_to_ask" if ready_to_ask else str(committee.get("status") or deal_readiness.get("status") or "proof_first")
    headline = (
        "Proof and close are ready for the paid ask."
        if ready_to_ask
        else "Forward proof, name blockers and convert them into paid scope."
        if blockers
        else "Use this receipt to turn proof interest into the next paid step."
    )
    return {
        "schema_version": "1.0",
        "filename": MEETING_CLOSE_RECEIPT_MD,
        "json_filename": MEETING_CLOSE_RECEIPT_JSON,
        "route": "/killer-demo",
        "client_name": client_name,
        "status": status,
        "ready_to_send": ready_to_send,
        "ready_to_ask": ready_to_ask,
        "headline": headline,
        "decision": {
            "status": str(decision.get("status") or ""),
            "score": _int(decision.get("score")),
            "headline": str(decision.get("headline") or ""),
        },
        "primary_ask": str(commercial_close_packet.get("primary_ask") or ""),
        "next_paid_step": {
            "label": str(next_paid_step.get("label") or order.get("recommended_purchase") or "Next paid step"),
            "route": str(next_paid_step.get("route") or order.get("route") or "/commercial-offer-studio"),
            "owner": str(next_paid_step.get("owner") or "director / sponsor"),
            "acceptance": str(next_paid_step.get("acceptance") or order.get("first_invoice_trigger") or ""),
        },
        "proof_packet": {
            "forwardable": ready_to_send,
            "bundle_id": str(proof_packet.get("bundle_id") or "demo-checklist"),
            "archive_filename": str(killer_archive.get("filename") or "killer-demo-archive.zip"),
            "archive_endpoint": str(killer_archive.get("endpoint") or "/api/v1/killer-demo/archive"),
            "archive_hash_header": str(killer_archive.get("sha256_header") or KILLER_DEMO_ARCHIVE_HASH_HEADER),
            "manifest": str(killer_archive.get("manifest") or "killer-demo-manifest.json"),
            "open_first": str(killer_archive.get("open_first") or "OPEN_FIRST_KILLER_DEMO.md"),
            "buyer_room_packet": BUYER_ROOM_PACKET_ZIP,
            "buyer_room_packet_endpoint": BUYER_ROOM_PACKET_ENDPOINT,
            "buyer_room_packet_hash_header": BUYER_ROOM_PACKET_HASH_HEADER,
            "verification_packet": str(verification_packet.get("filename") or ARCHIVE_VERIFICATION_PACKET_ZIP),
            "verification_packet_endpoint": str(
                verification_packet.get("endpoint") or ARCHIVE_VERIFICATION_PACKET_ENDPOINT
            ),
            "verification_packet_hash_header": str(
                verification_packet.get("sha256_header") or ARCHIVE_VERIFICATION_PACKET_HASH_HEADER
            ),
            "verification_packet_open_first": str(
                verification_packet.get("open_first") or ARCHIVE_VERIFICATION_PACKET_OPEN_FIRST
            ),
            "role_packet_rollup": str(role_rollup.get("line") or ""),
            "procurement_status": str(procurement.get("status") or "unknown"),
            "procurement_missing_files": _int(procurement.get("missing_files")),
            "procurement_blockers": _int(procurement.get("blockers")),
        },
        "committee": {
            "status": str(committee.get("status") or ""),
            "accepted_roles": _int(committee.get("accepted_roles")),
            "blocked_roles": _int(committee.get("blocked_roles")),
            "total_roles": _int(committee.get("total_roles")),
            "final_question": str(committee.get("final_question") or ""),
            "roles": roles,
        },
        "role_packets": role_packets,
        "forwarding_kit": forwarding_kit,
        "blockers": blockers,
        "buyer_commitments": [
            {
                "role": str(item.get("role") or ""),
                "commitment": str(item.get("commitment") or ""),
                "route": str(item.get("route") or "/killer-demo"),
            }
            for item in commercial_close_packet.get("buyer_commitments", [])
        ],
        "checkout": [
            {
                "gate": str(item.get("gate") or ""),
                "route": str(item.get("route") or "/killer-demo"),
                "evidence": str(item.get("evidence") or ""),
            }
            for item in commercial_close_packet.get("checkout", [])
        ],
        "customer_can_repeat": [str(item) for item in deal_readiness.get("customer_can_repeat", []) if item],
        "close_questions": [
            str(committee.get("final_question") or ""),
            str(primary_objection.get("close_question") or ""),
        ],
        "send_files": [
            BUYER_ROOM_PACKET_ZIP,
            MEETING_CLOSE_RECEIPT_MD,
            MEETING_CLOSE_RECEIPT_JSON,
            str(killer_archive.get("open_first") or "OPEN_FIRST_KILLER_DEMO.md"),
            str(verification_packet.get("filename") or ARCHIVE_VERIFICATION_PACKET_ZIP),
            "proof-packet.json",
            str(killer_archive.get("manifest") or "killer-demo-manifest.json"),
            *[item["filename"] for item in role_packets if item.get("filename")],
        ],
        "why": "Attach this receipt after the demo so sponsor, security, architecture and delivery see the same accepted proof, blockers and paid next step.",
    }


def meeting_close_receipt_markdown(receipt: dict[str, Any]) -> str:
    next_paid = receipt.get("next_paid_step") or {}
    proof = receipt.get("proof_packet") or {}
    committee = receipt.get("committee") or {}
    lines = [
        "# Meeting Close Receipt",
        "",
        f"Client: **{receipt.get('client_name', 'Demo client')}**",
        f"Status: **{receipt.get('status', 'unknown')}**",
        f"Ready to send: **{bool(receipt.get('ready_to_send'))}**",
        f"Ready to ask: **{bool(receipt.get('ready_to_ask'))}**",
        "",
        f"## {receipt.get('headline', 'Post-demo receipt')}",
        "",
        f"- Primary ask: {receipt.get('primary_ask', '')}",
        f"- Next paid step: **{next_paid.get('label', 'n/a')}** (`{next_paid.get('route', '/killer-demo')}`)",
        f"- Owner: {next_paid.get('owner', '')}",
        f"- Acceptance: {next_paid.get('acceptance', '')}",
        "",
        "## Proof To Forward",
        "",
        f"- Archive: `{proof.get('archive_filename', 'killer-demo-archive.zip')}` via `{proof.get('archive_endpoint', '/api/v1/killer-demo/archive')}`",
        f"- Hash header: `{proof.get('archive_hash_header', KILLER_DEMO_ARCHIVE_HASH_HEADER)}`",
        f"- Verification packet: `{proof.get('verification_packet', ARCHIVE_VERIFICATION_PACKET_ZIP)}` via `{proof.get('verification_packet_endpoint', ARCHIVE_VERIFICATION_PACKET_ENDPOINT)}`",
        f"- Verification hash header: `{proof.get('verification_packet_hash_header', ARCHIVE_VERIFICATION_PACKET_HASH_HEADER)}`",
        f"- Verification open-first: `{proof.get('verification_packet_open_first', ARCHIVE_VERIFICATION_PACKET_OPEN_FIRST)}`",
        f"- Open first: `{proof.get('open_first', 'OPEN_FIRST_KILLER_DEMO.md')}`",
        f"- Manifest: `{proof.get('manifest', 'killer-demo-manifest.json')}`",
        f"- Procurement: **{proof.get('procurement_status', 'unknown')}**, missing **{proof.get('procurement_missing_files', 0)}**, blockers **{proof.get('procurement_blockers', 0)}**",
        f"- Role packets: {proof.get('role_packet_rollup', '')}",
        "",
        "## Committee",
        "",
        f"- Status: **{committee.get('status', 'unknown')}**",
        f"- Accepted roles: **{committee.get('accepted_roles', 0)} / {committee.get('total_roles', 0)}**",
        f"- Blocked roles: **{committee.get('blocked_roles', 0)}**",
        f"- Final question: {committee.get('final_question', '')}",
    ]
    for item in committee.get("roles", []):
        send = ", ".join(str(file) for file in item.get("send", []))
        lines.append(
            f"- **{item.get('role', '')}** ({item.get('status', '')}, `{item.get('route', '/killer-demo')}`): "
            f"{item.get('remaining_question', '')}; send {send}"
        )
    role_packets = receipt.get("role_packets") or []
    if role_packets:
        lines.extend(["", "## Role Packets", ""])
        for item in role_packets:
            missing = ", ".join(str(file) for file in item.get("missing_files", [])) or "none"
            lines.append(
                f"- **{item.get('recipient', '')}**: `{item.get('filename', '')}` "
                f"({item.get('status', '')}, `{item.get('route', '/killer-demo')}`), missing {missing}"
            )
    forwarding = receipt.get("forwarding_kit") or {}
    forwarding_packets = forwarding.get("packets") or []
    if forwarding_packets:
        lines.extend(["", "## Forwarding Kit", ""])
        lines.append(f"- Source: **{forwarding.get('source', 'Evidence Bundle')}**")
        lines.append(f"- Packets: **{forwarding.get('packet_count', len(forwarding_packets))}**")
        for item in forwarding_packets:
            attachments = ", ".join(str(file) for file in item.get("attachments", [])[:6])
            lines.append(
                f"- **{item.get('role', '')}**: `{item.get('filename', '')}` / "
                f"{item.get('forwarding_subject', '')}. Attachments: {attachments}"
            )
    blockers = receipt.get("blockers") or []
    if blockers:
        lines.extend(["", "## Blockers To Convert", ""])
        for item in blockers:
            lines.append(
                f"- **{item.get('severity', '')}** / `{item.get('route', '/killer-demo')}`: "
                f"{item.get('title', '')}. Action: {item.get('action', '')}"
            )
    commitments = receipt.get("buyer_commitments") or []
    if commitments:
        lines.extend(["", "## Buyer Commitments", ""])
        for item in commitments:
            lines.append(f"- **{item.get('role', '')}** (`{item.get('route', '/killer-demo')}`): {item.get('commitment', '')}")
    send_files = receipt.get("send_files") or []
    if send_files:
        lines.extend(["", "## Send Files", ""])
        lines.extend(f"- `{file}`" for file in send_files)
    activation = receipt.get("activation_handoff") or {}
    if activation:
        lines.extend(["", "## Post-Demo Activation", ""])
        lines.append(f"- File: `{activation.get('filename', POST_DEMO_ACTIVATION_MD)}`")
        lines.append(f"- Status: **{activation.get('status', 'unknown')}**")
        lines.append(f"- Next route: `{activation.get('route', '/pilot-launchpad')}`")
        lines.append(f"- Line: {activation.get('line', '')}")
    repeat = receipt.get("customer_can_repeat") or []
    if repeat:
        lines.extend(["", "## Customer Can Repeat", ""])
        lines.extend(f"- {item}" for item in repeat)
    questions = [item for item in receipt.get("close_questions", []) if item]
    if questions:
        lines.extend(["", "## Close Questions", ""])
        lines.extend(f"- {item}" for item in questions)
    lines.extend(["", "## Why", "", str(receipt.get("why") or "")])
    return "\n".join(lines)


def _unique_strings(items: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        value = str(item or "")
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _post_demo_activation_handoff(
    *,
    receipt: dict[str, Any],
    proof_packet: dict[str, Any],
    commercial_close_packet: dict[str, Any],
    outcome_ledger: dict[str, Any],
) -> dict[str, Any]:
    next_paid = receipt.get("next_paid_step") or {}
    proof = receipt.get("proof_packet") or {}
    acceptance_rollup = outcome_ledger.get("acceptance_rollup") or {}
    governance_refresh = outcome_ledger.get("governance_refresh") or {}
    outcome_summary = _summary(outcome_ledger)
    blockers = list(receipt.get("blockers") or [])
    role_packets = list(receipt.get("role_packets") or [])
    forwarding_kit = receipt.get("forwarding_kit") or {}
    checkout = list(receipt.get("checkout") or [])
    ready_to_start = bool(receipt.get("ready_to_send")) and bool(next_paid.get("label")) and bool(next_paid.get("route"))
    status = "paid_scope_ready" if ready_to_start and blockers else "ready_to_start" if ready_to_start else "proof_first"
    route_chain = _unique_strings(
        [
            "/killer-demo",
            str(next_paid.get("route") or "/commercial-offer-studio"),
            "/pilot-launchpad",
            "/approvals",
            "/audit",
            "/outcome-ledger",
            "/evidence-bundle",
        ]
    )
    files = _unique_strings(
        [
            BUYER_ROOM_PACKET_ZIP,
            MEETING_CLOSE_RECEIPT_MD,
            MEETING_CLOSE_RECEIPT_JSON,
            POST_DEMO_ACTIVATION_MD,
            POST_DEMO_ACTIVATION_JSON,
            str(proof.get("open_first") or "OPEN_FIRST_KILLER_DEMO.md"),
            str(proof.get("verification_packet") or ARCHIVE_VERIFICATION_PACKET_ZIP),
            "proof-packet.json",
            str(proof.get("manifest") or "killer-demo-manifest.json"),
            *[str(item.get("filename") or "") for item in role_packets],
            *[str(item.get("filename") or "") for item in forwarding_kit.get("packets", [])],
        ]
    )
    timeline: list[dict[str, Any]] = []
    for item in commercial_close_packet.get("mutual_action_plan", [])[:2]:
        timeline.append(
            {
                "window": str(item.get("window") or "Today"),
                "owner": str(item.get("owner") or next_paid.get("owner") or "seller + buyer"),
                "action": str(item.get("action") or ""),
                "route": str(item.get("route") or next_paid.get("route") or "/commercial-offer-studio"),
                "proof_file": MEETING_CLOSE_RECEIPT_MD,
                "exit": str(item.get("exit") or ""),
                "status": "ready" if receipt.get("ready_to_send") else "watch",
            }
        )
    timeline.append(
        {
            "window": "Day 0",
            "owner": str(next_paid.get("owner") or "pilot owner"),
            "action": str(next_paid.get("acceptance") or commercial_close_packet.get("primary_ask") or "Start the paid scope with accepted proof."),
            "route": str(next_paid.get("route") or "/pilot-launchpad"),
            "proof_file": MEETING_CLOSE_RECEIPT_MD,
            "exit": str((commercial_close_packet.get("one_page_order") or {}).get("first_invoice_trigger") or "Paid owner, scope, date and proof recipient are named."),
            "status": "ready" if ready_to_start else "watch",
        }
    )
    rollup_items = list(acceptance_rollup.get("items") or [])
    if rollup_items:
        for item in rollup_items[:4]:
            timeline.append(
                {
                    "window": str(item.get("window") or "Day 30"),
                    "owner": str(item.get("owner") or "pilot owner"),
                    "action": str(item.get("next_action") or item.get("decision") or item.get("acceptance") or ""),
                    "route": str(item.get("evidence_route") or "/outcome-ledger"),
                    "proof_file": str(item.get("evidence_file") or "rentgen-outcome-ledger.md"),
                    "exit": str(item.get("acceptance") or ""),
                    "status": str(item.get("status") or "watch"),
                }
            )
    else:
        timeline.extend(
            [
                {
                    "window": "Day 7",
                    "owner": "developer / QA lead",
                    "action": "Show the first proof result, remaining blockers and refreshed Evidence Bundle.",
                    "route": "/pilot-launchpad",
                    "proof_file": POST_DEMO_ACTIVATION_MD,
                    "exit": "Buyer accepts, blocks or scopes the first proof result.",
                    "status": "watch",
                },
                {
                    "window": "Day 30",
                    "owner": "sponsor / delivery lead",
                    "action": "Decide rollout, hardening scope or next paid package from Outcome Ledger.",
                    "route": "/outcome-ledger",
                    "proof_file": "rentgen-outcome-ledger.md",
                    "exit": "Day 30 decision names measured outcome and next paid motion.",
                    "status": "watch",
                },
            ]
        )
    gates = [
        {
            "gate": "Close receipt is attached",
            "status": "ready" if receipt.get("ready_to_send") else "watch",
            "route": "/killer-demo",
            "evidence": MEETING_CLOSE_RECEIPT_MD,
        },
        {
            "gate": "Killer Demo ZIP hash is recordable",
            "status": "ready" if proof_packet.get("ready_to_forward") else "watch",
            "route": "/killer-demo",
            "evidence": str(proof.get("archive_hash_header") or KILLER_DEMO_ARCHIVE_HASH_HEADER),
        },
        {
            "gate": "Verification packet is attached",
            "status": "ready" if proof_packet.get("verification_packet", {}).get("ready") else "watch",
            "route": "/evidence-bundle",
            "evidence": str(proof.get("verification_packet") or ARCHIVE_VERIFICATION_PACKET_ZIP),
        },
        {
            "gate": "Paid start owner is named",
            "status": "ready" if next_paid.get("owner") else "watch",
            "route": str(next_paid.get("route") or "/commercial-offer-studio"),
            "evidence": str(next_paid.get("acceptance") or ""),
        },
        {
            "gate": "Outcome acceptance path is visible",
            "status": "ready" if acceptance_rollup.get("ready_to_claim") or outcome_summary.get("acceptance_rollup_items") else "watch",
            "route": "/outcome-ledger",
            "evidence": "Day 7/30 acceptance rows or default activation timeline.",
        },
    ]
    gates.extend(
        {
            "gate": str(item.get("gate") or ""),
            "status": "ready",
            "route": str(item.get("route") or "/killer-demo"),
            "evidence": str(item.get("evidence") or ""),
        }
        for item in checkout[:4]
    )
    return {
        "schema_version": "1.0",
        "filename": POST_DEMO_ACTIVATION_MD,
        "json_filename": POST_DEMO_ACTIVATION_JSON,
        "route": str(next_paid.get("route") or "/pilot-launchpad"),
        "status": status,
        "ready_to_start": ready_to_start,
        "headline": (
            "Paid scope can start from the close receipt."
            if ready_to_start
            else "Activation needs a forwardable receipt and named paid owner."
        ),
        "activation_line": (
            f"{next_paid.get('label', 'Next paid step')}: {next_paid.get('acceptance', '')}"
        ),
        "next_paid_step": {
            "label": str(next_paid.get("label") or "Next paid step"),
            "route": str(next_paid.get("route") or "/pilot-launchpad"),
            "owner": str(next_paid.get("owner") or "pilot owner"),
            "acceptance": str(next_paid.get("acceptance") or ""),
        },
        "invoice_trigger": str(
            (commercial_close_packet.get("one_page_order") or {}).get("first_invoice_trigger")
            or next_paid.get("acceptance")
            or "Buyer names paid owner, scope, date, proof recipient and accepted gates."
        ),
        "route_chain": route_chain,
        "timeline": timeline,
        "gates": gates,
        "role_packets": role_packets,
        "forwarding_kit": forwarding_kit,
        "proof_files": files,
        "outcome": {
            "route": "/outcome-ledger",
            "acceptance_rollup_ready": bool(acceptance_rollup.get("ready_to_claim")),
            "acceptance_items": _int(acceptance_rollup.get("items")) if isinstance(acceptance_rollup.get("items"), int) else len(rollup_items),
            "governance_refresh_ready": bool(governance_refresh.get("ready")),
            "next_window": str(acceptance_rollup.get("next_window") or "Day 7"),
            "owner_line": str(acceptance_rollup.get("owner_line") or "Day 7/30 acceptance must be refreshed before claiming rollout value."),
        },
        "blockers": blockers,
        "why": "This handoff prevents the post-demo drop: buyer receives the paid start, owner, proof gates, Day 7 proof and Day 30 acceptance path in one artifact.",
    }


def post_demo_activation_handoff_markdown(handoff: dict[str, Any]) -> str:
    next_paid = handoff.get("next_paid_step") or {}
    outcome = handoff.get("outcome") or {}
    lines = [
        "# Post-Demo Activation Handoff",
        "",
        f"Status: **{handoff.get('status', 'unknown')}**",
        f"Ready to start: **{bool(handoff.get('ready_to_start'))}**",
        f"Route: `{handoff.get('route', '/pilot-launchpad')}`",
        "",
        f"## {handoff.get('headline', 'Activation handoff')}",
        "",
        f"- Next paid step: **{next_paid.get('label', 'n/a')}** (`{next_paid.get('route', '/pilot-launchpad')}`)",
        f"- Owner: {next_paid.get('owner', '')}",
        f"- Acceptance: {next_paid.get('acceptance', '')}",
        f"- Invoice trigger: {handoff.get('invoice_trigger', '')}",
        "",
        "## Route Chain",
        "",
    ]
    lines.extend(f"- `{route}`" for route in handoff.get("route_chain", []))
    lines.extend(["", "## Timeline", ""])
    for item in handoff.get("timeline", []):
        lines.append(
            f"- **{item.get('window', '')}** / {item.get('owner', '')} / {item.get('status', '')}: "
            f"{item.get('action', '')} (`{item.get('route', '/pilot-launchpad')}`), proof `{item.get('proof_file', '')}`. "
            f"Exit: {item.get('exit', '')}"
        )
    lines.extend(["", "## Gates", ""])
    for item in handoff.get("gates", []):
        lines.append(
            f"- **{item.get('status', '')}** / `{item.get('route', '/killer-demo')}`: "
            f"{item.get('gate', '')} - {item.get('evidence', '')}"
        )
    files = handoff.get("proof_files") or []
    if files:
        lines.extend(["", "## Proof Files", ""])
        lines.extend(f"- `{file}`" for file in files)
    forwarding = handoff.get("forwarding_kit") or {}
    forwarding_packets = forwarding.get("packets") or []
    if forwarding_packets:
        lines.extend(["", "## Forwarding Kit", ""])
        lines.append(f"- Source: **{forwarding.get('source', 'Evidence Bundle')}**")
        for item in forwarding_packets:
            lines.append(
                f"- **{item.get('role', '')}**: `{item.get('filename', '')}` / "
                f"{item.get('forwarding_subject', '')}"
            )
    blockers = handoff.get("blockers") or []
    if blockers:
        lines.extend(["", "## Scope First Blockers", ""])
        for item in blockers:
            lines.append(f"- **{item.get('severity', '')}** / `{item.get('route', '/killer-demo')}`: {item.get('action', '')}")
    lines.extend(
        [
            "",
            "## Outcome Refresh",
            "",
            f"- Acceptance ready: **{bool(outcome.get('acceptance_rollup_ready'))}**",
            f"- Governance refresh ready: **{bool(outcome.get('governance_refresh_ready'))}**",
            f"- Next window: **{outcome.get('next_window', 'Day 7')}**",
            f"- Owner line: {outcome.get('owner_line', '')}",
            "",
            "## Why",
            "",
            str(handoff.get("why") or ""),
        ]
    )
    return "\n".join(lines)


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 1C Rentgen Killer Demo Path",
        "",
        f"Client: **{report['client']['name']}**",
        f"Status: **{report['decision']['status'].upper()}** / score **{report['decision']['score']}**",
        f"Primary route: **{report['primary_route']['label']}** (`{report['primary_route']['route']}`)",
        "",
    ]
    opening = report.get("opening_brief") or {}
    if opening:
        lines.extend(["## Opening Brief", ""])
        lines.append(f"- **{opening.get('headline', 'Opening brief')}**")
        lines.append(f"- {opening.get('one_sentence', '')}")
        for item in opening.get("first_30_seconds", []):
            lines.append(f"- {item}")
        first_click = opening.get("first_click") or {}
        first_click_label = first_click.get("label", "primary route")
        first_click_route = first_click.get("route", "/killer-demo")
        lines.append(f"- First click: **{first_click_label}** (`{first_click_route}`)")
        lines.append(f"- Success signal: {opening.get('success_signal', '')}")
        lines.extend(["", "## Killer Stages", ""])
    else:
        lines.extend(["## Killer Stages", ""])
    for item in report["killer_stages"]:
        lines.append(f"- **{item['title']}** ({item['minutes']} min, `{item['route']}`): {item['spark']}")
    lines.extend(["", "## Demo Modes", ""])
    for item in report["demo_modes"]:
        lines.append(f"- **{item['title']}** ({item['minutes']} min): {item['close']}")
    lines.extend(["", "## Proof Moments", ""])
    for item in report["proof_moments"]:
        lines.append(f"- **{item['title']}**: {item['signal']} (`{item['route']}`)")
    packet = report.get("proof_packet") or {}
    lines.extend(["", "## Proof Packet", ""])
    lines.append(f"- Bundle: `{packet.get('bundle_id') or 'demo-checklist'}`")
    if packet.get("bundle_sha256"):
        lines.append(f"- Bundle SHA-256: `{packet['bundle_sha256']}`")
    room_map = packet.get("room_map") or {}
    if room_map:
        lines.append(
            f"- Buyer room map: `{room_map.get('filename', 'buyer-brief.md')}` "
            f"({'ready' if room_map.get('ready') else 'not ready'}) - {room_map.get('why', '')}"
        )
        lines.append(
            f"- Buyer room plan: `{room_map.get('plan_filename', 'buyer-room-plan.md')}` "
            f"({'ready' if room_map.get('plan_ready') else 'not ready'})"
        )
        lines.append(
            f"- Open-first path: `{room_map.get('open_first_path_filename', 'open-first-path.md')}` "
            f"({'ready' if room_map.get('open_first_path_ready') else 'not ready'})"
        )
    lines.extend(
        open_first_path_markdown_lines(
            packet.get("open_first_path") or [],
            heading="### Open-First Path",
            default_route="/killer-demo",
        )
    )
    archive = packet.get("archive") or {}
    if archive:
        lines.append(f"- ZIP archive: `{archive.get('filename', 'evidence-archive.zip')}` via `{archive.get('route', '/evidence-bundle')}`")
        lines.append(f"- Archive SHA header: `{archive.get('sha256_header', 'X-Archive-Sha256')}`")
    killer_archive = packet.get("killer_archive") or {}
    if killer_archive:
        lines.append(
            f"- Killer Demo ZIP: `{killer_archive.get('filename', 'killer-demo-archive.zip')}` "
            f"via `{killer_archive.get('endpoint', '/api/v1/killer-demo/archive')}`"
        )
        lines.append(
            f"- Killer archive open-first: `{killer_archive.get('open_first', 'OPEN_FIRST_KILLER_DEMO.md')}`; "
            f"manifest `{killer_archive.get('manifest', 'killer-demo-manifest.json')}`; "
            f"role packets {', '.join(str(item) for item in killer_archive.get('role_packets', []))}"
        )
    verification_packet = packet.get("verification_packet") or {}
    if verification_packet:
        lines.append(
            f"- Verification Packet ZIP: `{verification_packet.get('filename', ARCHIVE_VERIFICATION_PACKET_ZIP)}` "
            f"via `{verification_packet.get('endpoint', ARCHIVE_VERIFICATION_PACKET_ENDPOINT)}`"
        )
        lines.append(
            f"- Verification hash header: `{verification_packet.get('sha256_header', ARCHIVE_VERIFICATION_PACKET_HASH_HEADER)}`; "
            f"open-first `{verification_packet.get('open_first', ARCHIVE_VERIFICATION_PACKET_OPEN_FIRST)}`"
        )
    role_rollup = packet.get("role_packet_rollup") or {}
    if role_rollup:
        lines.append(
            f"- Role packet coverage: **{role_rollup.get('status', 'unknown')}**; "
            f"ready **{role_rollup.get('ready', 0)} / {role_rollup.get('total', 0)}**, "
            f"partial **{role_rollup.get('partial', 0)}**, missing files **{role_rollup.get('missing_files', 0)}**"
        )
        missing_names = role_rollup.get("missing_file_names") or []
        if missing_names:
            lines.append(f"- Role packet missing files: {', '.join(str(item) for item in missing_names[:10])}")
    procurement = packet.get("procurement_handoff") or {}
    if procurement:
        covered = procurement.get("covered_by_current_demo") or []
        lines.append(
            f"- Procurement handoff: **{procurement.get('status', 'unknown')}**; "
            f"missing **{procurement.get('missing_files', 0)}**, blockers **{procurement.get('blockers', 0)}**, "
            f"risk reviews **{procurement.get('risk_review_items', 0)}**, recipients **{procurement.get('recipients', 0)}**"
        )
        lines.append(
            f"- Procurement file: `{procurement.get('first_file', 'procurement-handoff.md')}`; "
            f"open first `{procurement.get('open_first_file', 'OPEN_FIRST.md')}`; "
            f"endpoint `{procurement.get('endpoint', '/api/v1/evidence-bundle/archive')}`"
        )
        open_order = procurement.get("open_order") or []
        if open_order:
            lines.append(f"- Procurement acceptance: {procurement.get('acceptance', '')}")
            for item in open_order:
                header = f" / `{item.get('hash_header')}`" if item.get("hash_header") else ""
                lines.append(
                    f"- **{item.get('step')}. {item.get('label', '')}** (`{item.get('route', '/killer-demo')}`): "
                    f"`{item.get('file', '')}`{header} - {item.get('check', '')}"
                )
        if covered:
            lines.append(f"- Covered by current demo export: {', '.join(str(item) for item in covered)}")
    for item in packet.get("handoff", []):
        lines.append(f"- **{item['recipient']}**: {item['why']} (`{item['route']}`)")
    close_packet = report.get("commercial_close_packet") or {}
    if close_packet:
        order = close_packet.get("one_page_order") or {}
        lines.extend(["", "## Commercial Close Packet", ""])
        lines.append(f"- Ready to close: **{bool(close_packet.get('ready_to_close'))}**")
        lines.append(f"- Ready to ask with proof: **{bool(close_packet.get('ready_to_ask'))}**")
        lines.append(f"- Mode: **{close_packet.get('close_mode', 'unknown')}**")
        lines.append(f"- Primary ask: {close_packet.get('primary_ask', '')}")
        lines.append(f"- Recommended purchase: **{order.get('recommended_purchase', 'n/a')}** (`{order.get('route', '/commercial-offer-studio')}`)")
        lines.append(f"- Value anchor: {order.get('value_anchor', 'Business Case')}; AI rent baseline: {order.get('ai_rent_baseline', 'n/a')}")
        lines.append(
            f"- Three-year AI rent: {order.get('three_year_ai_rent', 'n/a')}; "
            f"local license anchor: {order.get('local_license_anchor', 'n/a')}; "
            f"break-even: {order.get('break_even', 'n/a')}"
        )
        for item in close_packet.get("checkout", []):
            lines.append(f"- Checkout `{item.get('route', '/killer-demo')}`: {item.get('gate', '')} - {item.get('evidence', '')}")
    receipt = report.get("meeting_close_receipt") or {}
    if receipt:
        proof = receipt.get("proof_packet") or {}
        next_paid = receipt.get("next_paid_step") or {}
        committee_receipt = receipt.get("committee") or {}
        lines.extend(["", "## Meeting Close Receipt", ""])
        lines.append(f"- File: `{receipt.get('filename', MEETING_CLOSE_RECEIPT_MD)}` / `{receipt.get('json_filename', MEETING_CLOSE_RECEIPT_JSON)}`")
        lines.append(f"- Status: **{receipt.get('status', 'unknown')}**; ready to send **{bool(receipt.get('ready_to_send'))}**")
        lines.append(f"- Headline: {receipt.get('headline', '')}")
        lines.append(f"- Next paid step: **{next_paid.get('label', 'n/a')}** (`{next_paid.get('route', '/killer-demo')}`)")
        lines.append(
            f"- Archive: `{proof.get('archive_filename', 'killer-demo-archive.zip')}`; "
            f"hash header `{proof.get('archive_hash_header', KILLER_DEMO_ARCHIVE_HASH_HEADER)}`"
        )
        lines.append(
            f"- Verification packet: `{proof.get('verification_packet', ARCHIVE_VERIFICATION_PACKET_ZIP)}`; "
            f"hash header `{proof.get('verification_packet_hash_header', ARCHIVE_VERIFICATION_PACKET_HASH_HEADER)}`"
        )
        lines.append(
            f"- Committee accepted/blocked: **{committee_receipt.get('accepted_roles', 0)} / "
            f"{committee_receipt.get('blocked_roles', 0)}**; final question: {committee_receipt.get('final_question', '')}"
        )
    activation_handoff = report.get("post_demo_activation_handoff") or {}
    if activation_handoff:
        next_paid = activation_handoff.get("next_paid_step") or {}
        outcome = activation_handoff.get("outcome") or {}
        lines.extend(["", "## Post-Demo Activation Handoff", ""])
        lines.append(
            f"- File: `{activation_handoff.get('filename', POST_DEMO_ACTIVATION_MD)}` / "
            f"`{activation_handoff.get('json_filename', POST_DEMO_ACTIVATION_JSON)}`"
        )
        lines.append(f"- Status: **{activation_handoff.get('status', 'unknown')}**; ready to start **{bool(activation_handoff.get('ready_to_start'))}**")
        lines.append(f"- Next paid step: **{next_paid.get('label', 'n/a')}** (`{next_paid.get('route', '/pilot-launchpad')}`)")
        lines.append(f"- Invoice trigger: {activation_handoff.get('invoice_trigger', '')}")
        lines.append(
            f"- Outcome next window: **{outcome.get('next_window', 'Day 7')}**; "
            f"governance refresh ready **{bool(outcome.get('governance_refresh_ready'))}**"
        )
        for item in activation_handoff.get("timeline", [])[:4]:
            lines.append(
                f"- {item.get('window', '')} / {item.get('owner', '')}: "
                f"{item.get('action', '')} (`{item.get('route', '/pilot-launchpad')}`)"
            )
    readiness = report.get("deal_readiness") or {}
    lines.extend(["", "## Deal Readiness", ""])
    lines.append(f"- Status: **{str(readiness.get('status') or 'unknown').upper()}** / score **{readiness.get('score', 0)}**")
    step = readiness.get("next_paid_step") or {}
    lines.append(f"- Next paid step: **{step.get('label', 'n/a')}** (`{step.get('route', '/killer-demo')}`)")
    for item in readiness.get("blockers", []):
        lines.append(f"- Blocker `{item['route']}`: {item['title']} Action: {item['action']}")
    asset_case = readiness.get("local_asset_case") or {}
    lines.extend(["", "## Local Asset Case", ""])
    lines.append(f"- **{asset_case.get('headline', 'Local 1C evidence product')}**")
    lines.append(f"- Value anchor: {asset_case.get('value_anchor', 'Business Case')}")
    lines.append(f"- Three-year AI rent: {asset_case.get('three_year_ai_rent', 'n/a')}")
    lines.append(f"- Local license anchor: {asset_case.get('local_license_anchor', 'n/a')}")
    lines.append(f"- Break-even: {asset_case.get('break_even', 'n/a')}")
    for item in asset_case.get("why_it_is_asset", []):
        lines.append(f"- {item}")
    lines.extend(["", "## Customer Can Repeat", ""])
    for item in readiness.get("customer_can_repeat", []):
        lines.append(f"- {item}")
    lines.extend(["", "## Role Acceptance", ""])
    for item in readiness.get("role_acceptance", []):
        lines.append(f"- **{item['role']}** ({item['status']}, `{item['route']}`): {item['must_hear']}")
    committee = readiness.get("committee_close_board") or {}
    if committee:
        lines.extend(["", "## Committee Close Board", ""])
        lines.append(f"- Status: **{committee.get('status', 'unknown')}**")
        lines.append(f"- Accepted roles: **{committee.get('accepted_roles', 0)} / {committee.get('total_roles', 0)}**")
        lines.append(f"- Blocked roles: **{committee.get('blocked_roles', 0)}**")
        lines.append(f"- Final question: {committee.get('final_question', '')}")
        for item in committee.get("roles", []):
            lines.append(
                f"- **{item.get('role', '')}** ({item.get('status', '')}, `{item.get('route', '/killer-demo')}`): "
                f"send {', '.join(item.get('send', []))}; {item.get('remaining_question', '')}"
            )
    router = report.get("objection_router") or {}
    if router:
        lines.extend(["", "## Objection Router", ""])
        lines.append(f"- Status: **{router.get('status', 'unknown')}**")
        lines.append(f"- Ready/watch/blocked: **{router.get('ready_items', 0)}** / **{router.get('watch_items', 0)}** / **{router.get('blocked_items', 0)}**")
        lines.append(f"- Presenter line: {router.get('presenter_line', '')}")
        primary = router.get("primary_objection") or {}
        if primary:
            lines.append(f"- Primary objection: **{primary.get('objection', '')}** (`{primary.get('route', '/killer-demo')}`)")
        for item in router.get("items", []):
            lines.append(
                f"- **{item.get('audience', '')}** / {item.get('status', '')} / `{item.get('route', '/killer-demo')}`: "
                f"{item.get('objection', '')} Answer: {item.get('answer', '')}"
            )
    lines.extend(["", "## Caveats", ""])
    lines.extend(f"- {item}" for item in report["caveats"])
    return "\n".join(lines)


def build_killer_demo_path(
    *,
    launch_room: dict[str, Any],
    demo_command_center: dict[str, Any],
    test_factory: dict[str, Any],
    buyer_concierge: dict[str, Any],
    scenario_hub: dict[str, Any],
    enterprise_trust_center: dict[str, Any],
    commercial_offer_studio: dict[str, Any],
    board_pack: dict[str, Any],
    outcome_ledger: dict[str, Any],
    client_name: str = "Demo client",
    config_path: str | None = None,
    target_platform_version: str | None = None,
    evidence_bundle: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the buyer-ready killer demo route with proof, fallback and close scripts."""

    score = _weighted_score(
        [
            (launch_room, 0.18),
            (demo_command_center, 0.16),
            (test_factory, 0.14),
            (enterprise_trust_center, 0.18),
            (commercial_offer_studio, 0.12),
            (board_pack, 0.12),
            (outcome_ledger, 0.10),
        ]
    )
    status = _decision_status(
        launch_room,
        demo_command_center,
        test_factory,
        enterprise_trust_center,
        board_pack,
        outcome_ledger,
        score=score,
    )
    primary_route = _primary_route(
        launch_room=launch_room,
        enterprise_trust_center=enterprise_trust_center,
        test_factory=test_factory,
        board_pack=board_pack,
        outcome_ledger=outcome_ledger,
    )
    stages = _killer_stages(
        launch_room=launch_room,
        demo_command_center=demo_command_center,
        test_factory=test_factory,
        enterprise_trust_center=enterprise_trust_center,
        board_pack=board_pack,
        outcome_ledger=outcome_ledger,
    )
    demo_modes = _demo_modes(stages, board_pack)
    role_sparks = _role_sparks(
        buyer_concierge=buyer_concierge,
        test_factory=test_factory,
        board_pack=board_pack,
        outcome_ledger=outcome_ledger,
    )
    proof_moments = _proof_moments(
        test_factory=test_factory,
        enterprise_trust_center=enterprise_trust_center,
        commercial_offer_studio=commercial_offer_studio,
        outcome_ledger=outcome_ledger,
    )
    close_scripts = _close_scripts(board_pack, outcome_ledger)
    exports = _exports()
    proof_routes = sorted(
        {primary_route["route"]}
        | {item["route"] for item in stages}
        | {step["route"] for mode in demo_modes for step in mode["steps"]}
        | {item["first_route"] for item in role_sparks}
        | {item["route"] for item in proof_moments}
        | {item["route"] for item in exports}
        | _commercial_close_routes(commercial_offer_studio)
        | {"/approvals", "/audit"}
    )
    proof_packet = _proof_packet(
        evidence_bundle=evidence_bundle,
        exports=exports,
        proof_routes=proof_routes,
    )
    proof_packet["role_packet_rollup"] = _role_packet_rollup(list(proof_packet.get("handoff") or []))
    commercial_close_packet = _commercial_close_packet(
        commercial_offer_studio=commercial_offer_studio,
        proof_packet=proof_packet,
    )
    deal_readiness = _deal_readiness(
        score=score,
        launch_room=launch_room,
        test_factory=test_factory,
        enterprise_trust_center=enterprise_trust_center,
        commercial_offer_studio=commercial_offer_studio,
        board_pack=board_pack,
        outcome_ledger=outcome_ledger,
        role_sparks=role_sparks,
        proof_packet=proof_packet,
    )
    opening_brief = _opening_brief(
        primary_route=primary_route,
        deal_readiness=deal_readiness,
        role_sparks=role_sparks,
        proof_packet=proof_packet,
    )
    objection_router = _objection_router(
        launch_room=launch_room,
        test_factory=test_factory,
        enterprise_trust_center=enterprise_trust_center,
        commercial_offer_studio=commercial_offer_studio,
        board_pack=board_pack,
        outcome_ledger=outcome_ledger,
        proof_packet=proof_packet,
        deal_readiness={**deal_readiness, "commercial_close_packet": commercial_close_packet},
    )
    proof_routes = sorted(set(proof_routes) | set(objection_router["proof_routes"]))
    decision = {
        "status": status,
        "score": score,
        "headline": (
            "Killer Demo Path is ready: one route can spark developer, architect, security, director and sponsor interest."
            if status == "ready"
            else "Killer Demo Path is usable, but risk/caveat stages should be shown before asking for approval."
        ),
    }
    meeting_close_receipt = _meeting_close_receipt(
        client_name=client_name,
        decision=decision,
        proof_packet=proof_packet,
        commercial_close_packet=commercial_close_packet,
        deal_readiness=deal_readiness,
        objection_router=objection_router,
    )
    post_demo_activation_handoff = _post_demo_activation_handoff(
        receipt=meeting_close_receipt,
        proof_packet=proof_packet,
        commercial_close_packet=commercial_close_packet,
        outcome_ledger=outcome_ledger,
    )
    meeting_close_receipt["activation_handoff"] = {
        "filename": POST_DEMO_ACTIVATION_MD,
        "json_filename": POST_DEMO_ACTIVATION_JSON,
        "status": str(post_demo_activation_handoff.get("status") or ""),
        "route": str(post_demo_activation_handoff.get("route") or "/pilot-launchpad"),
        "line": str(post_demo_activation_handoff.get("activation_line") or ""),
    }
    meeting_close_receipt["send_files"] = _unique_strings(
        [
            *[str(file) for file in meeting_close_receipt.get("send_files", []) if file],
            POST_DEMO_ACTIVATION_MD,
            POST_DEMO_ACTIVATION_JSON,
        ]
    )
    proof_packet["close_receipt"] = {
        "ready": bool(meeting_close_receipt["ready_to_send"]),
        "status": str(meeting_close_receipt["status"]),
        "route": "/killer-demo",
        "filename": MEETING_CLOSE_RECEIPT_MD,
        "json_filename": MEETING_CLOSE_RECEIPT_JSON,
        "next_paid_step": str((meeting_close_receipt.get("next_paid_step") or {}).get("label") or ""),
        "why": str(meeting_close_receipt.get("why") or ""),
    }
    proof_packet["activation_handoff"] = {
        "ready": bool(post_demo_activation_handoff["ready_to_start"]),
        "status": str(post_demo_activation_handoff["status"]),
        "route": str(post_demo_activation_handoff["route"]),
        "filename": POST_DEMO_ACTIVATION_MD,
        "json_filename": POST_DEMO_ACTIVATION_JSON,
        "next_window": str((post_demo_activation_handoff.get("outcome") or {}).get("next_window") or "Day 7"),
        "why": str(post_demo_activation_handoff.get("why") or ""),
    }
    report: dict[str, Any] = {
        "generated_at": _now(),
        "client": {
            "name": client_name,
            "config_path": config_path or "",
            "target_platform_version": target_platform_version or "",
        },
        "decision": decision,
        "summary": {
            "stages": len(stages),
            "demo_modes": len(demo_modes),
            "role_sparks": len(role_sparks),
            "proof_moments": len(proof_moments),
            "close_scripts": len(close_scripts),
            "proof_routes": len(proof_routes),
            "proof_files": proof_packet["file_count"],
            "open_first_steps": len(proof_packet.get("open_first_path") or []),
            "role_packets_ready": proof_packet["role_packet_rollup"]["ready"],
            "role_packets_partial": proof_packet["role_packet_rollup"]["partial"],
            "role_packets_missing": proof_packet["role_packet_rollup"]["missing"],
            "role_packet_missing_files": proof_packet["role_packet_rollup"]["missing_files"],
            "deal_readiness_score": deal_readiness["score"],
            "committee_roles": deal_readiness["committee_close_board"]["total_roles"],
            "committee_blocked_roles": deal_readiness["committee_close_board"]["blocked_roles"],
            "opening_roles": len(opening_brief["role_entries"]),
            "objection_items": len(objection_router["items"]),
            "objection_watch": objection_router["watch_items"],
            "objection_blocked": objection_router["blocked_items"],
            "close_ready": bool(commercial_close_packet["ready_to_close"]),
            "close_receipt_ready": bool(meeting_close_receipt["ready_to_send"]),
            "activation_handoff_ready": bool(post_demo_activation_handoff["ready_to_start"]),
            "checkout_gates": len(commercial_close_packet["checkout"]),
            "total_minutes": round(sum(float(item["minutes"]) for item in stages), 1),
            "test_gaps": _summary(test_factory).get("gaps", 0),
            "trust_status": _status(enterprise_trust_center),
        },
        "primary_route": primary_route,
        "opening_brief": opening_brief,
        "killer_stages": stages,
        "demo_modes": demo_modes,
        "role_sparks": role_sparks,
        "proof_moments": proof_moments,
        "close_scripts": close_scripts,
        "exports": exports,
        "proof_packet": proof_packet,
        "commercial_close_packet": commercial_close_packet,
        "deal_readiness": deal_readiness,
        "objection_router": objection_router,
        "meeting_close_receipt": meeting_close_receipt,
        "post_demo_activation_handoff": post_demo_activation_handoff,
        "proof_routes": proof_routes,
        "source_signals": {
            "launch_room_status": _status(launch_room),
            "demo_command_status": _status(demo_command_center),
            "test_factory_status": _status(test_factory),
            "scenario_hub_status": _status(scenario_hub),
            "trust_status": _status(enterprise_trust_center),
            "board_status": _status(board_pack),
            "outcome_status": _status(outcome_ledger),
            "offer_status": _status(commercial_offer_studio),
        },
        "caveats": [
            "Killer Demo Path is a presentation route over implemented proof surfaces; deep reports remain the source of details.",
            "If Trust Center or Test Factory is risky, lead with that risk instead of hiding it until the close.",
            "Customer-specific acceptance data is required before generated tests can become final release gates.",
        ],
        "download_name": "rentgen-killer-demo-path.md",
    }
    report["markdown"] = _markdown(report)
    return report
