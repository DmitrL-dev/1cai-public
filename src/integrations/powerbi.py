
from __future__ import annotations

import os
from typing import Any, Dict, Optional

from .base_client import BaseIntegrationClient
from .exceptions import IntegrationConfigError


class PowerBIClient(BaseIntegrationClient):
    """Client for Power BI REST API (dataset refresh)."""

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
    def from_env(cls, *, transport: Optional[Any] = None) -> "PowerBIClient":
        base_url = os.getenv("BA_POWERBI_BASE_URL", "https://api.powerbi.com")
        token = os.getenv("BA_POWERBI_TOKEN")
        if not token:
            raise IntegrationConfigError("BA_POWERBI_TOKEN must be configured.")
        return cls(base_url=base_url, token=token, transport=transport)

    async def trigger_refresh(
        self, workspace_id: str, dataset_id: str
    ) -> Dict[str, Any]:
        endpoint = f"/v1.0/myorg/groups/{workspace_id}/datasets/{dataset_id}/refreshes"
        response = await self._request("POST", endpoint, json={})
        return response.json()
