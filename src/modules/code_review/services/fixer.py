"""
Code Fixer Service
"""
import re

from fastapi import HTTPException

from src.infrastructure.logging.structured_logging import StructuredLogger
from src.modules.code_review.domain.models import AutoFixRequest, AutoFixResponse

logger = StructuredLogger(__name__).logger


class CodeFixer:
    """Service for automated code fixing"""

    async def apply_auto_fix(self, payload: AutoFixRequest) -> AutoFixResponse:
        """
        SMART Auto-Fix - Apply auto-fix based on issue type
        Supports multiple fix patterns based on suggestion ID
        """
        try:
            fixed_code = payload.code
            changes = []

            # Parse suggestion ID to determine fix type
            suggestion_id = payload.suggestionId.lower()

            # Pattern 1: Type checking (Тип → ПроверитьТип)
            if "type-check" in suggestion_id or "bsl-type" in suggestion_id or "Тип(" in fixed_code:
                original = fixed_code
                fixed_code = fixed_code.replace("Тип(", "ПроверитьТип(")

                if fixed_code != original:
                    changes.append(
                        {
                            "type": "type_safety",
                            "old": "Тип(",
                            "new": "ПроверитьТип(",
                            "count": fixed_code.count("ПроверитьТип(") - original.count("ПроверитьТип("),
                            "description": "Added type checking for safety",
                        }
                    )

            # Pattern 2: Null checking
            if "null-check" in suggestion_id:
                # Find assignments without null checks
                pattern = r"(\w+)\s*=\s*(\w+\.\w+\([^)]*\));"

                def add_null_check(match: re.Match) -> str:
                    var_name = match.group(1)
                    call = match.group(2)
                    return f"{var_name} = {call};\nЕсли {var_name} = Неопределено Тогда\n    // Handle null\n    Возврат;\nКонецЕсли;"

                new_code = re.sub(pattern, add_null_check, fixed_code)
                if new_code != fixed_code:
                    changes.append(
                        {
                            "type": "null_safety",
                            "description": "Added null checks",
                            "count": len(re.findall(pattern, fixed_code)),
                        }
                    )
                    fixed_code = new_code

            # Pattern 3: Error handling
            if "error-handling" in suggestion_id or "exception" in suggestion_id:
                if "Попытка" not in fixed_code:
                    # Wrap code in try-catch
                    lines = fixed_code.split("\n")
                    indented = "\n".join(["    " + line for line in lines])
                    fixed_code = f"Попытка\n{indented}\nИсключение\n    // Log error\n    ЗаписьЖурналаРегистрации(ОписаниеОшибки());\n    ВызватьИсключение;\nКонецПопытки;"

                    changes.append(
                        {
                            "type": "error_handling",
                            "description": "Wrapped code in try-catch block",
                            "count": 1,
                        }
                    )

            # Pattern 4: Performance - N+1 queries
            if "n+1" in suggestion_id or "batch" in suggestion_id:
                # Replace loop queries with batch query
                pattern = r"Для\s+Каждого\s+(\w+)\s+Из\s+(\w+)\s+Цикл\s+.*?Запрос\."

                if re.search(pattern, fixed_code, re.DOTALL):
                    changes.append(
                        {
                            "type": "performance",
                            "description": "Suggested: Convert to batch query (manual intervention needed)",
                            "suggestion": "Replace loop with: Запрос.УстановитьПараметр('Список', Список);",
                        }
                    )

            # Pattern 5: Magic numbers
            if "magic-number" in suggestion_id:
                # Find bare numbers (except 0, 1, -1)
                pattern = r"(?<=[^\w])(\d{2,})(?=[^\w])"

                def replace_with_constant(match: re.Match) -> str:
                    num = match.group(1)
                    return f"КОНСТАНТА_{num}"

                new_code = re.sub(pattern, replace_with_constant, fixed_code)
                if new_code != fixed_code:
                    changes.append(
                        {
                            "type": "maintainability",
                            "description": "Replaced magic numbers with constants",
                            "count": len(re.findall(pattern, fixed_code)),
                        }
                    )
                    fixed_code = new_code

            return AutoFixResponse(
                fixedCode=fixed_code,
                changes=changes,
                success=len(changes) > 0,
                message=(
                    f"Applied {len(changes)} fix(es)" if changes else "No applicable auto-fixes for this suggestion"
                ),
            )

        except Exception as e:
            logger.error(
                "Error in auto-fix",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "suggestion_id": payload.suggestionId,
                },
                exc_info=True,
            )
            raise HTTPException(status_code=500, detail=f"Auto-fix error: {str(e)}")
