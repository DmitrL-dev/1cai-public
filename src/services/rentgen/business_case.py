"""Director-level business case and money map for 1C Rentgen."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.services.rentgen.open_first_path import (
    OPEN_FIRST_PATH_FILE,
    build_open_first_path,
    open_first_path_markdown_lines,
)


DEFAULT_ASSUMPTIONS: dict[str, int] = {
    "monthly_ai_subscription_cost": 120_000,
    "hourly_rate": 2_500,
    "manual_review_hours_month": 80,
    "incident_cost": 300_000,
    "release_delay_hours_per_item": 4,
    "release_windows_per_month": 2,
}

ASSUMPTION_BOUNDS: dict[str, int] = {
    "monthly_ai_subscription_cost": 50_000_000,
    "hourly_rate": 2_000_000,
    "manual_review_hours_month": 20_000,
    "incident_cost": 50_000_000,
    "release_delay_hours_per_item": 1_000,
    "release_windows_per_month": 100,
}

# Human-readable disclosure of every operator-overridable input assumption.
# Order is presentation order; labels are buyer-facing.
ASSUMPTION_LABELS: dict[str, dict[str, str]] = {
    "monthly_ai_subscription_cost": {"label": "Assumed current AI subscription / rent", "unit": "RUB per month"},
    "hourly_rate": {"label": "Assumed loaded hourly rate of a 1C specialist", "unit": "RUB per hour"},
    "manual_review_hours_month": {"label": "Assumed manual review / audit-prep effort", "unit": "hours per month"},
    "incident_cost": {"label": "Assumed cost of one production incident", "unit": "RUB per incident"},
    "release_delay_hours_per_item": {"label": "Assumed delay per queued review item", "unit": "hours per item"},
    "release_windows_per_month": {"label": "Assumed release windows", "unit": "per month"},
}

# Derived multipliers / clamps applied on top of the raw assumptions.
# Each is an arbitrary commercial default, not a measured value.
DERIVED_ASSUMPTIONS: list[dict[str, Any]] = [
    {"key": "hotspot_exposure_factor", "label": "Share of incident cost attributed to each high-risk hotspot", "value": 0.35, "unit": "fraction"},
    {"key": "platform_exposure_factor", "label": "Share of incident cost attributed to each failing platform check", "value": 0.25, "unit": "fraction"},
    {"key": "local_license_anchor_pct", "label": "Local-license anchor as a share of first-year visible value", "value": 0.22, "unit": "fraction"},
    {"key": "local_license_anchor_floor", "label": "Local-license anchor floor (minimum shown regardless of value)", "value": 1_800_000, "unit": "RUB"},
    {"key": "local_license_anchor_ceiling", "label": "Local-license anchor ceiling (maximum shown regardless of value)", "value": 12_000_000, "unit": "RUB"},
]

ASSUMPTIONS_DISCLAIMER = (
    "These are DEFAULT ASSUMPTIONS, operator-overridable, NOT measured values. "
    "Every RUB headline is (real KPI count) x (assumed rate), then clamped by the floors/ceilings below. "
    "Counts are observed from the analysed configuration; rates, percentages, floors and ceilings are assumed."
)


def _assumptions_disclosure(normalized: dict[str, Any]) -> dict[str, Any]:
    """Human-readable disclosure of every rate / percentage / floor / ceiling used.

    Additive: lives inside the existing ``assumptions`` block so the buyer can
    see that a number is ``real_count x assumed_rate``, not a measurement.
    """

    inputs = [
        {
            "key": key,
            "label": ASSUMPTION_LABELS.get(key, {}).get("label", key),
            "value": int(normalized.get(key, 0)),
            "unit": ASSUMPTION_LABELS.get(key, {}).get("unit", ""),
            "default": int(DEFAULT_ASSUMPTIONS[key]),
            "overridden": int(normalized.get(key, 0)) != int(DEFAULT_ASSUMPTIONS[key]),
        }
        for key in DEFAULT_ASSUMPTIONS
    ]
    return {
        "note": ASSUMPTIONS_DISCLAIMER,
        "kind": "default_assumptions",
        "overridable": True,
        "measured": False,
        "currency": str(normalized.get("currency") or "RUB"),
        "inputs": inputs,
        "derived": [dict(item) for item in DERIVED_ASSUMPTIONS],
    }


def _basis_money(currency: str) -> str:
    return currency or "RUB"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_int(value: Any, default: int, *, min_value: int = 0, max_value: int = 50_000_000) -> int:
    try:
        parsed = int(float(value))
    except (TypeError, ValueError):
        parsed = default
    return max(min_value, min(max_value, parsed))


def normalize_assumptions(assumptions: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return bounded commercial assumptions used by the money map."""

    source = assumptions or {}
    normalized = {
        key: _as_int(source.get(key), default, max_value=ASSUMPTION_BOUNDS[key])
        for key, default in DEFAULT_ASSUMPTIONS.items()
    }
    normalized["currency"] = str(source.get("currency") or "RUB")[:12]
    return normalized


