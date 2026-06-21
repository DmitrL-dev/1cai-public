"""Product value packs for role-based 1C Rentgen packaging."""

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


def _pack(
    *,
    id: str,
    title: str,
    audience: str,
    outcome: str,
    maturity: str,
    routes: list[dict[str, str]],
    proof_points: list[str],
    deliverables: list[str],
    price_story: str,
    caveats: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": id,
        "title": title,
        "audience": audience,
        "outcome": outcome,
        "maturity": maturity,
        "routes": routes,
        "proof_points": proof_points,
        "deliverables": deliverables,
        "price_story": price_story,
        "caveats": caveats or [],
    }


def _value_room_bridge(
    *,
    buyer_brief: dict[str, Any] | None,
    packs: list[dict[str, Any]],
) -> dict[str, Any]:
    brief = buyer_brief or {}
    primary = dict(brief.get("primary_motion") or {})
    if not primary:
        primary = {
            "label": "Pick value pack",
            "route": "/value-packs",
            "status": "watch",
            "ask": "Choose the role package that matches the buyer room.",
            "reason": "Value Packs turn feature depth into purchasable outcomes.",
        }

    first_ready = next((pack for pack in packs if pack.get("maturity") == "pilot-ready"), packs[0] if packs else {})
    value_motion = {
        "label": str(first_ready.get("title") or "Pick value pack"),
        "route": "/value-packs",
        "status": "ready" if packs else "watch",
        "ask": str(first_ready.get("price_story") or "Select the package that becomes the paid proof or rollout."),
        "reason": str(first_ready.get("outcome") or "The package connects role, outcome, proof and deliverables."),
    }

    role_cards = list(brief.get("role_cards") or [])
    if not role_cards:
        role_cards = [
            {
                "role": str(pack.get("id") or "pack"),
                "title": str(pack.get("title") or "Value pack"),
                "route": str((pack.get("routes") or [{"to": "/value-packs"}])[0].get("to") or "/value-packs"),
                "status": "ready" if pack.get("maturity") == "pilot-ready" else "watch",
                "spark": str(pack.get("outcome") or ""),
                "proof_file": "rentgen-value-packs.md",
            }
            for pack in packs[:5]
        ]

    proof_readiness = list(brief.get("proof_readiness") or [])
    if not proof_readiness:
        proof_readiness = [
            {
                "id": str(pack.get("id") or "pack"),
                "title": str(pack.get("title") or "Value pack"),
                "route": "/value-packs",
                "status": "ready" if pack.get("maturity") == "pilot-ready" else "watch",
                "signal": "; ".join(str(item) for item in (pack.get("proof_points") or [])[:2]),
                "file": "rentgen-value-packs.md",
            }
            for pack in packs[:4]
        ]

    meeting_flow = list(brief.get("meeting_flow") or [])
    if not meeting_flow:
        meeting_flow = [
            {"step": 1, "label": "Orient", "route": "/buyer-concierge", "line": "Pick the role or pain first."},
            {"step": 2, "label": "Package", "route": "/value-packs", "line": "Choose the role pack that becomes the paid scope."},
            {"step": 3, "label": "Price", "route": "/commercial-offer-studio", "line": "Convert the pack into offer and procurement language."},
            {"step": 4, "label": "Forward", "route": "/evidence-bundle", "line": "Attach buyer brief, value pack and proof files."},
        ]
    open_first_path = build_open_first_path(
        existing_path=brief.get("open_first_path"),
        proof_readiness=proof_readiness,
        primary=primary,
        meeting_flow=meeting_flow,
        source="value-packs-fallback",
        orient_title="Value Packs",
        orient_route="/value-packs",
        orient_line="Choose the role pack that becomes the paid scope.",
        orient_status=str(primary.get("status") or value_motion.get("status") or "watch"),
        prove_line="Show the package proof points that match the buyer role.",
        close_title="Commercial Offer",
        close_route="/commercial-offer-studio",
        close_line="Convert the pack into offer and procurement language.",
        close_file="rentgen-commercial-offer-studio.md",
        close_status=str(primary.get("status") or value_motion.get("status") or "watch"),
        verify_line="Attach buyer brief, value pack and proof files.",
    )

    routes = sorted(
        {
            "/value-packs",
            str(primary.get("route") or "/value-packs"),
            str(value_motion["route"]),
            *[str(route.get("to") or "") for pack in packs for route in pack.get("routes", [])],
            *[str(item.get("route") or "") for item in role_cards],
            *[str(item.get("route") or "") for item in proof_readiness],
            *[str(item.get("route") or "") for item in meeting_flow],
            *[str(item.get("route") or "") for item in open_first_path],
        }
        - {""}
    )
    return {
        "status": str(brief.get("purchase_status") or primary.get("status") or "watch"),
        "score": _int(brief.get("score"), 76),
        "source": str(brief.get("source") or "value-packs-derived"),
        "room_line": str(
            brief.get("room_line")
            or f"{primary.get('label', 'Pick value pack')}: {primary.get('ask', 'Choose package and prove it.')}"
        ),
        "primary_motion": {
            "label": str(primary.get("label") or "Pick value pack"),
            "route": str(primary.get("route") or "/value-packs"),
            "status": str(primary.get("status") or "watch"),
            "ask": str(primary.get("ask") or "Choose package and prove it."),
            "reason": str(primary.get("reason") or "Role packaging makes the product buyable."),
        },
        "value_motion": value_motion,
        "role_cards": role_cards[:5],
        "proof_readiness": proof_readiness[:4],
        "meeting_flow": meeting_flow[:4],
        "open_first_path": open_first_path[:4],
        "files": ["buyer-brief.md", "buyer-pulse.md", OPEN_FIRST_PATH_FILE, "rentgen-value-packs.md", "rentgen-commercial-offer-studio.md", "OPEN_FIRST.md"],
        "routes": routes,
        "close_question": "Which pack becomes the first paid proof, pilot or rollout?",
    }


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 1C Rentgen Value Packs",
        "",
        f"Generated: {report['generated_at']}",
        f"Status: **{report['decision']['status'].upper()}** / score **{report['decision']['score']}**",
        "",
        "## Packs",
        "",
    ]
    for pack in report["packs"]:
        lines.extend(
            [
                f"### {pack['title']}",
                "",
                f"Audience: **{pack['audience']}**",
                f"Outcome: {pack['outcome']}",
                f"Maturity: **{pack['maturity']}**",
                "",
                "Deliverables:",
            ]
        )
        lines.extend(f"- {item}" for item in pack["deliverables"])
        lines.extend(["", "Proof:"])
        lines.extend(f"- {item}" for item in pack["proof_points"])
        lines.extend(["", "Routes:"])
        lines.extend(f"- {item['label']}: `{item['to']}`" for item in pack["routes"])
        lines.append("")
    bridge = report.get("value_room_bridge") or {}
    if bridge:
        lines.extend(["## Value Room Bridge", ""])
        lines.append(f"- Source: **{bridge.get('source', 'n/a')}**; status **{bridge.get('status', 'watch')}** / score **{bridge.get('score', 0)}**")
        lines.append(f"- Room line: {bridge.get('room_line', '')}")
        motion = bridge.get("primary_motion") or {}
        lines.append(f"- Primary motion: **{motion.get('label', 'n/a')}** (`{motion.get('route', '/value-packs')}`): {motion.get('ask', '')}")
        value_motion = bridge.get("value_motion") or {}
        lines.append(f"- Value motion: **{value_motion.get('label', 'n/a')}** (`{value_motion.get('route', '/value-packs')}`): {value_motion.get('ask', '')}")
        lines.extend(open_first_path_markdown_lines(bridge.get("open_first_path"), default_route="/value-packs"))
        for item in bridge.get("role_cards", []):
            lines.append(f"- **{item.get('title', item.get('role', 'role'))}** `{item.get('route', '')}`: {item.get('spark', '')}")
        for item in bridge.get("proof_readiness", []):
            lines.append(f"- Proof **{item.get('title', 'proof')}** `{item.get('route', '')}` -> {item.get('file', '')}: {item.get('signal', '')}")
        for item in bridge.get("meeting_flow", []):
            lines.append(f"- Step {item.get('step', '')} **{item.get('label', 'step')}** `{item.get('route', '')}`: {item.get('line', '')}")
        lines.append("")
    lines.extend(["## Licensing story", "", report["licensing_story"]])
    return "\n".join(lines)


