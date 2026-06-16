
"""
Тесты для оптимизатора промптов.
"""


import pytest

from src.py_server.code_generation.prompts.optimizer import (PromptMetrics,
                                                             PromptOptimizer)


class TestPromptMetrics:
    """Тесты для класса PromptMetrics."""
    
    def test_prompt_metrics_creation(self):
        """Тест создания метрик промпта."""
        metrics = PromptMetrics(
            prompt_name="test_prompt",
            usage_count=10,
            success_rate=0.8,
            avg_generation_time=2.5,
            avg_code_quality=0.85,
            common_errors=["syntax_error", "validation_error"],
            improvement_suggestions=["Добавить больше примеров", "Улучшить инструкции"],
            optimization_score=0.75
        )
        
        assert metrics.prompt_name == "test_prompt"
        assert metrics.usage_count == 10
        assert metrics.success_rate == 0.8
        assert metrics.avg_generation_time == 2.5
        assert metrics.avg_code_quality == 0.85
        assert len(metrics.common_errors) == 2
        assert len(metrics.improvement_suggestions) == 2
        assert metrics.optimization_score == 0.75
    
    def test_prompt_metrics_defaults(self):
        """Тест значений по умолчанию для метрик."""
        metrics = PromptMetrics(
            prompt_name="test",
            usage_count=0,
            success_rate=0.0,
            avg_generation_time=0.0,
            avg_code_quality=0.0,
            common_errors=[],
            improvement_suggestions=[]
        )
        
        assert metrics.optimization_score == 0.0


