"""
TypeScript Code Analyzer
"""
import re
from typing import Any, Dict

from src.infrastructure.logging.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


class TypeScriptAnalyzer:
    """Analyzer for TypeScript code"""

    def analyze(self, code: str) -> Dict[str, Any]:
        """Analyze TypeScript code"""
        # Input validation
        if not isinstance(code, str) or not code.strip():
            logger.warning(
                "Invalid code in analyze_typescript_code",
                extra={"code_type": type(code).__name__ if code else None},
            )
            return self._empty_result()

        # Limit code length (prevent DoS)
        max_code_length = 100000  # 100KB max
        if len(code) > max_code_length:
            logger.warning(
                "Code too long in analyze_typescript_code",
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
                # Проверка any типов
                if "any" in line and ":" in line:
                    suggestions.append(
                        {
                            "id": f"ts-any-{i}",
                            "type": "warning",
                            "severity": "medium",
                            "message": "Использование типа 'any' снижает типобезопасность",
                            "description": "TypeScript предоставляет строгую типизацию - используйте конкретные типы",
                            "suggestion": "Замените 'any' на конкретный тип или используйте 'unknown'",
                            "position": {"line": i, "column": 1},
                            "category": "best-practice",
                            "autoFixable": False,
                            "confidence": 0.8,
                        }
                    )

                # Проверка console.log в production коде
                if "console.log" in line or "console.error" in line:
                    suggestions.append(
                        {
                            "id": f"ts-console-{i}",
                            "type": "hint",
                            "severity": "low",
                            "message": "Использование console.log в production коде",
                            "description": "Логирование должно использовать систему логирования",
                            "suggestion": "Используйте logger вместо console.log",
                            "position": {"line": i, "column": 1},
                            "category": "best-practice",
                            "autoFixable": True,
                            "confidence": 0.7,
                        }
                    )

                # Проверка неиспользуемых импортов (базовая)
                if line.strip().startswith("import") and "from" in line:
                    imported = re.search(r"import\s+.*?\s+from", line)
                    if imported and "{" not in line:
                        # Простая проверка - в реальности нужен AST парсер
                        pass

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
            security_score = 85  # TypeScript более безопасен по умолчанию
            performance_score = 80

            code_quality = (maintainability + security_score + performance_score) / 3

            recommendations = []
            if maintainability < 70:
                recommendations.append(
                    "Код требует улучшения для лучшей поддерживаемости")

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
                "Error analyzing TypeScript code",
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
