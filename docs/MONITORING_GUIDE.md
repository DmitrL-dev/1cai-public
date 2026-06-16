# 📊 Monitoring & Observability Guide

**Complete guide to monitoring 1C AI Stack**

---

## 🎯 Overview

Monitoring stack включает:
- **Prometheus** - метрики
- **Grafana** - визуализация
- **ELK Stack** - логи (опционально)
- **Health checks** - проверки здоровья

---

## 🚀 Quick Start

### Запуск monitoring stack:

```bash
# Запустить Prometheus + Grafana
docker-compose -f docker-compose.monitoring.yml up -d

# Проверить
docker ps | grep -E "prometheus|grafana"
```

**Доступ:**
- **Prometheus:** http://localhost:9090
- **Grafana:** http://localhost:3000 (admin/admin)

---

## 📈 Prometheus Setup

### Configuration

```yaml
# monitoring/prometheus/prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: '1c-ai-api'
    static_configs:
      - targets: ['host.docker.internal:8000']
  
  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres-exporter:9187']
  
  - job_name: 'redis'
    static_configs:
      - targets: ['redis-exporter:9121']
```

### Key Metrics

**Application metrics:**
```promql
# Request rate
rate(http_requests_total[5m])

# Response time
histogram_quantile(0.95, http_request_duration_seconds)

# Error rate
rate(http_requests_total{status=~"5.."}[5m])
```

**Database metrics:**
```promql
# PostgreSQL connections
pg_stat_database_numbackends

# Query time
rate(pg_stat_statements_total_time[5m])

# Redis memory
redis_memory_used_bytes
```

---

## 📊 Grafana Dashboards

### Pre-configured Dashboards

1. **System Overview** - общий обзор системы
   - Request rate, response time
   - Error rate, uptime
   - Resource usage (CPU, RAM)

2. **AI Agents Performance**
   - Agent utilization
   - Response times по агентам
   - Success rates

3. **Database Performance**
   - Connections, queries/sec
   - Query latency
   - Cache hit rates

4. **Telegram Bot**
   - Active users
   - Messages processed
   - Response times

### Accessing Dashboards

```bash
# 1. Открыть Grafana
open http://localhost:3000

# 2. Login: admin / admin
# 3. Dashboards → Browse
# 4. Выбрать dashboard
```

### Creating Custom Dashboard

```bash
# 1. Grafana UI: Create → Dashboard
# 2. Add Panel
# 3. Query: выберите Prometheus
# 4. Metric: начните вводить (autocomplete)
```

---

## 🏥 Health Checks

### Application Health

```bash
# FastAPI
curl http://localhost:8000/health

# Response:
{
  "status": "healthy",
  "version": "5.1.0",
  "uptime": 3600,
  "checks": {
    "database": "ok",
    "redis": "ok",
    "ai_services": "ok"
  }
}
```

### Database Health

```bash
# PostgreSQL
docker exec 1c-ai-postgres pg_isready
# postgres is accepting connections

# Redis
docker exec 1c-ai-redis redis-cli PING
# PONG

# Neo4j
curl http://localhost:7474/db/neo4j/tx/commit
```

---

## 📝 Logging

### Log Levels

```bash
# .env
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FORMAT=json # json или text
```

### Viewing Logs

```bash
# Docker logs
docker-compose logs -f api

# Конкретный сервис
docker-compose logs telegram-bot --tail=100

# Все логи
docker-compose logs --tail=1000 > all_logs.txt
```

### Log Aggregation

**Structured Logging (JSON):**
```json
{
  "timestamp": "2025-11-06T12:00:00Z",
  "level": "INFO",
  "service": "telegram-bot",
  "message": "Message processed",
  "user_id": 123456,
  "duration_ms": 234
}
```

**ELK Stack (опционально):**
```bash
# Запустить ELK
docker-compose -f docker-compose.monitoring.yml \
  --profile elk up -d

# Kibana: http://localhost:5601
```

---

## 🔔 Alerting

### Prometheus Alerts

```yaml
# monitoring/prometheus/alerts/system_alerts.yml
groups:
  - name: 1c-ai-alerts
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        annotations:
          summary: "High error rate detected"
      
      - alert: DatabaseDown
        expr: up{job="postgres"} == 0
        for: 1m
        annotations:
          summary: "PostgreSQL is down"
```