class TestPromptOptimizer:
    """Тесты для класса PromptOptimizer."""
    
    def test_prompt_optimizer_initialization(self, mock_prompt_manager):
        """Тест инициализации оптимизатора промптов."""
        optimizer = PromptOptimizer(mock_prompt_manager)
        
        assert optimizer.prompt_manager == mock_prompt_manager
        assert optimizer.metrics_storage is None
        assert len(optimizer.quality_patterns) > 0
        assert len(optimizer.problem_patterns) > 0
    
    def test_prompt_optimizer_with_metrics_storage(self, mock_prompt_manager, temp_dir):
        """Тест инициализации с хранилищем метрик."""
        metrics_file = temp_dir / "metrics.json"
        optimizer = PromptOptimizer(mock_prompt_manager, str(metrics_file))
        
        assert optimizer.metrics_storage == str(metrics_file)
    
    @pytest.fixture
    def mock_prompt_manager_with_template(self, mock_prompt_manager):
        """Фикстура менеджера промптов с тестовым шаблоном."""
        template_data = {
            'name': 'test_prompt',
            'version': '1.0.0',
            'description': 'Test prompt',
            'object_type': 'processing',
            'content': 'Ты - эксперт по 1С. Создай {description}. Обязательно используй комментарии.',
            'variables': ['description'],
            'context_requirements': {'include_forms': 'да'},
            'min_tokens': 100,
            'max_tokens': 1000,
            'quality_score': 0.8
        }
        mock_prompt_manager.save_template('test_prompt', template_data)
        return mock_prompt_manager
    
    def test_analyze_prompt_success(self, mock_prompt_manager_with_template):
        """Тест успешного анализа промпта."""
        optimizer = PromptOptimizer(mock_prompt_manager_with_template)
        
        generation_history = [
            {'generation_time': 2.0, 'quality_score': 0.8, 'error_type': 'validation_error'},
            {'generation_time': 3.0, 'quality_score': 0.9, 'error_type': None},
            {'generation_time': 2.5, 'quality_score': 0.85, 'error_type': None}
        ]
        
        metrics = optimizer.analyze_prompt('test_prompt', generation_history)
        
        assert isinstance(metrics, PromptMetrics)
        assert metrics.prompt_name == 'test_prompt'
        assert metrics.usage_count == 0
        assert metrics.avg_generation_time == 2.5
        assert metrics.avg_code_quality == 0.85
        assert metrics.optimization_score > 0
    
    def test_analyze_prompt_not_found(self, mock_prompt_manager):
        """Тест анализа несуществующего промпта."""
        optimizer = PromptOptimizer(mock_prompt_manager)
        
        with pytest.raises(ValueError, match="Промпт 'nonexistent' не найден"):
            optimizer.analyze_prompt('nonexistent')
    
    def test_analyze_content_quality(self, mock_prompt_manager):
        """Тест анализа качества содержимого промпта."""
        optimizer = PromptOptimizer(mock_prompt_manager)
        
        # Хороший промпт с четкими инструкциями
        good_content = """
Ты - эксперт по разработке в 1С. Твоя задача - создать качественный код.

Требования к генерации кода:
1. Структура объекта
2. Стиль кода
3. Валидация данных
4. Обработка ошибок

Верни код в формате:
```bsl
// Модуль объекта
&НаСервере
Процедура Выполнить() Экспорт
    // Основная логика
КонецПроцедуры
```"""
        
        analysis = optimizer._analyze_content_quality(good_content)
        
        assert 'detailed_instructions' in analysis
        assert 'code_structure' in analysis
        assert 'context_awareness' in analysis
        assert 'validation_rules' in analysis
        assert 'specificity' in analysis
        
        # Хорошие промпты должны иметь высокие скоры
        assert analysis['detailed_instructions'] > 0.5
        assert analysis['code_structure'] > 0.5
    
    def test_analyze_content_quality_poor_prompt(self, mock_prompt_manager):
        """Тест анализа плохого промпта."""
        optimizer = PromptOptimizer(mock_prompt_manager)
        
        # Плохой промпт с неясными инструкциями
        poor_content = "Создай простую обработку как угодно"
        
        analysis = optimizer._analyze_content_quality(poor_content)
        
        # Плохие промпты должны иметь низкие скоры
        assert analysis['detailed_instructions'] < 0.5
        assert analysis['code_structure'] < 0.5
    
    def test_analyze_generation_history(self, mock_prompt_manager):
        """Тест анализа истории генераций."""
        optimizer = PromptOptimizer(mock_prompt_manager)
        
        history = [
            {'generation_time': 1.5, 'quality_score': 0.8},
            {'generation_time': 2.0, 'quality_score': 0.9},
            {'generation_time': 1.8, 'quality_score': 0.85},
            {'error_type': 'validation_error'},
            {'error_type': 'syntax_error'},
            {'error_type': 'validation_error'}
        ]
        
        analysis = optimizer._analyze_generation_history(history)
        
        assert analysis['avg_time'] == pytest.approx(1.766666, 0.001)
        assert analysis['avg_quality'] == pytest.approx(0.85, 0.001)
        assert 'validation_error' in analysis['common_errors']
        assert analysis['common_errors'][0][0] == 'validation_error'
    
    def test_analyze_generation_history_empty(self, mock_prompt_manager):
        """Тест анализа пустой истории генераций."""
        optimizer = PromptOptimizer(mock_prompt_manager)
        
        analysis = optimizer._analyze_generation_history([])
        
        assert analysis['avg_time'] == 0.0
        assert analysis['avg_quality'] == 0.0
        assert analysis['common_errors'] == []
    
    def test_generate_improvement_suggestions(self, mock_prompt_manager):
        """Тест генерации предложений по улучшению."""
        optimizer = PromptOptimizer(mock_prompt_manager)
        
        content_analysis = {
            'detailed_instructions': 0.3,  # Низкий скор
            'code_structure': 0.8,
            'validation_rules': 0.4,  # Низкий скор
            'context_awareness': 0.6,
            'specificity': 0.7
        }
        
        history_analysis = {
            'avg_quality': 0.6,  # Низкое качество
            'common_errors': [('syntax_error', 3), ('validation_error', 2)]
        }
        
        suggestions = optimizer._generate_improvement_suggestions(content_analysis, history_analysis)
        
        assert len(suggestions) > 0
        assert any('детальные инструкции' in s for s in suggestions)
        assert any('правила валидации' in s for s in suggestions)
        assert any('низкого качества' in s for s in suggestions)
    
    def test_calculate_optimization_score(self, mock_prompt_manager):
        """Тест вычисления скора оптимизации."""
        optimizer = PromptOptimizer(mock_prompt_manager)
        
        content_analysis = {
            'detailed_instructions': 0.8,
            'code_structure': 0.9,
            'validation_rules': 0.7,
            'context_awareness': 0.6,
            'specificity': 0.8
        }
        
        history_analysis = {
            'avg_quality': 0.85,
            'avg_time': 2.0
        }
        
        score = optimizer._calculate_optimization_score(content_analysis, history_analysis)
        
        assert 0 <= score <= 1
        assert score > 0.7  # Должен быть высоким для хорошего промпта
    
    def test_optimize_prompt_success(self, mock_prompt_manager_with_template):
        """Тест успешной оптимизации промпта."""
        optimizer = PromptOptimizer(mock_prompt_manager_with_template)
        
        generation_history = [
            {'generation_time': 3.0, 'quality_score': 0.6, 'error_type': 'validation_error'}
        ]
        
        result = optimizer.optimize_prompt('test_prompt', target_improvement=0.1)
        
        assert result is not None
        assert result.original_prompt != result.optimized_prompt
        assert len(result.changes_made) > 0
        assert result.expected_improvement > 0
        assert 0 <= result.confidence_level <= 1
    
    def test_optimize_prompt_insufficient_improvement(self, mock_prompt_manager_with_template):
        """Тест оптимизации с недостаточным улучшением."""
        optimizer = PromptOptimizer(mock_prompt_manager_with_template)
        
        # Хороший промпт, который уже оптимален
        generation_history = [
            {'generation_time': 2.0, 'quality_score': 0.95}
        ]
        
        result = optimizer.optimize_prompt('test_prompt', target_improvement=0.2)
        
        assert result is None  # Недостаточно улучшения
    
    def test_optimize_prompt_not_found(self, mock_prompt_manager):
        """Тест оптимизации несуществующего промпта."""
        optimizer = PromptOptimizer(mock_prompt_manager)
        
        result = optimizer.optimize_prompt('nonexistent')
        
        assert result is None
    
    def test_create_adaptive_prompt(self, mock_prompt_manager_with_template):
        """Тест создания адаптивного промпта."""
        optimizer = PromptOptimizer(mock_prompt_manager_with_template)
        
        context = {
            'object_type': 'processing',
            'complexity_level': 'advanced',
            'quality_requirements': ['security', 'performance']
        }
        
        adaptive_prompt = optimizer.create_adaptive_prompt('test_prompt', context)
        
        assert adaptive_prompt != ''
        assert len(adaptive_prompt) > len(optimizer.prompt_manager.get_template('test_prompt'))
    
    def test_create_adaptive_prompt_nonexistent_base(self, mock_prompt_manager):
        """Тест создания адаптивного промпта с несуществующим базовым."""
        optimizer = PromptOptimizer(mock_prompt_manager)
        
        context = {'object_type': 'processing'}
        
        result = optimizer.create_adaptive_prompt('nonexistent', context)
        
        assert result == ""
    
    def test_batch_optimize_prompts(self, mock_prompt_manager):
        """Тест пакетной оптимизации промптов."""
        # Создаем несколько промптов для оптимизации
        templates = [
            'template_1', 'template_2', 'template_3'
        ]
        
        for i, template_name in enumerate(templates):
            template_data = {
                'name': template_name,
                'version': '1.0.0',
                'description': f'Template {i}',
                'object_type': 'processing',
                'content': f'Content {i} with TODO placeholders',
                'variables': [],
                'context_requirements': {},
                'min_tokens': 0,
                'max_tokens': 1000,
                'quality_score': 0.5 + i * 0.1
            }
            mock_prompt_manager.save_template(template_name, template_data)
        
        optimizer = PromptOptimizer(mock_prompt_manager)
        
        results = optimizer.batch_optimize_prompts(templates, min_improvement=0.1)
        
        assert isinstance(results, dict)
        # Некоторые промпты должны быть оптимизированы
        assert len(results) >= 0
    
    def test_save_optimization_metrics_success(self, mock_prompt_manager, temp_dir):
        """Тест успешного сохранения метрик оптимизации."""
        metrics_file = temp_dir / "metrics.json"
        optimizer = PromptOptimizer(mock_prompt_manager, str(metrics_file))
        
        metrics = PromptMetrics(
            prompt_name="test_prompt",
            usage_count=10,
            success_rate=0.8,
            avg_generation_time=2.5,
            avg_code_quality=0.85,
            common_errors=[],
            improvement_suggestions=[],
            optimization_score=0.75
        )
        
        result = optimizer.save_optimization_metrics(metrics)
        
        assert result is True
        assert metrics_file.exists()
        
        # Проверяем содержимое файла
        with open(metrics_file, 'r', encoding='utf-8') as f:
            content = f.read()
            assert 'test_prompt' in content
    
    def test_save_optimization_metrics_no_storage(self, mock_prompt_manager):
        """Тест сохранения метрик без хранилища."""
        optimizer = PromptOptimizer(mock_prompt_manager)
        
        metrics = PromptMetrics(
            prompt_name="test",
            usage_count=0,
            success_rate=0.0,
            avg_generation_time=0.0,
            avg_code_quality=0.0,
            common_errors=[],
            improvement_suggestions=[]
        )
        
        result = optimizer.save_optimization_metrics(metrics)
        
        assert result is False