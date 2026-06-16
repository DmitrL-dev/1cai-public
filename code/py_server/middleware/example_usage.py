
"""
Пример использования middleware для обработки ошибок FastAPI

Демонстрирует:
- Базовую настройку всех middleware
- Использование correlation_id
- Обработку различных типов ошибок
- Graceful degradation
- Структурированное логирование
"""

import asyncio
import logging

# Импорт иерархии исключений
from errors.base import ServiceUnavailableError
from errors.mcp import McpToolNotFoundError
from errors.transport import TransportError
from errors.validation import ValidationError
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

# Импорт middleware
from middleware import (ErrorResponse, create_error_middleware, get_correlation_id,
                        log_with_correlation, trace_operation)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(correlation_id)s - %(message)s'
)

# Создание FastAPI приложения
app = FastAPI(
    title="1C MCP Server с Middleware",
    description="Демонстрация обработки ошибок в FastAPI",
    version="1.0.0"
)

# Настройка всех middleware
handlers = create_error_middleware(app, language="ru")


@app.get("/")
async def root():
    """Корневой эндпоинт"""
    correlation_id = get_correlation_id()
    
    log_with_correlation(
        logging.INFO,
        "Запрос к корневому эндпоинту",
        extra={"endpoint": "root"}
    )
    
    return {
        "message": "Привет от 1C MCP Server!",
        "correlation_id": correlation_id
    }


@app.get("/health")
async def health_check():
    """Проверка здоровья с кастомной логикой"""
    
    # Симулируем проверку различных сервисов
    health_status = {
        "database": {"status": "ok", "response_time_ms": 15},
        "cache": {"status": "ok", "response_time_ms": 3},
        "external_api": {"status": "warning", "response_time_ms": 2500}
    }
    
    # Определяем общий статус
    overall_status = "healthy"
    for service, status in health_status.items():
        if status["status"] == "error":
            overall_status = "unhealthy"
            break
        elif status["status"] == "warning" and overall_status == "healthy":
            overall_status = "warning"
    
    return {
        "status": overall_status,
        "services": health_status,
        "timestamp": "2025-10-29T22:12:00Z",
        "correlation_id": get_correlation_id()
    }


@app.get("/tools")
async def list_tools():
    """Список доступных MCP инструментов"""
    
    # Симулируем получение списка инструментов
    tools = [
        {"name": "get_catalog", "description": "Получить структуру справочника"},
        {"name": "execute_report", "description": "Выполнить отчет"},
        {"name": "process_document", "description": "Обработать документ"}
    ]
    
    return {
        "tools": tools,
        "total": len(tools),
        "correlation_id": get_correlation_id()
    }


@app.post("/tools/{tool_name}")
async def execute_tool(tool_name: str, request: Request):
    """Выполнение MCP инструмента с обработкой ошибок"""
    
    # Получаем параметры
    params = await request.json() if request.headers.get('content-type') else {}
    
    log_with_correlation(
        logging.INFO,
        f"Выполнение инструмента: {tool_name}",
        extra={
            "tool_name": tool_name,
            "parameters": params
        }
    )
    
    # Симулируем выполнение инструмента
    if tool_name == "nonexistent_tool":
        # Генерируем McpToolNotFoundError
        raise McpToolNotFoundError(
            tool_name=tool_name,
            available_tools=["get_catalog", "execute_report", "process_document"]
        )
    
    elif tool_name == "slow_tool":
        # Симулируем медленную операцию
        await asyncio.sleep(2)
        return {"result": "Медленная операция выполнена"}
    
    elif tool_name == "error_tool":
        # Генерируем общую ошибку
        raise ValueError("Симулированная ошибка инструмента")
    
    # Успешное выполнение
    return {
        "result": f"Инструмент {tool_name} выполнен успешно",
        "parameters": params,
        "execution_time": "0.1s"
    }


@app.get("/users/{user_id}")
async def get_user(user_id: int):
    """Получение пользователя с обработкой ошибок валидации"""
    
    if user_id <= 0:
        raise ValidationError(
            error_code="E020",
            field_name="user_id",
            field_value=user_id,
            validation_rule="positive_integer",
            user_message="ID пользователя должен быть положительным числом"
        )
    
    if user_id == 404:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    if user_id == 403:
        raise HTTPException(status_code=403, detail="Доступ запрещен")
    
    # Симуляция получения пользователя
    return {
        "user_id": user_id,
        "name": f"Пользователь {user_id}",
        "email": f"user{user_id}@example.com",
        "correlation_id": get_correlation_id()
    }


