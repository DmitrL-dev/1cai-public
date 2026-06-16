
"""
Сервис кэширования для Code Review и других сервисов
Версия: 2.0.0

Улучшения:
- Circuit breaker для Redis
- Улучшенная обработка ошибок
- Логирование через logging вместо print
- Timeout для операций Redis
"""

import asyncio
import hashlib
import json
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from typing import Any, Optional

import redis.asyncio as aioredis

from src.config import settings
from src.utils.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger

# In-memory кэш для fallback (если Redis недоступен)
memory_cache: dict = {}
memory_cache_ttl: dict = {}


class CircuitState(Enum):
    """Состояния circuit breaker"""

    CLOSED = "closed"  # Нормальная работа
    OPEN = "open"  # Сбой, не используем Redis
    HALF_OPEN = "half_open"  # Пробуем восстановить


class CacheService:
    """
    Сервис кэширования результатов с circuit breaker

    Best practices:
    - Circuit breaker для защиты от каскадных сбоев
    - Graceful fallback на in-memory cache
    - Timeout для всех операций
    - Structured logging
    """

    def __init__(self):
        self.redis_client: Optional[aioredis.Redis] = None
        self.use_redis = False
        self.circuit_state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.circuit_open_timeout = 60  # секунд до попытки восстановления
        self.max_failures = 5  # Максимум ошибок перед открытием circuit
        self._init_redis()

    def _init_redis(self):
        """Инициализация Redis клиента (синхронная инициализация)"""
        # Redis инициализируется асинхронно при первом использовании
        self.use_redis = False

    async def _ensure_redis(self):
        """Обеспечение наличия Redis соединения с circuit breaker"""
        # Проверяем circuit breaker
        if self.circuit_state == CircuitState.OPEN:
            # Проверяем, можно ли попробовать восстановить
            if self.last_failure_time:
                elapsed = (datetime.now() - self.last_failure_time).total_seconds()
                if elapsed > self.circuit_open_timeout:
                    self.circuit_state = CircuitState.HALF_OPEN
                    logger.info("Circuit breaker: переход в HALF_OPEN состояние")
                else:
                    return  # Circuit открыт, используем fallback

        if not self.use_redis and not self.redis_client:
            try:
                # Timeout для подключения
                self.redis_client = aioredis.from_url(
                    settings.redis_url,
                    socket_connect_timeout=2,
                    socket_timeout=2,
                    decode_responses=True,
                )
                # Проверка соединения с timeout
                await asyncio.wait_for(self.redis_client.ping(), timeout=2.0)
                self.use_redis = True
                self.circuit_state = CircuitState.CLOSED
                self.failure_count = 0
                logger.info("Redis подключен успешно")
            except Exception as e:
                logger.warning(
                    "Redis недоступен, используется in-memory кэш",
                    extra={
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "failure_count": self.failure_count,
                    },
                )
                self.use_redis = False
                self.failure_count += 1
                self.last_failure_time = datetime.now()

                if self.failure_count >= self.max_failures:
                    self.circuit_state = CircuitState.OPEN
                    logger.error(
                        "Circuit breaker открыт после ошибок",
                        extra={
                            "failure_count": self.failure_count,
                            "max_failures": self.max_failures,
                            "circuit_state": self.circuit_state.value,
                        },
                    )

                if self.redis_client:
                    try:
                        await self.redis_client.close()
                    except Exception as e:
                        logger.warning(
                            "Error closing Redis client",
                            extra={"error": str(e), "error_type": type(e).__name__},
                        )
                    self.redis_client = None

    async def get(self, key: str) -> Optional[Any]:
        """
        Получение значения из кэша с circuit breaker и input validation

        Best practice: Graceful degradation при сбоях Redis
        """
        # Input validation
        if not isinstance(key, str) or not key.strip():
            logger.warning(
                "Invalid key in CacheService.get",
                extra={"key_type": type(key).__name__ if key else None},
            )
            return None

        # Limit key length (prevent DoS)
        max_key_length = 1000
        if len(key) > max_key_length:
            logger.warning(
                "Key too long in CacheService.get",
                extra={"key_length": len(key), "max_length": max_key_length},
            )
            key = key[:max_key_length]

        await self._ensure_redis()

        if (
            self.use_redis
            and self.redis_client
            and self.circuit_state != CircuitState.OPEN
        ):
            try:
                # Timeout для операции чтения
                value = await asyncio.wait_for(self.redis_client.get(key), timeout=1.0)
                if value:
                    # Успешная операция - сбрасываем счетчик ошибок
                    if self.circuit_state == CircuitState.HALF_OPEN:
                        self.circuit_state = CircuitState.CLOSED
                        self.failure_count = 0
                    try:
                        return json.loads(value)
                    except (json.JSONDecodeError, TypeError) as e:
                        logger.warning(
                            "Error parsing cached value",
                            extra={
                                "key": key,
                                "error": str(e),
                                "error_type": type(e).__name__,
                            },
                        )
                        return None
            except asyncio.TimeoutError:
                logger.warning("Timeout при чтении из Redis", extra={"key": key})
                self.failure_count += 1
            except Exception as e:
                logger.warning(
                    "Ошибка чтения из Redis",
                    extra={"key": key, "error": str(e), "error_type": type(e).__name__},
                    exc_info=True,
                )
                self.failure_count += 1
                self.last_failure_time = datetime.now()

                if self.failure_count >= self.max_failures:
                    self.circuit_state = CircuitState.OPEN

        # In-memory fallback
        if key in memory_cache:
            if key in memory_cache_ttl:
                if datetime.now() < memory_cache_ttl[key]:
                    return memory_cache[key]
                else:
                    # TTL истек
                    del memory_cache[key]
                    del memory_cache_ttl[key]
            else:
                return memory_cache[key]

        return None

    async def set(self, key: str, value: Any, ttl: int = 3600):
        """
        Сохранение значения в кэш с circuit breaker и input validation

        Best practice: Всегда сохраняем в memory cache как fallback
        """
        # Input validation
        if not isinstance(key, str) or not key.strip():
            logger.warning(
                "Invalid key in CacheService.set",
                extra={"key_type": type(key).__name__ if key else None},
            )
            return

        # Limit key length (prevent DoS)
        max_key_length = 1000
        if len(key) > max_key_length:
            logger.warning(
                "Key too long in CacheService.set",
                extra={"key_length": len(key), "max_length": max_key_length},
            )
            key = key[:max_key_length]

        # Validate TTL
        if not isinstance(ttl, int) or ttl < 0:
            logger.warning(
                "Invalid TTL in CacheService.set",
                extra={"ttl": ttl, "ttl_type": type(ttl).__name__},
            )
            ttl = 3600

        if ttl > 86400 * 365:  # Max 1 year
            logger.warning("TTL too large in CacheService.set", extra={"ttl": ttl})
            ttl = 86400 * 365

        await self._ensure_redis()

        try:
            serialized = json.dumps(value, default=str)
            # Limit serialized value size (prevent DoS)
            max_value_size = 10 * 1024 * 1024  # 10MB max
            if len(serialized) > max_value_size:
                logger.warning(
                    "Value too large in CacheService.set",
                    extra={"value_size": len(serialized), "max_size": max_value_size},
                )
                return
        except (TypeError, ValueError) as e:
            logger.warning(
                "Error serializing value in CacheService.set",
                extra={"key": key, "error": str(e), "error_type": type(e).__name__},
            )
            return

        # Всегда сохраняем в memory cache (fallback)
        memory_cache[key] = value
        memory_cache_ttl[key] = datetime.now() + timedelta(seconds=ttl)

        if (
            self.use_redis
            and self.redis_client
            and self.circuit_state != CircuitState.OPEN
        ):
            try:
                # Timeout для операции записи
                await asyncio.wait_for(
                    self.redis_client.setex(key, ttl, serialized), timeout=1.0
                )
                # Успешная операция - сбрасываем счетчик ошибок
                if self.circuit_state == CircuitState.HALF_OPEN:
                    self.circuit_state = CircuitState.CLOSED
                    self.failure_count = 0
            except asyncio.TimeoutError:
                logger.warning("Timeout при записи в Redis", extra={"key": key})
                self.failure_count += 1
            except Exception as e:
                logger.warning(
                    "Ошибка записи в Redis",
                    extra={"key": key, "error": str(e), "error_type": type(e).__name__},
                    exc_info=True,
                )
                self.failure_count += 1
                self.last_failure_time = datetime.now()

                if self.failure_count >= self.max_failures:
                    self.circuit_state = CircuitState.OPEN

    async def delete(self, key: str):
        """Удаление значения из кэша с input validation"""
        # Input validation
        if not isinstance(key, str) or not key.strip():
            logger.warning(
                "Invalid key in CacheService.delete",
                extra={"key_type": type(key).__name__ if key else None},
            )
            return

        # Limit key length (prevent DoS)
        max_key_length = 1000
        if len(key) > max_key_length:
            logger.warning(
                "Key too long in CacheService.delete",
                extra={"key_length": len(key), "max_length": max_key_length},
            )
            key = key[:max_key_length]

        await self._ensure_redis()

        if self.use_redis and self.redis_client:
            try:
                await self.redis_client.delete(key)
            except Exception as e:
                logger.warning(
                    "Ошибка удаления из Redis",
                    extra={"key": key, "error": str(e), "error_type": type(e).__name__},
                    exc_info=True,
                )

        # In-memory fallback
        if key in memory_cache:
            del memory_cache[key]
        if key in memory_cache_ttl:
            del memory_cache_ttl[key]

    async def clear_pattern(self, pattern: str):
        """Очистка кэша по паттерну с input validation"""
        # Input validation
        if not isinstance(pattern, str) or not pattern.strip():
            logger.warning(
                "Invalid pattern in CacheService.clear_pattern",
                extra={"pattern_type": type(pattern).__name__ if pattern else None},
            )
            return

        # Limit pattern length (prevent DoS)
        max_pattern_length = 500
        if len(pattern) > max_pattern_length:
            logger.warning(
                "Pattern too long in CacheService.clear_pattern",
                extra={
                    "pattern_length": len(pattern),
                    "max_length": max_pattern_length,
                },
            )
            pattern = pattern[:max_pattern_length]

        await self._ensure_redis()

        if self.use_redis and self.redis_client:
            try:
                keys = await self.redis_client.keys(pattern)
                if keys:
                    # Limit number of keys to delete (prevent DoS)
                    max_keys_to_delete = 10000
                    if len(keys) > max_keys_to_delete:
                        logger.warning(
                            "Too many keys to delete in CacheService.clear_pattern",
                            extra={
                                "keys_count": len(keys),
                                "max_keys": max_keys_to_delete,
                            },
                        )
                        keys = keys[:max_keys_to_delete]
                    await self.redis_client.delete(*keys)
            except Exception as e:
                logger.warning(
                    "Ошибка очистки Redis",
                    extra={
                        "pattern": pattern,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                    exc_info=True,
                )

        # In-memory fallback
        keys_to_delete = [
            k for k in memory_cache.keys() if pattern.replace("*", "") in k
        ]
        # Limit keys to delete
        max_keys_to_delete = 10000
        if len(keys_to_delete) > max_keys_to_delete:
            logger.warning(
                "Too many keys to delete in memory cache",
                extra={
                    "keys_count": len(keys_to_delete),
                    "max_keys": max_keys_to_delete,
                },
            )
            keys_to_delete = keys_to_delete[:max_keys_to_delete]

        for key in keys_to_delete:
            if key in memory_cache:
                del memory_cache[key]
            if key in memory_cache_ttl:
                del memory_cache_ttl[key]

    def generate_key(self, prefix: str, *args, **kwargs) -> str:
        """Генерация ключа кэша с input validation"""
        # Input validation
        if not isinstance(prefix, str) or not prefix.strip():
            logger.warning(
                "Invalid prefix in CacheService.generate_key",
                extra={"prefix_type": type(prefix).__name__ if prefix else None},
            )
            prefix = "cache"

        # Limit prefix length
        max_prefix_length = 100
        if len(prefix) > max_prefix_length:
            logger.warning(
                "Prefix too long in CacheService.generate_key",
                extra={"prefix_length": len(prefix), "max_length": max_prefix_length},
            )
            prefix = prefix[:max_prefix_length]

        try:
            # Limit args and kwargs size (prevent DoS)
            args_str = json.dumps(args, default=str)
            kwargs_str = json.dumps(kwargs, sort_keys=True, default=str)

            max_data_length = 10000
            if len(args_str) > max_data_length:
                args_str = args_str[:max_data_length]
            if len(kwargs_str) > max_data_length:
                kwargs_str = kwargs_str[:max_data_length]

            key_data = f"{prefix}:{args_str}:{kwargs_str}"
            key_hash = hashlib.md5(key_data.encode()).hexdigest()
            return f"{prefix}:{key_hash}"
        except (TypeError, ValueError) as e:
            logger.warning(
                "Error generating cache key",
                extra={
                    "prefix": prefix,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
            # Fallback to simple hash
            key_data = f"{prefix}:{str(args)}:{str(kwargs)}"
            key_hash = hashlib.md5(key_data.encode()).hexdigest()
            return f"{prefix}:{key_hash}"


# Глобальный экземпляр
_cache_service: Optional[CacheService] = None


def get_cache_service() -> CacheService:
    """Получение экземпляра сервиса кэширования"""
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()
    return _cache_service


# ==================== ДЕКОРАТОРЫ ДЛЯ КЭШИРОВАНИЯ ====================


def cache_result(ttl: int = 3600, key_prefix: str = "cache"):
    """Декоратор для кэширования результатов функции"""

    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            cache_service = get_cache_service()

            # Генерация ключа
            cache_key = cache_service.generate_key(
                f"{key_prefix}:{func.__name__}", *args, **kwargs
            )

            # Попытка получить из кэша
            cached = await cache_service.get(cache_key)
            if cached is not None:
                return cached

            # Выполнение функции
            result = await func(*args, **kwargs)

            # Сохранение в кэш
            await cache_service.set(cache_key, result, ttl)

            return result

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            cache_service = get_cache_service()

            # Генерация ключа
            cache_key = cache_service.generate_key(
                f"{key_prefix}:{func.__name__}", *args, **kwargs
            )

            # Для синхронных функций используем синхронный вызов
            # (упрощенная версия)
            if cache_key in memory_cache:
                return memory_cache[cache_key]

            result = func(*args, **kwargs)
            memory_cache[cache_key] = result
            memory_cache_ttl[cache_key] = datetime.now() + timedelta(seconds=ttl)

            return result

        # Возвращаем async или sync wrapper в зависимости от типа функции
        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator
