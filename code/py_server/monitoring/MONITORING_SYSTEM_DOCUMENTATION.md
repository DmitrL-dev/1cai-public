# Система интеграции с мониторингом MCP сервера

## Обзор

Система интеграции с мониторингом предоставляет комплексное решение для отслеживания производительности, ошибок и состояния MCP сервера. Включает метрики Prometheus, интеграцию с Sentry, систему алертинга и поддержку OpenTelemetry.

## Структура модулей

### Основные модули

#### 1. `prometheus_metrics.py` (343 строки)
**Назначение**: Prometheus метрики для отслеживания производительности и ошибок

**Основные компоненты**:
- Счетчики ошибок по типам (validation, transport, integration, auth)
- Гистограммы времени выполнения операций (MCP, HTTP, интеграция)
- Счетчики retry попыток и успешности
- Gauge для состояния circuit breaker
- Метрики активных запросов и размера очередей
- Декораторы для автоматического мониторинга

**Ключевые возможности**:
```python
from monitoring import record_error, monitor_mcp_operation

# Запись ошибки
record_error('validation', 'user_input', correlation_id='123')

# Автоматическое измерение времени операции
@monitor_mcp_operation('tools', 'get_weather')
def get_weather():
    return weather_service.get()
```

#### 2. `sentry_integration.py` (395 строк)
**Назначение**: Интеграция с Sentry для отслеживания исключений и APM

**Основные компоненты**:
- Автоматическая отправка исключений с контекстом
- Трассировка операций (transactions и spans)
- Группировка похожих ошибок
- Установка корреляционных ID
- Фильтрация шумовых событий

**Ключевые возможности**:
```python
from monitoring import get_sentry, sentry_transaction

# Создание транзакции
with get_sentry().transaction('user_request', 'http'):
    # Операция с автоматической трассировкой
    pass

# Декоратор для мониторинга функций
@sentry_transaction('process_data')
def process_data():
    return process()
```

#### 3. `alerting.py` (574 строки)
**Назначение**: Система алертинга для критичных ошибок

**Основные компоненты**:
- Менеджер алертов с правилами эскалации
- Каналы уведомлений (Email, Slack, Telegram)
- Автоматическое создание инцидентов
- Группировка и группировка алертов
- Retention политика для старых алертов

**Ключевые возможности**:
```python
from monitoring.alerting import create_error_alert, create_integration_alert

# Создание алерта об ошибке
await create_error_alert('integration', '1c_connection', '456')

# Создание алерта о проблемах интеграции
await create_integration_alert('1c', 'connect', 'Connection timeout')
```

#### 4. `config.py` (519 строк)
**Назначение**: Конфигурация системы мониторинга

**Основные компоненты**:
- Настройки для всех компонентов мониторинга
- Пороговые значения для алертинга
- SLO/SLI метрики
- Валидация конфигурации
- Поддержка JSON и YAML форматов

**Ключевые возможности**:
```python
from monitoring import get_config, init_config

# Получение конфигурации
config = get_config()

# Инициализация с файлом конфигурации
config = init_config('monitoring_config.json')
```

#### 5. `__init__.py` (392 строки)
**Назначение**: Главный пакет системы мониторинга

**Основные компоненты**:
- Координация всех компонентов
- Автоматическая инициализация
- Глобальные функции доступа
- Декораторы для быстрого использования
- Обработчики исключений

**Ключевые возможности**:
```python
from monitoring import init_monitoring, monitor_function

# Инициализация системы мониторинга
init_monitoring()

# Декоратор для мониторинга функций
@monitor_function('data_processing')
def process_data():
    return process()
```

### Дополнительные модули

#### 6. `opentelemetry_integration.py` (387 строк)
**Назначение**: Интеграция с OpenTelemetry для распределенной трассировки

**Основные компоненты**:
- Экспортеры для Jaeger, Zipkin, OTLP
- Автоматическая инструментация популярных библиотек
- Мост между Prometheus и OpenTelemetry
- Контекстные менеджеры для трассировки

### Конфигурационные файлы

#### 7. `example_dashboard.json` (300 строк)
**Назначение**: Пример Grafana дашборда

