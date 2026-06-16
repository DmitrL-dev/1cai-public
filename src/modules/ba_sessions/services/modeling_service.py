"""
Modeling Service
"""
from typing import Any, Dict, List, Optional

from src.infrastructure.logging.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


class ModelingService:
    """Service for Process & Journey Modelling"""

    async def generate_process_model(
        self,
        description: str,
        requirement_id: Optional[str] = None,
        format: str = "mermaid",
        use_graph: bool = True,
    ) -> Dict[str, Any]:
        """Generate process model"""
        try:
            from src.ai.agents.business_analyst_agent import (
                BusinessAnalystAgent,
            )

            agent = BusinessAnalystAgent()

            return await agent.generate_process_model(
                description=description,
                requirement_id=requirement_id,
                format=format,
                use_graph=use_graph,
            )
        except Exception as e:
            logger.error(f"Error generating process model: {e}", exc_info=True)
            raise

    async def generate_journey_map(
        self,
        journey_description: str,
        stages: Optional[List[str]] = None,
        format: str = "mermaid",
        use_graph: bool = True,
    ) -> Dict[str, Any]:
        """Generate journey map"""
        try:
            from src.ai.agents.business_analyst_agent import (
                BusinessAnalystAgent,
            )

            agent = BusinessAnalystAgent()

            return await agent.generate_journey_map(
                journey_description=journey_description,
                stages=stages,
                format=format,
                use_graph=use_graph,
            )
        except Exception as e:
            logger.error(f"Error generating journey map: {e}", exc_info=True)
            raise

    async def validate_process_model(self, process_model: Dict[str, Any]) -> Dict[str, Any]:
        """Validate process model"""
        try:
            from src.ai.agents.business_analyst_agent import (
                BusinessAnalystAgent,
            )

            agent = BusinessAnalystAgent()

            return await agent.validate_process_model(process_model)
        except Exception as e:
            logger.error(f"Error validating process model: {e}", exc_info=True)
            raise
