
"""
Request rate limiting middleware using Redis counters.
Версия: 2.1.0

Улучшения:
- Structured logging
- Улучшена обработка ошибок
- Graceful fallback при ошибках Redis
"""

from __future__ import annotations

import time
from typing import Optional, TYPE_CHECKING

from fastapi import HTTPException, status
from redis.asyncio import Redis
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

if TYPE_CHECKING:
    from src.modules.auth.application.service import AuthService

from src.utils.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


class UserRateLimitMiddleware(BaseHTTPMiddleware):
    """Apply per-user or per-IP rate limiting using Redis counters."""

    def __init__(
        self,
        app,
        redis_client: Redis,
        max_requests: int = 60,
        window_seconds: int = 60,
        auth_service: Optional["AuthService"] = None,
    ) -> None:
        super().__init__(app)

        # Input validation
        if not isinstance(max_requests, int) or max_requests < 1:
            logger.warning(
                "Invalid max_requests in UserRateLimitMiddleware.__init__",
                extra={
                    "max_requests": max_requests,
                    "max_requests_type": type(max_requests).__name__,
                },
            )
            max_requests = 60  # Default

        if not isinstance(window_seconds, int) or window_seconds < 1:
            logger.warning(
                "Invalid window_seconds in UserRateLimitMiddleware.__init__",
                extra={
                    "window_seconds": window_seconds,
                    "window_seconds_type": type(window_seconds).__name__,
                },
            )
            window_seconds = 60  # Default

        self.redis = redis_client
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.auth_service = auth_service

        logger.debug(
            "UserRateLimitMiddleware initialized",
            extra={"max_requests": max_requests, "window_seconds": window_seconds},
        )

    # type: ignore[override]
    async def dispatch(self, request: Request, call_next) -> Response:
        limiter_key = self._build_rate_key(request)
        if limiter_key:
            try:
                current_value = await self.redis.incr(limiter_key)
                if current_value == 1:
                    await self.redis.expire(limiter_key, self.window_seconds)

                if current_value > self.max_requests:
                    logger.warning(
                        "Rate limit exceeded",
                        extra={
                            "limiter_key": limiter_key,
                            "current_value": current_value,
                            "max_requests": self.max_requests,
                            "path": str(request.url.path),
                        },
                    )
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail=f"Too many requests, please try again later. Limit: {self.max_requests} per {self.window_seconds}s",
                    )
            except Exception as e:
                # Graceful fallback: allow request if Redis fails
                logger.error(
                    f"Error checking rate limit: {e}",
                    extra={
                        "limiter_key": limiter_key,
                        "error_type": type(e).__name__,
                        "path": str(request.url.path),
                    },
                    exc_info=True,
                )
                # Continue without rate limiting rather than blocking all requests
        return await call_next(request)

    def _build_rate_key(self, request: Request) -> Optional[str]:
        """Build rate limit key with input validation"""
        try:
            window = int(time.time() // self.window_seconds)
            current_user = getattr(request.state, "current_user", None)

            if not current_user and self.auth_service:
                authorization: Optional[str] = request.headers.get("Authorization")
                if authorization and isinstance(authorization, str) and authorization.lower().startswith("bearer "):
                    token = authorization.split(" ", maxsplit=1)[1].strip()

                    # Validate token length (prevent DoS)
                    max_token_length = 1000
                    if len(token) > max_token_length:
                        logger.warning(
                            "Token too long in _build_rate_key",
                            extra={
                                "token_length": len(token),
                                "max_length": max_token_length,
                            },
                        )
                        token = token[:max_token_length]

                    try:
                        current_user = self.auth_service.decode_token(token)
                        request.state.current_user = current_user
                    except HTTPException:
                        current_user = None
                    except Exception as e:
                        logger.debug(
                            f"Error decoding token in _build_rate_key: {e}",
                            extra={"error_type": type(e).__name__},
                        )
                        current_user = None

            if current_user and getattr(current_user, "user_id", None):
                user_id = str(getattr(current_user, "user_id"))
                # Sanitize user_id (prevent injection)
                user_id = user_id.replace(":", "").replace(" ", "")
                return f"rl:user:{user_id}:{window}"

            if request.client and request.client.host:
                host = str(request.client.host)
                # Sanitize host (prevent injection)
                host = host.replace(":", "").replace(" ", "")
                return f"rl:ip:{host}:{window}"

            return None
        except Exception as e:
            logger.error(
                f"Error building rate key: {e}",
                extra={
                    "error_type": type(e).__name__,
                    "path": str(request.url.path) if request else None,
                },
                exc_info=True,
            )
            return None
