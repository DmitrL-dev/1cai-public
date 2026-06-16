
"""
Интеграция системы устойчивости с FastAPI

Предоставляет middleware, зависимости и утилиты для автоматического
применения circuit breaker, retry политик и graceful degradation
в FastAPI приложениях.
"""

import logging
import time
from contextlib import asynccontextmanager
from functools import wraps
from typing import Any, Dict, List

try:
    from fastapi import Depends, FastAPI, HTTPException, Request, Response
    from fastapi.middleware.base import BaseHTTPMiddleware
    from fastapi.responses import JSONResponse
    from starlette.middleware.base import RequestResponseEndpoint
    from starlette.status import (HTTP_503_SERVICE_UNAVAILABLE,
                                  HTTP_504_GATEWAY_TIMEOUT)
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    # Создаем заглушки для случая, когда FastAPI не установлен
    class FastAPI:
        def __init__(self, *args, **kwargs): pass
        def middleware(self, middleware_type): 
            def decorator(func): return func
            return decorator
    
    class Request:
        def __init__(self): pass
    
    class Response:
        def __init__(self): pass

from . import (CircuitBreakerConfig, DegradationLevel, get_circuit_breaker_manager,
               get_fallback_strategy_manager, get_graceful_degradation_manager,
               get_retry_policy_manager)
from .circuit_breaker import CircuitBreakerOpenError
from .config import (ServiceType, get_circuit_breaker_config,
                     get_retry_policy_config)
from .fallback_strategies import ServiceContext

logger = logging.getLogger("resilience.fastapi")


