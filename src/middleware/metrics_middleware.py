
"""
Metrics Collection Middleware
Версия: 2.0.0

Улучшения:
- Улучшенная нормализация endpoints
- Обработка ошибок при сбое метрик
- Структурированное логирование
- Поддержка различных типов ID в путях
"""

import re
import time
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from src.utils.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger

# Try to import prometheus metrics (graceful fallback if not available)
try:
    from src.monitoring.prometheus_metrics import track_request

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.warning("Prometheus metrics not available, metrics collection disabled")


def normalize_endpoint(path: str) -> str:
    """
    Нормализация endpoint для метрик с input validation

    Best practice: Заменяем динамические части на плейсхолдеры
    для группировки метрик по типам endpoints, а не по конкретным ID

    Примеры:
    - /api/projects/123 → /api/projects/{id}
    - /api/users/abc-123-def → /api/users/{uuid}
    - /api/plugins/plugin_abc123 → /api/plugins/{plugin_id}
    """
    # Input validation
    if not isinstance(path, str):
        logger.warning(
            "Invalid path type in normalize_endpoint",
            extra={"path_type": type(path).__name__ if path else None},
        )
        return "/"

    # Limit path length (prevent DoS)
    max_path_length = 2000
    if len(path) > max_path_length:
        logger.warning(
            "Path too long in normalize_endpoint",
            extra={"path_length": len(path), "max_length": max_path_length},
        )
        path = path[:max_path_length]

    try:
        # UUID pattern (8-4-4-4-12 hex digits)
        path = re.sub(
            r"/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            "/{uuid}",
            path,
            flags=re.IGNORECASE,
        )

        # Plugin IDs (plugin_xxx)
        path = re.sub(r"/plugin_[0-9a-f]+", "/{plugin_id}", path, flags=re.IGNORECASE)

        # Numeric IDs
        path = re.sub(r"/\d+", "/{id}", path)

        # Hex IDs (32+ chars)
        path = re.sub(r"/[0-9a-f]{32,}", "/{hex_id}", path, flags=re.IGNORECASE)

        # Remove trailing slashes (except root)
        path = path.rstrip("/") or "/"

        return path
    except Exception as e:
        logger.error(
            "Error normalizing endpoint",
            extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "path": path if "path" in locals() else None,
                "path_length": (
                    len(path) if "path" in locals() and isinstance(path, str) else None
                ),
            },
            exc_info=True,
        )
        return "/"  # Return root on error


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware для сбора метрик запросов"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        return await metrics_middleware(request, call_next)


async def metrics_middleware(request: Request, call_next: Callable) -> Response:
    """
    Middleware для сбора Prometheus метрик со всех запросов с input validation

    Best practices:
    - Нормализация endpoints для группировки метрик
    - Graceful degradation при сбое метрик
    - Добавление timing headers для debugging
    - Обработка ошибок без влияния на основной запрос
    - Input validation для безопасности
    """
    # Input validation
    if not request or not hasattr(request, "url"):
        logger.error("Invalid request object in metrics_middleware")
        return await call_next(request)

    # Пропускаем метрики для самих метрик (избегаем рекурсии)
    request_path = str(request.url.path) if request.url.path else ""
    if request_path.startswith("/metrics"):
        return await call_next(request)

    # Start timer
    start_time = (
        time.perf_counter()
    )  # Используем perf_counter для более точного измерения

    try:
        # Process request
        response = await call_next(request)

        # Calculate duration
        duration = time.perf_counter() - start_time

        # Validate duration (prevent negative or invalid values)
        if not isinstance(duration, (int, float)) or duration < 0:
            logger.warning(
                "Invalid duration in metrics_middleware",
                extra={"duration": duration, "duration_type": type(duration).__name__},
            )
            duration = 0.0

        # Normalize endpoint (best practice: group by endpoint type, not specific IDs)
        endpoint = normalize_endpoint(request_path)

        # Track metrics (graceful fallback if Prometheus unavailable)
        if PROMETHEUS_AVAILABLE:
            try:
                # Get response size (if available) with validation
                content_length = response.headers.get("content-length", "0")
                try:
                    size = int(content_length) if content_length.isdigit() else 0
                    # Limit size (prevent overflow)
                    if size < 0 or size > 10**12:  # 1TB max
                        logger.warning(
                            "Invalid content length in metrics_middleware",
                            extra={"content_length": content_length},
                        )
                        size = 0
                except (ValueError, TypeError):
                    size = 0

                # Validate method
                method = str(request.method)[:10] if request.method else "UNKNOWN"

                # Validate status_code
                status_code = (
                    response.status_code if hasattr(response, "status_code") else 0
                )
                if (
                    not isinstance(status_code, int)
                    or status_code < 100
                    or status_code > 599
                ):
                    logger.warning(
                        "Invalid status code in metrics_middleware",
                        extra={"status_code": status_code},
                    )
                    status_code = 500

                track_request(
                    method=method,
                    endpoint=endpoint,
                    status_code=status_code,
                    duration=duration,
                    size=size,
                )
            except Exception as e:
                # Не прерываем запрос при ошибке метрик
                logger.warning(
                    "Failed to track metrics",
                    extra={"error": str(e), "error_type": type(e).__name__},
                    exc_info=True,
                )

        # Add metrics to response headers (best practice: inform client about performance)
        response.headers["X-Process-Time"] = f"{duration:.3f}"
        try:
            response.headers["X-Endpoint"] = endpoint.encode("ascii", "replace").decode(
                "ascii"
            )
        except Exception:
            pass

        return response

    except Exception as e:
        # Обрабатываем ошибки в middleware без влияния на запрос
        duration = time.perf_counter() - start_time

        # Track error metrics if available
        if PROMETHEUS_AVAILABLE:
            try:
                endpoint = normalize_endpoint(request.url.path)
                track_request(
                    method=request.method,
                    endpoint=endpoint,
                    status_code=500,  # Assume 500 for unhandled errors
                    duration=duration,
                    size=0,
                )
            except Exception:
                pass  # Ignore errors in error handling

        # Re-raise exception
        raise
