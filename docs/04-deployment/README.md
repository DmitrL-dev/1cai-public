# 🚀 Deployment Guide

Инструкции по развёртыванию 1C AI Stack в разных окружениях — от локального Docker до Kubernetes/Argo CD.

---

## 📚 Навигация по разделу
| Документ | Что внутри |
|----------|------------|
| [`PRODUCTION_DEPLOYMENT.md`](PRODUCTION_DEPLOYMENT.md) | Подробный сценарий продакшн-развёртывания (Helm, Vault, Linkerd, GitOps). |
| [`instructions.md`](instructions.md) | Общие требования к инфраструктуре и переменным окружения. |
| [`production.md`](production.md) | Чек-лист готовности и контрольные вопросы. |
| [`migrations.md`](migrations.md) | Подготовка БД: PostgreSQL → Neo4j → Qdrant. |
| [`kubernetes/`](kubernetes/) | Kustomize-манифесты (namespace, ingress, deployments, PVC). |
| `security/` | Политики сети и TLS-скрипты. |

---

## ⚡ Быстрый старт (локально)
```bash
make docker-up      # поднимает PostgreSQL, Neo4j, Redis, Qdrant, брокеры
make migrate        # выполняет последовательность миграций
make servers        # старт Graph API + MCP
```
- Остановить: `make docker-down`
- Проверить статус: `docker compose ps`
- Windows: используйте PowerShell аналоги в `scripts/windows/`.

---

## ☁️ Kubernetes и GitOps
1. **Подготовка кластера:** используйте `infrastructure/kind/cluster.yaml` (локально) или Terraform-модули (`infrastructure/terraform/aws-eks`, `azure-aks`).
2. **Базовая установка:**
   ```bash
   make gitops-apply      # создаёт Argo CD приложения и синхронизирует чарты
   make vault-csi-apply   # настраивает Vault CSI провайдер
   make linkerd-install   # ставит Linkerd (или restore из backup)
   ```
3. **Синхронизация:** `make gitops-sync` или `scripts/gitops/sync.sh`.
4. **Helm charts:** лежат в `infrastructure/helm/1cai-stack` (основное приложение) и `infrastructure/helm/observability-stack` (Prometheus/Loki/Tempo/Grafana/OTEL).
5. **Секреты и конфигурация:** синхронизируются скриптами `scripts/secrets/*.py` (AWS/Azure → Vault → Kubernetes).

---

## 🔐 Безопасность и сеть
- NetworkPolicy пример: `security/network-policy.yaml`.
- TLS: `security/ssl-tls-setup.sh` (создание сертификатов и Secret).
- Проверка политик: `make policy-check` (Conftest, Semgrep, Checkov/Trivy).

---

## ✅ Перед релизом
1. `make preflight`
2. `make test` / `make test-bsl`
3. `make render-uml` (если менялись диаграммы)
4. `make policy-check` (если трогали инфраструктурные манифесты)
5. После деплоя зафиксируйте вывод `make gitops-sync`/`kubectl get pods` и обновите [`docs/runbooks/dr_rehearsal_plan.md`](../runbooks/dr_rehearsal_plan.md)

---

[⬅️ AI Agents](../03-ai-agents/README.md) | [➡️ Development](../05-development/README.md)

