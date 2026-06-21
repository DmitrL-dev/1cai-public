"""Commercial offer studio that converts Rentgen proof into buyable packages."""

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


def _price(value: int, percent: float, *, floor: int, ceiling: int) -> int:
    return max(floor, min(ceiling, round(value * percent)))


def _business_value(business_case: dict[str, Any]) -> tuple[int, str]:
    summary = business_case.get("summary") or {}
    assumptions = business_case.get("assumptions") or {}
    currency = str(assumptions.get("currency") or "RUB")
    return _int(summary.get("first_year_visible_value")), currency


def _offers(
    *,
    business_case: dict[str, Any],
    pilot_launchpad: dict[str, Any],
    enterprise_trust_center: dict[str, Any],
    value_packs: dict[str, Any],
    vendor_portfolio: dict[str, Any],
) -> list[dict[str, Any]]:
    value, currency = _business_value(business_case)
    packs = [item.get("title") for item in value_packs.get("packs", []) if item.get("title")]
    work_packages = [item.get("title") for item in vendor_portfolio.get("work_packages", []) if item.get("title")]
    pilot_summary = pilot_launchpad.get("summary") or {}
    trust_summary = enterprise_trust_center.get("summary") or {}
    proof_price = _price(value, 0.04, floor=180_000, ceiling=900_000)
    local_pilot = _price(value, 0.10, floor=600_000, ceiling=2_400_000)
    enterprise = _price(value, 0.22, floor=1_800_000, ceiling=12_000_000)
    vendor = _price(value, 0.30, floor=2_400_000, ceiling=18_000_000)
    return [
        {
            "id": "proof-sprint",
            "title": "24-hour proof sprint",
            "buyer": "director + tech lead",
            "commercial_frame": f"fixed proof from {_money(proof_price, currency)}, credited into license",
            "route": "/scenario-hub",
            "why_buy": "Buyer sees one concrete 1C pain, one proof route and one artifact pack before procurement starts.",
            "includes": [
                "Scenario Hub over current evidence",
                "Demo Command Center route",
                "first Evidence Bundle",
            ],
            "proof_routes": ["/scenario-hub", "/demo-command-center", "/evidence-bundle"],
            "acceptance": "Buyer can repeat the product value and name the first pilot acceptance check.",
        },
        {
            "id": "local-license-pilot",
            "title": "30-day local license pilot",
            "buyer": "CIO + security + architecture board",
            "commercial_frame": f"paid local pilot from {_money(local_pilot, currency)}",
            "route": "/pilot-launchpad",
            "why_buy": "The customer buys a local evidence system, not another mandatory AI token subscription.",
            "includes": [
                "local install contour",
                "Enterprise Trust Center",
                "Business Case assumptions review",
                "release or platform proof route",
            ],
            "proof_routes": ["/pilot-launchpad", "/enterprise-trust-center", "/business-case"],
            "acceptance": f"Security questions: {_int(trust_summary.get('security_questions'))}; pilot offers: {_int(pilot_summary.get('offers'))}.",
        },
        {
            "id": "enterprise-local-license",
            "title": "Enterprise local license",
            "buyer": "director / CIO",
            "commercial_frame": f"annual local license anchor {_money(enterprise, currency)}",
            "route": "/commercial-offer-studio",
            "why_buy": "Visible first-year value anchors the price while optional AI credits remain separate.",
            "includes": packs[:5] or [
                "Developer proof",
                "Architecture and platform proof",
                "Release governance",
                "Trust Center",
                "Evidence Bundle standard",
            ],
            "proof_routes": ["/business-case", "/enterprise-trust-center", "/value-packs", "/evidence-bundle"],
            "acceptance": "Finance, security and architecture approve value assumptions, install mode and production blockers.",
        },
        {
            "id": "platform-trust-pack",
            "title": "Platform and trust hardening pack",
            "buyer": "architect + security",
            "commercial_frame": f"scoped hardening package from {_money(max(450_000, round(enterprise * 0.35)), currency)}",
            "route": "/enterprise-trust-center",
            "why_buy": "The painful 1C platform/update/security part becomes a named package instead of expert anxiety.",
            "includes": [
                "Platform Doctor",
                "Rights/RLS",
                "Productization blockers review",
                "offline bundle verification",
            ],
            "proof_routes": ["/platform-doctor", "/rights-rls", "/productization", "/enterprise-trust-center"],
            "acceptance": "Every high trust/platform blocker has an owner, fix, accepted risk or release block.",
        },
        {
            "id": "vendor-portfolio-rollout",
            "title": "Vendor portfolio rollout",
            "buyer": "franchisee / implementation partner",
            "commercial_frame": f"partner rollout anchor {_money(vendor, currency)}",
            "route": "/vendor-portfolio",
            "why_buy": "A partner can sell paid audits, modernization packages and repeatable proof without custom deck work.",
            "includes": work_packages[:5] or [
                "buyer-safe audit report",
                "work package catalog",
                "portfolio dashboard",
                "proposal markdown",
            ],
            "proof_routes": ["/vendor-portfolio", "/value-packs", "/evidence-bundle", "/commercial-offer-studio"],
            "acceptance": "Partner sends one buyer-safe report and converts at least one finding into a scoped work package.",
        },
    ]


