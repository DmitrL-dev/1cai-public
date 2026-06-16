
"""
Интеграция с Sentry для отслеживания ошибок и производительности.
Включает автоматическую отправку исключений, группировку ошибок и APM мониторинг.
"""

import functools
import os
import threading
import time
from contextlib import contextmanager
from typing import Any, Callable, Dict, Optional


class SentryIntegration:
    """Класс для интеграции с Sentry"""
    
    def __init__(self, dsn: Optional[str] = None, 
                 environment: str = "production",
                 service_name: str = "mcp_server",
                 traces_sample_rate: float = 0.1,
                 profiles_sample_rate: float = 0.1):
        """
        Инициализация интеграции с Sentry
        
        Args:
            dsn: Sentry DSN для отправки событий
            environment: Окружение (production, staging, development)
            service_name: Имя сервиса
            traces_sample_rate: Частота трассировки (0.0 - 1.0)
            profiles_sample_rate: Частота профилирования (0.0 - 1.0)
        """
        self.dsn = dsn or os.getenv('SENTRY_DSN')
        self.environment = environment
        self.service_name = service_name
        self.traces_sample_rate = traces_sample_rate
        self.profiles_sample_rate = profiles_sample_rate
        
        self.client = None
        self._initialized = False
        self._local = threading.local()
        
        if self.dsn:
            self._initialize_sentry()
            
    def _initialize_sentry(self):
        """Инициализация Sentry SDK"""
        try:
            import sentry_sdk
            from sentry_sdk.integrations.logging import LoggingIntegration

            # Настройка логирования для Sentry
            sentry_logging = LoggingIntegration(
                level=logging.INFO,
                event_level=logging.ERROR
            )
            
            # Инициализация клиента
            sentry_sdk.init(
                dsn=self.dsn,
                environment=self.environment,
                traces_sample_rate=self.traces_sample_rate,
                profiles_sample_rate=self.profiles_sample_rate,
                integrations=[sentry_logging],
                release=f"{self.service_name}@1.0.0",
                before_send=self._before_send,
                before_send_transaction=self._before_send_transaction
            )
            
            self.client = sentry_sdk
            self._initialized = True
            
            # Установка тегов по умолчанию
            self.set_extra_context({
                'service_name': self.service_name,
                'environment': self.environment,
                'version': '1.0.0'
            })
            
        except ImportError:
            print("Sentry SDK не установлен. Установите: pip install sentry-sdk[logging]")
        except Exception as e:
            print(f"Ошибка инициализации Sentry: {e}")
            
    def _before_send(self, event, hint):
        """Фильтрация событий перед отправкой"""
        # Фильтрация шумовых ошибок
        if 'exception' in event:
            exception_values = event['exception']['values']
            for exception in exception_values:
                if exception.get('type') in ['ConnectionError', 'TimeoutError']:
                    # Уменьшаем частоту сетевых ошибок
                    return None if 'test' in self.environment else event
                    
        # Добавляем корреляционный ID
        correlation_id = getattr(self._local, 'correlation_id', None)
        if correlation_id:
            event.setdefault('extra', {})['correlation_id'] = correlation_id
            
        return event
        
    def _before_send_transaction(self, event, hint):
        """Фильтрация транзакций перед отправкой"""
        # Фильтрация быстрых операций
        if 'transaction' in event:
            duration = event.get('transaction', {}).get('transaction', {}).get('op', '')
            if duration and isinstance(duration, float) and duration < 0.1:
                return None
                
        return event
        
    def capture_exception(self, exc_info=None, extra=None, tags=None):
        """Захват исключения"""
        if self._initialized and self.client:
            with self._capture_context(extra=extra, tags=tags):
                self.client.capture_exception(exc_info)
                
    def capture_message(self, message, level='info', extra=None, tags=None):
        """Захват сообщения"""
        if self._initialized and self.client:
            with self._capture_context(extra=extra, tags=tags):
                self.client.capture_message(message, level=level)
                
    def set_user_context(self, user_data: Dict[str, Any]):
        """Установка контекста пользователя"""
        if self._initialized and self.client:
            self.client.set_user(user_data)
            
    def set_extra_context(self, extra_data: Dict[str, Any]):
        """Установка дополнительного контекста"""
        if self._initialized and self.client:
            for key, value in extra_data.items():
                self.client.set_extra(key, value)
                
    def set_tag(self, key: str, value: str):
        """Установка тега"""
        if self._initialized and self.client:
            self.client.set_tag(key, value)
            
    @contextmanager
    def _capture_context(self, extra=None, tags=None):
        """Контекстный менеджер для установки контекста"""
        if not self._initialized:
            yield
            return
            
        # Сохраняем текущий контекст
        old_extra = getattr(self._local, 'extra_context', {})
        old_tags = getattr(self._local, 'tags_context', {})
        
        # Устанавливаем новый контекст
        if extra:
            self._local.extra_context = {**old_extra, **extra}
            for key, value in extra.items():
                self.client.set_extra(key, value)
                
        if tags:
            self._local.tags_context = {**old_tags, **tags}
            for key, value in tags.items():
                self.client.set_tag(key, value)
                
        try:
            yield
        finally:
            # Восстанавливаем старый контекст
            self._local.extra_context = old_extra
            self._local.tags_context = old_tags
            
    @contextmanager
    def transaction(self, name: str, op: str = 'custom', 
                   description: Optional[str] = None):
        """Контекстный менеджер для трассировки операций"""
        if not self._initialized:
            yield
            return
            
        start_time = time.time()
        transaction = self.client.start_transaction(
            name=name,
            op=op,
            description=description
        )
        
        try:
            yield transaction
            transaction.set_status('ok')
        except Exception as e:
            transaction.set_status('internal_error')
            self.capture_exception(
                extra={'operation': name, 'op': op},
                tags={'error_type': 'transaction_error'}
            )
            raise
        finally:
            duration = time.time() - start_time
            transaction.set_data('duration_ms', duration * 1000)
            transaction.finish()
            
    @contextmanager
    def span(self, op: str, description: Optional[str] = None):
        """Контекстный менеджер для трассировки span"""
        if not self._initialized:
            yield
            return
            
        with self.client.start_span(op=op, description=description) as span:
            try:
                yield span
            except Exception as e:
                span.set_status('internal_error')
                raise
                
    def set_correlation_id(self, correlation_id: str):
        """Установка корреляционного ID для трассировки"""
        self._local.correlation_id = correlation_id
        if self._initialized:
            self.client.set_tag('correlation_id', correlation_id)
            
    def breadcrumb(self, message: str, category: str = 'custom', 
                  level: str = 'info', **kwargs):
        """Добавление breadcrumb для отладки"""
        if self._initialized:
            self.client.add_breadcrumb(
                message=message,
                category=category,
                level=level,
                timestamp=time.time(),
                **kwargs
            )
            
    def add_integration_tags(self, integration_type: str, operation: str):
        """Добавление тегов интеграции"""
        self.set_tag('integration_type', integration_type)
        self.set_tag('integration_operation', operation)
        
    def add_mcp_tags(self, operation_type: str, operation: str):
        """Добавление тегов MCP операции"""
        self.set_tag('mcp_operation_type', operation_type)
        self.set_tag('mcp_operation', operation)


