# 📊 Документация системы мониторинга Demo AI Assistants

## 🎯 Обзор

Система мониторинга Demo AI Assistants обеспечивает комплексное наблюдение за всеми компонентами приложения, включая метрики, логи, трассировку и алерты. Архитектура построена на принципах observability и follows best practices современного DevOps.

## 🏗️ Архитектура мониторинга

```
┌─────────────────────────────────────────────────────────────┐
│                     Demo AI Assistants                      │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐   │
│  │ API Gateway │  │ Edge Functions│  │   Frontend      │   │
│  └─────┬───────┘  └──────┬───────┘  └────────┬────────┘   │
│        │                 │                     │           │
└────────┼─────────────────┼─────────────────────┼───────────┘
         │                 │                     │
    ┌────▼─────────────────▼─────────────────────▼────┐
    │           Application Metrics & Logs           │
    └────┬──────────────────┬─────────────────────┬────┘
         │                  │                     │
    ┌────▼─────┐     ┌──────▼──────┐      ┌─────▼─────┐
    │Prometheus│     │ Logstash    │      │ Jaeger    │
    │Metrics   │     │& Elasticsearch│     │ Tracing   │
    └──────────┘     └─────────────┘      └───────────┘
    ┌───────────────────────────────────────────────────┐
    │                   Grafana Dashboards             │
    │              + AlertManager Notifications        │
    └───────────────────────────────────────────────────┘
```

## 📊 Компоненты детально

### 🔍 Prometheus Stack

#### Prometheus
- **Роль**: Сбор и хранение метрик
- **Конфигурация**: `/monitoring/prometheus/prometheus.yml`
- **Хранение**: 30 дней retention, 10GB max size
- **Scrape конфигурация**:
  - API Gateway каждые 10 секунд
  - Supabase Edge Functions каждые 10 секунд
  - Node Exporter каждые 10 секунд
  - Database exporter каждые 10 секунд

#### AlertManager
- **Роль**: Управление алертами и уведомлениями
- **Конфигурация**: `/monitoring/alertmanager/alertmanager.yml`
- **Интеграции**: Slack, Email, PagerDuty, Webhooks
- **Маршрутизация**: По сервисам и severity

#### Node Exporter
- **Роль**: Системные метрики хоста
- **Конфигурация**: `/monitoring/prometheus/node_exporter.yml`
- **Метрики**: CPU, Memory, Disk, Network, Filesystem
- **Port**: 9100

### 📈 Grafana Dashboards

#### Overview Dashboard
- **URL**: http://localhost:3000/d/overview
- **Назначение**: Общий мониторинг всех сервисов
- **Ключевые панели**:
  - Service Status (real-time)
  - Request Rate (RPS)
  - Response Time (95th percentile)
  - Error Rate (%)
  - CPU & Memory Usage
  - Database Connections
  - Disk Usage

#### API Gateway Dashboard
- **URL**: http://localhost:3000/d/api-gateway
- **Назначение**: Детальная аналитика API Gateway
- **Метрики**:
  - Uptime статус
  - Requests per Second
  - Response Time percentiles (50th, 90th, 95th, 99th)
  - Error Rate by Status Code
  - Active Connections
  - Rate Limiter Statistics
  - Cache Hit Rate
  - Top 10 slow endpoints

#### Database Dashboard
- **URL**: http://localhost:3000/d/database
- **Назначение**: PostgreSQL мониторинг
- **Метрики**:
  - Connection Usage (%)
  - Database Activity (INSERT/UPDATE/DELETE)
  - Query Performance (read/write time)
  - Cache Hit Ratio
  - Deadlocks counter
  - Replication Lag
  - WAL Archiving status

### 📋 ELK Stack

#### Elasticsearch
- **Роль**: Поисковая система для логов
- **Версия**: 8.11.0
- **Конфигурация**: Single node deployment
- **Heap Size**: 2GB (Xms2g -Xmx2g)
- **Port**: 9200
- **Индексы**: По дням для оптимизации производительности

#### Logstash
- **Роль**: Обработка и трансформация логов
- **Input Sources**:
  - TCP (5000) - Application logs
  - UDP (5001) - Application logs  
  - Beats (5044) - Filebeat input
  - HTTP (8080) - Custom applications
- **Pipeline**: `/monitoring/elk/logstash/pipeline/logstash.conf`
- **Features**:
  - JSON parsing
  - GeoIP enrichment
  - Error detection
  - Critical event alerting

