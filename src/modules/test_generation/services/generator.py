"""
Test Generator Service
"""
from typing import Any, Dict, List

from src.infrastructure.logging.structured_logging import StructuredLogger
from src.modules.test_generation.services.generators.bsl_generator import (
    BSLTestGenerator,
)
from src.modules.test_generation.services.generators.js_generator import JSTestGenerator
from src.modules.test_generation.services.generators.python_generator import (
    PythonTestGenerator,
)

logger = StructuredLogger(__name__).logger


class TestGeneratorService:
    """Main service for test generation"""

    def __init__(self) -> None:
        self.bsl_generator = BSLTestGenerator()
        self.python_generator = PythonTestGenerator()
        self.js_generator = JSTestGenerator()

    async def generate_tests(
        self,
        code: str,
        language: str,
        include_edge_cases: bool = True,
        timeout: float = 30.0,
    ) -> List[Dict[str, Any]]:
        """Generate tests based on language"""
        try:
            if language == "bsl":
                return await self.bsl_generator.generate(code, include_edge_cases, timeout)
            elif language == "python":
                return await self.python_generator.generate(code, include_edge_cases)
            elif language in ["javascript", "typescript"]:
                return await self.js_generator.generate(code, include_edge_cases)
            else:
                logger.warning(
                    "Unsupported language for test generation",
                    extra={"language": language},
                )
                return []

        except Exception as e:
            logger.error(
                "Error in test generation service",
                extra={
                    "error": str(e),
                    "language": language,
                    "code_length": len(code),
                },
                exc_info=True,
            )
            return []
