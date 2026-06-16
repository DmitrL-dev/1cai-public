
"""
Конфигурация pytest для тестирования системы генерации кода 1С.
"""

import asyncio
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest

# Добавляем путь к исходному коду
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.py_server.code_generation.llm.client import LLMClient
from src.py_server.code_generation.prompts.manager import (PromptManager,
                                                           PromptTemplate)
from src.py_server.code_generation.security.manager import SecurityManager
from src.py_server.code_generation.templates.library import (CodeTemplate,
                                                             TemplateLibrary)
from src.py_server.code_generation.validation.validator import CodeValidator


@pytest.fixture
def temp_dir():
    """Временная директория для тестов."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def mock_prompt_manager(temp_dir):
    """Фикстура для мок-менеджера промптов."""
    return PromptManager(temp_dir)


@pytest.fixture
def sample_prompt_template():
    """Пример шаблона промпта для тестов."""
    return PromptTemplate(
        name="test_prompt",
        version="1.0.0",
        description="Тестовый промпт",
        object_type="processing",
        content="Ты - эксперт по 1С. {description}",
        variables=["description"],
        context_requirements={"include_forms": "да"},
        min_tokens=100,
        max_tokens=1000,
        quality_score=0.8
    )


@pytest.fixture
def mock_template_library(temp_dir):
    """Фикстура для библиотеки шаблонов."""
    return TemplateLibrary(temp_dir)


@pytest.fixture
def sample_code_template():
    """Пример шаблона кода для тестов."""
    from src.py_server.code_generation.templates.library import \
        TemplateMetadata
    
    metadata = TemplateMetadata(
        name="test_template",
        description="Тестовый шаблон",
        version="1.0.0",
        object_type="processing",
        complexity_level="simple",
        author="Test"
    )
    
    template_content = {
        "module_object": "&НаСервере\nПроцедура Тест() Экспорт\n    // {description}\nКонецПроцедуры"
    }
    
    return CodeTemplate(
        metadata=metadata,
        template_content=template_content
    )


@pytest.fixture
def mock_llm_client():
    """Фикстура для клиента LLM."""
    client = Mock(spec=LLMClient)
    client.generate.return_value = "Сгенерированный код 1С"
    client.validate.return_value = {"valid": True, "score": 0.9}
    return client


@pytest.fixture
def mock_code_validator():
    """Фикстура для валидатора кода."""
    validator = Mock(spec=CodeValidator)
    validator.validate_comprehensive.return_value = {
        "valid": True,
        "errors": [],
        "warnings": [],
        "score": 0.9
    }
    return validator


@pytest.fixture
def mock_security_manager():
    """Фикстура для менеджера безопасности."""
    manager = Mock(spec=SecurityManager)
    manager.analyze_security.return_value = {
        "security_level": "LOW",
        "threats": [],
        "score": 0.9
    }
    return manager


@pytest.fixture
def event_loop():
    """Цикл событий для async тестов."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# Параметры для тестирования разных конфигураций
@pytest.fixture(params=[
    {"llm": {"provider": "mock"}, "templates": {"enabled": True}},
    {"llm": {"provider": "openai", "api_key": "test_key"}, "templates": {"enabled": False}},
    {"llm": {"provider": "anthropic"}, "security": {"strict_mode": True}}
])
def test_config(request):
    """Параметризованная конфигурация для тестов."""
    return request.param


# Исключения для тестирования
class TestException(Exception):
    """Исключение для тестов."""


# Маркеры для категоризации тестов
pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.unit,
    pytest.mark.slow
]


def pytest_configure(config):
    """Настройка pytest."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "unit: mark test as unit test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )


def pytest_collection_modifyitems(config, items):
    """Модификация коллекции тестов."""
    for item in items:
        if "integration" in item.nodeid:
            item.add_marker(pytest.mark.integration)
        else:
            item.add_marker(pytest.mark.unit)


# Фикстуры для тестовых данных
@pytest.fixture
def valid_bsl_code():
    """Пример валидного кода BSL."""
    return """
&НаСервере
Процедура ВыполнитьОбработку() Экспорт
    Сообщить("Начинается обработка");
    
    Попытка
        // Основная логика
        Результат = ОбработатьДанные();
        Сообщить("Обработка завершена: " + Результат);
    Исключение
        Сообщить("Ошибка: " + ОписаниеОшибки());
    КонецПопытки;
КонецПроцедуры
    """.strip()


@pytest.fixture
def invalid_bsl_code():
    """Пример невалидного кода BSL."""
    return """
&НаСервере
Процедура ВыполнитьОбработку()
    Сообщить("Некорректная процедура
    // Незакрытая строка
КонецПроцедуры
    """.strip()


@pytest.fixture
def security_risky_code():
    """Пример кода с потенциальными угрозами безопасности."""
    return """
&НаСервере
Процедура ВыполнитьОбработку() Экспорт
    // Опасные функции
    Выполнить("system('rm -rf /')");
    
    Вычислить("os.system('malicious_command')");
    
    // SQL инъекция
    Запрос = Новый Запрос;
    Запрос.Текст = "ВЫБРАТЬ * ИЗ Таблица WHERE Поле = '" + ПользовательскийВвод + "'";
    
    // Выполнение произвольного кода
    Результат = Выполнить(ПользовательскийКод);
КонецПроцедуры
    """.strip()


# Константы для тестирования
class TestConstants:
    """Константы для тестирования."""
    
    VALID_OBJECT_TYPES = ["processing", "report", "catalog", "document"]
    INVALID_OBJECT_TYPES = ["invalid_type", "", None]
    
    COMPLEXITY_LEVELS = ["simple", "standard", "advanced", "enterprise"]
    
    QUALITY_REQUIREMENTS = [
        "high_coverage", "performance", "security", 
        "maintainability", "compliance", "optimization"
    ]
    
    SAMPLE_VARIABLES = {
        "object_name": "ТестоваяОбработка",
        "description": "Тестовая обработка для проверки функционала",
        "input_params": "ДатаНачала, ДатаОкончания",
        "output_result": "Обновленные данные"
    }