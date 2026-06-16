
"""
Middleware для работы с correlation_id и контекстом запросов.

Предоставляет автоматическое отслеживание запросов через
корреляционные идентификаторы и контекст.
"""

import asyncio
import threading
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Callable, Dict, Optional

import structlog

from .config import logging_config
from .formatter import LogLevel, create_log_structure

# Context variables для thread-safe хранения контекста
_correlation_id_var: ContextVar[str] = ContextVar('correlation_id', default=str(uuid.uuid4()))
_user_id_var: ContextVar[Optional[str]] = ContextVar('user_id', default=None)
_request_id_var: ContextVar[str] = ContextVar('request_id', default=str(uuid.uuid4()))
_start_time_var: ContextVar[float] = ContextVar('start_time', default=time.time())
_context_var: ContextVar[Dict[str, Any]] = ContextVar('context', default={})
_parent_correlation_var: ContextVar[Optional[str]] = ContextVar('parent_correlation', default=None)


class CorrelationContext:
    """Контекст корреляции для отслеживания запросов"""
    
    def __init__(self):
        self.logger = structlog.get_logger("correlation")
        self._local = threading.local()
    
    def generate_correlation_id(self) -> str:
        """Генерация нового correlation_id"""
        return str(uuid.uuid4())
    
    def get_correlation_id(self) -> str:
        """Получение текущего correlation_id"""
        try:
            return _correlation_id_var.get()
        except LookupError:
            new_id = self.generate_correlation_id()
            _correlation_id_var.set(new_id)
            return new_id
    
    def set_correlation_id(self, correlation_id: str):
        """Установка correlation_id"""
        _correlation_id_var.set(correlation_id)
    
    def get_user_id(self) -> Optional[str]:
        """Получение текущего user_id"""
        return _user_id_var.get()
    
    def set_user_id(self, user_id: Optional[str]):
        """Установка user_id"""
        _user_id_var.set(user_id)
    
    def get_request_id(self) -> str:
        """Получение текущего request_id"""
        return _request_id_var.get()
    
    def set_request_id(self, request_id: str):
        """Установка request_id"""
        _request_id_var.set(request_id)
    
    def get_start_time(self) -> float:
        """Получение времени начала запроса"""
        return _start_time_var.get()
    
    def set_start_time(self, start_time: float):
        """Установка времени начала запроса"""
        _start_time_var.set(start_time)
    
    def get_context(self) -> Dict[str, Any]:
        """Получение контекста запроса"""
        return _context_var.get().copy()
    
    def set_context(self, context: Dict[str, Any]):
        """Установка контекста запроса"""
        _context_var.set(context.copy())
    
    def update_context(self, key: str, value: Any):
        """Обновление контекста"""
        current_context = self.get_context()
        current_context[key] = value
        self.set_context(current_context)
    
    def get_parent_correlation(self) -> Optional[str]:
        """Получение parent correlation_id"""
        return _parent_correlation_var.get()
    
    def set_parent_correlation(self, parent_id: Optional[str]):
        """Установка parent correlation_id"""
        _parent_correlation_var.set(parent_id)
    
    def get_duration_ms(self) -> float:
        """Вычисление продолжительности в миллисекундах"""
        return (time.time() - self.get_start_time()) * 1000


# Глобальный экземпляр контекста
correlation_context = CorrelationContext()


@contextmanager
def correlation_context_manager(
    correlation_id: Optional[str] = None,
    user_id: Optional[str] = None,
    parent_correlation: Optional[str] = None,
    **context_data
):
    """Контекстный менеджер для установки correlation контекста"""
    
    # Сохранение предыдущих значений
    prev_correlation = correlation_context.get_correlation_id()
    prev_user_id = correlation_context.get_user_id()
    prev_parent = correlation_context.get_parent_correlation()
    prev_context = correlation_context.get_context()
    
    try:
        # Установка новых значений
        if correlation_id:
            correlation_context.set_correlation_id(correlation_id)
        else:
            correlation_context.set_correlation_id(correlation_context.generate_correlation_id())
        
        if user_id:
            correlation_context.set_user_id(user_id)
        
        if parent_correlation:
            correlation_context.set_parent_correlation(parent_correlation)
        
        if context_data:
            correlation_context.set_context(context_data)
        
        yield correlation_context
        
    finally:
        # Восстановление предыдущих значений
        correlation_context.set_correlation_id(prev_correlation)
        correlation_context.set_user_id(prev_user_id)
        correlation_context.set_parent_correlation(prev_parent)
        correlation_context.set_context(prev_context)