#### Kibana
- **Роль**: Визуализация и анализ логов
- **URL**: http://localhost:5601
- **Index Patterns**: `demo-ai-assistants-logs-*`
- **Features**:
  - Real-time log search
  - Custom visualizations
  - Log correlation
  - Anomaly detection

#### Filebeat
- **Роль**: Сбор логов Docker контейнеров
- **Конфигурация**: `/monitoring/elk/filebeat/filebeat.yml`
- **Sources**: 
  - `/var/lib/docker/containers/*/*.log`
  - Kubernetes logs (if applicable)
- **Features**:
  - JSON parsing
  - Multi-line support for stack traces
  - Auto-discovery containers
  - Environment enrichment

### 🔄 Distributed Tracing

#### Jaeger
- **Роль**: Distributed tracing система
- **Компоненты**:
  - Collector (14268, 14250, 9411)
  - Query Service (16686)
  - Elasticsearch backend
- **URL**: http://localhost:16686
- **Интеграция**: OpenTelemetry SDKs

#### OpenTelemetry Collector
- **Роль**: Centralized telemetry collection
- **Конфигурация**: `/monitoring/opentelemetry/collector-config.yaml`
- **Receivers**: OTLP, Jaeger, Zipkin, Prometheus
- **Processors**: Batch, Memory limiter, Resource processor
- **Exporters**: Jaeger, Prometheus, Elasticsearch, Logging

### 📡 Health Checks

#### Kubernetes Probes
```yaml
livenessProbe:
  httpGet:
    path: /health/live
    port: 8080
  initialDelaySeconds: 30
  periodSeconds: 30
  failureThreshold: 3

readinessProbe:
  httpGet:
    path: /health/ready  
    port: 8080
  initialDelaySeconds: 10
  periodSeconds: 10
  failureThreshold: 3

startupProbe:
  httpGet:
    path: /health/startup
    port: 8080
  initialDelaySeconds: 0
  periodSeconds: 5
  failureThreshold: 30
```

#### Custom Health Endpoints
- **Liveness**: `/health/live` - основная функциональность
- **Readiness**: `/health/ready` - готовность к трафику
- **Startup**: `/health/startup` - процесс запуска
- **Detailed**: `/health` - полная диагностика
- **Metrics**: `/metrics` - Prometheus метрики

## 🚨 Алерты и уведомления

### Критические алерты (🔴)

1. **ServiceDown** (Alert)
   ```yaml
   condition: up{job="api-gateway"} == 0
   duration: 1m
   severity: critical
   ```

2. **HighErrorRate** (Alert)
   ```yaml
   condition: |
     (rate(http_requests_total{status=~"5.."}[5m]) /
      rate(http_requests_total[5m])) * 100 > 5
   duration: 2m
   severity: critical
   ```

3. **HighMemoryUsage** (Alert)
   ```yaml
   condition: |
     (container_memory_usage_bytes{name!=""} /
      container_spec_memory_limit_bytes{name!=""} * 100) > 90
   duration: 5m
   severity: critical
   ```

### Предупреждения (🟡)

1. **HighLatency** (Alert)
   ```yaml
   condition: |
     histogram_quantile(0.95,
       rate(http_request_duration_seconds_bucket{job="api-gateway"}[5m])
     ) > 1
   duration: 5m
   severity: warning
   ```

2. **HighCPUUsage** (Alert)
   ```yaml
   condition: |
     (rate(container_cpu_usage_seconds_total{name!=""}[5m]) * 100) > 80
   duration: 5m
   severity: warning
   ```

### Уведомления

#### Slack интеграция
```yaml
slack_configs:
  - api_url: 'https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK'
    channel: '#critical-alerts'
    color: 'danger'  # Для критических
    color: 'warning' # Для предупреждений
```

#### Email уведомления
```yaml
email_configs:
  - to: 'critical-alerts@company.com'
    subject: '🚨 CRITICAL: {{ .GroupLabels.service }} - {{ .GroupLabels.alertname }}'
```

#### Маршрутизация по командам
- **API команда**: api-team@company.com → #api-alerts
- **Backend команда**: backend-team@company.com → #backend-alerts  
- **DBA команда**: dba-team@company.com → #database-alerts
- **DevOps команда**: devops-team@company.com → #devops-alerts

## 📝 Логирование

### Структура логов

Все логи структурированы в JSON формате:

