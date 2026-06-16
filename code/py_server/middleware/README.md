# Middleware для обработки ошибок в FastAPI

## Обзор

Комплексное решение для обработки ошибок в FastAPI приложениях, специально разработанное для интеграции с проектом 1C MCP. Обеспечивает структурированное логирование, нормализованные ответы об ошибках и поддержку всех стандартов обработки ошибок.

## Основные возможности

### 🔧 Глобальный Exception Handler
- Перехват всех типов исключений с нормализацией ответов
- Интеграция с иерархией исключений из `errors/`
- Структурированное логирование всех ошибок
- Поддержка восстановимых и невосстановимых ошибок

### 📊 Нормализованные ответы
- Стандартная структура `ErrorResponse`
- Поддержка русского и английского языков
- Различение HTTP статус-кодов и error.code
- Интеграция с иерархией исключений

### 🔍 Корреляционные ID
- Автоматическое добавление correlation_id в ответы
- Генерация если отсутствует
- Логирование с полным контекстом
- Связь с tracing системами

### 🚀 MCP Endpoints
- Обработка `/health` с proper статус-кодами
- Обработка `/rpc` с нормализацией JSON-RPC ошибок
- MCP tools/list, tools/call с fallback ответами
- Resources и prompts с graceful degradation

### 🔐 HTTP OAuth2
- Обработка 401/403 с информативными сообщениями
- Логирование попыток аутентификации
- Маскирование чувствительных данных
- Rate limiting ошибки

## Структура модулей

```
middleware/
├── __init__.py              - Основной пакет и фабрики
├── correlation.py           - Управление correlation_id (323 строки)
├── response_models.py       - Модели ответов (543 строки)
├── error_handler.py         - Главный обработчик (685 строк)
├── mcp_handlers.py          - MCP обработчики (881 строка)
├── http_handlers.py         - HTTP обработчики (879 строк)
└── example_usage.py         - Пример использования (378 строк)
```

**Общий объем: ~3,689 строк кода**

## Быстрый старт

### Базовая настройка

```python
from fastapi import FastAPI
from middleware import create_error_middleware

app = FastAPI()

# Настройка всех middleware
handlers = create_error_middleware(app, language="ru")

@app.get("/")
async def root():
    return {"message": "Привет от 1C MCP Server!"}
```

### Ручная настройка

```python
from fastapi import FastAPI
from middleware import (
    setup_global_exception_handler,
    setup_http_error_handlers,
    McpHandlersFactory,
    CorrelationIdMiddleware
)

app = FastAPI()

# Добавляем middleware
app.add_middleware(CorrelationIdMiddleware)

# Настраиваем обработчики
setup_global_exception_handler(app)
setup_http_error_handlers(app)
McpHandlersFactory(app).setup_all_handlers()
```

## Структура ErrorResponse

```json
{
  "error": {
    "code": "E001",
    "type": "SystemError",
    "message": {
      "ru": "Внутренняя ошибка сервера",
      "en": "Internal server error"
    },
    "details": {
      "original_exception": "ValueError: Invalid input data",
      "operation": "validate_input",
      "context": {"field": "user_id"}
    },
    "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2025-10-29T21:57:33",
    "severity": "high",
    "category": "system",
    "recoverable": false,
    "http_status_code": 500
  }
}
```

## Типы исключений

### McpError и подклассы
```python
from errors.mcp import McpToolNotFoundError, McpProtocolError
from errors.validation import ValidationError
from errors.transport import TransportError
from errors.integration import IntegrationError

# Обрабатываются автоматически с нормализацией
raise McpToolNotFoundError("tool_name", ["available_tools"])
raise ValidationError("E020", "field_name", field_value)
raise TransportError("E040", url, method, network_error)
```

### HTTPException
```python
from fastapi import HTTPException

raise HTTPException(status_code=404, detail="Ресурс не найден")
```

### Общие исключения
```python
raise ValueError("Некорректные данные")
raise KeyError("Отсутствует ключ")
raise ConnectionError("Ошибка соединения")
```

## Модули детально

### 1. correlation.py (323 строки)

Управление корреляционными ID:

```python
from middleware import get_correlation_id, log_with_correlation

# Получение correlation_id
correlation_id = get_correlation_id()

# Логирование с контекстом
log_with_correlation(
    logging.INFO,
    "Сообщение с correlation_id",
    extra={"operation": "example"}
)

# Context Logger
from middleware import get_context_logger
logger = get_context_logger(__name__)
logger.info("Сообщение с автоматическим correlation_id")
```

### 2. response_models.py (543 строки)

