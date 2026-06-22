"""
Traceability Service
"""
from typing import Any, Dict, List

from src.infrastructure.logging.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


class TraceabilityService:
    """Service for Traceability & Compliance"""

    async def build_traceability_matrix(
        self,
        requirement_ids: List[str],
        include_code: bool = True,
        include_tests: bool = True,
        include_incidents: bool = True,
        use_graph: bool = True,
    ) -> Dict[str, Any]:
        """Build traceability matrix"""
        try:
            from src.ai.agents.business_analyst_agent import BusinessAnalystAgent

            agent = BusinessAnalystAgent()

            # Format requirements for compatibility
            requirements = [
                {"id": req_id, "title": req_id} for req_id in requirement_ids
            ]
            test_cases = []  # Found via graph

            return await agent.build_traceability_and_risks(
                requirements,
                test_cases,
                use_graph=use_graph,
            )
        except Exception as e:
            logger.error(f"Error building traceability matrix: {e}", exc_info=True)
            raise

    async def build_risk_register(
        self, requirement_ids: List[str], include_incidents: bool = True
    ) -> Dict[str, Any]:
        """Build risk register"""
        try:
            from src.ai.agents.traceability_with_graph import TraceabilityWithGraph
            from src.ai.code_analysis.graph import InMemoryCodeGraphBackend

            backend = InMemoryCodeGraphBackend()
            traceability = TraceabilityWithGraph(backend)

            return await traceability.build_risk_register(
                requirement_ids,
                include_incidents=include_incidents,
            )
        except Exception as e:
            logger.error(f"Error building risk register: {e}", exc_info=True)
            raise

    async def build_full_traceability_report(
        self, requirement_ids: List[str]
    ) -> Dict[str, Any]:
        """Build full traceability report"""
        try:
            from src.ai.agents.traceability_with_graph import TraceabilityWithGraph
            from src.ai.code_analysis.graph import InMemoryCodeGraphBackend

            backend = InMemoryCodeGraphBackend()
            traceability = TraceabilityWithGraph(backend)

            return await traceability.build_full_traceability_report(requirement_ids)
        except Exception as e:
            logger.error(f"Error building full report: {e}", exc_info=True)
            raise
