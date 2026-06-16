# Rate Limiting - Система конфигурируемых лимитов и учета запросов

Модуль для управления лимитами запросов в 1c_mcp с поддержкой гибкой конфигурации и высокопроизводительным учетом запросов.

## Особенности

### Конфигурация лимитов
- **Конфигурируемые лимиты**: Поддержка YAML/JSON конфигурации
- **Динамические лимиты**: Изменение лимитов по времени
- **Многоуровневая система**: Bronze/Silver/Gold/Platinum/Admin уровни
- **Hot reload**: Обновление конфигурации без перезапуска
- **Backup & Recovery**: Автоматическое резервное копирование
- **Валидация**: Проверка корректности конфигурации

### Учет запросов (RequestTracker)
- **Потокобезопасность**: Все операции защищены thread-safe механизмами
- **Высокая производительность**: < 1ms на запрос
- **Геолокация**: Отслеживание IP с определением географического положения
- **Многоуровневый tracking**: По IP, пользователям, MCP tools
- **Distributed режим**: Поддержка Redis для горизонтального масштабирования
- **Автоочистка**: Автоматическое удаление устаревших данных
- **OAuth2 интеграция**: Поддержка аутентифицированных пользователей

### Мониторинг
- **Интеграция с системой мониторинга**: Сбор метрик и статистики
- **Детальная аналитика**: Статистика по IP, пользователям, инструментам
- **Системные метрики**: CPU, память, диск

## Базовые лимиты

По умолчанию установлены следующие лимиты согласно техническим требованиям:

### По IP
- 100 запросов в минуту
- 1000 запросов в час

### По пользователю
- 50 запросов в минуту
- 500 запросов в час

### По MCP tool
- 10 запросов в минуту
- 100 запросов в час (для ресурсоемких операций)

## Уровни пользователей

| Уровень | Множитель | Приоритет |
|---------|-----------|-----------|
| Bronze | 0.5x | 1 |
| Silver | 1.0x | 2 |
| Gold | 1.5x | 3 |
| Platinum | 2.0x | 4 |
| Admin | 10.0x | 10 |

## Быстрый старт - RequestTracker

### Базовое использование

```python
import asyncio
from ratelimit import RequestTracker

async def main():
    # Инициализация трекера
    tracker = RequestTracker(
        use_redis=False,  # Для продакшена: True
        redis_url="redis://localhost:6379",
        geoip_db_path="/path/to/geoip.db"
    )
    
    # Отслеживание запроса
    allowed = await tracker.track_request(
        request=request,
        response_time_ms=45.2,
        status_code=200,
        user_id="user123",
        tool_name="database_query"
    )
    
    if not allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

asyncio.run(main())
```

### Интеграция с FastAPI

```python
from fastapi import FastAPI
from ratelimit import init_request_tracker, create_rate_limit_middleware

app = FastAPI()

@app.on_event("startup")
async def startup():
    await init_request_tracker({
        "use_redis": True,
        "redis_url": "redis://localhost:6379"
    })

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    middleware = create_rate_limit_middleware()
    return await middleware(request, call_next)

@app.get("/data/{data_id}")
async def get_data(data_id: str, request: Request):
    # Автоматический tracking через middleware
    return {"data_id": data_id, "message": "Данные получены"}
```

### Получение статистики

```python
# Комплексная статистика
stats = tracker.get_comprehensive_stats()
print(f"Всего запросов: {stats['overall']['total_requests']}")
print(f"Заблокировано: {stats['overall']['blocked_rate_percent']:.2f}%")

# Статистика по IP
ip_stats = tracker.get_ip_stats("192.168.1.1")

# Статистика по пользователю
user_stats = tracker.get_user_stats("user123")

# Статистика по инструменту
tool_stats = tracker.get_tool_stats("database_query")
```

## Конфигурация лимитов

```python
from ratelimit import ConfigurationManager

# Создание менеджера конфигурации
config_manager = ConfigurationManager('/path/to/config.yaml')

# Назначение уровня пользователю
config_manager.tiered_limits.assign_user_tier("user123", "gold")

# Добавление администратора
config_manager.limit_overrides.add_admin("admin456")

# Получение эффективного лимита
context = {
    'user_id': 'user123',
    'limit_type': 'user',
    'endpoint': '/api/data'
}

effective_limit = config_manager.get_effective_limit(context)
print(f"Лимит: {effective_limit.requests_per_minute} запросов/мин")
```

## Динамические лимиты

Система поддерживает временные окна для автоматического изменения лимитов:

