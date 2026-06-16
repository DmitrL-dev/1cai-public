"""
Python Test Generator
"""
import re
from typing import Any, Dict, List


class PythonTestGenerator:
    """Generator for Python tests (pytest)"""

    async def generate(self, code: str, include_edge_cases: bool = False) -> List[Dict[str, Any]]:
        """Generate pytest tests for Python code"""
        tests = []

        # Parse Python functions
        function_pattern = r"def\s+(\w+)\s*\(([^)]*)\):"
        matches = re.finditer(function_pattern, code)

        for match in matches:
            function_name = match.group(1)
            params_str = match.group(2)

            # Parse parameters
            params = []
            if params_str.strip():
                for param in params_str.split(","):
                    param = param.strip()
                    if "=" in param:
                        param = param.split("=")[0].strip()
                    if ":" in param:
                        param = param.split(":")[0].strip()
                    if param and param != "self":
                        params.append(param)

            # Generate test cases
            test_cases = []

            # Happy path
            test_cases.append(
                {
                    "name": f"test_{function_name}_happy_path",
                    "description": f"Test {function_name} with valid inputs",
                    "code": self._generate_test_code(function_name, params, "happy"),
                    "type": "happy_path",
                }
            )

            # Edge cases
            if include_edge_cases:
                test_cases.append(
                    {
                        "name": f"test_{function_name}_empty_input",
                        "description": f"Test {function_name} with empty/null inputs",
                        "code": self._generate_test_code(function_name, params, "empty"),
                        "type": "edge_case",
                    }
                )

                test_cases.append(
                    {
                        "name": f"test_{function_name}_invalid_type",
                        "description": f"Test {function_name} with invalid types",
                        "code": self._generate_test_code(function_name, params, "invalid"),
                        "type": "edge_case",
                    }
                )

            tests.append(
                {
                    "functionName": function_name,
                    "testCases": test_cases,
                    "framework": "pytest",
                    "coverage": {
                        "lines": 80 if include_edge_cases else 60,
                        "branches": 70 if include_edge_cases else 50,
                        "functions": 1,
                    },
                }
            )

        return tests

    def _generate_test_code(self, function_name: str, params: List[str], test_type: str) -> str:
        """Generate pytest test code"""

        if test_type == "happy":
            param_values = ", ".join(
                [f"'{p}_value'" if i % 2 == 0 else str(i) for i, p in enumerate(params)])
            return f"""
def test_{function_name}_happy_path():
    # Arrange
    {', '.join(params)} = {param_values if param_values else ''}

    # Act
    result = {function_name}({', '.join(params) if params else ''})

    # Assert
    assert result is not None
    # TODO: Add specific assertions
"""

        elif test_type == "empty":
            return f"""
def test_{function_name}_empty_input():
    # Test with None/empty inputs
    result = {function_name}({', '.join(['None'] * len(params)) if params else ''})

    # Should handle gracefully
    assert result is not None or result == expected_default
"""

        elif test_type == "invalid":
            return f"""
def test_{function_name}_invalid_type():
    # Test with wrong types
    with pytest.raises((TypeError, ValueError)):
        {function_name}({', '.join(["'invalid'"] * len(params)) if params else ''})
"""

        return ""
