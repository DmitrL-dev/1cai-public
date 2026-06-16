# 🛠️ Каталог `scripts/`

Коллекция CLI-утилит и вспомогательных сценариев, которыми живёт платформа 1C AI Stack. Здесь лежат анализаторы конфигураций, миграции, GitOps/FinOps утилиты, security-пайплайн и помощники для Windows.

## 🔍 Быстрая навигация
| Задача | Где посмотреть | Быстрый запуск |
|--------|----------------|----------------|
| Анализ конфигураций и отчёты | [`analysis/`](analysis/README.md) | `python scripts/analysis/generate_documentation.py` |
| Парсеры 1С/EDT и AST | [`parsers/`](parsers/README.md) | `python scripts/parsers/parse_1c_config.py` |
| Миграции данных (Postgres → Neo4j → Qdrant) | [`migrations/`](migrations/README.md) | `make migrate` (запускает последовательность скриптов) |
| Подготовка ML-датасетов | [`dataset/`](dataset/README.md) | `python scripts/dataset/create_ml_dataset.py` |
| Контекст и документация | [`context/`](context/README.md), [`docs/`](docs/README.md) | `make export-context`, `make generate-docs`, `make render-uml` |
| Аудиты и проверка качества | [`audit/`](audit/README.md), [`cleanup/`](cleanup/README.md) | `python scripts/audit/comprehensive_project_audit.py` |
| GitOps/ArgoCD | [`gitops/`](gitops/README.md) | `make gitops-apply`, `make gitops-sync` |
| Service Mesh (Linkerd) | [`service_mesh/`](service_mesh/README.md) → [`linkerd/`](service_mesh/linkerd/README.md) | `make linkerd-install`, `scripts/service_mesh/linkerd/bootstrap_certs.sh` |
| Security / Policy-as-code | [`security/`](security/README.md) | `make policy-check`, `bash scripts/security/run_security_scans.sh` |
| FinOps отчёты и бюджеты | [`finops/`](finops/README.md) | `make finops-slack` |
| Secrets & Vault | [`secrets/`](secrets/README.md) | `bash scripts/secrets/aws_sync_to_vault.py` |
| Observability & мониторинг | [`monitoring/`](monitoring/README.md) | `python scripts/monitoring/github_monitor.py` |
| Тесты и smoke-проверки | [`testing/`](testing/README.md) | `make smoke-tests`, `make test-bsl` |
| Запуск DR тренировок | [`runbooks/`](runbooks/README.md) | `python scripts/runbooks/dr_rehearsal_runner.py` |
| Спецификации и research workflow | [`research/`](research/README.md) | `make feature-init FEATURE=...` |
| Помощники Windows | [`windows/`](windows/README.md) | `pwsh scripts/windows/docker-up.ps1` |

> **Совет:** запустите `make help`, чтобы увидеть, какие make-таргеты уже обёрнуты вокруг этих скриптов.

## ⚙️ Среда выполнения
- Python 3.11 (проверяется `make check-runtime`, см. [`scripts/setup/check_runtime.py`](setup/check_runtime.py)).
- Активированное виртуальное окружение (`make install` или `pip install -r requirements.txt`).
- Docker/Compose для баз данных и очередей (`make docker-up`).
- Дополнительные утилиты по месту (Helm, ArgoCD CLI, Linkerd CLI, Conftest, Semgrep, Checkov, Trivy, Terraform, YAxUnit, OneScript и т.д.). Конкретные требования перечислены в README каждой подпапки.

## 🔁 Связь с Makefile и CI
| Make-таргет | Что запускается | Где описано |
|-------------|-----------------|--------------|
| `make docker-up / docker-down` | docker-compose стэк | [docs/04-deployment/README.md](../docs/04-deployment/README.md) |
| `make migrate` | `scripts/migrations/*` + `run_migrations.py` | [`migrations/README.md`](migrations/README.md) |
| `make generate-docs` | `scripts/context/generate_docs.py` | [`context/README.md`](context/README.md) |
| `make export-context` | `scripts/context/export_platform_context.py` | [`context/README.md`](context/README.md) |
| `make render-uml` | `scripts/docs/render_uml.py` | [`docs/README.md`](docs/README.md) |
| `make gitops-apply / gitops-sync` | `scripts/gitops/*.sh` | [`gitops/README.md`](gitops/README.md) |
| `make linkerd-install` | `scripts/service_mesh/linkerd/*.sh` | [`service_mesh/README.md`](service_mesh/README.md) |
| `make vault-csi-apply` | `scripts/secrets/apply_vault_csi.sh` | [`secrets/README.md`](secrets/README.md) |
| `make finops-slack` | `scripts/finops/aws_cost_to_slack.py` / `azure_cost_to_slack.py` | [`finops/README.md`](finops/README.md) |
| `make preflight` | `scripts/checklists/preflight.sh` | [`checklists/README.md`](checklists/README.md) |
| `make test-bsl` | `scripts/tests/run_bsl_tests.py` | [`testing/README.md`](testing/README.md) |
| `make smoke-tests` | `scripts/testing/smoke_healthcheck.py` | [`testing/README.md`](testing/README.md) |
| `make policy-check` | `scripts/security/run_policy_checks.sh` | [`security/README.md`](security/README.md) |

GitHub Actions используют те же сценарии: `uml-render-check.yml`, `observability-test.yml`, `finops-report.yml`, `dr-rehearsal.yml`, `dora-metrics.yml`, `secret-scan.yml`, `trufflehog.yml`.

## ✅ Перед запуском любого скрипта
1. Прочитайте README соответствующего каталога (см. ссылки выше).
2. Проверьте переменные окружения (`.env`, `env.example`).
3. Убедитесь, что зависимые сервисы запущены (`make docker-up`, `kubectl get pods`).
4. Прогоните `make check-runtime` и `make install` при первом запуске.
5. На Windows используйте аналоги из [`scripts/windows/`](windows/README.md).

## 📎 Связанные разделы
- [Docs: Getting Started](../docs/01-getting-started/README.md)
- [Docs: Deployment](../docs/04-deployment/README.md)
- [Docs: Ops Playbook](../docs/ops/README.md)
- [Docs: Security & Policy](../docs/security/README.md)

Обновляйте этот индекс при добавлении новых сценариев или изменении пайплайнов. Скрипты без описания — повод создать README в соответствующей папке.
