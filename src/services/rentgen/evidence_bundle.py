"""Evidence bundle composer for buyer, approval and delivery packs."""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from src.services import audit_log
from src.services.productization_readiness import (
    productization_markdown_report,
    productization_readiness,
)
from src.services.rentgen import approval_workflow
from src.services.rentgen.board_pack import build_board_pack
from src.services.rentgen.business_case import build_business_case
from src.services.rentgen.buyer_brief import build_buyer_brief
from src.services.rentgen.buyer_concierge import build_buyer_concierge
from src.services.rentgen.buyer_pulse import build_buyer_pulse
from src.services.rentgen.commercial_offer_studio import build_commercial_offer_studio
from src.services.rentgen.demo_command_center import build_demo_command_center
from src.services.rentgen.demo_story import build_demo_story
from src.services.rentgen.enterprise_trust_center import build_enterprise_trust_center
from src.services.rentgen.extension_safety import build_extension_safety
from src.services.rentgen.guided_demo import build_guided_demo
from src.services.rentgen.intake_wizard import build_intake_plan
from src.services.rentgen.killer_demo_path import (
    ARCHIVE_VERIFICATION_PACKET_ENDPOINT,
    ARCHIVE_VERIFICATION_PACKET_HASH_HEADER,
    ARCHIVE_VERIFICATION_PACKET_OPEN_FIRST,
    ARCHIVE_VERIFICATION_PACKET_ZIP,
    KILLER_DEMO_ARCHIVE_HASH_HEADER,
    MEETING_CLOSE_RECEIPT_JSON,
    MEETING_CLOSE_RECEIPT_MD,
    POST_DEMO_ACTIVATION_JSON,
    POST_DEMO_ACTIVATION_MD,
    build_killer_demo_path,
    role_packet_filename,
)
from src.services.rentgen.launch_room import build_launch_room
from src.services.rentgen.lock_radar import build_lock_radar
from src.services.rentgen.offline_readiness import build_offline_readiness
from src.services.rentgen.outcome_ledger import build_outcome_ledger
from src.services.rentgen.pilot_launchpad import build_pilot_launchpad
from src.services.rentgen.platform_doctor import build_platform_doctor
from src.services.rentgen.rights_rls import build_rights_rls
from src.services.rentgen.safe_autopilot import build_safe_autopilot
from src.services.rentgen.scenario_hub import build_scenario_hub
from src.services.rentgen.security_posture import build_security_posture
from src.services.rentgen.test_factory import build_test_factory
from src.services.rentgen.update_war_room import build_update_war_room
from src.services.rentgen.value_packs import build_value_packs
from src.services.rentgen.vendor_portfolio import build_vendor_portfolio


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_text(payload: Any) -> str:
    return json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    )


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _status(report: dict[str, Any]) -> str:
    return str(
        (report.get("decision") or {}).get("status")
        or report.get("status")
        or "unknown"
    )


def _score(report: dict[str, Any]) -> int | None:
    value = (report.get("decision") or {}).get("score")
    return int(value) if isinstance(value, (int, float)) else None


