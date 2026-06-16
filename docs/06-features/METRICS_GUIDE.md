# Metrics — Руководство пользователя

**Версия:** 1.0 | **Статус:** ✅ Production Ready | **API:** `/api/v1/metrics`

## Обзор
**Metrics Module** — сбор и экспорт метрик. Prometheus-compatible metrics, custom metrics.

**Возможности:** 📊 Prometheus Format | 📈 Custom Metrics | 🎯 Performance Metrics | 🔔 Alerts | 📉 Time Series | 🔄 Auto-export

## Quick Start

```python
# Отправка custom метрики
await client.post("/api/v1/metrics/custom", json={
    "name": "api_response_time",
    "value": 234,
    "type": "gauge",
    "labels": {"endpoint": "/api/v1/dashboard"}
})

# Получение метрик (Prometheus format)
metrics = await client.get("/api/v1/metrics")
print(metrics.text)  # Prometheus format
```

## Prometheus Integration

```yaml
# prometheus.yml
scrape_configs:
  - job_name: '1c-ai-stack'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/api/v1/metrics'
    scrape_interval: 15s
```

## Custom Metrics

```python
from prometheus_client import Counter, Gauge, Histogram

# Counter
requests_total = Counter('requests_total', 'Total requests', ['endpoint'])
requests_total.labels(endpoint='/api/v1/dashboard').inc()

# Gauge
active_users = Gauge('active_users', 'Active users')
active_users.set(523)

# Histogram
response_time = Histogram('response_time_seconds', 'Response time')
with response_time.time():
    # Your code here
    pass
```

## Built-in Metrics

- `http_requests_total` — Total HTTP requests
- `http_request_duration_seconds` — Request duration
- `active_connections` — Active connections
- `cpu_usage_percent` — CPU usage
- `memory_usage_bytes` — Memory usage
- `db_connections_active` — Active DB connections

## Grafana Dashboards

```python
# Импорт готового дашборда
import requests

dashboard = {
    "dashboard": {
        "title": "1C AI Stack Metrics",
        "panels": [...]
    }
}

requests.post(
    "http://grafana:3000/api/dashboards/db",
    json=dashboard,
    headers={"Authorization": f"Bearer {grafana_token}"}
)
```

## FAQ
**Q: Как долго хранятся метрики?** A: Зависит от Prometheus retention (по умолчанию 15 дней)  
**Q: Поддерживается ли StatsD?** A: Да, через `/api/v1/metrics/statsd`

---

**Документация:** [Metrics API](../api/METRICS_API.md)
