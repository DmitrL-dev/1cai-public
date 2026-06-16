
"""
API администрирования кэша для 1С сервера

Основан на стандартах мониторинга и кэширования из RFC 7234
и практических рекомендациях по кэшированию в 1С:Предприятие.

Включает:
- Endpoints для мониторинга и управления кэшем
- Middleware для сбора метрик
- Аутентификацию для административных операций
- Интеграцию с различными типами кэшей
"""

import json
import logging
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import psutil
from fastapi import (APIRouter, Depends, HTTPException, Request, Security,
                     status)
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Схемы Pydantic для API
class CacheStats(BaseModel):
    """Модель статистики кэша"""
    total_keys: int = Field(..., description="Общее количество ключей")
    memory_usage_bytes: int = Field(..., description="Использование памяти в байтах")
    memory_usage_mb: float = Field(..., description="Использование памяти в МБ")
    hit_count: int = Field(..., description="Количество попаданий")
    miss_count: int = Field(..., description="Количество промахов")
    hit_rate: float = Field(..., description="Коэффициент попаданий (0.0 - 1.0)")
    avg_response_time_ms: float = Field(..., description="Среднее время отклика в мс")
    max_response_time_ms: float = Field(..., description="Максимальное время отклика в мс")
    min_response_time_ms: float = Field(..., description="Минимальное время отклика в мс")
    last_updated: datetime = Field(default_factory=datetime.now, description="Время последнего обновления")

class CacheHealth(BaseModel):
    """Модель проверки здоровья кэша"""
    status: str = Field(..., description="Статус (healthy/degraded/unhealthy)")
    timestamp: datetime = Field(default_factory=datetime.now, description="Время проверки")
    checks: Dict[str, Any] = Field(..., description="Результаты проверок")
    uptime_seconds: float = Field(..., description="Время работы в секундах")

class CacheKeyInfo(BaseModel):
    """Модель информации о ключе кэша"""
    key: str = Field(..., description="Ключ кэша")
    size_bytes: int = Field(..., description="Размер данных в байтах")
    ttl_seconds: Optional[int] = Field(None, description="Время жизни в секундах")
    created_at: datetime = Field(..., description="Время создания")
    last_accessed: datetime = Field(..., description="Последний доступ")
    hit_count: int = Field(default=0, description="Количество обращений")

class InvalidateRequest(BaseModel):
    """Модель запроса на инвалидацию кэша"""
    keys: List[str] = Field(..., description="Список ключей для инвалидации")
    reason: Optional[str] = Field(None, description="Причина инвалидации")

# Счетчики и метрики кэша
@dataclass
class CacheMetrics:
    """Метрики производительности кэша"""
    hit_count: int = 0
    miss_count: int = 0
    response_times: deque = deque(maxlen=1000)  # Последние 1000 измерений
    start_time: float = time.time()
    memory_snapshots: deque = deque(maxlen=100)  # Последние 100 снимков памяти
    
    @property
    def hit_rate(self) -> float:
        """Вычисляет коэффициент попаданий"""
        total = self.hit_count + self.miss_count
        return self.hit_count / total if total > 0 else 0.0
    
    @property
    def avg_response_time(self) -> float:
        """Вычисляет среднее время отклика"""
        if not self.response_times:
            return 0.0
        return sum(self.response_times) / len(self.response_times)
    
    @property
    def max_response_time(self) -> float:
        """Максимальное время отклика"""
        return max(self.response_times) if self.response_times else 0.0
    
    @property
    def min_response_time(self) -> float:
        """Минимальное время отклика"""
        return min(self.response_times) if self.response_times else 0.0

# Глобальные переменные для метрик
cache_metrics = CacheMetrics()
active_caches: Dict[str, Any] = {}

# Аутентификация
security = HTTPBearer(auto_error=False)

async def verify_admin_token(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> bool:
    """
    Проверка токена администратора.
    
    В реальном приложении здесь должна быть проверка JWT токена
    или интеграция с системой аутентификации.
    """
    # Простая проверка токена (в реальности нужна безопасная проверка)
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется аутентификация",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Проверка токена (пример - должен быть заменен на реальную проверку)
    expected_token = "admin_token_123"  # В продакшене - из переменных окружения
    if credentials.credentials != expected_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав доступа"
        )
    
    return True

