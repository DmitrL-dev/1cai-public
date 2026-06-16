"""
Code Analyzer Service
"""
from typing import Any, Dict



class CodeAnalyzer:
    """Service for code analysis"""

    def analyze_bsl_code(self, code: str) -> Dict[str, Any]:
        """Basic BSL code analysis"""
        if not code.strip():
            return {
                "suggestions": [],
                "metrics": {
                    "complexity": 0,
                    "maintainability": 100,
                    "securityScore": 100,
                    "performanceScore": 100,
                    "codeQuality": 100,
                },
                "statistics": {
                    "totalLines": 0,
                    "functions": 0,
                    "variables": 0,
                    "comments": 0,
                    "potentialIssues": 0,
                },
                "recommendations": [],
            }

        suggestions = []
        lines = code.split("\n")

        # Simple analysis rules
        for i, line in enumerate(lines, 1):
            # Check loops with queries
            if "Для" in line and "По" in line:
                # Check next lines for queries
                next_lines = "\n".join(lines[i - 1 : min(i + 5, len(lines))])
                if "Запрос" in next_lines or "Справочники" in next_lines:
                    suggestions.append(
                        {
                            "id": f"perf-{i}",
                            "type": "warning",
                            "severity": "high",
                            "message": "Possible performance issue: database query inside loop",
                            "description": "Database queries inside loops can significantly slow down execution",
                            "suggestion": "Consider moving the query outside the loop or using batch processing",
                            "position": {"line": i, "column": 1},
                            "category": "performance",
                            "autoFixable": False,
                            "confidence": 0.8,
                        }
                    )

            # Security check (SQL injection)
            if "Запрос" in line and "+" in line and "Запрос" in line:
                suggestions.append(
                    {
                        "id": f"sec-{i}",
                        "type": "error",
                        "severity": "critical",
                        "message": "Potential SQL injection",
                        "description": "String concatenation in queries can be unsafe",
                        "suggestion": "Use query parameters instead of string concatenation",
                        "position": {"line": i, "column": 1},
                        "category": "security",
                        "autoFixable": False,
                        "confidence": 0.9,
                    }
                )

            # Hardcoded passwords check
            if ("Пароль" in line or "password" in line.lower()) and ("=" in line or ":=" in line):
                if '"' in line or "'" in line:
                    suggestions.append(
                        {
                            "id": f"sec-pass-{i}",
                            "type": "error",
                            "severity": "critical",
                            "message": "Hardcoded password detected",
                            "description": "Passwords should not be stored in code",
                            "suggestion": "Use environment variables or a secret manager",
                            "position": {"line": i, "column": 1},
                            "category": "security",
                            "autoFixable": False,
                            "confidence": 1.0,
                        }
                    )

            # Best practice: ПроверитьТип instead of Тип
            if "Если" in line and "Тип(" in line and "ПроверитьТип" not in line:
                suggestions.append(
                    {
                        "id": f"bsl-type-{i}",
                        "type": "hint",
                        "severity": "low",
                        "message": "Recommended to use ПроверитьТип() instead of Тип()",
                        "description": "ПроверитьТип() is more efficient and safe",
                        "suggestion": "Replace Тип() with ПроверитьТип()",
                        "position": {"line": i, "column": 1},
                        "category": "best-practice",
                        "autoFixable": True,
                        "confidence": 0.7,
                    }
                )

        # Calculate metrics
        total_lines = len(lines)
        functions = len([l for l in lines if "Процедура" in l or "Функция" in l])
        variables = len([l for l in lines if "=" in l])
        comments = len(
            [l for l in lines if "//" in l or "#" in l or (
                l.strip().startswith("'") and len(l.strip()) > 1)]
        )

        critical_issues = len([s for s in suggestions if s["severity"] == "critical"])
        high_issues = len([s for s in suggestions if s["severity"] == "high"])

        complexity = min(100, int((total_lines / 100) * \
                         50 + (len(suggestions) / 10) * 50))
        maintainability = max(0, 100 - (critical_issues * 20 + high_issues * 10))

        security_issues = len([s for s in suggestions if s["category"] == "security"])
        security_score = max(0, 100 - security_issues * 25)

        performance_issues = len(
            [s for s in suggestions if s["category"] == "performance"])
        performance_score = max(0, 100 - performance_issues * 15)

        code_quality = (maintainability + security_score + performance_score) / 3

        recommendations = []
        if security_score < 70:
            recommendations.append("Recommended to strengthen security checks in code")
        if performance_score < 70:
            recommendations.append(
                "Performance issues detected. Consider optimizing queries and algorithms")
        if maintainability < 70:
            recommendations.append(
                "Code requires improvement for better maintainability")
        if critical_issues > 0:
            recommendations.append(
                f"Detected {critical_issues} critical issues. Immediate fix required")

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
