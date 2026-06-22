"""Guided buyer demo and deal-room route for 1C Rentgen."""

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


def _decision(report: dict[str, Any] | None) -> dict[str, Any]:
    return (report or {}).get("decision") or {}


def _status(report: dict[str, Any] | None, default: str = "watch") -> str:
    direct = (report or {}).get("status")
    return str(_decision(report).get("status") or direct or default)


def _score(report: dict[str, Any] | None, default: int = 0) -> int:
    if report and "score" in report:
        return _int(report.get("score"), default)
    return _int(_decision(report).get("score"), default)


def _money(value: Any, currency: str) -> str:
    return f"{_int(value):,}".replace(",", " ") + f" {currency}"


def _route(path: str) -> str:
    return path


def _guided_steps(
    *,
    executive: dict[str, Any],
    business_case: dict[str, Any],
    productization: dict[str, Any],
    vendor_portfolio: dict[str, Any],
) -> list[dict[str, Any]]:
    kpis = executive.get("kpis") or {}
    risk = executive.get("risk_summary") or {}
    business_summary = business_case.get("summary") or {}
    assumptions = business_case.get("assumptions") or {"currency": "RUB"}
    product_summary = productization.get("summary") or {}
    vendor_portfolio_summary = vendor_portfolio.get("portfolio") or {}
    currency = str(assumptions.get("currency") or "RUB")
    return [
        {
            "id": "orientation",
            "title": "Open the product as a buyer cockpit",
            "role": "all",
            "minutes": 0.5,
            "route": _route("/"),
            "proof": "One screen shows score, top risks, role cards and the fastest next actions.",
            "success_signal": f"Executive decision: {_status(executive)} / {_score(executive)}.",
            "buyer_question": "Can I understand in 30 seconds what this product does?",
            "talk_track": "Start from the role, not the menu. The same evidence is shown differently for developer, architect, director, QA, ops and vendor.",
        },
        {
            "id": "developer-proof",
            "title": "Prove value on one risky code change",
            "role": "developer",
            "minutes": 1.0,
            "route": _route("/change"),
            "proof": "Change Impact links changed modules to risk, affected tests and caveats before commit.",
            "success_signal": f"High-risk hotspots: {_int(risk.get('high_hotspots'))}; modules with issues: {_int(kpis.get('modules_with_issues'))}.",
            "buyer_question": "Will this save a developer from a real broken release?",
            "talk_track": "Use the LEFT JOIN/NULL guard story: deterministic rules find the bug class without requiring cloud AI.",
        },
        {
            "id": "query-surgeon",
            "title": "Show a concrete 1C query defect, not a generic linter",
            "role": "developer",
            "minutes": 1.0,
            "route": _route("/quality"),
            "proof": "Fields from joined tables are checked for ЕстьNULL/ЕСТЬ NULL handling or a safe inner join decision.",
            "success_signal": "The report names the rule, the unsafe pattern, the safe rewrite and the expected behavioral test.",
            "buyer_question": "Is the product deep enough for 1C-specific code pain?",
            "talk_track": "This is where developers get the spark: not a vague score, but a fixable defect and a regression test.",
        },
        {
            "id": "architecture-proof",
            "title": "Turn configuration complexity into a system map",
            "role": "architect",
            "minutes": 1.0,
            "route": _route("/architecture"),
            "proof": "Graph, metadata, modules, ownership and blast radius expose why a small change can be dangerous.",
            "success_signal": f"Call graph edges: {_int(kpis.get('call_edges'))}; red areas: {_int(kpis.get('red_areas'))}.",
            "buyer_question": "Can an architect trust the product beyond a source-code folder scan?",
            "talk_track": "Show that the system is about 1C configuration topology, not just BSL text.",
        },
        {
            "id": "platform-proof",
            "title": "Put platform upgrade risk in the same conversation",
            "role": "architect / operations",
            "minutes": 1.0,
            "route": _route("/platform-doctor"),
            "proof": "Platform Doctor covers version, compatibility, DBMS, tech journal, OpenMetrics and upgrade caveats.",
            "success_signal": f"Productization readiness: {_status(productization)} / {_score(productization)}; deliverables: {_int(product_summary.get('deliverables'))}.",
            "buyer_question": "Will this help with the part of 1C that usually hurts most: platform and runtime risk?",
            "talk_track": "The answer is not 'ask AI'. The answer is a local checklist with facts, missing facts and explicit caveats.",
        },
        {
            "id": "director-value",
            "title": "Translate the technical story into money and decision",
            "role": "director",
            "minutes": 1.0,
            "route": _route("/business-case"),
            "proof": "Business Case connects recurring AI spend, review effort, release delays and incident exposure.",
            "success_signal": f"First-year visible value: {_money(business_summary.get('first_year_visible_value'), currency)}.",
            "buyer_question": "Why should we buy this product instead of another AI subscription?",
            "talk_track": "This is the local asset argument: useful evidence remains even when external AI credits are zero.",
        },
        {
            "id": "vendor-pack",
            "title": "Make the same demo sellable for a vendor or franchisee",
            "role": "vendor",
            "minutes": 0.5,
            "route": _route("/vendor-portfolio"),
            "proof": "Vendor Portfolio turns audit signals into work packages, opportunities and client-facing markdown.",
            "success_signal": f"Portfolio clients: {_int(vendor_portfolio_summary.get('clients'), 1)}; work packages: {len(vendor_portfolio.get('work_packages') or [])}.",
            "buyer_question": "Can a partner use this to sell audits and modernization work tomorrow?",
            "talk_track": "The product is not only an internal cockpit; it is a proposal factory with evidence.",
        },
        {
            "id": "evidence-close",
            "title": "Close with portable evidence and enterprise delivery",
            "role": "director / security",
            "minutes": 0.5,
            "route": _route("/evidence-bundle"),
            "proof": "Evidence Bundle exports JSON/Markdown artifacts with SHA-256 hashes for approval and audit.",
            "success_signal": "The buyer leaves with artifacts, not screenshots or promises.",
            "buyer_question": "Can we pass this to security, finance and the release board?",
            "talk_track": "Finish by showing the export path and then Productization/SBOM/offline bundle for enterprise trust.",
        },
        {
            "id": "productization-close",
            "title": "Show that this can become an enterprise product, not a demo script",
            "role": "CIO / security",
            "minutes": 0.5,
            "route": _route("/enterprise-trust-center"),
            "proof": "Enterprise Trust Center connects local contour, SBOM, offline manifest, rights, platform and procurement proof.",
            "success_signal": f"Release decision: {productization.get('release_decision', 'unknown')}; findings: {_int(product_summary.get('findings'))}.",
            "buyer_question": "Can we install and govern this in our contour?",
            "talk_track": "Be honest about findings; the point is that enterprise trust gaps are visible and packaged.",
        },
        {
            "id": "productization-deep-dive",
            "title": "Open SBOM and offline delivery controls as the drill-down",
            "role": "security",
            "minutes": 0.25,
            "route": _route("/productization"),
            "proof": "Productization Console exposes readiness, SBOM, offline manifest, archive and verification paths.",
            "success_signal": f"Release decision: {productization.get('release_decision', 'unknown')}; findings: {_int(product_summary.get('findings'))}.",
            "buyer_question": "Where are the concrete SBOM/offline controls?",
            "talk_track": "Use Trust Center as the answer map, then open Productization when the buyer wants artifact-level detail.",
        },
    ]


