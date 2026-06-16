
"""
Тесты для процессора шаблонов.
"""


import pytest

from src.py_server.code_generation.templates.processor import (
    GeneratedCode, TemplateProcessor, TemplateVariable)


class TestTemplateVariable:
    """Тесты для класса TemplateVariable."""
    
    def test_template_variable_creation(self):
        """Тест создания переменной шаблона."""
        variable = TemplateVariable(
            name="test_var",
            description="Test variable",
            default_value="default",
            required=True,
            validation_pattern=r"^[a-zA-Z]+$",
            example_value="example"
        )
        
        assert variable.name == "test_var"
        assert variable.description == "Test variable"
        assert variable.default_value == "default"
        assert variable.required is True
        assert variable.validation_pattern == r"^[a-zA-Z]+$"
        assert variable.example_value == "example"
    
    def test_template_variable_defaults(self):
        """Тест значений по умолчанию для переменной."""
        variable = TemplateVariable(
            name="test_var",
            description="Test variable"
        )
        
        assert variable.default_value == ""
        assert variable.required is True
        assert variable.validation_pattern == ""
        assert variable.example_value == ""
    
    def test_template_variable_is_valid(self):
        """Тест валидации переменной."""
        variable = TemplateVariable(
            name="test_var",
            description="Test",
            validation_pattern=r"^[a-zA-Z]+$"
        )
        
        # Валидные значения
        assert variable.is_valid("test") is True
        assert variable.is_valid("Test") is True
        assert variable.is_valid("Variable") is True
        
        # Невалидные значения
        assert variable.is_valid("test123") is False
        assert variable.is_valid("123test") is False
        assert variable.is_valid("test-variable") is False
        
        # Без паттерна валидации
        no_pattern_variable = TemplateVariable(
            name="test",
            description="Test"
        )
        assert no_pattern_variable.is_valid("any_value") is True


class TestGeneratedCode:
    """Тесты для класса GeneratedCode."""
    
    def test_generated_code_creation(self):
        """Тест создания сгенерированного кода."""
        code_modules = {
            "module_object": "Test object code",
            "module_form": "Test form code"
        }
        
        result = GeneratedCode(
            object_name="TestObject",
            object_type="processing",
            code_modules=code_modules,
            form_layout="Test layout",
            metadata={"key": "value"},
            variables_used=["var1", "var2"],
            validation_results=["validation1"]
        )
        
        assert result.object_name == "TestObject"
        assert result.object_type == "processing"
        assert result.code_modules == code_modules
        assert result.form_layout == "Test layout"
        assert result.metadata == {"key": "value"}
        assert result.variables_used == ["var1", "var2"]
        assert result.validation_results == ["validation1"]
        assert result.generation_time is not None
    
    def test_generated_code_defaults(self):
        """Тест значений по умолчанию для сгенерированного кода."""
        result = GeneratedCode(
            object_name="TestObject",
            object_type="processing",
            code_modules={}
        )
        
        assert result.form_layout is None
        assert result.metadata == {}
        assert result.variables_used == []
        assert result.validation_results == []
        assert result.generation_time is not None