def _decision_status(
    *,
    case_score: int,
    executive_status: str,
    red_areas: int,
    failed_platform_checks: int,
) -> str:
    if executive_status in {"blocked", "critical"} or red_areas >= 3 or failed_platform_checks >= 4:
        return "risk"
    if case_score >= 78:
        return "ready"
    return "watch"


def _configuration_name(platform: dict[str, Any]) -> str:
    inventory = platform.get("inventory") or {}
    return str(inventory.get("configuration_name") or "1C configuration")


def _money(
    *,
    executive: dict[str, Any],
    platform: dict[str, Any],
    assumptions: dict[str, Any],
) -> dict[str, int]:
    kpis = executive.get("kpis") or {}
    risk = executive.get("risk_summary") or {}
    platform_checks = platform.get("checks") or []
    failed_platform = sum(1 for item in platform_checks if item.get("status") != "pass")

    hourly_rate = int(assumptions["hourly_rate"])
    manual_review_month = int(assumptions["manual_review_hours_month"]) * hourly_rate
    manual_review_year = manual_review_month * 12
    ai_subscription_year = int(assumptions["monthly_ai_subscription_cost"]) * 12
    release_delay_exposure = (
        int(kpis.get("review_queue") or 0)
        * int(assumptions["release_delay_hours_per_item"])
        * int(assumptions["release_windows_per_month"])
        * hourly_rate
    )
    incident_cost = int(assumptions["incident_cost"])
    red_areas = int(kpis.get("red_areas") or 0)
    high_hotspots = int(risk.get("high_hotspots") or 0)
    review_queue = int(kpis.get("review_queue") or 0)
    manual_hours = int(assumptions["manual_review_hours_month"])
    delay_per_item = int(assumptions["release_delay_hours_per_item"])
    windows = int(assumptions["release_windows_per_month"])
    monthly_ai = int(assumptions["monthly_ai_subscription_cost"])
    red_area_exposure = red_areas * incident_cost
    hotspot_exposure = round(high_hotspots * incident_cost * 0.35)
    platform_exposure = round(failed_platform * incident_cost * 0.25)
    risk_exposure = red_area_exposure + hotspot_exposure + platform_exposure
    first_year_visible_value = (
        manual_review_year
        + ai_subscription_year
        + release_delay_exposure
        + risk_exposure
    )
    # Each entry exposes the derivation: (observed count) x (assumed rate).
    # The counts are real; the rates/percentages are DEFAULT ASSUMPTIONS.
    basis = {
        "manual_review_month": f"{manual_hours} h/month (assumed) x {hourly_rate} RUB/h (assumed)",
        "manual_review_year": f"{manual_hours} h/month (assumed) x {hourly_rate} RUB/h (assumed) x 12 months",
        "ai_subscription_year": f"{monthly_ai} RUB/month (assumed AI rent) x 12 months",
        "release_delay_exposure": (
            f"review_queue={review_queue} (observed) x {delay_per_item} h/item (assumed) "
            f"x {windows} windows/month (assumed) x {hourly_rate} RUB/h (assumed)"
        ),
        "red_area_exposure": f"red_areas={red_areas} (observed) x {incident_cost} RUB/incident (assumed)",
        "hotspot_exposure": f"high_hotspots={high_hotspots} (observed) x {incident_cost} RUB (assumed) x 0.35 (assumed factor)",
        "platform_exposure": f"failed_platform_checks={failed_platform} (observed) x {incident_cost} RUB (assumed) x 0.25 (assumed factor)",
        "risk_exposure": "red_area + hotspot + platform exposure (all assumption-scaled, see above)",
        "first_year_visible_value": "manual_review_year + ai_subscription_year + release_delay_exposure + risk_exposure (sum of assumption-scaled figures)",
    }
    return {
        "manual_review_month": manual_review_month,
        "manual_review_year": manual_review_year,
        "ai_subscription_year": ai_subscription_year,
        "release_delay_exposure": release_delay_exposure,
        "risk_exposure": risk_exposure,
        "red_area_exposure": red_area_exposure,
        "hotspot_exposure": hotspot_exposure,
        "platform_exposure": platform_exposure,
        "first_year_visible_value": first_year_visible_value,
        "failed_platform_checks": failed_platform,
        "_basis": basis,
    }


def _ceil_div(left: int, right: int) -> int:
    if right <= 0:
        return 0
    return (left + right - 1) // right


LOCAL_LICENSE_ANCHOR_PCT = 0.22
LOCAL_LICENSE_ANCHOR_FLOOR = 1_800_000
LOCAL_LICENSE_ANCHOR_CEILING = 12_000_000


def _local_license_anchor(first_year_visible_value: int) -> int:
    raw = round(first_year_visible_value * LOCAL_LICENSE_ANCHOR_PCT)
    return max(LOCAL_LICENSE_ANCHOR_FLOOR, min(LOCAL_LICENSE_ANCHOR_CEILING, raw))


