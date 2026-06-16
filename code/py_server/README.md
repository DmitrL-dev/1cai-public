# 1C MCP Server - Python сервер интеграции

Python сервер для интеграции платформы 1С:Предприятие с Model Context Protocol (MCP), включающий API администрирования кэша и модуль кэширования MCP tools.

## Основные компоненты

### 1. API администрирования кэша
API администрирования кэша для Python сервера, основанный на стандартах мониторинга из RFC 7234 и практических рекомендациях по кэшированию в 1С:Предприятие.

### 2. MCP Tools Cache (NEW)
Современный модуль кэширования результатов MCP tools, основанный на анализе производительности и стандартах кэширования. Поддерживает TTL стратегии, LRU вытеснение, persistent cache и автоматическую инвалидацию.

**Документация по кэшированию**: [cache/README.md](cache/README.md)

## Особенности

### API администрирования кэша
- **Полный мониторинг кэша**: статистика попаданий, промахов, использования памяти
- **Управление кэшами**: очистка, инвалидация ключей, получение списков
- **Middleware для метрик**: автоматический сбор времени отклика и коэффициента попаданий
- **Аутентификация**: защищенные endpoints для административных операций
- **Интеграция с различными кэшами**: поддержка MemoryCache и Redis
- **OpenAPI документация**: автоматическая документация всех endpoints

### MCP Tools Cache (НОВИНКА)
- **TTL стратегии**: 30 минут для стабильных данных, 5 минут для динамических
- **Максимальный размер**: 100MB (настраивается)
- **Кэширование только успешных запросов**
- **Метрики попаданий/промахов**
- **Многоуровневое кэширование**: память + persistent cache на диске
- **Стратегии вытеснения**: LRU и TTL-based
- **Механизмы инвалидации**: по шаблонам, сущностям, событиям
- **Специализированные функции**: для MCP tools, метаданных 1С, агрегатов
- **Декораторы кэширования**: @cached и @cached_async
- **Интеграция с mcp_server.py и onec_client.py**

## Установка

```bash
pip install -r requirements.txt
```

## Быстрый старт

```python
# Инициализация API администрирования кэша
from fastapi import FastAPI
from api import cache_admin_router, cache_middleware

# Создание приложения
app = FastAPI(title="1С Сервер API")

# Подключение API администрирования кэша
app.include_router(cache_admin_router)

# Добавление middleware для сбора метрик
@app.middleware("http")
async def add_cache_middleware(request, call_next):
    return await cache_middleware(request, call_next)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

## MCP Tools Cache - Быстрый старт

```python
from cache import init_cache, cached, cache_tool_result

# Инициализация кэша
cache = init_cache(
    max_size_mb=100,
    default_ttl_stable=30 * 60,  # 30 минут
    default_ttl_dynamic=5 * 60,   # 5 минут
    persistent_cache_dir="./cache_data"
)

# Использование декоратора
@cached(ttl=300, data_type='stable')
def get_catalog_structure(catalog_name):
    # Дорогостоящая операция получения структуры
    return fetch_from_1c(catalog_name)

# Кэширование результата MCP tool
result = execute_tool("get_nomenclature", {"id": 123})
cache_tool_result("get_nomenclature", {"id": 123}, result)