```json
{
  "timestamp": "2025-11-02T10:57:28.000Z",
  "level": "info",
  "service": "api-gateway",
  "message": "Request processed successfully",
  "correlation_id": "trace-1730633848000-abc123def",
  "user_id": "user_67890",
  "request_duration": 125,
  "response_size": 1024,
  "endpoint": "/api/v1/predict",
  "method": "POST",
  "status": 200,
  "client_ip": "192.168.1.100",
  "environment": "production"
}
```

### Обязательные поля
- `timestamp` - ISO 8601 формат времени
- `level` - Уровень логирования (debug, info, warn, error, critical)
- `service` - Название сервиса
- `message` - Основное сообщение
- `correlation_id` - ID для трассировки (если доступен)

### Индексы Elasticsearch

1. **demo-ai-assistants-logs-YYYY.MM.dd** - Основные логи всех сервисов
2. **demo-ai-assistants-errors-YYYY.MM.dd** - Ошибки (level: error, critical)
3. **demo-ai-assistants-critical-YYYY.MM.dd** - Критические события

### Log rotation и архивирование

- **Индекс lifecycle**: 30 дней хранения
- **Hot-warm архитектура**: Hot (7 дней) → Warm (23 дня) → Delete
- **Snapshot бэкапы**: Ежедневно в S3 или аналог

## 🔍 Distributed Tracing

### Correlation IDs

Correlation ID используется для отслеживания запросов через всю систему:

```javascript
// Генерация correlation ID
const correlationId = `trace-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

// В HTTP заголовках
headers: {
  'X-Correlation-ID': correlationId,
  'X-Trace-ID': correlationId,
  'X-Span-ID': currentSpanId
}

// В логах
console.log(JSON.stringify({
  timestamp: new Date().toISOString(),
  level: 'info',
  service: 'api-gateway',
  message: 'Processing request',
  correlation_id: correlationId,
  request_id: requestId
}));
```

### Jaeger интеграция

1. **Instrumentation**: OpenTelemetry SDK в каждом сервисе
2. **Trace Collection**: Отправка в Jaeger Collector
3. **Correlation**: Trace ID связан с логами
4. **Performance Analysis**: Trace помогает найти bottleneck'ы

### OpenTelemetry Configuration

```yaml
# Collector конфигурация
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  batch:
    timeout: 1s
    send_batch_size: 8192
  resource:
    attributes:
      - key: service.name
        value: demo-ai-assistants
        action: upsert

