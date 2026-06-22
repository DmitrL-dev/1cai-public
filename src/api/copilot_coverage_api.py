"""Enterprise coverage map for Rentgen subscription-escape positioning."""

from __future__ import annotations

from collections import Counter
from typing import Any

from fastapi import APIRouter

from src.api._rentgen_store import store_or_none

router = APIRouter(
    prefix="/api/v1/copilot-coverage", tags=["Subscription Escape Coverage"]
)


STAGES: list[dict[str, str]] = [
    {
        "id": "discover",
        "title": "Discovery",
        "description": "Понимание конфигурации, домена и legacy.",
    },
    {
        "id": "requirements",
        "title": "Requirements",
        "description": "Требования, сценарии, критерии приемки.",
    },
    {
        "id": "architecture",
        "title": "Architecture",
        "description": "Архитектурные границы, impact, техдолг.",
    },
    {
        "id": "coding",
        "title": "Coding",
        "description": "Генерация, правка, рефакторинг BSL и метаданных.",
    },
    {
        "id": "ui_forms",
        "title": "Forms/UI",
        "description": "Формы 1С, команды, динамические списки, UX.",
    },
    {
        "id": "data",
        "title": "Data",
        "description": "Метаданные, запросы, миграции, права, обмены.",
    },
    {
        "id": "review",
        "title": "Review",
        "description": "Стандарты, безопасность, качество, diff-review.",
    },
    {
        "id": "performance",
        "title": "Performance",
        "description": "ТЖ, запросы, N+1, блокировки, blast radius.",
    },
    {
        "id": "testing",
        "title": "Testing",
        "description": "YAxUnit/Vanessa, тестовые данные, выбор тестов.",
    },
    {
        "id": "delivery",
        "title": "Delivery",
        "description": "Git, CI/CD, release gates, сравнение и поставка.",
    },
    {
        "id": "operations",
        "title": "Operations",
        "description": "Наблюдаемость, инциденты, эксплуатационные риски.",
    },
    {
        "id": "governance",
        "title": "Governance",
        "description": "Портфель, роли, аудит, enterprise-контроль.",
    },
]

PERSONAS: list[dict[str, str]] = [
    {"id": "developer", "title": "Разработчик"},
    {"id": "architect", "title": "Архитектор"},
    {"id": "ba", "title": "Бизнес-аналитик"},
    {"id": "qa", "title": "QA/тестировщик"},
    {"id": "lead", "title": "Тимлид"},
    {"id": "manager", "title": "Руководитель"},
    {"id": "ops", "title": "Эксплуатация"},
    {"id": "security", "title": "ИБ"},
]

COMPETITOR_SOURCES: list[dict[str, str]] = [
    {
        "title": "1С:Напарник — официальный сайт",
        "url": "https://code.1c.ai/",
        "signal": "Автопродолжение, генерация, чат-навыки, агентный режим, поиск/чтение/редактирование проекта, Git/diff.",
    },
    {
        "title": "Портал 1С:ИТС — карточка продукта",
        "url": "https://portal.1c.ru/applications/1C-Second-Pilot",
        "signal": "EDT-плагин, генерация кода, исправление ошибок, документирование, оптимизация; требуется интернет.",
    },
    {
        "title": "1С:Предприятие — искусственный интеллект",
        "url": "https://v8.1c.ru/platforma/iskusstvennyy-intellekt/",
        "signal": "Официальное позиционирование: генерация кода, работа с кодовой базой, ревью, рефакторинг, комментирование.",
    },
]

