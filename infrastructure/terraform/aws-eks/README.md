# AWS EKS Terraform Module (Preview)

> Требования: Terraform >= 1.6, AWS CLI, учетные данные с правами на создание VPC/EKS/NodeGroup/IAM.

## 1. Структура
- `main.tf` — создает VPC, EKS кластер и node group через официальные модули `terraform-aws-modules`.
- `variables.tf` — параметры (region, cluster_name, node группы).
- `outputs.tf` — kubeconfig, ARN и IAM роли.

## 2. Быстрый старт
```bash
cd infrastructure/terraform/aws-eks
terraform init
terraform apply -var="aws_region=eu-central-1" -var="cluster_name=1cai-dev"
# После создания:
aws eks update-kubeconfig --name 1cai-dev --region eu-central-1
```

## 3. Интеграция
- Используйте `make gitops-apply`/`gitops-sync` для развертывания Helm charts на EKS (kubectl context должен указывать на кластер).
- Vault: настройте IAM role для `1cai-app` и политику доступа (см. TODO).

## 4. TODO
- Terraform backend (S3 + DynamoDB) — шаблон в `backend.tf.example` (добавить).
- Terragrunt поддержка.
- Автоматизация CI (`terraform plan/apply` через Jenkins/GitLab).