```python
from ratelimit import TimeWindow

# Создание временного окна
peak_window = TimeWindow(
    start_time="09:00",
    end_time="18:00",
    days_of_week=[1, 2, 3, 4, 5],  # Пн-Пт
    multiplier=0.7  # Снижение на 30% в рабочее время
)

# Добавление окна
config_manager.dynamic_limits.add_time_window("peak_hours", peak_window)
```

## Правила применения

Можно настроить правила для автоматического применения лимитов:

```python
# Правило для админов
config_manager.limit_rules.add_rule(
    name="admin_override",
    condition="user_id in admin_list",
    action="apply_admin_limits",
    priority=100
)

# Правило для тяжелых MCP операций
config_manager.limit_rules.add_rule(
    name="mcp_heavy",
    condition="endpoint.startswith('/mcp/heavy/')",
    action="apply_mcp_heavy_limits",
    priority=50
)
```

## Hot Reload

Для автоматической перезагрузки конфигурации при изменениях:

```python
# Запуск горячей перезагрузки (проверка каждые 30 секунд)
config_manager.start_hot_reload(check_interval=30)

# Остановка
config_manager.stop_hot_reload()
```

## Экспорт/Импорт конфигурации

```python
# Экспорт в JSON
config_manager.export_config('/path/to/export.json', 'json')

# Экспорт в YAML
config_manager.export_config('/path/to/export.yaml', 'yaml')

# Импорт конфигурации
config_manager.import_config('/path/to/config.yaml')
```

## Мониторинг

### Статистика конфигурации лимитов

```python
# Получение статистики для мониторинга
stats = config_manager.get_monitoring_stats()
print(f"Уровней пользователей: {stats['total_tiers']}")
print(f"Активных правил: {stats['active_rules']}")
```

### Статистика RequestTracker

```python
tracker = get_request_tracker()

# Получить комплексную статистику
stats = tracker.get_comprehensive_stats()
print(stats)
# {
#     "overall": {
#         "total_requests": 15420,
#         "blocked_requests": 234,
#         "blocked_rate_percent": 1.52,
#         "uptime_seconds": 86400,
#         "requests_per_second": 0.18
#     },
#     "trackers": {
#         "ip_tracker": {...},
#         "user_tracker": {...},
#         "tool_tracker": {...}
#     },
#     "system": {
#         "cpu_percent": 15.2,
#         "memory_percent": 45.8,
#         "disk_usage_percent": 23.1
#     }
# }

# Статистика по компонентам
ip_stats = tracker.get_ip_stats("192.168.1.1")
user_stats = tracker.get_user_stats("user123")
tool_stats = tracker.get_tool_stats("database_query")
```

## Детальная документация RequestTracker

### Архитектура

```
RequestTracker
├── IPTracker - отслеживание по IP с геолокацией
├── UserTracker - учет по аутентифицированным пользователям
├── ToolTracker - специализированный tracking для MCP tools
└── DistributedTracker - для горизонтального масштабирования
```

### IPTracker - Отслеживание по IP

- **Геолокация**: Определение страны, города, региона по IP
- **Детекция ботов**: Автоматическое обнаружение подозрительной активности
- **Автоблокировка**: Блокировка вредоносных IP

```python
# Заблокировать IP
tracker.block_ip("192.168.1.100", "Подозрительная активность")

# Получить статистику IP
stats = tracker.get_ip_stats("192.168.1.100")
print(stats)
# {
#     "ip": "192.168.1.100",
#     "is_blocked": True,
#     "suspicious_score": 2.5,
#     "total_requests": 1500,
#     "geo_data": {
#         "country": "Россия",
#         "city": "Москва"
#     }
# }
```

### UserTracker - Учет пользователей

- **Уровни пользователей**: free/premium/enterprise
- **Квоты по уровням**: Различные лимиты для разных уровней
- **JWT интеграция**: Автоматическое извлечение user_id из токенов

| Уровень | Запросов/мин | Запросов/час |
|---------|---------------|---------------|
| free | 60 | 1,000 |
| premium | 300 | 10,000 |
| enterprise | 1,000 | 50,000 |

```python
# Установить уровень пользователя
tracker.set_user_tier("user123", "premium")

# Получить статистику пользователя
stats = tracker.get_user_stats("user123")
print(stats)
# {
#     "user_id": "user123",
#     "user_tier": "premium",
#     "total_requests": 2500,
#     "remaining_quota": {
#         "per_minute": 50,
#         "per_hour": 7500
#     }
# }
```

### ToolTracker - MCP инструменты

