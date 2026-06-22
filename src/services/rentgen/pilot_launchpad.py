"""Pilot launchpad and buyer rollout plan for 1C Rentgen."""

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
ARCHIVE_VERIFICATION_PACKET_ENDPOINT = (
    "/api/v1/evidence-bundle/archive/verification-packet"
)
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
    return str(
        (report.get("decision") or {}).get("status") or report.get("status") or default
    )


def _money(value: Any, currency: str) -> str:
    return f"{_int(value):,}".replace(",", " ") + f" {currency}"


def _route_set(items: list[dict[str, Any]], key: str = "route") -> set[str]:
    return {str(item.get(key) or "") for item in items if item.get(key)}


def _pilot_offers(
    *,
    business_case: dict[str, Any],
    scenario_hub: dict[str, Any],
    vendor_portfolio: dict[str, Any],
) -> list[dict[str, Any]]:
    summary = business_case.get("summary") or {}
    assumptions = business_case.get("assumptions") or {"currency": "RUB"}
    currency = str(assumptions.get("currency") or "RUB")
    scenarios = {item.get("id"): item for item in scenario_hub.get("scenarios", [])}
    return [
        {
            "id": "day-one-proof",
            "title": "24-hour buyer proof",
            "buyer": "director + tech lead",
            "duration": "1 day",
            "price_frame": "fixed discovery / credited into license",
            "route": "/scenario-hub",
            "includes": [
                "Scenario Hub over current configuration signals",
                "Guided Demo route for the buyer committee",
                "first Evidence Bundle with hashes",
            ],
            "acceptance": "Buyer names at least one real pain, one proof route and one artifact they can forward.",
            "why_buy": "This removes first-meeting confusion and makes the product concrete before procurement starts.",
            "evidence": [
                (scenarios.get("left-join-null") or {}).get(
                    "title", "1C-specific defect proof"
                ),
                (scenarios.get("local-enterprise-proof") or {}).get(
                    "title", "local enterprise proof"
                ),
            ],
        },
        {
            "id": "release-pilot",
            "title": "7-day release pilot",
            "buyer": "release manager + architect + QA",
            "duration": "7 days",
            "price_frame": "paid pilot / release window insurance",
            "route": "/release-readiness",
            "includes": [
                "one real change or release window",
                "Change Impact, Testing and Release Readiness",
                "Platform Doctor and Update War Room when upgrade risk exists",
            ],
            "acceptance": "Release decision has gates, caveats, affected tests and a portable approval artifact.",
            "why_buy": "The team stops paying the same manual release tax every sprint or update window.",
            "evidence": [
                f"Review queue: {_int(summary.get('review_queue'))}",
                f"First-year visible value: {_money(summary.get('first_year_visible_value'), currency)}",
            ],
        },
        {
            "id": "enterprise-local-license",
            "title": "30-day local license pilot",
            "buyer": "CIO + security + architecture board",
            "duration": "30 days",
            "price_frame": "enterprise local license with optional AI credits",
            "route": "/enterprise-trust-center",
            "includes": [
                "offline/productization readiness",
                "Evidence Bundle standard for release board",
                "Business Case reviewed with finance assumptions",
                "security and rights/RLS proof path",
            ],
            "acceptance": "Security, finance and architecture can approve the local product contour with known caveats.",
            "why_buy": "The customer buys a local evidence system, not endless AI subscription rent.",
            "evidence": [
                f"AI subscription displacement: {_money(summary.get('ai_subscription_year'), currency)} per year",
                "Productization and SBOM/offline controls are explicit.",
            ],
        },
        {
            "id": "vendor-rollout",
            "title": "Vendor portfolio rollout",
            "buyer": "franchisee / implementation partner",
            "duration": "30 days",
            "price_frame": "partner portfolio license + paid audit packages",
            "route": "/vendor-portfolio",
            "includes": [
                "pre-sale audit story",
                "work packages and value packs",
                "buyer-safe markdown reports",
                "multi-client portfolio view",
            ],
            "acceptance": "Partner can send a buyer-safe audit and convert findings into scoped work packages.",
            "why_buy": "The product becomes a revenue factory for audits, upgrades and release governance.",
            "evidence": [
                f"Work packages: {len(vendor_portfolio.get('work_packages') or [])}",
                "Vendor Portfolio and Value Packs are exportable.",
            ],
        },
    ]


def _day_plan() -> list[dict[str, Any]]:
    return [
        {
            "window": "0-24 hours",
            "owner": "vendor / tech lead",
            "goal": "Make the product understandable and prove one real buyer pain.",
            "actions": [
                "run configuration intake or use current local store",
                "open Scenario Hub and pick the strongest pain",
                "walk Guided Demo in under 8 minutes",
                "export Evidence Bundle",
            ],
            "exit_criteria": "Buyer can repeat the product value without a product expert in the room.",
        },
        {
            "window": "Days 2-7",
            "owner": "delivery lead",
            "goal": "Attach Rentgen to one release/change/update decision.",
            "actions": [
                "choose one real changed module or release window",
                "run Change Impact, Testing and Release Readiness",
                "run Platform Doctor / Update War Room if platform risk is present",
                "review Business Case assumptions with the decision maker",
            ],
            "exit_criteria": "Pilot has a go/no-go artifact, owner actions and measurable acceptance checks.",
        },
        {
            "window": "Days 8-30",
            "owner": "CIO / vendor owner",
            "goal": "Convert pilot proof into license, rollout or partner package.",
            "actions": [
                "standardize Evidence Bundle for approval",
                "close productization and security caveats",
                "pick value packs for the first team or client portfolio",
                "decide local license and optional AI add-on model",
            ],
            "exit_criteria": "Purchase decision is tied to local evidence, adoption route and procurement pack.",
        },
    ]


