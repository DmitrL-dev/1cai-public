# Система структурированного логирования

Современная система структурированного логирования для Python серверов с поддержкой correlation ID, маскирования данных и интеграции с системами мониторинга.

## Возможности

- **JSON структурированные логи** с корреляционными ID
- **Автоматическое маскирование PII данных** (email, phone, SSN, кредитные карты)
- **HTTP middleware** для автоматического отслеживания запросов
- **Интеграция с APM системами** (Jaeger, Zipkin, OpenTelemetry)
- **Метрики для Prometheus** и других систем мониторинга
- **Асинхронная обработка логов** для высокой производительности
- **Гибкая конфигурация** через переменные окружения
- **Цветной вывод в консоль** для разработки

## Архитектура

```
logging/
├── __init__.py          # Главный модуль и экспорт
├── config.py            # Конфигурация системы
├── formatter.py         # JSON форматирование и структура логов
├── middleware.py        # HTTP middleware и correlation ID
├── sanitizers.py        # Маскирование чувствительных данных
├── handlers.py          # Специализированные обработчики
└── examples.py          # Примеры использования
```

## Быстрый старт

### 1. Инициализация системы

```python
from logging_system import setup_logging, get_logger

# Базовая настройка
setup_logging()

# Получение логгера
logger = get_logger("my_service")
```

### 2. Базовое логирование

```python
logger = get_logger("api")

# Информационное сообщение
logger.info("User login successful", user_id="12345", session_duration=120)

# Предупреждение
logger.warning("High memory usage detected", memory_usage_mb=850.5)

# Ошибка с дополнительными данными
try:
    risky_operation()
except Exception as e:
    logger.error(
        "Operation failed",
        error=str(e),
        error_type="OPERATION_ERROR",
        user_id="12345"
    )
```

### 3. HTTP Middleware

```python
from fastapi import FastAPI
from logging_system.middleware import LoggingMiddleware

app = FastAPI()

# Автоматическое логирование всех HTTP запросов
app.add_middleware(LoggingMiddleware)
```

### 4. Декораторы для функций

```python
from logging_system.middleware import with_correlation_id, log_execution_time

@with_user_id("user123")
@log_execution_time("data_processing")
async def process_user_data(data):
    # Функция будет автоматически логироваться
    # с correlation ID и временем выполнения
    return processed_data
```

## Конфигурация

Система настраивается через переменные окружения:

```bash
# Базовые настройки
export LOG_LEVEL=INFO
export SERVICE_NAME=my_api
export ENVIRONMENT=production

# Формат вывода
export JSON_OUTPUT=true
export PRETTY_PRINT=false
export CONSOLE_COLOR=true

# Интеграция с мониторингом
export ENABLE_METRICS=true
export METRICS_ENDPOINT=http://localhost:9090
export ENABLE_APM=true
export APM_ENDPOINT=http://localhost:14268

# Настройки маскирования
export MASK_EMAIL=true
export MASK_PHONE=true
export MASK_CREDIT_CARD=true
export MASK_SSN=true
```

## Структура логов

Каждый лог содержит стандартные поля:

```json
{
  "timestamp": "2025-10-29T21:57:33.123Z",
  "level": "INFO",
  "message": "User authentication successful",
  "logger_name": "auth",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "request_id": "req_12345",
  "service_name": "auth_service",
  "user_id": "user_abc123",
  "duration_ms": 45.2,
  "http_method": "POST",
  "http_status_code": 200,
  "target_url": "/api/auth/login",
  "context": {
    "session_id": "sess_67890",
    "user_agent": "Mozilla/5.0..."
  }
}
```

## Маскирование данных

Система автоматически маскирует чувствительные данные:

```python
from logging_system.sanitizers import sanitize_user_data

user_data = {
    "email": "user@example.com",
    "phone": "+7 (900) 123-45-67", 
    "password": "secret123",
    "credit_card": "4532 1234 5678 9012"
}

sanitized = sanitize_user_data(user_data)
# Результат: email и phone маскированы, password и карта скрыты
```

### Маскируемые данные:
- **Email адреса**: `user***@example.com`
- **Телефоны**: `+7 (XXX) XXX-XX-XX`
- **Кредитные карты**: показывает только последние 4 цифры
- **Пароли/токены**: полностью скрыты
- **SSN**: маскированы полностью

## Корреляционные ID

### Автоматическая генерация

```python
from logging_system.middleware import correlation_context

# Автоматически создается correlation ID
logger.info("Operation started")  # correlation_id будет сгенерирован
```

### Установка вручную

```python
from logging_system.middleware import correlation_context_manager

with correlation_context_manager(
    correlation_id="custom-id-123",
    user_id="user_456"
):
    logger.info("Within correlation context")
    # Все логи будут иметь указанный correlation_id
```

### HTTP заголовки

```
X-Correlation-ID: 550e8400-e29b-41d4-a716-446655440000
X-User-ID: user_123
```

## HTTP логирование

Автоматическое логирование HTTP запросов:

