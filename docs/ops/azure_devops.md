# Azure DevOps Pipeline

## 1. Назначение
- Альтернативный CI/CD для компаний на Azure DevOps (ADO).
- Включает lint/test/policy/build/deploy (AKS).

## 2. Файл
- `infrastructure/azure/azure-pipelines.yml` — добавьте в корень репозитория или импортируйте в ADO.

## 3. Требования
- Service connection `dockerRegistryServiceConnection` (Azure Container Registry или GHCR).
- Service connection `$(azureServiceConnection)` (Azure Resource Manager).
- Переменные: `AZURE_SUBSCRIPTION_ID`, `AKS_CLUSTER_NAME`, `AKS_RESOURCE_GROUP`.

## 4. Структура Pipeline
1. **Lint** — `make lint`.
2. **Tests** — `make test` + публикация JUnit.
3. **Security** — `scripts/security/run_policy_checks.sh` (helm/conftest/semgrep/checkov).
4. **Build** — Docker build/push (tags: commit + latest).
5. **Deploy_AKS** — Terraform apply (AKS), затем `make gitops-apply` (Helm via Argo CD manifests).

## 5. Следующие шаги
- Поддержка environments (staging/prod) через multi-stage deployment.
- Azure Key Vault интеграция (Managed Identity).
- Добавить оповещения (Teams/Slack) через pipeline notifications.