def _pricing_ladder(business_case: dict[str, Any]) -> list[dict[str, Any]]:
    value, currency = _business_value(business_case)
    ai_year = _int((business_case.get("summary") or {}).get("ai_subscription_year"))
    return [
        {
            "tier": "Proof",
            "anchor": _money(_price(value, 0.04, floor=180_000, ceiling=900_000), currency),
            "logic": "low-friction proof that is credited into the local license",
            "replaces": "first paid discovery and demo-prep uncertainty",
        },
        {
            "tier": "Local Pilot",
            "anchor": _money(_price(value, 0.10, floor=600_000, ceiling=2_400_000), currency),
            "logic": "priced below first-year visible value, tied to acceptance checks",
            "replaces": "manual review tax and another generic AI pilot",
        },
        {
            "tier": "Enterprise License",
            "anchor": _money(_price(value, 0.22, floor=1_800_000, ceiling=12_000_000), currency),
            "logic": "local product asset with optional AI credits separated from core value",
            "replaces": f"recurring AI rent baseline: {_money(ai_year, currency)} per year",
        },
        {
            "tier": "Partner Rollout",
            "anchor": _money(_price(value, 0.30, floor=2_400_000, ceiling=18_000_000), currency),
            "logic": "portfolio license plus packaged audits and modernization work",
            "replaces": "one-off expert audits and bespoke proposal decks",
        },
    ]


def _stakeholder_closers() -> list[dict[str, str]]:
    return [
        {
            "role": "Developer",
            "buy_trigger": "A real 1C defect class is caught before review.",
            "proof_route": "/quality",
            "close_line": "Start with the LEFT JOIN/NULL proof and make the first saved review visible.",
        },
        {
            "role": "Architect",
            "buy_trigger": "Platform, topology, extensions and rights are connected.",
            "proof_route": "/platform-doctor",
            "close_line": "Attach the first upgrade or extension decision to the pilot.",
        },
        {
            "role": "Director",
            "buy_trigger": "Local product value is larger than another AI subscription budget.",
            "proof_route": "/business-case",
            "close_line": "Use visible first-year value as the license anchor, not as a vague ROI promise.",
        },
        {
            "role": "Security",
            "buy_trigger": "Local contour, SBOM/offline and hash artifacts are visible.",
            "proof_route": "/enterprise-trust-center",
            "close_line": "Ask which artifact is required to approve a pilot install.",
        },
        {
            "role": "Vendor",
            "buy_trigger": "Audit evidence becomes packages and repeatable proposals.",
            "proof_route": "/vendor-portfolio",
            "close_line": "Pick the first client portfolio and sell the proof sprint.",
        },
    ]


def _deal_risks(
    *,
    productization: dict[str, Any],
    enterprise_trust_center: dict[str, Any],
    pilot_launchpad: dict[str, Any],
) -> list[dict[str, str]]:
    risks = [
        {
            "risk": "Security asks for locality, SBOM, offline archive or rights/RLS before commercial approval.",
            "route": "/enterprise-trust-center",
            "mitigation": "Open Trust Center first and export the Evidence Bundle manifest.",
        },
        {
            "risk": "Finance treats the product as another AI subscription line.",
            "route": "/business-case",
            "mitigation": "Separate local product value from optional AI credits and show subscription displacement.",
        },
        {
            "risk": "Pilot interest does not become a paid next step.",
            "route": "/pilot-launchpad",
            "mitigation": "Select one offer, owner, date and acceptance check during the meeting.",
        },
    ]
    if _status(productization) in {"fail", "risk", "blocked", "critical"}:
        risks.append(
            {
                "risk": "Productization gate has blockers or hardening gaps.",
                "route": "/productization",
                "mitigation": "Sell Platform and Trust Hardening Pack or keep production rollout conditional.",
            }
        )
    if _status(enterprise_trust_center) == "risk":
        risks.append(
            {
                "risk": "Trust Center reports failed controls.",
                "route": "/enterprise-trust-center",
                "mitigation": "Use the risk register as paid hardening scope before enterprise rollout.",
            }
        )
    if _status(pilot_launchpad) != "ready":
        risks.append(
            {
                "risk": "Pilot acceptance is not buyer-ready.",
                "route": "/pilot-launchpad",
                "mitigation": "Use the 24-hour proof sprint before quoting the full license.",
            }
        )
    return risks


def _proposal_sections() -> list[dict[str, str]]:
    return [
        {
            "title": "First-click orientation",
            "route": "/buyer-concierge",
            "content": "Role, pain and shortest-route guidance so the buyer does not start from the whole menu.",
        },
        {
            "title": "Board approval packet",
            "route": "/board-pack",
            "content": "One decision brief with value, trust, risks, committee answers and the recommended buying motion.",
        },
        {
            "title": "Executive offer",
            "route": "/business-case",
            "content": "Local 1C evidence product, optional AI credits, first-year value anchor and clear purchase tiers.",
        },
        {
            "title": "Technical proof",
            "route": "/scenario-hub",
            "content": "Role-led scenarios for developer, architect, operations, release and vendor proof.",
        },
        {
            "title": "Enterprise trust",
            "route": "/enterprise-trust-center",
            "content": "Local contour, SBOM/offline, rights/RLS, platform caveats, procurement pack and risk register.",
        },
        {
            "title": "Pilot route",
            "route": "/pilot-launchpad",
            "content": "24-hour proof, 7-day release pilot, 30-day local license pilot or vendor rollout.",
        },
        {
            "title": "Outcome ledger",
            "route": "/outcome-ledger",
            "content": "Adoption metrics, risk burndown, proof refresh windows and expansion paths after purchase.",
        },
        {
            "title": "Proof bundle",
            "route": "/evidence-bundle",
            "content": "Markdown/JSON artifacts with SHA-256 manifest for approval forwarding.",
        },
    ]


def _offer_index(offers: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(item.get("id")): item for item in offers if item.get("id")}


