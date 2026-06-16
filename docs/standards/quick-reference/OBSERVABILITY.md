# Quick Reference: Observability Standards

**Version:** 1.0 | **Last Updated:** 2025-11-27

## Overview
Краткий справочник по стандартам observability для 1C AI Stack.

---

## 📊 Three Pillars of Observability

### 1. Metrics (Prometheus)
```python
from prometheus_client import Counter, Histogram

api_requests = Counter('api_requests_total', 'Total API requests')
response_time = Histogram('api_response_seconds', 'API response time')

@app.get("/api/data")
async def get_data():
    api_requests.inc()
    with response_time.time():
        return {"data": "..."}
```

### 2. Logs (Structured)
```python
import structlog

log = structlog.get_logger()
log.info("api_request", 
         method="GET", 
         path="/api/data",
         user_id="usr_123",
         duration_ms=234)
```

### 3. Traces (OpenTelemetry)
```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

with tracer.start_as_current_span("process_request"):
    # Process request
    pass
```

---

## 🎯 Key Metrics

### Golden Signals
1. **Latency** - Response time (p50, p95, p99)
2. **Traffic** - Requests per second
3. **Errors** - Error rate (%)
4. **Saturation** - Resource utilization (%)

### RED Method
- **Rate** - Requests per second
- **Errors** - Error rate
- **Duration** - Response time

### USE Method
- **Utilization** - % time resource busy
- **Saturation** - Queue length
- **Errors** - Error count

---

## 📈 Dashboards

### System Health Dashboard
- CPU Usage
- Memory Usage
- Disk I/O
- Network Traffic

### API Performance Dashboard
- Request Rate
- Response Time (p95)
- Error Rate
- Active Connections

### Business Metrics Dashboard
- Active Users
- API Calls per User
- Revenue Metrics
- Feature Usage

---

## 🚨 Alerting Rules

### Critical Alerts
```yaml
- alert: HighErrorRate
  expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
  for: 5m
  annotations:
    summary: "High error rate detected"

- alert: SlowResponseTime
  expr: histogram_quantile(0.95, http_request_duration_seconds) > 0.5
  for: 10m
  annotations:
    summary: "Slow API response time"
```

---

## 🔍 Debugging Workflow

1. **Check Dashboards** - Grafana
2. **Review Logs** - Loki/ELK
3. **Analyze Traces** - Jaeger
4. **Check Metrics** - Prometheus
5. **Root Cause** - Correlate all signals

---

**See Also:**
- [Metrics Guide](../../06-features/METRICS_GUIDE.md)
- [Analytics Guide](../../06-features/ANALYTICS_GUIDE.md)
- [DevOps Standards](./DEVOPS.md)
