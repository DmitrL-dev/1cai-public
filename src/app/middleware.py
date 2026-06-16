"""
Middleware Configuration for 1C AI Stack

Настройка middleware в одном месте.
"""

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from src.config import settings
from src.middleware.security_headers import SecurityHeadersMiddleware
from src.middleware.ai_security_middleware import AISecurityMiddleware
from src.middleware.metrics_middleware import MetricsMiddleware

logger = logging.getLogger(__name__)


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
        expose_headers=["X-Request-ID", "X-RateLimit-Limit", "X-RateLimit-Remaining"],
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
    
    # JWT User Context
    try:
        from src.middleware.jwt_user_context import JWTUserContextMiddleware
        from src.modules.auth.api.dependencies import get_auth_service
        
        auth_service = get_auth_service()
        app.add_middleware(JWTUserContextMiddleware, auth_service=auth_service)
        logger.info("JWT middleware added")
    except Exception as e:
        logger.warning(f"Failed to add JWT middleware: {e}")
    
    logger.info("Middleware setup completed")
