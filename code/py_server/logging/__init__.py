
"""
Система структурированного логирования для Python сервера.

Предоставляет:
- JSON логирование с correlation_id
- Автоматическое маскирование PII данных
- Интеграцию с monitoring системами
- Middleware для HTTP запросов
"""

from .config import get_correlation_id, get_logger, setup_logging
from .formatter import StructuredFormatter, create_log_structure
from .handlers import APMHandler, MonitorHandler, StructuredLogger
from .middleware import LoggingMiddleware, correlation_context
from .sanitizers import DataSanitizer, sanitize_sensitive_data

__version__ = "1.0.0"

# Глобальные настройки
LOGGING_CONFIGURED = False

def initialize_logging():
    """Инициализация системы логирования"""
    global LOGGING_CONFIGURED
    if not LOGGING_CONFIGURED:
        setup_logging()
        LOGGING_CONFIGURED = True

# Экспорт основных компонентов
__all__ = [
    "setup_logging",
    "get_logger", 
    "get_correlation_id",
    "LoggingMiddleware",
    "correlation_context",
    "StructuredLogger",
    "MonitorHandler", 
    "APMHandler",
    "DataSanitizer",
    "sanitize_sensitive_data",
    "StructuredFormatter",
    "create_log_structure",
    "initialize_logging"
]