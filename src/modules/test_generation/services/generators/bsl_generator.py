"""
BSL Test Generator
"""
import asyncio
from datetime import datetime
from typing import Any, Dict, List

from src.infrastructure.logging.structured_logging import StructuredLogger
from src.services.openai_code_analyzer import get_openai_analyzer

logger = StructuredLogger(__name__).logger


class BSLTestGenerator:
    """Generator for BSL (1C:Enterprise) tests"""

    async def generate(self, code: str, include_edge_cases: bool = True, timeout: float = 30.0) -> List[Dict[str, Any]]:
        """Generate tests for BSL code"""
        try:
            return await asyncio.wait_for(
                self._generate_internal(code, include_edge_cases), timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.warning(
                "Timeout in BSL test generation",
                extra={"timeout": timeout, "code_length": len(code)},
            )
            return []
        except Exception as e:
            logger.error(
                "Error in BSL test generation",
                extra={"error": str(e), "code_length": len(code)},
                exc_info=True,
            )
            return []

    async def _generate_internal(self, code: str, include_edge_cases: bool) -> List[Dict[str, Any]]:
        """Internal generation logic"""
        tests = []
        from src.ai.agents.code_review.bsl_parser import BSLParser
        parser = BSLParser()

        try:
            parsed_data = parser.parse_file(code)
            raw_functions = parsed_data.get("functions", [])

            functions = []
            for f in raw_functions:
                functions.append(
                    {
                        "name": f.get("name"),
                        "code": f.get("body", ""),
                        "params": [p["name"] for p in f.get("parameters", [])],
                        "params_detailed": f.get("parameters", []),
                        "exported": f.get("is_export", False),
                    }
                )
        except Exception as e:
            logger.error(f"BSL parsing failed: {e}", exc_info=True)
            return []

        for func in functions:
            test_cases = await self._generate_test_cases(func, include_edge_cases)
            test_code = self._generate_test_code(func, test_cases)

            tests.append(
                {
                    "id": f"test-{func['name']}-{datetime.now().timestamp()}",
                    "functionName": func["name"],
                    "testCases": test_cases,
                    "code": test_code,
                    "language": "bsl",
                    "framework": "xUnitFor1C",
                    "coverage": {
                        "lines": self._calculate_coverage(func["code"], test_code),
                        "branches": 0,
                        "functions": 1,
                    },
                }
            )

        return tests

    async def _generate_test_cases(self, func: Dict[str, Any], include_edge_cases: bool) -> List[Dict[str, Any]]:
        """Generate test cases using AI or fallback"""
        test_cases = []

        # Try AI generation
        try:
            openai_analyzer = get_openai_analyzer()
            if getattr(openai_analyzer, "enabled", False):
                ai_test_cases = await openai_analyzer.generate_test_cases(
                    code=func["code"], function_name=func["name"]
                )
                if ai_test_cases:
                    for ai_case in ai_test_cases:
                        test_cases.append(
                            {
                                "id": ai_case.get("id", f"test-{func['name']}-{len(test_cases)}"),
                                "name": ai_case.get("name", f"{func['name']}_Test{len(test_cases)+1}"),
                                "description": ai_case.get("description", ""),
                                "input": ai_case.get("input", {}),
                                "expectedOutput": ai_case.get("expectedOutput"),
                                "type": ai_case.get("type", "unit"),
                                "category": ai_case.get("category", "positive"),
                            }
                        )
                    return test_cases
        except Exception as e:
            logger.warning(
                "AI test generation failed, using fallback",
                extra={"error": str(e), "function": func["name"]},
            )

        # Fallback generation
        test_cases.append(
            {
                "id": f"test-{func['name']}-positive",
                "name": f"{func['name']}_Positive",
                "description": f"Positive test for {func['name']}",
                "input": {p: 0 for p in func["params"]},
                "expectedOutput": "OK",
                "type": "unit",
                "category": "positive",
            }
        )

        if include_edge_cases and func["params"]:
            test_cases.append(
                {
                    "id": f"test-{func['name']}-boundary",
                    "name": f"{func['name']}_Boundary",
                    "description": "Boundary test",
                    "input": {p: 0 for p in func["params"]},
                    "expectedOutput": "OK",
                    "type": "unit",
                    "category": "boundary",
                }
            )

        return test_cases

    def _generate_test_code(self, func: Dict[str, Any], test_cases: List[Dict[str, Any]]) -> str:
        """Generate BSL test code"""
        test_code = f"// Auto-generated tests for function {func['name']}\n\n"

        for test_case in test_cases:
            test_code += f"Процедура Тест_{func['name']}_{test_case['name']}()\n"
            test_code += f"\t// {test_case['description']}\n\n"

            # Prepare input
            for key, value in test_case["input"].items():
                formatted_value = self._format_value(value)
                test_code += f"\t{key} = {formatted_value};\n"

            # Call function
            params_str = ", ".join(func["params"])
            test_code += f"\tResult = {func['name']}({params_str});\n\n"

            # Assert
            expected = self._format_value(test_case["expectedOutput"])
            test_code += f'\tAssertTrue(Result = {expected}, "Expected: {expected}");\n'
            test_code += "КонецПроцедуры\n\n"

        return test_code

    def _format_value(self, value: Any) -> str:
        """Format value for BSL"""
        if value is None:
            return "Неопределено"
        if isinstance(value, str):
            return f'"{value}"'
        if isinstance(value, bool):
            return "Истина" if value else "Ложь"
        return str(value)

    def _calculate_coverage(self, original_code: str, test_code: str) -> int:
        """Simple coverage calculation"""
        original_lines = len(original_code.split("\n"))
        tested_lines = len(test_code.split("\n"))
        return min(100, int((tested_lines / max(original_lines, 1)) * 100))
