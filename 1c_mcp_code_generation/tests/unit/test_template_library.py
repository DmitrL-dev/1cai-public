
"""
Тесты для библиотеки шаблонов.
"""

import json
from unittest.mock import patch


from src.py_server.code_generation.templates.library import (CodeTemplate,
                                                             TemplateLibrary,
                                                             TemplateMetadata)


class TestTemplateMetadata:
    """Тесты для класса TemplateMetadata."""
    
    def test_template_metadata_creation(self):
        """Тест создания метаданных шаблона."""
        metadata = TemplateMetadata(
            name="test_template",
            description="Test template description",
            version="1.0.0",
            object_type="processing",
            complexity_level="simple",
            author="Test Author",
            tags=["test", "simple"],
            dependencies=["dependency1"],
            requirements=["requirement1"]
        )
        
        assert metadata.name == "test_template"
        assert metadata.description == "Test template description"
        assert metadata.version == "1.0.0"
        assert metadata.object_type == "processing"
        assert metadata.complexity_level == "simple"
        assert metadata.author == "Test Author"
        assert metadata.tags == ["test", "simple"]
        assert metadata.dependencies == ["dependency1"]
        assert metadata.requirements == ["requirement1"]
        assert metadata.usage_count == 0
        assert metadata.rating == 0.0
        assert metadata.created_at is not None
        assert metadata.updated_at is not None
    
    def test_template_metadata_defaults(self):
        """Тест значений по умолчанию для метаданных."""
        metadata = TemplateMetadata(
            name="test",
            description="Test",
            version="1.0.0",
            object_type="processing",
            complexity_level="simple",
            author="Test"
        )
        
        assert metadata.tags == []
        assert metadata.dependencies == []
        assert metadata.requirements == []
        assert metadata.usage_count == 0
        assert metadata.rating == 0.0


class TestCodeTemplate:
    """Тесты для класса CodeTemplate."""
    
    def test_code_template_creation(self):
        """Тест создания шаблона кода."""
        metadata = TemplateMetadata(
            name="test_template",
            description="Test template",
            version="1.0.0",
            object_type="processing",
            complexity_level="simple",
            author="Test"
        )
        
        template_content = {
            "module_object": "Test object code",
            "module_form": "Test form code"
        }
        
        template = CodeTemplate(
            metadata=metadata,
            template_content=template_content,
            form_layout="Test form layout",
            configuration={"key": "value"},
            variables={"var1": "value1"},
            validation_rules=["rule1", "rule2"],
            examples=["example1", "example2"]
        )
        
        assert template.metadata.name == "test_template"
        assert template.template_content == template_content
        assert template.form_layout == "Test form layout"
        assert template.configuration == {"key": "value"}
        assert template.variables == {"var1": "value1"}
        assert template.validation_rules == ["rule1", "rule2"]
        assert template.examples == ["example1", "example2"]
    
    def test_code_template_to_dict(self):
        """Тест преобразования шаблона в словарь."""
        metadata = TemplateMetadata(
            name="test_template",
            description="Test template",
            version="1.0.0",
            object_type="processing",
            complexity_level="simple",
            author="Test"
        )
        
        template_content = {"module_object": "Test code"}
        
        template = CodeTemplate(
            metadata=metadata,
            template_content=template_content
        )
        
        result = template.to_dict()
        
        assert "metadata" in result
        assert "template_content" in result
        assert result["metadata"]["name"] == "test_template"
        assert result["template_content"] == template_content
        assert isinstance(result["metadata"]["created_at"], str)
        assert isinstance(result["metadata"]["updated_at"], str)
    
    def test_code_template_from_dict(self):
        """Тест создания шаблона из словаря."""
        data = {
            "metadata": {
                "name": "test_template",
                "description": "Test template",
                "version": "1.0.0",
                "object_type": "processing",
                "complexity_level": "simple",
                "author": "Test",
                "created_at": "2025-10-30T09:40:34Z",
                "updated_at": "2025-10-30T09:40:34Z",
                "tags": [],
                "usage_count": 0,
                "rating": 0.0,
                "dependencies": [],
                "requirements": []
            },
            "template_content": {"module_object": "Test code"},
            "form_layout": "Test layout",
            "configuration": {},
            "variables": {},
            "validation_rules": [],
            "examples": []
        }
        
        template = CodeTemplate.from_dict(data)
        
        assert template.metadata.name == "test_template"
        assert template.template_content == {"module_object": "Test code"}
        assert template.form_layout == "Test layout"
        assert isinstance(template.metadata.created_at, type(template.metadata.updated_at))