def _local_license_anchor_detail(first_year_visible_value: int) -> dict[str, Any]:
    """Anchor plus disclosure of the percentage and which clamp (if any) bound it."""

    raw = round(first_year_visible_value * LOCAL_LICENSE_ANCHOR_PCT)
    if raw <= LOCAL_LICENSE_ANCHOR_FLOOR:
        clamped: str | None = "floor"
    elif raw >= LOCAL_LICENSE_ANCHOR_CEILING:
        clamped = "ceiling"
    else:
        clamped = None
    value = max(LOCAL_LICENSE_ANCHOR_FLOOR, min(LOCAL_LICENSE_ANCHOR_CEILING, raw))
    basis = (
        f"{int(LOCAL_LICENSE_ANCHOR_PCT * 100)}% (assumed) of first-year visible value "
        f"{first_year_visible_value} = {raw}; floored at {LOCAL_LICENSE_ANCHOR_FLOOR} (assumption), "
        f"capped at {LOCAL_LICENSE_ANCHOR_CEILING} (assumption)"
    )
    if clamped == "floor":
        basis += "; shown value is the assumed FLOOR, not a computed anchor"
    elif clamped == "ceiling":
        basis += "; shown value is the assumed CEILING, not a computed anchor"
    return {"value": value, "raw": raw, "clamped": clamped, "basis": basis}


def _subscription_escape_plan(money: dict[str, int], assumptions: dict[str, Any]) -> dict[str, Any]:
    monthly_ai_rent = int(assumptions["monthly_ai_subscription_cost"])
    annual_ai_rent = money["ai_subscription_year"]
    three_year_ai_rent = annual_ai_rent * 3
    anchor_detail = _local_license_anchor_detail(money["first_year_visible_value"])
    local_anchor = anchor_detail["value"]
    visible_value_month = round(money["first_year_visible_value"] / 12)
    break_even_months = _ceil_div(local_anchor, visible_value_month)
    ai_rent_months = _ceil_div(local_anchor, monthly_ai_rent)
    currency = str(assumptions["currency"])
    if monthly_ai_rent:
        decision_line = (
            f"Local license anchor equals about {ai_rent_months} months of current AI rent, "
            "but creates reusable 1C evidence, approvals, tests and archives that stay valuable without mandatory token spend."
        )
    else:
        decision_line = (
            "No current AI rent was entered; anchor the purchase on local review effort, release delay and risk evidence instead."
        )
    return {
        "headline": "Buy a local 1C evidence asset; keep AI credits optional.",
        "monthly_ai_rent": monthly_ai_rent,
        "annual_ai_rent": annual_ai_rent,
        "three_year_ai_rent": three_year_ai_rent,
        "local_license_anchor": local_anchor,
        "local_license_anchor_basis": anchor_detail["basis"],
        "local_license_anchor_clamped": anchor_detail["clamped"],
        "visible_value_month": visible_value_month,
        "break_even_months": break_even_months,
        "ai_rent_equivalent_months": ai_rent_months,
        "currency": currency,
        "decision_line": decision_line,
        "guardrails": [
            "Baseline value is local static analysis, metadata graph, release governance, tests and hashed evidence exports.",
            "External AI credits are optional add-ons, not the pricing meter for the core product.",
            "Evidence Bundle and Productization archives remain useful when cloud AI is disabled.",
            "Security can approve install mode, SBOM/offline posture and audit chain before any AI integration is discussed.",
        ],
        "stakeholder_lines": [
            {
                "role": "Finance",
                "line": "Compare three-year AI rent with a local license anchor and explicit value assumptions.",
                "route": "/commercial-offer-studio",
            },
            {
                "role": "Director",
                "line": "The purchase creates a reusable release and audit control plane, not another prompt budget.",
                "route": "/business-case",
            },
            {
                "role": "Architect",
                "line": "Core proof is grounded in configuration metadata, platform checks, rights and offline artifacts.",
                "route": "/enterprise-trust-center",
            },
            {
                "role": "Security",
                "line": "Approve locality and evidence retention first; optional AI integrations can be governed separately.",
                "route": "/productization",
            },
        ],
        "evidence_files": [
            {"title": "Business Case", "filename": "business-case.md", "route": "/business-case"},
            {"title": "Commercial Offer Studio", "filename": "commercial-offer-studio.md", "route": "/commercial-offer-studio"},
            {"title": "Enterprise Trust Center", "filename": "enterprise-trust-center.md", "route": "/enterprise-trust-center"},
            {"title": "Evidence Bundle", "filename": "OPEN_FIRST.md", "route": "/evidence-bundle"},
        ],
    }