# Middleware для сбора метрик
async def cache_middleware(request: Request, call_next):
    """Middleware для сбора метрик кэша"""
    start_time = time.time()
    
    # Игнорируем internal пути
    if request.url.path.startswith(("/cache/", "/docs", "/openapi.json", "/health")):
        return await call_next(request)
    
    try:
        response = await call_next(request)
        
        # Сбор метрик для кэш-запросов
        if response.headers.get("X-Cache-Status") in ["HIT", "MISS"]:
            response_time = (time.time() - start_time) * 1000  # в миллисекундах
            cache_metrics.response_times.append(response_time)
            
            cache_status = response.headers.get("X-Cache-Status")
            if cache_status == "HIT":
                cache_metrics.hit_count += 1
            elif cache_status == "MISS":
                cache_metrics.miss_count += 1
        
        # Добавляем заголовки с метриками
        if cache_metrics.response_times:
            response.headers["X-Avg-Response-Time"] = f"{cache_metrics.avg_response_time:.2f}ms"
            response.headers["X-Cache-Hit-Rate"] = f"{cache_metrics.hit_rate:.2%}"
        
        return response
        
    except Exception as e:
        logger.error(f"Ошибка в cache middleware: {e}")
        raise

# Интерфейс кэша
class CacheInterface:
    """Базовый интерфейс для работы с кэшами"""
    
    def __init__(self, name: str, cache_type: str = "memory"):
        self.name = name
        self.cache_type = cache_type
        self._data: Dict[str, Any] = {}
        self._metadata: Dict[str, Dict[str, Any]] = {}
        self._created_at = time.time()
    
    def get(self, key: str) -> Optional[Any]:
        """Получить значение из кэша"""
        start_time = time.time()
        
        if key in self._data:
            # Обновляем метаданные
            self._metadata[key]["last_accessed"] = datetime.now()
            self._metadata[key]["hit_count"] += 1
            
            response_time = (time.time() - start_time) * 1000
            cache_metrics.response_times.append(response_time)
            cache_metrics.hit_count += 1
            
            return self._data[key]
        
        cache_metrics.miss_count += 1
        return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Установить значение в кэш"""
        self._data[key] = value
        
        # Сохраняем метаданные
        self._metadata[key] = {
            "created_at": datetime.now(),
            "last_accessed": datetime.now(),
            "hit_count": 0,
            "ttl": ttl,
            "size_bytes": len(json.dumps(value, default=str))
        }
    
    def delete(self, key: str) -> bool:
        """Удалить значение из кэша"""
        if key in self._data:
            del self._data[key]
            del self._metadata[key]
            return True
        return False
    
    def clear(self) -> None:
        """Очистить кэш"""
        self._data.clear()
        self._metadata.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику кэша"""
        total_size = sum(
            meta.get("size_bytes", 0) 
            for meta in self._metadata.values()
        )
        
        return {
            "name": self.name,
            "type": self.cache_type,
            "total_keys": len(self._data),
            "memory_usage_bytes": total_size,
            "memory_usage_mb": total_size / (1024 * 1024),
            "uptime_seconds": time.time() - self._created_at
        }
    
    def get_keys_info(self) -> List[CacheKeyInfo]:
        """Получить информацию о всех ключах"""
        keys_info = []
        for key, meta in self._metadata.items():
            keys_info.append(CacheKeyInfo(
                key=key,
                size_bytes=meta.get("size_bytes", 0),
                ttl_seconds=meta.get("ttl"),
                created_at=meta["created_at"],
                last_accessed=meta["last_accessed"],
                hit_count=meta["hit_count"]
            ))
        return keys_info
    
    def get_key(self, key: str) -> Optional[CacheKeyInfo]:
        """Получить информацию о конкретном ключе"""
        if key in self._metadata:
            meta = self._metadata[key]
            return CacheKeyInfo(
                key=key,
                size_bytes=meta.get("size_bytes", 0),
                ttl_seconds=meta.get("ttl"),
                created_at=meta["created_at"],
                last_accessed=meta["last_accessed"],
                hit_count=meta["hit_count"]
            )
        return None

