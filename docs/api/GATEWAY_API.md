# Gateway API Reference

**Version:** 1.0  
**Base URL:** `/api/v1/gateway`

## Endpoints

### Route Request
```http
POST /api/v1/gateway/route
{
  "method": "GET",
  "path": "/api/v1/dashboard"
}
```

### Health Check
```http
GET /api/v1/gateway/health
```

### Rate Limits
```http
POST /api/v1/gateway/rate-limits
GET /api/v1/gateway/rate-limits
```

### Metrics
```http
GET /api/v1/gateway/metrics
```

**See:** [Gateway Guide](../06-features/GATEWAY_GUIDE.md)
