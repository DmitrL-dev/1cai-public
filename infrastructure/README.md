# 🧱 Infrastructure Stack

В этом каталоге лежат артефакты для развёртывания 1C AI Stack: локальный Kubernetes, Helm charts, Terraform, GitOps-манифесты, Vault, сервис-меш и CI/CD конфигурации. Используйте эту страницу как карту входа.

## 🔍 Быстрая навигация
| Задача | Где смотреть | Make/CLI |
|--------|--------------|----------|
| Поднять локальный кластер | [`kind/`](kind/cluster.yaml) | `make kind-up` / `make kind-down` |
| Установить приложение через Helm | [`helm/1cai-stack/`](helm/1cai-stack/README.md) | `make helm-deploy` |
| Развернуть observability стек | [`helm/observability-stack/`](helm/observability-stack/README.md) | `make helm-observability` |
| Настроить GitOps (Argo CD) | [`argocd/`](argocd/README.md) | `make gitops-apply`, `make gitops-sync` |
| Настроить Vault/Secret Store | [`vault/`](vault/README.md), [`scripts/secrets/`](../scripts/secrets/README.md) | `make vault-csi-apply`, `scripts/secrets/*.py` |
| Сервис-меш (Linkerd/Istio) | [`service-mesh/`](service-mesh/README.md), [`scripts/service_mesh/`](../scripts/service_mesh/README.md) | `make linkerd-install`, `make linkerd-rotate-certs` |
| Terraform-ресурсы | [`terraform/`](terraform/README.md) + модули (`aws-eks/`, `azure-aks/`, `azure-keyvault/`) | `make terraform-apply`, `make terraform-destroy` |
| Ansible bootstrap | [`ansible/`](ansible/README.md) | `ansible-playbook -i hosts.ini site.yml` |
| Chaos/Litmus эксперименты | [`chaos/litmus/`](chaos/litmus/README.md) | `make chaos-litmus-run` |
| CI/CD pipelines | [`jenkins/Jenkinsfile`](jenkins/Jenkinsfile), [`gitlab/.gitlab-ci.yml`](gitlab/.gitlab-ci.yml), [`azure/azure-pipelines.yml`](azure/azure-pipelines.yml) | — |

## 🧰 Основные шаги
1. **Локальная инфраструктура:** поднимите Docker-стек (`make docker-up`) и/или Kind-кластер (`make kind-up`).
2. **Приложение:** `make helm-deploy` (или GitOps через `make gitops-apply`).
3. **Observability:** `make helm-observability` и `make observability-up` (локальный docker-compose).
4. **Secret store:** `make vault-csi-apply`, затем синхронизация секретов (`scripts/secrets/aws_sync_to_vault.py`, `azure_sync_to_vault.py`).
5. **Service Mesh:** `make linkerd-install`, генерация сертификатов (`scripts/service_mesh/linkerd/bootstrap_certs.sh`).
6. **FinOps/Security:** проверьте `make finops-slack`, `make policy-check`, `make preflight`.

Все шаги подробно описаны в соответствии с [docs/04-deployment/README.md](../docs/04-deployment/README.md) и [docs/ops/README.md](../docs/ops/README.md).

## 📂 Что внутри
- [`ansible/`](ansible/README.md) — bootstrap Linux-хостов (Docker, Helm, Terraform, kubectl).
- [`argocd/`](argocd/README.md) — Kustomize-манифесты AppProject и приложений Argo CD.
- [`helm/1cai-stack/`](helm/1cai-stack/README.md) — Helm chart приложения (API + MCP + Vault CSI).
- [`helm/observability-stack/`](helm/observability-stack/README.md) — Helm chart Prometheus/Loki/Tempo/Grafana/OTEL.
- [`terraform/`](terraform/README.md) — инфраструктурные модули и пример apply.
- [`vault/`](vault/README.md) — политики и CSI-манифесты Vault.
- [`service-mesh/`](service-mesh/README.md) — профили Linkerd и Istio.
- [`chaos/litmus/`](chaos/litmus/README.md) — chaos-эксперименты.
- [`kind/cluster.yaml`](kind/cluster.yaml) — конфиг локального Kubernetes.
- [`jenkins/`](jenkins/Jenkinsfile), [`gitlab/`](gitlab/.gitlab-ci.yml), [`azure/`](azure/azure-pipelines.yml) — примеры CI/CD pipeline.

## 🔗 Полезные материалы
- [docs/ops/devops_platform.md](../docs/ops/devops_platform.md)
- [docs/ops/gitops.md](../docs/ops/gitops.md)
- [docs/ops/service_mesh.md](../docs/ops/service_mesh.md)
- [docs/ops/vault.md](../docs/ops/vault.md)
- [docs/ops/finops.md](../docs/ops/finops.md)
- [docs/runbooks/dr_rehearsal_plan.md](../docs/runbooks/dr_rehearsal_plan.md)

Обновляйте этот индекс при добавлении новых компонентов инфраструктуры или изменении команд.
