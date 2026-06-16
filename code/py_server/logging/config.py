
"""
Конфигурация системы структурированного логирования.

Настройки для structlog, обработчиков и middleware.
"""

import logging.config
import os
import sys
from datetime import datetime
from typing import Any, Dict, Optional

import structlog


class LoggingConfig:
    """Конфигурация системы логирования"""
    
    # Базовые настройки
    SERVICE_NAME = os.getenv("SERVICE_NAME", "py_server")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
    DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"
    
    # Настройки JSON вывода
    JSON_OUTPUT = os.getenv("JSON_OUTPUT", "true").lower() == "true"
    PRETTY_PRINT = os.getenv("PRETTY_PRINT", "false").lower() == "true"
    
    # Настройки консольного вывода
    CONSOLE_COLOR = os.getenv("CONSOLE_COLOR", "true").lower() == "true"
    CONSOLE_TIMESTAMP = os.getenv("CONSOLE_TIMESTAMP", "true").lower() == "true"
    
    # Настройки correlation_id
    CORRELATION_ID_HEADER = os.getenv("CORRELATION_ID_HEADER", "X-Correlation-ID")
    CORRELATION_ID_KEY = os.getenv("CORRELATION_ID_KEY", "correlation_id")
    
    # Настройки маскирования
    MASK_EMAIL = os.getenv("MASK_EMAIL", "true").lower() == "true"
    MASK_PHONE = os.getenv("MASK_PHONE", "true").lower() == "true"
    MASK_CREDIT_CARD = os.getenv("MASK_CREDIT_CARD", "true").lower() == "true"
    MASK_SSN = os.getenv("MASK_SSN", "true").lower() == "true"
    
    # Настройки интеграции с monitoring
    ENABLE_METRICS = os.getenv("ENABLE_METRICS", "true").lower() == "true"
    ENABLE_APM = os.getenv("ENABLE_APM", "false").lower() == "true"
    METRICS_ENDPOINT = os.getenv("METRICS_ENDPOINT", "http://localhost:9090")
    APM_ENDPOINT = os.getenv("APM_ENDPOINT", "http://localhost:14268")
    
    # Настройки производительности
    ASYNC_PROCESSING = os.getenv("ASYNC_PROCESSING", "false").lower() == "true"
    BUFFER_SIZE = int(os.getenv("LOG_BUFFER_SIZE", "1000"))
    
    @classmethod
    def to_dict(cls) -> Dict[str, Any]:
        """Преобразование конфигурации в словарь"""
        return {
            "service_name": cls.SERVICE_NAME,
            "log_level": cls.LOG_LEVEL,
            "debug_mode": cls.DEBUG_MODE,
            "json_output": cls.JSON_OUTPUT,
            "pretty_print": cls.PRETTY_PRINT,
            "console_color": cls.CONSOLE_COLOR,
            "console_timestamp": cls.CONSOLE_TIMESTAMP,
            "correlation_id_header": cls.CORRELATION_ID_HEADER,
            "mask_email": cls.MASK_EMAIL,
            "mask_phone": cls.MASK_PHONE,
            "mask_credit_card": cls.MASK_CREDIT_CARD,
            "mask_ssn": cls.MASK_SSN,
            "enable_metrics": cls.ENABLE_METRICS,
            "enable_apm": cls.ENABLE_APM,
            "async_processing": cls.ASYNC_PROCESSING,
            "buffer_size": cls.BUFFER_SIZE,
        }


# Глобальный объект конфигурации
logging_config = LoggingConfig()


def setup_logging():
    """Настройка структурированного логирования"""
    
    # Настройка Python logging
    if logging_config.JSON_OUTPUT:
        # JSON формат для файлов
        formatter_class = StructuredFormatter
    else:
        # Стандартный формат для консоли
        formatter_class = logging.Formatter
    
    # Базовая конфигурация Python logging
    logging.basicConfig(
        level=getattr(logging, logging_config.LOG_LEVEL),
        format="%(message)s",
        stream=sys.stdout,
        force=True
    )
    
    # Настройка structlog
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    
    if logging_config.JSON_OUTPUT:
        processors.extend([
            structlog.processors.add_log_level,
            StructuredFormatter.json_processor,
            structlog.processors.JSONRenderer(),
        ])
    else:
        # Цветной вывод для консоли
        processors.extend([
            structlog.dev.ConsoleRenderer(colors=logging_config.CONSOLE_COLOR),
        ])
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Создание named logger
    logger = structlog.get_logger()
    logger.info("Logging system initialized", config=logging_config.to_dict())
    
    return logger


def get_logger(name: Optional[str] = None) -> structlog.BoundLogger:
    """Получение именованного логгера"""
    return structlog.get_logger(name or logging_config.SERVICE_NAME)


def get_correlation_id() -> str:
    """Получение текущего correlation_id из контекста"""
    from .middleware import get_correlation_id_from_context
    return get_correlation_id_from_context()


# Настройка цветного вывода для консоли
class ColoredFormatter(logging.Formatter):
    """Цветной форматировщик для консоли"""
    
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'        # Reset
    }
    
    def format(self, record):
        level_name = record.levelname
        color = self.COLORS.get(level_name, self.COLORS['RESET'])
        record.levelname = f"{color}{level_name}{self.COLORS['RESET']}"
        return super().format(record)


# Утилиты для настройки
def configure_for_environment(env: str = "development"):
    """Конфигурация логирования для разных окружений"""
    if env == "development":
        logging_config.PRETTY_PRINT = True
        logging_config.CONSOLE_COLOR = True
        logging_config.JSON_OUTPUT = False
    elif env == "production":
        logging_config.JSON_OUTPUT = True
        logging_config.CONSOLE_COLOR = False
        logging_config.PRETTY_PRINT = False
    elif env == "testing":
        logging_config.JSON_OUTPUT = True
        logging_config.CONSOLE_COLOR = False
        logging_config.PRETTY_PRINT = False
        
    return logging_config


def get_version_info() -> Dict[str, str]:
    """Информация о версии логирования"""
    return {
        "version": "1.0.0",
        "service": logging_config.SERVICE_NAME,
        "configured_at": datetime.now().isoformat(),
        "environment": os.getenv("ENVIRONMENT", "development")
    }