### Alertmanager

```yaml
# monitoring/alertmanager/alertmanager.yml
receivers:
  - name: 'telegram'
    telegram_configs:
      - bot_token: 'your_bot_token'
        chat_id: your_chat_id
```

---

## 📉 Performance Monitoring

### Key Performance Indicators (KPIs)

```yaml
Availability: >99.5%
Response Time (p95): <2s
Error Rate: <0.1%
Cache Hit Rate: >70%
```

### Tracking in Grafana

**SLA Dashboard:**
- Uptime (последние 30 дней)
- Average response time
- Error rate trend
- SLA compliance (%)

**Queries:**
```promql
# Uptime
avg_over_time(up{job="1c-ai-api"}[30d])

# P95 response time
histogram_quantile(0.95,
  rate(http_request_duration_seconds_bucket[5m])
)
```

---

## 🔍 Debugging with Metrics

### Slow Requests

```promql
# Найти медленные endpoints
topk(10, 
  histogram_quantile(0.95,
    rate(http_request_duration_seconds_bucket[5m])
  )
) by (endpoint)
```

### High Memory Usage

```promql
# Memory usage trend
container_memory_usage_bytes{name="1c-ai-api"}

# Alert if >80%
container_memory_usage_bytes / container_spec_memory_limit_bytes > 0.8
```

### Database Issues

```promql
# Long-running queries
pg_stat_activity_max_tx_duration > 30

# Connection pool saturation
pg_stat_database_numbackends / pg_settings_max_connections > 0.8
```

---

## 📱 Application Metrics

### Custom Metrics (Python)

```python
from prometheus_client import Counter, Histogram

# Counter example
telegram_messages = Counter(
    'telegram_messages_total',
    'Total Telegram messages',
    ['user_type']  # labels
)

# Usage
telegram_messages.labels(user_type='premium').inc()

# Histogram example
request_duration = Histogram(
    'request_duration_seconds',
    'Request duration'
)

# Usage
with request_duration.time():
    process_request()
```

### Exposing Metrics

```python
# src/main.py
from prometheus_client import make_asgi_app

# Mount metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)
```

**Access:** http://localhost:8000/metrics

---

## 🎯 Monitoring Scenarios

### Scenario 1: System is slow

**Check:**
```promql
# 1. Response time spike?
rate(http_request_duration_seconds_sum[5m])

# 2. Database slow?
rate(pg_stat_statements_total_time[5m])

# 3. Memory issues?
container_memory_usage_bytes

# 4. CPU throttling?
rate(container_cpu_usage_seconds_total[5m])
```

---

### Scenario 2: Errors increasing

**Check:**
```promql
# 1. Which endpoint?
topk(5, rate(http_requests_total{status="500"}[5m])) by (endpoint)

# 2. Which service?
rate(http_requests_total{status="500"}[5m]) by (service)

# 3. Error types
logs search: level:ERROR | last 1h
```

---

### Scenario 3: High load

**Check:**
```promql
# 1. Request spike?
rate(http_requests_total[5m])

# 2. Legitimate traffic?
rate(http_requests_total[5m]) by (user_agent)

# 3. DDoS?
rate(http_requests_total[1m]) > 1000
```

---

## 🔗 Integration with External Services

### Sentry (Error Tracking)

```bash
# .env
SENTRY_DSN=https://key@sentry.io/project

# Python
import sentry_sdk
sentry_sdk.init(dsn=os.getenv("SENTRY_DSN"))
```

### DataDog (опционально)

```bash
# .env
DATADOG_API_KEY=your_datadog_key

# Agent
docker run -d --name datadog \
  -e DD_API_KEY=$DATADOG_API_KEY \
  -e DD_SITE="datadoghq.com" \
  datadog/agent:latest
```

---

## 📚 Dashboard Gallery

### Screenshots и примеры:

См. [monitoring/grafana/dashboards/](../monitoring/grafana/dashboards/)

- `overview.json` - ??? (нужно проверить)
- `system_overview.json` - главный dashboard
- `business_metrics.json` - бизнес метрики
- `celery_monitoring.json` - очереди задач
- `system_monitoring.json` - мониторинг системы

