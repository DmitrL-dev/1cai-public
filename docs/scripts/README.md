# Scripts Overview

> Обновлено: 11 ноября 2025  •  Основано на Python 3.11 и сопутствующих CLI из `scripts/`

## 1. Назначение

Эта страница объединяет основные утилиты из каталога `scripts/`: что они делают, какие зависимости требуют и как связаны с `Makefile` и CI. Читайте перед запуском скриптов напрямую — особенно если работаете в Windows окружении или через WSL.

## 2. Быстрая карта

| Категория | Путь | Ключевые скрипты | Когда использовать |
|-----------|------|------------------|--------------------|
| Analysis | `scripts/analysis/` | `generate_documentation.py`, `analyze_*`, `tree_sitter_adapter.py` | Анализ 1C конфигураций, формирование отчётов и метрик |
| Parsers | `scripts/parsers/` | `bsl_ast_parser.py`, `parse_1c_config*.py`, `edt/` | Парсинг EDT XML и конфигураций, интеграция с `bsl-language-server` |
| Context & Docs | `scripts/context/`, `scripts/docs/` | `export_platform_context.py`, `generate_docs.py`, `create_adr.py`, `render_uml.py` | Генерация платформенного контекста, документации, ADR и UML |
| Audits | `scripts/audit/`, `run_full_audit.py` | `comprehensive_project_audit.py`, `project_structure_audit.py`, `check_git_safety.py` | Комплексные проверки перед релизом, выполнение требований конституции |
| Migrations & Data | `scripts/migrations/`, `scripts/data/` | `migrate_json_to_postgres.py`, `migrate_postgres_to_neo4j.py`, `load_configurations.py` | Наполнение хранилищ (PostgreSQL→Neo4j→Qdrant), загрузка конфигураций |
| Testing | `scripts/tests/`, `scripts/testing/` | `run_bsl_tests.py`, `check_all_results.py`, `test_gateway.sh` | Запуск BSL/YAxUnit и вспомогательных smoke/health тестов |
| Maintenance & Cleanup | `scripts/maintenance/`, `scripts/cleanup/` | `cleanup_project.py`, `move_research_files.py`, `final_root_cleanup.ps1` | Наведение порядка перед публикацией, перенос временных файлов |
| Deployment & Ops | shell-скрипты в корне (`start.sh`, `monitor-deployment.sh`) + `scripts/monitoring/` | `blue-green-deploy.sh`, `schedule-traffic-switch.sh`, `health-check.sh`, `monitoring/github_monitor.py` | Управление окружениями, мониторинг деплоя и внешних зависимостей |
| Windows Helpers | `scripts/windows/` | `bsl-ls-up.ps1`, `bsl-ls-check.ps1`, `feature-init.ps1`, `feature-validate.ps1` | Альтернатива make/dc для PowerShell пользователей |
| Spec-driven workflow | `scripts/research/`, `templates/` | `init_feature.py`, шаблоны `feature-*.md` | Создание каркасов планов/спеков, работа по методологии |
| Release & Metrics | `scripts/release/`, `scripts/metrics/` | `create_release.py`, `collect_dora.py` | Подготовка релизов, генерация нотесов, сбор DORA-показателей |
| Observability | `docs/observability/`, `docs/runbooks/` | SLO, runbooks, postmortem template | Мониторинг, Error Budget, реакции |
| ML & Benchmarks | `scripts/dataset/`, `scripts/ml/`, `benchmark_*.py` | `create_ml_dataset.py`, `massive_ast_dataset_builder.py`, `benchmark_performance.py` | Подготовка датасетов, измерение производительности |
| Setup | `scripts/setup/` | `check_runtime.py` | Проверка наличия Python 3.11, подготовка окружения |
| Security | `scripts/security/` | `run_security_scans.sh`, `run_policy_checks.sh`, `run_checkov.sh` | Запуск bandit/pip-audit/safety, Conftest/Semgrep, Checkov/Trivy |
| GitOps | `scripts/gitops/` | `apply.sh`, `sync.sh` | Применение Argo CD manifest’ов и инициирование sync |
| Chaos | `scripts/chaos/` | `run_litmus.sh` | Запуск Litmus pod-delete эксперимента |
| FinOps | `scripts/finops/` | `aws_cost_report.py`, `aws_cost_to_slack.py` | Краткий отчёт AWS Cost Explorer и отправка в Slack |
| Checklists | `scripts/checklists/` | `preflight.sh` | Самоконтроль перед деплоем |
| Secrets | `scripts/secrets/` | `aws_sync_to_vault.py` | Синхронизация AWS Secrets Manager → Vault |
| Infrastructure | `infrastructure/terraform/aws-eks` | Terraform модуль EKS | Развёртывание AWS инфраструктуры |
| Infrastructure | `infrastructure/terraform/azure-keyvault` | Terraform модуль Key Vault | Provisioning Azure Key Vault |
| Infrastructure | `infrastructure/ansible/` | `site.yml`, `hosts.ini` | Bootstrap Linux-хостов |

