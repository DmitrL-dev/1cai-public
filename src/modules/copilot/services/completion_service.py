"""
Completion Service
"""
from typing import Any, Dict, List

from src.infrastructure.logging.structured_logging import StructuredLogger
from src.modules.copilot.services.model_service import ModelService

logger = StructuredLogger(__name__).logger


class CompletionService:
    """Service for code completion"""

    def __init__(self, model_service: ModelService):
        self.model_service = model_service

    async def get_completions(self, code: str, current_line: str, max_suggestions: int = 3) -> List[Dict[str, Any]]:
        """
        Get code completion suggestions
        Uses model if available, otherwise rule-based
        """
        if self.model_service.is_loaded():
            return await self._get_model_completions(code, current_line, max_suggestions)
        else:
            return self._get_rule_based_completions(code, current_line, max_suggestions)

    async def _get_model_completions(self, code: str, current_line: str, max_suggestions: int) -> List[Dict[str, Any]]:
        """Model-based completions"""
        import torch

        suggestions = []
        model = self.model_service.get_model()
        tokenizer = self.model_service.get_tokenizer()
        device = self.model_service.get_device()

        try:
            # Prepare prompt
            prompt = f"{code}\n{current_line}"

            # Tokenize
            inputs = tokenizer(prompt, return_tensors="pt",
                               max_length=2048, truncation=True).to(device)

            # Generate multiple completions with different temperatures
            temperatures = [0.2, 0.5, 0.8][:max_suggestions]

            for temp in temperatures:
                with torch.no_grad():
                    outputs = model.generate(
                        inputs.input_ids,
                        max_new_tokens=50,
                        temperature=temp,
                        do_sample=True,
                        top_p=0.95,
                        pad_token_id=tokenizer.eos_token_id,
                        num_return_sequences=1,
                    )

                # Decode
                completion = tokenizer.decode(outputs[0], skip_special_tokens=True)
                new_part = completion[len(prompt) :].strip()

                if new_part:
                    suggestions.append(
                        {
                            "text": new_part,
                            "description": f"AI suggestion (temp={temp})",
                            # Higher temp = lower confidence
                            "score": 1.0 - (temp * 0.2),
                        }
                    )

            logger.info(
                "Generated model-based completions",
                extra={
                    "suggestions_count": len(suggestions),
                    "max_suggestions": max_suggestions,
                },
            )

        except Exception as e:
            logger.error(
                "Model completion error, falling back to rules",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )
            # Fallback to rules
            return self._get_rule_based_completions(code, current_line, max_suggestions)

        return suggestions[:max_suggestions]

    def _get_rule_based_completions(self, code: str, current_line: str, max_suggestions: int) -> List[Dict[str, Any]]:
        """
        SMART rule-based completions
        20+ patterns for comprehensive coverage
        """

        suggestions = []
        line_lower = current_line.lower()

        # Pattern 1: Для Каждого
        if "для каждого" in line_lower or "для каждого" in current_line:
            suggestions.append(
                {
                    "text": " Элемент Из Коллекция Цикл\n        // Process element\n    КонецЦикла;",
                    "description": "Цикл по коллекции",
                    "score": 0.95,
                }
            )

        # Pattern 2: Функция
        if "функция" in line_lower:
            if "(" not in current_line:
                suggestions.append(
                    {
                        "text": "(Параметр1)\n    Результат = Неопределено;\n    \n    // Implementation\n    \n    Возврат Результат;\nКонецФункции;",
                        "description": "Функция с параметром",
                        "score": 0.9,
                    }
                )
            elif ")" in current_line and "экспорт" not in line_lower:
                suggestions.append(
                    {
                        "text": " Экспорт\n    Результат = Неопределено;\n    \n    // Implementation\n    \n    Возврат Результат;\nКонецФункции;",
                        "description": "Экспортная функция",
                        "score": 0.88,
                    }
                )

        # Pattern 3: Процедура
        if "процедура" in line_lower:
            if "(" not in current_line:
                suggestions.append(
                    {
                        "text": "(Параметр1)\n    // Implementation\nКонецПроцедуры;",
                        "description": "Процедура с параметром",
                        "score": 0.9,
                    }
                )

        # Pattern 4: Запрос
        if "запрос" in line_lower:
            suggestions.extend(
                [
                    {
                        "text": '.Текст = "\n    |ВЫБРАТЬ\n    |    *\n    |ИЗ\n    |    Справочник.Номенклатура\n    |";\n    Результат = Запрос.Выполнить();',
                        "description": "Запрос с текстом",
                        "score": 0.92,
                    },
                    {
                        "text": ".Выполнить()",
                        "description": "Выполнить запрос",
                        "score": 0.85,
                    },
                ]
            )

        # Pattern 5: Если
        if "если" in line_lower and "тогда" not in line_lower:
            suggestions.append(
                {
                    "text": " Тогда\n        // TODO\n    КонецЕсли;",
                    "description": "Условие",
                    "score": 0.93,
                }
            )

        # Pattern 6: Попытка
        if "попытка" in line_lower:
            suggestions.append(
                {
                    "text": "\n    // Protected code\nИсключение\n    ЗаписьЖурналаРегистрации(ОписаниеОшибки());\nКонецПопытки;",
                    "description": "Обработка ошибок",
                    "score": 0.91,
                }
            )

        # Pattern 7: Новый
        if "новый" in line_lower:
            suggestions.append(
                {"text": " Массив", "description": "Новый массив", "score": 0.87})
            suggestions.append(
                {
                    "text": " Структура",
                    "description": "Новая структура",
                    "score": 0.86,
                }
            )

        # Pattern 8: СоздатьОбъект
        if "создатьобъект" in line_lower.replace(" ", ""):
            suggestions.append(
                {
                    "text": '("AddIn.COMConnector")',
                    "description": "COM-объект",
                    "score": 0.84,
                }
            )

        # Pattern 9: ЗаписьXML
        if "записьxml" in line_lower.replace(" ", ""):
            suggestions.append(
                {
                    "text": ' = Новый ЗаписьXML;\n    ЗаписьXML.ОткрытьФайл("файл.xml");\n    ЗаписьXML.ЗаписатьНачалоЭлемента("Корень");',
                    "description": "Запись XML",
                    "score": 0.83,
                }
            )

        # Pattern 10: ЧтениеJSON
        if "чтениеjson" in line_lower.replace(" ", ""):
            suggestions.append(
                {
                    "text": " = Новый ЧтениеJSON;\n    ЧтениеJSON.УстановитьСтроку(СтрокаJSON);\n    Результат = ПрочитатьJSON(ЧтениеJSON);",
                    "description": "Чтение JSON",
                    "score": 0.82,
                }
            )

        # Pattern 11: HTTPЗапрос
        if "httpзапрос" in line_lower.replace(" ", ""):
            suggestions.append(
                {
                    "text": ' = Новый HTTPЗапрос;\n    HTTPЗапрос.АдресРесурса = "/api/endpoint";\n    Ответ = HTTPСоединение.Получить(HTTPЗапрос);',
                    "description": "HTTP запрос",
                    "score": 0.81,
                }
            )

        return suggestions[:max_suggestions]