def _acceptance_matrix(scenario_hub: dict[str, Any]) -> list[dict[str, Any]]:
    scenario_ids = {item.get("id") for item in scenario_hub.get("scenarios", [])}
    return [
        {
            "role": "Developer",
            "must_believe": "The product catches real 1C risks before code review.",
            "scenario_id": "left-join-null"
            if "left-join-null" in scenario_ids
            else "change-blast-radius",
            "proof_route": "/quality",
            "pass_criteria": "A concrete finding includes unsafe pattern, safe rewrite and regression test route.",
        },
        {
            "role": "Architect",
            "must_believe": "Architecture, platform, extensions and rights are connected.",
            "scenario_id": "platform-upgrade",
            "proof_route": "/platform-doctor",
            "pass_criteria": "Upgrade or platform risk has facts, missing facts, caveats and next actions.",
        },
        {
            "role": "Director",
            "must_believe": "This is a local product asset, not a token-rent chat.",
            "scenario_id": "local-enterprise-proof",
            "proof_route": "/business-case",
            "pass_criteria": "Money map, artifacts and local contour are understandable without reading code.",
        },
        {
            "role": "Security",
            "must_believe": "Private code and approval evidence can stay in the customer contour.",
            "scenario_id": "rights-rls",
            "proof_route": "/enterprise-trust-center",
            "pass_criteria": "Productization, SBOM/offline controls and hashed exports are visible with caveats.",
        },
        {
            "role": "Operations",
            "must_believe": "Runtime pain connects to code, release and platform actions.",
            "scenario_id": "locks-after-release",
            "proof_route": "/lock-radar",
            "pass_criteria": "TJ/lock evidence produces affected modules or an explicit missing-data caveat.",
        },
        {
            "role": "Vendor",
            "must_believe": "A scan can become a paid audit and scoped work.",
            "scenario_id": "vendor-presale-audit",
            "proof_route": "/vendor-portfolio",
            "pass_criteria": "Audit report, work packages and buyer-safe markdown are available.",
        },
    ]


def _procurement_pack(
    *,
    business_case: dict[str, Any],
    productization: dict[str, Any],
) -> list[dict[str, Any]]:
    assumptions = business_case.get("assumptions") or {"currency": "RUB"}
    summary = business_case.get("summary") or {}
    currency = str(assumptions.get("currency") or "RUB")
    return [
        {
            "owner": "Sponsor / procurement",
            "question": "What should the room open first after the demo?",
            "artifact": "Buyer Room Packet ZIP",
            "route": "/",
            "answer": f"`{BUYER_ROOM_PACKET_ZIP}` is generated by `{BUYER_ROOM_PACKET_ENDPOINT}` and recorded with `{BUYER_ROOM_PACKET_HASH_HEADER}`.",
        },
        {
            "owner": "Finance",
            "question": "Why buy instead of another AI subscription?",
            "artifact": "Business Case",
            "route": "/business-case",
            "answer": f"First-year visible value: {_money(summary.get('first_year_visible_value'), currency)}; AI subscription displacement is explicit.",
        },
        {
            "owner": "Security",
            "question": "Will private 1C code leave the contour?",
            "artifact": "Enterprise Trust Center",
            "route": "/enterprise-trust-center",
            "answer": f"Local evidence and productization status are visible: {_status(productization)} / {_score(productization)}.",
        },
        {
            "owner": "Security / governance",
            "question": "Who approved risky or write-capable actions?",
            "artifact": "Approvals",
            "route": "/approvals",
            "answer": "Scoped approval records show actor, reason, tool and argument constraints before write-like actions.",
        },
        {
            "owner": "Audit / compliance",
            "question": "Can the pilot proof be audited after the meeting?",
            "artifact": "Audit",
            "route": "/audit",
            "answer": "Tamper-evident audit-chain verification and export are available for the pilot packet.",
        },
        {
            "owner": "Procurement",
            "question": "Which files prove the demo closed and paid activation can start?",
            "artifact": "Archive Acceptance Receipt",
            "route": "/evidence-bundle",
            "answer": f"`{BUYER_ROOM_PACKET_ZIP}` opens the room; `{ARCHIVE_ACCEPTANCE_RECEIPT_MD}` records both archive hashes; `{MEETING_CLOSE_RECEIPT_MD}` and `{POST_DEMO_ACTIVATION_MD}` carry the accepted close and activation handoff.",
        },
        {
            "owner": "Security / procurement",
            "question": "Can the two ZIP archives be verified as one pair before Day 0 starts?",
            "artifact": "Verification Packet ZIP",
            "route": "/evidence-bundle",
            "answer": f"`{ARCHIVE_VERIFICATION_PACKET_ZIP}` is generated by `{ARCHIVE_VERIFICATION_PACKET_ENDPOINT}` and recorded with `{ARCHIVE_VERIFICATION_PACKET_HASH_HEADER}`.",
        },
        {
            "owner": "Architecture board",
            "question": "Does it understand the 1C platform and configuration topology?",
            "artifact": "Scenario Hub + Architecture + Platform Doctor",
            "route": "/scenario-hub",
            "answer": "Scenario routes include platform update, architecture map, extension risk and rights/RLS.",
        },
        {
            "owner": "Release board",
            "question": "Can this change release behavior, not just produce reports?",
            "artifact": "Release Readiness + Evidence Bundle",
            "route": "/release-readiness",
            "answer": "Pilot acceptance requires gates, test impact, owner actions and hashed markdown/JSON evidence.",
        },
        {
            "owner": "Vendor owner",
            "question": "Can a partner sell this tomorrow?",
            "artifact": "Vendor Portfolio",
            "route": "/vendor-portfolio",
            "answer": "Vendor Portfolio turns audit signals into packages, proposal markdown and next actions.",
        },
    ]