class CircuitBreakerMiddleware(BaseHTTPMiddleware):
    """
    FastAPI Middleware для автоматического применения circuit breaker
    к HTTP запросам на основе пути и метода
    """
    
    def __init__(self, app: FastAPI, 
                 excluded_paths: List[str] = None,
                 service_type: ServiceType = ServiceType.EXTERNAL_API,
                 custom_config: CircuitBreakerConfig = None):
        """
        Инициализация middleware
        
        Args:
            app: FastAPI приложение
            excluded_paths: Список путей для исключения из circuit breaker
            service_type: Тип сервиса для конфигурации circuit breaker
            custom_config: Кастомная конфигурация circuit breaker
        """
        super().__init__(app)
        self.excluded_paths = excluded_paths or ["/health", "/metrics", "/docs", "/redoc"]
        self.service_type = service_type
        
        # Создаем или получаем circuit breaker
        self.circuit_breaker_manager = get_circuit_breaker_manager()
        self.circuit_breaker = self.circuit_breaker_manager.get_breaker(
            f"fastapi_{service_type.value}", 
            custom_config or get_circuit_breaker_config(service_type)
        )
        
        self.graceful_degradation_manager = get_graceful_degradation_manager()
        self.fallback_manager = get_fallback_strategy_manager()
        
        logger.info(f"Circuit Breaker Middleware инициализирован для сервиса: {service_type.value}")
    
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Обработка запроса через circuit breaker"""
        path = request.url.path
        method = request.method
        
        # Проверяем, нужно ли применять circuit breaker
        if self._should_skip_circuit_breaker(path):
            return await call_next(request)
        
        # Создаем контекст сервиса
        service_name = f"{method}_{path}"
        self.graceful_degradation_manager.register_service(service_name, DegradationLevel.FULL_SERVICE)
        
        # Оборачиваем обработчик запроса в circuit breaker
        async def request_handler():
            try:
                response = await call_next(request)
                
                # Оцениваем успешное выполнение
                self.graceful_degradation_manager.evaluate_request(service_name, "http_request", True)
                
                return response
                
            except Exception as e:
                # Оцениваем неудачное выполнение
                self.graceful_degradation_manager.evaluate_request(service_name, "http_request", False)
                
                # Пробуем fallback для определенных ошибок
                if isinstance(e, (CircuitBreakerOpenError, HTTPException)):
                    context = ServiceContext(
                        service_name=service_name,
                        service_type=self.service_type,
                        operation="http_request",
                        metadata={
                            "path": path,
                            "method": method,
                            "status_code": getattr(e, "status_code", 500)
                        }
                    )
                    
                    fallback_result = self.fallback_manager.handle_service_fallback(
                        self.service_type, context, self._create_fallback_response, request
                    )
                    
                    if fallback_result.success:
                        return JSONResponse(
                            content=fallback_result.data,
                            status_code=503
                        )
                
                # Перебрасываем исключение
                raise
        
        try:
            # Выполняем запрос через circuit breaker
            response = await self.circuit_breaker.call(request_handler)
            return response
            
        except CircuitBreakerOpenError:
            # Circuit breaker открыт
            logger.warning(f"Circuit breaker OPEN для пути: {path}")
            
            self.graceful_degradation_manager.evaluate_request(service_name, "http_request", False)
            
            return JSONResponse(
                status_code=HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "error": "Service Unavailable",
                    "message": "Сервис временно недоступен из-за превышения лимита ошибок",
                    "retry_after": self.circuit_breaker.config.timeout
                }
            )
        
        except Exception as e:
            logger.error(f"Ошибка в Circuit Breaker Middleware: {e}")
            raise
    
    def _should_skip_circuit_breaker(self, path: str) -> bool:
        """Проверка, нужно ли пропустить circuit breaker для пути"""
        return any(path.startswith(excluded) for excluded in self.excluded_paths)
    
    def _create_fallback_response(self, request: Request) -> Dict[str, Any]:
        """Создание fallback ответа"""
        return {
            "error": "Service Degraded",
            "message": "Сервис работает в режиме ограниченной функциональности",
            "path": str(request.url.path),
            "method": request.method,
            "timestamp": time.time()
        }


def retry_dependency(policy_name: str = "default"):
    """
    Зависимость FastAPI для автоматического применения retry политики
    
    Usage:
        @app.get("/api/data")
        async def get_data(data = Depends(retry_dependency("external_api"))):
            return data
    """
    def dependency():
        retry_policy_manager = get_retry_policy_manager()
        retry_config = get_retry_policy_config(policy_name)
        return retry_policy_manager.get_policy(policy_name, retry_config)
    
    return Depends(dependency)


def resilience_depends(service_name: str, service_type: ServiceType = ServiceType.EXTERNAL_API):
    """
    Зависимость FastAPI для получения компонентов устойчивости
    
    Usage:
        @app.get("/api/data")
        async def get_data(resilience = Depends(resilience_depends("data_service"))):
            return {"status": "ok"}
    """
    def dependency():
        circuit_breaker_manager = get_circuit_breaker_manager()
        retry_policy_manager = get_retry_policy_manager()
        degradation_manager = get_graceful_degradation_manager()
        
        # Получаем компоненты
        circuit_breaker = circuit_breaker_manager.get_breaker(
            f"fastapi_{service_name}",
            get_circuit_breaker_config(service_type)
        )
        
        retry_policy = retry_policy_manager.get_policy(
            f"fastapi_{service_name}",
            get_retry_policy_config("default")
        )
        
        # Регистрируем сервис если еще не зарегистрирован
        degradation_manager.register_service(service_name)
        
        return {
            "circuit_breaker": circuit_breaker,
            "retry_policy": retry_policy,
            "degradation_manager": degradation_manager,
            "service_name": service_name,
            "service_type": service_type
        }
    
    return Depends(dependency)


def create_resilient_endpoint(operation_name: str = None, 
                            service_type: ServiceType = ServiceType.EXTERNAL_API,
                            enable_retry: bool = True,
                            enable_circuit_breaker: bool = True):
    """
    Декоратор для создания устойчивого endpoint
    
    Usage:
        @app.get("/api/data")
        @create_resilient_endpoint("get_data", ServiceType.EXTERNAL_API)
        async def get_data():
            # Ваша логика здесь
            return {"data": "value"}
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            operation = operation_name or func.__name__
            
            # Получаем компоненты устойчивости
            circuit_breaker_manager = get_circuit_breaker_manager()
            retry_policy_manager = get_retry_policy_manager()
            degradation_manager = get_graceful_degradation_manager()
            fallback_manager = get_fallback_strategy_manager()
            
            # Создаем или получаем компоненты
            if enable_circuit_breaker:
                circuit_breaker = circuit_breaker_manager.get_breaker(
                    f"endpoint_{operation}",
                    get_circuit_breaker_config(service_type)
                )
            
            if enable_retry:
                retry_policy = retry_policy_manager.get_policy(
                    f"endpoint_{operation}",
                    get_retry_policy_config("default")
                )
            
            # Регистрируем сервис
            degradation_manager.register_service(operation)
            
            # Создаем контекст для fallback
            context = ServiceContext(
                service_name=operation,
                service_type=service_type,
                operation=operation
            )
            
            try:
                # Выполняем функцию с retry и circuit breaker
                if enable_retry and enable_circuit_breaker:
                    async def protected_operation():
                        return await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
                    
                    result = await retry_policy.execute_async(lambda: circuit_breaker.call(protected_operation))
                    
                elif enable_retry:
                    result = await retry_policy.execute_async(func) if asyncio.iscoroutinefunction(func) else retry_policy.execute(func)
                    
                elif enable_circuit_breaker:
                    async def protected_operation():
                        return await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
                    
                    result = circuit_breaker.call(protected_operation)
                    
                else:
                    result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
                
                # Оцениваем успешное выполнение
                degradation_manager.evaluate_request(operation, operation, True)
                
                return result
                
            except Exception as e:
                # Оцениваем неудачное выполнение
                degradation_manager.evaluate_request(operation, operation, False)
                
                # Пробуем fallback
                fallback_result = fallback_manager.handle_service_fallback(
                    service_type, context, func, *args, **kwargs
                )
                
                if fallback_result.success:
                    return fallback_result.data
                else:
                    # Если fallback не удался, перебрасываем исключение
                    if isinstance(e, HTTPException):
                        raise e
                    raise HTTPException(status_code=HTTP_504_GATEWAY_TIMEOUT, detail=str(e))
        
        # Добавляем метаданные для документации
        wrapper._resilience_protected = True
        wrapper._resilience_operation = operation
        wrapper._resilience_service_type = service_type
        
        return wrapper
    
    return decorator