def _recommended_purchase(
    *,
    offers: list[dict[str, Any]],
    enterprise_trust_center: dict[str, Any],
    pilot_launchpad: dict[str, Any],
    productization: dict[str, Any],
) -> dict[str, Any]:
    by_id = _offer_index(offers)
    if _status(enterprise_trust_center) == "risk" or _status(productization) in {"fail", "risk", "blocked", "critical"}:
        preferred = "platform-trust-pack"
    elif _score(pilot_launchpad) >= 78:
        preferred = "enterprise-local-license"
    elif _score(pilot_launchpad) >= 65:
        preferred = "local-license-pilot"
    else:
        preferred = "proof-sprint"
    return by_id.get(preferred) or (offers[0] if offers else {})


def _procurement_dossier(
    *,
    business_case: dict[str, Any],
    enterprise_trust_center: dict[str, Any],
    productization: dict[str, Any],
    pilot_launchpad: dict[str, Any],
    offers: list[dict[str, Any]],
) -> dict[str, Any]:
    value, currency = _business_value(business_case)
    summary = business_case.get("summary") or {}
    escape_plan = business_case.get("subscription_escape_plan") or {}
    ai_year = _int(summary.get("ai_subscription_year"))
    annual_ai_rent = _int(escape_plan.get("annual_ai_rent"), ai_year)
    three_year_ai_rent = _int(escape_plan.get("three_year_ai_rent"), annual_ai_rent * 3)
    local_license_anchor = _int(escape_plan.get("local_license_anchor"), value)
    break_even_months = _int(escape_plan.get("break_even_months"))
    ai_rent_months = _int(escape_plan.get("ai_rent_equivalent_months"))
    recommended = _recommended_purchase(
        offers=offers,
        enterprise_trust_center=enterprise_trust_center,
        pilot_launchpad=pilot_launchpad,
        productization=productization,
    )
    return {
        "headline": "Open procurement for a local 1C evidence product, not mandatory AI rent.",
        "recommended_purchase": {
            "id": str(recommended.get("id") or "proof-sprint"),
            "title": str(recommended.get("title") or "24-hour proof sprint"),
            "route": str(recommended.get("route") or "/commercial-offer-studio"),
            "commercial_frame": str(recommended.get("commercial_frame") or "fixed paid next step"),
            "acceptance": str(recommended.get("acceptance") or "Buyer names owner, acceptance and proof packet."),
        },
        "subscription_escape": {
            "annual_ai_rent": _money(annual_ai_rent, currency),
            "three_year_ai_rent": _money(three_year_ai_rent, currency),
            "local_value_anchor": _money(value, currency),
            "local_license_anchor": _money(local_license_anchor, currency),
            "break_even_months": break_even_months,
            "ai_rent_equivalent_months": ai_rent_months,
            "line": "Core value is local analysis, governance, tests and hashed evidence; AI credits stay optional and separately budgeted.",
            "decision_line": str(escape_plan.get("decision_line") or ""),
            "proof_route": "/business-case",
            "guardrails": list(escape_plan.get("guardrails") or [])[:4],
            "stakeholder_lines": list(escape_plan.get("stakeholder_lines") or [])[:6],
            "evidence_files": list(escape_plan.get("evidence_files") or [])[:8],
        },
        "license_model": [
            {
                "model": "per installation",
                "buyer": "single enterprise contour",
                "why": "Simple first enterprise purchase when the buyer wants one closed local control plane.",
            },
            {
                "model": "per configuration",
                "buyer": "holding / complex 1C landscape",
                "why": "Ties price to the number of analyzed 1C assets and their release risk.",
            },
            {
                "model": "portfolio",
                "buyer": "vendor / franchisee",
                "why": "Lets a partner scan clients, sell audits and repeat modernization packages.",
            },
            {
                "model": "local AI appliance",
                "buyer": "security-sensitive enterprise",
                "why": "Premium optional capacity when external AI calls are not acceptable.",
            },
        ],
        "procurement_pack": [
            {
                "owner": "finance",
                "artifact": "Business Case",
                "route": "/business-case",
                "why": "Visible value, AI-rent displacement and explicit assumptions.",
                "exit_criteria": "Finance accepts local value anchor and separates optional AI credits.",
            },
            {
                "owner": "security",
                "artifact": "Enterprise Trust Center",
                "route": "/enterprise-trust-center",
                "why": "Locality, SBOM/offline, rights/RLS, platform caveats and approval artifacts.",
                "exit_criteria": "Security names required pilot artifacts or hardening blockers.",
            },
            {
                "owner": "architecture",
                "artifact": "Productization Readiness",
                "route": "/productization",
                "why": "Offline bundle, SBOM, verification and rollout caveats.",
                "exit_criteria": "Architecture accepts install mode and hardening scope.",
            },
            {
                "owner": "sponsor",
                "artifact": "Pilot Launchpad",
                "route": "/pilot-launchpad",
                "why": "Paid proof, local pilot or rollout path with owner and acceptance.",
                "exit_criteria": "Sponsor books a dated next paid step.",
            },
            {
                "owner": "procurement",
                "artifact": "Evidence Bundle",
                "route": "/evidence-bundle",
                "why": "Forwardable JSON/Markdown artifacts with SHA-256 manifest.",
                "exit_criteria": "Procurement receives one packet instead of screenshots.",
            },
            {
                "owner": "procurement",
                "artifact": "Archive Acceptance Receipt",
                "route": "/evidence-bundle",
                "why": "Records Evidence Bundle ZIP and linked Killer Demo ZIP filenames, hash headers and file boundaries.",
                "exit_criteria": f"Procurement stores `{ARCHIVE_ACCEPTANCE_RECEIPT_MD}` beside the purchase ticket.",
            },
        ],
        "approval_matrix": [
            {
                "role": "finance",
                "must_accept": "Price is anchored to local 1C value, not token usage.",
                "artifact": "Business Case",
                "route": "/business-case",
                "blocker_if_missing": "The offer is treated as another AI subscription.",
            },
            {
                "role": "security",
                "must_accept": "No mandatory source-code egress or hidden cloud dependency in baseline mode.",
                "artifact": "Enterprise Trust Center",
                "route": "/enterprise-trust-center",
                "blocker_if_missing": "Pilot approval stalls on locality/SBOM/offline questions.",
            },
            {
                "role": "architecture",
                "must_accept": "Platform, extensions, rights and evidence caveats are visible before rollout.",
                "artifact": "Productization / Platform Doctor",
                "route": "/productization",
                "blocker_if_missing": "Enterprise rollout is over-promised.",
            },
            {
                "role": "delivery",
                "must_accept": "Pilot scope has owner, date, tests and acceptance.",
                "artifact": "Pilot Launchpad",
                "route": "/pilot-launchpad",
                "blocker_if_missing": "Interest does not become a paid next step.",
            },
        ],
        "red_lines": [
            "No mandatory external AI subscription for baseline value.",
            "No direct production writes or hidden apply actions.",
            "No quote that hides Trust Center or Productization caveats.",
            "No evidence-free approval pack; every claim must route to an artifact.",
        ],
        "close_question": "Which procurement artifact is missing before opening the paid local-license motion?",
    }