- **Специализированные лимиты**: Разные лимиты для разных типов операций
- **Мониторинг производительности**: Время отклика, количество ошибок
- **Кастомные лимиты**: Возможность установки индивидуальных лимитов

| Инструмент | Запросов/мин | Запросов/час |
|------------|---------------|---------------|
| database_query | 100 | 2,000 |
| file_operation | 50 | 1,000 |
| report_generation | 10 | 200 |
| external_api | 30 | 500 |

```python
# Установить кастомные лимиты
tracker.set_tool_limits("custom_tool", {"per_minute": 200, "per_hour": 5000})

# Получить статистику инструмента
stats = tracker.get_tool_stats("database_query")
print(stats)
# {
#     "tool_name": "database_query",
#     "total_calls": 1500,
#     "avg_response_time_ms": 45.2,
#     "error_rate_percent": 2.1
# }
```

### DistributedTracker - Горизонтальное масштабирование

- **Redis backend**: Для shared state между инстансами
- **Высокая производительность**: < 0.5ms latency
- **Автоматическая репликация**: Синхронизация данных

```python
async def example_distributed():
    tracker = RequestTracker(
        use_redis=True,
        redis_url="redis://redis-server:6379"
    )
    
    # Добавить запрос в distributed режиме
    allowed = await tracker.distributed_tracker.add_request_distributed(
        key="user:12345",
        request_data={"timestamp": time.time(), "ip": "192.168.1.1"},
        expire_seconds=3600
    )
    
    # Получить distributed статистику
    stats = await tracker.get_distributed_stats("user:12345")
```

## Конфигурационный файл

Пример конфигурации находится в файле `config_example.yaml`.

Основные разделы:
- `limits` - базовые лимиты по типам
- `tiers` - конфигурация уровней пользователей
- `time_windows` - временные окна для динамических лимитов
- `overrides` - переопределения для специальных случаев
- `monitoring` - настройки мониторинга

## Требования

### Для конфигурации лимитов
- Python 3.7+
- PyYAML >= 6.0.0

### Для RequestTracker (опциональные)
- Redis >= 6.0 (для distributed режима)
- geoip2 >= 4.7.0 (для геолокации)
- psutil >= 5.8.0 (для системных метрик)

### Установка зависимостей

```bash
# Основные зависимости
pip install fastapi uvicorn redis geoip2 psutil

# Для production
pip install geoip2==4.7.0 redis==5.0.1 psutil==5.9.0
```

## Интеграция

### Система конфигурации лимитов интегрируется с:
- RequestTracker - для отслеживания запросов
- SlidingWindow - для алгоритма скользящего окна
- Системой мониторинга - для сбора метрик
- Логированием - для отслеживания изменений

### RequestTracker интегрируется с:
- FastAPI - middleware для автоматического трекинга
- OAuth2/JWT - извлечение user_id из токенов
- Redis - для distributed режима
- GeoIP - для геолокационного анализа
- Системой мониторинга - Prometheus/Grafana compatible

### Полная интеграция с FastAPI

```python
from fastapi import FastAPI, Depends
from fastapi.security import HTTPBearer
from ratelimit import (
    init_request_tracker, 
    get_request_tracker,
    create_rate_limit_middleware,
    request_tracking_context
)

app = FastAPI()

@app.on_event("startup")
async def startup():
    await init_request_tracker({
        "use_redis": True,
        "redis_url": "redis://localhost:6379",
        "geoip_db_path": "/usr/share/GeoIP/GeoLite2-City.mmdb"
    })

# Middleware для автоматического rate limiting
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    middleware = create_rate_limit_middleware()
    return await middleware(request, call_next)

# OAuth2 интеграция
security = HTTPBearer()

async def get_current_user(credentials = Depends(security)):
    # Валидация JWT и извлечение user_id
    return validate_jwt_token(credentials.credentials) if credentials else None

@app.get("/secure-data")
async def secure_endpoint(
    request: Request,
    current_user: str = Depends(get_current_user)
):
    # Контекстный трекинг для детальной аналитики
    async with request_tracking_context(request, user_id=current_user) as tracker:
        # Ваша бизнес-логика здесь
        return {"data": "Секретные данные", "user": current_user}
```

### Docker развертывание

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Установка системных зависимостей для GeoIP
RUN apt-get update && apt-get install -y \
    geoip-database-extra \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
# docker-compose.yml
version: '3.8'
services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - REDIS_URL=redis://redis:6379
      - USE_REDIS=true
      - GEOIP_DB_PATH=/usr/share/GeoIP/GeoLite2-City.mmdb
    depends_on:
      - redis
    
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

volumes:
  redis_data:
```