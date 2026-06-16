# Admin Dashboard — Руководство пользователя

**Версия:** 1.0 | **Статус:** ✅ Production Ready | **API:** `/api/v1/admin_dashboard`

## Обзор
**Admin Dashboard** — административная панель для управления платформой. Управление пользователями, тенантами, настройками.

**Возможности:** 👥 User Management | 🏢 Tenant Management | ⚙️ Settings | 📊 Analytics | 🔒 Security | 📝 Audit Logs

## Quick Start

```python
# Получить admin dashboard
dashboard = await client.get("/api/v1/admin_dashboard")

print(f"Total users: {dashboard.json()['users']['total']}")
print(f"Active tenants: {dashboard.json()['tenants']['active']}")
print(f"System health: {dashboard.json()['system']['health']}")
```

## API Reference

### Get Dashboard
```http
GET /api/v1/admin_dashboard

Response:
{
  "users": {
    "total": 1523,
    "active_today": 342,
    "new_this_month": 45
  },
  "tenants": {
    "total": 25,
    "active": 23,
    "trial": 5
  },
  "system": {
    "health": "healthy",
    "cpu_usage": 45,
    "memory_usage": 62,
    "disk_usage": 38
  },
  "recent_activity": [...]
}
```

### Manage Users
```http
# Список пользователей
GET /api/v1/admin_dashboard/users?page=1&limit=50

# Блокировать пользователя
POST /api/v1/admin_dashboard/users/{id}/block

# Изменить роль
PUT /api/v1/admin_dashboard/users/{id}/role
{"role": "admin"}
```

### Manage Tenants
```http
# Список тенантов
GET /api/v1/admin_dashboard/tenants

# Создать тенанта
POST /api/v1/admin_dashboard/tenants
{
  "name": "Acme Corp",
  "plan": "enterprise",
  "max_users": 100
}

# Приостановить тенанта
POST /api/v1/admin_dashboard/tenants/{id}/suspend
```

### System Settings
```http
# Получить настройки
GET /api/v1/admin_dashboard/settings

# Обновить настройки
PUT /api/v1/admin_dashboard/settings
{
  "max_file_upload_size": 10485760,
  "session_timeout_minutes": 60,
  "enable_2fa": true
}
```

### Audit Logs
```http
GET /api/v1/admin_dashboard/audit?user_id=usr_123&action=login&start_date=2025-11-01

Response:
{
  "logs": [
    {
      "timestamp": "2025-11-27T12:00:00Z",
      "user_id": "usr_123",
      "action": "login",
      "ip_address": "192.168.1.1",
      "user_agent": "Mozilla/5.0..."
    }
  ]
}
```

## Security Features

```python
# Проверка подозрительной активности
suspicious = await client.get("/api/v1/admin_dashboard/security/suspicious")

for activity in suspicious.json()["activities"]:
    print(f"⚠️ {activity['type']}: {activity['description']}")
    
    # Заблокировать пользователя если нужно
    if activity['severity'] == 'critical':
        await client.post(f"/api/v1/admin_dashboard/users/{activity['user_id']}/block")
```

## Monitoring

```python
# Real-time мониторинг системы
import asyncio

async def monitor_system():
    while True:
        health = await client.get("/api/v1/admin_dashboard/system/health")
        
        if health.json()["cpu_usage"] > 80:
            print("⚠️ High CPU usage!")
        
        if health.json()["memory_usage"] > 90:
            print("🚨 Critical memory usage!")
        
        await asyncio.sleep(60)  # Каждую минуту
```

## FAQ
**Q: Кто имеет доступ к admin dashboard?** A: Только пользователи с ролью `admin`  
**Q: Можно ли экспортировать audit logs?** A: Да, в CSV/JSON формате

---

**Документация:** [Admin Dashboard API](../api/ADMIN_DASHBOARD_API.md)
