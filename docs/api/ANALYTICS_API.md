# Analytics API Reference

**Version:** 1.0  
**Base URL:** `/api/v1/analytics`

## Endpoints

### Collect Metric
```http
POST /api/v1/analytics/metrics
{
  "name": "api_calls",
  "value": 1,
  "tags": {"endpoint": "/api/v1/dashboard"}
}
```

### Get Report
```http
GET /api/v1/analytics/reports/daily?start_date=2025-11-01&end_date=2025-11-27
```

### Create Dashboard
```http
POST /api/v1/analytics/dashboards
{
  "name": "Performance Dashboard",
  "widgets": [...]
}
```

### Export Metrics (Prometheus)
```http
GET /api/v1/analytics/export/prometheus
```

**See:** [Analytics Guide](../06-features/ANALYTICS_GUIDE.md)
