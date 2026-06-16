
"""
Middleware пакет для обработки ошибок FastAPI приложения

Обеспечивает:
- Глобальную обработку всех типов исключений
- Нормализованные ответы об ошибках
- Структурированное логирование с correlation_id
- Интеграцию с иерархией исключений проекта
- Поддержку MCP протокола
- Graceful degradation для сервисов

Основные модули:
- correlation: Управление корреляционными ID
- response_models: Модели нормализованных ответов
- error_handler: Глобальный обработчик исключений
- mcp_handlers: Обработчики MCP эндпоинтов
- http_handlers: HTTP обработчики ошибок
"""

from .correlation import (ContextLogger, CorrelationIdContext,
                          CorrelationIdMiddleware, format_correlation_context,
                          get_context_logger, get_correlation_id,
                          log_with_correlation, set_correlation_id,
                          trace_operation)
from .error_handler import (GlobalExceptionHandler,
                            setup_global_exception_handler,
                            with_error_handling)
from .http_handlers import (HttpErrorHandler, HttpGracefulDegradation,
                            HttpLoggingMiddleware, HttpServiceErrorHandler,
                            OAuth2ErrorHandler, RateLimitErrorHandler,
                            setup_http_error_handlers)
from .mcp_handlers import (McpEndpointHandler, McpErrorMapper,
                           McpHandlersFactory, McpHealthHandler,
                           McpPromptsHandler, McpResourcesHandler,
                           McpRpcHandler, McpToolsHandler)
from .response_models import (ErrorCategory, ErrorResponse, ErrorSeverity,
                              HealthCheckResponse, Language, McpErrorResponse,
                              McpResponse, McpSuccessResponse, SuccessResponse)

__version__ = "1.0.0"
__all__ = [
    # Correlation
    "CorrelationIdMiddleware",
    "CorrelationIdContext", 
    "get_correlation_id",
    "set_correlation_id",
    "log_with_correlation",
    "format_correlation_context",
    "ContextLogger",
    "get_context_logger",
    "trace_operation",
    
    # Response Models
    "ErrorResponse",
    "SuccessResponse", 
    "HealthCheckResponse",
    "McpResponse",
    "McpSuccessResponse",
    "McpErrorResponse",
    "Language",
    "ErrorSeverity",
    "ErrorCategory",
    
    # Error Handler
    "GlobalExceptionHandler",
    "setup_global_exception_handler", 
    "with_error_handling",
    
    # MCP Handlers
    "McpEndpointHandler",
    "McpHealthHandler",
    "McpRpcHandler",
    "McpToolsHandler", 
    "McpResourcesHandler",
    "McPPromptsHandler",
    "McpHandlersFactory",
    "McpErrorMapper",
    
    # HTTP Handlers
    "OAuth2ErrorHandler",
    "RateLimitErrorHandler",
    "HttpServiceErrorHandler",
    "HttpGracefulDegradation",
    "HttpErrorHandler", 
    "HttpLoggingMiddleware",
    "setup_http_error_handlers"
]


def setup_complete_error_handling(
    app,
    default_language: Language = Language.RU,
    enable_structured_logging: bool = True,
    enable_mcp_handlers: bool = True,
    enable_http_handlers: bool = True,
    enable_logging_middleware: bool = True,
    enable_graceful_degradation: bool = True
):
    """
    Полная настройка всех middleware для обработки ошибок
    
    Args:
        app: FastAPI приложение
        default_language: Язык по умолчанию для сообщений
        enable_structured_logging: Включить структурированное логирование
        enable_mcp_handlers: Включить MCP обработчики
        enable_http_handlers: Включить HTTP обработчики
        enable_logging_middleware: Включить middleware логирования
        enable_graceful_degradation: Включить graceful degradation
        
    Returns:
        Dict: Словарь с настроенными обработчиками
    """
    
    handlers = {}
    
    # Добавляем Correlation ID middleware
    app.add_middleware(CorrelationIdMiddleware)
    
    # Настраиваем глобальный обработчик исключений
    handlers['global_error'] = setup_global_exception_handler(
        app, 
        default_language,
        enable_structured_logging
    )
    
    # Настраиваем HTTP обработчики
    if enable_http_handlers:
        handlers['http'] = setup_http_error_handlers(
            app,
            default_language,
            enable_logging_middleware,
            enable_graceful_degradation
        )
    
    # Настраиваем MCP обработчики
    if enable_mcp_handlers:
        handlers['mcp'] = McpHandlersFactory(app, default_language).setup_all_handlers()
    
    return handlers


# Удобные фабрики для быстрого старта
def create_error_middleware(
    app,
    language: str = "ru"
) -> Dict[str, Any]:
    """
    Создает базовую конфигурацию middleware для обработки ошибок
    
    Args:
        app: FastAPI приложение
        language: Язык по умолчанию (ru/en)
        
    Returns:
        Dict: Конфигурация middleware
    """
    default_language = Language.RU if language == "ru" else Language.EN
    
    return setup_complete_error_handling(
        app=app,
        default_language=default_language,
        enable_structured_logging=True,
        enable_mcp_handlers=True,
        enable_http_handlers=True,
        enable_logging_middleware=True,
        enable_graceful_degradation=True
    )


def create_production_config() -> Dict[str, Any]:
    """
    Создает production конфигурацию middleware
    
    Returns:
        Dict: Production настройки
    """
    return {
        "default_language": Language.RU,
        "enable_structured_logging": True,
        "enable_mcp_handlers": True,
        "enable_http_handlers": True,
        "enable_logging_middleware": True,
        "enable_graceful_degradation": True,
        "log_level": "INFO",
        "json_logging": True,
        "include_stack_traces": False,  # Отключаем для безопасности в продакшене
        "correlation_id_header": "X-Correlation-Id",
        "rate_limit_enabled": True,
        "health_check_enabled": True
    }


def create_development_config() -> Dict[str, Any]:
    """
    Создает development конфигурацию middleware
    
    Returns:
        Dict: Development настройки
    """
    return {
        "default_language": Language.RU,
        "enable_structured_logging": True,
        "enable_mcp_handlers": True,
        "enable_http_handlers": True,
        "enable_logging_middleware": True,
        "enable_graceful_degradation": True,
        "log_level": "DEBUG",
        "json_logging": False,  # Текстовое логирование для разработки
        "include_stack_traces": True,
        "correlation_id_header": "X-Correlation-Id",
        "rate_limit_enabled": False,  # Отключаем для удобства разработки
        "health_check_enabled": True
    }


# Примеры использования
EXAMPLE_USAGE = '''
# Быстрый старт
from fastapi import FastAPI
from middleware import create_error_middleware

app = FastAPI()

# Настройка всех middleware
handlers = create_error_middleware(app, language="ru")

# Или ручная настройка
from middleware import (
    setup_global_exception_handler,
    setup_http_error_handlers,
    McpHandlersFactory,
    CorrelationIdMiddleware
)

app.add_middleware(CorrelationIdMiddleware)
setup_global_exception_handler(app)
setup_http_error_handlers(app)
McpHandlersFactory(app).setup_all_handlers()

# Добавление кастомных обработчиков
@app.get("/protected")
async def protected_endpoint():
    # Ваша логика
    pass
'''

if __name__ == "__main__":
    print("Middleware пакет для FastAPI успешно загружен")
    print("Документация: https://github.com/example/middleware")
    print(__doc__)