```python
# Автоматически создается при использовании LoggingMiddleware
{
  "level": "INFO",
  "message": "GET /api/users - 200",
  "http_method": "GET",
  "http_status_code": 200,
  "duration_ms": 45.2,
  "client_ip": "192.168.1.100",
  "user_agent": "Mozilla/5.0..."
}
```

## Мониторинг и метрики

### Prometheus интеграция

Логи автоматически конвертируются в Prometheus метрики:

```prometheus
log_request_duration_ms{correlation_id="550e...",service_name="api"} 45.2
log_error_count_total{error_code="VALIDATION_ERROR",service_name="api"} 1
log_http_requests_total{status_group="2xx",service_name="api"} 150
```

### APM трассировка

Поддержка Jaeger и Zipkin для распределенного трейсинга:

```python
# Автоматически создаются spans для:
# - HTTP запросов (>1ms)
# - Операций с базой данных
# - Вызовов внешних сервисов
# - Долгих операций (>100ms)
```

## Специализированные обработчики

### Console Handler
```python
from logging_system.handlers import ConsoleHandler

handler = ConsoleHandler(
    color=True,
    pretty_print=True
)
```

### File Handler
```python
from logging_system.handlers import FileHandler

handler = FileHandler(
    file_path="/var/log/app.log",
    rotation="size",  # или "time"
    max_size=100 * 1024 * 1024,  # 100MB
    backup_count=5
)
```

### Monitor Handler (Prometheus)
```python
from logging_system.handlers import MonitorHandler

handler = MonitorHandler(
    endpoint="http://localhost:9090",
    auth={"username": "admin", "password": "secret"}
)
```

### APM Handler
```python
from logging_system.handlers import APMHandler

handler = APMHandler(
    endpoint="http://localhost:14268",
    service_name="my_service"
)
```

## Создание специализированных логгеров

```python
from logging_system.handlers import create_application_logger

# Логгер для приложения
app_logger = create_application_logger("my_app")

# HTTP логгер
http_logger = create_http_logger()

# Бизнес-логгер
business_logger = create_business_logger()
```

## Фоновые задачи

Логирование фоновых операций:

```python
from logging_system.middleware import log_execution_time

async def background_task():
    logger = get_logger("background")
    
    while True:
        logger.info("Background task heartbeat")
        await asyncio.sleep(30)
```

## Обработка исключений

Структурированное логирование ошибок:

```python
try:
    risky_operation()
except ValidationError as e:
    logger.error(
        "Validation failed",
        error=str(e),
        error_type="VALIDATION_ERROR", 
        error_code="VAL_001",
        field_name="user_input",
        validation_rules=["required", "format"]
    )
```

## Производительность

### Асинхронная обработка
- Неблокирующая запись логов
- Буферизация для снижения нагрузки
- Thread pool для I/O операций

### Конфигурация производительности
```bash
export ASYNC_PROCESSING=true
export LOG_BUFFER_SIZE=1000
export BUFFER_FLUSH_INTERVAL=10
```

## Запуск примеров

```bash
# Установка зависимостей
pip install fastapi uvicorn structlog aiohttp

# Запуск демо приложения
cd code/py_server/logging
python examples.py

# Открыть браузер
open http://localhost:8000
```

### Доступные endpoint'ы:
- `/` - главная страница
- `/demo/basic` - базовое логирование
- `/demo/http` - HTTP логирование
- `/demo/business` - бизнес-события
- `/demo/performance` - производительность
- `/demo/error` - обработка ошибок
- `/demo/sanitization` - маскирование данных

## Интеграция с различными фреймворками

### FastAPI
```python
from fastapi import FastAPI
from logging_system.middleware import LoggingMiddleware

app = FastAPI()
app.add_middleware(LoggingMiddleware)
```

### Flask
```python
from flask import Flask
from logging_system.middleware import LoggingMiddleware

app = Flask(__name__)

@app.before_request
def before_request():
    # Настройка correlation_id для каждого запроса
    pass
```

### Django
```python
# middleware.py
from logging_system.middleware import LoggingMiddleware as LoggingMiddlewareBase

class LoggingMiddleware(LoggingMiddlewareBase):
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Middleware логики
        response = self.get_response(request)
        return response
```

## Лучшие практики

1. **Всегда используйте correlation_id** для трассировки запросов
2. **Маскируйте чувствительные данные** автоматически
3. **Логируйте на всех уровнях**: INFO, WARNING, ERROR, CRITICAL
4. **Используйте context** для дополнительной информации
5. **Мониторьте производительность** через метрики
6. **Интегрируйте с APM** для распределенного трейсинга

## Устранение неполадок

### Проверка конфигурации
```python
from logging_system.config import get_version_info, logging_config

print("Version:", get_version_info())
print("Config:", logging_config.to_dict())
```

### Тестирование маскирования
```python
from logging_system.sanitizers import create_masking_report

data = {"email": "test@example.com", "password": "secret"}
report = create_masking_report(data)
print("Masking report:", report)
```

### Валидация структуры логов
```python
from logging_system.formatter import LogValidator

log_data = create_log_structure(
    level=LogLevel.INFO,
    message="Test message",
    logger_name="test"
)

is_valid, errors = LogValidator.validate(log_data)
print(f"Valid: {is_valid}, Errors: {errors}")
```