class TestTemplateProcessor:
    """Тесты для класса TemplateProcessor."""
    
    @pytest.fixture
    def mock_template_library_with_template(self, mock_template_library):
        """Фикстура библиотеки шаблонов с тестовым шаблоном."""
        from src.py_server.code_generation.templates.library import \
            TemplateMetadata
        
        metadata = TemplateMetadata(
            name="test_template",
            description="Test template",
            version="1.0.0",
            object_type="processing",
            complexity_level="simple",
            author="Test"
        )
        
        template_content = {
            "module_object": """
&НаСервере
Процедура {object_name}() Экспорт
    // {description}
    Сообщить("Выполняется {object_name}");
    // TODO: Добавить основную логику здесь
КонецПроцедуры
            """.strip(),
            "module_form": """
&НаКлиенте
Процедура КнопкаВыполнитьНажатие(Кнопка)
    // Обработка для {object_name}
    {object_name}();
КонецПроцедуры
            """.strip()
        }
        
        from src.py_server.code_generation.templates.library import \
            CodeTemplate
        template = CodeTemplate(
            metadata=metadata,
            template_content=template_content,
            variables={
                "object_name": {
                    "description": "Имя объекта",
                    "default": "МойОбъект",
                    "required": True,
                    "validation_pattern": "^[a-zA-Zа-яА-Я_][a-zA-Zа-яА-Я0-9_]*$",
                    "example": "ТестоваяОбработка"
                },
                "description": {
                    "description": "Описание объекта",
                    "default": "",
                    "required": True,
                    "validation_pattern": "^.{10,200}$",
                    "example": "Тестовая обработка для проверки функционала"
                }
            },
            validation_rules=[
                "Проверить наличие TODO комментариев",
                "Проверить баланс скобок"
            ]
        )
        
        mock_template_library.save_template(template)
        return mock_template_library
    
    def test_template_processor_initialization(self, mock_template_library):
        """Тест инициализации процессора шаблонов."""
        processor = TemplateProcessor(mock_template_library)
        
        assert processor.template_library == mock_template_library
        assert len(processor.builtin_variables) > 0
        assert 'current_date' in processor.builtin_variables
        assert 'current_time' in processor.builtin_variables
        assert len(processor.safe_patterns) > 0
    
    def test_generate_from_template_success(self, mock_template_library_with_template):
        """Тест успешной генерации из шаблона."""
        processor = TemplateProcessor(mock_template_library_with_template)
        
        variables = {
            "object_name": "ТестоваяОбработка",
            "description": "Тестовая обработка для проверки функционала"
        }
        
        result = processor.generate_from_template("test_template", variables, "TestObject")
        
        assert isinstance(result, GeneratedCode)
        assert result.object_name == "TestObject"
        assert result.object_type == "processing"
        assert len(result.code_modules) == 2
        assert "module_object" in result.code_modules
        assert "module_form" in result.code_modules
        
        # Проверяем замену переменных
        object_code = result.code_modules["module_object"]
        assert "ТестоваяОбработка" in object_code
        assert "Тестовая обработка для проверки функционала" in object_code
        assert "Выполняется ТестоваяОбработка" in object_code
        
        # Проверяем обработку TODO комментариев
        assert "TODO" not in object_code  # TODO должно быть заменено
    
    def test_generate_from_template_missing_required_variable(self, mock_template_library_with_template):
        """Тест генерации с отсутствующей обязательной переменной."""
        processor = TemplateProcessor(mock_template_library_with_template)
        
        variables = {
            "object_name": "ТестоваяОбработка"
            # description отсутствует
        }
        
        with pytest.raises(ValueError, match="Отсутствуют обязательные переменные"):
            processor.generate_from_template("test_template", variables)
    
    def test_generate_from_template_invalid_variable_value(self, mock_template_library_with_template):
        """Тест генерации с невалидным значением переменной."""
        processor = TemplateProcessor(mock_template_library_with_template)
        
        variables = {
            "object_name": "123InvalidName",  # Невалидное имя (начинается с цифры)
            "description": "Test description"
        }
        
        with pytest.raises(ValueError, match="Некорректные значения переменных"):
            processor.generate_from_template("test_template", variables)
    
    def test_generate_from_template_nonexistent_template(self, mock_template_library):
        """Тест генерации из несуществующего шаблона."""
        processor = TemplateProcessor(mock_template_library)
        
        variables = {
            "object_name": "TestObject",
            "description": "Test description"
        }
        
        with pytest.raises(ValueError, match="Шаблон 'nonexistent' не найден"):
            processor.generate_from_template("nonexistent", variables)
    
    def test_replace_todo_comments(self, mock_template_library_with_template):
        """Тест замены комментариев TODO."""
        processor = TemplateProcessor(mock_template_library_with_template)
        
        code_with_todo = """
&НаСервере
Процедура Тест() Экспорт
    // TODO: Добавить основную логику здесь
КонецПроцедуры
        """.strip()
        
        variables = {"object_type": "processing"}
        processed_code = processor._replace_todo_comments(code_with_todo, variables)
        
        assert "TODO" not in processed_code
        assert "Основная логика обработки данных" in processed_code
    
    def test_apply_code_formatting(self, mock_template_library):
        """Тест применения форматирования кода."""
        processor = TemplateProcessor(mock_template_library)
        
        unformatted_code = """

&НаСервере
Процедура Тест() Экспорт


    
    Сообщить("Тест");    
    
    
КонецПроцедуры


        """.strip()
        
        formatted_code = processor._apply_code_formatting(unformatted_code)
        
        lines = formatted_code.split('\n')
        # Проверяем, что нет множественных пустых строк
        consecutive_empty = 0
        for line in lines:
            if line.strip() == '':
                consecutive_empty += 1
                assert consecutive_empty <= 1
            else:
                consecutive_empty = 0
    
    def test_to_pascal_case(self, mock_template_library):
        """Тест преобразования в PascalCase."""
        processor = TemplateProcessor(mock_template_library)
        
        assert processor._to_pascal_case("test_object") == "TestObject"
        assert processor._to_pascal_case("test_object_123") == "TestObject123"
        assert processor._to_pascal_case("тест_объект") == "ТестОбъект"
        assert processor._to_pascal_case("test") == "Test"
        assert processor._to_pascal_case("") == ""
    
    def test_to_camel_case(self, mock_template_library):
        """Тест преобразования в camelCase."""
        processor = TemplateProcessor(mock_template_library)
        
        assert processor._to_camel_case("TestObject") == "testObject"
        assert processor._to_camel_case("test_object") == "testObject"
        assert processor._to_camel_case("Test_Object_123") == "testObject123"
        assert processor._to_camel_case("тестОбъект") == "тестОбъект"
        assert processor._to_camel_case("test") == "test"
        assert processor._to_camel_case("") == ""
    
    def test_check_brackets_balance(self, mock_template_library):
        """Тест проверки баланса скобок."""
        processor = TemplateProcessor(mock_template_library)
        
        # Правильный баланс
        valid_code = "Если (Условие1 И Условие2) Тогда\n    // код\nКонецЕсли;"
        assert processor._check_brackets_balance(valid_code) is True
        
        # Неправильный баланс
        invalid_code = "Если (Условие И Условие2 Тогда\n    // код\nКонецЕсли;"
        assert processor._check_brackets_balance(invalid_code) is False
        
        # Дополнительные скобки
        extra_brackets = "Если (Условие) И (Условие2)) Тогда\n    // код\nКонецЕсли;"
        assert processor._check_brackets_balance(extra_brackets) is False
    
    def test_check_comments_balance(self, mock_template_library):
        """Тест проверки баланса комментариев."""
        processor = TemplateProcessor(mock_template_library)
        
        # Правильный баланс
        valid_code = "/* Комментарий 1 */ код /* Комментарий 2 */"
        assert processor._check_comments_balance(valid_code) is True
        
        # Незакрытый комментарий
        invalid_code = "/* Незакрытый комментарий код"
        assert processor._check_comments_balance(invalid_code) is False
    
    def test_validate_generated_code(self, mock_template_library_with_template):
        """Тест валидации сгенерированного кода."""
        processor = TemplateProcessor(mock_template_library_with_template)
        
        # Загружаем шаблон
        template = mock_template_library_with_template.get_template_by_name("test_template")
        
        # Генерируем код
        variables = {
            "object_name": "TestObject",
            "description": "Test description"
        }
        generated_modules = {
            "module_object": processor._process_module_code(
                template.template_content["module_object"], variables
            )
        }
        
        validation_results = processor._validate_generated_code(generated_modules, template)
        
        # Проверяем результаты валидации
        assert isinstance(validation_results, list)
        # Валидация может найти нарушения или пройти успешно
    
    def test_preview_template(self, mock_template_library_with_template):
        """Тест предпросмотра шаблона."""
        processor = TemplateProcessor(mock_template_library_with_template)
        
        variables = {
            "object_name": "TestObject",
            "description": "Test description"
        }
        
        preview = processor.preview_template("test_template", variables)
        
        assert isinstance(preview, dict)
        assert len(preview) == 2  # module_object и module_form
        assert "module_object" in preview
        assert "module_form" in preview
        
        # Проверяем, что переменные заменены
        object_preview = preview["module_object"]
        assert "TestObject" in object_preview
        assert "Test description" in object_preview
    
    def test_get_template_variables(self, mock_template_library_with_template):
        """Тест получения переменных шаблона."""
        processor = TemplateProcessor(mock_template_library_with_template)
        
        variables = processor.get_template_variables("test_template")
        
        assert len(variables) == 2
        assert any(v.name == "object_name" for v in variables)
        assert any(v.name == "description" for v in variables)
        
        # Проверяем свойства переменной
        object_name_var = next(v for v in variables if v.name == "object_name")
        assert object_name_var.required is True
        assert object_name_var.validation_pattern != ""
        assert object_name_var.example_value != ""
    
    def test_get_template_variables_nonexistent(self, mock_template_library):
        """Тест получения переменных несуществующего шаблона."""
        processor = TemplateProcessor(mock_template_library)
        
        with pytest.raises(ValueError, match="Шаблон 'nonexistent' не найден"):
            processor.get_template_variables("nonexistent")


