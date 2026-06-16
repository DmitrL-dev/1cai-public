# Connection Pool Guide

## Обзор

`ConnectionPool` - это пул соединений для переиспользования HTTP сессий между AI клиентами. Улучшает производительность за счет переиспользования TCP соединений.

## Использование

### Базовое использование

```python
from src.ai.connection_pool import ConnectionPool

async def example():
    pool = ConnectionPool(max_size=10, timeout=60)
    
    # Получить сессию
    session = await pool.get_session("http://api.example.com")
    
    # Использовать сессию
    async with session.get("http://api.example.com/endpoint") as response:
        data = await response.json()
    
    # Закрыть все сессии
    await pool.close_all()
```

### Context Manager

```python
async with ConnectionPool(max_size=5, timeout=60) as pool:
    session = await pool.get_session("http://api.example.com")
    # Использовать сессию
    # После выхода из контекста сессии автоматически закроются
```

### Глобальный пул (Singleton)

```python
from src.ai.connection_pool import get_global_pool, close_global_pool

async def example():
    # Получить глобальный пул
    pool = get_global_pool()
    
    session = await pool.get_session("http://api.example.com")
    # Использовать сессию
    
    # Закрыть глобальный пул
    await close_global_pool()
```

### Использование через acquire

```python
async with pool.acquire("http://api.example.com") as session:
    # Использовать сессию
    # Автоматическая обработка ошибок
    async with session.get("/endpoint") as response:
        data = await response.json()
```

## Интеграция с AI клиентами

ConnectionPool автоматически интегрирован в следующие клиенты:
- `GigaChatClient`
- `YandexGPTClient`
- `NaparnikClient`

Клиенты автоматически используют глобальный пул через параметр `use_pool=True` в методе `_get_session()`.

### Отключение пула

Если нужно использовать отдельную сессию без пула:

```python
session = await client._get_session(use_pool=False)
```

## Особенности

### LRU Eviction

При достижении `max_size` самая старая сессия автоматически вытесняется (FIFO).

### Автоматическое пересоздание

Если сессия закрыта, она автоматически пересоздается при следующем запросе.

### Thread-safe

ConnectionPool использует `asyncio.Lock` для безопасного конкурентного доступа.

## Конфигурация

```python
ConnectionPool(
    max_size=10,  # Максимальный размер пула
    timeout=60,   # Таймаут для соединений в секундах
)
```

## Performance

- Переиспользование сессий снижает overhead создания новых соединений
- Конкурентный доступ к одному ключу возвращает одну и ту же сессию
- LRU eviction предотвращает утечки памяти

## Примеры

### Множественные запросы к одному API

```python
pool = ConnectionPool(max_size=5, timeout=60)
base_url = "https://api.example.com"

# Все запросы используют одну сессию
session = await pool.get_session(base_url)

for endpoint in ["/users", "/posts", "/comments"]:
    async with session.get(f"{base_url}{endpoint}") as response:
        data = await response.json()
        # Обработать данные
```

### Конкурентные запросы

```python
async def fetch_data(url):
    pool = get_global_pool()
    session = await pool.get_session(url)
    async with session.get(url) as response:
        return await response.json()

# Параллельные запросы переиспользуют сессии
tasks = [fetch_data(url) for url in urls]
results = await asyncio.gather(*tasks)
```

## Troubleshooting

### Сессия закрыта

Если сессия закрыта, она автоматически пересоздается. Но для предотвращения проблем:

```python
session = await pool.get_session("http://api.example.com")
if session.closed:
    # Сессия уже закрыта, будет пересоздана при следующем запросе
    session = await pool.get_session("http://api.example.com")
```

### Переполнение пула

При достижении `max_size` старая сессия вытесняется. Увеличьте `max_size` если нужно:

```python
pool = ConnectionPool(max_size=20, timeout=60)
```

## Best Practices

1. Используйте один пул на приложение (глобальный singleton)
2. Закрывайте пул при завершении приложения
3. Используйте context manager для автоматического управления ресурсами
4. Настройте `max_size` в зависимости от количества уникальных API endpoints