def _activation_contract(
    *,
    offers: list[dict[str, Any]],
    day_plan: list[dict[str, Any]],
    acceptance: list[dict[str, Any]],
    productization: dict[str, Any],
) -> dict[str, Any]:
    by_id = {str(item.get("id")): item for item in offers if item.get("id")}
    if _status(productization) in {"fail", "blocked", "critical"}:
        selected = by_id.get("release-pilot") or offers[0]
        primary_ask = (
            "Approve a paid release pilot or hardening scope before enterprise rollout."
        )
    elif _score(productization) >= 80:
        selected = (
            by_id.get("enterprise-local-license")
            or by_id.get("release-pilot")
            or offers[0]
        )
        primary_ask = "Start the paid local license pilot with owner, date, install contour and acceptance gates."
    else:
        selected = by_id.get("day-one-proof") or offers[0]
        primary_ask = "Start a paid 24-hour proof with one named 1C pain and one forwardable evidence archive."

    gates = [
        {
            "gate": "Pilot owner and paid scope are named",
            "route": "/pilot-launchpad",
            "evidence": "Selected offer has owner, duration, acceptance and proof route.",
        },
        {
            "gate": "Approval records are visible",
            "route": "/approvals",
            "evidence": "Risky/write-capable actions require scoped approval records.",
        },
        {
            "gate": "Audit chain is valid",
            "route": "/audit",
            "evidence": "Pilot actions and approval events can be verified/exported.",
        },
        {
            "gate": "Evidence archive is forwardable",
            "route": "/evidence-bundle",
            "evidence": "Evidence Bundle contains hashed JSON/Markdown and governance proof.",
        },
        {
            "gate": "Post-demo close packet is attached",
            "route": "/evidence-bundle",
            "evidence": f"{BUYER_ROOM_PACKET_ZIP}, {MEETING_CLOSE_RECEIPT_MD}, {POST_DEMO_ACTIVATION_MD} and {ARCHIVE_ACCEPTANCE_RECEIPT_MD} are present in the buyer handoff.",
        },
        {
            "gate": "Archive verification packet is attached",
            "route": "/evidence-bundle",
            "evidence": f"{ARCHIVE_VERIFICATION_PACKET_ZIP} is downloaded and {ARCHIVE_VERIFICATION_PACKET_HASH_HEADER} is recorded before Day 0 starts.",
        },
        {
            "gate": "Trust/productization caveats are accepted or scoped",
            "route": "/enterprise-trust-center",
            "evidence": "Trust Center and Productization keep install/offline/platform caveats visible.",
        },
    ]
    milestones = [
        {
            "window": "Day 0",
            "owner": "sponsor + delivery lead",
            "route": "/pilot-launchpad",
            "acceptance": "Paid scope, owner, date, first route and proof recipient are named.",
        },
        {
            "window": "Day 7",
            "owner": "tech lead + security",
            "route": "/scenario-hub",
            "acceptance": "First real 1C pain has proof, caveats, tests/owner actions and audit trail.",
        },
        {
            "window": "Day 30",
            "owner": "sponsor",
            "route": "/outcome-ledger",
            "acceptance": "Pilot converts to local license, hardening scope, vendor package or explicit no-go.",
        },
    ]
    commitments = [
        {
            "role": "sponsor",
            "commitment": "Name paid owner, date and proof recipient.",
            "route": "/pilot-launchpad",
        },
        {
            "role": "tech lead",
            "commitment": "Pick one real 1C pain or release/change scope.",
            "route": "/scenario-hub",
        },
        {
            "role": "security",
            "commitment": "Review approval/audit evidence and trust caveats.",
            "route": "/approvals",
        },
        {
            "role": "finance",
            "commitment": "Accept local value anchor and optional AI-credit separation.",
            "route": "/business-case",
        },
        {
            "role": "delivery",
            "commitment": "Refresh Evidence Bundle at each acceptance window.",
            "route": "/evidence-bundle",
        },
    ]
    proof_routes = sorted(
        {str(selected.get("route") or "/pilot-launchpad")}
        | _route_set(gates)
        | _route_set(milestones)
        | _route_set(commitments)
        | {
            str(item.get("proof_route") or "")
            for item in acceptance
            if item.get("proof_route")
        }
    )
    ready_to_activate = bool(
        selected
        and len(acceptance) >= 4
        and _status(productization) not in {"fail", "blocked", "critical"}
    )
    handoff_files = [
        {
            "title": "Buyer Room Packet ZIP",
            "filename": BUYER_ROOM_PACKET_ZIP,
            "route": "/",
            "endpoint": BUYER_ROOM_PACKET_ENDPOINT,
            "hash_header": BUYER_ROOM_PACKET_HASH_HEADER,
            "reason": "Open-first packet with buyer brief, pulse, room plan, purchase path and procurement handoff.",
        },
        {
            "title": "Meeting Close Receipt",
            "filename": MEETING_CLOSE_RECEIPT_MD,
            "route": "/killer-demo",
            "reason": "Accepted roles, blockers, send files and next paid step from the demo room.",
        },
        {
            "title": "Post-Demo Activation Handoff",
            "filename": POST_DEMO_ACTIVATION_MD,
            "route": "/pilot-launchpad",
            "reason": "Day 0/7/30 activation path, invoice trigger and outcome route.",
        },
        {
            "title": "Archive Acceptance Receipt",
            "filename": ARCHIVE_ACCEPTANCE_RECEIPT_MD,
            "route": "/evidence-bundle",
            "reason": "Evidence ZIP and Killer Demo ZIP filenames, hash headers and file boundary receipt.",
        },
        {
            "title": "Archive Acceptance Receipt JSON",
            "filename": ARCHIVE_ACCEPTANCE_RECEIPT_JSON,
            "route": "/evidence-bundle",
            "reason": "Machine-readable procurement receipt for ticketing or approval systems.",
        },
        {
            "title": "Verification Packet ZIP",
            "filename": ARCHIVE_VERIFICATION_PACKET_ZIP,
            "route": "/evidence-bundle",
            "reason": f"Pair-level control ZIP generated by {ARCHIVE_VERIFICATION_PACKET_ENDPOINT}; record {ARCHIVE_VERIFICATION_PACKET_HASH_HEADER}.",
        },
        {
            "title": "Killer Demo Manifest",
            "filename": KILLER_DEMO_MANIFEST_JSON,
            "route": "/killer-demo",
            "reason": "Close-room ZIP file hashes and role packet inventory.",
        },
    ]
    proof_routes = sorted(set(proof_routes) | _route_set(handoff_files))
    return {
        "ready_to_activate": ready_to_activate,
        "selected_offer_id": str(selected.get("id") or ""),
        "selected_offer_title": str(selected.get("title") or "Selected paid pilot"),
        "primary_ask": primary_ask,
        "commercial_frame": str(selected.get("price_frame") or "paid next step"),
        "invoice_trigger": "Buyer names paid owner, scope, date, proof recipient and accepted governance gates.",
        "start_route": str(selected.get("route") or "/pilot-launchpad"),
        "activation_line": (
            "Pilot can start as a paid motion with governance gates attached."
            if ready_to_activate
            else "Start with proof/hardening scope until productization and acceptance gates are safe."
        ),
        "gates": gates,
        "milestones": milestones,
        "buyer_commitments": commitments,
        "handoff_files": handoff_files,
        "proof_routes": proof_routes,
        "script": [
            "Pick the paid offer and name the owner before leaving the meeting.",
            "Attach approvals, audit verification and Evidence Bundle to the pilot packet.",
            "Use Day 7 for proof and Day 30 for conversion, not vague follow-up.",
        ],
    }