# Реализация различных типов кэшей
class MemoryCache(CacheInterface):
    """Кэш в памяти"""
    
    def __init__(self, name: str):
        super().__init__(name, "memory")

class RedisCache:
    """Адаптер для Redis (заглушка)"""
    
    def __init__(self, name: str, connection_string: str = "redis://localhost:6379"):
        self.name = name
        self.connection_string = connection_string
        self._metadata: Dict[str, Dict[str, Any]] = {}
        
        # В реальной реализации здесь будет подключение к Redis
        logger.info(f"Инициализация Redis кэша: {name}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Статистика Redis кэша"""
        return {
            "name": self.name,
            "type": "redis",
            "connection": self.connection_string,
            "total_keys": len(self._metadata),
            "memory_usage_bytes": 0,  # В реальности получаем из Redis
            "uptime_seconds": 0
        }

# Инициализация кэшей
def initialize_caches():
    """Инициализация различных кэшей системы"""
    global active_caches
    
    # Кэш метаданных 1С
    active_caches["metadata"] = MemoryCache("1c_metadata")
    
    # Кэш результатов вычислений
    active_caches["computations"] = MemoryCache("1c_computations")
    
    # Кэш HTTP запросов
    active_caches["http_responses"] = MemoryCache("http_responses")
    
    # Кэш пользовательских сессий
    active_caches["user_sessions"] = MemoryCache("user_sessions")
    
    # Redis кэш (если настроен)
    if True:  # В реальности - проверка наличия Redis
        active_caches["redis"] = RedisCache("main_redis")
    
    logger.info(f"Инициализировано {len(active_caches)} кэшей")

# Создание роутера
router = APIRouter(prefix="/cache", tags=["cache_admin"])

@router.get("/stats", response_model=CacheStats)
async def get_cache_stats(
    current_user: bool = Depends(verify_admin_token)
) -> CacheStats:
    """
    Получить статистику всех кэшей системы.
    
    Включает:
    - Общее количество ключей
    - Использование памяти
    - Коэффициент попаданий
    - Время отклика
    """
    try:
        # Собираем статистику по всем кэшам
        total_keys = 0
        total_memory = 0
        cache_details = []
        
        for cache_name, cache in active_caches.items():
            if hasattr(cache, 'get_stats'):
                stats = cache.get_stats()
                total_keys += stats["total_keys"]
                total_memory += stats["memory_usage_bytes"]
                cache_details.append(stats)
        
        # Добавляем системную информацию о памяти
        process = psutil.Process()
        system_memory = process.memory_info().rss
        
        return CacheStats(
            total_keys=total_keys,
            memory_usage_bytes=total_memory + system_memory,
            memory_usage_mb=(total_memory + system_memory) / (1024 * 1024),
            hit_count=cache_metrics.hit_count,
            miss_count=cache_metrics.miss_count,
            hit_rate=cache_metrics.hit_rate,
            avg_response_time_ms=cache_metrics.avg_response_time,
            max_response_time_ms=cache_metrics.max_response_time,
            min_response_time_ms=cache_metrics.min_response_time
        )
        
    except Exception as e:
        logger.error(f"Ошибка получения статистики кэша: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения статистики: {str(e)}"
        )

@router.get("/keys", response_model=List[CacheKeyInfo])
async def get_cache_keys(
    cache_name: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    current_user: bool = Depends(verify_admin_token)
) -> List[CacheKeyInfo]:
    """
    Получить список ключей в кэшах.
    
    - cache_name: имя конкретного кэша (опционально)
    - limit: максимальное количество записей
    - offset: смещение для пагинации
    """
    try:
        keys_info = []
        
        if cache_name:
            # Получаем ключи из конкретного кэша
            if cache_name not in active_caches:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Кэш '{cache_name}' не найден"
                )
            
            cache = active_caches[cache_name]
            if hasattr(cache, 'get_keys_info'):
                keys_info = cache.get_keys_info()
        else:
            # Получаем ключи из всех кэшей
            for name, cache in active_caches.items():
                if hasattr(cache, 'get_keys_info'):
                    cache_keys = cache.get_keys_info()
                    # Добавляем префикс с именем кэша
                    for key_info in cache_keys:
                        key_info.key = f"{name}:{key_info.key}"
                    keys_info.extend(cache_keys)
        
        # Сортируем по времени создания (новые сначала)
        keys_info.sort(key=lambda x: x.created_at, reverse=True)
        
        # Применяем пагинацию
        paginated_keys = keys_info[offset:offset + limit]
        
        return paginated_keys
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения ключей кэша: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения ключей: {str(e)}"
        )

