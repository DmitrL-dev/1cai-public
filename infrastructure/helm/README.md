# Helm Charts

В каталоге два Helm chart'а:

| Каталог | Назначение |
|---------|------------|
| [`1cai-stack/`](1cai-stack/README.md) | Основное приложение (API, MCP, сервисы, Vault CSI). |
| [`observability-stack/`](observability-stack/README.md) | Prometheus, Loki, Tempo, Grafana, OTEL Collector, Promtail.

## Быстрые команды
```bash
# Деплой приложения
make helm-deploy

# Деплой observability stack
make helm-observability
```

Перед деплоем убедитесь, что namespace созданы и секреты Vault доступны. Подробнее — [docs/04-deployment/README.md](../../docs/04-deployment/README.md).
