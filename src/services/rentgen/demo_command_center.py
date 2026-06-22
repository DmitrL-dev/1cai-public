"""Live demo command center for 1C Rentgen buyer meetings."""

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
    return str(
        (report.get("decision") or {}).get("status") or report.get("status") or default
    )


def _stage(
    *,
    id: str,
    title: str,
    role: str,
    route: str,
    minutes: float,
    cue: str,
    talk_track: str,
    proof: str,
    expected_reaction: str,
    next_click: str,
    fallback_line: str,
    evidence_asset: str,
) -> dict[str, Any]:
    return {
        "id": id,
        "title": title,
        "role": role,
        "route": route,
        "minutes": minutes,
        "cue": cue,
        "talk_track": talk_track,
        "proof": proof,
        "expected_reaction": expected_reaction,
        "next_click": next_click,
        "fallback_line": fallback_line,
        "evidence_asset": evidence_asset,
    }


def _scenario_title(
    scenario_hub: dict[str, Any], scenario_id: str, default: str
) -> str:
    for item in scenario_hub.get("scenarios", []):
        if item.get("id") == scenario_id:
            return str(item.get("title") or default)
    return default


def _stages(
    *,
    executive: dict[str, Any],
    scenario_hub: dict[str, Any],
    guided_demo: dict[str, Any],
    pilot_launchpad: dict[str, Any],
    business_case: dict[str, Any],
    productization: dict[str, Any],
) -> list[dict[str, Any]]:
    business_summary = business_case.get("summary") or {}
    product_summary = productization.get("summary") or {}
    return [
        _stage(
            id="orientation",
            title="Orient the room in 30 seconds",
            role="all",
            route="/buyer-concierge",
            minutes=0.5,
            cue="Start from the cockpit, not from the menu.",
            talk_track="This is a local 1C evidence system: risks, platform, tests, business case and exportable proof stay connected.",
            proof=f"Executive status: {_status(executive)} / {_score(executive)}.",
            expected_reaction="The buyer understands this is not another code chat.",
            next_click="Open Buyer Concierge or Scenario Hub.",
            fallback_line="If live data is thin, say that missing facts are shown as caveats rather than fabricated green checks.",
            evidence_asset="Executive cockpit",
        ),
        _stage(
            id="pain-pick",
            title="Let the buyer pick a pain",
            role="all",
            route="/scenario-hub",
            minutes=1.0,
            cue="Ask which pain feels closest: release, LEFT JOIN, platform update, rights, locks or vendor audit.",
            talk_track="Every scenario is a route from pain to proof, not a list of disconnected features.",
            proof=f"Scenario Hub: {len(scenario_hub.get('scenarios') or [])} scenarios, {len(scenario_hub.get('role_lenses') or [])} role lenses.",
            expected_reaction="The buyer chooses their own entry point and stops scanning the whole product at once.",
            next_click="Open the selected proof route or continue with developer spark.",
            fallback_line="If the buyer is silent, pick LEFT JOIN for developers or local enterprise proof for directors.",
            evidence_asset="Scenario Hub markdown",
        ),
        _stage(
            id="developer-spark",
            title="Show the developer spark",
            role="developer",
            route="/quality",
            minutes=1.0,
            cue="Use a concrete 1C query defect before talking about architecture.",
            talk_track="Fields from joined tables need an explicit NULL story: ЕстьNULL, ЕСТЬ NULL check or intentional inner join.",
            proof=_scenario_title(
                scenario_hub, "left-join-null", "LEFT JOIN field without NULL guard"
            ),
            expected_reaction="Developer sees a real defect class and a testable fix path.",
            next_click="Open Change Impact or Testing.",
            fallback_line="If there is no finding in current data, show the deterministic rule and explain when it triggers.",
            evidence_asset="Quality / Query Surgeon finding",
        ),
        _stage(
            id="architecture-platform",
            title="Earn architect trust",
            role="architect",
            route="/platform-doctor",
            minutes=1.0,
            cue="Move from code finding to platform/update risk.",
            talk_track="The product treats platform, compatibility, extensions and runtime evidence as first-class risk, not as afterthoughts.",
            proof=_scenario_title(
                scenario_hub,
                "platform-upgrade",
                "Platform or typical update feels unsafe",
            ),
            expected_reaction="Architect sees 1C topology and platform risk in the same conversation.",
            next_click="Open Architecture or Update War Room.",
            fallback_line="If platform facts are missing, emphasize that unknown facts stay visible as warnings.",
            evidence_asset="Platform Doctor report",
        ),
        _stage(
            id="director-value",
            title="Translate proof into money",
            role="director",
            route="/business-case",
            minutes=1.0,
            cue="Switch from features to budget and decision.",
            talk_track="The product is a local asset that reduces recurring AI rent, manual review effort and release risk exposure.",
            proof=f"First-year visible value: {_int(business_summary.get('first_year_visible_value'))}.",
            expected_reaction="Director can explain why this is a product purchase, not another AI subscription.",
            next_click="Open Commercial Offer Studio or Pilot Launchpad.",
            fallback_line="If finance challenges assumptions, show that every assumption is explicit and adjustable.",
            evidence_asset="Business Case markdown",
        ),
        _stage(
            id="enterprise-trust",
            title="Pre-answer security and enterprise trust",
            role="security",
            route="/enterprise-trust-center",
            minutes=0.75,
            cue="Do this before security asks about locality, SBOM or installability.",
            talk_track="The demo is honest about enterprise trust: local contour, SBOM/offline controls, rights, platform, findings and caveats are visible.",
            proof=f"Productization status: {_status(productization)} / {_score(productization)}; findings: {_int(product_summary.get('findings'))}.",
            expected_reaction="Security sees the local-contour story and known hardening work.",
            next_click="Open Evidence Bundle.",
            fallback_line="If production readiness is challenged, say this is exactly why Productization is a visible gate.",
            evidence_asset="Productization readiness",
        ),
        _stage(
            id="pilot-close",
            title="Convert interest into pilot",
            role="director",
            route="/pilot-launchpad",
            minutes=1.0,
            cue="Do not end with applause; end with a pilot offer and acceptance check.",
            talk_track="Pick 24-hour proof, 7-day release pilot, 30-day local license pilot or vendor rollout.",
            proof=f"Pilot offers: {(pilot_launchpad.get('summary') or {}).get('offers', 0)}; acceptance checks: {(pilot_launchpad.get('summary') or {}).get('acceptance_checks', 0)}.",
            expected_reaction="Buyer has a next step with owner, date and acceptance criteria.",
            next_click="Open Evidence Bundle or download Pilot Launchpad markdown.",
            fallback_line="If the buyer is not ready to pick a pilot, ask which acceptance check they would trust first.",
            evidence_asset="Pilot Launchpad markdown",
        ),
        _stage(
            id="artifact-close",
            title="Close with proof, not screenshots",
            role="all",
            route="/evidence-bundle",
            minutes=0.75,
            cue="End by exporting artifacts with hashes.",
            talk_track="The buyer leaves with JSON/Markdown artifacts and SHA-256 manifest they can forward.",
            proof="Evidence Bundle contains the demo, scenario, pilot and business artifacts.",
            expected_reaction="The meeting creates a reusable approval package.",
            next_click="Download markdown/manifest.",
            fallback_line="If export is not needed now, show the manifest and explain what would be attached to approval.",
            evidence_asset="Evidence Bundle manifest",
        ),
    ]


