from __future__ import annotations

import os
from typing import Any, Dict, Optional

from .base_client import BaseIntegrationClient
from .exceptions import IntegrationConfigError


class OneCDocflowClient(BaseIntegrationClient):
    """Client for 1C:Документооборот HTTP endpoints."""

    def __init__(
        self,
        *,
        base_url: str,
        token: str,
        transport: Optional[Any] = None,
    ) -> None:
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        super().__init__(base_url=base_url, headers=headers, transport=transport)

    @classmethod
    def from_env(cls, *, transport: Optional[Any] = None) -> "OneCDocflowClient":
        base_url = os.getenv("BA_1C_DOCFLOW_URL")
        token = os.getenv("BA_1C_DOCFLOW_TOKEN")
        if not base_url or not token:
            raise IntegrationConfigError(
                "BA_1C_DOCFLOW_URL and BA_1C_DOCFLOW_TOKEN must be configured."
            )
        return cls(base_url=base_url, token=token, transport=transport)

    async def register_document(
        self,
        *,
        title: str,
        description: str,
        category: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        body = {
            "title": title,
            "description": description,
            "category": category,
            "payload": payload or {},
        }
        response = await self._request("POST", "/api/documents", json=body)
        return response.json()
