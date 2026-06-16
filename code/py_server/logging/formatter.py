
"""
JSON форматирование и структура логов.

Создание стандартизированных структур логов с поддержкой
correlation_id, метрик и APM интеграции.
"""

import json
import time
import traceback
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class LogLevel(Enum):
    """Уровни логирования"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ErrorType(Enum):
    """Типы ошибок"""
    VALIDATION_ERROR = "VALIDATION_ERROR"
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    AUTHORIZATION_ERROR = "AUTHORIZATION_ERROR"
    BUSINESS_LOGIC_ERROR = "BUSINESS_LOGIC_ERROR"
    INFRASTRUCTURE_ERROR = "INFRASTRUCTURE_ERROR"
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
    DATA_ERROR = "DATA_ERROR"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"
    RATE_LIMIT_ERROR = "RATE_LIMIT_ERROR"


def create_log_structure(
    level: LogLevel,
    message: str,
    logger_name: str,
    correlation_id: Optional[str] = None,
    user_id: Optional[str] = None,
    request_id: Optional[str] = None,
    duration_ms: Optional[float] = None,
    service_name: Optional[str] = None,
    error_code: Optional[str] = None,
    error_type: Optional[ErrorType] = None,
    stacktrace: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    http_method: Optional[str] = None,
    http_status_code: Optional[int] = None,
    target_url: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Создание структурированного лога.
    
    Args:
        level: Уровень логирования
        message: Основное сообщение
        logger_name: Имя логгера
        correlation_id: ID трассировки запросов
        user_id: Анонимизированный ID пользователя
        request_id: ID запроса
        duration_ms: Время выполнения в миллисекундах
        service_name: Имя сервиса
        error_code: Код ошибки
        error_type: Тип ошибки
        stacktrace: Стек ошибки
        context: Дополнительные данные
        http_method: HTTP метод
        http_status_code: HTTP статус код
        target_url: Целевой URL
        **kwargs: Дополнительные поля
    
    Returns:
        Словарь со структурой лога
    """
    
    # Генерация недостающих идентификаторов
    correlation_id = correlation_id or str(uuid.uuid4())
    request_id = request_id or str(uuid.uuid4())
    
    # Базовые поля
    log_structure = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level.value,
        "message": message,
        "logger_name": logger_name,
        "correlation_id": correlation_id,
        "request_id": request_id,
        "service_name": service_name,
    }
    
    # Опциональные поля
    if user_id:
        log_structure["user_id"] = user_id
    
    if duration_ms:
        log_structure["duration_ms"] = duration_ms
    
    if error_code:
        log_structure["error_code"] = error_code
    
    if error_type:
        log_structure["error_type"] = error_type.value
    
    if stacktrace:
        log_structure["stacktrace"] = stacktrace
    
    if context:
        log_structure["context"] = context
    
    if http_method:
        log_structure["http_method"] = http_method
    
    if http_status_code:
        log_structure["http_status_code"] = http_status_code
    
    if target_url:
        log_structure["target_url"] = target_url
    
    # Добавление дополнительных полей
    log_structure.update(kwargs)
    
    # Метаданные
    log_structure["_metadata"] = {
        "structured_log_version": "1.0",
        "created_at": time.time(),
        "format_version": "json",
    }
    
    return log_structure


class StructuredFormatter:
    """Форматировщик для структурированных логов"""
    
    def __init__(self, **kwargs):
        self.additional_fields = kwargs
        self.pretty_print = kwargs.get('pretty_print', False)
        
    def json_processor(self, logger, method_name, event_dict):
        """Обработчик для JSON вывода"""
        
        # Создание базовой структуры
        log_data = create_log_structure(
            level=LogLevel(method_name.upper()),
            message=event_dict.get('event', ''),
            logger_name=logger.name,
            correlation_id=event_dict.get('correlation_id'),
            user_id=event_dict.get('user_id'),
            duration_ms=event_dict.get('duration_ms'),
            error_code=event_dict.get('error_code'),
            error_type=event_dict.get('error_type'),
            context=event_dict.get('context'),
            **self.additional_fields
        )
        
        # Добавление исключения
        if 'exception' in event_dict:
            log_data['exception'] = event_dict['exception']
            log_data['stacktrace'] = self._extract_stacktrace(event_dict['exception'])
        
        # Добавление дополнительных данных
        extra_fields = {k: v for k, v in event_dict.items() 
                       if k not in ['event', 'correlation_id', 'user_id', 
                                   'duration_ms', 'error_code', 'error_type', 'context', 'exception']}
        
        if extra_fields:
            log_data['extra'] = extra_fields
        
        return log_data
    
    def _extract_stacktrace(self, exception_info):
        """Извлечение стека ошибки"""
        if isinstance(exception_info, tuple) and len(exception_info) >= 3:
            return ''.join(traceback.format_tb(exception_info[2]))
        return str(exception_info)
    
    @staticmethod
    def format_json(data: Dict[str, Any], pretty: bool = False) -> str:
        """Форматирование данных в JSON"""
        if pretty:
            return json.dumps(data, indent=2, ensure_ascii=False, default=str)
        return json.dumps(data, separators=(',', ':'), ensure_ascii=False, default=str)
    
    @staticmethod
    def parse_json(log_line: str) -> Optional[Dict[str, Any]]:
        """Парсинг JSON лога"""
        try:
            return json.loads(log_line)
        except (json.JSONDecodeError, TypeError):
            return None