def _acceptance_register(
    *,
    acceptance: list[dict[str, Any]],
    procurement: list[dict[str, Any]],
    activation: dict[str, Any],
    productization: dict[str, Any],
) -> dict[str, Any]:
    proof_routes = set(activation.get("proof_routes") or [])
    proof_routes |= {
        str(item.get("proof_route") or "")
        for item in acceptance
        if item.get("proof_route")
    }
    proof_routes |= _route_set(procurement)
    product_status = _status(productization)
    product_blocked = product_status in {"fail", "blocked", "critical"}
    activation_ready = bool(activation.get("ready_to_activate"))
    acceptance_by_role = {
        str(item.get("role") or "").lower(): item for item in acceptance
    }

    def status(
        required_routes: list[str], *, blocked: bool = False, watch: bool = False
    ) -> str:
        if blocked:
            return "blocked"
        if any(route not in proof_routes for route in required_routes):
            return "watch"
        if watch:
            return "watch"
        return "ready"

    def item(
        *,
        id: str,
        role: str,
        owner: str,
        window: str,
        decision: str,
        acceptance_text: str,
        evidence_route: str,
        evidence_file: str,
        required_routes: list[str],
        next_action: str,
        blocked: bool = False,
        watch: bool = False,
        blocker: str = "",
    ) -> dict[str, Any]:
        item_status = status(required_routes, blocked=blocked, watch=watch)
        return {
            "id": id,
            "role": role,
            "owner": owner,
            "window": window,
            "decision": decision,
            "acceptance": acceptance_text,
            "evidence_route": evidence_route,
            "evidence_file": evidence_file,
            "required_routes": required_routes,
            "status": item_status,
            "blocker": blocker if item_status == "blocked" else "",
            "next_action": next_action,
        }

    developer = acceptance_by_role.get("developer") or {}
    architect = acceptance_by_role.get("architect") or {}
    director = acceptance_by_role.get("director") or {}
    security = acceptance_by_role.get("security") or {}
    rows = [
        item(
            id="day0-owner-scope",
            role="Sponsor",
            owner="sponsor + delivery lead",
            window="Day 0",
            decision="Start the paid pilot with named owner, scope, date and proof recipient.",
            acceptance_text=str(
                activation.get("invoice_trigger")
                or "Owner, scope and proof recipient are named."
            ),
            evidence_route="/pilot-launchpad",
            evidence_file="rentgen-pilot-launchpad.md",
            required_routes=["/pilot-launchpad"],
            next_action="Name pilot owner, scope, date and proof recipient before leaving the meeting.",
            watch=not activation_ready,
        ),
        item(
            id="day0-close-packet",
            role="Procurement / sponsor",
            owner="procurement + sponsor",
            window="Day 0",
            decision="Attach the meeting close receipt, activation handoff, archive receipt and verification packet before paid work starts.",
            acceptance_text=f"`{BUYER_ROOM_PACKET_ZIP}`, `{MEETING_CLOSE_RECEIPT_MD}`, `{POST_DEMO_ACTIVATION_MD}`, `{ARCHIVE_ACCEPTANCE_RECEIPT_MD}` and `{ARCHIVE_VERIFICATION_PACKET_ZIP}` are present in the pilot ticket.",
            evidence_route="/evidence-bundle",
            evidence_file=ARCHIVE_ACCEPTANCE_RECEIPT_MD,
            required_routes=[
                "/",
                "/killer-demo",
                "/pilot-launchpad",
                "/evidence-bundle",
            ],
            next_action="Download the Buyer Room Packet, both archives and verification packet, then attach close-room receipts to the paid activation ticket.",
            watch=not activation_ready,
        ),
        item(
            id="day0-verification-packet",
            role="Security / procurement",
            owner="security + procurement",
            window="Day 0",
            decision="Accept the Evidence/Killer archive pair only after the verification packet is recorded.",
            acceptance_text=f"`{ARCHIVE_VERIFICATION_PACKET_ZIP}` has `{ARCHIVE_VERIFICATION_PACKET_HASH_HEADER}` and contains the pair-level verification receipts.",
            evidence_route="/evidence-bundle",
            evidence_file=ARCHIVE_VERIFICATION_PACKET_ZIP,
            required_routes=["/evidence-bundle", "/killer-demo"],
            next_action="Download the verification packet after both archives and store the packet hash in the procurement ticket.",
            watch=not activation_ready,
        ),
        item(
            id="day0-finance",
            role="Finance",
            owner="finance owner",
            window="Day 0",
            decision=str(
                director.get("must_believe")
                or "Accept local product value and optional AI-credit separation."
            ),
            acceptance_text=str(
                director.get("pass_criteria")
                or "Money map and local contour are understood without reading code."
            ),
            evidence_route="/business-case",
            evidence_file="rentgen-business-case.md",
            required_routes=["/business-case", "/commercial-offer-studio"],
            next_action="Attach Business Case and Commercial Offer Studio to the purchase motion.",
        ),
        item(
            id="day1-security-governance",
            role="Security / governance",
            owner="security owner",
            window="Day 1",
            decision=str(
                security.get("must_believe")
                or "Approve local contour, approvals and audit proof before write-like work."
            ),
            acceptance_text=str(
                security.get("pass_criteria")
                or "Approval records, audit export and trust caveats are visible."
            ),
            evidence_route="/approvals",
            evidence_file="governance-proof.md",
            required_routes=[
                "/approvals",
                "/audit",
                "/evidence-bundle",
                "/enterprise-trust-center",
            ],
            next_action="Review approval/audit evidence and turn unresolved caveats into scope.",
            blocked=product_blocked,
            watch=product_status not in {"pass", "ready"},
            blocker="Productization is blocked/critical; scope hardening before enterprise rollout.",
        ),
        item(
            id="day1-architecture",
            role="Architect",
            owner="architecture board",
            window="Day 1",
            decision=str(
                architect.get("must_believe")
                or "Accept platform, topology, extension and rollout risks."
            ),
            acceptance_text=str(
                architect.get("pass_criteria")
                or "Platform and productization caveats have owner or accepted risk."
            ),
            evidence_route="/enterprise-trust-center",
            evidence_file="rentgen-enterprise-trust-center.md",
            required_routes=["/enterprise-trust-center", "/productization"],
            next_action="Close install mode, platform version and offline/productization caveats.",
            blocked=product_blocked,
            watch=product_status not in {"pass", "ready"},
            blocker="Productization is blocked/critical; convert rollout into hardening scope.",
        ),
        item(
            id="day7-developer-proof",
            role="Developer / tech lead",
            owner="tech lead",
            window="Day 7",
            decision=str(
                developer.get("must_believe")
                or "Trust the product on one real 1C finding."
            ),
            acceptance_text=str(
                developer.get("pass_criteria")
                or "Finding, safe rewrite and regression route are explainable."
            ),
            evidence_route=str(developer.get("proof_route") or "/quality"),
            evidence_file="rentgen-guided-demo.md",
            required_routes=[
                str(developer.get("proof_route") or "/quality"),
                "/scenario-hub",
            ],
            next_action="Pick one real 1C pain, run proof and record test/owner action.",
        ),
        item(
            id="day7-release-proof",
            role="QA / release board",
            owner="release owner",
            window="Day 7",
            decision="Accept go/no-go proof instead of screenshots or informal chat notes.",
            acceptance_text="Release decision has gates, caveats, affected tests and portable evidence.",
            evidence_route="/release-readiness",
            evidence_file="rentgen-release-readiness.md",
            required_routes=["/release-readiness", "/evidence-bundle"],
            next_action="Attach release gates and refreshed Evidence Bundle to the pilot packet.",
        ),
        item(
            id="day30-conversion",
            role="Sponsor / procurement",
            owner="sponsor + procurement",
            window="Day 30",
            decision="Convert pilot to local license, hardening scope, vendor package or explicit no-go.",
            acceptance_text="Day 30 decision names measured outcome, caveats and next paid package.",
            evidence_route="/outcome-ledger",
            evidence_file="rentgen-outcome-ledger.md",
            required_routes=[
                "/outcome-ledger",
                "/commercial-offer-studio",
                "/evidence-bundle",
            ],
            next_action="Refresh Outcome Ledger and select rollout, renewal, hardening or no-go.",
        ),
    ]
    blocked_items = [row for row in rows if row["status"] == "blocked"]
    watch_items = [row for row in rows if row["status"] == "watch"]
    ready_items = [row for row in rows if row["status"] == "ready"]
    return {
        "ready_to_sign": not blocked_items,
        "owner_line": "Day 0/7/30 acceptance is explicit: every owner has a decision, route, file and next action.",
        "items": rows,
        "ready_items": len(ready_items),
        "watch_items": len(watch_items),
        "blocked_items": len(blocked_items),
        "proof_routes": sorted(route for route in proof_routes if route),
    }


