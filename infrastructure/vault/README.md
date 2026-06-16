# Vault Configuration

## Политики
- [`policies/1cai-app.hcl`](policies/1cai-app.hcl) — доступ к KV `secret/data/1cai/*` (read/list) и lease management для приложения.

## Скрипт настройки
- [`scripts/configure.sh`](scripts/configure.sh) — включает KV v2, настраивает Kubernetes auth и роль `1cai-app`.

### Переменные окружения
- `VAULT_ADDR`, `VAULT_TOKEN` — адрес и токен администратора Vault.
- `KUBERNETES_HOST`, `KUBERNETES_REVIEWER_JWT` — данные API сервера и JWT service account для настройки Kubernetes Auth.

### Пример
```bash
cd infrastructure/vault/scripts
VAULT_ADDR=https://vault.example.com \
VAULT_TOKEN=... \
KUBERNETES_HOST=https://<cluster-endpoint> \
KUBERNETES_REVIEWER_JWT=$(cat token.jwt) \
./configure.sh
```

## Kubernetes CSI Driver
- Примеры в [`csi/`](csi/): `secret-provider-class.yaml` и `deployment-example.yaml`.
- Совместимы с Secrets Store CSI Driver + Vault provider (см. [официальную документацию](https://secrets-store-csi-driver.sigs.k8s.io/)).

## Работа с секретами
```bash
vault kv put secret/1cai/database url=... user=...
```
Синхронизация с Kubernetes — через `make vault-csi-apply` и скрипты [`scripts/secrets/`](../../scripts/secrets/README.md).

Дополнительные рекомендации и best practices описаны в [docs/ops/vault.md](../../docs/ops/vault.md).