def _buy_now_path() -> list[dict[str, str]]:
    return [
        {
            "step": "Pick offer",
            "owner": "director / vendor owner",
            "route": "/buyer-concierge",
            "exit": "Buyer starts from role or pain before selecting a paid package.",
        },
        {
            "step": "Select package",
            "owner": "director / vendor owner",
            "route": "/commercial-offer-studio",
            "exit": "One commercial package is selected as the next paid step.",
        },
        {
            "step": "Confirm trust",
            "owner": "security / architect",
            "route": "/enterprise-trust-center",
            "exit": "Required approval artifacts are named.",
        },
        {
            "step": "Prepare board pack",
            "owner": "director / seller",
            "route": "/board-pack",
            "exit": "Value, trust, risk and proof packet are compressed into one board-level motion.",
        },
        {
            "step": "Attach proof",
            "owner": "seller / delivery lead",
            "route": "/evidence-bundle",
            "exit": "Proposal pack contains hashes, caveats and buyer-safe markdown.",
        },
        {
            "step": "Book pilot",
            "owner": "pilot owner",
            "route": "/pilot-launchpad",
            "exit": "Owner, date and acceptance criteria are agreed.",
        },
        {
            "step": "Track outcomes",
            "owner": "sponsor / delivery lead",
            "route": "/outcome-ledger",
            "exit": "7/30/90-day outcomes, risk burndown and expansion path are visible.",
        },
    ]


