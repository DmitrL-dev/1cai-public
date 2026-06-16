
"""
Prometheus метрики для системы мониторинга MCP сервера.
Включает метрики ошибок, производительности и состояния системы.
"""

import functools
import time
from typing import Any, Callable, Dict, Optional

from prometheus_client import (CONTENT_TYPE_LATEST, CollectorRegistry, Counter,
                               Gauge, Histogram, Info, generate_latest)
from prometheus_client.core import REGISTRY


class PrometheusMetrics:
    """Класс для управления Prometheus метриками"""
    
    def __init__(self, registry: Optional[CollectorRegistry] = None, 
                 service_name: str = "mcp_server"):
        """
        Инициализация метрик
        
        Args:
            registry: Пользовательский registry для метрик
            service_name: Имя сервиса для тегов
        """
        self.service_name = service_name
        self.registry = registry or REGISTRY
        
        # Счетчики ошибок по типам
        self.error_counters = {
            'validation': Counter(
                'mcp_validation_errors_total',
                'Total validation errors',
                ['error_type', 'operation', 'correlation_id'],
                registry=self.registry
            ),
            'transport': Counter(
                'mcp_transport_errors_total',
                'Total transport errors',
                ['error_type', 'operation', 'correlation_id'],
                registry=self.registry
            ),
            'integration': Counter(
                'mcp_integration_errors_total',
                'Total integration errors',
                ['error_type', 'operation', 'correlation_id'],
                registry=self.registry
            ),
            'auth': Counter(
                'mcp_auth_errors_total',
                'Total authentication errors',
                ['error_type', 'operation', 'correlation_id'],
                registry=self.registry
            ),
            'circuit_breaker': Counter(
                'mcp_circuit_breaker_errors_total',
                'Total circuit breaker errors',
                ['operation', 'correlation_id'],
                registry=self.registry
            )
        }
        
        # Гистограммы времени выполнения операций
        self.duration_histograms = {
            'mcp_operations': Histogram(
                'mcp_operation_duration_seconds',
                'Duration of MCP operations',
                ['operation_type', 'operation', 'status'],
                buckets=[0.01, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
                registry=self.registry
            ),
            'http_requests': Histogram(
                'mcp_http_request_duration_seconds',
                'Duration of HTTP requests',
                ['method', 'endpoint', 'status_code'],
                buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
                registry=self.registry
            ),
            'integration_calls': Histogram(
                'mcp_integration_call_duration_seconds',
                'Duration of integration calls',
                ['integration_type', 'operation', 'status'],
                buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0],
                registry=self.registry
            )
        }
        
        # Счетчики retry попыток
        self.retry_counters = Counter(
            'mcp_retry_attempts_total',
            'Total retry attempts',
            ['operation', 'attempt_number', 'success'],
            registry=self.registry
        )
        
        # Gauge для состояния circuit breaker
        self.circuit_breaker_gauge = Gauge(
            'mcp_circuit_breaker_state',
            'Circuit breaker state (0=closed, 1=half-open, 2=open)',
            ['operation'],
            registry=self.registry
        )
        
        # Gauge для активных запросов
        self.active_requests_gauge = Gauge(
            'mcp_active_requests',
            'Number of active requests',
            ['operation_type'],
            registry=self.registry
        )
        
        # Gauge для очередей
        self.queue_gauge = Gauge(
            'mcp_queue_size',
            'Size of operation queues',
            ['queue_name'],
            registry=self.registry
        )
        
        # Информационные метрики
        self.service_info = Info(
            'mcp_service_info',
            'Information about the MCP service',
            registry=self.registry
        )
        
        self._initialize_service_info()
        
    def _initialize_service_info(self):
        """Инициализация информационных метрик"""
        self.service_info.info({
            'service_name': self.service_name,
            'version': '1.0.0',
            'environment': 'production'
        })
        
    def record_error(self, error_type: str, operation: str, 
                    correlation_id: Optional[str] = None, 
                    error_details: Optional[Dict[str, Any]] = None):
        """
        Запись ошибки в метрики
        
        Args:
            error_type: Тип ошибки (validation, transport, integration, auth)
            operation: Операция, где произошла ошибка
            correlation_id: Корреляционный ID для трассировки
            error_details: Дополнительные детали ошибки
        """
        if error_type in self.error_counters:
            correlation = correlation_id or 'unknown'
            self.error_counters[error_type].labels(
                error_type=error_type,
                operation=operation,
                correlation_id=correlation
            ).inc()
            
    def record_circuit_breaker_error(self, operation: str, 
                                   correlation_id: Optional[str] = None):
        """Запись ошибки circuit breaker"""
        correlation = correlation_id or 'unknown'
        self.circuit_breaker_gauge.labels(operation=operation).set(2)  # Open state
        self.error_counters['circuit_breaker'].labels(
            operation=operation,
            correlation_id=correlation
        ).inc()
        
    def record_operation_duration(self, operation_type: str, operation: str,
                                duration: float, status: str = 'success'):
        """
        Запись времени выполнения операции
        
        Args:
            operation_type: Тип операции (tools, resources, prompts, http)
            operation: Конкретная операция
            duration: Время выполнения в секундах
            status: Статус операции (success, error, timeout)
        """
        self.duration_histograms['mcp_operations'].labels(
            operation_type=operation_type,
            operation=operation,
            status=status
        ).observe(duration)
        
    def record_http_request(self, method: str, endpoint: str, 
                          duration: float, status_code: int):
        """Запись HTTP запроса"""
        self.duration_histograms['http_requests'].labels(
            method=method,
            endpoint=endpoint,
            status_code=str(status_code)
        ).observe(duration)
        
    def record_integration_call(self, integration_type: str, operation: str,
                              duration: float, status: str):
        """Запись вызова интеграции"""
        self.duration_histograms['integration_calls'].labels(
            integration_type=integration_type,
            operation=operation,
            status=status
        ).observe(duration)
        
    def record_retry_attempt(self, operation: str, attempt_number: int, success: bool):
        """Запись попытки retry"""
        self.retry_counters.labels(
            operation=operation,
            attempt_number=str(attempt_number),
            success=str(success)
        ).inc()
        
    def update_circuit_breaker_state(self, operation: str, state: str):
        """
        Обновление состояния circuit breaker
        
        Args:
            operation: Операция
            state: Состояние (closed, half-open, open)
        """
        state_map = {'closed': 0, 'half-open': 1, 'open': 2}
        self.circuit_breaker_gauge.labels(operation=operation).set(state_map.get(state, 0))
        
    def update_active_requests(self, operation_type: str, count: int):
        """Обновление количества активных запросов"""
        self.active_requests_gauge.labels(operation_type=operation_type).set(count)
        
    def update_queue_size(self, queue_name: str, size: int):
        """Обновление размера очереди"""
        self.queue_gauge.labels(queue_name=queue_name).set(size)
        
    def timing(self, operation_type: str, operation: str):
        """
        Декоратор для автоматического измерения времени выполнения
        
        Args:
            operation_type: Тип операции
            operation: Название операции
        """
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()
                status = 'success'
                
                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    status = 'error'
                    # Запись ошибки если есть error_type
                    error_type = getattr(e, 'error_type', 'unknown')
                    correlation_id = getattr(e, 'correlation_id', None)
                    self.record_error(error_type, operation, correlation_id)
                    raise
                finally:
                    duration = time.time() - start_time
                    self.record_operation_duration(operation_type, operation, duration, status)
                    
            return wrapper
        return decorator
        
    def get_metrics(self) -> str:
        """
        Получение всех метрик в формате Prometheus
        
        Returns:
            Строка с метриками в формате Prometheus
        """
        return generate_latest(self.registry).decode('utf-8')
        
    def get_metrics_content_type(self) -> str:
        """Получение content type для метрик"""
        return CONTENT_TYPE_LATEST