Модели нормализованных ответов:

```python
from middleware import ErrorResponse, Language, ErrorSeverity

# Создание ответа об ошибке
error_response = ErrorResponse.create(
    error_code="E020",
    error_type="ValidationError",
    message_ru="Ошибка валидации",
    message_en="Validation error",
    http_status_code=422,
    severity=ErrorSeverity.MEDIUM,
    recoverable=False
)

# Из McpError
error_response = ErrorResponse.from_mcp_error(mcp_error)

# Из HTTPException
error_response = ErrorResponse.from_http_exception(http_exception)
```

### 3. error_handler.py (685 строк)

Глобальный обработчик исключений:

```python
from middleware import GlobalExceptionHandler, setup_global_exception_handler

# Настройка обработчика
handler = GlobalExceptionHandler(app, Language.RU)

# Декоратор для обработки функций
@with_error_handling("operation_name")
async def my_operation():
    # Ваша логика
    pass
```

### 4. mcp_handlers.py (881 строка)

Обработчики MCP эндпоинтов:

```python
from middleware import McpHandlersFactory

# Создание и настройка обработчиков
factory = McpHandlersFactory(app, Language.RU)
handlers = factory.setup_all_handlers()

# Доступные эндпоинты:
# - GET /health - проверка здоровья
# - POST /rpc - JSON-RPC обработка
# - GET /mcp/tools/list - список инструментов
# - POST /mcp/tools/call/{name} - выполнение инструмента
# - GET /mcp/resources/list - список ресурсов
# - GET /mcp/resources/read/{uri} - чтение ресурса
# - GET /mcp/prompts/list - список промптов
# - GET /mcp/prompts/get/{name} - получение промпта
```

### 5. http_handlers.py (879 строк)

HTTP обработчики ошибок:

```python
from middleware import (
    OAuth2ErrorHandler,
    RateLimitErrorHandler,
    HttpServiceErrorHandler,
    HttpGracefulDegradation
)

# Обработка OAuth2 ошибок
oauth_handler = OAuth2ErrorHandler(Language.RU)
await oauth_handler.handle_auth_error(
    request, "invalid_token", "Недействительный токен", 401
)

# Graceful degradation
degradation = HttpGracefulDegradation()
degradation.register_fallback(
    "/api/users/*",
    fallback_function,
    conditions={"error_types": ["ServiceUnavailableError"]}
)
```

## Примеры использования

### Базовый пример

```python
from fastapi import FastAPI
from middleware import create_error_middleware

app = FastAPI()
create_error_middleware(app)

@app.get("/users/{user_id}")
async def get_user(user_id: int):
    if user_id <= 0:
        from errors.validation import ValidationError
        raise ValidationError("E020", "user_id", user_id)
    
    return {"user_id": user_id, "name": f"User {user_id}"}
```

### С трассировкой

```python
from middleware import trace_operation, get_correlation_id
import logging

@trace_operation("get_user_data")
async def get_user_data(user_id: int):
    log_with_correlation(logging.INFO, "Получение данных пользователя")
    # Ваша логика
    return {"user_id": user_id, "data": "some_data"}
```

### С graceful degradation

```python
from middleware import HttpGracefulDegradation

degradation = HttpGracefulDegradation()

async def fallback_user_data(request, endpoint, error, correlation_id):
    # Возвращаем fallback данные
    return {"user_id": "unknown", "data": "cached_data"}

degradation.register_fallback(
    "/api/users/*",
    fallback_user_data,
    conditions={"error_types": ["ServiceUnavailableError"]}
)
```

## Конфигурации

### Production конфигурация

```python
from middleware import create_production_config

config = create_production_config()
# {
#     "default_language": Language.RU,
#     "enable_structured_logging": True,
#     "enable_mcp_handlers": True,
#     "enable_http_handlers": True,
#     "enable_logging_middleware": True,
#     "enable_graceful_degradation": True,
#     "log_level": "INFO",
#     "json_logging": True,
#     "include_stack_traces": False,
#     "correlation_id_header": "X-Correlation-Id",
#     "rate_limit_enabled": True,
#     "health_check_enabled": True
# }
```

### Development конфигурация

```python
from middleware import create_development_config

config = create_development_config()
# {
#     "default_language": Language.RU,
#     "enable_structured_logging": True,
#     "enable_mcp_handlers": True,
#     "enable_http_handlers": True,
#     "enable_logging_middleware": True,
#     "enable_graceful_degradation": True,
#     "log_level": "DEBUG",
#     "json_logging": False,
#     "include_stack_traces": True,
#     "correlation_id_header": "X-Correlation-Id",
#     "rate_limit_enabled": False,
#     "health_check_enabled": True
# }
```

