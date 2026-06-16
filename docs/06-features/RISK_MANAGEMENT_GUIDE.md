# Risk Management — Руководство пользователя

**Версия:** 1.0 | **Статус:** ✅ Production Ready | **API:** `/api/v1/risk`

## Обзор
**Risk Management** — управление рисками проекта. Идентификация, оценка, митигация рисков.

**Возможности:** 🎯 Risk Identification | 📊 Risk Assessment | 🛡️ Mitigation Plans | 📈 Risk Tracking | 🔔 Alerts

## Quick Start
```python
# Создать риск
risk = await client.post("/api/v1/risk/create", json={
    "title": "Database migration delay",
    "description": "Migration may take longer than planned",
    "probability": 0.7,
    "impact": "high",
    "category": "technical"
})

# Добавить план митигации
await client.post(f"/api/v1/risk/{risk['id']}/mitigation", json={
    "action": "Start migration 2 weeks earlier",
    "owner": "DBA Team",
    "deadline": "2025-12-01"
})
```

## API Reference
```http
POST /api/v1/risk/create
{
  "title": "Third-party API unavailable",
  "probability": 0.3,
  "impact": "medium",
  "category": "external"
}

Response:
{
  "id": "risk_123",
  "risk_score": 0.45,
  "priority": "medium"
}
```

## Risk Matrix
- **Critical:** probability > 0.7 AND impact = high
- **High:** probability > 0.5 OR impact = high
- **Medium:** probability > 0.3 OR impact = medium
- **Low:** probability < 0.3 AND impact = low

## FAQ
**Q: Как часто обновлять риски?** A: Еженедельно на sprint planning  
**Q: Кто может создавать риски?** A: Все члены команды

---
**Документация:** [Risk Management API](../api/RISK_MANAGEMENT_API.md)
