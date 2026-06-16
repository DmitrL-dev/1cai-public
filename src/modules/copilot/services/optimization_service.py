"""
Optimization Service
"""
import re
from typing import Any, Dict

from src.infrastructure.logging.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


class OptimizationService:
    """Service for code optimization"""

    async def optimize_code(self, code: str, language: str = "bsl") -> Dict[str, Any]:
        """
        Code optimization with real analysis
        Analyzes code and suggests optimizations
        """

        optimizations = []
        optimized_code = code

        try:
            # Optimization 1: Replace string concatenation with StrTemplate
            if "+" in code and ('"' in code or "'" in code):
                pattern = r'(\w+)\s*=\s*"([^"]+)"\s*\+\s*(\w+)\s*\+\s*"([^"]+)"'
                matches = re.findall(pattern, code)

                if matches:
                    optimizations.append(
                        {
                            "type": "string_concatenation",
                            "description": "Replace string concatenation with StrTemplate for better performance",
                            "impact": "medium",
                            "example": 'Использовать СтрШаблон("...", Параметр1, Параметр2)',
                        }
                    )

            # Optimization 2: N+1 query detection
            if re.search(r"Для\s+Каждого.*Цикл.*Запрос\.", code, re.DOTALL):
                optimizations.append(
                    {
                        "type": "n_plus_1_query",
                        "description": "Detected N+1 query pattern in loop - use batch query instead",
                        "impact": "high",
                        "fix": "Move query outside loop and use IN clause with array",
                    }
                )

            # Optimization 3: Unused variables
            assignments = re.findall(r"(\w+)\s*=\s*.+;", code)
            usages = re.findall(r"\b(\w+)\b", code)
            usage_counts = {var: usages.count(var) for var in set(assignments)}

            unused = [var for var, count in usage_counts.items() if count == 1]
            if unused:
                optimizations.append(
                    {
                        "type": "unused_variables",
                        "description": f"Found {len(unused)} potentially unused variables",
                        "impact": "low",
                        "variables": unused[:5],
                    }
                )

            # Optimization 4: Exception handling
            if "Попытка" not in code and ("Запрос" in code or "СоздатьОбъект" in code):
                optimizations.append(
                    {
                        "type": "missing_error_handling",
                        "description": "Add Попытка/Исключение for external operations",
                        "impact": "high",
                        "fix": "Wrap risky code in try-catch block",
                    }
                )

            # Optimization 5: Type checking
            if "Тип(" in code and "ПроверитьТип(" not in code:
                optimized_code = code.replace("Тип(", "ПроверитьТип(")
                optimizations.append(
                    {
                        "type": "type_safety",
                        "description": "Use ПроверитьТип() for safer type checking",
                        "impact": "medium",
                        "applied": True,
                    }
                )

            return {
                "optimized_code": optimized_code,
                "improvements": optimizations,
                "score": self._calculate_code_quality(code),
                "optimized_score": self._calculate_code_quality(optimized_code),
            }

        except Exception as e:
            logger.error(
                "Optimization error",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "code_length": len(code) if code else 0,
                },
                exc_info=True,
            )
            return {
                "optimized_code": code,
                "improvements": [],
                "error": str(e),
            }

    def _calculate_code_quality(self, code: str) -> int:
        """Calculate code quality score 0-100"""
        score = 100

        # Deduct for issues
        if "Попытка" not in code and ("Запрос" in code or "СоздатьОбъект" in code):
            score -= 15  # No error handling

        if "Тип(" in code and "ПроверитьТип(" not in code:
            score -= 10  # Unsafe type checking

        if "//" not in code:
            score -= 10  # No comments

        # Add for good practices
        if "Экспорт" in code:
            score += 5  # Good API design

        if re.search(r"//.*Параметры:", code):
            score += 5  # Good documentation

        return max(0, min(100, score))
