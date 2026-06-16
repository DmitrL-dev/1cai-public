
"""
Тесты для менеджера промптов.
"""

from unittest.mock import patch


from src.py_server.code_generation.prompts.manager import (PromptManager,
                                                           PromptTemplate)


class TestPromptTemplate:
    """Тесты для класса PromptTemplate."""
    
    def test_prompt_template_creation(self, sample_prompt_template):
        """Тест создания шаблона промпта."""
        assert sample_prompt_template.name == "test_prompt"
        assert sample_prompt_template.version == "1.0.0"
        assert sample_prompt_template.object_type == "processing"
        assert len(sample_prompt_template.variables) == 1
        assert sample_prompt_template.quality_score == 0.8
        assert sample_prompt_template.created_at is not None
        assert sample_prompt_template.updated_at is not None
    
    def test_prompt_template_defaults(self):
        """Тест значений по умолчанию для шаблона промпта."""
        template = PromptTemplate(
            name="test",
            version="1.0.0",
            description="Test",
            object_type="processing",
            content="Test content",
            variables=[],
            context_requirements={},
            min_tokens=0,
            max_tokens=1000,
            quality_score=0.0
        )
        
        assert template.usage_count == 0
        assert template.success_rate == 0.0
        assert template.created_at is not None
        assert template.updated_at is not None


