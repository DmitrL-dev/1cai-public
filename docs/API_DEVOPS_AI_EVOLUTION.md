# DevOps & AI Evolution API

## Обзор

Новые API эндпоинты для интеграции DevOps Agent и Self-Evolving AI в основное приложение.

## Эндпоинты

### 1. Health Check (улучшенный)

**GET** `/health`

Проверяет реальное состояние подключений к сервисам.

**Ответ:**
```json
{
  "status": "healthy",
  "services": {
    "neo4j": "healthy",
    "qdrant": "healthy",
    "postgres": "healthy"
  }
}
```

**Статусы:**
- `healthy` - сервис работает и подключен
- `unhealthy` - сервис не работает или не подключен
- `not_configured` - сервис не настроен

---

### 2. DevOps Infrastructure Status

**GET** `/api/v1/devops/infrastructure/status`

Быстрая проверка статуса запущенных Docker контейнеров.

**Ответ:**
```json
{
  "status": "success",
  "containers": [
    {
      "id": "abc123",
      "name": "1c-ai-postgres",
      "image": "postgres:15-alpine",
      "status": "Up 2 hours"
    }
  ],
  "count": 1
}
```

---

### 3. DevOps Infrastructure Analysis

**POST** `/api/v1/devops/infrastructure/analyze?compose_file=docker-compose.yml`

Полный анализ Docker инфраструктуры:
- Статический анализ `docker-compose.yml` (best practices, безопасность)
- Проверка реального статуса контейнеров
- Корреляция между конфигурацией и runtime
- Рекомендации по улучшению

**Параметры:**
- `compose_file` (optional) - путь к docker-compose.yml (по умолчанию ищется в корне проекта)

**Ответ:**
```json
{
  "status": "success",
  "static_analysis": {
    "service_count": 2,
    "version": "3.8",
    "services_analysis": {
      "postgres": {
        "image": "postgres:15-alpine",
        "issues": [],
        "status": "ok"
      }
    },
    "security_issues": [],
    "performance_issues": []
  },
  "runtime_status": [...],
  "services_status": {...},
  "recommendations": []
}
```

---

### 4. Self-Evolving AI Status

**GET** `/api/v1/ai/evolve/status`

Получить текущий статус Self-Evolving AI.

**Ответ:**
```json
{
  "is_evolving": false,
  "current_stage": "analyzing",
  "performance_history_count": 5,
  "improvements_count": 2,
  "latest_metrics": {
    "accuracy": 0.95,
    "error_rate": 0.02,
    "latency_ms": 150,
    "throughput": 100,
    "user_satisfaction": 0.9
  }
}
```

---

### 5. Self-Evolving AI Metrics

**GET** `/api/v1/ai/evolve/metrics`

Получить историю метрик производительности.

**Ответ:**
```json
{
  "count": 5,
  "history": [
    {
      "accuracy": 0.95,
      "error_rate": 0.02,
      "latency_ms": 150,
      "throughput": 100,
      "user_satisfaction": 0.9
    }
  ]
}
```

---

### 6. Self-Evolving AI Evolution

**POST** `/api/v1/ai/evolve`

Запустить цикл эволюции Self-Evolving AI.

**Тело запроса:**
```json
{
  "force": false
}
```

**Параметры:**
- `force` (optional, default: false) - принудительный запуск даже если система здорова

**Ответ:**
```json
{
  "status": "completed",
  "stage": "completed",
  "metrics": {
    "accuracy": 0.95,
    "error_rate": 0.02,
    "latency_ms": 150
  },
  "improvements": [
    {
      "description": "Optimize latency by caching frequent queries",
      "code_changes": {...},
      "expected_improvement": {"latency_ms": -200.0}
    }
  ],
  "message": "Evolution completed successfully"
}
```

**Статусы:**
- `completed` - эволюция завершена успешно
- `partial` - выполнена только часть (например, без LLM)
- `in_progress` - эволюция уже запущена
- `failed` - ошибка при выполнении

---

## Использование

### Пример с curl

```bash
# Health check
curl http://localhost:8001/health

# Infrastructure status
curl http://localhost:8001/api/v1/devops/infrastructure/status

# Infrastructure analysis
curl -X POST "http://localhost:8001/api/v1/devops/infrastructure/analyze?compose_file=docker-compose.mvp.yml"

# AI Evolution status
curl http://localhost:8001/api/v1/ai/evolve/status

# Start AI Evolution
curl -X POST http://localhost:8001/api/v1/ai/evolve \
  -H "Content-Type: application/json" \
  -d '{"force": false}'
```

### Пример с Python

```python
import httpx

async with httpx.AsyncClient() as client:
    # Health check
    response = await client.get("http://localhost:8001/health")
    print(response.json())
    
    # Infrastructure analysis
    response = await client.post(
        "http://localhost:8001/api/v1/devops/infrastructure/analyze",
        params={"compose_file": "docker-compose.mvp.yml"}
    )
    print(response.json())
    
    # Start AI Evolution
    response = await client.post(
        "http://localhost:8001/api/v1/ai/evolve",
        json={"force": False}
    )
    print(response.json())
```

### Тестовый скрипт

Запустить полный набор тестов:

```bash
python scripts/test_new_endpoints.py
```

---

## Изменения в коде

### 1. PostgreSQL Connection

**Файл:** `src/db/postgres_saver.py`

- Добавлен парсинг `DATABASE_URL`
- Поддержка отдельных переменных окружения
- Метод `is_connected()` для проверки реального подключения

### 2. Health Check

**Файл:** `src/api/graph_api.py`

- Улучшен `/health` endpoint
- Проверка реальных подключений вместо только наличия объектов

### 3. Новый API модуль

**Файл:** `src/api/devops_api.py`

- Все новые эндпоинты для DevOps и AI Evolution
- Интеграция с существующими агентами

### 4. Регистрация роутера

**Файл:** `src/main.py`

- Добавлен `devops_router` в список роутеров

---

## Переменные окружения

Для работы PostgreSQL подключения:

```bash
# Вариант 1: DATABASE_URL
DATABASE_URL=postgresql://admin:changeme@localhost:5432/knowledge_base

# Вариант 2: Отдельные переменные
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=knowledge_base
POSTGRES_USER=admin
POSTGRES_PASSWORD=changeme
```

---

## Примечания

1. **LLM Provider**: Self-Evolving AI пока работает без реального LLM (использует `None`). Для полной функциональности нужно реализовать метод `generate()` в `LLMProviderAbstraction`.

2. **Docker CLI**: DevOps Agent требует доступ к Docker CLI для проверки статуса контейнеров. В DevContainer это может быть недоступно.

3. **Timeout**: Эндпоинт `/api/v1/ai/evolve` может выполняться долго (до 60 секунд), так как выполняет полный цикл эволюции.

---

## Следующие шаги

1. ✅ Починить подключение к PostgreSQL
2. ✅ Улучшить health check
3. ✅ Создать DevOps API эндпоинты
4. ✅ Создать Self-Evolving AI эндпоинты
5. ⏳ Протестировать полный цикл
6. ⏳ Реализовать метод `generate()` в `LLMProviderAbstraction`