def _close_packet(
    *,
    procurement_dossier: dict[str, Any],
    business_case: dict[str, Any],
    enterprise_trust_center: dict[str, Any],
    pilot_launchpad: dict[str, Any],
    productization: dict[str, Any],
) -> dict[str, Any]:
    recommended = procurement_dossier.get("recommended_purchase") or {}
    escape = procurement_dossier.get("subscription_escape") or {}
    recommended_id = str(recommended.get("id") or "proof-sprint")
    trust_status = _status(enterprise_trust_center)
    productization_status = _status(productization)
    pilot_score = _score(pilot_launchpad)
    ready_to_close = (
        recommended_id in {"enterprise-local-license", "local-license-pilot", "proof-sprint"}
        and trust_status != "risk"
        and productization_status not in {"fail", "blocked", "critical"}
        and pilot_score >= 65
    )
    if productization_status in {"fail", "blocked", "critical"} or trust_status == "risk":
        close_mode = "sell_hardening_before_rollout"
        primary_ask = "Approve a paid Platform and Trust Hardening Pack before enterprise rollout."
    elif recommended_id == "proof-sprint":
        close_mode = "sell_paid_proof_sprint"
        primary_ask = "Approve a paid 24-hour proof sprint with one named 1C pain and one evidence archive."
    elif recommended_id == "local-license-pilot":
        close_mode = "open_paid_local_pilot"
        primary_ask = "Approve a paid local pilot with owner, date, install contour and acceptance checks."
    else:
        close_mode = "open_enterprise_purchase"
        primary_ask = "Open enterprise local-license procurement and use the proof sprint as credited onboarding."

    return {
        "ready_to_close": ready_to_close,
        "close_mode": close_mode,
        "primary_ask": primary_ask,
        "one_page_order": {
            "product": "1C Rentgen local evidence control plane",
            "recommended_purchase": str(recommended.get("title") or "24-hour proof sprint"),
            "commercial_frame": str(recommended.get("commercial_frame") or "fixed paid next step"),
            "value_anchor": str(escape.get("local_value_anchor") or "n/a"),
            "ai_rent_baseline": str(escape.get("annual_ai_rent") or "n/a"),
            "three_year_ai_rent": str(escape.get("three_year_ai_rent") or "n/a"),
            "local_license_anchor": str(escape.get("local_license_anchor") or escape.get("local_value_anchor") or "n/a"),
            "break_even": f"{escape.get('break_even_months') or 0} months by visible value",
            "first_invoice_trigger": "Buyer names owner, scope, date and accepted proof artifacts.",
            "route": str(recommended.get("route") or "/commercial-offer-studio"),
        },
        "mutual_action_plan": [
            {
                "window": "Today",
                "owner": "sponsor + seller",
                "action": "Choose the paid next step and named buyer owner.",
                "artifact": "Commercial Offer Studio",
                "route": "/commercial-offer-studio",
                "exit": "Recommended purchase is accepted or downgraded to proof sprint.",
            },
            {
                "window": "24 hours",
                "owner": "tech lead",
                "action": "Run the strongest 1C pain route and attach Evidence Bundle ZIP.",
                "artifact": "Scenario Hub + Evidence Bundle",
                "route": "/evidence-bundle",
                "exit": "Buyer can forward one archive with hashes and caveats.",
            },
            {
                "window": "48 hours",
                "owner": "security / architect",
                "action": "Confirm locality, SBOM/offline, approval/audit and platform caveats.",
                "artifact": "Enterprise Trust Center + Governance Center",
                "route": "/enterprise-trust-center",
                "exit": "Blockers are accepted, converted to hardening scope or marked no-go.",
            },
            {
                "window": "7 days",
                "owner": "delivery lead",
                "action": "Attach the product to one release/change/update decision.",
                "artifact": "Pilot Launchpad",
                "route": "/pilot-launchpad",
                "exit": "Pilot acceptance has owner, date, tests and release gate.",
            },
            {
                "window": "30 days",
                "owner": "sponsor",
                "action": "Convert proof into local license, rollout or vendor portfolio motion.",
                "artifact": "Outcome Ledger",
                "route": "/outcome-ledger",
                "exit": "Outcome metrics and expansion path are agreed.",
            },
        ],
        "buyer_commitments": [
            {
                "role": "finance",
                "commitment": "Accept local value anchor and separate optional AI credits.",
                "route": "/business-case",
            },
            {
                "role": "security",
                "commitment": "Confirm required locality, SBOM/offline, approval and audit evidence.",
                "route": "/enterprise-trust-center",
            },
            {
                "role": "architect",
                "commitment": "Name platform/configuration blockers that must be fixed before rollout.",
                "route": "/platform-doctor",
            },
            {
                "role": "delivery",
                "commitment": "Select one release/change/update scope and acceptance gate.",
                "route": "/pilot-launchpad",
            },
            {
                "role": "sponsor",
                "commitment": "Approve paid next step or explicit hardening scope.",
                "route": "/commercial-offer-studio",
            },
        ],
        "evidence_requirements": [
            {"artifact": "Evidence Bundle ZIP", "route": "/evidence-bundle", "why": "Forwardable proof with SHA-256 manifest."},
            {
                "artifact": "Archive Acceptance Receipt",
                "route": "/evidence-bundle",
                "why": f"`{ARCHIVE_ACCEPTANCE_RECEIPT_MD}` records both archive hashes and file boundaries.",
            },
            {"artifact": "Governance proof", "route": "/approvals", "why": "Approval records, scope constraints and audit trail."},
            {"artifact": "Audit verify", "route": "/audit", "why": "Tamper-evident hash-chain status."},
            {"artifact": "Delivery passport", "route": "/productization", "why": "Offline archive and verification handoff."},
            {"artifact": "Business Case", "route": "/business-case", "why": "Value anchor and AI-rent displacement."},
        ],
        "checkout": [
            {
                "gate": "Approval record exists for risky/write action",
                "route": "/approvals",
                "evidence": "edt_mcp_call record with actor, reason, tool and argument constraints.",
            },
            {
                "gate": "Audit chain is valid",
                "route": "/audit",
                "evidence": "Audit verify reports valid=true and broken=0.",
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
        ],
        "close_script": [
            "We can keep discussing features, or we can buy proof of one real 1C pain today.",
            "The price is anchored to local evidence value, not token usage.",
            str(escape.get("decision_line") or "Core product value remains useful without mandatory token spend."),
            "If security blocks rollout, we sell the hardening pack, not a fantasy production promise.",
            "If the proof archive is accepted, the next step is a paid local pilot or enterprise license motion.",
        ],
    }


def _exports() -> list[dict[str, str]]:
    return [
        {"title": "Buyer Brief markdown", "filename": "buyer-brief.md", "route": "/"},
        {"title": "Buyer Pulse markdown", "filename": "buyer-pulse.md", "route": "/"},
        {"title": "Outcome Ledger markdown", "filename": "rentgen-outcome-ledger.md", "route": "/outcome-ledger"},
        {"title": "Board Pack markdown", "filename": "rentgen-board-pack.md", "route": "/board-pack"},
        {"title": "Buyer Concierge markdown", "filename": "rentgen-buyer-concierge.md", "route": "/buyer-concierge"},
        {"title": "Commercial Offer Studio markdown", "filename": "rentgen-commercial-offer-studio.md", "route": "/commercial-offer-studio"},
        {"title": "Business Case markdown", "filename": "rentgen-business-case.md", "route": "/business-case"},
        {"title": "Enterprise Trust Center markdown", "filename": "rentgen-enterprise-trust-center.md", "route": "/enterprise-trust-center"},
        {"title": "Pilot Launchpad markdown", "filename": "rentgen-pilot-launchpad.md", "route": "/pilot-launchpad"},
        {"title": "Evidence Bundle manifest", "filename": "evidence-bundle-manifest.json", "route": "/evidence-bundle"},
    ]


def _offer_room_bridge(
    *,
    buyer_brief: dict[str, Any] | None,
    procurement_dossier: dict[str, Any],
    close_packet: dict[str, Any],
    stakeholder_closers: list[dict[str, str]],
) -> dict[str, Any]:
    brief = buyer_brief or {}
    recommended = procurement_dossier.get("recommended_purchase") or {}
    order = close_packet.get("one_page_order") or {}
    ready_to_close = bool(close_packet.get("ready_to_close"))
    primary = dict(brief.get("primary_motion") or {})
    if not primary:
        primary = {
            "label": str(recommended.get("title") or order.get("recommended_purchase") or "Select paid next step"),
            "route": str(recommended.get("route") or order.get("route") or "/commercial-offer-studio"),
            "status": "ready" if ready_to_close else "watch",
            "ask": str(close_packet.get("primary_ask") or "Select the paid next step and attach proof."),
            "reason": str(recommended.get("acceptance") or procurement_dossier.get("headline") or "Commercial proof is ready to route."),
        }

    role_cards = list(brief.get("role_cards") or [])
    if not role_cards:
        role_cards = [
            {
                "role": item["role"].casefold(),
                "title": item["role"],
                "route": item["proof_route"],
                "status": "ready" if ready_to_close else "watch",
                "spark": item["buy_trigger"],
                "proof_file": "rentgen-commercial-offer-studio.md",
                "close_line": item["close_line"],
            }
            for item in stakeholder_closers[:5]
        ]

    route_to_file = {
        "/evidence-bundle": "OPEN_FIRST.md",
        "/approvals": "governance-proof.md",
        "/audit": "rentgen-audit-log.jsonl",
        "/productization": "rentgen-delivery-passport.md",
        "/business-case": "rentgen-business-case.md",
        "/enterprise-trust-center": "rentgen-security-questionnaire.md",
    }
    proof_readiness = list(brief.get("proof_readiness") or [])
    if not proof_readiness:
        proof_readiness = [
            {
                "id": str(item.get("artifact") or item.get("route") or "proof").lower().replace(" ", "-"),
                "title": str(item.get("artifact") or "Commercial proof"),
                "route": str(item.get("route") or "/evidence-bundle"),
                "status": "ready" if ready_to_close else "watch",
                "signal": str(item.get("why") or "Required before the buyer can forward the offer."),
                "file": route_to_file.get(str(item.get("route") or ""), "rentgen-commercial-offer-studio.md"),
            }
            for item in close_packet.get("evidence_requirements", [])[:4]
        ]

    meeting_flow = list(brief.get("meeting_flow") or [])
    if not meeting_flow:
        meeting_flow = [
            {"step": 1, "label": "Orient", "route": "/buyer-concierge", "line": "Name the buyer role, pain and first proof path."},
            {"step": 2, "label": "Prove", "route": "/killer-demo", "line": "Show the proof packet, role sparks and objection answers."},
            {
                "step": 3,
                "label": "Price",
                "route": str(primary.get("route") or "/commercial-offer-studio"),
                "line": str(primary.get("ask") or close_packet.get("primary_ask") or "Select the paid next step."),
            },
            {"step": 4, "label": "Forward", "route": "/evidence-bundle", "line": "Attach buyer brief, offer, checkout gates and hashes."},
        ]
    open_first_path = build_open_first_path(
        existing_path=brief.get("open_first_path"),
        proof_readiness=proof_readiness,
        primary=primary,
        meeting_flow=meeting_flow,
        source="commercial-offer-fallback",
        orient_title="Commercial Offer",
        orient_route="/commercial-offer-studio",
        orient_line="Name the buyer role, pain and first proof path.",
        orient_status=str(primary.get("status") or ("ready" if ready_to_close else "watch")),
        prove_line="Show the proof packet, role sparks and objection answers.",
        close_title=str(recommended.get("title") or order.get("recommended_purchase") or "Selected paid next step"),
        close_route=str(primary.get("route") or recommended.get("route") or order.get("route") or "/commercial-offer-studio"),
        close_line=str(primary.get("ask") or close_packet.get("primary_ask") or "Select the paid next step."),
        close_file="rentgen-commercial-offer-studio.md",
        close_status=str(primary.get("status") or ("ready" if ready_to_close else "watch")),
        verify_line="Attach buyer brief, offer, checkout gates and hashes.",
    )

    routes = sorted(
        {
            "/commercial-offer-studio",
            str(primary.get("route") or "/commercial-offer-studio"),
            *[str(item.get("route") or "") for item in role_cards],
            *[str(item.get("route") or "") for item in proof_readiness],
            *[str(item.get("route") or "") for item in meeting_flow],
            *[str(item.get("route") or "") for item in open_first_path],
        }
        - {""}
    )
    fallback_score = 86 if ready_to_close else 70
    return {
        "status": str(brief.get("purchase_status") or primary.get("status") or ("ready" if ready_to_close else "watch")),
        "score": _int(brief.get("score"), fallback_score),
        "source": str(brief.get("source") or "commercial-offer-derived"),
        "room_line": str(
            brief.get("room_line")
            or f"{primary.get('label', recommended.get('title', 'Select paid next step'))}: "
            f"{primary.get('ask', close_packet.get('primary_ask', 'Attach proof and approve the motion.'))} "
            f"Offer: {recommended.get('commercial_frame', order.get('commercial_frame', 'fixed paid next step'))}."
        ),
        "primary_motion": {
            "label": str(primary.get("label") or recommended.get("title") or order.get("recommended_purchase") or "Select paid next step"),
            "route": str(primary.get("route") or recommended.get("route") or order.get("route") or "/commercial-offer-studio"),
            "status": str(primary.get("status") or ("ready" if ready_to_close else "watch")),
            "ask": str(primary.get("ask") or close_packet.get("primary_ask") or "Select the paid next step."),
            "reason": str(primary.get("reason") or recommended.get("acceptance") or procurement_dossier.get("headline") or ""),
        },
        "recommended_purchase": {
            "title": str(recommended.get("title") or order.get("recommended_purchase") or "Selected paid next step"),
            "route": str(recommended.get("route") or order.get("route") or "/commercial-offer-studio"),
            "commercial_frame": str(recommended.get("commercial_frame") or order.get("commercial_frame") or "fixed paid next step"),
            "acceptance": str(recommended.get("acceptance") or order.get("first_invoice_trigger") or "Buyer accepts owner, scope and proof packet."),
        },
        "role_cards": role_cards[:5],
        "proof_readiness": proof_readiness[:4],
        "meeting_flow": meeting_flow[:4],
        "open_first_path": open_first_path[:4],
        "files": ["buyer-brief.md", "buyer-pulse.md", OPEN_FIRST_PATH_FILE, "rentgen-commercial-offer-studio.md", "rentgen-board-pack.md", "OPEN_FIRST.md"],
        "routes": routes,
        "close_question": str(
            procurement_dossier.get("close_question")
            or "Which procurement artifact is missing before opening the paid local-license motion?"
        ),
    }


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 1C Rentgen Commercial Offer Studio",
        "",
        f"Client: **{report['client']['name']}**",
        f"Status: **{report['decision']['status'].upper()}** / score **{report['decision']['score']}**",
        f"Value anchor: **{report['summary']['first_year_visible_value']} {report['summary']['currency']}**",
        "",
        "## Offers",
        "",
    ]
    for item in report["offers"]:
        lines.append(f"- **{item['title']}** ({item['buyer']}, `{item['route']}`): {item['commercial_frame']}. {item['why_buy']}")
    lines.extend(["", "## Pricing ladder", ""])
    for item in report["pricing_ladder"]:
        lines.append(f"- **{item['tier']}**: {item['anchor']} - {item['logic']}")
    dossier = report.get("procurement_dossier") or {}
    lines.extend(["", "## Procurement Dossier", ""])
    lines.append(f"- **{dossier.get('headline', 'Procurement dossier')}**")
    recommended = dossier.get("recommended_purchase") or {}
    lines.append(
        f"- Recommended purchase: **{recommended.get('title', 'n/a')}** "
        f"(`{recommended.get('route', '/commercial-offer-studio')}`): {recommended.get('commercial_frame', '')}"
    )
    escape = dossier.get("subscription_escape") or {}
    lines.append(f"- Local value: {escape.get('local_value_anchor', 'n/a')}; AI rent baseline: {escape.get('annual_ai_rent', 'n/a')}")
    lines.append(
        f"- Three-year AI rent: {escape.get('three_year_ai_rent', 'n/a')}; "
        f"local license anchor: {escape.get('local_license_anchor', 'n/a')}; "
        f"break-even: {escape.get('break_even_months', 0)} months"
    )
    if escape.get("decision_line"):
        lines.append(f"- Subscription escape: {escape['decision_line']}")
    guardrails = escape.get("guardrails") or []
    if guardrails:
        lines.extend(["", "### Subscription guardrails", ""])
        lines.extend(f"- {item}" for item in guardrails)
    for item in dossier.get("license_model", []):
        lines.append(f"- License model **{item['model']}** for {item['buyer']}: {item['why']}")
    for item in dossier.get("procurement_pack", []):
        lines.append(f"- **{item['owner']}** `{item['route']}`: {item['artifact']} - {item['exit_criteria']}")
    bridge = report.get("offer_room_bridge") or {}
    if bridge:
        lines.extend(["", "## Offer Room Bridge", ""])
        lines.append(f"- Source: **{bridge.get('source', 'n/a')}**; status **{bridge.get('status', 'watch')}** / score **{bridge.get('score', 0)}**")
        lines.append(f"- Room line: {bridge.get('room_line', '')}")
        motion = bridge.get("primary_motion") or {}
        lines.append(f"- Primary motion: **{motion.get('label', 'n/a')}** (`{motion.get('route', '/commercial-offer-studio')}`): {motion.get('ask', '')}")
        recommended_bridge = bridge.get("recommended_purchase") or {}
        lines.append(
            f"- Recommended purchase: **{recommended_bridge.get('title', 'n/a')}** "
            f"(`{recommended_bridge.get('route', '/commercial-offer-studio')}`): {recommended_bridge.get('commercial_frame', '')}"
        )
        lines.extend(open_first_path_markdown_lines(bridge.get("open_first_path"), default_route="/commercial-offer-studio"))
        for item in bridge.get("role_cards", []):
            lines.append(f"- **{item.get('title', item.get('role', 'role'))}** `{item.get('route', '')}`: {item.get('spark', '')}")
        for item in bridge.get("proof_readiness", []):
            lines.append(f"- Proof **{item.get('title', 'proof')}** `{item.get('route', '')}` -> {item.get('file', '')}: {item.get('signal', '')}")
        for item in bridge.get("meeting_flow", []):
            lines.append(f"- Step {item.get('step', '')} **{item.get('label', 'step')}** `{item.get('route', '')}`: {item.get('line', '')}")
    close_packet = report.get("close_packet") or {}
    lines.extend(["", "## Close Packet", ""])
    lines.append(f"- Ready to close: **{close_packet.get('ready_to_close', False)}**")
    lines.append(f"- Mode: **{close_packet.get('close_mode', 'unknown')}**")
    lines.append(f"- Primary ask: {close_packet.get('primary_ask', '')}")
    for item in close_packet.get("mutual_action_plan", []):
        lines.append(f"- **{item['window']}** / {item['owner']} (`{item['route']}`): {item['exit']}")
    lines.extend(["", "### Checkout", ""])
    for item in close_packet.get("checkout", []):
        lines.append(f"- `{item['route']}` **{item['gate']}**: {item['evidence']}")
    lines.extend(["", "### Evidence Requirements", ""])
    for item in close_packet.get("evidence_requirements", []):
        lines.append(f"- `{item.get('route', '')}` **{item.get('artifact', '')}**: {item.get('why', '')}")
    lines.extend(["", "## Buy-now path", ""])
    for item in report["buy_now_path"]:
        lines.append(f"- **{item['step']}** / {item['owner']} (`{item['route']}`): {item['exit']}")
    lines.extend(["", "## Deal risks", ""])
    for item in report["deal_risks"]:
        lines.append(f"- `{item['route']}` {item['risk']} Mitigation: {item['mitigation']}")
    lines.extend(["", "## Caveats", ""])
    lines.extend(f"- {item}" for item in report["caveats"])
    return "\n".join(lines)