### System Overview

Дашборд `system_overview.json` служит быстрым health-check’ом площадки:

- **Request Rate / Success Rate** — `http_requests_total` c темплейтами `$job`, `$endpoint` и автоматическим clamping для избежания деления на ноль.
- **HTTP latency p95 / 5xx rate** — `histogram_quantile` по `http_request_duration_seconds_bucket` и `rate` для ошибок.
- **Active Users / Tenants** — Gauge `active_users`, `active_tenants{status="active"}`.
- **AI Queries / Latency** — `ai_queries_total`, `ai_response_duration_seconds_bucket` по фильтру `$agent`.
- **Cache hit % / DB pool** — расчёт на базе `cache_operations_total`, `db_pool_size`, `db_pool_available_connections`.
- **System CPU usage** — Gauge `system_cpu_usage_percent` от агента.

Темплейты `$datasource`, `$job`, `$endpoint`, `$agent`, `$cache_layer` позволяют переключать сервисы и компоненты без правки запросов.

### Business & Adoption Metrics

`business_metrics.json` показывает активность пользователей и использование AI:

- **Active Users / Tenants** — Gauge `active_users` и `active_tenants{status="active"}` с цветовыми порогами.
- **Tenants by Status / Projects by Status** — piechart с распределением `active_tenants` и `projects_total` по статусам.
- **AI Queries / Tokens** — метрики `ai_queries_total`, `ai_tokens_used_total` через `rate`/`increase` и фильтр `$agent`.
- **Code Reviews / Tests Generated** — `code_reviews_total`, `tests_generated_total` с выбором `$language`.
- **Projects** — отдельные стат-панели `projects_total{status="active"|"review"}`.

Темплейты `$datasource`, `$agent`, `$language` позволяют быстро переключать срезы. Дашборд рассчитан на накопительные счётчики (используем `increase()`/`rate()`), поэтому важен сохранённый retention в Prometheus.

### System Monitoring

`system_monitoring.json` обновлён под актуальные метрики Prometheus и внутреннего агента:

- **Активные таргеты / Алерты** — быстрые стат-панели по `up{}` и `ALERTS{alertstate="firing"}`.
- **Статус сервисов** — таблица с цветовым маппингом состояний для `instance` и `job` (фильтры через темплейты).
- **Инфраструктура** — CPU, RAM, диски c `node_exporter`, плюс отдельная линия `system_cpu_usage_percent` из нашего агента.
- **HTTP & сервисные метрики** — `http_requests_total`, `http_request_duration_seconds_bucket` с p95/p50 и отдельная серия для 5xx.
- **Темплейты**: `$datasource`, `$instance`, `$job`, `$endpoint` — помогают сузить выборку без редактирования запросов.

Важно: дашборд предполагает наличие Node Exporter и включённого `/metrics` сервиса приложения. Если часть таргетов отсутствует, убедитесь в актуальности scrape-конфигураций.

### Celery Tasks Monitoring

Dashboard `celery_monitoring.json` теперь привязан к актуальным метрикам `celery-exporter` и содержит готовые фильтры по очередям и задачам. Основные панели:

- **Active Workers** — `sum(celery_workers)`, цветовые пороги помогают заметить потерю воркеров.
- **Tasks Received/Failed (5m)** — прирост счётчиков `celery_tasks_total` по состояниям `received` и `failed` за последние 5 минут.
- **Success Rate %** — отношение `succeeded` к `received` с защитой от деления на ноль (`clamp_min`).
- **Task Throughput / Duration p95** — производительность и перцентили `histogram_quantile` по лейблу `name` (фильтр `$task`).
- **Queue Length** — `sum by (queue) (celery_queue_length)` с фильтром `$queue`.
- **Worker Availability** — `max_over_time(up{job=~"celery.*"}[5m])`, показывает стабильность таргетов в Prometheus.
- **Failures & Retries per minute** — скорость ошибок/повторных запусков для оперативного реагирования.
- **Top Failed Tasks / Queue Share (6h)** — таблица и круговая диаграмма по `increase(...[6h])` для ретроспективного анализа.

Темплейты `$queue`