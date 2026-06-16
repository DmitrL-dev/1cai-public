"""
FastAPI Application Factory for 1C AI Stack

Централизованное создание и конфигурация приложения.
"""

import logging
import os
import time
import uuid

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from prometheus_fastapi_instrumentator import Instrumentator

from src.app.lifespan import lifespan
from src.app.middleware import setup_middleware
from src.app.routers import register_routers
from src.config import settings
from src.infrastructure.logging.structured_logging import (
    StructuredLogger,
    set_request_context,
)
from src.services.health_checker import get_health_checker

try:
    from src.utils.error_handling import register_error_handlers
except ImportError:
    register_error_handlers = None  # type: ignore

logger = logging.getLogger(__name__)
structured_logger = StructuredLogger(__name__)


def create_app() -> FastAPI:
    """
    Создаёт и конфигурирует FastAPI приложение.

    Returns:
        FastAPI: Настроенное приложение
    """
    app = FastAPI(
        title="1C AI Stack API",
        description="AI-Powered Development Platform для 1C - WITH SECURITY",
        version="2.2.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        openapi_tags=[
            {"name": "Health", "description": "Health check endpoints"},
            {"name": "Monitoring", "description": "Monitoring and metrics"},
            {"name": "API", "description": "Core API endpoints"},
        ],
        swagger_ui_parameters={
            "displayRequestDuration": True,
            "filter": True,
            "tryItOutEnabled": True,
        },
    )

    # Prometheus metrics
    try:
        Instrumentator().instrument(app).expose(app, include_in_schema=False)
    except Exception as e:
        logger.warning(f"Failed to instrument Prometheus metrics: {e}")

    # Error handlers
    try:
        if register_error_handlers:
            register_error_handlers(app)
    except Exception as e:
        logger.warning(f"Failed to register error handlers: {e}")

    # Middleware
    setup_middleware(app)

    # Logging middleware
    _add_logging_middleware(app)

    # Legacy API redirect
    if settings.enable_legacy_api_redirect:
        _add_legacy_redirect(app)

    # Routers
    api_v1_router = APIRouter(
        prefix="/api/v1",
        tags=["API v1"],
        default_response_class=JSONResponse,
    )
    register_routers(app, api_v1_router)

    # MCP Server mount
    _mount_mcp(app)

    # Static files
    _mount_static(app)

    # Health endpoint
    @app.get("/health", tags=["Health"], summary="Health check endpoint")
    async def health_check():
        health_checker = get_health_checker()
        return await health_checker.check_all()

    # Root endpoint
    @app.get("/", tags=["API"], summary="API root endpoint")
    async def root():
        return {
            "name": "1C AI Stack API",
            "version": "2.2.0",
            "status": "running",
            "security": "Agents Rule of Two Enabled",
            "integrations": {
                "mcp": "/mcp (Cursor/VSCode)",
                "telegram": "Available via bot",
                "wiki": "/wiki-ui (Web Interface)",
                "archi": "/api/v1/archi (ArchiMate Export/Import)",
            },
            "docs": "/docs",
            "redoc": "/redoc",
            "health": "/health",
            "openapi": "/openapi.json",
        }

    return app


def _add_logging_middleware(app: FastAPI):
    """Добавляет middleware для логирования запросов."""

    @app.middleware("http")
    async def logging_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        start_time = time.time()

        set_request_context(request_id=request_id)
        request.state.request_id = request_id

        user_id = getattr(request.state, "user_id", None)
        tenant_id = getattr(request.state, "tenant_id", None)
        if user_id:
            set_request_context(user_id=user_id, tenant_id=tenant_id)

        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id

            process_time = time.time() - start_time
            structured_logger.info(
                f"{request.method} {request.url.path}",
                request_id=request_id,
                user_id=user_id,
                method=request.method,
                path=str(request.url.path),
                status_code=response.status_code,
                process_time_ms=round(process_time * 1000, 2),
            )
            return response
        except Exception as e:
            process_time = time.time() - start_time
            structured_logger.error(
                f"Request failed: {request.method} {request.url.path}",
                request_id=request_id,
                error=str(e),
                process_time_ms=round(process_time * 1000, 2),
            )
            raise


def _add_legacy_redirect(app: FastAPI):
    """Добавляет редирект для legacy API путей."""
    from fastapi import status
    from fastapi.responses import RedirectResponse

    @app.middleware("http")
    async def legacy_api_redirect(request: Request, call_next):
        path = request.url.path or ""
        if path.startswith("/api/") and not path.startswith("/api/v1"):
            trimmed = path[5:]  # Remove "/api/"
            new_path = f"/api/v1/{trimmed}" if trimmed else "/api/v1"
            new_url = request.url.replace(path=new_path)
            logger.warning(f"Legacy API redirect: {path} -> {new_path}")
            return RedirectResponse(
                url=str(new_url),
                status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            )
        return await call_next(request)


def _mount_mcp(app: FastAPI):
    """Монтирует MCP сервер."""
    try:
        from src.ai.mcp.server import app as mcp_app

        app.mount("/mcp", mcp_app)
        logger.info("MCP server mounted at /mcp")
    except ImportError:
        logger.info("MCP server not available")
    except Exception as e:
        logger.warning(f"Failed to mount MCP server: {e}")


def _mount_static(app: FastAPI):
    """Монтирует статические файлы."""
    try:
        wiki_static_path = os.path.join(os.path.dirname(__file__), "../static/wiki")
        if os.path.exists(wiki_static_path):
            app.mount(
                "/wiki-ui",
                StaticFiles(directory=wiki_static_path, html=True),
                name="wiki-ui",
            )
            logger.info(f"Wiki UI mounted at /wiki-ui")
    except Exception as e:
        logger.warning(f"Failed to mount Wiki UI: {e}")