class LoggingMiddleware:
    """HTTP middleware для автоматического логирования запросов"""
    
    def __init__(self, app: Callable, **kwargs):
        self.app = app
        self.correlation_header = kwargs.get('correlation_header', logging_config.CORRELATION_ID_HEADER)
        self.user_id_header = kwargs.get('user_id_header', 'X-User-ID')
        self.logger = structlog.get_logger("middleware")
    
    async def __call__(self, scope, receive, send):
        """ASGI middleware для обработки HTTP запросов"""
        if scope["type"] == "http":
            await self.handle_http_request(scope, receive, send)
        else:
            # Прямой прокси для других типов
            await self.app(scope, receive, send)
    
    async def handle_http_request(self, scope, receive, send):
        """Обработка HTTP запроса"""
        start_time = time.time()
        
        # Извлечение заголовков
        headers = dict(scope.get("headers", []))
        
        # Получение correlation_id
        correlation_id = self._get_header(headers, self.correlation_header)
        if not correlation_id:
            correlation_id = correlation_context.generate_correlation_id()
        
        # Получение user_id
        user_id = self._get_header(headers, self.user_id_header)
        
        # Извлечение HTTP данных
        method = scope.get("method", "")
        path = scope.get("path", "")
        query_string = scope.get("query_string", b"").decode()
        url = f"{path}?{query_string}" if query_string else path
        client_ip = self._get_client_ip(scope, headers)
        user_agent = self._get_header(headers, b"user-agent")
        
        # Создание контекста
        with correlation_context_manager(
            correlation_id=correlation_id,
            user_id=user_id,
            http_method=method,
            target_url=url,
            ip_address=client_ip,
            user_agent=user_agent.decode() if user_agent else None,
            start_time=time.time()
        ):
            # Логирование начала запроса
            self._log_request_start(method, url, correlation_id, user_id, client_ip, user_agent)
            
            try:
                # Обработка запроса
                await self.app(scope, receive, send)
                
                # Логирование успешного завершения
                duration = (time.time() - start_time) * 1000
                self._log_request_success(method, url, 200, duration, correlation_id)
                
            except Exception as e:
                # Логирование ошибки
                duration = (time.time() - start_time) * 1000
                self._log_request_error(method, url, e, duration, correlation_id)
                raise
    
    def _get_header(self, headers: Dict, key: str) -> Optional[str]:
        """Извлечение заголовка из HTTP headers"""
        if isinstance(key, str):
            key = key.lower().encode()
        
        for header_key, header_value in headers.items():
            if header_key == key:
                return header_value.decode().strip()
        return None
    
    def _get_client_ip(self, scope: Dict, headers: Dict) -> str:
        """Получение IP адреса клиента"""
        # Проверка прокси заголовков
        forwarded_for = self._get_header(headers, "X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = self._get_header(headers, "X-Real-IP")
        if real_ip:
            return real_ip
        
        # Использование IP из scope
        client = scope.get("client")
        if client:
            return f"{client[0]}:{client[1]}"
        
        return "unknown"
    
    def _log_request_start(self, method: str, url: str, correlation_id: str, 
                          user_id: Optional[str], client_ip: str, user_agent: Optional[str]):
        """Логирование начала запроса"""
        log_data = create_log_structure(
            level=LogLevel.INFO,
            message=f"Request started: {method} {url}",
            logger_name="http.request",
            correlation_id=correlation_id,
            user_id=user_id,
            http_method=method,
            target_url=url,
            context={
                "event": "request_start",
                "client_ip": client_ip,
                "user_agent": user_agent,
                "scope": "incoming"
            }
        )
        
        self.logger.info("Request started", **log_data)
    
    def _log_request_success(self, method: str, url: str, status_code: int, 
                           duration: float, correlation_id: str):
        """Логирование успешного завершения"""
        log_data = create_log_structure(
            level=LogLevel.INFO if status_code < 400 else LogLevel.WARNING,
            message=f"Request completed: {method} {url} - {status_code}",
            logger_name="http.request",
            correlation_id=correlation_id,
            duration_ms=duration,
            http_method=method,
            http_status_code=status_code,
            target_url=url,
            context={
                "event": "request_complete",
                "scope": "incoming",
                "success": status_code < 400
            }
        )
        
        self.logger.info("Request completed", **log_data)
    
    def _log_request_error(self, method: str, url: str, error: Exception, 
                         duration: float, correlation_id: str):
        """Логирование ошибки запроса"""
        log_data = create_log_structure(
            level=LogLevel.ERROR,
            message=f"Request error: {method} {url} - {error}",
            logger_name="http.error",
            correlation_id=correlation_id,
            duration_ms=duration,
            http_method=method,
            target_url=url,
            error_type=str(type(error).__name__),
            error_code=f"{type(error).__name__.upper()}",
            stacktrace=self._format_error_traceback(error),
            context={
                "event": "request_error",
                "scope": "incoming"
            }
        )
        
        self.logger.error("Request error", **log_data)
    
    def _format_error_traceback(self, error: Exception) -> str:
        """Форматирование stack trace для ошибки"""
        import traceback
        return ''.join(traceback.format_exception(type(error), error, error.__traceback__))


# Утилиты для работы с контекстом
def get_correlation_id_from_context() -> str:
    """Получение correlation_id из текущего контекста"""
    return correlation_context.get_correlation_id()


def get_user_id_from_context() -> Optional[str]:
    """Получение user_id из текущего контекста"""
    return correlation_context.get_user_id()


def get_request_duration() -> float:
    """Получение времени выполнения текущего запроса"""
    return correlation_context.get_duration_ms()


def add_to_context(key: str, value: Any):
    """Добавление данных в контекст запроса"""
    correlation_context.update_context(key, value)


# Декораторы для функций
def with_correlation_id(correlation_id: Optional[str] = None):
    """Декоратор для автоматического установления correlation_id"""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            with correlation_context_manager(correlation_id=correlation_id):
                return await func(*args, **kwargs)
        
        def sync_wrapper(*args, **kwargs):
            with correlation_context_manager(correlation_id=correlation_id):
                return func(*args, **kwargs)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def with_user_id(user_id: Optional[str] = None):
    """Декоратор для автоматического установления user_id"""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            with correlation_context_manager(user_id=user_id):
                return await func(*args, **kwargs)
        
        def sync_wrapper(*args, **kwargs):
            with correlation_context_manager(user_id=user_id):
                return func(*args, **kwargs)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def log_execution_time(operation_name: str = None):
    """Декоратор для логирования времени выполнения функции"""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            op_name = operation_name or func.__name__
            start_time = time.time()
            
            with correlation_context_manager():
                try:
                    result = await func(*args, **kwargs)
                    duration = (time.time() - start_time) * 1000
                    
                    log_data = create_log_structure(
                        level=LogLevel.INFO,
                        message=f"Function '{op_name}' completed successfully",
                        logger_name="function.execution",
                        duration_ms=duration,
                        context={
                            "operation": op_name,
                            "function": func.__name__,
                            "success": True
                        }
                    )
                    
                    structlog.get_logger("function.execution").info("Function executed", **log_data)
                    return result
                
                except Exception as e:
                    duration = (time.time() - start_time) * 1000
                    
                    log_data = create_log_structure(
                        level=LogLevel.ERROR,
                        message=f"Function '{op_name}' failed: {e}",
                        logger_name="function.error",
                        duration_ms=duration,
                        error_type=str(type(e).__name__),
                        stacktrace=traceback.format_exc(),
                        context={
                            "operation": op_name,
                            "function": func.__name__,
                            "success": False
                        }
                    )
                    
                    structlog.get_logger("function.error").error("Function failed", **log_data)
                    raise
        
        def sync_wrapper(*args, **kwargs):
            op_name = operation_name or func.__name__
            start_time = time.time()
            
            with correlation_context_manager():
                try:
                    result = func(*args, **kwargs)
                    duration = (time.time() - start_time) * 1000
                    
                    log_data = create_log_structure(
                        level=LogLevel.INFO,
                        message=f"Function '{op_name}' completed successfully",
                        logger_name="function.execution",
                        duration_ms=duration,
                        context={
                            "operation": op_name,
                            "function": func.__name__,
                            "success": True
                        }
                    )
                    
                    structlog.get_logger("function.execution").info("Function executed", **log_data)
                    return result
                
                except Exception as e:
                    duration = (time.time() - start_time) * 1000
                    
                    log_data = create_log_structure(
                        level=LogLevel.ERROR,
                        message=f"Function '{op_name}' failed: {e}",
                        logger_name="function.error",
                        duration_ms=duration,
                        error_type=str(type(e).__name__),
                        stacktrace=traceback.format_exc(),
                        context={
                            "operation": op_name,
                            "function": func.__name__,
                            "success": False
                        }
                    )
                    
                    structlog.get_logger("function.error").error("Function failed", **log_data)
                    raise
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator