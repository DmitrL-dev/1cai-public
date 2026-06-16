# Система устойчивости для Python серверов

Комплексное решение для обеспечения надежности и устойчивости серверных приложений.

## 🎯 Возможности

- **Circuit Breaker**: Автоматическое обнаружение сбоев с тремя состояниями (CLOSED/OPEN/HALF_OPEN)
- **Graceful Degradation**: Адаптивные уровни деградации (FULL_SERVICE → CACHED_DATA → SIMPLIFIED_RESPONSE → MINIMAL_RESPONSE)  
- **Retry Policies**: Экспоненциальная задержка с джиттером для избежания синхронизации
- **Fallback Strategies**: Специализированные стратегии для 1С, OAuth2, MCP сервисов
- **FastAPI Integration**: Middleware, зависимости и декораторы для автоматического применения

## 📊 Статистика проекта

- **Общее количество строк кода**: 4,393
- **Основные модули**: 8
- **Покрытие тестами**: Комплексные тесты всех компонентов
- **Документация**: Подробные примеры и API reference

## 🏗️ Архитектура

```
resilience/
├── __init__.py              # 361 строка - Главный пакет и публичное API
├── config.py               # 218 строк - Конфигурация системы
├── circuit_breaker.py      # 347 строк - Реализация паттерна Circuit Breaker
├── graceful_degradation.py # 427 строк - Управление деградацией
├── retry_policy.py         # 456 строк - Политики ретраев
├── fallback_strategies.py  # 706 строк - Стратегии fallback
├── fastapi_integration.py  # 622 строк - Интеграция с FastAPI
├── examples.py             # 459 строк - Примеры использования
├── tests.py                # 805 строк - Комплексные тесты
└── README.md               # Документация
```

## 🚀 Быстрый старт

### Circuit Breaker
```python
from resilience import CircuitBreaker, CircuitBreakerConfig

breaker = CircuitBreaker("api_service", CircuitBreakerConfig(failure_threshold=5))
result = breaker.call(lambda: requests.get("https://api.example.com"))
```

### Retry Policy
```python
from resilience import RetryPolicy, RetryPolicyConfig

config = RetryPolicyConfig(max_attempts=3, base_delay=0.5)
retry_policy = RetryPolicy(config)
result = retry_policy.execute(lambda: unstable_api_call())
```

### Graceful Degradation
```python
from resilience import GracefulDegradationManager

manager = GracefulDegradationManager()
manager.register_service("user_service")
level = manager.evaluate_request("user_service", "get_profile", success=True)
```

### Декоратор устойчивости
```python
from resilience import create_resilient_operation, ServiceType

@create_resilient_operation("payment_service", ServiceType.EXTERNAL_API)
def process_payment(amount: float, user_id: str):
    return {"status": "success", "transaction_id": "TXN123"}
```

### FastAPI Integration
```python
from fastapi import FastAPI
from resilience.fastapi import CircuitBreakerMiddleware

app = FastAPI()
app.add_middleware(CircuitBreakerMiddleware, service_type=ServiceType.EXTERNAL_API)
```

## 🧪 Тестирование

```bash
# Запуск всех тестов
python -m resilience.tests

# Запуск примеров
python resilience/examples.py
```

## 📈 Мониторинг

```python
from resilience import get_resilience_status

status = get_resilience_status()
print(f"Circuit Breakers: {len(status['circuit_breakers'])}")
print(f"Retry Policies: {len(status['retry_policies'])}")
print(f"Graceful Degradation: {status['graceful_degradation']['total_services']}")
```

## 🔧 Ключевые особенности

- **Автоматическое восстановление** через тестирование в HALF_OPEN режиме
- **Кэширование результатов** для быстрого восстановления после сбоев
- **Уведомления администраторов** о критических изменениях уровня деградации
- **Детальная статистика** и метрики для мониторинга
- **Потокобезопасность** для многопоточных приложений
- **Асинхронная поддержка** для современных Python приложений

## 📞 Поддержка

- Полная документация в исходном коде
- Комплексные примеры использования
- Юнит-тесты для всех компонентов
- FastAPI integration готов к использованию

---
Создано для обеспечения надежности Python серверов в production среде.