def _role_pivots() -> list[dict[str, str]]:
    return [
        {
            "role": "Developer",
            "opener": "Let me show one defect class you can fix before review.",
            "route": "/quality",
            "prove_with": "LEFT JOIN field without NULL guard, Change Impact and Testing.",
            "if_time_short": "Show Quality first, then skip to Testing.",
            "close_question": "Would this have caught a recent review or regression?",
        },
        {
            "role": "Architect",
            "opener": "Let us look at system shape, platform and update risk.",
            "route": "/platform-doctor",
            "prove_with": "Architecture, Platform Doctor, Extension Safety and Update War Room.",
            "if_time_short": "Show Platform Doctor and one architecture risk.",
            "close_question": "Which upgrade or extension decision would you pilot first?",
        },
        {
            "role": "Director",
            "opener": "I will connect local evidence to budget and go/no-go.",
            "route": "/business-case",
            "prove_with": "Business Case, Pilot Launchpad and Evidence Bundle.",
            "if_time_short": "Show Business Case and Pilot Launchpad only.",
            "close_question": "Is the 24-hour proof or 7-day release pilot the right first step?",
        },
        {
            "role": "Security",
            "opener": "Before we talk adoption, here is the local-contour and artifact story.",
            "route": "/enterprise-trust-center",
            "prove_with": "Enterprise Trust Center, Productization, Evidence Bundle, Rights/RLS and offline readiness.",
            "if_time_short": "Show Trust Center and hashed Evidence Bundle.",
            "close_question": "What artifact do you need before approving a pilot install?",
        },
        {
            "role": "Vendor",
            "opener": "This can become a paid audit and scoped work package.",
            "route": "/vendor-portfolio",
            "prove_with": "Vendor Portfolio, Value Packs, Pilot Launchpad and Business Case.",
            "if_time_short": "Show Vendor Portfolio and the 30-day rollout offer.",
            "close_question": "Which client should get the first buyer-safe audit report?",
        },
    ]


