"""Buyer scenario hub for 1C Rentgen."""

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


def _evidence(label: str, to: str) -> dict[str, str]:
    return {"label": label, "to": to}


def _scenario(
    *,
    id: str,
    title: str,
    pain: str,
    buyer_line: str,
    primary_role: str,
    roles: list[str],
    minutes: float,
    severity: int,
    route: str,
    proof: str,
    success_signal: str,
    demo_script: list[str],
    evidence_routes: list[dict[str, str]],
    outputs: list[str],
    why_buy_now: str,
    maturity: str = "live",
) -> dict[str, Any]:
    return {
        "id": id,
        "title": title,
        "pain": pain,
        "buyer_line": buyer_line,
        "primary_role": primary_role,
        "roles": roles,
        "minutes": minutes,
        "severity": max(1, min(5, severity)),
        "route": route,
        "proof": proof,
        "success_signal": success_signal,
        "demo_script": demo_script,
        "evidence_routes": evidence_routes,
        "outputs": outputs,
        "why_buy_now": why_buy_now,
        "maturity": maturity,
    }


def _scenarios(
    *,
    executive: dict[str, Any],
    business_case: dict[str, Any],
    productization: dict[str, Any],
    value_packs: dict[str, Any],
    vendor_portfolio: dict[str, Any],
) -> list[dict[str, Any]]:
    kpis = executive.get("kpis") or {}
    risk = executive.get("risk_summary") or {}
    business_summary = business_case.get("summary") or {}
    product_summary = productization.get("summary") or {}
    vendor_summary = vendor_portfolio.get("portfolio") or {}
    return [
        _scenario(
            id="release-go-no-go",
            title="Can we release today?",
            pain="Release meetings depend on memory, screenshots and manual heroics.",
            buyer_line="Open one screen and answer go/no-go with gates, caveats and owner actions.",
            primary_role="director",
            roles=["director", "qa", "release"],
            minutes=1.0,
            severity=4 if _int(kpis.get("review_queue")) else 3,
            route="/release-readiness",
            proof=f"Review queue: {_int(kpis.get('review_queue'))}; executive status: {_status(executive)} / {_score(executive)}.",
            success_signal="The release board can approve, delay or scope fixes from the same evidence pack.",
            demo_script=[
                "Start from the executive decision and explain why it is not a green checkbox.",
                "Open Release Readiness and show gates, tests and residual risk.",
                "Close on Evidence Bundle so the board gets portable proof.",
            ],
            evidence_routes=[
                _evidence("Release Readiness", "/release-readiness"),
                _evidence("Testing", "/testing"),
                _evidence("Evidence Bundle", "/evidence-bundle"),
            ],
            outputs=["release gate", "test gap list", "approval markdown"],
            why_buy_now="Every release window repeats this decision cost until the evidence path is standardized.",
        ),
        _scenario(
            id="left-join-null",
            title="LEFT JOIN field without ЕстьNULL / ЕСТЬ NULL guard",
            pain="A 1C query returns wrong totals when a joined row is missing and NULL flows into business logic.",
            buyer_line="Show a concrete 1C defect class, the safe rewrite and the regression test.",
            primary_role="developer",
            roles=["developer", "qa", "architect"],
            minutes=1.0,
            severity=5,
            route="/quality",
            proof="Query Surgeon flags fields from joined tables unless they use ЕстьNULL, ЕСТЬ NULL checks or an intentional inner join.",
            success_signal="A developer sees the unsafe pattern, safe options and expected test before code review.",
            demo_script=[
                "Open Quality and filter to query/standards diagnostics.",
                "Use the LEFT JOIN/NULL case as the first developer spark.",
                "Jump to Testing and show the missing regression expectation.",
            ],
            evidence_routes=[
                _evidence("Quality", "/quality"),
                _evidence("Change Impact", "/change"),
                _evidence("Testing", "/testing"),
            ],
            outputs=["deterministic rule finding", "safe rewrite", "regression test expectation"],
            why_buy_now="This is a visible bug class that generic code chat usually explains only after the damage is known.",
        ),
        _scenario(
            id="change-blast-radius",
            title="A small patch breaks unexpected places",
            pain="Developers cannot see which modules, owners and tests are touched by one BSL change.",
            buyer_line="Turn a patch into impact, hotspots, caveats and test selection before commit.",
            primary_role="developer",
            roles=["developer", "qa", "architect"],
            minutes=1.0,
            severity=4 if _int(risk.get("high_hotspots")) else 3,
            route="/change",
            proof=f"High-risk hotspots: {_int(risk.get('high_hotspots'))}; modules with issues: {_int(kpis.get('modules_with_issues'))}.",
            success_signal="The first risky module produces a review plan instead of another manual investigation.",
            demo_script=[
                "Open Change Impact with a changed module or demo diff.",
                "Show affected modules, risk reasons and caveats.",
                "Open the test matrix directly from impact.",
            ],
            evidence_routes=[
                _evidence("Change Impact", "/change"),
                _evidence("Architecture", "/architecture"),
                _evidence("Testing", "/testing"),
            ],
            outputs=["impact report", "affected tests", "risk caveats"],
            why_buy_now="The team pays this tax on every meaningful change.",
        ),
        _scenario(
            id="architecture-map",
            title="The configuration is a system, not folders",
            pain="Architects see a huge EDT/XML tree but not coupling, ownership, boundaries or risky areas.",
            buyer_line="Open the architecture map and turn legacy size into a navigable system view.",
            primary_role="architect",
            roles=["architect", "developer", "director"],
            minutes=1.0,
            severity=4 if _int(kpis.get("red_areas")) else 3,
            route="/architecture",
            proof=f"Call graph edges: {_int(kpis.get('call_edges'))}; red areas: {_int(kpis.get('red_areas'))}.",
            success_signal="The architect can point to boundaries, hotspots and impact instead of reading folders aloud.",
            demo_script=[
                "Open Architecture and show graph/risk summary.",
                "Connect red areas to release and change routes.",
                "Show where governance and ownership enter the decision.",
            ],
            evidence_routes=[
                _evidence("Architecture", "/architecture"),
                _evidence("Metadata", "/metadata"),
                _evidence("Team Governance", "/team-governance"),
            ],
            outputs=["architecture map", "blast radius", "ownership signals"],
            why_buy_now="A platform or ERP modernization cannot start from a folder tree.",
        ),
        _scenario(
            id="platform-upgrade",
            title="Platform or typical update feels unsafe",
            pain="The hardest 1C risk is often platform/runtime uncertainty, not only BSL code.",
            buyer_line="Put platform version, DBMS, compatibility, tech journal and upgrade caveats into the same plan.",
            primary_role="architect",
            roles=["architect", "operations", "director"],
            minutes=1.0,
            severity=5 if _status(productization) in {"risk", "blocked", "fail"} else 4,
            route="/platform-doctor",
            proof=f"Productization: {_status(productization)} / {_score(productization)}; findings: {_int(product_summary.get('findings'))}.",
            success_signal="The upgrade discussion gets facts, missing facts and rollback work instead of expert anxiety.",
            demo_script=[
                "Open Platform Doctor and point out explicit unknowns.",
                "Open Update War Room for release/update sequence.",
                "Show Extension Safety when borrowed objects or CFE risk matters.",
            ],
            evidence_routes=[
                _evidence("Platform Doctor", "/platform-doctor"),
                _evidence("Update War Room", "/update-war-room"),
                _evidence("Extension Safety", "/extension-safety"),
            ],
            outputs=["platform readiness", "upgrade checklist", "rollback caveats"],
            why_buy_now="The buyer is already afraid of platform updates; the product makes the fear actionable.",
        ),
        _scenario(
            id="extension-risk",
            title="Extension or borrowed object can break the update",
            pain="Extension safety is usually checked late, manually and under release pressure.",
            buyer_line="Separate extension risk from core configuration risk before the update window.",
            primary_role="architect",
            roles=["architect", "developer", "release"],
            minutes=0.75,
            severity=4,
            route="/extension-safety",
            proof="Extension Safety connects CFE inventory, hooks, rights and changed modules to update work.",
            success_signal="The release owner sees which extension concerns are blockers, warnings or caveats.",
            demo_script=[
                "Open Extension Safety with the same config path.",
                "Show extension inventory and borrowed-object caveats.",
                "Route blockers into Update War Room.",
            ],
            evidence_routes=[
                _evidence("Extension Safety", "/extension-safety"),
                _evidence("Update War Room", "/update-war-room"),
                _evidence("Evidence Bundle", "/evidence-bundle"),
            ],
            outputs=["extension inventory", "update blockers", "evidence artifact"],
            why_buy_now="Extensions are where many customers feel vendor lock and upgrade pain most sharply.",
        ),
        _scenario(
            id="rights-rls",
            title="Rights and RLS are too opaque to trust",
            pain="Roles, dangerous rights and RLS are checked by scattered expertise instead of a repeatable matrix.",
            buyer_line="Turn access risk into a role/object matrix with findings and a release gate.",
            primary_role="security",
            roles=["security", "architect", "director"],
            minutes=0.75,
            severity=4,
            route="/rights-rls",
            proof="Rights/RLS maps roles, objects, dangerous permissions, RLS fragments and recommended actions.",
            success_signal="Security can review concrete findings without reading configuration XML by hand.",
            demo_script=[
                "Open Rights/RLS and show the role/object matrix.",
                "Point to dangerous rights and missing source caveats.",
                "Export the result through Evidence Bundle.",
            ],
            evidence_routes=[
                _evidence("Rights/RLS", "/rights-rls"),
                _evidence("Security Posture", "/security"),
                _evidence("Evidence Bundle", "/evidence-bundle"),
            ],
            outputs=["rights matrix", "security findings", "approval artifact"],
            why_buy_now="Access review becomes mandatory as soon as the product enters an enterprise contour.",
        ),
        _scenario(
            id="locks-after-release",
            title="After release the base slows down or locks",
            pain="Runtime incidents are detached from code, platform, owners and tests.",
            buyer_line="Use tech journal events to connect locks/deadlocks/timeouts to module and runbook actions.",
            primary_role="operations",
            roles=["operations", "developer", "architect"],
            minutes=1.0,
            severity=4,
            route="/lock-radar",
            proof="Lock Radar turns TLOCK/TTIMEOUT/TDEADLOCK signals into affected modules, tests and runbook steps.",
            success_signal="Operations stops owning the incident alone; the release and code path are visible.",
            demo_script=[
                "Open Lock Radar with TJ path or demo data.",
                "Show event classes and affected modules.",
                "Open Operations incident report for runbook actions.",
            ],
            evidence_routes=[
                _evidence("Lock Radar", "/lock-radar"),
                _evidence("Operations", "/operations"),
                _evidence("Platform Doctor", "/platform-doctor"),
            ],
            outputs=["lock/deadlock radar", "incident report", "runbook actions"],
            why_buy_now="Performance pain is budget pain; the product ties it back to release work.",
        ),
        _scenario(
            id="vendor-presale-audit",
            title="Vendor needs a paid audit story tomorrow",
            pain="Partners struggle to turn a short scan into a credible commercial proposal.",
            buyer_line="Produce a buyer-safe audit, work packages and a markdown report from the same local evidence.",
            primary_role="vendor",
            roles=["vendor", "director", "architect"],
            minutes=0.75,
            severity=4,
            route="/vendor-portfolio",
            proof=f"Portfolio clients: {_int(vendor_summary.get('clients'), 1)}; work packages: {len(vendor_portfolio.get('work_packages') or [])}.",
            success_signal="The vendor leaves with a pre-sale report, not a vague promise to inspect later.",
            demo_script=[
                "Open Vendor Portfolio and show commercial signals.",
                "Map work packages to Value Packs and Business Case.",
                "Export the buyer artifact through Evidence Bundle.",
            ],
            evidence_routes=[
                _evidence("Vendor Portfolio", "/vendor-portfolio"),
                _evidence("Value Packs", "/value-packs"),
                _evidence("Business Case", "/business-case"),
            ],
            outputs=["pre-sale audit", "work packages", "proposal markdown"],
            why_buy_now="This creates partner revenue before a long implementation starts.",
        ),
        _scenario(
            id="local-enterprise-proof",
            title="We do not want another endless AI subscription",
            pain="Clients fear token rent, cloud code exposure and a tool that disappears when AI credits stop.",
            buyer_line="Show local evidence, productization, SBOM/offline controls and a money map in one path.",
            primary_role="director",
            roles=["director", "security", "cio"],
            minutes=1.0,
            severity=5,
            route="/business-case",
            proof=f"First-year visible value: {_int(business_summary.get('first_year_visible_value'))}; productization score: {_score(productization)}.",
            success_signal="The buyer understands Rentgen as a local product asset with optional AI, not AI rent.",
            demo_script=[
                "Open Business Case and show subscription displacement.",
                "Open Enterprise Trust Center and show local contour, SBOM/offline, rights and procurement proof.",
                "Close through Evidence Bundle hashes.",
            ],
            evidence_routes=[
                _evidence("Business Case", "/business-case"),
                _evidence("Enterprise Trust Center", "/enterprise-trust-center"),
                _evidence("Productization", "/productization"),
                _evidence("Evidence Bundle", "/evidence-bundle"),
            ],
            outputs=["money map", "productization report", "hash manifest"],
            why_buy_now="This is the board-level reason to buy the product instead of another AI chat subscription.",
        ),
    ]