class HTTPRequestFormatter:
    """Специализированный форматировщик для HTTP запросов"""
    
    @staticmethod
    def format_request_log(
        method: str,
        url: str,
        status_code: int,
        duration_ms: float,
        correlation_id: str,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
        request_size: Optional[int] = None,
        response_size: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Форматирование лога HTTP запроса"""
        
        level = LogLevel.INFO if status_code < 400 else LogLevel.ERROR
        if status_code >= 500:
            level = LogLevel.ERROR
        elif status_code >= 400:
            level = LogLevel.WARNING
        
        return create_log_structure(
            level=level,
            message=f"{method} {url} - {status_code}",
            logger_name="http.request",
            correlation_id=correlation_id,
            duration_ms=duration_ms,
            http_method=method,
            http_status_code=status_code,
            target_url=url,
            context={
                "user_agent": user_agent,
                "ip_address": ip_address,
                "request_size": request_size,
                "response_size": response_size,
                **kwargs
            }
        )
    
    @staticmethod
    def format_error_log(
        method: str,
        url: str,
        error: Exception,
        correlation_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Форматирование лога ошибки HTTP"""
        
        # Определение типа ошибки
        error_type = HTTPRequestFormatter._get_error_type(error)
        error_code = HTTPRequestFormatter._get_error_code(error)
        
        return create_log_structure(
            level=LogLevel.ERROR,
            message=str(error),
            logger_name="http.error",
            correlation_id=correlation_id,
            http_method=method,
            target_url=url,
            error_code=error_code,
            error_type=error_type,
            stacktrace=traceback.format_exc(),
            context=kwargs
        )
    
    @staticmethod
    def _get_error_type(error: Exception) -> ErrorType:
        """Определение типа ошибки"""
        error_name = type(error).__name__
        
        type_mapping = {
            'ValidationError': ErrorType.VALIDATION_ERROR,
            'AuthenticationError': ErrorType.AUTHENTICATION_ERROR,
            'AuthorizationError': ErrorType.AUTHORIZATION_ERROR,
            'TimeoutError': ErrorType.TIMEOUT_ERROR,
            'RateLimitError': ErrorType.RATE_LIMIT_ERROR,
        }
        
        return type_mapping.get(error_name, ErrorType.BUSINESS_LOGIC_ERROR)
    
    @staticmethod
    def _get_error_code(error: Exception) -> str:
        """Генерация кода ошибки"""
        return f"{type(error).__name__.upper()}_{hash(str(error)) % 10000:04d}"


class PerformanceFormatter:
    """Форматировщик для метрик производительности"""
    
    @staticmethod
    def format_performance_log(
        operation: str,
        duration_ms: float,
        correlation_id: str,
        **metrics
    ) -> Dict[str, Any]:
        """Форматирование лога производительности"""
        
        # Определение уровня на основе длительности
        if duration_ms > 5000:
            level = LogLevel.ERROR
        elif duration_ms > 1000:
            level = LogLevel.WARNING
        else:
            level = LogLevel.INFO
        
        return create_log_structure(
            level=level,
            message=f"Operation '{operation}' completed",
            logger_name="performance",
            correlation_id=correlation_id,
            duration_ms=duration_ms,
            context={
                "operation": operation,
                "performance_metrics": metrics
            }
        )


class BusinessEventFormatter:
    """Форматировщик для бизнес-событий"""
    
    @staticmethod
    def format_business_event(
        event_type: str,
        action: str,
        user_id: str,
        correlation_id: str,
        **event_data
    ) -> Dict[str, Any]:
        """Форматирование бизнес-события"""
        
        return create_log_structure(
            level=LogLevel.INFO,
            message=f"Business event: {event_type} - {action}",
            logger_name="business",
            correlation_id=correlation_id,
            user_id=user_id,
            context={
                "event_type": event_type,
                "action": action,
                "event_data": event_data
            }
        )


# Утилиты для работы с логами
class LogValidator:
    """Валидатор структуры логов"""
    
    REQUIRED_FIELDS = ['timestamp', 'level', 'message', 'logger_name', 'correlation_id']
    OPTIONAL_FIELDS = [
        'user_id', 'request_id', 'duration_ms', 'service_name',
        'error_code', 'error_type', 'stacktrace', 'context',
        'http_method', 'http_status_code', 'target_url'
    ]
    
    @classmethod
    def validate(cls, log_data: Dict[str, Any]) -> tuple[bool, List[str]]:
        """Валидация структуры лога"""
        errors = []
        
        # Проверка обязательных полей
        for field in cls.REQUIRED_FIELDS:
            if field not in log_data:
                errors.append(f"Missing required field: {field}")
        
        # Проверка формата timestamp
        if 'timestamp' in log_data:
            try:
                datetime.fromisoformat(log_data['timestamp'].replace('Z', '+00:00'))
            except ValueError:
                errors.append("Invalid timestamp format")
        
        # Проверка correlation_id
        if 'correlation_id' in log_data:
            try:
                uuid.UUID(log_data['correlation_id'])
            except ValueError:
                errors.append("Invalid correlation_id format")
        
        return len(errors) == 0, errors
    
    @classmethod
    def sanitize_for_storage(cls, log_data: Dict[str, Any]) -> Dict[str, Any]:
        """Сантизация лога для хранения"""
        # Удаление чувствительных данных
        sanitized = log_data.copy()
        
        sensitive_keys = ['password', 'token', 'secret', 'api_key']
        for key in sensitive_keys:
            if key in sanitized.get('context', {}):
                sanitized['context'][key] = '***REDACTED***'
        
        return sanitized


def format_structured_log(
    level: LogLevel,
    message: str,
    logger_name: str,
    **kwargs
) -> str:
    """Быстрое форматирование структурированного лога"""
    log_data = create_log_structure(
        level=level,
        message=message,
        logger_name=logger_name,
        **kwargs
    )
    return StructuredFormatter.format_json(log_data)