**Панели**:
- Обзор сервиса (статус, количество запросов)
- Распределение времени ответа
- Анализ ошибок по типам
- Состояние circuit breaker
- Метрики MCP операций

#### 8. `dashboards/grafana_mcp_overview.yaml` (44 строки)
**Назначение**: Конфигурация Grafana для автоматической загрузки дашбордов

#### 9. `alerts/critical_alerts.yaml` (79 строк)
**Назначение**: Правила алертинга для критичных ошибок

**Включает алерты**:
- Высокая частота ошибок интеграции
- Критические ошибки аутентификации
- Circuit Breaker в открытом состоянии
- Высокий уровень активных запросов
- Критические транспортные ошибки

#### 10. `alerts/medium_and_low_alerts.yaml` (134 строки)
**Назначение**: Правила алертинга для средних и низких приоритетов

**Включает алерты**:
- Ошибки валидации
- Увеличенное время операций
- Множественные попытки повтора
- Анализ производительности

#### 11. `dashboards/error_analysis_dashboard.json` (282 строки)
**Назначение**: Дашборд для анализа ошибок

**Панели**:
- Общий уровень ошибок
- Распределение ошибок по операциям
- Топ операций с ошибками
- Анализ корреляции ошибок
- Состояние circuit breaker

## Интеграция с существующими модулями

### С модулем ошибок (`/errors/`)
```python
from errors.base import MCPError
from monitoring import record_error, get_sentry

class ValidationError(MCPError):
    def __init__(self, message, correlation_id=None):
        super().__init__(message, correlation_id)
        # Автоматическая запись в метрики
        record_error('validation', 'input_validation', correlation_id)
        
        # Отправка в Sentry
        get_sentry().capture_exception(
            extra={'operation': 'input_validation'},
            tags={'error_type': 'validation'}
        )
```

### С middleware (`/middleware/`)
```python
from middleware.correlation import correlation_context
from monitoring.prometheus_metrics import monitor_http_request

@monitor_http_request('POST', '/api/rpc')
async def handle_rpc_request(request):
    correlation_id = request.headers.get('X-Correlation-ID')
    
    with correlation_context(correlation_id):
        # Обработка запроса с автоматическим мониторингом
        return await process_request(request)
```

### С logging (`/logging/`)
```python
from logging.handlers import StructLogHandler
from monitoring.sentry_integration import get_sentry

class MonitoringStructLogHandler(StructLogHandler):
    def emit(self, record):
        # Отправка логов в Sentry
        get_sentry().logger.info(
            record.getMessage(),
            extra={
                'level': record.levelname,
                'module': record.module,
                'function': record.funcName
            }
        )
        super().emit(record)
```

## Пороговые значения и SLO

### Метрики производительности
- **Время ответа**: < 200ms для 95% запросов
- **Время ответа**: < 500ms для 99% запросов
- **Доступность сервиса**: 99.5%
- **Частота ошибок**: < 0.1%

### Пороговые значения для алертов
- **Критические ошибки интеграции**: > 0.01/сек
- **Критические ошибки аутентификации**: > 0.005/сек
- **Транспортные ошибки**: > 0.02/сек
- **Активные запросы**: > 100
- **Время ответа**: > 500ms (P95)

### Circuit Breaker
- **Порог отказов**: 5 ошибок подряд
- **Таймаут**: 60 секунд
- **Порог восстановления**: 3 успешные операции

## Использование

### Базовая инициализация
```python
from monitoring import init_monitoring

# Инициализация с настройками по умолчанию
init_monitoring()

# Инициализация с файлом конфигурации
init_monitoring('monitoring_config.json')
```

### Мониторинг MCP операций
```python
from monitoring import monitor_mcp_operation, record_error

@monitor_mcp_operation('tools', 'get_weather')
async def get_weather_tool(parameters):
    try:
        # Операция с автоматическим мониторингом
        result = await weather_service.get(parameters)
        return result
    except Exception as e:
        # Автоматическая запись ошибки
        record_error('integration', 'weather_service', str(e))
        raise
```