# Глобальный экземпляр интеграции с Sentry
_global_sentry: Optional[SentryIntegration] = None


def get_sentry() -> SentryIntegration:
    """Получение глобального экземпляра интеграции с Sentry"""
    global _global_sentry
    if _global_sentry is None:
        _global_sentry = SentryIntegration()
    return _global_sentry


def init_sentry(dsn: Optional[str] = None,
                environment: str = "production",
                service_name: str = "mcp_server",
                traces_sample_rate: float = 0.1) -> SentryIntegration:
    """
    Инициализация глобальной интеграции с Sentry
    
    Args:
        dsn: Sentry DSN
        environment: Окружение
        service_name: Имя сервиса
        traces_sample_rate: Частота трассировки
        
    Returns:
        Экземпляр SentryIntegration
    """
    global _global_sentry
    _global_sentry = SentryIntegration(
        dsn=dsn,
        environment=environment,
        service_name=service_name,
        traces_sample_rate=traces_sample_rate
    )
    return _global_sentry


# Декораторы для удобного использования
def sentry_transaction(name: str, op: str = 'function'):
    """Декоратор для создания транзакции Sentry"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            sentry = get_sentry()
            correlation_id = kwargs.get('correlation_id')
            if correlation_id:
                sentry.set_correlation_id(correlation_id)
                
            with sentry.transaction(name=name, op=op):
                return func(*args, **kwargs)
                
        return wrapper
    return decorator


def sentry_span(op: str, description: Optional[str] = None):
    """Декоратор для создания span в Sentry"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            sentry = get_sentry()
            correlation_id = kwargs.get('correlation_id')
            if correlation_id:
                sentry.set_correlation_id(correlation_id)
                
            with sentry.span(op=op, description=description or func.__name__):
                return func(*args, **kwargs)
                
        return wrapper
    return decorator


