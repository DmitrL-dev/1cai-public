# DevOps Platform Blueprint

> Обновлено: 11 ноября 2025 — пилотная версия современной платформы для 1C AI Stack.

## 1. Цели
- Быстрая доставка изменений (multi-stage pipeline).
- Репрожигаемость инфраструктуры (IaC, GitOps).
- Наблюдаемость и контроль безопасности по умолчанию.
- Масштабирование до production без смены инструментов.

## 2. Компоненты

| Категория | Инструмент | Назначение |
|-----------|------------|------------|
| Kubernetes | kind (локально), Helm chart `infrastructure/helm/1cai-stack` | базовый кластер и оркестрация сервисов |
| IaC | Terraform (`infrastructure/terraform`) | описывает namespace и устанавливает chart |
| CI/CD | Jenkins (`infrastructure/jenkins/Jenkinsfile`), GitLab CI (`infrastructure/gitlab/.gitlab-ci.yml`) | multi-stage pipeline с lint/test/security/build/deploy |
| Observability | Helm chart `infrastructure/helm/observability-stack` (Prometheus + Loki + Tempo + OTEL + Grafana) | метрики, логи, трейсы, дашборды |
| Registry | GHCR (по умолчанию) | хранение контейнеров |
| Secret store | HashiCorp Vault (адрес `vault.vault:8200`) | выдача секретов приложения и пайплайна |
| Security scans | Bandit, pip-audit, Safety, Trufflehog | статический анализ и поиск секрета |

## 3. Поток изменений

1. **Разработчик** пушит ветку → запускается Jenkins/GitLab пайплайн.
2. `lint` / `test` / `security` стадии выполняют `make` таргеты и скрипт `scripts/security/run_security_scans.sh`.
3. `build` создаёт образ и пушит в GHCR (или GitLab registry).
4. `deploy-kind` (preview) — устанавливает Helm chart в локальный kind-кластер (интеграционные проверки).
5. `deploy` (manual) — Terraform применяет Helm chart в production кластере.
6. Alertmanager / Prometheus отслеживают состояние; отчёты публикуются в Telegram.
4. `make helm-observability` → устанавливает Prometheus/Loki/Tempo/Grafana/OTEL Collector/Promtail в namespace `observability`.

## 4. Onboarding

1. Создать кластер `kind create cluster --config infrastructure/kind/cluster.yaml`.
2. Применить Helm chart (`helm upgrade --install ...`).
3. Настроить Jenkins:
   - Credentials: `registry-ghcr`, `kubeconfig-1cai`, `kubeconfig-prod`, `vault-token`.
   - Agent с Docker + kubectl + helm + terraform.
4. Настроить GitLab CI variables:
   - `KIND_KUBECONFIG_B64`, `KUBE_PROD_CONFIG_B64`, `CI_REGISTRY_USER/PASSWORD`.

## 5. Следующие шаги
- Подключить Argo CD/Flux для GitOps (watch Helm release).
- Модуль Terraform для managed Kubernetes (EKS/AKS/GKE).
- IaC для Vault (policies, Kubernetes auth).
- Автоматическая публикация Helm chart в собственный репозиторий.
- Настроить политики Conftest/OPA (см. план security).
- Подключить Prometheus Operator/kube-prometheus-stack, когда выпадет необходимость.

## 6. Благодарности
- kind (https://kind.sigs.k8s.io/)
- Terraform (https://www.terraform.io/)
- Jenkins (https://www.jenkins.io/)
- GitLab CI (https://docs.gitlab.com/ee/ci/)

Благодарим авторов за открытые инструменты, на которых построена платформа.
