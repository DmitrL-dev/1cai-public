
"""
Модуль управления корреляционными ID для трассировки запросов

Обеспечивает:
- Генерацию уникальных correlation_id
- Извлечение из заголовков запросов
- Проксирование через все уровни системы
- Логирование с полным контекстом
"""

import asyncio
import logging
import uuid
from typing import Any, Dict, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


class CorrelationIdContext:
    """Контекст для хранения correlation_id"""
    
    _local = {}
    
    @classmethod
    def set_correlation_id(cls, correlation_id: str) -> None:
        """Устанавливает correlation_id в контекст"""
        cls._local['correlation_id'] = correlation_id
    
    @classmethod
    def get_correlation_id(cls) -> Optional[str]:
        """Получает correlation_id из контекста"""
        return cls._local.get('correlation_id')
    
    @classmethod
    def clear(cls) -> None:
        """Очищает контекст"""
        cls._local.clear()


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware для автоматического управления correlation_id
    
    Функции:
    - Извлекает correlation_id из заголовков (X-Correlation-Id, X-Request-Id)
    - Генерирует новый если отсутствует
    - Сохраняет в контексте запроса
    - Добавляет в ответ
    """
    
    def __init__(
        self,
        app: ASGIApp,
        header_names: Optional[list] = None
    ):
        super().__init__(app)
        self.header_names = header_names or [
            'x-correlation-id',
            'x-request-id', 
            'x-trace-id',
            'trace-id',
            'correlation-id'
        ]
    
    async def dispatch(self, request: Request, call_next) -> Response:
        # Извлекаем или генерируем correlation_id
        correlation_id = self._extract_correlation_id(request)
        
        # Устанавливаем в контекст
        CorrelationIdContext.set_correlation_id(correlation_id)
        
        # Логируем начало обработки
        logger.info(
            f"Начало обработки запроса {request.method} {request.url.path}",
            extra={
                'correlation_id': correlation_id,
                'method': request.method,
                'path': str(request.url.path),
                'client_ip': self._get_client_ip(request),
                'user_agent': request.headers.get('user-agent', '')
            }
        )
        
        try:
            # Выполняем запрос
            response = await call_next(request)
            
            # Добавляем correlation_id в ответ
            response.headers['X-Correlation-Id'] = correlation_id
            
            # Логируем успешное завершение
            logger.info(
                f"Запрос завершен успешно: {response.status_code}",
                extra={
                    'correlation_id': correlation_id,
                    'status_code': response.status_code,
                    'method': request.method,
                    'path': str(request.url.path)
                }
            )
            
            return response
            
        except Exception as e:
            # Логируем ошибку с correlation_id
            logger.error(
                f"Ошибка при обработке запроса: {str(e)}",
                extra={
                    'correlation_id': correlation_id,
                    'method': request.method,
                    'path': str(request.url.path),
                    'error_type': type(e).__name__,
                    'error_message': str(e)
                },
                exc_info=True
            )
            raise
            
        finally:
            # Очищаем контекст
            CorrelationIdContext.clear()
    
    def _extract_correlation_id(self, request: Request) -> str:
        """
        Извлекает correlation_id из заголовков запроса
        
        Args:
            request: FastAPI Request объект
            
        Returns:
            str: Извлеченный или сгенерированный correlation_id
        """
        # Проверяем заголовки в порядке приоритета
        for header_name in self.header_names:
            correlation_id = request.headers.get(header_name)
            if correlation_id:
                logger.debug(
                    f"Извлечен correlation_id из заголовка {header_name}",
                    extra={'correlation_id': correlation_id}
                )
                return correlation_id.strip()
        
        # Генерируем новый если не найден
        correlation_id = str(uuid.uuid4())
        logger.debug(
            "Сгенерирован новый correlation_id",
            extra={'correlation_id': correlation_id}
        )
        
        return correlation_id
    
    def _get_client_ip(self, request: Request) -> str:
        """Получает IP адрес клиента"""
        # Проверяем прокси заголовки
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        
        real_ip = request.headers.get('X-Real-IP')
        if real_ip:
            return real_ip
        
        # Используем прямое подключение
        if hasattr(request.client, 'host'):
            return request.client.host
        
        return 'unknown'


def get_correlation_id() -> Optional[str]:
    """
    Получает текущий correlation_id из контекста
    
    Returns:
        Optional[str]: Текущий correlation_id или None
    """
    return CorrelationIdContext.get_correlation_id()


def set_correlation_id(correlation_id: str) -> None:
    """
    Устанавливает correlation_id в контекст
    
    Args:
        correlation_id: Идентификатор корреляции
    """
    CorrelationIdContext.set_correlation_id(correlation_id)


def log_with_correlation(
    level: int,
    message: str,
    extra: Optional[Dict[str, Any]] = None,
    **kwargs
) -> None:
    """
    Логирует сообщение с автоматическим добавлением correlation_id
    
    Args:
        level: Уровень логирования
        message: Сообщение
        extra: Дополнительные данные
        **kwargs: Дополнительные параметры логирования
    """
    correlation_id = get_correlation_id()
    
    if extra is None:
        extra = {}
    
    extra['correlation_id'] = correlation_id
    
    logger.log(level, message, extra=extra, **kwargs)


def format_correlation_context(
    operation: str,
    **context_data
) -> Dict[str, Any]:
    """
    Форматирует контекст с correlation_id для структурированного логирования
    
    Args:
        operation: Название операции
        **context_data: Дополнительные данные контекста
        
    Returns:
        Dict[str, Any]: Контекст с correlation_id
    """
    correlation_id = get_correlation_id()
    
    context = {
        'operation': operation,
        'correlation_id': correlation_id,
        'timestamp': logger.handlers[0].formatter.formatTime(
            logging.LogRecord('', 0, '', 0, '', (), None)
        ) if logger.handlers else None
    }
    
    context.update(context_data)
    
    return context


# Фабрика для создания контекстного логгера
class ContextLogger:
    """Логгер с автоматическим добавлением correlation_id"""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
    
    def info(self, message: str, **context) -> None:
        """Логирует информационное сообщение"""
        log_with_correlation(logging.INFO, message, context)
    
    def warning(self, message: str, **context) -> None:
        """Логирует предупреждение"""
        log_with_correlation(logging.WARNING, message, context)
    
    def error(self, message: str, **context) -> None:
        """Логирует ошибку"""
        log_with_correlation(logging.ERROR, message, context)
    
    def debug(self, message: str, **context) -> None:
        """Логирует отладочное сообщение"""
        log_with_correlation(logging.DEBUG, message, context)


def get_context_logger(name: str) -> ContextLogger:
    """Создает контекстный логгер"""
    return ContextLogger(name)


# Интеграция с OpenTelemetry (опционально)
try:
    from opentelemetry.trace import get_tracer
    
    def trace_operation(operation_name: str):
        """Декоратор для трассировки операций с correlation_id"""
        tracer = get_tracer(__name__)
        
        def decorator(func):
            async def async_wrapper(*args, **kwargs):
                correlation_id = get_correlation_id()
                with tracer.start_as_current_span(operation_name) as span:
                    if correlation_id:
                        span.set_attribute('correlation_id', correlation_id)
                    
                    try:
                        result = await func(*args, **kwargs)
                        span.set_status('ok')
                        return result
                    except Exception as e:
                        span.set_status('error', str(e))
                        span.set_attribute('error.type', type(e).__name__)
                        raise
            
            def sync_wrapper(*args, **kwargs):
                correlation_id = get_correlation_id()
                with tracer.start_as_current_span(operation_name) as span:
                    if correlation_id:
                        span.set_attribute('correlation_id', correlation_id)
                    
                    try:
                        result = func(*args, **kwargs)
                        span.set_status('ok')
                        return result
                    except Exception as e:
                        span.set_status('error', str(e))
                        span.set_attribute('error.type', type(e).__name__)
                        raise
            
            return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
        return decorator

except ImportError:
    # OpenTelemetry не установлен, используем заглушку
    def trace_operation(operation_name: str):
        def decorator(func):
            return func
        return decorator
