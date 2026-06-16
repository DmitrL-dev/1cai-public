# Azure Key Vault Terraform Module (Preview)

## 1. Цель
- Создать Key Vault рядом с AKS/EKS инфраструктурой.
- Записать секреты и выдать доступ Managed Identity/Service Principal.

## 2. Структура
- `main.tf` — ресурсная группа (опционально), Key Vault, секреты, политики доступа.
- `variables.tf` — параметры (имена, местоположение, список секретов и доступов).
- `outputs.tf` — имя Key Vault, URI, списки секретов.

## 3. Запуск
```bash
cd infrastructure/terraform/azure-keyvault
terraform init
terraform apply \
  -var="resource_group_name=1cai-rg" \
  -var="location=westeurope" \
  -var="key_vault_name=kv1cai" \
  -var='secrets={ "database-url" = "postgres://..." }' \
  -var='access_policies=[{"object_id"="<aks-principal>","secret_permissions"=["Get","List"]}]'
```

## 4. Интеграция
- Используйте `scripts/secrets/azure_sync_to_vault.py` для синхронизации в Vault (если требуется).
- В Helm-значениях `vault.secretProviderClass.parameters.static` можно ссылаться на Key Vault URI (TODO).

## 5. TODO
- Миграция секретов из Key Vault в CSI (через external-secrets или sync скрипт).
- Заполнение trust anchors Linkerd из Key Vault.
