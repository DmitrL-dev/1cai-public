
#!/usr/bin/env python3
"""
Context Collector для 1C AI MCP Code Generation

Коллектор контекста для сбора информации о 1С конфигурации и среде.

Версия: 1.0
Дата: 30.10.2025
"""

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

@dataclass
class ConfigurationContext:
    """Контекст конфигурации 1С"""
    configuration_name: str
    platform_version: str
    language: str
    existing_objects: List[Dict[str, str]]
    module_structure: Dict[str, Any]
    performance_hints: List[str]
    metadata: Dict[str, Any]

class ContextCollector:
    """Коллектор контекста для генерации кода"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Инициализация коллектора контекста
        
        Args:
            config: Конфигурация коллектора
        """
        self.config = config
        
        # Настройки
        self.enabled = config.get('enabled', True)
        self.cache_enabled = config.get('cache_enabled', True)
        self.cache_ttl = config.get('cache_ttl', 1800)  # 30 минут
        self.include_metadata = config.get('include_metadata', True)
        self.include_performance_hints = config.get('include_performance_hints', True)
        
        # Кэш контекста
        self.context_cache = {}
        self.cache_timestamps = {}
        
        # Источники контекста
        self.context_sources = self._initialize_context_sources()
        
        logger.info("ContextCollector инициализирован")
    
    async def collect_context(self, request) -> Dict[str, Any]:
        """
        Сбор контекста для генерации кода
        
        Args:
            request: Запрос на генерацию
            
        Returns:
            Словарь с контекстом
        """
        if not self.enabled:
            return {}
        
        try:
            # Проверка кэша
            cache_key = self._generate_cache_key(request)
            if self.cache_enabled and self._is_cache_valid(cache_key):
                logger.info(f"Контекст получен из кэша: {cache_key}")
                return self.context_cache[cache_key]
            
            # Сбор контекста из различных источников
            context_data = {}
            
            # 1. Контекст из запроса
            request_context = self._extract_request_context(request)
            context_data.update(request_context)
            
            # 2. Информация о платформе
            platform_context = await self._collect_platform_context()
            context_data.update(platform_context)
            
            # 3. Структура конфигурации
            config_context = await self._collect_configuration_context()
            context_data.update(config_context)
            
            # 4. Метаданные объектов
            if self.include_metadata:
                metadata_context = await self._collect_metadata_context(request)
                context_data.update(metadata_context)
            
            # 5. Подсказки по производительности
            if self.include_performance_hints:
                performance_context = await self._collect_performance_context(request)
                context_data.update(performance_context)
            
            # 6. Стандарты и лучшие практики
            standards_context = await self._collect_standards_context(request.object_type)
            context_data.update(standards_context)
            
            # Кэширование результата
            if self.cache_enabled:
                self.context_cache[cache_key] = context_data
                self.cache_timestamps[cache_key] = datetime.now()
            
            logger.info(f"Контекст собран: {len(context_data)} элементов")
            return context_data
            
        except Exception as e:
            logger.error(f"Ошибка сбора контекста: {e}")
            return {'error': str(e)}
    
    async def get_configuration_info(self) -> Dict[str, Any]:
        """Получение информации о конфигурации"""
        
        try:
            # В реальной системе здесь был бы запрос к 1С через COM/ODBC
            # Для демонстрации возвращаем mock данные
            
            return {
                'configuration_name': 'ДемоКонфигурация',
                'platform_version': '8.3.20.1563',
                'language': 'ru',
                'created_date': '2023-01-01',
                'last_modified': datetime.now().isoformat(),
                'module_count': 150,
                'user_count': 25,
                'database_size': '2.5 GB'
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения информации о конфигурации: {e}")
            return {}
    
    async def get_existing_objects(self, object_type: str = None) -> List[Dict[str, str]]:
        """Получение списка существующих объектов"""
        
        try:
            # Mock данные для демонстрации
            all_objects = [
                {'type': 'Справочник', 'name': 'Номенклатура', 'description': 'Справочник номенклатуры'},
                {'type': 'Справочник', 'name': 'Контрагенты', 'description': 'Справочник контрагентов'},
                {'type': 'Документ', 'name': 'ПоступлениеТоваров', 'description': 'Документ поступления товаров'},
                {'type': 'Документ', 'name': 'РеализацияТоваров', 'description': 'Документ реализации'},
                {'type': 'Обработка', 'name': 'ЗагрузкаДанных', 'description': 'Обработка загрузки данных'},
                {'type': 'Обработка', 'name': 'ОбменДанными', 'description': 'Обработка обмена данными'},
                {'type': 'Отчет', 'name': 'Продажи', 'description': 'Отчет по продажам'},
                {'type': 'Отчет', 'name': 'Остатки', 'description': 'Отчет по остаткам'},
                {'type': 'Регистр', 'name': 'ОстаткиТоваров', 'description': 'Регистр остатков товаров'},
                {'type': 'Регистр', 'name': 'Продажи', 'description': 'Регистр продаж'}
            ]
            
            if object_type:
                return [obj for obj in all_objects if obj['type'] == object_type]
            else:
                return all_objects
                
        except Exception as e:
            logger.error(f"Ошибка получения списка объектов: {e}")
            return []
    
    def _extract_request_context(self, request) -> Dict[str, Any]:
        """Извлечение контекста из запроса"""
        
        context = {
            'request_type': 'code_generation',
            'object_type': getattr(request, 'object_type', 'unknown'),
            'code_style': getattr(request, 'code_style', 'standard'),
            'include_comments': getattr(request, 'include_comments', True),
            'use_standards': getattr(request, 'use_standards', True)
        }
        
        # Дополнительные параметры из контекста запроса
        if hasattr(request, 'context') and request.context:
            context['custom_context'] = request.context
        
        return context
    
    async def _collect_platform_context(self) -> Dict[str, Any]:
        """Сбор контекста платформы"""
        
        try:
            platform_info = await self.get_configuration_info()
            
            return {
                'platform': {
                    'version': platform_info.get('platform_version', 'unknown'),
                    'configuration_name': platform_info.get('configuration_name', 'unknown'),
                    'language': platform_info.get('language', 'ru')
                },
                'environment': {
                    'os': os.name,
                    'python_version': '3.8+',
                    'timestamp': datetime.now().isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Ошибка сбора контекста платформы: {e}")
            return {'platform_error': str(e)}
    
    async def _collect_configuration_context(self) -> Dict[str, Any]:
        """Сбор контекста конфигурации"""
        
        try:
            config_info = await self.get_configuration_info()
            existing_objects = await self.get_existing_objects()
            
            # Группировка объектов по типам
            objects_by_type = {}
            for obj in existing_objects:
                obj_type = obj['type']
                if obj_type not in objects_by_type:
                    objects_by_type[obj_type] = []
                objects_by_type[obj_type].append(obj['name'])
            
            return {
                'configuration': {
                    'name': config_info.get('configuration_name'),
                    'created_date': config_info.get('created_date'),
                    'last_modified': config_info.get('last_modified'),
                    'statistics': {
                        'total_objects': len(existing_objects),
                        'modules_count': config_info.get('module_count', 0),
                        'users_count': config_info.get('user_count', 0),
                        'database_size': config_info.get('database_size', '0 MB')
                    }
                },
                'objects_summary': objects_by_type,
                'existing_objects_count': len(existing_objects)
            }
            
        except Exception as e:
            logger.error(f"Ошибка сбора контекста конфигурации: {e}")
            return {'configuration_error': str(e)}
    
    async def _collect_metadata_context(self, request) -> Dict[str, Any]:
        """Сбор контекста метаданных"""
        
        try:
            object_type = getattr(request, 'object_type', 'unknown')
            existing_objects = await self.get_existing_objects(object_type)
            
            # Анализ существующих объектов того же типа
            similar_objects = existing_objects
            
            # Рекомендации на основе существующих объектов
            recommendations = []
            
            if similar_objects:
                recommendations.append(f"Найдено {len(similar_objects)} существующих объектов типа '{object_type}'")
                
                # Анализ именований
                existing_names = [obj['name'] for obj in similar_objects]
                recommendations.append(f"Используйте уникальное имя, отличное от: {', '.join(existing_names[:5])}")
                
                # Предложения по структуре
                if object_type == 'Обработка':
                    recommendations.append("Рекомендуется использовать стандартную структуру: ПрограммныйИнтерфейс, СлужебныеПроцедурыИФункции")
                elif object_type == 'Справочник':
                    recommendations.append("Не забудьте добавить реквизиты: Код, Наименование")
            
            return {
                'metadata': {
                    'similar_objects': similar_objects,
                    'recommendations': recommendations,
                    'analysis_date': datetime.now().isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Ошибка сбора контекста метаданных: {e}")
            return {'metadata_error': str(e)}
    
    async def _collect_performance_context(self, request) -> Dict[str, Any]:
        """Сбор контекста производительности"""
        
        try:
            object_type = getattr(request, 'object_type', 'unknown')
            code_style = getattr(request, 'code_style', 'standard')
            
            performance_hints = []
            
            # Общие подсказки по производительности
            performance_hints.extend([
                "Избегайте использования Выполнить() для повышения производительности",
                "Используйте параметризованные запросы",
                "Минимизируйте количество запросов к базе данных",
                "Кэшируйте часто используемые данные"
            ])
            
            # Специфичные подсказки для типов объектов
            if object_type == 'Обработка':
                performance_hints.extend([
                    "Для больших объемов данных используйте фоновое выполнение",
                    "Добавляйте прогресс-бар для индикации выполнения"
                ])
            elif object_type == 'Отчет':
                performance_hints.extend([
                    "Оптимизируйте запросы для больших периодов",
                    "Используйте индексацию в запросах",
                    "Рассмотрите возможность кэширования результатов"
                ])
            elif object_type == 'Документ':
                performance_hints.extend([
                    "Проводите документы порционно",
                    "Используйте блокировки для предотвращения конфликтов"
                ])
            
            # Подсказки на основе стиля кода
            if code_style == 'compact':
                performance_hints.append("Компактный стиль может ухудшить читаемость, но улучшить производительность")
            elif code_style == 'detailed':
                performance_hints.append("Подробный стиль может повлиять на производительность из-за дополнительных проверок")
            
            return {
                'performance': {
                    'hints': performance_hints,
                    'optimization_level': 'standard',
                    'scalability_notes': [
                        "Код должен эффективно работать с большими объемами данных",
                        "Предусмотрите возможность масштабирования"
                    ]
                }
            }
            
        except Exception as e:
            logger.error(f"Ошибка сбора контекста производительности: {e}")
            return {'performance_error': str(e)}
    
    async def _collect_standards_context(self, object_type: str) -> Dict[str, Any]:
        """Сбор контекста стандартов и лучших практик"""
        
        try:
            # Стандарты для различных типов объектов
            standards_by_type = {
                'Обработка': {
                    'required_sections': ['ПрограммныйИнтерфейс', 'СлужебныеПроцедурыИФункции'],
                    'naming_conventions': [
                        "Процедуры должны начинаться с глагола",
                        "Используйте camelCase для переменных",
                        "Имена функций должны отражать возвращаемое значение"
                    ],
                    'structure_requirements': [
                        "Обязательные области кода",
                        "Комментирование основных процедур",
                        "Обработка ошибок"
                    ]
                },
                'Отчет': {
                    'required_sections': ['ПрограммныйИнтерфейс'],
                    'naming_conventions': [
                        "Имя отчета должно отражать его назначение",
                        "Используйте префиксы для группировки отчетов"
                    ],
                    'structure_requirements': [
                        "Схема компоновки данных",
                        "Настройки отчета",
                        "Параметры для пользовательской настройки"
                    ]
                },
                'Справочник': {
                    'required_sections': ['ПрограммныйИнтерфейс'],
                    'naming_conventions': [
                        "Имена справочников в единственном числе",
                        "Реквизиты: Код, Наименование"
                    ],
                    'structure_requirements': [
                        "Обработчики событий: ПриЗаписи, ПриКопировании",
                        "Формы: Основная форма, Форма элемента"
                    ]
                },
                'Документ': {
                    'required_sections': ['ПрограммныйИнтерфейс'],
                    'naming_conventions': [
                        "Имена документов отражают операцию",
                        "Используйте стандартные реквизиты"
                    ],
                    'structure_requirements': [
                        "ОбработкаПроведения",
                        "ОбработкаОтменыПроведения",
                        "Формы: Основная форма, Форма документа"
                    ]
                }
            }
            
            type_standards = standards_by_type.get(object_type, {})
            
            return {
                'standards': {
                    'object_type': object_type,
                    'conventions': type_standards.get('naming_conventions', []),
                    'structure': type_standards.get('structure_requirements', []),
                    'required_sections': type_standards.get('required_sections', []),
                    'general_best_practices': [
                        "Следуйте стандартам разработки 1С",
                        "Документируйте сложную логику",
                        "Используйте понятные имена переменных и процедур",
                        "Обрабатывайте исключения",
                        "Избегайте глобальных переменных"
                    ]
                }
            }
            
        except Exception as e:
            logger.error(f"Ошибка сбора контекста стандартов: {e}")
            return {'standards_error': str(e)}
    
    def _initialize_context_sources(self) -> List[str]:
        """Инициализация источников контекста"""
        
        return [
            'request_parameters',
            'platform_info',
            'configuration_metadata',
            'existing_objects',
            'performance_hints',
            'coding_standards',
            'security_guidelines'
        ]
    
    def _generate_cache_key(self, request) -> str:
        """Генерация ключа кэша"""
        
        import hashlib
        
        cache_data = {
            'object_type': getattr(request, 'object_type', ''),
            'code_style': getattr(request, 'code_style', ''),
            'include_comments': getattr(request, 'include_comments', False),
            'use_standards': getattr(request, 'use_standards', False)
        }
        
        cache_string = json.dumps(cache_data, sort_keys=True)
        return hashlib.md5(cache_string.encode('utf-8')).hexdigest()
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Проверка валидности кэша"""
        
        if cache_key not in self.cache_timestamps:
            return False
        
        cache_age = datetime.now() - self.cache_timestamps[cache_key]
        return cache_age.total_seconds() < self.cache_ttl
    
    def clear_cache(self):
        """Очистка кэша контекста"""
        
        self.context_cache.clear()
        self.cache_timestamps.clear()
        logger.info("Кэш контекста очищен")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Получение статистики кэша"""
        
        return {
            'cache_enabled': self.cache_enabled,
            'cache_ttl': self.cache_ttl,
            'cached_entries': len(self.context_cache),
            'cache_sources': self.context_sources
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Получение статуса коллектора"""
        
        return {
            'enabled': self.enabled,
            'cache_stats': self.get_cache_stats(),
            'sources': self.context_sources,
            'version': '1.0'
        }