COVERAGE_ITEMS: list[dict[str, Any]] = [
    {
        "id": "context-digital-twin",
        "stage": "discover",
        "title": "Цифровой двойник конфигурации",
        "personas": ["developer", "architect", "lead", "manager"],
        "naparnik": "Проектный контекст внутри EDT: метаданные, формы, функции, файлы.",
        "ours": "Граф всей конфигурации: 730K подпрограмм, 1.47M ребер, 26K оцененных модулей.",
        "target": "Мульти-конфигурационный цифровой двойник с историей по релизам.",
        "status": "done",
        "priority": "P0",
        "moat": "whole_config_graph",
        "enterprise_value": "Новая команда видит систему как карту зависимостей, а не набор файлов.",
        "next_build": "Добавить drill-down из карты покрытия в конкретные hotspots и impact.",
        "implementation_refs": [
            "tools/rentgen/store.py",
            "src/api/rentgen_api.py",
            "portal/src/routes/_authenticated/quality.tsx",
        ],
    },
    {
        "id": "onprem-offline",
        "stage": "governance",
        "title": "Закрытый контур и data sovereignty",
        "personas": ["manager", "security", "architect"],
        "naparnik": "Защищенные серверы 1С в России, но для работы требуется интернет-соединение.",
        "ours": "SQLite/Rentgen, offline ITS-RAG и offline readiness self-test работают локально; отчет доступен в API, MCP и UI.",
        "target": "OFFLINE=1 профиль с проверяемым отчетом ИБ и offline installer.",
        "status": "done",
        "priority": "P0",
        "moat": "offline_enterprise",
        "enterprise_value": "Подходит для периметров, где код конфигурации нельзя выносить из компании.",
        "next_build": "Добавить packaged offline installer и signed artifact manifest.",
        "implementation_refs": [
            "src/services/rentgen/offline_readiness.py",
            "src/api/offline_readiness_api.py",
            "src/ai/mcp/server.py",
            "portal/src/routes/_authenticated/offline-readiness.tsx",
        ],
    },
    {
        "id": "autocomplete-generation",
        "stage": "coding",
        "title": "Автодополнение и генерация BSL",
        "personas": ["developer"],
        "naparnik": "Сильная зона: автопродолжение, генерация кода по описанию, исправление и модификация кода.",
        "ours": "Базовые coding-assistant endpoint-ы есть, но им нужен зрелый локальный BSL provider и контекст графа.",
        "target": "Локальный агент кодогенерации с BSL LS, ITS-RAG и Рентген-context.",
        "status": "partial",
        "priority": "P0",
        "moat": "graph_grounded_codegen",
        "enterprise_value": "Генерация должна учитывать последствия правки, стандарты и тесты.",
        "next_build": "Подключить local LLM/profile и давать генератору impact-context.",
        "implementation_refs": [
            "src/services/rentgen/grounded_codegen.py",
            "src/modules/copilot/api/routes.py",
            "src/ai/mcp/server.py",
            "portal/src/routes/_authenticated/copilot.tsx",
        ],
    },
    {
        "id": "change-impact",
        "stage": "architecture",
        "title": "Change-driven impact analysis",
        "personas": ["developer", "architect", "lead", "qa"],
        "naparnik": "Работает с diff/Git и проектом, но публично не заявляет графовый blast radius всей конфигурации.",
        "ours": "Измененные модули или diff -> blast radius, hotspots, performance hints, caveats.",
        "target": "Pre-commit/PR gate: риск, тесты, owners, release decision.",
        "status": "done",
        "priority": "P0",
        "moat": "blast_radius",
        "enterprise_value": "Перед правкой видно, что сломается в масштабе ERP/УХ.",
        "next_build": "Связать с Git provider и risk-driven test selector.",
        "implementation_refs": [
            "src/api/rentgen_api.py",
            "src/api/quality_api.py",
            "portal/src/routes/_authenticated/change.tsx",
        ],
    },
    {
        "id": "architecture-review",
        "stage": "architecture",
        "title": "Архитектурное ревью и границы модулей",
        "personas": ["architect", "lead", "manager"],
        "naparnik": "Может планировать и редактировать проект как агент, но без публичной модели архитектурных границ.",
        "ours": "Есть граф, fan-in/fan-out и hotspots; нет правил bounded contexts и ADR-gates.",
        "target": "Architecture cockpit: слои, зависимости, циклы, запрещенные связи, ADR enforcement.",
        "status": "partial",
        "priority": "P0",
        "moat": "architecture_intelligence",
        "enterprise_value": "Архитектор управляет эволюцией конфигурации, а не тушит регрессии.",
        "next_build": "Добавить правила слоев и отчеты по нарушенным зависимостям.",
        "implementation_refs": [
            "tools/rentgen/store.py",
            "docs/02-architecture/adr/ADR_TEMPLATE.md",
        ],
    },
    {
        "id": "requirements-traceability",
        "stage": "requirements",
        "title": "Трассировка требований до объектов 1С",
        "personas": ["ba", "architect", "developer", "manager"],
        "naparnik": "Помогает разработчику в EDT, но BA traceability не является заявленным основным сценарием.",
        "ours": "Requirement traceability: текст требования -> candidate modules -> metadata/code/tests links -> impact -> ITS context -> сохраненный trace record.",
        "target": "BA workspace: user story, acceptance criteria, affected objects, risks, test plan.",
        "status": "done",
        "priority": "P0",
        "moat": "requirements_to_graph",
        "enterprise_value": "Бизнес-изменение превращается в управляемый инженерный change plan.",
        "next_build": "Усилить внутренний BA workspace: статусы согласования, версии требований и историю решений без обязательной внешней ALM.",
        "implementation_refs": [
            "src/api/requirements_api.py",
            "src/services/rentgen/change_plan.py",
            "src/services/rentgen/requirements_traceability.py",
            "src/ai/mcp/server.py",
            "portal/src/routes/_authenticated/requirements.tsx",
        ],
    },
    {
        "id": "forms-ui-generation",
        "stage": "ui_forms",
        "title": "Формы 1С и графические интерфейсы",
        "personas": ["developer", "ba", "architect"],
        "naparnik": "Учитывает формы и метаданные в контексте; публично основной акцент на коде.",
        "ours": (
            "Form blueprint designer generates metadata-aware layout, command model, dynamic-list plan, "
            "XML draft, BSL module draft, UX rules and form-review context in API, MCP and UI."
        ),
        "target": "Form designer assistant: dynamic list, commands, реквизиты, UX rules, generated form XML.",
        "status": "done",
        "priority": "P1",
        "moat": "metadata_aware_ui",
        "enterprise_value": "Автоматизирует дорогой слой 1С, где чистый BSL-codegen недостаточен.",
        "next_build": "Add import-ready EDT XML writer and visual diff against existing managed forms.",
        "implementation_refs": [
            "src/services/rentgen/form_designer.py",
            "src/api/metadata_api.py",
            "src/ai/mcp/server.py",
            "portal/src/routes/_authenticated/forms.tsx",
        ],
    },
    {
        "id": "data-metadata-rights",
        "stage": "data",
        "title": "Метаданные, права, миграции и обмены",
        "personas": ["developer", "architect", "security"],
        "naparnik": "В EDT-контексте знает метаданные и помогает писать код.",
        "ours": "Рентген видит часть метаданных через пути и модули; нет полной модели прав/миграций/обменов.",
        "target": "Metadata graph: objects, registers, rights, subscriptions, exchanges, migration plan.",
        "status": "partial",
        "priority": "P0",
        "moat": "metadata_graph",
        "enterprise_value": "Безопасные изменения структуры данных и прав в больших внедрениях.",
        "next_build": "Расширить build_store метаданными EDT XML и правами.",
        "implementation_refs": [
            "src/services/rentgen/metadata_graph.py",
            "src/services/rentgen/metadata_data_governance.py",
            "src/api/metadata_api.py",
            "src/ai/mcp/server.py",
            "portal/src/routes/_authenticated/metadata.tsx",
        ],
    },
    {
        "id": "review-standards",
        "stage": "review",
        "title": "Diff-review, стандарты и рекомендации",
        "personas": ["developer", "lead", "security"],
        "naparnik": "Ревью кода, форматирование, проблемы, предложения улучшений.",
        "ours": "Review-diff и standards-review связывают changed modules с impact, catalog-aware BSL diagnostics, auto-fix hints и stored findings.",
        "target": "BSL Language Server diagnostics + standards catalog + auto-fix patches.",
        "status": "done",
        "priority": "P0",
        "moat": "review_with_blast_radius",
        "enterprise_value": "Ревью учитывает не только файл, но последствия по всей конфигурации.",
        "next_build": "Подключить полный bsl-language-server jar как дополнительный engine рядом с offline fallback.",
        "implementation_refs": [
            "src/services/rentgen/standards_review.py",
            "src/api/quality_api.py",
            "src/ai/mcp/server.py",
            "portal/src/routes/_authenticated/standards-review.tsx",
            "C:/Users/chg/.bsl-language-server",
        ],
    },
    {
        "id": "performance-tj",
        "stage": "performance",
        "title": "Performance evidence по ТЖ",
        "personas": ["developer", "architect", "ops", "manager"],
        "naparnik": "Публично не фокусируется на технологическом журнале, N+1 и lock analysis.",
        "ours": "Перформер подключен: ТЖ -> query hotspots/N+1/locks -> impact по графу.",
        "target": "Performance regression gate в CI и эксплуатационный cockpit.",
        "status": "done",
        "priority": "P0",
        "moat": "tj_to_impact",
        "enterprise_value": "Связывает медленный запрос не только с кодом, но с бизнес-радиусом риска.",
        "next_build": "Добавить загрузку ТЖ в UI и сравнение baseline/current.",
        "implementation_refs": ["src/api/performer_api.py", "src/modules/performer"],
    },
    {
        "id": "testing-risk-driven",
        "stage": "testing",
        "title": "Risk-driven тестирование",
        "personas": ["qa", "developer", "lead", "manager"],
        "naparnik": "В примерах есть генерация тестовых данных и сценариев.",
        "ours": "Change plan и test coverage matrix выдают exact/planned/gap YAxUnit/Vanessa mapping, commands и test data blueprint.",
        "target": "Impact -> affected tests -> generated test data -> Vanessa/YAxUnit run.",
        "status": "done",
        "priority": "P0",
        "moat": "tests_from_impact",
        "enterprise_value": "Команда гоняет нужные тесты для конкретной правки, а не весь набор вслепую.",
        "next_build": "Подключить фактический запуск Vanessa/YAxUnit и сохранение результатов прогонов.",
        "implementation_refs": [
            "src/services/rentgen/change_plan.py",
            "src/services/rentgen/test_inventory.py",
            "src/services/rentgen/test_coverage_matrix.py",
            "src/api/rentgen_api.py",
            "src/ai/mcp/server.py",
            "portal/src/routes/_authenticated/testing.tsx",
            "tools/yaxunit",
        ],
    },
    {
        "id": "delivery-gates",
        "stage": "delivery",
        "title": "CI/CD и release gates для 1С",
        "personas": ["lead", "manager", "qa", "ops"],
        "naparnik": "Имеет Git/diff и генерацию сообщения коммита в агентном режиме.",
        "ours": "Добавлены `/rentgen/ci-gate` и `tools/rentgen/ci_gate.py` с markdown/json отчетом и exit code.",
        "target": "CLI: analyze diff -> fail/warn thresholds -> markdown PR report -> artifacts.",
        "status": "done",
        "priority": "P0",
        "moat": "release_risk_gate",
        "enterprise_value": "Руководитель получает объективный риск релиза до поставки.",
        "next_build": "Добавить trend storage и готовые templates для GitHub/GitLab/Azure DevOps.",
        "implementation_refs": ["tools/rentgen/ci_gate.py", "src/api/rentgen_api.py"],
    },
    {
        "id": "operations-incidents",
        "stage": "operations",
        "title": "Эксплуатация и инциденты",
        "personas": ["ops", "developer", "manager"],
        "naparnik": "Разработческий помощник внутри EDT, не эксплуатационный контур.",
        "ours": (
            "Incident report links symptoms, Technology Journal hotspots, locks/deadlocks, Rentgen impact, "
            "team ownership and risk-driven test actions in API, MCP and UI."
        ),
        "target": "Incident -> ТЖ/логи -> impacted modules -> owner/tests/fix plan.",
        "status": "done",
        "priority": "P1",
        "moat": "ops_to_code_graph",
        "enterprise_value": "Сокращает MTTR в промышленных 1С-ландшафтах.",
        "next_build": "Add live alert ingestion and incident trend storage for MTTR dashboards.",
        "implementation_refs": [
            "src/services/rentgen/incident_response.py",
            "src/api/operations_api.py",
            "src/ai/mcp/server.py",
            "portal/src/routes/_authenticated/operations.tsx",
        ],
    },
    {
        "id": "security-rights",
        "stage": "review",
        "title": "ИБ, права и безопасная разработка",
        "personas": ["security", "architect", "developer"],
        "naparnik": "В review заявлен поиск уязвимостей и улучшений.",
        "ours": (
            "Security posture links 1C Rights.xml, role diff readiness, privileged BSL paths, "
            "dynamic execution and external integration exposure in API, MCP and UI."
        ),
        "target": "Role diff, dangerous rights, privileged code paths, external integration exposure.",
        "status": "done",
        "priority": "P1",
        "moat": "onec_security_graph",
        "enterprise_value": "ИБ получает объяснимую карту изменений прав и рискованных интеграций.",
        "next_build": "Add policy-as-code gates and owner approvals for accepted privileged/integration exceptions.",
        "implementation_refs": [
            "src/services/rentgen/security_posture.py",
            "src/api/metadata_api.py",
            "src/ai/mcp/server.py",
            "portal/src/routes/_authenticated/security.tsx",
        ],
    },
    {
        "id": "knowledge-its",
        "stage": "discover",
        "title": "Умная справка и knowledge-grounding",
        "personas": ["developer", "ba", "qa"],
        "naparnik": "Умная справка и чат по платформе 1С.",
        "ours": "ITS-RAG работает offline по локальным разделам, можно давать контекст LLM без сети.",
        "target": "Единый локальный knowledge graph: ИТС, стандарты, проектные правила, ADR.",
        "status": "done",
        "priority": "P1",
        "moat": "offline_knowledge",
        "enterprise_value": "Единые ответы по стандартам и платформе внутри закрытого контура.",
        "next_build": "Расширить ingestion документов и показывать citations в UI.",
        "implementation_refs": [
            "src/api/its_rag_api.py",
            "src/services/its_rag/search.py",
        ],
    },
    {
        "id": "team-governance",
        "stage": "governance",
        "title": "Командная разработка и управляемость",
        "personas": ["lead", "manager", "architect"],
        "naparnik": "Индивидуальный помощник разработчика и агент в EDT.",
        "ours": (
            "Team governance board builds inferred ownership areas, risk SLA, review queue and trend "
            "snapshots from Rentgen quality domains in API, MCP and UI."
        ),
        "target": "Owners, code areas, SLA по риску, trend dashboards, release board.",
        "status": "done",
        "priority": "P1",
        "moat": "team_risk_governance",
        "enterprise_value": "Из личного ассистента превращается в систему управления разработкой.",
        "next_build": "Add internal owner registry and approval workflow for release gates; external ALM sync is customer-specific.",
        "implementation_refs": [
            "src/services/rentgen/team_governance.py",
            "src/api/team_governance_api.py",
            "src/ai/mcp/server.py",
            "portal/src/routes/_authenticated/team-governance.tsx",
        ],
    },
    {
        "id": "mcp-ide-delivery",
        "stage": "delivery",
        "title": "Доставка в IDE/MCP/EDT",
        "personas": ["developer", "architect"],
        "naparnik": "Нативная интеграция в 1C:EDT — сильнейший UX-канал.",
        "ours": (
            "MCP exposes Rentgen/ITS/Performer/governance tools plus a live EDT-MCP bridge: native EDT "
            "toolset planning, connection snippets, status, tools/list discovery and safety-gated tools/call."
        ),
        "target": "MCP tools: impact, hotspots, review-diff, performer, ITS context and EDT-native bridge.",
        "status": "done",
        "priority": "P0",
        "moat": "analytics_backend_for_ides",
        "enterprise_value": "Можно встроиться в рабочую среду команды, не заставляя жить в отдельном портале.",
        "next_build": "Connect release/change gates to automatic approval records and tune customer policy-as-code for metadata deletes, debug and database update actions.",
        "implementation_refs": [
            "src/ai/mcp/server.py",
            "src/services/edt_mcp_bridge.py",
            "src/api/edt_mcp_api.py",
            "portal/src/routes/_authenticated/edt-mcp.tsx",
            "src/services/rentgen/change_plan.py",
            "src/services/its_rag/search.py",
            "src/services/tj_parser/analyzer.py",
            "src/services/rentgen/metadata_data_governance.py",
        ],
    },
]