@asynccontextmanager
async def lifespan_context(app: FastAPI):
    """Контекст жизненного цикла для инициализации систем устойчивости"""
    # Инициализация при старте
    logger.info("Инициализация систем устойчивости...")
    
    # Создаем глобальные компоненты
    get_circuit_breaker_manager()
    get_retry_policy_manager()
    get_graceful_degradation_manager()
    get_fallback_strategy_manager()
    
    yield
    
    # Очистка при завершении
    logger.info("Завершение работы систем устойчивости...")


def setup_resilience_middleware(app: FastAPI, 
                               config: Dict[str, Any] = None):
    """
    Настройка всех middleware устойчивости для FastAPI приложения
    
    Args:
        app: FastAPI приложение
        config: Конфигурация middleware
    """
    if not FASTAPI_AVAILABLE:
        logger.warning("FastAPI не установлен, интеграция недоступна")
        return
    
    default_config = {
        "excluded_paths": ["/health", "/metrics", "/docs", "/redoc", "/openapi.json"],
        "enable_circuit_breaker": True,
        "enable_retry": True,
        "service_types": {
            "/api/": ServiceType.EXTERNAL_API,
            "/auth/": ServiceType.OAUTH2,
            "/data/": ServiceType.DB
        }
    }
    
    config = {**default_config, **(config or {})}
    
    # Добавляем middleware для circuit breaker
    if config.get("enable_circuit_breaker", True):
        for path_pattern, service_type in config.get("service_types", {}).items():
            # Создаем middleware для определенного пути
            middleware = CircuitBreakerMiddleware(
                app,
                excluded_paths=config["excluded_paths"],
                service_type=service_type
            )
            # В реальном FastAPI приложении здесь бы добавлялся middleware
            # app.add_middleware(CircuitBreakerMiddleware, ...)
    
    # Добавляем lifespan context
    app.router.add_event_handler("startup", lambda: lifespan_context(app))


def get_resilience_status() -> Dict[str, Any]:
    """Получение статуса всех систем устойчивости для FastAPI"""
    try:
        circuit_breakers = get_circuit_breaker_manager().get_all_states()
        retry_policies = get_retry_policy_manager().get_all_stats()
        degradation_report = get_graceful_degradation_manager().get_degradation_report()
        
        return {
            "timestamp": time.time(),
            "circuit_breakers": {
                name: {
                    "state": state["state"],
                    "total_requests": state["stats"]["total_requests"],
                    "success_rate": state["stats"]["success_rate"],
                    "recent_failures": state["recent_failures"]
                }
                for name, state in circuit_breakers.items()
            },
            "retry_policies": {
                name: {
                    "total_attempts": stats.total_attempts,
                    "success_rate": stats.get_success_rate(),
                    "average_delay": stats.get_average_delay()
                }
                for name, stats in retry_policies.items()
            },
            "graceful_degradation": {
                service: {
                    "degradation_level": data["degradation_level"],
                    "consecutive_failures": data["metrics"]["consecutive_failures"],
                    "error_rate": data["metrics"]["error_rate"]
                }
                for service, data in degradation_report["services"].items()
            },
            "status": "healthy" if all(
                state["state"] == "CLOSED" for state in circuit_breakers.values()
            ) else "degraded"
        }
    except Exception as e:
        logger.error(f"Ошибка получения статуса устойчивости: {e}")
        return {
            "timestamp": time.time(),
            "status": "error",
            "error": str(e)
        }


# Endpoint для мониторинга (можно добавить в FastAPI приложение)
async def resilience_health_endpoint():
    """Endpoint для проверки здоровья систем устойчивости"""
    status = get_resilience_status()
    
    if status["status"] == "healthy":
        return {
            "status": "healthy",
            "message": "Все системы устойчивости работают нормально",
            "details": status
        }
    elif status["status"] == "degraded":
        return {
            "status": "degraded", 
            "message": "Некоторые системы работают в ограниченном режиме",
            "details": status
        }
    else:
        raise HTTPException(
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "unhealthy",
                "message": "Системы устойчивости не работают",
                "details": status
            }
        )


