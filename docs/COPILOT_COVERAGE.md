# 1cAI Enterprise 1C Copilot Coverage Map

Дата среза: 2026-06-15.

## Позиционирование

Цель 1cAI — не просто повторить IDE-помощника для генерации BSL, а закрыть весь enterprise-цикл разработки 1С:

`требование -> архитектура -> правка -> review -> performance -> тесты -> CI/release -> эксплуатация`.

1С:Напарник силен в рабочем месте разработчика: автопродолжение, генерация кода, чат-навыки, review/refactor/comment, агентный режим, поиск/чтение/редактирование проекта, Git/diff. Наша зона первенства — on-prem аналитический слой поверх всей конфигурации: граф, impact, риск релиза, performance, тестовый выбор и командное управление.

Официальные источники по текущему публичному контуру 1С:Напарника:

- https://code.1c.ai/
- https://code.1c.ai/examples/
- https://portal.1c.ru/applications/1C-Second-Pilot
- https://v8.1c.ru/platforma/iskusstvennyy-intellekt/
- https://v8.1c.ru/platforma/news/novoe-v-1c-edt-2025-1/

## Карта покрытия

| Этап | Что нужно для полного Copilot | 1С:Напарник | 1cAI сейчас | Что строим первым |
|---|---|---|---|---|
| Discovery | Понять конфигурацию, домен, legacy, карту объектов | Контекст EDT-проекта | Рентген: граф всей конфигурации, hotspots, dead code | Multi-config snapshots и drill-down |
| Requirements | Требования, сценарии, acceptance criteria, связь с объектами | Не основной публичный сценарий | Internal traceability workspace: requirement -> metadata/code/tests -> impact + ITS context | Internal approvals, versions and decision history |
| Architecture | Границы, зависимости, ADR, техдолг, blast radius | Агент может планировать/править проект | Architecture cockpit: слои, forbidden deps, cycles, dense coupling | ADR/policy enforcement |
| Coding | Генерация, правка, refactor, autocomplete | Сильная зона | Local graph-grounded BSL generation with Rentgen/metadata/ITS context | Full local LLM profile |
| Forms/UI | Формы, команды, динамические списки, UX | Учитывает формы в EDT-контексте | Managed-form blueprint: layout, commands, XML draft, BSL draft, UX checks | Import-ready EDT XML writer |
| Data | Метаданные, права, миграции, обмены | Метаданные в контексте | Metadata graph: objects, roles, rights, exchanges, governance findings | Multi-config metadata snapshots |
| Review | Стандарты, diff-review, security | Ревью/исправления/улучшения | `review-diff`, standards cockpit, security posture, impact-aware findings | Policy-as-code exceptions |
| Performance | ТЖ, запросы, N+1, блокировки | Не заявлен как фокус | Performer -> hotspots/N+1/locks -> graph impact + MCP | Baseline/current trend storage |
| Testing | YAxUnit/Vanessa, тестовые данные, affected tests | Примеры генерации тестовых данных | Test coverage matrix: exact/planned/gap selectors, commands, data blueprint | Actual Vanessa/YAxUnit runner |
| Delivery | Git, CI, release gates, markdown reports | Git/diff, commit message | CI gate + release readiness cockpit + markdown artifacts | CI templates for providers |
| Operations | Инциденты, логи, MTTR, owners | Не фокус EDT-помощника | Incident cockpit: symptoms/ТЖ/modules -> impact, owners, tests, runbook | Alert ingestion + MTTR trends |
| Governance | Командная ownership-модель, audit, trend | Индивидуальный помощник | Team governance + executive cockpit: ownership areas, risk SLA, review queue, snapshots, manager actions | Internal approval workflow and owner registry |

## Приоритеты реализации

P0:

- Local BSL codegen provider с контекстом Рентгена.
- Requirement impact workflow с persistent trace links.
- Metadata graph: объекты, права, обмены.
- BSL Language Server diagnostics в `review-diff`.
- Exact risk-driven test mapping для YAxUnit/Vanessa.
- CI templates и trend storage: diff -> risk -> tests -> markdown report.
- MCP tools для IDE: `performer`, `its_context`, EDT-MCP live bridge и стабильный transport contract.

Уже реализовано после первичной карты:

