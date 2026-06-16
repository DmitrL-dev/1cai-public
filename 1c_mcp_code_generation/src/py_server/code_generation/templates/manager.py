
#!/usr/bin/env python3
"""
Template Manager для 1C AI MCP Code Generation

Менеджер шаблонов для генерации кода 1С.
Обеспечивает управление библиотекой шаблонов и их применение.

Версия: 1.0
Дата: 30.10.2025
"""

import hashlib
import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

@dataclass
class CodeTemplate:
    """Шаблон кода 1С"""
    id: str
    name: str
    description: str
    object_type: str
    complexity: str  # simple, medium, complex
    tags: List[str]
    structure: Dict[str, str]  # manager_module, object_module, form, macros
    parameters: List[Dict[str, Any]]
    examples: List[Dict[str, str]]
    version: str
    created_at: datetime
    updated_at: datetime
    usage_count: int = 0
    success_rate: float = 0.0

class TemplateManager:
    """Менеджер шаблонов для генерации кода"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Инициализация менеджера шаблонов
        
        Args:
            config: Конфигурация менеджера
        """
        self.config = config
        self.templates: Dict[str, CodeTemplate] = {}
        self.template_cache = {}
        self.learning_data = {}
        
        # Настройки
        self.auto_learning = config.get('auto_learning', True)
        self.cache_enabled = config.get('cache_enabled', True)
        self.cache_ttl = config.get('cache_ttl', 3600)  # секунд
        self.custom_templates_path = config.get('custom_templates_path', './custom_templates')
        
        # Инициализация
        self._initialize_templates()
        self._load_custom_templates()
    
    async def get_template(self, object_type: str, prompt: str) -> Optional[Dict[str, Any]]:
        """
        Получение оптимального шаблона для генерации
        
        Args:
            object_type: Тип объекта 1С
            prompt: Промпт для генерации
            
        Returns:
            Данные шаблона или None
        """
        try:
            # Поиск в кэше
            cache_key = self._generate_cache_key(object_type, prompt)
            if self.cache_enabled and cache_key in self.template_cache:
                cached_entry = self.template_cache[cache_key]
                if self._is_cache_valid(cached_entry):
                    logger.info(f"Шаблон найден в кэше: {cache_key}")
                    return cached_entry['template']
            
            # Поиск подходящего шаблона
            suitable_templates = self._find_suitable_templates(object_type, prompt)
            
            if not suitable_templates:
                logger.warning(f"Не найдены подходящие шаблоны для типа {object_type}")
                return self._get_default_template(object_type)
            
            # Выбор лучшего шаблона
            best_template = self._select_best_template(suitable_templates, prompt)
            
            # Обновление статистики использования
            self._update_template_usage(best_template.id)
            
            # Кэширование результата
            if self.cache_enabled:
                self.template_cache[cache_key] = {
                    'template': asdict(best_template),
                    'timestamp': datetime.now()
                }
            
            logger.info(f"Выбран шаблон: {best_template.name} (id: {best_template.id})")
            return asdict(best_template)
            
        except Exception as e:
            logger.error(f"Ошибка получения шаблона: {e}")
            return self._get_default_template(object_type)
    
    async def create_template(self, template_data: Dict[str, Any], created_by: str = "system") -> str:
        """
        Создание нового шаблона
        
        Args:
            template_data: Данные шаблона
            created_by: Автор шаблона
            
        Returns:
            ID созданного шаблона
        """
        try:
            # Генерация ID
            template_id = self._generate_template_id(template_data)
            
            # Валидация данных
            if not self._validate_template_data(template_data):
                raise ValueError("Некорректные данные шаблона")
            
            # Создание объекта шаблона
            template = CodeTemplate(
                id=template_id,
                name=template_data['name'],
                description=template_data['description'],
                object_type=template_data['object_type'],
                complexity=template_data.get('complexity', 'medium'),
                tags=template_data.get('tags', []),
                structure=template_data.get('structure', {}),
                parameters=template_data.get('parameters', []),
                examples=template_data.get('examples', []),
                version=template_data.get('version', '1.0'),
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            # Сохранение шаблона
            self.templates[template_id] = template
            
            # Обновление кэша
            self._clear_cache()
            
            # Обучение системы (если включено)
            if self.auto_learning:
                await self._learn_from_template(template, template_data)
            
            logger.info(f"Создан новый шаблон: {template.name} (id: {template_id})")
            return template_id
            
        except Exception as e:
            logger.error(f"Ошибка создания шаблона: {e}")
            raise
    
    async def update_template(self, template_id: str, updates: Dict[str, Any]) -> bool:
        """
        Обновление существующего шаблона
        
        Args:
            template_id: ID шаблона
            updates: Обновления данных
            
        Returns:
            True если обновление успешно
        """
        try:
            if template_id not in self.templates:
                logger.error(f"Шаблон не найден: {template_id}")
                return False
            
            template = self.templates[template_id]
            
            # Применение обновлений
            for key, value in updates.items():
                if hasattr(template, key):
                    setattr(template, key, value)
            
            template.updated_at = datetime.now()
            
            # Обновление кэша
            self._clear_cache()
            
            logger.info(f"Обновлен шаблон: {template_id}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка обновления шаблона {template_id}: {e}")
            return False
    
    async def delete_template(self, template_id: str) -> bool:
        """
        Удаление шаблона
        
        Args:
            template_id: ID шаблона
            
        Returns:
            True если удаление успешно
        """
        try:
            if template_id not in self.templates:
                logger.error(f"Шаблон не найден: {template_id}")
                return False
            
            # Удаление шаблона
            del self.templates[template_id]
            
            # Очистка кэша
            self._clear_cache()
            
            logger.info(f"Удален шаблон: {template_id}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка удаления шаблона {template_id}: {e}")
            return False
    
    def get_template_list(self, object_type: str = None, tags: List[str] = None) -> List[Dict[str, Any]]:
        """
        Получение списка шаблонов
        
        Args:
            object_type: Фильтр по типу объекта
            tags: Фильтр по тегам
            
        Returns:
            Список шаблонов
        """
        templates = list(self.templates.values())
        
        # Фильтрация по типу объекта
        if object_type:
            templates = [t for t in templates if t.object_type == object_type]
        
        # Фильтрация по тегам
        if tags:
            templates = [t for t in templates if any(tag in t.tags for tag in tags)]
        
        # Сортировка по популярности и дате обновления
        templates.sort(key=lambda t: (t.success_rate, t.updated_at), reverse=True)
        
        return [asdict(template) for template in templates]
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Получение статистики менеджера шаблонов
        
        Returns:
            Статистика использования
        """
        if not self.templates:
            return {
                'total_templates': 0,
                'by_object_type': {},
                'average_success_rate': 0.0,
                'total_usage': 0
            }
        
        # Статистика по типам объектов
        by_object_type = {}
        total_usage = 0
        total_success_rate = 0.0
        
        for template in self.templates.values():
            obj_type = template.object_type
            if obj_type not in by_object_type:
                by_object_type[obj_type] = {'count': 0, 'usage': 0}
            
            by_object_type[obj_type]['count'] += 1
            by_object_type[obj_type]['usage'] += template.usage_count
            
            total_usage += template.usage_count
            total_success_rate += template.success_rate
        
        avg_success_rate = total_success_rate / len(self.templates) if self.templates else 0.0
        
        return {
            'total_templates': len(self.templates),
            'by_object_type': by_object_type,
            'average_success_rate': round(avg_success_rate, 2),
            'total_usage': total_usage,
            'cache_size': len(self.template_cache),
            'auto_learning_enabled': self.auto_learning
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Получение статуса менеджера"""
        return {
            'initialized': True,
            'templates_loaded': len(self.templates),
            'cache_enabled': self.cache_enabled,
            'auto_learning': self.auto_learning,
            'custom_path': self.custom_templates_path,
            'version': '1.0'
        }
    
    def _initialize_templates(self):
        """Инициализация базовых шаблонов"""
        
        # Базовые шаблоны для разных типов объектов
        base_templates = [
            self._create_basic_processing_template(),
            self._create_basic_report_template(),
            self._create_basic_catalog_template(),
            self._create_basic_document_template(),
            self._create_basic_register_template(),
            self._create_basic_common_module_template()
        ]
        
        for template_data in base_templates:
            template_id = self._generate_template_id(template_data)
            template = CodeTemplate(
                id=template_id,
                name=template_data['name'],
                description=template_data['description'],
                object_type=template_data['object_type'],
                complexity=template_data['complexity'],
                tags=template_data['tags'],
                structure=template_data['structure'],
                parameters=template_data['parameters'],
                examples=template_data['examples'],
                version='1.0',
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            self.templates[template_id] = template
    
    def _create_basic_processing_template(self) -> Dict[str, Any]:
        """Создание базового шаблона обработки"""
        return {
            'name': 'Базовая обработка',
            'description': 'Стандартный шаблон для создания обработок',
            'object_type': 'processing',
            'complexity': 'simple',
            'tags': ['basic', 'starter', 'common'],
            'structure': {
                'manager_module': '''// =====================================
// Модуль менеджера обработки: {object_name}
// =====================================

#Область ПрограммныйИнтерфейс

// Основная процедура обработки данных
Процедура ОбработатьДанные(ПараметрыОбработки) Экспорт
    // Логика обработки данных
КонецПроцедуры

// Получение результата обработки
Функция ПолучитьРезультат() Экспорт
    // Возврат результата обработки
КонецФункции

#КонецОбласти

#Область СлужебныеПроцедурыИФункции

// Служебные процедуры и функции
Процедура ВнутренняяОбработка()
    // Внутренняя логика
КонецПроцедуры

#КонецОбласти''',
                'object_module': '''// =====================================
// Модуль объекта обработки: {object_name}
// =====================================

#Область ПрограммныйИнтерфейс

// Запуск обработки
Процедура ВыполнитьОбработку() Экспорт
    // Основная логика обработки
КонецПроцедуры

#КонецОбласти''',
                'form': '''&НаКлиенте
Процедура Обработать(Команда)
    // Обработка команды пользователя
КонецПроцедуры''',
                'macros': ['ОсновнаяФорма', 'Результат']
            },
            'parameters': [
                {
                    'name': 'object_name',
                    'type': 'string',
                    'required': True,
                    'description': 'Имя создаваемого объекта'
                }
            ],
            'examples': [
                {
                    'prompt': 'Создать обработку для очистки данных',
                    'generated_code': 'Сгенерированный код...'
                }
            ]
        }
    
    def _create_basic_report_template(self) -> Dict[str, Any]:
        """Создание базового шаблона отчета"""
        return {
            'name': 'Базовый отчет',
            'description': 'Шаблон отчета с группировками и отборами',
            'object_type': 'report',
            'complexity': 'medium',
            'tags': ['reporting', 'data', 'analytics'],
            'structure': {
                'manager_module': '''// =====================================
// Модуль менеджера отчета: {object_name}
// =====================================

#Область ПрограммныйИнтерфейс

// Получение схемы компоновки данных
Функция ПолучитьСхему() Экспорт
    // Возврат схемы СКД
КонецФункции

// Компоновка результата отчета
Процедура СформироватьОтчет(Результат, ДанныеРасшифровки, СтандартнаяОбработка) Экспорт
    // Стандартная компоновка отчета
КонецПроцедуры

#КонецОбласти''',
                'object_module': '''// =====================================
// Модуль объекта отчета: {object_name}
// =====================================

#Область ПрограммныйИнтерфейс

// Создание и настройка отчета
Процедура СоздатьОтчет() Экспорт
    // Настройка параметров отчета
КонецПроцедуры

#КонецОбласти''',
                'form': '''&НаКлиенте
Процедура Сформировать(Команда)
    // Формирование отчета
КонецПроцедуры''',
                'macros': ['Схема', 'Настройки', 'Результат']
            },
            'parameters': [
                {
                    'name': 'object_name',
                    'type': 'string',
                    'required': True,
                    'description': 'Имя создаваемого отчета'
                }
            ],
            'examples': [
                {
                    'prompt': 'Создать отчет по продажам',
                    'generated_code': 'Сгенерированный код отчета...'
                }
            ]
        }
    
    def _create_basic_catalog_template(self) -> Dict[str, Any]:
        """Создание базового шаблона справочника"""
        return {
            'name': 'Базовый справочник',
            'description': 'Стандартный шаблон справочника',
            'object_type': 'catalog',
            'complexity': 'simple',
            'tags': ['catalog', 'reference', 'basic'],
            'structure': {
                'manager_module': '''// =====================================
// Модуль менеджера справочника: {object_name}
// =====================================

#Область ПрограммныйИнтерфейс

// Создание нового элемента справочника
Функция СоздатьЭлемент(Параметры) Экспорт
    // Логика создания элемента
КонецФункции

// Поиск элемента по наименованию
Функция НайтиПоНаименованию(Наименование) Экспорт
    // Поиск элемента
КонецФункции

#КонецОбласти''',
                'object_module': '''// =====================================
// Модуль объекта справочника: {object_name}
// =====================================

#Область ПрограммныйИнтерфейс

// При записи элемента
Процедура ПриЗаписи(Отказ)
    // Логика при записи
КонецПроцедуры

// При копировании
Процедура ПриКопировании(ОбъектКопирования)
    // Логика при копировании
КонецПроцедуры

#КонецОбласти''',
                'form': '''&НаКлиенте
Процедура Записать(Команда)
    // Запись элемента справочника
КонецПроцедуры''',
                'macros': ['ОсновнаяФорма', 'ФормаЭлемента']
            },
            'parameters': [
                {
                    'name': 'object_name',
                    'type': 'string',
                    'required': True,
                    'description': 'Имя создаваемого справочника'
                }
            ],
            'examples': [
                {
                    'prompt': 'Создать справочник номенклатуры',
                    'generated_code': 'Сгенерированный код справочника...'
                }
            ]
        }
    
    def _create_basic_document_template(self) -> Dict[str, Any]:
        """Создание базового шаблона документа"""
        return {
            'name': 'Базовый документ',
            'description': 'Шаблон документа с проведением',
            'object_type': 'document',
            'complexity': 'medium',
            'tags': ['document', 'transaction', 'basic'],
            'structure': {
                'manager_module': '''// =====================================
// Модуль менеджера документа: {object_name}
// =====================================

#Область ПрограммныйИнтерфейс

// Создание документа
Функция СоздатьДокумент(Параметры) Экспорт
    // Логика создания документа
КонецФункции

// Проведение документа
Процедура ПровестиДокумент(Документ) Экспорт
    // Логика проведения
КонецПроцедуры

#КонецОбласти''',
                'object_module': '''// =====================================
// Модуль объекта документа: {object_name}
// =====================================

#Область ПрограммныйИнтерфейс

// Обработка проведения
Процедура ОбработкаПроведения(Отказ, Режим)
    // Логика проведения документа
КонецПроцедуры

// Обработка отмены проведения
Процедура ОбработкаОтменыПроведения(Отказ)
    // Логика отмены проведения
КонецПроцедуры

#КонецОбласти''',
                'form': '''&НаКлиенте
Процедура Провести(Команда)
    // Проведение документа
КонецПроцедуры''',
                'macros': ['ОсновнаяФорма', 'ФормаДокумента']
            },
            'parameters': [
                {
                    'name': 'object_name',
                    'type': 'string',
                    'required': True,
                    'description': 'Имя создаваемого документа'
                }
            ],
            'examples': [
                {
                    'prompt': 'Создать документ поступления товаров',
                    'generated_code': 'Сгенерированный код документа...'
                }
            ]
        }
    
    def _create_basic_register_template(self) -> Dict[str, Any]:
        """Создание базового шаблона регистра"""
        return {
            'name': 'Базовый регистр',
            'description': 'Шаблон регистра накопления',
            'object_type': 'register',
            'complexity': 'medium',
            'tags': ['register', 'accumulation', 'data'],
            'structure': {
                'manager_module': '''// =====================================
// Модуль менеджера регистра: {object_name}
// =====================================

#Область ПрограммныйИнтерфейс

// Движение по регистру
Процедура ДобавитьДвижение(Движение, Запись) Экспорт
    // Логика формирования движения
КонецПроцедуры

// Получение остатков
Функция ПолучитьОстатки(Параметры) Экспорт
    // Получение остатков по регистру
КонецФункции

#КонецОбласти''',
                'object_module': '''// =====================================
// Модуль набора записей регистра: {object_name}
// =====================================

#Область ПрограммныйИнтерфейс

// При записи набора
Процедура ПриЗаписи(Отказ, Замещение)
    // Логика при записи
КонецПроцедуры

#КонецОбласти''',
                'form': '''&НаКлиенте
Процедура Записать(Команда)
    // Запись набора записей
КонецПроцедуры''',
                'macros': ['ОсновнаяФорма', 'СписокЗаписей']
            },
            'parameters': [
                {
                    'name': 'object_name',
                    'type': 'string',
                    'required': True,
                    'description': 'Имя создаваемого регистра'
                }
            ],
            'examples': [
                {
                    'prompt': 'Создать регистр остатков товаров',
                    'generated_code': 'Сгенерированный код регистра...'
                }
            ]
        }
    
    def _create_basic_common_module_template(self) -> Dict[str, Any]:
        """Создание базового шаблона общего модуля"""
        return {
            'name': 'Базовый общий модуль',
            'description': 'Шаблон общего модуля',
            'object_type': 'common_module',
            'complexity': 'simple',
            'tags': ['common', 'utility', 'helper'],
            'structure': {
                'manager_module': '''// =====================================
// Общий модуль: {object_name}
// =====================================

#Область ПрограммныйИнтерфейс

// Основная функция модуля
Функция ВыполнитьОперацию(Параметры) Экспорт
    // Логика операции
КонецФункции

#КонецОбласти

#Область СлужебныеПроцедурыИФункции

// Служебные функции
Функция ВспомогательнаяФункция(Параметр) Экспорт
    // Вспомогательная логика
КонецФункции

#КонецОбласти''',
                'object_module': '',
                'form': '',
                'macros': []
            },
            'parameters': [
                {
                    'name': 'object_name',
                    'type': 'string',
                    'required': True,
                    'description': 'Имя создаваемого общего модуля'
                }
            ],
            'examples': [
                {
                    'prompt': 'Создать общий модуль для работы с файлами',
                    'generated_code': 'Сгенерированный код общего модуля...'
                }
            ]
        }
    
    def _load_custom_templates(self):
        """Загрузка пользовательских шаблонов"""
        try:
            if os.path.exists(self.custom_templates_path):
                for filename in os.listdir(self.custom_templates_path):
                    if filename.endswith('.json'):
                        template_file = os.path.join(self.custom_templates_path, filename)
                        self._load_template_file(template_file)
        except Exception as e:
            logger.error(f"Ошибка загрузки пользовательских шаблонов: {e}")
    
    def _load_template_file(self, file_path: str):
        """Загрузка шаблона из файла"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                template_data = json.load(f)
            
            template_id = self._generate_template_id(template_data)
            if template_id not in self.templates:
                # Создание шаблона (упрощенная версия)
                logger.info(f"Загружен пользовательский шаблон: {template_data.get('name', 'Unknown')}")
                
        except Exception as e:
            logger.error(f"Ошибка загрузки файла шаблона {file_path}: {e}")
    
    def _find_suitable_templates(self, object_type: str, prompt: str) -> List[CodeTemplate]:
        """Поиск подходящих шаблонов"""
        
        suitable = []
        
        for template in self.templates.values():
            # Проверка типа объекта
            if template.object_type != object_type:
                continue
            
            # Оценка релевантности по тегам и описанию
            relevance_score = self._calculate_relevance(template, prompt)
            
            if relevance_score > 0.3:  # Минимальный порог релевантности
                suitable.append(template)
        
        return suitable
    
    def _calculate_relevance(self, template: CodeTemplate, prompt: str) -> float:
        """Расчет релевантности шаблона"""
        
        score = 0.0
        
        # Поиск ключевых слов в промпте
        prompt_lower = prompt.lower()
        template_text = f"{template.name} {template.description} {' '.join(template.tags)}".lower()
        
        # Счетчик совпадений
        words_in_prompt = set(prompt_lower.split())
        words_in_template = set(template_text.split())
        
        matches = len(words_in_prompt.intersection(words_in_template))
        total_words = len(words_in_prompt.union(words_in_template))
        
        if total_words > 0:
            score += matches / total_words * 0.7
        
        # Бонус за успешность использования
        score += template.success_rate * 0.3
        
        return min(score, 1.0)
    
    def _select_best_template(self, templates: List[CodeTemplate], prompt: str) -> CodeTemplate:
        """Выбор лучшего шаблона"""
        
        if len(templates) == 1:
            return templates[0]
        
        # Комплексная оценка
        best_template = None
        best_score = 0.0
        
        for template in templates:
            score = (
                self._calculate_relevance(template, prompt) * 0.4 +
                template.success_rate * 0.3 +
                (template.usage_count / 100) * 0.2 +  # Нормализованное использование
                (1.0 if template.complexity == 'medium' else 0.7) * 0.1  # Преимущество средней сложности
            )
            
            if score > best_score:
                best_score = score
                best_template = template
        
        return best_template or templates[0]
    
    def _update_template_usage(self, template_id: str):
        """Обновление статистики использования шаблона"""
        if template_id in self.templates:
            self.templates[template_id].usage_count += 1
    
    def _generate_template_id(self, template_data: Dict[str, Any]) -> str:
        """Генерация ID шаблона"""
        content = f"{template_data['name']}_{template_data['object_type']}_{template_data['version']}"
        return hashlib.md5(content.encode('utf-8')).hexdigest()[:16]
    
    def _generate_cache_key(self, object_type: str, prompt: str) -> str:
        """Генерация ключа кэша"""
        content = f"{object_type}_{hashlib.md5(prompt.encode('utf-8')).hexdigest()}"
        return content
    
    def _is_cache_valid(self, cached_entry: Dict[str, Any]) -> bool:
        """Проверка валидности кэша"""
        cache_lifetime = timedelta(seconds=self.cache_ttl)
        return datetime.now() - cached_entry['timestamp'] < cache_lifetime
    
    def _get_default_template(self, object_type: str) -> Dict[str, Any]:
        """Получение шаблона по умолчанию для типа объекта"""
        
        default_templates = {
            'processing': 'basic_processing',
            'report': 'basic_report',
            'catalog': 'basic_catalog',
            'document': 'basic_document',
            'register': 'basic_register',
            'common_module': 'basic_common_module'
        }
        
        default_id = default_templates.get(object_type)
        
        if default_id:
            for template in self.templates.values():
                if template.id == default_id:
                    return asdict(template)
        
        # Fallback - первый доступный шаблон
        for template in self.templates.values():
            if template.object_type == object_type:
                return asdict(template)
        
        return {}
    
    def _validate_template_data(self, template_data: Dict[str, Any]) -> bool:
        """Валидация данных шаблона"""
        
        required_fields = ['name', 'description', 'object_type']
        
        for field in required_fields:
            if field not in template_data or not template_data[field]:
                return False
        
        # Проверка типа объекта
        valid_types = ['processing', 'report', 'catalog', 'document', 'register', 'common_module']
        if template_data['object_type'] not in valid_types:
            return False
        
        return True
    
    def _clear_cache(self):
        """Очистка кэша"""
        self.template_cache.clear()
    
    async def _learn_from_template(self, template: CodeTemplate, template_data: Dict[str, Any]):
        """Обучение системы на основе шаблона"""
        # Упрощенная реализация обучения
        # В полной версии здесь был бы ML компонент
        
        learning_entry = {
            'template_id': template.id,
            'object_type': template.object_type,
            'complexity': template.complexity,
            'tags': template.tags,
            'performance_score': 0.8,  # Примерная оценка
            'timestamp': datetime.now().isoformat()
        }
        
        if template.object_type not in self.learning_data:
            self.learning_data[template.object_type] = []
        
        self.learning_data[template.object_type].append(learning_entry)
    
    async def optimize_templates(self) -> Dict[str, Any]:
        """Оптимизация шаблонов на основе данных обучения"""
        
        optimization_results = {
            'updated_templates': 0,
            'removed_templates': 0,
            'new_templates_suggested': 0,
            'performance_improvements': []
        }
        
        try:
            # Анализ неэффективных шаблонов
            for template in list(self.templates.values()):
                if template.usage_count > 10 and template.success_rate < 0.6:
                    # Предложение улучшения
                    optimization_results['performance_improvements'].append({
                        'template_id': template.id,
                        'current_success_rate': template.success_rate,
                        'suggested_action': 'optimize_structure'
                    })
            
            logger.info(f"Оптимизация завершена: {optimization_results}")
            
        except Exception as e:
            logger.error(f"Ошибка оптимизации шаблонов: {e}")
        
        return optimization_results