def _levers(
    *,
    executive: dict[str, Any],
    platform: dict[str, Any],
    intake: dict[str, Any],
    money: dict[str, int],
    assumptions: dict[str, Any],
) -> list[dict[str, Any]]:
    kpis = executive.get("kpis") or {}
    risk = executive.get("risk_summary") or {}
    platform_decision = platform.get("decision") or {}
    intake_decision = intake.get("decision") or {}
    currency = assumptions["currency"]
    basis = money.get("_basis") or {}
    return [
        {
            "id": "subscription-displacement",
            "title": "Replace mandatory AI subscription spend with a local product asset",
            "audience": "CIO / director",
            "annual_value": money["ai_subscription_year"],
            "currency": currency,
            "basis": basis.get("ai_subscription_year", ""),
            "evidence": f"{assumptions['monthly_ai_subscription_cost']} per month is moved from recurring AI rent to optional add-on budget.",
            "route": "/offline-readiness",
            "confidence": "medium",
            "why_buy_now": "The customer can buy the local cockpit once and keep cloud AI credits optional.",
        },
        {
            "id": "manual-review",
            "title": "Compress manual review, release explanation and audit preparation",
            "audience": "delivery lead / QA",
            "annual_value": money["manual_review_year"],
            "currency": currency,
            "basis": basis.get("manual_review_year", ""),
            "evidence": f"{assumptions['manual_review_hours_month']} hours/month at {assumptions['hourly_rate']} are replaced by repeatable evidence.",
            "route": "/release-readiness",
            "confidence": "high",
            "why_buy_now": "Every release currently recreates the same impact, tests and approval story by hand.",
        },
        {
            "id": "release-queue",
            "title": "Reduce hidden release delay from owner review queues",
            "audience": "director / release manager",
            "annual_value": money["release_delay_exposure"],
            "currency": currency,
            "basis": basis.get("release_delay_exposure", ""),
            "evidence": f"Review queue: {kpis.get('review_queue', 0)} items; release policy is {((executive.get('decision') or {}).get('release_policy') or 'configured locally')}.",
            "route": "/team-governance",
            "confidence": "medium",
            "why_buy_now": "The report turns waiting work into named owners, SLA and go/no-go evidence.",
        },
        {
            "id": "risk-exposure",
            "title": "Make production incident exposure visible before the release window",
            "audience": "architect / operations",
            "annual_value": money["risk_exposure"],
            "currency": currency,
            "basis": basis.get("risk_exposure", ""),
            "evidence": f"Red areas: {kpis.get('red_areas', 0)}, high-risk hotspots: {risk.get('high_hotspots', 0)}, platform checks needing attention: {money['failed_platform_checks']}.",
            "route": "/quality",
            "confidence": "medium",
            "why_buy_now": "The buyer sees concrete modules, platform gaps and owner actions instead of an abstract risk score.",
        },
        {
            "id": "platform-upgrade",
            "title": "De-risk platform and extension upgrade decisions",
            "audience": "architect / platform owner",
            "annual_value": money["platform_exposure"],
            "currency": currency,
            "basis": basis.get("platform_exposure", ""),
            "evidence": f"Platform status: {platform_decision.get('status', 'unknown')} / {platform_decision.get('score', 0)}; intake: {intake_decision.get('status', 'unknown')} / {intake_decision.get('score', 0)}.",
            "route": "/platform-doctor",
            "confidence": "medium",
            "why_buy_now": "Platform, locks, extensions, rollback and evidence are checked in one local contour.",
        },
        {
            "id": "pre-sale-audit",
            "title": "Turn technical audit into a paid project package",
            "audience": "vendor / franchisee",
            "annual_value": 0,
            "currency": currency,
            "basis": "Scoped per engagement; no assumed RUB figure attached.",
            "evidence": "Vendor audit, value packs and evidence bundle form the commercial proposal path.",
            "route": "/vendor-portfolio",
            "confidence": "high",
            "why_buy_now": "The vendor can sell an audit first, then convert findings into modernization and support work.",
        },
    ]


def _buyer_committee(money: dict[str, int]) -> list[dict[str, str]]:
    return [
        {
            "role": "Developer",
            "wants": "One patch should show impact, standards findings and test gaps before commit.",
            "proof": "Change Impact, Query Surgeon, Testing and Quality routes share the same local evidence.",
            "route": "/change",
            "decision_trigger": "The tool saves a failed review or production regression on a real module.",
        },
        {
            "role": "Architect",
            "wants": "The configuration must look like a system, not a folder tree.",
            "proof": "Architecture, metadata, platform, extension and rights reports expose blast radius.",
            "route": "/architecture",
            "decision_trigger": "The first upgrade or extension decision becomes evidence-backed.",
        },
        {
            "role": "Director",
            "wants": "A go/no-go, money map and buyer-safe explanation without technical immersion.",
            "proof": f"First-year visible value map: {money['first_year_visible_value']}.",
            "route": "/business-case",
            "decision_trigger": "The report ties recurring spend, review effort and release risk to one local product.",
        },
        {
            "role": "Operations",
            "wants": "Platform, locks, incidents and rollback should be visible before the night window.",
            "proof": "Platform Doctor, Lock Radar and Operations produce runbooks and caveats.",
            "route": "/operations",
            "decision_trigger": "A real TJ/log issue becomes a module plan and runbook.",
        },
        {
            "role": "Vendor",
            "wants": "A demo must become a paid audit and then scoped implementation work.",
            "proof": "Vendor Portfolio, Value Packs and Evidence Bundle already export proposal artifacts.",
            "route": "/vendor-portfolio",
            "decision_trigger": "The same product artifact can be sent to the buyer as a pre-sale audit.",
        },
    ]