def _role_paths() -> list[dict[str, Any]]:
    return [
        {
            "role": "Developer",
            "headline": "Fix a real 1C risk before commit.",
            "steps": [
                {
                    "label": "Change Impact",
                    "to": "/change",
                    "proof": "impact, risk, affected tests",
                },
                {
                    "label": "Quality / Query Surgeon",
                    "to": "/quality",
                    "proof": "LEFT JOIN fields, NULL guards, deterministic rule",
                },
                {
                    "label": "Testing",
                    "to": "/testing",
                    "proof": "exact/planned/gap test matrix",
                },
            ],
            "buying_trigger": "The first real module gets a defect, impact path and test expectation in one route.",
        },
        {
            "role": "Architect",
            "headline": "See configuration topology, upgrade impact and security boundaries.",
            "steps": [
                {
                    "label": "Architecture",
                    "to": "/architecture",
                    "proof": "graph and blast radius",
                },
                {
                    "label": "Update War Room",
                    "to": "/update-war-room",
                    "proof": "platform, extension, rollback and evidence plan",
                },
                {
                    "label": "Rights/RLS",
                    "to": "/rights-rls",
                    "proof": "roles, rights, dangerous permissions and caveats",
                },
            ],
            "buying_trigger": "An upgrade discussion becomes evidence-backed instead of expert-memory backed.",
        },
        {
            "role": "Director",
            "headline": "Turn local technical evidence into a go/no-go and a money map.",
            "steps": [
                {
                    "label": "Business Case",
                    "to": "/business-case",
                    "proof": "visible value and objections",
                },
                {
                    "label": "Release Readiness",
                    "to": "/release-readiness",
                    "proof": "decision, gates and residual risk",
                },
                {
                    "label": "Evidence Bundle",
                    "to": "/evidence-bundle",
                    "proof": "portable approval artifacts",
                },
            ],
            "buying_trigger": "The buyer can justify a local product purchase without reading module code.",
        },
        {
            "role": "QA / Release",
            "headline": "Replace release faith with evidence.",
            "steps": [
                {
                    "label": "Testing",
                    "to": "/testing",
                    "proof": "test selection and gaps",
                },
                {
                    "label": "Release Readiness",
                    "to": "/release-readiness",
                    "proof": "policy gates",
                },
                {
                    "label": "Evidence Bundle",
                    "to": "/evidence-bundle",
                    "proof": "approval-ready exports",
                },
            ],
            "buying_trigger": "The release meeting gets a reusable test and evidence path.",
        },
        {
            "role": "Operations",
            "headline": "Connect runtime pain with code, platform and runbooks.",
            "steps": [
                {
                    "label": "Platform Doctor",
                    "to": "/platform-doctor",
                    "proof": "runtime and upgrade facts",
                },
                {
                    "label": "Lock Radar",
                    "to": "/lock-radar",
                    "proof": "TLOCK/TTIMEOUT/TDEADLOCK to module plan",
                },
                {
                    "label": "Operations",
                    "to": "/operations",
                    "proof": "incident report and runbook",
                },
            ],
            "buying_trigger": "A runtime incident stops being isolated from release and code evidence.",
        },
        {
            "role": "Vendor / Franchisee",
            "headline": "Sell a paid audit, then convert it into scoped work.",
            "steps": [
                {
                    "label": "Vendor Portfolio",
                    "to": "/vendor-portfolio",
                    "proof": "audit and work packages",
                },
                {
                    "label": "Value Packs",
                    "to": "/value-packs",
                    "proof": "buyable role outcomes",
                },
                {
                    "label": "Business Case",
                    "to": "/business-case",
                    "proof": "buyer committee and commercial story",
                },
            ],
            "buying_trigger": "The partner can send a buyer-safe report after a short local scan.",
        },
        {
            "role": "Security / Enterprise IT",
            "headline": "Check locality, artifacts and installability before trust.",
            "steps": [
                {
                    "label": "Enterprise Trust Center",
                    "to": "/enterprise-trust-center",
                    "proof": "local contour, SBOM/offline, rights and procurement proof",
                },
                {
                    "label": "Productization",
                    "to": "/productization",
                    "proof": "SBOM and offline bundle controls",
                },
                {
                    "label": "Evidence Bundle",
                    "to": "/evidence-bundle",
                    "proof": "hash manifest",
                },
            ],
            "buying_trigger": "The security conversation starts from local artifacts and explicit gaps.",
        },
    ]


