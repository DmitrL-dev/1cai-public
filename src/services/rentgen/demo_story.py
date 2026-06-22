"""Role-oriented demo story and reports for the 1C Rentgen cockpit."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.services.rentgen.coverage_ledger import build_coverage_ledger

DEMO_CHANGED_MODULE = "CommonModules/СводнаяТаблицаУХ/Ext/Module.bsl"

ROLE_TITLES = {
    "developer": "Отчет для разработчика",
    "architect": "Отчет для архитектора",
    "director": "Отчет для директора",
    "qa": "Отчет для QA и релиза",
    "ops": "Отчет для эксплуатации",
    "vendor": "Отчет для вендора / франчайзи",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _route(path: str) -> str:
    return path


def _top_module(executive: dict[str, Any]) -> str:
    risks = (executive.get("risk_summary") or {}).get("top_risks") or []
    for item in risks:
        module = item.get("module_path")
        if module:
            return str(module)
    return DEMO_CHANGED_MODULE


def _status_tone(status: str | None) -> str:
    if status in {"ready", "pass", "ok"}:
        return "ok"
    if status in {"critical", "blocked", "fail"}:
        return "danger"
    return "warn"


def _role_report(
    role: str, executive: dict[str, Any], changed_module: str
) -> dict[str, Any]:
    decision = executive.get("decision") or {}
    kpis = executive.get("kpis") or {}
    risk = executive.get("risk_summary") or {}
    coverage = executive.get("coverage") or {}
    offline = executive.get("offline") or {}
    actions = executive.get("manager_actions") or []
    top_risks = risk.get("top_risks") or []
    top = top_risks[0] if top_risks else {}

    templates: dict[str, dict[str, Any]] = {
        "developer": {
            "headline": "Проверить правку до коммита: impact, запрос, тесты и caveat в одном месте.",
            "proof_points": [
                f"Модуль для demo: {changed_module}",
                f"High-risk hotspots: {risk.get('high_hotspots', 0)}",
                "Query Surgeon показывает LEFT JOIN-поля без ЕстьNULL как риск неверного результата.",
                "Test Factory строит матрицу exact/planned/gap вместо ручного спора о регрессии.",
            ],
            "next_actions": [
                {"label": "Проверить правку", "to": _route("/change")},
                {"label": "Открыть тесты", "to": _route("/testing")},
                {"label": "Стандарты кода", "to": _route("/quality")},
            ],
            "status": "watch" if risk.get("high_hotspots") else "ready",
        },
        "architect": {
            "headline": "Увидеть blast radius как систему: модули, метаданные, требования и границы.",
            "proof_points": [
                f"Ребер графа вызовов: {kpis.get('call_edges', 0)}",
                f"Красных зон: {kpis.get('red_areas', 0)}",
                f"Самый заметный риск: {top.get('module_path', changed_module)}",
                "Неполное покрытие не маскируется под нулевой impact.",
            ],
            "next_actions": [
                {"label": "Архитектура", "to": _route("/architecture")},
                {"label": "Extensions", "to": _route("/extension-safety")},
                {"label": "Метаданные", "to": _route("/metadata")},
            ],
            "status": "risk" if kpis.get("red_areas") else "ready",
        },
        "director": {
            "headline": "Получить go/no-go без технического погружения и увидеть, что именно снижает риск.",
            "proof_points": [
                f"Решение: {decision.get('status', 'unknown')} / score {decision.get('score', 0)}",
                f"Очередь ревью: {kpis.get('review_queue', 0)}",
                f"Покрытие продуктового контура: {coverage.get('score', 'n/a')}%",
                "Локальный контур снижает зависимость от вечной AI-подписки и утечки кода.",
            ],
            "next_actions": [
                {"label": "Business Case", "to": _route("/business-case")},
                {"label": "Релизное решение", "to": _route("/release-readiness")},
                {"label": "Evidence bundle", "to": _route("/evidence-bundle")},
            ],
            "status": decision.get("status", "watch"),
        },
        "qa": {
            "headline": "Превратить изменение в доказательный тест-план и релизный gate.",
            "proof_points": [
                "Матрица тестов разделяет exact tests, planned selectors и gaps.",
                "Release Readiness связывает diff/modules с impact, формами, правами и actions.",
                f"Gate policy: {decision.get('release_policy', 'red areas block release')}",
                "Отчет можно приложить к approval без внешнего AI.",
            ],
            "next_actions": [
                {"label": "Матрица тестов", "to": _route("/testing")},
                {"label": "Релиз", "to": _route("/release-readiness")},
                {"label": "Evidence", "to": _route("/evidence-bundle")},
            ],
            "status": "watch",
        },
        "ops": {
            "headline": "Связать инцидент, релиз, код, платформу и offline-готовность.",
            "proof_points": [
                f"Offline score: {kpis.get('offline_score', 0)}%",
                f"Runtime profile: {(offline.get('runtime') or {}).get('environment', 'local')}",
                "Operations page собирает incident report с evidence и next actions.",
                "Platform/ops caveats видны отдельно от бизнес-решения по релизу.",
            ],
            "next_actions": [
                {"label": "Инциденты", "to": _route("/operations")},
                {"label": "Lock Radar", "to": _route("/lock-radar")},
                {"label": "Платформа", "to": _route("/platform-doctor")},
            ],
            "status": "ready" if int(kpis.get("offline_score") or 0) >= 90 else "watch",
        },
        "vendor": {
            "headline": "Собрать pre-sale аудит клиента: риск, обновление, тесты, права, поставка.",
            "proof_points": [
                f"Модулей в анализе: {kpis.get('modules', 0)}",
                f"Модулей с проблемами: {kpis.get('modules_with_issues', 0)}",
                "Vendor report переводит техдолг в понятные работы и коммерческий next step.",
                "Demo работает в закрытом контуре и показывает ценность без отправки кода наружу.",
            ],
            "next_actions": [
                {"label": "Портфель клиента", "to": _route("/vendor-portfolio")},
                {"label": "Business Case", "to": _route("/business-case")},
                {"label": "Evidence bundle", "to": _route("/evidence-bundle")},
                {"label": "Пакеты продукта", "to": _route("/value-packs")},
            ],
            "status": "ready",
        },
    }
    payload = templates.get(role, templates["director"])
    markdown = _render_role_markdown(role, payload, executive)
    return {
        "role": role,
        "title": ROLE_TITLES.get(role, ROLE_TITLES["director"]),
        "status": payload["status"],
        "tone": _status_tone(str(payload["status"])),
        "headline": payload["headline"],
        "proof_points": payload["proof_points"],
        "next_actions": payload["next_actions"],
        "markdown": markdown,
        "download_name": f"rentgen-{role}-report.md",
    }


def _render_role_markdown(
    role: str, payload: dict[str, Any], executive: dict[str, Any]
) -> str:
    decision = executive.get("decision") or {}
    lines = [
        f"# {ROLE_TITLES.get(role, ROLE_TITLES['director'])}",
        "",
        f"Status: **{payload['status']}**",
        f"Executive score: **{decision.get('score', 0)}**",
        "",
        "## Главное",
        "",
        payload["headline"],
        "",
        "## Доказательства",
        "",
    ]
    lines.extend(f"- {item}" for item in payload["proof_points"])
    lines.extend(["", "## Дальше", ""])
    lines.extend(
        f"- {item['label']}: `{item['to']}`" for item in payload["next_actions"]
    )
    return "\n".join(lines)


def _demo_markdown(story: dict[str, Any]) -> str:
    lines = [
        "# 1С:Рентген Demo Story",
        "",
        f"Scenario: **{story['scenario']['title']}**",
        f"Generated: {story['generated_at']}",
        "",
        "## First Value",
        "",
    ]
    for item in story["first_value"]:
        lines.append(f"- **{item['title']}**: {item['value']} — {item['why']}")
    lines.extend(["", "## Demo Steps", ""])
    for item in story["demo_steps"]:
        lines.append(
            f"- **{item['title']}** ({item['role']}, {item['minutes']} min): {item['evidence']}"
        )
    lines.extend(["", "## Role Reports", ""])
    for report in story["role_reports"]:
        lines.append(f"- {report['title']}: {report['headline']}")
    ledger = story.get("coverage_ledger") or {}
    if ledger:
        summary = ledger.get("summary") or {}
        lines.extend(["", "## Coverage Ledger", ""])
        lines.append(
            f"- Status: **{ledger.get('status', 'unknown')}** / score **{ledger.get('score', 0)}**"
        )
        lines.append(
            f"- Measured: {summary.get('measured', 0)}/{summary.get('items', 0)}; caveats: {summary.get('caveats', 0)}"
        )
    return "\n".join(lines)


def build_demo_story(executive: dict[str, Any]) -> dict[str, Any]:
    """Build a complete role-oriented demo story from live deterministic signals."""

    decision = executive.get("decision") or {}
    kpis = executive.get("kpis") or {}
    risk = executive.get("risk_summary") or {}
    coverage = executive.get("coverage") or {}
    changed_module = _top_module(executive)
    coverage_ledger = build_coverage_ledger(executive=executive)
    role_reports = [
        _role_report(role, executive, changed_module)
        for role in ("developer", "architect", "director", "qa", "ops", "vendor")
    ]

    story = {
        "generated_at": _now(),
        "mode": "live-demo",
        "scenario": {
            "id": "erp-slow-order-safe-release",
            "title": "ERP: тормозящий заказ, опасный LEFT JOIN и релизное решение",
            "subtitle": "Одна история показывает разработчику, архитектору и директору разные ответы на один риск.",
            "configuration": "1C ERP / UH style configuration",
            "setup_minutes": 5,
            "coverage": {
                "status": "partial"
                if int(coverage.get("score") or 0) < 100
                else "ready",
                "score": coverage.get("score"),
                "caveat": "Неполные источники показываются как caveat; impact не превращается в безопасный ноль.",
            },
        },
        "first_value": [
            {
                "title": "Можно выпускать?",
                "value": f"{decision.get('status', 'unknown')} / {decision.get('score', 0)}",
                "tone": _status_tone(str(decision.get("status"))),
                "why": decision.get("headline")
                or "Release decision is built from local evidence.",
                "next_action": "Открыть релизное решение",
                "to": _route("/release-readiness"),
            },
            {
                "title": "Где риск?",
                "value": f"{risk.get('high_hotspots', 0)} high-risk hotspots",
                "tone": "danger" if risk.get("high_hotspots") else "ok",
                "why": f"Top module: {changed_module}",
                "next_action": "Открыть Рентген качества",
                "to": _route("/quality"),
            },
            {
                "title": "Что проверить?",
                "value": "impact + tests + caveats",
                "tone": "warn",
                "why": "Изменение превращается в blast radius и тестовый план.",
                "next_action": "Проверить изменение",
                "to": _route("/change"),
            },
            {
                "title": "Почему это локальный актив?",
                "value": "offline-first",
                "tone": "ok",
                "why": "Граф, правила, отчеты и evidence работают без отправки кода в облако.",
                "next_action": "Проверить offline",
                "to": _route("/offline-readiness"),
            },
        ],
        "pain_map": [
            {
                "role": "Разработчик",
                "pain": "Не видно, что сломает маленькая правка.",
                "proof": "Impact Oracle показывает affected modules, hotspots, tests и caveats.",
                "action": "Проверить правку",
                "to": _route("/change"),
            },
            {
                "role": "Архитектор",
                "pain": "Конфигурация выглядит как дерево, а не как система.",
                "proof": "Configuration Genome связывает модули, метаданные и требования.",
                "action": "Открыть архитектуру",
                "to": _route("/architecture"),
            },
            {
                "role": "Директор",
                "pain": "Релизное решение зависит от ручной экспертизы.",
                "proof": "Go/no-go строится из локальных evidence, gates и owner queue.",
                "action": "Собрать отчет",
                "to": _route("/release-readiness"),
            },
        ],
        "query_surgeon_case": {
            "title": "LEFT JOIN без ЕстьNULL",
            "problem": "Поле из левого соединения используется как обычное значение; при отсутствии строки результат становится NULL/Неопределено.",
            "unsafe_pattern": "ЛЕВОЕ СОЕДИНЕНИЕ ... КАК Скидки; ВЫБРАТЬ Скидки.Процент",
            "safe_options": [
                "обернуть поле: ЕстьNULL(Скидки.Процент, 0)",
                "добавить явную проверку: Скидки.Процент ЕСТЬ NULL",
                "заменить на внутреннее соединение, если отсутствие строки недопустимо по бизнес-правилу",
            ],
            "evidence": "Детерминированное правило standards-review/query-surgeon, без LLM.",
            "test": "Поведенческий тест: заказ без скидки должен дать 0, а не NULL.",
        },
        "demo_steps": [
            {
                "id": "open-home",
                "title": "Открыть рабочий пульт",
                "role": "all",
                "minutes": 0.5,
                "to": _route("/"),
                "evidence": "Роль, score, top risks и быстрые входы видны сразу.",
            },
            {
                "id": "guided-demo",
                "title": "Open the buyer-guided route",
                "role": "all",
                "minutes": 0.5,
                "to": _route("/guided-demo"),
                "evidence": "Guided Demo turns product surfaces into one buyer path: role proof, money map, productization and evidence close.",
            },
            {
                "id": "developer-impact",
                "title": "Проверить правку разработчика",
                "role": "developer",
                "minutes": 1,
                "to": _route("/change"),
                "evidence": "impact_measured/coverage_caveat не дают принять неизвестность за ноль.",
            },
            {
                "id": "query-surgeon",
                "title": "Показать ошибку LEFT JOIN",
                "role": "developer",
                "minutes": 1,
                "to": _route("/quality"),
                "evidence": "Есть конкретный rule_id, строка и безопасные варианты fix.",
            },
            {
                "id": "architect-map",
                "title": "Показать архитектурный blast radius",
                "role": "architect",
                "minutes": 1,
                "to": _route("/architecture"),
                "evidence": f"Граф вызовов: {kpis.get('call_edges', 0)} ребер.",
            },
            {
                "id": "lock-radar",
                "title": "Разобрать блокировки по технологическому журналу",
                "role": "ops",
                "minutes": 1,
                "to": _route("/lock-radar"),
                "evidence": "TLOCK, TTIMEOUT и TDEADLOCK превращаются в риск, затронутые модули, тестовые gaps и runbook.",
            },
            {
                "id": "platform-doctor",
                "title": "Проверить обновление платформы",
                "role": "ops",
                "minutes": 1,
                "to": _route("/platform-doctor"),
                "evidence": "Версия, совместимость, СУБД, техжурнал и OpenMetrics превращаются в checklist.",
            },
            {
                "id": "update-war-room",
                "title": "Собрать план обновления",
                "role": "architect",
                "minutes": 1,
                "to": _route("/update-war-room"),
                "evidence": "Платформа, расширения, impact, тесты, rollback и evidence становятся одним war-room планом.",
            },
            {
                "id": "extension-safety",
                "title": "Проверить расширения перед обновлением",
                "role": "architect",
                "minutes": 1,
                "to": _route("/extension-safety"),
                "evidence": "CFE/EDT-расширения показывают права, привилегированный режим, write hooks, borrowed objects, impact и gaps.",
            },
            {
                "id": "director-go-no-go",
                "title": "Собрать go/no-go для директора",
                "role": "director",
                "minutes": 1,
                "to": _route("/release-readiness"),
                "evidence": decision.get("headline")
                or "Release decision is available.",
            },
            {
                "id": "rights-rls",
                "title": "Проверить security gate по правам",
                "role": "qa",
                "minutes": 1,
                "to": _route("/rights-rls"),
                "evidence": "Роли, объекты, опасные права и RLS caveats становятся release/security gate.",
            },
            {
                "id": "vendor-audit",
                "title": "Собрать pre-sale audit pack",
                "role": "vendor",
                "minutes": 0.5,
                "to": _route("/vendor-portfolio"),
                "evidence": "Vendor Portfolio соединяет risk audit, platform readiness, intake и релизный gate в пакет работ.",
            },
            {
                "id": "value-packs",
                "title": "Показать покупаемые пакеты",
                "role": "director",
                "minutes": 0.5,
                "to": _route("/value-packs"),
                "evidence": "Value Packs объясняют продукт через outcomes, deliverables, routes и licensing story без токенной зависимости.",
            },
            {
                "id": "business-case",
                "title": "Build the buyer business case",
                "role": "director",
                "minutes": 0.5,
                "to": _route("/business-case"),
                "evidence": "Business Case connects local evidence, money levers, objections, buyer roles and 30/60/90 rollout.",
            },
            {
                "id": "evidence-bundle",
                "title": "Собрать evidence bundle",
                "role": "director",
                "minutes": 0.5,
                "to": _route("/evidence-bundle"),
                "evidence": "JSON/Markdown артефакты получают SHA-256 manifest для approval, КП и внутреннего аудита.",
            },
        ],
        "role_reports": role_reports,
        "coverage_ledger": coverage_ledger,
    }
    story["export"] = {
        "markdown": _demo_markdown(story),
        "download_name": "rentgen-demo-story.md",
    }
    return story


def build_role_report(role: str, executive: dict[str, Any]) -> dict[str, Any]:
    """Return a single role report; unknown roles fall back to director."""

    normalized = role.strip().lower().replace("-", "_")
    aliases = {
        "руководитель": "director",
        "director": "director",
        "manager": "director",
        "dev": "developer",
        "developer": "developer",
        "architect": "architect",
        "архитектор": "architect",
        "qa": "qa",
        "release": "qa",
        "ops": "ops",
        "operations": "ops",
        "vendor": "vendor",
        "franchisee": "vendor",
    }
    return _role_report(
        aliases.get(normalized, "director"), executive, _top_module(executive)
    )