- `POST /api/v1/requirements/impact`
- `POST /api/v1/requirements/trace`, `GET /api/v1/requirements/traces`, `GET /api/v1/requirements/traces/{trace_id}`
- `POST /api/v1/rentgen/test-selector`
- `POST /api/v1/rentgen/ci-gate`
- `POST /api/v1/release-readiness/analyze`
- `POST /api/v1/architecture/review`
- `tools/rentgen/ci_gate.py`
- MCP tools: `rentgen_hotspots`, `rentgen_change_plan`, `rentgen_requirement_impact`
- MCP tool: `rentgen_requirement_trace`
- `GET /api/v1/metadata/summary`, `/search`, `/object`, `/object-impact`
- `POST /api/v1/metadata/snapshots`, `GET /api/v1/metadata/snapshots`, `POST /api/v1/metadata/diff`
- `GET /api/v1/metadata/security-review`, `GET /api/v1/metadata/security-posture`, `POST /api/v1/metadata/form-review`
- `POST /api/v1/metadata/form-blueprint`
- `GET /api/v1/metadata/data-governance`
- `POST /api/v1/quality/diagnostics` and fallback diagnostics inside `review-diff`
- `POST /api/v1/quality/standards-review`, `GET /api/v1/quality/standards-findings`, `GET /api/v1/quality/standards-catalog`
- `POST /api/v1/generate-grounded`
- `GET /api/v1/offline-readiness/analyze` and `GET /api/v1/offline-readiness/health`
- `GET /api/v1/team-governance/board`, `POST /api/v1/team-governance/snapshots`
- `POST /api/v1/operations/incident-report`
- Local grounded BSL provider: `src/services/rentgen/grounded_codegen.py`
- MCP tool: `rentgen_generate_grounded`
- MCP tool: `rentgen_offline_readiness`
- `GET /api/v1/rentgen/test-inventory` and `POST /api/v1/rentgen/test-inventory/match`
- `POST /api/v1/rentgen/test-coverage-matrix`
- MCP tools: `rentgen_metadata_search`, `rentgen_metadata_object_impact`, `rentgen_metadata_security_review`, `rentgen_form_review`, `bsl_diagnostics`, `rentgen_test_match`
- MCP tool: `rentgen_form_blueprint`
- MCP tool: `rentgen_security_posture`
- MCP tool: `bsl_standards_review`
- MCP tool: `rentgen_test_coverage_matrix`
- MCP tool: `rentgen_metadata_data_governance`
- MCP tool: `rentgen_team_governance`
- MCP tool: `rentgen_incident_report`
- MCP tools: `rentgen_its_search`, `rentgen_its_context`
- MCP tools: `rentgen_performer_analyze`, `rentgen_performer_impact`
- MCP tool: `rentgen_release_readiness`
- MCP tool: `rentgen_architecture_review`
- MCP tools: `edt_mcp_toolsets`, `edt_mcp_plan`, `edt_mcp_connection_config`
- MCP tools: `edt_mcp_status`, `edt_mcp_live_tools`, `edt_mcp_call`
- API: `GET /api/v1/edt-mcp/toolsets`, `POST /api/v1/edt-mcp/plan`, `GET /api/v1/edt-mcp/connection-config`
- API: `GET /api/v1/edt-mcp/status`, `GET /api/v1/edt-mcp/live-tools`, `POST /api/v1/edt-mcp/call`
- UI: `/metadata` Metadata Explorer
- UI: `/metadata` Data Governance panel
- UI: `/release-readiness` Release Cockpit
- UI: `/architecture` Architecture Cockpit
- UI: `/copilot` grounded generation cockpit
- UI: `/offline-readiness` closed-contour readiness report
- UI: `/requirements` BA traceability workspace
- UI: `/standards-review` BSL standards review cockpit
- UI: `/testing` risk-driven test coverage matrix
- UI: `/security` 1C security posture cockpit
- UI: `/forms` managed-form blueprint cockpit
- UI: `/team-governance` ownership and risk SLA board
- UI: `/operations` incident-to-code cockpit
- UI: `/` executive control cockpit for managers
- UI: `/edt-mcp` live EDT-MCP bridge with status, planner, tools/list and safe call
- API: `GET /api/v1/management/executive`

P1:

- Import-ready EDT XML writer and visual form diff.
- Live alert ingestion and incident trend storage for MTTR dashboards.
- Policy-as-code gates for accepted security exceptions.
- Internal owner registry and approval workflow; external ALM sync stays customer-specific.

## Критерий первенства

Мы первые не тогда, когда умеем “написать функцию по комментарию”. Это уже commodity. Мы первые, когда для любой правки в большой 1С-конфигурации локально отвечаем:

- какие требования и объекты затронуты;
- что сломается по графу;
- какие риски качества и производительности появятся;
- какие стандарты нарушены;
- какие тесты нужно прогнать;
- можно ли выпускать релиз;
- кто владелец зоны и что делать дальше.

Живой API карты: `GET /api/v1/copilot-coverage`.
Живой экран: `/copilot-coverage`.
