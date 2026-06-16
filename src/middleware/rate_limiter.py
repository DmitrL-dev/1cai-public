
"""
Rate Limiting Middleware для FastAPI
Версия: 2.0.0

Улучшения:
- Поддержка Redis для распределенного rate limiting
- Улучшенная обработка ошибок
- Структурированное логирование
- Graceful fallback на memory storage
"""

import os
from typing import Callable

from fastapi import Request, Response
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from src.utils.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


# Определение storage для rate limiting (best practice: Redis для production)
def get_storage_uri() -> str:
    """
    Получить URI storage для rate limiting с input validation

    Best practice: Использовать Redis для распределенного rate limiting в production
    """
    redis_url = os.getenv("REDIS_URL", "")

    # Input validation and sanitization
    if redis_url and isinstance(redis_url, str):
        # Limit URL length (prevent DoS)
        max_url_length = 1000
        if len(redis_url) > max_url_length:
            logger.warning(
                "Redis URL too long in get_storage_uri",
                extra={"url_length": len(redis_url), "max_length": max_url_length},
            )
            redis_url = redis_url[:max_url_length]

        # Basic URL validation (prevent injection)
        if redis_url.startswith(("redis://", "rediss://", "unix://")):
            logger.info(
                "Using Redis for rate limiting",
                extra={"redis_url_length": len(redis_url)},
            )
            return redis_url
        else:
            logger.warning(
                "Invalid Redis URL format in get_storage_uri",
                extra={"redis_url_start": redis_url[:20] if redis_url else None},
            )
            redis_url = ""

    # Fallback на memory storage (для development или single-instance)
    logger.warning("Redis not configured, using memory storage for rate limiting")
    return "memory://"


# Создание лимитера с улучшенной конфигурацией
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["1000/hour"],  # По умолчанию 1000 запросов в час
    storage_uri=get_storage_uri(),
    headers_enabled=True,  # Включаем заголовки X-RateLimit-*
    retry_after="x-ratelimit-retry-after",  # Стандартный заголовок для retry
)


def create_rate_limit_middleware(app):
    """Создание rate limiting middleware для приложения"""

    # Добавление обработчика ошибок rate limit
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next: Callable) -> Response:
        """
        Middleware для rate limiting с улучшенной обработкой ошибок и input validation

        Best practices:
        - Пропускаем health checks и документацию
        - Логируем rate limit violations
        - Возвращаем структурированные ошибки
        - Input validation для безопасности
        """
        # Input validation
        if not request or not hasattr(request, "url"):
            logger.error("Invalid request object in rate_limit_middleware")
            return await call_next(request)

        # Пропускаем health checks и документацию (best practice)
        excluded_paths = [
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/metrics",
            "/favicon.ico",
        ]

        # Sanitize path (prevent injection)
        request_path = str(request.url.path) if request.url.path else ""
        if len(request_path) > 1000:  # Prevent DoS
            logger.warning(
                "Path too long in rate_limit_middleware",
                extra={"path_length": len(request_path)},
            )
            request_path = request_path[:1000]

        if request_path in excluded_paths:
            return await call_next(request)

        try:
            # Применяем лимиты (автоматически через декораторы)
            # Для публичных endpoints лимиты применяются через декораторы
            response = await call_next(request)

            # Добавляем rate limit headers (best practice: inform client about limits)
            if hasattr(request.state, "view_rate_limit"):
                limit_info = request.state.view_rate_limit

                # Validate limit_info values
                if hasattr(limit_info, "limit"):
                    response.headers["X-RateLimit-Limit"] = str(
                        max(0, int(limit_info.limit))
                    )
                if hasattr(limit_info, "remaining"):
                    response.headers["X-RateLimit-Remaining"] = str(
                        max(0, int(limit_info.remaining))
                    )
                if hasattr(limit_info, "reset"):
                    response.headers["X-RateLimit-Reset"] = str(
                        max(0, int(limit_info.reset))
                    )

            return response

        except RateLimitExceeded as e:
            # Логируем rate limit violation (best practice: structured logging)
            client_ip = None
            if request.client and hasattr(request.client, "host"):
                client_ip = str(request.client.host)[:100]  # Limit length

            logger.warning(
                "Rate limit exceeded",
                extra={
                    "path": request_path,
                    "method": str(request.method)[:10] if request.method else None,
                    "client_ip": client_ip,
                    "limit": str(e.limit) if hasattr(e, "limit") else "unknown",
                },
            )
            # Пробрасываем исключение для обработки через exception handler
            raise

    logger.info(
        "Rate limiting middleware настроен", extra={"storage": get_storage_uri()}
    )

    return app


# ==================== ДЕКОРАТОРЫ ДЛЯ ЛИМИТОВ ====================


def rate_limit(limit: str = "10/minute", per: str = None):
    """
    Декоратор для rate limiting endpoints

    Args:
        limit: Лимит запросов (например "10/minute", "100/hour")
        per: Дополнительный параметр (опционально)

    Примеры:
        @rate_limit("10/minute")  # 10 запросов в минуту
        @rate_limit("100/hour")    # 100 запросов в час
        @rate_limit("1000/day")    # 1000 запросов в день
    """

    def decorator(func):
        return limiter.limit(limit)(func)

    return decorator


# ==================== ПРЕДУСТАНОВЛЕННЫЕ ЛИМИТЫ ====================

# Публичные endpoints (Code Review, Test Generation)
PUBLIC_RATE_LIMIT = "20/minute"  # 20 запросов в минуту

# Защищенные endpoints (AI Assistants)
PROTECTED_RATE_LIMIT = "100/hour"  # 100 запросов в час

# Тяжелые операции (ML, анализ)
HEAVY_OPERATION_LIMIT = "10/hour"  # 10 запросов в час

# Легкие операции (health check, метрики)
LIGHT_OPERATION_LIMIT = "1000/hour"  # 1000 запросов в час
