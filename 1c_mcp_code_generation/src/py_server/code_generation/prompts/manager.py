
"""
Менеджер промптов для системы генерации кода 1С.

Управляет библиотекой промптов, их версиями, контекстами и адаптацией
под различные сценарии использования.
"""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


@dataclass
class PromptTemplate:
    """Класс для представления шаблона промпта."""
    name: str
    version: str
    description: str
    object_type: str  # processing, report, catalog, document
    content: str
    variables: List[str]
    context_requirements: Dict[str, str]
    min_tokens: int
    max_tokens: int
    quality_score: float
    usage_count: int = 0
    success_rate: float = 0.0
    created_at: datetime = None
    updated_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()


class PromptManager:
    """Менеджер промптов для генерации кода 1С."""
    
    def __init__(self, 
                 templates_dir: Union[str, Path] = None,
                 config: Optional[Dict[str, Any]] = None):
        """
        Инициализация менеджера промптов.
        
        Args:
            templates_dir: Директория с шаблонами промптов
            config: Конфигурация менеджера
        """
        self.templates_dir = Path(templates_dir) if templates_dir else Path(__file__).parent / 'templates'
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        
        # Кэш загруженных промптов
        self._prompt_cache: Dict[str, PromptTemplate] = {}
        
        # Версии промптов для A/B тестирования
        self.version_tracker: Dict[str, Dict[str, float]] = {}
        
        self._ensure_templates_dir()
        
    def _ensure_templates_dir(self):
        """Создает директорию с шаблонами если не существует."""
        if not self.templates_dir.exists():
            self.templates_dir.mkdir(parents=True, exist_ok=True)
            self._create_default_templates()
    
    def _create_default_templates(self):
        """Создает базовые промпты по умолчанию."""
        default_templates = {
            'processing_basic': self._get_processing_template(),
            'report_basic': self._get_report_template(),
            'catalog_basic': self._get_catalog_template(),
            'document_basic': self._get_document_template(),
            'validation_prompt': self._get_validation_template(),
            'security_analysis': self._get_security_template()
        }
        
        for name, template_data in default_templates.items():
            self.save_template(name, template_data)
    
    def _get_processing_template(self) -> Dict[str, Any]:
        """Возвращает базовый промпт для обработки."""
        return {
            'name': 'processing_basic',
            'version': '1.0.0',
            'description': 'Базовый промпт для генерации обработок 1С',
            'object_type': 'processing',
            'content': self._get_processing_content(),
            'variables': ['description', 'input_parameters', 'output_parameters', 'business_logic'],
            'context_requirements': {
                'include_forms': 'да',
                'include_print_forms': 'нет',
                'code_style': 'standard'
            },
            'min_tokens': 200,
            'max_tokens': 2000,
            'quality_score': 0.85
        }
    
    def _get_processing_content(self) -> str:
        """Возвращает контент промпта для обработки."""
        return """Ты - эксперт по разработке в системе 1С:Предприятие. Твоя задача - создать качественный код обработки на языке BSL (Built-in Script Language).

Требования к генерации кода:

1. СТРУКТУРА ОБРАБОТКИ:
   - Создай модуль объекта с основными процедурами и функциями
   - Добавь модуль формы с обработчиками событий
   - Используй правильные типы данных 1С

2. СТИЛЬ КОДА:
   - Используй стандартные отступы (4 пробела)
   - Добавляй комментарии к сложным местам
   - Следуй соглашениям об именовании 1С
   - Используй Строка(), Число(), Булево() для преобразования типов

3. БЕЗОПАСНОСТЬ:
   - Не используй Выполнить() и Вычислить()
   - Проверяй входные параметры на корректность
   - Используй Попытка...Исключение для обработки ошибок

4. ОПТИМИЗАЦИЯ:
   - Используй Запросы для работы с данными
   - Избегай циклов по большим таблицам
   - Используй индексы при обращении к регистрам

ЗАДАЧА: {description}

Входные параметры: {input_parameters}
Выходные параметры: {output_parameters}
Бизнес-логика: {business_logic}

Верни код в формате:
```bsl
// Модуль объекта
&НаСервере
Процедура ВыполнитьОбработку() Экспорт
    // Основной код обработки
КонецПроцедуры

// Модуль формы
&НаКлиенте
Процедура КнопкаВыполнитьНажатие(Кнопка)
    // Обработчик кнопки
КонецПроцедуры
```""",
    
    def _get_report_template(self) -> Dict[str, Any]:
        """Возвращает базовый промпт для отчета."""
        return {
            'name': 'report_basic',
            'version': '1.0.0',
            'description': 'Базовый промпт для генерации отчетов 1С',
            'object_type': 'report',
            'content': self._get_report_content(),
            'variables': ['report_purpose', 'data_sources', 'grouping', 'filtering'],
            'context_requirements': {
                'include_forms': 'да',
                'include_print_forms': 'да',
                'use_sbrf_standard': 'да'
            },
            'min_tokens': 300,
            'max_tokens': 2500,
            'quality_score': 0.9
        }
    
    def _get_report_content(self) -> str:
        """Возвращает контент промпта для отчета."""
        return """Ты - эксперт по разработке отчетов в системе 1С:Предприятие. Создай качественный отчет используя СКД (Система Компоновки Данных).

Требования к генерации отчета:

1. СТРУКТУРА ОТЧЕТА:
   - Используй СКД для построения отчетов
   - Создай схему компоновки данных с наборами данных
   - Добавь группировки и поля
   - Используй параметры и отборы

2. МАКЕТ ОТЧЕТА:
   - Создай макет оформления
   - Настрой заголовки и подписи
   - Добавь форматирование для чисел и дат
   - Используй стандартные стили оформления

3. ЗАПРОС К ДАННЫМ:
   - Оптимизируй запросы к базе данных
   - Используй индексы и ограничения
   - Группируй данные по необходимости
   - Сортируй результаты

4. ФИЛЬТРАЦИЯ И ГРУППИРОВКА:
   - Добавь параметры для фильтрации данных
   - Реализуй группировки по ключевым полям
   - Используй агрегатные функции (СУММА, СРЕДНЕЕ, КОЛИЧЕСТВО)

ЗАДАЧА: {report_purpose}

Источники данных: {data_sources}
Группировки: {grouping}
Фильтрация: {filtering}

Верни код отчета в формате:
```bsl
// Схема компоновки данных
Функция СформироватьОтчет() Экспорт
    // Создание схемы СКД
    // Настройка компоновщика
    // Формирование и вывод отчета
КонецФункции

// Модуль формы
&НаКлиенте
Процедура СформироватьНажатие(Кнопка)
    // Вызов серверной функции формирования
КонецПроцедуры
```""",
    
    def _get_catalog_template(self) -> Dict[str, Any]:
        """Возвращает базовый промпт для справочника."""
        return {
            'name': 'catalog_basic',
            'version': '1.0.0',
            'description': 'Базовый промпт для генерации справочников 1С',
            'object_type': 'catalog',
            'content': self._get_catalog_content(),
            'variables': ['catalog_purpose', 'attributes', 'hierarchical', 'codes'],
            'context_requirements': {
                'include_forms': 'да',
                'include_search': 'да',
                'code_length': 'неограничено'
            },
            'min_tokens': 400,
            'max_tokens': 3000,
            'quality_score': 0.88
        }
    
    def _get_catalog_content(self) -> str:
        """Возвращает контент промпта для справочника."""
        return """Ты - эксперт по разработке справочников в системе 1С:Предприятие. Создай качественный справочник с правильной структурой данных и формами.

Требования к генерации справочника:

1. СТРУКТУРА СПРАВОЧНИКА:
   - Определи основные реквизиты справочника
   - Добавь код и наименование
   - Создай иерархию при необходимости
   - Настрой длину кода и точность наименования

2. МОДУЛЬ ОБЪЕКТА:
   - Реализуй ПриЗаписи() для валидации данных
   - Добавь ОбработкаЗаполнения() для создания по шаблону
   - Создай серверные методы для бизнес-логики

3. ФОРМЫ СПРАВОЧНИКА:
   - Основная форма элемента с необходимыми реквизитами
   - Форма списка с поиском и отбором
   - Форма выбора для подстановки в другие объекты
   - Добавь обработчики событий

4. ВАЛИДАЦИЯ ДАННЫХ:
   - Проверяй уникальность кодов
   - Валидируй заполнение обязательных реквизитов
   - Проверяй корректность ссылочных полей

ЗАДАЧА: {catalog_purpose}

Реквизиты: {attributes}
Иерархия: {hierarchical}
Кодирование: {codes}

Верни код справочника в формате:
```bsl
// Модуль объекта
&НаСервере
Процедура ПриЗаписи(Отказ)
    // Проверки и валидация
КонецПроцедуры

&НаСервере
Процедура ОбработкаЗаполнения(ДанныеЗаполнения, ТекстЗаполнения, СтандартнаяОбработка)
    // Заполнение по умолчанию
КонецПроцедуры

// Модуль формы элемента
&НаКлиенте
Процедура РеквизитПриИзменении(Элемент)
    // Обработчики изменений
КонецПроцедуры
```""",
    
    def _get_document_template(self) -> Dict[str, Any]:
        """Возвращает базовый промпт для документа."""
        return {
            'name': 'document_basic',
            'version': '1.0.0',
            'description': 'Базовый промпт для генерации документов 1С',
            'object_type': 'document',
            'content': self._get_document_content(),
            'variables': ['document_purpose', 'table_sections', 'states', 'posting'],
            'context_requirements': {
                'include_forms': 'да',
                'include_numbering': 'да',
                'automatic_posting': 'нет'
            },
            'min_tokens': 500,
            'max_tokens': 3500,
            'quality_score': 0.92
        }
    
    def _get_document_content(self) -> str:
        """Возвращает контент промпта для документа."""
        return """Ты - эксперт по разработке документов в системе 1С:Предприятие. Создай качественный документ с табличными частями, движениями и формами.

Требования к генерации документа:

1. СТРУКТУРА ДОКУМЕНТА:
   - Определи реквизиты шапки документа
   - Создай табличные части с необходимыми колонками
   - Настрой нумерацию и дату документа
   - Добавь подписи и статус документа

2. ДВИЖЕНИЯ РЕГИСТРОВ:
   - Определи какие регистры ведет документ
   - Создай процедуры ОбработкаПроведения() и ОбработкаУдаленияПроведения()
   - Проверяй корректность данных перед проведением
   - Обрабатывай ошибки проведения

3. ФОРМЫ ДОКУМЕНТА:
   - Основная форма документа с табличными частями
   - Форма печати документа
   - Форма списка документов
   - Добавь проверки при записи

4. СОСТОЯНИЯ И ОСТАТКИ:
   - Реализуй проверку остатков при необходимости
   - Добавь состояния документа (Черновик, Проведен, Отменен)
   - Создай обработчики смены состояний

ЗАДАЧА: {document_purpose}

Табличные части: {table_sections}
Состояния: {states}
Проведение: {posting}

Верни код документа в формате:
```bsl
// Модуль объекта
&НаСервере
Процедура ОбработкаПроведения(Отказ, Режим)
    // Создание движений по регистрам
    // Проверки корректности
КонецПроцедуры

&НаСервере
Процедура ОбработкаУдаленияПроведения(Отказ)
    // Удаление движений
КонецПроцедуры

// Модуль формы
&НаКлиенте
Процедура ТабличнаяЧастьПриИзменении(Элемент)
    // Обработчик изменений в ТЧ
КонецПроцедуры
```""",
    
    def _get_validation_template(self) -> Dict[str, Any]:
        """Возвращает промпт для валидации кода."""
        return {
            'name': 'validation_prompt',
            'version': '1.0.0',
            'description': 'Промпт для валидации сгенерированного кода',
            'object_type': 'validation',
            'content': self._get_validation_content(),
            'variables': ['code', 'object_type', 'validation_level'],
            'context_requirements': {
                'check_syntax': 'да',
                'check_standards': 'да',
                'check_security': 'да'
            },
            'min_tokens': 150,
            'max_tokens': 1500,
            'quality_score': 0.95
        }
    
    def _get_validation_content(self) -> str:
        """Возвращает контент промпта для валидации."""
        return """Ты - эксперт по качеству кода в 1С:Предприятие. Проанализируй предоставленный код и верни результат валидации.

Проверки для выполнения:

1. СИНТАКСИЧЕСКАЯ ПРОВЕРКА:
   - Корректность использования операторов
   - Правильность типов данных
   - Соответствие синтаксису BSL
   - Закрытие скобок и кавычек

2. СООТВЕТСТВИЕ СТАНДАРТАМ:
   - Именование переменных и процедур
   - Комментарии к коду
   - Структура кода и отступы
   - Использование типовых конструкций

3. БЕЗОПАСНОСТЬ:
   - Проверка на опасные функции (Выполнить, Вычислить)
   - Валидация входных данных
   - Обработка исключений
   - SQL-инъекции и утечки данных

4. ПРОИЗВОДИТЕЛЬНОСТЬ:
   - Оптимизация запросов к БД
   - Избегание лишних циклов
   - Правильное использование индексов
   - Кэширование данных

КОД ДЛЯ ПРОВЕРКИ:
```bsl
{code}
```

Тип объекта: {object_type}
Уровень проверки: {validation_level}

Верни результат в формате JSON:
{
  "valid": true/false,
  "syntax_errors": [],
  "standard_violations": [],
  "security_issues": [],
  "performance_issues": [],
  "overall_score": 0.95,
  "recommendations": []
}""",
    
    def _get_security_template(self) -> Dict[str, Any]:
        """Возвращает промпт для анализа безопасности."""
        return {
            'name': 'security_analysis',
            'version': '1.0.0',
            'description': 'Промпт для анализа безопасности кода',
            'object_type': 'security',
            'content': self._get_security_content(),
            'variables': ['code', 'security_context', 'threat_model'],
            'context_requirements': {
                'check_injection': 'да',
                'check_privileges': 'да',
                'check_data_exposure': 'да'
            },
            'min_tokens': 200,
            'max_tokens': 2000,
            'quality_score': 0.98
        }
    
    def _get_security_content(self) -> str:
        """Возвращает контент промпта для анализа безопасности."""
        return """Ты - эксперт по информационной безопасности в системах 1С:Предприятие. Проведи глубокий анализ безопасности предоставленного кода.

Типы угроз для проверки:

1. ВЫПОЛНЕНИЕ ПРОИЗВОЛЬНОГО КОДА:
   - Функции Выполнить() и Вычислить()
   - Динамическое создание кода
   - Выполнение внешних скриптов
   - Вызов системных команд

2. SQL-ИНЪЕКЦИИ:
   - Небезопасное формирование запросов
   - Параметризованные запросы
   - Экранирование специальных символов
   - Проверка входных данных

3. УТЕЧКА ДАННЫХ:
   - Некорректная работа с кэшем
   - Логирование чувствительных данных
   - Ограничения доступа к данным
   - Шифрование конфиденциальной информации

4. ПОВЫШЕНИЕ ПРИВИЛЕГИЙ:
   - Проверка прав пользователей
   - Ролевые модели доступа
   - Временные привилегии
   - Аудит действий пользователей

КОД ДЛЯ АНАЛИЗА:
```bsl
{code}
```

Контекст безопасности: {security_context}
Модель угроз: {threat_model}

Верни анализ в формате JSON:
{
  "security_level": "LOW/MEDIUM/HIGH/CRITICAL",
  "threats_found": [
    {
      "type": "sql_injection",
      "severity": "HIGH",
      "location": "строка 45",
      "description": "Описание угрозы",
      "recommendation": "Рекомендация по устранению"
    }
  ],
  "compliance_check": {
    "owasp_top10": "PASS/FAIL",
    "nist_framework": "PASS/FAIL",
    "iso27001": "PASS/FAIL"
  },
  "overall_risk": 0.15,
  "mitigation_recommendations": []
}""",
    
    def save_template(self, name: str, template_data: Dict[str, Any]) -> bool:
        """Сохраняет шаблон промпта."""
        try:
            template = PromptTemplate(**template_data)
            self._prompt_cache[name] = template
            
            # Сохранить в файл
            template_file = self.templates_dir / f"{name}.json"
            with open(template_file, 'w', encoding='utf-8') as f:
                json.dump(asdict(template), f, ensure_ascii=False, indent=2, default=str)
            
            self.logger.info(f"Шаблон промпта '{name}' сохранен")
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка при сохранении шаблона '{name}': {e}")
            return False
    
    def load_template(self, name: str) -> Optional[PromptTemplate]:
        """Загружает шаблон промпта из кэша или файла."""
        if name in self._prompt_cache:
            return self._prompt_cache[name]
        
        try:
            template_file = self.templates_dir / f"{name}.json"
            if not template_file.exists():
                return None
            
            with open(template_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Преобразование дат
                if 'created_at' in data:
                    data['created_at'] = datetime.fromisoformat(data['created_at'].replace('Z', '+00:00'))
                if 'updated_at' in data:
                    data['updated_at'] = datetime.fromisoformat(data['updated_at'].replace('Z', '+00:00'))
                
                template = PromptTemplate(**data)
                self._prompt_cache[name] = template
                return template
                
        except Exception as e:
            self.logger.error(f"Ошибка при загрузке шаблона '{name}': {e}")
            return None
    
    def get_template(self, name: str) -> Optional[str]:
        """Возвращает содержимое промпта по имени."""
        template = self.load_template(name)
        return template.content if template else None
    
    def get_templates_by_type(self, object_type: str) -> List[PromptTemplate]:
        """Возвращает все шаблоны для указанного типа объекта."""
        templates = []
        for template in self._prompt_cache.values():
            if template.object_type == object_type:
                templates.append(template)
        return templates
    
    def list_templates(self) -> List[str]:
        """Возвращает список всех доступных шаблонов."""
        templates = []
        for template_file in self.templates_dir.glob("*.json"):
            templates.append(template_file.stem)
        return sorted(templates)
    
    def update_template_stats(self, name: str, success: bool, quality_score: float = None):
        """Обновляет статистику использования шаблона."""
        template = self.load_template(name)
        if template:
            template.usage_count += 1
            if success:
                template.success_rate = (template.success_rate * (template.usage_count - 1) + 1.0) / template.usage_count
            else:
                template.success_rate = (template.success_rate * (template.usage_count - 1)) / template.usage_count
            
            if quality_score is not None:
                template.quality_score = (template.quality_score + quality_score) / 2
            
            template.updated_at = datetime.utcnow()
            self.save_template(name, asdict(template))
    
    def get_best_template(self, object_type: str, context: Dict[str, Any] = None) -> Optional[PromptTemplate]:
        """Возвращает лучший шаблон для указанного типа и контекста."""
        templates = self.get_templates_by_type(object_type)
        if not templates:
            return None
        
        # Сортируем по качеству и проценту успеха
        best_template = max(templates, key=lambda t: t.quality_score * t.success_rate)
        return best_template
    
    def create_derivative_template(self, base_name: str, name: str, modifications: Dict[str, Any]) -> bool:
        """Создает производный шаблон на основе существующего."""
        base_template = self.load_template(base_name)
        if not base_template:
            return False
        
        # Создаем производный шаблон
        derivative_data = asdict(base_template)
        derivative_data.update({
            'name': name,
            'version': f"{base_template.version}.{derivative_data.get('usage_count', 0) + 1}",
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
            **modifications
        })
        
        return self.save_template(name, derivative_data)