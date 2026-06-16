"""
Authentication Middleware
"""
import os
from typing import Any, List

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.infrastructure.logging.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Middleware for authentication"""

    def __init__(self, app: Any, allowed_paths: List[str] = None) -> None:
        super().__init__(app)
        self.allowed_paths = allowed_paths or [
            "/health",
            "/metrics",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/api/gateway/health",
        ]
        # Use environment variables for API keys
        api_keys_env = os.getenv("GATEWAY_API_KEYS", "")
        if api_keys_env:
            self.valid_api_keys = [key.strip()
                                             for key in api_keys_env.split(",") if key.strip()]
        else:
            # Fallback for development (in production should be via env)
            self.valid_api_keys = ["demo-key-12345", "admin-key-67890"]
            logger.warning(
                "Using default API keys. Set GATEWAY_API_KEYS environment variable for production!")

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        """Middleware for authentication with input validation"""
        try:
            # Check allowed paths
            if request.url.path in self.allowed_paths:
                return await call_next(request)

            # Check API key
            api_key = request.headers.get(
                "X-API-Key") or request.headers.get("Authorization")

            # If Authorization header contains "Bearer ", extract token
            if api_key and api_key.startswith("Bearer "):
                api_key = api_key[7:].strip()

            if not api_key:
                logger.warning(
                    "API key not provided",
                    extra={"path": request.url.path, "method": request.method},
                )
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "API key not provided"},
                )

            # Validate API key length (prevent DoS)
            max_key_length = 500
            if len(api_key) > max_key_length:
                logger.warning(
                    "API key too long",
                    extra={
                        "path": request.url.path,
                        "method": request.method,
                        "key_length": len(api_key),
                    },
                )
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Invalid API key"},
                )

            # Simple API key check (in production use JWT or OAuth)
            if api_key not in self.valid_api_keys:
                logger.warning(
                    "Invalid API key",
                    extra={
                        "path": request.url.path,
                        "method": request.method,
                        "key_preview": (api_key[:10] + "..." if len(api_key) > 10 else api_key),
                    },
                )
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Invalid API key"},
                )

            return await call_next(request)
        except Exception as e:
            logger.error(
                f"Error in AuthenticationMiddleware: {e}",
                extra={
                    "path": request.url.path if "request" in locals() else None,
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Internal server error"},
            )
