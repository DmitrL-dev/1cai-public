
"""
Основное приложение FastAPI для 1С сервера с интеграцией API администрирования кэша

Демонстрирует:
- Интеграцию API администрирования кэша
- Middleware для сбора метрик
- Аутентификацию для административных операций
- Документацию OpenAPI
"""

import logging
import os

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Импорт API администрирования кэша
from api import (MemoryCache, cache_admin_router, cache_metrics,
                 cache_middleware)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Создание FastAPI приложения
app = FastAPI(
    title="1С Сервер API",
    description="API для 1С сервера с администрированием кэша",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# CORS middleware
origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Кэш для бизнес-данных
business_cache = MemoryCache("business_data")
session_cache = MemoryCache("sessions")

# Middleware для кэша (должен быть добавлен после других middleware)
@app.middleware("http")
async def cache_middleware_wrapper(request: Request, call_next):
    """Обертка для middleware кэша с обработкой ошибок"""
    try:
        return await cache_middleware(request, call_next)
    except Exception as e:
        logger.error(f"Ошибка в cache middleware: {e}")
        return await call_next(request)

# Базовая информация о системе
@app.get("/")
async def root():
    """Корневой endpoint"""
    return {
        "service": "1С Сервер API",
        "version": "1.0.0",
        "status": "running",
        "caches": list(business_cache.get_stats().keys())
    }

# Endpoint для получения данных (с кэшированием)
@app.get("/data/{data_id}")
async def get_data(data_id: str):
    """Получить данные с кэшированием"""
    # Проверяем кэш
    cached_data = business_cache.get(data_id)
    if cached_data:
        return {
            "data_id": data_id,
            "data": cached_data,
            "from_cache": True
        }
    
    # Симуляция получения данных (в реальности - из БД или внешнего API)
    import time
    time.sleep(0.01)  # Симуляция задержки
    
    data = {
        "id": data_id,
        "name": f"Данные {data_id}",
        "value": f"Значение {data_id}",
        "timestamp": "2025-10-29T19:56:35"
    }
    
    # Кэшируем результат
    business_cache.set(data_id, data, ttl=300)  # TTL 5 минут
    
    return {
        "data_id": data_id,
        "data": data,
        "from_cache": False
    }

# Endpoint для очистки кэша данных
@app.delete("/data/clear")
async def clear_business_cache():
    """Очистить кэш бизнес-данных"""
    business_cache.clear()
    return {"status": "cleared", "cache": "business_data"}

# Endpoint для мониторинга системы
@app.get("/health")
async def health_check():
    """Базовая проверка здоровья системы"""
    return {
        "status": "healthy",
        "timestamp": "2025-10-29T19:56:35",
        "caches": {
            "business_cache": business_cache.get_stats(),
            "session_cache": session_cache.get_stats(),
            "metrics": {
                "hit_rate": cache_metrics.hit_rate,
                "total_requests": cache_metrics.hit_count + cache_metrics.miss_count
            }
        }
    }

# Подключение API администрирования кэша
app.include_router(cache_admin_router)

# Middleware для логирования всех запросов
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Логирование всех запросов"""
    start_time = time.time()
    
    response = await call_next(request)
    
    process_time = time.time() - start_time
    logger.info(
        f"Запрос: {request.method} {request.url.path} "
        f"- Статус: {response.status_code} "
        f"- Время: {process_time:.3f}s"
    )
    
    response.headers["X-Process-Time"] = str(process_time)
    return response

# Обработчик ошибок
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Глобальный обработчик ошибок"""
    logger.error(f"Необработанная ошибка: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Внутренняя ошибка сервера",
            "message": str(exc) if app.debug else "Обратитесь к администратору"
        }
    )

# Точка входа для запуска
if __name__ == "__main__":
    # Запуск сервера для разработки
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

# Экспорт для использования в других модулях
__all__ = ["app"]
