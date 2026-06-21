"""Board pack that turns Rentgen proof into a board-level buying decision."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.services.rentgen.open_first_path import (
    OPEN_FIRST_PATH_FILE,
    build_open_first_path,
    open_first_path_markdown_lines,
)


ARCHIVE_ACCEPTANCE_RECEIPT_MD = "archive-acceptance-receipt.md"


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


def _offer_by_id(commercial_offer_studio: dict[str, Any], offer_id: str) -> dict[str, Any]:
    for offer in commercial_offer_studio.get("offers", []):
        if offer.get("id") == offer_id:
            return offer
    return {}


def _ensure_archive_receipt_requirement(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if any(str(item.get("artifact") or "") == "Archive Acceptance Receipt" for item in items):
        return items
    return [
        *items,
        {
            "artifact": "Archive Acceptance Receipt",
            "route": "/evidence-bundle",
            "why": f"`{ARCHIVE_ACCEPTANCE_RECEIPT_MD}` records Evidence Bundle and Killer Demo archive hashes.",
        },
    ]


def _recommended_offer(
    *,
    commercial_offer_studio: dict[str, Any],
    enterprise_trust_center: dict[str, Any],
    pilot_launchpad: dict[str, Any],
) -> dict[str, Any]:
    if _status(enterprise_trust_center) == "risk":
        preferred = "platform-trust-pack"
    elif _score(commercial_offer_studio) >= 82 and _score(pilot_launchpad) >= 78:
        preferred = "enterprise-local-license"
    elif _score(pilot_launchpad) >= 72:
        preferred = "local-license-pilot"
    else:
        preferred = "proof-sprint"
    offer = _offer_by_id(commercial_offer_studio, preferred)
    if offer:
        return offer
    offers = commercial_offer_studio.get("offers") or []
    return dict(offers[0]) if offers else {}


def _value_anchor(
    *,
    business_case: dict[str, Any],
    commercial_offer_studio: dict[str, Any],
) -> tuple[int, str, int]:
    commercial_summary = commercial_offer_studio.get("summary") or {}
    business_summary = business_case.get("summary") or {}
    assumptions = business_case.get("assumptions") or {}
    value = _int(commercial_summary.get("first_year_visible_value") or business_summary.get("first_year_visible_value"))
    currency = str(commercial_summary.get("currency") or assumptions.get("currency") or "RUB")
    ai_year = _int(business_summary.get("ai_subscription_year"))
    return value, currency, ai_year


def _subscription_escape(
    *,
    business_case: dict[str, Any],
    commercial_offer_studio: dict[str, Any],
    value: int,
    currency: str,
    ai_year: int,
) -> dict[str, Any]:
    dossier_escape = ((commercial_offer_studio.get("procurement_dossier") or {}).get("subscription_escape") or {})
    close_order = ((commercial_offer_studio.get("close_packet") or {}).get("one_page_order") or {})
    business_escape = business_case.get("subscription_escape_plan") or {}
    return {
        "annual_ai_rent": str(dossier_escape.get("annual_ai_rent") or close_order.get("ai_rent_baseline") or (_money(ai_year, currency) if ai_year else "not provided")),
        "three_year_ai_rent": str(dossier_escape.get("three_year_ai_rent") or close_order.get("three_year_ai_rent") or (_money(ai_year * 3, currency) if ai_year else "not provided")),
        "local_value_anchor": str(dossier_escape.get("local_value_anchor") or close_order.get("value_anchor") or _money(value, currency)),
        "local_license_anchor": str(dossier_escape.get("local_license_anchor") or close_order.get("local_license_anchor") or (_money(_int(business_escape.get("local_license_anchor")), currency) if business_escape.get("local_license_anchor") else "not provided")),
        "break_even": str(close_order.get("break_even") or (f"{_int(dossier_escape.get('break_even_months') or business_escape.get('break_even_months'))} months by visible value")),
        "decision_line": str(dossier_escape.get("decision_line") or business_escape.get("decision_line") or "Core product value stays local; AI credits remain optional."),
    }


def _board_snapshot(
    *,
    business_case: dict[str, Any],
    buyer_concierge: dict[str, Any],
    commercial_offer_studio: dict[str, Any],
    enterprise_trust_center: dict[str, Any],
    recommended_offer: dict[str, Any],
) -> dict[str, Any]:
    value, currency, ai_year = _value_anchor(
        business_case=business_case,
        commercial_offer_studio=commercial_offer_studio,
    )
    escape = _subscription_escape(
        business_case=business_case,
        commercial_offer_studio=commercial_offer_studio,
        value=value,
        currency=currency,
        ai_year=ai_year,
    )
    trust_summary = enterprise_trust_center.get("summary") or {}
    return {
        "one_line": "Buy a local 1C evidence product that starts from role or pain and ends with trusted, hashed decision artifacts.",
        "why_now": "The product already connects developer proof, platform/trust risk, commercial packages and portable evidence.",
        "not_generic_ai": (
            "Core value is local 1C analysis, governance and proof packaging; optional AI credits are separated from the license story."
        ),
        "value_anchor": escape["local_value_anchor"],
        "ai_rent_baseline": escape["annual_ai_rent"],
        "three_year_ai_rent": escape["three_year_ai_rent"],
        "local_license_anchor": escape["local_license_anchor"],
        "break_even": escape["break_even"],
        "subscription_escape_line": escape["decision_line"],
        "recommended_motion": str(recommended_offer.get("title") or "Select proof sprint"),
        "commercial_frame": str(recommended_offer.get("commercial_frame") or "fixed next step"),
        "default_route": str((buyer_concierge.get("default_next_action") or {}).get("route") or "/buyer-concierge"),
        "trust_position": (
            f"{_status(enterprise_trust_center)} / {_score(enterprise_trust_center)}; "
            f"failed controls: {_int(trust_summary.get('failed_controls'))}"
        ),
    }


def _decision_brief(
    *,
    board_snapshot: dict[str, Any],
    recommended_offer: dict[str, Any],
    commercial_offer_studio: dict[str, Any],
    enterprise_trust_center: dict[str, Any],
) -> list[dict[str, str]]:
    dossier = commercial_offer_studio.get("procurement_dossier") or {}
    procurement_pack = dossier.get("procurement_pack") or []
    procurement_answer = (
        f"{len(procurement_pack)} procurement artifacts are prepared: finance, security, architecture, sponsor and evidence."
        if procurement_pack
        else "Offer Studio keeps finance, security, architecture, sponsor and evidence artifacts in the buying path."
    )
    close_packet = commercial_offer_studio.get("close_packet") or {}
    checkout = list(close_packet.get("checkout") or [])
    checkout_answer = (
        f"{len(checkout)} checkout gates must be visible: approval, audit, evidence archive and trust caveats."
        if checkout
        else "Approval, audit, evidence archive and trust caveats must be visible before signature."
    )
    return [
        {
            "question": "What are we buying?",
            "answer": board_snapshot["one_line"],
            "owner": "director / CIO",
            "route": "/buyer-concierge",
        },
        {
            "question": "Why not just keep paying for AI subscriptions?",
            "answer": board_snapshot["not_generic_ai"],
            "owner": "finance",
            "route": "/business-case",
        },
        {
            "question": "What is the money anchor?",
            "answer": (
                f"First-year visible value is {board_snapshot['value_anchor']}; "
                f"AI rent baseline is {board_snapshot['ai_rent_baseline']}; "
                f"three-year AI rent is {board_snapshot.get('three_year_ai_rent', 'n/a')}; "
                f"local license anchor is {board_snapshot.get('local_license_anchor', 'n/a')}."
            ),
            "owner": "finance / director",
            "route": "/business-case",
        },
        {
            "question": "What should we approve now?",
            "answer": (
                f"{recommended_offer.get('title') or 'Proof sprint'}: "
                f"{recommended_offer.get('commercial_frame') or 'fixed next step'}."
            ),
            "owner": "director / vendor owner",
            "route": str(recommended_offer.get("route") or "/commercial-offer-studio"),
        },
        {
            "question": "What does procurement need?",
            "answer": procurement_answer,
            "owner": "procurement / finance / security",
            "route": "/commercial-offer-studio",
        },
        {
            "question": "What must pass before signature?",
            "answer": checkout_answer,
            "owner": "procurement / security / sponsor",
            "route": "/commercial-offer-studio",
        },
        {
            "question": "Can security and architecture live with it?",
            "answer": (
                f"Trust Center is {_status(enterprise_trust_center)} / {_score(enterprise_trust_center)} "
                "and keeps locality, SBOM/offline, rights and platform caveats visible."
            ),
            "owner": "security / architect",
            "route": "/enterprise-trust-center",
        },
        {
            "question": "How do we prove the meeting output later?",
            "answer": "Board Pack, Offer Studio, Trust Center and Evidence Bundle produce portable markdown/JSON with hashes.",
            "owner": "seller / release board",
            "route": "/evidence-bundle",
        },
    ]


def _committee_map(
    *,
    buyer_concierge: dict[str, Any],
    commercial_offer_studio: dict[str, Any],
) -> list[dict[str, str]]:
    closers = {
        str(item.get("role")): item
        for item in commercial_offer_studio.get("stakeholder_closers", [])
        if item.get("role")
    }
    committee: list[dict[str, str]] = []
    for card in buyer_concierge.get("persona_cards", []):
        role = str(card.get("role") or "Stakeholder")
        closer = closers.get(role) or closers.get(role.split(" / ")[0]) or {}
        committee.append(
            {
                "role": role,
                "first_question": str(card.get("first_question") or ""),
                "must_believe": str(card.get("proof") or closer.get("buy_trigger") or ""),
                "buy_trigger": str(card.get("buy_trigger") or closer.get("buy_trigger") or ""),
                "proof_route": str(card.get("start_route") or closer.get("proof_route") or "/buyer-concierge"),
                "close_line": str(closer.get("close_line") or "Name the first proof they want repeated on customer data."),
            }
        )
    return committee


def _risk_to_decision(
    *,
    commercial_offer_studio: dict[str, Any],
    enterprise_trust_center: dict[str, Any],
) -> list[dict[str, str]]:
    risks: list[dict[str, str]] = []
    for item in enterprise_trust_center.get("risk_register", [])[:8]:
        risks.append(
            {
                "severity": str(item.get("severity") or "medium"),
                "owner": str(item.get("owner") or "lead"),
                "risk": str(item.get("risk") or "Trust risk"),
                "route": str(item.get("route") or "/enterprise-trust-center"),
                "decision": str(item.get("next_action") or "Assign owner before rollout."),
            }
        )
    for item in commercial_offer_studio.get("deal_risks", [])[:6]:
        risks.append(
            {
                "severity": "medium",
                "owner": "seller / buyer owner",
                "risk": str(item.get("risk") or "Deal risk"),
                "route": str(item.get("route") or "/commercial-offer-studio"),
                "decision": str(item.get("mitigation") or "Name mitigation in proposal."),
            }
        )
    close_packet = commercial_offer_studio.get("close_packet") or {}
    if close_packet and not bool(close_packet.get("ready_to_close")):
        mode = str(close_packet.get("close_mode") or "")
        risks.append(
            {
                "severity": "high" if mode == "sell_hardening_before_rollout" else "medium",
                "owner": "director / security / architect",
                "risk": "Board close is not ready without explicit scope.",
                "route": "/commercial-offer-studio",
                "decision": str(close_packet.get("primary_ask") or "Convert the blocker into paid proof, hardening or pilot scope."),
            }
        )
    if not risks:
        risks.append(
            {
                "severity": "low",
                "owner": "lead",
                "risk": "No blocking board risks were found in the supplied reports.",
                "route": "/board-pack",
                "decision": "Keep caveats visible and attach the Evidence Bundle.",
            }
        )
    order = {"high": 0, "medium": 1, "low": 2}
    return sorted(risks, key=lambda item: order.get(item["severity"], 9))[:10]


def _proof_packet(evidence_artifacts: list[dict[str, Any]]) -> list[dict[str, str]]:
    artifact_count = len(evidence_artifacts)
    return [
        {
            "title": "Buyer Brief markdown",
            "filename": "buyer-brief.md",
            "route": "/",
            "reason": "first-minute room map for committee roles, proof readiness and paid ask",
        },
        {
            "title": "Buyer Pulse markdown",
            "filename": "buyer-pulse.md",
            "route": "/",
            "reason": "fast buying pulse with purchase status and AI-rent assumptions",
        },
        {
            "title": "Board Pack markdown",
            "filename": "rentgen-board-pack.md",
            "route": "/board-pack",
            "reason": "one board-level decision brief",
        },
        {
            "title": "Buyer Concierge markdown",
            "filename": "rentgen-buyer-concierge.md",
            "route": "/buyer-concierge",
            "reason": "role and pain orientation",
        },
        {
            "title": "Commercial Offer Studio markdown",
            "filename": "rentgen-commercial-offer-studio.md",
            "route": "/commercial-offer-studio",
            "reason": "buyable package and price anchor",
        },
        {
            "title": "Enterprise Trust Center markdown",
            "filename": "rentgen-enterprise-trust-center.md",
            "route": "/enterprise-trust-center",
            "reason": "security, procurement and platform caveats",
        },
        {
            "title": "Business Case markdown",
            "filename": "rentgen-business-case.md",
            "route": "/business-case",
            "reason": "visible value and AI-rent comparison",
        },
        {
            "title": "Governance Proof markdown",
            "filename": "governance-proof.md",
            "route": "/approvals",
            "reason": "approval scope, constraints and decision records",
        },
        {
            "title": "Audit verification/export",
            "filename": "rentgen-audit-log.jsonl",
            "route": "/audit",
            "reason": "tamper-evident hash-chain proof",
        },
        {
            "title": "Evidence Bundle manifest",
            "filename": "evidence-bundle-manifest.json",
            "route": "/evidence-bundle",
            "reason": f"hashes for {artifact_count or 'generated'} artifacts",
        },
    ]


def _board_room_bridge(
    *,
    buyer_brief: dict[str, Any] | None,
    board_snapshot: dict[str, Any],
    board_close_packet: dict[str, Any],
    committee_map: list[dict[str, str]],
) -> dict[str, Any]:
    brief = buyer_brief or {}
    order = board_close_packet.get("one_page_order") or {}
    primary = dict(brief.get("primary_motion") or {})
    if not primary:
        primary = {
            "label": str(order.get("recommended_purchase") or board_snapshot.get("recommended_motion") or "Approve paid next step"),
            "route": str(order.get("route") or "/commercial-offer-studio"),
            "status": "ready" if board_close_packet.get("ready_to_close") else "watch",
            "ask": str(board_close_packet.get("primary_ask") or "Approve the selected paid next step with proof attached."),
            "reason": str(board_snapshot.get("why_now") or "Board has value, trust and evidence in one packet."),
        }
    role_cards = list(brief.get("role_cards") or [])
    if not role_cards:
        role_cards = [
            {
                "role": item["role"].casefold(),
                "title": item["role"],
                "route": item["proof_route"],
                "status": "watch",
                "spark": item["must_believe"],
                "proof_file": "rentgen-board-pack.md",
            }
            for item in committee_map[:5]
        ]
    proof_readiness = list(brief.get("proof_readiness") or [])
    if not proof_readiness:
        proof_readiness = [
            {
                "id": "evidence-bundle",
                "title": "Forwardable evidence",
                "route": "/evidence-bundle",
                "status": "ready" if board_close_packet.get("ready_to_close") else "watch",
                "signal": "Board Pack, Offer Studio, Trust Center and governance proof can be forwarded.",
                "file": "OPEN_FIRST.md",
            },
            {
                "id": "governance",
                "title": "Approval gates",
                "route": "/approvals",
                "status": "ready",
                "signal": "Approval records and audit route are part of the checkout gates.",
                "file": "governance-proof.md",
            },
        ]
    meeting_flow = list(brief.get("meeting_flow") or [])
    if not meeting_flow:
        meeting_flow = [
            {"step": 1, "label": "Orient", "route": "/buyer-concierge", "line": "Name who is in the committee."},
            {"step": 2, "label": "Prove", "route": "/killer-demo", "line": "Show the proof packet and objections."},
            {"step": 3, "label": "Ask", "route": str(primary.get("route") or "/commercial-offer-studio"), "line": str(primary.get("ask") or "")},
            {"step": 4, "label": "Forward", "route": "/evidence-bundle", "line": "Attach buyer brief, board pack and proof archive."},
        ]
    open_first_path = build_open_first_path(
        existing_path=brief.get("open_first_path"),
        proof_readiness=proof_readiness,
        primary=primary,
        meeting_flow=meeting_flow,
        source="board-pack-fallback",
        orient_title="Board Pack",
        orient_route="/board-pack",
        orient_line="Name who is in the committee.",
        orient_status=str(primary.get("status") or ("ready" if board_close_packet.get("ready_to_close") else "watch")),
        prove_line="Show the proof packet and objections.",
        close_title=str(order.get("recommended_purchase") or board_snapshot.get("recommended_motion") or "Approve paid next step"),
        close_route=str(primary.get("route") or order.get("route") or "/commercial-offer-studio"),
        close_line=str(primary.get("ask") or board_close_packet.get("primary_ask") or "Approve the selected paid next step."),
        close_file="rentgen-board-pack.md",
        close_status=str(primary.get("status") or ("ready" if board_close_packet.get("ready_to_close") else "watch")),
        verify_line="Attach buyer brief, board pack and proof archive.",
    )
    routes = sorted(
        {
            str(primary.get("route") or "/commercial-offer-studio"),
            *[str(item.get("route") or "") for item in role_cards],
            *[str(item.get("route") or "") for item in proof_readiness],
            *[str(item.get("route") or "") for item in meeting_flow],
            *[str(item.get("route") or "") for item in open_first_path],
        }
        - {""}
    )
    fallback_score = 84 if board_close_packet.get("ready_to_close") else 70
    return {
        "status": str(brief.get("purchase_status") or primary.get("status") or ("ready" if board_close_packet.get("ready_to_close") else "watch")),
        "score": _int(brief.get("score"), fallback_score),
        "source": str(brief.get("source") or "board-pack-derived"),
        "room_line": str(
            brief.get("room_line")
            or f"{primary.get('label', board_snapshot.get('recommended_motion', 'Approve paid next step'))}: {primary.get('ask', board_close_packet.get('primary_ask', 'Attach proof and approve the motion.'))}"
        ),
        "primary_motion": {
            "label": str(primary.get("label") or board_snapshot.get("recommended_motion") or "Approve paid next step"),
            "route": str(primary.get("route") or order.get("route") or "/commercial-offer-studio"),
            "status": str(primary.get("status") or ("ready" if board_close_packet.get("ready_to_close") else "watch")),
            "ask": str(primary.get("ask") or board_close_packet.get("primary_ask") or "Approve the selected paid next step."),
            "reason": str(primary.get("reason") or board_snapshot.get("why_now") or ""),
        },
        "role_cards": role_cards[:5],
        "proof_readiness": proof_readiness[:4],
        "meeting_flow": meeting_flow[:4],
        "open_first_path": open_first_path[:4],
        "files": ["buyer-brief.md", "buyer-pulse.md", OPEN_FIRST_PATH_FILE, "rentgen-board-pack.md", "commercial-offer-studio.md", "OPEN_FIRST.md"],
        "routes": routes,
        "board_question": (
            "Can we approve the selected local-license/proof motion with these owners and artifacts?"
            if board_close_packet.get("ready_to_close")
            else "Which blocker becomes paid proof or hardening scope before procurement?"
        ),
    }


def _next_72_hours(recommended_offer: dict[str, Any]) -> list[dict[str, str]]:
    offer_route = str(recommended_offer.get("route") or "/commercial-offer-studio")
    return [
        {
            "window": "0-2 hours",
            "owner": "director / sponsor",
            "action": "Approve the recommended motion or explicitly downgrade it to a proof sprint.",
            "route": "/board-pack",
            "output": "selected buying motion",
        },
        {
            "window": "same day",
            "owner": "security / architect",
            "action": "Name mandatory pilot artifacts: locality, SBOM/offline, rights/RLS, platform caveats.",
            "route": "/enterprise-trust-center",
            "output": "approval artifact list",
        },
        {
            "window": "same day",
            "owner": "seller / delivery lead",
            "action": "Attach markdown and hash manifest to the buyer-safe packet.",
            "route": "/evidence-bundle",
            "output": "portable proof pack",
        },
        {
            "window": "24 hours",
            "owner": "pilot owner",
            "action": f"Book {recommended_offer.get('title') or 'the selected paid step'} with acceptance criteria.",
            "route": offer_route,
            "output": "paid next-step scope",
        },
        {
            "window": "72 hours",
            "owner": "delivery lead",
            "action": "Run the first role-led scenario and freeze go/no-go criteria.",
            "route": "/pilot-launchpad",
            "output": "dated pilot checklist",
        },
    ]


def _board_close_packet(
    *,
    commercial_offer_studio: dict[str, Any],
    recommended_offer: dict[str, Any],
) -> dict[str, Any]:
    close_packet = commercial_offer_studio.get("close_packet") or {}
    one_page_order = close_packet.get("one_page_order") or {}
    checkout = list(close_packet.get("checkout") or [])
    evidence_requirements = list(close_packet.get("evidence_requirements") or [])
    buyer_commitments = list(close_packet.get("buyer_commitments") or [])
    close_script = list(close_packet.get("close_script") or [])

    if not checkout:
        checkout = [
            {
                "gate": "Approval record exists for risky/write action",
                "route": "/approvals",
                "evidence": "Scoped approval record with actor, reason, tool and constraints.",
            },
            {
                "gate": "Audit chain is valid",
                "route": "/audit",
                "evidence": "Audit verify reports a valid tamper-evident hash chain.",
            },
            {
                "gate": "Proof archive is exportable",
                "route": "/evidence-bundle",
                "evidence": "ZIP archive includes manifest, bundle JSON and governance proof.",
            },
            {
                "gate": "Trust caveats are visible",
                "route": "/enterprise-trust-center",
                "evidence": "Security/procurement controls and caveats are named before quote.",
            },
        ]
    if not evidence_requirements:
        evidence_requirements = [
            {"artifact": "Evidence Bundle ZIP", "route": "/evidence-bundle", "why": "Forwardable proof with SHA-256 manifest."},
            {
                "artifact": "Archive Acceptance Receipt",
                "route": "/evidence-bundle",
                "why": f"`{ARCHIVE_ACCEPTANCE_RECEIPT_MD}` records Evidence Bundle and Killer Demo archive hashes.",
            },
            {"artifact": "Governance proof", "route": "/approvals", "why": "Approval records, scope constraints and audit trail."},
            {"artifact": "Audit verify", "route": "/audit", "why": "Tamper-evident hash-chain status."},
            {"artifact": "Business Case", "route": "/business-case", "why": "Value anchor and AI-rent displacement."},
        ]
    else:
        evidence_requirements = _ensure_archive_receipt_requirement(evidence_requirements)
    if not buyer_commitments:
        buyer_commitments = [
            {"role": "finance", "commitment": "Accept local value anchor and separated optional AI credits.", "route": "/business-case"},
            {"role": "security", "commitment": "Confirm approval/audit evidence and trust caveats.", "route": "/approvals"},
            {"role": "sponsor", "commitment": "Approve the paid next step or explicit hardening scope.", "route": "/commercial-offer-studio"},
        ]
    if not close_script:
        close_script = [
            "Approve the paid next step only with evidence, approvals and audit proof attached.",
            "The price is anchored to local 1C evidence value, not token usage.",
            "If rollout is blocked, approve hardening scope instead of an unsafe enterprise promise.",
        ]

    proof_routes = sorted(
        _route_set(checkout)
        | _route_set(evidence_requirements)
        | _route_set(buyer_commitments)
        | {str(one_page_order.get("route") or recommended_offer.get("route") or "/commercial-offer-studio")}
    )
    ready_to_close = bool(close_packet.get("ready_to_close", _status(commercial_offer_studio) == "ready"))
    return {
        "ready_to_close": ready_to_close,
        "close_mode": str(close_packet.get("close_mode") or "open_enterprise_purchase"),
        "primary_ask": str(close_packet.get("primary_ask") or "Approve the recommended paid next step with the proof packet attached."),
        "one_page_order": {
            "product": str(one_page_order.get("product") or "1C Rentgen local evidence control plane"),
            "recommended_purchase": str(one_page_order.get("recommended_purchase") or recommended_offer.get("title") or "Selected paid next step"),
            "commercial_frame": str(one_page_order.get("commercial_frame") or recommended_offer.get("commercial_frame") or "fixed paid next step"),
            "value_anchor": str(one_page_order.get("value_anchor") or "Business Case"),
            "ai_rent_baseline": str(one_page_order.get("ai_rent_baseline") or "optional AI credits"),
            "three_year_ai_rent": str(one_page_order.get("three_year_ai_rent") or "not provided"),
            "local_license_anchor": str(one_page_order.get("local_license_anchor") or "Business Case"),
            "break_even": str(one_page_order.get("break_even") or "review Business Case"),
            "first_invoice_trigger": str(one_page_order.get("first_invoice_trigger") or "Board names owner, scope, date and accepted proof artifacts."),
            "route": str(one_page_order.get("route") or recommended_offer.get("route") or "/commercial-offer-studio"),
        },
        "checkout": checkout,
        "evidence_requirements": evidence_requirements,
        "buyer_commitments": buyer_commitments,
        "close_script": close_script,
        "proof_routes": proof_routes,
        "board_line": (
            "Board can approve the paid motion now if checkout gates are accepted."
            if ready_to_close
            else "Board should approve paid proof or hardening scope before rollout procurement."
        ),
    }


def _objection_answers() -> list[dict[str, str]]:
    return [
        {
            "objection": "This looks like another AI subscription.",
            "answer": "The board buys local 1C evidence, release governance and proof exports; AI is optional capacity, not the product core.",
            "route": "/business-case",
        },
        {
            "objection": "The surface is too large to understand in a meeting.",
            "answer": "Start from Buyer Concierge: role, pain, shortest path and default next action.",
            "route": "/buyer-concierge",
        },
        {
            "objection": "Security will block this.",
            "answer": "Trust Center turns the block into an artifact list, risk register and hardening package.",
            "route": "/enterprise-trust-center",
        },
        {
            "objection": "Developers will not care about management dashboards.",
            "answer": "Open a concrete defect path first: LEFT JOIN/NULL guard, impact and regression expectation.",
            "route": "/quality",
        },
        {
            "objection": "We cannot buy without a clear next step.",
            "answer": "Offer Studio provides proof sprint, local pilot, enterprise license and vendor rollout motions.",
            "route": "/commercial-offer-studio",
        },
    ]


def _board_room_script(recommended_offer: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "minute": "0-1",
            "speaker": "sponsor",
            "route": "/buyer-concierge",
            "line": "We will start from the role or pain in the room, not from the full menu.",
        },
        {
            "minute": "1-3",
            "speaker": "technical lead",
            "route": "/scenario-hub",
            "line": "Show one concrete 1C scenario and the proof route behind it.",
        },
        {
            "minute": "3-5",
            "speaker": "security / architect",
            "route": "/enterprise-trust-center",
            "line": "Name install mode, trust artifacts and remaining caveats before selling rollout.",
        },
        {
            "minute": "5-7",
            "speaker": "director",
            "route": "/business-case",
            "line": "Anchor the purchase to local product value, not a vague AI promise.",
        },
        {
            "minute": "7-8",
            "speaker": "seller",
            "route": str(recommended_offer.get("route") or "/commercial-offer-studio"),
            "line": f"Approve {recommended_offer.get('title') or 'the selected paid next step'} and attach the Evidence Bundle.",
        },
    ]


def _exports() -> list[dict[str, str]]:
    return [
        {"title": "Board Pack markdown", "filename": "rentgen-board-pack.md", "route": "/board-pack"},
        {"title": "Buyer Concierge markdown", "filename": "rentgen-buyer-concierge.md", "route": "/buyer-concierge"},
        {"title": "Commercial Offer Studio markdown", "filename": "rentgen-commercial-offer-studio.md", "route": "/commercial-offer-studio"},
        {"title": "Enterprise Trust Center markdown", "filename": "rentgen-enterprise-trust-center.md", "route": "/enterprise-trust-center"},
        {"title": "Governance Proof markdown", "filename": "governance-proof.md", "route": "/approvals"},
        {"title": "Audit verification/export", "filename": "rentgen-audit-log.jsonl", "route": "/audit"},
        {"title": "Evidence Bundle manifest", "filename": "evidence-bundle-manifest.json", "route": "/evidence-bundle"},
    ]


def _board_status(
    *,
    score: int,
    statuses: set[str],
    severe_risks: list[dict[str, str]],
    enterprise_trust_center: dict[str, Any],
) -> str:
    if statuses & {"blocked", "critical", "fail"}:
        return "risk"
    if _status(enterprise_trust_center) == "risk":
        return "risk"
    if score >= 82 and len(severe_risks) <= 2:
        return "ready"
    return "watch"


def _markdown(report: dict[str, Any]) -> str:
    board_room = report.get("board_room_bridge") or {}
    lines = [
        "# 1C Rentgen Board Pack",
        "",
        f"Client: **{report['client']['name']}**",
        f"Status: **{report['decision']['status'].upper()}** / score **{report['decision']['score']}**",
        f"Recommended motion: **{report['board_snapshot']['recommended_motion']}**",
        f"Value anchor: **{report['board_snapshot']['value_anchor']}**",
        f"Three-year AI rent: **{report['board_snapshot'].get('three_year_ai_rent', 'n/a')}**",
        f"Local license anchor: **{report['board_snapshot'].get('local_license_anchor', 'n/a')}**",
        f"Break-even: **{report['board_snapshot'].get('break_even', 'n/a')}**",
        "",
        "## Board Room Bridge",
        "",
        f"- Status: **{board_room.get('status', 'unknown')}** / score **{board_room.get('score', 0)}**",
        f"- Room line: {board_room.get('room_line', '')}",
        f"- Primary motion: **{(board_room.get('primary_motion') or {}).get('label', '')}** (`{(board_room.get('primary_motion') or {}).get('route', '/board-pack')}`)",
        f"- Board question: {board_room.get('board_question', '')}",
        f"- Files: {', '.join(board_room.get('files', []))}",
    ]
    lines.extend(open_first_path_markdown_lines(board_room.get("open_first_path"), default_route="/board-pack"))
    lines.extend(["", "## Decision Brief", ""])
    for item in report["decision_brief"]:
        lines.append(f"- **{item['question']}** {item['answer']} (`{item['route']}`)")
    lines.extend(["", "## Committee Map", ""])
    for item in report["committee_map"]:
        lines.append(f"- **{item['role']}** (`{item['proof_route']}`): {item['must_believe']} Close: {item['close_line']}")
    lines.extend(["", "## Risks To Decision", ""])
    for item in report["risk_to_decision"]:
        lines.append(f"- **{item['severity']}** {item['owner']} (`{item['route']}`): {item['risk']} Decision: {item['decision']}")
    close_packet = report.get("board_close_packet") or {}
    if close_packet:
        order = close_packet.get("one_page_order") or {}
        lines.extend(["", "## Board Close Packet", ""])
        lines.append(f"- Ready to close: **{bool(close_packet.get('ready_to_close'))}**")
        lines.append(f"- Mode: **{close_packet.get('close_mode', 'unknown')}**")
        lines.append(f"- Primary ask: {close_packet.get('primary_ask', '')}")
        lines.append(f"- Recommended purchase: **{order.get('recommended_purchase', 'n/a')}** (`{order.get('route', '/commercial-offer-studio')}`)")
        lines.append(f"- Board line: {close_packet.get('board_line', '')}")
        for item in close_packet.get("checkout", []):
            lines.append(f"- Checkout `{item.get('route', '/board-pack')}`: {item.get('gate', '')} - {item.get('evidence', '')}")
        for item in close_packet.get("evidence_requirements", []):
            lines.append(
                f"- Evidence `{item.get('route', '/board-pack')}`: {item.get('artifact', '')} - {item.get('why', '')}"
            )
    lines.extend(["", "## Next 72 Hours", ""])
    for item in report["next_72_hours"]:
        lines.append(f"- **{item['window']}** / {item['owner']} (`{item['route']}`): {item['action']} -> {item['output']}")
    lines.extend(["", "## Caveats", ""])
    lines.extend(f"- {item}" for item in report["caveats"])
    return "\n".join(lines)


def build_board_pack(
    *,
    executive: dict[str, Any],
    buyer_concierge: dict[str, Any],
    commercial_offer_studio: dict[str, Any],
    enterprise_trust_center: dict[str, Any],
    business_case: dict[str, Any],
    scenario_hub: dict[str, Any],
    pilot_launchpad: dict[str, Any],
    demo_command_center: dict[str, Any],
    productization: dict[str, Any],
    evidence_artifacts: list[dict[str, Any]] | None = None,
    buyer_brief: dict[str, Any] | None = None,
    client_name: str = "Demo client",
    config_path: str | None = None,
    target_platform_version: str | None = None,
) -> dict[str, Any]:
    """Build the board-level decision packet over buyer, trust, offer and proof reports."""

    artifacts = list(evidence_artifacts or [])
    recommended_offer = _recommended_offer(
        commercial_offer_studio=commercial_offer_studio,
        enterprise_trust_center=enterprise_trust_center,
        pilot_launchpad=pilot_launchpad,
    )
    board_snapshot = _board_snapshot(
        business_case=business_case,
        buyer_concierge=buyer_concierge,
        commercial_offer_studio=commercial_offer_studio,
        enterprise_trust_center=enterprise_trust_center,
        recommended_offer=recommended_offer,
    )
    decision_brief = _decision_brief(
        board_snapshot=board_snapshot,
        recommended_offer=recommended_offer,
        commercial_offer_studio=commercial_offer_studio,
        enterprise_trust_center=enterprise_trust_center,
    )
    committee_map = _committee_map(
        buyer_concierge=buyer_concierge,
        commercial_offer_studio=commercial_offer_studio,
    )
    risk_to_decision = _risk_to_decision(
        commercial_offer_studio=commercial_offer_studio,
        enterprise_trust_center=enterprise_trust_center,
    )
    proof_packet = _proof_packet(artifacts)
    next_72_hours = _next_72_hours(recommended_offer)
    board_close_packet = _board_close_packet(
        commercial_offer_studio=commercial_offer_studio,
        recommended_offer=recommended_offer,
    )
    board_room_bridge = _board_room_bridge(
        buyer_brief=buyer_brief,
        board_snapshot=board_snapshot,
        board_close_packet=board_close_packet,
        committee_map=committee_map,
    )
    objection_answers = _objection_answers()
    board_room_script = _board_room_script(recommended_offer)
    value, currency, ai_year = _value_anchor(
        business_case=business_case,
        commercial_offer_studio=commercial_offer_studio,
    )
    score = max(
        0,
        min(
            100,
            round(
                _score(buyer_concierge) * 0.12
                + _score(commercial_offer_studio) * 0.24
                + _score(enterprise_trust_center) * 0.22
                + _score(business_case) * 0.16
                + _score(scenario_hub) * 0.10
                + _score(pilot_launchpad) * 0.10
                + _score(demo_command_center) * 0.06
            ),
        ),
    )
    statuses = {
        _status(executive),
        _status(buyer_concierge),
        _status(commercial_offer_studio),
        _status(enterprise_trust_center),
        _status(business_case),
        _status(productization),
    }
    severe_risks = [item for item in risk_to_decision if item["severity"] in {"high", "critical"}]
    status = _board_status(
        score=score,
        statuses=statuses,
        severe_risks=severe_risks,
        enterprise_trust_center=enterprise_trust_center,
    )
    proof_routes = sorted(
        {item["route"] for item in decision_brief}
        | {item["proof_route"] for item in committee_map}
        | {item["route"] for item in risk_to_decision}
        | {item["route"] for item in proof_packet}
        | {item["route"] for item in next_72_hours}
        | {item["route"] for item in board_close_packet["checkout"]}
        | {item["route"] for item in board_close_packet["evidence_requirements"]}
        | {item["route"] for item in board_close_packet["buyer_commitments"]}
        | set(board_close_packet["proof_routes"])
        | set(board_room_bridge["routes"])
        | {item["route"] for item in objection_answers}
        | {item["route"] for item in board_room_script}
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
                "Board Pack is ready: value, trust, offer, committee answers and evidence are compressed into one buying motion."
                if status == "ready"
                else "Board Pack is usable, but trust/productization caveats must stay visible before full rollout approval."
            ),
        },
        "summary": {
            "board_minutes": 8,
            "decision_items": len(decision_brief),
            "committee_roles": len(committee_map),
            "risks": len(risk_to_decision),
            "severe_risks": len(severe_risks),
            "proof_items": len(proof_packet),
            "proof_routes": len(proof_routes),
            "first_year_visible_value": value,
            "ai_subscription_year": ai_year,
            "currency": currency,
            "recommended_offer": str(recommended_offer.get("id") or ""),
            "evidence_artifacts": len(artifacts),
            "close_ready": bool(board_close_packet["ready_to_close"]),
            "checkout_gates": len(board_close_packet["checkout"]),
            "board_room_roles": len(board_room_bridge["role_cards"]),
            "board_room_proofs": len(board_room_bridge["proof_readiness"]),
            "board_room_steps": len(board_room_bridge["meeting_flow"]),
            "board_room_open_first": len(board_room_bridge["open_first_path"]),
        },
        "board_snapshot": board_snapshot,
        "board_room_bridge": board_room_bridge,
        "decision_brief": decision_brief,
        "committee_map": committee_map,
        "recommended_offer": recommended_offer,
        "risk_to_decision": risk_to_decision,
        "proof_packet": proof_packet,
        "board_close_packet": board_close_packet,
        "next_72_hours": next_72_hours,
        "objection_answers": objection_answers,
        "board_room_script": board_room_script,
        "exports": _exports(),
        "proof_routes": proof_routes,
        "source_signals": {
            "executive_status": _status(executive),
            "buyer_concierge_status": _status(buyer_concierge),
            "commercial_offer_status": _status(commercial_offer_studio),
            "commercial_close_mode": board_close_packet["close_mode"],
            "trust_center_status": _status(enterprise_trust_center),
            "business_case_score": _score(business_case),
            "scenario_hub_status": _status(scenario_hub),
            "pilot_launchpad_status": _status(pilot_launchpad),
            "demo_command_center_status": _status(demo_command_center),
            "productization_status": _status(productization),
            "board_room_source": board_room_bridge["source"],
        },
        "caveats": [
            "Board Pack v1 is a buying-decision artifact, not a signed commercial contract.",
            "Security, legal, support terms and exact license metrics remain customer-specific.",
            "If Trust Center is risky, approve proof or hardening before enterprise rollout.",
        ],
        "download_name": "rentgen-board-pack.md",
    }
    report["markdown"] = _markdown(report)
    return report
