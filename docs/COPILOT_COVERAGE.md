# 1C Rentgen Subscription Escape Coverage Map

Дата среза: 2026-06-15.

> **Current truth, 2026-06-18:** живой API больше не должен трактоваться как "100% done".
> Текущий код считает покрытие честно: 17 tracked items, 14 ready, 3 partial, примерно 92% total
> coverage и 89% P0 coverage. Partial items остаются в next actions и являются частью roadmap.

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

| Этап | Что нужно для локального Rentgen asset | 1С:Напарник | Rentgen сейчас | Что строим первым |
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
- `POST /api/v1/lock-radar/analyze`
- `POST /api/v1/extension-safety/analyze`
- `POST /api/v1/business-case/build`
- `POST /api/v1/board-pack/build`
- `POST /api/v1/outcome-ledger/build`
- `POST /api/v1/launch-room/build`
- `POST /api/v1/buyer-concierge/build`
- `POST /api/v1/commercial-offer-studio/build`
- `POST /api/v1/demo-command-center/build`
- `POST /api/v1/enterprise-trust-center/build`
- `POST /api/v1/guided-demo/build`
- `POST /api/v1/scenario-hub/build`
- `POST /api/v1/pilot-launchpad/build`
- Local grounded BSL provider: `src/services/rentgen/grounded_codegen.py`
- MCP tool: `rentgen_generate_grounded`
- MCP tool: `rentgen_offline_readiness`
- `GET /api/v1/rentgen/test-inventory` and `POST /api/v1/rentgen/test-inventory/match`
- `POST /api/v1/rentgen/test-coverage-matrix`
- `POST /api/v1/test-factory/build`
- `POST /api/v1/killer-demo/build`
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
- UI: `/safe-autopilot` read-only plan/diff/tests/approval cockpit
- UI: `/offline-readiness` closed-contour readiness report
- UI: `/requirements` BA traceability workspace
- UI: `/standards-review` BSL standards review cockpit
- UI: `/testing` Test Factory with run-now tests, YAxUnit/Vanessa skeletons, manual checks, evidence packet and coverage matrix
- UI: `/killer-demo` buyer-ready demo path with stages, role sparks, proof moments, close scripts and Evidence Bundle export
- UI: `/security` 1C security posture cockpit
- UI: `/forms` managed-form blueprint cockpit
- UI: `/team-governance` ownership and risk SLA board
- UI: `/operations` incident-to-code cockpit
- UI: `/lock-radar` Technology Journal lock/deadlock radar
- UI: `/extension-safety` extension/update safety cockpit
- UI: `/business-case` director money map and deal-room report
- UI: `/board-pack` board-level buying motion with value, trust, risks, committee answers and proof packet
- UI: `/outcome-ledger` post-purchase adoption ledger with outcome metrics, risk burndown and expansion paths
- UI: `/launch-room` first buyer-facing cockpit with next best action, role paths, meeting modes, route health and proof packet
- UI: `/buyer-concierge` first-click role/pain router with shortest paths, default next action and anti-confusion guardrails
- UI: `/commercial-offer-studio` buyable offer studio with package stack, value-based price anchors, proposal sections and close path
- UI: `/demo-command-center` live presenter route with stages, role pivots, recovery cards and close checklist
- UI: `/enterprise-trust-center` security/CIO/procurement trust route for local contour, SBOM/offline, rights, platform caveats and approval artifacts
- UI: `/guided-demo` buyer-guided deal-room route across role proof, money map, productization and evidence close
- UI: `/scenario-hub` pain-led buyer scenario gallery across developer, architect, director, vendor, security and operations routes
- UI: `/pilot-launchpad` buyer pilot offers, acceptance matrix, procurement pack and 30-day rollout plan
- UI: `/` executive control cockpit for managers
- UI: `/edt-mcp` live EDT-MCP bridge with status, planner, tools/list and safe call
- API: `GET /api/v1/management/executive`
- UI: `/productization` enterprise delivery console for SBOM and offline bundle verification
- API: `POST /api/v1/vendor-portfolio/portfolio`

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

Живой API карты совместимости: `GET /api/v1/copilot-coverage`.
Живой экран: `/copilot-coverage`, теперь оформлен как Rentgen Subscription Escape Map.
