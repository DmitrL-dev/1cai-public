"""
Tenant Context Middleware
Устанавливает контекст tenant для каждого запроса
"""

import os

import jwt
from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware

from src.utils.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


class TenantContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware для установки tenant context

    Извлекает tenant_id из JWT токена и устанавливает:
    1. request.state.tenant_id
    2. PostgreSQL session variable (для RLS)
    """

    def __init__(self, app):
        super().__init__(app)
        self.jwt_secret = os.getenv(
            "JWT_SECRET", "your-secret-key-change-in-production"
        )
        self.jwt_algorithm = "HS256"

    async def dispatch(self, request: Request, call_next):
        # Paths that don't require tenant context
        public_paths = [
            "/docs",
            "/openapi.json",
            "/health",
            "/api/tenants/register",  # Registration endpoint
            "/api/auth/login",
        ]

        # Skip tenant check for public paths
        if any(request.url.path.startswith(path) for path in public_paths):
            return await call_next(request)

        # Extract Authorization header
        auth_header = request.headers.get("Authorization")

        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=401, detail="Missing or invalid Authorization header"
            )

        token = auth_header.replace("Bearer ", "")

        try:
            # Decode JWT
            payload = jwt.decode(
                token, self.jwt_secret, algorithms=[self.jwt_algorithm]
            )

            tenant_id = payload.get("tenant_id")
            user_id = payload.get("user_id")
            user_role = payload.get("role", "viewer")

            if not tenant_id:
                raise HTTPException(
                    status_code=403, detail="Missing tenant_id in token"
                )

            # Set in request state
            request.state.tenant_id = tenant_id
            request.state.user_id = user_id
            request.state.user_role = user_role

            # Set PostgreSQL session variable (для RLS)
            # This will be done per-request in database connection
            request.state.postgres_session_vars = {
                "app.current_tenant_id": tenant_id,
                "app.current_user_id": user_id,
            }

            logger.debug(
                "Tenant context set", extra={"tenant_id": tenant_id, "user_id": user_id}
            )

            # Continue with request
            response = await call_next(request)

            return response

        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")
        except Exception as e:
            logger.error(
                "Tenant context error",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )
            raise HTTPException(status_code=500, detail="Internal server error")


def extract_tenant_id(request: Request) -> str:
    """
    Утилита для прямого извлечения tenant-id из заголовков (используется тестами).
    """
    tenant_id = request.headers.get("X-Tenant-ID")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-ID header missing")
    return tenant_id
