"""
Proxy Service
"""
from typing import Any, Dict, Optional

import httpx
from fastapi import HTTPException

from src.infrastructure.logging.structured_logging import StructuredLogger
from src.modules.gateway.domain.config import SERVICES_CONFIG

logger = StructuredLogger(__name__).logger


class ProxyService:
    """Service for proxying requests to microservices"""

    def __init__(self) -> None:
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0))

    async def proxy_request(
        self,
        service: str,
        endpoint: str,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> httpx.Response:
        """Proxy request to service with input validation"""
        # Input validation
        if not service or not isinstance(service, str):
            logger.warning(
                "Invalid service in proxy_request",
                extra={"service_type": type(service).__name__ if service else None},
            )
            raise HTTPException(
                status_code=400,
                detail="Service name is required and must be a non-empty string",
            )

        if not endpoint or not isinstance(endpoint, str):
            logger.warning(
                "Invalid endpoint in proxy_request",
                extra={"endpoint_type": type(endpoint).__name__ if endpoint else None},
            )
            raise HTTPException(
                status_code=400,
                detail="Endpoint is required and must be a non-empty string",
            )

        # Validate endpoint length (prevent DoS)
        max_endpoint_length = 2000
        if len(endpoint) > max_endpoint_length:
            logger.warning(
                "Endpoint too long in proxy_request",
                extra={
                    "endpoint_length": len(endpoint),
                    "max_length": max_endpoint_length,
                },
            )
            raise HTTPException(
                status_code=400,
                detail=f"Endpoint too long. Maximum length: {max_endpoint_length} characters",
            )

        # Validate method
        valid_methods = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]
        method_upper = method.upper() if method else "GET"
        if method_upper not in valid_methods:
            logger.warning(
                "Invalid method in proxy_request",
                extra={"method": method, "valid_methods": valid_methods},
            )
            raise HTTPException(
                status_code=400,
                detail=f"Invalid HTTP method: {method}. Valid methods: {', '.join(valid_methods)}",
            )

        if service not in SERVICES_CONFIG:
            logger.warning(
                f"Service not found: {service}",
                extra={
                    "service": service,
                    "available_services": list(SERVICES_CONFIG.keys()),
                },
            )
            raise HTTPException(
                status_code=404, detail=f"Service '{service}' not found")

        service_config = SERVICES_CONFIG[service]

        # Input validation (best practice: sanitize inputs)
        if endpoint and not endpoint.startswith("/"):
            endpoint = "/" + endpoint

        # Sanitize endpoint path (prevent path traversal)
        endpoint_original = endpoint
        endpoint = endpoint.replace("..", "").replace("//", "/")

        if endpoint != endpoint_original:
            logger.warning(
                "Endpoint sanitized (path traversal attempt?)",
                extra={"original": endpoint_original, "sanitized": endpoint},
            )

        # Prepare URL
        url = f"{service_config['url']}{endpoint}"

        # Prepare headers
        request_headers = headers or {}
        request_headers.update(
            {"X-Gateway-Request": "true", "X-Forwarded-For": "1C-AI-Gateway"})

        # Proxy request with improved error handling
        try:
            response = await self.client.request(
                method=method,
                url=url,
                headers=request_headers,
                json=data if method.upper() in ["POST", "PUT", "PATCH"] else None,
                params=params,
                timeout=service_config["timeout"],
            )

            return response

        except httpx.TimeoutException as e:
            logger.error(
                f"Timeout calling service '{service}': {e}",
                extra={
                    "service": service,
                    "endpoint": endpoint,
                    "method": method,
                    "timeout": service_config.get("timeout", 30.0),
                    "error_type": "TimeoutException",
                },
            )
            raise HTTPException(
                status_code=504, detail=f"Timeout calling service '{service}'")
        except httpx.ConnectError as e:
            logger.error(
                f"Connection error calling service '{service}': {e}",
                extra={
                    "service": service,
                    "endpoint": endpoint,
                    "method": method,
                    "url": url,
                    "error_type": "ConnectError",
                },
            )
            raise HTTPException(
                status_code=503, detail=f"Service '{service}' unavailable")
        except httpx.HTTPStatusError as e:
            logger.warning(
                f"HTTP error {e.response.status_code} from service '{service}'",
                extra={
                    "service": service,
                    "endpoint": endpoint,
                    "method": method,
                    "status_code": e.response.status_code,
                    "response_preview": e.response.text[:200],
                    "error_type": "HTTPStatusError",
                },
            )
            # Propagate status code from upstream service
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Error from service '{service}': {e.response.text[:200]}",
            )
        except Exception as e:
            logger.error(
                "Unexpected error proxying to service",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "service": service,
                    "endpoint": endpoint,
                    "method": method,
                    "url": url,
                },
                exc_info=True,
            )
            raise HTTPException(
                status_code=500, detail=f"Error proxying to service '{service}'")
