
"""
Оптимизатор промптов для улучшения качества генерации кода.

Анализирует результаты генерации, адаптирует промпты и создает
оптимизированные версии для повышения качества.
"""

import json
import logging
import re
import statistics
from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional


@dataclass
class PromptMetrics:
    """Метрики эффективности промпта."""
    prompt_name: str
    usage_count: int
    success_rate: float
    avg_generation_time: float
    avg_code_quality: float
    common_errors: List[str]
    improvement_suggestions: List[str]
    optimization_score: float = 0.0


@dataclass
class OptimizationResult:
    """Результат оптимизации промпта."""
    original_prompt: str
    optimized_prompt: str
    changes_made: List[str]
    expected_improvement: float
    confidence_level: float


class PromptOptimizer:
    """Оптимизатор промптов для генерации кода 1С."""
    
    def __init__(self, prompt_manager, metrics_storage: str = None):
        """
        Инициализация оптимизатора.
        
        Args:
            prompt_manager: Экземпляр PromptManager
            metrics_storage: Путь для хранения метрик
        """
        self.prompt_manager = prompt_manager
        self.metrics_storage = metrics_storage
        self.logger = logging.getLogger(__name__)
        
        # Паттерны для анализа качества промптов
        self.quality_patterns = {
            'detailed_instructions': r'(Требования|Инструкции|Требования к|Rules|Requirements)',
            'code_structure': r'(СТРУКТУРА|Structure|Верни код|format|формат)',
            'context_awareness': r'(контекст|context|Ты - |You are)',
            'validation_rules': r'(провер|check|валид|valid)',
            'error_handling': r'(ошибк|exception|error|попытка)',
            'best_practices': r'(стандарт|standard|правильно|best practices)'
        }
        
        # Паттерны проблем в промптах
        self.problem_patterns = {
            'vague_instructions': r'(.*?)(просто|простое|небольшой|легкий|простой)',
            'missing_context': r'(.*?)(не учитывая|ignoring|без учета)',
            'unclear_format': r'(.*?)(как угодно|любым способом|в любом формате)',
            'contradictory_requirements': r'(но также|однако|однако|при этом)',
            'missing_constraints': r'(.*?)(ограничения|лимиты|ограничения)',
            'insufficient_examples': r'(.*?)(пример|example|образец)'
        }
    
    def analyze_prompt(self, prompt_name: str, generation_history: List[Dict[str, Any]] = None) -> PromptMetrics:
        """
        Анализирует эффективность промпта.
        
        Args:
            prompt_name: Имя промпта для анализа
            generation_history: История генераций для анализа
            
        Returns:
            PromptMetrics: Метрики эффективности промпта
        """
        template = self.prompt_manager.load_template(prompt_name)
        if not template:
            raise ValueError(f"Промпт '{prompt_name}' не найден")
        
        # Анализ содержимого промпта
        content_analysis = self._analyze_content_quality(template.content)
        
        # Анализ истории генераций
        history_analysis = self._analyze_generation_history(generation_history or [])
        
        # Создание метрик
        metrics = PromptMetrics(
            prompt_name=prompt_name,
            usage_count=template.usage_count,
            success_rate=template.success_rate,
            avg_generation_time=history_analysis.get('avg_time', 0.0),
            avg_code_quality=history_analysis.get('avg_quality', template.quality_score),
            common_errors=history_analysis.get('common_errors', []),
            improvement_suggestions=self._generate_improvement_suggestions(content_analysis, history_analysis),
            optimization_score=self._calculate_optimization_score(content_analysis, history_analysis)
        )
        
        return metrics
    
    def _analyze_content_quality(self, content: str) -> Dict[str, float]:
        """Анализирует качество содержимого промпта."""
        analysis = {}
        
        for category, pattern in self.quality_patterns.items():
            matches = len(re.findall(pattern, content, re.IGNORECASE))
            # Нормализуем по длине контента
            analysis[category] = min(matches / (len(content) / 1000), 1.0)
        
        # Анализ структуры
        analysis['has_structure'] = 1.0 if any(structure_word in content.lower() 
                                             for structure_word in ['структура', 'format', 'верни код']) else 0.0
        
        # Анализ конкретности
        specific_words = ['тип', 'строка', 'число', 'булево', 'запрос', 'регистр', 'справочник']
        analysis['specificity'] = sum(1 for word in specific_words if word in content.lower()) / len(specific_words)
        
        return analysis
    
    def _analyze_generation_history(self, history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Анализирует историю генераций."""
        if not history:
            return {'avg_time': 0.0, 'avg_quality': 0.0, 'common_errors': []}
        
        # Основные метрики
        times = [h.get('generation_time', 0) for h in history if 'generation_time' in h]
        qualities = [h.get('quality_score', 0) for h in history if 'quality_score' in h]
        errors = [h.get('error_type', '') for h in history if 'error_type' in h]
        
        return {
            'avg_time': statistics.mean(times) if times else 0.0,
            'avg_quality': statistics.mean(qualities) if qualities else 0.0,
            'common_errors': list(Counter(errors).most_common(5))
        }
    
    def _generate_improvement_suggestions(self, content_analysis: Dict[str, float], 
                                        history_analysis: Dict[str, Any]) -> List[str]:
        """Генерирует предложения по улучшению промпта."""
        suggestions = []
        
        # Анализ содержимого
        if content_analysis.get('detailed_instructions', 0) < 0.5:
            suggestions.append("Добавьте более детальные инструкции и требования")
        
        if content_analysis.get('code_structure', 0) < 0.7:
            suggestions.append("Уточните структуру ожидаемого кода")
        
        if content_analysis.get('validation_rules', 0) < 0.6:
            suggestions.append("Добавьте больше правил валидации")
        
        if content_analysis.get('context_awareness', 0) < 0.5:
            suggestions.append("Усильте контекстную осведомленность")
        
        # Анализ истории
        if history_analysis.get('avg_quality', 0) < 0.7:
            suggestions.append("Промпт генерирует код низкого качества")
        
        common_errors = history_analysis.get('common_errors', [])
        if common_errors:
            suggestions.append(f"Частые ошибки: {', '.join([error[0] for error in common_errors[:3]])}")
        
        return suggestions
    
    def _calculate_optimization_score(self, content_analysis: Dict[str, float], 
                                    history_analysis: Dict[str, Any]) -> float:
        """Вычисляет общий скор оптимизации."""
        # Веса для разных аспектов
        weights = {
            'detailed_instructions': 0.2,
            'code_structure': 0.25,
            'validation_rules': 0.2,
            'context_awareness': 0.15,
            'specificity': 0.2
        }
        
        # Вычисляем взвешенный скор
        weighted_score = sum(content_analysis.get(key, 0) * weight 
                           for key, weight in weights.items())
        
        # Корректируем на основе истории
        quality_factor = history_analysis.get('avg_quality', 0.5)
        time_factor = 1.0 - min(history_analysis.get('avg_time', 5.0) / 10.0, 1.0)
        
        final_score = weighted_score * 0.7 + quality_factor * 0.2 + time_factor * 0.1
        return min(final_score, 1.0)
    
    def optimize_prompt(self, prompt_name: str, target_improvement: float = 0.15) -> Optional[OptimizationResult]:
        """
        Оптимизирует промпт для улучшения качества генерации.
        
        Args:
            prompt_name: Имя промпта для оптимизации
            target_improvement: Целевое улучшение (0-1)
            
        Returns:
            OptimizationResult: Результат оптимизации
        """
        template = self.prompt_manager.load_template(prompt_name)
        if not template:
            return None
        
        # Анализируем текущий промпт
        metrics = self.analyze_prompt(prompt_name)
        current_score = metrics.optimization_score
        
        # Генерируем улучшения
        optimized_content = self._apply_optimizations(template.content, metrics)
        
        # Оцениваем ожидаемое улучшение
        expected_improvement = self._estimate_improvement(template.content, optimized_content)
        
        if expected_improvement < target_improvement:
            self.logger.info(f"Недостаточное улучшение для промпта '{prompt_name}': {expected_improvement:.3f}")
            return None
        
        # Определяем изменения
        changes_made = self._identify_changes(template.content, optimized_content)
        
        result = OptimizationResult(
            original_prompt=template.content,
            optimized_prompt=optimized_content,
            changes_made=changes_made,
            expected_improvement=expected_improvement,
            confidence_level=min(expected_improvement * 2, 0.95)
        )
        
        return result
    
    def _apply_optimizations(self, content: str, metrics: PromptMetrics) -> str:
        """Применяет оптимизации к содержимому промпта."""
        optimized = content
        
        # Добавляем более четкие инструкции
        if 'detailed_instructions' in metrics.improvement_suggestions:
            optimized = self._add_detailed_instructions(optimized)
        
        # Улучшаем структуру
        if 'code_structure' in metrics.improvement_suggestions:
            optimized = self._improve_code_structure(optimized)
        
        # Добавляем примеры
        optimized = self._add_examples(optimized)
        
        # Усиливаем требования валидации
        optimized = self._add_validation_requirements(optimized)
        
        # Добавляем ограничения и проверки
        optimized = self._add_constraints_and_checks(optimized)
        
        return optimized
    
    def _add_detailed_instructions(self, content: str) -> str:
        """Добавляет более детальные инструкции."""
        detailed_instructions = """
ДОПОЛНИТЕЛЬНЫЕ ТРЕБОВАНИЯ:
1. Все переменные должны быть типизированы с использованием функций Строка(), Число(), Булево()
2. Обязательно используй Попытка...Исключение для обработки ошибок
3. Проверяй входные параметры на корректность и пустые значения
4. Используй точные типы данных 1С вместо общих
5. Добавляй комментарии к сложным алгоритмам
6. Следуй стандартам именования 1С (верблюжий регистр для процедур, UpperCase для констант)

"""
        
        # Вставляем после вводной части
        return content + detailed_instructions
    
    def _improve_code_structure(self, content: str) -> str:
        """Улучшает структуру инструкций по коду."""
        structure_improvements = """
СТРУКТУРА ОТВЕТА ОБЯЗАТЕЛЬНО:
```bsl
// ======================================
// МОДУЛЬ ОБЪЕКТА/МЕНЕДЖЕРА
// ======================================
&НаСервере
Процедура/Функция ИмяПроцедуры(Параметры) Экспорт
    // 1. Валидация параметров
    // 2. Бизнес-логика
    // 3. Возврат результата
КонецПроцедуры/КонецФункции

// ======================================
// МОДУЛЬ ФОРМЫ
// ======================================
&НаКлиенте
Процедура ИмяЭлементаНажатие(Элемент)
    // Обработчик события
КонецПроцедуры
```
"""
        
        return content + structure_improvements
    
    def _add_examples(self, content: str) -> str:
        """Добавляет примеры кода."""
        examples = """
ПРИМЕРЫ ПРАВИЛЬНОГО КОДА:

Пример валидации:
```bsl
Если ПустаяСтрока(Номенклатура) Тогда
    Сообщить("Номенклатура не выбрана!");
    Возврат;
КонецЕсли;
```

Пример работы с запросом:
```bsl
Запрос = Новый Запрос;
Запрос.Текст = "ВЫБРАТЬ * ИЗ Справочник.Номенклатура ГДЕ Ссылка = &Ссылка";
Запрос.УстановитьПараметр("Ссылка", Номенклатура);
Результат = Запрос.Выполнить();
Выборка = Результат.Выбрать();
```

Пример обработки ошибок:
```bsl
Попытка
    // Основная логика
    Результат = ВыполнитьОперацию();
Исключение
    Сообщить("Ошибка: " + ОписаниеОшибки());
    Возврат;
КонецПопытки;
```
"""
        
        return content + examples
    
    def _add_validation_requirements(self, content: str) -> str:
        """Добавляет дополнительные требования валидации."""
        validation_requirements = """
ОБЯЗАТЕЛЬНАЯ ВАЛИДАЦИЯ:
- Все входные параметры проверяй на ПустаяСтрока() и ЗначениеЗаполнено()
- Строковые параметры проверяй на ДлинаСтроки() и корректность
- Ссылки проверяй на НЕ ПустаяСсылка() перед использованием
- Даты проверяй на корректность и диапазон
- Числовые значения проверяй на больше 0 если требуется
- Массивы и списки проверяй на Количество() > 0
"""
        
        return content + validation_requirements
    
    def _add_constraints_and_checks(self, content: str) -> str:
        """Добавляет ограничения и проверки."""
        constraints = """
ОГРАНИЧЕНИЯ И ЗАПРЕТЫ:
ЗАПРЕЩЕНО использовать:
- Выполнить() и Вычислить() (угроза безопасности)
- СоздатьОбъект("WSExec") (выполнение системных команд)
- РаботаСФайлами.ЗагрузитьФайл() без проверки расширения
- Запросы без параметров через &Параметр

ОБЯЗАТЕЛЬНО ПРОВЕРЯТЬ:
- Права доступа пользователя
- Состояние документов (проведен/непроведен)
- Остатки при списании
- Конфликты блокировок данных
"""
        
        return content + constraints
    
    def _estimate_improvement(self, original: str, optimized: str) -> float:
        """Оценивает ожидаемое улучшение качества."""
        # Анализируем различия в структуре
        original_analysis = self._analyze_content_quality(original)
        optimized_analysis = self._analyze_content_quality(optimized)
        
        # Вычисляем улучшение по каждой метрике
        improvements = []
        for metric in original_analysis:
            orig_score = original_analysis[metric]
            opt_score = optimized_analysis[metric]
            improvement = max(0, opt_score - orig_score)
            improvements.append(improvement)
        
        # Возвращаем среднее улучшение
        return statistics.mean(improvements) if improvements else 0.0
    
    def _identify_changes(self, original: str, optimized: str) -> List[str]:
        """Определяет сделанные изменения."""
        changes = []
        
        # Проверяем основные улучшения
        if len(optimized) > len(original) * 1.2:
            changes.append("Добавлены детальные инструкции")
        
        if "ПРИМЕРЫ" in optimized and "ПРИМЕРЫ" not in original:
            changes.append("Добавлены примеры кода")
        
        if "ОБЯЗАТЕЛЬНАЯ ВАЛИДАЦИЯ" in optimized:
            changes.append("Добавлены требования валидации")
        
        if "ОГРАНИЧЕНИЯ И ЗАПРЕТЫ" in optimized:
            changes.append("Добавлены ограничения безопасности")
        
        if "СТРУКТУРА ОТВЕТА" in optimized:
            changes.append("Улучшена структура ответа")
        
        return changes
    
    def create_adaptive_prompt(self, base_prompt_name: str, context: Dict[str, Any]) -> str:
        """Создает адаптивный промпт на основе контекста."""
        base_template = self.prompt_manager.load_template(base_prompt_name)
        if not base_template:
            return ""
        
        base_content = base_template.content
        
        # Адаптация под контекст
        adapted_content = base_content
        
        # Адаптация под тип объекта
        if 'object_type' in context:
            adapted_content = self._adapt_for_object_type(adapted_content, context['object_type'])
        
        # Адаптация под уровень сложности
        if 'complexity_level' in context:
            adapted_content = self._adapt_for_complexity(adapted_content, context['complexity_level'])
        
        # Адаптация под требования качества
        if 'quality_requirements' in context:
            adapted_content = self._adapt_for_quality(adapted_content, context['quality_requirements'])
        
        return adapted_content
    
    def _adapt_for_object_type(self, content: str, object_type: str) -> str:
        """Адаптирует промпт под тип объекта."""
        adaptations = {
            'processing': "Особое внимание удели обработке данных и пользовательскому интерфейсу",
            'report': "Сосредоточься на построении отчетов с использованием СКД",
            'catalog': "Удели внимание структуре данных и валидации",
            'document': "Особое внимание движениям регистров и проведению документов"
        }
        
        if object_type.lower() in adaptations:
            adaptation_note = f"\nКОНТЕКСТ ОБЪЕКТА: {adaptations[object_type.lower()]}"
            content += adaptation_note
        
        return content
    
    def _adapt_for_complexity(self, content: str, complexity_level: str) -> str:
        """Адаптирует промпт под уровень сложности."""
        complexity_notes = {
            'simple': "Создай простую реализацию без излишних проверок",
            'standard': "Создай стандартную реализацию с основными проверками",
            'advanced': "Создай продвинутую реализацию с полной валидацией и обработкой ошибок",
            'enterprise': "Создай enterprise-решение с полным аудитом, логированием и мониторингом"
        }
        
        if complexity_level.lower() in complexity_notes:
            complexity_note = f"\nУРОВЕНЬ СЛОЖНОСТИ: {complexity_notes[complexity_level.lower()]}"
            content += complexity_note
        
        return content
    
    def _adapt_for_quality(self, content: str, quality_requirements: List[str]) -> str:
        """Адаптирует промпт под требования качества."""
        quality_notes = []
        
        if 'high_coverage' in quality_requirements:
            quality_notes.append("Добавь максимальное покрытие тестами")
        
        if 'performance' in quality_requirements:
            quality_notes.append("Оптимизируй код для высокой производительности")
        
        if 'security' in quality_requirements:
            quality_notes.append("Усиль меры безопасности и валидацию")
        
        if 'maintainability' in quality_requirements:
            quality_notes.append("Улучши читаемость и поддерживаемость кода")
        
        if quality_notes:
            quality_section = f"\nТРЕБОВАНИЯ К КАЧЕСТВУ:\n" + "\n".join(f"- {note}" for note in quality_notes)
            content += quality_section
        
        return content
    
    def batch_optimize_prompts(self, prompt_names: List[str], min_improvement: float = 0.1) -> Dict[str, OptimizationResult]:
        """
        Пакетная оптимизация нескольких промптов.
        
        Args:
            prompt_names: Список имен промптов для оптимизации
            min_improvement: Минимальное улучшение для применения
            
        Returns:
            Dict[str, OptimizationResult]: Результаты оптимизации
        """
        results = {}
        
        for prompt_name in prompt_names:
            try:
                result = self.optimize_prompt(prompt_name, min_improvement)
                if result and result.expected_improvement >= min_improvement:
                    results[prompt_name] = result
                    self.logger.info(f"Промпт '{prompt_name}' оптимизирован (улучшение: {result.expected_improvement:.3f})")
                else:
                    self.logger.info(f"Промпт '{prompt_name}' не требует оптимизации")
            except Exception as e:
                self.logger.error(f"Ошибка при оптимизации промпта '{prompt_name}': {e}")
        
        return results
    
    def save_optimization_metrics(self, metrics: PromptMetrics) -> bool:
        """Сохраняет метрики оптимизации."""
        if not self.metrics_storage:
            return False
        
        try:
            with open(self.metrics_storage, 'a', encoding='utf-8') as f:
                f.write(json.dumps(asdict(metrics), ensure_ascii=False, indent=2, default=str) + '\n')
            return True
        except Exception as e:
            self.logger.error(f"Ошибка при сохранении метрик: {e}")
            return False