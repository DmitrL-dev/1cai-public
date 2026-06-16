"""
JavaScript Code Analyzer
"""
import re
from typing import Any, Dict

from src.infrastructure.logging.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


class JavaScriptAnalyzer:
    """Analyzer for JavaScript code"""

    def analyze(self, code: str) -> Dict[str, Any]:
        """Analyze JavaScript code"""
        # Input validation
        if not isinstance(code, str) or not code.strip():
            logger.warning(
                "Invalid code in analyze_javascript_code",
                extra={"code_type": type(code).__name__ if code else None},
            )
            return self._empty_result()

        # Limit code length (prevent DoS)
        max_code_length = 100000  # 100KB max
        if len(code) > max_code_length:
            logger.warning(
                "Code too long in analyze_javascript_code",
                extra={
                    "code_length": len(code),
                    "max_length": max_code_length,
                },
            )
            code = code[:max_code_length]

        try:
            suggestions = []
            lines = code.split("\n")

            for i, line in enumerate(lines, 1):
                # Проверка var (устаревший)
                if re.search(r"\bvar\s+", line):
                    suggestions.append(
                        {
                            "id": f"js-var-{i}",
                            "type": "warning",
                            "severity": "medium",
                            "message": "Использование 'var' устарело",
                            "description": "'var' имеет function scope и может привести к неожиданному поведению",
                            "suggestion": "Используйте 'const' или 'let' вместо 'var'",
                            "position": {"line": i, "column": 1},
                            "category": "best-practice",
                            "autoFixable": True,
                            "confidence": 0.8,
                        }
                    )

                # Проверка == вместо ===
                if " == " in line and " === " not in line:
                    suggestions.append(
                        {
                            "id": f"js-equals-{i}",
                            "type": "warning",
                            "severity": "medium",
                            "message": "Использование == вместо ===",
                            "description": "== выполняет приведение типов, что может привести к ошибкам",
                            "suggestion": "Используйте === для строгого сравнения",
                            "position": {"line": i, "column": 1},
                            "category": "best-practice",
                            "autoFixable": True,
                            "confidence": 0.9,
                        }
                    )

                # Проверка eval
                if "eval(" in line:
                    suggestions.append(
                        {
                            "id": f"js-eval-{i}",
                            "type": "error",
                            "severity": "critical",
                            "message": "Использование eval() опасно",
                            "description": "eval может выполнить произвольный код",
                            "suggestion": "Избегайте eval(), используйте безопасные альтернативы",
                            "position": {"line": i, "column": 1},
                            "category": "security",
                            "autoFixable": False,
                            "confidence": 1.0,
                        }
                    )

            total_lines = len(lines)
            functions = len(
                [l for l in lines if "function" in l or "=>" in l or "const.*=" in l])
            variables = len(
                [l for l in lines if "const " in l or "let " in l or "var " in l])
            comments = len([l for l in lines if "//" in l or "/*" in l])

            critical_issues = len(
                [s for s in suggestions if s["severity"] == "critical"])
            high_issues = len([s for s in suggestions if s["severity"] == "high"])

            complexity = min(
                100,
                int((total_lines / 100) * 50 + (len(suggestions) / 10) * 50),
            )
            maintainability = max(0, 100 - (critical_issues * 20 + high_issues * 10))
            security_score = max(0, 100 - critical_issues * 25)
            performance_score = 75

            code_quality = (maintainability + security_score + performance_score) / 3

            recommendations = []
            if security_score < 70:
                recommendations.append(
                    "Рекомендуется усилить проверки безопасности в коде")

            return {
                "suggestions": suggestions,
                "metrics": {
                    "complexity": complexity,
                    "maintainability": maintainability,
                    "securityScore": security_score,
                    "performanceScore": performance_score,
                    "codeQuality": int(code_quality),
                },
                "statistics": {
                    "totalLines": total_lines,
                    "functions": functions,
                    "variables": variables,
                    "comments": comments,
                    "potentialIssues": len(suggestions),
                },
                "recommendations": recommendations,
            }
        except Exception as e:
            logger.error(
                "Error analyzing JavaScript code",
                extra={"error": str(e), "error_type": type(e).__name__},
            )
            return self._empty_result(error=True)

    def _empty_result(self, error: bool = False) -> Dict[str, Any]:
        """Return empty result structure"""
        return {
            "suggestions": [],
            "metrics": {
                "complexity": 0,
                "maintainability": 0,
                "securityScore": 0,
                "performanceScore": 0,
                "codeQuality": 0,
            },
            "statistics": {
                "totalLines": 0,
                "functions": 0,
                "variables": 0,
                "comments": 0,
                "potentialIssues": 0,
            },
            "recommendations": ["Ошибка при анализе кода"] if error else [],
        }
