"""
CI/CD Integration Client

Supports:
- GitLab CI
- GitHub Actions
"""

import logging
import aiohttp
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class CIPlatform(Enum):
    """CI/CD platforms"""
    GITLAB = "gitlab"
    GITHUB = "github"


class CICDClient:
    """
    CI/CD integration client

    Supports GitLab CI and GitHub Actions
    """

    def __init__(
        self,
        platform: CIPlatform,
        api_token: str,
        base_url: Optional[str] = None
    ):
        """
        Initialize CI/CD client

        Args:
            platform: CI/CD platform
            api_token: API token
            base_url: Optional base URL for self-hosted instances
        """
        self.platform = platform
        self.api_token = api_token
        self.base_url = base_url or self._get_default_url(platform)
        self.logger = logging.getLogger("cicd_client")

    def _get_default_url(self, platform: CIPlatform) -> str:
        """Get default API URL for platform"""
        if platform == CIPlatform.GITLAB:
            return "https://gitlab.com/api/v4"
        elif platform == CIPlatform.GITHUB:
            return "https://api.github.com"
        return ""

    async def trigger_pipeline(
        self,
        project_id: str,
        ref: str = "main",
        variables: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Trigger CI/CD pipeline

        Args:
            project_id: Project/repository ID (GitLab: ID, GitHub: owner/repo)
            ref: Git ref (branch/tag)
            variables: Pipeline variables
        """
        async with aiohttp.ClientSession() as session:
            if self.platform == CIPlatform.GITLAB:
                url = f"{self.base_url}/projects/{project_id}/pipeline"
                headers = {"PRIVATE-TOKEN": self.api_token}
                data = {"ref": ref}
                if variables:
                    for k, v in variables.items():
                        data[f"variables[{k}]"] = v
                
                async with session.post(url, headers=headers, data=data) as resp:
                    if resp.status >= 400:
                        text = await resp.text()
                        self.logger.error(f"GitLab API Error: {text}")
                        resp.raise_for_status()
                    return await resp.json()

            elif self.platform == CIPlatform.GITHUB:
                # GitHub requires workflow_id. For now, we assume 'main.yml' or passed in variables
                workflow_id = variables.get("workflow_id", "main.yml") if variables else "main.yml"
                url = f"{self.base_url}/repos/{project_id}/actions/workflows/{workflow_id}/dispatches"
                headers = {
                    "Authorization": f"Bearer {self.api_token}",
                    "Accept": "application/vnd.github.v3+json"
                }
                data = {"ref": ref}
                if variables:
                    # GitHub inputs must be strings
                    inputs = {k: str(v) for k, v in variables.items() if k != "workflow_id"}
                    if inputs:
                        data["inputs"] = inputs

                async with session.post(url, headers=headers, json=data) as resp:
                    if resp.status >= 400:
                        text = await resp.text()
                        self.logger.error(f"GitHub API Error: {text}")
                        resp.raise_for_status()
                    
                    # GitHub returns 204 No Content on success
                    return {
                        "status": "triggered", 
                        "web_url": f"https://github.com/{project_id}/actions"
                    }
        return {}

    async def get_pipeline_status(
        self,
        project_id: str,
        pipeline_id: str
    ) -> Dict[str, Any]:
        """Get pipeline status"""
        async with aiohttp.ClientSession() as session:
            if self.platform == CIPlatform.GITLAB:
                url = f"{self.base_url}/projects/{project_id}/pipelines/{pipeline_id}"
                headers = {"PRIVATE-TOKEN": self.api_token}
                
                async with session.get(url, headers=headers) as resp:
                    resp.raise_for_status()
                    return await resp.json()

            elif self.platform == CIPlatform.GITHUB:
                url = f"{self.base_url}/repos/{project_id}/actions/runs/{pipeline_id}"
                headers = {
                    "Authorization": f"Bearer {self.api_token}",
                    "Accept": "application/vnd.github.v3+json"
                }
                
                async with session.get(url, headers=headers) as resp:
                    resp.raise_for_status()
                    data = await resp.json()
                    return {
                        "id": str(data.get("id")),
                        "status": data.get("status"),
                        "conclusion": data.get("conclusion"),
                        "web_url": data.get("html_url")
                    }
        return {}

    async def get_test_results(
        self,
        project_id: str,
        pipeline_id: str
    ) -> Dict[str, Any]:
        """Get test results from pipeline"""
        async with aiohttp.ClientSession() as session:
            if self.platform == CIPlatform.GITLAB:
                url = f"{self.base_url}/projects/{project_id}/pipelines/{pipeline_id}/test_report"
                headers = {"PRIVATE-TOKEN": self.api_token}
                
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 404:
                        return {"total": 0, "error": "No test report found"}
                    resp.raise_for_status()
                    return await resp.json()

            elif self.platform == CIPlatform.GITHUB:
                # GitHub doesn't have a direct "test report" API for runs.
                # We would need to parse logs or artifacts.
                # Returning stub for now.
                return {
                    "total": 0,
                    "status": "not_supported_for_github",
                    "note": "GitHub Actions requires artifact parsing for test results"
                }
        return {}


def get_cicd_client(
    platform: str,
    api_token: str,
    base_url: Optional[str] = None
) -> CICDClient:
    """
    Create CI/CD client

    Args:
        platform: "gitlab" or "github"
        api_token: API token
        base_url: Optional base URL

    Returns:
        CICDClient instance
    """
    platform_enum = CIPlatform(platform.lower())
    return CICDClient(platform_enum, api_token, base_url)


__all__ = ["CIPlatform", "CICDClient", "get_cicd_client"]
