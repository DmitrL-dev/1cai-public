# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Security / Dependencies
- Tracked upstream issues for `starlette` (<0.42) и `urllib3` (>=2.5.0) — см. pip-audit отчёт и `README` (ограничения обновления до исправленных версий).
- План: обновить FastAPI/Starlette до версии, допускающей `starlette>=0.47`, и стек boto3/botocore до релиза с поддержкой `urllib3>=2.5.0`, затем повторно прогнать `pip-audit` и обновить данный раздел.

### Security / Tooling
- Добавлен скрипт `scripts/audit/check_secrets.py` и make-таргет `audit-secrets` для лёгкого локального сканирования возможных секретов (`analysis/secret_scan_report.json`).
- Добавлен составной make-таргет `security-audit`, объединяющий `audit-hidden-dirs`, `audit-secrets`, `check_git_safety.py` и `comprehensive_project_audit.py` для полного security-аудита перед релизом.
- Добавлен Windows-скрипт `scripts/windows/security-audit.ps1` для эквивалентного security-audit в PowerShell.

### AI Agents / Testing
- Developer AI Secure: девгид и unit-тесты безопасности (approve flow, токены).
- QA Engineer AI: гайд, e2e-тесты маршрутизации и генерации тестов.
- Business Analyst Agent: интеграционные тесты Jira/Confluence/PowerBI/Docflow.
- LLM Diagnostics: скрипт и юнит-тесты для проверки доступности LLM-провайдеров.
- SQL Optimizer: unit-тесты и отдельный гайд (SQL_OPTIMIZER_GUIDE).
- TechLogAnalyzer / RAS Monitor / Issue Classifier: unit-тесты для анализа техлога, мониторинга кластера и ML/rule-based классификатора инцидентов.
- AI Orchestrator: базовые unit-тесты для QueryClassifier и process_query (валидация, кэш, offline-мультисервис) + дополнительные тесты graceful-ошибок.
- BA → Developer AI Secure → QA Engineer AI: сквозной system-тест `tests/system/test_e2e_ba_dev_qa.py` и гайд `docs/08-e2e-tests/BA_DEV_QA_E2E.md`.
- GigaChat / YandexGPT: асинхронные клиенты `src/ai/clients/gigachat_client.py`, `src/ai/clients/yandexgpt_client.py` и unit-тесты конфигурации/поведения при отсутствии кредов (`tests/unit/test_gigachat_client.py`, `tests/unit/test_yandexgpt_client.py`).

### Observability / Performance
- Добавлен `docs/06-features/AI_PERFORMANCE_GUIDE.md` с обзором метрик Orchestrator/Kimi/Qwen, promql-запросами и рекомендациями по latency/cache hit rate.
- Тесты `tests/unit/test_ai_orchestrator_basic.py` дополнены проверкой метрик `orchestrator_cache_hits_total` и `orchestrator_cache_misses_total`, а также поведением без Kimi/Qwen.
- Добавлены скрипты `scripts/testing/kimi_benchmark.py` (performance Kimi) и `scripts/testing/orchestrator_latency_smoke.py` (latency smoke Orchestrator).

### DevEx / Windows
- Добавлен Windows Quickstart (`docs/01-getting-started/windows_quickstart.md`) с шагами локального запуска AI-стека, тестов и security-аудита без GNU Make.
- Добавлен Usage Cookbook (`docs/01-getting-started/cookbook.md`) с типовыми сценариями.
- README дополнен ссылками на Quickstart и Cookbook в разделе Usage/Documentation Hub.

### Spec-Driven Workflow
- В `comprehensive-testing.yml` добавлен job `spec-driven-validation`, выполняющий `make feature-validate` для проверки заполнения feature-спек на CI.

### BA Agents
- Подготовлены гайды BA-03…BA-07 (`BA_PROCESS_MODELLING_GUIDE`, `BA_ANALYTICS_KPI_GUIDE`, `BA_TRACEABILITY_COMPLIANCE_GUIDE`, `BA_INTEGRATIONS_COLLAB_GUIDE`, `BA_ENABLEMENT_GUIDE`) и отражены в `docs/06-features/README.md` и `docs/research/alkoleft_todo.md`.

### DR / Resilience
- Добавлен `scripts/runbooks/generate_dr_postmortem.py` для автоматической генерации черновиков постмортемов после DR rehearsal (`docs/runbooks/postmortems/`), обновлён `docs/runbooks/dr_rehearsal_plan.md`.

### DORA / Status
- Добавлен шаблон `docs/status/weekly_summary_template.md` и обновлён `docs/status/README.md` (weekly summary + DORA history).

