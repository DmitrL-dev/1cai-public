"""
Integration Service
"""
from typing import Any, Dict, List, Optional

from src.infrastructure.logging.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


class IntegrationService:
    """Service for Integrations (Jira, Confluence)"""

    async def sync_requirements_to_jira(
        self,
        requirement_ids: List[str],
        project_key: Optional[str] = None,
        issue_type: str = "Story",
        use_graph: bool = True,
    ) -> Dict[str, Any]:
        """Sync requirements to Jira"""
        try:
            from src.ai.agents.business_analyst_agent import BusinessAnalystAgent

            agent = BusinessAnalystAgent()

            return await agent.sync_requirements_to_jira(
                requirement_ids=requirement_ids,
                project_key=project_key,
                issue_type=issue_type,
                use_graph=use_graph,
            )
        except Exception as e:
            logger.error(f"Error syncing to Jira: {e}", exc_info=True)
            raise

    async def sync_bpmn_to_confluence(
        self,
        process_model: Dict[str, Any],
        space_key: Optional[str] = None,
        parent_page_id: Optional[str] = None,
        use_graph: bool = True,
    ) -> Dict[str, Any]:
        """Sync BPMN to Confluence"""
        try:
            from src.ai.agents.business_analyst_agent import BusinessAnalystAgent

            agent = BusinessAnalystAgent()

            return await agent.sync_bpmn_to_confluence(
                process_model=process_model,
                space_key=space_key,
                parent_page_id=parent_page_id,
                use_graph=use_graph,
            )
        except Exception as e:
            logger.error(f"Error syncing BPMN to Confluence: {e}", exc_info=True)
            raise

    async def sync_kpi_to_confluence(
        self,
        kpi_report: Dict[str, Any],
        space_key: Optional[str] = None,
        parent_page_id: Optional[str] = None,
        use_graph: bool = True,
    ) -> Dict[str, Any]:
        """Sync KPI to Confluence"""
        try:
            from src.ai.agents.business_analyst_agent import BusinessAnalystAgent

            agent = BusinessAnalystAgent()

            return await agent.sync_kpi_to_confluence(
                kpi_report=kpi_report,
                space_key=space_key,
                parent_page_id=parent_page_id,
                use_graph=use_graph,
            )
        except Exception as e:
            logger.error(f"Error syncing KPI to Confluence: {e}", exc_info=True)
            raise

    async def sync_traceability_to_confluence(
        self,
        traceability_report: Dict[str, Any],
        space_key: Optional[str] = None,
        parent_page_id: Optional[str] = None,
        use_graph: bool = True,
    ) -> Dict[str, Any]:
        """Sync Traceability to Confluence"""
        try:
            from src.ai.agents.business_analyst_agent import BusinessAnalystAgent

            agent = BusinessAnalystAgent()

            return await agent.sync_traceability_to_confluence(
                traceability_report=traceability_report,
                space_key=space_key,
                parent_page_id=parent_page_id,
                use_graph=use_graph,
            )
        except Exception as e:
            logger.error(
                f"Error syncing traceability to Confluence: {e}", exc_info=True
            )
            raise