class TestPromptManager:
    """Тесты для класса PromptManager."""
    
    def test_prompt_manager_initialization(self, temp_dir):
        """Тест инициализации менеджера промптов."""
        manager = PromptManager(temp_dir)
        
        assert manager.templates_dir == temp_dir
        assert manager.config == {}
        assert len(manager._prompt_cache) == 0
    
    def test_prompt_manager_with_config(self, temp_dir):
        """Тест инициализации с конфигурацией."""
        config = {"max_prompts": 100}
        manager = PromptManager(temp_dir, config)
        
        assert manager.config == config
    
    def test_ensure_templates_dir_creates_default_templates(self, temp_dir):
        """Тест создания директории с шаблонами по умолчанию."""
        manager = PromptManager(temp_dir)
        
        # Проверяем, что создались файлы с шаблонами
        template_files = list(Path(temp_dir).glob("*.json"))
        assert len(template_files) >= 5  # Минимум 5 базовых шаблонов
    
    def test_save_template(self, mock_prompt_manager, sample_prompt_template):
        """Тест сохранения шаблона."""
        template_data = {
            'name': sample_prompt_template.name,
            'version': sample_prompt_template.version,
            'description': sample_prompt_template.description,
            'object_type': sample_prompt_template.object_type,
            'content': sample_prompt_template.content,
            'variables': sample_prompt_template.variables,
            'context_requirements': sample_prompt_template.context_requirements,
            'min_tokens': sample_prompt_template.min_tokens,
            'max_tokens': sample_prompt_template.max_tokens,
            'quality_score': sample_prompt_template.quality_score
        }
        
        result = mock_prompt_manager.save_template("test_prompt", template_data)
        assert result is True
        
        # Проверяем, что шаблон попал в кэш
        assert "test_prompt" in mock_prompt_manager._prompt_cache
        
        # Проверяем файл
        template_file = mock_prompt_manager.templates_dir / "test_prompt.json"
        assert template_file.exists()
    
    def test_save_template_failure(self, mock_prompt_manager):
        """Тест ошибки сохранения шаблона."""
        template_data = {
            'name': 'test_prompt',
            'version': '1.0.0',
            'description': 'Test',
            'object_type': 'processing',
            'content': 'Test content',
            'variables': [],
            'context_requirements': {},
            'min_tokens': 0,
            'max_tokens': 1000,
            'quality_score': 0.0
        }
        
        with patch.object(mock_prompt_manager.templates_dir, 'mkdir', side_effect=PermissionError):
            result = mock_prompt_manager.save_template('test_prompt', template_data)
            assert result is False
    
    def test_load_template(self, mock_prompt_manager, sample_prompt_template):
        """Тест загрузки шаблона."""
        template_data = {
            'name': sample_prompt_template.name,
            'version': sample_prompt_template.version,
            'description': sample_prompt_template.description,
            'object_type': sample_prompt_template.object_type,
            'content': sample_prompt_template.content,
            'variables': sample_prompt_template.variables,
            'context_requirements': sample_prompt_template.context_requirements,
            'min_tokens': sample_prompt_template.min_tokens,
            'max_tokens': sample_prompt_template.max_tokens,
            'quality_score': sample_prompt_template.quality_score
        }
        
        # Сначала сохраняем
        mock_prompt_manager.save_template("test_prompt", template_data)
        
        # Затем загружаем
        loaded_template = mock_prompt_manager.load_template("test_prompt")
        
        assert loaded_template is not None
        assert loaded_template.name == "test_prompt"
        assert loaded_template.version == "1.0.0"
    
    def test_load_template_not_found(self, mock_prompt_manager):
        """Тест загрузки несуществующего шаблона."""
        result = mock_prompt_manager.load_template("nonexistent")
        assert result is None
    
    def test_get_template(self, mock_prompt_manager, sample_prompt_template):
        """Тест получения содержимого промпта."""
        template_data = {
            'name': sample_prompt_template.name,
            'version': sample_prompt_template.version,
            'description': sample_prompt_template.description,
            'object_type': sample_prompt_template.object_type,
            'content': sample_prompt_template.content,
            'variables': sample_prompt_template.variables,
            'context_requirements': sample_prompt_template.context_requirements,
            'min_tokens': sample_prompt_template.min_tokens,
            'max_tokens': sample_prompt_template.max_tokens,
            'quality_score': sample_prompt_template.quality_score
        }
        
        mock_prompt_manager.save_template("test_prompt", template_data)
        content = mock_prompt_manager.get_template("test_prompt")
        
        assert content == "Ты - эксперт по 1С. {description}"
    
    def test_get_template_nonexistent(self, mock_prompt_manager):
        """Тест получения содержимого несуществующего промпта."""
        content = mock_prompt_manager.get_template("nonexistent")
        assert content is None
    
    def test_get_templates_by_type(self, mock_prompt_manager):
        """Тест получения шаблонов по типу объекта."""
        # Сохраняем несколько шаблонов разных типов
        templates = [
            ("processing_template", "processing"),
            ("report_template", "report"),
            ("catalog_template", "catalog"),
            ("another_processing", "processing")
        ]
        
        for name, obj_type in templates:
            template_data = {
                'name': name,
                'version': '1.0.0',
                'description': 'Test',
                'object_type': obj_type,
                'content': f'Content for {name}',
                'variables': [],
                'context_requirements': {},
                'min_tokens': 0,
                'max_tokens': 1000,
                'quality_score': 0.0
            }
            mock_prompt_manager.save_template(name, template_data)
        
        # Получаем шаблоны обработок
        processing_templates = mock_prompt_manager.get_templates_by_type("processing")
        
        assert len(processing_templates) == 2
        assert all(t.object_type == "processing" for t in processing_templates)
        assert any(t.name == "processing_template" for t in processing_templates)
        assert any(t.name == "another_processing" for t in processing_templates)
    
    def test_list_templates(self, mock_prompt_manager):
        """Тест списка всех шаблонов."""
        # Сохраняем несколько шаблонов
        for i in range(3):
            template_data = {
                'name': f'template_{i}',
                'version': '1.0.0',
                'description': 'Test',
                'object_type': 'processing',
                'content': f'Content {i}',
                'variables': [],
                'context_requirements': {},
                'min_tokens': 0,
                'max_tokens': 1000,
                'quality_score': 0.0
            }
            mock_prompt_manager.save_template(f'template_{i}', template_data)
        
        templates = mock_prompt_manager.list_templates()
        
        assert len(templates) == 3
        assert "template_0" in templates
        assert "template_1" in templates
        assert "template_2" in templates
    
    def test_update_template_stats(self, mock_prompt_manager, sample_prompt_template):
        """Тест обновления статистики шаблона."""
        template_data = {
            'name': sample_prompt_template.name,
            'version': sample_prompt_template.version,
            'description': sample_prompt_template.description,
            'object_type': sample_prompt_template.object_type,
            'content': sample_prompt_template.content,
            'variables': sample_prompt_template.variables,
            'context_requirements': sample_prompt_template.context_requirements,
            'min_tokens': sample_prompt_template.min_tokens,
            'max_tokens': sample_prompt_template.max_tokens,
            'quality_score': 0.8
        }
        
        mock_prompt_manager.save_template("test_prompt", template_data)
        
        # Обновляем статистику
        mock_prompt_manager.update_template_stats("test_prompt", True, 0.9)
        
        # Проверяем обновления
        template = mock_prompt_manager.load_template("test_prompt")
        assert template.usage_count == 1
        assert template.success_rate == 1.0
        assert template.quality_score == 0.85  # (0.8 + 0.9) / 2
    
    def test_update_template_stats_multiple_calls(self, mock_prompt_manager, sample_prompt_template):
        """Тест множественных обновлений статистики."""
        template_data = {
            'name': sample_prompt_template.name,
            'version': sample_prompt_template.version,
            'description': sample_prompt_template.description,
            'object_type': sample_prompt_template.object_type,
            'content': sample_prompt_template.content,
            'variables': sample_prompt_template.variables,
            'context_requirements': sample_prompt_template.context_requirements,
            'min_tokens': sample_prompt_template.min_tokens,
            'max_tokens': sample_prompt_template.max_tokens,
            'quality_score': 0.8
        }
        
        mock_prompt_manager.save_template("test_prompt", template_data)
        
        # Обновляем статистику несколько раз
        mock_prompt_manager.update_template_stats("test_prompt", True, 0.9)
        mock_prompt_manager.update_template_stats("test_prompt", True, 0.95)
        mock_prompt_manager.update_template_stats("test_prompt", False, 0.7)
        
        template = mock_prompt_manager.load_template("test_prompt")
        assert template.usage_count == 3
        # 2 успешных из 3 попыток
        assert template.success_rate == 2/3
    
    def test_get_best_template(self, mock_prompt_manager):
        """Тест получения лучшего шаблона."""
        templates = [
            ("good_template", "processing", 0.9, 0.8),
            ("bad_template", "processing", 0.6, 0.7),
            ("excellent_template", "processing", 0.95, 0.9)
        ]
        
        for name, obj_type, quality, success in templates:
            template_data = {
                'name': name,
                'version': '1.0.0',
                'description': 'Test',
                'object_type': obj_type,
                'content': f'Content for {name}',
                'variables': [],
                'context_requirements': {},
                'min_tokens': 0,
                'max_tokens': 1000,
                'quality_score': quality
            }
            mock_prompt_manager.save_template(name, template_data)
            mock_prompt_manager.update_template_stats(name, success > 0.7, quality)
        
        best_template = mock_prompt_manager.get_best_template("processing")
        
        # excellent_template должен быть лучшим (0.95 * 0.9 = 0.855)
        assert best_template is not None
        assert best_template.name == "excellent_template"
    
    def test_create_derivative_template(self, mock_prompt_manager, sample_prompt_template):
        """Тест создания производного шаблона."""
        # Сначала сохраняем базовый шаблон
        template_data = {
            'name': sample_prompt_template.name,
            'version': sample_prompt_template.version,
            'description': sample_prompt_template.description,
            'object_type': sample_prompt_template.object_type,
            'content': sample_prompt_template.content,
            'variables': sample_prompt_template.variables,
            'context_requirements': sample_prompt_template.context_requirements,
            'min_tokens': sample_prompt_template.min_tokens,
            'max_tokens': sample_prompt_template.max_tokens,
            'quality_score': sample_prompt_template.quality_score,
            'usage_count': 5
        }
        mock_prompt_manager.save_template("base_template", template_data)
        
        # Создаем производный шаблон
        modifications = {
            'description': 'Производный шаблон',
            'content': 'Измененный контент',
            'quality_score': 0.9
        }
        
        result = mock_prompt_manager.create_derivative_template(
            "base_template", "derivative_template", modifications
        )
        
        assert result is True
        
        # Проверяем производный шаблон
        derivative = mock_prompt_manager.load_template("derivative_template")
        assert derivative is not None
        assert derivative.description == 'Производный шаблон'
        assert derivative.content == 'Измененный контент'
        assert derivative.version == "1.0.6"  # 5 + 1
        assert derivative.quality_score == 0.9
    
    def test_create_derivative_template_nonexistent_base(self, mock_prompt_manager):
        """Тест создания производного шаблона от несуществующего базового."""
        modifications = {'description': 'Test'}
        
        result = mock_prompt_manager.create_derivative_template(
            "nonexistent", "test_template", modifications
        )
        
        assert result is False
    
    def test_empty_cache_behavior(self, mock_prompt_manager):
        """Тест поведения с пустым кэшем."""
        # Проверяем методы с пустым кэшем
        assert mock_prompt_manager.get_templates_by_type("processing") == []
        assert mock_prompt_manager.list_templates() == []
        assert mock_prompt_manager.get_best_template("processing") is None