
"""
Система устойчивости для Python серверов

Предоставляет комплексные возможности для обеспечения надежности и устойчивости
серверных приложений через circuit breaker, graceful degradation, retry политики
и fallback стратегии.

Модули:
- circuit_breaker: Реализация паттерна circuit breaker
- graceful_degradation: Управление уровнями деградации сервисов
- retry_policy: Политики ретраев с exponential backoff
- fallback_strategies: Стратегии fallback для критичных сервисов
- config: Конфигурация системы устойчивости

Пример использования:
    from resilience import CircuitBreaker, RetryPolicy, GracefulDegradationManager
    
    # Создание circuit breaker
    breaker = CircuitBreaker("api_service", CircuitBreakerConfig())
    
    # Вызов функции с circuit breaker
    result = breaker.call(lambda: requests.get("https://api.example.com", timeout=10))
    
    # Retry политика
    retry_policy = RetryPolicy(RetryPolicyConfig())
    result = retry_policy.execute(lambda: some_api_call())
    
    # Graceful degradation
    degradation_manager = GracefulDegradationManager(GracefulDegradationConfig())
    level = degradation_manager.evaluate_request("service", "operation", success=False)

Версия: 1.0.0
"""

# Импорт основных классов
from .circuit_breaker import (CircuitBreaker, CircuitBreakerManager,
                              CircuitBreakerOpenError, CircuitBreakerState,
                              CircuitBreakerStats)
from .config import DEFAULT_CONFIG, CircuitBreakerConfig
from .config import DegradationLevel as ConfigDegradationLevel
from .config import (GracefulDegradationConfig, ResilienceConfig,
                     RetryPolicyConfig, ServiceType,
                     get_circuit_breaker_config, get_config,
                     get_retry_policy_config, update_config)
from .fallback_strategies import (AdminNotificationStrategy, FallbackResult,
                                  FallbackStrategy, FallbackStrategyManager,
                                  MCPClientFallbackStrategy,
                                  OAuth2FallbackStrategy, OneCFallbackStrategy,
                                  ServiceContext)
from .graceful_degradation import (DefaultFallbackHandler, DegradationLevel,
                                   FallbackData, GracefulDegradationManager,
                                   ServiceMetrics)
from .retry_policy import (RetryAttempt, RetryPolicy, RetryPolicyConfig,
                           RetryPolicyManager, RetryResult, RetryStats, retry,
                           with_exponential_backoff, with_fixed_delay,
                           with_linear_backoff)

# Версия пакета
__version__ = "1.0.0"
__author__ = "System Resilience Team"

# Публичное API
__all__ = [
    # Circuit Breaker
    "CircuitBreaker",
    "CircuitBreakerState", 
    "CircuitBreakerStats",
    "CircuitBreakerManager",
    "CircuitBreakerOpenError",
    
    # Graceful Degradation
    "GracefulDegradationManager",
    "ServiceMetrics",
    "FallbackData", 
    "DefaultFallbackHandler",
    "DegradationLevel",
    
    # Retry Policy
    "RetryPolicy",
    "RetryPolicyConfig",
    "RetryAttempt",
    "RetryStats",
    "RetryPolicyManager", 
    "RetryResult",
    "retry",
    "with_exponential_backoff",
    "with_linear_backoff",
    "with_fixed_delay",
    
    # Fallback Strategies
    "FallbackStrategy",
    "ServiceContext",
    "FallbackResult",
    "OneCFallbackStrategy",
    "OAuth2FallbackStrategy",
    "MCPClientFallbackStrategy",
    "AdminNotificationStrategy",
    "FallbackStrategyManager",
    
    # Configuration
    "ServiceType",
    "ConfigDegradationLevel",
    "CircuitBreakerConfig",
    "RetryPolicyConfig", 
    "GracefulDegradationConfig",
    "ResilienceConfig",
    "DEFAULT_CONFIG",
    "get_config",
    "get_circuit_breaker_config",
    "get_retry_policy_config",
    "update_config"
]

# Интеграция с FastAPI (опционально)
try:
    from .fastapi_integration import (CircuitBreakerMiddleware,
                                      get_resilience_status,
                                      resilience_depends, retry_dependency)
    __all__.extend([
        "CircuitBreakerMiddleware",
        "retry_dependency", 
        "resilience_depends",
        "get_resilience_status"
    ])
except ImportError:
    # FastAPI не установлен, пропускаем интеграцию
    pass

# Глобальные экземпляры менеджеров
_circuit_breaker_manager = None
_retry_policy_manager = None
_graceful_degradation_manager = None
_fallback_strategy_manager = None


def get_circuit_breaker_manager() -> CircuitBreakerManager:
    """Получение глобального менеджера circuit breaker'ов"""
    global _circuit_breaker_manager
    if _circuit_breaker_manager is None:
        _circuit_breaker_manager = CircuitBreakerManager()
    return _circuit_breaker_manager