### Создание алертов
```python
from monitoring.alerting import create_performance_alert

# Алерт о превышении времени ответа
await create_performance_alert(
    metric_name='response_time',
    value=1.5,  # 1.5 секунды
    threshold=0.5,  # порог 500ms
    operation='user_request'
)
```

### Интеграция с 1С
```python
from monitoring import record_error, get_sentry

async def connect_to_1c():
    try:
        connection = await onec_client.connect()
        return connection
    except OneCConnectionError as e:
        # Запись критической ошибки интеграции
        record_error('integration', 'onec_connection', str(e))
        
        # Создание алерта
        await create_integration_alert(
            integration_type='1c',
            operation='connect',
            error_message=str(e)
        )
        
        # Отправка в Sentry с контекстом
        get_sentry().capture_exception(
            extra={
                'integration': '1c',
                'operation': 'connect',
                'timeout': 30
            },
            tags={
                'component': 'integration',
                'severity': 'critical'
            }
        )
        
        raise
```

## Мониторинг операций

### MCP операции
- Инструменты (`/tools/*`)
- Ресурсы (`/resources/*`)
- Подсказки (`/prompts/*`)

### HTTP endpoints
- `/health` - проверка состояния
- `/rpc` - обработка RPC запросов
- `/authorize` - авторизация

### 1С интеграция
- Успешность подключения
- Время ответа запросов
- Частота ошибок
- Состояние сессий

### База данных
- Время выполнения запросов
- Количество активных соединений
- Частота ошибок подключения
- Метрики кэширования

## Установка зависимостей

```bash
# Базовые зависимости
pip install prometheus-client sentry-sdk[logging] aiohttp

# OpenTelemetry (опционально)
pip install opentelemetry-api opentelemetry-sdk
pip install opentelemetry-exporter-jaeger opentelemetry-exporter-zipkin
pip install opentelemetry-exporter-otlp opentelemetry-instrumentation-fastapi
pip install opentelemetry-instrumentation-requests opentelemetry-instrumentation-sqlalchemy

# Дополнительные зависимости для алертинга
pip install pyyaml  # для работы с YAML конфигурацией
```

## Конфигурация

### Переменные окружения
```bash
# Sentry
SENTRY_DSN=https://your-sentry-dsn
SENTRY_ENABLED=true
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.1

# Prometheus
PROMETHEUS_ENABLED=true
PROMETHEUS_PORT=8000

# OpenTelemetry
OTEL_ENABLED=true
OTEL_TRACES_SAMPLE_RATE=0.1
JAEGER_ENDPOINT=http://localhost:14268/api/traces
ZIPKIN_ENDPOINT=http://localhost:9411/api/v2/spans
OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://localhost:4317/v1/traces

# Email уведомления
SMTP_SERVER=smtp.company.com
SMTP_PORT=587
SMTP_USERNAME=alerts@company.com
SMTP_PASSWORD=password
ALERT_FROM_EMAIL=alerts@company.com
ALERT_TO_EMAILS=devops@company.com,admin@company.com

# Slack уведомления
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK
SLACK_CHANNEL=#alerts

# Telegram уведомления
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_CHAT_ID=your-chat-id
```

### Пример файла конфигурации
```json
{
  "environment": "production",
  "prometheus": {
    "enabled": true,
    "port": 8000,
    "service_name": "mcp_server",
    "metrics_prefix": "mcp"
  },
  "sentry": {
    "enabled": true,
    "dsn": "https://your-sentry-dsn",
    "environment": "production",
    "traces_sample_rate": 0.1
  },
  "alerts": {
    "enabled": true,
    "retention_days": 30,
    "channels": {
      "email": {
        "enabled": true,
        "smtp_server": "smtp.company.com",
        "smtp_port": 587
      },
      "slack": {
        "enabled": true,
        "webhook_url": "https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK"
      }
    }
  },
  "thresholds": {
    "error_rate_threshold": 0.01,
    "response_time_threshold_ms": 200,
    "circuit_breaker_failure_threshold": 5
  }
}
```

## Общий объем кода: 2,969 строк

Система мониторинга предоставляет полнофункциональное решение для отслеживания производительности, ошибок и состояния MCP сервера с интеграцией в существующую архитектуру.