# Кэширование метаданных 1С
metadata = get_catalog_metadata("Пользователи")
cache_metadata_1c("catalog", "Пользователи", metadata)
```

## Демонстрация

Запустите демонстрацию MCP Tools Cache:

```bash
cd cache
python mcp_cache_demo.py
```

Запустите тесты кэширования:

```bash
python -m unittest tests.test_mcp_cache -v
```

## API Endpoints

### 1. Статистика кэша

**GET** `/cache/stats`

Возвращает полную статистику кэша системы.

**Аутентификация**: Bearer токен `admin_token_123`

**Ответ**:
```json
{
  "total_keys": 150,
  "memory_usage_bytes": 1048576,
  "memory_usage_mb": 1.0,
  "hit_count": 1250,
  "miss_count": 250,
  "hit_rate": 0.833,
  "avg_response_time_ms": 45.2,
  "max_response_time_ms": 120.5,
  "min_response_time_ms": 2.1,
  "last_updated": "2025-10-29T19:56:35"
}
```

### 2. Список ключей кэша

**GET** `/cache/keys`

Получить список ключей в кэшах с поддержкой фильтрации и пагинации.

**Параметры**:
- `cache_name` (опционально): имя конкретного кэша
- `limit` (опционально): максимальное количество записей (по умолчанию 100)
- `offset` (опционально): смещение для пагинации (по умолчанию 0)

**Ответ**:
```json
[
  {
    "key": "metadata:config_123",
    "size_bytes": 2048,
    "ttl_seconds": 3600,
    "created_at": "2025-10-29T19:00:00",
    "last_accessed": "2025-10-29T19:45:00",
    "hit_count": 15
  }
]
```

### 3. Информация о ключе

**GET** `/cache/key/{key}`

Получить подробную информацию о конкретном ключе кэша.

**Ответ**:
```json
{
  "key": "metadata:config_123",
  "size_bytes": 2048,
  "ttl_seconds": 3600,
  "created_at": "2025-10-29T19:00:00",
  "last_accessed": "2025-10-29T19:45:00",
  "hit_count": 15
}
```

### 4. Очистка кэша

**DELETE** `/cache/clear`

Очистить кэш или все кэши системы.

**Параметры**:
- `cache_name` (опционально): имя конкретного кэша для очистки

**Ответ**:
```json
{
  "status": "success",
  "message": "Кэши очищены: business_data, sessions",
  "cleared_caches": ["business_data", "sessions"],
  "timestamp": "2025-10-29T19:56:35"
}
```

### 5. Инвалидация ключа

**DELETE** `/cache/invalidate/{key}`

Инвалидировать конкретный ключ кэша.

**Параметры**:
- `key`: ключ для инвалидации (может содержать префикс `cache_name:key`)
- `cache_name` (опционально): имя кэша

**Ответ**:
```json
{
  "status": "success",
  "message": "Ключи инвалидированы: metadata:config_123",
  "invalidated_keys": ["metadata:config_123"],
  "timestamp": "2025-10-29T19:56:35"
}
```

### 6. Проверка здоровья кэша

**GET** `/cache/health`

Проверить здоровье кэша системы с диагностикой.

**Ответ**:
```json
{
  "status": "healthy",
  "timestamp": "2025-10-29T19:56:35",
  "checks": {
    "business_data": {
      "status": "available",
      "keys": 100,
      "memory_mb": 1.5
    },
    "hit_rate": {
      "status": "ok",
      "value": 0.85
    },
    "response_time": {
      "status": "ok",
      "avg_ms": 42.3
    },
    "memory": {
      "status": "ok",
      "percent": 45.2
    }
  },
  "uptime_seconds": 3600.0
}
```

### 7. Список кэшей

**GET** `/cache/list`

Получить список всех доступных кэшей системы.

**Ответ**:
```json
{
  "business_data": {
    "name": "business_data",
    "type": "memory",
    "total_keys": 100,
    "memory_usage_bytes": 1048576,
    "memory_usage_mb": 1.0,
    "uptime_seconds": 3600.0
  }
}
```

## Middleware для сбора метрик

API автоматически собирает следующие метрики:

- **Время отклика кэша**: измеряется для каждого запроса
- **Коэффициент попаданий (hit rate)**: процент успешных обращений к кэшу
- **Использование памяти**: мониторинг потребления ресурсов
- **Статистика запросов**: общее количество обращений

## Аутентификация

Все административные endpoints требуют Bearer аутентификацию:

```bash
curl -H "Authorization: Bearer admin_token_123" \
     http://localhost:8000/cache/stats
```

**Внимание**: В продакшене необходимо заменить простую проверку токена на безопасную аутентификацию (JWT, OAuth2, etc.).

## Интеграция с кэшами

API поддерживает различные типы кэшей:

### MemoryCache
Кэш в памяти с полной функциональностью мониторинга:
- Подробная статистика
- Информация о ключах
- Время жизни (TTL)

### RedisCache
Адаптер для Redis (требует дополнительной реализации):
```python
from api import RedisCache

# Создание Redis кэша
redis_cache = RedisCache("main_redis", "redis://localhost:6379")
```

## Конфигурация

### Переменные окружения

```bash
# Токен администратора (должен быть изменен в продакшене)
ADMIN_TOKEN=admin_token_123

# Настройки Redis (если используется)
REDIS_URL=redis://localhost:6379
REDIS_PASSWORD=your_redis_password
```

### Настройка кэшей

```python
from api import MemoryCache

# Создание пользовательского кэша
custom_cache = MemoryCache("custom_data")

# Добавление в систему мониторинга
active_caches["custom"] = custom_cache
```

## Мониторинг и метрики

API автоматически генерирует метрики в HTTP заголовках:

- `X-Avg-Response-Time`: среднее время отклика
- `X-Cache-Hit-Rate`: коэффициент попаданий
- `X-Cache-Status`: статус кэша (HIT/MISS)

## Интеграция с 1С

API разработан специально для интеграции с 1С:Предприятие:

- **Кэш метаданных**: хранение структуры конфигурации
- **Кэш вычислений**: результаты тяжелых операций
- **Кэш HTTP ответов**: статические данные
- **Кэш сессий**: данные пользователей

## Документация OpenAPI

Автоматическая документация доступна по адресам:
- `/docs` - Swagger UI
- `/redoc` - ReDoc
- `/openapi.json` - OpenAPI схема

## Примеры использования

### Python клиент

```python
import httpx
import asyncio

