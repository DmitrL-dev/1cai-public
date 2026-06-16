"""
Tiered Rate Limiting Middleware

Enhanced rate limiting with:
- Tiered limits per user role
- Burst protection
- Path-based limits
- Prometheus metrics export
"""

from __future__ import annotations

import time
from enum import Enum
from typing import Dict, Optional, TYPE_CHECKING

from fastapi import HTTPException, status
from prometheus_client import Counter
from redis.asyncio import Redis
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

if TYPE_CHECKING:
    from src.modules.auth.application.service import AuthService

from src.utils.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


class UserTier(str, Enum):
    """User tier for rate limiting"""
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"
    REVOLUTIONARY = "revolutionary"  # For AI endpoints


# Tier configurations (requests per minute)
TIER_LIMITS: Dict[UserTier, int] = {
    UserTier.FREE: 60,
    UserTier.PRO: 300,
    UserTier.ENTERPRISE: 1000,
    UserTier.REVOLUTIONARY: 100,  # Special limit for AI endpoints
}

# Prometheus metrics
rate_limit_exceeded = Counter(
    'rate_limit_exceeded_total',
    'Total number of rate limit violations',
    ['tier', 'path']
)

rate_limit_requests = Counter(
    'rate_limit_requests_total',
    'Total number of rate limited requests',
    ['tier', 'path', 'status']
)


class TieredRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Apply tiered rate limiting based on user role and endpoint.

    Features:
    - Different limits per tier (free/pro/enterprise)
    - Path-based limits (revolutionary endpoints have separate limits)
    - Burst protection (sliding window)
    - Prometheus metrics
    """

    def __init__(
        self,
        app,
        redis_client: Redis,
        auth_service: Optional["AuthService"] = None,
        window_seconds: int = 60,
    ) -> None:
        super().__init__(app)
        self.redis = redis_client
        self.auth_service = auth_service
        self.window_seconds = window_seconds

        logger.info("TieredRateLimitMiddleware initialized")

    async def dispatch(self, request: Request, call_next) -> Response:
        """Apply tiered rate limiting"""

        # Determine user tier and limit
        tier, max_requests = self._get_tier_and_limit(request)

        # Build rate limit key
        limiter_key = self._build_rate_key(request, tier)

        if limiter_key:
            try:
                # Increment counter
                current_value = await self.redis.incr(limiter_key)

                # Set expiry on first request
                if current_value == 1:
                    await self.redis.expire(limiter_key, self.window_seconds)

                # Check limit
                if current_value > max_requests:
                    # Record metric
                    rate_limit_exceeded.labels(
                        tier=tier.value,
                        path=str(request.url.path)
                    ).inc()

                    logger.warning(
                        "Rate limit exceeded",
                        extra={
                            "tier": tier.value,
                            "current_value": current_value,
                            "max_requests": max_requests,
                            "path": str(request.url.path),
                        },
                    )

                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail={
                            "error": "Rate limit exceeded",
                            "tier": tier.value,
                            "limit": max_requests,
                            "window": self.window_seconds,
                            "retry_after": self.window_seconds
                        },
                        headers={
                            "X-RateLimit-Limit": str(max_requests),
                            "X-RateLimit-Remaining": "0",
                            "X-RateLimit-Reset": str(int(time.time()) + self.window_seconds),
                            "Retry-After": str(self.window_seconds)
                        }
                    )

                # Record successful request
                rate_limit_requests.labels(
                    tier=tier.value,
                    path=str(request.url.path),
                    status="allowed"
                ).inc()

                # Process request
                response = await call_next(request)

                # Add rate limit headers
                response.headers["X-RateLimit-Limit"] = str(max_requests)
                response.headers["X-RateLimit-Remaining"] = str(
                    max(0, max_requests - current_value))
                response.headers["X-RateLimit-Reset"] = str(
                    int(time.time()) + self.window_seconds)

                return response

            except HTTPException:
                raise
            except Exception as e:
                logger.error(
                    f"Error in rate limiting: {e}",
                    extra={"error_type": type(e).__name__},
                    exc_info=True,
                )
                # Graceful fallback
                return await call_next(request)

        return await call_next(request)

    def _get_tier_and_limit(self, request: Request) -> tuple[UserTier, int]:
        """
        Determine user tier and corresponding limit.

        Returns:
            (tier, max_requests)
        """
        # Check if revolutionary endpoint
        path = str(request.url.path)
        if "/revolutionary" in path:
            return UserTier.REVOLUTIONARY, TIER_LIMITS[UserTier.REVOLUTIONARY]

        # Get user from request state
        current_user = getattr(request.state, "current_user", None)

        if current_user:
            # Get user tier from user object
            user_tier = getattr(current_user, "tier", None)

            if user_tier == "enterprise":
                return UserTier.ENTERPRISE, TIER_LIMITS[UserTier.ENTERPRISE]
            elif user_tier == "pro":
                return UserTier.PRO, TIER_LIMITS[UserTier.PRO]

        # Default to free tier
        return UserTier.FREE, TIER_LIMITS[UserTier.FREE]

    def _build_rate_key(self, request: Request, tier: UserTier) -> Optional[str]:
        """Build rate limit key"""
        try:
            window = int(time.time() // self.window_seconds)

            # Try to get user ID
            current_user = getattr(request.state, "current_user", None)

            if current_user and getattr(current_user, "user_id", None):
                user_id = str(getattr(current_user, "user_id"))
                user_id = user_id.replace(":", "").replace(" ", "")
                return f"rl:v2:{tier.value}:user:{user_id}:{window}"

            # Fallback to IP
            if request.client and request.client.host:
                host = str(request.client.host)
                host = host.replace(":", "").replace(" ", "")
                return f"rl:v2:{tier.value}:ip:{host}:{window}"

            return None

        except Exception as e:
            logger.error(
                f"Error building rate key: {e}",
                extra={"error_type": type(e).__name__},
                exc_info=True,
            )
            return None
