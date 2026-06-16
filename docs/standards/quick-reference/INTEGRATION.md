# Quick Reference: Integration Standards

**Version:** 1.0 | **Last Updated:** 2025-11-27

## Overview
Краткий справочник по стандартам интеграции для 1C AI Stack.

---

## 🔌 Integration Patterns

### REST API Integration
```python
import requests

response = requests.post(
    "https://api.1cai.com/v1/integrate",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={"data": "..."}
)
```

### WebSocket Integration
```javascript
const ws = new WebSocket('wss://api.1cai.com/ws');
ws.onmessage = (event) => {
    console.log(event.data);
};
```

### Webhook Integration
```python
@app.post("/webhook")
async def handle_webhook(request: Request):
    payload = await request.json()
    # Process webhook
    return {"status": "ok"}
```

---

## 📋 Standards Checklist

- ✅ Authentication: JWT or OAuth 2.0
- ✅ Rate Limiting: 100 req/min
- ✅ Timeout: 30s max
- ✅ Retry: Exponential backoff
- ✅ Error Handling: Structured errors
- ✅ Logging: All requests logged
- ✅ Monitoring: Prometheus metrics

---

## 🔒 Security Requirements

1. **HTTPS Only** - All integrations over HTTPS
2. **API Keys** - Rotate every 90 days
3. **IP Whitelist** - Optional for sensitive endpoints
4. **Request Signing** - HMAC-SHA256 for webhooks

---

## 📊 Common Integration Scenarios

### Scenario 1: External System → 1C AI Stack
```
External System → API Gateway → Auth → Service → Response
```

### Scenario 2: 1C AI Stack → External System
```
1C AI Stack → Webhook → External System → Acknowledgment
```

### Scenario 3: Bidirectional Sync
```
System A ↔ Event Bus ↔ System B
```

---

**See Also:**
- [Integration Guides](../../07-integrations/)
- [API Reference](../../api/)
- [Security Standards](../SECURITY.md)
