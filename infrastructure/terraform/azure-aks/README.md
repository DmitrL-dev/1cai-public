# Azure AKS Terraform Module (Preview)

> Требования: Terraform >= 1.6, Azure CLI (`az login`), подписка с правами Contributor.

## 1. Структура
- `main.tf` — ресурсная группа, виртуальная сеть, AKS кластер, identity.
- `variables.tf` — параметры (subscription_id, location, node size).
- `outputs.tf` — kubeconfig, идентификаторы.

## 2. Запуск
```bash
cd infrastructure/terraform/azure-aks
terraform init
terraform apply -var="azure_subscription_id=<id>" -var="cluster_name=1cai-aks"
az aks get-credentials --resource-group 1cai-rg --name 1cai-aks
```

## 3. Интеграция
- Применить GitOps (`make gitops-apply`) c kubeconfig AKS.
- Использовать Managed Identity для Vault/Secret Manager (TODO).

## 4. TODO
- Terraform backend (Azure Storage + Table).
- Terraform role assignments (AcrPull, KeyVault).
- CI/CD в Azure DevOps (см. `infrastructure/azure/azure-pipelines.yml`).
