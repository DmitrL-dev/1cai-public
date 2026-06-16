
"""
Базовые классы исключений для 1С MCP сервера

Основан на стандартах обработки ошибок из проекта 1c_mcp и лучших практиках Python:
- Структурированное логирование с correlation_id
- Категоризация ошибок по типам
- Поддержка MCP протокола
- Интеграция с OpenTelemetry
"""

import json
import traceback
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

# Условный импорт логирования для избежания конфликтов
try:
    import logging
    _has_logging = True
except ImportError:
    _has_logging = False
    # Создаем заглушку для логирования
    class MockLogger:
        def debug(self, msg, *args, **kwargs): pass
        def info(self, msg, *args, **kwargs): pass
        def warning(self, msg, *args, **kwargs): pass
        def error(self, msg, *args, **kwargs): pass
        def critical(self, msg, *args, **kwargs): pass
        
        @property 
        def level(self):
            return 20  # INFO level
    
    class MockLogging:
        DEBUG = 10
        INFO = 20
        WARNING = 30
        ERROR = 40
        CRITICAL = 50
        
        class Logger:
            pass
        
        @staticmethod
        def getLogger(name):
            return MockLogger()
    
    logging = MockLogging()


class ErrorSeverity(Enum):
    """Уровни серьезности ошибок"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Категории ошибок для систематизации"""
    SYSTEM = "system"  # E001-E019
    VALIDATION = "validation"  # E020-E039
    TRANSPORT = "transport"  # E040-E059
    INTEGRATION = "integration"  # E060-E079
    AUTH = "auth"  # E080-E089
    DATABASE = "database"  # E090-E099
    MCP = "mcp"  # MCP протокол ошибки
    SERVICE = "service"  # Сервисные ошибки


