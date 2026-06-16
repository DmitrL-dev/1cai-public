
from __future__ import annotations

import os
from typing import Any, Dict, Optional

import httpx

from .exceptions import IntegrationConfigError, IntegrationError


class BaseIntegrationClient:
    """Common HTTP helper for integration clients."""

    def __init__(
        self,
        *,
        base_url: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 10.0,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ) -> None:
        if not base_url:
            raise IntegrationConfigError("Base URL is required for integration client.")
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers=headers or {},
            timeout=timeout,
            transport=transport,
        )

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        try:
            response = await self._client.request(method, url, **kwargs)
        except httpx.HTTPError as exc:  # pragma: no cover - network failure path
            raise IntegrationError(str(exc)) from exc
        if response.status_code >= 400:
            raise IntegrationError(
                f"Integration request failed ({response.status_code}): {response.text}"
            )
        return response

    async def aclose(self) -> None:
        await self._client.aclose()


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise IntegrationConfigError(f"Environment variable {name} is required.")
    return value
