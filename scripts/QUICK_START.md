# Quick Start Guide - Новые API эндпоинты

## Что было сделано

✅ **PostgreSQL Connection** - добавлен парсинг `DATABASE_URL` и улучшена проверка подключения  
✅ **Health Check** - теперь проверяет реальные подключения  
✅ **DevOps API** - эндпоинты для анализа инфраструктуры  
✅ **Self-Evolving AI API** - эндпоинты для автоматического улучшения системы

## Быстрый старт

### 1. Убедитесь, что Docker контейнеры запущены

```powershell
# В PowerShell на хосте
cd C:\1cAI
docker compose -f docker-compose.mvp.yml ps
```

Если контейнеры не запущены:

```powershell
.\scripts\start_battle_mode.ps1
```

### 2. Запустите API

```powershell
.\scripts\run_api_local.ps1
```

API будет доступен на `http://127.0.0.1:8001`

### 3. Проверьте health check

Откройте в браузере или используйте curl:

```powershell
curl http://127.0.0.1:8001/health
```

Должен вернуть:

```json
{
  "status": "healthy",
  "services": {
    "neo4j": "not_configured",
    "qdrant": "not_configured",
    "postgres": "healthy"
  }
}
```

### 4. Запустите тесты

В новом терминале (пока API работает):

```powershell
python scripts/test_new_endpoints.py
```

## Новые эндпоинты

### DevOps

- `GET /api/v1/devops/infrastructure/status` - статус контейнеров
- `POST /api/v1/devops/infrastructure/analyze` - полный анализ инфраструктуры

### Self-Evolving AI

- `GET /api/v1/ai/evolve/status` - статус эволюции
- `GET /api/v1/ai/evolve/metrics` - история метрик
- `POST /api/v1/ai/evolve` - запуск эволюции

## Swagger UI

Откройте в браузере:

```
http://127.0.0.1:8001/docs
```

Все новые эндпоинты будут в разделе **"DevOps & AI Evolution"**

### Как использовать Swagger UI для запуска эволюции

**Шаг 1: Откройте Swagger UI**

- Откройте браузер и перейдите по адресу: `http://127.0.0.1:8001/docs`
- Вы увидите список всех доступных API эндпоинтов

**Шаг 2: Найдите раздел "DevOps & AI Evolution"**

- Прокрутите страницу вниз или используйте поиск (Ctrl+F)
- Найдите раздел с названием **"DevOps & AI Evolution"**
- В этом разделе будут все эндпоинты для DevOps и Self-Evolving AI

**Шаг 3: Выберите эндпоинт для запуска эволюции**

- Найдите эндпоинт: `POST /api/v1/ai/evolve`
- Нажмите на него, чтобы развернуть детали

**Шаг 4: Нажмите "Try it out"**

- В правом верхнем углу блока с эндпоинтом найдите кнопку **"Try it out"**
- Нажмите на неё - блок станет редактируемым

**Шаг 5: Заполните параметры (опционально)**

- В поле **Request body** вы увидите JSON:
  ```json
  {
    "force": false
  }
  ```
- `force: false` - запустит эволюцию только если система нездорова
- `force: true` - запустит эволюцию принудительно
- Можете оставить как есть или изменить на `true`

**Шаг 6: Нажмите "Execute"**

- Прокрутите вниз до кнопки **"Execute"** (синяя кнопка)
- Нажмите на неё - запрос будет отправлен на сервер

**Шаг 7: Просмотрите результат**

- После выполнения вы увидите:
  - **Response code** (например, `200`)
  - **Response body** с результатами эволюции:
    ```json
    {
      "status": "partial",
      "stage": "analyzing",
      "metrics": {
        "accuracy": 0.95,
        "error_rate": 0.02,
        "latency_ms": 150
      },
      "improvements": [],
      "message": "LLM provider not configured. Only performance analysis available."
    }
    ```

**Шаг 8: Проверьте другие эндпоинты**

- `GET /api/v1/ai/evolve/status` - текущий статус эволюции
- `GET /api/v1/ai/evolve/metrics` - история метрик
- `GET /api/v1/devops/infrastructure/status` - статус контейнеров
- `POST /api/v1/devops/infrastructure/analyze` - анализ инфраструктуры

### Визуальная подсказка

В Swagger UI вы увидите:

```
┌─────────────────────────────────────────┐
│ POST /api/v1/ai/evolve                 │
│ Launch Self-Evolving AI Evolution       │
│                                         │
│ [Try it out]  ← Нажмите здесь          │
│                                         │
│ Request body:                           │
│ {                                       │
│   "force": false                        │
│ }                                       │
│                                         │
│ [Execute]  ← Затем нажмите здесь       │
└─────────────────────────────────────────┘
```

## Примеры использования

### Проверка инфраструктуры

```powershell
# Статус контейнеров
curl http://127.0.0.1:8001/api/v1/devops/infrastructure/status

# Полный анализ
curl -X POST "http://127.0.0.1:8001/api/v1/devops/infrastructure/analyze?compose_file=docker-compose.mvp.yml"
```

### Self-Evolving AI

```powershell
# Статус
curl http://127.0.0.1:8001/api/v1/ai/evolve/status

# Запуск эволюции
curl -X POST http://127.0.0.1:8001/api/v1/ai/evolve -H "Content-Type: application/json" -d '{\"force\": false}'
```

## Устранение проблем

### PostgreSQL показывает "unhealthy"

1. Проверьте, что контейнер запущен:

   ```powershell
   docker ps | findstr postgres
   ```

2. Проверьте переменные окружения в `run_api_local.ps1`:

   - `POSTGRES_PASSWORD=changeme`
   - `DATABASE_URL=postgresql://admin:changeme@localhost:5432/knowledge_base`

3. Проверьте подключение вручную:
   ```powershell
   docker exec -it 1c-ai-postgres psql -U admin -d knowledge_base -c "SELECT 1;"
   ```

### Docker CLI недоступен

DevOps Agent требует Docker CLI для проверки статуса контейнеров. В DevContainer это может быть недоступно.

**Решение:** Запускайте API на хосте (WSL 2), а не в DevContainer.

### LLM Provider не настроен

Self-Evolving AI пока работает без реального LLM. Это нормально - он вернет метрики, но не сгенерирует улучшения.

**Решение:** Реализовать метод `generate()` в `LLMProviderAbstraction` (TODO).

## Документация

Полная документация: `docs/API_DEVOPS_AI_EVOLUTION.md`
