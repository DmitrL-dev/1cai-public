# Observability Examples

**Version:** 1.0 | **Last Updated:** 2025-11-27

## Overview
Примеры настройки observability для 1C AI Stack.

---

## 📊 Prometheus Metrics Example

### metrics.py
```python
from prometheus_client import Counter, Histogram, Gauge
from prometheus_client import start_http_server

# Counters
api_requests_total = Counter(
    'api_requests_total',
    'Total API requests',
    ['method', 'endpoint', 'status']
)

# Histograms
api_response_time = Histogram(
    'api_response_seconds',
    'API response time',
    ['endpoint']
)

# Gauges
active_connections = Gauge(
    'active_connections',
    'Number of active connections'
)

# Start metrics server
start_http_server(9090)
```

### Usage
```python
@app.get("/api/data")
async def get_data():
    with api_response_time.labels('/api/data').time():
        api_requests_total.labels('GET', '/api/data', '200').inc()
        return {"data": "..."}
```

---

## 📝 Structured Logging Example

### logging_config.py
```python
import structlog

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

log = structlog.get_logger()
```

### Usage
```python
log.info("api_request",
         method="GET",
         path="/api/data",
         user_id="usr_123",
         duration_ms=234,
         status=200)
```

---

## 🔍 OpenTelemetry Tracing Example

### tracing.py
```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.jaeger.thrift import JaegerExporter

# Setup tracer
trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)

# Setup Jaeger exporter
jaeger_exporter = JaegerExporter(
    agent_host_name="localhost",
    agent_port=6831,
)

trace.get_tracer_provider().add_span_processor(
    BatchSpanProcessor(jaeger_exporter)
)
```

### Usage
```python
@app.get("/api/data")
async def get_data():
    with tracer.start_as_current_span("get_data"):
        with tracer.start_as_current_span("db_query"):
            data = await db.query("SELECT * FROM data")
        
        with tracer.start_as_current_span("process_data"):
            result = process(data)
        
        return result
```

---

## 📈 Grafana Dashboard Example

### dashboard.json
```json
{
  "dashboard": {
    "title": "1C AI Stack - API Performance",
    "panels": [
      {
        "title": "Request Rate",
        "targets": [
          {
            "expr": "rate(api_requests_total[5m])"
          }
        ]
      },
      {
        "title": "Response Time (p95)",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, api_response_seconds)"
          }
        ]
      },
      {
        "title": "Error Rate",
        "targets": [
          {
            "expr": "rate(api_requests_total{status=~\"5..\"}[5m])"
          }
        ]
      }
    ]
  }
}
```

---

## 🚨 Alert Rules Example

### alerts.yml
```yaml
groups:
  - name: api_alerts
    rules:
      - alert: HighErrorRate
        expr: rate(api_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value }} (threshold: 0.05)"

      - alert: SlowResponseTime
        expr: histogram_quantile(0.95, api_response_seconds) > 0.5
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Slow API response time"
          description: "p95 response time is {{ $value }}s (threshold: 0.5s)"
```

---

**See Also:**
- [Observability Quick Reference](../../quick-reference/OBSERVABILITY.md)
- [Metrics Guide](../../../06-features/METRICS_GUIDE.md)
- [Analytics Guide](../../../06-features/ANALYTICS_GUIDE.md)