def build_commercial_offer_studio(
    *,
    executive: dict[str, Any],
    business_case: dict[str, Any],
    pilot_launchpad: dict[str, Any],
    enterprise_trust_center: dict[str, Any],
    productization: dict[str, Any],
    scenario_hub: dict[str, Any],
    value_packs: dict[str, Any],
    vendor_portfolio: dict[str, Any],
    buyer_brief: dict[str, Any] | None = None,
    client_name: str = "Demo client",
    config_path: str | None = None,
    target_platform_version: str | None = None,
) -> dict[str, Any]:
    """Build the commercial offer and proposal route over proven Rentgen artifacts."""

    value, currency = _business_value(business_case)
    offers = _offers(
        business_case=business_case,
        pilot_launchpad=pilot_launchpad,
        enterprise_trust_center=enterprise_trust_center,
        value_packs=value_packs,
        vendor_portfolio=vendor_portfolio,
    )
    score = max(
        0,
        min(
            100,
            round(
                _score(business_case) * 0.28
                + _score(pilot_launchpad) * 0.20
                + _score(enterprise_trust_center) * 0.20
                + _score(value_packs) * 0.12
                + _score(vendor_portfolio) * 0.10
                + _score(scenario_hub) * 0.10
            ),
        ),
    )
    statuses = {
        _status(executive),
        _status(business_case),
        _status(pilot_launchpad),
        _status(enterprise_trust_center),
        _status(productization),
        _status(vendor_portfolio),
    }
    status = "risk" if statuses & {"blocked", "critical", "fail"} else "ready" if score >= 82 else "watch"
    deal_risks = _deal_risks(
        productization=productization,
        enterprise_trust_center=enterprise_trust_center,
        pilot_launchpad=pilot_launchpad,
    )
    pricing_ladder = _pricing_ladder(business_case)
    procurement_dossier = _procurement_dossier(
        business_case=business_case,
        enterprise_trust_center=enterprise_trust_center,
        productization=productization,
        pilot_launchpad=pilot_launchpad,
        offers=offers,
    )
    stakeholder_closers = _stakeholder_closers()
    proposal_sections = _proposal_sections()
    buy_now_path = _buy_now_path()
    close_packet = _close_packet(
        procurement_dossier=procurement_dossier,
        business_case=business_case,
        enterprise_trust_center=enterprise_trust_center,
        pilot_launchpad=pilot_launchpad,
        productization=productization,
    )
    offer_room_bridge = _offer_room_bridge(
        buyer_brief=buyer_brief,
        procurement_dossier=procurement_dossier,
        close_packet=close_packet,
        stakeholder_closers=stakeholder_closers,
    )
    proof_routes = sorted(
        {route for item in offers for route in item["proof_routes"]}
        | {item["route"] for item in proposal_sections}
        | {item["route"] for item in buy_now_path}
        | {item["route"] for item in close_packet["evidence_requirements"]}
        | {item["route"] for item in close_packet["checkout"]}
        | set(offer_room_bridge["routes"])
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
                "Commercial Offer Studio is ready: proof, trust, pilot and price anchors form a buyable local-license proposal."
                if status == "ready"
                else "Commercial Offer Studio is usable, but trust/productization or pilot caveats should be named before quoting the full rollout."
            ),
        },
        "summary": {
            "offers": len(offers),
            "pricing_tiers": len(pricing_ladder),
            "stakeholder_closers": len(stakeholder_closers),
            "deal_risks": len(deal_risks),
            "proposal_sections": len(proposal_sections),
            "procurement_items": len(procurement_dossier["procurement_pack"]),
            "approval_roles": len(procurement_dossier["approval_matrix"]),
            "close_ready": bool(close_packet["ready_to_close"]),
            "checkout_gates": len(close_packet["checkout"]),
            "proof_routes": len(proof_routes),
            "offer_room_roles": len(offer_room_bridge["role_cards"]),
            "offer_room_proofs": len(offer_room_bridge["proof_readiness"]),
            "offer_room_steps": len(offer_room_bridge["meeting_flow"]),
            "offer_room_open_first": len(offer_room_bridge["open_first_path"]),
            "first_year_visible_value": value,
            "currency": currency,
            "trust_score": _score(enterprise_trust_center),
            "pilot_score": _score(pilot_launchpad),
            "subscription_break_even_months": _int(
                (procurement_dossier.get("subscription_escape") or {}).get("break_even_months")
            ),
        },
        "offers": offers,
        "pricing_ladder": pricing_ladder,
        "procurement_dossier": procurement_dossier,
        "subscription_escape_plan": business_case.get("subscription_escape_plan") or procurement_dossier["subscription_escape"],
        "offer_room_bridge": offer_room_bridge,
        "close_packet": close_packet,
        "stakeholder_closers": stakeholder_closers,
        "deal_risks": deal_risks,
        "proposal_sections": proposal_sections,
        "buy_now_path": buy_now_path,
        "exports": _exports(),
        "proof_routes": proof_routes,
        "source_signals": {
            "executive_status": _status(executive),
            "business_case_score": _score(business_case),
            "pilot_launchpad_status": _status(pilot_launchpad),
            "trust_center_status": _status(enterprise_trust_center),
            "productization_status": _status(productization),
            "value_packs": len(value_packs.get("packs") or []),
            "vendor_work_packages": len(vendor_portfolio.get("work_packages") or []),
        },
        "caveats": [
            "Commercial Offer Studio v1 produces proposal guidance and price anchors, not a legal quote.",
            "Final pricing, taxes, support terms and license metrics remain customer-specific.",
            "Trust Center and Productization caveats must stay visible when quoting enterprise rollout.",
        ],
        "download_name": "rentgen-commercial-offer-studio.md",
    }
    report["markdown"] = _markdown(report)
    return report
