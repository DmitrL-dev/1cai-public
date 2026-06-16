import logging
import os
from typing import Any, Dict, List, Optional
import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class ODataConfig(BaseModel):
    base_url: str
    username: str
    password: str
    timeout: float = 30.0

class OneCODataClient:
    """
    Async client for 1C:Enterprise OData Interface.
    Allows reading catalogs, documents, and metadata.
    """

    def __init__(self, config: Optional[ODataConfig] = None):
        self.config = config or self._load_config_from_env()
        self.client = httpx.AsyncClient(
            base_url=self.config.base_url,
            auth=(self.config.username, self.config.password),
            timeout=self.config.timeout,
            headers={"Accept": "application/json"}
        )

    def _load_config_from_env(self) -> ODataConfig:
        return ODataConfig(
            base_url=os.getenv("ONEC_ODATA_URL", "http://localhost/base/odata/standard.odata"),
            username=os.getenv("ONEC_USERNAME", "Administrator"),
            password=os.getenv("ONEC_PASSWORD", "")
        )

    async def close(self):
        await self.client.aclose()

    async def get_metadata(self) -> str:
        """
        Fetches the $metadata XML document.
        """
        try:
            response = await self.client.get("/$metadata")
            response.raise_for_status()
            return response.text
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch metadata: {e}")
            raise

    async def get_catalog(self, catalog_name: str, top: int = 100, select: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Fetches items from a Catalog.
        Example: catalog_name="Catalog_Товары"
        """
        params = {"$top": top, "$format": "json"}
        if select:
            params["$select"] = ",".join(select)

        try:
            # Note: 1C OData entity names are usually like Catalog_Name
            entity_name = f"Catalog_{catalog_name}" if not catalog_name.startswith("Catalog_") else catalog_name
            
            response = await self.client.get(f"/{entity_name}", params=params)
            response.raise_for_status()
            data = response.json()
            return data.get("value", [])
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch catalog {catalog_name}: {e}")
            raise

    async def post_document(self, doc_name: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Creates a new Document.
        Example: doc_name="Document_ЗаказКлиента"
        """
        try:
            entity_name = f"Document_{doc_name}" if not doc_name.startswith("Document_") else doc_name
            
            response = await self.client.post(f"/{entity_name}", json=data, params={"$format": "json"})
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to post document {doc_name}: {e}")
            raise

    async def execute_query(self, query: str) -> List[Dict[str, Any]]:
        """
        Executes a query via a custom HTTP service (if available).
        This requires the 'QueryConsole' pattern to be implemented on 1C side.
        """
        # Placeholder for future integration with QueryConsole
        logger.warning("execute_query is not yet implemented on 1C side")
        return []