def get_retry_policy_manager() -> RetryPolicyManager:
    """Получение глобального менеджера retry политик"""
    global _retry_policy_manager
    if _retry_policy_manager is None:
        _retry_policy_manager = RetryPolicyManager()
    return _retry_policy_manager


def get_graceful_degradation_manager() -> GracefulDegradationManager:
    """Получение глобального менеджера graceful degradation"""
    global _graceful_degradation_manager
    if _graceful_degradation_manager is None:
        config = get_config().degradation
        _graceful_degradation_manager = GracefulDegradationManager(config)
    return _graceful_degradation_manager


def get_fallback_strategy_manager() -> FallbackStrategyManager:
    """Получение глобального менеджера fallback стратегий"""
    global _fallback_strategy_manager
    if _fallback_strategy_manager is None:
        degradation_manager = get_graceful_degradation_manager()
        _fallback_strategy_manager = FallbackStrategyManager(degradation_manager)
    return _fallback_strategy_manager


# Функции для удобного создания компонентов
def create_circuit_breaker(name: str, service_type: ServiceType = None) -> CircuitBreaker:
    """Создание circuit breaker с конфигурацией по умолчанию"""
    if service_type:
        config = get_circuit_breaker_config(service_type)
    else:
        config = CircuitBreakerConfig()
    
    manager = get_circuit_breaker_manager()
    return manager.get_breaker(name, config)


def create_retry_policy(name: str, policy_type: str = "default") -> RetryPolicy:
    """Создание retry политики с конфигурацией по умолчанию"""
    config = get_retry_policy_config(policy_type)
    manager = get_retry_policy_manager()
    return manager.get_policy(name, config)


def create_resilient_operation(service_name: str, service_type: ServiceType):
    """
    Создание устойчивой операции с всеми компонентами устойчивости
    
    Args:
        service_name: Имя сервиса
        service_type: Тип сервиса
        
    Returns:
        Функция-обертка с полной устойчивостью
    """
    from functools import wraps
    
    def resilient_decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Создаем компоненты устойчивости
            circuit_breaker = create_circuit_breaker(f"{service_name}_cb", service_type)
            retry_policy = create_retry_policy(f"{service_name}_retry")
            degradation_manager = get_graceful_degradation_manager()
            fallback_manager = get_fallback_strategy_manager()
            
            # Регистрируем сервис
            degradation_manager.register_service(service_name)
            
            try:
                # Выполняем через circuit breaker с retry
                result = retry_policy.execute(
                    lambda: circuit_breaker.call(func, *args, **kwargs)
                )
                
                # Оцениваем успешное выполнение
                degradation_manager.evaluate_request(service_name, func.__name__, True)
                
                return result
                
            except Exception as e:
                # Оцениваем неудачное выполнение
                degradation_manager.evaluate_request(service_name, func.__name__, False)
                
                # Пробуем fallback
                context = ServiceContext(
                    service_name=service_name,
                    service_type=service_type,
                    operation=func.__name__
                )
                
                fallback_result = fallback_manager.handle_service_fallback(
                    service_type, context, func, *args, **kwargs
                )
                
                if fallback_result.success:
                    return fallback_result.data
                else:
                    raise e
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Асинхронная версия
            circuit_breaker = create_circuit_breaker(f"{service_name}_cb", service_type)
            retry_policy = create_retry_policy(f"{service_name}_retry")
            degradation_manager = get_graceful_degradation_manager()
            fallback_manager = get_fallback_strategy_manager()
            
            degradation_manager.register_service(service_name)
            
            try:
                async def async_operation():
                    result = await func(*args, **kwargs)
                    return result
                
                result = await retry_policy.execute_async(
                    lambda: circuit_breaker.call(async_operation)
                )
                
                degradation_manager.evaluate_request(service_name, func.__name__, True)
                return result
                
            except Exception as e:
                degradation_manager.evaluate_request(service_name, func.__name__, False)
                
                context = ServiceContext(
                    service_name=service_name,
                    service_type=service_type,
                    operation=func.__name__
                )
                
                fallback_result = fallback_manager.handle_service_fallback(
                    service_type, context, func, *args, **kwargs
                )
                
                if fallback_result.success:
                    return fallback_result.data
                else:
                    raise e
        
        # Возвращаем подходящую версию
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return wrapper
    
    return resilient_decorator


# Функции для мониторинга и отчетности
def get_resilience_status() -> dict:
    """Получение статуса всей системы устойчивости"""
    return {
        "circuit_breakers": get_circuit_breaker_manager().get_all_states(),
        "retry_policies": get_retry_policy_manager().get_all_stats(),
        "graceful_degradation": get_graceful_degradation_manager().get_degradation_report(),
        "timestamp": time.time() if 'time' in globals() else 0
    }


def reset_all_resilience_systems():
    """Сброс всех систем устойчивости"""
    get_circuit_breaker_manager().reset_all()
    get_retry_policy_manager().reset_all_stats()
    get_graceful_degradation_manager().clear_all_data()


# Инициализация логгера при импорте
import logging

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

logger.info("Система устойчивости инициализирована")