@router.delete("/clear")
async def clear_cache(
    cache_name: Optional[str] = None,
    current_user: bool = Depends(verify_admin_token)
) -> Dict[str, str]:
    """
    Очистить кэш или все кэши.
    
    - cache_name: имя конкретного кэша (опционально)
    """
    try:
        cleared_caches = []
        
        if cache_name:
            # Очищаем конкретный кэш
            if cache_name not in active_caches:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Кэш '{cache_name}' не найден"
                )
            
            cache = active_caches[cache_name]
            if hasattr(cache, 'clear'):
                cache.clear()
                cleared_caches.append(cache_name)
        else:
            # Очищаем все кэши
            for name, cache in active_caches.items():
                if hasattr(cache, 'clear'):
                    cache.clear()
                    cleared_caches.append(name)
            
            # Сбрасываем глобальные метрики
            cache_metrics.hit_count = 0
            cache_metrics.miss_count = 0
            cache_metrics.response_times.clear()
        
        return {
            "status": "success",
            "message": f"Кэши очищены: {', '.join(cleared_caches)}",
            "cleared_caches": cleared_caches,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка очистки кэша: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка очистки кэша: {str(e)}"
        )

@router.delete("/invalidate/{key}")
async def invalidate_cache_key(
    key: str,
    cache_name: Optional[str] = None,
    current_user: bool = Depends(verify_admin_token)
) -> Dict[str, str]:
    """
    Инвалидировать конкретный ключ кэша.
    
    - key: ключ для инвалидации
    - cache_name: имя кэша (опционально, если ключ содержит префикс)
    """
    try:
        # Обработка ключей с префиксом cache_name:key
        if ":" in key and not cache_name:
            cache_name, clean_key = key.split(":", 1)
        else:
            clean_key = key
        
        invalidated_keys = []
        
        if cache_name:
            # Инвалидируем в конкретном кэше
            if cache_name not in active_caches:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Кэш '{cache_name}' не найден"
                )
            
            cache = active_caches[cache_name]
            if hasattr(cache, 'delete'):
                if cache.delete(clean_key):
                    invalidated_keys.append(key)
        else:
            # Ищем ключ во всех кэшах
            for name, cache in active_caches.items():
                if hasattr(cache, 'delete'):
                    if cache.delete(clean_key):
                        invalidated_keys.append(f"{name}:{clean_key}")
        
        if not invalidated_keys:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ключ '{key}' не найден в кэшах"
            )
        
        return {
            "status": "success",
            "message": f"Ключи инвалидированы: {', '.join(invalidated_keys)}",
            "invalidated_keys": invalidated_keys,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка инвалидации ключа кэша: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка инвалидации ключа: {str(e)}"
        )