def _close_plan() -> list[dict[str, Any]]:
    return [
        {
            "window": "First 24 hours",
            "owner": "vendor / tech lead",
            "actions": [
                "run configuration intake",
                "open Guided Demo with the buyer's config path",
                "show one developer proof and one director proof",
                "export the first Evidence Bundle",
            ],
            "exit_criteria": "Buyer understands the product and has a hashed artifact to forward.",
        },
        {
            "window": "First 7 days",
            "owner": "delivery lead",
            "actions": [
                "connect one real change or release window",
                "run Platform Doctor and Update War Room",
                "review Business Case assumptions with the decision maker",
                "pick the first value pack to pilot",
            ],
            "exit_criteria": "Pilot scope has a measurable route, owner and acceptance evidence.",
        },
        {
            "window": "First 30 days",
            "owner": "CIO / vendor owner",
            "actions": [
                "standardize evidence exports for release approval",
                "add vendor portfolio or enterprise rollout clients",
                "prepare productization readiness, SBOM and offline bundle checks",
                "decide local license and optional AI add-on model",
            ],
            "exit_criteria": "Purchase decision is tied to local value, governance and delivery artifacts.",
        },
    ]


def _objections(
    *,
    business_case: dict[str, Any],
    productization: dict[str, Any],
) -> list[dict[str, str]]:
    cards = [
        {
            "question": str(item.get("question", "")),
            "answer": str(item.get("answer", "")),
            "proof_route": str(item.get("proof_route", "/business-case")),
        }
        for item in business_case.get("objections", [])
        if item.get("question")
    ]
    cards.extend(
        [
            {
                "question": "Is it production-ready or only a demo?",
                "answer": (
                    "Productization readiness is explicit: deliverables, findings, tests, SBOM and offline bundle controls are visible."
                ),
                "proof_route": "/productization",
            },
            {
                "question": "What happens if external AI is disabled?",
                "answer": (
                    "The demo path relies on local graph, deterministic rules, reports, hashes and productization checks. AI remains optional."
                ),
                "proof_route": "/evidence-bundle",
            },
            {
                "question": "Can we trust the caveats?",
                "answer": (
                    f"Current productization status is {_status(productization)} / {_score(productization)}; the product shows gaps instead of hiding them."
                ),
                "proof_route": "/enterprise-trust-center",
            },
        ]
    )
    return cards[:8]


