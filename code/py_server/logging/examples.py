
"""
Примеры использования системы структурированного логирования.

Демонстрация основных возможностей:
- Настройка логирования
- HTTP middleware
- Корреляционные ID
- Маскирование данных
- Интеграция с мониторингом
"""

import asyncio
import os
import time
from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

# Импорт компонентов системы логирования
from .config import LoggingConfig, setup_logging
from .formatter import PerformanceFormatter
from .handlers import (create_application_logger, create_business_logger,
                       create_http_logger)
from .middleware import (LoggingMiddleware, log_execution_time,
                         with_correlation_id, with_user_id)
from .sanitizers import (sanitize_request_data, sanitize_response_data,
                         sanitize_user_data)

# Инициализация системы логирования
setup_logging()

# Создание специализированных логгеров
app_logger = create_application_logger()
http_logger = create_http_logger()
business_logger = create_business_logger()


# FastAPI приложение с middleware
app = FastAPI(title="Logging System Demo")

# Добавление CORS middleware
origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Добавление logging middleware
app.add_middleware(LoggingMiddleware)


# Примеры функций с декораторами логирования
@log_execution_time("user_authentication")
@with_user_id("demo_user")
async def authenticate_user(username: str, password: str) -> Dict[str, Any]:
    """Пример функции с автоматическим логированием времени выполнения"""
    
    # Имитация задержки
    await asyncio.sleep(0.1)
    
    if username == "admin" and password == "secret":
        app_logger.info(
            "User authentication successful",
            user_info={
                "username": username,
                "role": "admin",
                "permissions": ["read", "write", "admin"]
            }
        )
        return {"success": True, "token": "demo_token_123"}
    else:
        app_logger.warning(
            "User authentication failed",
            user_info={
                "username": username,
                "attempt_count": 1
            }
        )
        return {"success": False, "error": "Invalid credentials"}