def _offer_stack(value_packs: dict[str, Any] | None, vendor: dict[str, Any] | None) -> list[dict[str, Any]]:
    packs = [item.get("title") for item in (value_packs or {}).get("packs", []) if item.get("title")]
    work_packages = [item.get("title") for item in (vendor or {}).get("work_packages", []) if item.get("title")]
    return [
        {
            "id": "closed-contour-pilot",
            "title": "Closed-contour pilot",
            "target_buyer": "one delivery team",
            "includes": [
                "local install",
                "configuration intake",
                "developer and release cockpit",
                "first evidence bundle",
            ],
            "routes": ["/configurations", "/change", "/release-readiness", "/evidence-bundle"],
            "commercial_note": "Sold as fast proof on the customer's own 1C code, not as generic code chat.",
        },
        {
            "id": "enterprise-license",
            "title": "Enterprise local license",
            "target_buyer": "director / CIO / architecture board",
            "includes": packs[:5] or ["Developer Pack", "Architect Pack", "Release / QA Pack", "Platform Doctor Pack"],
            "routes": ["/value-packs", "/productization", "/offline-readiness", "/team-governance", "/platform-doctor"],
            "commercial_note": "Core deterministic analysis works locally; external AI remains optional.",
        },
        {
            "id": "vendor-rollout",
            "title": "Vendor portfolio rollout",
            "target_buyer": "franchisee / implementation partner",
            "includes": work_packages[:4] or ["pre-sale audit", "platform upgrade estimate", "release gate"],
            "routes": ["/vendor-portfolio", "/business-case", "/evidence-bundle"],
            "commercial_note": "Every audit can become a scoped paid modernization or support package.",
        },
    ]


def _objections() -> list[dict[str, str]]:
    return [
        {
            "question": "Is this just another AI subscription?",
            "answer": "No. The core value is a local, deterministic 1C evidence system. Cloud AI can be added, but the buyer keeps useful reports without mandatory token rent.",
            "proof_route": "/offline-readiness",
        },
        {
            "question": "Will it send private 1C code outside?",
            "answer": "The business case is built from local store/files and hashed artifacts. External calls are optional integration choices, not required for this report.",
            "proof_route": "/evidence-bundle",
        },
        {
            "question": "Can a director understand it without reading modules?",
            "answer": "The report collapses modules, platform, review queues and releases into money levers, owner actions and 30/60/90 execution.",
            "proof_route": "/business-case",
        },
        {
            "question": "Can an architect trust it?",
            "answer": "Every claim links back to a route: graph, metadata, platform, rights, extensions, locks or evidence artifacts.",
            "proof_route": "/architecture",
        },
    ]


def _plan() -> list[dict[str, Any]]:
    return [
        {
            "stage": "0-30 days",
            "goal": "Prove value on one real configuration and one release window.",
            "actions": [
                "run configuration intake",
                "build first executive dashboard",
                "analyze one risky change",
                "export evidence bundle",
            ],
            "exit_criteria": "Director sees a go/no-go report and a money map for the current release.",
        },
        {
            "stage": "31-60 days",
            "goal": "Turn pilot into release governance and platform risk control.",
            "actions": [
                "connect release gates",
                "assign owner queues",
                "run Platform Doctor, Lock Radar and Extension Safety",
                "standardize markdown/JSON exports for approval",
            ],
            "exit_criteria": "Release board uses Rentgen evidence for approval and rollback planning.",
        },
        {
            "stage": "61-90 days",
            "goal": "Scale to enterprise or vendor portfolio packaging.",
            "actions": [
                "package value packs by role",
                "use vendor audit as paid pre-sale entry",
                "prepare offline/productization artifacts",
                "review ROI assumptions with finance",
            ],
            "exit_criteria": "Buyer can justify enterprise local license or vendor rollout without mandatory AI subscription.",
        },
    ]


