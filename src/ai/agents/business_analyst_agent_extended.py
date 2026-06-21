"""Compatibility wrapper for the legacy BusinessAnalystAgentExtended API."""

from typing import Any, Dict

from src.ai.agents.business_analyst_agent import BusinessAnalystAgent


class BusinessAnalystAgentExtended(BusinessAnalystAgent):
    """Legacy class name with the historical extract_requirements method."""

    async def extract_requirements(
        self, document: str, document_type: str = "text"
    ) -> Dict[str, Any]:
        result = await self.analyze_requirements(document)
        result["document_type"] = document_type
        return result


__all__ = ["BusinessAnalystAgentExtended"]
