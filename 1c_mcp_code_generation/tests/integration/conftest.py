
"""
Конфигурация интеграционных тестов для 1C MCP Code Generation System.

Содержит общие fixtures и конфигурацию для интеграционных тестов,
покрывающих полный цикл генерации кода, валидацию и безопасность.
"""

import asyncio
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock

import pytest

from src.core.engine import CodeGenerationEngine
from src.core.validator import CodeValidator
from src.llm.client import LLMClient
from src.prompts.context import ContextualPromptBuilder
from src.prompts.manager import PromptManager
from src.prompts.optimizer import PromptOptimizer
from src.security.manager import SecurityManager
from src.templates.library import TemplateLibrary
from src.templates.manager import TemplateManager
from src.templates.processor import TemplateProcessor


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def temp_test_dir():
    """Создает временную директорию для тестов."""
    temp_dir = tempfile.mkdtemp(prefix="1c_mcp_integration_test_")
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
async def mock_llm_client():
    """Mock объект для LLM клиента."""
    client = AsyncMock(spec=LLMClient)
    
    # Настраиваем типичные ответы для тестирования
    client.generate_code.return_value = """
    // Автоматически сгенерированный код для обработки
    Процедура ВыполнитьОбработку() Экспорт
        // Основная логика обработки
        Сообщить("Обработка выполнена успешно");
    КонецПроцедуры
    """
    
    client.validate_code.return_value = {"valid": True, "issues": []}
    
    client.optimize_code.return_value = {
        "optimized": True,
        "improvements": ["Улучшена производительность", "Добавлены проверки"]
    }
    
    return client


@pytest.fixture
async def integration_test_setup(temp_test_dir, mock_llm_client):
    """Полная настройка для интеграционного тестирования."""
    # Создаем структуру проекта
    config_dir = temp_test_dir / "config"
    src_dir = temp_test_dir / "src"
    templates_dir = temp_test_dir / "templates"
    
    for dir_path in [config_dir, src_dir, templates_dir]:
        dir_path.mkdir(parents=True)
    
    # Инициализируем компоненты
    engine = CodeGenerationEngine(
        llm_client=mock_llm_client,
        base_path=src_dir
    )
    
    validator = CodeValidator()
    
    security_manager = SecurityManager(
        config_path=config_dir / "security.json"
    )
    
    template_manager = TemplateManager(
        templates_dir=templates_dir
    )
    
    prompt_manager = PromptManager(
        prompts_dir=src_dir / "prompts"
    )
    
    optimizer = PromptOptimizer(
        prompt_manager=prompt_manager,
        llm_client=mock_llm_client
    )
    
    context_builder = ContextualPromptBuilder(
        prompt_manager=prompt_manager
    )
    
    template_library = TemplateLibrary(
        templates_dir=templates_dir
    )
    
    template_processor = TemplateProcessor(
        template_library=template_library,
        llm_client=mock_llm_client
    )
    
    # Создаем конфигурационные файлы
    security_config = {
        "enable_sql_injection_check": True,
        "enable_code_analysis": True,
        "blocked_patterns": [
            "SELECT.*FROM.*WHERE",
            "EXEC.*SP_",
            "SHUTDOWN"
        ],
        "allowed_modules": [
            "Справочники",
            "Документы",
            "Обработки",
            "Отчеты"
        ]
    }
    
    with open(config_dir / "security.json", "w", encoding="utf-8") as f:
        json.dump(security_config, f, ensure_ascii=False, indent=2)
    
    return {
        "engine": engine,
        "validator": validator,
        "security_manager": security_manager,
        "template_manager": template_manager,
        "prompt_manager": prompt_manager,
        "optimizer": optimizer,
        "context_builder": context_builder,
        "template_library": template_library,
        "template_processor": template_processor,
        "temp_dir": temp_test_dir,
        "config_dir": config_dir,
        "src_dir": src_dir,
        "templates_dir": templates_dir,
        "llm_client": mock_llm_client
    }