def _int_or_none(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _money(value: Any, currency: str) -> str:
    number = _int_or_none(value)
    if number is None:
        return "not provided"
    return f"{number:,}".replace(",", " ") + f" {currency}"


def _commercial_assumption_receipt(
    business_case: dict[str, Any] | None,
    assumptions: dict[str, Any] | None,
) -> dict[str, Any]:
    source = "business-case" if business_case else "request"
    business_case = business_case or {}
    normalized = dict(business_case.get("assumptions") or assumptions or {})
    summary = business_case.get("summary") or {}
    escape = business_case.get("subscription_escape_plan") or {}
    currency = str(escape.get("currency") or normalized.get("currency") or "RUB")
    monthly = _int_or_none(normalized.get("monthly_ai_subscription_cost"))
    annual = _int_or_none(escape.get("annual_ai_rent")) or (
        monthly * 12 if monthly is not None else None
    )
    three_year = _int_or_none(escape.get("three_year_ai_rent")) or (
        annual * 3 if annual is not None else None
    )
    local_license = _int_or_none(escape.get("local_license_anchor")) or _int_or_none(
        summary.get("local_license_anchor")
    )
    break_even = _int_or_none(escape.get("break_even_months")) or _int_or_none(
        summary.get("subscription_break_even_months")
    )
    ai_rent_equivalent = _int_or_none(
        escape.get("ai_rent_equivalent_months")
    ) or _int_or_none(summary.get("subscription_escape_months"))
    line = str(
        escape.get("decision_line")
        or "Commercial assumptions are carried from the request; build Business Case to materialize the full local-license comparison."
    )
    return {
        "source": source,
        "currency": currency,
        "monthly_ai_subscription_cost": monthly,
        "annual_ai_rent": annual,
        "three_year_ai_rent": three_year,
        "local_license_anchor": local_license,
        "break_even_months": break_even,
        "ai_rent_equivalent_months": ai_rent_equivalent,
        "monthly_ai_rent_label": _money(monthly, currency),
        "annual_ai_rent_label": _money(annual, currency),
        "three_year_ai_rent_label": _money(three_year, currency),
        "local_license_anchor_label": _money(local_license, currency),
        "break_even_label": f"{break_even} months"
        if break_even is not None
        else "not provided",
        "decision_line": line,
        "evidence_files": list(
            escape.get("evidence_files")
            or [
                {
                    "title": "Business Case",
                    "filename": "business-case.md",
                    "route": "/business-case",
                }
            ]
        ),
    }


def _artifact(
    *,
    id: str,
    title: str,
    route: str,
    report: dict[str, Any],
    filename: str,
    summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    json_payload = _json_text(report)
    markdown = str(
        report.get("markdown") or report.get("export", {}).get("markdown") or ""
    )
    return {
        "id": id,
        "title": title,
        "route": route,
        "filename": filename,
        "status": _status(report),
        "score": _score(report),
        "json_sha256": _sha256_text(json_payload),
        "markdown_sha256": _sha256_text(markdown) if markdown else "",
        "summary": summary or report.get("summary") or {},
        "caveats": list(report.get("caveats") or [])[:10],
        "json": json_payload,
        "markdown": markdown,
    }


def _buyer_pulse_markdown(report: dict[str, Any]) -> str:
    pulse = report.get("buyer_pulse") or {}
    commercial = pulse.get("commercial") or {}
    launch = pulse.get("launch") or {}
    concierge = pulse.get("concierge") or {}
    evidence = pulse.get("evidence") or {}
    executive = pulse.get("executive") or {}
    purchase_path = pulse.get("purchase_path") or {}
    lines = [
        "# Buyer Pulse",
        "",
        "Fast first-screen buying signal for the local-license motion.",
        "",
        f"Status: **{(report.get('decision') or {}).get('status', 'unknown')}** / score **{(report.get('decision') or {}).get('score', 0)}**",
        f"Source: **{pulse.get('source', 'unknown')}**",
        "",
        "## Commercial Line",
        "",
        f"- AI/month: **{commercial.get('monthly_ai_rent', 'n/a')}**",
        f"- Annual AI rent: **{commercial.get('annual_ai_rent', 'n/a')}**",
        f"- Three-year AI rent: **{commercial.get('three_year_ai_rent', 'n/a')}**",
        f"- Local license anchor: **{commercial.get('local_license_anchor', 'n/a')}**",
        f"- Buyer line: {commercial.get('buyer_line', '')}",
        "",
        "## First Clicks",
        "",
        f"- Launch Room `{launch.get('route', '/launch-room')}`: {launch.get('journey_ready', 0)}/{launch.get('journey_steps', 0)} journey steps ready; purchase spine **{launch.get('purchase_spine_status', 'unknown')}**.",
        f"- Buyer Concierge `{concierge.get('route', '/buyer-concierge')}`: {concierge.get('persona_cards', 0)} role cards, {concierge.get('shortest_paths', 0)} shortest paths; purchase router **{concierge.get('purchase_router_status', 'unknown')}**.",
        f"- Evidence Bundle `{evidence.get('route', '/evidence-bundle')}`: {evidence.get('proof_routes', 0)} proof routes and {evidence.get('governance_gates', 0)} governance gates.",
        "",
        "## Purchase Path",
        "",
        f"- **{purchase_path.get('headline', 'Launch -> Killer Demo -> Receipt -> Activation -> Outcome.')}**",
        f"- {purchase_path.get('buyer_line', '')}",
    ]
    for item in purchase_path.get("steps") or []:
        lines.append(
            f"- **{item.get('step', '')}. {item.get('label', '')}** (`{item.get('route', '/')}`): "
            f"{item.get('artifact', '')} / `{item.get('file', '')}` - {item.get('line', '')}"
        )
    send_files = purchase_path.get("send_files") or []
    if send_files:
        lines.extend(["", "### Purchase Path Files", ""])
        lines.extend(f"- `{filename}`" for filename in send_files)
    lines.extend(
        [
            "",
            "## Executive Signals",
            "",
            f"- Red areas: **{executive.get('red_areas', 0)}**",
            f"- Review queue: **{executive.get('review_queue', 0)}**",
            f"- High hotspots: **{executive.get('high_hotspots', 0)}**",
            f"- Headline: {executive.get('headline', '')}",
            "",
            "## How To Use",
            "",
            "1. Open Buyer Pulse first when the room asks where to start.",
            "2. If purchase status is ready, open Launch Room and ask for the paid next step.",
            "3. If purchase status is watch or risk, open Buyer Concierge or Trust Center and name the blocker.",
            "4. Keep this file in the ZIP so procurement can see the first-screen assumptions that led to the route.",
        ]
    )
    return "\n".join(lines)


def _buyer_pulse_report(
    *,
    executive: dict[str, Any],
    assumptions: dict[str, Any] | None,
    generated_at: str,
    client_name: str,
    config_path: str | None,
    target_platform_version: str | None,
) -> dict[str, Any]:
    monthly_ai = (
        _int_or_none((assumptions or {}).get("monthly_ai_subscription_cost")) or 120_000
    )
    currency = str((assumptions or {}).get("currency") or "RUB")
    pulse = build_buyer_pulse(
        executive=executive,
        monthly_ai_subscription_cost=monthly_ai,
        currency=currency,
    )
    report: dict[str, Any] = {
        "generated_at": generated_at,
        "client": {
            "name": client_name,
            "config_path": config_path or "",
            "target_platform_version": target_platform_version or "",
        },
        "decision": {
            "status": pulse["purchase_status"],
            "score": pulse["score"],
            "headline": "Buyer Pulse is export-ready: first-screen purchase status, AI-rent line, proof routes and governance gates are materialized.",
        },
        "summary": {
            "source": pulse["source"],
            "purchase_status": pulse["purchase_status"],
            "three_year_ai_rent": (pulse.get("commercial") or {}).get(
                "three_year_ai_rent", ""
            ),
            "local_license_anchor": (pulse.get("commercial") or {}).get(
                "local_license_anchor", ""
            ),
            "proof_routes": (pulse.get("evidence") or {}).get("proof_routes", 0),
            "governance_gates": (pulse.get("evidence") or {}).get(
                "governance_gates", 0
            ),
            "persona_cards": (pulse.get("concierge") or {}).get("persona_cards", 0),
            "purchase_path_steps": len(
                (pulse.get("purchase_path") or {}).get("steps") or []
            ),
            "purchase_path_files": len(
                (pulse.get("purchase_path") or {}).get("send_files") or []
            ),
        },
        "buyer_pulse": pulse,
        "caveats": [
            "Buyer Pulse is a fast first-screen signal. Deep proof remains in Launch Room, Buyer Concierge, Offer Studio and Evidence Bundle artifacts.",
            "Commercial numbers come from request assumptions when provided; otherwise default demo assumptions are used.",
        ],
    }
    report["markdown"] = _buyer_pulse_markdown(report)
    return report


def _buyer_brief_markdown(report: dict[str, Any]) -> str:
    brief = report.get("buyer_brief") or {}
    commercial = brief.get("commercial") or {}
    primary = brief.get("primary_motion") or {}
    purchase_path = brief.get("purchase_path") or {}
    room_plan = brief.get("buyer_room_plan") or {}
    open_first_path = brief.get("open_first_path") or []
    lines = [
        "# Buyer Brief",
        "",
        "Fast first-minute room map for the buying committee.",
        "",
        f"Status: **{(report.get('decision') or {}).get('status', 'unknown')}** / score **{(report.get('decision') or {}).get('score', 0)}**",
        f"Source: **{brief.get('source', 'unknown')}**",
        f"Primary motion: **{primary.get('label', 'n/a')}** (`{primary.get('route', '/')}`)",
        f"Ask: {primary.get('ask', '')}",
        "",
        "## Room Line",
        "",
        str(brief.get("room_line") or ""),
        "",
        "## Commercial Line",
        "",
        f"- AI/month: **{commercial.get('monthly_ai_rent', 'n/a')}**",
        f"- Three-year AI rent: **{commercial.get('three_year_ai_rent', 'n/a')}**",
        f"- Local license anchor: **{commercial.get('local_license_anchor', 'n/a')}**",
        "",
        "## Purchase Path",
        "",
        f"- **{purchase_path.get('headline', 'Launch -> Killer Demo -> Receipt -> Activation -> Outcome.')}**",
        f"- {purchase_path.get('buyer_line', '')}",
    ]
    if open_first_path:
        lines.extend(["", "## Open-First Path", ""])
        for item in open_first_path:
            lines.append(
                f"- **{item.get('step', '')}. {item.get('label', '')}** (`{item.get('route', '/')}`): "
                f"`{item.get('file', '')}` - {item.get('line', '')}"
            )
    for item in purchase_path.get("steps") or []:
        lines.append(
            f"- **{item.get('step', '')}. {item.get('label', '')}** (`{item.get('route', '/')}`): "
            f"{item.get('artifact', '')} / `{item.get('file', '')}` - {item.get('line', '')}"
        )
    archive_receipt = purchase_path.get("archive_receipt_artifact") or {}
    if archive_receipt:
        lines.extend(
            [
                "",
                "### Archive Receipt",
                "",
                f"- **{archive_receipt.get('title', 'Archive Acceptance Receipt')}** (`{archive_receipt.get('route', '/evidence-bundle')}`): "
                f"`{archive_receipt.get('file', 'archive-acceptance-receipt.md')}` - {archive_receipt.get('line', '')}",
            ]
        )
    send_files = purchase_path.get("send_files") or []
    if send_files:
        lines.extend(["", "### Purchase Path Files", ""])
        lines.extend(f"- `{filename}`" for filename in send_files)
    if room_plan:
        lines.extend(
            [
                "",
                "## Buyer Room Plan",
                "",
                f"- Mode: **{room_plan.get('mode', 'unknown')}**",
                f"- Role: **{room_plan.get('role', 'all')}**",
                f"- Route: `{room_plan.get('route', '/')}`",
                f"- Start with: {room_plan.get('start_with', '')}",
                f"- Show: {room_plan.get('show', '')}",
                f"- Close question: {room_plan.get('close_question', '')}",
                f"- Proof file: `{room_plan.get('proof_file', 'buyer-brief.md')}`",
            ]
        )
        sequence = room_plan.get("sequence") or []
        if sequence:
            lines.extend(["", "### Room Sequence", ""])
            for item in sequence:
                lines.append(
                    f"- **{item.get('step', '')}. {item.get('label', '')}** (`{item.get('route', '/')}`): "
                    f"{item.get('line', '')}"
                )
        room_files = room_plan.get("send_files") or []
        if room_files:
            lines.extend(["", "### Room Files", ""])
            lines.extend(f"- `{filename}`" for filename in room_files)
    lines.extend(
        [
            "",
            "## Role Cards",
            "",
        ]
    )
    for item in brief.get("role_cards") or []:
        lines.append(
            f"- **{item.get('title', '')}** / {item.get('status', '')} (`{item.get('route', '/')}`): "
            f"{item.get('spark', '')} File: `{item.get('proof_file', '')}`"
        )
    lines.extend(["", "## Proof Readiness", ""])
    for item in brief.get("proof_readiness") or []:
        lines.append(
            f"- **{item.get('title', '')}** / {item.get('status', '')} (`{item.get('route', '/')}`): "
            f"{item.get('signal', '')} File: `{item.get('file', '')}`"
        )
    lines.extend(["", "## Meeting Flow", ""])
    for item in brief.get("meeting_flow") or []:
        lines.append(
            f"- **{item.get('step', '')}. {item.get('label', '')}** (`{item.get('route', '/')}`): {item.get('line', '')}"
        )
    lines.extend(
        [
            "",
            "## How To Use",
            "",
            "1. Open this file before role-specific reports when the recipient asks what to read first.",
            "2. Use the primary motion to decide whether the next ask is local license, proof sprint or configuration connection.",
            "3. Send the role card proof files listed here rather than the whole archive when a stakeholder needs a narrow packet.",
            "4. Keep Buyer Pulse beside this file for the numeric purchase status and AI-rent baseline.",
        ]
    )
    return "\n".join(lines)


def _buyer_brief_report(
    *,
    executive: dict[str, Any],
    assumptions: dict[str, Any] | None,
    generated_at: str,
    client_name: str,
    config_path: str | None,
    target_platform_version: str | None,
) -> dict[str, Any]:
    monthly_ai = (
        _int_or_none((assumptions or {}).get("monthly_ai_subscription_cost")) or 120_000
    )
    currency = str((assumptions or {}).get("currency") or "RUB")
    brief = build_buyer_brief(
        executive=executive,
        monthly_ai_subscription_cost=monthly_ai,
        currency=currency,
    )
    report: dict[str, Any] = {
        "generated_at": generated_at,
        "client": {
            "name": client_name,
            "config_path": config_path or "",
            "target_platform_version": target_platform_version or "",
        },
        "decision": {
            "status": brief["purchase_status"],
            "score": brief["score"],
            "headline": "Buyer Brief is export-ready: first-minute room map, role cards, proof readiness and meeting flow are materialized.",
        },
        "summary": {
            "source": brief["source"],
            "purchase_status": brief["purchase_status"],
            "primary_route": (brief.get("primary_motion") or {}).get("route", ""),
            "primary_label": (brief.get("primary_motion") or {}).get("label", ""),
            "three_year_ai_rent": (brief.get("commercial") or {}).get(
                "three_year_ai_rent", ""
            ),
            "roles": (brief.get("summary") or {}).get("roles", 0),
            "proof_items": (brief.get("summary") or {}).get("proof_items", 0),
            "meeting_steps": (brief.get("summary") or {}).get("meeting_steps", 0),
            "open_first_steps": (brief.get("summary") or {}).get("open_first_steps", 0),
            "purchase_path_steps": (brief.get("summary") or {}).get(
                "purchase_path_steps", 0
            ),
            "purchase_path_files": (brief.get("summary") or {}).get(
                "purchase_path_files", 0
            ),
            "room_plan_files": (brief.get("summary") or {}).get(
                "room_plan_files",
                len((brief.get("buyer_room_plan") or {}).get("send_files") or []),
            ),
            "room_plan_route": (brief.get("buyer_room_plan") or {}).get("route", ""),
        },
        "buyer_brief": brief,
        "caveats": [
            "Buyer Brief is a fast first-minute route map. Deep proof remains in the referenced artifacts and routes.",
            "Role and proof guidance is generated from executive signals and commercial assumptions available at bundle build time.",
        ],
    }
    report["markdown"] = _buyer_brief_markdown(report)
    return report


def _buyer_room_plan_markdown(report: dict[str, Any]) -> str:
    plan = report.get("buyer_room_plan") or {}
    decision = report.get("decision") or {}
    source = report.get("source_report") or {}
    lines = [
        "# Buyer Room Plan",
        "",
        "One-file operating plan for the live buyer room: first click, proof route, close question and send files.",
        "",
        f"Status: **{decision.get('status', 'unknown')}** / score **{decision.get('score', 0)}**",
        "Recommended file: `buyer-room-plan.md`",
        f"Evidence contract: **{plan.get('evidence_contract', '')}**",
        f"Mode: **{plan.get('mode', 'unknown')}**",
        f"Role: **{plan.get('role', 'all')}**",
        f"Title: {plan.get('title', '')}",
        f"Route: `{plan.get('route', '/')}`",
        f"Selected status: **{plan.get('status', 'unknown')}**",
        "",
        "## First Move",
        "",
        f"- Start with: {plan.get('start_with', '')}",
        f"- Show: {plan.get('show', '')}",
        f"- Why this route: {plan.get('why', '')}",
        f"- Proof file: `{plan.get('proof_file', 'buyer-brief.md')}`",
        f"- Close question: {plan.get('close_question', '')}",
        "",
        "## Sequence",
        "",
    ]
    sequence = plan.get("sequence") or []
    if sequence:
        for item in sequence:
            lines.append(
                f"- **{item.get('step', '')}. {item.get('label', '')}** (`{item.get('route', '/')}`): "
                f"{item.get('line', '')}"
            )
    else:
        lines.append("- No room sequence was generated.")
    lines.extend(["", "## Send Files", ""])
    send_files = plan.get("send_files") or []
    if send_files:
        lines.extend(f"- `{filename}`" for filename in send_files)
    else:
        lines.append("- No send files were generated.")
    if source:
        lines.extend(
            [
                "",
                "## Source",
                "",
                f"- Source artifact: `{source.get('filename', 'buyer-brief.md')}`",
                f"- Source id: **{source.get('id', 'buyer-brief')}**",
                f"- Source route: `{source.get('route', '/')}`",
            ]
        )
    lines.extend(
        [
            "",
            "## How To Use",
            "",
            "1. Open this file after OPEN_FIRST.md when the room asks what to do first.",
            "2. Follow the selected route before showing the full product surface.",
            "3. Ask the close question exactly once the proof file is accepted.",
            "4. Send only the listed files unless procurement asks for the full archive.",
        ]
    )
    return "\n".join(lines)


def _buyer_room_plan_report(buyer_brief_report: dict[str, Any]) -> dict[str, Any]:
    brief = buyer_brief_report.get("buyer_brief") or {}
    plan = dict(brief.get("buyer_room_plan") or {})
    sequence = list(plan.get("sequence") or [])
    send_files = list(plan.get("send_files") or [])
    contract = str(plan.get("evidence_contract") or "")
    export_ready = bool(plan) and contract == "buyer_room_plan_v1"
    report: dict[str, Any] = {
        "generated_at": buyer_brief_report.get("generated_at"),
        "client": buyer_brief_report.get("client") or {},
        "decision": {
            "status": "ready" if export_ready else "blocked",
            "score": _score(buyer_brief_report) or 0,
            "headline": (
                "Buyer Room Plan is export-ready: one role, one first route, one close question and send files are materialized."
                if export_ready
                else "Buyer Room Plan could not be materialized from Buyer Brief."
            ),
        },
        "summary": {
            "mode": str(plan.get("mode") or ""),
            "role": str(plan.get("role") or ""),
            "route": str(plan.get("route") or "/"),
            "selected_status": str(plan.get("status") or ""),
            "proof_file": str(plan.get("proof_file") or ""),
            "sequence_steps": len(sequence),
            "send_files": len(send_files),
            "close_question": str(plan.get("close_question") or ""),
            "evidence_contract": contract,
        },
        "buyer_room_plan": plan,
        "source_report": {
            "id": "buyer-brief",
            "route": "/",
            "filename": "buyer-brief.md",
            "sha256": _sha256_text(str(buyer_brief_report.get("markdown") or "")),
        },
        "caveats": [
            "Buyer Room Plan is an operator route for the live room; deep proof remains in the referenced artifacts.",
            "MEETING_CLOSE_RECEIPT.md and POST_DEMO_ACTIVATION_HANDOFF.md are produced by the linked Killer Demo ZIP.",
        ],
    }
    report["markdown"] = _buyer_room_plan_markdown(report)
    return report


def _open_first_path_markdown(report: dict[str, Any]) -> str:
    path = report.get("open_first_path") or []
    decision = report.get("decision") or {}
    lines = [
        "# Open-First Path",
        "",
        "Four buyer-safe actions before the full workbench: orient, prove, close and verify.",
        "",
        f"Status: **{decision.get('status', 'unknown')}** / score **{decision.get('score', 0)}**",
        "Recommended file: `open-first-path.md`",
        "",
    ]
    for item in path:
        lines.extend(
            [
                f"## {item.get('step', '')}. {item.get('label', '')}",
                "",
                f"- Stage: **{item.get('stage', '')}**",
                f"- Title: {item.get('title', '')}",
                f"- Route: `{item.get('route', '/')}`",
                f"- File: `{item.get('file', '')}`",
                f"- Status: **{item.get('status', '')}**",
                f"- Source: `{item.get('source', '')}`",
                f"- Line: {item.get('line', '')}",
                "",
            ]
        )
    lines.extend(
        [
            "## How To Use",
            "",
            "1. Open this file before role-specific packets when the buyer asks what happens first.",
            "2. Keep the sequence unchanged across Home, Launch Room, Killer Demo and procurement handoff.",
            "3. Treat the verify step as mandatory before the archive pair is accepted.",
        ]
    )
    return "\n".join(lines)


def _open_first_path_report(buyer_brief_report: dict[str, Any]) -> dict[str, Any]:
    brief = buyer_brief_report.get("buyer_brief") or {}
    path = list(brief.get("open_first_path") or [])
    export_ready = len(path) >= 4 and [
        str(item.get("stage") or "") for item in path[:4]
    ] == [
        "orient",
        "prove",
        "close",
        "verify",
    ]
    report: dict[str, Any] = {
        "generated_at": buyer_brief_report.get("generated_at"),
        "client": buyer_brief_report.get("client") or {},
        "decision": {
            "status": "ready" if export_ready else "blocked",
            "score": _score(buyer_brief_report) or 0,
            "headline": (
                "Open-First Path is export-ready: orient, prove, close and verify steps are materialized."
                if export_ready
                else "Open-First Path could not be materialized from Buyer Brief."
            ),
        },
        "summary": {
            "steps": len(path),
            "stages": [str(item.get("stage") or "") for item in path],
            "routes": [str(item.get("route") or "") for item in path],
            "files": [str(item.get("file") or "") for item in path],
        },
        "open_first_path": path,
        "source_report": {
            "id": "buyer-brief",
            "route": "/",
            "filename": "buyer-brief.md",
            "sha256": _sha256_text(str(buyer_brief_report.get("markdown") or "")),
        },
        "caveats": [
            "Open-First Path is an orientation contract; deep evidence remains in the referenced artifacts.",
            "The verify step depends on the separate Verification Packet ZIP generated from archive endpoints.",
        ],
    }
    report["markdown"] = _open_first_path_markdown(report)
    return report


def _manifest(artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    for item in artifacts:
        files.append(
            {
                "id": item["id"],
                "filename": f"{item['filename']}.json",
                "media_type": "application/json",
                "sha256": item["json_sha256"],
            }
        )
        if item["markdown"]:
            files.append(
                {
                    "id": item["id"],
                    "filename": f"{item['filename']}.md",
                    "media_type": "text/markdown",
                    "sha256": item["markdown_sha256"],
                }
            )
    return {"files": files, "total_files": len(files)}


_PROCUREMENT_REQUIRED_ARTIFACTS: tuple[dict[str, str], ...] = (
    {
        "id": "open-first-path",
        "title": "Open-First Path",
        "filename": "open-first-path.md",
        "route": "/",
        "role": "Buying committee",
        "why": "Four-step orient/prove/close/verify path that keeps the first meeting from becoming a product maze.",
    },
    {
        "id": "buyer-brief",
        "title": "Buyer Brief",
        "filename": "buyer-brief.md",
        "route": "/",
        "role": "Buying committee",
        "why": "First-minute room map: primary motion, role cards, proof readiness and meeting flow.",
    },
    {
        "id": "buyer-room-plan",
        "title": "Buyer Room Plan",
        "filename": "buyer-room-plan.md",
        "route": "/",
        "role": "Presenter / buying committee",
        "why": "Single live-room operating plan: first route, proof file, close question and send files.",
    },
    {
        "id": "buyer-pulse",
        "title": "Buyer Pulse",
        "filename": "buyer-pulse.md",
        "route": "/",
        "role": "Buying committee",
        "why": "First-screen purchase status, AI-rent line, proof routes and governance gates.",
    },
    {
        "id": "board-pack",
        "title": "Board Pack",
        "filename": "board-pack.md",
        "route": "/board-pack",
        "role": "Director / sponsor",
        "why": "Board-ready value, risks, paid ask and approval gates.",
    },
    {
        "id": "commercial-offer-studio",
        "title": "Commercial Offer Studio",
        "filename": "commercial-offer-studio.md",
        "route": "/commercial-offer-studio",
        "role": "Procurement / finance",
        "why": "Offer, purchase model, procurement dossier and red lines.",
    },
    {
        "id": "enterprise-trust-center",
        "title": "Enterprise Trust Center",
        "filename": "enterprise-trust-center.md",
        "route": "/enterprise-trust-center",
        "role": "Security / architect",
        "why": "Locality, security posture, SBOM/offline caveats and trust proof.",
    },
    {
        "id": "security-questionnaire",
        "title": "Security Questionnaire",
        "filename": "rentgen-security-questionnaire.md",
        "route": "/enterprise-trust-center",
        "role": "Security / procurement",
        "why": "Buyer-forwardable questionnaire with owners, send files, blockers and verification steps.",
    },
    {
        "id": "business-case",
        "title": "Business Case",
        "filename": "business-case.md",
        "route": "/business-case",
        "role": "Director / finance",
        "why": "Visible first-year value and AI subscription displacement story.",
    },
    {
        "id": "role-report-developer",
        "title": "Developer Role Report",
        "filename": "rentgen-developer-report.md",
        "route": "/",
        "role": "Developer",
        "why": "Developer-facing proof: changed module, impact, tests and safe next action.",
    },
    {
        "id": "role-report-architect",
        "title": "Architect Role Report",
        "filename": "rentgen-architect-report.md",
        "route": "/",
        "role": "Architect",
        "why": "Architecture-facing proof: blast radius, metadata, caveats and topology route.",
    },
    {
        "id": "role-report-director",
        "title": "Director Role Report",
        "filename": "rentgen-director-report.md",
        "route": "/",
        "role": "Director / sponsor",
        "why": "Director-facing proof: go/no-go, value, local asset story and next buying motion.",
    },
    {
        "id": "role-report-qa",
        "title": "QA Role Report",
        "filename": "rentgen-qa-report.md",
        "route": "/",
        "role": "QA / release",
        "why": "QA-facing proof: test matrix, release gate and evidence route.",
    },
    {
        "id": "role-report-ops",
        "title": "Ops Role Report",
        "filename": "rentgen-ops-report.md",
        "route": "/",
        "role": "Operations",
        "why": "Ops-facing proof: platform, incidents, lock radar and offline readiness.",
    },
    {
        "id": "role-report-vendor",
        "title": "Vendor Role Report",
        "filename": "rentgen-vendor-report.md",
        "route": "/",
        "role": "Vendor / partner",
        "why": "Vendor-facing proof: pre-sale audit, work packages and commercial next step.",
    },
    {
        "id": "pilot-launchpad",
        "title": "Pilot Launchpad",
        "filename": "pilot-launchpad.md",
        "route": "/pilot-launchpad",
        "role": "Project owner",
        "why": "Day 0/7/30 acceptance plan, buyer commitments and activation gates.",
    },
    {
        "id": "launch-room",
        "title": "Launch Room",
        "filename": "launch-room.md",
        "route": "/launch-room",
        "role": "Buying committee",
        "why": "Single start cockpit for close, activate, govern and realize steps.",
    },
    {
        "id": "killer-demo",
        "title": "Killer Demo Path",
        "filename": "killer-demo.md",
        "route": "/killer-demo",
        "role": "Presenter / sponsor",
        "why": "Role-specific proof moments, committee close board and send packet.",
    },
    {
        "id": "governance-proof",
        "title": "Governance Proof",
        "filename": "governance-proof.md",
        "route": "/approvals",
        "role": "Security / change owner",
        "why": "Approval records, audit-chain verification and recent governance events.",
    },
    {
        "id": "safe-autopilot",
        "title": "Safe Autopilot",
        "filename": "safe-autopilot.md",
        "route": "/safe-autopilot",
        "role": "Developer / QA",
        "why": "Read-only plan, diff blueprint, test proof and approval handoff.",
    },
    {
        "id": "test-factory",
        "title": "Test Factory",
        "filename": "test-factory.md",
        "route": "/testing",
        "role": "Developer / QA",
        "why": "Run-now test plan and regression evidence for changed modules.",
    },
    {
        "id": "productization",
        "title": "Productization Readiness",
        "filename": "productization-readiness.md",
        "route": "/productization",
        "role": "IT operations / security",
        "why": "Offline delivery, hardening and signed-archive readiness caveats.",
    },
)


def _file_sha(manifest: dict[str, Any], filename: str) -> str:
    for item in manifest.get("files", []):
        if item.get("filename") == filename:
            return str(item.get("sha256") or "")
    return ""


def _killer_demo_handoff_bridge(
    *, bundle_id: str, artifact: dict[str, Any] | None
) -> dict[str, Any]:
    available = artifact is not None
    files = [
        "OPEN_FIRST_KILLER_DEMO.md",
        "killer-demo-manifest.json",
        "proof-packet.json",
        MEETING_CLOSE_RECEIPT_MD,
        MEETING_CLOSE_RECEIPT_JSON,
        POST_DEMO_ACTIVATION_MD,
        POST_DEMO_ACTIVATION_JSON,
    ]
    return {
        "id": "killer-demo-linked-archive",
        "title": "Linked Killer Demo ZIP",
        "status": "ready" if available else "missing",
        "available": available,
        "route": "/killer-demo",
        "archive_endpoint": "/api/v1/killer-demo/archive",
        "archive_filename": f"{bundle_id}-killer-demo-archive.zip",
        "archive_hash_header": KILLER_DEMO_ARCHIVE_HASH_HEADER,
        "open_first_file": "OPEN_FIRST_KILLER_DEMO.md",
        "manifest_file": "killer-demo-manifest.json",
        "proof_packet_file": "proof-packet.json",
        "files": files,
        "post_demo_files": [
            MEETING_CLOSE_RECEIPT_MD,
            MEETING_CLOSE_RECEIPT_JSON,
            POST_DEMO_ACTIVATION_MD,
            POST_DEMO_ACTIVATION_JSON,
        ],
        "recipient_overlays": [
            {
                "role": "Director / sponsor",
                "source_archive": "linked Killer Demo ZIP",
                "send_files": [MEETING_CLOSE_RECEIPT_MD, POST_DEMO_ACTIVATION_MD],
                "reason": "Meeting decision receipt and paid-start activation packet after the live room.",
            },
            {
                "role": "Architect / CTO",
                "source_archive": "linked Killer Demo ZIP",
                "send_files": [POST_DEMO_ACTIVATION_MD],
                "reason": "Day 0/7/30 technical activation gates and accepted caveats.",
            },
            {
                "role": "Security / procurement",
                "source_archive": "linked Killer Demo ZIP",
                "send_files": [
                    "killer-demo-manifest.json",
                    MEETING_CLOSE_RECEIPT_JSON,
                    POST_DEMO_ACTIVATION_JSON,
                ],
                "reason": "Hashable post-demo overlays that should be recorded next to the Evidence Bundle hash.",
            },
            {
                "role": "Developer / QA",
                "source_archive": "linked Killer Demo ZIP",
                "send_files": ["OPEN_FIRST_KILLER_DEMO.md"],
                "reason": "Role-specific proof path for the technical room.",
            },
        ],
        "buyer_line": (
            "Use this linked ZIP after the live demo for meeting close, activation handoff and role packet overlays. "
            "The Evidence Bundle ZIP remains the source evidence archive; the linked Killer Demo ZIP carries the current close-room overlays."
        ),
        "verification_steps": [
            {
                "id": "download-killer-demo-zip",
                "owner": "Presenter / sponsor",
                "action": "Download /api/v1/killer-demo/archive when the buyer asks for the close packet.",
                "expected": "The archive opens with OPEN_FIRST_KILLER_DEMO.md and contains the close receipt plus activation handoff.",
            },
            {
                "id": "hash-killer-demo-zip",
                "owner": "Security / procurement",
                "action": f"Record {KILLER_DEMO_ARCHIVE_HASH_HEADER} next to the Evidence Bundle archive hash.",
                "expected": "Both hashes are stored in the same intake or procurement ticket.",
            },
        ],
    }


def _verification_packet_contract(*, ready: bool) -> dict[str, Any]:
    return {
        "id": "archive-verification-packet",
        "title": "Verification Packet ZIP",
        "status": "ready" if ready else "review_required",
        "ready": ready,
        "route": "/evidence-bundle",
        "endpoint": ARCHIVE_VERIFICATION_PACKET_ENDPOINT,
        "filename": ARCHIVE_VERIFICATION_PACKET_ZIP,
        "hash_header": ARCHIVE_VERIFICATION_PACKET_HASH_HEADER,
        "open_first_file": ARCHIVE_VERIFICATION_PACKET_OPEN_FIRST,
        "contains": [
            ARCHIVE_VERIFICATION_PACKET_OPEN_FIRST,
            "dual-archive-verification-packet.json",
            "dual-archive-verification-packet.md",
            "evidence-archive-verification-receipt.json",
            "evidence-archive-verification-receipt.md",
            "killer-demo-archive-verification-receipt.json",
            "killer-demo-archive-verification-receipt.md",
            "hash-table.json",
        ],
        "boundary": "Generated control ZIP; attach next to Evidence Bundle ZIP and Killer Demo ZIP, not inside either archive.",
    }


def _procurement_handoff_markdown(handoff: dict[str, Any]) -> str:
    receipt = handoff.get("commercial_assumptions") or {}
    killer_demo_handoff = handoff.get("killer_demo_handoff") or {}
    verification_packet = handoff.get("verification_packet") or {}
    lines = [
        "# Procurement Handoff",
        "",
        f"Status: **{handoff.get('status', 'unknown')}**",
        f"Ready to forward: **{handoff.get('ready_to_forward', False)}**",
        f"Bundle: `{handoff.get('bundle_id', '')}`",
        f"Bundle SHA-256: `{handoff.get('bundle_sha256', '')}`",
        f"Archive endpoint: `{handoff.get('archive_endpoint', '')}`",
        f"Open first: `{handoff.get('open_first_file', 'OPEN_FIRST.md')}`",
        "Archive file manifest: `archive-manifest.json`",
        "Archive acceptance receipt: `archive-acceptance-receipt.md`",
        f"Verification packet: `{verification_packet.get('filename', ARCHIVE_VERIFICATION_PACKET_ZIP)}`",
        "",
        "## Buyer Line",
        "",
        str(handoff.get("buyer_line") or ""),
        "",
        "## Commercial Assumptions",
        "",
        f"- Source: **{receipt.get('source', 'unknown')}**",
        f"- AI/month: **{receipt.get('monthly_ai_rent_label', 'not provided')}**",
        f"- Three-year AI rent: **{receipt.get('three_year_ai_rent_label', 'not provided')}**",
        f"- Local license anchor: **{receipt.get('local_license_anchor_label', 'not provided')}**",
        f"- Break-even: **{receipt.get('break_even_label', 'not provided')}**",
        f"- Decision line: {receipt.get('decision_line', '')}",
        "",
        "## Verification Steps",
        "",
    ]
    for item in handoff.get("verification_steps", []):
        lines.append(
            f"- **{item.get('owner', '')}**: {item.get('action', '')} Expected: {item.get('expected', '')}"
        )
    lines.extend(["", "## Recipients", ""])
    for item in handoff.get("recipients", []):
        files = ", ".join(item.get("send_files") or [])
        packet_file = item.get("packet_file") or role_packet_filename(
            str(item.get("role") or "stakeholder")
        )
        forwarding_file = _forwarding_note_filename(str(packet_file))
        lines.append(
            f"- **{item.get('role', '')}**: {item.get('decision', '')}. "
            f"Packet: `{packet_file}`. Forwarding note: `{forwarding_file}`. Files: {files}"
        )
    if killer_demo_handoff:
        lines.extend(
            [
                "",
                "## Linked Killer Demo ZIP",
                "",
                str(killer_demo_handoff.get("buyer_line") or ""),
                "",
                f"- Status: **{killer_demo_handoff.get('status', 'unknown')}**",
                f"- Route: `{killer_demo_handoff.get('route', '')}`",
                f"- Archive endpoint: `{killer_demo_handoff.get('archive_endpoint', '')}`",
                f"- Archive filename: `{killer_demo_handoff.get('archive_filename', '')}`",
                f"- Open first: `{killer_demo_handoff.get('open_first_file', '')}`",
                "",
                "Post-demo files in the linked ZIP:",
            ]
        )
        for filename in killer_demo_handoff.get("post_demo_files", []):
            lines.append(f"- `{filename}`")
        overlays = killer_demo_handoff.get("recipient_overlays") or []
        if overlays:
            lines.extend(["", "Role overlays from the linked ZIP:"])
            for overlay in overlays:
                files = ", ".join(f"`{item}`" for item in overlay.get("send_files", []))
                lines.append(
                    f"- **{overlay.get('role', '')}**: {files}. {overlay.get('reason', '')}"
                )
    if verification_packet:
        lines.extend(
            [
                "",
                "## Verification Packet ZIP",
                "",
                str(verification_packet.get("boundary") or ""),
                "",
                f"- Status: **{verification_packet.get('status', 'unknown')}**",
                f"- Endpoint: `{verification_packet.get('endpoint', ARCHIVE_VERIFICATION_PACKET_ENDPOINT)}`",
                f"- Filename: `{verification_packet.get('filename', ARCHIVE_VERIFICATION_PACKET_ZIP)}`",
                f"- Hash header: `{verification_packet.get('hash_header', ARCHIVE_VERIFICATION_PACKET_HASH_HEADER)}`",
                f"- Open first: `{verification_packet.get('open_first_file', ARCHIVE_VERIFICATION_PACKET_OPEN_FIRST)}`",
                "",
                "Contains:",
            ]
        )
        for filename in verification_packet.get("contains", []):
            lines.append(f"- `{filename}`")
    lines.extend(["", "## Required Files", ""])
    for item in handoff.get("required_files", []):
        mark = "present" if item.get("present") else "missing"
        lines.append(
            f"- **{item.get('title', '')}** `{item.get('filename', '')}` - {mark}"
        )
    blockers = handoff.get("blockers") or []
    if blockers:
        lines.extend(["", "## Blockers", ""])
        lines.extend(f"- {item}" for item in blockers)
    review_items = handoff.get("review_items") or []
    if review_items:
        lines.extend(["", "## Review Items", ""])
        lines.extend(
            f"- {item.get('title', '')}: {item.get('status', '')}"
            for item in review_items
        )
    return "\n".join(lines)


def _archive_acceptance_receipt_markdown(receipt: dict[str, Any]) -> str:
    lines = [
        "# Archive Acceptance Receipt",
        "",
        f"Status: **{receipt.get('status', 'unknown')}**",
        f"Bundle: `{receipt.get('bundle_id', '')}`",
        f"Client: **{receipt.get('client_name', '')}**",
        "",
        "## Buyer Line",
        "",
        str(receipt.get("buyer_line") or ""),
        "",
        "## Archives",
        "",
    ]
    for archive in receipt.get("archives", []):
        lines.extend(
            [
                f"### {archive.get('title', '')}",
                "",
                f"- Status: **{archive.get('status', 'unknown')}**",
                f"- Endpoint: `{archive.get('endpoint', '')}`",
                f"- Filename: `{archive.get('filename', '')}`",
                f"- Hash header: `{archive.get('hash_header', '')}`",
                f"- Open first: `{archive.get('open_first_file', '')}`",
                f"- Manifest: `{archive.get('manifest_file', '')}`",
            ]
        )
        if archive.get("archive_manifest_file"):
            lines.append(
                f"- Archive manifest: `{archive.get('archive_manifest_file', '')}`"
            )
        lines.extend(
            ["- Boundary: " + str(archive.get("boundary", "")), "", "Contains:"]
        )
        for filename in archive.get("contains", []):
            lines.append(f"- `{filename}`")
        excludes = archive.get("excludes") or []
        if excludes:
            lines.extend(["", "Not standalone files in this archive:"])
            for filename in excludes:
                lines.append(f"- `{filename}`")
        lines.append("")

    overlays = receipt.get("role_overlays") or []
    if overlays:
        lines.extend(["## Role Overlays", ""])
        for overlay in overlays:
            files = ", ".join(f"`{item}`" for item in overlay.get("send_files", []))
            lines.append(
                f"- **{overlay.get('role', '')}** from {overlay.get('source_archive', 'linked archive')}: {files}. {overlay.get('reason', '')}"
            )
        lines.append("")

    control_packets = receipt.get("control_packets") or []
    if control_packets:
        lines.extend(["## Control Packets", ""])
        for packet in control_packets:
            lines.extend(
                [
                    f"### {packet.get('title', '')}",
                    "",
                    f"- Status: **{packet.get('status', 'unknown')}**",
                    f"- Endpoint: `{packet.get('endpoint', '')}`",
                    f"- Filename: `{packet.get('filename', '')}`",
                    f"- Hash header: `{packet.get('hash_header', '')}`",
                    f"- Open first: `{packet.get('open_first_file', '')}`",
                    f"- Boundary: {packet.get('boundary', '')}",
                    "",
                    "Contains:",
                ]
            )
            for filename in packet.get("contains", []):
                lines.append(f"- `{filename}`")
            lines.append("")

    lines.extend(["## Acceptance Steps", ""])
    for step in receipt.get("acceptance_steps", []):
        lines.append(
            f"{step.get('step', '')}. **{step.get('owner', '')}**: {step.get('action', '')} Expected: {step.get('expected', '')}"
        )
    return "\n".join(lines).strip()


def _archive_acceptance_receipt(report: dict[str, Any]) -> dict[str, Any]:
    handoff = report.get("procurement_handoff") or {}
    killer_demo_handoff = handoff.get("killer_demo_handoff") or {}
    verification_packet = handoff.get("verification_packet") or {}
    post_demo_files = list(killer_demo_handoff.get("post_demo_files") or [])
    evidence_archive = {
        "id": "evidence-archive",
        "title": "Evidence Bundle ZIP",
        "status": "ready" if handoff.get("ready_to_forward") else "review_required",
        "endpoint": handoff.get("archive_endpoint")
        or "/api/v1/evidence-bundle/archive",
        "filename": handoff.get("archive_filename")
        or f"{report.get('bundle_id', 'rentgen')}-evidence-archive.zip",
        "hash_header": handoff.get("archive_hash_header") or "X-Archive-Sha256",
        "open_first_file": handoff.get("open_first_file") or "OPEN_FIRST.md",
        "manifest_file": "manifest.json",
        "archive_manifest_file": "archive-manifest.json",
        "contains": [
            "OPEN_FIRST.md",
            "manifest.json",
            "archive-manifest.json",
            "VERIFY_ARCHIVE.md",
            "procurement-handoff.md",
            "procurement-handoff.json",
            "archive-acceptance-receipt.md",
            "archive-acceptance-receipt.json",
            "open-first-path.md",
            "buyer-room-plan.md",
            "buyer-brief.md",
            "buyer-pulse.md",
        ]
        + [
            str(
                recipient.get("packet_file")
                or role_packet_filename(str(recipient.get("role") or "stakeholder"))
            )
            for recipient in handoff.get("recipients", [])
        ]
        + [
            _forwarding_note_filename(
                str(
                    recipient.get("packet_file")
                    or role_packet_filename(str(recipient.get("role") or "stakeholder"))
                )
            )
            for recipient in handoff.get("recipients", [])
        ],
        "excludes": post_demo_files,
        "boundary": "Source evidence, procurement handoff, required files and generated artifacts.",
    }
    killer_archive = {
        "id": "linked-killer-demo-archive",
        "title": "Linked Killer Demo ZIP",
        "status": killer_demo_handoff.get("status") or "missing",
        "endpoint": killer_demo_handoff.get("archive_endpoint")
        or "/api/v1/killer-demo/archive",
        "filename": killer_demo_handoff.get("archive_filename")
        or f"{report.get('bundle_id', 'rentgen')}-killer-demo-archive.zip",
        "hash_header": killer_demo_handoff.get("archive_hash_header")
        or KILLER_DEMO_ARCHIVE_HASH_HEADER,
        "open_first_file": killer_demo_handoff.get("open_first_file")
        or "OPEN_FIRST_KILLER_DEMO.md",
        "manifest_file": killer_demo_handoff.get("manifest_file")
        or "killer-demo-manifest.json",
        "contains": list(killer_demo_handoff.get("files") or []),
        "excludes": [],
        "boundary": "Live-demo close overlays, role packets, receipt, activation handoff and proof-packet manifest.",
    }
    receipt = {
        "bundle_id": report.get("bundle_id"),
        "generated_at": report.get("generated_at"),
        "client_name": (report.get("client") or {}).get("name"),
        "status": "ready"
        if handoff.get("ready_to_forward") and killer_demo_handoff.get("available")
        else "review_required",
        "buyer_line": (
            "Record both archive downloads in the same procurement ticket: Evidence Bundle ZIP proves source evidence; "
            "linked Killer Demo ZIP proves the live close, meeting receipt and activation handoff; "
            "Verification Packet ZIP proves the two archives as a checked pair."
        ),
        "archives": [evidence_archive, killer_archive],
        "control_packets": [verification_packet] if verification_packet else [],
        "role_overlays": list(killer_demo_handoff.get("recipient_overlays") or []),
        "acceptance_steps": [
            {
                "id": "record-evidence-archive",
                "step": 1,
                "owner": "Procurement / security",
                "action": "Download the Evidence Bundle ZIP and record X-Archive-Sha256.",
                "expected": "The ticket includes evidence archive filename, hash header value and bundle id.",
            },
            {
                "id": "record-killer-demo-archive",
                "step": 2,
                "owner": "Presenter / sponsor",
                "action": "Download the linked Killer Demo ZIP after the close-room walkthrough.",
                "expected": f"The ticket includes Killer Demo filename and {KILLER_DEMO_ARCHIVE_HASH_HEADER}.",
            },
            {
                "id": "forward-correct-boundary",
                "step": 3,
                "owner": "Buying committee",
                "action": "Forward role files from the correct archive boundary only.",
                "expected": "Evidence files come from Evidence Bundle ZIP; receipt and activation overlays come from Killer Demo ZIP.",
            },
        ],
    }
    receipt["markdown"] = _archive_acceptance_receipt_markdown(receipt)
    return receipt


def _open_first_markdown(report: dict[str, Any]) -> str:
    handoff = report.get("procurement_handoff") or {}
    receipt = report.get("commercial_assumptions") or {}
    killer_demo_handoff = handoff.get("killer_demo_handoff") or {}
    verification_packet = handoff.get("verification_packet") or {}
    lines = [
        "# Open First",
        "",
        "This archive is a buyer-forwardable 1C Rentgen proof packet. It is generated from local evidence, not from screenshots.",
        "",
        f"Client: **{report.get('client', {}).get('name', 'Demo client')}**",
        f"Bundle: `{report.get('bundle_id', '')}`",
        f"Decision: **{(report.get('decision') or {}).get('status', 'unknown')}** / score **{(report.get('decision') or {}).get('score', '')}**",
        f"Ready to forward: **{handoff.get('ready_to_forward', False)}**",
        f"Bundle SHA-256: `{(report.get('manifest') or {}).get('bundle_sha256', '')}`",
        "",
        "## Commercial Assumptions",
        "",
        f"- Source: **{receipt.get('source', 'unknown')}**",
        f"- AI/month: **{receipt.get('monthly_ai_rent_label', 'not provided')}**",
        f"- Three-year AI rent: **{receipt.get('three_year_ai_rent_label', 'not provided')}**",
        f"- Local license anchor: **{receipt.get('local_license_anchor_label', 'not provided')}**",
        f"- Break-even: **{receipt.get('break_even_label', 'not provided')}**",
        f"- Decision line: {receipt.get('decision_line', '')}",
        "",
        "## Start Here",
        "",
        "1. Open `open-first-path.md` for the orient/prove/close/verify route.",
        "2. Open `buyer-room-plan.md` for the single first route, proof file and close question.",
        "3. Open `procurement-handoff.md` for owner, gate and send-file decisions.",
        "4. Open `manifest.json` and verify SHA-256 before the packet is accepted.",
        "5. Open `archive-manifest.json` to verify generated ZIP files, role packets and forwarding notes.",
        "6. Open `VERIFY_ARCHIVE.md` for the exact archive verification checklist.",
        "7. Open `archive-acceptance-receipt.md` before recording the Evidence ZIP and linked Killer Demo ZIP in procurement.",
        f"8. Download `{ARCHIVE_VERIFICATION_PACKET_ZIP}` as the separate control ZIP before the ticket is accepted.",
        "9. Send each stakeholder only the files listed in their role packet below.",
        "10. Treat risk/review items as scope or paid hardening work before production approval.",
        "",
        "## Role Packets",
        "",
    ]
    for recipient in handoff.get("recipients", []):
        files = ", ".join(f"`{item}`" for item in recipient.get("send_files", []))
        routes = ", ".join(f"`{item}`" for item in recipient.get("routes", []))
        packet_file = recipient.get("packet_file") or role_packet_filename(
            str(recipient.get("role") or "stakeholder")
        )
        forwarding_file = _forwarding_note_filename(str(packet_file))
        lines.append(
            f"- **{recipient.get('role', '')}**: {recipient.get('decision', '')}"
        )
        lines.append(f"  - Packet: `{packet_file}`")
        lines.append(f"  - Forwarding note: `{forwarding_file}`")
        lines.append(f"  - Files: {files}")
        lines.append(f"  - Routes: {routes}")

    if killer_demo_handoff:
        lines.extend(
            [
                "",
                "## Linked Killer Demo ZIP",
                "",
                str(killer_demo_handoff.get("buyer_line") or ""),
                "",
                f"- Route: `{killer_demo_handoff.get('route', '')}`",
                f"- Archive endpoint: `{killer_demo_handoff.get('archive_endpoint', '')}`",
                f"- Archive filename: `{killer_demo_handoff.get('archive_filename', '')}`",
                f"- Open first: `{killer_demo_handoff.get('open_first_file', '')}`",
                f"- Hash header: `{killer_demo_handoff.get('archive_hash_header', '')}`",
                "",
                "Post-demo overlay files:",
            ]
        )
        for filename in killer_demo_handoff.get("post_demo_files", []):
            lines.append(f"- `{filename}`")
        overlays = killer_demo_handoff.get("recipient_overlays") or []
        if overlays:
            lines.extend(["", "Role overlays from the linked ZIP:"])
            for overlay in overlays:
                files = ", ".join(f"`{item}`" for item in overlay.get("send_files", []))
                lines.append(
                    f"- **{overlay.get('role', '')}** from {overlay.get('source_archive', 'linked archive')}: {files}"
                )

    if verification_packet:
        lines.extend(
            [
                "",
                "## Verification Packet ZIP",
                "",
                str(verification_packet.get("boundary") or ""),
                "",
                f"- Endpoint: `{verification_packet.get('endpoint', ARCHIVE_VERIFICATION_PACKET_ENDPOINT)}`",
                f"- Filename: `{verification_packet.get('filename', ARCHIVE_VERIFICATION_PACKET_ZIP)}`",
                f"- Hash header: `{verification_packet.get('hash_header', ARCHIVE_VERIFICATION_PACKET_HASH_HEADER)}`",
                f"- Open first: `{verification_packet.get('open_first_file', ARCHIVE_VERIFICATION_PACKET_OPEN_FIRST)}`",
            ]
        )

    blockers = handoff.get("blockers") or []
    review_items = handoff.get("review_items") or []
    lines.extend(["", "## Readiness", ""])
    if blockers:
        lines.append("Do not forward as approved until these blockers are resolved:")
        lines.extend(f"- {item}" for item in blockers)
    elif review_items:
        lines.append("Forward for owner review; record decisions for these items:")
        for item in review_items[:10]:
            lines.append(
                f"- **{item.get('status', '')}** `{item.get('filename', '')}` {item.get('title', '')}"
            )
    else:
        lines.append(
            "No blockers or review items were detected in the procurement handoff."
        )

    lines.extend(["", "## Verification", ""])
    for step in handoff.get("verification_steps", []):
        lines.append(f"- **{step.get('owner', '')}**: {step.get('action', '')}")

    lines.extend(["", "## Archive Contents To Notice", ""])
    for filename in handoff.get("archive_contents", [])[:24]:
        lines.append(f"- `{filename}`")
    return "\n".join(lines)


def _security_questionnaire_markdown(report: dict[str, Any]) -> str:
    questionnaire = report["security_questionnaire"]
    client = report.get("client") or {}
    lines = [
        "# 1C Rentgen Security Questionnaire",
        "",
        f"Client: **{client.get('name') or 'Demo client'}**",
        f"Questionnaire status: **{questionnaire['status']}**",
        f"Ready to send: **{questionnaire['ready_to_send']}**",
        f"Ready to approve: **{questionnaire['ready_to_approve']}**",
        f"Owner line: {questionnaire['owner_line']}",
        "",
        "## Sections",
        "",
    ]
    for item in questionnaire["sections"]:
        routes = ", ".join(f"`{route}`" for route in item.get("proof_routes", []))
        files = ", ".join(item.get("evidence_files", []))
        lines.append(
            f"- **{item['status']}** `{item['id']}` / {item['owner']} / {item['audience']}: {item['title']}"
        )
        lines.append(f"  - Answer: {item['answer']}")
        lines.append(f"  - Acceptance: {item['acceptance']}")
        lines.append(f"  - Routes: {routes}")
        lines.append(f"  - Evidence files: {files}")
        for blocker in item.get("blockers", []):
            lines.append(f"  - Blocker: {blocker}")
        for caveat in item.get("caveats", []):
            lines.append(f"  - Caveat: {caveat}")
    lines.extend(["", "## Send Files", ""])
    lines.extend(f"- {filename}" for filename in questionnaire.get("send_files", []))
    lines.extend(["", "## Verification Steps", ""])
    for item in questionnaire.get("verification_steps", []):
        lines.append(
            f"- **{item['owner']}** (`{item['route']}`): {item['action']} Expected: {item['expected']}"
        )
    high_risks = questionnaire.get("high_risks", [])
    if high_risks:
        lines.extend(["", "## High Risks", ""])
        for item in high_risks:
            lines.append(
                f"- **{item['severity']}** {item['owner']} (`{item['route']}`): {item['risk']}"
            )
    return "\n".join(lines)


def _security_questionnaire_report(report: dict[str, Any]) -> dict[str, Any]:
    questionnaire = report["security_questionnaire"]
    blocked = int(questionnaire.get("blocked_sections") or 0)
    watch = int(questionnaire.get("watch_sections") or 0)
    status = "blocked" if blocked else "watch" if watch else "ready"
    score = max(0, 100 - blocked * 25 - watch * 5)
    payload = {
        "generated_at": report.get("generated_at"),
        "client": report.get("client") or {},
        "decision": {
            "status": status,
            "score": score,
            "headline": questionnaire.get("owner_line")
            or "Security questionnaire is ready for buyer review.",
        },
        "summary": {
            "sections": len(questionnaire.get("sections") or []),
            "ready_sections": int(questionnaire.get("ready_sections") or 0),
            "watch_sections": watch,
            "blocked_sections": blocked,
            "send_files": len(questionnaire.get("send_files") or []),
            "verification_steps": len(questionnaire.get("verification_steps") or []),
            "high_risks": len(questionnaire.get("high_risks") or []),
            "ready_to_send": bool(questionnaire.get("ready_to_send")),
            "ready_to_approve": bool(questionnaire.get("ready_to_approve")),
        },
        "questionnaire_status": questionnaire.get("status"),
        "security_questionnaire": questionnaire,
        "source_report": {
            "id": "enterprise-trust-center",
            "route": "/enterprise-trust-center",
            "filename": "enterprise-trust-center.md",
            "sha256": report.get("markdown_sha256") or "",
        },
        "caveats": list(report.get("caveats") or [])[:10],
    }
    payload["markdown"] = _security_questionnaire_markdown(payload)
    return payload


def _build_procurement_handoff(
    *,
    bundle_id: str,
    generated_at: str,
    client_name: str,
    artifacts: list[dict[str, Any]],
    manifest: dict[str, Any],
    risky: list[dict[str, Any]],
    watch: list[dict[str, Any]],
    commercial_assumptions: dict[str, Any] | None = None,
) -> dict[str, Any]:
    artifact_by_id = {str(item.get("id")): item for item in artifacts}
    required_files: list[dict[str, Any]] = []
    for required in _PROCUREMENT_REQUIRED_ARTIFACTS:
        artifact = artifact_by_id.get(required["id"])
        sha256 = _file_sha(manifest, required["filename"])
        present = artifact is not None and bool(sha256)
        required_files.append(
            {
                **required,
                "present": present,
                "status": "present" if present else "missing",
                "sha256": sha256,
                "artifact_status": str((artifact or {}).get("status") or "missing"),
            }
        )

    missing = [item for item in required_files if not item["present"]]
    risk_reviews = [
        {
            "id": item["id"],
            "title": item["title"],
            "status": item["status"],
            "route": item["route"],
            "filename": item["filename"],
        }
        for item in risky
    ]
    watch_reviews = [
        {
            "id": item["id"],
            "title": item["title"],
            "status": item["status"],
            "route": item["route"],
            "filename": item["filename"],
        }
        for item in watch[:8]
    ]
    blockers = [
        f"Missing required file: {item['filename']} ({item['title']})"
        for item in missing
    ]
    status = (
        "blocked"
        if blockers
        else "review_required"
        if risk_reviews
        else "ready_to_forward"
    )
    ready_to_forward = status == "ready_to_forward"
    required_present = len(required_files) - len(missing)
    governance = artifact_by_id.get("governance-proof")
    offer = artifact_by_id.get("commercial-offer-studio")
    board = artifact_by_id.get("board-pack")
    productization = artifact_by_id.get("productization")
    killer_demo_handoff = _killer_demo_handoff_bridge(
        bundle_id=bundle_id, artifact=artifact_by_id.get("killer-demo")
    )
    verification_packet = _verification_packet_contract(
        ready=bool(killer_demo_handoff["available"])
    )
    gates = [
        {
            "id": "required-files",
            "label": "Required proof files",
            "status": "pass" if not missing else "blocked",
            "detail": f"{required_present}/{len(required_files)} required files present",
            "route": "/evidence-bundle",
        },
        {
            "id": "manifest",
            "label": "Manifest SHA-256",
            "status": "pass"
            if manifest.get("bundle_sha256") and manifest.get("files")
            else "blocked",
            "detail": "manifest.json carries SHA-256 for every artifact file",
            "route": "/evidence-bundle",
        },
        {
            "id": "governance",
            "label": "Approval and audit proof",
            "status": "pass"
            if governance and governance.get("status") == "ready"
            else "watch"
            if governance
            else "blocked",
            "detail": "governance-proof.md plus /approvals and /audit routes",
            "route": "/approvals",
        },
        {
            "id": "commercial",
            "label": "Commercial close packet",
            "status": "pass" if offer and board else "blocked",
            "detail": "Offer Studio and Board Pack are included",
            "route": "/commercial-offer-studio",
        },
        {
            "id": "delivery",
            "label": "Delivery readiness",
            "status": "pass" if productization else "watch",
            "detail": "Productization readiness and offline caveats travel with the archive",
            "route": "/productization",
        },
        {
            "id": "risk-review",
            "label": "Risk review",
            "status": "pass" if not risk_reviews else "review",
            "detail": f"{len(risk_reviews)} risk artifacts require owner decision",
            "route": "/evidence-bundle",
        },
        {
            "id": "killer-demo-zip",
            "label": "Killer Demo ZIP bridge",
            "status": "pass" if killer_demo_handoff["available"] else "blocked",
            "detail": "Linked close-room archive carries OPEN_FIRST_KILLER_DEMO.md, receipt and activation handoff",
            "route": "/killer-demo",
        },
        {
            "id": "archive-verification-packet",
            "label": "Verification Packet ZIP",
            "status": "pass" if verification_packet["ready"] else "blocked",
            "detail": "Control ZIP verifies Evidence and Killer Demo archives as one pair with receipts and hash table",
            "route": "/evidence-bundle",
        },
    ]
    recipients = [
        {
            "role": "Director / sponsor",
            "decision": "Approve paid pilot or purchase motion from value, board ask and outcome proof.",
            "send_files": [
                "open-first-path.md",
                "buyer-brief.md",
                "buyer-room-plan.md",
                "buyer-pulse.md",
                "board-pack.md",
                "business-case.md",
                "rentgen-director-report.md",
                "outcome-ledger.md",
                "commercial-offer-studio.md",
                ARCHIVE_VERIFICATION_PACKET_ZIP,
            ],
            "routes": [
                "/board-pack",
                "/business-case",
                "/outcome-ledger",
                "/commercial-offer-studio",
            ],
        },
        {
            "role": "Architect / CTO",
            "decision": "Accept architecture, platform and rollout risks before technical scope is signed.",
            "send_files": [
                "open-first-path.md",
                "buyer-brief.md",
                "buyer-room-plan.md",
                "enterprise-trust-center.md",
                "rentgen-security-questionnaire.md",
                "rentgen-architect-report.md",
                "platform-doctor.md",
                "productization-readiness.md",
                "launch-room.md",
                ARCHIVE_VERIFICATION_PACKET_ZIP,
            ],
            "routes": [
                "/enterprise-trust-center",
                "/platform-doctor",
                "/productization",
                "/launch-room",
            ],
        },
        {
            "role": "Security / procurement",
            "decision": "Verify locality, governance chain, archive hash and required-file completeness.",
            "send_files": [
                "manifest.json",
                "procurement-handoff.md",
                "open-first-path.md",
                "buyer-brief.md",
                "buyer-room-plan.md",
                "buyer-pulse.md",
                "governance-proof.md",
                "enterprise-trust-center.md",
                "rentgen-security-questionnaire.md",
                ARCHIVE_VERIFICATION_PACKET_ZIP,
            ],
            "routes": [
                "/evidence-bundle",
                "/approvals",
                "/audit",
                "/enterprise-trust-center",
            ],
        },
        {
            "role": "Developer / QA",
            "decision": "Check changed-module proof, tests, safe diff blueprint and manual approval handoff.",
            "send_files": [
                "open-first-path.md",
                "buyer-brief.md",
                "buyer-room-plan.md",
                "safe-autopilot.md",
                "test-factory.md",
                "rentgen-developer-report.md",
                "rentgen-qa-report.md",
                "killer-demo.md",
                "configuration-intake.md",
                ARCHIVE_VERIFICATION_PACKET_ZIP,
            ],
            "routes": [
                "/safe-autopilot",
                "/testing",
                "/killer-demo",
                "/configurations",
            ],
        },
    ]
    for recipient in recipients:
        recipient["packet_file"] = role_packet_filename(
            str(recipient.get("role") or "stakeholder")
        )

    handoff: dict[str, Any] = {
        "bundle_id": bundle_id,
        "generated_at": generated_at,
        "client_name": client_name,
        "status": status,
        "ready_to_forward": ready_to_forward,
        "buyer_line": (
            "Forward the ZIP archive starting with OPEN_FIRST.md, manifest.json, archive-manifest.json, procurement-handoff.md "
            "and the role files; accept only after SHA-256, governance and missing-file checks are recorded."
        ),
        "archive_endpoint": "/api/v1/evidence-bundle/archive",
        "archive_filename": f"{bundle_id}-evidence-archive.zip",
        "bundle_sha256": str(manifest.get("bundle_sha256") or ""),
        "commercial_assumptions": commercial_assumptions or {},
        "archive_hash_header": "X-Archive-Sha256",
        "open_first_file": "OPEN_FIRST.md",
        "required_files": required_files,
        "missing_files": missing,
        "blockers": blockers,
        "review_items": risk_reviews + watch_reviews,
        "gates": gates,
        "recipients": recipients,
        "killer_demo_handoff": killer_demo_handoff,
        "verification_packet": verification_packet,
        "control_attachments": [ARCHIVE_VERIFICATION_PACKET_ZIP],
        "verification_steps": [
            {
                "id": "download",
                "owner": "Procurement / security",
                "action": "Download the ZIP from /api/v1/evidence-bundle/archive and record X-Archive-Sha256.",
                "expected": "The archive filename matches this bundle id and the archive hash is stored in the intake ticket.",
            },
            {
                "id": "manifest",
                "owner": "Security / QA",
                "action": "Open manifest.json and archive-manifest.json and verify each required/generated Markdown/JSON/TXT file SHA-256.",
                "expected": "Every required and generated file is present and matches its recorded SHA-256.",
            },
            {
                "id": "killer-demo-linked-archive",
                "owner": "Presenter / procurement",
                "action": "Download the linked Killer Demo ZIP when MEETING_CLOSE_RECEIPT.md or POST_DEMO_ACTIVATION_HANDOFF.md is sent.",
                "expected": "OPEN_FIRST_KILLER_DEMO.md, killer-demo-manifest.json, receipt and activation handoff are present and hashed separately from the Evidence Bundle ZIP.",
            },
            {
                "id": "archive-verification-packet",
                "owner": "Security / procurement",
                "action": f"Download {ARCHIVE_VERIFICATION_PACKET_ZIP} from {ARCHIVE_VERIFICATION_PACKET_ENDPOINT} and record {ARCHIVE_VERIFICATION_PACKET_HASH_HEADER}.",
                "expected": "The control ZIP contains dual archive verification, both verification receipts and hash-table.json.",
            },
            {
                "id": "governance",
                "owner": "Change owner",
                "action": "Open governance-proof.md, /approvals and /audit before approving write/apply work.",
                "expected": "Approval records exist and the audit hash chain verifies or has an accepted caveat.",
            },
            {
                "id": "commercial",
                "owner": "Director / procurement",
                "action": "Compare board-pack.md and commercial-offer-studio.md with the purchase order.",
                "expected": "Scope, pilot gates, buyer commitments and red lines are identical.",
            },
            {
                "id": "delivery",
                "owner": "Architect / operations",
                "action": "Check productization-readiness.md, enterprise-trust-center.md and rentgen-security-questionnaire.md for offline, platform and security caveats.",
                "expected": "Unresolved caveats are either accepted in scope or turned into paid hardening work.",
            },
        ],
        "archive_contents": [
            "OPEN_FIRST.md",
            "manifest.json",
            "archive-manifest.json",
            "VERIFY_ARCHIVE.md",
            "bundle.json",
            "evidence-bundle.md",
            "README.md",
            "procurement-handoff.json",
            "procurement-handoff.md",
            "archive-acceptance-receipt.json",
            "archive-acceptance-receipt.md",
        ]
        + [
            str(item.get("packet_file"))
            for item in recipients
            if item.get("packet_file")
        ]
        + [
            _forwarding_note_filename(str(item.get("packet_file")))
            for item in recipients
            if item.get("packet_file")
        ]
        + [item["filename"] for item in required_files if item["present"]],
    }
    handoff["markdown"] = _procurement_handoff_markdown(handoff)
    return handoff


def _bundle_markdown(report: dict[str, Any]) -> str:
    receipt = report.get("commercial_assumptions") or {}
    lines = [
        "# 1C Rentgen Evidence Bundle",
        "",
        f"Bundle: **{report['bundle_id']}**",
        f"Generated: {report['generated_at']}",
        f"Client: **{report['client']['name']}**",
        f"Status: **{report['decision']['status'].upper()}** / score **{report['decision']['score']}**",
        f"Bundle hash: `{report['manifest']['bundle_sha256']}`",
        "",
        "## Commercial Assumptions",
        "",
        f"- Source: **{receipt.get('source', 'unknown')}**",
        f"- AI/month: **{receipt.get('monthly_ai_rent_label', 'not provided')}**",
        f"- Three-year AI rent: **{receipt.get('three_year_ai_rent_label', 'not provided')}**",
        f"- Local license anchor: **{receipt.get('local_license_anchor_label', 'not provided')}**",
        f"- Break-even: **{receipt.get('break_even_label', 'not provided')}**",
        f"- Decision line: {receipt.get('decision_line', '')}",
        "",
        "## Artifacts",
        "",
    ]
    for item in report["artifacts"]:
        score = f" / {item['score']}" if item.get("score") is not None else ""
        lines.append(
            f"- **{item['title']}**: {item['status']}{score} · `{item['filename']}`"
        )
    handoff = report.get("procurement_handoff") or {}
    if handoff:
        lines.extend(["", "## Procurement Handoff", ""])
        lines.append(f"- Status: **{handoff.get('status', 'unknown')}**")
        lines.append(
            f"- Ready to forward: **{handoff.get('ready_to_forward', False)}**"
        )
        lines.append(f"- Archive endpoint: `{handoff.get('archive_endpoint', '')}`")
        lines.append(f"- Bundle SHA-256: `{handoff.get('bundle_sha256', '')}`")
        lines.append(
            f"- Required files: **{len(handoff.get('required_files') or [])}**"
        )
        lines.append(f"- Missing files: **{len(handoff.get('missing_files') or [])}**")
        lines.append(f"- Buyer line: {handoff.get('buyer_line', '')}")
        lines.extend(["", "### Verification", ""])
        for step in handoff.get("verification_steps", []):
            lines.append(f"- **{step.get('owner', '')}**: {step.get('action', '')}")
    archive_receipt = report.get("archive_acceptance_receipt") or {}
    if archive_receipt:
        lines.extend(["", "## Archive Acceptance Receipt", ""])
        lines.append(f"- Status: **{archive_receipt.get('status', 'unknown')}**")
        lines.append("- File: `archive-acceptance-receipt.md`")
        lines.append(f"- Buyer line: {archive_receipt.get('buyer_line', '')}")
        for archive in archive_receipt.get("archives", []):
            lines.append(
                f"- **{archive.get('title', '')}**: `{archive.get('endpoint', '')}` / `{archive.get('hash_header', '')}`"
            )
    lines.extend(["", "## Manifest", ""])
    for item in report["manifest"]["files"]:
        lines.append(f"- `{item['filename']}` `{item['sha256']}`")
    lines.extend(["", "## Caveats", ""])
    lines.extend(f"- {item}" for item in report["caveats"])
    return "\n".join(lines)


def _approval_record_digest(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    digest: list[dict[str, Any]] = []
    for item in records:
        digest.append(
            {
                "id": item.get("id"),
                "status": item.get("status"),
                "kind": item.get("kind"),
                "tool_name": item.get("tool_name"),
                "risk": item.get("risk"),
                "actor": item.get("actor"),
                "requested_by": item.get("requested_by"),
                "approved_by": item.get("approved_by"),
                "approval_ticket": item.get("approval_ticket"),
                "approval_reason": item.get("approval_reason"),
                "linked_record": item.get("linked_record") or {},
                "argument_constraints": item.get("argument_constraints") or {},
                "created_at": item.get("created_at"),
                "updated_at": item.get("updated_at"),
                "expires_at": item.get("expires_at"),
                "used_at": item.get("used_at"),
            }
        )
    return digest


def _status_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counts = {status: 0 for status in sorted(approval_workflow.APPROVAL_STATUSES)}
    for item in items:
        status = str(item.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    return counts


def _recent_audit_events(limit: int = 20) -> list[dict[str, Any]]:
    try:
        events = audit_log.list_events(limit=limit).get("items", [])
    except (
        Exception
    ) as exc:  # pragma: no cover - defensive: evidence export must stay available
        return [
            {
                "action": "audit.read_failed",
                "outcome": "error",
                "metadata": {"error": str(exc)},
            }
        ]
    return [
        {
            "id": item.get("id"),
            "timestamp": item.get("timestamp"),
            "actor": item.get("actor"),
            "action": item.get("action"),
            "target": item.get("target"),
            "category": item.get("category"),
            "outcome": item.get("outcome"),
            "correlation_id": item.get("correlation_id"),
            "prev_hash": item.get("prev_hash"),
        }
        for item in events
    ]


def _governance_decision(
    *,
    approvals: list[dict[str, Any]],
    audit_report: dict[str, Any],
) -> dict[str, Any]:
    broken = len(audit_report.get("broken") or [])
    audit_events = int(audit_report.get("total") or 0)
    legacy = int(audit_report.get("legacy") or 0)
    if broken:
        return {
            "status": "risk",
            "score": 55,
            "headline": "Governance proof found a broken audit hash-chain.",
        }
    if not audit_events:
        return {
            "status": "watch",
            "score": 76,
            "headline": "Governance proof is ready, but the audit log has no events yet.",
        }
    if not approvals:
        return {
            "status": "watch",
            "score": 82,
            "headline": "Audit chain is valid; create an approval record to complete the write-control proof.",
        }
    score = 94 if not legacy else 90
    return {
        "status": "ready",
        "score": score,
        "headline": "Approval records and tamper-evident audit proof are export-ready.",
    }


def _governance_caveats(
    *,
    approvals: list[dict[str, Any]],
    audit_report: dict[str, Any],
) -> list[str]:
    caveats: list[str] = []
    if not approvals:
        caveats.append(
            "No local approval records were found; request one from Safe Autopilot before a write/apply demo."
        )
    if int(audit_report.get("total") or 0) == 0:
        caveats.append(
            "The product audit log has no events yet; run an approval or governance action to create proof."
        )
    if audit_report.get("broken"):
        caveats.append(
            "Audit hash-chain verification reported broken entries; investigate before sharing this pack."
        )
    if int(audit_report.get("legacy") or 0) > 0:
        caveats.append(
            "Some audit events are legacy entries without hash-chain fields; they are listed but not cryptographically asserted."
        )
    caveats.append(
        "SIEM-ready audit export is available from /api/v1/audit/siem-export; live SIEM streaming still depends on customer adapters."
    )
    return caveats


def _governance_markdown(report: dict[str, Any]) -> str:
    audit_report = report.get("audit") or {}
    summary = report.get("summary") or {}
    lines = [
        "# Governance Proof",
        "",
        f"Status: **{(report.get('decision') or {}).get('status', 'unknown')}**",
        f"Score: **{(report.get('decision') or {}).get('score', 0)}**",
        f"Bundle: `{report.get('bundle_id', '')}`",
        f"Client: **{(report.get('client') or {}).get('name', '')}**",
        "",
        "## Summary",
        "",
        f"- Approval records: **{summary.get('approval_records', 0)}**",
        f"- Requested approvals: **{summary.get('requested', 0)}**",
        f"- Approved approvals: **{summary.get('approved', 0)}**",
        f"- Audit events: **{summary.get('audit_events', 0)}**",
        f"- Audit chain valid: **{audit_report.get('valid', False)}**",
        f"- Broken audit entries: **{summary.get('audit_broken', 0)}**",
        "",
        "## Approval Records",
        "",
    ]
    approvals = report.get("approval_records") or []
    if approvals:
        for item in approvals[:12]:
            linked = item.get("linked_record") or {}
            lines.append(
                "- "
                f"`{item.get('id')}` {item.get('status')} / {item.get('risk')} / "
                f"{item.get('tool_name')} / actor `{item.get('actor')}` / "
                f"linked `{linked.get('type') or ''}:{linked.get('id') or ''}`"
            )
    else:
        lines.append("- No approval records in the local store.")
    lines.extend(["", "## Recent Audit Events", ""])
    events = report.get("recent_audit_events") or []
    if events:
        for item in events[:12]:
            lines.append(
                "- "
                f"`{item.get('timestamp')}` {item.get('actor')} -> {item.get('action')} "
                f"({item.get('category')}, {item.get('outcome')}) `{item.get('id')}`"
            )
    else:
        lines.append("- No audit events in the local log.")
    siem = report.get("siem_handoff") or {}
    if siem:
        lines.extend(["", "## SIEM Handoff", ""])
        lines.append(f"- Schema: **{siem.get('schema', '')}**")
        lines.append(f"- Endpoint: `{siem.get('endpoint', '')}`")
        lines.append(f"- Recommended file: `{siem.get('recommended_filename', '')}`")
        lines.append(f"- Events: **{siem.get('events', 0)}**")
        lines.append(f"- Chain valid: **{siem.get('chain_valid', False)}**")
        lines.append(f"- Export SHA-256: `{siem.get('content_sha256', '')}`")
    lines.extend(["", "## Controls", ""])
    for item in report.get("controls") or []:
        lines.append(f"- **{item.get('title')}**: {item.get('evidence')}")
    lines.extend(["", "## Caveats", ""])
    lines.extend(f"- {item}" for item in report.get("caveats") or [])
    return "\n".join(lines)


def build_governance_proof(
    *,
    client_name: str,
    bundle_id: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build read-only approval and audit-chain proof for Evidence Bundle."""

    try:
        approvals_payload = approval_workflow.list_approval_records(limit=25)
        approvals = _approval_record_digest(list(approvals_payload.get("items") or []))
    except (
        Exception
    ) as exc:  # pragma: no cover - defensive: export should degrade gracefully
        approvals = [
            {
                "id": "approval.read_failed",
                "status": "error",
                "tool_name": "approval_store",
                "risk": "unknown",
                "approval_reason": str(exc),
            }
        ]
    audit_report = audit_log.verify_chain()
    recent_events = _recent_audit_events(limit=20)
    try:
        siem_export = audit_log.export_siem_events(output_format="jsonl", limit=1000)
    except (
        Exception
    ) as exc:  # pragma: no cover - defensive: governance proof should degrade gracefully
        siem_export = {
            "schema": "rentgen.audit.siem.v1",
            "events": 0,
            "content_sha256": "",
            "chain": {"valid": False},
            "ingestion": {"recommended_filename": "rentgen-audit-siem.jsonl"},
            "error": str(exc),
        }
    counts = _status_counts(approvals)
    decision = _governance_decision(approvals=approvals, audit_report=audit_report)
    report: dict[str, Any] = {
        "bundle_id": bundle_id,
        "generated_at": generated_at or _now(),
        "client": {"name": client_name},
        "decision": decision,
        "summary": {
            "approval_records": len(approvals),
            "requested": counts.get("requested", 0),
            "approved": counts.get("approved", 0),
            "rejected": counts.get("rejected", 0),
            "used": counts.get("used", 0),
            "expired": counts.get("expired", 0),
            "audit_events": int(audit_report.get("total") or 0),
            "audit_chained": int(audit_report.get("chained") or 0),
            "audit_legacy": int(audit_report.get("legacy") or 0),
            "audit_broken": len(audit_report.get("broken") or []),
            "audit_valid": bool(audit_report.get("valid")),
            "siem_events": int(siem_export.get("events") or 0),
            "siem_ready": bool((siem_export.get("chain") or {}).get("valid")),
        },
        "approval_records": approvals,
        "approval_store": str(approval_workflow.STORE_PATH),
        "audit": audit_report,
        "siem_handoff": {
            "schema": siem_export.get("schema"),
            "endpoint": "/api/v1/audit/siem-export",
            "route": "/audit",
            "recommended_filename": (siem_export.get("ingestion") or {}).get(
                "recommended_filename"
            ),
            "format": siem_export.get("format"),
            "events": int(siem_export.get("events") or 0),
            "content_sha256": siem_export.get("content_sha256"),
            "chain_valid": bool((siem_export.get("chain") or {}).get("valid")),
            "ingestion": siem_export.get("ingestion") or {},
        },
        "recent_audit_events": recent_events,
        "controls": [
            {
                "id": "write-approval",
                "title": "Write actions require approval",
                "evidence": "Safe Autopilot creates edt_mcp_call records with actor, tool, risk and argument constraints.",
                "route": "/safe-autopilot",
            },
            {
                "id": "separation-of-duties",
                "title": "Separation of duties",
                "evidence": "Approval workflow blocks requester self-approval for approved status.",
                "route": "/api/v1/approvals",
            },
            {
                "id": "tamper-evident-audit",
                "title": "Tamper-evident audit chain",
                "evidence": "Audit entries link through prev_hash and are verified by /api/v1/audit/verify.",
                "route": "/api/v1/audit/verify",
            },
            {
                "id": "siem-export",
                "title": "SIEM-ready audit export",
                "evidence": "Audit events can be exported as rentgen.audit.siem.v1 JSONL with chain-valid field and export SHA-256.",
                "route": "/api/v1/audit/siem-export",
            },
            {
                "id": "portable-proof",
                "title": "Portable proof pack",
                "evidence": "Evidence Bundle archive includes this JSON/Markdown artifact and SHA-256 manifest entries.",
                "route": "/evidence-bundle",
            },
        ],
        "routes": [
            "/safe-autopilot",
            "/api/v1/safe-autopilot/approval-request",
            "/api/v1/approvals",
            "/api/v1/audit/verify",
            "/api/v1/audit/siem-export",
            "/evidence-bundle",
        ],
        "buyer_line": "Rentgen can prove who requested a risky action, what scope was constrained, and whether the audit chain is intact.",
        "caveats": _governance_caveats(approvals=approvals, audit_report=audit_report),
    }
    report["markdown"] = _governance_markdown(report)
    return report


def _forwarding_note_filename(packet_file: str) -> str:
    if packet_file.lower().endswith(".md"):
        return f"{packet_file[:-3]}-forwarding-note.txt"
    return f"{packet_file}-forwarding-note.txt"


def _forwarding_note_text(packet: dict[str, Any]) -> str:
    subject = str(packet.get("forwarding_subject") or "")
    body = str(packet.get("forwarding_body") or "")
    return f"Subject: {subject}\n\n{body}".rstrip() + "\n"


def _archive_media_type(filename: str) -> str:
    if filename.endswith(".json"):
        return "application/json"
    if filename.endswith(".md"):
        return "text/markdown"
    if filename.endswith(".txt"):
        return "text/plain"
    return "application/octet-stream"


def _archive_manifest_payload(
    report: dict[str, Any], files: list[tuple[str, str]]
) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for filename, content in files:
        payload = content.encode("utf-8")
        entries.append(
            {
                "filename": filename,
                "media_type": _archive_media_type(filename),
                "size_bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
    return {
        "schema_version": "rentgen.evidence_archive_manifest.v1",
        "bundle_id": report.get("bundle_id"),
        "generated_at": report.get("generated_at"),
        "source_manifest_file": "manifest.json",
        "source_manifest_bundle_sha256": (report.get("manifest") or {}).get(
            "bundle_sha256"
        ),
        "manifest_scope": "All ZIP entries except archive-manifest.json.",
        "file_count": len(entries),
        "files": entries,
    }


def _archive_verify_markdown(report: dict[str, Any]) -> str:
    handoff = report.get("procurement_handoff") or {}
    receipt = report.get("archive_acceptance_receipt") or {}
    killer_demo_handoff = handoff.get("killer_demo_handoff") or {}
    verification_packet = handoff.get("verification_packet") or {}
    lines = [
        "# Verify Evidence Bundle Archive",
        "",
        f"Bundle: `{report.get('bundle_id', '')}`",
        f"Client: **{(report.get('client') or {}).get('name', '')}**",
        "",
        "## Record From Download Response",
        "",
        f"- Evidence ZIP filename: `{handoff.get('archive_filename', '')}`",
        f"- Evidence ZIP hash header: `{handoff.get('archive_hash_header', 'X-Archive-Sha256')}`",
        "- Archive manifest header: `X-Archive-Manifest`",
        "- Archive manifest hash header: `X-Archive-Manifest-Sha256`",
        "- Archive manifest count header: `X-Archive-Manifest-Files`",
        "",
        "## Verify Files",
        "",
        "1. Open `manifest.json` and verify source evidence artifact hashes.",
        "2. Open `archive-manifest.json` and verify generated ZIP entries, including this file.",
        "3. Open `OPEN_FIRST.md` and follow the role packet order.",
        "4. Open `archive-acceptance-receipt.md` and record both Evidence ZIP and linked Killer Demo ZIP boundaries.",
        "5. Forward `ROLE_*.md` and `ROLE_*-forwarding-note.txt` only after the hashes are recorded.",
        f"6. Download `{ARCHIVE_VERIFICATION_PACKET_ZIP}` and record `{ARCHIVE_VERIFICATION_PACKET_HASH_HEADER}` as the pair-level receipt.",
        "",
        "## Boundary",
        "",
        "- Evidence Bundle ZIP contains source evidence, procurement handoff, role packets and forwarding notes.",
        f"- Linked Killer Demo ZIP contains `{MEETING_CLOSE_RECEIPT_MD}`, `{POST_DEMO_ACTIVATION_MD}` and `killer-demo-manifest.json`.",
    ]
    if killer_demo_handoff:
        lines.extend(
            [
                "",
                "## Linked Killer Demo ZIP",
                "",
                f"- Endpoint: `{killer_demo_handoff.get('archive_endpoint', '')}`",
                f"- Filename: `{killer_demo_handoff.get('archive_filename', '')}`",
                f"- Hash header: `{killer_demo_handoff.get('archive_hash_header', KILLER_DEMO_ARCHIVE_HASH_HEADER)}`",
                f"- Manifest: `{killer_demo_handoff.get('manifest_file', 'killer-demo-manifest.json')}`",
            ]
        )
    if verification_packet:
        lines.extend(
            [
                "",
                "## Verification Packet ZIP",
                "",
                f"- Endpoint: `{verification_packet.get('endpoint', ARCHIVE_VERIFICATION_PACKET_ENDPOINT)}`",
                f"- Filename: `{verification_packet.get('filename', ARCHIVE_VERIFICATION_PACKET_ZIP)}`",
                f"- Hash header: `{verification_packet.get('hash_header', ARCHIVE_VERIFICATION_PACKET_HASH_HEADER)}`",
                f"- Open first: `{verification_packet.get('open_first_file', ARCHIVE_VERIFICATION_PACKET_OPEN_FIRST)}`",
            ]
        )
    archives = receipt.get("archives") or []
    if archives:
        lines.extend(["", "## Acceptance Receipt Archives", ""])
        for archive in archives:
            lines.append(
                f"- **{archive.get('title', '')}**: `{archive.get('filename', '')}` / `{archive.get('hash_header', '')}` / `{archive.get('manifest_file', '')}`"
            )
    return "\n".join(lines)


def _recipient_packet_markdown(
    report: dict[str, Any], recipient: dict[str, Any]
) -> str:
    handoff = report.get("procurement_handoff") or {}
    manifest_by_filename = {
        str(item.get("filename") or ""): str(item.get("sha256") or "")
        for item in (report.get("manifest") or {}).get("files", [])
    }
    archive_core = {
        "OPEN_FIRST.md",
        "manifest.json",
        "bundle.json",
        "evidence-bundle.md",
        "README.md",
        "procurement-handoff.json",
        "procurement-handoff.md",
        "archive-acceptance-receipt.json",
        "archive-acceptance-receipt.md",
    }
    linked_files = set(
        (handoff.get("killer_demo_handoff") or {}).get("post_demo_files") or []
    )
    control_attachments = set(
        str(item) for item in handoff.get("control_attachments", []) if item
    )
    role = str(recipient.get("role") or "Stakeholder")
    packet_file = str(recipient.get("packet_file") or role_packet_filename(role))
    forwarding_file = _forwarding_note_filename(packet_file)
    lines = [
        f"# {role} Evidence Packet",
        "",
        f"Packet file: `{packet_file}`",
        f"Forwarding note file: `{forwarding_file}`",
        f"Bundle: `{report.get('bundle_id', '')}`",
        f"Client: **{(report.get('client') or {}).get('name', '')}**",
        f"Evidence archive hash header: `{handoff.get('archive_hash_header', 'X-Archive-Sha256')}`",
        "",
        "## Decision",
        "",
        str(recipient.get("decision") or ""),
        "",
        "## Send Files",
        "",
    ]
    for filename in recipient.get("send_files") or []:
        sha256 = manifest_by_filename.get(str(filename), "")
        if sha256:
            status = "manifest"
            source = "Evidence Bundle ZIP"
        elif filename in archive_core:
            status = "archive-core"
            source = "Evidence Bundle ZIP"
        elif filename in linked_files:
            status = "linked-killer-demo"
            source = "Linked Killer Demo ZIP"
        elif filename in control_attachments:
            status = "control-attachment"
            source = "Verification Packet ZIP endpoint"
        else:
            status = "not-manifested"
            source = "Check procurement handoff"
        lines.append(
            f"- `{filename}` - **{status}** / {source} / `{sha256 or 'no-sha256-in-manifest'}`"
        )

    routes = list(recipient.get("routes") or [])
    if routes:
        lines.extend(["", "## Routes", ""])
        lines.extend(f"- `{route}`" for route in routes)

    lines.extend(["", "## Verification", ""])
    for step in handoff.get("verification_steps", [])[:4]:
        lines.append(f"- **{step.get('owner', '')}**: {step.get('action', '')}")
    lines.extend(
        [
            "",
            "## Archive Boundary",
            "",
            "- Evidence Bundle ZIP carries this role packet, manifest, procurement handoff and source evidence files.",
            "- Linked Killer Demo ZIP carries meeting close receipt, activation handoff and close-room role overlays.",
            f"- `{ARCHIVE_VERIFICATION_PACKET_ZIP}` is a separate control attachment generated by `{ARCHIVE_VERIFICATION_PACKET_ENDPOINT}`.",
        ]
    )
    return "\n".join(lines)


def _recipient_packets(report: dict[str, Any]) -> list[dict[str, Any]]:
    handoff = report.get("procurement_handoff") or {}
    packets: list[dict[str, Any]] = []
    for recipient in handoff.get("recipients", []):
        role = str(recipient.get("role") or "Stakeholder")
        filename = str(recipient.get("packet_file") or role_packet_filename(role))
        forwarding_filename = _forwarding_note_filename(filename)
        markdown = _recipient_packet_markdown(report, recipient)
        send_files = list(recipient.get("send_files") or [])
        control_attachments = [
            str(item) for item in handoff.get("control_attachments", []) if item
        ]
        attachments = list(
            dict.fromkeys(
                [
                    filename,
                    *send_files,
                    "archive-acceptance-receipt.md",
                    *control_attachments,
                ]
            )
        )
        subject = f"{(report.get('client') or {}).get('name', 'Client')}: 1C Rentgen evidence packet for {role}"
        body_lines = [
            f"Evidence packet for {role}.",
            "",
            str(
                recipient.get("decision")
                or "Review the attached evidence packet and listed proof files."
            ),
            "",
            f"Start with {filename}.",
            f"Evidence archive: {handoff.get('archive_filename', '')}",
            f"Archive hash header to record: {handoff.get('archive_hash_header', 'X-Archive-Sha256')}",
            "",
            "Attachments / files to forward:",
            *[f"- {item}" for item in attachments],
            "",
            "Acceptance:",
            "- Verify manifest.json SHA-256 entries before accepting the packet.",
            "- Record archive-acceptance-receipt.md in the procurement or intake ticket.",
            f"- Attach {ARCHIVE_VERIFICATION_PACKET_ZIP} and record {ARCHIVE_VERIFICATION_PACKET_HASH_HEADER}.",
            "- Send MEETING_CLOSE_RECEIPT.md and POST_DEMO_ACTIVATION_HANDOFF.md only from the linked Killer Demo ZIP.",
        ]
        packets.append(
            {
                "role": role,
                "filename": filename,
                "markdown_sha256": _sha256_text(markdown),
                "send_files": send_files,
                "routes": list(recipient.get("routes") or []),
                "forwarding_subject": subject,
                "forwarding_filename": forwarding_filename,
                "forwarding_body": "\n".join(body_lines),
                "attachments": attachments,
                "markdown": markdown,
            }
        )
    return packets


def evidence_bundle_archive(report: dict[str, Any]) -> dict[str, Any]:
    """Build a portable ZIP archive from an already composed evidence bundle."""

    receipt = report.get("commercial_assumptions") or {}
    handoff = report.get("procurement_handoff") or {}
    killer_demo_handoff = handoff.get("killer_demo_handoff") or {}
    verification_packet = handoff.get("verification_packet") or {}
    readme_lines = [
        "# 1C Rentgen Evidence Archive",
        "",
        f"Bundle: `{report['bundle_id']}`",
        f"Client: {report['client']['name']}",
        f"Bundle SHA-256: `{report['manifest']['bundle_sha256']}`",
        f"Commercial assumptions: AI/month `{receipt.get('monthly_ai_rent_label', 'not provided')}`, three-year AI rent `{receipt.get('three_year_ai_rent_label', 'not provided')}`.",
        "",
        "Start with `OPEN_FIRST.md` for role packets, readiness and verification steps.",
        "Use `VERIFY_ARCHIVE.md` for the exact archive verification checklist.",
        "Open `open-first-path.md` for the orient/prove/close/verify buyer path.",
        "Open `buyer-room-plan.md` when the presenter needs the single live-room route and close question.",
        "Forward `ROLE_*.md` files when one stakeholder needs only their send-ready packet.",
        "Use `ROLE_*-forwarding-note.txt` files as copy-paste subject/body notes for stakeholder forwarding.",
        "Use `archive-acceptance-receipt.md` to record Evidence Bundle ZIP and linked Killer Demo ZIP hashes.",
        f"Download `{ARCHIVE_VERIFICATION_PACKET_ZIP}` separately to verify both archives as one procurement pair.",
        "Use `manifest.json` to verify artifact hashes.",
        "Use `archive-manifest.json` to verify generated ZIP files, role packets and forwarding notes.",
        "All JSON/Markdown files are generated from local Rentgen evidence.",
    ]
    if killer_demo_handoff:
        readme_lines.extend(
            [
                "",
                "Linked Killer Demo ZIP:",
                f"- Endpoint: `{killer_demo_handoff.get('archive_endpoint', '')}`",
                f"- Open first: `{killer_demo_handoff.get('open_first_file', '')}`",
                f"- Manifest: `{killer_demo_handoff.get('manifest_file', 'killer-demo-manifest.json')}`",
                f"- Post-demo files: `{MEETING_CLOSE_RECEIPT_MD}`, `{POST_DEMO_ACTIVATION_MD}`",
                "These close-room overlay files are in the linked Killer Demo ZIP, not in this Evidence Archive.",
            ]
        )
    if verification_packet:
        readme_lines.extend(
            [
                "",
                "Verification Packet ZIP:",
                f"- Endpoint: `{verification_packet.get('endpoint', ARCHIVE_VERIFICATION_PACKET_ENDPOINT)}`",
                f"- Hash header: `{verification_packet.get('hash_header', ARCHIVE_VERIFICATION_PACKET_HASH_HEADER)}`",
                f"- Open first: `{verification_packet.get('open_first_file', ARCHIVE_VERIFICATION_PACKET_OPEN_FIRST)}`",
                "This control ZIP is generated next to the archives, not stored inside this Evidence Archive.",
            ]
        )
    files: list[tuple[str, str]] = [
        (
            "OPEN_FIRST.md",
            str(report.get("open_first_markdown") or _open_first_markdown(report)),
        ),
        ("manifest.json", _json_text(report["manifest"])),
        ("VERIFY_ARCHIVE.md", _archive_verify_markdown(report)),
        ("evidence-bundle.md", report.get("markdown") or ""),
        ("bundle.json", _json_text(report)),
        ("README.md", "\n".join(readme_lines)),
    ]
    for artifact in report.get("artifacts", []):
        files.append((f"{artifact['filename']}.json", artifact["json"]))
        if artifact.get("markdown"):
            files.append((f"{artifact['filename']}.md", artifact["markdown"]))
    if handoff:
        files.append(("procurement-handoff.json", _json_text(handoff)))
        files.append(
            (
                "procurement-handoff.md",
                str(handoff.get("markdown") or _procurement_handoff_markdown(handoff)),
            )
        )
        recipient_packets = list(
            handoff.get("recipient_packets") or _recipient_packets(report)
        )
        for packet in recipient_packets:
            packet_file = str(packet.get("filename") or "ROLE_STAKEHOLDER.md")
            files.append((packet_file, str(packet.get("markdown") or "")))
            forwarding_file = str(
                packet.get("forwarding_filename")
                or _forwarding_note_filename(packet_file)
            )
            files.append((forwarding_file, _forwarding_note_text(packet)))
    acceptance_receipt = report.get("archive_acceptance_receipt") or {}
    if acceptance_receipt:
        files.append(
            ("archive-acceptance-receipt.json", _json_text(acceptance_receipt))
        )
        files.append(
            (
                "archive-acceptance-receipt.md",
                str(
                    acceptance_receipt.get("markdown")
                    or _archive_acceptance_receipt_markdown(acceptance_receipt)
                ),
            )
        )

    archive_manifest = _archive_manifest_payload(report, files)
    archive_manifest_text = _json_text(archive_manifest)
    files.append(("archive-manifest.json", archive_manifest_text))

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for filename, content in files:
            archive.writestr(filename, content.encode("utf-8"))

    payload = buffer.getvalue()
    return {
        "filename": f"{report['bundle_id']}-evidence-archive.zip",
        "media_type": "application/zip",
        "sha256": hashlib.sha256(payload).hexdigest(),
        "size_bytes": len(payload),
        "files": len(files),
        "archive_manifest_file": "archive-manifest.json",
        "archive_manifest_sha256": _sha256_text(archive_manifest_text),
        "archive_manifest_files": archive_manifest["file_count"],
        "archive_manifest": archive_manifest,
        "bytes": payload,
    }


def _archive_verification_decision(status: str) -> dict[str, str]:
    if status == "pass":
        return {
            "status": "ready_to_record",
            "headline": "Archive verification passed.",
            "action": "Record the archive hash and attach this verification receipt to the procurement ticket.",
        }
    if status == "warn":
        return {
            "status": "record_with_review",
            "headline": "Archive verification completed with review items.",
            "action": "Record the archive hash only after the listed warnings are accepted by security or procurement.",
        }
    return {
        "status": "reject_archive",
        "headline": "Archive verification failed.",
        "action": "Do not forward this archive until high-severity findings are fixed and verification passes.",
    }


def _compact_embedded_verify(result: dict[str, Any] | None) -> dict[str, Any] | None:
    if not result:
        return None
    return {
        "status": result.get("status"),
        "archive_type": result.get("archive_type"),
        "filename": result.get("filename"),
        "archive_sha256": result.get("archive_sha256"),
        "checked_files": result.get("checked_files"),
        "summary": result.get("summary") or {},
    }


def archive_verification_receipt_markdown(receipt: dict[str, Any]) -> str:
    """Render a buyer-forwardable archive verification receipt."""

    decision = receipt.get("decision") or {}
    summary = receipt.get("summary") or {}
    embedded = receipt.get("embedded_evidence")
    lines = [
        "# Archive Verification Receipt",
        "",
        f"Status: **{receipt.get('status', 'unknown')}**",
        f"Decision: **{decision.get('status', 'unknown')}**",
        f"Archive type: `{receipt.get('archive_type', '')}`",
        f"Filename: `{receipt.get('filename', '')}`",
        f"Archive SHA-256: `{receipt.get('archive_sha256', '')}`",
        f"Generated at: `{receipt.get('generated_at', '')}`",
        "",
        "## Decision",
        "",
        str(decision.get("headline") or ""),
        "",
        str(decision.get("action") or ""),
        "",
        "## Verification Summary",
        "",
        f"- Checked files: **{receipt.get('checked_files', 0)}**",
        f"- Findings: **{summary.get('findings', 0)}**",
        f"- High: **{summary.get('high', 0)}**",
        f"- Medium: **{summary.get('medium', 0)}**",
        f"- Low: **{summary.get('low', 0)}**",
        "",
        "## Expected Headers",
        "",
    ]
    headers = receipt.get("expected_headers") or {}
    if headers:
        lines.extend(f"- `{key}`: `{value}`" for key, value in headers.items())
    else:
        lines.append("- No download headers were attached to this receipt.")
    if embedded:
        embedded_summary = embedded.get("summary") or {}
        lines.extend(
            [
                "",
                "## Embedded Evidence",
                "",
                f"- Status: **{embedded.get('status', 'unknown')}**",
                f"- Archive SHA-256: `{embedded.get('archive_sha256', '')}`",
                f"- Checked files: **{embedded.get('checked_files', 0)}**",
                f"- Findings: **{embedded_summary.get('findings', 0)}**",
            ]
        )
    lines.extend(["", "## Findings", ""])
    findings = receipt.get("findings") or []
    if findings:
        for item in findings[:20]:
            filename = f" `{item.get('filename')}`" if item.get("filename") else ""
            message = f" - {item.get('message')}" if item.get("message") else ""
            lines.append(
                f"- **{item.get('severity', 'low')}** `{item.get('code', 'unknown')}`{filename}{message}"
            )
    else:
        lines.append("- No findings.")
    lines.extend(
        [
            "",
            "## Acceptance Steps",
            "",
        ]
    )
    for step in receipt.get("acceptance_steps") or []:
        lines.append(
            f"- **{step.get('owner', '')}**: {step.get('action', '')} Expected: {step.get('expected', '')}"
        )
    return "\n".join(lines).strip()


def attach_archive_verification_receipt(
    result: dict[str, Any],
    *,
    expected_headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Attach a procurement-friendly receipt to an archive verification result."""

    headers = dict(expected_headers or result.get("expected_headers") or {})
    decision = _archive_verification_decision(str(result.get("status") or "unknown"))
    receipt = {
        "schema_version": "rentgen.archive_verification_receipt.v1",
        "generated_at": _now(),
        "status": result.get("status"),
        "decision": decision,
        "archive_type": result.get("archive_type"),
        "filename": result.get("filename"),
        "archive_sha256": result.get("archive_sha256"),
        "checked_files": result.get("checked_files"),
        "required_files": result.get("required_files") or [],
        "summary": result.get("summary") or {},
        "expected_headers": headers,
        "findings": result.get("findings") or [],
        "embedded_evidence": _compact_embedded_verify(
            result.get("embedded_evidence_verify")
        ),
        "receipt_files": {
            "json": "archive-verification-receipt.json",
            "markdown": "archive-verification-receipt.md",
        },
        "acceptance_steps": [
            {
                "owner": "Security / procurement",
                "action": "Record archive SHA-256 and expected response headers in the intake ticket.",
                "expected": "The recorded hash matches this receipt and the downloaded archive.",
            },
            {
                "owner": "Architect / delivery lead",
                "action": "Review warnings or failures before forwarding role packets or close-room artifacts.",
                "expected": "Pass archives can be forwarded; warn/fail archives have an accepted review note or are regenerated.",
            },
        ],
    }
    result["verification_receipt"] = receipt
    result["verification_receipt_markdown"] = archive_verification_receipt_markdown(
        receipt
    )
    return result


def verify_evidence_bundle_archive_payload(
    payload: bytes, *, filename: str = ""
) -> dict[str, Any]:
    """Verify an Evidence Bundle ZIP archive without extracting it."""

    findings: list[dict[str, Any]] = []
    checked = 0
    required = {
        "OPEN_FIRST.md",
        "VERIFY_ARCHIVE.md",
        "manifest.json",
        "archive-manifest.json",
        "bundle.json",
        "README.md",
        "procurement-handoff.md",
        "procurement-handoff.json",
        "archive-acceptance-receipt.md",
        "archive-acceptance-receipt.json",
    }
    archive_sha256 = hashlib.sha256(payload).hexdigest()

    try:
        with zipfile.ZipFile(io.BytesIO(payload), mode="r") as archive:
            names = {item.filename for item in archive.infolist() if not item.is_dir()}
            for required_file in sorted(required - names):
                findings.append(
                    {
                        "severity": "high",
                        "code": "required-file-missing",
                        "filename": required_file,
                        "message": f"Archive is missing required buyer proof file {required_file}.",
                    }
                )

            manifest: dict[str, Any] = {}
            if "manifest.json" in names:
                manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
                if not isinstance(manifest, dict):
                    findings.append(
                        {
                            "severity": "high",
                            "code": "manifest-invalid",
                            "message": "manifest.json is not an object.",
                        }
                    )
                    manifest = {}

            if "archive-manifest.json" not in names:
                findings.append(
                    {
                        "severity": "high",
                        "code": "archive-manifest-missing",
                        "message": "archive-manifest.json is required to verify generated ZIP entries.",
                    }
                )
                archive_manifest: dict[str, Any] = {}
            else:
                archive_manifest = json.loads(
                    archive.read("archive-manifest.json").decode("utf-8")
                )
                if not isinstance(archive_manifest, dict):
                    findings.append(
                        {
                            "severity": "high",
                            "code": "archive-manifest-invalid",
                            "message": "archive-manifest.json is not an object.",
                        }
                    )
                    archive_manifest = {}

            if archive_manifest:
                if (
                    archive_manifest.get("schema_version")
                    != "rentgen.evidence_archive_manifest.v1"
                ):
                    findings.append(
                        {
                            "severity": "medium",
                            "code": "archive-manifest-schema",
                            "expected": "rentgen.evidence_archive_manifest.v1",
                            "actual": archive_manifest.get("schema_version"),
                        }
                    )
                if "archive-manifest.json" in {
                    str(item.get("filename") or "")
                    for item in archive_manifest.get("files", [])
                    if isinstance(item, dict)
                }:
                    findings.append(
                        {
                            "severity": "medium",
                            "code": "archive-manifest-self-reference",
                            "message": "archive-manifest.json should describe all ZIP entries except itself.",
                        }
                    )
                if manifest and archive_manifest.get(
                    "source_manifest_bundle_sha256"
                ) != manifest.get("bundle_sha256"):
                    findings.append(
                        {
                            "severity": "high",
                            "code": "source-manifest-digest-mismatch",
                            "expected": manifest.get("bundle_sha256"),
                            "actual": archive_manifest.get(
                                "source_manifest_bundle_sha256"
                            ),
                        }
                    )
                for entry in archive_manifest.get("files", []):
                    if not isinstance(entry, dict):
                        findings.append(
                            {
                                "severity": "high",
                                "code": "archive-manifest-entry-invalid",
                            }
                        )
                        continue
                    entry_name = str(entry.get("filename") or "")
                    if not entry_name:
                        findings.append(
                            {
                                "severity": "high",
                                "code": "archive-manifest-entry-without-filename",
                            }
                        )
                        continue
                    if entry_name not in names:
                        findings.append(
                            {
                                "severity": "high",
                                "code": "archive-entry-missing",
                                "filename": entry_name,
                            }
                        )
                        continue
                    content = archive.read(entry_name)
                    checked += 1
                    actual_sha = hashlib.sha256(content).hexdigest()
                    if actual_sha != entry.get("sha256"):
                        findings.append(
                            {
                                "severity": "high",
                                "code": "archive-entry-hash-mismatch",
                                "filename": entry_name,
                                "expected": entry.get("sha256"),
                                "actual": actual_sha,
                            }
                        )
                    if len(content) != entry.get("size_bytes"):
                        findings.append(
                            {
                                "severity": "high",
                                "code": "archive-entry-size-mismatch",
                                "filename": entry_name,
                                "expected": entry.get("size_bytes"),
                                "actual": len(content),
                            }
                        )

            if "archive-acceptance-receipt.json" in names:
                receipt = json.loads(
                    archive.read("archive-acceptance-receipt.json").decode("utf-8")
                )
                evidence_archive = next(
                    (
                        item
                        for item in receipt.get("archives", [])
                        if isinstance(item, dict)
                        and item.get("id") == "evidence-archive"
                    ),
                    {},
                )
                for receipt_file in evidence_archive.get("contains", []):
                    if str(receipt_file) not in names:
                        findings.append(
                            {
                                "severity": "medium",
                                "code": "receipt-contained-file-missing",
                                "filename": str(receipt_file),
                            }
                        )
    except zipfile.BadZipFile:
        findings.append(
            {
                "severity": "high",
                "code": "zip-invalid",
                "message": "Payload is not a readable ZIP archive.",
            }
        )
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
        findings.append(
            {"severity": "high", "code": "archive-json-invalid", "message": str(exc)}
        )

    severities = Counter(str(item.get("severity") or "low") for item in findings)
    status = "fail" if severities.get("high") else ("warn" if findings else "pass")
    result = {
        "status": status,
        "archive_type": "evidence-bundle",
        "filename": filename,
        "archive_sha256": archive_sha256,
        "checked_files": checked,
        "required_files": sorted(required),
        "summary": {
            "findings": len(findings),
            "high": severities.get("high", 0),
            "medium": severities.get("medium", 0),
            "low": severities.get("low", 0),
        },
        "findings": findings,
    }
    return attach_archive_verification_receipt(result)


def build_evidence_bundle(
    *,
    executive: dict[str, Any],
    store: Any = None,
    client_name: str = "Demo client",
    config_path: str | None = None,
    target_platform_version: str | None = None,
    release_name: str | None = None,
    changed_modules: list[str] | None = None,
    lock_radar_log_path: str | None = None,
    assumptions: dict[str, Any] | None = None,
    include_demo: bool = True,
    include_vendor: bool = True,
    include_update: bool = True,
    include_rights: bool = True,
    include_lock_radar: bool = False,
    include_extension_safety: bool = False,
    include_test_factory: bool = True,
    include_safe_autopilot: bool = True,
    include_value_packs: bool = True,
    include_business_case: bool = True,
    include_board_pack: bool = True,
    include_outcome_ledger: bool = True,
    include_launch_room: bool = True,
    include_killer_demo: bool = True,
    include_buyer_concierge: bool = True,
    include_commercial_offer_studio: bool = True,
    include_demo_command_center: bool = True,
    include_enterprise_trust_center: bool = True,
    include_guided_demo: bool = True,
    include_scenario_hub: bool = True,
    include_pilot_launchpad: bool = True,
    include_productization: bool = True,
    include_governance_proof: bool = True,
) -> dict[str, Any]:
    """Build a portable evidence bundle with hashed JSON/Markdown artifacts."""

    generated_at = _now()
    bundle_source = f"{client_name}\n{config_path or ''}\n{target_platform_version or ''}\n{generated_at}"
    bundle_id = "evb_" + hashlib.sha1(bundle_source.encode("utf-8")).hexdigest()[:16]
    changed = list(changed_modules or [])
    business_assumptions = dict(assumptions or {}) or None
    artifacts: list[dict[str, Any]] = []
    rights_report: dict[str, Any] | None = None
    caveats: list[str] = [
        "Evidence Bundle can export an unsigned ZIP proof archive; signed offline archives remain a Productization hardening step.",
        "Artifact hashes prove the returned payloads, not external customer systems.",
    ]

    buyer_pulse_report = _buyer_pulse_report(
        executive=executive,
        assumptions=business_assumptions,
        generated_at=generated_at,
        client_name=client_name,
        config_path=config_path,
        target_platform_version=target_platform_version,
    )
    artifacts.append(
        _artifact(
            id="buyer-pulse",
            title="Buyer Pulse",
            route="/",
            report=buyer_pulse_report,
            filename="buyer-pulse",
            summary=buyer_pulse_report.get("summary", {}),
        )
    )
    buyer_brief_report = _buyer_brief_report(
        executive=executive,
        assumptions=business_assumptions,
        generated_at=generated_at,
        client_name=client_name,
        config_path=config_path,
        target_platform_version=target_platform_version,
    )
    artifacts.append(
        _artifact(
            id="buyer-brief",
            title="Buyer Brief",
            route="/",
            report=buyer_brief_report,
            filename="buyer-brief",
            summary=buyer_brief_report.get("summary", {}),
        )
    )
    buyer_room_plan_report = _buyer_room_plan_report(buyer_brief_report)
    artifacts.append(
        _artifact(
            id="buyer-room-plan",
            title="Buyer Room Plan",
            route=str(
                (buyer_room_plan_report.get("buyer_room_plan") or {}).get("route")
                or "/"
            ),
            report=buyer_room_plan_report,
            filename="buyer-room-plan",
            summary=buyer_room_plan_report.get("summary", {}),
        )
    )
    open_first_path_report = _open_first_path_report(buyer_brief_report)
    artifacts.append(
        _artifact(
            id="open-first-path",
            title="Open-First Path",
            route="/",
            report=open_first_path_report,
            filename="open-first-path",
            summary=open_first_path_report.get("summary", {}),
        )
    )

    platform = build_platform_doctor(
        config_path=config_path,
        target_platform_version=target_platform_version,
    )
    artifacts.append(
        _artifact(
            id="platform-doctor",
            title="Platform Doctor",
            route="/platform-doctor",
            report=platform,
            filename="platform-doctor",
            summary={
                "checks": len(platform.get("checks", [])),
                **(platform.get("decision") or {}),
            },
        )
    )

    intake = build_intake_plan(config_path, "auto")
    artifacts.append(
        _artifact(
            id="configuration-intake",
            title="Configuration Intake",
            route="/configurations",
            report={**intake, "markdown": _intake_markdown(intake)},
            filename="configuration-intake",
            summary=intake.get("inventory", {}),
        )
    )

    demo_report: dict[str, Any] | None = None
    if include_demo:
        demo_report = build_demo_story(executive)
        artifacts.append(
            _artifact(
                id="demo-story",
                title="Demo Story",
                route="/",
                report={
                    **demo_report,
                    "markdown": demo_report.get("export", {}).get("markdown", ""),
                },
                filename="demo-story",
                summary={
                    "steps": len(demo_report.get("demo_steps", [])),
                    "roles": len(demo_report.get("role_reports", [])),
                },
            )
        )
        for role_report in demo_report.get("role_reports", []):
            role = str(role_report.get("role") or "role")
            filename = str(
                role_report.get("download_name") or f"rentgen-{role}-report.md"
            ).removesuffix(".md")
            artifacts.append(
                _artifact(
                    id=f"role-report-{role}",
                    title=str(role_report.get("title") or f"Role Report: {role}"),
                    route="/",
                    report=role_report,
                    filename=filename,
                    summary={
                        "role": role,
                        "proof_points": len(role_report.get("proof_points") or []),
                        "next_actions": len(role_report.get("next_actions") or []),
                    },
                )
            )

    value_packs_report: dict[str, Any] | None = None
    if include_value_packs:
        value_packs_report = build_value_packs(executive)
        artifacts.append(
            _artifact(
                id="value-packs",
                title="Value Packs",
                route="/value-packs",
                report=value_packs_report,
                filename="value-packs",
                summary=value_packs_report.get("summary", {}),
            )
        )

    vendor_report: dict[str, Any] | None = None
    if include_vendor:
        vendor_report = build_vendor_portfolio(
            executive=executive,
            platform=platform,
            intake=intake,
            client_name=client_name,
        )
        artifacts.append(
            _artifact(
                id="vendor-portfolio",
                title="Vendor Portfolio",
                route="/vendor-portfolio",
                report=vendor_report,
                filename="vendor-portfolio",
                summary=vendor_report.get("portfolio", {}),
            )
        )

    business_case_report: dict[str, Any] | None = None
    if include_business_case:
        value_packs_report = value_packs_report or build_value_packs(executive)
        vendor_report = vendor_report or build_vendor_portfolio(
            executive=executive,
            platform=platform,
            intake=intake,
            client_name=client_name,
        )
        business_case_report = build_business_case(
            executive=executive,
            platform=platform,
            intake=intake,
            vendor=vendor_report,
            value_packs=value_packs_report,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
            assumptions=business_assumptions,
        )
        artifacts.append(
            _artifact(
                id="business-case",
                title="Business Case",
                route="/business-case",
                report=business_case_report,
                filename="business-case",
                summary=business_case_report.get("summary", {}),
            )
        )

    productization_report: dict[str, Any] | None = None
    if include_productization:
        productization_report = productization_readiness()
        productization_markdown = productization_markdown_report().get("content", "")
        artifacts.append(
            _artifact(
                id="productization",
                title="Productization Readiness",
                route="/productization",
                report={**productization_report, "markdown": productization_markdown},
                filename="productization-readiness",
                summary=productization_report.get("summary", {}),
            )
        )

    guided_demo_report: dict[str, Any] | None = None
    if include_guided_demo:
        demo_report = demo_report or build_demo_story(executive)
        value_packs_report = value_packs_report or build_value_packs(executive)
        vendor_report = vendor_report or build_vendor_portfolio(
            executive=executive,
            platform=platform,
            intake=intake,
            client_name=client_name,
        )
        business_case_report = business_case_report or build_business_case(
            executive=executive,
            platform=platform,
            intake=intake,
            vendor=vendor_report,
            value_packs=value_packs_report,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
            assumptions=business_assumptions,
        )
        productization_report = productization_report or productization_readiness()
        guided_demo_report = build_guided_demo(
            executive=executive,
            demo_story=demo_report,
            business_case=business_case_report,
            productization=productization_report,
            value_packs=value_packs_report,
            vendor_portfolio=vendor_report,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
        )
        artifacts.append(
            _artifact(
                id="guided-demo",
                title="Guided Demo / Deal Room",
                route="/guided-demo",
                report=guided_demo_report,
                filename="guided-demo",
                summary=guided_demo_report.get("summary", {}),
            )
        )

    scenario_hub_report: dict[str, Any] | None = None
    if include_scenario_hub:
        demo_report = demo_report or build_demo_story(executive)
        value_packs_report = value_packs_report or build_value_packs(executive)
        vendor_report = vendor_report or build_vendor_portfolio(
            executive=executive,
            platform=platform,
            intake=intake,
            client_name=client_name,
        )
        business_case_report = business_case_report or build_business_case(
            executive=executive,
            platform=platform,
            intake=intake,
            vendor=vendor_report,
            value_packs=value_packs_report,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
            assumptions=business_assumptions,
        )
        productization_report = productization_report or productization_readiness()
        guided_demo_report = guided_demo_report or build_guided_demo(
            executive=executive,
            demo_story=demo_report,
            business_case=business_case_report,
            productization=productization_report,
            value_packs=value_packs_report,
            vendor_portfolio=vendor_report,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
        )
        scenario_hub_report = build_scenario_hub(
            executive=executive,
            guided_demo=guided_demo_report,
            business_case=business_case_report,
            productization=productization_report,
            value_packs=value_packs_report,
            vendor_portfolio=vendor_report,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
        )
        artifacts.append(
            _artifact(
                id="scenario-hub",
                title="Scenario Hub",
                route="/scenario-hub",
                report=scenario_hub_report,
                filename="scenario-hub",
                summary=scenario_hub_report.get("summary", {}),
            )
        )

    pilot_launchpad_report: dict[str, Any] | None = None
    if include_pilot_launchpad:
        demo_report = demo_report or build_demo_story(executive)
        value_packs_report = value_packs_report or build_value_packs(executive)
        vendor_report = vendor_report or build_vendor_portfolio(
            executive=executive,
            platform=platform,
            intake=intake,
            client_name=client_name,
        )
        business_case_report = business_case_report or build_business_case(
            executive=executive,
            platform=platform,
            intake=intake,
            vendor=vendor_report,
            value_packs=value_packs_report,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
            assumptions=business_assumptions,
        )
        productization_report = productization_report or productization_readiness()
        guided_demo_report = guided_demo_report or build_guided_demo(
            executive=executive,
            demo_story=demo_report,
            business_case=business_case_report,
            productization=productization_report,
            value_packs=value_packs_report,
            vendor_portfolio=vendor_report,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
        )
        scenario_hub_report = scenario_hub_report or build_scenario_hub(
            executive=executive,
            guided_demo=guided_demo_report,
            business_case=business_case_report,
            productization=productization_report,
            value_packs=value_packs_report,
            vendor_portfolio=vendor_report,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
        )
        pilot_launchpad_report = build_pilot_launchpad(
            executive=executive,
            scenario_hub=scenario_hub_report,
            guided_demo=guided_demo_report,
            business_case=business_case_report,
            productization=productization_report,
            value_packs=value_packs_report,
            vendor_portfolio=vendor_report,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
        )
        artifacts.append(
            _artifact(
                id="pilot-launchpad",
                title="Pilot Launchpad",
                route="/pilot-launchpad",
                report=pilot_launchpad_report,
                filename="pilot-launchpad",
                summary=pilot_launchpad_report.get("summary", {}),
            )
        )

    demo_command_center_report: dict[str, Any] | None = None
    enterprise_trust_center_report: dict[str, Any] | None = None
    commercial_offer_studio_report: dict[str, Any] | None = None
    buyer_concierge_report: dict[str, Any] | None = None
    board_pack_report: dict[str, Any] | None = None
    outcome_ledger_report: dict[str, Any] | None = None
    launch_room_report: dict[str, Any] | None = None
    test_factory_report: dict[str, Any] | None = None
    if include_demo_command_center:
        demo_report = demo_report or build_demo_story(executive)
        value_packs_report = value_packs_report or build_value_packs(executive)
        vendor_report = vendor_report or build_vendor_portfolio(
            executive=executive,
            platform=platform,
            intake=intake,
            client_name=client_name,
        )
        business_case_report = business_case_report or build_business_case(
            executive=executive,
            platform=platform,
            intake=intake,
            vendor=vendor_report,
            value_packs=value_packs_report,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
            assumptions=business_assumptions,
        )
        productization_report = productization_report or productization_readiness()
        guided_demo_report = guided_demo_report or build_guided_demo(
            executive=executive,
            demo_story=demo_report,
            business_case=business_case_report,
            productization=productization_report,
            value_packs=value_packs_report,
            vendor_portfolio=vendor_report,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
        )
        scenario_hub_report = scenario_hub_report or build_scenario_hub(
            executive=executive,
            guided_demo=guided_demo_report,
            business_case=business_case_report,
            productization=productization_report,
            value_packs=value_packs_report,
            vendor_portfolio=vendor_report,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
        )
        pilot_launchpad_report = pilot_launchpad_report or build_pilot_launchpad(
            executive=executive,
            scenario_hub=scenario_hub_report,
            guided_demo=guided_demo_report,
            business_case=business_case_report,
            productization=productization_report,
            value_packs=value_packs_report,
            vendor_portfolio=vendor_report,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
        )
        demo_command_center_report = build_demo_command_center(
            executive=executive,
            scenario_hub=scenario_hub_report,
            guided_demo=guided_demo_report,
            pilot_launchpad=pilot_launchpad_report,
            business_case=business_case_report,
            productization=productization_report,
            vendor_portfolio=vendor_report,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
        )
        artifacts.append(
            _artifact(
                id="demo-command-center",
                title="Demo Command Center",
                route="/demo-command-center",
                report=demo_command_center_report,
                filename="demo-command-center",
                summary=demo_command_center_report.get("summary", {}),
            )
        )

    if include_enterprise_trust_center:
        demo_report = demo_report or build_demo_story(executive)
        value_packs_report = value_packs_report or build_value_packs(executive)
        vendor_report = vendor_report or build_vendor_portfolio(
            executive=executive,
            platform=platform,
            intake=intake,
            client_name=client_name,
        )
        business_case_report = business_case_report or build_business_case(
            executive=executive,
            platform=platform,
            intake=intake,
            vendor=vendor_report,
            value_packs=value_packs_report,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
            assumptions=business_assumptions,
        )
        productization_report = productization_report or productization_readiness()
        guided_demo_report = guided_demo_report or build_guided_demo(
            executive=executive,
            demo_story=demo_report,
            business_case=business_case_report,
            productization=productization_report,
            value_packs=value_packs_report,
            vendor_portfolio=vendor_report,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
        )
        scenario_hub_report = scenario_hub_report or build_scenario_hub(
            executive=executive,
            guided_demo=guided_demo_report,
            business_case=business_case_report,
            productization=productization_report,
            value_packs=value_packs_report,
            vendor_portfolio=vendor_report,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
        )
        pilot_launchpad_report = pilot_launchpad_report or build_pilot_launchpad(
            executive=executive,
            scenario_hub=scenario_hub_report,
            guided_demo=guided_demo_report,
            business_case=business_case_report,
            productization=productization_report,
            value_packs=value_packs_report,
            vendor_portfolio=vendor_report,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
        )
        demo_command_center_report = (
            demo_command_center_report
            or build_demo_command_center(
                executive=executive,
                scenario_hub=scenario_hub_report,
                guided_demo=guided_demo_report,
                pilot_launchpad=pilot_launchpad_report,
                business_case=business_case_report,
                productization=productization_report,
                vendor_portfolio=vendor_report,
                client_name=client_name,
                config_path=config_path,
                target_platform_version=target_platform_version,
            )
        )
        rights_report = rights_report or build_rights_rls(
            config_path=config_path, role_limit=60, object_limit=160
        )
        offline_readiness = build_offline_readiness(
            strict=False, include_metadata=False
        )
        security_posture = build_security_posture(
            config_path=config_path, limit=120, module_limit=1200
        )
        enterprise_trust_center_report = build_enterprise_trust_center(
            executive=executive,
            platform=platform,
            business_case=business_case_report,
            productization=productization_report,
            offline_readiness=offline_readiness,
            security_posture=security_posture,
            rights_rls=rights_report,
            demo_command_center=demo_command_center_report,
            pilot_launchpad=pilot_launchpad_report,
            scenario_hub=scenario_hub_report,
            vendor_portfolio=vendor_report,
            evidence_artifacts=artifacts,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
        )
        artifacts.append(
            _artifact(
                id="enterprise-trust-center",
                title="Enterprise Trust Center",
                route="/enterprise-trust-center",
                report=enterprise_trust_center_report,
                filename="enterprise-trust-center",
                summary=enterprise_trust_center_report.get("summary", {}),
            )
        )
        security_questionnaire_report = _security_questionnaire_report(
            enterprise_trust_center_report
        )
        artifacts.append(
            _artifact(
                id="security-questionnaire",
                title="Security Questionnaire",
                route="/enterprise-trust-center",
                report=security_questionnaire_report,
                filename="rentgen-security-questionnaire",
                summary=security_questionnaire_report.get("summary", {}),
            )
        )

    if include_commercial_offer_studio:
        demo_report = demo_report or build_demo_story(executive)
        value_packs_report = value_packs_report or build_value_packs(executive)
        vendor_report = vendor_report or build_vendor_portfolio(
            executive=executive,
            platform=platform,
            intake=intake,
            client_name=client_name,
        )
        business_case_report = business_case_report or build_business_case(
            executive=executive,
            platform=platform,
            intake=intake,
            vendor=vendor_report,
            value_packs=value_packs_report,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
            assumptions=business_assumptions,
        )
        productization_report = productization_report or productization_readiness()
        guided_demo_report = guided_demo_report or build_guided_demo(
            executive=executive,
            demo_story=demo_report,
            business_case=business_case_report,
            productization=productization_report,
            value_packs=value_packs_report,
            vendor_portfolio=vendor_report,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
        )
        scenario_hub_report = scenario_hub_report or build_scenario_hub(
            executive=executive,
            guided_demo=guided_demo_report,
            business_case=business_case_report,
            productization=productization_report,
            value_packs=value_packs_report,
            vendor_portfolio=vendor_report,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
        )
        pilot_launchpad_report = pilot_launchpad_report or build_pilot_launchpad(
            executive=executive,
            scenario_hub=scenario_hub_report,
            guided_demo=guided_demo_report,
            business_case=business_case_report,
            productization=productization_report,
            value_packs=value_packs_report,
            vendor_portfolio=vendor_report,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
        )
        demo_command_center_report = (
            demo_command_center_report
            or build_demo_command_center(
                executive=executive,
                scenario_hub=scenario_hub_report,
                guided_demo=guided_demo_report,
                pilot_launchpad=pilot_launchpad_report,
                business_case=business_case_report,
                productization=productization_report,
                vendor_portfolio=vendor_report,
                client_name=client_name,
                config_path=config_path,
                target_platform_version=target_platform_version,
            )
        )
        rights_report = rights_report or build_rights_rls(
            config_path=config_path, role_limit=60, object_limit=160
        )
        enterprise_trust_center_report = (
            enterprise_trust_center_report
            or build_enterprise_trust_center(
                executive=executive,
                platform=platform,
                business_case=business_case_report,
                productization=productization_report,
                offline_readiness=build_offline_readiness(
                    strict=False, include_metadata=False
                ),
                security_posture=build_security_posture(
                    config_path=config_path, limit=120, module_limit=1200
                ),
                rights_rls=rights_report,
                demo_command_center=demo_command_center_report,
                pilot_launchpad=pilot_launchpad_report,
                scenario_hub=scenario_hub_report,
                vendor_portfolio=vendor_report,
                evidence_artifacts=artifacts,
                client_name=client_name,
                config_path=config_path,
                target_platform_version=target_platform_version,
            )
        )
        commercial_offer_studio_report = build_commercial_offer_studio(
            executive=executive,
            business_case=business_case_report,
            pilot_launchpad=pilot_launchpad_report,
            enterprise_trust_center=enterprise_trust_center_report,
            productization=productization_report,
            scenario_hub=scenario_hub_report,
            value_packs=value_packs_report,
            vendor_portfolio=vendor_report,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
        )
        artifacts.append(
            _artifact(
                id="commercial-offer-studio",
                title="Commercial Offer Studio",
                route="/commercial-offer-studio",
                report=commercial_offer_studio_report,
                filename="commercial-offer-studio",
                summary=commercial_offer_studio_report.get("summary", {}),
            )
        )

    if include_buyer_concierge:
        demo_report = demo_report or build_demo_story(executive)
        value_packs_report = value_packs_report or build_value_packs(executive)
        vendor_report = vendor_report or build_vendor_portfolio(
            executive=executive,
            platform=platform,
            intake=intake,
            client_name=client_name,
        )
        business_case_report = business_case_report or build_business_case(
            executive=executive,
            platform=platform,
            intake=intake,
            vendor=vendor_report,
            value_packs=value_packs_report,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
            assumptions=business_assumptions,
        )
        productization_report = productization_report or productization_readiness()
        guided_demo_report = guided_demo_report or build_guided_demo(
            executive=executive,
            demo_story=demo_report,
            business_case=business_case_report,
            productization=productization_report,
            value_packs=value_packs_report,
            vendor_portfolio=vendor_report,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
        )
        scenario_hub_report = scenario_hub_report or build_scenario_hub(
            executive=executive,
            guided_demo=guided_demo_report,
            business_case=business_case_report,
            productization=productization_report,
            value_packs=value_packs_report,
            vendor_portfolio=vendor_report,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
        )
        pilot_launchpad_report = pilot_launchpad_report or build_pilot_launchpad(
            executive=executive,
            scenario_hub=scenario_hub_report,
            guided_demo=guided_demo_report,
            business_case=business_case_report,
            productization=productization_report,
            value_packs=value_packs_report,
            vendor_portfolio=vendor_report,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
        )
        demo_command_center_report = (
            demo_command_center_report
            or build_demo_command_center(
                executive=executive,
                scenario_hub=scenario_hub_report,
                guided_demo=guided_demo_report,
                pilot_launchpad=pilot_launchpad_report,
                business_case=business_case_report,
                productization=productization_report,
                vendor_portfolio=vendor_report,
                client_name=client_name,
                config_path=config_path,
                target_platform_version=target_platform_version,
            )
        )
        rights_report = rights_report or build_rights_rls(
            config_path=config_path, role_limit=60, object_limit=160
        )
        enterprise_trust_center_report = (
            enterprise_trust_center_report
            or build_enterprise_trust_center(
                executive=executive,
                platform=platform,
                business_case=business_case_report,
                productization=productization_report,
                offline_readiness=build_offline_readiness(
                    strict=False, include_metadata=False
                ),
                security_posture=build_security_posture(
                    config_path=config_path, limit=120, module_limit=1200
                ),
                rights_rls=rights_report,
                demo_command_center=demo_command_center_report,
                pilot_launchpad=pilot_launchpad_report,
                scenario_hub=scenario_hub_report,
                vendor_portfolio=vendor_report,
                evidence_artifacts=artifacts,
                client_name=client_name,
                config_path=config_path,
                target_platform_version=target_platform_version,
            )
        )
        commercial_offer_studio_report = (
            commercial_offer_studio_report
            or build_commercial_offer_studio(
                executive=executive,
                business_case=business_case_report,
                pilot_launchpad=pilot_launchpad_report,
                enterprise_trust_center=enterprise_trust_center_report,
                productization=productization_report,
                scenario_hub=scenario_hub_report,
                value_packs=value_packs_report,
                vendor_portfolio=vendor_report,
                client_name=client_name,
                config_path=config_path,
                target_platform_version=target_platform_version,
            )
        )
        buyer_concierge_report = build_buyer_concierge(
            executive=executive,
            scenario_hub=scenario_hub_report,
            guided_demo=guided_demo_report,
            pilot_launchpad=pilot_launchpad_report,
            enterprise_trust_center=enterprise_trust_center_report,
            commercial_offer_studio=commercial_offer_studio_report,
            business_case=business_case_report,
            productization=productization_report,
            vendor_portfolio=vendor_report,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
        )
        artifacts.append(
            _artifact(
                id="buyer-concierge",
                title="Buyer Concierge",
                route="/buyer-concierge",
                report=buyer_concierge_report,
                filename="buyer-concierge",
                summary=buyer_concierge_report.get("summary", {}),
            )
        )

    if include_board_pack:
        demo_report = demo_report or build_demo_story(executive)
        value_packs_report = value_packs_report or build_value_packs(executive)
        vendor_report = vendor_report or build_vendor_portfolio(
            executive=executive,
            platform=platform,
            intake=intake,
            client_name=client_name,
        )
        business_case_report = business_case_report or build_business_case(
            executive=executive,
            platform=platform,
            intake=intake,
            vendor=vendor_report,
            value_packs=value_packs_report,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
            assumptions=business_assumptions,
        )
        productization_report = productization_report or productization_readiness()
        guided_demo_report = guided_demo_report or build_guided_demo(
            executive=executive,
            demo_story=demo_report,
            business_case=business_case_report,
            productization=productization_report,
            value_packs=value_packs_report,
            vendor_portfolio=vendor_report,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
        )
        scenario_hub_report = scenario_hub_report or build_scenario_hub(
            executive=executive,
            guided_demo=guided_demo_report,
            business_case=business_case_report,
            productization=productization_report,
            value_packs=value_packs_report,
            vendor_portfolio=vendor_report,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
        )
        pilot_launchpad_report = pilot_launchpad_report or build_pilot_launchpad(
            executive=executive,
            scenario_hub=scenario_hub_report,
            guided_demo=guided_demo_report,
            business_case=business_case_report,
            productization=productization_report,
            value_packs=value_packs_report,
            vendor_portfolio=vendor_report,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
        )
        demo_command_center_report = (
            demo_command_center_report
            or build_demo_command_center(
                executive=executive,
                scenario_hub=scenario_hub_report,
                guided_demo=guided_demo_report,
                pilot_launchpad=pilot_launchpad_report,
                business_case=business_case_report,
                productization=productization_report,
                vendor_portfolio=vendor_report,
                client_name=client_name,
                config_path=config_path,
                target_platform_version=target_platform_version,
            )
        )
        rights_report = rights_report or build_rights_rls(
            config_path=config_path, role_limit=60, object_limit=160
        )
        enterprise_trust_center_report = (
            enterprise_trust_center_report
            or build_enterprise_trust_center(
                executive=executive,
                platform=platform,
                business_case=business_case_report,
                productization=productization_report,
                offline_readiness=build_offline_readiness(
                    strict=False, include_metadata=False
                ),
                security_posture=build_security_posture(
                    config_path=config_path, limit=120, module_limit=1200
                ),
                rights_rls=rights_report,
                demo_command_center=demo_command_center_report,
                pilot_launchpad=pilot_launchpad_report,
                scenario_hub=scenario_hub_report,
                vendor_portfolio=vendor_report,
                evidence_artifacts=artifacts,
                client_name=client_name,
                config_path=config_path,
                target_platform_version=target_platform_version,
            )
        )
        commercial_offer_studio_report = (
            commercial_offer_studio_report
            or build_commercial_offer_studio(
                executive=executive,
                business_case=business_case_report,
                pilot_launchpad=pilot_launchpad_report,
                enterprise_trust_center=enterprise_trust_center_report,
                productization=productization_report,
                scenario_hub=scenario_hub_report,
                value_packs=value_packs_report,
                vendor_portfolio=vendor_report,
                client_name=client_name,
                config_path=config_path,
                target_platform_version=target_platform_version,
            )
        )
        buyer_concierge_report = buyer_concierge_report or build_buyer_concierge(
            executive=executive,
            scenario_hub=scenario_hub_report,
            guided_demo=guided_demo_report,
            pilot_launchpad=pilot_launchpad_report,
            enterprise_trust_center=enterprise_trust_center_report,
            commercial_offer_studio=commercial_offer_studio_report,
            business_case=business_case_report,
            productization=productization_report,
            vendor_portfolio=vendor_report,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
        )
        board_pack_report = build_board_pack(
            executive=executive,
            buyer_concierge=buyer_concierge_report,
            commercial_offer_studio=commercial_offer_studio_report,
            enterprise_trust_center=enterprise_trust_center_report,
            business_case=business_case_report,
            scenario_hub=scenario_hub_report,
            pilot_launchpad=pilot_launchpad_report,
            demo_command_center=demo_command_center_report,
            productization=productization_report,
            evidence_artifacts=artifacts,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
        )
        artifacts.append(
            _artifact(
                id="board-pack",
                title="Board Pack",
                route="/board-pack",
                report=board_pack_report,
                filename="board-pack",
                summary=board_pack_report.get("summary", {}),
            )
        )

    if include_outcome_ledger:
        demo_report = demo_report or build_demo_story(executive)
        value_packs_report = value_packs_report or build_value_packs(executive)
        vendor_report = vendor_report or build_vendor_portfolio(
            executive=executive,
            platform=platform,
            intake=intake,
            client_name=client_name,
        )
        business_case_report = business_case_report or build_business_case(
            executive=executive,
            platform=platform,
            intake=intake,
            vendor=vendor_report,
            value_packs=value_packs_report,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
            assumptions=business_assumptions,
        )
        productization_report = productization_report or productization_readiness()
        guided_demo_report = guided_demo_report or build_guided_demo(
            executive=executive,
            demo_story=demo_report,
            business_case=business_case_report,
            productization=productization_report,
            value_packs=value_packs_report,
            vendor_portfolio=vendor_report,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
        )
        scenario_hub_report = scenario_hub_report or build_scenario_hub(
            executive=executive,
            guided_demo=guided_demo_report,
            business_case=business_case_report,
            productization=productization_report,
            value_packs=value_packs_report,
            vendor_portfolio=vendor_report,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
        )
        pilot_launchpad_report = pilot_launchpad_report or build_pilot_launchpad(
            executive=executive,
            scenario_hub=scenario_hub_report,
            guided_demo=guided_demo_report,
            business_case=business_case_report,
            productization=productization_report,
            value_packs=value_packs_report,
            vendor_portfolio=vendor_report,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
        )
        demo_command_center_report = (
            demo_command_center_report
            or build_demo_command_center(
                executive=executive,
                scenario_hub=scenario_hub_report,
                guided_demo=guided_demo_report,
                pilot_launchpad=pilot_launchpad_report,
                business_case=business_case_report,
                productization=productization_report,
                vendor_portfolio=vendor_report,
                client_name=client_name,
                config_path=config_path,
                target_platform_version=target_platform_version,
            )
        )
        rights_report = rights_report or build_rights_rls(
            config_path=config_path, role_limit=60, object_limit=160
        )
        enterprise_trust_center_report = (
            enterprise_trust_center_report
            or build_enterprise_trust_center(
                executive=executive,
                platform=platform,
                business_case=business_case_report,
                productization=productization_report,
                offline_readiness=build_offline_readiness(
                    strict=False, include_metadata=False
                ),
                security_posture=build_security_posture(
                    config_path=config_path, limit=120, module_limit=1200
                ),
                rights_rls=rights_report,
                demo_command_center=demo_command_center_report,
                pilot_launchpad=pilot_launchpad_report,
                scenario_hub=scenario_hub_report,
                vendor_portfolio=vendor_report,
                evidence_artifacts=artifacts,
                client_name=client_name,
                config_path=config_path,
                target_platform_version=target_platform_version,
            )
        )
        commercial_offer_studio_report = (
            commercial_offer_studio_report
            or build_commercial_offer_studio(
                executive=executive,
                business_case=business_case_report,
                pilot_launchpad=pilot_launchpad_report,
                enterprise_trust_center=enterprise_trust_center_report,
                productization=productization_report,
                scenario_hub=scenario_hub_report,
                value_packs=value_packs_report,
                vendor_portfolio=vendor_report,
                client_name=client_name,
                config_path=config_path,
                target_platform_version=target_platform_version,
            )
        )
        buyer_concierge_report = buyer_concierge_report or build_buyer_concierge(
            executive=executive,
            scenario_hub=scenario_hub_report,
            guided_demo=guided_demo_report,
            pilot_launchpad=pilot_launchpad_report,
            enterprise_trust_center=enterprise_trust_center_report,
            commercial_offer_studio=commercial_offer_studio_report,
            business_case=business_case_report,
            productization=productization_report,
            vendor_portfolio=vendor_report,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
        )
        board_pack_report = board_pack_report or build_board_pack(
            executive=executive,
            buyer_concierge=buyer_concierge_report,
            commercial_offer_studio=commercial_offer_studio_report,
            enterprise_trust_center=enterprise_trust_center_report,
            business_case=business_case_report,
            scenario_hub=scenario_hub_report,
            pilot_launchpad=pilot_launchpad_report,
            demo_command_center=demo_command_center_report,
            productization=productization_report,
            evidence_artifacts=artifacts,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
        )
        outcome_ledger_report = build_outcome_ledger(
            executive=executive,
            board_pack=board_pack_report,
            buyer_concierge=buyer_concierge_report,
            commercial_offer_studio=commercial_offer_studio_report,
            enterprise_trust_center=enterprise_trust_center_report,
            business_case=business_case_report,
            scenario_hub=scenario_hub_report,
            pilot_launchpad=pilot_launchpad_report,
            demo_command_center=demo_command_center_report,
            productization=productization_report,
            value_packs=value_packs_report,
            vendor_portfolio=vendor_report,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
        )
        artifacts.append(
            _artifact(
                id="outcome-ledger",
                title="Outcome Ledger",
                route="/outcome-ledger",
                report=outcome_ledger_report,
                filename="outcome-ledger",
                summary=outcome_ledger_report.get("summary", {}),
            )
        )

    if include_launch_room:
        demo_report = demo_report or build_demo_story(executive)
        value_packs_report = value_packs_report or build_value_packs(executive)
        vendor_report = vendor_report or build_vendor_portfolio(
            executive=executive,
            platform=platform,
            intake=intake,
            client_name=client_name,
        )
        business_case_report = business_case_report or build_business_case(
            executive=executive,
            platform=platform,
            intake=intake,
            vendor=vendor_report,
            value_packs=value_packs_report,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
            assumptions=business_assumptions,
        )
        productization_report = productization_report or productization_readiness()
        guided_demo_report = guided_demo_report or build_guided_demo(
            executive=executive,
            demo_story=demo_report,
            business_case=business_case_report,
            productization=productization_report,
            value_packs=value_packs_report,
            vendor_portfolio=vendor_report,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
        )
        scenario_hub_report = scenario_hub_report or build_scenario_hub(
            executive=executive,
            guided_demo=guided_demo_report,
            business_case=business_case_report,
            productization=productization_report,
            value_packs=value_packs_report,
            vendor_portfolio=vendor_report,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
        )
        pilot_launchpad_report = pilot_launchpad_report or build_pilot_launchpad(
            executive=executive,
            scenario_hub=scenario_hub_report,
            guided_demo=guided_demo_report,
            business_case=business_case_report,
            productization=productization_report,
            value_packs=value_packs_report,
            vendor_portfolio=vendor_report,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
        )
        demo_command_center_report = (
            demo_command_center_report
            or build_demo_command_center(
                executive=executive,
                scenario_hub=scenario_hub_report,
                guided_demo=guided_demo_report,
                pilot_launchpad=pilot_launchpad_report,
                business_case=business_case_report,
                productization=productization_report,
                vendor_portfolio=vendor_report,
                client_name=client_name,
                config_path=config_path,
                target_platform_version=target_platform_version,
            )
        )
        rights_report = rights_report or build_rights_rls(
            config_path=config_path, role_limit=60, object_limit=160
        )
        enterprise_trust_center_report = (
            enterprise_trust_center_report
            or build_enterprise_trust_center(
                executive=executive,
                platform=platform,
                business_case=business_case_report,
                productization=productization_report,
                offline_readiness=build_offline_readiness(
                    strict=False, include_metadata=False
                ),
                security_posture=build_security_posture(
                    config_path=config_path, limit=120, module_limit=1200
                ),
                rights_rls=rights_report,
                demo_command_center=demo_command_center_report,
                pilot_launchpad=pilot_launchpad_report,
                scenario_hub=scenario_hub_report,
                vendor_portfolio=vendor_report,
                evidence_artifacts=artifacts,
                client_name=client_name,
                config_path=config_path,
                target_platform_version=target_platform_version,
            )
        )
        commercial_offer_studio_report = (
            commercial_offer_studio_report
            or build_commercial_offer_studio(
                executive=executive,
                business_case=business_case_report,
                pilot_launchpad=pilot_launchpad_report,
                enterprise_trust_center=enterprise_trust_center_report,
                productization=productization_report,
                scenario_hub=scenario_hub_report,
                value_packs=value_packs_report,
                vendor_portfolio=vendor_report,
                client_name=client_name,
                config_path=config_path,
                target_platform_version=target_platform_version,
            )
        )
        buyer_concierge_report = buyer_concierge_report or build_buyer_concierge(
            executive=executive,
            scenario_hub=scenario_hub_report,
            guided_demo=guided_demo_report,
            pilot_launchpad=pilot_launchpad_report,
            enterprise_trust_center=enterprise_trust_center_report,
            commercial_offer_studio=commercial_offer_studio_report,
            business_case=business_case_report,
            productization=productization_report,
            vendor_portfolio=vendor_report,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
        )
        board_pack_report = board_pack_report or build_board_pack(
            executive=executive,
            buyer_concierge=buyer_concierge_report,
            commercial_offer_studio=commercial_offer_studio_report,
            enterprise_trust_center=enterprise_trust_center_report,
            business_case=business_case_report,
            scenario_hub=scenario_hub_report,
            pilot_launchpad=pilot_launchpad_report,
            demo_command_center=demo_command_center_report,
            productization=productization_report,
            evidence_artifacts=artifacts,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
        )
        outcome_ledger_report = outcome_ledger_report or build_outcome_ledger(
            executive=executive,
            board_pack=board_pack_report,
            buyer_concierge=buyer_concierge_report,
            commercial_offer_studio=commercial_offer_studio_report,
            enterprise_trust_center=enterprise_trust_center_report,
            business_case=business_case_report,
            scenario_hub=scenario_hub_report,
            pilot_launchpad=pilot_launchpad_report,
            demo_command_center=demo_command_center_report,
            productization=productization_report,
            value_packs=value_packs_report,
            vendor_portfolio=vendor_report,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
        )
        launch_room_report = build_launch_room(
            executive=executive,
            buyer_concierge=buyer_concierge_report,
            scenario_hub=scenario_hub_report,
            demo_command_center=demo_command_center_report,
            enterprise_trust_center=enterprise_trust_center_report,
            commercial_offer_studio=commercial_offer_studio_report,
            board_pack=board_pack_report,
            outcome_ledger=outcome_ledger_report,
            business_case=business_case_report,
            pilot_launchpad=pilot_launchpad_report,
            evidence_bundle_artifacts=artifacts,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
        )
        artifacts.append(
            _artifact(
                id="launch-room",
                title="Launch Room",
                route="/launch-room",
                report=launch_room_report,
                filename="launch-room",
                summary=launch_room_report.get("summary", {}),
            )
        )

    if include_test_factory:
        test_factory_report = build_test_factory(
            store,
            changed_modules=changed,
            client_name=client_name,
            release_name=release_name,
        )
        artifacts.append(
            _artifact(
                id="test-factory",
                title="Test Factory",
                route="/testing",
                report=test_factory_report,
                filename="test-factory",
                summary=test_factory_report.get("summary", {}),
            )
        )

    if include_safe_autopilot:
        safe_autopilot_report = build_safe_autopilot(
            store,
            goal="Prepare safe 1C change proof",
            changed_modules=changed,
        )
        artifacts.append(
            _artifact(
                id="safe-autopilot",
                title="Safe Autopilot",
                route="/safe-autopilot",
                report=safe_autopilot_report,
                filename="safe-autopilot",
                summary=safe_autopilot_report.get("summary", {}),
            )
        )

    if include_governance_proof:
        governance_proof_report = build_governance_proof(
            client_name=client_name,
            bundle_id=bundle_id,
            generated_at=generated_at,
        )
        artifacts.append(
            _artifact(
                id="governance-proof",
                title="Governance Proof",
                route="/approvals",
                report=governance_proof_report,
                filename="governance-proof",
                summary=governance_proof_report.get("summary", {}),
            )
        )
        caveats.append(
            "Governance Proof reads local approval and audit stores; external ALM/SIEM proof depends on customer adapters."
        )

    if include_killer_demo:
        demo_report = demo_report or build_demo_story(executive)
        value_packs_report = value_packs_report or build_value_packs(executive)
        vendor_report = vendor_report or build_vendor_portfolio(
            executive=executive,
            platform=platform,
            intake=intake,
            client_name=client_name,
        )
        business_case_report = business_case_report or build_business_case(
            executive=executive,
            platform=platform,
            intake=intake,
            vendor=vendor_report,
            value_packs=value_packs_report,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
            assumptions=business_assumptions,
        )
        productization_report = productization_report or productization_readiness()
        guided_demo_report = guided_demo_report or build_guided_demo(
            executive=executive,
            demo_story=demo_report,
            business_case=business_case_report,
            productization=productization_report,
            value_packs=value_packs_report,
            vendor_portfolio=vendor_report,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
        )
        scenario_hub_report = scenario_hub_report or build_scenario_hub(
            executive=executive,
            guided_demo=guided_demo_report,
            business_case=business_case_report,
            productization=productization_report,
            value_packs=value_packs_report,
            vendor_portfolio=vendor_report,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
        )
        pilot_launchpad_report = pilot_launchpad_report or build_pilot_launchpad(
            executive=executive,
            scenario_hub=scenario_hub_report,
            guided_demo=guided_demo_report,
            business_case=business_case_report,
            productization=productization_report,
            value_packs=value_packs_report,
            vendor_portfolio=vendor_report,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
        )
        demo_command_center_report = (
            demo_command_center_report
            or build_demo_command_center(
                executive=executive,
                scenario_hub=scenario_hub_report,
                guided_demo=guided_demo_report,
                pilot_launchpad=pilot_launchpad_report,
                business_case=business_case_report,
                productization=productization_report,
                vendor_portfolio=vendor_report,
                client_name=client_name,
                config_path=config_path,
                target_platform_version=target_platform_version,
            )
        )
        rights_report = rights_report or build_rights_rls(
            config_path=config_path, role_limit=60, object_limit=160
        )
        enterprise_trust_center_report = (
            enterprise_trust_center_report
            or build_enterprise_trust_center(
                executive=executive,
                platform=platform,
                business_case=business_case_report,
                productization=productization_report,
                offline_readiness=build_offline_readiness(
                    strict=False, include_metadata=False
                ),
                security_posture=build_security_posture(
                    config_path=config_path, limit=120, module_limit=1200
                ),
                rights_rls=rights_report,
                demo_command_center=demo_command_center_report,
                pilot_launchpad=pilot_launchpad_report,
                scenario_hub=scenario_hub_report,
                vendor_portfolio=vendor_report,
                evidence_artifacts=artifacts,
                client_name=client_name,
                config_path=config_path,
                target_platform_version=target_platform_version,
            )
        )
        commercial_offer_studio_report = (
            commercial_offer_studio_report
            or build_commercial_offer_studio(
                executive=executive,
                business_case=business_case_report,
                pilot_launchpad=pilot_launchpad_report,
                enterprise_trust_center=enterprise_trust_center_report,
                productization=productization_report,
                scenario_hub=scenario_hub_report,
                value_packs=value_packs_report,
                vendor_portfolio=vendor_report,
                client_name=client_name,
                config_path=config_path,
                target_platform_version=target_platform_version,
            )
        )
        buyer_concierge_report = buyer_concierge_report or build_buyer_concierge(
            executive=executive,
            scenario_hub=scenario_hub_report,
            guided_demo=guided_demo_report,
            pilot_launchpad=pilot_launchpad_report,
            enterprise_trust_center=enterprise_trust_center_report,
            commercial_offer_studio=commercial_offer_studio_report,
            business_case=business_case_report,
            productization=productization_report,
            vendor_portfolio=vendor_report,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
        )
        board_pack_report = board_pack_report or build_board_pack(
            executive=executive,
            buyer_concierge=buyer_concierge_report,
            commercial_offer_studio=commercial_offer_studio_report,
            enterprise_trust_center=enterprise_trust_center_report,
            business_case=business_case_report,
            scenario_hub=scenario_hub_report,
            pilot_launchpad=pilot_launchpad_report,
            demo_command_center=demo_command_center_report,
            productization=productization_report,
            evidence_artifacts=artifacts,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
        )
        outcome_ledger_report = outcome_ledger_report or build_outcome_ledger(
            executive=executive,
            board_pack=board_pack_report,
            buyer_concierge=buyer_concierge_report,
            commercial_offer_studio=commercial_offer_studio_report,
            enterprise_trust_center=enterprise_trust_center_report,
            business_case=business_case_report,
            scenario_hub=scenario_hub_report,
            pilot_launchpad=pilot_launchpad_report,
            demo_command_center=demo_command_center_report,
            productization=productization_report,
            value_packs=value_packs_report,
            vendor_portfolio=vendor_report,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
        )
        launch_room_report = launch_room_report or build_launch_room(
            executive=executive,
            buyer_concierge=buyer_concierge_report,
            scenario_hub=scenario_hub_report,
            demo_command_center=demo_command_center_report,
            enterprise_trust_center=enterprise_trust_center_report,
            commercial_offer_studio=commercial_offer_studio_report,
            board_pack=board_pack_report,
            outcome_ledger=outcome_ledger_report,
            business_case=business_case_report,
            pilot_launchpad=pilot_launchpad_report,
            evidence_bundle_artifacts=artifacts,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
        )
        test_factory_report = test_factory_report or build_test_factory(
            store,
            changed_modules=changed,
            client_name=client_name,
            release_name=release_name,
        )
        killer_demo_report = build_killer_demo_path(
            launch_room=launch_room_report,
            demo_command_center=demo_command_center_report,
            test_factory=test_factory_report,
            buyer_concierge=buyer_concierge_report,
            scenario_hub=scenario_hub_report,
            enterprise_trust_center=enterprise_trust_center_report,
            commercial_offer_studio=commercial_offer_studio_report,
            board_pack=board_pack_report,
            outcome_ledger=outcome_ledger_report,
            client_name=client_name,
            config_path=config_path,
            target_platform_version=target_platform_version,
            evidence_bundle={
                "bundle_id": bundle_id,
                "artifacts": artifacts,
                "manifest": _manifest(artifacts),
            },
        )
        artifacts.append(
            _artifact(
                id="killer-demo",
                title="Killer Demo Path",
                route="/killer-demo",
                report=killer_demo_report,
                filename="killer-demo",
                summary=killer_demo_report.get("summary", {}),
            )
        )

    if include_update:
        update = build_update_war_room(
            store,
            config_path=config_path,
            target_platform_version=target_platform_version,
            release_name=release_name,
            changed_modules=changed,
        )
        artifacts.append(
            _artifact(
                id="update-war-room",
                title="Update War Room",
                route="/update-war-room",
                report=update,
                filename="update-war-room",
                summary=update.get("summary", {}),
            )
        )

    if include_lock_radar:
        lock_radar = build_lock_radar(
            store,
            log_path=lock_radar_log_path,
            changed_modules=changed,
        )
        artifacts.append(
            _artifact(
                id="lock-radar",
                title="Lock Radar",
                route="/lock-radar",
                report=lock_radar,
                filename="lock-radar",
                summary=lock_radar.get("summary", {}),
            )
        )

    if include_extension_safety:
        extension_safety = build_extension_safety(
            store,
            config_path=config_path,
            changed_modules=changed,
        )
        artifacts.append(
            _artifact(
                id="extension-safety",
                title="Extension Safety",
                route="/extension-safety",
                report=extension_safety,
                filename="extension-safety",
                summary=extension_safety.get("summary", {}),
            )
        )

    if include_rights:
        rights_report = rights_report or build_rights_rls(
            config_path=config_path, role_limit=60, object_limit=160
        )
        artifacts.append(
            _artifact(
                id="rights-rls",
                title="Rights & RLS",
                route="/rights-rls",
                report=rights_report,
                filename="rights-rls",
                summary=rights_report.get("summary", {}),
            )
        )

    manifest = _manifest(artifacts)
    manifest_payload = {
        "bundle_id": bundle_id,
        "generated_at": generated_at,
        "client_name": client_name,
        **manifest,
    }
    manifest_payload["bundle_sha256"] = _sha256_text(
        _json_text(manifest_payload["files"])
    )
    risky = [
        item
        for item in artifacts
        if item["status"] in {"risk", "fail", "critical", "blocked"}
    ]
    watch = [
        item for item in artifacts if item["status"] in {"watch", "warn", "partial"}
    ]
    commercial_assumptions = _commercial_assumption_receipt(
        business_case_report, business_assumptions
    )
    procurement_handoff = _build_procurement_handoff(
        bundle_id=bundle_id,
        generated_at=generated_at,
        client_name=client_name,
        artifacts=artifacts,
        manifest=manifest_payload,
        risky=risky,
        watch=watch,
        commercial_assumptions=commercial_assumptions,
    )
    score = max(0, 100 - len(risky) * 12 - len(watch) * 5)
    report: dict[str, Any] = {
        "bundle_id": bundle_id,
        "generated_at": generated_at,
        "client": {
            "name": client_name,
            "config_path": config_path or "",
            "target_platform_version": target_platform_version or "",
        },
        "decision": {
            "status": "risk" if risky else "watch" if watch else "ready",
            "score": score,
            "headline": "Evidence bundle собран: отчеты, caveats и SHA-256 manifest готовы для approval/КП.",
        },
        "summary": {
            "artifacts": len(artifacts),
            "files": manifest_payload["total_files"],
            "risk_artifacts": len(risky),
            "watch_artifacts": len(watch),
            "changed_modules": len(changed),
            "procurement_required_files": len(procurement_handoff["required_files"]),
            "procurement_missing_files": len(procurement_handoff["missing_files"]),
            "procurement_blockers": len(procurement_handoff["blockers"]),
            "procurement_recipients": len(procurement_handoff["recipients"]),
            "procurement_ready": procurement_handoff["ready_to_forward"],
            "commercial_assumption_source": commercial_assumptions["source"],
        },
        "artifacts": artifacts,
        "manifest": manifest_payload,
        "procurement_handoff": procurement_handoff,
        "commercial_assumptions": commercial_assumptions,
        "caveats": caveats,
    }
    report["procurement_handoff"]["recipient_packets"] = _recipient_packets(report)
    report["archive_acceptance_receipt"] = _archive_acceptance_receipt(report)
    report["summary"]["archive_acceptance_steps"] = len(
        report["archive_acceptance_receipt"]["acceptance_steps"]
    )
    report["markdown"] = _bundle_markdown(report)
    report["open_first_markdown"] = _open_first_markdown(report)
    report["download_name"] = f"{bundle_id}-evidence-bundle.md"
    return report


def _intake_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# 1C Configuration Intake",
        "",
        f"Status: **{(plan.get('decision') or {}).get('status', 'unknown')}**",
        f"Score: **{(plan.get('decision') or {}).get('score', 0)}**",
        f"Path: `{(plan.get('source') or {}).get('path', '')}`",
        "",
        "## Coverage",
        "",
    ]
    for item in plan.get("coverage", []):
        lines.append(
            f"- **{item.get('status')}** {item.get('title')}: {item.get('count')}"
        )
    lines.extend(["", "## Caveats", ""])
    lines.extend(f"- {item}" for item in plan.get("caveats", []))
    return "\n".join(lines)
