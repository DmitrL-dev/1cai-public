
"""
Пример интеграции RequestTracker с FastAPI сервером
Демонстрирует:
- Инициализацию трекера запросов
- Добавление middleware для rate limiting
- Использование в endpoint'ах
- Интеграцию с OAuth2
- Мониторинг и статистику
"""

import asyncio
import logging
import os
import time
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
# Импорт компонентов request tracking
from ratelimit import (create_rate_limit_middleware, get_request_tracker,
                       init_request_tracker, request_tracking_context)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Создание FastAPI приложения
app = FastAPI(
    title="1С MCP Сервер с Rate Limiting",
    description="Пример интеграции системы учета запросов",
    version="1.0.0"
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

# Схема аутентификации
security = HTTPBearer(auto_error=False)


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Optional[str]:
    """Получить текущего пользователя из JWT (упрощенная версия)"""
    if not credentials:
        return None
    
    # В реальном приложении здесь была бы проверка JWT токена
    # Для примера используем простую логику
    token = credentials.credentials
    
    # Простая демонстрация - извлекаем user_id из токена
    if token.startswith("user_"):
        return token
    elif token == "admin":
        return "admin"
    else:
        return None


@app.on_event("startup")
async def startup_event():
    """Инициализация при запуске приложения"""
    # Конфигурация трекера запросов
    tracker_config = {
        "use_redis": False,  # В продакшене: True
        "redis_url": "redis://localhost:6379",  # В продакшене указать реальный URL
        "geoip_db_path": "/usr/share/GeoIP/GeoLite2-City.mmdb"  # Опционально
    }
    
    await init_request_tracker(tracker_config)
    logger.info("RequestTracker инициализирован")


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Добавляем middleware для rate limiting"""
    middleware = create_rate_limit_middleware()
    return await middleware(request, call_next)


@app.get("/")
async def root():
    """Корневой endpoint"""
    tracker = get_request_tracker()
    stats = tracker.get_comprehensive_stats()
    
    return {
        "service": "1С MCP Сервер",
        "version": "1.0.0",
        "rate_limiting": "enabled",
        "stats": {
            "total_requests": stats["overall"]["total_requests"],
            "blocked_rate": f"{stats['overall']['blocked_rate_percent']:.2f}%",
            "uptime": f"{stats['overall']['uptime_seconds']:.0f}s"
        }
    }


@app.get("/data/{data_id}")
async def get_data(
    data_id: str,
    request: Request,
    current_user: Optional[str] = Depends(get_current_user)
):
    """Пример endpoint с отслеживанием запросов"""
    
    # Используем контекстный менеджер для более детального трекинга
    async with request_tracking_context(request, user_id=current_user) as tracker:
        # Имитация обработки данных
        await asyncio.sleep(0.01)  # Симуляция работы с БД
        
        data = {
            "id": data_id,
            "name": f"Данные {data_id}",
            "value": f"Значение {data_id}",
            "timestamp": time.time()
        }
        
        # Дополнительная информация для трекинга
        logger.info(
            f"Получены данные {data_id} для пользователя {current_user}"
        )
        
        return data


@app.get("/tools/{tool_name}")
async def call_mcp_tool(
    tool_name: str,
    request: Request,
    current_user: Optional[str] = Depends(get_current_user)
):
    """Пример вызова MCP инструмента с отслеживанием"""
    
    async with request_tracking_context(
        request, 
        user_id=current_user, 
        tool_name=tool_name
    ) as tracker:
        
        # Имитация выполнения MCP инструмента
        await asyncio.sleep(0.05)  # Симуляция работы с 1С
        
        result = {
            "tool": tool_name,
            "result": f"Результат выполнения {tool_name}",
            "executed_at": time.time(),
            "user": current_user
        }
        
        logger.info(f"Выполнен MCP инструмент {tool_name} пользователем {current_user}")
        
        return result


@app.get("/admin/stats")
async def get_admin_stats(
    request: Request,
    current_user: Optional[str] = Depends(get_current_user)
):
    """Endpoint для получения статистики (только для админов)"""
    
    if current_user != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав доступа"
        )
    
    tracker = get_request_tracker()
    stats = tracker.get_comprehensive_stats()
    
    return {
        "timestamp": time.time(),
        "stats": stats
    }


@app.get("/admin/ip/{ip_address}")
async def get_ip_stats(
    ip_address: str,
    request: Request,
    current_user: Optional[str] = Depends(get_current_user)
):
    """Получить статистику по конкретному IP"""
    
    if current_user != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав доступа"
        )
    
    tracker = get_request_tracker()
    ip_stats = tracker.get_ip_stats(ip_address)
    
    if not ip_stats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Статистика для IP {ip_address} не найдена"
        )
    
    return {
        "ip": ip_address,
        "stats": ip_stats
    }


@app.post("/admin/block_ip/{ip_address}")
async def block_ip(
    ip_address: str,
    request: Request,
    current_user: Optional[str] = Depends(get_current_user),
    reason: str = "Ручная блокировка"
):
    """Заблокировать IP адрес"""
    
    if current_user != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав доступа"
        )
    
    tracker = get_request_tracker()
    tracker.block_ip(ip_address, reason)
    
    return {
        "message": f"IP {ip_address} заблокирован",
        "reason": reason,
        "blocked_at": time.time()
    }


@app.post("/admin/unblock_ip/{ip_address}")
async def unblock_ip(
    ip_address: str,
    request: Request,
    current_user: Optional[str] = Depends(get_current_user)
):
    """Разблокировать IP адрес"""
    
    if current_user != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав доступа"
        )
    
    tracker = get_request_tracker()
    tracker.unblock_ip(ip_address)
    
    return {
        "message": f"IP {ip_address} разблокирован",
        "unblocked_at": time.time()
    }


@app.post("/admin/user/{user_id}/tier")
async def set_user_tier(
    user_id: str,
    tier: str,
    request: Request,
    current_user: Optional[str] = Depends(get_current_user)
):
    """Установить уровень пользователя"""
    
    if current_user != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав доступа"
        )
    
    if tier not in ["free", "premium", "enterprise"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный уровень пользователя. Доступны: free, premium, enterprise"
        )
    
    tracker = get_request_tracker()
    tracker.set_user_tier(user_id, tier)
    
    return {
        "message": f"Пользователю {user_id} установлен уровень {tier}",
        "updated_at": time.time()
    }


@app.get("/health")
async def health_check():
    """Проверка здоровья системы"""
    tracker = get_request_tracker()
    stats = tracker.get_comprehensive_stats()
    
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "rate_limiting": {
            "enabled": True,
            "total_requests": stats["overall"]["total_requests"],
            "blocked_rate": f"{stats['overall']['blocked_rate_percent']:.2f}%"
        },
        "system": stats["system"]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "example_integration:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
