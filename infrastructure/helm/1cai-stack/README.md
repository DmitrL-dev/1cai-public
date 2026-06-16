# Helm Chart: 1cai-stack

Чарт деплоит основные компоненты платформы: FastAPI (Graph API), MCP server, Vault CSI и сервисы.

## Структура
- `values.yaml` — дефолтные значения (образы, ресурсы, секреты, ingress).
- `templates/` — Deployment/Service для API и MCP, SecretProviderClass, ServiceAccount и Ingress.

## Быстрый старт
```bash
helm upgrade --install 1cai infrastructure/helm/1cai-stack \
  --namespace 1cai --create-namespace \
  -f infrastructure/helm/1cai-stack/values.yaml
```

## Настройки
- `image.repository/tag` — образы API и MCP.
- `ingress.*` — параметры ingress/host.
- `vault.*` — конфигурация Vault CSI (совместима с `scripts/secrets/`).
- `resources` — лимиты/requests для подов.

Перед установкой убедитесь, что Vault CSI и секреты настроены (см. [`docs/ops/vault.md`](../../../docs/ops/vault.md)).