def _exports() -> list[dict[str, str]]:
    return [
        {"title": "Buyer Brief markdown", "filename": "buyer-brief.md", "route": "/"},
        {"title": "Buyer Pulse markdown", "filename": "buyer-pulse.md", "route": "/"},
        {
            "title": "Buyer Concierge markdown",
            "filename": "rentgen-buyer-concierge.md",
            "route": "/buyer-concierge",
        },
        {
            "title": "Demo Command Center markdown",
            "filename": "rentgen-demo-command-center.md",
            "route": "/demo-command-center",
        },
        {
            "title": "Commercial Offer Studio markdown",
            "filename": "rentgen-commercial-offer-studio.md",
            "route": "/commercial-offer-studio",
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
            "title": "Evidence Bundle manifest",
            "filename": "evidence-bundle-manifest.json",
            "route": "/evidence-bundle",
        },
        {
            "title": "Enterprise Trust Center",
            "filename": "rentgen-enterprise-trust-center.md",
            "route": "/enterprise-trust-center",
        },
        {
            "title": "Productization readiness",
            "filename": "productization-readiness.md",
            "route": "/productization",
        },
        {
            "title": "Vendor audit report",
            "filename": "vendor-portfolio.md",
            "route": "/vendor-portfolio",
        },
    ]