def _business_room_bridge(
    *,
    buyer_brief: dict[str, Any] | None,
    subscription_escape_plan: dict[str, Any],
    buyer_committee: list[dict[str, str]],
) -> dict[str, Any]:
    brief = buyer_brief or {}
    primary = dict(brief.get("primary_motion") or {})
    if not primary:
        primary = {
            "label": "Prove local value",
            "route": "/business-case",
            "status": "watch",
            "ask": "Compare recurring AI rent with local evidence, governance and risk reduction.",
            "reason": "Business Case turns proof into a finance-readable buying motion.",
        }

    business_motion = {
        "label": "Show subscription escape",
        "route": "/business-case",
        "status": str(primary.get("status") or "watch"),
        "ask": str(subscription_escape_plan.get("decision_line") or "Show why local product value beats mandatory AI rent."),
        "reason": str(subscription_escape_plan.get("headline") or "Business Case keeps the purchase grounded in explicit assumptions."),
    }

    role_cards = list(brief.get("role_cards") or [])
    if not role_cards:
        role_cards = [
            {
                "role": item["role"].casefold(),
                "title": item["role"],
                "route": item["route"],
                "status": "ready" if item["role"] == "Director" else "watch",
                "spark": item["decision_trigger"],
                "proof_file": "rentgen-business-case.md",
            }
            for item in buyer_committee[:5]
        ]

    proof_readiness = list(brief.get("proof_readiness") or [])
    if not proof_readiness:
        proof_readiness = [
            {
                "id": "business-case",
                "title": "Business Case",
                "route": "/business-case",
                "status": str(primary.get("status") or "watch"),
                "signal": str(subscription_escape_plan.get("decision_line") or "Money map and assumptions are explicit."),
                "file": "rentgen-business-case.md",
            },
            {
                "id": "commercial-offer",
                "title": "Commercial Offer",
                "route": "/commercial-offer-studio",
                "status": "ready",
                "signal": "Turns value anchor into paid package and procurement dossier.",
                "file": "rentgen-commercial-offer-studio.md",
            },
            {
                "id": "trust",
                "title": "Enterprise Trust",
                "route": "/enterprise-trust-center",
                "status": "ready",
                "signal": "Answers locality, SBOM/offline, rights and approval proof.",
                "file": "rentgen-security-questionnaire.md",
            },
            {
                "id": "evidence-bundle",
                "title": "Evidence Bundle",
                "route": "/evidence-bundle",
                "status": "ready",
                "signal": "Forwards assumptions, role files and hash-verifiable proof.",
                "file": "OPEN_FIRST.md",
            },
        ]

    meeting_flow = list(brief.get("meeting_flow") or [])
    if not meeting_flow:
        meeting_flow = [
            {"step": 1, "label": "Orient", "route": "/buyer-concierge", "line": "Pick the room role and pain first."},
            {"step": 2, "label": "Value", "route": "/business-case", "line": "Show AI rent, visible value and local-license anchor."},
            {"step": 3, "label": "Offer", "route": "/commercial-offer-studio", "line": "Convert value into a paid package and approval path."},
            {"step": 4, "label": "Forward", "route": "/evidence-bundle", "line": "Forward buyer brief, business case and proof archive."},
        ]
    open_first_path = build_open_first_path(
        existing_path=brief.get("open_first_path"),
        proof_readiness=proof_readiness,
        primary=primary,
        meeting_flow=meeting_flow,
        source="business-case-fallback",
        orient_title="Business Case",
        orient_route="/business-case",
        orient_line="Show AI rent, visible value and local-license anchor.",
        orient_status=str(primary.get("status") or business_motion.get("status") or "watch"),
        prove_line=str(subscription_escape_plan.get("decision_line") or "Money map and assumptions are explicit."),
        close_title="Commercial Offer",
        close_route="/commercial-offer-studio",
        close_line="Convert value into a paid package and approval path.",
        close_file="rentgen-commercial-offer-studio.md",
        close_status=str(primary.get("status") or business_motion.get("status") or "watch"),
        verify_line="Forward buyer brief, business case and proof archive.",
    )

    routes = sorted(
        {
            "/business-case",
            str(primary.get("route") or "/business-case"),
            str(business_motion["route"]),
            *[str(item.get("route") or "") for item in role_cards],
            *[str(item.get("route") or "") for item in proof_readiness],
            *[str(item.get("route") or "") for item in meeting_flow],
            *[str(item.get("route") or "") for item in open_first_path],
            *[str(item.get("route") or "") for item in subscription_escape_plan.get("stakeholder_lines", [])],
            *[str(item.get("route") or "") for item in subscription_escape_plan.get("evidence_files", [])],
        }
        - {""}
    )
    return {
        "status": str(brief.get("purchase_status") or primary.get("status") or "watch"),
        "score": _as_int(brief.get("score"), 74),
        "source": str(brief.get("source") or "business-case-derived"),
        "room_line": str(
            brief.get("room_line")
            or f"{primary.get('label', 'Prove local value')}: {primary.get('ask', 'Show the money map and paid next step.')}"
        ),
        "primary_motion": {
            "label": str(primary.get("label") or "Prove local value"),
            "route": str(primary.get("route") or "/business-case"),
            "status": str(primary.get("status") or "watch"),
            "ask": str(primary.get("ask") or "Show the money map and paid next step."),
            "reason": str(primary.get("reason") or "Business Case turns evidence into a finance-readable purchase."),
        },
        "business_motion": business_motion,
        "role_cards": role_cards[:5],
        "proof_readiness": proof_readiness[:4],
        "meeting_flow": meeting_flow[:4],
        "open_first_path": open_first_path[:4],
        "files": ["buyer-brief.md", "buyer-pulse.md", OPEN_FIRST_PATH_FILE, "rentgen-business-case.md", "rentgen-commercial-offer-studio.md", "OPEN_FIRST.md"],
        "routes": routes,
        "close_question": "Does the room accept local product value as the paid buying motion?",
    }


