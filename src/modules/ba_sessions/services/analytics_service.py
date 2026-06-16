"""
Analytics Service
"""
from typing import Any, Dict, Optional

from src.infrastructure.logging.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


class AnalyticsService:
    """Service for Analytics & KPI"""

    async def generate_kpis(
        self,
        initiative_name: str,
        feature_id: Optional[str] = None,
        include_technical: bool = True,
        include_business: bool = True,
        use_graph: bool = True,
    ) -> Dict[str, Any]:
        """Generate KPIs"""
        try:
            from src.ai.agents.business_analyst_agent import (
                BusinessAnalystAgent,
            )

            agent = BusinessAnalystAgent()

            return await agent.design_kpi_blueprint(
                initiative_name=initiative_name,
                feature_id=feature_id,
                use_graph=use_graph,
            )
        except Exception as e:
            logger.error(f"Error generating KPIs: {e}", exc_info=True)
            raise