def _role_lenses(scenarios: list[dict[str, Any]]) -> list[dict[str, Any]]:
    roles = [
        ("Developer", "Fix real 1C defects and understand blast radius before commit.", "/quality"),
        ("Architect", "Turn configuration, platform, extensions and rights into governed architecture.", "/architecture"),
        ("Director", "See money, go/no-go and enterprise proof without reading code.", "/business-case"),
        ("QA / Release", "Convert release faith into gates, tests and portable evidence.", "/release-readiness"),
        ("Operations", "Connect runtime pain with platform, code and runbooks.", "/lock-radar"),
        ("Vendor", "Convert scans into paid audits, packages and buyer-safe reports.", "/vendor-portfolio"),
        ("Security", "Check locality, rights, productization and exportable evidence.", "/enterprise-trust-center"),
    ]
    result: list[dict[str, Any]] = []
    for role, outcome, first_route in roles:
        key = role.split(" / ")[0].lower()
        scenario_ids = [
            item["id"]
            for item in scenarios
            if key in {str(value).lower() for value in item["roles"]}
            or item["primary_role"] == key
        ]
        if role == "Security":
            scenario_ids = [
                item["id"]
                for item in scenarios
                if "security" in {str(value).lower() for value in item["roles"]}
            ]
        result.append(
            {
                "role": role,
                "outcome": outcome,
                "first_route": first_route,
                "scenario_ids": scenario_ids[:5],
            }
        )
    return result


