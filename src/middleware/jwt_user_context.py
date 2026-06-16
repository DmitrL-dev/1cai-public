"""
JWT user-context middleware and authentication dependencies.

This middleware decodes and verifies the incoming Bearer token (or
``X-Service-Token``) using the configured ``AuthService`` and attaches the
**real** authenticated principal to ``request.state.user``. When no valid
credential is supplied the request is left UNAUTHENTICATED — no user is
fabricated. Route handlers opt in to enforcement via the ``require_auth`` /
``require_roles`` / ``require_permissions`` dependencies defined here, which
read the principal off ``request.state`` and raise ``401``/``403`` as needed.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import Depends, HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


def _extract_bearer_token(request: Request) -> Optional[str]:
    """Return the raw JWT from the ``Authorization: Bearer <token>`` header."""
    header = request.headers.get("Authorization") or request.headers.get(
        "authorization"
    )
    if not header:
        return None
    parts = header.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1].strip()
    return token or None


class JWTUserContextMiddleware(BaseHTTPMiddleware):
    """Attach the verified principal to ``request.state.user``.

    The middleware NEVER fabricates a user. If the token/service-token is
    absent or invalid, ``request.state.user`` is set to ``None`` and the
    request proceeds unauthenticated; protected routes then reject it via the
    ``require_auth`` dependency.
    """

    def __init__(self, app: ASGIApp, auth_service: Any = None):
        super().__init__(app)
        self.auth_service = auth_service

    def _resolve_auth_service(self) -> Any:
        if self.auth_service is not None:
            return self.auth_service
        # Lazy fallback so the middleware still works if constructed without
        # an explicit service (e.g. in some test harnesses).
        try:
            from src.modules.auth.api.dependencies import (
                get_auth_service as _get_auth_service,
            )

            self.auth_service = _get_auth_service()
        except Exception:  # noqa: BLE001
            try:
                from src.security.auth import get_auth_service as _get_auth_service

                self.auth_service = _get_auth_service()
            except Exception:  # noqa: BLE001
                self.auth_service = None
        return self.auth_service

    async def dispatch(self, request: Request, call_next):
        principal = None
        auth_service = self._resolve_auth_service()

        if auth_service is not None:
            token = _extract_bearer_token(request)
            try:
                if token:
                    principal = auth_service.decode_token(token)
                else:
                    service_token = request.headers.get("X-Service-Token")
                    if service_token:
                        principal = auth_service.authenticate_service_token(
                            service_token
                        )
            except HTTPException:
                # Invalid/expired token -> remain unauthenticated. We do NOT
                # raise here so that genuinely public routes still work; the
                # require_auth dependency enforces 401 on protected routes.
                principal = None
            except Exception:  # noqa: BLE001
                logger.warning("Token verification failed", exc_info=True)
                principal = None

        request.state.user = principal
        if principal is not None:
            request.state.user_id = getattr(principal, "user_id", None)
            request.state.username = getattr(principal, "username", None)
        else:
            # Explicitly clear any inherited identity. Do NOT set a fake user.
            request.state.user_id = None

        response = await call_next(request)
        return response


def _principal_from_request(request: Request) -> Optional[Any]:
    return getattr(request.state, "user", None)


async def require_auth(request: Request) -> Any:
    """FastAPI dependency: require an authenticated principal.

    Returns the verified principal (``CurrentUser``) attached by the
    middleware, or raises ``401`` when the request is unauthenticated.
    """
    principal = _principal_from_request(request)
    if principal is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return principal


# Alias kept for compatibility with code expecting a get_current_user dep that
# reads request.state (distinct from src.security.auth.get_current_user, which
# decodes the token itself via OAuth2PasswordBearer).
async def get_current_user(request: Request) -> Any:
    """Return the authenticated principal from ``request.state`` or raise 401."""
    return await require_auth(request)


def require_roles(*roles: str):
    """Dependency factory enforcing that the principal has one of ``roles``."""

    async def dependency(principal: Any = Depends(require_auth)) -> Any:
        if roles:
            has_role = getattr(principal, "has_role", None)
            ok = has_role(*roles) if callable(has_role) else False
            if not ok:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient role",
                )
        return principal

    return dependency


def require_permissions(*permissions: str):
    """Dependency factory enforcing that the principal has one permission."""

    async def dependency(principal: Any = Depends(require_auth)) -> Any:
        if permissions:
            has_permission = getattr(principal, "has_permission", None)
            ok = has_permission(*permissions) if callable(has_permission) else False
            if not ok:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions",
                )
        return principal

    return dependency


def principal_actor(principal: Any) -> Optional[str]:
    """Derive a stable actor identity string from an authenticated principal."""
    if principal is None:
        return None
    return getattr(principal, "username", None) or getattr(principal, "user_id", None)


__all__ = [
    "JWTUserContextMiddleware",
    "require_auth",
    "get_current_user",
    "require_roles",
    "require_permissions",
    "principal_actor",
]