# Дополнительные тесты для конкретных генераций
class TestSpecificGenerations:
    """Тесты для специфических генераций кода."""
    
    def test_generate_main_logic_processing(self, mock_template_library):
        """Тест генерации основной логики для обработки."""
        processor = TemplateProcessor(mock_template_library)
        
        variables = {"object_type": "processing"}
        logic = processor._generate_main_logic(variables)
        
        assert "Основная логика обработки данных" in logic
        assert "Начинается обработка данных" in logic
    
    def test_generate_main_logic_report(self, mock_template_library):
        """Тест генерации основной логики для отчета."""
        processor = TemplateProcessor(mock_template_library)
        
        variables = {"object_type": "report"}
        logic = processor._generate_main_logic(variables)
        
        assert "Построение отчета" in logic
        assert "Формирование отчета" in logic
    
    def test_generate_validation_logic(self, mock_template_library):
        """Тест генерации логики валидации."""
        processor = TemplateProcessor(mock_template_library)
        
        logic = processor._generate_validation_logic({})
        
        assert "Валидация входных данных" in logic
        assert "ПустаяСтрока" in logic
        assert "ЗначениеЗаполнено" in logic
    
    def test_generate_error_handling(self, mock_template_library):
        """Тест генерации обработки ошибок."""
        processor = TemplateProcessor(mock_template_library)
        
        logic = processor._generate_error_handling({})
        
        assert "Обработка ошибок" in logic
        assert "Попытка" in logic
        assert "Исключение" in logic
        assert "ОписаниеОшибки" in logic