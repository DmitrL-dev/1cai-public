from typing import Any, Dict

from src.ai.clients.kimi_client import KimiClient, KimiConfig
from src.ai.strategies.base import AIStrategy
from src.utils.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


class KimiStrategy(AIStrategy):
    """Strategy for Kimi-K2-Thinking"""

    def __init__(self):
        try:
            config = KimiConfig()
            self.client = KimiClient(config=config)
            self.is_available = self.client.is_configured
        except Exception as e:
            logger.warning("Kimi client not available: %s", e)
            self.client = None
            self.is_available = False

    @property
    def service_name(self) -> str:
        return "kimi_k2"

    async def execute(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        if not self.is_available:
            return {"error": "Kimi client not available", "service": self.service_name}

        try:
            system_prompt = context.get(
                "system_prompt",
                "You are an expert 1C:Enterprise developer. Generate clean, efficient BSL code.",
            )

            result = await self.client.generate(
                prompt=query,
                system_prompt=system_prompt,
                temperature=1.0,
                max_tokens=context.get("max_tokens", 4096),
            )

            # Extract code
            code_text = result.get("text", "")
            import re

            code_match = re.search(r"```(?:bsl|1c)?\n?(.*?)```", code_text, re.DOTALL)
            if code_match:
                code_text = code_match.group(1).strip()

            return {
                "type": "code_generation",
                "service": self.service_name,
                "code": code_text,
                "full_response": result.get("text"),
                "reasoning": result.get("reasoning_content", ""),
                "model": "Kimi-K2-Thinking",
                "usage": result.get("usage", {}),
            }
        except Exception as e:
            logger.error(f"Kimi strategy error: {e}", exc_info=True)
            return {"error": str(e), "service": self.service_name}
