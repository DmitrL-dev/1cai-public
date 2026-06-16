# Analytics — Руководство пользователя

**Версия:** 1.0 | **Статус:** ✅ Production Ready | **API:** `/api/v1/analytics`

## Обзор
**Analytics Module** — сбор метрик, построение отчетов, визуализация данных, KPI tracking.

**Возможности:** 📊 Metrics Collection | 📈 Report Generation | 📉 Data Visualization | 🎯 KPI Tracking | 📅 Time Series Analysis | 🔔 Alerts

## API Reference

### Collect Metric
```http
POST /api/v1/analytics/metrics
{"name": "api_calls", "value": 1, "tags": {"endpoint": "/api/v1/dashboard"}}
```

### Get Report
```http
GET /api/v1/analytics/reports/daily?start_date=2025-11-01&end_date=2025-11-27

Response:
{
  "metrics": {
    "api_calls": 15234,
    "active_users": 523,
    "avg_response_time": 234
  },
  "charts": [...]
}
```

### Create Dashboard
```http
POST /api/v1/analytics/dashboards
{
  "name": "Performance Dashboard",
  "widgets": [
    {"type": "line_chart", "metric": "api_calls"},
    {"type": "gauge", "metric": "cpu_usage"}
  ]
}
```

## Примеры

```python
# Отправка метрики
await client.post("/api/v1/analytics/metrics", json={
    "name": "user_login",
    "value": 1,
    "tags": {"source": "web"}
})

# Получение отчета
report = await client.get("/api/v1/analytics/reports/weekly")
print(f"Total users: {report.json()['metrics']['total_users']}")
```

## Интеграция с Grafana

```python
# Экспорт метрик для Grafana
metrics = await client.get("/api/v1/analytics/export/prometheus")
# Настройте Grafana datasource на /api/v1/analytics/export/prometheus
```

## FAQ
**Q: Как долго хранятся метрики?** A: 90 дней (настраивается)  
**Q: Поддерживается ли real-time?** A: Да, через WebSocket `/api/v1/websocket/analytics`

---

**Документация:** [Analytics API](../api/ANALYTICS_API.md)
