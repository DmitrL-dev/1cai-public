from __future__ import annotations

import os
from typing import Any, Dict, Optional

from .base_client import BaseIntegrationClient
from .exceptions import IntegrationConfigError


class JiraClient(BaseIntegrationClient):
    """Client for Jira Cloud REST API (v3)."""

    ISSUE_ENDPOINT = "/rest/api/3/issue"

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
    def from_env(cls, *, transport: Optional[Any] = None) -> "JiraClient":
        base_url = os.getenv("BA_JIRA_BASE_URL")
        token = os.getenv("BA_JIRA_TOKEN")
        if not base_url or not token:
            raise IntegrationConfigError(
                "BA_JIRA_BASE_URL and BA_JIRA_TOKEN must be configured."
            )
        return cls(base_url=base_url, token=token, transport=transport)

    async def create_issue(
        self,
        *,
        project_key: str,
        summary: str,
        description: str,
        issue_type: str = "Task",
        fields: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload = {
            "fields": {
                "project": {"key": project_key},
                "summary": summary,
                "description": description,
                "issuetype": {"name": issue_type},
            }
        }
        if fields:
            payload["fields"].update(fields)
        response = await self._request("POST", self.ISSUE_ENDPOINT, json=payload)
        return response.json()

    async def update_issue(self, issue_key: str, fields: Dict[str, Any]) -> None:
        if not fields:
            return
        await self._request(
            "PUT",
            f"{self.ISSUE_ENDPOINT}/{issue_key}",
            json={"fields": fields},
        )
