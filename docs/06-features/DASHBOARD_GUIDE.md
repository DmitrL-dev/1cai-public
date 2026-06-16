# Dashboard — Руководство пользователя

**Версия:** 1.0  
**Статус:** ✅ Production Ready  
**API Endpoint:** `/api/v1/dashboard`

---

## 📋 Содержание

1. [Обзор](#обзор)
2. [Установка и настройка](#установка-и-настройка)
3. [API Reference](#api-reference)
4. [Примеры использования](#примеры-использования)
5. [Интеграция](#интеграция)
6. [Кастомизация](#кастомизация)
7. [Troubleshooting](#troubleshooting)
8. [FAQ](#faq)

---

## Обзор

### Что это такое?

**Dashboard** — это главная панель управления 1C AI Stack с role-based views. Каждая роль (Executive, Owner, PM, Developer, Team Lead, BA) получает персонализированный дашборд с релевантными метриками и данными.

### Для кого предназначен?

- 👔 **Руководители** — стратегические метрики и KPI
- 👨‍💼 **Владельцы продукта** — бизнес-метрики простым языком
- 📊 **Project Managers** — проекты, timeline, workload
- 👨‍💻 **Разработчики** — задачи, code reviews, build status
- 👥 **Team Leads** — производительность команды, code quality
- 📝 **Бизнес-аналитики** — требования, traceability, BPMN

### Основные возможности

✅ **6 role-based dashboards** — персонализированные дашборды для каждой роли  
✅ **Real-time metrics** — метрики в реальном времени  
✅ **Customizable widgets** — настраиваемые виджеты  
✅ **Data visualization** — графики и диаграммы  
✅ **Export capabilities** — экспорт данных (JSON, CSV, PDF)  
✅ **Responsive design** — адаптивный дизайн для всех устройств

---

## Установка и настройка

### Требования

**Минимальные:**
- Python 3.11+
- PostgreSQL 15+
- Redis 5.0+

**Рекомендуемые:**
- Python 3.12.7
- PostgreSQL 15.4
- Redis 7.0+

### Установка

Dashboard модуль уже включен в 1C AI Stack. Дополнительная установка не требуется.

### Конфигурация

Настройте переменные окружения в `.env`:

```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/1c_ai_stack

# Redis (для кэширования)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Dashboard Settings
DASHBOARD_CACHE_TTL=300  # 5 минут
DASHBOARD_REFRESH_INTERVAL=60  # 1 минута
```

### Инициализация

```bash
# Создать таблицы БД
alembic upgrade head

# Запустить приложение
uvicorn src.main:app --reload
```

---

## API Reference

### Base URL

```
http://localhost:8000/api/v1/dashboard
```

### Endpoints

#### 1. Executive Dashboard

**Endpoint:** `GET /api/v1/dashboard/executive`

**Описание:** Высокоуровневые KPI и бизнес-метрики для руководства.

**Request:**
```http
GET /api/v1/dashboard/executive HTTP/1.1
Host: localhost:8000
Authorization: Bearer <token>
```

**Response:**
```json
{
  "revenue": {
    "current_month": 150000,
    "previous_month": 140000,
    "growth_percent": 7.14
  },
  "active_projects": 12,
  "team_size": 45,
  "customer_satisfaction": 4.5,
  "key_metrics": {
    "deployment_frequency": "2.3 per week",
    "lead_time": "3.2 days",
    "mttr": "1.5 hours",
    "change_failure_rate": "5%"
  },
  "top_risks": [
    {
      "id": "RISK-001",
      "title": "Database migration delay",
      "severity": "high",
      "probability": 0.7
    }
  ]
}
```

**Error Responses:**
- `401 Unauthorized` — не авторизован
- `403 Forbidden` — нет прав доступа
- `500 Internal Server Error` — ошибка сервера

---

#### 2. Owner Dashboard

**Endpoint:** `GET /api/v1/dashboard/owner`

**Описание:** Простые бизнес-метрики понятным языком для владельца продукта.

**Request:**
```http
GET /api/v1/dashboard/owner HTTP/1.1
Host: localhost:8000
Authorization: Bearer <token>
```

**Response:**
```json
{
  "summary": "Всё идёт хорошо. Проекты в срок, команда продуктивна.",
  "projects_status": {
    "on_track": 10,
    "at_risk": 2,
    "delayed": 0
  },
  "team_health": "good",
  "budget_status": {
    "spent": 450000,
    "budget": 500000,
    "remaining_percent": 10
  },
  "upcoming_milestones": [
    {
      "name": "Release 2.0",
      "date": "2025-12-01",
      "status": "on_track"
    }
  ],
  "plain_language_insights": [
    "Команда работает на 95% capacity",
    "Следующий релиз через 4 дня",
    "Бюджет в норме, осталось 10%"
  ]
}
```

---

#### 3. PM Dashboard

**Endpoint:** `GET /api/v1/dashboard/pm`

**Описание:** Проекты, timeline, team workload для project manager.

**Request:**
```http
GET /api/v1/dashboard/pm HTTP/1.1
Host: localhost:8000
Authorization: Bearer <token>
```

**Response:**
```json
{
  "projects": [
    {
      "id": "PROJ-001",
      "name": "1C Integration Module",
      "status": "in_progress",
      "progress": 75,
      "deadline": "2025-12-15",
      "team_size": 5,
      "budget_spent": 0.7
    }
  ],
  "timeline": {
    "current_sprint": "Sprint 12",
    "sprint_progress": 60,
    "days_remaining": 5
  },
  "team_workload": {
    "total_capacity": 200,
    "allocated": 180,
    "utilization": 0.9
  },
  "blockers": [
    {
      "id": "BLOCK-001",
      "title": "Waiting for API access",
      "project": "PROJ-001",
      "days_blocked": 3
    }
  ],
  "upcoming_deadlines": [
    {
      "project": "PROJ-001",
      "milestone": "Beta Release",
      "date": "2025-12-01",
      "days_left": 4
    }
  ]
}
```

---

#### 4. Developer Dashboard

**Endpoint:** `GET /api/v1/dashboard/developer`

**Описание:** Задачи, code reviews, build status для разработчика.

**Request:**
```http
GET /api/v1/dashboard/developer HTTP/1.1
Host: localhost:8000
Authorization: Bearer <token>
```

**Response:**
```json
{
  "assigned_tasks": [
    {
      "id": "TASK-123",
      "title": "Implement OAuth integration",
      "status": "in_progress",
      "priority": "high",
      "estimated_hours": 8,
      "spent_hours": 5
    }
  ],
  "code_reviews": {
    "pending_review": 3,
    "awaiting_changes": 1,
    "approved": 12
  },
  "build_status": {
    "last_build": "success",
    "timestamp": "2025-11-27T10:30:00Z",
    "duration": "3m 45s"
  },
  "my_prs": [
    {
      "id": "PR-456",
      "title": "Add user authentication",
      "status": "approved",
      "approvals": 2,
      "comments": 5
    }
  ],
  "today_commits": 5,
  "this_week_commits": 23
}
```

---

#### 5. Team Lead Dashboard

**Endpoint:** `GET /api/v1/dashboard/team-lead`

**Описание:** Производительность команды, code quality, velocity, technical debt.

**Request:**
```http
GET /api/v1/dashboard/team-lead HTTP/1.1
Host: localhost:8000
Authorization: Bearer <token>
```

**Response:**
```json
{
  "team_performance": {
    "velocity": 45,
    "velocity_trend": "increasing",
    "sprint_completion": 0.92
  },
  "code_quality": {
    "test_coverage": 85,
    "code_review_time_avg": "4.2 hours",
    "bugs_per_1000_loc": 2.3
  },
  "technical_debt": {
    "total_hours": 120,
    "critical_issues": 5,
    "high_priority": 12
  },
  "team_members": [
    {
      "name": "Ivan Petrov",
      "role": "Senior Developer",
      "tasks_completed": 8,
      "code_reviews": 12,
      "availability": "available"
    }
  ],
  "bottlenecks": [
    {
      "area": "Code Review",
      "avg_wait_time": "6 hours",
      "recommendation": "Add more reviewers"
    }
  ]
}
```

---

#### 6. BA Dashboard

**Endpoint:** `GET /api/v1/dashboard/ba`

**Описание:** Требования, traceability, gap analysis, process diagrams.

**Request:**
```http
GET /api/v1/dashboard/ba HTTP/1.1
Host: localhost:8000
Authorization: Bearer <token>
```

**Response:**
```json
{
  "requirements": {
    "total": 150,
    "implemented": 120,
    "in_progress": 20,
    "pending": 10
  },
  "traceability": {
    "requirements_to_code": 0.95,
    "requirements_to_tests": 0.88,
    "orphaned_requirements": 5
  },
  "gap_analysis": [
    {
      "requirement_id": "REQ-045",
      "title": "User authentication",
      "status": "not_implemented",
      "priority": "high"
    }
  ],
  "process_diagrams": [
    {
      "id": "BPMN-001",
      "name": "Order Processing",
      "last_updated": "2025-11-20",
      "status": "approved"
    }
  ],
  "stakeholder_feedback": {
    "pending_reviews": 3,
    "approved": 25,
    "rejected": 2
  }
}
```

---

## Примеры использования

### Пример 1: Получение Executive Dashboard

```python
import httpx

async def get_executive_dashboard():
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "http://localhost:8000/api/v1/dashboard/executive",
            headers={"Authorization": f"Bearer {token}"}
        )
        data = response.json()
        
        print(f"Revenue growth: {data['revenue']['growth_percent']}%")
        print(f"Active projects: {data['active_projects']}")
        print(f"Team size: {data['team_size']}")
        
        return data

# Использование
dashboard = await get_executive_dashboard()
```

### Пример 2: Мониторинг Team Performance

```python
async def monitor_team_performance():
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "http://localhost:8000/api/v1/dashboard/team-lead",
            headers={"Authorization": f"Bearer {token}"}
        )
        data = response.json()
        
        # Проверка velocity
        if data['team_performance']['velocity'] < 40:
            print("⚠️ Warning: Velocity below target!")
        
        # Проверка code quality
        if data['code_quality']['test_coverage'] < 80:
            print("⚠️ Warning: Test coverage below 80%!")
        
        return data
```

### Пример 3: Экспорт данных дашборда

```python
import json

async def export_dashboard_data(role: str, format: str = "json"):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"http://localhost:8000/api/v1/dashboard/{role}",
            headers={"Authorization": f"Bearer {token}"}
        )
        data = response.json()
        
        if format == "json":
            with open(f"dashboard_{role}.json", "w") as f:
                json.dump(data, f, indent=2)
        
        return data

# Экспорт PM dashboard
await export_dashboard_data("pm")
```

---

## Интеграция

### С другими модулями

**Analytics Module:**
```python
# Dashboard использует Analytics для метрик
from src.modules.analytics.api.routes import router as analytics_router

# Получение детальной аналитики
analytics_data = await analytics_router.get_metrics()
```

**Metrics Module:**
```python
# Dashboard собирает метрики через Metrics API
from src.modules.metrics.api.routes import router as metrics_router

# Отправка custom метрик
await metrics_router.send_custom_metric({
    "name": "dashboard_views",
    "value": 1,
    "tags": {"role": "executive"}
})
```

**WebSocket Module:**
```python
# Real-time обновления через WebSocket
from src.modules.websocket.api.routes import router as ws_router

# Подписка на обновления дашборда
await ws_router.subscribe("dashboard_updates")
```

### С внешними системами

**Grafana Integration:**
```python
# Экспорт метрик в Grafana
import requests

def export_to_grafana(dashboard_data):
    grafana_url = "http://grafana:3000/api/dashboards/db"
    headers = {"Authorization": f"Bearer {grafana_token}"}
    
    payload = {
        "dashboard": {
            "title": "1C AI Stack Dashboard",
            "panels": [
                {
                    "title": "Revenue",
                    "targets": [{"target": dashboard_data['revenue']}]
                }
            ]
        }
    }
    
    response = requests.post(grafana_url, json=payload, headers=headers)
    return response.json()
```

---

## Кастомизация

### Добавление custom виджетов

```python
# src/modules/dashboard/services/custom_service.py

class CustomDashboardService:
    async def get_custom_widget(self, conn) -> Dict[str, Any]:
        """Пользовательский виджет"""
        query = """
            SELECT 
                metric_name,
                metric_value,
                timestamp
            FROM custom_metrics
            WHERE timestamp > NOW() - INTERVAL '7 days'
        """
        
        rows = await conn.fetch(query)
        return {
            "widget_type": "custom",
            "data": [dict(row) for row in rows]
        }
```

### Настройка refresh interval

```python
# В .env
DASHBOARD_REFRESH_INTERVAL=30  # 30 секунд

# В коде
import os

REFRESH_INTERVAL = int(os.getenv("DASHBOARD_REFRESH_INTERVAL", "60"))
```

### Кастомные метрики

```python
# Добавление своих метрик в дашборд
async def add_custom_metric(conn, metric_name: str, value: float):
    query = """
        INSERT INTO dashboard_metrics (metric_name, value, timestamp)
        VALUES ($1, $2, NOW())
    """
    await conn.execute(query, metric_name, value)
```

---

## Troubleshooting

### Проблема: Дашборд не загружается

**Симптомы:**
- HTTP 500 error
- Timeout при запросе

**Решение:**
```bash
# 1. Проверить подключение к БД
psql -U user -d 1c_ai_stack -c "SELECT 1"

# 2. Проверить Redis
redis-cli ping

# 3. Проверить логи
tail -f logs/app.log | grep dashboard
```

### Проблема: Медленная загрузка данных

**Симптомы:**
- Долгий ответ API (>5 секунд)

**Решение:**
```sql
-- Добавить индексы
CREATE INDEX idx_metrics_timestamp ON dashboard_metrics(timestamp);
CREATE INDEX idx_projects_status ON projects(status);

-- Включить кэширование
DASHBOARD_CACHE_TTL=600  # 10 минут
```

### Проблема: Неактуальные данные

**Симптомы:**
- Старые метрики в дашборде

**Решение:**
```python
# Очистить кэш
import redis

r = redis.Redis(host='localhost', port=6379, db=0)
r.flushdb()

# Или через API
await client.post("/api/v1/dashboard/cache/clear")
```

---

## FAQ

**Q: Как часто обновляются данные в дашборде?**  
A: По умолчанию каждые 60 секунд. Можно настроить через `DASHBOARD_REFRESH_INTERVAL`.

**Q: Можно ли экспортировать дашборд в PDF?**  
A: Да, используйте endpoint `/api/v1/dashboard/{role}/export?format=pdf`.

**Q: Как добавить новую роль?**  
A: Создайте новый сервис в `src/modules/dashboard/services/` и зарегистрируйте endpoint в `routes.py`.

**Q: Поддерживается ли real-time обновление?**  
A: Да, через WebSocket API. Подключитесь к `/api/v1/websocket/dashboard`.

**Q: Как настроить права доступа?**  
A: Используйте RBAC через Auth Module. Настройте роли в `src/modules/auth/`.

**Q: Можно ли кастомизировать виджеты?**  
A: Да, см. раздел [Кастомизация](#кастомизация).

---

## Дополнительные ресурсы

- [API Documentation](../api/DASHBOARD_API.md)
- [Architecture Overview](../02-architecture/ARCHITECTURE_OVERVIEW.md)
- [Analytics Module Guide](./ANALYTICS_GUIDE.md)
- [Metrics Module Guide](./METRICS_GUIDE.md)

---

**Версия документа:** 1.0  
**Последнее обновление:** 2025-11-27  
**Автор:** 1C AI Stack Team