async def get_cache_stats():
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "http://localhost:8000/cache/stats",
            headers={"Authorization": "Bearer admin_token_123"}
        )
        return response.json()

# Запуск
stats = asyncio.run(get_cache_stats())
print(f"Коэффициент попаданий: {stats['hit_rate']:.2%}")
```

### Bash скрипт

```bash
#!/bin/bash

# Функция для вызова API с аутентификацией
call_api() {
    local endpoint=$1
    curl -s -H "Authorization: Bearer admin_token_123" \
         http://localhost:8000$endpoint
}

# Получение статистики
echo "=== Статистика кэша ==="
call_api "/cache/stats" | jq '.'

# Список ключей
echo "=== Ключи кэша ==="
call_api "/cache/keys?limit=10" | jq '.'

# Проверка здоровья
echo "=== Проверка здоровья ==="
call_api "/cache/health" | jq '.'
```

## Безопасность

**Важно для продакшена**:

1. Замените простую проверку токена на JWT или OAuth2
2. Ограничьте доступ к административным endpoints
3. Используйте HTTPS для всех запросов
4. Реализуйте rate limiting
5. Логируйте все административные операции

## MCP Tools Cache - Дополнительная информация

### Документация
- **[Полная документация по кэшированию](cache/README.md)** - подробное руководство по использованию
- **[Примеры интеграции](cache/integration_examples.py)** - практические примеры интеграции с mcp_server.py
- **[Конфигурация](cache/config.py)** - настройки для разных окружений
- **[Тесты](tests/test_mcp_cache.py)** - полный набор unit-тестов

### Производительность
Ожидаемые улучшения при использовании MCP Tools Cache:
- **Сокращение латентности**: до 95% для кэш-попаданий
- **Снижение нагрузки на БД**: на 60-80%
- **Экономия токенов**: до 80% при оптимизации JSON
- **Увеличение пропускной способности**: в 3-5 раз

### Архитектура кэширования

```
┌─────────────────────────────────────┐
│         Application Layer           │
│  (mcp_server.py, onec_client.py)   │
└─────────────────┬───────────────────┘
                  │
┌─────────────────▼───────────────────┐
│         MCPToolsCache               │
│  - In-Memory Cache (LRU/TTL)       │
│  - Persistent Cache (disk)         │
│  - Metrics & Monitoring            │
└─────────────────┬───────────────────┘
                  │
┌─────────────────▼───────────────────┐
│        Storage Layer                │
│  - Memory (OrderedDict)            │
│  - Disk (pickle + index.json)      │
└─────────────────────────────────────┘
```

### Поддерживаемые типы данных

| Тип | TTL | Persistent | Описание |
|-----|-----|------------|----------|
| **metadata** | 30 мин | ✅ | Метаданные конфигурации 1С |
| **aggregates** | 5 мин | ❌ | Агрегированные данные и отчёты |
| **tool_config** | 30 мин | ✅ | Конфигурации MCP инструментов |
| **api_response** | 5 мин | ❌ | Ответы API 1С |
| **stable** | 30 мин | ✅ | Стабильные данные |
| **dynamic** | 5 мин | ❌ | Динамические данные |

### Интеграция с MCP сервером

```python
from cache.integration_examples import setup_cache_integration

# При инициализации сервера
cache_integrations = setup_cache_integration()

# Использование в обработчике инструментов
async def handle_tool_with_cache(tool_name, arguments):
    # Проверяем кэш
    cached_result = await cache_integrations['mcp_integration'].get_cached_tool_execution(
        tool_name, arguments
    )
    
    if cached_result:
        return cached_result['result']
    
    # Выполняем инструмент
    result = await execute_1c_tool(tool_name, arguments)
    
    # Кэшируем результат
    await cache_integrations['mcp_integration'].cache_tool_execution(
        tool_name, arguments, result
    )
    
    return result
```

## Лицензия

Модуль создан в соответствии со стандартами мониторинга 1С, HTTP кэширования и лучшими практиками оптимизации MCP серверов.

## Поддержка

Для вопросов и предложений создавайте issues в репозитории проекта.

### Дополнительные ресурсы
- [Документация проекта](../../docs/)
- [Cache README](cache/README.md)
- [Спецификация Model Context Protocol](https://modelcontextprotocol.io/)