def _live_checklist() -> dict[str, list[str]]:
    return {
        "before_demo": [
            "Open Demo Command Center, Scenario Hub, Pilot Launchpad and Evidence Bundle in tabs.",
            "Confirm config path or local store is available; if not, state caveats upfront.",
            "Pick one primary buyer role and one backup role.",
            "Prepare the first export filename and buyer email recipient.",
        ],
        "during_demo": [
            "Start from the buyer pain, not from all modules.",
            "Keep every claim tied to a route and artifact.",
            "Name caveats before the buyer finds them.",
            "Ask for the first pilot acceptance check before ending.",
        ],
        "close": [
            "Export Pilot Launchpad markdown.",
            "Export Evidence Bundle manifest.",
            "Assign owner, date and pilot route.",
            "Send the buyer one artifact pack, not a screenshot dump.",
        ],
    }


def _objections(productization: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "question": "Is this just another AI assistant?",
            "answer": "No. The live demo uses local graph, rules, reports, gates and hashes; AI remains optional.",
            "route": "/business-case",
        },
        {
            "question": "What if our data is incomplete?",
            "answer": "Missing facts remain caveats. The demo should show unknowns instead of pretending safety.",
            "route": "/scenario-hub",
        },
        {
            "question": "Can security approve this?",
            "answer": f"Productization is visible as {_status(productization)} / {_score(productization)} with SBOM/offline controls and findings.",
            "route": "/enterprise-trust-center",
        },
        {
            "question": "What happens after the demo?",
            "answer": "Pilot Launchpad turns interest into 24-hour proof, 7-day release pilot or 30-day local rollout.",
            "route": "/pilot-launchpad",
        },
        {
            "question": "Can a vendor sell this repeatedly?",
            "answer": "Vendor Portfolio and Value Packs turn audit signals into buyer-safe reports and work packages.",
            "route": "/vendor-portfolio",
        },
    ]


def _proof_assets() -> list[dict[str, str]]:
    return [
        {
            "title": "Scenario Hub",
            "route": "/scenario-hub",
            "why": "pain-led entry point",
        },
        {
            "title": "Buyer Concierge",
            "route": "/buyer-concierge",
            "why": "first-click orientation",
        },
        {"title": "Guided Demo", "route": "/guided-demo", "why": "role proof route"},
        {
            "title": "Pilot Launchpad",
            "route": "/pilot-launchpad",
            "why": "pilot offers and acceptance",
        },
        {
            "title": "Business Case",
            "route": "/business-case",
            "why": "money and objections",
        },
        {
            "title": "Commercial Offer Studio",
            "route": "/commercial-offer-studio",
            "why": "buyable offer",
        },
        {
            "title": "Enterprise Trust Center",
            "route": "/enterprise-trust-center",
            "why": "enterprise trust",
        },
        {
            "title": "Productization",
            "route": "/productization",
            "why": "SBOM/offline controls",
        },
        {
            "title": "Evidence Bundle",
            "route": "/evidence-bundle",
            "why": "portable proof with hashes",
        },
    ]