def _recommended_path(scenarios: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = sorted(
        scenarios,
        key=lambda item: (
            -_int(item.get("severity")),
            item.get("minutes", 9),
            str(item.get("id")),
        ),
    )
    selected = ranked[:5]
    return [
        {
            "step": index + 1,
            "scenario_id": item["id"],
            "title": item["title"],
            "route": item["route"],
            "role": item["primary_role"],
            "why": item["why_buy_now"],
        }
        for index, item in enumerate(selected)
    ]


def _objection_map() -> list[dict[str, Any]]:
    return [
        {
            "objection": "I do not understand what to open first.",
            "answer": "Start from Scenario Hub, pick the pain, then follow the linked proof route.",
            "scenario_ids": ["release-go-no-go", "left-join-null", "local-enterprise-proof"],
            "proof_route": "/scenario-hub",
        },
        {
            "objection": "This looks like a big expert system, not a product.",
            "answer": "Guided Demo and Scenario Hub compress the product into role journeys and buyer scripts.",
            "scenario_ids": ["local-enterprise-proof", "vendor-presale-audit"],
            "proof_route": "/guided-demo",
        },
        {
            "objection": "Developers already have AI coding assistants.",
            "answer": "Rentgen proves 1C-specific risks around joins, impact, tests, platform and release gates locally.",
            "scenario_ids": ["left-join-null", "change-blast-radius", "platform-upgrade"],
            "proof_route": "/quality",
        },
        {
            "objection": "Architects need platform and update risk, not another linter.",
            "answer": "Platform Doctor, Update War Room, Extension Safety and Architecture are first-class scenarios.",
            "scenario_ids": ["architecture-map", "platform-upgrade", "extension-risk"],
            "proof_route": "/platform-doctor",
        },
        {
            "objection": "Security will block any tool that sends code outside.",
            "answer": "The close path uses Trust Center, local evidence, productization readiness and hashed bundle exports.",
            "scenario_ids": ["rights-rls", "local-enterprise-proof"],
            "proof_route": "/enterprise-trust-center",
        },
    ]


def _exports() -> list[dict[str, str]]:
    return [
        {"title": "Buyer Brief markdown", "filename": "buyer-brief.md", "route": "/"},
        {"title": "Buyer Pulse markdown", "filename": "buyer-pulse.md", "route": "/"},
        {"title": "Buyer Concierge markdown", "filename": "rentgen-buyer-concierge.md", "route": "/buyer-concierge"},
        {"title": "Demo Command Center markdown", "filename": "rentgen-demo-command-center.md", "route": "/demo-command-center"},
        {"title": "Commercial Offer Studio markdown", "filename": "rentgen-commercial-offer-studio.md", "route": "/commercial-offer-studio"},
        {"title": "Pilot Launchpad markdown", "filename": "rentgen-pilot-launchpad.md", "route": "/pilot-launchpad"},
        {"title": "Scenario Hub markdown", "filename": "rentgen-scenario-hub.md", "route": "/scenario-hub"},
        {"title": "Guided Demo markdown", "filename": "rentgen-guided-demo.md", "route": "/guided-demo"},
        {"title": "Business Case markdown", "filename": "rentgen-business-case.md", "route": "/business-case"},
        {"title": "Evidence Bundle manifest", "filename": "evidence-bundle-manifest.json", "route": "/evidence-bundle"},
        {"title": "Enterprise Trust Center", "filename": "rentgen-enterprise-trust-center.md", "route": "/enterprise-trust-center"},
        {"title": "Productization readiness", "filename": "productization-readiness.md", "route": "/productization"},
    ]


def _scenario_room_bridge(
    *,
    buyer_brief: dict[str, Any] | None,
    scenarios: list[dict[str, Any]],
    role_lenses: list[dict[str, Any]],
    recommended_path: list[dict[str, Any]],
) -> dict[str, Any]:
    brief = buyer_brief or {}
    first_recommended = recommended_path[0] if recommended_path else {}
    primary = dict(brief.get("primary_motion") or {})
    scenario_motion = {
        "label": str(first_recommended.get("title") or "Pick buyer pain"),
        "route": str(first_recommended.get("route") or "/scenario-hub"),
        "status": "ready" if recommended_path else "watch",
        "ask": str(first_recommended.get("why") or "Pick one pain, show one proof route and forward the packet."),
        "reason": "Scenario Hub turns the product map into buyer-recognizable pains.",
    }
    if not primary:
        primary = {
            "label": "Pick buyer pain",
            "route": "/scenario-hub",
            "status": "watch",
            "ask": "Choose one scenario and follow the linked proof route.",
            "reason": "Pain-led entry prevents the buyer from scanning the whole product.",
        }

    role_cards = list(brief.get("role_cards") or [])
    if not role_cards:
        role_cards = [
            {
                "role": item["role"].casefold(),
                "title": item["role"],
                "route": item["first_route"],
                "status": "ready",
                "spark": item["outcome"],
                "proof_file": "rentgen-scenario-hub.md",
                "scenario_ids": item["scenario_ids"],
            }
            for item in role_lenses[:5]
        ]

    proof_readiness = list(brief.get("proof_readiness") or [])
    if not proof_readiness:
        proof_readiness = [
            {
                "id": item["scenario_id"],
                "title": item["title"],
                "route": item["route"],
                "status": "ready",
                "signal": item["why"],
                "file": "rentgen-scenario-hub.md",
            }
            for item in recommended_path[:4]
        ]

    meeting_flow = list(brief.get("meeting_flow") or [])
    if not meeting_flow:
        meeting_flow = [
            {"step": 1, "label": "Orient", "route": "/buyer-concierge", "line": "Pick the role in the room."},
            {"step": 2, "label": "Choose", "route": "/scenario-hub", "line": "Let the buyer choose the pain they recognize."},
            {"step": 3, "label": "Prove", "route": "/killer-demo", "line": "Compress the chosen pain into the buyer-ready demo path."},
            {"step": 4, "label": "Forward", "route": "/evidence-bundle", "line": "Forward buyer brief, scenario and proof artifacts."},
        ]
    open_first_path = build_open_first_path(
        existing_path=brief.get("open_first_path"),
        proof_readiness=proof_readiness,
        primary=primary,
        meeting_flow=meeting_flow,
        source="scenario-hub-fallback",
        orient_title="Scenario Hub",
        orient_route="/scenario-hub",
        orient_line="Let the buyer choose the pain they recognize.",
        orient_status=str(primary.get("status") or scenario_motion.get("status") or "watch"),
        prove_line="Compress the chosen pain into the buyer-ready demo path.",
        close_title="Launch Room",
        close_route="/launch-room",
        close_line="Name paid proof or pilot from the selected pain.",
        close_file="launch-room.md",
        close_status=str(primary.get("status") or scenario_motion.get("status") or "watch"),
        verify_line="Forward buyer brief, scenario and proof artifacts.",
    )

    routes = sorted(
        {
            "/scenario-hub",
            str(primary.get("route") or "/scenario-hub"),
            str(scenario_motion["route"]),
            *[str(item.get("route") or "") for item in role_cards],
            *[str(item.get("route") or "") for item in proof_readiness],
            *[str(item.get("route") or "") for item in meeting_flow],
            *[str(item.get("route") or "") for item in open_first_path],
            *[str(item.get("route") or "") for item in scenarios],
        }
        - {""}
    )
    return {
        "status": str(brief.get("purchase_status") or primary.get("status") or "watch"),
        "score": _int(brief.get("score"), 74),
        "source": str(brief.get("source") or "scenario-hub-derived"),
        "room_line": str(
            brief.get("room_line")
            or f"{primary.get('label', 'Pick buyer pain')}: {primary.get('ask', 'Choose a scenario and prove it.')}"
        ),
        "primary_motion": {
            "label": str(primary.get("label") or "Pick buyer pain"),
            "route": str(primary.get("route") or "/scenario-hub"),
            "status": str(primary.get("status") or "watch"),
            "ask": str(primary.get("ask") or "Choose a scenario and prove it."),
            "reason": str(primary.get("reason") or "Pain-led entry prevents menu overload."),
        },
        "scenario_motion": scenario_motion,
        "role_cards": role_cards[:5],
        "proof_readiness": proof_readiness[:4],
        "meeting_flow": meeting_flow[:4],
        "open_first_path": open_first_path[:4],
        "files": ["buyer-brief.md", "buyer-pulse.md", OPEN_FIRST_PATH_FILE, "rentgen-scenario-hub.md", "rentgen-guided-demo.md", "OPEN_FIRST.md"],
        "routes": routes,
        "close_question": "Which pain is strong enough to open the paid proof or pilot?",
    }


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 1C Rentgen Scenario Hub",
        "",
        f"Client: **{report['client']['name']}**",
        f"Status: **{report['decision']['status'].upper()}** / score **{report['decision']['score']}**",
        f"Scenarios: **{report['summary']['scenarios']}**",
        "",
        "## Recommended path",
        "",
    ]
    for item in report["recommended_path"]:
        lines.append(f"- **{item['step']}. {item['title']}** (`{item['route']}`): {item['why']}")
    lines.extend(["", "## Scenarios", ""])
    for item in report["scenarios"]:
        lines.append(
            f"- **{item['title']}** [{item['primary_role']}, severity {item['severity']}] "
            f"`{item['route']}`: {item['buyer_line']}"
        )
    lines.extend(["", "## Role lenses", ""])
    for item in report["role_lenses"]:
        lines.append(f"- **{item['role']}**: {item['outcome']} (`{item['first_route']}`)")
    bridge = report.get("scenario_room_bridge") or {}
    if bridge:
        lines.extend(["", "## Scenario Room Bridge", ""])
        lines.append(f"- Source: **{bridge.get('source', 'n/a')}**; status **{bridge.get('status', 'watch')}** / score **{bridge.get('score', 0)}**")
        lines.append(f"- Room line: {bridge.get('room_line', '')}")
        motion = bridge.get("primary_motion") or {}
        lines.append(f"- Primary motion: **{motion.get('label', 'n/a')}** (`{motion.get('route', '/scenario-hub')}`): {motion.get('ask', '')}")
        scenario_motion = bridge.get("scenario_motion") or {}
        lines.append(f"- Scenario motion: **{scenario_motion.get('label', 'n/a')}** (`{scenario_motion.get('route', '/scenario-hub')}`): {scenario_motion.get('ask', '')}")
        lines.extend(open_first_path_markdown_lines(bridge.get("open_first_path"), default_route="/scenario-hub"))
        for item in bridge.get("role_cards", []):
            lines.append(f"- **{item.get('title', item.get('role', 'role'))}** `{item.get('route', '')}`: {item.get('spark', '')}")
        for item in bridge.get("proof_readiness", []):
            lines.append(f"- Proof **{item.get('title', 'proof')}** `{item.get('route', '')}` -> {item.get('file', '')}: {item.get('signal', '')}")
        for item in bridge.get("meeting_flow", []):
            lines.append(f"- Step {item.get('step', '')} **{item.get('label', 'step')}** `{item.get('route', '')}`: {item.get('line', '')}")
    lines.extend(["", "## Caveats", ""])
    lines.extend(f"- {item}" for item in report["caveats"])
    return "\n".join(lines)