# Глобальный экземпляр метрик
_global_metrics: Optional[PrometheusMetrics] = None


def get_metrics() -> PrometheusMetrics:
    """Получение глобального экземпляра метрик"""
    global _global_metrics
    if _global_metrics is None:
        _global_metrics = PrometheusMetrics()
    return _global_metrics


def init_metrics(service_name: str = "mcp_server", 
                registry: Optional[CollectorRegistry] = None) -> PrometheusMetrics:
    """
    Инициализация глобальных метрик
    
    Args:
        service_name: Имя сервиса
        registry: Пользовательский registry
        
    Returns:
        Экземпляр PrometheusMetrics
    """
    global _global_metrics
    _global_metrics = PrometheusMetrics(service_name=service_name, registry=registry)
    return _global_metrics


# Декораторы для удобного использования
def monitor_mcp_operation(operation_type: str, operation: str):
    """Декоратор для мониторинга MCP операций"""
    return get_metrics().timing(operation_type, operation)


def monitor_http_request(method: str, endpoint: str):
    """Декоратор для мониторинга HTTP запросов"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            metrics = get_metrics()
            
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                metrics.record_http_request(method, endpoint, duration, 200)
                return result
            except Exception as e:
                duration = time.time() - start_time
                status_code = getattr(e, 'status_code', 500)
                metrics.record_http_request(method, endpoint, duration, status_code)
                raise
                
        return wrapper
    return decorator


def record_error(error_type: str, operation: str, 
                correlation_id: Optional[str] = None):
    """Функция для записи ошибки"""
    get_metrics().record_error(error_type, operation, correlation_id)


def record_circuit_breaker_state(operation: str, state: str):
    """Функция для обновления состояния circuit breaker"""
    get_metrics().update_circuit_breaker_state(operation, state)