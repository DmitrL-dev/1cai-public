# Azure DevOps Pipeline

| Файл | Описание |
|------|----------|
| `azure-pipelines.yml` | Пример Azure DevOps pipeline: проверка кода, сборка контейнеров, деплой в AKS.

## Настройка
1. Импортируйте `azure-pipelines.yml` в Azure DevOps Pipeline.
2. Создайте сервисные подключения для ACR/AKS (или используйте Managed Identity).
3. Добавьте переменные: `AZURE_CONTAINER_REGISTRY`, `AZURE_SUBSCRIPTION`, `VAULT_TOKEN`, `ARGOCD_TOKEN` (если требуется).

Pipeline повторяет ключевые шаги Jenkins/GitLab, описанные в [docs/ops/devops_platform.md](../../docs/ops/devops_platform.md).
