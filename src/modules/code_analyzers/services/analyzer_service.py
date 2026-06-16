"""
Code Analyzer Service Facade
"""
from typing import Any, Dict

from src.modules.code_analyzers.services.analyzers.javascript_analyzer import (
    JavaScriptAnalyzer,
)
from src.modules.code_analyzers.services.analyzers.python_analyzer import PythonAnalyzer
from src.modules.code_analyzers.services.analyzers.typescript_analyzer import (
    TypeScriptAnalyzer,
)


class CodeAnalyzerService:
    """Facade service for code analysis"""

    def __init__(self):
        self.python_analyzer = PythonAnalyzer()
        self.typescript_analyzer = TypeScriptAnalyzer()
        self.javascript_analyzer = JavaScriptAnalyzer()

    def analyze_python(self, code: str) -> Dict[str, Any]:
        """Analyze Python code"""
        return self.python_analyzer.analyze(code)

    def analyze_typescript(self, code: str) -> Dict[str, Any]:
        """Analyze TypeScript code"""
        return self.typescript_analyzer.analyze(code)

    def analyze_javascript(self, code: str) -> Dict[str, Any]:
        """Analyze JavaScript code"""
        return self.javascript_analyzer.analyze(code)
