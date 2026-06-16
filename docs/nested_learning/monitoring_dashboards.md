# Nested Learning - Monitoring Dashboards

**Версия:** 1.0 | **Platform:** Grafana

## Overview

Мониторинг Nested Learning через Grafana dashboards для отслеживания training progress, model performance, и system health.

## Dashboards

### 1. Training Progress Dashboard

**Metrics:**
- Training progress по уровням
- Loss и accuracy в real-time
- Estimated time remaining
- Resource usage (CPU, GPU, Memory)

**Grafana Query:**
```promql
# Training progress
nested_learning_training_progress{level="1"}
nested_learning_training_progress{level="2"}
nested_learning_training_progress{level="3"}

# Accuracy
nested_learning_accuracy{level="1"}
```

### 2. Model Performance Dashboard

**Metrics:**
- Inference latency (p50, p95, p99)
- Throughput (requests/sec)
- Error rate
- Model accuracy по уровням

**Grafana Query:**
```promql
# Latency
histogram_quantile(0.95, nested_learning_inference_duration_seconds_bucket)

# Throughput
rate(nested_learning_requests_total[5m])
```

### 3. System Health Dashboard

**Metrics:**
- GPU utilization
- Memory usage
- Disk I/O
- Network bandwidth

## Alerts

```yaml
# alerts.yml
groups:
  - name: nested_learning
    rules:
      - alert: HighInferenceLatency
        expr: nested_learning_inference_duration_seconds > 1
        for: 5m
        annotations:
          summary: "High inference latency"
          
      - alert: LowAccuracy
        expr: nested_learning_accuracy < 0.8
        for: 10m
        annotations:
          summary: "Model accuracy below threshold"
```

## Setup

```bash
# Import dashboards
curl -X POST http://grafana:3000/api/dashboards/db \
  -H "Content-Type: application/json" \
  -d @nested_learning_dashboard.json
```

---

**См. также:**
- [Performance Benchmarks](performance_benchmarks.md)
- [API Documentation](api_documentation.md)
