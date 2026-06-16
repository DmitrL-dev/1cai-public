
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Пример использования иерархии исключений для 1С MCP сервера

Демонстрирует:
- Создание различных типов исключений
- Маппинг между системами 1С и Python
- Структурированное логирование
- MCP интеграцию
"""

import json
import os
import sys
from datetime import datetime

# Добавляем текущую папку в путь для импорта
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import McpError
from integration import ExternalServiceUnavailableError
from mapping import prepare_api_error_response, translate_python_error_to_1c
from mcp import McpProtocolError, McpToolError
from transport import ConnectionTimeoutError, NetworkError
from validation import InvalidInputDataError, MissingRequiredFieldError


def demo_validation_errors():
    """Демонстрация ошибок валидации"""
    print("\n🔍 Ошибки валидации данных:")
    print("-" * 40)
    
    # Ошибка некорректных данных
    email_error = InvalidInputDataError(
        field_name="email",
        field_value="invalid-email",
        expected_format="user@domain.com"
    )
    print(f"📧 Ошибка email: {email_error.user_message}")
    print(f"   Код: {email_error.error_code}")
    print(f"   Восстановимое: {email_error.recoverable}")
    
    # Ошибка отсутствующего поля
    field_error = MissingRequiredFieldError("user_id")
    print(f"\n📝 Отсутствует поле: {field_error.user_message}")
    print(f"   Код: {field_error.error_code}")


def demo_transport_errors():
    """Демонстрация транспортных ошибок"""
    print("\n🌐 Транспортные ошибки:")
    print("-" * 40)
    
    # Сетевая ошибка
    network_error = NetworkError(
        url="https://api.example.com/data",
        method="GET",
        network_error="Connection refused"
    )
    print(f"🔌 Сетевая ошибка: {network_error.user_message}")
    print(f"   URL: {network_error.context_data.get('url')}")
    print(f"   Восстановимое: {network_error.recoverable}")
    
    # Таймаут соединения
    timeout_error = ConnectionTimeoutError(
        url="https://slow-service.com/api",
        timeout_seconds=30.0
    )
    print(f"\n⏰ Таймаут: {timeout_error.user_message}")
    print(f"   Код: {timeout_error.error_code}")


def demo_integration_errors():
    """Демонстрация интеграционных ошибок"""
    print("\n🔗 Интеграционные ошибки:")
    print("-" * 40)
    
    # Недоступность внешнего сервиса
    service_error = ExternalServiceUnavailableError(
        service_name="external_payment_api",
        service_url="https://payments.example.com/v1",
        availability_check=True
    )
    print(f"🏢 Сервис недоступен: {service_error.user_message}")
    print(f"   Сервис: {service_error.context_data.get('service_name')}")
    print(f"   Проверка доступности: {service_error.context_data.get('availability_check')}")


def demo_mcp_errors():
    """Демонстрация MCP ошибок"""
    print("\n🤖 MCP ошибки:")
    print("-" * 40)
    
    # Ошибка инструмента
    tool_error = McpToolError(
        tool_name="calculate_invoice",
        operation="execution",
        tool_error="Division by zero in calculation"
    )
    print(f"🔧 Ошибка инструмента: {tool_error.user_message}")
    print(f"   Инструмент: {tool_error.context_data.get('tool_name')}")
    
    # Ошибка протокола
    protocol_error = McpProtocolError(
        protocol_version="2024-11-05",
        operation="tools/list",
        protocol_error="Invalid JSON-RPC request structure"
    )
    print(f"\n📋 Ошибка протокола: {protocol_error.user_message}")
    print(f"   Версия: {protocol_error.context_data.get('protocol_version')}")


def demo_mapping():
    """Демонстрация маппинга между системами"""
    print("\n🔄 Маппинг 1С ↔ Python:")
    print("-" * 40)
    
    # Создаем Python исключение
    python_error = McpError(
        error_code="E001",
        error_type="SystemError",
        user_message="Общая системная ошибка",
        correlation_id="corr-123456789"
    )
    
    # Транслируем в формат 1С
    one_c_data = translate_python_error_to_1c(python_error)
    print("📤 Python → 1С:")
    print(f"   Код: {one_c_data['КодОшибки']}")
    print(f"   Категория: {one_c_data['Категория']}")
    print(f"   Сообщение: {one_c_data['ПользовательскоеСообщение']}")
    print(f"   Восстановимое: {one_c_data['Восстановимое']}")
    
    # Готовим ответ API
    api_response = prepare_api_error_response(python_error)
    print("\n📡 Ответ API:")
    print(f"   Код ошибки: {api_response['error']['code']}")
    print(f"   Сообщение: {api_response['error']['message']}")
    print(f"   Correlation ID: {api_response['error']['data']['correlation_id']}")


def demo_structured_logging():
    """Демонстрация структурированного логирования"""
    print("\n📋 Структурированное логирование:")
    print("-" * 40)
    
    # Создаем исключение с дополнительным контекстом
    error = McpError(
        error_code="E042",
        error_type="ServiceUnavailable",
        user_message="Сервис временно недоступен",
        correlation_id="req-987654321"
    )
    
    # Добавляем контекст
    error.add_context('service_url', 'https://api.example.com')
    error.add_context('request_duration', 5.2)
    error.add_context('retry_count', 3)
    
    # Получаем данные для логирования
    log_data = error.to_structured_log()
    
    print("📤 JSON для логирования:")
    print(json.dumps(log_data, ensure_ascii=False, indent=2))


def demo_error_factory():
    """Демонстрация фабрики ошибок"""
    print("\n🏭 Фабрика ошибок:")
    print("-" * 40)
    
    # Использование фабрики для быстрого создания ошибок
    from validation import ValidationErrorFactory
    
    validation_factory = ValidationErrorFactory()
    
    # Создаем ошибки через фабрику
    format_error = validation_factory.invalid_format('phone', 'phone format (+7XXXXXXXXXX)')
    required_error = validation_factory.required_field('password')
    
    print("⚡ Быстрое создание ошибок валидации:")
    print(f"   Формат: {format_error.user_message}")
    print(f"   Обязательное поле: {required_error.user_message}")


def main():
    """Основная функция демонстрации"""
    print("🚀 Демонстрация иерархии исключений 1С MCP сервера")
    print("=" * 60)
    print(f"🕒 Время запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Запускаем все демонстрации
        demo_validation_errors()
        demo_transport_errors()
        demo_integration_errors()
        demo_mcp_errors()
        demo_mapping()
        demo_structured_logging()
        demo_error_factory()
        
        print("\n" + "=" * 60)
        print("✅ Все демонстрации выполнены успешно!")
        print("📚 Иерархия исключений готова к использованию!")
        
    except Exception as e:
        print(f"\n❌ Ошибка в демонстрации: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()