## Логирование

### Структурированное логирование

Все логи включают correlation_id и структурированный контекст:

```json
{
  "timestamp": "2025-10-29T22:12:00Z",
  "level": "INFO",
  "message": "Запрос к эндпоинту /users/123",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "operation": "get_user",
  "user_id": 123,
  "duration_ms": 45.2
}
```

### Уровни логирования

- **INFO**: Нормальные операции
- **WARNING**: Предупреждения, восстановимые ошибки
- **ERROR**: Ошибки, требующие внимания
- **CRITICAL**: Критические ошибки

## Тестирование

Запустите пример использования:

```bash
cd /workspace/code/py_server/middleware
python example_usage.py
```

Тестовые эндпоинты:

```bash
# Успешный запрос
curl http://localhost:8000/

# Проверка здоровья
curl http://localhost:8000/health

# Ошибка валидации
curl -X GET http://localhost:8000/users/-1

# Не найдено
curl -X GET http://localhost:8000/users/404

# McpToolNotFoundError
curl -X POST http://localhost:8000/tools/nonexistent_tool

# Graceful degradation
curl http://localhost:8000/fallback-example
```

## Интеграция с 1C MCP

### Соответствие стандартам

- **E001-E099**: Коды ошибок системы
- **MCP001-MCP099**: Коды ошибок MCP протокола
- Поддержка JSON-RPC ошибок
- Интеграция с журналом регистрации 1С

### Маппинг исключений

```python
# 1С ошибки -> MCP ошибки
SystemError("E001") -> McpServerError("MCP005")
ValidationError("E020") -> McpInvalidRequestError("MCP010")
TransportError("E042") -> ServiceUnavailableError("E042")
```

## Производительность

### Оптимизации

- Ленивая загрузка обработчиков
- Кэширование correlation_id
- Асинхронное логирование
- Batch обработка ошибок

### Метрики

- Время обработки запросов
- Частота ошибок по типам
- Время ответа эндпоинтов
- Использование памяти

## Безопасность

### Защита данных

- Маскирование чувствительных данных в логах
- Санитизация пользовательского ввода
- Защита от информационных утечек
- Rate limiting для защиты от атак

### Соответствие стандартам

- GDPR совместимость
- PCI DSS требования
- OWASP рекомендации

## Развертывание

### Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . .

RUN pip install -r requirements.txt

EXPOSE 8000
CMD ["python", "example_usage.py"]
```

### Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: 1c-mcp-server
spec:
  replicas: 3
  selector:
    matchLabels:
      app: 1c-mcp-server
  template:
    metadata:
      labels:
        app: 1c-mcp-server
    spec:
      containers:
      - name: server
        image: 1c-mcp-server:latest
        ports:
        - containerPort: 8000
        env:
        - name: LOG_LEVEL
          value: "INFO"
        - name: CORRELATION_ID_HEADER
          value: "X-Correlation-Id"
```

## Мониторинг

### Health Checks

```python
# Встроенная проверка здоровья
GET /health

{
  "status": "healthy",
  "timestamp": "2025-10-29T22:12:00Z",
  "checks": {
    "database": {"status": "ok"},
    "cache": {"status": "ok"},
    "external_api": {"status": "warning"}
  }
}
```

### Метрики для Prometheus

- `http_requests_total` - Общее количество HTTP запросов
- `http_request_duration_seconds` - Время выполнения запросов
- `http_errors_total` - Количество ошибок по типам
- `correlation_id_generated_total` - Количество сгенерированных correlation_id

## Поддержка и разработка

### Вклад в проект

1. Форкните репозиторий
2. Создайте feature branch
3. Внесите изменения
4. Добавьте тесты
5. Создайте Pull Request

### Тестирование

```bash
# Запуск всех тестов
python -m pytest tests/

# Запуск с покрытием
python -m pytest --cov=middleware tests/

# Запуск конкретного теста
python -m pytest tests/test_error_handler.py -v
```

### Документация

```bash
# Генерация документации
mkdocs build

# Локальный сервер документации
mkdocs serve
```

## Лицензия

MIT License - см. файл LICENSE для деталей.

## Контакты

- **Проект**: 1C MCP Server
- **Документация**: [ссылка]
- **Issues**: [ссылка]
- **Email**: support@example.com

---

**Версия**: 1.0.0  
**Последнее обновление**: 2025-10-29  
**Совместимость**: FastAPI 0.100+, Python 3.8+
