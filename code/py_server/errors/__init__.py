
"""
Исключения для 1С MCP сервера

Пакет содержит иерархию исключений для Python сервера,
интегрированного с системой 1С через MCP протокол.

Модули:
- base: Базовые классы исключений
- validation: Ошибки валидации данных (E020-E039)
- transport: Транспортные ошибки (E040-E059)
- integration: Ошибки интеграции (E060-E079)
- mcp: MCP-специфичные ошибки
- mapping: Маппинг между 1С и Python исключениями

Основано на стандартах обработки ошибок из проекта 1c_mcp.
"""

# Прямые импорты для обратной совместимости
from base import (ErrorCategory, ErrorSeverity, McpError, NonRecoverableError,
                  RecoverableError, ServiceUnavailableError, SystemError,
                  TimeoutError)
from integration import *
from mapping import *
from mcp import *
from transport import *
from validation import *

# Основные экспорты
__all__ = [
    # Базовые исключения
    "McpError",
    "RecoverableError", 
    "NonRecoverableError",
    "SystemError",
    "ServiceUnavailableError",
    "TimeoutError",
    "ErrorSeverity",
    "ErrorCategory",
    
    # Валидация
    "ValidationError",
    "InvalidInputDataError",
    "MissingRequiredFieldError",
    "InvalidFieldValueError",
    "DataSizeExceededError",
    "InvalidDataFormatError",
    "DataDuplicationError",
    "UniquenessViolationError",
    "SerializationError",
    "DeserializationError",
    "DatabaseConstraintViolationError",
    "SchemaValidationError",
    "BusinessRuleValidationError",
    "ValidationErrorFactory",
    
    # Транспорт
    "TransportError",
    "NetworkError",
    "ConnectionTimeoutError",
    "ServiceUnavailableTransportError",
    "DNSResolutionError",
    "SSLCertificateError",
    "RateLimitExceededError",
    "HTTPRequestError",
    "InvalidURLError",
    "ConnectionError",
    "CorruptedResponseError",
    "ConnectionPoolError",
    "ProxyError",
    "ChunkedEncodingError",
    "SSLError",
    "TransportErrorFactory",
    
    # Интеграция
    "IntegrationError",
    "ExternalServiceUnavailableError",
    "ExternalServiceAuthError",
    "InvalidExternalServiceResponseError",
    "DataMappingError",
    "ExternalServiceTimeoutError",
    "ProtocolTranslationError",
    "APIContractViolationError",
    "APIVersioningError",
    "DataMarshallingError",
    "APICompatibilityError",
    "ServiceConfigurationError",
    "RateLimitIntegrationError",
    "WebhookError",
    "OAuth2Error",
    "SOAPError",
    "IntegrationErrorFactory",
    
    # MCP
    "McpProtocolError",
    "McpToolError",
    "McpResourceError",
    "McpPromptError",
    "McpServerError",
    "McpClientError",
    "InvalidMcpRequestError",
    "UnsupportedMcpOperationError",
    "McpVersionMismatchError",
    "McpJsonRpcError",
    "McpToolNotFoundError",
    "McpToolExecutionError",
    "McpToolTimeoutError",
    "McpToolValidationError",
    "McpResourceNotFoundError",
    "McpResourceAccessDeniedError",
    "McpResourceCorruptedError",
    "McpPromptNotFoundError",
    "McpPromptExecutionError",
    "McpInternalServerError",
    "McpServerStartupError",
    "McpConnectionError",
    "McpInvalidRequestError",
    "McpRateLimitError",
    "McpErrorFactory",
    
    # Маппинг
    "ErrorMapping",
    "ErrorMappingConfig",
    "CrossSystemErrorHandler",
    "default_error_mapping",
    "default_error_handler",
    "translate_1c_error_to_python",
    "translate_python_error_to_1c",
    "handle_api_error",
    "prepare_api_error_response"
]

# Версия пакета
__version__ = "1.0.0"
__author__ = "1С MCP Server Team"
__description__ = "Иерархия исключений для 1С MCP сервера"
__license__ = "MIT"

# Утилиты для быстрого создания ошибок
def create_validation_error(error_code: str, field_name: str = "", field_value=None, **kwargs):
    """Создает ошибку валидации с предустановленными параметрами"""
    return ValidationError(
        error_code=error_code,
        field_name=field_name,
        field_value=field_value,
        **kwargs
    )

def create_transport_error(error_code: str, url: str = "", method: str = "GET", **kwargs):
    """Создает транспортную ошибку с предустановленными параметрами"""
    return TransportError(
        error_code=error_code,
        url=url,
        method=method,
        **kwargs
    )

def create_integration_error(error_code: str, service_name: str, **kwargs):
    """Создает интеграционную ошибку с предустановленными параметрами"""
    return IntegrationError(
        error_code=error_code,
        service_name=service_name,
        **kwargs
    )

def get_error_category(error_code: str) -> str:
    """Возвращает категорию ошибки по коду"""
    if error_code.startswith('E00'):
        return "system"
    elif error_code.startswith('E02'):
        return "validation"
    elif error_code.startswith('E04'):
        return "transport"
    elif error_code.startswith('E06'):
        return "integration"
    elif error_code.startswith('E08'):
        return "auth"
    elif error_code.startswith('E09'):
        return "database"
    elif error_code.startswith('MCP'):
        return "mcp"
    else:
        return "unknown"

def is_recoverable_error(error_code: str) -> bool:
    """Определяет, является ли ошибка восстановимой"""
    recoverable_codes = {
        'E040', 'E041', 'E042', 'E043', 'E044', 'E045', 'E046', 'E047', 'E048', 'E049',
        'E060', 'E061', 'E062', 'E063', 'E064', 'E065', 'E066', 'E067', 'E068', 'E069'
    }
    base_code = error_code[:4] if len(error_code) >= 4 else error_code
    return base_code in recoverable_codes

def format_error_for_logging(error: Exception, correlation_id: str = None) -> str:
    """Форматирует исключение для логирования"""
    correlation_id = correlation_id or getattr(error, 'correlation_id', 'unknown')
    
    if isinstance(error, McpError):
        return f"[{error.error_code}] {error.user_message} (corr_id: {correlation_id})"
    else:
        return f"[{type(error).__name__}] {str(error)} (corr_id: {correlation_id})"