def _markdown(report: dict[str, Any]) -> str:
    currency = report["assumptions"]["currency"]
    lines = [
        "# 1C Rentgen Business Case",
        "",
        f"Client: **{report['client']['name']}**",
        f"Configuration: **{report['client']['configuration']}**",
        f"Status: **{report['decision']['status'].upper()}** / score **{report['decision']['score']}**",
        f"First-year visible value: **{report['summary']['first_year_visible_value']} {currency}**",
        "",
        "## Money levers",
        "",
    ]
    for item in report["business_levers"]:
        value = item["annual_value"]
        suffix = f" ({value} {currency})" if value else ""
        basis = item.get("basis")
        basis_note = f" _Basis: {basis}_" if basis else ""
        lines.append(f"- **{item['title']}**{suffix}: {item['why_buy_now']}{basis_note}")
    escape = report.get("subscription_escape_plan") or {}
    if escape:
        lines.extend(["", "## Subscription escape", ""])
        lines.append(str(escape.get("headline") or ""))
        lines.append(f"- Annual AI rent: **{escape.get('annual_ai_rent', 0)} {currency}**")
        lines.append(f"- Three-year AI rent: **{escape.get('three_year_ai_rent', 0)} {currency}**")
        clamp = escape.get("local_license_anchor_clamped")
        clamp_tag = f" _(clamped: {clamp})_" if clamp else ""
        lines.append(f"- Local license anchor: **{escape.get('local_license_anchor', 0)} {currency}**{clamp_tag}")
        if escape.get("local_license_anchor_basis"):
            lines.append(f"  - Basis: {escape['local_license_anchor_basis']}")
        lines.append(f"- Break-even by visible value: **{escape.get('break_even_months', 0)} months**")
        lines.append(f"- Decision line: {escape.get('decision_line', '')}")
        lines.extend(["", "### Guardrails", ""])
        lines.extend(f"- {item}" for item in escape.get("guardrails", []))
    bridge = report.get("business_room_bridge") or {}
    if bridge:
        lines.extend(["", "## Business Room Bridge", ""])
        lines.append(f"- Source: **{bridge.get('source', 'n/a')}**; status **{bridge.get('status', 'watch')}** / score **{bridge.get('score', 0)}**")
        lines.append(f"- Room line: {bridge.get('room_line', '')}")
        motion = bridge.get("primary_motion") or {}
        lines.append(f"- Primary motion: **{motion.get('label', 'n/a')}** (`{motion.get('route', '/business-case')}`): {motion.get('ask', '')}")
        business_motion = bridge.get("business_motion") or {}
        lines.append(f"- Business motion: **{business_motion.get('label', 'n/a')}** (`{business_motion.get('route', '/business-case')}`): {business_motion.get('ask', '')}")
        lines.extend(open_first_path_markdown_lines(bridge.get("open_first_path"), default_route="/business-case"))
        for item in bridge.get("role_cards", []):
            lines.append(f"- **{item.get('title', item.get('role', 'role'))}** `{item.get('route', '')}`: {item.get('spark', '')}")
        for item in bridge.get("proof_readiness", []):
            lines.append(f"- Proof **{item.get('title', 'proof')}** `{item.get('route', '')}` -> {item.get('file', '')}: {item.get('signal', '')}")
        for item in bridge.get("meeting_flow", []):
            lines.append(f"- Step {item.get('step', '')} **{item.get('label', 'step')}** `{item.get('route', '')}`: {item.get('line', '')}")
    lines.extend(["", "## Buyer committee", ""])
    for item in report["buyer_committee"]:
        lines.append(f"- **{item['role']}**: {item['decision_trigger']} (`{item['route']}`)")
    lines.extend(["", "## 30/60/90 plan", ""])
    for item in report["plan_30_60_90"]:
        lines.append(f"- **{item['stage']}**: {item['goal']} Exit: {item['exit_criteria']}")
    disclosed = (report.get("assumptions") or {}).get("disclosed") or {}
    if disclosed:
        lines.extend(["", "## Assumptions (default, operator-overridable)", ""])
        lines.append(f"_{disclosed.get('note', ASSUMPTIONS_DISCLAIMER)}_")
        lines.append("")
        for item in disclosed.get("inputs", []):
            flag = " (overridden)" if item.get("overridden") else ""
            lines.append(f"- **{item['label']}**: {item['value']} {item['unit']} _(assumption; default {item['default']}{flag})_")
        for item in disclosed.get("derived", []):
            lines.append(f"- **{item['label']}**: {item['value']} {item['unit']} _(assumption)_")
    lines.extend(["", "## Caveats", ""])
    lines.extend(f"- {item}" for item in report["caveats"])
    return "\n".join(lines)


