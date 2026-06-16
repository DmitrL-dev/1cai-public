
#!/usr/bin/env python3
"""
LLM Client для 1C AI MCP Code Generation

Клиент для интеграции с различными LLM провайдерами (OpenAI, Anthropic, Mock).

Версия: 1.0
Дата: 30.10.2025
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

@dataclass
class LLMRequest:
    """Запрос к LLM"""
    prompt: str
    model: str = "gpt-4"
    temperature: float = 0.3
    max_tokens: int = 4000
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0

@dataclass
class LLMResponse:
    """Ответ от LLM"""
    success: bool
    content: str
    model: str
    tokens_used: int
    finish_reason: str
    error_message: Optional[str] = None

class LLMClient:
    """Клиент для работы с LLM провайдерами"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Инициализация LLM клиента
        
        Args:
            config: Конфигурация клиента
        """
        self.config = config
        
        # Настройки
        self.provider = config.get('provider', 'mock')
        self.model = config.get('model', 'gpt-4')
        self.temperature = config.get('temperature', 0.3)
        self.max_tokens = config.get('max_tokens', 4000)
        self.timeout = config.get('timeout', 30)
        
        # API ключи (должны храниться безопасно)
        self.api_keys = config.get('api_keys', {})
        
        # Статистика
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'total_tokens_used': 0,
            'average_response_time': 0.0
        }
        
        # Инициализация провайдеров
        self._initialize_providers()
        
        logger.info(f"LLMClient инициализирован с провайдером: {self.provider}")
    
    async def generate_code(self, prompt: str, **kwargs) -> Optional[str]:
        """
        Генерация кода через LLM
        
        Args:
            prompt: Промпт для генерации
            **kwargs: Дополнительные параметры
            
        Returns:
            Сгенерированный код или None при ошибке
        """
        start_time = time.time()
        self.stats['total_requests'] += 1
        
        try:
            # Создание запроса
            request = LLMRequest(
                prompt=prompt,
                model=kwargs.get('model', self.model),
                temperature=kwargs.get('temperature', self.temperature),
                max_tokens=kwargs.get('max_tokens', self.max_tokens)
            )
            
            # Отправка запроса
            response = await self._send_request(request)
            
            if response.success:
                self.stats['successful_requests'] += 1
                self.stats['total_tokens_used'] += response.tokens_used
                
                # Обновление среднего времени ответа
                response_time = time.time() - start_time
                total_requests = self.stats['total_requests']
                current_avg = self.stats['average_response_time']
                self.stats['average_response_time'] = (
                    (current_avg * (total_requests - 1) + response_time) / total_requests
                )
                
                logger.info(f"LLM запрос выполнен успешно: {response.tokens_used} токенов")
                return response.content
            else:
                self.stats['failed_requests'] += 1
                logger.error(f"LLM запрос не удался: {response.error_message}")
                return None
                
        except Exception as e:
            self.stats['failed_requests'] += 1
            logger.error(f"Исключение при выполнении LLM запроса: {e}")
            return None
    
    async def generate_code_with_fallback(self, prompt: str, 
                                        primary_provider: str = None,
                                        fallback_providers: List[str] = None) -> Optional[str]:
        """
        Генерация кода с fallback провайдерами
        
        Args:
            prompt: Промпт для генерации
            primary_provider: Основной провайдер
            fallback_providers: Список провайдеров для fallback
            
        Returns:
            Сгенерированный код или None при ошибке
        """
        providers_to_try = []
        
        if primary_provider:
            providers_to_try.append(primary_provider)
        else:
            providers_to_try.append(self.provider)
        
        if fallback_providers:
            providers_to_try.extend(fallback_providers)
        else:
            # Стандартные fallback провайдеры
            providers_to_try.extend(['mock', 'openai', 'anthropic'])
        
        # Удаление дубликатов, сохраняя порядок
        providers_to_try = list(dict.fromkeys(providers_to_try))
        
        for provider in providers_to_try:
            try:
                logger.info(f"Попытка генерации через провайдера: {provider}")
                
                # Временная смена провайдера
                original_provider = self.provider
                self.provider = provider
                
                result = await self.generate_code(prompt)
                
                # Восстановление оригинального провайдера
                self.provider = original_provider
                
                if result:
                    logger.info(f"Генерация успешна через провайдера: {provider}")
                    return result
                else:
                    logger.warning(f"Провайдер {provider} не смог сгенерировать код")
                    continue
                    
            except Exception as e:
                logger.error(f"Ошибка провайдера {provider}: {e}")
                # Продолжаем с следующим провайдером
                continue
        
        logger.error("Все провайдеры не смогли сгенерировать код")
        return None
    
    async def _send_request(self, request: LLMRequest) -> LLMResponse:
        """
        Отправка запроса к выбранному провайдеру
        
        Args:
            request: Запрос к LLM
            
        Returns:
            Ответ от LLM
        """
        if self.provider == 'mock':
            return await self._mock_provider(request)
        elif self.provider == 'openai':
            return await self._openai_provider(request)
        elif self.provider == 'anthropic':
            return await self._anthropic_provider(request)
        else:
            return LLMResponse(
                success=False,
                content="",
                model=request.model,
                tokens_used=0,
                finish_reason="unknown_provider",
                error_message=f"Неподдерживаемый провайдер: {self.provider}"
            )
    
    async def _mock_provider(self, request: LLMRequest) -> LLMResponse:
        """
        Mock провайдер для демонстрации и тестирования
        """
        try:
            # Имитация задержки сети
            await asyncio.sleep(0.5)
            
            # Генерация mock ответа на основе промпта
            mock_response = self._generate_mock_response(request.prompt)
            
            return LLMResponse(
                success=True,
                content=mock_response,
                model=request.model,
                tokens_used=len(mock_response.split()) * 1.3,  # Приблизительный подсчет
                finish_reason="stop"
            )
            
        except Exception as e:
            return LLMResponse(
                success=False,
                content="",
                model=request.model,
                tokens_used=0,
                finish_reason="error",
                error_message=str(e)
            )
    
    def _generate_mock_response(self, prompt: str) -> str:
        """
        Генерация mock ответа на основе промпта
        """
        # Анализ промпта для определения типа генерируемого кода
        prompt_lower = prompt.lower()
        
        if 'обработка' in prompt_lower or 'processing' in prompt_lower:
            return self._generate_mock_processing_code(prompt)
        elif 'отчет' in prompt_lower or 'report' in prompt_lower:
            return self._generate_mock_report_code(prompt)
        elif 'справочник' in prompt_lower or 'catalog' in prompt_lower:
            return self._generate_mock_catalog_code(prompt)
        elif 'документ' in prompt_lower or 'document' in prompt_lower:
            return self._generate_mock_document_code(prompt)
        else:
            return self._generate_mock_general_code(prompt)
    
    def _generate_mock_processing_code(self, prompt: str) -> str:
        """Генерация mock кода обработки"""
        return '''{
  "manager_module": "// =====================================\n// Модуль менеджера обработки\n// Сгенерирован автоматически\n// =====================================\n\n#Область ПрограммныйИнтерфейс\n\n// Основная процедура обработки данных\nПроцедура ОбработатьДанные(ПараметрыОбработки) Экспорт\n    // Логика обработки данных\n    // Здесь должен быть код в соответствии с требованиями\nКонецПроцедуры\n\n// Получение результата обработки\nФункция ПолучитьРезультат() Экспорт\n    // Возврат результата обработки\nКонецФункции\n\n#КонецОбласти\n\n#Область СлужебныеПроцедурыИФункции\n\n// Служебные процедуры и функции\nПроцедура ВнутренняяОбработка()\n    // Внутренняя логика\nКонецПроцедуры\n\n#КонецОбласти''",
  "object_module": "// =====================================\n// Модуль объекта обработки\n// Сгенерирован автоматически\n// =====================================\n\n#Область ПрограммныйИнтерфейс\n\n// Запуск обработки\nПроцедура ВыполнитьОбработку() Экспорт\n    // Основная логика обработки\nКонецПроцедуры\n\n#КонецОбласти''",
  "form": "&НаКлиенте\nПроцедура Обработать(Команда)\n    // Обработка команды пользователя\nКонецПроцедуры",
  "macros": ["ОсновнаяФорма", "Результат"]
}'''
    
    def _generate_mock_report_code(self, prompt: str) -> str:
        """Генерация mock кода отчета"""
        return '''{
  "manager_module": "// Модуль менеджера отчета\n#Область ПрограммныйИнтерфейс\nФункция ПолучитьСхему() Экспорт\n    // Возврат схемы СКД\nКонецФункции\n#КонецОбласти",
  "object_module": "// Модуль объекта отчета\n#Область ПрограммныйИнтерфейс\nПроцедура СоздатьОтчет() Экспорт\n    // Настройка параметров отчета\nКонецПроцедуры\n#КонецОбласти",
  "form": "&НаКлиенте\nПроцедура Сформировать(Команда)\n    // Формирование отчета\nКонецПроцедуры",
  "macros": ["Схема", "Настройки", "Результат"]
}'''
    
    def _generate_mock_catalog_code(self, prompt: str) -> str:
        """Генерация mock кода справочника"""
        return '''{
  "manager_module": "// Модуль менеджера справочника\n#Область ПрограммныйИнтерфейс\nФункция СоздатьЭлемент(Параметры) Экспорт\n    // Логика создания элемента\nКонецФункции\n#КонецОбласти",
  "object_module": "// Модуль объекта справочника\n#Область ПрограммныйИнтерфейс\nПроцедура ПриЗаписи(Отказ)\n    // Логика при записи\nКонецПроцедуры\n#КонецОбласти",
  "form": "&НаКлиенте\nПроцедура Записать(Команда)\n    // Запись элемента справочника\nКонецПроцедуры",
  "macros": ["ОсновнаяФорма", "ФормаЭлемента"]
}'''
    
    def _generate_mock_document_code(self, prompt: str) -> str:
        """Генерация mock кода документа"""
        return '''{
  "manager_module": "// Модуль менеджера документа\n#Область ПрограммныйИнтерфейс\nФункция СоздатьДокумент(Параметры) Экспорт\n    // Логика создания документа\nКонецФункции\n#КонецОбласти",
  "object_module": "// Модуль объекта документа\n#Область ПрограммныйИнтерфейс\nПроцедура ОбработкаПроведения(Отказ, Режим)\n    // Логика проведения документа\nКонецПроцедуры\n#КонецОбласти",
  "form": "&НаКлиенте\nПроцедура Провести(Команда)\n    // Проведение документа\nКонецПроцедуры",
  "macros": ["ОсновнаяФорма", "ФормаДокумента"]
}'''
    
    def _generate_mock_general_code(self, prompt: str) -> str:
        """Генерация mock общего кода"""
        return '''{
  "manager_module": "// Общий модуль\n#Область ПрограммныйИнтерфейс\nФункция ВыполнитьОперацию(Параметры) Экспорт\n    // Логика операции\nКонецФункции\n#КонецОбласти",
  "object_module": "",
  "form": "",
  "macros": []
}'''
    
    async def _openai_provider(self, request: LLMRequest) -> LLMResponse:
        """Провайдер OpenAI (заглушка)"""
        # В реальной реализации здесь был бы код для работы с OpenAI API
        # Для демонстрации возвращаем mock ответ
        
        logger.info("Используется заглушка OpenAI провайдера")
        return await self._mock_provider(request)
    
    async def _anthropic_provider(self, request: LLMRequest) -> LLMResponse:
        """Провайдер Anthropic (заглушка)"""
        # В реальной реализации здесь был бы код для работы с Anthropic API
        # Для демонстрации возвращаем mock ответ
        
        logger.info("Используется заглушка Anthropic провайдера")
        return await self._mock_provider(request)
    
    def _initialize_providers(self):
        """Инициализация провайдеров"""
        # В реальной реализации здесь была бы инициализация различных провайдеров
        # с проверкой доступности API ключей и т.д.
        
        if self.provider not in ['mock', 'openai', 'anthropic']:
            logger.warning(f"Неподдерживаемый провайдер: {self.provider}, использую mock")
            self.provider = 'mock'
    
    def get_status(self) -> Dict[str, Any]:
        """Получение статуса клиента"""
        return {
            'provider': self.provider,
            'model': self.model,
            'statistics': self.stats.copy(),
            'available_providers': ['mock', 'openai', 'anthropic'],
            'version': '1.0'
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Получение подробной статистики"""
        stats = self.stats.copy()
        
        # Вычисление дополнительных метрик
        if stats['total_requests'] > 0:
            stats['success_rate'] = stats['successful_requests'] / stats['total_requests']
            stats['failure_rate'] = stats['failed_requests'] / stats['total_requests']
            stats['average_tokens_per_request'] = stats['total_tokens_used'] / stats['total_requests']
        else:
            stats['success_rate'] = 0.0
            stats['failure_rate'] = 0.0
            stats['average_tokens_per_request'] = 0.0
        
        return stats
    
    def switch_provider(self, provider: str, **kwargs):
        """
        Смена провайдера
        
        Args:
            provider: Новый провайдер
            **kwargs: Дополнительные настройки
        """
        if provider not in ['mock', 'openai', 'anthropic']:
            raise ValueError(f"Неподдерживаемый провайдер: {provider}")
        
        self.provider = provider
        
        # Обновление настроек если указаны
        if 'model' in kwargs:
            self.model = kwargs['model']
        if 'temperature' in kwargs:
            self.temperature = kwargs['temperature']
        if 'timeout' in kwargs:
            self.timeout = kwargs['timeout']
        
        logger.info(f"Провайдер изменен на: {provider}")
    
    def validate_api_key(self, provider: str, api_key: str) -> bool:
        """
        Валидация API ключа провайдера
        
        Args:
            provider: Провайдер
            api_key: API ключ
            
        Returns:
            True если ключ валиден
        """
        # Упрощенная валидация для демонстрации
        if provider == 'openai':
            return api_key.startswith('sk-') and len(api_key) > 20
        elif provider == 'anthropic':
            return api_key.startswith('sk-ant-') and len(api_key) > 20
        else:
            return True  # Mock провайдер не требует валидации
    
    def reset_statistics(self):
        """Сброс статистики"""
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'total_tokens_used': 0,
            'average_response_time': 0.0
        }
        logger.info("Статистика LLM клиента сброшена")