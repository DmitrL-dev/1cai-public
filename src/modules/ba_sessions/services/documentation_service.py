"""
Documentation Service
"""
from typing import Any, Dict

from src.infrastructure.logging.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


class DocumentationService:
    """Service for Documentation & Enablement"""

    async def generate_enablement_plan(
        self,
        feature_name: str,
        audience: str = "BA+Dev+QA",
        include_examples: bool = True,
        use_graph: bool = True,
    ) -> Dict[str, Any]:
        """Generate enablement plan"""
        try:
            from src.ai.agents.business_analyst_agent import BusinessAnalystAgent

            agent = BusinessAnalystAgent()

            return await agent.build_enablement_plan(
                feature_name=feature_name,
                audience=audience,
                include_examples=include_examples,
                use_graph=use_graph,
            )
        except Exception as e:
            logger.error(f"Error generating enablement plan: {e}", exc_info=True)
            raise

    async def generate_guide(
        self,
        topic: str,
        format: str = "markdown",
        include_code_examples: bool = True,
        use_graph: bool = True,
    ) -> Dict[str, Any]:
        """Generate guide"""
        try:
            from src.ai.agents.business_analyst_agent import BusinessAnalystAgent

            agent = BusinessAnalystAgent()

            return await agent.generate_guide(
                topic=topic,
                format=format,
                include_code_examples=include_code_examples,
                use_graph=use_graph,
            )
        except Exception as e:
            logger.error(f"Error generating guide: {e}", exc_info=True)
            raise

    async def generate_presentation(
        self,
        topic: str,
        audience: str = "stakeholders",
        duration_minutes: int = 30,
        use_graph: bool = True,
    ) -> Dict[str, Any]:
        """Generate presentation outline"""
        try:
            from src.ai.agents.business_analyst_agent import BusinessAnalystAgent

            agent = BusinessAnalystAgent()

            return await agent.generate_presentation_outline(
                topic=topic,
                audience=audience,
                duration_minutes=duration_minutes,
                use_graph=use_graph,
            )
        except Exception as e:
            logger.error(f"Error generating presentation: {e}", exc_info=True)
            raise

    async def generate_onboarding_checklist(
        self,
        role: str = "BA",
        include_practical_tasks: bool = True,
        use_graph: bool = True,
    ) -> Dict[str, Any]:
        """Generate onboarding checklist"""
        try:
            from src.ai.agents.business_analyst_agent import BusinessAnalystAgent

            agent = BusinessAnalystAgent()

            return await agent.generate_onboarding_checklist(
                role=role,
                include_practical_tasks=include_practical_tasks,
                use_graph=use_graph,
            )
        except Exception as e:
            logger.error(f"Error generating onboarding checklist: {e}", exc_info=True)
            raise