def build_value_packs(
    executive: dict[str, Any] | None = None,
    *,
    buyer_brief: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return role-oriented product packs that turn features into purchasable outcomes."""

    decision = (executive or {}).get("decision") or {}
    kpis = (executive or {}).get("kpis") or {}
    coverage = (executive or {}).get("coverage") or {}
    packs = [
        _pack(
            id="developer",
            title="Developer Pack",
            audience="1C developers and tech leads",
            outcome="Правка до коммита получает impact, риск, Query Surgeon и тестовый маршрут.",
            maturity="pilot-ready",
            routes=[
                {"label": "Scenario Hub", "to": "/scenario-hub"},
                {"label": "Change Impact", "to": "/change"},
                {"label": "Рентген качества", "to": "/quality"},
                {"label": "Тесты", "to": "/testing"},
            ],
            proof_points=[
                "LEFT JOIN поля без ЕстьNULL/ЕСТЬ NULL ловятся детерминированным rule_id.",
                f"High-risk hotspots: {((executive or {}).get('risk_summary') or {}).get('high_hotspots', 0)}",
                "Impact caveats не превращаются в ложный безопасный ноль.",
            ],
            deliverables=[
                "Impact report по changed modules/diff.",
                "Standards findings и безопасные варианты исправления.",
                "Affected tests / missing tests для QA.",
            ],
            price_story="Покупается как ускорение ревью и снижение регрессий, не как токены генерации кода.",
        ),
        _pack(
            id="architect",
            title="Architect Pack",
            audience="Architects and solution owners",
            outcome="Конфигурация видна как система: метаданные, граф, права, обновление и blast radius.",
            maturity="pilot-ready",
            routes=[
                {"label": "Архитектура", "to": "/architecture"},
                {"label": "Scenario Hub", "to": "/scenario-hub"},
                {"label": "Update War Room", "to": "/update-war-room"},
                {"label": "Rights/RLS", "to": "/rights-rls"},
            ],
            proof_points=[
                f"Call graph edges: {kpis.get('call_edges', 0)}",
                f"Red areas: {kpis.get('red_areas', 0)}",
                "Update War Room связывает платформу, расширения, impact, тесты и rollback.",
            ],
            deliverables=[
                "Architecture/risk map by module and metadata surface.",
                "Update/upgrade war-room plan.",
                "Security rights gate для affected ролей.",
            ],
            price_story="Покупается как контроль архитектурного долга и обновлений, а не как IDE-плагин.",
        ),
        _pack(
            id="release-qa",
            title="Release / QA Pack",
            audience="QA, release managers and directors",
            outcome="Релиз перестает быть верой: go/no-go, тесты, evidence, права и rollback.",
            maturity="pilot-ready",
            routes=[
                {"label": "Scenario Hub", "to": "/scenario-hub"},
                {"label": "Guided Demo", "to": "/guided-demo"},
                {"label": "Release Readiness", "to": "/release-readiness"},
                {"label": "Business Case", "to": "/business-case"},
                {"label": "Testing", "to": "/testing"},
                {"label": "Evidence Bundle", "to": "/evidence-bundle"},
            ],
            proof_points=[
                f"Review queue: {kpis.get('review_queue', 0)}",
                f"Coverage score: {coverage.get('score', kpis.get('coverage_score', 'n/a'))}",
                "No release page says pass when impacted tests are unknown.",
            ],
            deliverables=[
                "Release gate report.",
                "Affected test matrix and missing tests.",
                "Markdown evidence для approval.",
            ],
            price_story="Покупается как страхование релизного окна и управляемая доказательная база.",
        ),
        _pack(
            id="platform",
            title="Platform Doctor Pack",
            audience="Operations, architects and platform owners",
            outcome="Платформа, совместимость, СУБД, техжурнал, OpenMetrics и upgrade checklist в одном месте.",
            maturity="pilot-ready",
            routes=[
                {"label": "Scenario Hub", "to": "/scenario-hub"},
                {"label": "Platform Doctor", "to": "/platform-doctor"},
                {"label": "Lock Radar", "to": "/lock-radar"},
                {"label": "Extension Safety", "to": "/extension-safety"},
                {"label": "Update War Room", "to": "/update-war-room"},
            ],
            proof_points=[
                "Unknown platform facts are warnings, not green status.",
                "Lock Radar turns TLOCK/TTIMEOUT/TDEADLOCK into release and runbook actions.",
                "Extension Safety separates CFE/borrowed-object risk from the typical configuration update.",
                "OpenMetrics/tech journal/license signals are explicit env/file facts.",
                f"Offline score: {kpis.get('offline_score', 0)}%",
            ],
            deliverables=[
                "Platform readiness report.",
                "Lock/deadlock radar with affected modules and test gaps.",
                "Extension inventory with rights, hooks, borrowed objects and impact.",
                "Upgrade checklist and caveats.",
                "Ops/runbook signals for incident and rollback.",
            ],
            price_story="Покупается как снижение риска платформенного обновления и аварийного окна.",
        ),
        _pack(
            id="vendor",
            title="Vendor Portfolio Pack",
            audience="Franchisees, vendors and pre-sale teams",
            outcome="Клиентский аудит превращается в пакет работ: риск, платформа, подключение, релизный gate.",
            maturity="pilot-ready",
            routes=[
                {"label": "Scenario Hub", "to": "/scenario-hub"},
                {"label": "Guided Demo", "to": "/guided-demo"},
                {"label": "Vendor Portfolio", "to": "/vendor-portfolio"},
                {"label": "Business Case", "to": "/business-case"},
                {"label": "Evidence Bundle", "to": "/evidence-bundle"},
                {"label": "Конфигурации", "to": "/configurations"},
            ],
            proof_points=[
                "Pre-sale audit pack собирается из локальных evidence.",
                "Commercial signals are work-package signals, not token spend.",
                f"Modules with issues: {kpis.get('modules_with_issues', 0)}",
            ],
            deliverables=[
                "Markdown audit report для КП/письма клиенту.",
                "Work packages и next actions.",
                "Caveats по покрытию, платформе и source intake.",
            ],
            price_story="Покупается как источник выручки партнера: audit → проект → сопровождение.",
        ),
        _pack(
            id="enterprise-offline",
            title="Enterprise Offline Pack",
            audience="CIO, security and enterprise IT",
            outcome="Локальный контур, IAM/governance/audit/offline readiness без обязательной облачной AI-подписки.",
            maturity="beta",
            routes=[
                {"label": "Scenario Hub", "to": "/scenario-hub"},
                {"label": "Guided Demo", "to": "/guided-demo"},
                {"label": "Offline", "to": "/offline-readiness"},
                {"label": "Productization", "to": "/productization"},
                {"label": "Evidence Bundle", "to": "/evidence-bundle"},
                {"label": "Governance", "to": "/team-governance"},
            ],
            proof_points=[
                "Core analysis works from local SQLite and files.",
                "External/cloud AI is optional; deterministic fallback remains useful.",
                "Dev/protected APIs use real JWT in local demo mode.",
            ],
            deliverables=[
                "Offline readiness report.",
                "Governance/audit controls.",
                "Deployment and evidence checklist.",
            ],
            price_story="Покупается как on-prem актив/лицензия, AI credits остаются optional add-on.",
            caveats=["Enterprise hardening still needs installer/SBOM/signed offline bundle work."],
        ),
    ]
    mature = sum(1 for pack in packs if pack["maturity"] == "pilot-ready")
    score = round(mature / len(packs) * 100)
    value_room_bridge = _value_room_bridge(buyer_brief=buyer_brief, packs=packs)
    report: dict[str, Any] = {
        "generated_at": _now(),
        "decision": {
            "status": "ready" if score >= 80 else "watch",
            "score": score,
            "headline": "Пакеты превращают страницы продукта в понятные покупаемые outcomes.",
        },
        "summary": {
            "packs": len(packs),
            "pilot_ready": mature,
            "beta": sum(1 for pack in packs if pack["maturity"] == "beta"),
            "executive_score": decision.get("score"),
            "coverage_score": coverage.get("score", kpis.get("coverage_score")),
            "value_room_roles": len(value_room_bridge["role_cards"]),
            "value_room_proofs": len(value_room_bridge["proof_readiness"]),
            "value_room_steps": len(value_room_bridge["meeting_flow"]),
            "value_room_open_first": len(value_room_bridge["open_first_path"]),
        },
        "packs": packs,
        "value_room_bridge": value_room_bridge,
        "licensing_story": (
            "Базовая продажа: installation/configuration/portfolio license. "
            "Локальный анализ, reports, gates and evidence are not tied to token burn. "
            "External AI credits are optional only when customer explicitly enables cloud/external AI."
        ),
        "caveats": [
            "Value Packs v1 is packaging over implemented local capabilities; it is not a billing engine yet.",
            "Pack maturity is honest: beta packs require enterprise installer/SBOM/offline bundle hardening.",
        ],
    }
    report["markdown"] = _markdown(report)
    return report
