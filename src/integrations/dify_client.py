"""
Dify Platform Integration Client

Provides integration with Dify for:
- Agentic workflow orchestration
- Multi-agent coordination
- RAG pipeline management
- Prompt optimization
- LLMOps monitoring
"""

import logging
from enum import Enum
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class WorkflowType(Enum):
    """Types of Dify workflows"""
    CODE_GENERATION = "code_generation"
    CODE_REVIEW = "code_review"
    TEST_GENERATION = "test_generation"
    SECURITY_SCAN = "security_scan"
    ARCHITECTURE_ANALYSIS = "architecture_analysis"
    REQUIREMENTS_EXTRACTION = "requirements_extraction"
    LOG_ANALYSIS = "log_analysis"


class DifyClient:
    """
    Dify Platform integration client

    Features:
    - Workflow execution
    - Multi-agent orchestration
    - RAG pipeline
    - Prompt management
    - Model management
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.dify.ai/v1"
    ):
        """
        Initialize Dify client

        Args:
            api_key: Dify API key
            base_url: Dify API base URL
        """
        self.api_key = api_key
        self.base_url = base_url
        self.logger = logging.getLogger("dify_client")

        self.client = httpx.AsyncClient(
            base_url=base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            timeout=60.0
        )

    async def create_workflow(
        self,
        name: str,
        workflow_type: WorkflowType,
        steps: List[Dict[str, Any]],
        description: Optional[str] = None
    ) -> str:
        """
        Create a new workflow

        Args:
            name: Workflow name
            workflow_type: Type of workflow
            steps: Workflow steps configuration
            description: Optional description

        Returns:
            Workflow ID
        """
        try:
            response = await self.client.post(
                "/workflows",
                json={
                    "name": name,
                    "type": workflow_type.value,
                    "steps": steps,
                    "description": description or f"{name} workflow"
                }
            )
            response.raise_for_status()

            data = response.json()
            workflow_id = data.get("id")

            self.logger.info("Created workflow: %s", workflow_id)
            return workflow_id

        except Exception as e:
            self.logger.error("Failed to create workflow: %s", e)
            raise

    async def execute_workflow(
        self,
        workflow_id: str,
        inputs: Dict[str, Any],
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute a workflow

        Args:
            workflow_id: Workflow ID
            inputs: Input parameters
            user_id: Optional user ID for tracking

        Returns:
            Workflow execution result
        """
        try:
            response = await self.client.post(
                f"/workflows/{workflow_id}/run",
                json={
                    "inputs": inputs,
                    "user": user_id or "system"
                }
            )
            response.raise_for_status()

            result = response.json()

            self.logger.info(
                f"Workflow {workflow_id} executed successfully"
            )

            return {
                "status": "success",
                "outputs": result.get("data", {}),
                "execution_id": result.get("workflow_run_id"),
                "metadata": {
                    "workflow_id": workflow_id,
                    "elapsed_time": result.get("elapsed_time", 0)
                }
            }

        except httpx.HTTPStatusError as e:
            self.logger.error("Workflow execution failed: %s", e)
            return {
                "status": "error",
                "error": str(e),
                "outputs": {}
            }
        except Exception as e:
            self.logger.error("Unexpected error: %s", e)
            return {
                "status": "error",
                "error": str(e),
                "outputs": {}
            }

    async def create_rag_dataset(
        self,
        name: str,
        documents: List[Dict[str, Any]]
    ) -> str:
        """
        Create RAG dataset

        Args:
            name: Dataset name
            documents: List of documents to index

        Returns:
            Dataset ID
        """
        try:
            response = await self.client.post(
                "/datasets",
                json={
                    "name": name,
                    "indexing_technique": "high_quality"
                }
            )
            response.raise_for_status()

            dataset_id = response.json().get("id")

            # Upload documents
            for doc in documents:
                await self._upload_document(dataset_id, doc)

            self.logger.info("Created RAG dataset: %s", dataset_id)
            return dataset_id

        except Exception as e:
            self.logger.error("Failed to create dataset: %s", e)
            raise

    async def _upload_document(
        self,
        dataset_id: str,
        document: Dict[str, Any]
    ):
        """Upload document to dataset"""
        try:
            await self.client.post(
                f"/datasets/{dataset_id}/documents",
                json=document
            )
        except Exception as e:
            self.logger.error("Failed to upload document: %s", e)

    async def query_rag(
        self,
        dataset_id: str,
        query: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Query RAG dataset

        Args:
            dataset_id: Dataset ID
            query: Search query
            top_k: Number of results

        Returns:
            Retrieved documents
        """
        try:
            response = await self.client.post(
                f"/datasets/{dataset_id}/retrieve",
                json={
                    "query": query,
                    "top_k": top_k
                }
            )
            response.raise_for_status()

            results = response.json().get("records", [])

            return [
                {
                    "content": r.get("content"),
                    "score": r.get("score"),
                    "metadata": r.get("metadata", {})
                }
                for r in results
            ]

        except Exception as e:
            self.logger.error("RAG query failed: %s", e)
            return []

    async def get_workflow_status(
        self,
        execution_id: str
    ) -> Dict[str, Any]:
        """
        Get workflow execution status

        Args:
            execution_id: Execution ID

        Returns:
            Execution status
        """
        try:
            response = await self.client.get(
                f"/workflow-runs/{execution_id}"
            )
            response.raise_for_status()

            return response.json()

        except Exception as e:
            self.logger.error("Failed to get status: %s", e)
            return {"status": "unknown"}

    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()


# Workflow templates
WORKFLOW_TEMPLATES = {
    "code_generation": {
        "steps": [
            {
                "type": "llm",
                "name": "analyze_requirements",
                "model": "gpt-4",
                "prompt": "Analyze the following requirements..."
            },
            {
                "type": "llm",
                "name": "generate_code",
                "model": "gpt-4",
                "prompt": "Generate BSL code based on analysis..."
            },
            {
                "type": "code",
                "name": "validate_code",
                "code": "# Validation logic"
            }
        ]
    },
    "security_scan": {
        "steps": [
            {
                "type": "parallel",
                "tasks": [
                    {"type": "tool", "name": "sast_scan"},
                    {"type": "tool", "name": "dast_scan"},
                    {"type": "tool", "name": "cve_check"}
                ]
            },
            {
                "type": "llm",
                "name": "aggregate_results",
                "prompt": "Analyze security findings..."
            }
        ]
    }
}


# Singleton instance
_dify_client: Optional[DifyClient] = None


def get_dify_client(
    api_key: Optional[str] = None,
    base_url: Optional[str] = None
) -> DifyClient:
    """
    Get or create Dify client singleton

    Args:
        api_key: Dify API key
        base_url: Optional base URL

    Returns:
        DifyClient instance
    """
    global _dify_client

    if _dify_client is None:
        if not api_key:
            raise ValueError("API key required for first initialization")

        _dify_client = DifyClient(
            api_key=api_key,
            base_url=base_url or "https://api.dify.ai/v1"
        )

    return _dify_client


__all__ = [
    "DifyClient",
    "WorkflowType",
    "WORKFLOW_TEMPLATES",
    "get_dify_client"
]
