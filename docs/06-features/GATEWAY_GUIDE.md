# Gateway — Руководство пользователя

**Версия:** 1.0 | **Статус:** ✅ Production Ready | **API:** `/api/v1/gateway`

## Обзор
**Gateway Module** — API Gateway для маршрутизации запросов, rate limiting, authentication.

**Возможности:** 🔀 Request Routing | ⏱️ Rate Limiting | 🔐 Authentication | 📊 Metrics | 🔄 Load Balancing | 🛡️ Security

## API Reference

### Route Request
```http
POST /api/v1/gateway/route
{
  "method": "GET",
  "path": "/api/v1/dashboard",
  "headers": {"Authorization": "Bearer ..."}
}

Response:
{
  "status": 200,
  "data": {...},
  "latency_ms": 45
}
```

### Health Check
```http
GET /api/v1/gateway/health

Response:
{
  "status": "healthy",
  "uptime": 86400,
  "requests_per_second": 150
}
```

## Configuration

```yaml
# gateway.yml
routes:
  - path: /api/v1/dashboard
    backend: http://dashboard-service:8000
    rate_limit: 100/minute
    
  - path: /api/v1/copilot
    backend: http://copilot-service:8000
    rate_limit: 10/minute
    timeout: 30s

middleware:
  - auth
  - rate_limit
  - metrics
```

## Rate Limiting

```python
# Настройка rate limits
await client.post("/api/v1/gateway/rate-limits", json={
    "endpoint": "/api/v1/copilot",
    "limit": 10,
    "window": "1m",
    "scope": "user"  # per user
})

# Проверка лимита
response = await client.get("/api/v1/copilot")
print(f"Remaining: {response.headers['X-RateLimit-Remaining']}")
```

## Load Balancing

```yaml
# Несколько backend серверов
routes:
  - path: /api/v1/dashboard
    backends:
      - http://dashboard-1:8000
      - http://dashboard-2:8000
      - http://dashboard-3:8000
    strategy: round_robin  # или least_connections
```

## Monitoring

```python
# Метрики gateway
metrics = await client.get("/api/v1/gateway/metrics")
print(f"Total requests: {metrics.json()['total_requests']}")
print(f"Avg latency: {metrics.json()['avg_latency_ms']}ms")
print(f"Error rate: {metrics.json()['error_rate']}%")
```

## Best Practices

1. **Timeouts:** Настройте разумные timeouts (30s для API, 5m для long-running)
2. **Circuit Breaker:** Включите для защиты от cascade failures
3. **Caching:** Кэшируйте часто запрашиваемые данные
4. **Monitoring:** Отслеживайте latency и error rate

## FAQ
**Q: Поддерживается ли gRPC?** A: Да, через gRPC-Web proxy  
**Q: Можно ли добавить custom middleware?** A: Да, см. [Custom Middleware Guide](GATEWAY_CUSTOM_MIDDLEWARE.md)

---

**Документация:** [Gateway API](../api/GATEWAY_API.md)