@router.get("/health", response_model=CacheHealth)
async def cache_health_check(
    current_user: bool = Depends(verify_admin_token)
) -> CacheHealth:
    """
    Проверка здоровья кэша системы.
    
    Проверяет:
    - Доступность кэшей
    - Использование памяти
    - Коэффициент попаданий
    - Время отклика
    """
    try:
        checks = {}
        health_status = "healthy"
        
        # Проверка доступности кэшей
        for cache_name, cache in active_caches.items():
            try:
                if hasattr(cache, 'get_stats'):
                    stats = cache.get_stats()
                    checks[cache_name] = {
                        "status": "available",
                        "keys": stats["total_keys"],
                        "memory_mb": round(stats["memory_usage_mb"], 2)
                    }
                else:
                    checks[cache_name] = {"status": "available", "note": "Redis адаптер"}
            except Exception as e:
                checks[cache_name] = {"status": "error", "error": str(e)}
                health_status = "degraded"
        
        # Проверка метрик производительности
        total_requests = cache_metrics.hit_count + cache_metrics.miss_count
        
        if cache_metrics.hit_rate < 0.5:
            checks["hit_rate"] = {
                "status": "warning",
                "value": cache_metrics.hit_rate,
                "message": "Низкий коэффициент попаданий"
            }
            if health_status == "healthy":
                health_status = "degraded"
        else:
            checks["hit_rate"] = {
                "status": "ok",
                "value": cache_metrics.hit_rate
            }
        
        # Проверка времени отклика
        if cache_metrics.avg_response_time > 100:  # больше 100ms
            checks["response_time"] = {
                "status": "warning",
                "avg_ms": round(cache_metrics.avg_response_time, 2),
                "message": "Высокое время отклика"
            }
            if health_status == "healthy":
                health_status = "degraded"
        else:
            checks["response_time"] = {
                "status": "ok",
                "avg_ms": round(cache_metrics.avg_response_time, 2)
            }
        
        # Проверка использования памяти
        process = psutil.Process()
        memory_percent = process.memory_percent()
        
        if memory_percent > 80:
            checks["memory"] = {
                "status": "warning",
                "percent": round(memory_percent, 2),
                "message": "Высокое использование памяти"
            }
            if health_status == "healthy":
                health_status = "degraded"
        else:
            checks["memory"] = {
                "status": "ok",
                "percent": round(memory_percent, 2)
            }
        
        uptime_seconds = time.time() - cache_metrics.start_time
        
        return CacheHealth(
            status=health_status,
            checks=checks,
            uptime_seconds=uptime_seconds
        )
        
    except Exception as e:
        logger.error(f"Ошибка проверки здоровья кэша: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка проверки здоровья: {str(e)}"
        )

@router.get("/key/{key}", response_model=Optional[CacheKeyInfo])
async def get_cache_key_info(
    key: str,
    current_user: bool = Depends(verify_admin_token)
) -> Optional[CacheKeyInfo]:
    """
    Получить подробную информацию о конкретном ключе кэша.
    """
    try:
        # Обработка ключей с префиксом cache_name:key
        if ":" in key:
            cache_name, clean_key = key.split(":", 1)
            
            if cache_name not in active_caches:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Кэш '{cache_name}' не найден"
                )
            
            cache = active_caches[cache_name]
            if hasattr(cache, 'get_key'):
                key_info = cache.get_key(clean_key)
                if key_info:
                    key_info.key = key  # Возвращаем полный ключ с префиксом
                return key_info
        else:
            # Ищем ключ во всех кэшах
            for cache_name, cache in active_caches.items():
                if hasattr(cache, 'get_key'):
                    key_info = cache.get_key(key)
                    if key_info:
                        key_info.key = f"{cache_name}:{key_info.key}"
                        return key_info
        
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения информации о ключе: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения информации о ключе: {str(e)}"
        )

@router.get("/list")
async def list_caches(
    current_user: bool = Depends(verify_admin_token)
) -> Dict[str, Dict[str, Any]]:
    """
    Получить список всех доступных кэшей системы.
    """
    try:
        cache_list = {}
        
        for cache_name, cache in active_caches.items():
            if hasattr(cache, 'get_stats'):
                cache_list[cache_name] = cache.get_stats()
            else:
                cache_list[cache_name] = {
                    "name": cache_name,
                    "type": "redis",
                    "connection": getattr(cache, 'connection_string', 'unknown')
                }
        
        return cache_list
        
    except Exception as e:
        logger.error(f"Ошибка получения списка кэшей: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения списка кэшей: {str(e)}"
        )

# Инициализация при импорте модуля
initialize_caches()

# Экспорт для использования в других модулях
__all__ = [
    "router",
    "cache_middleware", 
    "CacheStats",
    "CacheHealth",
    "CacheKeyInfo",
    "MemoryCache",
    "RedisCache",
    "cache_metrics"
]