class McpError(Exception):
    """
    Базовый класс исключений для MCP сервера
    
    Атрибуты:
    - error_code: Код ошибки (E001-E099)
    - error_type: Тип исключения
    - correlation_id: Идентификатор корреляции событий
    - context: Контекст ошибки
    - user_message: Сообщение для пользователя
    - technical_details: Технические детали
    - severity: Серьезность ошибки
    - recoverable: Возможность восстановления
    - context_data: Дополнительные данные контекста
    """
    
    def __init__(
        self,
        error_code: str,
        error_type: str,
        user_message: str,
        technical_message: Optional[str] = None,
        correlation_id: Optional[str] = None,
        context: str = "",
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        recoverable: bool = True,
        context_data: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None
    ):
        self.error_code = error_code
        self.error_type = error_type
        self.correlation_id = correlation_id or str(uuid.uuid4())
        self.context = context
        self.user_message = user_message
        self.technical_message = technical_message or user_message
        self.severity = severity
        self.recoverable = recoverable
        self.context_data = context_data or {}
        self.original_exception = original_exception
        self.timestamp = datetime.utcnow()
        
        # Для совместимости со старым API
        self.category = self._determine_category()
        self.trace_id = self.correlation_id
        
        super().__init__(self.user_message)
    
    def _determine_category(self) -> ErrorCategory:
        """Определяет категорию ошибки по коду"""
        if self.error_code.startswith('E00'):
            return ErrorCategory.SYSTEM
        elif self.error_code.startswith('E02'):
            return ErrorCategory.VALIDATION
        elif self.error_code.startswith('E04'):
            return ErrorCategory.TRANSPORT
        elif self.error_code.startswith('E06'):
            return ErrorCategory.INTEGRATION
        elif self.error_code.startswith('E08'):
            return ErrorCategory.AUTH
        elif self.error_code.startswith('E09'):
            return ErrorCategory.DATABASE
        elif self.error_code.startswith('MCP'):
            return ErrorCategory.MCP
        else:
            return ErrorCategory.SERVICE
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Преобразует исключение в словарь для JSON сериализации
        
        Returns:
            Dict[str, Any]: Словарь с данными исключения
        """
        return {
            "error_code": self.error_code,
            "error_type": self.error_type,
            "correlation_id": self.correlation_id,
            "context": self.context,
            "user_message": self.user_message,
            "technical_message": self.technical_message,
            "severity": self.severity.value,
            "recoverable": self.recoverable,
            "category": self.category.value,
            "timestamp": self.timestamp.isoformat(),
            "context_data": self.context_data,
            "traceback": traceback.format_exc() if self.original_exception else None
        }
    
    def to_mcp_response(self) -> Dict[str, Any]:
        """
        Преобразует исключение в формат ответа MCP протокола
        
        Returns:
            Dict[str, Any]: Ответ в формате MCP
        """
        return {
            "error": {
                "code": self.error_code,
                "message": self.user_message,
                "data": {
                    "error_type": self.error_type,
                    "correlation_id": self.correlation_id,
                    "context": self.context,
                    "severity": self.severity.value,
                    "recoverable": self.recoverable,
                    "timestamp": self.timestamp.isoformat(),
                    **self.context_data
                }
            }
        }
    
    def to_structured_log(self) -> Dict[str, Any]:
        """
        Форматирует исключение для структурированного логирования
        
        Returns:
            Dict[str, Any]: Данные для JSON логирования
        """
        log_data = {
            "timestamp": self.timestamp.isoformat(),
            "level": "ERROR",
            "message": self.user_message,
            "correlation_id": self.correlation_id,
            "trace_id": self.trace_id,
            "error_code": self.error_code,
            "error_type": self.error_type,
            "category": self.category.value,
            "context": self.context,
            "severity": self.severity.value,
            "recoverable": self.recoverable,
            "session_id": "",
            "technical_message": self.technical_message
        }
        
        # Добавляем дополнительные данные контекста
        if self.context_data:
            log_data["additional_data"] = self.context_data
        
        # Добавляем traceback для отладки
        if self.original_exception and logging.getLogger().level <= logging.DEBUG:
            log_data["exception_traceback"] = traceback.format_exc()
        
        return log_data
    
    def log(self, logger: Optional[logging.Logger] = None) -> None:
        """
        Логирует исключение с использованием структурированного логирования
        
        Args:
            logger: Логгер для записи. Если None, используется корневой логгер
        """
        if logger is None:
            logger = logging.getLogger(__name__)
        
        log_data = self.to_structured_log()
        
        # Выбираем уровень логирования на основе серьезности
        if self.severity == ErrorSeverity.CRITICAL:
            logger.critical(json.dumps(log_data, ensure_ascii=False))
        elif self.severity == ErrorSeverity.HIGH:
            logger.error(json.dumps(log_data, ensure_ascii=False))
        elif self.severity == ErrorSeverity.MEDIUM:
            logger.warning(json.dumps(log_data, ensure_ascii=False))
        else:
            logger.info(json.dumps(log_data, ensure_ascii=False))
    
    def add_context(self, key: str, value: Any) -> 'McpError':
        """
        Добавляет данные в контекст ошибки
        
        Args:
            key: Ключ параметра
            value: Значение параметра
            
        Returns:
            McpError: Текущий экземпляр для fluent interface
        """
        self.context_data[key] = value
        return self
    
    def with_correlation_id(self, correlation_id: str) -> 'McpError':
        """
        Устанавливает correlation_id для трассировки
        
        Args:
            correlation_id: Идентификатор корреляции
            
        Returns:
            McpError: Текущий экземпляр для fluent interface
        """
        self.correlation_id = correlation_id
        self.trace_id = correlation_id
        return self
    
    def __str__(self) -> str:
        """Строковое представление исключения"""
        return f"[{self.error_code}] {self.user_message}"
    
    def __repr__(self) -> str:
        """Детальное представление исключения"""
        return (
            f"McpError(error_code='{self.error_code}', "
            f"error_type='{self.error_type}', "
            f"user_message='{self.user_message}', "
            f"correlation_id='{self.correlation_id}')"
        )


class RecoverableError(McpError):
    """
    Базовый класс для восстановимых ошибок
    
    Восстановимые ошибки могут быть исправлены повторной попыткой (retry).
    Примеры: сетевые ошибки, временная недоступность сервиса, таймауты.
    """
    
    def __init__(self, *args, **kwargs):
        # По умолчанию восстановимое
        if 'recoverable' not in kwargs:
            kwargs['recoverable'] = True
        super().__init__(*args, **kwargs)


class NonRecoverableError(McpError):
    """
    Базовый класс для невосстановимых ошибок
    
    Невосстановимые ошибки требуют вмешательства администратора.
    Примеры: нарушение целостности данных, ошибки конфигурации.
    """
    
    def __init__(self, *args, **kwargs):
        # По умолчанию невосстановимое
        if 'recoverable' not in kwargs:
            kwargs['recoverable'] = False
        super().__init__(*args, **kwargs)


class SystemError(McpError):
    """
    Базовый класс для системных ошибок (E001-E019)
    
    Включает ошибки инициализации, проблемы с ресурсами, 
    нарушения прав доступа и другие системные сбои.
    """
    
    def __init__(self, error_code: str, *args, **kwargs):
        if error_code.startswith('E00'):
            kwargs.setdefault('severity', ErrorSeverity.HIGH)
        super().__init__(error_code, "SystemError", *args, **kwargs)


class ServiceUnavailableError(McpError):
    """
    Исключение для недоступности сервиса
    
    Используется когда сервис временно или постоянно недоступен.
    Соответствует HTTP статус коду 503 Service Unavailable.
    """
    
    def __init__(
        self,
        service_name: str,
        user_message: Optional[str] = None,
        **kwargs
    ):
        if user_message is None:
            user_message = f"Сервис '{service_name}' временно недоступен. Попробуйте позже."
        
        kwargs.setdefault('error_code', 'E042')
        kwargs.setdefault('severity', ErrorSeverity.HIGH)
        kwargs.setdefault('recoverable', True)
        kwargs.setdefault('context_data', {})
        kwargs['context_data']['service_name'] = service_name
        
        super().__init__(
            kwargs['error_code'],
            "ServiceUnavailableError",
            user_message,
            **kwargs
        )


class TimeoutError(McpError):
    """
    Исключение для превышения времени ожидания
    
    Используется при превышении лимитов времени выполнения операций.
    """
    
    def __init__(
        self,
        operation: str,
        timeout_seconds: float,
        **kwargs
    ):
        user_message = f"Превышено время ожидания операции '{operation}' ({timeout_seconds}s)"
        
        kwargs.setdefault('error_code', 'E041')
        kwargs.setdefault('severity', ErrorSeverity.MEDIUM)
        kwargs.setdefault('recoverable', True)
        kwargs.setdefault('context_data', {})
        kwargs['context_data'].update({
            'operation': operation,
            'timeout_seconds': timeout_seconds
        })
        
        super().__init__(
            kwargs['error_code'],
            "TimeoutError",
            user_message,
            **kwargs
        )