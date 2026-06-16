# Helm Chart: observability-stack

Чарт устанавливает мониторинговый стек: Prometheus, Grafana, Loki, Tempo, OTEL Collector, Promtail.

## Компоненты
- `deployment-prometheus.yaml`, `deployment-grafana.yaml`, `deployment-loki.yaml`, `deployment-tempo.yaml`, `deployment-otel.yaml`
- ConfigMap'ы с dashboards/datasources (`configmap-grafana-*`), Prometheus rules, Loki/Tempo конфигурации.
- DaemonSet Promtail для логов.

## Установка
```bash
make helm-observability
# или
helm upgrade --install observability infrastructure/helm/observability-stack \
  --namespace observability --create-namespace \
  -f infrastructure/helm/observability-stack/values.yaml
```

## Доступы
- Grafana — сервис `observability-stack-grafana` (порт 3000). Логин/пароль по умолчанию `admin/admin` (смените!).
- Prometheus — `observability-stack-prometheus` (порт 9090).
- OTEL Collector — `observability-stack-otel-collector` (порты 4317/4318).

Настройка и операции описаны в [`docs/observability/README.md`](../../../docs/observability/README.md).
