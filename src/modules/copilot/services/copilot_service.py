import asyncio
import os
import re
from typing import Dict, List

from src.config import USE_NESTED_COMPLETION
from src.utils.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


class CopilotService:
    """
    Service for 1C:Copilot code assistance.

    With optional Nested Learning for multi-level completion.
    """

    def __init__(self):
        self.model_available = False
        try:
            model_path = "models/qwen-bsl-lora"
            if os.path.exists(model_path):
                logger.info("Loading model", extra={"model_path": model_path})
                self.model_available = True
        except Exception as e:
            logger.warning(
                "Model not available - using fallback",
                extra={"error": str(e), "error_type": type(e).__name__},
            )

        # Nested Learning integration (optional)
        self._nested = None
        if USE_NESTED_COMPLETION:
            try:
                from src.modules.copilot.services.nested_copilot_service import (
                    NestedCopilotService,
                )

                self._nested = NestedCopilotService(self)
                logger.info("Nested completion enabled for CopilotService")
            except Exception as e:
                logger.warning(
                    f"Failed to initialize nested completion: {e}", exc_info=True)

    async def get_completions(
        self,
        code: str,
        current_line: str,
        max_suggestions: int = 3,
        timeout: float = 5.0,
    ) -> List[Dict]:
        """Get autocomplete suggestions with timeout handling."""
        if not isinstance(code, str):
            code = str(code) if code else ""
        if not isinstance(current_line, str):
            current_line = str(current_line) if current_line else ""
        if not isinstance(max_suggestions, int) or max_suggestions < 1:
            max_suggestions = 3
        if not isinstance(timeout, (int, float)) or timeout <= 0:
            timeout = 5.0

        try:
            return await asyncio.wait_for(
                self._get_completions_internal(code, current_line, max_suggestions),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            logger.warning("Timeout in get_completions", extra={"timeout": timeout})
            return []
        except Exception as e:
            logger.error(f"Error in get_completions: {e}", exc_info=True)
            return []

    async def _get_completions_internal(self, code: str, current_line: str, max_suggestions: int) -> List[Dict]:
        """Internal method for getting completions."""
        suggestions = []

        if "Для Каждого" in current_line or "для каждого" in current_line.lower():
            suggestions.append(
                {
                    "text": " Строка Из КоллекцияСтрок Цикл\\n    // TODO\\nКонецЦикла;",
                    "description": "Цикл по коллекции",
                    "score": 0.9,
                }
            )

        if "Запрос" in current_line:
            suggestions.append(
                {
                    "text": ".Выполнить()",
                    "description": "Выполнить запрос",
                    "score": 0.85,
                }
            )

        if "Результат" in current_line:
            suggestions.append(
                {"text": " = ", "description": "Присвоение значения", "score": 0.8})

        return suggestions[:max_suggestions]

    async def generate_code(self, prompt: str, code_type: str = "function", timeout: float = 10.0) -> str:
        """Generate code from description with timeout handling."""
        if not isinstance(prompt, str) or not prompt.strip():
            prompt = "Новая функция"

        valid_types = ["function", "procedure", "test"]
        if code_type not in valid_types:
            code_type = "function"

        if not isinstance(timeout, (int, float)) or timeout <= 0:
            timeout = 10.0

        try:
            return await asyncio.wait_for(self._generate_code_internal(prompt, code_type), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning("Timeout in generate_code", extra={"timeout": timeout})
            return self._generate_function_template(prompt)
        except Exception as e:
            logger.error("Error in generate_code", exc_info=True)
            return self._generate_function_template(prompt)

    async def _generate_code_internal(self, prompt: str, code_type: str) -> str:
        """Internal method for generating code."""
        if code_type == "function":
            return self._generate_function_template(prompt)
        elif code_type == "procedure":
            return self._generate_procedure_template(prompt)
        elif code_type == "test":
            return self._generate_test_template(prompt)
        else:
            return self._generate_function_template(prompt)

    def _generate_function_template(self, prompt: str) -> str:
        """Template for function."""
        if not isinstance(prompt, str) or not prompt.strip():
            prompt = "Новая функция"

        prompt = prompt[:500]
        words = prompt.split()
        func_name = words[0].capitalize() if words else "НоваяФункция"
        func_name = re.sub(r"[^\\wА-Яа-я]", "", func_name)
        if not func_name:
            func_name = "НоваяФункция"

        return f"""
// {prompt}
//
// Параметры:
//   Параметр1 - Тип - Описание
//
// Возвращаемое значение:
//   Тип - Описание результата
//
Функция {func_name}(Параметр1) Экспорт

    Результат = Неопределено;

    Попытка
        // Реализация функции

    Исключение
        ЗаписьЖурналаРегистрации("Ошибка в {func_name}",
            УровеньЖурналаРегистрации.Ошибка,,,
            ОписаниеОшибки());
        ВызватьИсключение;
    КонецПопытки;

    Возврат Результат;

КонецФункции
"""

    def _generate_procedure_template(self, prompt: str) -> str:
        """Template for procedure."""
        if not isinstance(prompt, str) or not prompt.strip():
            prompt = "Новая процедура"

        prompt = prompt[:500]
        words = prompt.split()
        proc_name = words[0].capitalize() if words else "НоваяПроцедура"
        proc_name = re.sub(r"[^\\wА-Яа-я]", "", proc_name)
        if not proc_name:
            proc_name = "НоваяПроцедура"

        return f"""//
// {prompt}
//
// Параметры:
//   Параметр1 - Произвольный - Описание параметра
//
Процедура {proc_name}(Параметр1) Экспорт

    Попытка
        // Реализация процедуры

    Исключение
        ЗаписьЖурналаРегистрации("Ошибка в {proc_name}",
            УровеньЖурналаРегистрации.Ошибка,,,
            ОписаниеОшибки());
        ВызватьИсключение;
    КонецПопытки;

КонецПроцедуры
"""

    def _generate_test_template(self, function_name: str) -> str:
        """Template for test."""
        if not isinstance(function_name, str) or not function_name.strip():
            function_name = "ТестоваяФункция"

        function_name = function_name[:200]
        clean_name = re.sub(r"[^\\wА-Яа-я]", "",
                            function_name) if function_name else "ТестоваяФункция"
        if not clean_name:
            clean_name = "ТестоваяФункция"

        return f"""//
// Тест для функции {clean_name}
//
Процедура Тест_{clean_name}() Экспорт

    // Arrange (Подготовка данных)
    ВходныеДанные = "test_value";
    ОжидаемыйРезультат = "expected_value";

    // Act (Выполнение)
    ФактическийРезультат = {clean_name}(ВходныеДанные);

    // Assert (Проверка)
    юТест.ПроверитьРавенство(
        ФактическийРезультат,
        ОжидаемыйРезультат,
        "Функция {clean_name} должна вернуть ожидаемое значение"
    );

КонецПроцедуры
"""

    async def optimize_code(self, code: str, language: str = "bsl") -> Dict:
        """Optimize code and return suggestions."""
        optimizations = []

        # String concatenation optimization
        if "+" in code and ('"' in code or "'" in code):
            pattern = r'(\\w+)\\s*=\\s*"([^"]+)"\\s*\\+\\s*(\\w+)\\s*\\+\\s*"([^"]+)"'
            matches = re.findall(pattern, code)
            if matches:
                optimizations.append(
                    {
                        "type": "string_concatenation",
                        "description": "Replace string concatenation with StrTemplate",
                        "impact": "medium",
                    }
                )

        # N+1 query detection
        if re.search(r"Для\\s+Каждого.*Цикл.*Запрос\\.", code, re.DOTALL):
            optimizations.append(
                {
                    "type": "n_plus_1_query",
                    "description": "Detected N+1 query pattern in loop",
                    "impact": "high",
                }
            )

        # Unused variables
        assignments = re.findall(r"(\\w+)\\s*=\\s*.+;", code)
        usages = re.findall(r"\\b(\\w+)\\b", code)
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

        return {
            "optimized_code": code,
            "improvements": optimizations,
            "optimization_count": len(optimizations),
            "language": language,
        }
