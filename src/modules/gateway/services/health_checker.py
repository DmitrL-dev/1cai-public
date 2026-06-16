"""
Service Health Checker
"""
import asyncio
import time
from datetime import datetime
from typing import Any, Dict

import httpx

from src.infrastructure.logging.structured_logging import StructuredLogger
from src.modules.gateway.domain.config import SERVICES_CONFIG
from src.modules.gateway.domain.models import ServiceHealthResponse

logger = StructuredLogger(__name__).logger


class ServiceHealthChecker:
    """Class for checking service health"""

    def __init__(self):
        self.services_status = {}
        self.last_check_times = {}

    async def check_service_health(self, service_name: str, config: Dict[str, Any]) -> ServiceHealthResponse:
        """Check health of a specific service with input validation"""
        # Input validation
        if not service_name or not isinstance(service_name, str):
            logger.warning(
                "Invalid service_name in check_service_health",
                extra={"service_name_type": (
                    type(service_name).__name__ if service_name else None)},
            )
            return ServiceHealthResponse(
                service_name=service_name or "unknown",
                status="unknown",
                response_time_ms=0,
                last_check=datetime.now(),
                error="Invalid service name",
            )

        if not config or not isinstance(config, dict):
            logger.warning(
                "Invalid config in check_service_health",
                extra={"config_type": type(config).__name__ if config else None},
            )
            return ServiceHealthResponse(
                service_name=service_name,
                status="unknown",
                response_time_ms=0,
                last_check=datetime.now(),
                error="Invalid config",
            )

        # Validate required config fields
        if "url" not in config or "health_endpoint" not in config:
            logger.warning(
                "Missing required config fields in check_service_health",
                extra={
                    "service_name": service_name,
                    "config_keys": list(config.keys()),
                },
            )
            return ServiceHealthResponse(
                service_name=service_name,
                status="unknown",
                response_time_ms=0,
                last_check=datetime.now(),
                error="Missing required config fields",
            )

        start_time = time.time()

        try:
            timeout = config.get("timeout", 30.0)
            if not isinstance(timeout, (int, float)) or timeout <= 0:
                timeout = 30.0  # Default timeout

            async with httpx.AsyncClient(timeout=timeout) as client:
                health_url = f"{config['url']}{config['health_endpoint']}"
                logger.debug(
                    "Checking health for service",
                    extra={"service_name": service_name, "health_url": health_url},
                )

                response = await client.get(health_url)

                response_time = (time.time() - start_time) * 1000

                if response.status_code == 200:
                    status = "healthy"
                    error = None
                else:
                    status = "unhealthy"
                    error = f"HTTP {response.status_code}"

        except httpx.TimeoutException as e:
            logger.warning(
                "Timeout checking health for service",
                extra={
                    "service_name": service_name,
                    "timeout": timeout,
                    "error_type": "TimeoutException",
                },
            )
            status = "unhealthy"
            error = "Timeout"
            response_time = timeout * 1000

        except httpx.ConnectError as e:
            logger.warning(
                "Connection error checking health for service",
                extra={
                    "service_name": service_name,
                    "url": config.get("url"),
                    "error_type": "ConnectError",
                },
            )
            status = "unhealthy"
            error = "Connection failed"
            response_time = (time.time() - start_time) * 1000

        except Exception as e:
            logger.error(
                "Unexpected error checking health for service",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "service_name": service_name,
                },
                exc_info=True,
            )
            status = "unhealthy"
            error = str(e)
            response_time = (time.time() - start_time) * 1000

        service_status = ServiceHealthResponse(
            service_name=service_name,
            status=status,
            response_time_ms=response_time,
            last_check=datetime.now(),
            error=error,
        )

        self.services_status[service_name] = service_status
        self.last_check_times[service_name] = datetime.now()

        return service_status

    async def check_all_services(self) -> Dict[str, ServiceHealthResponse]:
        """Check health of all services"""
        tasks = []
        for service_name, config in SERVICES_CONFIG.items():
            task = self.check_service_health(service_name, config)
            tasks.append(task)

        # Optimized: Use asyncio.gather with timeout (best practice)
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=30.0,  # Timeout for all health checks
            )
        except asyncio.TimeoutError:
            logger.error(
                "Timeout checking health of all services",
                extra={"services_count": len(tasks), "timeout": 30.0},
            )
            # Return partial results
            results = [{"error": "timeout"} for _ in tasks]

        health_status = {}
        for i, (service_name, _) in enumerate(SERVICES_CONFIG.items()):
            if isinstance(results[i], Exception):
                health_status[service_name] = ServiceHealthResponse(
                    service_name=service_name,
                    status="unknown",
                    last_check=datetime.now(),
                    error=str(results[i]),
                )
            else:
                health_status[service_name] = results[i]

        return health_status
