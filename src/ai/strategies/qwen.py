from typing import Any, Dict

from src.ai.qwen_client import QwenCoderClient
from src.ai.strategies.base import AIStrategy
from src.utils.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


class QwenStrategy(AIStrategy):
    """Strategy for Qwen3-Coder"""

    def __init__(self):
        # Lazy initialization or DI is preferred to avoid connection errors at startup
        pass

    @property
    def service_name(self) -> str:
        return "qwen_coder"

    def _get_client(self):
        try:
            return QwenCoderClient()
        except Exception as e:
            logger.warning("Qwen client not available: %s", e)
            return None

    async def execute(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        client = self._get_client()
        if not client:
            return {"error": "Qwen client not available", "service": self.service_name}

        try:
            function_name = context.get("function_name")
            parameters = context.get("parameters", [])

            if function_name:
                result = await client.generate_function(
                    description=query,
                    function_name=function_name,
                    parameters=parameters,
                )
            else:
                result = await client.generate_code(prompt=query, context=context)

            return {
                "type": "code_generation",
                "service": self.service_name,
                "code": result.get("code"),
                "full_response": result.get("full_response"),
                "model": result.get("model"),
            }
        except Exception as e:
            logger.error(f"Qwen strategy error: {e}", exc_info=True)
            return {"error": str(e), "service": self.service_name}
