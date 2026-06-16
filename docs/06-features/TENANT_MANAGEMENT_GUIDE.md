# Tenant Management — Руководство пользователя

**Версия:** 1.0 | **Статус:** ✅ Production Ready | **API:** `/api/v1/tenants`

## Обзор
**Tenant Management API** — управление multi-tenancy. Создание, управление, изоляция тенантов.

**Возможности:** 🏢 Tenant Registration | 👥 User Management | 💰 Billing | 📊 Usage Tracking | 🔒 Data Isolation

## Quick Start
```python
# Регистрация тенанта
tenant = await client.post("/api/v1/tenants/register", json={
    "name": "Acme Corp",
    "plan": "enterprise",
    "max_users": 100,
    "admin_email": "admin@acme.com"
})

# Добавить пользователя
await client.post(f"/api/v1/tenants/{tenant['id']}/users", json={
    "email": "user@acme.com",
    "role": "developer"
})

# Получить usage
usage = await client.get(f"/api/v1/tenants/{tenant['id']}/usage")
print(f"API calls: {usage.json()['api_calls']}")
```

## API Reference
```http
POST /api/v1/tenants/register
{
  "name": "Tech Startup Inc",
  "plan": "professional",
  "max_users": 50,
  "admin_email": "cto@startup.com"
}

Response:
{
  "id": "tenant_123",
  "name": "Tech Startup Inc",
  "status": "active",
  "created_at": "2025-11-27T12:00:00Z",
  "api_key": "tk_..."
}
```

## Plans
- **Free:** 5 users, 1000 API calls/month
- **Professional:** 50 users, 100K API calls/month
- **Enterprise:** Unlimited users, unlimited API calls

## Data Isolation
```python
# Каждый тенант имеет изолированные данные
# Автоматическая фильтрация по tenant_id
@router.get("/api/v1/projects")
async def get_projects(tenant_id: str = Depends(get_current_tenant)):
    # Возвращает только проекты этого тенанта
    return await db.fetch("SELECT * FROM projects WHERE tenant_id = $1", tenant_id)
```

## Billing
```python
# Получить счет
invoice = await client.get(f"/api/v1/tenants/{tenant_id}/billing/invoice")

# Обновить план
await client.put(f"/api/v1/tenants/{tenant_id}/plan", json={
    "plan": "enterprise"
})
```

## FAQ
**Q: Как работает изоляция данных?** A: Row-level security в PostgreSQL  
**Q: Можно ли перенести данные между тенантами?** A: Да, через export/import

---
**Документация:** [Tenant Management API](../api/TENANT_MANAGEMENT_API.md)