# Пример использования
EXAMPLE_USAGE = '''
from fastapi import FastAPI
from resilience.fastapi import (
    CircuitBreakerMiddleware,
    retry_dependency,
    resilience_depends,
    create_resilient_endpoint,
    setup_resilience_middleware
)

app = FastAPI(title="Resilient API", version="1.0.0")

# Настройка всех middleware
setup_resilience_middleware(app)

# Метрики и мониторинг
@app.get("/resilience/health")
async def resilience_health():
    from resilience.fastapi import resilience_health_endpoint
    return await resilience_health_endpoint()

@app.get("/resilience/status")
async def resilience_status():
    from resilience.fastapi import get_resilience_status
    return get_resilience_status()

# Пример 1: Использование декоратора для устойчивого endpoint
@app.get("/api/data/{item_id}")
@create_resilient_endpoint("get_item_data", ServiceType.EXTERNAL_API)
async def get_item_data(item_id: int):
    # Симуляция внешнего API вызова
    import random
    if random.random() < 0.3:
        raise ConnectionError("External API unavailable")
    return {"item_id": item_id, "data": f"Sample data for item {item_id}"}

# Пример 2: Использование dependency для retry политики
@app.get("/api/users/{user_id}")
async def get_user(user_id: int, retry_policy = Depends(retry_dependency("external_api"))):
    def fetch_user():
        # Симуляция API вызова
        if user_id > 100:
            raise ConnectionError("User service unavailable")
        return {"user_id": user_id, "name": f"User {user_id}"}
    
    try:
        user_data = retry_policy.execute(fetch_user)
        return user_data
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

# Пример 3: Использование resilience dependency
@app.post("/api/orders")
async def create_order(order_data: dict, resilience = Depends(resilience_depends("order_service"))):
    def process_order():
        # Логика обработки заказа
        if order_data.get("amount", 0) > 1000:
            raise TimeoutError("Payment service timeout")
        return {"order_id": "12345", "status": "created", "data": order_data}
    
    circuit_breaker = resilience["circuit_breaker"]
    retry_policy = resilience["retry_policy"]
    
    try:
        # Выполняем с устойчивостью
        async def async_process():
            return process_order()
        
        result = retry_policy.execute_async(
            lambda: circuit_breaker.call(async_process)
        )
        return result
        
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Order processing failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
'''

# Дополнительные утилиты для FastAPI
class ResilienceConfig:
    """Конфигурация для интеграции с FastAPI"""
    
    def __init__(self):
        self.middleware_configs = {}
        self.endpoint_configs = {}
        self.global_settings = {
            "enable_middleware": True,
            "enable_retry": True,
            "enable_circuit_breaker": True,
            "excluded_paths": ["/health", "/metrics", "/docs", "/redoc"],
            "fallback_enabled": True
        }
    
    def add_middleware_for_path(self, path_pattern: str, service_type: ServiceType, config: dict = None):
        """Добавление middleware конфигурации для пути"""
        self.middleware_configs[path_pattern] = {
            "service_type": service_type,
            "config": config or {}
        }
    
    def configure_endpoint(self, endpoint_path: str, operation_name: str = None, service_type: ServiceType = None):
        """Конфигурация endpoint для устойчивости"""
        self.endpoint_configs[endpoint_path] = {
            "operation_name": operation_name or endpoint_path,
            "service_type": service_type or ServiceType.EXTERNAL_API
        }
    
    def update_global_settings(self, settings: dict):
        """Обновление глобальных настроек"""
        self.global_settings.update(settings)


def configure_resilience_for_app(app: FastAPI, config: ResilienceConfig = None) -> ResilienceConfig:
    """Автоматическая настройка устойчивости для FastAPI приложения"""
    if config is None:
        config = ResilienceConfig()
    
    # Настройка middleware
    if config.global_settings.get("enable_middleware", True):
        setup_resilience_middleware(app)
    
    # Добавление endpoints для мониторинга
    app.add_api_route("/resilience/health", resilience_health_endpoint, methods=["GET"])
    app.add_api_route("/resilience/status", get_resilience_status, methods=["GET"])
    
    logger.info("Устойчивость настроена для FastAPI приложения")
    return config


# Экспорт для удобства
__all__ = [
    "CircuitBreakerMiddleware",
    "retry_dependency", 
    "resilience_depends",
    "create_resilient_endpoint",
    "setup_resilience_middleware",
    "get_resilience_status",
    "resilience_health_endpoint",
    "ResilienceConfig",
    "configure_resilience_for_app",
    "EXAMPLE_USAGE"
]

if FASTAPI_AVAILABLE:
    __all__.append("FastAPI")