"""Vendor/franchisee portfolio and pre-sale audit report."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any

from src.services.rentgen.coverage_ledger import build_coverage_ledger
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


def _status(score: int, red_areas: int, platform_status: str) -> str:
    if red_areas or platform_status == "risk" or score < 60:
        return "risk"
    if score >= 82 and platform_status == "ready":
        return "ready"
    return "watch"


def _money_signal(executive: dict[str, Any], platform: dict[str, Any], intake: dict[str, Any]) -> list[dict[str, Any]]:
    kpis = executive.get("kpis") or {}
    platform_decision = platform.get("decision") or {}
    intake_decision = intake.get("decision") or {}
    return [
        {
            "id": "risk-audit",
            "title": "Аудит риска до договора сопровождения",
            "value": f"{kpis.get('modules_with_issues', 0)} modules with issues",
            "offer": "Фиксированный экспресс-аудит конфигурации и отчёт для руководителя.",
        },
        {
            "id": "platform-upgrade",
            "title": "Оценка обновления платформы",
            "value": f"platform {platform_decision.get('status', 'unknown')} / {platform_decision.get('score', 0)}",
            "offer": "Пакет Platform Doctor + тестовое окно + rollback/evidence.",
        },
        {
            "id": "intake-readiness",
            "title": "Готовность к подключению проекта",
            "value": f"intake {intake_decision.get('status', 'unknown')} / {intake_decision.get('score', 0)}",
            "offer": "Подключение EDT/Git/XML, coverage report и инкрементальный план индексации.",
        },
        {
            "id": "release-factory",
            "title": "Фабрика безопасных релизов",
            "value": f"review queue {kpis.get('review_queue', 0)}",
            "offer": "Регулярный release gate: impact, tests, approvals, evidence bundle.",
        },
    ]


def _work_packages(executive: dict[str, Any], platform: dict[str, Any], intake: dict[str, Any]) -> list[dict[str, Any]]:
    kpis = executive.get("kpis") or {}
    platform_failed = [item for item in platform.get("checks", []) if item.get("status") != "pass"]
    intake_caveats = intake.get("caveats") or []
    packages = [
        {
            "id": "connect",
            "title": "Подключить конфигурацию и источники",
            "priority": "P0",
            "effort": "1-2 дня",
            "evidence": f"{len(intake_caveats)} caveats in intake",
            "outcome": "Понятное покрытие: код, метаданные, формы, права, тесты, платформа.",
        },
        {
            "id": "risk-burn-down",
            "title": "Снизить top-risk hotspots",
            "priority": "P0" if kpis.get("red_areas") else "P1",
            "effort": "3-10 дней",
            "evidence": f"{kpis.get('red_areas', 0)} red areas, {kpis.get('modules_with_issues', 0)} modules with issues",
            "outcome": "Список точечных работ, владельцы, impact и тесты.",
        },
        {
            "id": "platform-readiness",
            "title": "Подготовить платформенный upgrade/readiness",
            "priority": "P0" if platform_failed else "P1",
            "effort": "2-5 дней",
            "evidence": f"{len(platform_failed)} platform checks need attention",
            "outcome": "Версии, совместимость, СУБД, техжурнал, OpenMetrics, rollback checklist.",
        },
        {
            "id": "release-control",
            "title": "Ввести релизный gate",
            "priority": "P1",
            "effort": "1 неделя",
            "evidence": f"review queue {kpis.get('review_queue', 0)}",
            "outcome": "Каждая правка получает go/no-go, тест-план и evidence для approval.",
        },
    ]
    return packages


def _deal_board(report: dict[str, Any]) -> dict[str, Any]:
    status = str((report.get("decision") or {}).get("status") or "watch")
    packages = list(report.get("work_packages") or [])
    priority_package = next((item for item in packages if item.get("priority") == "P0"), packages[0] if packages else {})
    if status == "risk":
        motion = "Sell a paid risk burn-down sprint before promising support or upgrade dates."
        route = "/pilot-launchpad"
    elif status == "ready":
        motion = "Sell a rollout or portfolio license anchored by the audit proof packet."
        route = "/commercial-offer-studio"
    else:
        motion = "Sell a fixed proof sprint that turns watch items into a priced scope."
        route = "/business-case"
    return {
        "recommended_motion": motion,
        "primary_package": {
            "id": str(priority_package.get("id") or "audit"),
            "title": str(priority_package.get("title") or "Audit package"),
            "priority": str(priority_package.get("priority") or "P1"),
            "evidence": str(priority_package.get("evidence") or ""),
        },
        "next_step": {
            "label": "Build commercial offer" if status != "risk" else "Build pilot/risk sprint",
            "to": route,
            "reason": "Move from audit evidence to a buyer-safe paid step.",
        },
        "role_sparks": [
            {
                "role": "partner lead",
                "spark": "Client rows become work packages and a next paid move.",
            },
            {
                "role": "architect",
                "spark": "Risk, platform and connection caveats are visible before estimates.",
            },
            {
                "role": "director",
                "spark": "The audit can be forwarded as a commercial decision artifact.",
            },
        ],
        "proof_packet": [
            {"title": "Vendor audit markdown", "route": "/vendor-portfolio", "artifact": "rentgen-vendor-audit.md"},
            {"title": "Business Case", "route": "/business-case", "artifact": "rentgen-business-case.md"},
            {"title": "Commercial Offer", "route": "/commercial-offer-studio", "artifact": "rentgen-commercial-offer.md"},
            {"title": "Evidence Bundle", "route": "/evidence-bundle", "artifact": "evidence-bundle-manifest.json"},
        ],
    }


def _portfolio_decision_board(
    *,
    rows: list[dict[str, Any]],
    opportunities: list[dict[str, Any]],
    portfolio: dict[str, Any],
    status: str,
) -> dict[str, Any]:
    risk_clients = [row["name"] for row in rows if row["status"] == "risk"]
    watch_clients = [row["name"] for row in rows if row["status"] == "watch"]
    ready_clients = [row["name"] for row in rows if row["status"] == "ready"]
    first_opportunity = opportunities[0] if opportunities else {}
    next_route = "/pilot-launchpad" if risk_clients else "/commercial-offer-studio"
    next_label = "Sell risk burn-down sprint" if risk_clients else "Sell portfolio rollout"
    return {
        "status": status,
        "next_commercial_move": {
            "label": next_label,
            "to": next_route,
            "reason": (
                "Risk clients need scoped remediation before broad promises."
                if risk_clients
                else "Ready/watch clients can move to offer, business case and evidence packet."
            ),
        },
        "segments": [
            {
                "id": "risk-first",
                "title": "Stabilize before promises",
                "clients": risk_clients,
                "motion": "Paid risk burn-down / platform readiness sprint",
                "route": "/pilot-launchpad",
            },
            {
                "id": "watch-to-proof",
                "title": "Convert watch to proof",
                "clients": watch_clients,
                "motion": "Fixed proof sprint with Evidence Bundle",
                "route": "/business-case",
            },
            {
                "id": "ready-to-rollout",
                "title": "Ready to roll out",
                "clients": ready_clients,
                "motion": "Portfolio license or support package",
                "route": "/commercial-offer-studio",
            },
        ],
        "offer_sequence": [
            {
                "step": 1,
                "title": "Portfolio audit",
                "route": "/vendor-portfolio",
                "evidence": f"{portfolio.get('clients', 0)} clients, avg score {portfolio.get('avg_score', 0)}",
            },
            {
                "step": 2,
                "title": str(first_opportunity.get("title") or "Top work package"),
                "route": "/value-packs",
                "evidence": f"{first_opportunity.get('clients', 0)} clients share this package",
            },
            {
                "step": 3,
                "title": "Commercial offer and proof packet",
                "route": "/commercial-offer-studio",
                "evidence": "Offer, business case and Evidence Bundle are buyer-safe artifacts.",
            },
        ],
        "proof_packet": [
            {"title": "Portfolio markdown", "route": "/vendor-portfolio", "artifact": "rentgen-vendor-portfolio.md"},
            {"title": "Pilot Launchpad", "route": "/pilot-launchpad", "artifact": "rentgen-pilot-launchpad.md"},
            {"title": "Commercial Offer", "route": "/commercial-offer-studio", "artifact": "rentgen-commercial-offer.md"},
            {"title": "Evidence Bundle", "route": "/evidence-bundle", "artifact": "evidence-bundle-manifest.json"},
        ],
    }


def _vendor_room_bridge(
    *,
    buyer_brief: dict[str, Any] | None,
    deal_board: dict[str, Any],
    work_packages: list[dict[str, Any]],
) -> dict[str, Any]:
    brief = buyer_brief or {}
    primary = dict(brief.get("primary_motion") or {})
    if not primary:
        primary = {
            "label": "Sell audit proof",
            "route": "/vendor-portfolio",
            "status": "watch",
            "ask": "Turn the scan into one paid audit, sprint or rollout package.",
            "reason": "Vendor Portfolio converts technical findings into commercial work packages.",
        }

    package = deal_board.get("primary_package") or (work_packages[0] if work_packages else {})
    vendor_motion = {
        "label": str((deal_board.get("next_step") or {}).get("label") or "Build vendor offer"),
        "route": str((deal_board.get("next_step") or {}).get("to") or "/commercial-offer-studio"),
        "status": str(primary.get("status") or "watch"),
        "ask": str(deal_board.get("recommended_motion") or "Move from audit evidence to a buyer-safe paid step."),
        "reason": str((deal_board.get("next_step") or {}).get("reason") or "The vendor needs a concrete first package."),
    }

    role_cards = list(brief.get("role_cards") or [])
    if not role_cards:
        role_cards = [
            {
                "role": "vendor",
                "title": "Vendor",
                "route": "/vendor-portfolio",
                "status": "ready",
                "spark": "Audit rows become work packages and next paid move.",
                "proof_file": "rentgen-vendor-audit.md",
            },
            {
                "role": "director",
                "title": "Director",
                "route": "/business-case",
                "status": "ready",
                "spark": "Audit becomes a commercial decision artifact.",
                "proof_file": "rentgen-business-case.md",
            },
            {
                "role": "architect",
                "title": "Architect",
                "route": "/platform-doctor",
                "status": "watch",
                "spark": "Risk, platform and connection caveats are visible before estimates.",
                "proof_file": "platform-doctor.md",
            },
            {
                "role": "security",
                "title": "Security",
                "route": "/enterprise-trust-center",
                "status": "watch",
                "spark": "Buyer-safe evidence and trust questions are ready for procurement.",
                "proof_file": "rentgen-security-questionnaire.md",
            },
            {
                "role": "developer",
                "title": "Developer",
                "route": "/change",
                "status": "watch",
                "spark": "Top findings become scoped remediation work.",
                "proof_file": "rentgen-developer-report.md",
            },
        ]

    proof_readiness = list(brief.get("proof_readiness") or [])
    if not proof_readiness:
        proof_readiness = [
            {
                "id": "vendor-audit",
                "title": "Vendor audit",
                "route": "/vendor-portfolio",
                "status": "ready",
                "signal": str(package.get("evidence") or "Primary package is selected."),
                "file": "rentgen-vendor-audit.md",
            },
            {
                "id": "business-case",
                "title": "Business Case",
                "route": "/business-case",
                "status": "ready",
                "signal": "Turns audit findings into buyer value and local product logic.",
                "file": "rentgen-business-case.md",
            },
            {
                "id": "commercial-offer",
                "title": "Commercial Offer",
                "route": "/commercial-offer-studio",
                "status": "watch",
                "signal": "Turns package into price, acceptance and procurement dossier.",
                "file": "rentgen-commercial-offer.md",
            },
            {
                "id": "evidence-bundle",
                "title": "Evidence Bundle",
                "route": "/evidence-bundle",
                "status": "ready",
                "signal": "Forwards audit, buyer brief and proof packet.",
                "file": "OPEN_FIRST.md",
            },
        ]

    meeting_flow = list(brief.get("meeting_flow") or [])
    if not meeting_flow:
        meeting_flow = [
            {"step": 1, "label": "Orient", "route": "/buyer-concierge", "line": "Pick partner, buyer role or pain."},
            {"step": 2, "label": "Audit", "route": "/vendor-portfolio", "line": "Show work package, evidence and commercial signal."},
            {"step": 3, "label": "Offer", "route": vendor_motion["route"], "line": vendor_motion["ask"]},
            {"step": 4, "label": "Forward", "route": "/evidence-bundle", "line": "Send buyer brief, vendor audit and proof archive."},
        ]
    open_first_path = build_open_first_path(
        existing_path=brief.get("open_first_path"),
        proof_readiness=proof_readiness,
        primary=primary,
        meeting_flow=meeting_flow,
        source="vendor-portfolio-fallback",
        orient_title="Vendor Portfolio",
        orient_route="/vendor-portfolio",
        orient_line="Show work package, evidence and commercial signal.",
        orient_status=str(primary.get("status") or vendor_motion.get("status") or "watch"),
        prove_line=str(package.get("evidence") or "Primary package is selected."),
        close_title=str(vendor_motion.get("label") or "Commercial Offer"),
        close_route=str(vendor_motion.get("route") or "/commercial-offer-studio"),
        close_line=str(vendor_motion.get("ask") or "Move from audit evidence to a buyer-safe paid step."),
        close_file="rentgen-commercial-offer.md",
        close_status=str(primary.get("status") or vendor_motion.get("status") or "watch"),
        verify_line="Send buyer brief, vendor audit and proof archive.",
    )

    routes = sorted(
        {
            "/vendor-portfolio",
            str(primary.get("route") or "/vendor-portfolio"),
            str(vendor_motion["route"]),
            *[str(item.get("route") or "") for item in role_cards],
            *[str(item.get("route") or "") for item in proof_readiness],
            *[str(item.get("route") or "") for item in meeting_flow],
            *[str(item.get("route") or "") for item in open_first_path],
            *[str(item.get("route") or "") for item in deal_board.get("proof_packet", [])],
        }
        - {""}
    )
    return {
        "status": str(brief.get("purchase_status") or primary.get("status") or "watch"),
        "score": _int(brief.get("score"), 75),
        "source": str(brief.get("source") or "vendor-portfolio-derived"),
        "room_line": str(
            brief.get("room_line")
            or f"{primary.get('label', 'Sell audit proof')}: {primary.get('ask', 'Turn audit evidence into paid scope.')}"
        ),
        "primary_motion": {
            "label": str(primary.get("label") or "Sell audit proof"),
            "route": str(primary.get("route") or "/vendor-portfolio"),
            "status": str(primary.get("status") or "watch"),
            "ask": str(primary.get("ask") or "Turn audit evidence into paid scope."),
            "reason": str(primary.get("reason") or "Vendor Portfolio makes audit evidence buyable."),
        },
        "vendor_motion": vendor_motion,
        "role_cards": role_cards[:5],
        "proof_readiness": proof_readiness[:4],
        "meeting_flow": meeting_flow[:4],
        "open_first_path": open_first_path[:4],
        "files": ["buyer-brief.md", "buyer-pulse.md", OPEN_FIRST_PATH_FILE, "rentgen-vendor-audit.md", "rentgen-commercial-offer.md", "OPEN_FIRST.md"],
        "routes": routes,
        "close_question": "Which audit package becomes the first paid vendor motion?",
    }


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 1C Rentgen Vendor Audit",
        "",
        f"Client: **{report['client']['name']}**",
        f"Configuration: **{report['client']['configuration']}**",
        f"Status: **{report['decision']['status'].upper()}** / score **{report['decision']['score']}**",
        "",
        "## Commercial signals",
        "",
    ]
    for item in report["commercial_signals"]:
        lines.append(f"- **{item['title']}**: {item['value']}. {item['offer']}")
    lines.extend(["", "## Work packages", ""])
    for item in report["work_packages"]:
        lines.append(f"- **{item['priority']}** {item['title']} ({item['effort']}): {item['outcome']}")
    board = report.get("deal_board") or {}
    if board:
        lines.extend(["", "## Deal Board", ""])
        lines.append(f"- Recommended motion: {board['recommended_motion']}")
        lines.append(f"- Next step: `{board['next_step']['to']}` - {board['next_step']['reason']}")
        primary = board["primary_package"]
        lines.append(f"- Primary package: **{primary['priority']}** {primary['title']} - {primary['evidence']}")
    bridge = report.get("vendor_room_bridge") or {}
    if bridge:
        lines.extend(["", "## Vendor Room Bridge", ""])
        lines.append(f"- Source: **{bridge.get('source', 'n/a')}**; status **{bridge.get('status', 'watch')}** / score **{bridge.get('score', 0)}**")
        lines.append(f"- Room line: {bridge.get('room_line', '')}")
        motion = bridge.get("primary_motion") or {}
        lines.append(f"- Primary motion: **{motion.get('label', 'n/a')}** (`{motion.get('route', '/vendor-portfolio')}`): {motion.get('ask', '')}")
        vendor_motion = bridge.get("vendor_motion") or {}
        lines.append(f"- Vendor motion: **{vendor_motion.get('label', 'n/a')}** (`{vendor_motion.get('route', '/vendor-portfolio')}`): {vendor_motion.get('ask', '')}")
        lines.extend(open_first_path_markdown_lines(bridge.get("open_first_path"), default_route="/vendor-portfolio"))
        for item in bridge.get("role_cards", []):
            lines.append(f"- **{item.get('title', item.get('role', 'role'))}** `{item.get('route', '')}`: {item.get('spark', '')}")
        for item in bridge.get("proof_readiness", []):
            lines.append(f"- Proof **{item.get('title', 'proof')}** `{item.get('route', '')}` -> {item.get('file', '')}: {item.get('signal', '')}")
        for item in bridge.get("meeting_flow", []):
            lines.append(f"- Step {item.get('step', '')} **{item.get('label', 'step')}** `{item.get('route', '')}`: {item.get('line', '')}")
    ledger = report.get("coverage_ledger") or {}
    if ledger:
        summary = ledger.get("summary") or {}
        lines.extend(["", "## Coverage Ledger", ""])
        lines.append(
            f"- Status: **{ledger.get('status', 'unknown')}** / score **{ledger.get('score', 0)}**"
        )
        lines.append(
            f"- Measured: {summary.get('measured', 0)}/{summary.get('items', 0)}; caveats: {summary.get('caveats', 0)}"
        )
    lines.extend(["", "## Caveats", ""])
    lines.extend(f"- {item}" for item in report["caveats"])
    return "\n".join(lines)


def _portfolio_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 1C Rentgen Vendor Portfolio",
        "",
        f"Portfolio: **{report['portfolio']['name']}**",
        f"Status: **{report['decision']['status'].upper()}** / score **{report['decision']['score']}**",
        "",
        "## Clients",
        "",
    ]
    for item in report["clients"]:
        lines.append(
            f"- **{item['name']}**: {item['status']} / {item['score']} - {item['configuration']}"
        )
    lines.extend(["", "## Opportunities", ""])
    for item in report["opportunities"]:
        lines.append(f"- **{item['title']}**: {item['clients']} clients, priority {item['priority']}")
    board = report.get("decision_board") or {}
    if board:
        lines.extend(["", "## Portfolio Decision Board", ""])
        lines.append(f"- Next commercial move: `{board['next_commercial_move']['to']}` - {board['next_commercial_move']['reason']}")
        for segment in board["segments"]:
            lines.append(f"- **{segment['title']}**: {len(segment['clients'])} clients, {segment['motion']}")
    lines.extend(["", "## Caveats", ""])
    lines.extend(f"- {item}" for item in report["caveats"])
    return "\n".join(lines)


def build_vendor_portfolio(
    *,
    executive: dict[str, Any],
    platform: dict[str, Any],
    intake: dict[str, Any],
    buyer_brief: dict[str, Any] | None = None,
    client_name: str = "Demo client",
) -> dict[str, Any]:
    """Build a vendor/franchisee pre-sale audit from local product signals."""

    kpis = executive.get("kpis") or {}
    decision = executive.get("decision") or {}
    platform_decision = platform.get("decision") or {}
    intake_decision = intake.get("decision") or {}
    score = round(
        (int(decision.get("score") or 0) * 0.45)
        + (int(platform_decision.get("score") or 0) * 0.30)
        + (int(intake_decision.get("score") or 0) * 0.25)
    )
    status = _status(
        score,
        red_areas=int(kpis.get("red_areas") or 0),
        platform_status=str(platform_decision.get("status") or "unknown"),
    )
    configuration = (
        (platform.get("inventory") or {}).get("configuration_name")
        or "1C configuration"
    )
    report = {
        "generated_at": _now(),
        "client": {
            "name": client_name,
            "configuration": configuration,
            "configuration_version": (platform.get("inventory") or {}).get("configuration_version") or "",
        },
        "decision": {
            "status": status,
            "score": score,
            "headline": (
                "Есть понятный pre-sale пакет: аудит, платформа, подключение, релизный gate."
                if status != "risk"
                else "Перед коммерческим обещанием нужно закрыть красные зоны и платформенные неизвестные."
            ),
        },
        "portfolio": {
            "clients": 1,
            "configurations": 1,
            "avg_score": score,
            "red_areas": int(kpis.get("red_areas") or 0),
            "modules": int(kpis.get("modules") or 0),
            "modules_with_issues": int(kpis.get("modules_with_issues") or 0),
        },
        "commercial_signals": _money_signal(executive, platform, intake),
        "work_packages": _work_packages(executive, platform, intake),
        "top_risks": (executive.get("risk_summary") or {}).get("top_risks", [])[:5],
        "next_actions": [
            {"label": "Demo Command Center", "to": "/demo-command-center"},
            {"label": "Scenario Hub", "to": "/scenario-hub"},
            {"label": "Pilot Launchpad", "to": "/pilot-launchpad"},
            {"label": "Открыть demo story", "to": "/"},
            {"label": "Guided Demo", "to": "/guided-demo"},
            {"label": "Business Case", "to": "/business-case"},
            {"label": "Проверить конфигурацию", "to": "/configurations"},
            {"label": "Проверить платформу", "to": "/platform-doctor"},
            {"label": "Собрать релизный gate", "to": "/release-readiness"},
        ],
        "caveats": [
            "Vendor Portfolio v1 is a local pre-sale audit for the current configuration, not a multi-client CRM store yet.",
            "Commercial estimates are work-package signals, not fixed-price obligations.",
            *list(intake.get("caveats") or [])[:5],
            *list(platform.get("caveats") or [])[:3],
        ],
    }
    report["coverage_ledger"] = build_coverage_ledger(
        executive=executive,
        intake=intake,
        platform=platform,
    )
    report["deal_board"] = _deal_board(report)
    report["vendor_room_bridge"] = _vendor_room_bridge(
        buyer_brief=buyer_brief,
        deal_board=report["deal_board"],
        work_packages=report["work_packages"],
    )
    report["portfolio"]["vendor_room_roles"] = len(report["vendor_room_bridge"]["role_cards"])
    report["portfolio"]["vendor_room_proofs"] = len(report["vendor_room_bridge"]["proof_readiness"])
    report["portfolio"]["vendor_room_steps"] = len(report["vendor_room_bridge"]["meeting_flow"])
    report["portfolio"]["vendor_room_open_first"] = len(report["vendor_room_bridge"]["open_first_path"])
    report["portfolio"]["coverage_caveats"] = report["coverage_ledger"]["summary"]["caveats"]
    report["vendor_room_bridge"]["coverage_ledger"] = report["coverage_ledger"]
    report["proof_routes"] = sorted(
        {item["to"] for item in report["next_actions"]}
        | {item["route"] for item in report["deal_board"]["proof_packet"]}
        | set(report["vendor_room_bridge"]["routes"])
    )
    report["markdown"] = _markdown(report)
    return report


def build_vendor_portfolio_book(
    *,
    audits: list[dict[str, Any]],
    portfolio_name: str = "Vendor portfolio",
) -> dict[str, Any]:
    """Aggregate several single-client audits into a vendor portfolio view."""

    if not audits:
        report: dict[str, Any] = {
            "generated_at": _now(),
            "decision": {
                "status": "blocked",
                "score": 0,
                "headline": "Portfolio needs at least one client audit.",
            },
            "portfolio": {
                "name": portfolio_name,
                "clients": 0,
                "avg_score": 0,
                "ready": 0,
                "watch": 0,
                "risk": 0,
                "modules": 0,
                "modules_with_issues": 0,
                "red_areas": 0,
            },
            "clients": [],
            "opportunities": [],
            "next_actions": [],
            "caveats": ["Portfolio mode needs at least one client/configuration."],
        }
        report["markdown"] = _portfolio_markdown(report)
        return report

    rows: list[dict[str, Any]] = []
    package_counts: dict[str, dict[str, Any]] = {}
    total_score = 0
    total_modules = 0
    total_issues = 0
    total_red = 0
    statuses = Counter()
    for audit in audits:
        client = audit.get("client") or {}
        decision = audit.get("decision") or {}
        portfolio = audit.get("portfolio") or {}
        status = str(decision.get("status") or "watch")
        score = int(decision.get("score") or 0)
        statuses[status] += 1
        total_score += score
        total_modules += int(portfolio.get("modules") or 0)
        total_issues += int(portfolio.get("modules_with_issues") or 0)
        total_red += int(portfolio.get("red_areas") or 0)
        rows.append(
            {
                "name": str(client.get("name") or "Client"),
                "configuration": str(client.get("configuration") or "1C configuration"),
                "configuration_version": str(client.get("configuration_version") or ""),
                "status": status,
                "score": score,
                "modules": int(portfolio.get("modules") or 0),
                "modules_with_issues": int(portfolio.get("modules_with_issues") or 0),
                "red_areas": int(portfolio.get("red_areas") or 0),
                "headline": str(decision.get("headline") or ""),
                "top_risks": list(audit.get("top_risks") or [])[:3],
            }
        )
        for package in audit.get("work_packages") or []:
            package_id = str(package.get("id") or package.get("title") or "package")
            current = package_counts.setdefault(
                package_id,
                {
                    "id": package_id,
                    "title": str(package.get("title") or package_id),
                    "priority": str(package.get("priority") or "P1"),
                    "clients": 0,
                    "evidence": [],
                },
            )
            current["clients"] += 1
            current["evidence"].append(str((audit.get("client") or {}).get("name") or "Client"))

    avg_score = round(total_score / len(audits))
    risk_count = statuses.get("risk", 0)
    status = "risk" if risk_count else ("ready" if avg_score >= 82 and statuses.get("watch", 0) == 0 else "watch")
    opportunities = sorted(
        package_counts.values(),
        key=lambda item: (
            0 if item["priority"] == "P0" else 1 if item["priority"] == "P1" else 2,
            -int(item["clients"]),
            item["title"],
        ),
    )
    portfolio_summary = {
        "name": portfolio_name,
        "clients": len(audits),
        "avg_score": avg_score,
        "ready": statuses.get("ready", 0),
        "watch": statuses.get("watch", 0),
        "risk": statuses.get("risk", 0),
        "modules": total_modules,
        "modules_with_issues": total_issues,
        "red_areas": total_red,
    }
    report = {
        "generated_at": _now(),
        "decision": {
            "status": status,
            "score": avg_score,
            "headline": (
                "Portfolio mode shows where vendor effort converts into paid audits, upgrades and release gates."
                if status != "risk"
                else "Portfolio has risk clients that need scoped remediation before broad support promises."
            ),
        },
        "portfolio": portfolio_summary,
        "clients": sorted(rows, key=lambda item: (item["status"] != "risk", -item["score"], item["name"])),
        "opportunities": opportunities,
        "next_actions": [
            {"label": "Demo Command Center", "to": "/demo-command-center"},
            {"label": "Scenario Hub", "to": "/scenario-hub"},
            {"label": "Pilot Launchpad", "to": "/pilot-launchpad"},
            {"label": "Guided Demo", "to": "/guided-demo"},
            {"label": "Business Case", "to": "/business-case"},
            {"label": "Evidence Bundle", "to": "/evidence-bundle"},
            {"label": "Value Packs", "to": "/value-packs"},
            {"label": "Productization", "to": "/productization"},
        ],
        "caveats": [
            "Portfolio mode v1 aggregates current audit signals; it is not a CRM or billing ledger yet.",
            "Each client row should be regenerated when the configuration path or platform target changes.",
        ],
    }
    report["decision_board"] = _portfolio_decision_board(
        rows=rows,
        opportunities=opportunities,
        portfolio=portfolio_summary,
        status=status,
    )
    report["markdown"] = _portfolio_markdown(report)
    return report