def capture_exception_safe(exc_info=None, extra=None, tags=None):
    """Безопасный захват исключения (не бросает исключения если Sentry недоступен)"""
    try:
        get_sentry().capture_exception(exc_info, extra, tags)
    except Exception:
        pass  # Игнорируем ошибки Sentry


def capture_message_safe(message: str, level='info', extra=None, tags=None):
    """Безопасный захват сообщения"""
    try:
        get_sentry().capture_message(message, level, extra, tags)
    except Exception:
        pass


# Утилиты для группировки ошибок
class ErrorGrouper:
    """Класс для группировки похожих ошибок"""
    
    def __init__(self):
        self.error_hashes = {}
        self.group_count = {}
        
    def get_error_group(self, error: Exception, context: Dict[str, Any]) -> str:
        """
        Получение группы ошибки для группировки
        
        Args:
            error: Исключение
            context: Контекст ошибки
            
        Returns:
            Хэш группы ошибки
        """
        import hashlib

        # Базовые параметры для группировки
        group_key = {
            'error_type': type(error).__name__,
            'error_message': str(error)[:100],  # Ограничиваем длину
            'operation': context.get('operation', 'unknown'),
            'module': context.get('module', 'unknown')
        }
        
        # Создаем хэш
        hash_input = f"{group_key['error_type']}_{group_key['operation']}_{group_key['module']}"
        return hashlib.md5(hash_input.encode()).hexdigest()[:8]
        
    def should_group_error(self, error: Exception, context: Dict[str, Any]) -> bool:
        """
        Определение, нужно ли группировать ошибку
        
        Args:
            error: Исключение
            context: Контекст ошибки
            
        Returns:
            True если ошибка должна быть сгруппирована
        """
        group_hash = self.get_error_group(error, context)
        return self.error_hashes.get(group_hash, 0) > 0
        
    def register_error(self, error: Exception, context: Dict[str, Any]):
        """Регистрация ошибки в группировке"""
        group_hash = self.get_error_group(error, context)
        self.error_hashes[group_hash] = self.error_hashes.get(group_hash, 0) + 1
        
        # Создаем тэг для Sentry
        sentry = get_sentry()
        sentry.set_tag('error_group', group_hash)
        sentry.set_tag('error_type', type(error).__name__)


# Глобальный группировщик ошибок
_global_grouper = ErrorGrouper()


def group_error(error: Exception, context: Dict[str, Any]):
    """Группировка ошибки"""
    _global_grouper.register_error(error, context)