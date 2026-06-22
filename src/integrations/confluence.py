from __future__ import annotations

import os
from typing import Any, Dict, Optional

from .base_client import BaseIntegrationClient
from .exceptions import IntegrationConfigError


class ConfluenceClient(BaseIntegrationClient):
    """Client for Confluence Cloud (v2 API)."""

    def __init__(
        self,
        *,
        base_url: str,
        token: str,
        transport: Optional[Any] = None,
    ) -> None:
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        super().__init__(base_url=base_url, headers=headers, transport=transport)

    @classmethod
    def from_env(cls, *, transport: Optional[Any] = None) -> "ConfluenceClient":
        base_url = os.getenv("BA_CONFLUENCE_BASE_URL")
        token = os.getenv("BA_CONFLUENCE_TOKEN")
        if not base_url or not token:
            raise IntegrationConfigError(
                "BA_CONFLUENCE_BASE_URL and BA_CONFLUENCE_TOKEN must be configured."
            )
        return cls(base_url=base_url, token=token, transport=transport)

    async def create_page(
        self,
        *,
        space_key: str,
        title: str,
        body: str,
        parent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "spaceId": space_key,
            "title": title,
            "body": {
                "representation": "storage",
                "value": body,
            },
        }
        if parent_id:
            payload["parentId"] = parent_id
        response = await self._request("POST", "/wiki/api/v2/pages", json=payload)
        return response.json()