## 3. Зависимости и подготовка

- Python 3.11.x — установите системно или через `pyenv`. Скрипты проверяют версию (см. `make check-runtime`).
- Виртуальное окружение + `make install` (или соответствующие `pip install -r requirements*.txt`).
- Docker Compose: требуется для миграций и анализа (PostgreSQL, Neo4j, Qdrant, Redis).
- **Внешние инструменты**: 
  - `platform-context-exporter` → переменная `PLATFORM_CONTEXT_EXPORTER_CMD` (см. `export_platform_context.py`).
  - `ones_doc_gen` → `ONES_DOC_GEN_CMD` (см. `generate_docs.py`).
  - YAxUnit/OneScript → для `run_bsl_tests.py` и тестов 1С.
- Windows: для PowerShell-скриптов (`*.ps1`) запускайте под администратором, либо используйте аналоги в bash/WSL.

## 4. Основные рабочие сценарии

### 4.1 Аналитика (`scripts/analysis/`)
- `generate_documentation.py` — собирает JSON-результаты анализа (архитектура, best practices) и формирует Markdown (используется в pipeline документации).
- `analyze_architecture.py`, `analyze_dependencies.py`, `extract_best_practices.py` — запускаются вручную или через orchestrators для извлечения статистики.
- `tree_sitter_adapter.py` — обёртка над `tree-sitter-bsl` с fallback на regex (используется внутри анализаторов).

### 4.2 Контекст и документация
- `context/export_platform_context.py` — прокси к `alkoleft/platform-context-exporter`. Без заданного `PLATFORM_CONTEXT_EXPORTER_CMD` скрипт мягко завершится, напомнив установить инструмент.
- `context/generate_docs.py` — аналогичный вызов `alkoleft/ones_doc_gen` (env `ONES_DOC_GEN_CMD`).
- `docs/create_adr.py` — создаёт новый ADR на основе slug, автоматически обновляет `docs/architecture/adr/README.md`.
- `docs/render_uml.py` — рендер PlantUML диаграмм; используется в `make render-uml` и GitHub Actions.

### 4.3 Миграции и данные
- `migrations/migrate_json_to_postgres.py` → загрузка выгрузки DO/ERP в Postgres.
- `migrations/migrate_postgres_to_neo4j.py`, `migrate_to_qdrant.py` → построение графа и векторного индекса.
- `run_migrations.py` — orchestration to end-to-end migration.
- **Внимание**: все миграции требуют поднятых сервисов (`make docker-up`).

### 4.4 Аудиты и контроль качества
- `audit/comprehensive_project_audit.py` + `run_full_audit.py` — выполняют полный чек-лист (структура, лицензии, broken links). Обязательны перед публикацией, см. `docs/research/constitution.md`.
- `audit/check_git_safety.py`, `audit/license_compliance_audit.py` — точечные проверки безопасности и лицензий.

### 4.5 Тесты и QA
- `tests/run_bsl_tests.py` — исполняет BSL/YAxUnit манифест (`tests/bsl/testplan.json`), сохраняет логи в `output/bsl-tests`. Связан с `make test-bsl` и job `bsl-tests`.
- `testing/run_demo_tests.py`, `testing/test_its_api.py` и др. — быстрые smoke-проверки API/интеграций.
- Подробный обзор команд — в [`docs/06-features/TESTING_GUIDE.md`](../06-features/TESTING_GUIDE.md).