def build_scenario_hub(
    *,
    executive: dict[str, Any],
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
    """Build a pain-led scenario gallery over implemented Rentgen surfaces."""

    scenarios = _scenarios(
        executive=executive,
        business_case=business_case,
        productization=productization,
        value_packs=value_packs,
        vendor_portfolio=vendor_portfolio,
    )
    recommended = _recommended_path(scenarios)
    role_lenses = _role_lenses(scenarios)
    scenario_room_bridge = _scenario_room_bridge(
        buyer_brief=buyer_brief,
        scenarios=scenarios,
        role_lenses=role_lenses,
        recommended_path=recommended,
    )
    score = max(
        0,
        min(
            100,
            round(
                _score(executive) * 0.25
                + _score(guided_demo) * 0.25
                + _score(business_case) * 0.20
                + _score(productization) * 0.15
                + _score(value_packs) * 0.10
                + _score(vendor_portfolio) * 0.05
            ),
        ),
    )
    statuses = {
        _status(executive),
        _status(guided_demo),
        _status(business_case),
        _status(productization),
        _status(vendor_portfolio),
    }
    status = "risk" if statuses & {"blocked", "critical", "fail"} else "ready" if score >= 82 else "watch"
    proof_routes = sorted(
        {
            route["to"]
            for scenario in scenarios
            for route in scenario["evidence_routes"]
            if route.get("to")
        }
        | {item["route"] for item in scenarios if item.get("route")}
        | set(scenario_room_bridge["routes"])
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
                "Scenario Hub is ready: buyer pains are mapped to role routes, proof artifacts and closing exports."
                if status == "ready"
                else "Scenario Hub is usable, but show caveats and productization gaps while walking buyer pains."
            ),
        },
        "summary": {
            "scenarios": len(scenarios),
            "killer_scenarios": sum(1 for item in scenarios if _int(item.get("severity")) >= 5),
            "roles": len(role_lenses),
            "total_minutes": round(sum(float(item["minutes"]) for item in scenarios), 1),
            "proof_routes": len(proof_routes),
            "value_packs": len(value_packs.get("packs") or []),
            "scenario_room_roles": len(scenario_room_bridge["role_cards"]),
            "scenario_room_proofs": len(scenario_room_bridge["proof_readiness"]),
            "scenario_room_steps": len(scenario_room_bridge["meeting_flow"]),
            "scenario_room_open_first": len(scenario_room_bridge["open_first_path"]),
        },
        "scenarios": scenarios,
        "scenario_room_bridge": scenario_room_bridge,
        "role_lenses": role_lenses,
        "recommended_path": recommended,
        "objection_map": _objection_map(),
        "exports": _exports(),
        "proof_routes": proof_routes,
        "source_signals": {
            "executive_status": _status(executive),
            "executive_score": _score(executive),
            "guided_demo_status": _status(guided_demo),
            "guided_demo_score": _score(guided_demo),
            "business_case_score": _score(business_case),
            "productization_status": _status(productization),
            "productization_score": _score(productization),
            "value_packs": len(value_packs.get("packs") or []),
            "vendor_work_packages": len(vendor_portfolio.get("work_packages") or []),
        },
        "caveats": [
            "Scenario Hub v1 is a navigation and sales-proof layer over implemented local reports; it does not replace acceptance testing.",
            "Severity ranks buyer urgency, not an audited production incident probability.",
            "Routes with missing local source data must keep their own caveats visible during the demo.",
        ],
        "download_name": "rentgen-scenario-hub.md",
    }
    report["markdown"] = _markdown(report)
    return report
