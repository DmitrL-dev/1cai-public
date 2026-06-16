"""
Generation Service
"""
import re

from src.infrastructure.logging.structured_logging import StructuredLogger
from src.modules.copilot.services.model_service import ModelService

logger = StructuredLogger(__name__).logger


class GenerationService:
    """Service for code generation"""

    def __init__(self, model_service: ModelService):
        self.model_service = model_service

    async def generate_code(self, prompt: str, code_type: str = "function") -> str:
        """
        Generate code from description
        Uses model if available, otherwise templates
        """
        if self.model_service.is_loaded():
            return await self._generate_with_model(prompt, code_type)
        else:
            return self._generate_with_template(prompt, code_type)

    async def _generate_with_model(self, prompt: str, code_type: str) -> str:
        """Model-based code generation"""
        import torch

        model = self.model_service.get_model()
        tokenizer = self.model_service.get_tokenizer()
        device = self.model_service.get_device()

        try:
            # Create generation prompt
            if code_type == "function":
                full_prompt = f"// Generate BSL function:\n// {prompt}\n\nФункция "
            elif code_type == "test":
                full_prompt = f"// Generate BSL test:\n// {prompt}\n\nПроцедура Тест_"
            else:
                full_prompt = f"// Generate BSL code:\n// {prompt}\n\n"

            # Tokenize
            inputs = tokenizer(
                full_prompt,
                return_tensors="pt",
                max_length=1024,
                truncation=True,
            ).to(device)

            # Generate
            with torch.no_grad():
                outputs = model.generate(
                    inputs.input_ids,
                    max_new_tokens=200,
                    temperature=0.3,
                    do_sample=True,
                    top_p=0.9,
                    pad_token_id=tokenizer.eos_token_id,
                )

            # Decode
            generated = tokenizer.decode(outputs[0], skip_special_tokens=True)

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