def _pilot_room_bridge(
    *,
    buyer_brief: dict[str, Any] | None,
    activation: dict[str, Any],
    acceptance: list[dict[str, Any]],
    acceptance_register: dict[str, Any],
) -> dict[str, Any]:
    brief = buyer_brief or {}
    ready_to_activate = bool(activation.get("ready_to_activate"))
    primary = dict(brief.get("primary_motion") or {})
    activation_motion = {
        "label": str(activation.get("selected_offer_title") or "Start paid pilot"),
        "route": str(activation.get("start_route") or "/pilot-launchpad"),
        "status": "ready" if ready_to_activate else "watch",
        "ask": str(
            activation.get("primary_ask")
            or "Start the paid pilot with owner, date and evidence gates."
        ),
        "reason": str(
            activation.get("activation_line")
            or "Pilot activation needs owner, gates and acceptance evidence."
        ),
        "invoice_trigger": str(activation.get("invoice_trigger") or ""),
    }
    if not primary:
        primary = activation_motion

    role_cards = list(brief.get("role_cards") or [])
    if not role_cards:
        role_cards = [
            {
                "role": item["role"].casefold(),
                "title": item["role"],
                "route": item["proof_route"],
                "status": "ready" if ready_to_activate else "watch",
                "spark": item["must_believe"],
                "proof_file": "rentgen-pilot-launchpad.md",
            }
            for item in acceptance[:5]
        ]

    route_to_file = {
        "/approvals": "governance-proof.md",
        "/audit": "rentgen-audit-log.jsonl",
        "/evidence-bundle": "OPEN_FIRST.md",
        "/enterprise-trust-center": "rentgen-security-questionnaire.md",
        "/business-case": "rentgen-business-case.md",
        "/pilot-launchpad": "rentgen-pilot-launchpad.md",
    }
    proof_readiness = list(brief.get("proof_readiness") or [])
    if not proof_readiness:
        proof_readiness = [
            {
                "id": str(item.get("gate") or item.get("route") or "pilot-proof")
                .lower()
                .replace(" ", "-"),
                "title": str(item.get("gate") or "Pilot proof"),
                "route": str(item.get("route") or "/pilot-launchpad"),
                "status": "ready" if ready_to_activate else "watch",
                "signal": str(
                    item.get("evidence")
                    or "Required before the buyer can start the paid pilot."
                ),
                "file": route_to_file.get(
                    str(item.get("route") or ""), "rentgen-pilot-launchpad.md"
                ),
            }
            for item in activation.get("gates", [])[:4]
        ]

    meeting_flow = list(brief.get("meeting_flow") or [])
    if not meeting_flow:
        meeting_flow = [
            {
                "step": 1,
                "label": "Orient",
                "route": "/buyer-concierge",
                "line": "Name role, pain and the first proof path.",
            },
            {
                "step": 2,
                "label": "Prove",
                "route": "/killer-demo",
                "line": "Show one buyer proof and the packet that can be forwarded.",
            },
            {
                "step": 3,
                "label": "Activate",
                "route": str(activation_motion["route"]),
                "line": str(activation_motion["ask"]),
            },
            {
                "step": 4,
                "label": "Sign",
                "route": "/evidence-bundle",
                "line": "Attach approvals, audit proof, buyer brief and pilot evidence.",
            },
        ]
    open_first_path = build_open_first_path(
        existing_path=brief.get("open_first_path"),
        proof_readiness=proof_readiness,
        primary=primary,
        meeting_flow=meeting_flow,
        source="pilot-launchpad-fallback",
        orient_title="Pilot room",
        orient_route="/pilot-launchpad",
        orient_line="Name role, pain and first proof path.",
        orient_status=str(primary.get("status") or activation_motion["status"]),
        prove_line="Show one buyer proof and forwarding packet.",
        prove_file="OPEN_FIRST.md",
        prove_status=str(activation_motion["status"]),
        close_title="Post-Demo Activation Handoff",
        close_route=str(activation_motion["route"]),
        close_line=str(activation_motion["ask"]),
        close_file=POST_DEMO_ACTIVATION_MD,
        close_status=str(activation_motion["status"]),
        verify_line="Attach the pair-level archive verification packet before Day 0 acceptance.",
    )

    routes = sorted(
        {
            "/pilot-launchpad",
            str(primary.get("route") or "/pilot-launchpad"),
            str(activation_motion["route"]),
            *[str(item.get("route") or "") for item in role_cards],
            *[str(item.get("route") or "") for item in proof_readiness],
            *[str(item.get("route") or "") for item in meeting_flow],
            *[str(item.get("route") or "") for item in open_first_path],
            *[str(item) for item in activation.get("proof_routes", [])],
            *[str(item) for item in acceptance_register.get("proof_routes", [])],
        }
        - {""}
    )
    fallback_score = 84 if ready_to_activate else 68
    return {
        "status": str(
            brief.get("purchase_status")
            or primary.get("status")
            or ("ready" if ready_to_activate else "watch")
        ),
        "score": _int(brief.get("score"), fallback_score),
        "source": str(brief.get("source") or "pilot-launchpad-derived"),
        "room_line": str(
            brief.get("room_line")
            or f"{primary.get('label', activation_motion['label'])}: "
            f"{primary.get('ask', activation_motion['ask'])} "
            f"Activation: {activation_motion['invoice_trigger']}"
        ),
        "primary_motion": {
            "label": str(primary.get("label") or activation_motion["label"]),
            "route": str(primary.get("route") or activation_motion["route"]),
            "status": str(primary.get("status") or activation_motion["status"]),
            "ask": str(primary.get("ask") or activation_motion["ask"]),
            "reason": str(primary.get("reason") or activation_motion["reason"]),
        },
        "activation_motion": activation_motion,
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
            "rentgen-pilot-launchpad.md",
            "governance-proof.md",
            "OPEN_FIRST.md",
        ],
        "routes": routes,
        "activation_question": (
            "Can we start the selected paid pilot now with owner, date, gates and evidence packet?"
            if ready_to_activate
            else "Which blocker must become a proof sprint or hardening scope before activation?"
        ),
    }