def _recovery_cards() -> list[dict[str, str]]:
    return [
        {
            "signal": "No real configuration path",
            "response": "Use the local store/demo data and explicitly say the first pilot action is configuration intake.",
            "route": "/configurations",
        },
        {
            "signal": "Buyer jumps to security",
            "response": "Skip feature tour and open Trust Center, Rights/RLS and Evidence Bundle.",
            "route": "/enterprise-trust-center",
        },
        {
            "signal": "Developer challenges generic value",
            "response": "Open the LEFT JOIN/NULL scenario and tie it to test expectations.",
            "route": "/quality",
        },
        {
            "signal": "Director asks price before proof",
            "response": "Open Business Case, then Pilot Launchpad. Keep assumptions editable.",
            "route": "/business-case",
        },
        {
            "signal": "Demo time is cut to five minutes",
            "response": "Use Scenario Hub -> Quality or Platform Doctor -> Business Case -> Pilot Launchpad.",
            "route": "/demo-command-center",
        },
    ]


def _exports() -> list[dict[str, str]]:
    return [
        {"title": "Buyer Brief markdown", "filename": "buyer-brief.md", "route": "/"},
        {"title": "Buyer Pulse markdown", "filename": "buyer-pulse.md", "route": "/"},
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
            "title": "Pilot Launchpad markdown",
            "filename": "rentgen-pilot-launchpad.md",
            "route": "/pilot-launchpad",
        },
        {
            "title": "Evidence Bundle manifest",
            "filename": "evidence-bundle-manifest.json",
            "route": "/evidence-bundle",
        },
    ]