class TestTemplateLibrary:
    """Тесты для класса TemplateLibrary."""
    
    def test_template_library_initialization(self, temp_dir):
        """Тест инициализации библиотеки шаблонов."""
        library = TemplateLibrary(temp_dir)
        
        assert library.templates_dir == temp_dir
        assert len(library.object_types) == 4
        assert "processing" in library.object_types
        assert "report" in library.object_types
        assert "catalog" in library.object_types
        assert "document" in library.object_types
        
        # Проверяем создание подпапок
        for obj_type in library.object_types:
            dir_path = temp_dir / obj_type
            assert dir_path.exists()
    
    def test_template_library_ensure_directories(self, temp_dir):
        """Тест создания директорий библиотеки."""
        library = TemplateLibrary(temp_dir)
        
        for obj_type in library.object_types:
            dir_path = temp_dir / obj_type
            assert dir_path.exists()
            assert dir_path.is_dir()
    
    def test_load_all_templates(self, temp_dir):
        """Тест загрузки всех шаблонов."""
        # Создаем тестовый шаблон
        template_data = {
            "metadata": {
                "name": "test_template",
                "description": "Test template",
                "version": "1.0.0",
                "object_type": "processing",
                "complexity_level": "simple",
                "author": "Test",
                "created_at": "2025-10-30T09:40:34Z",
                "updated_at": "2025-10-30T09:40:34Z",
                "tags": [],
                "usage_count": 0,
                "rating": 0.0,
                "dependencies": [],
                "requirements": []
            },
            "template_content": {"module_object": "Test code"},
            "form_layout": None,
            "configuration": {},
            "variables": {},
            "validation_rules": [],
            "examples": []
        }
        
        template_file = temp_dir / "processing" / "test_template.json"
        with open(template_file, 'w', encoding='utf-8') as f:
            json.dump(template_data, f, ensure_ascii=False, indent=2)
        
        library = TemplateLibrary(temp_dir)
        
        # Проверяем, что шаблон загружен
        assert len(library._templates_cache) == 1
        assert "processing.test_template" in library._templates_cache
        template = library._templates_cache["processing.test_template"]
        assert template.metadata.name == "test_template"
    
    def test_get_template(self, mock_template_library):
        """Тест получения шаблона."""
        # Сначала сохраняем шаблон
        template = mock_template_library.create_processing_template()
        mock_template_library.save_template(template)
        
        # Получаем шаблон
        retrieved_template = mock_template_library.get_template("processing", "basic_processing")
        
        assert retrieved_template is not None
        assert retrieved_template.metadata.name == "basic_processing"
        assert retrieved_template.metadata.object_type == "processing"
    
    def test_get_template_not_found(self, mock_template_library):
        """Тест получения несуществующего шаблона."""
        template = mock_template_library.get_template("processing", "nonexistent")
        assert template is None
    
    def test_list_templates_all(self, mock_template_library):
        """Тест списка всех шаблонов."""
        # Инициализируем библиотеку базовыми шаблонами
        mock_template_library.initialize_library()
        
        templates = mock_template_library.list_templates()
        
        assert len(templates) == 4  # 4 базовых шаблона
        assert any("processing.basic_processing" in t for t in templates)
        assert any("report.basic_report" in t for t in templates)
        assert any("catalog.basic_catalog" in t for t in templates)
        assert any("document.basic_document" in t for t in templates)
    
    def test_list_templates_by_type(self, mock_template_library):
        """Тест списка шаблонов по типу."""
        # Инициализируем библиотеку базовыми шаблонами
        mock_template_library.initialize_library()
        
        processing_templates = mock_template_library.list_templates("processing")
        
        assert len(processing_templates) == 1
        assert processing_templates[0] == "processing.basic_processing"
    
    def test_list_templates_by_type_none(self, mock_template_library):
        """Тест списка шаблонов по несуществующему типу."""
        templates = mock_template_library.list_templates("nonexistent")
        assert templates == []
    
    def test_get_templates_by_complexity(self, mock_template_library):
        """Тест получения шаблонов по сложности."""
        mock_template_library.initialize_library()
        
        simple_templates = mock_template_library.get_templates_by_complexity("simple")
        standard_templates = mock_template_library.get_templates_by_complexity("standard")
        advanced_templates = mock_template_library.get_templates_by_complexity("advanced")
        
        assert len(simple_templates) == 1  # basic_processing
        assert len(standard_templates) == 1  # basic_report
        assert len(advanced_templates) == 1  # basic_document
        
        assert simple_templates[0].metadata.name == "basic_processing"
        assert standard_templates[0].metadata.name == "basic_report"
        assert advanced_templates[0].metadata.name == "basic_document"
    
    def test_search_templates(self, mock_template_library):
        """Тест поиска шаблонов."""
        mock_template_library.initialize_library()
        
        # Поиск по названию
        results = mock_template_library.search_templates("basic")
        assert len(results) == 4  # Все шаблоны содержат "basic"
        
        # Поиск по описанию
        results = mock_template_library.search_templates("обработки")
        assert len(results) == 1  # Только обработка
        assert results[0].metadata.name == "basic_processing"
        
        # Поиск по тегам
        results = mock_template_library.search_templates("skd")
        assert len(results) == 1  # Только отчет
        assert results[0].metadata.name == "basic_report"
        
        # Поиск по несуществующему запросу
        results = mock_template_library.search_templates("nonexistent")
        assert len(results) == 0
    
    def test_save_template(self, mock_template_library):
        """Тест сохранения шаблона."""
        template = mock_template_library.create_processing_template()
        
        result = mock_template_library.save_template(template)
        
        assert result is True
        assert "processing.basic_processing" in mock_template_library._templates_cache
        
        # Проверяем файл
        template_file = mock_template_library.templates_dir / "processing" / "basic_processing.json"
        assert template_file.exists()
        
        # Проверяем содержимое файла
        with open(template_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            assert data["metadata"]["name"] == "basic_processing"
    
    def test_save_template_increment_usage(self, mock_template_library):
        """Тест инкремента счетчика использования при сохранении."""
        template = mock_template_library.create_processing_template()
        
        # Сохраняем несколько раз
        for _ in range(3):
            mock_template_library.save_template(template)
        
        saved_template = mock_template_library._templates_cache["processing.basic_processing"]
        assert saved_template.metadata.usage_count == 3
    
    def test_save_template_error(self, mock_template_library, temp_dir):
        """Тест ошибки сохранения шаблона."""
        template = mock_template_library.create_processing_template()
        
        # Симулируем ошибку записи файла
        with patch.object(mock_template_library.templates_dir / "processing", 'open', side_effect=IOError):
            result = mock_template_library.save_template(template)
            
            assert result is False
            assert "processing.basic_processing" not in mock_template_library._templates_cache
    
    def test_create_processing_template(self, mock_template_library):
        """Тест создания шаблона обработки."""
        template = mock_template_library.create_processing_template()
        
        assert template.metadata.name == "basic_processing"
        assert template.metadata.object_type == "processing"
        assert template.metadata.complexity_level == "simple"
        assert "module_object" in template.template_content
        assert "module_form" in template.template_content
        assert template.form_layout is not None
        assert len(template.validation_rules) == 3
        assert len(template.examples) == 3
    
    def test_create_report_template(self, mock_template_library):
        """Тест создания шаблона отчета."""
        template = mock_template_library.create_report_template()
        
        assert template.metadata.name == "basic_report"
        assert template.metadata.object_type == "report"
        assert template.metadata.complexity_level == "standard"
        assert "module_object" in template.template_content
        assert "module_form" in template.template_content
        assert "Система компоновки данных" in template.metadata.dependencies
        assert "Право на чтение данных" in template.metadata.requirements
    
    def test_create_catalog_template(self, mock_template_library):
        """Тест создания шаблона справочника."""
        template = mock_template_library.create_catalog_template()
        
        assert template.metadata.name == "basic_catalog"
        assert template.metadata.object_type == "catalog"
        assert template.metadata.complexity_level == "standard"
        assert "module_object" in template.template_content
        assert "module_manager" in template.template_content
        assert "Проверить уникальность кода" in template.validation_rules
    
    def test_create_document_template(self, mock_template_library):
        """Тест создания шаблона документа."""
        template = mock_template_library.create_document_template()
        
        assert template.metadata.name == "basic_document"
        assert template.metadata.object_type == "document"
        assert template.metadata.complexity_level == "advanced"
        assert "module_object" in template.template_content
        assert "module_form" in template.template_content
        assert "ОбработкаПроведения" in template.template_content["module_object"]
        assert "ОбработкаУдаленияПроведения" in template.template_content["module_object"]
    
    def test_initialize_library(self, mock_template_library):
        """Тест инициализации библиотеки базовыми шаблонами."""
        # Проверяем, что библиотека пустая
        assert len(mock_template_library._templates_cache) == 0
        
        # Инициализируем
        mock_template_library.initialize_library()
        
        # Проверяем, что создались базовые шаблоны
        templates = mock_template_library.list_templates()
        assert len(templates) == 4
        
        # Проверяем наличие всех типов объектов
        for obj_type in ["processing", "report", "catalog", "document"]:
            templates_by_type = mock_template_library.list_templates(obj_type)
            assert len(templates_by_type) == 1
    
    def test_get_template_statistics(self, mock_template_library):
        """Тест получения статистики библиотеки."""
        mock_template_library.initialize_library()
        
        stats = mock_template_library.get_template_statistics()
        
        assert stats["total_templates"] == 4
        assert stats["templates_by_type"]["processing"] == 1
        assert stats["templates_by_type"]["report"] == 1
        assert stats["templates_by_type"]["catalog"] == 1
        assert stats["templates_by_type"]["document"] == 1
        
        # Проверяем категории сложности
        complexity_stats = stats["templates_by_complexity"]
        assert complexity_stats["simple"] == 1
        assert complexity_stats["standard"] == 1
        assert complexity_stats["advanced"] == 1
        assert complexity_stats["enterprise"] == 0
        
        assert stats["average_rating"] == 0.0  # Рейтинги по умолчанию
        assert stats["total_usage"] == 0  # Использование по умолчанию
    
    def test_get_template_statistics_empty_library(self, mock_template_library):
        """Тест статистики пустой библиотеки."""
        stats = mock_template_library.get_template_statistics()
        
        assert stats["total_templates"] == 0
        assert stats["templates_by_type"] == {}
        assert stats["templates_by_complexity"] == {}
        assert stats["average_rating"] == 0.0
        assert stats["total_usage"] == 0