def _risk_burndown(scenario_hub: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    scenarios = {
        item.get("id"): item
        for item in scenario_hub.get("scenarios", [])
        if item.get("id")
    }
    for item in scenario_hub.get("recommended_path", [])[:5]:
        scenario = scenarios.get(item.get("scenario_id")) or {}
        rows.append(
            {
                "scenario_id": str(item.get("scenario_id") or ""),
                "buyer_risk": str(scenario.get("pain") or item.get("title") or ""),
                "close_action": str(
                    scenario.get("buyer_line") or item.get("why") or ""
                ),
                "route": str(
                    item.get("route") or scenario.get("route") or "/scenario-hub"
                ),
            }
        )
    return rows


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
        {
            "title": "Meeting Close Receipt",
            "filename": MEETING_CLOSE_RECEIPT_MD,
            "route": "/killer-demo",
        },
        {
            "title": "Post-Demo Activation Handoff",
            "filename": POST_DEMO_ACTIVATION_MD,
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
        },
        {
            "title": "Demo Command Center markdown",
            "filename": "rentgen-demo-command-center.md",
            "route": "/demo-command-center",
        },
        {
            "title": "Buyer Concierge markdown",
            "filename": "rentgen-buyer-concierge.md",
            "route": "/buyer-concierge",
        },
        {
            "title": "Commercial Offer Studio markdown",
            "filename": "rentgen-commercial-offer-studio.md",
            "route": "/commercial-offer-studio",
        },
        {
            "title": "Enterprise Trust Center markdown",
            "filename": "rentgen-enterprise-trust-center.md",
            "route": "/enterprise-trust-center",
        },
        {
            "title": "Pilot Launchpad markdown",
            "filename": "rentgen-pilot-launchpad.md",
            "route": "/pilot-launchpad",
        },
        {
            "title": "Scenario Hub markdown",
            "filename": "rentgen-scenario-hub.md",
            "route": "/scenario-hub",
        },
        {
            "title": "Guided Demo markdown",
            "filename": "rentgen-guided-demo.md",
            "route": "/guided-demo",
        },
        {
            "title": "Business Case markdown",
            "filename": "rentgen-business-case.md",
            "route": "/business-case",
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


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 1C Rentgen Pilot Launchpad",
        "",
        f"Client: **{report['client']['name']}**",
        f"Status: **{report['decision']['status'].upper()}** / score **{report['decision']['score']}**",
        f"Pilot horizon: **{report['summary']['pilot_days']} days**",
        "",
        "## Pilot offers",
        "",
    ]
    for item in report["pilot_offers"]:
        lines.append(
            f"- **{item['title']}** ({item['duration']}, `{item['route']}`): {item['acceptance']}"
        )
    lines.extend(["", "## Day plan", ""])
    for item in report["day_plan"]:
        lines.append(
            f"- **{item['window']}** / {item['owner']}: {item['exit_criteria']}"
        )
    lines.extend(["", "## Acceptance matrix", ""])
    for item in report["acceptance_matrix"]:
        lines.append(
            f"- **{item['role']}** (`{item['proof_route']}`): {item['pass_criteria']}"
        )
    lines.extend(["", "## Procurement pack", ""])
    for item in report["procurement_pack"]:
        lines.append(f"- **{item['owner']}** / {item['artifact']}: {item['answer']}")
    activation = report.get("activation_contract") or {}
    if activation:
        lines.extend(["", "## Activation Contract", ""])
        lines.append(
            f"- Ready to activate: **{bool(activation.get('ready_to_activate'))}**"
        )
        lines.append(
            f"- Selected offer: **{activation.get('selected_offer_title', 'n/a')}** (`{activation.get('start_route', '/pilot-launchpad')}`)"
        )
        lines.append(f"- Primary ask: {activation.get('primary_ask', '')}")
        lines.append(f"- Invoice trigger: {activation.get('invoice_trigger', '')}")
        for item in activation.get("gates", []):
            lines.append(
                f"- Gate `{item.get('route', '/pilot-launchpad')}`: {item.get('gate', '')} - {item.get('evidence', '')}"
            )
        handoff_files = activation.get("handoff_files") or []
        if handoff_files:
            lines.extend(["", "### Post-Demo Handoff Files", ""])
            for item in handoff_files:
                lines.append(
                    f"- `{item.get('filename', '')}` (`{item.get('route', '/pilot-launchpad')}`): {item.get('reason', '')}"
                )
        for item in activation.get("milestones", []):
            lines.append(
                f"- **{item.get('window', '')}** / {item.get('owner', '')}: {item.get('acceptance', '')}"
            )
    register = report.get("acceptance_register") or {}
    if register:
        lines.extend(["", "## Acceptance Register", ""])
        lines.append(f"- Ready to sign: **{bool(register.get('ready_to_sign'))}**")
        lines.append(
            f"- Ready/watch/blocked: **{register.get('ready_items', 0)}** / **{register.get('watch_items', 0)}** / **{register.get('blocked_items', 0)}**"
        )
        lines.append(f"- Owner line: {register.get('owner_line', '')}")
        for item in register.get("items", []):
            lines.append(
                f"- **{item.get('window', '')}** / {item.get('role', '')} / {item.get('owner', '')}: "
                f"{item.get('status', '')}. {item.get('decision', '')} "
                f"Evidence: `{item.get('evidence_file', '')}` `{item.get('evidence_route', '')}`"
            )
    bridge = report.get("pilot_room_bridge") or {}
    if bridge:
        lines.extend(["", "## Pilot Room Bridge", ""])
        lines.append(
            f"- Source: **{bridge.get('source', 'n/a')}**; status **{bridge.get('status', 'watch')}** / score **{bridge.get('score', 0)}**"
        )
        lines.append(f"- Room line: {bridge.get('room_line', '')}")
        motion = bridge.get("primary_motion") or {}
        lines.append(
            f"- Primary motion: **{motion.get('label', 'n/a')}** (`{motion.get('route', '/pilot-launchpad')}`): {motion.get('ask', '')}"
        )
        activation_motion = bridge.get("activation_motion") or {}
        lines.append(
            f"- Activation motion: **{activation_motion.get('label', 'n/a')}** "
            f"(`{activation_motion.get('route', '/pilot-launchpad')}`): {activation_motion.get('ask', '')}"
        )
        for item in bridge.get("open_first_path", []):
            lines.append(
                f"- Open-first {item.get('step', '')} **{item.get('label', 'step')}** "
                f"`{item.get('route', '')}` -> `{item.get('file', '')}`: {item.get('line', '')}"
            )
        for item in bridge.get("role_cards", []):
            lines.append(
                f"- **{item.get('title', item.get('role', 'role'))}** `{item.get('route', '')}`: {item.get('spark', '')}"
            )
        for item in bridge.get("proof_readiness", []):
            lines.append(
                f"- Proof **{item.get('title', 'proof')}** `{item.get('route', '')}` -> {item.get('file', '')}: {item.get('signal', '')}"
            )
        for item in bridge.get("meeting_flow", []):
            lines.append(
                f"- Step {item.get('step', '')} **{item.get('label', 'step')}** `{item.get('route', '')}`: {item.get('line', '')}"
            )
    lines.extend(["", "## Caveats", ""])
    lines.extend(f"- {item}" for item in report["caveats"])
    return "\n".join(lines)


def build_pilot_launchpad(
    *,
    executive: dict[str, Any],
    scenario_hub: dict[str, Any],
    guided_demo: dict[str, Any],
    business_case: dict[str, Any],
    productization: dict[str, Any],
    value_packs: dict[str, Any],
    vendor_portfolio: dict[str, Any],
    buyer_brief: dict[str, Any] | None = None,
    client_name: str = "Demo client",
    config_path: str | None = None,
    target_platform_version: str | None = None,
) -> dict[str, Any]:
    """Build the buyer pilot and procurement plan over live Rentgen evidence."""

    score = max(
        0,
        min(
            100,
            round(
                _score(scenario_hub) * 0.25
                + _score(guided_demo) * 0.20
                + _score(business_case) * 0.25
                + _score(productization) * 0.15
                + _score(value_packs) * 0.10
                + _score(vendor_portfolio) * 0.05
            ),
        ),
    )
    statuses = {
        _status(executive),
        _status(scenario_hub),
        _status(guided_demo),
        _status(business_case),
        _status(productization),
        _status(vendor_portfolio),
    }
    status = (
        "risk"
        if statuses & {"blocked", "critical", "fail"}
        else "ready"
        if score >= 82
        else "watch"
    )
    offers = _pilot_offers(
        business_case=business_case,
        scenario_hub=scenario_hub,
        vendor_portfolio=vendor_portfolio,
    )
    day_plan = _day_plan()
    acceptance = _acceptance_matrix(scenario_hub)
    procurement = _procurement_pack(
        business_case=business_case,
        productization=productization,
    )
    activation = _activation_contract(
        offers=offers,
        day_plan=day_plan,
        acceptance=acceptance,
        productization=productization,
    )
    acceptance_register = _acceptance_register(
        acceptance=acceptance,
        procurement=procurement,
        activation=activation,
        productization=productization,
    )
    pilot_room_bridge = _pilot_room_bridge(
        buyer_brief=buyer_brief,
        activation=activation,
        acceptance=acceptance,
        acceptance_register=acceptance_register,
    )
    risk_burndown = _risk_burndown(scenario_hub)
    proof_routes = sorted(
        {item["route"] for item in offers}
        | {item["proof_route"] for item in acceptance}
        | {item["route"] for item in procurement}
        | {item["route"] for item in risk_burndown}
        | {item["route"] for item in _exports()}
        | set(activation["proof_routes"])
        | set(acceptance_register["proof_routes"])
        | set(pilot_room_bridge["routes"])
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
                "Pilot Launchpad is ready: buyer proof, acceptance checks and procurement artifacts are connected."
                if status == "ready"
                else "Pilot Launchpad is usable, but caveats and red productization signals must stay visible during the pilot."
            ),
        },
        "summary": {
            "pilot_days": 30,
            "offers": len(offers),
            "stages": len(day_plan),
            "acceptance_checks": len(acceptance),
            "procurement_items": len(procurement),
            "risk_burndown_items": len(risk_burndown),
            "value_packs": len(value_packs.get("packs") or []),
            "activation_ready": bool(activation["ready_to_activate"]),
            "activation_gates": len(activation["gates"]),
            "acceptance_register_items": len(acceptance_register["items"]),
            "acceptance_register_ready": bool(acceptance_register["ready_to_sign"]),
            "acceptance_register_watch": acceptance_register["watch_items"],
            "acceptance_register_blocked": acceptance_register["blocked_items"],
            "pilot_room_roles": len(pilot_room_bridge["role_cards"]),
            "pilot_room_proofs": len(pilot_room_bridge["proof_readiness"]),
            "pilot_room_steps": len(pilot_room_bridge["meeting_flow"]),
            "pilot_room_open_first": len(pilot_room_bridge["open_first_path"]),
        },
        "pilot_offers": offers,
        "day_plan": day_plan,
        "acceptance_matrix": acceptance,
        "procurement_pack": procurement,
        "activation_contract": activation,
        "acceptance_register": acceptance_register,
        "pilot_room_bridge": pilot_room_bridge,
        "risk_burndown": risk_burndown,
        "close_script": [
            activation["primary_ask"],
            "Open Scenario Hub and let the buyer choose the pain.",
            "Walk the matching Guided Demo proof route.",
            "Open Business Case for money and local-license positioning.",
            "Open Commercial Offer Studio and pick one paid package.",
            "Show Trust Center and Evidence Bundle before security asks.",
            "Pick one pilot offer and assign owner, date and acceptance check.",
        ],
        "exports": _exports(),
        "proof_routes": proof_routes,
        "source_signals": {
            "executive_status": _status(executive),
            "scenario_hub_status": _status(scenario_hub),
            "guided_demo_status": _status(guided_demo),
            "business_case_score": _score(business_case),
            "productization_status": _status(productization),
            "activation_offer": activation["selected_offer_id"],
            "vendor_work_packages": len(vendor_portfolio.get("work_packages") or []),
        },
        "caveats": [
            "Pilot Launchpad v1 is a buyer plan over implemented evidence surfaces; pricing and legal terms remain customer-specific.",
            "Acceptance criteria prove the pilot artifact, not an audited production SLA.",
            "Security and productization caveats must be reviewed before enterprise rollout.",
        ],
        "download_name": "rentgen-pilot-launchpad.md",
    }
    report["markdown"] = _markdown(report)
    return report