def _demo_room_bridge(
    *,
    buyer_brief: dict[str, Any] | None,
    stages: list[dict[str, Any]],
    role_pivots: list[dict[str, str]],
    proof_assets: list[dict[str, str]],
) -> dict[str, Any]:
    brief = buyer_brief or {}
    opening_stage = stages[0] if stages else {}
    primary = dict(brief.get("primary_motion") or {})
    presenter_opening = {
        "label": str(opening_stage.get("title") or "Orient the room"),
        "route": str(opening_stage.get("route") or "/buyer-concierge"),
        "status": "ready",
        "ask": str(
            opening_stage.get("talk_track")
            or "Start from role, pain and one proof path."
        ),
        "reason": str(
            opening_stage.get("expected_reaction")
            or "Buyer should understand the product before seeing the full menu."
        ),
        "minutes": float(opening_stage.get("minutes") or 0.5),
    }
    if not primary:
        primary = {
            "label": "Run buyer-safe demo",
            "route": "/demo-command-center",
            "status": "watch",
            "ask": "Orient the room, prove one pain, then ask for the next paid step.",
            "reason": "Presenter has stages, pivots, recovery cards and proof files.",
        }

    role_cards = list(brief.get("role_cards") or [])
    if not role_cards:
        role_cards = [
            {
                "role": item["role"].casefold(),
                "title": item["role"],
                "route": item["route"],
                "status": "ready",
                "spark": item["opener"],
                "proof_file": "rentgen-demo-command-center.md",
                "close_question": item["close_question"],
            }
            for item in role_pivots[:5]
        ]

    proof_readiness = list(brief.get("proof_readiness") or [])
    if not proof_readiness:
        proof_readiness = [
            {
                "id": str(item.get("title") or "proof").lower().replace(" ", "-"),
                "title": str(item.get("title") or "Proof asset"),
                "route": str(item.get("route") or "/demo-command-center"),
                "status": "ready",
                "signal": str(
                    item.get("why") or "Use this route during the live demo."
                ),
                "file": "rentgen-demo-command-center.md"
                if item.get("route") == "/demo-command-center"
                else "OPEN_FIRST.md",
            }
            for item in proof_assets[:4]
        ]

    meeting_flow = list(brief.get("meeting_flow") or [])
    if not meeting_flow:
        meeting_flow = [
            {
                "step": 1,
                "label": "Orient",
                "route": "/buyer-concierge",
                "line": "Pick the role and pain before showing the menu.",
            },
            {
                "step": 2,
                "label": "Prove",
                "route": "/killer-demo",
                "line": "Show one buyer-ready proof and objection answer.",
            },
            {
                "step": 3,
                "label": "Ask",
                "route": "/pilot-launchpad",
                "line": "Select the paid proof or pilot with owner and date.",
            },
            {
                "step": 4,
                "label": "Forward",
                "route": "/evidence-bundle",
                "line": "Send buyer brief, demo script and hash-verifiable proof files.",
            },
        ]
    open_first_path = build_open_first_path(
        existing_path=brief.get("open_first_path"),
        proof_readiness=proof_readiness,
        primary=primary,
        meeting_flow=meeting_flow,
        source="demo-command-center-fallback",
        orient_title="Demo Command Center",
        orient_route="/demo-command-center",
        orient_line="Orient the room, prove one pain, then ask for the next paid step.",
        orient_status=str(primary.get("status") or "watch"),
        prove_line="Show one buyer-ready proof and objection answer.",
        close_title="Pilot Launchpad",
        close_route="/pilot-launchpad",
        close_line="Select the paid proof or pilot with owner and date.",
        close_file="rentgen-pilot-launchpad.md",
        close_status=str(primary.get("status") or "watch"),
        verify_line="Send buyer brief, demo script and hash-verifiable proof files.",
    )

    routes = sorted(
        {
            "/demo-command-center",
            str(primary.get("route") or "/demo-command-center"),
            str(presenter_opening["route"]),
            *[str(item.get("route") or "") for item in role_cards],
            *[str(item.get("route") or "") for item in proof_readiness],
            *[str(item.get("route") or "") for item in meeting_flow],
            *[str(item.get("route") or "") for item in open_first_path],
        }
        - {""}
    )
    return {
        "status": str(brief.get("purchase_status") or primary.get("status") or "watch"),
        "score": _int(brief.get("score"), 74),
        "source": str(brief.get("source") or "demo-command-center-derived"),
        "room_line": str(
            brief.get("room_line")
            or f"{primary.get('label', 'Run buyer-safe demo')}: {primary.get('ask', 'Prove one pain and ask for the paid next step.')}"
        ),
        "primary_motion": {
            "label": str(primary.get("label") or "Run buyer-safe demo"),
            "route": str(primary.get("route") or "/demo-command-center"),
            "status": str(primary.get("status") or "watch"),
            "ask": str(
                primary.get("ask") or "Prove one pain and ask for the paid next step."
            ),
            "reason": str(
                primary.get("reason") or "Presenter has a staged proof path."
            ),
        },
        "presenter_opening": presenter_opening,
        "role_cards": role_cards[:5],
        "proof_readiness": proof_readiness[:4],
        "meeting_flow": meeting_flow[:4],
        "open_first_path": open_first_path[:4],
        "files": [
            "buyer-brief.md",
            "buyer-pulse.md",
            OPEN_FIRST_PATH_FILE,
            "rentgen-demo-command-center.md",
            "rentgen-killer-demo-path.md",
            "OPEN_FIRST.md",
        ],
        "routes": routes,
        "close_question": "Which proof or paid pilot should we commit to before leaving the meeting?",
    }


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 1C Rentgen Demo Command Center",
        "",
        f"Client: **{report['client']['name']}**",
        f"Status: **{report['decision']['status'].upper()}** / score **{report['decision']['score']}**",
        f"Live route: **{report['summary']['total_minutes']} minutes**",
        "",
        "## Live stages",
        "",
    ]
    for item in report["live_stages"]:
        lines.append(
            f"- **{item['title']}** ({item['role']}, {item['minutes']} min, `{item['route']}`): {item['talk_track']}"
        )
    lines.extend(["", "## Role pivots", ""])
    for item in report["role_pivots"]:
        lines.append(
            f"- **{item['role']}** (`{item['route']}`): {item['opener']} Close: {item['close_question']}"
        )
    lines.extend(["", "## Close checklist", ""])
    for item in report["live_checklist"]["close"]:
        lines.append(f"- {item}")
    bridge = report.get("demo_room_bridge") or {}
    if bridge:
        lines.extend(["", "## Demo Room Bridge", ""])
        lines.append(
            f"- Source: **{bridge.get('source', 'n/a')}**; status **{bridge.get('status', 'watch')}** / score **{bridge.get('score', 0)}**"
        )
        lines.append(f"- Room line: {bridge.get('room_line', '')}")
        motion = bridge.get("primary_motion") or {}
        lines.append(
            f"- Primary motion: **{motion.get('label', 'n/a')}** (`{motion.get('route', '/demo-command-center')}`): {motion.get('ask', '')}"
        )
        opening = bridge.get("presenter_opening") or {}
        lines.append(
            f"- Presenter opening: **{opening.get('label', 'n/a')}** (`{opening.get('route', '/buyer-concierge')}`): {opening.get('ask', '')}"
        )
        lines.extend(
            open_first_path_markdown_lines(
                bridge.get("open_first_path"), default_route="/demo-command-center"
            )
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


def build_demo_command_center(
    *,
    executive: dict[str, Any],
    scenario_hub: dict[str, Any],
    guided_demo: dict[str, Any],
    pilot_launchpad: dict[str, Any],
    business_case: dict[str, Any],
    productization: dict[str, Any],
    vendor_portfolio: dict[str, Any],
    buyer_brief: dict[str, Any] | None = None,
    client_name: str = "Demo client",
    config_path: str | None = None,
    target_platform_version: str | None = None,
) -> dict[str, Any]:
    """Build the live presenter cockpit for a buyer demo."""

    stages = _stages(
        executive=executive,
        scenario_hub=scenario_hub,
        guided_demo=guided_demo,
        pilot_launchpad=pilot_launchpad,
        business_case=business_case,
        productization=productization,
    )
    score = max(
        0,
        min(
            100,
            round(
                _score(scenario_hub) * 0.25
                + _score(guided_demo) * 0.20
                + _score(pilot_launchpad) * 0.20
                + _score(business_case) * 0.20
                + _score(productization) * 0.10
                + _score(vendor_portfolio) * 0.05
            ),
        ),
    )
    statuses = {
        _status(executive),
        _status(scenario_hub),
        _status(guided_demo),
        _status(pilot_launchpad),
        _status(business_case),
        _status(productization),
    }
    status = (
        "risk"
        if statuses & {"blocked", "critical", "fail"}
        else "ready"
        if score >= 82
        else "watch"
    )
    role_pivots = _role_pivots()
    proof_assets = _proof_assets()
    demo_room_bridge = _demo_room_bridge(
        buyer_brief=buyer_brief,
        stages=stages,
        role_pivots=role_pivots,
        proof_assets=proof_assets,
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
                "Demo Command Center is ready: live stages, role pivots, recovery cards and close artifacts are connected."
                if status == "ready"
                else "Demo Command Center is usable, but presenter should name caveats and productization gaps during the meeting."
            ),
        },
        "summary": {
            "stages": len(stages),
            "role_pivots": len(role_pivots),
            "proof_assets": len(proof_assets),
            "total_minutes": round(sum(float(item["minutes"]) for item in stages), 1),
            "objections": len(_objections(productization)),
            "recovery_cards": len(_recovery_cards()),
            "demo_room_roles": len(demo_room_bridge["role_cards"]),
            "demo_room_proofs": len(demo_room_bridge["proof_readiness"]),
            "demo_room_steps": len(demo_room_bridge["meeting_flow"]),
            "demo_room_open_first": len(demo_room_bridge["open_first_path"]),
        },
        "live_stages": stages,
        "demo_room_bridge": demo_room_bridge,
        "role_pivots": role_pivots,
        "live_checklist": _live_checklist(),
        "objections": _objections(productization),
        "proof_assets": proof_assets,
        "recovery_cards": _recovery_cards(),
        "exports": _exports(),
        "source_signals": {
            "scenario_hub_status": _status(scenario_hub),
            "guided_demo_status": _status(guided_demo),
            "pilot_launchpad_status": _status(pilot_launchpad),
            "business_case_score": _score(business_case),
            "productization_status": _status(productization),
            "vendor_work_packages": len(vendor_portfolio.get("work_packages") or []),
        },
        "caveats": [
            "Demo Command Center v1 is a presenter workflow over implemented reports; it is not a meeting recorder.",
            "Presenter lines should be adjusted to the buyer's real configuration and procurement process.",
            "If live source coverage is incomplete, show caveats before making adoption claims.",
        ],
        "download_name": "rentgen-demo-command-center.md",
    }
    report["markdown"] = _markdown(report)
    return report