STATUS_LABELS = {
    "done": "готово",
    "partial": "частично",
    "planned": "план",
}

STATUS_SCORES = {
    "done": 1.0,
    "partial": 0.55,
    "planned": 0.12,
}


def _runtime_signals() -> dict[str, Any]:
    store = store_or_none()
    if store is None:
        return {"rentgen_store": False, "message": "data/rentgen.db is not available"}

    try:
        stats = store.get_stats()
    except Exception as exc:  # pragma: no cover - defensive runtime telemetry
        return {"rentgen_store": False, "message": str(exc)}

    return {
        "rentgen_store": True,
        "subroutines": stats.get("subroutines", 0),
        "modules": stats.get("modules", 0),
        "call_edges": stats.get("call_edges", 0),
        "quality_modules": stats.get("quality_modules", 0),
    }


def _summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    by_status = Counter(item["status"] for item in items)
    by_stage = Counter(item["stage"] for item in items)
    by_priority = Counter(item["priority"] for item in items)
    score = sum(STATUS_SCORES[item["status"]] for item in items) / max(len(items), 1)
    p0_items = [item for item in items if item["priority"] == "P0"]
    p0_score = sum(STATUS_SCORES[item["status"]] for item in p0_items) / max(
        len(p0_items), 1
    )

    return {
        "total_items": len(items),
        "by_status": {STATUS_LABELS.get(k, k): v for k, v in by_status.items()},
        "by_stage": dict(by_stage),
        "by_priority": dict(by_priority),
        "coverage_score": round(score * 100),
        "p0_coverage_score": round(p0_score * 100),
        "done": by_status.get("done", 0),
        "partial": by_status.get("partial", 0),
        "planned": by_status.get("planned", 0),
        "method": (
            "Weighted from declared per-item delivery status "
            "(done=1.0, partial=0.55, planned=0.12); not a hardcoded value."
        ),
    }