@pytest.fixture
def sample_generation_requests():
    """Примеры запросов для генерации кода."""
    return [
        {
            "request_type": "processing",
            "description": "Создать обработку для анализа продаж",
            "parameters": {
                "object_name": "АнализПродаж",
                "description": "Обработка для анализа продаж по периодам",
                "author": "ТестСистема",
                "features": ["Отчетность", "Фильтры", "Экспорт"]
            }
        },
        {
            "request_type": "report",
            "description": "Создать отчет по остаткам товаров",
            "parameters": {
                "object_name": "ОстаткиТоваров",
                "description": "Отчет по остаткам товаров на складах",
                "author": "ТестСистема",
                "period_type": "Дата",
                "grouping": ["Номенклатура", "Склад"]
            }
        },
        {
            "request_type": "catalog",
            "description": "Создать справочник клиентов",
            "parameters": {
                "object_name": "Клиенты",
                "description": "Справочник клиентов компании",
                "author": "ТестСистема",
                "hierarchical": True,
                "parent_field": "Родитель",
                "code_length": 10
            }
        },
        {
            "request_type": "document",
            "description": "Создать документ заказа покупателя",
            "parameters": {
                "object_name": "ЗаказПокупателя",
                "description": "Документ для оформления заказов покупателей",
                "author": "ТестСистема",
                "posting": True,
                "tabular_sections": ["Товары", "Услуги"],
                "registers": ["Продажи", "Взаиморасчеты"]
            }
        }
    ]


@pytest.fixture
def sample_1c_code():
    """Примеры кода 1C для тестирования."""
    return {
        "valid_processing": """
        // Обработка для анализа данных
        &НаСервере
        Процедура ВыполнитьАнализ() Экспорт
            // Основная логика анализа
            Запрос = Новый Запрос;
            Запрос.Текст = "ВЫБРАТЬ * ИЗ Справочник.Номенклатура";
            Результат = Запрос.Выполнить();
            Выборка = Результат.Выбрать();
            
            Пока Выборка.Следующий() Цикл
                Сообщить("Номенклатура: " + Выборка.Наименование);
            КонецЦикла;
        КонецПроцедуры
        """,
        
        "invalid_sql_injection": """
        // Код с потенциальной SQL injection
        Процедура ВыполнитьЗапрос(ПользовательскийЗапрос) Экспорт
            Запрос = Новый Запрос;
            Запрос.Текст = "ВЫБРАТЬ * ИЗ Справочник.Номенклатура ГДЕ Наименование = '" + 
                         ПользовательскийЗапрос + "'";
            Результат = Запрос.Выполнить();
            Возврат Результат;
        КонецПроцедуры
        """,
        
        "dangerous_operations": """
        // Код с опасными операциями
        Процедура ОпасныеОперации() Экспорт
            // Попытка остановить сервер
            Система.ЗавершитьРаботу();
            
            // Удаление данных
            Справочники.Номенклатура.Удалить(Справочники.Номенклатура.ПустаяСсылка());
            
            // Небезопасный доступ к файловой системе
            Файл = Новый Файл("C:/Windows/System32/");
        КонецПроцедуры
        """,
        
        "proper_validation": """
        // Код с правильной валидацией
        Функция ПолучитьНоменклатуру(Код) Экспорт
            Если ПустаяСтрока(Код) Тогда
                Возврат Неопределено;
            КонецЕсли;
            
            Запрос = Новый Запрос;
            Запрос.Текст = "ВЫБРАТЬ ПЕРВЫЕ 1 * ИЗ Справочник.Номенклатура ГДЕ Код = &Код";
            Запрос.УстановитьПараметр("Код", Код);
            
            Попытка
                Результат = Запрос.Выполнить();
                Выборка = Результат.Выбрать();
                Если Выборка.Следующий() Тогда
                    Возврат Выборка.Ссылка;
                Иначе
                    Возврат Неопределено;
                КонецЕсли;
            Исключение
                ЗаписатьЛог("Ошибка выполнения запроса: " + ОписаниеОшибки());
                Возврат Неопределено;
            КонецПопытки;
        КонецФункции
        """
    }


