# Vault & Secret Management

## 1. Цели
- Централизованное управление секретами 1C AI Stack (Kubernetes/EKS/AKS).
- Минимальный доступ (least privilege), audit trail, короткие lease.

## 2. Файлы
- `infrastructure/vault/policies/1cai-app.hcl` — политика доступа к `secret/data/1cai/*`.
- `infrastructure/vault/scripts/configure.sh` — включает KV v2, Kubernetes auth, роль `1cai-app`.

## 3. Kubernetes интеграция
1. Настроить `vault auth enable kubernetes` (скрипт выше).
2. Создать service account `1cai-app` в namespace `1cai`.
3. Использовать Secrets Store CSI Driver:
   - `infrastructure/vault/csi/secret-provider-class.yaml` — описывает, какие данные из Vault попадут в K8s Secret `db-credentials`.
   - `infrastructure/vault/csi/deployment-example.yaml` — пример Deployment, подключающий volume `vault-secrets`.
   - Helm: `values.vault.enabled=true` → CSI интеграция; `values.vault.agent.enabled=true` → Vault Agent sidecar (рендерит `/vault/secrets/app.env`).
   - Скрипт `scripts/secrets/apply_vault_csi.sh` / `make vault-csi-apply` — быстрый запуск.

## 4. Cloud секреты
- AWS: скрипт `scripts/secrets/aws_sync_to_vault.py`.
- Azure: скрипт `scripts/secrets/azure_sync_to_vault.py`.
- Terraform модуль `infrastructure/terraform/azure-keyvault` — Key Vault + секреты + access policies.

## 5. Best Practices
- Политики только на нужные пути (`secret/data/1cai/*`).
- Короткие TTL, `vault lease renew` через агент.
- Audit log включен (`vault audit enable file ...`).
- Secrets никогда не коммитятся.
- При изменении секретов — перезапуск через Vault Agent sidecar (watcher) или `scripts/secrets/test_vault_sync.sh` + `make preflight`.

## 6. Проверка
- `scripts/secrets/test_vault_sync.sh` проверяет значение в Vault и Kubernetes secret; полезно для CI (`make vault-test`).

## 6. Roadmap
- CSI driver манифесты для K8s.
- Динамические секреты (PostgreSQL, Redis).
- Автоматический sync AWS Secrets → Vault.