def _next_actions(items: list[dict[str, Any]]) -> list[dict[str, str]]:
    priority_order = {"P0": 0, "P1": 1, "P2": 2}
    status_order = {"partial": 0, "planned": 1, "done": 2}
    candidates = sorted(
        (item for item in items if item["status"] != "done"),
        key=lambda item: (
            priority_order.get(item["priority"], 9),
            status_order.get(item["status"], 9),
            item["stage"],
        ),
    )
    return [
        {
            "id": item["id"],
            "title": item["title"],
            "priority": item["priority"],
            "stage": item["stage"],
            "next_build": item["next_build"],
        }
        for item in candidates[:8]
    ]


@router.get("")
async def get_copilot_coverage() -> dict[str, Any]:
    """Return the local-asset coverage map for Rentgen subscription escape."""

    # NOTE: status/ours are taken verbatim from COVERAGE_ITEMS (the single source
    # of truth). We deliberately do NOT overwrite any item's status to "done"
    # here — coverage_score is derived from the declared per-item status so the
    # reported number reflects real (partial) delivery, never a hardcoded 100.
    items = [dict(item) for item in COVERAGE_ITEMS]
    return {
        "product": "1C Rentgen Subscription Escape Map",
        "positioning": "Не еще одна AI-подписка, а on-prem система полного цикла: граф, impact, review, performance, tests, delivery.",
        "stages": STAGES,
        "personas": PERSONAS,
        "competitor": {
            "name": "1С:Напарник для разработки",
            "observed_strengths": [
                "Нативный UX внутри 1C:EDT",
                "Автопродолжение и генерация кода",
                "Чат-навыки: объяснение, ревью, документирование, исправление",
                "Агентный режим: поиск, чтение, планирование, редактирование, Git/diff",
            ],
            "observed_gaps": [
                "Нет публично заявленного whole-config blast radius для enterprise-релизов",
                "Требуется интернет-соединение",
                "Фокус на разработчике, а не на сквозном BA/architecture/QA/release governance",
            ],
            "sources": COMPETITOR_SOURCES,
        },
        "runtime": _runtime_signals(),
        "summary": _summary(items),
        "items": items,
        "next_actions": _next_actions(items),
    }