### 4.6 Сервисные и maintenance скрипты
- `maintenance/cleanup_project.py`, `cleanup/move_research_files.py` — автоматизируют уборку временных файлов, соблюдают требования `.gitignore` и публикации.
- PowerShell сценарии `maintenance/*.ps1` — для Windows (архивация, финальная очистка).
- `backup-restore.sh`, `create-backup.sh`, `emergency-rollback.sh` — готовые процедуры резервирования.

### 4.7 Операции и деплой
- `start.sh`, `stop.sh`, `start_ecosystem.sh` — запуск локальной экосистемы (API, MCP, базы).
- `blue-green-deploy.sh`, `schedule-traffic-switch.sh`, `monitor-deployment.sh` — сценарии развёртывания и переключения трафика.
- `health-check.sh`, `monitoring.sh` — базовые health-проверки.
- `monitoring/github_monitor.py` — опрос GitHub API для отслеживания релизов/коммитов внешних зависимостей, сохраняет состояние в `output/monitoring/github_state.json` (см. план мониторинга).
- Prometheus `/metrics` обрабатывается `prometheus_fastapi_instrumentator` из `src/main.py` (см. `requirements.txt`).

### 4.8 Spec-driven workflow
- `templates/feature-*.md` — заготовки для планов, спецификаций, задач и исследований (благодарность [github/spec-kit](https://github.com/github/spec-kit)).
- `scripts/research/init_feature.py` — создаёт каталог `docs/research/features/<slug>/` и копирует шаблоны.
- `scripts/research/check_feature.py` — проверяет, что заполненные документы не содержат шаблонных маркеров/`TODO`.
- Make-таргеты: `make feature-init FEATURE=my-feature` и `make feature-validate [FEATURE=my-feature]`.
- После создания обязательно заполните документы, обновите README/CHANGELOG и соблюдайте `docs/research/constitution.md`.

### 4.9 Windows helpers
- `scripts/windows/bsl-ls-up.ps1`, `bsl-ls-check.ps1`, `bsl-ls-logs.ps1` — запуск и диагностика `bsl-language-server` без `make`.
- `scripts/windows/feature-init.ps1`, `feature-validate.ps1` — PowerShell аналоги make-таргетов spec-driven workflow.
- Запускаются из корня проекта: `pwsh scripts/windows/feature-init.ps1 -Feature my-feature`.

### 4.10 Release и метрики
- `scripts/release/create_release.py` — формирует блок `RELEASE_NOTES.md`, создаёт/пушит теги (`make release-*`).
- Workflow `.github/workflows/release.yml` публикует GitHub Release при пуше тега `v*`.
- `scripts/metrics/collect_dora.py` — вычисляет DORA метрики (deployment frequency, lead time, CFR, MTTR) и сохраняет их в `output/metrics/`.
- Workflow `dora-metrics.yml` выполняет скрипт еженедельно и прикладывает отчёты как артефакт.
- Allure отчёты (`output/test-results/allure/`) доступны после job `unit-tests`; открываются `allure serve ...`.
- `observability/docker-compose.observability.yml` запускает стек Prometheus+Grafana (`make observability-up`). Проверяется в CI (`observability-test.yml`).

### 4.11 Настройка окружения (`scripts/setup/`)
- `check_runtime.py` — проверяет доступность Python 3.11 (`make check-runtime`). При отсутствии выводит инструкцию `docs/setup/python_311.md`.
- Дополнительно: используйте PowerShell/WSL скрипты из `scripts/windows/` для установки зависимостей.

### 4.12 Безопасность (`scripts/security/`)
- `run_security_scans.sh` — единая точка запуска bandit/pip-audit/safety. Используется в Jenkins/GitLab pipeline.
- `run_policy_checks.sh` — рендер Helm-чартов, Conftest (Rego-политики из `policy/`), Semgrep (`security/semgrep.yml`). Требуются утилиты `helm`, `conftest`, `semgrep`, `terraform`.
- `run_checkov.sh` — Checkov (Terraform IaC) + Trivy config scan.

### 4.13 GitOps (`scripts/gitops/`)
- `apply.sh` — `kubectl apply -k infrastructure/argocd` (создаёт AppProject, Applications).
- `sync.sh` — вызывает `argocd app sync` для `1cai-stack` и `observability-stack` (требует `ARGOCD_TOKEN`, переменная `ARGOCD_SERVER`).
- README: `scripts/gitops/README.md`.

### 4.14 Chaos (`scripts/chaos/`)
- `run_litmus.sh` — применяет Litmus experiment/engine (требует установленного оператора).

### 4.15 FinOps (`scripts/finops/`)
- `aws_cost_report.py` — отчёт по затратам AWS (Cost Explorer).
- `aws_cost_to_slack.py` — отправляет отчёт за 3 дня в Slack (нужно `SLACK_WEBHOOK_URL`).

### 4.16 Checklists (`scripts/checklists/`)
- `preflight.sh` — выполняет ключевые проверки перед деплоем (lint/test/policy/checkov).

### 4.17 Secrets (`scripts/secrets/`)
- `aws_sync_to_vault.py` — перенос Secrets Manager в Vault.
- `azure_sync_to_vault.py` — синхронизация Azure Key Vault → Vault.
- `apply_vault_csi.sh` — разворачивает SecretProviderClass и пример Deployment.
- `test_vault_sync.sh` — проверка соответствия Vault и Kubernetes secret.

### 4.18 FinOps (`scripts/finops/`)
- `aws_cost_report.py` — отчёт по затратам AWS (Cost Explorer).
- `aws_cost_to_slack.py` / `azure_cost_to_slack.py` — отправка отчётов в Slack/Teams.
- `aws_budget_check.py`, `azure_budget_check.py` — проверка Budgets.
- `teams_notify.py` — утилита отправки произвольных сообщений в Teams.

### 4.19 Checklists (`scripts/checklists/`)
- `preflight.sh` — выполняет ключевые проверки перед деплоем (lint/test/policy/checkov) и отправляет отчет в Slack/Teams.

### 4.20 Service Mesh (`scripts/service_mesh/`)
- `bootstrap_certs.sh` — генерация trust anchor/issuer для Linkerd (TODO).

### 4.21 ML и экспериментальные утилиты
- `dataset/create_ml_dataset.py`, `prepare_neural_training_data.py` — подготовка выборок для моделей.
- `finetune_qwen_smoltalk.py`, `train_copilot_model.py` — эксперименты с дообучением ассистента.
- `benchmark_performance.py`, `profile_full_parser.py` — измерение скорости анализа/парсинга.

## 5. Связь с Makefile

| Make цель | Что запускает | Где описано |
|-----------|---------------|-------------|
| `make generate-docs` | `context/generate_docs.py` | текущий документ (4.2) |
| `make export-context` | `context/export_platform_context.py` | текущий документ (4.2) |
| `make bsl-ls-check` | `parsers/check_bsl_language_server.py` | [AST tooling guide](../06-features/AST_TOOLING_BSL_LANGUAGE_SERVER.md) |
| `make migrate` | `migrations/*` через последовательный pipelines | раздел 4.3 |
| `make test-bsl` | `tests/run_bsl_tests.py` | раздел 4.5 |
| `make render-uml` | `docs/render_uml.py` | раздел 4.2 |
| `make quality` | пакет формата/линта + `pytest` | см. `Makefile` |
| `make release-notes/tag/push` | `scripts/release/create_release.py` | раздел 4.10 |
| `make observability-up/down` | `observability/docker-compose.observability.yml` | раздел 4.11 |
| `make check-runtime` | `scripts/setup/check_runtime.py` | раздел 4.11 |
| `make helm-observability` | `infrastructure/helm/observability-stack` | раздел 4.3 |
| security pipeline | `scripts/security/run_security_scans.sh` | раздел 4.12 |
| GitHub Actions | `observability-test.yml` | автоматическая проверка compose стека |
| Spec-driven validation | `comprehensive-testing.yml` (job `spec-driven-validation`) | см. `docs/research/spec_kit_analysis.md`, `templates/README.md` |
| `make gitops-apply` | `scripts/gitops/apply.sh` | раздел 4.13 |
| `make gitops-sync` | `scripts/gitops/sync.sh` | раздел 4.13 |
| `make chaos-litmus-run` | `scripts/chaos/run_litmus.sh` | раздел 4.14 |
| `make preflight` | `scripts/checklists/preflight.sh` | раздел 4.16 |
| secrets sync | `scripts/secrets/aws_sync_to_vault.py` | раздел 4.17 |

Всегда сверяйтесь с `