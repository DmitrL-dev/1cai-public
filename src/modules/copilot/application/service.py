import os
import re
from typing import Any, Dict, List

from src.infrastructure.logging.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


class CopilotService:
    """
    Unified Copilot Service
    Combines 'Perfect' implementation features with GBNF integration.
    """

    def __init__(self):
        """Initialize Copilot with model loading and GBNF"""
        self.model = None
        self.tokenizer = None
        self.model_loaded = False
        self.device = "cpu"
        self.gbnf_generator = None

        # 1. Initialize GBNF generator
        try:
            from src.gbnf_generator.gbnf_generator import GBNFGenerator

            self.gbnf_generator = GBNFGenerator()
            logger.info("GBNF Generator initialized")
        except ImportError:
            logger.warning("Could not import GBNFGenerator")
        except Exception as e:
            logger.error("Error initializing GBNFGenerator: %s", e)

        # 2. Attempt to load fine-tuned model
        self._load_model()

    def _load_model(self):
        """Load ML model if available"""
        try:
            model_path = os.getenv("COPILOT_MODEL_PATH", os.getenv(
                "BSL_MODEL_PATH", "./models/1c-copilot-lora"))

            if os.path.exists(model_path):
                logger.info("Loading Copilot model", extra={"model_path": model_path})

                try:
                    import torch
                    from peft import PeftModel
                    from transformers import AutoModelForCausalLM, AutoTokenizer

                    # Determine device
                    self.device = "cuda" if torch.cuda.is_available() else "cpu"
                    logger.info("Using device", extra={"device": self.device})

                    # Load base model
                    base_model_name = os.getenv(
                        "BASE_MODEL", "Qwen/Qwen2.5-Coder-7B-Instruct")

                    logger.info("Loading base model", extra={
                                "base_model_name": base_model_name})
                    base_model = AutoModelForCausalLM.from_pretrained(
                        base_model_name,
                        device_map="auto",
                        torch_dtype=(torch.float16 if self.device ==
                                     "cuda" else torch.float32),
                        low_cpu_mem_usage=True,
                    )

                    # Load LoRA adapter
                    logger.info("Loading LoRA adapter...")
                    self.model = PeftModel.from_pretrained(base_model, model_path)

                    # Load tokenizer
                    self.tokenizer = AutoTokenizer.from_pretrained(model_path)

                    self.model.eval()  # Set to evaluation mode
                    self.model_loaded = True

                    logger.info("✅ Copilot model loaded successfully!")

                except ImportError as e:
                    logger.warning(
                        "Required libraries not installed",
                        extra={"error": str(e), "error_type": type(e).__name__},
                    )
                    logger.warning("Install with: pip install transformers peft torch")
                except Exception as e:
                    logger.error(
                        "Failed to load model",
                        extra={
                            "error": str(e),
                            "error_type": type(e).__name__,
                            "model_path": model_path,
                        },
                        exc_info=True,
                    )
            else:
                logger.info(
                    "Model path not found, using rule-based fallback",
                    extra={"model_path": model_path},
                )

        except Exception as e:
            logger.error(
                "Copilot initialization error",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )

    async def get_completions(self, code: str, current_line: str, max_suggestions: int = 3) -> List[Dict]:
        """
        Get code completion suggestions
        Priority: Model -> Rules
        """

        if self.model_loaded:
            # Use model-based completion
            return await self._get_model_completions(code, current_line, max_suggestions)
        else:
            # Use rule-based completion
            return self._get_rule_based_completions(code, current_line, max_suggestions)

    async def _get_model_completions(self, code: str, current_line: str, max_suggestions: int) -> List[Dict]:
        """Model-based completions"""
        import torch

        suggestions = []

        try:
            # Prepare prompt
            prompt = f"{code}\n{current_line}"

            # Tokenize
            inputs = self.tokenizer(prompt, return_tensors="pt",
                                    max_length=2048, truncation=True).to(self.device)

            # Generate multiple completions with different temperatures
            temperatures = [0.2, 0.5, 0.8][:max_suggestions]

            for temp in temperatures:
                with torch.no_grad():
                    outputs = self.model.generate(
                        inputs.input_ids,
                        max_new_tokens=50,
                        temperature=temp,
                        do_sample=True,
                        top_p=0.95,
                        pad_token_id=self.tokenizer.eos_token_id,
                        num_return_sequences=1,
                    )

                # Decode
                completion = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
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

    def _get_rule_based_completions(self, code: str, current_line: str, max_suggestions: int) -> List[Dict]:
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
                {"text": " Структура", "description": "Новая структура", "score": 0.86})

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

    async def generate_code(self, prompt: str, code_type: str = "function") -> str:
        """
        Generate code from description
        Uses model if available, otherwise templates
        """

        if self.model_loaded:
            return await self._generate_with_model(prompt, code_type)
        else:
            return self._generate_with_template(prompt, code_type)

    async def _generate_with_model(self, prompt: str, code_type: str) -> str:
        """Model-based code generation"""
        import torch

        try:
            # Create generation prompt
            if code_type == "function":
                full_prompt = f"// Generate BSL function:\n// {prompt}\n\nФункция "
            elif code_type == "test":
                full_prompt = f"// Generate BSL test:\n// {prompt}\n\nПроцедура Тест_"
            else:
                full_prompt = f"// Generate BSL code:\n// {prompt}\n\n"

            # Tokenize
            inputs = self.tokenizer(full_prompt, return_tensors="pt",
                                    max_length=1024, truncation=True).to(self.device)

            # Generate
            with torch.no_grad():
                outputs = self.model.generate(
                    inputs.input_ids,
                    max_new_tokens=200,
                    temperature=0.3,
                    do_sample=True,
                    top_p=0.9,
                    pad_token_id=self.tokenizer.eos_token_id,
                )

            # Decode
            generated = self.tokenizer.decode(outputs[0], skip_special_tokens=True)

            # Extract only the new part
            code = generated[len(full_prompt) :].strip()

            logger.info(
                "Generated code with model",
                extra={"code_length": len(code), "code_type": code_type},
            )
            return code

        except Exception as e:
            logger.error(
                "Model generation error, falling back to template",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "code_type": code_type,
                },
                exc_info=True,
            )
            # Fallback to template
            return self._generate_with_template(prompt, code_type)

    def _generate_with_template(self, prompt: str, code_type: str) -> str:
        """Template-based code generation"""

        if code_type == "function":
            return self._generate_function_template(prompt)
        elif code_type == "test":
            return self._generate_test_template(prompt)
        elif code_type == "procedure":
            return self._generate_procedure_template(prompt)
        else:
            return f"// Generated code for: {prompt}\n// Implementation needed"

    def _generate_function_template(self, prompt: str) -> str:
        """Generate function template with smart naming"""

        # Extract function name from prompt
        words = [w for w in re.findall(r"\w+", prompt) if len(w) > 2]
        func_name = "".join(w.capitalize()
                            for w in words[:3]) if words else "НоваяФункция"

        # Detect if needs parameters
        needs_params = any(word in prompt.lower()
                           for word in ["параметр", "значение", "данные", "объект"])

        params = "Параметр1, Параметр2" if needs_params else ""

        return f"""//
// {prompt}
//
// Параметры:
//   Параметр1 - Произвольный - Описание первого параметра
//   Параметр2 - Произвольный - Описание второго параметра
//
// Возвращаемое значение:
//   Произвольный - Результат выполнения функции
//
Функция {func_name}({params}) Экспорт

    Результат = Неопределено;

    // Реализация функции
    Попытка
        // Основная логика

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
        """Generate procedure template"""

        words = [w for w in re.findall(r"\w+", prompt) if len(w) > 2]
        proc_name = "".join(w.capitalize()
                            for w in words[:3]) if words else "НоваяПроцедура"

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
        """Generate Vanessa test template"""

        # Extract clean function name
        clean_name = re.sub(r"[^\w]", "", function_name)

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

    async def optimize_code(self, code: str, language: str = "bsl") -> Dict[str, Any]:
        """
        Code optimization with real analysis
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
            return {"optimized_code": code, "improvements": [], "error": str(e)}

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
