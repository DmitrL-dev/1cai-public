"""Buyer concierge that turns a large Rentgen surface into first-click guidance."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.services.rentgen.open_first_path import (
    OPEN_FIRST_PATH_FILE,
    build_open_first_path,
    open_first_path_markdown_lines,
)


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


def _first_offer(commercial_offer_studio: dict[str, Any], offer_id: str) -> dict[str, Any]:
    for offer in commercial_offer_studio.get("offers", []):
        if offer.get("id") == offer_id:
            return offer
    return {}


def _month_line(months: int) -> str:
    return f"{months} months by visible value" if months else "review Business Case"


def _proof_file(route: str) -> str:
    names = {
        "/quality": "quality-findings.md",
        "/change": "change-impact.md",
        "/testing": "test-factory.md",
        "/release-readiness": "release-readiness.md",
        "/platform-doctor": "platform-doctor.md",
        "/architecture": "architecture-map.md",
        "/enterprise-trust-center": "enterprise-trust-center.md",
        "/evidence-bundle": "OPEN_FIRST.md",
        "/business-case": "business-case.md",
        "/commercial-offer-studio": "commercial-offer-studio.md",
        "/vendor-portfolio": "vendor-audit.md",
        "/lock-radar": "lock-radar.md",
    }
    return names.get(route, "evidence-bundle.md")


def _persona_cards(
    *,
    business_case: dict[str, Any],
    enterprise_trust_center: dict[str, Any],
    commercial_offer_studio: dict[str, Any],
    scenario_hub: dict[str, Any],
) -> list[dict[str, Any]]:
    summary = business_case.get("summary") or {}
    assumptions = business_case.get("assumptions") or {}
    currency = str(assumptions.get("currency") or "RUB")
    trust_summary = enterprise_trust_center.get("summary") or {}
    offer_summary = commercial_offer_studio.get("summary") or {}
    scenarios = {
        item.get("id"): item
        for item in scenario_hub.get("scenarios", [])
        if item.get("id")
    }
    return [
        {
            "id": "developer",
            "role": "Developer",
            "first_question": "Can this catch a real 1C bug before review?",
            "start_route": "/quality",
            "second_route": "/change",
            "spark": (scenarios.get("left-join-null") or {}).get("title", "LEFT JOIN field without NULL guard"),
            "proof": "Show one deterministic finding, safe rewrite and test expectation.",
            "buy_trigger": "A real module gets a finding, impact route and regression expectation.",
            "purchase_route": "/evidence-bundle",
            "purchase_ask": "Attach the defect proof to a paid proof sprint or release gate.",
            "proof_file": _proof_file("/quality"),
            "time_to_value_minutes": 2,
        },
        {
            "id": "architect",
            "role": "Architect",
            "first_question": "Does it understand configuration topology and platform risk?",
            "start_route": "/platform-doctor",
            "second_route": "/architecture",
            "spark": (scenarios.get("platform-upgrade") or {}).get("title", "Platform or update risk"),
            "proof": "Connect platform, compatibility, extensions, rights and release caveats.",
            "buy_trigger": "The first upgrade or extension decision becomes evidence-backed.",
            "purchase_route": "/enterprise-trust-center",
            "purchase_ask": "Turn platform caveats into hardening scope or enterprise acceptance.",
            "proof_file": _proof_file("/platform-doctor"),
            "time_to_value_minutes": 3,
        },
        {
            "id": "director",
            "role": "Director",
            "first_question": "Why buy this instead of another AI subscription?",
            "start_route": "/business-case",
            "second_route": "/commercial-offer-studio",
            "spark": f"First-year visible value: {_money(summary.get('first_year_visible_value'), currency)}.",
            "proof": "Show local product value, recurring spend displacement and buyable offers.",
            "buy_trigger": f"Offer Studio has {_int(offer_summary.get('offers'))} packages with price anchors.",
            "purchase_route": "/launch-room",
            "purchase_ask": "Open the purchase cockpit and choose proof sprint, pilot or local license.",
            "proof_file": "launch-room.md",
            "time_to_value_minutes": 3,
        },
        {
            "id": "security",
            "role": "Security / CIO",
            "first_question": "Can this live in our contour with inspectable artifacts?",
            "start_route": "/enterprise-trust-center",
            "second_route": "/evidence-bundle",
            "spark": f"Trust controls: {_int(trust_summary.get('controls'))}; failed controls: {_int(trust_summary.get('failed_controls'))}.",
            "proof": "Local contour, SBOM/offline, Rights/RLS, platform caveats and hash manifest.",
            "buy_trigger": "Security names the required artifact for pilot approval.",
            "purchase_route": "/enterprise-trust-center",
            "purchase_ask": "Approve install contour and evidence retention before optional AI add-ons.",
            "proof_file": _proof_file("/enterprise-trust-center"),
            "time_to_value_minutes": 3,
        },
        {
            "id": "vendor",
            "role": "Vendor / Franchisee",
            "first_question": "Can this become a paid audit and repeatable proposal?",
            "start_route": "/vendor-portfolio",
            "second_route": "/commercial-offer-studio",
            "spark": (_first_offer(commercial_offer_studio, "vendor-portfolio-rollout") or {}).get("commercial_frame", "Partner rollout offer is available."),
            "proof": "Vendor Portfolio, Value Packs and Offer Studio turn scan evidence into packaged work.",
            "buy_trigger": "Partner sends one buyer-safe report and scopes the first work package.",
            "purchase_route": "/commercial-offer-studio",
            "purchase_ask": "Convert the first audit into a packaged paid rollout offer.",
            "proof_file": _proof_file("/vendor-portfolio"),
            "time_to_value_minutes": 4,
        },
        {
            "id": "release",
            "role": "QA / Release",
            "first_question": "Can it change our release meeting?",
            "start_route": "/release-readiness",
            "second_route": "/evidence-bundle",
            "spark": (scenarios.get("release-go-no-go") or {}).get("title", "Can we release today?"),
            "proof": "Show gates, test gaps, owner actions and portable approval artifacts.",
            "buy_trigger": "The release board gets one go/no-go artifact instead of screenshots.",
            "purchase_route": "/evidence-bundle",
            "purchase_ask": "Make the release artifact a repeatable acceptance gate.",
            "proof_file": _proof_file("/release-readiness"),
            "time_to_value_minutes": 4,
        },
        {
            "id": "operations",
            "role": "Operations",
            "first_question": "Can runtime pain connect back to code and platform?",
            "start_route": "/lock-radar",
            "second_route": "/operations",
            "spark": (scenarios.get("locks-after-release") or {}).get("title", "Locks or slowdowns after release"),
            "proof": "Use tech journal, Platform Doctor and runbooks to connect runtime symptoms to owner actions.",
            "buy_trigger": "Operations stops owning incidents alone; release/code context is visible.",
            "purchase_route": "/launch-room",
            "purchase_ask": "Route incident evidence to the owner, acceptance and renewal decision.",
            "proof_file": _proof_file("/lock-radar"),
            "time_to_value_minutes": 4,
        },
    ]


def _pain_picker(scenario_hub: dict[str, Any]) -> list[dict[str, Any]]:
    scenarios = scenario_hub.get("scenarios", [])
    preferred = [
        "left-join-null",
        "release-go-no-go",
        "platform-upgrade",
        "local-enterprise-proof",
        "rights-rls",
        "vendor-presale-audit",
        "locks-after-release",
        "architecture-map",
    ]
    by_id = {item.get("id"): item for item in scenarios if item.get("id")}
    result: list[dict[str, Any]] = []
    for scenario_id in preferred:
        item = by_id.get(scenario_id)
        if not item:
            continue
        result.append(
            {
                "scenario_id": scenario_id,
                "title": str(item.get("title") or scenario_id),
                "pain": str(item.get("pain") or ""),
                "role": str(item.get("primary_role") or "all"),
                "route": str(item.get("route") or "/scenario-hub"),
                "why_now": str(item.get("why_buy_now") or ""),
                "minutes": float(item.get("minutes") or 1),
            }
        )
    return result


def _shortest_paths() -> list[dict[str, Any]]:
    return [
        {
            "id": "five-minute-buyer",
            "title": "5-minute buyer route",
            "audience": "director + mixed room",
            "total_minutes": 5,
            "steps": [
                {"label": "Buyer Concierge", "route": "/buyer-concierge", "minutes": 0.5, "why": "pick role or pain"},
                {"label": "Scenario Hub", "route": "/scenario-hub", "minutes": 1.0, "why": "make the product concrete"},
                {"label": "Business Case", "route": "/business-case", "minutes": 1.0, "why": "money and local asset"},
                {"label": "Enterprise Trust Center", "route": "/enterprise-trust-center", "minutes": 1.0, "why": "security pre-answer"},
                {"label": "Commercial Offer Studio", "route": "/commercial-offer-studio", "minutes": 1.5, "why": "pick paid package"},
            ],
            "close": "Pick proof sprint, local pilot or enterprise license path.",
        },
        {
            "id": "developer-spark",
            "title": "Developer spark route",
            "audience": "developer + QA",
            "total_minutes": 4,
            "steps": [
                {"label": "Quality", "route": "/quality", "minutes": 1.0, "why": "LEFT JOIN/NULL defect"},
                {"label": "Change Impact", "route": "/change", "minutes": 1.0, "why": "blast radius"},
                {"label": "Testing", "route": "/testing", "minutes": 1.0, "why": "regression expectation"},
                {"label": "Evidence Bundle", "route": "/evidence-bundle", "minutes": 1.0, "why": "portable proof"},
            ],
            "close": "Ask whether this would have saved a recent review or regression.",
        },
        {
            "id": "architect-trust",
            "title": "Architect and security trust route",
            "audience": "architect + security",
            "total_minutes": 6,
            "steps": [
                {"label": "Platform Doctor", "route": "/platform-doctor", "minutes": 1.5, "why": "platform/update facts"},
                {"label": "Rights/RLS", "route": "/rights-rls", "minutes": 1.0, "why": "access gate"},
                {"label": "Enterprise Trust Center", "route": "/enterprise-trust-center", "minutes": 2.0, "why": "trust questions"},
                {"label": "Commercial Offer Studio", "route": "/commercial-offer-studio", "minutes": 1.5, "why": "hardening or license package"},
            ],
            "close": "Name the first blocker, accepted risk or hardening package.",
        },
        {
            "id": "vendor-buy-now",
            "title": "Vendor buy-now route",
            "audience": "franchisee / implementation partner",
            "total_minutes": 6,
            "steps": [
                {"label": "Vendor Portfolio", "route": "/vendor-portfolio", "minutes": 1.5, "why": "audit signals"},
                {"label": "Value Packs", "route": "/value-packs", "minutes": 1.0, "why": "sellable outcomes"},
                {"label": "Commercial Offer Studio", "route": "/commercial-offer-studio", "minutes": 2.0, "why": "partner rollout offer"},
                {"label": "Evidence Bundle", "route": "/evidence-bundle", "minutes": 1.5, "why": "buyer-safe export"},
            ],
            "close": "Pick first portfolio client and paid proof sprint.",
        },
    ]


def _default_next_action(
    *,
    scenario_hub: dict[str, Any],
    commercial_offer_studio: dict[str, Any],
    enterprise_trust_center: dict[str, Any],
) -> dict[str, str]:
    if _status(enterprise_trust_center) == "risk":
        return {
            "label": "Start with Trust Center",
            "route": "/enterprise-trust-center",
            "reason": "Security/productization caveats are visible; name them before selling rollout.",
        }
    if _score(commercial_offer_studio) >= 82:
        return {
            "label": "Open Offer Studio",
            "route": "/commercial-offer-studio",
            "reason": "Proof and trust are strong enough to choose a paid package.",
        }
    return {
        "label": "Open Scenario Hub",
        "route": "/scenario-hub",
        "reason": f"Use pain-led orientation first; Scenario Hub status is {_status(scenario_hub)} / {_score(scenario_hub)}.",
    }


def _purchase_router(
    *,
    business_case: dict[str, Any],
    commercial_offer_studio: dict[str, Any],
    enterprise_trust_center: dict[str, Any],
) -> dict[str, Any]:
    assumptions = business_case.get("assumptions") or {}
    summary = business_case.get("summary") or {}
    escape = business_case.get("subscription_escape_plan") or {}
    dossier = commercial_offer_studio.get("procurement_dossier") or {}
    dossier_escape = dossier.get("subscription_escape") or {}
    close_packet = commercial_offer_studio.get("close_packet") or {}
    one_page_order = close_packet.get("one_page_order") or {}
    recommended = dossier.get("recommended_purchase") or {}
    currency = str(escape.get("currency") or assumptions.get("currency") or "RUB")

    monthly_ai = _int(escape.get("monthly_ai_rent") or assumptions.get("monthly_ai_subscription_cost"))
    annual_ai = _int(escape.get("annual_ai_rent") or summary.get("ai_subscription_year") or monthly_ai * 12)
    three_year_ai = _int(escape.get("three_year_ai_rent") or summary.get("three_year_ai_subscription") or annual_ai * 3)
    local_license = _int(escape.get("local_license_anchor") or summary.get("local_license_anchor"))
    break_even = _int(escape.get("break_even_months") or summary.get("subscription_break_even_months"))
    ai_rent_months = _int(escape.get("ai_rent_equivalent_months") or summary.get("subscription_escape_months"))
    first_year_value = _int(summary.get("first_year_visible_value"))

    route = str(one_page_order.get("route") or recommended.get("route") or "/commercial-offer-studio")
    recommended_purchase = str(
        one_page_order.get("recommended_purchase") or recommended.get("title") or "24-hour proof sprint"
    )
    commercial_frame = str(
        one_page_order.get("commercial_frame") or recommended.get("commercial_frame") or "fixed paid next step"
    )
    value_anchor = str(
        one_page_order.get("value_anchor")
        or dossier_escape.get("local_value_anchor")
        or _money(first_year_value, currency)
    )
    break_even_line = str(one_page_order.get("break_even") or _month_line(break_even))
    status = "ready" if local_license and three_year_ai else "watch"
    trust_status = _status(enterprise_trust_center)
    if trust_status in {"risk", "fail", "blocked", "critical"}:
        status = "watch"

    if monthly_ai:
        buyer_line = (
            f"Current AI rent baseline is {_money(monthly_ai, currency)}/month and "
            f"{_money(three_year_ai, currency)} over three years; anchor a local license at "
            f"{_money(local_license, currency)} with {break_even_line}."
        )
    else:
        buyer_line = (
            "No AI rent baseline was entered; route the buyer through local value, risk reduction "
            "and procurement-ready evidence instead."
        )

    guardrails = list(dossier_escape.get("guardrails") or escape.get("guardrails") or [])[:4]
    if not guardrails:
        guardrails = [
            "Sell the local evidence product first; keep external AI credits optional.",
            "Name security, platform and evidence caveats before asking for rollout.",
            "Convert every role demo into one artifact the buyer can forward.",
        ]

    evidence_files = [
        {"title": "Launch Room", "filename": "launch-room.md", "route": "/launch-room"},
        {"title": "Business Case", "filename": "business-case.md", "route": "/business-case"},
        {"title": "Commercial Offer Studio", "filename": "commercial-offer-studio.md", "route": "/commercial-offer-studio"},
        {"title": "Evidence Bundle", "filename": "OPEN_FIRST.md", "route": "/evidence-bundle"},
    ]
    for item in dossier_escape.get("evidence_files") or escape.get("evidence_files") or []:
        if item.get("route") and item.get("route") not in {entry["route"] for entry in evidence_files}:
            evidence_files.append(
                {
                    "title": str(item.get("title") or item.get("route")),
                    "filename": str(item.get("filename") or _proof_file(str(item.get("route")))),
                    "route": str(item.get("route")),
                }
            )

    return {
        "status": status,
        "headline": "Route role curiosity into one local-license buying motion.",
        "buyer_line": buyer_line,
        "primary_route": "/launch-room",
        "primary_label": "Open Launch Room",
        "recommended_purchase": recommended_purchase,
        "recommended_route": route,
        "commercial_frame": commercial_frame,
        "first_invoice_trigger": str(
            one_page_order.get("first_invoice_trigger")
            or "Buyer names owner, scope, date and accepted proof artifacts."
        ),
        "value_anchor": value_anchor,
        "monthly_ai_rent": _money(monthly_ai, currency),
        "annual_ai_rent": _money(annual_ai, currency),
        "three_year_ai_rent": _money(three_year_ai, currency),
        "local_license_anchor": _money(local_license, currency),
        "break_even": break_even_line,
        "ai_rent_equivalent_months": ai_rent_months,
        "quick_actions": [
            {
                "label": "Start buyer room",
                "route": "/launch-room",
                "why": "Show next best action, purchase spine, role path and proof packet in one cockpit.",
            },
            {
                "label": "Prove value",
                "route": "/business-case",
                "why": "Expose assumptions, visible value and subscription escape math.",
            },
            {
                "label": "Choose paid step",
                "route": "/commercial-offer-studio",
                "why": "Select proof sprint, pilot, hardening pack or enterprise local license.",
            },
            {
                "label": "Forward proof",
                "route": "/evidence-bundle",
                "why": "Hand procurement a hashed archive with markdown, JSON, caveats and manifest.",
            },
        ],
        "role_prompts": [
            {
                "role": "Developer",
                "route": "/quality",
                "ask": "Show one real LEFT JOIN/NULL or review defect, then attach the proof file.",
                "close": "Would this have prevented a recent review loop or regression?",
                "proof_file": _proof_file("/quality"),
            },
            {
                "role": "Architect",
                "route": "/platform-doctor",
                "ask": "Show configuration topology, platform/update caveats and extension risk.",
                "close": "Which upgrade or extension decision should become the paid pilot scope?",
                "proof_file": _proof_file("/platform-doctor"),
            },
            {
                "role": "Director",
                "route": "/launch-room",
                "ask": "Compare AI rent with a local reusable evidence asset and open the paid next step.",
                "close": f"Should we approve {recommended_purchase} with proof artifacts attached?",
                "proof_file": "launch-room.md",
            },
            {
                "role": "Security / CIO",
                "route": "/enterprise-trust-center",
                "ask": "Approve locality, SBOM/offline posture, Rights/RLS and evidence retention.",
                "close": "What artifact unblocks pilot approval?",
                "proof_file": _proof_file("/enterprise-trust-center"),
            },
            {
                "role": "Vendor",
                "route": "/commercial-offer-studio",
                "ask": "Turn the audit into a repeatable paid offer with acceptance criteria.",
                "close": "Which client receives the first proof sprint proposal?",
                "proof_file": _proof_file("/vendor-portfolio"),
            },
        ],
        "close_sequence": [
            {
                "window": "Today",
                "owner": "sponsor + seller",
                "action": "Pick the role pain and route it through Launch Room.",
                "route": "/launch-room",
            },
            {
                "window": "24 hours",
                "owner": "tech lead",
                "action": "Run one proof route and export Evidence Bundle.",
                "route": "/evidence-bundle",
            },
            {
                "window": "48 hours",
                "owner": "security + finance",
                "action": "Accept caveats, value assumptions and paid next step.",
                "route": "/commercial-offer-studio",
            },
        ],
        "evidence_files": evidence_files[:8],
        "guardrails": guardrails,
        "proof_routes": sorted(
            {"/launch-room", "/business-case", "/commercial-offer-studio", "/evidence-bundle", route}
            | {item["route"] for item in evidence_files}
        ),
    }


def _confusion_guardrails() -> list[dict[str, str]]:
    return [
        {
            "signal": "Buyer scans the sidebar and gets quiet.",
            "response": "Do not explain every module. Ask for role or pain and open Buyer Concierge or Scenario Hub.",
            "route": "/buyer-concierge",
        },
        {
            "signal": "Developer says it looks like another generic AI assistant.",
            "response": "Open the LEFT JOIN/NULL path in Quality, then Change Impact and Testing.",
            "route": "/quality",
        },
        {
            "signal": "Architect asks about platform, EDT, compatibility or updates.",
            "response": "Open Platform Doctor, then Trust Center for the install and caveat story.",
            "route": "/platform-doctor",
        },
        {
            "signal": "Security asks if code leaves the contour.",
            "response": "Open Enterprise Trust Center before Productization details.",
            "route": "/enterprise-trust-center",
        },
        {
            "signal": "Director asks price too early.",
            "response": "Open Business Case for value anchor, then Offer Studio for packages.",
            "route": "/commercial-offer-studio",
        },
        {
            "signal": "Meeting time is cut to three minutes.",
            "response": "Use Buyer Concierge -> Business Case -> Trust Center -> Offer Studio.",
            "route": "/buyer-concierge",
        },
    ]


def _exports() -> list[dict[str, str]]:
    return [
        {"title": "Buyer Brief markdown", "filename": "buyer-brief.md", "route": "/"},
        {"title": "Buyer Pulse markdown", "filename": "buyer-pulse.md", "route": "/"},
        {"title": "Buyer Concierge markdown", "filename": "rentgen-buyer-concierge.md", "route": "/buyer-concierge"},
        {"title": "Scenario Hub markdown", "filename": "rentgen-scenario-hub.md", "route": "/scenario-hub"},
        {"title": "Commercial Offer Studio markdown", "filename": "rentgen-commercial-offer-studio.md", "route": "/commercial-offer-studio"},
        {"title": "Enterprise Trust Center markdown", "filename": "rentgen-enterprise-trust-center.md", "route": "/enterprise-trust-center"},
        {"title": "Evidence Bundle manifest", "filename": "evidence-bundle-manifest.json", "route": "/evidence-bundle"},
    ]


def _concierge_room_bridge(
    *,
    buyer_brief: dict[str, Any] | None,
    default_next_action: dict[str, str],
    persona_cards: list[dict[str, Any]],
    purchase_router: dict[str, Any],
) -> dict[str, Any]:
    brief = buyer_brief or {}
    primary = dict(brief.get("primary_motion") or {})
    if not primary:
        primary = {
            "label": str(default_next_action.get("label") or "Open buyer route"),
            "route": str(default_next_action.get("route") or "/buyer-concierge"),
            "status": str(purchase_router.get("status") or "watch"),
            "ask": "Pick the role or pain, then open the shortest proof path.",
            "reason": str(default_next_action.get("reason") or "Buyer Concierge prevents first-screen confusion."),
        }

    concierge_motion = {
        "label": str(default_next_action.get("label") or "Open Buyer Concierge"),
        "route": str(default_next_action.get("route") or "/buyer-concierge"),
        "status": str(purchase_router.get("status") or primary.get("status") or "watch"),
        "ask": str(default_next_action.get("reason") or "Use role, pain and proof route before showing the larger product."),
        "reason": "The first screen should choose the buyer path before deep workbench pages appear.",
    }

    role_cards = list(brief.get("role_cards") or [])
    if not role_cards:
        role_cards = [
            {
                "role": item["id"],
                "title": item["role"],
                "route": item["start_route"],
                "status": "ready",
                "spark": item["spark"],
                "proof_file": item["proof_file"],
                "purchase_ask": item["purchase_ask"],
            }
            for item in persona_cards[:5]
        ]

    proof_readiness = list(brief.get("proof_readiness") or [])
    if not proof_readiness:
        proof_readiness = [
            {
                "id": "launch-room",
                "title": "Launch Room",
                "route": "/launch-room",
                "status": str(purchase_router.get("status") or "watch"),
                "signal": "One cockpit for role path, purchase spine and proof packet.",
                "file": "launch-room.md",
            },
            {
                "id": "commercial-offer",
                "title": "Commercial Offer",
                "route": "/commercial-offer-studio",
                "status": str(purchase_router.get("status") or "watch"),
                "signal": str(purchase_router.get("recommended_purchase") or "Paid next step is selected."),
                "file": "rentgen-commercial-offer-studio.md",
            },
            {
                "id": "evidence-bundle",
                "title": "Evidence Bundle",
                "route": "/evidence-bundle",
                "status": "ready",
                "signal": "Forward buyer brief, role packets and hash-verifiable artifacts.",
                "file": "OPEN_FIRST.md",
            },
            {
                "id": "trust",
                "title": "Enterprise Trust",
                "route": "/enterprise-trust-center",
                "status": "ready",
                "signal": "Answer locality, SBOM/offline, rights and procurement questions.",
                "file": "rentgen-security-questionnaire.md",
            },
        ]

    meeting_flow = list(brief.get("meeting_flow") or [])
    if not meeting_flow:
        meeting_flow = [
            {"step": 1, "label": "Orient", "route": "/buyer-concierge", "line": "Pick role or pain before opening the large product map."},
            {"step": 2, "label": "Prove", "route": "/killer-demo", "line": "Compress the chosen pain into one buyer-ready demo path."},
            {"step": 3, "label": "Ask", "route": "/launch-room", "line": str(purchase_router.get("first_invoice_trigger") or "Name owner, scope and paid next step.")},
            {"step": 4, "label": "Forward", "route": "/evidence-bundle", "line": "Send buyer brief, pulse, role files and proof archive."},
        ]
    open_first_path = build_open_first_path(
        existing_path=brief.get("open_first_path"),
        proof_readiness=proof_readiness,
        primary=primary,
        meeting_flow=meeting_flow,
        source="buyer-concierge-fallback",
        orient_title="Buyer Concierge",
        orient_route="/buyer-concierge",
        orient_line="Pick role or pain before opening the large product map.",
        orient_status=str(primary.get("status") or purchase_router.get("status") or "watch"),
        prove_line="Compress the chosen pain into one buyer-ready demo path.",
        close_title="Launch Room",
        close_route="/launch-room",
        close_line=str(purchase_router.get("first_invoice_trigger") or "Name owner, scope and paid next step."),
        close_file="launch-room.md",
        close_status=str(purchase_router.get("status") or primary.get("status") or "watch"),
        verify_line="Send buyer brief, pulse, role files and proof archive.",
    )

    routes = sorted(
        {
            "/buyer-concierge",
            str(primary.get("route") or "/buyer-concierge"),
            str(concierge_motion["route"]),
            *[str(item.get("route") or "") for item in role_cards],
            *[str(item.get("route") or "") for item in proof_readiness],
            *[str(item.get("route") or "") for item in meeting_flow],
            *[str(item.get("route") or "") for item in open_first_path],
            *[str(item.get("route") or "") for item in purchase_router.get("quick_actions", [])],
            *[str(item.get("route") or "") for item in purchase_router.get("role_prompts", [])],
            *[str(item.get("route") or "") for item in purchase_router.get("evidence_files", [])],
        }
        - {""}
    )
    return {
        "status": str(brief.get("purchase_status") or primary.get("status") or purchase_router.get("status") or "watch"),
        "score": _int(brief.get("score"), 76),
        "source": str(brief.get("source") or "buyer-concierge-derived"),
        "room_line": str(
            brief.get("room_line")
            or f"{primary.get('label', 'Open buyer route')}: {primary.get('ask', 'Pick role or pain and prove it.')}"
        ),
        "primary_motion": {
            "label": str(primary.get("label") or "Open buyer route"),
            "route": str(primary.get("route") or "/buyer-concierge"),
            "status": str(primary.get("status") or purchase_router.get("status") or "watch"),
            "ask": str(primary.get("ask") or "Pick role or pain and prove it."),
            "reason": str(primary.get("reason") or "Buyer Concierge keeps the first route small and role-specific."),
        },
        "concierge_motion": concierge_motion,
        "role_cards": role_cards[:5],
        "proof_readiness": proof_readiness[:4],
        "meeting_flow": meeting_flow[:4],
        "open_first_path": open_first_path[:4],
        "files": ["buyer-brief.md", "buyer-pulse.md", OPEN_FIRST_PATH_FILE, "rentgen-buyer-concierge.md", "launch-room.md", "OPEN_FIRST.md"],
        "routes": routes,
        "close_question": "Which role pain is strong enough to open Launch Room and paid proof?",
    }


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 1C Rentgen Buyer Concierge",
        "",
        f"Client: **{report['client']['name']}**",
        f"Status: **{report['decision']['status'].upper()}** / score **{report['decision']['score']}**",
        f"Default next action: **{report['default_next_action']['label']}** (`{report['default_next_action']['route']}`)",
        "",
        "## Purchase Router",
        "",
        f"- Status: **{report['purchase_router']['status']}**",
        f"- Buyer line: {report['purchase_router']['buyer_line']}",
        f"- Recommended purchase: **{report['purchase_router']['recommended_purchase']}** (`{report['purchase_router']['recommended_route']}`)",
        f"- Three-year AI rent: **{report['purchase_router']['three_year_ai_rent']}**",
        f"- Local license anchor: **{report['purchase_router']['local_license_anchor']}**",
        f"- Break-even: **{report['purchase_router']['break_even']}**",
        "",
        "## Concierge Room Bridge",
        "",
    ]
    bridge = report.get("concierge_room_bridge") or {}
    if bridge:
        lines.append(f"- Source: **{bridge.get('source', 'n/a')}**; status **{bridge.get('status', 'watch')}** / score **{bridge.get('score', 0)}**")
        lines.append(f"- Room line: {bridge.get('room_line', '')}")
        motion = bridge.get("primary_motion") or {}
        lines.append(f"- Primary motion: **{motion.get('label', 'n/a')}** (`{motion.get('route', '/buyer-concierge')}`): {motion.get('ask', '')}")
        concierge_motion = bridge.get("concierge_motion") or {}
        lines.append(f"- Concierge motion: **{concierge_motion.get('label', 'n/a')}** (`{concierge_motion.get('route', '/buyer-concierge')}`): {concierge_motion.get('ask', '')}")
        lines.extend(open_first_path_markdown_lines(bridge.get("open_first_path"), default_route="/buyer-concierge"))
        for item in bridge.get("role_cards", []):
            lines.append(f"- **{item.get('title', item.get('role', 'role'))}** `{item.get('route', '')}`: {item.get('spark', '')}")
        for item in bridge.get("proof_readiness", []):
            lines.append(f"- Proof **{item.get('title', 'proof')}** `{item.get('route', '')}` -> {item.get('file', '')}: {item.get('signal', '')}")
        for item in bridge.get("meeting_flow", []):
            lines.append(f"- Step {item.get('step', '')} **{item.get('label', 'step')}** `{item.get('route', '')}`: {item.get('line', '')}")
    lines.extend([
        "",
        "## Persona Cards",
        "",
    ])
    for item in report["persona_cards"]:
        lines.append(
            f"- **{item['role']}** (`{item['start_route']}`): {item['first_question']} "
            f"{item['proof']} Purchase ask: {item['purchase_ask']} (`{item['purchase_route']}`)"
        )
    lines.extend(["", "## Role Purchase Prompts", ""])
    for item in report["purchase_router"]["role_prompts"]:
        lines.append(f"- **{item['role']}** (`{item['route']}`): {item['ask']} Close: {item['close']}")
    lines.extend(["", "## Shortest Paths", ""])
    for path in report["shortest_paths"]:
        lines.append(f"- **{path['title']}** ({path['total_minutes']} min): {path['close']}")
    lines.extend(["", "## Confusion Guardrails", ""])
    for item in report["confusion_guardrails"]:
        lines.append(f"- **{item['signal']}** -> {item['response']} (`{item['route']}`)")
    lines.extend(["", "## Caveats", ""])
    lines.extend(f"- {item}" for item in report["caveats"])
    return "\n".join(lines)


def build_buyer_concierge(
    *,
    executive: dict[str, Any],
    scenario_hub: dict[str, Any],
    guided_demo: dict[str, Any],
    pilot_launchpad: dict[str, Any],
    enterprise_trust_center: dict[str, Any],
    commercial_offer_studio: dict[str, Any],
    business_case: dict[str, Any],
    productization: dict[str, Any],
    vendor_portfolio: dict[str, Any],
    buyer_brief: dict[str, Any] | None = None,
    client_name: str = "Demo client",
    config_path: str | None = None,
    target_platform_version: str | None = None,
) -> dict[str, Any]:
    """Build a first-click concierge over role, pain, trust and offer routes."""

    persona_cards = _persona_cards(
        business_case=business_case,
        enterprise_trust_center=enterprise_trust_center,
        commercial_offer_studio=commercial_offer_studio,
        scenario_hub=scenario_hub,
    )
    pain_picker = _pain_picker(scenario_hub)
    shortest_paths = _shortest_paths()
    confusion_guardrails = _confusion_guardrails()
    default_next_action = _default_next_action(
        scenario_hub=scenario_hub,
        commercial_offer_studio=commercial_offer_studio,
        enterprise_trust_center=enterprise_trust_center,
    )
    purchase_router = _purchase_router(
        business_case=business_case,
        commercial_offer_studio=commercial_offer_studio,
        enterprise_trust_center=enterprise_trust_center,
    )
    concierge_room_bridge = _concierge_room_bridge(
        buyer_brief=buyer_brief,
        default_next_action=default_next_action,
        persona_cards=persona_cards,
        purchase_router=purchase_router,
    )
    score = max(
        0,
        min(
            100,
            round(
                _score(scenario_hub) * 0.24
                + _score(guided_demo) * 0.16
                + _score(pilot_launchpad) * 0.14
                + _score(enterprise_trust_center) * 0.18
                + _score(commercial_offer_studio) * 0.20
                + _score(business_case) * 0.08
            ),
        ),
    )
    statuses = {
        _status(executive),
        _status(scenario_hub),
        _status(guided_demo),
        _status(pilot_launchpad),
        _status(enterprise_trust_center),
        _status(commercial_offer_studio),
        _status(productization),
    }
    status = "risk" if statuses & {"blocked", "critical", "fail"} else "ready" if score >= 82 else "watch"
    proof_routes = sorted(
        {card["start_route"] for card in persona_cards}
        | {card["second_route"] for card in persona_cards}
        | {card["purchase_route"] for card in persona_cards}
        | {item["route"] for item in pain_picker}
        | {step["route"] for path in shortest_paths for step in path["steps"]}
        | set(purchase_router["proof_routes"])
        | set(concierge_room_bridge["routes"])
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
                "Buyer Concierge is ready: role cards, pain picker, shortest paths and buy-now guidance reduce first-screen confusion."
                if status == "ready"
                else "Buyer Concierge is usable, but trust/productization caveats should be named before pushing a rollout path."
            ),
        },
        "summary": {
            "persona_cards": len(persona_cards),
            "pain_cards": len(pain_picker),
            "shortest_paths": len(shortest_paths),
            "guardrails": len(confusion_guardrails),
            "proof_routes": len(proof_routes),
            "offer_packages": _int((commercial_offer_studio.get("summary") or {}).get("offers")),
            "trust_controls": _int((enterprise_trust_center.get("summary") or {}).get("controls")),
            "pilot_offers": _int((pilot_launchpad.get("summary") or {}).get("offers")),
            "purchase_router_status": purchase_router["status"],
            "concierge_room_roles": len(concierge_room_bridge["role_cards"]),
            "concierge_room_proofs": len(concierge_room_bridge["proof_readiness"]),
            "concierge_room_steps": len(concierge_room_bridge["meeting_flow"]),
            "concierge_room_open_first": len(concierge_room_bridge["open_first_path"]),
        },
        "default_next_action": default_next_action,
        "orientation": {
            "not_this": "Not a huge menu, not a generic AI chat, not a screenshot demo.",
            "this_is": "A local 1C evidence product that starts from role or pain and ends with trust, offer and hashed proof.",
            "first_question": "Who is in the room, and what pain do they want proven first?",
        },
        "persona_cards": persona_cards,
        "concierge_room_bridge": concierge_room_bridge,
        "purchase_router": purchase_router,
        "pain_picker": pain_picker,
        "shortest_paths": shortest_paths,
        "confusion_guardrails": confusion_guardrails,
        "exports": _exports(),
        "proof_routes": proof_routes,
        "source_signals": {
            "executive_status": _status(executive),
            "scenario_hub_status": _status(scenario_hub),
            "guided_demo_status": _status(guided_demo),
            "pilot_launchpad_status": _status(pilot_launchpad),
            "trust_center_status": _status(enterprise_trust_center),
            "commercial_offer_status": _status(commercial_offer_studio),
            "productization_status": _status(productization),
            "vendor_work_packages": len(vendor_portfolio.get("work_packages") or []),
            "purchase_router_status": purchase_router["status"],
            "purchase_recommended_route": purchase_router["recommended_route"],
            "purchase_primary_route": purchase_router["primary_route"],
        },
        "caveats": [
            "Buyer Concierge v1 routes the first meeting; it does not replace deep module reports.",
            "If real configuration evidence is missing, begin with configuration intake and keep caveats visible.",
            "Commercial prices and legal terms remain customer-specific even when Offer Studio gives anchors.",
        ],
        "download_name": "rentgen-buyer-concierge.md",
    }
    report["markdown"] = _markdown(report)
    return report