exporters:
  jaeger:
    endpoint: jaeger-collector:14250
  elasticsearch:
    endpoints: [http://elasticsearch:9200]
    index: demo-traces-{+yyyy.MM.dd}
```

## 🏥 Health Checks

### Endpoint Specification

#### GET /health/live
```json
{
  "status": "alive",
  "timestamp": "2025-11-02T10:57:28.000Z",
  "uptime": 3600000,
  "checks": {
    "alive": true
  }
}
```

#### GET /health/ready
```json
{
  "status": "ready",
  "timestamp": "2025-11-02T10:57:28.000Z",
  "uptime": 3600000,
  "checks": {
    "ready": true,
    "dependencies": {
      "database": true,
      "cache": true,
      "external_services": true
    }
  }
}
```

#### GET /health
```json
{
  "status": "healthy",
  "timestamp": "2025-11-02T10:57:28.000Z",
  "version": "1.0.0",
  "environment": "production",
  "checks": {
    "liveness": {
      "status": "pass",
      "timestamp": "2025-11-02T10:57:28.000Z"
    },
    "readiness": {
      "status": "pass", 
      "timestamp": "2025-11-02T10:57:28.000Z"
    },
    "dependencies": {
      "database": {
        "status": "healthy",
        "service": "PostgreSQL/Supabase"
      },
      "cache": {
        "status": "healthy",
        "service": "Redis"
      },
      "external_services": {
        "status": "healthy",
        "service": "External APIs"
      }
    }
  }
}
```

### Kubernetes интеграция

Health checks интегрированы с Kubernetes через probe endpoints:

```yaml
spec:
  containers:
  - name: api-gateway
    livenessProbe:
      httpGet:
        path: /health/live
        port: 8080
      failureThreshold: 3
      periodSeconds: 30
      
    readinessProbe:
      httpGet:
        path: /health/ready
        port: 8080
      failureThreshold: 3
      periodSeconds: 10
```

## 📊 Performance Monitoring

### Ключевые метрики

1. **Latency Metrics**:
   - P50, P90, P95, P99 response times
   - Request duration histogram
   - Database query time

2. **Throughput Metrics**:
   - Requests per second (RPS)
   - Transactions per second (TPS)
   - Database connections active

3. **Error Metrics**:
   - Error rate percentage
   - HTTP status code distribution
   - Exception counts

4. **Resource Metrics**:
   - CPU usage percentage
   - Memory usage percentage
   - Disk I/O operations
   - Network throughput

### SLA Targets

- **Availability**: 99.5% uptime
- **Response Time**: P95 < 1s, P99 < 2s
- **Error Rate**: < 1% for critical paths
- **Database Performance**: Query time < 500ms (P95)

### Dashboards

1. **Executive Dashboard**: High-level KPI summary
2. **Operations Dashboard**: Real-time monitoring
3. **Development Dashboard**: Detailed debugging metrics
4. **Business Dashboard**: User behavior and usage patterns

## 🚀 Развертывание

### Требования

- Docker & Docker Compose
- Минимум 8GB RAM для полного стека
- 50GB свободного места для логов и метрик
- Сетевые порты: 3000, 5601, 8080, 9090, 9200, 16686, 24224

### Quick Start

```bash
# Клонирование репозитория
git clone <repository-url>
cd demo-ai-assistants-1c

# Запуск системы мониторинга
cd monitoring
docker-compose up -d

# Проверка статуса
docker-compose ps
docker-compose logs -f

# Открыть веб-интерфейсы
open http://localhost:3000  # Grafana
open http://localhost:5601  # Kibana
open http://localhost:16686  # Jaeger
```

### Production Considerations

1. **Security**:
   - Настройка TLS для всех интерфейсов
   - Аутентификация в Grafana и Kibana
   - Сетевые политики в Kubernetes

2. **High Availability**:
   - Multi-node Elasticsearch cluster
   - Prometheus federation
   - AlertManager clustering

3. **Performance**:
   - Настройка resource limits
   - Monitoring dashboard optimization
   - Log retention policies

## 🔧 Troubleshooting

### Общие проблемы

1. **Prometheus не собирает метрики**:
   ```bash
   # Проверка targets
   curl http://localhost:9090/api/v1/targets
   
   # Проверка конфигурации
   docker-compose logs prometheus
   ```

2. **Логи не попадают в Elasticsearch**:
   ```bash
   # Проверка Elasticsearch
   curl http://localhost:9200/_cluster/health
   
   # Проверка Logstash
   curl http://localhost:9600/_node/stats
   
   # Проверка Filebeat
   docker logs filebeat
   ```

3. **Алерты не отправляются**:
   ```bash
   # Проверка AlertManager
   curl http://localhost:9093/api/v1/alerts
   
   # Проверка webhook endpoints
   curl -X POST http://alertmanager-webhook:8080/test
   ```

4. **Jaeger не отображает traces**:
   ```bash
   # Проверка Jaeger collector
   curl http://localhost:14269/
   
   # Проверка OpenTelemetry collector
   curl http://localhost:8888/metrics
   ```

### Performance optimization

1. **Prometheus retention**:
   ```yaml
   command:
     - '--storage.tsdb.retention.time=30d'
     - '--storage.tsdb.retention.size=10GB'
   ```

2. **Elasticsearch heap**:
   ```yaml
   environment:
     - ES_JAVA_OPTS=-Xms4g -Xmx4g
   ```

3. **Log rotation**:
   ```yaml
   elasticsearch:
     setup.ilm.policy: "demo-logs-policy"
     setup.ilm.rollover_alias: "demo-ai-assistants-logs"
   ```

## 📚 Дополнительные ресурсы

### Документация
- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [Elasticsearch Guide](https://www.elastic.co/guide/)
- [Jaeger Documentation](https://www.jaegertracing.io/docs/)
- [OpenTelemetry Documentation](https://opentelemetry.io/docs/)
- [Kubernetes Health Checks](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/)

### Best Practices
- [Observability Best Practices](https://www.honeycomb.io/blog/observability-best-practices/)
- [Monitoring Microservices](https://www.datadoghq.com/resources/monitoring-microservices/)
- [Logging Best Practices](https://www.loggly.com/ultimate-guide/python-logging-best-practices/)

### Community
- [Prometheus Community](https://prometheus.io/community/)
- [Grafana Community](https://community.grafana.com/)
- [Elastic Community](https://www.elastic.co/community/)

---

**Документация системы мониторинга Demo AI Assistants** - полное руководство по observability! 🚀