def build_business_case(
    *,
    executive: dict[str, Any],
    platform: dict[str, Any],
    intake: dict[str, Any],
    vendor: dict[str, Any] | None = None,
    value_packs: dict[str, Any] | None = None,
    client_name: str = "Demo client",
    config_path: str | None = None,
    target_platform_version: str | None = None,
    assumptions: dict[str, Any] | None = None,
    buyer_brief: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a buyer-safe money map over local Rentgen evidence."""

    normalized = normalize_assumptions(assumptions)
    money = _money(executive=executive, platform=platform, assumptions=normalized)
    subscription_escape_plan = _subscription_escape_plan(money, normalized)
    kpis = executive.get("kpis") or {}
    executive_decision = executive.get("decision") or {}
    platform_decision = platform.get("decision") or {}
    intake_decision = intake.get("decision") or {}
    score = max(
        0,
        min(
            100,
            round(
                int(executive_decision.get("score") or 0) * 0.35
                + int(platform_decision.get("score") or 0) * 0.20
                + int(intake_decision.get("score") or 0) * 0.15
                + min(30, money["first_year_visible_value"] / 220_000)
            ),
        ),
    )
    status = _decision_status(
        case_score=score,
        executive_status=str(executive_decision.get("status") or "unknown"),
        red_areas=int(kpis.get("red_areas") or 0),
        failed_platform_checks=money["failed_platform_checks"],
    )
    buyer_committee = _buyer_committee(money)
    business_room_bridge = _business_room_bridge(
        buyer_brief=buyer_brief,
        subscription_escape_plan=subscription_escape_plan,
        buyer_committee=buyer_committee,
    )
    report: dict[str, Any] = {
        "generated_at": _now(),
        "client": {
            "name": client_name,
            "configuration": _configuration_name(platform),
            "config_path": config_path or "",
            "target_platform_version": target_platform_version or "",
        },
        "decision": {
            "status": status,
            "score": score,
            "headline": (
                "Business case is ready for a buyer conversation: local evidence, money levers and role-specific proof are connected."
                if status == "ready"
                else "Business case is usable, but the buyer should see caveats and red areas before commercial commitment."
            ),
        },
        "assumptions": {
            **normalized,
            "note": ASSUMPTIONS_DISCLAIMER,
            "disclosed": _assumptions_disclosure(normalized),
        },
        "summary": {
            **{key: value for key, value in money.items() if key != "_basis"},
            "money_basis": money.get("_basis") or {},
            "local_license_anchor_basis": subscription_escape_plan["local_license_anchor_basis"],
            "local_license_anchor_clamped": subscription_escape_plan["local_license_anchor_clamped"],
            "work_packages": len((vendor or {}).get("work_packages", [])),
            "value_packs": len((value_packs or {}).get("packs", [])),
            "modules": int(kpis.get("modules") or 0),
            "modules_with_issues": int(kpis.get("modules_with_issues") or 0),
            "red_areas": int(kpis.get("red_areas") or 0),
            "review_queue": int(kpis.get("review_queue") or 0),
            "three_year_ai_subscription": subscription_escape_plan["three_year_ai_rent"],
            "local_license_anchor": subscription_escape_plan["local_license_anchor"],
            "subscription_escape_months": subscription_escape_plan["ai_rent_equivalent_months"],
            "subscription_break_even_months": subscription_escape_plan["break_even_months"],
            "business_room_roles": len(business_room_bridge["role_cards"]),
            "business_room_proofs": len(business_room_bridge["proof_readiness"]),
            "business_room_steps": len(business_room_bridge["meeting_flow"]),
            "business_room_open_first": len(business_room_bridge["open_first_path"]),
        },
        "subscription_escape_plan": subscription_escape_plan,
        "business_room_bridge": business_room_bridge,
        "business_levers": _levers(
            executive=executive,
            platform=platform,
            intake=intake,
            money=money,
            assumptions=normalized,
        ),
        "buyer_committee": buyer_committee,
        "offer_stack": _offer_stack(value_packs, vendor),
        "objections": _objections(),
        "plan_30_60_90": _plan(),
        "evidence_routes": [
            {"label": "Executive cockpit", "to": "/"},
            {"label": "Commercial Offer Studio", "to": "/commercial-offer-studio"},
            {"label": "Demo Command Center", "to": "/demo-command-center"},
            {"label": "Pilot Launchpad", "to": "/pilot-launchpad"},
            {"label": "Scenario Hub", "to": "/scenario-hub"},
            {"label": "Guided Demo", "to": "/guided-demo"},
            {"label": "Enterprise Trust Center", "to": "/enterprise-trust-center"},
            {"label": "Value Packs", "to": "/value-packs"},
            {"label": "Productization", "to": "/productization"},
            {"label": "Vendor Portfolio", "to": "/vendor-portfolio"},
            {"label": "Platform Doctor", "to": "/platform-doctor"},
            {"label": "Update War Room", "to": "/update-war-room"},
            {"label": "Evidence Bundle", "to": "/evidence-bundle"},
            *[
                {"label": f"Buyer Brief: {route}", "to": route}
                for route in business_room_bridge["routes"]
                if route not in {"/business-case", "/commercial-offer-studio", "/enterprise-trust-center", "/evidence-bundle"}
            ],
        ],
        "caveats": [
            "Money Map v1 is a commercial decision aid, not a guaranteed savings statement.",
            "Assumptions are explicit and should be reviewed with the buyer's finance owner.",
            "Annual value combines recurring budget displacement, manual effort and risk exposure; do not double-book it as audited savings.",
        ],
    }
    report["markdown"] = _markdown(report)
    return report