@app.post("/rpc")
async def handle_rpc(request: Request):
    """Обработка JSON-RPC запросов"""
    
    rpc_data = await request.json()
    method = rpc_data.get("method")
    params = rpc_data.get("params", {})
    
    log_with_correlation(
        logging.INFO,
        f"JSON-RPC запрос: {method}",
        extra={
            "method": method,
            "params": params
        }
    )
    
    # Симуляция различных RPC методов
    if method == "get_data":
        await asyncio.sleep(0.1)
        return {"data": "Результат RPC вызова"}
    
    elif method == "slow_operation":
        await asyncio.sleep(3)
        return {"result": "Медленная операция завершена"}
    
    elif method == "error_operation":
        raise ServiceUnavailableError("external_service", "Сервис временно недоступен")
    
    else:
        # Возвращаем ошибку в формате JSON-RPC
        return {
            "jsonrpc": "2.0",
            "id": rpc_data.get("id"),
            "error": {
                "code": -32601,
                "message": "Method not found",
                "data": {"correlation_id": get_correlation_id()}
            }
        }


@app.get("/external-service")
async def external_service():
    """Симуляция обращения к внешнему сервису"""
    
    log_with_correlation(
        logging.INFO,
        "Обращение к внешнему сервису"
    )
    
    # Симулируем ошибку внешнего сервиса
    raise TransportError(
        error_code="E048",
        url="https://external-service.example.com/api",
        method="GET",
        network_error="Connection timeout",
        recoverable=True,
        context_data={"service": "external_api"}
    )


@trace_operation("business_operation")
async def business_operation(data: dict):
    """Пример бизнес-операции с трассировкой"""
    
    log_with_correlation(
        logging.INFO,
        "Начало бизнес-операции",
        extra={"data": data}
    )
    
    # Симуляция обработки
    await asyncio.sleep(0.1)
    
    log_with_correlation(
        logging.INFO,
        "Бизнес-операция завершена успешно"
    )
    
    return {"result": "Обработка завершена", "processed_data": data}


@app.post("/business")
async def handle_business_operation(request: Request):
    """Обработка бизнес-операции"""
    
    data = await request.json()
    result = await business_operation(data)
    
    return {
        "success": True,
        "result": result,
        "correlation_id": get_correlation_id()
    }


# Обработчик для graceful degradation
@app.get("/fallback-example")
async def fallback_example():
    """Пример graceful degradation"""
    
    try:
        # Пытаемся обратиться к недоступному сервису
        await asyncio.sleep(0.1)  # Симуляция вызова
        raise ServiceUnavailableError("critical_service")
        
    except Exception as e:
        log_with_correlation(
            logging.WARNING,
            "Сервис недоступен, возвращаем fallback ответ",
            extra={"error": str(e)}
        )
        
        # Возвращаем fallback данные
        return {
            "data": {
                "status": "fallback",
                "message": "Используются резервные данные",
                "last_updated": "2025-10-29T22:12:00Z"
            },
            "fallback": True,
            "error": str(e),
            "correlation_id": get_correlation_id()
        }


# Глобальные обработчики событий
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Глобальный обработчик всех исключений"""
    
    log_with_correlation(
        logging.ERROR,
        f"Необработанное исключение: {type(exc).__name__}",
        extra={
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
            "request_path": str(request.url.path)
        }
    )
    
    # Возвращаем стандартный ответ об ошибке
    error_response = ErrorResponse.create(
        error_code="E001",
        error_type="InternalServerError",
        message_ru="Внутренняя ошибка сервера",
        message_en="Internal server error",
        http_status_code=500,
        correlation_id=get_correlation_id(),
        details={
            "exception_type": type(exc).__name__,
            "path": str(request.url.path)
        }
    )
    
    return JSONResponse(
        status_code=500,
        content=error_response.dict()
    )


if __name__ == "__main__":
    import uvicorn
    
    print("="*60)
    print("1C MCP Server с Middleware обработкой ошибок")
    print("="*60)
    print()
    print("Доступные эндпоинты:")
    print("  GET  /              - Корневой эндпоинт")
    print("  GET  /health        - Проверка здоровья")
    print("  GET  /tools         - Список инструментов")
    print("  POST /tools/{name}  - Выполнение инструмента")
    print("  GET  /users/{id}    - Получение пользователя")
    print("  POST /rpc           - JSON-RPC обработка")
    print("  GET  /external-service - Внешний сервис")
    print("  POST /business      - Бизнес-операция")
    print("  GET  /fallback-example - Graceful degradation")
    print()
    print("Примеры запросов:")
    print("  curl http://localhost:8000/")
    print("  curl http://localhost:8000/health")
    print("  curl -X POST http://localhost:8000/tools/nonexistent_tool")
    print("  curl -X GET http://localhost:8000/users/404")
    print("  curl -X POST http://localhost:8000/rpc")
    print()
    
    # Запуск сервера
    uvicorn.run(
        "example_usage:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