@log_execution_time("data_processing")
@with_correlation_id()
async def process_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Обработка данных с логированием"""
    
    # Имитация обработки
    await asyncio.sleep(0.05)
    
    # Логирование результата
    app_logger.info(
        "Data processing completed",
        data_size=len(str(data)),
        processing_time_ms=50,
        output_keys=list(data.keys()) if isinstance(data, dict) else None
    )
    
    return {
        "processed": True,
        "timestamp": time.time(),
        "data": data
    }


@with_user_id("system")
async def database_operation(operation: str, table: str) -> bool:
    """Пример операции с базой данных"""
    
    start_time = time.time()
    
    try:
        # Имитация операции БД
        await asyncio.sleep(0.02)
        
        duration = (time.time() - start_time) * 1000
        
        app_logger.info(
            f"Database operation: {operation} on {table}",
            operation=operation,
            table=table,
            duration_ms=duration,
            success=True
        )
        
        return True
        
    except Exception as e:
        duration = (time.time() - start_time) * 1000
        
        app_logger.error(
            f"Database operation failed: {operation} on {table}",
            operation=operation,
            table=table,
            duration_ms=duration,
            error=str(e),
            error_type="DATABASE_ERROR"
        )
        
        raise


# HTTP endpoint'ы
@app.get("/")
async def root():
    """Корневой endpoint"""
    app_logger.info(
        "Accessing root endpoint",
        user_agent="demo_client",
        source="api_call"
    )
    
    return {
        "message": "Logging System Demo",
        "endpoints": [
            "/demo/basic",
            "/demo/http",
            "/demo/business",
            "/demo/performance",
            "/demo/error"
        ]
    }


@app.get("/demo/basic")
@with_user_id("demo_user")
async def basic_logging_demo():
    """Демонстрация базового логирования"""
    
    # Различные уровни логирования
    app_logger.debug("Debug message", module="demo", function="basic_logging")
    app_logger.info("Information message", module="demo", request_count=1)
    app_logger.warning("Warning message", module="demo", performance_issue=True)
    
    try:
        # Генерация ошибки для демонстрации
        raise ValueError("Demo error for logging")
    except Exception as e:
        app_logger.error(
            "Exception caught in basic demo",
            error=str(e),
            error_type="VALUE_ERROR",
            stacktrace_demo=True
        )
    
    return {"status": "success", "demo": "basic_logging"}


@app.get("/demo/http")
async def http_logging_demo(request: Request):
    """Демонстрация HTTP логирования"""
    
    # Получение данных запроса
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    
    # Логирование HTTP запроса
    http_logger.info(
        "HTTP logging demo request",
        http_method="GET",
        target_url="/demo/http",
        http_status_code=200,
        client_ip=client_ip,
        user_agent=user_agent
    )
    
    return {"status": "success", "demo": "http_logging"}


@app.post("/demo/business")
@with_user_id("demo_user")
async def business_event_demo(data: Dict[str, Any]):
    """Демонстрация логирования бизнес-событий"""
    
    # Создание бизнес-события
    business_logger.info(
        "User action logged",
        event_type="USER_ACTION",
        action="demo_data_submission",
        user_id="demo_user",
        action_data=sanitize_user_data(data)
    )
    
    # Более сложное бизнес-событие
    app_logger.info(
        "Complex business event",
        logger_name="business",
        context={
            "event_category": "user_interaction",
            "event_subtype": "form_submission",
            "user_segment": "premium",
            "session_duration": 125.5,
            "features_used": ["logging", "business_events"]
        }
    )
    
    return {"status": "success", "demo": "business_logging"}


@app.get("/demo/performance")
@with_correlation_id()
async def performance_demo():
    """Демонстрация логирования производительности"""
    
    start_time = time.time()
    
    # Имитация ресурсоемкой операции
    await asyncio.sleep(0.2)
    
    duration = (time.time() - start_time) * 1000
    
    # Логирование производительности
    PerformanceFormatter.format_performance_log(
        operation="heavy_computation",
        duration_ms=duration,
        correlation_id=app_logger.name,
        cpu_usage_percent=45.2,
        memory_mb=128.5,
        items_processed=1000
    )
    
    return {
        "status": "success", 
        "demo": "performance_logging",
        "duration_ms": duration
    }


@app.get("/demo/error")
async def error_demo():
    """Демонстрация логирования ошибок"""
    
    try:
        # Генерация различных типов ошибок
        raise ConnectionError("Network connection failed")
        
    except ConnectionError as e:
        app_logger.error(
            "Connection error occurred",
            error=str(e),
            error_type="CONNECTION_ERROR",
            error_code="NET_001",
            retry_count=3,
            target_service="external_api",
            response_time_ms=5000
        )
        
        return {"status": "error_logged", "demo": "error_logging"}
    
    except Exception as e:
        app_logger.critical(
            "Critical system error",
            error=str(e),
            error_type="SYSTEM_ERROR",
            error_code="SYS_999",
            requires_immediate_attention=True,
            system_health="critical"
        )
        
        raise


@app.get("/demo/sanitization")
async def sanitization_demo():
    """Демонстрация маскирования данных"""
    
    # Данные с чувствительной информацией
    user_data = {
        "user_id": "12345",
        "email": "user@example.com",
        "phone": "+7 (900) 123-45-67",
        "password": "secret123",
        "api_key": "sk_live_1234567890",
        "credit_card": "4532 1234 5678 9012",
        "ssn": "123-45-6789",
        "profile": {
            "address": "123 Main St",
            "city": "New York"
        }
    }
    
    # Санитизация данных
    sanitized = sanitize_user_data(user_data, salt="demo_salt")
    
    app_logger.info(
        "User data processed",
        original_data=user_data,  # Показываем что было ДО санитизации
        sanitized_data=sanitized,  # Показываем что получилось ПОСЛЕ
        data_protection_applied=True
    )
    
    return {
        "status": "success",
        "demo": "data_sanitization",
        "sanitized": sanitized
    }


@app.post("/demo/auth")
@with_correlation_id()
async def auth_demo(request: Request, auth_data: Dict[str, Any]):
    """Демонстрация аутентификации с логированием"""
    
    correlation_id = request.headers.get("X-Correlation-ID", "unknown")
    user_agent = request.headers.get("user-agent", "unknown")
    
    # Санитизация данных аутентификации
    safe_auth_data = sanitize_request_data(auth_data)
    
    app_logger.info(
        "Authentication attempt",
        user_agent=user_agent,
        auth_data_keys=list(safe_auth_data.keys()),
        correlation_id=correlation_id
    )
    
    # Проверка учетных данных
    username = auth_data.get("username")
    password = auth_data.get("password")
    
    if username == "admin" and password == "admin123":
        # Успешная аутентификация
        app_logger.info(
            "Authentication successful",
            username=username,  # Не конфиденциально
            correlation_id=correlation_id,
            auth_method="password",
            session_duration=3600
        )
        
        response_data = {
            "token": "demo_token_12345",
            "user_id": "admin_001",
            "expires_in": 3600
        }
        
        # Санитизация ответа
        safe_response = sanitize_response_data(response_data)
        
        return safe_response
        
    else:
        # Неудачная аутентификация
        app_logger.warning(
            "Authentication failed",
            username=username,
            correlation_id=correlation_id,
            failure_reason="invalid_credentials",
            attempt_timestamp=time.time()
        )
        
        return {"error": "Invalid credentials"}, 401


# Асинхронная задача для фонового логирования
async def background_logging_task():
    """Фоновая задача для демонстрации логирования"""
    
    while True:
        try:
            # Логирование системного состояния
            app_logger.info(
                "Background task heartbeat",
                task_name="system_monitor",
                uptime_seconds=time.time(),
                active_connections=10,  # пример данных
                memory_usage_mb=150.5,
                cpu_usage_percent=25.3
            )
            
            # Имитация мониторинга производительности
            performance_data = {
                "response_time_p95": 45.2,
                "response_time_p99": 89.7,
                "throughput_rps": 150.0,
                "error_rate_percent": 0.5
            }
            
            app_logger.info(
                "Performance metrics update",
                metrics=performance_data
            )
            
            # Ожидание 30 секунд
            await asyncio.sleep(30)
            
        except Exception as e:
            app_logger.error(
                "Background task error",
                error=str(e),
                error_type="BACKGROUND_TASK_ERROR"
            )
            await asyncio.sleep(60)  # Пауза при ошибке


@app.on_event("startup")
async def startup_event():
    """Событие запуска приложения"""
    
    # Логирование запуска
    app_logger.info(
        "Application startup",
        version="1.0.0",
        environment="development",
        logging_config=LoggingConfig.to_dict(),
        startup_timestamp=time.time()
    )
    
    # Запуск фоновой задачи
    asyncio.create_task(background_logging_task())


@app.on_event("shutdown")
async def shutdown_event():
    """Событие остановки приложения"""
    
    # Логирование остановки
    app_logger.info(
        "Application shutdown",
        shutdown_timestamp=time.time(),
        graceful_shutdown=True
    )


# Функции для тестирования различных сценариев
def test_correlation_tracing():
    """Тестирование трассировки с correlation_id"""
    
    logger = create_application_logger("test_correlation")
    
    with logger.new_correlation_context(correlation_id="test-12345"):
        logger.info("Main operation started")
        
        # Вложенная операция
        logger.info(
            "Sub-operation within correlation",
            parent_operation="main_operation",
            sub_operation="data_validation"
        )
        
        logger.info("Main operation completed")


def test_error_scenarios():
    """Тестирование различных сценариев ошибок"""
    
    logger = create_application_logger("test_errors")
    
    # Валидационная ошибка
    try:
        raise ValueError("Invalid input data")
    except Exception as e:
        logger.error(
            "Validation error",
            error=str(e),
            error_type="VALIDATION_ERROR",
            error_code="VAL_001",
            field="user_input",
            validation_rules=["required", "format", "length"]
        )
    
    # Ошибка внешнего сервиса
    try:
        raise ConnectionError("External API timeout")
    except Exception as e:
        logger.error(
            "External service error",
            error=str(e),
            error_type="EXTERNAL_SERVICE_ERROR",
            error_code="EXT_001",
            service_name="payment_gateway",
            timeout_ms=5000,
            retry_count=3
        )
    
    # Системная ошибка
    try:
        raise MemoryError("Insufficient memory")
    except Exception as e:
        logger.critical(
            "Critical system error",
            error=str(e),
            error_type="SYSTEM_ERROR",
            error_code="SYS_001",
            requires_immediate_attention=True,
            memory_usage_percent=95.0
        )


def test_performance_monitoring():
    """Тестирование мониторинга производительности"""
    
    logger = create_application_logger("test_performance")
    
    # Быстрая операция
    start_time = time.time()
    time.sleep(0.01)  # 10ms
    duration = (time.time() - start_time) * 1000
    
    logger.info(
        "Fast operation completed",
        duration_ms=duration,
        operation="cache_lookup",
        cache_hit=True
    )
    
    # Медленная операция
    start_time = time.time()
    time.sleep(0.2)  # 200ms
    duration = (time.time() - start_time) * 1000
    
    logger.warning(
        "Slow operation detected",
        duration_ms=duration,
        operation="database_query",
        query_complexity="high",
        optimization_needed=True
    )


# Запуск демо
if __name__ == "__main__":
    import uvicorn
    
    print("Starting Logging System Demo...")
    print("Visit http://localhost:8000 to see the demo")
    
    uvicorn.run(
        "examples:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )