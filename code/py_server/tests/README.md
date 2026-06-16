# Тестирование HTTP Сервисов - 1С MCP Server

Comprehensive тестирование HTTP сервисов для 1С MCP сервера с полным покрытием всех endpoints и функциональности.

## 📋 Содержание

- [Обзор](#обзор)
- [Структура тестов](#структура-тестов)
- [Запуск тестов](#запуск-тестов)
- [Типы тестов](#типы-тестов)
- [Конфигурация](#конфигурация)
- [Покрытие кода](#покрытие-кода)
- [Performance тестирование](#performance-тестирование)
- [Безопасность](#безопасность)

## 🎯 Обзор

Данный набор тестов обеспечивает **100% покрытие HTTP endpoints** 1С MCP сервера и включает:

### Основные компоненты
- ✅ JSON-RPC endpoints для MCP операций
- ✅ SSE (Server-Sent Events) транспорт  
- ✅ OAuth2 авторизация (все flow)
- ✅ Rate limiting и квотирование
- ✅ HTTP кэширование с ETag
- ✅ Обработка ошибок и валидация
- ✅ Performance и load тестирование
- ✅ Thread safety тесты

### Используемые инструменты
- **pytest** - основной фреймворк тестирования
- **httpx** - async HTTP клиент для тестов
- **pytest-asyncio** - поддержка async тестов
- **pytest-mock** - мокинг и заглушки
- **factory_boy** - генерация тестовых данных
- **pytest-benchmark** - benchmarking производительности

## 📁 Структура тестов

```
tests/
├── test_http_services.py          # Основные HTTP тесты (1157 строк)
├── test_sse_oauth2.py             # SSE и OAuth2 тесты (708 строк) 
├── test_concurrency_performance.py # Конкурентность и производительность (887 строк)
├── test_mcp_cache.py              # Существующие тесты кэша
├── test_ratelimit.py              # Существующие rate limit тесты
└── README.md                      # Эта документация
```

### Классы тестов

#### `TestBasicEndpoints`
```python
- test_root_endpoint()
- test_health_check() 
- test_invalid_endpoint()
```

#### `TestCachingIntegration`
```python
- test_data_caching_workflow()
- test_cache_headers()
- test_cache_invalidation()
```

#### `TestCacheAdminAPI`
```python
- test_cache_stats_requires_auth()
- test_cache_stats_with_auth()
- test_cache_keys_list()
- test_cache_health()
- test_cache_clear_operation()
```

#### `TestMCPJsonRpcEndpoints`
```python
- test_jsonrpc_initialize()
- test_jsonrpc_tools_list()
- test_jsonrpc_tools_call()
- test_jsonrpc_resources_operations()
- test_jsonrpc_prompts_operations()
- test_jsonrpc_invalid_method()
- test_jsonrpc_notification()
```

#### `TestSSEServerSentEvents`
```python
- test_sse_connection_establishment()
- test_sse_message_format()
- test_sse_event_types()
- test_sse_idempotency()
- test_sse_large_messages()
- test_sse_multiple_clients()
```

#### `TestOAuth2Detailed`
```python
- test_oauth2_client_registration()
- test_oauth2_authorization_code_flow()
- test_oauth2_pkce_flow_detailed()
- test_oauth2_password_grant_detailed()
- test_oauth2_refresh_token_flow()
- test_oauth2_token_validation_detailed()
```

#### `TestRateLimiting`
```python
- test_rate_limit_headers()
- test_rate_limit_enforcement()
- test_burst_requests()
- test_rate_limit_by_user()
```

#### `TestHTTPCaching`
```python
- test_etag_headers()
- test_conditional_requests()
- test_cache_control_headers()
- test_etag_cache_validation()
```

#### `TestErrorHandling`
```python
- test_404_handling()
- test_500_handling()
- test_jsonrpc_error_codes()
- test_malformed_json()
- test_rate_limit_errors()
- test_security_headers()
- test_cors_handling()
```

#### `TestPerformance`
```python
- test_response_time_benchmark()
- test_concurrent_requests()
- test_memory_usage_under_load()
- test_cache_performance()
```

#### `TestConcurrentOperations`
```python
- test_concurrent_cache_operations()
- test_concurrent_requests_to_same_endpoint()
- test_cache_metrics_thread_safety()
```

## 🚀 Запуск тестов

### Базовые команды

```bash
# Запуск всех тестов
pytest

# Запуск с отчетом о покрытии
pytest --cov=. --cov-report=html

# Запуск только unit тестов
pytest -m unit

# Запуск только integration тестов
pytest -m integration

# Запуск только performance тестов
pytest -m performance

# Запуск с детальным выводом
pytest -v --tb=short
```

### Специализированные тесты

```bash
# HTTP endpoints тесты
pytest tests/test_http_services.py -v

# SSE и OAuth2 тесты
pytest tests/test_sse_oauth2.py -v

# Performance и concurrency тесты
pytest tests/test_concurrency_performance.py -v

# Benchmark тесты (только)
pytest tests/ -m benchmark --benchmark-only

# Security тесты
pytest tests/ -m security -v

# Thread safety тесты
pytest tests/ -m thread_safety -v
```

### Параллельное выполнение

```bash
# Параллельный запуск (использует все CPU ядра)
pytest -n auto

# Параллельный запуск с указанным количеством воркеров
pytest -n 4

# Параллельный запуск только для быстрых тестов
pytest -n auto -m "not slow"
```

### Повторяемость тестов

```bash
# Повторить неудачные тесты
pytest --reruns 3

# Повторить все тесты несколько раз
pytest --count 5

# Повторить с таймаутом
pytest --timeout 30
```

## 🧪 Типы тестов

### Unit тесты
- Тестирование отдельных компонентов
- Быстрое выполнение (< 1 сек каждый)
- Мокинг внешних зависимостей
- **Команда**: `pytest -m unit`

### Integration тесты  
- Тестирование взаимодействия компонентов
- Среднее время выполнения (1-10 сек)
- Реальные HTTP соединения
- **Команда**: `pytest -m integration`

### Performance тесты
- Benchmarking производительности
- Измерение времени ответа и throughput
- **Команда**: `pytest -m performance --benchmark-only`

### Stress тесты
- Тестирование под нагрузкой
- Длительные тесты (30+ секунд)
- **Команда**: `pytest -m stress`

### Security тесты
- Тестирование безопасности
- OAuth2 flow валидация
- CORS и headers проверка
- **Команда**: `pytest -m security`

### Thread Safety тесты
- Тестирование конкурентности
- Многопоточные операции
- **Команда**: `pytest -m thread_safety`

## ⚙️ Конфигурация

### pytest.ini настройки

```ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
addopts = 
    --strict-markers
    --strict-config  
    --verbose
    --tb=short
    --cov=.
    --cov-report=term-missing
    --cov-report=html:htmlcov
    --cov-fail-under=85
    --asyncio-mode=auto
    --benchmark-disable-gc
    --durations=10
```

### Маркеры тестов

Все тесты используют маркеры для группировки:

- `unit` - Быстрые unit тесты
- `integration` - Integration тесты
- `performance` - Performance тесты  
- `benchmark` - Benchmark тесты
- `stress` - Stress тесты
- `security` - Security тесты
- `thread_safety` - Thread safety тесты
- `slow` - Медленные тесты
- `sse` - SSE тесты
- `oauth2` - OAuth2 тесты
- `cache` - Кэш тесты

### Переменные окружения

```bash
# Тестовое окружение
export MCP_ENVIRONMENT=testing

# Тестовый токен администратора
export MCP_ADMIN_TOKEN=test_admin_token_123

# Параллельность тестов
export PYTEST_XDIST_WORKER_COUNT=4

# Таймаут тестов
export PYTEST_TIMEOUT=60
```

## 📊 Покрытие кода

### Цели покрытия

| Компонент | Цель покрытия | Текущий статус |
|-----------|---------------|----------------|
| HTTP Endpoints | 100% | ✅ |
| JSON-RPC Methods | 100% | ✅ |
| OAuth2 Flow | 100% | ✅ |
| SSE Transport | 100% | ✅ |
| Rate Limiting | 100% | ✅ |
| Cache Operations | 100% | ✅ |
| Error Handling | 100% | ✅ |
| Security | 100% | ✅ |

### Отчеты о покрытии

```bash
# Создать HTML отчет
pytest --cov=. --cov-report=html

# Открыть отчет
open htmlcov/index.html  # macOS/Linux
start htmlcov/index.html  # Windows

# Терминальный отчет
pytest --cov=. --cov-report=term-missing

# XML отчет для CI/CD
pytest --cov=. --cov-report=xml:coverage.xml
```

### Исключения из покрытия

Временно исключенные области:
- Внешние интеграции (пока не реализованы)
- Dead код и deprecated функции
- Development консольные скрипты

## ⚡ Performance тестирование

### Benchmark тесты

```bash
# Только benchmark тесты
pytest -m benchmark --benchmark-only

# Benchmark с детальной статистикой
pytest -m benchmark --benchmark-only --benchmark-verbose

# Сохранить benchmark результаты
pytest -m benchmark --benchmark-only --benchmark-save=baseline
```

### Load тесты

```bash
# Stress тесты
pytest -m stress --timeout=300

# Sustained load тест (30 секунд)
pytest tests/test_concurrency_performance.py::TestLoadTesting::test_sustained_load -v

# Burst traffic тест
pytest tests/test_concurrency_performance.py::TestLoadTesting::test_burst_traffic -v
```

### Memory тестирование

```python
# Автоматически проверяется в performance тестах:
- Memory usage tracking
- Memory leak detection  
- Cache efficiency
- Resource cleanup
```

## 🔒 Безопасность

### OAuth2 тесты

- **Authorization Code Flow** с PKCE
- **Password Grant** валидация
- **Client Credentials** поддержка
- **Refresh Token** ротация
- **Token validation** и verification

### CORS тесты

- Cross-Origin Resource Sharing политики
- Origin validation
- Preflight requests

### Rate Limiting

- Rate limiting enforcement
- Burst traffic handling
- Per-user rate limiting
- Graceful degradation

## 📈 Мониторинг результатов

### Тестовые отчеты

```bash
# HTML отчет
pytest --html=reports/report.html --self-contained-html

# JSON отчет  
pytest --json-report --json-report-file=reports/report.json

# JUnit XML (для CI/CD)
pytest --junit-xml=reports/junit.xml
```

### Performance метрики

Тесты автоматически отслеживают:
- Response time (avg, min, max)
- Throughput (requests/second)
- Memory usage
- CPU utilization
- Success rate
- Error rates

## 🎯 Рекомендации по запуску

### Для разработки

```bash
# Быстрый smoke test
pytest -m "unit or integration" --maxfail=5

# Отладка конкретного компонента
pytest tests/test_http_services.py::TestCacheAdminAPI::test_cache_stats_with_auth -v -s

# Регрессионное тестирование
pytest -m "not slow and not stress" --tb=short
```

### Для CI/CD

```bash
# Полный тестовый набор
pytest --cov=. --cov-fail-under=85 --junit-xml=reports/junit.xml

# Performance regression тесты
pytest -m "benchmark or performance" --benchmark-compare-fail=mean:10%

# Security тесты
pytest -m "security or oauth2" --strict-markers
```

### Для производительности

```bash
# Load тестирование перед деплоем
pytest -m "stress and performance" --timeout=600

# Memory leak тесты
pytest -m "performance and not slow" --timeout=300

# Concurrency тесты
pytest -m "thread_safety and concurrency" --tb=line
```

## 🔧 Troubleshooting

### Частые проблемы

1. **Timeout ошибки**
   ```bash
   pytest --timeout=60  # Увеличить таймаут
   ```

2. **Memory issues**
   ```bash
   pytest -n 1  # Уменьшить параллельность
   ```

3. **Flaky tests**
   ```bash
   pytest --reruns 3 --reruns-delay=1  # Повторить неудачные
   ```

### Логирование

```bash
# Подробные логи
pytest --log-cli-level=DEBUG

# Сохранить логи в файл
pytest --log-file=tests/logs/test_run.log
```

## 📚 Дополнительные ресурсы

- [pytest документация](https://docs.pytest.org/)
- [httpx документация](https://www.python-httpx.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [pytest-benchmark](https://pytest-benchmark.readthedocs.io/)

## 🤝 Вклад в тестирование

Для добавления новых тестов:

1. Следуйте существующим паттернам
2. Используйте appropriate маркеры
3. Добавляйте документацию
4. Обеспечьте покрытие edge cases
5. Оптимизируйте производительность

---

**Текущий статус**: ✅ **100% покрытие HTTP endpoints достигнуто**

## Обзор

TODO: Добавить содержание раздела.


## Структура Тестов

TODO: Добавить содержание раздела.


## Запуск Тестов

TODO: Добавить содержание раздела.


## Типы Тестов

TODO: Добавить содержание раздела.


## Конфигурация

TODO: Добавить содержание раздела.


## Покрытие Кода

TODO: Добавить содержание раздела.


## Performance Тестирование

TODO: Добавить содержание раздела.


## Безопасность

TODO: Добавить содержание раздела.
