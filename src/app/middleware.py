"""
Middleware Configuration for 1C AI Stack

Настройка middleware в одном месте.
"""

import logging
import os
import time
import threading

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from src.config import settings
from src.middleware.security_headers import SecurityHeadersMiddleware
from src.middleware.ai_security_middleware import AISecurityMiddleware
from src.middleware.metrics_middleware import MetricsMiddleware

logger = logging.getLogger(__name__)


# Paths that must never be throttled (liveness / readiness / docs / metrics).
_RATE_LIMIT_EXEMPT_PATHS = frozenset(
    {
        "/health",
        "/health/deep",
        "/metrics",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/favicon.ico",
    }
)


class InMemoryRateLimitMiddleware(BaseHTTPMiddleware):
    """Always-on, per-process, per-IP fixed-window rate limiter.

    SECURITY (P0): the Redis-backed ``UserRateLimitMiddleware`` is only wired up
    in :func:`src.app.lifespan.lifespan` when a Redis client is available. On the
    documented target deployment (no Docker / no Redis) that leaves the public
    surface (``/rentgen/*``, ``/quality/*``, ``/auth/token`` …) with ZERO
    throttling, open to credential brute-force and CPU-exhaustion. This
    middleware provides a lightweight default that is ALWAYS active, with no
    external dependency.

    Design:
    - Fixed-window counter keyed by client IP, kept in an in-process dict.
    - ``max_requests`` per ``window_seconds`` (configurable via env).
    - Fails OPEN: any internal error allows the request through.
    - Exempts liveness / docs / metrics paths.
    - Returns HTTP 429 with a ``Retry-After`` header when exceeded.

    This is per-process and therefore approximate behind multiple workers; it is
    a safety floor, not a substitute for the distributed Redis limiter.
    """

    def __init__(
        self,
        app,
        max_requests: int = 120,
        window_seconds: int = 60,
    ) -> None:
        super().__init__(app)
        if not isinstance(max_requests, int) or max_requests < 1:
            max_requests = 120
        if not isinstance(window_seconds, int) or window_seconds < 1:
            window_seconds = 60
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        # key -> (window_start_epoch, count)
        self._buckets: dict[str, list] = {}
        self._lock = threading.Lock()

    def _client_ip(self, request: Request) -> str:
        client = request.client
        if client and client.host:
            return str(client.host)
        return "unknown"

    def _check(self, key: str, now: float) -> tuple[bool, int]:
        """Return (allowed, retry_after_seconds). Increments the counter."""
        window = int(now // self.window_seconds)
        with self._lock:
            entry = self._buckets.get(key)
            if entry is None or entry[0] != window:
                # New window. Opportunistically drop stale buckets to bound memory.
                if len(self._buckets) > 10000:
                    self._buckets = {
                        k: v for k, v in self._buckets.items() if v[0] == window
                    }
                self._buckets[key] = [window, 1]
                return True, 0
            entry[1] += 1
            if entry[1] > self.max_requests:
                retry_after = self.window_seconds - int(now % self.window_seconds)
                return False, max(1, retry_after)
            return True, 0

    async def dispatch(self, request: Request, call_next) -> Response:
        try:
            path = request.url.path or ""
            if path in _RATE_LIMIT_EXEMPT_PATHS:
                return await call_next(request)

            key = self._client_ip(request)
            allowed, retry_after = self._check(key, time.time())
            if not allowed:
                logger.warning(
                    "In-memory rate limit exceeded for %s on %s (limit %s/%ss)",
                    key,
                    path,
                    self.max_requests,
                    self.window_seconds,
                )
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": "Too many requests, please try again later.",
                        "limit": self.max_requests,
                        "window_seconds": self.window_seconds,
                    },
                    headers={
                        "Retry-After": str(retry_after),
                        "X-RateLimit-Limit": str(self.max_requests),
                        "X-RateLimit-Remaining": "0",
                    },
                )
        except Exception as e:  # Fail OPEN — never block traffic on limiter bugs.
            logger.debug("In-memory rate limiter error (failing open): %s", e)
            return await call_next(request)

        return await call_next(request)


def setup_middleware(app: FastAPI):
    """Настраивает все middleware для приложения."""
    
    # CORS
    cors_origins = settings.get_cors_origins()
    
    if settings.environment == "development" and "*" in cors_origins:
        logger.warning(
            "CORS allows all origins in development mode. Restrict in production!"
        )
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=[
            "Content-Disposition",
            "X-Archive-Files",
            "X-Archive-Manifest",
            "X-Archive-Manifest-Files",
            "X-Archive-Manifest-Sha256",
            "X-Archive-Sha256",
            "X-Buyer-Room-Packet-Files",
            "X-Buyer-Room-Packet-Open-First",
            "X-Buyer-Room-Packet-Sha256",
            "X-Dual-Verification-Status",
            "X-Evidence-Archive-Sha256",
            "X-Killer-Demo-Archive-Sha256",
            "X-Killer-Demo-Manifest",
            "X-Killer-Demo-Manifest-Files",
            "X-Killer-Demo-Manifest-Sha256",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-Request-ID",
            "X-Verification-Packet-Files",
            "X-Verification-Packet-Sha256",
        ],
        max_age=3600,
    )
    
    # Security Headers
    app.add_middleware(SecurityHeadersMiddleware)
    
    # AI Security (Rule of Two)
    app.add_middleware(AISecurityMiddleware)
    
    # Compression
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    
    # Metrics
    app.add_middleware(MetricsMiddleware)

    # Default in-memory rate limiting (always on, no Redis required).
    # The Redis-backed limiter in lifespan only activates when Redis is present;
    # this guarantees a per-process throttle floor on the no-Redis target.
    _add_default_rate_limit(app)

    # JWT User Context
    try:
        from src.middleware.jwt_user_context import JWTUserContextMiddleware
        from src.modules.auth.api.dependencies import get_auth_service
        
        auth_service = get_auth_service()
        app.add_middleware(JWTUserContextMiddleware, auth_service=auth_service)
        logger.info("JWT middleware added")
    except Exception as e:
        if settings.environment == "production":
            raise
        logger.warning(f"Failed to add JWT middleware: {e}")
    
    logger.info("Middleware setup completed")


def _add_default_rate_limit(app: FastAPI):
    """Attach the always-on in-memory rate limiter (env-configurable).

    Env:
        DEFAULT_RATE_LIMIT_ENABLED   ("0"/"false" to disable; default enabled)
        DEFAULT_RATE_LIMIT_PER_MIN   (int, default 120 requests/IP/window)
        DEFAULT_RATE_LIMIT_WINDOW_S  (int, default 60 seconds)
    """
    enabled = os.getenv("DEFAULT_RATE_LIMIT_ENABLED", "true").strip().lower()
    if enabled in ("0", "false", "no", "off"):
        logger.info("Default in-memory rate limiter disabled via env")
        return

    def _int_env(name: str, default: int) -> int:
        try:
            value = int(os.getenv(name, str(default)))
            return value if value >= 1 else default
        except (TypeError, ValueError):
            return default

    max_requests = _int_env("DEFAULT_RATE_LIMIT_PER_MIN", 120)
    window_seconds = _int_env("DEFAULT_RATE_LIMIT_WINDOW_S", 60)

    app.add_middleware(
        InMemoryRateLimitMiddleware,
        max_requests=max_requests,
        window_seconds=window_seconds,
    )
    logger.info(
        "Default in-memory rate limiter enabled (%s req / %ss / IP)",
        max_requests,
        window_seconds,
    )
