# Terraform Stack

Terraform конфигурации для управления Kubernetes и сопутствующей инфраструктурой.

## Структура
| Каталог | Назначение |
|---------|------------|
| Корень (`main.tf`, `providers.tf`, `variables.tf`, `outputs.tf`) | Пример установки Helm release в существующий кластер.
| [`aws-eks/`](aws-eks/README.md) | Модуль развёртывания EKS и необходимых ресурсов AWS. |
| [`azure-aks/`](azure-aks/README.md) | Модуль развёртывания AKS. |
| [`azure-keyvault/`](azure-keyvault/README.md) | Модуль создания Azure Key Vault с секретами. |

## Использование (примеры)
```bash
cd infrastructure/terraform
terraform init
terraform apply -var="kubeconfig_path=$HOME/.kube/config" -var="kubeconfig_context=kind-1cai-devops"
```

Перед запуском:
- Убедитесь, что провайдеры (AWS/Azure/Kubernetes/Helm) настроены.
- Для state используйте удалённый backend (S3/Azure Storage) в реальных средах.

Дополнительно см. [`docs/ops/devops_platform.md`](../../docs/ops/devops_platform.md).
