# Metrics API Reference

**Version:** 1.0  
**Base URL:** `/api/v1/metrics`

## Endpoints

### Collect Custom Metric
```http
POST /api/v1/metrics/custom
{
  "name": "api_response_time",
  "value": 234,
  "type": "gauge"
}
```

### Get Metrics (Prometheus Format)
```http
GET /api/v1/metrics
```

### Export to StatsD
```http
POST /api/v1/metrics/statsd
```

**See:** [Metrics Guide](../06-features/METRICS_GUIDE.md)