@pytest.fixture
async def mcp_mock_client():
    """Mock клиент для тестирования MCP интеграции."""
    mock_client = AsyncMock()
    
    # Имитируем MCP методы
    mock_client.initialize = AsyncMock(return_value={
        "protocolVersion": "2024-11-05",
        "capabilities": {
            "tools": {}
        },
        "serverInfo": {
            "name": "1C MCP Code Generation Server",
            "version": "1.0.0"
        }
    })
    
    mock_client.list_tools = AsyncMock(return_value={
        "tools": [
            {
                "name": "generate_code",
                "description": "Генерирует код для объектов 1C",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "object_type": {"type": "string"},
                        "description": {"type": "string"},
                        "parameters": {"type": "object"}
                    }
                }
            },
            {
                "name": "validate_code",
                "description": "Валидирует сгенерированный код",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string"}
                    }
                }
            }
        ]
    })
    
    mock_client.call_tool = AsyncMock(return_value={
        "content": [
            {
                "type": "text",
                "text": "Код успешно сгенерирован и валидирован"
            }
        ]
    })
    
    return mock_client


@pytest.fixture
def performance_test_data():
    """Данные для тестирования производительности."""
    return {
        "large_request": {
            "object_type": "processing",
            "description": "Комплексная обработка с множеством функций",
            "complexity": "high",
            "expected_generation_time": 30  # секунд
        },
        "concurrent_requests": [
            {
                "object_type": "report",
                "description": f"Отчет {i}",
                "complexity": "medium"
            }
            for i in range(10)
        ]
    }


@pytest.fixture
async def audit_logger(temp_test_dir):
    """Создает логгер для аудита тестов."""
    audit_dir = temp_test_dir / "logs"
    audit_dir.mkdir(exist_ok=True)
    
    audit_file = audit_dir / "integration_tests.log"
    
    class AuditLogger:
        def __init__(self, log_file: Path):
            self.log_file = log_file
            
        def log_test_start(self, test_name: str, params: Dict[str, Any]):
            self._write_log("START", test_name, params)
            
        def log_test_result(self, test_name: str, result: str, duration: float, details: Optional[Dict] = None):
            self._write_log("RESULT", test_name, {
                "result": result,
                "duration": duration,
                "details": details or {}
            })
            
        def log_error(self, test_name: str, error: Exception, context: Dict[str, Any] = None):
            self._write_log("ERROR", test_name, {
                "error": str(error),
                "error_type": type(error).__name__,
                "context": context or {}
            })
            
        def _write_log(self, level: str, test_name: str, data: Dict[str, Any]):
            import datetime
            timestamp = datetime.datetime.now().isoformat()
            log_entry = {
                "timestamp": timestamp,
                "level": level,
                "test": test_name,
                **data
            }
            
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    
    return AuditLogger(audit_file)


def pytest_configure(config):
    """Настройка pytest для интеграционных тестов."""
    config.addinivalue_line(
        "markers", "integration: пометить интеграционные тесты"
    )
    config.addinivalue_line(
        "markers", "slow: пометить медленные тесты"
    )
    config.addinivalue_line(
        "markers", "security: пометить тесты безопасности"
    )
    config.addinivalue_line(
        "markers", "performance: пометить тесты производительности"
    )


def pytest_collection_modifyitems(config, items):
    """Модификация коллекции тестов."""
    for item in items:
        # Автоматически добавляем маркировку интеграционных тестов
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
            
        # Помечаем медленные тесты
        if "performance" in item.name.lower() or "full" in item.name.lower():
            item.add_marker(pytest.mark.slow)
            
        # Помечаем тесты безопасности
        if "security" in item.name.lower() or "sql" in item.name.lower():
            item.add_marker(pytest.mark.security)