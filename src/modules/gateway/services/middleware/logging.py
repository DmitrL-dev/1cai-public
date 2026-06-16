"""
Request Logging Middleware
"""
import time
from typing import Any

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from src.infrastructure.logging.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for request logging"""

    def __init__(self, app: Any) -> None:
        super().__init__(app)
        self.request_stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "response_times": [],
            "service_calls": {},
        }

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        start_time = time.time()

        # Log incoming request
        logger.info(
            f"Incoming request: {request.method} {request.url.path}",
            extra={
                "method": request.method,
                "path": request.url.path,
                "query_params": str(request.url.query) if request.url.query else None,
            },
        )

        self.request_stats["total_requests"] += 1

        try:
            response = await call_next(request)

            # Calculate response time
            response_time = (time.time() - start_time) * 1000
            self.request_stats["response_times"].append(response_time)

            # Response statistics
            if response.status_code < 400:
                self.request_stats["successful_requests"] += 1
            else:
                self.request_stats["failed_requests"] += 1

            # Log response
            logger.info(
                f"Response: {response.status_code}, time: {response_time:.2f}ms",
                extra={
                    "status_code": response.status_code,
                    "response_time_ms": response_time,
                    "method": request.method,
                    "path": request.url.path,
                },
            )

            return response

        except Exception as e:
            logger.error(
                "Error processing request",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "endpoint": request.url.path,
                    "method": request.method,
                },
                exc_info=True,
            )
            self.request_stats["failed_requests"] += 1
            raise