def _guided_room_bridge(
    *,
    buyer_brief: dict[str, Any] | None,
    steps: list[dict[str, Any]],
    role_paths: list[dict[str, Any]],
    proof_routes: list[str],
) -> dict[str, Any]:
    brief = buyer_brief or {}
    opening_step = steps[0] if steps else {}
    primary = dict(brief.get("primary_motion") or {})
    guided_path = {
        "label": str(opening_step.get("title") or "Open guided proof route"),
        "route": str(opening_step.get("route") or "/guided-demo"),
        "status": "ready",
        "ask": str(
            opening_step.get("talk_track")
            or "Start from role, pain and buyer-safe proof."
        ),
        "reason": str(
            opening_step.get("success_signal")
            or "Buyer sees one route instead of the whole product map."
        ),
        "minutes": float(opening_step.get("minutes") or 0.5),
    }
    if not primary:
        primary = {
            "label": "Run guided buyer route",
            "route": "/guided-demo",
            "status": "watch",
            "ask": "Open the guided route, prove one role path and close with artifacts.",
            "reason": "Guided Demo has role paths, close plan and proof exports.",
        }

    role_cards = list(brief.get("role_cards") or [])
    if not role_cards:
        role_cards = [
            {
                "role": item["role"].casefold(),
                "title": item["role"],
                "route": str(
                    (item.get("steps") or [{}])[0].get("to") or "/guided-demo"
                ),
                "status": "ready",
                "spark": item["headline"],
                "proof_file": "rentgen-guided-demo.md",
                "buying_trigger": item["buying_trigger"],
            }
            for item in role_paths[:5]
        ]

    proof_readiness = list(brief.get("proof_readiness") or [])
    if not proof_readiness:
        proof_readiness = [
            {
                "id": route.strip("/").replace("/", "-") or "home",
                "title": route.strip("/").replace("-", " ").title() or "Home",
                "route": route,
                "status": "ready",
                "signal": "Included in the guided proof route.",
                "file": "rentgen-guided-demo.md"
                if route == "/guided-demo"
                else "OPEN_FIRST.md",
            }
            for route in proof_routes[:4]
        ]

    meeting_flow = list(brief.get("meeting_flow") or [])
    if not meeting_flow:
        meeting_flow = [
            {
                "step": 1,
                "label": "Orient",
                "route": "/buyer-concierge",
                "line": "Pick role and first pain.",
            },
            {
                "step": 2,
                "label": "Guide",
                "route": "/guided-demo",
                "line": "Follow one buyer-safe route through proof.",
            },
            {
                "step": 3,
                "label": "Prove",
                "route": "/killer-demo",
                "line": "Compress proof into the buyer-ready demo path.",
            },
            {
                "step": 4,
                "label": "Forward",
                "route": "/evidence-bundle",
                "line": "Attach buyer brief, guided demo and hashed proof files.",
            },
        ]
    open_first_path = build_open_first_path(
        existing_path=brief.get("open_first_path"),
        proof_readiness=proof_readiness,
        primary=primary,
        meeting_flow=meeting_flow,
        source="guided-demo-fallback",
        orient_title="Guided Demo",
        orient_route="/guided-demo",
        orient_line="Follow one buyer-safe route through proof.",
        orient_status=str(primary.get("status") or "watch"),
        prove_line="Compress proof into the buyer-ready demo path.",
        close_title="Killer Demo",
        close_route="/killer-demo",
        close_line="Use the guided proof as the close-room demo path.",
        close_file="rentgen-killer-demo-path.md",
        close_status=str(primary.get("status") or "watch"),
        verify_line="Attach buyer brief, guided demo and hashed proof files.",
    )

    routes = sorted(
        {
            "/guided-demo",
            str(primary.get("route") or "/guided-demo"),
            str(guided_path["route"]),
            *[str(item.get("route") or "") for item in role_cards],
            *[str(item.get("route") or "") for item in proof_readiness],
            *[str(item.get("route") or "") for item in meeting_flow],
            *[str(item.get("route") or "") for item in open_first_path],
            *proof_routes,
        }
        - {""}
    )
    return {
        "status": str(brief.get("purchase_status") or primary.get("status") or "watch"),
        "score": _int(brief.get("score"), 74),
        "source": str(brief.get("source") or "guided-demo-derived"),
        "room_line": str(
            brief.get("room_line")
            or f"{primary.get('label', 'Run guided buyer route')}: {primary.get('ask', 'Prove one route and forward artifacts.')}"
        ),
        "primary_motion": {
            "label": str(primary.get("label") or "Run guided buyer route"),
            "route": str(primary.get("route") or "/guided-demo"),
            "status": str(primary.get("status") or "watch"),
            "ask": str(primary.get("ask") or "Prove one route and forward artifacts."),
            "reason": str(
                primary.get("reason")
                or "Guided route keeps the buyer away from menu overload."
            ),
        },
        "guided_path": guided_path,
        "role_cards": role_cards[:5],
        "proof_readiness": proof_readiness[:4],
        "meeting_flow": meeting_flow[:4],
        "open_first_path": open_first_path[:4],
        "files": [
            "buyer-brief.md",
            "buyer-pulse.md",
            OPEN_FIRST_PATH_FILE,
            "rentgen-guided-demo.md",
            "rentgen-demo-command-center.md",
            "OPEN_FIRST.md",
        ],
        "routes": routes,
        "close_question": "Which role path proves enough to open the paid next step?",
    }


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 1C Rentgen Guided Demo",
        "",
        f"Client: **{report['client']['name']}**",
        f"Status: **{report['decision']['status'].upper()}** / score **{report['decision']['score']}**",
        f"Total route: **{report['summary']['total_minutes']} minutes**",
        "",
        "## Opening claims",
        "",
    ]
    for item in report["opening"]:
        lines.append(f"- **{item['claim']}**: {item['proof']} (`{item['route']}`)")
    lines.extend(["", "## Guided steps", ""])
    for item in report["guided_steps"]:
        lines.append(
            f"- **{item['title']}** ({item['role']}, {item['minutes']} min, `{item['route']}`): {item['success_signal']}"
        )
    lines.extend(["", "## Close plan", ""])
    for item in report["close_plan"]:
        lines.append(
            f"- **{item['window']}** / {item['owner']}: {item['exit_criteria']}"
        )
    bridge = report.get("guided_room_bridge") or {}
    if bridge:
        lines.extend(["", "## Guided Room Bridge", ""])
        lines.append(
            f"- Source: **{bridge.get('source', 'n/a')}**; status **{bridge.get('status', 'watch')}** / score **{bridge.get('score', 0)}**"
        )
        lines.append(f"- Room line: {bridge.get('room_line', '')}")
        motion = bridge.get("primary_motion") or {}
        lines.append(
            f"- Primary motion: **{motion.get('label', 'n/a')}** (`{motion.get('route', '/guided-demo')}`): {motion.get('ask', '')}"
        )
        guided_path = bridge.get("guided_path") or {}
        lines.append(
            f"- Guided path: **{guided_path.get('label', 'n/a')}** (`{guided_path.get('route', '/guided-demo')}`): {guided_path.get('ask', '')}"
        )
        lines.extend(
            open_first_path_markdown_lines(
                bridge.get("open_first_path"), default_route="/guided-demo"
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


def build_guided_demo(
    *,
    executive: dict[str, Any],
    demo_story: dict[str, Any],
    business_case: dict[str, Any],
    productization: dict[str, Any],
    value_packs: dict[str, Any],
    vendor_portfolio: dict[str, Any],
    buyer_brief: dict[str, Any] | None = None,
    client_name: str = "Demo client",
    config_path: str | None = None,
    target_platform_version: str | None = None,
) -> dict[str, Any]:
    """Build the single buyer-safe route through the strongest product surfaces."""

    steps = _guided_steps(
        executive=executive,
        business_case=business_case,
        productization=productization,
        vendor_portfolio=vendor_portfolio,
    )
    exec_score = _score(executive)
    business_score = _score(business_case)
    product_score = _score(productization)
    value_score = _score(value_packs)
    vendor_score = _score(vendor_portfolio)
    score = max(
        0,
        min(
            100,
            round(
                exec_score * 0.30
                + business_score * 0.25
                + product_score * 0.20
                + value_score * 0.15
                + vendor_score * 0.10
            ),
        ),
    )
    statuses = {
        _status(executive),
        _status(business_case),
        _status(productization),
        _status(vendor_portfolio),
    }
    if statuses & {"blocked", "critical", "fail"}:
        status = "risk"
    elif score >= 82 and "risk" not in statuses:
        status = "ready"
    else:
        status = "watch"

    role_paths = _role_paths()
    proof_routes = sorted({item["route"] for item in steps})
    guided_room_bridge = _guided_room_bridge(
        buyer_brief=buyer_brief,
        steps=steps,
        role_paths=role_paths,
        proof_routes=proof_routes,
    )
    proof_routes = sorted(set(proof_routes) | set(guided_room_bridge["routes"]))
    total_minutes = round(sum(float(item["minutes"]) for item in steps), 1)
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
                "Guided Demo is ready: one route explains the product, proves value by role and closes with buyer-safe artifacts."
                if status == "ready"
                else "Guided Demo is usable, but show caveats and productization findings honestly during the buyer route."
            ),
        },
        "summary": {
            "total_minutes": total_minutes,
            "steps": len(steps),
            "roles": len(role_paths),
            "proof_routes": len(proof_routes),
            "value_packs": len(value_packs.get("packs") or []),
            "business_value": (business_case.get("summary") or {}).get(
                "first_year_visible_value", 0
            ),
            "productization_findings": (productization.get("summary") or {}).get(
                "findings", 0
            ),
            "guided_room_roles": len(guided_room_bridge["role_cards"]),
            "guided_room_proofs": len(guided_room_bridge["proof_readiness"]),
            "guided_room_steps": len(guided_room_bridge["meeting_flow"]),
            "guided_room_open_first": len(guided_room_bridge["open_first_path"]),
        },
        "opening": [
            {
                "claim": "This is not an AI chat.",
                "proof": "The core demo uses local graph, deterministic rules, reports, gates and evidence hashes.",
                "route": "/quality",
            },
            {
                "claim": "The buyer sees their 1C system, not a generic template.",
                "proof": "Routes connect configuration intake, architecture, code, platform, rights, tests and runtime facts.",
                "route": "/configurations",
            },
            {
                "claim": "The close is an artifact pack, not a verbal promise.",
                "proof": "Evidence Bundle, Business Case, Vendor Portfolio and Productization reports are exportable.",
                "route": "/evidence-bundle",
            },
        ],
        "guided_steps": steps,
        "guided_room_bridge": guided_room_bridge,
        "role_paths": role_paths,
        "close_plan": _close_plan(),
        "objection_cards": _objections(
            business_case=business_case, productization=productization
        ),
        "exports": _exports(),
        "proof_routes": proof_routes,
        "source_signals": {
            "executive_status": _status(executive),
            "executive_score": exec_score,
            "demo_steps": len(demo_story.get("demo_steps") or []),
            "business_status": _status(business_case),
            "productization_status": _status(productization),
            "vendor_status": _status(vendor_portfolio),
        },
        "caveats": [
            "Guided Demo v1 is a route through implemented evidence surfaces, not a substitute for customer acceptance testing.",
            "Commercial values come from explicit Business Case assumptions and should be reviewed with finance.",
            "Productization readiness is shown as-is; findings are part of the enterprise close, not hidden sales friction.",
        ],
    }
    report["markdown"] = _markdown(report)
    report["download_name"] = "rentgen-guided-demo.md"
    return report
