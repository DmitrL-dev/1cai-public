
"""
Security Headers Middleware
Версия: 2.1.0

Улучшения:
- Structured logging
- Улучшена обработка ошибок
- Input validation для CSP policy

Features:
- Content Security Policy (CSP)
- XSS Protection
- Clickjacking Protection
- MIME Sniffing Protection
- HSTS (HTTP Strict Transport Security)
- Referrer Policy
- Permissions Policy
"""

import os
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from src.utils.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware для добавления security headers ко всем ответам"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        return await security_headers_middleware(request, call_next)


async def security_headers_middleware(
    request: Request, call_next: Callable
) -> Response:
    """
    Add security headers to all responses

    Headers:
    - Content-Security-Policy: Prevents XSS
    - X-Frame-Options: Prevents clickjacking
    - X-Content-Type-Options: Prevents MIME sniffing
    - Strict-Transport-Security: Forces HTTPS
    - Referrer-Policy: Controls referrer info
    - Permissions-Policy: Controls browser features
    """
    try:
        response = await call_next(request)

        # Content Security Policy (CSP)
        # Best practice: Strict CSP, allow only necessary sources
        # Added cdn.jsdelivr.net for Swagger UI
        csp_policy = os.getenv(
            "CSP_POLICY",
            "default-src 'self'; "
            # Allow Swagger UI scripts
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; " # Allow Swagger UI styles
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            # Allow WebSocket (for local dev and Kasperski)
            "connect-src 'self' https://api.openai.com https://api.deepseek.com ws: wss:; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self';",
        )

        # Validate CSP policy length (prevent DoS)
        if len(csp_policy) > 2000:
            logger.warning(
                "CSP policy too long, truncating",
                extra={"csp_length": len(csp_policy), "max_length": 2000},
            )
            csp_policy = csp_policy[:2000]

        response.headers["Content-Security-Policy"] = csp_policy

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # Prevent MIME sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Force HTTPS (only in production)
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        # Referrer policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions policy (disable unnecessary features)
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), interest-cohort=()"
        )

        # XSS Protection (legacy, but doesn't hurt)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        logger.debug(
            "Security headers added",
            extra={
                "path": str(request.url.path),
                "method": request.method,
                "has_csp": "Content-Security-Policy" in response.headers,
            },
        )

        return response
    except Exception as e:
        logger.error(
            "Error in security headers middleware",
            extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "path": str(request.url.path) if request else None,
            },
            exc_info=True,
        )
        # Don't attempt to call next handler again (response pipeline may be closed)
        raise