### Scenario Hub & Tool Registry (experimental)
- Добавлен reference-слой Scenario Hub в `src/ai/scenario_hub.py` и документ `docs/architecture/AI_SCENARIO_HUB_REFERENCE.md` (цели/сценарии/плейбуки, уровни риска и автономности, trust-score).
- Реализован экспериментальный реестр инструментов/skills в `src/ai/tool_registry.py` и документ `docs/architecture/TOOL_REGISTRY_REFERENCE.md` (protocol-agnostic описание инструментов, привязка к риску и категориям).
- Добавлены примерные планы сценариев BA→Dev→QA и DR rehearsal в `src/ai/scenario_examples.py` и read-only endpoint `/api/scenarios/examples` в `src/ai/orchestrator.py` для их получения.
 - Добавлены YAML-плейбуки `playbooks/ba_dev_qa_example.yaml` и `playbooks/dr_vault_example.yaml`, dry-run исполнитель `src/ai/playbook_executor.py` и CLI `scripts/runbooks/run_playbook.py`; в tests/unit добавлен `test_playbook_executor.py`.
 - Добавлен примерный ToolRegistry (`src/ai/tool_registry_examples.py`) и read-only endpoint `/api/tools/registry/examples` в `src/ai/orchestrator.py`, а также тест `tests/unit/test_tool_registry_api.py`.
 - Формализованы открытые стандарты: Scenario DSL (`SCENARIO_DSL_SPEC.md` + `SCENARIO_DSL_SCHEMA.json`), Autonomy & Policy Model (`AUTONOMY_POLICY_SPEC.md` + `AUTONOMY_POLICY_SCHEMA.json`) и Unified Change Graph (`CODE_GRAPH_REFERENCE.md`); добавлены примеры внешних JSON (`docs/architecture/examples/*`), CLI `print_scenario_decisions.py`, скрипты валидации (`validate_scenarios_against_schema.py`, `check_conformance_report.py`), гид по внедрению (`STANDARDS_ADOPTION_GUIDE.md`) и чеклист соответствия (`STANDARDS_CONFORMANCE_CHECKLIST.md`), а также интеграция стандартизирующих проверок в CI (`make validate-standards` в `comprehensive-testing.yml`).

### Scenario Hub & Unified Change Graph (Production) - 2025-11-17
- **Scenario Recommender & Impact Analyzer**: реализованы компоненты для автоматического предложения релевантных сценариев и анализа влияния изменений через Unified Change Graph.
- **OneCCodeGraphBuilder**: создан автоматический построитель графа из BSL модулей для 1С кода.
- **LLM Provider Abstraction**: унифицированный уровень абстракции для работы с разными LLM провайдерами (Kimi, Qwen, GigaChat, YandexGPT) с автоматическим выбором на основе типа запроса, рисков, стоимости и compliance требований.
- **Intelligent Cache**: интеллектуальное кэширование с TTL на основе типа запроса, инвалидацией по тегам и типу запроса, LRU eviction и метриками производительности.
- **Unified CLI Tool**: создан `scripts/cli/1cai_cli.py` для работы со всеми компонентами платформы через REST API.
- **Performance Benchmarks**: созданы benchmarks для всех новых компонентов с целевыми метриками (p95 < 50ms для малого графа, p95 < 1ms для cache hit).
- **Prometheus Metrics**: расширены метрики для Scenario Recommender, Impact Analyzer, LLM Provider Abstraction, Intelligent Cache.
- **E2E Tests**: созданы E2E тесты для Scenario Hub, LLM Provider Abstraction, Intelligent Cache, CLI Tool, BA-функций с Unified Change Graph.
- **E2E Tests для критических путей**: создан `tests/system/test_e2e_critical_paths.py` с 13 тестами, покрывающими полный цикл API → Orchestrator → LLM Provider → Response, интеграцию с новыми компонентами, обработку ошибок и производительность.
- **Architecture Documentation**: созданы UML-схемы (sequence и component диаграммы), обновлён HLD документ, создан ADR-0006 для архитектурных решений.

### Added
- Initial project structure
- Docker Compose infrastructure (PostgreSQL, Redis, Nginx)
- PostgreSQL schema for knowledge base
- Architecture documentation (architecture.yaml)
- Implementation plan (30 weeks roadmap)
- Setup scripts
- README and contributing guidelines

### Changed
- parse_edt_xml.py: Added PostgreSQL integration (in progress)

### Deprecated
- JSON knowledge base (will be replaced by Neo4j in Stage 1)

## [0.1.0] - 2025-01-XX

### Added
- Project initialization
- Basic infrastructure setup
- Documentation framework

---

## Version History

- **v0.1.0** - Initial setup (Stage 0, Week 1)
- **v1.0.0** - Planned: Full release (Stage 6, Week 30)

