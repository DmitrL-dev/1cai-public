
#!/usr/bin/env python3
"""
1C AI MCP Code Generation Engine

Версия: 1.0
Дата создания: 30.10.2025

Основной движок генерации кода для 1C AI MCP системы.
Обеспечивает генерацию кода 1С с использованием LLM и шаблонов.
"""

import json
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

# Импорт внутренних модулей
from .llm.client import LLMClient
from .security.manager import SecurityManager
from .templates.manager import TemplateManager
from .utils.audit import AuditLogger
from .utils.context import ContextCollector
from .validation.validator import CodeValidator

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CodeGenerationStatus(Enum):
    """Статус генерации кода"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    VALIDATION_FAILED = "validation_failed"
    SECURITY_REJECTED = "security_rejected"

@dataclass
class CodeGenerationRequest:
    """Запрос на генерацию кода"""
    prompt: str
    object_type: str = "processing"
    code_style: str = "standard"
    include_comments: bool = True
    use_standards: bool = True
    context: Dict[str, Any] = None
    request_id: str = ""
    user_id: str = ""
    
    def __post_init__(self):
        if not self.request_id:
            self.request_id = f"gen_{int(time.time())}_{hash(self.prompt) % 10000}"
        if self.context is None:
            self.context = {}

@dataclass
class CodeGenerationResult:
    """Результат генерации кода"""
    success: bool
    status: CodeGenerationStatus
    generated_code: Dict[str, str]
    metadata: Dict[str, Any]
    recommendations: List[str]
    warnings: List[str]
    errors: List[str]
    request_id: str
    execution_time: float
    validation_score: Optional[int] = None
    security_status: str = "pending"

class CodeGenerationEngine:
    """Основной движок генерации кода 1С"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Инициализация движка генерации кода
        
        Args:
            config: Конфигурация движка
        """
        self.config = config
        
        # Инициализация компонентов
        self.llm_client = LLMClient(config.get('llm', {}))
        self.template_manager = TemplateManager(config.get('templates', {}))
        self.code_validator = CodeValidator(config.get('validation', {}))
        self.security_manager = SecurityManager(config.get('security', {}))
        self.audit_logger = AuditLogger(config.get('audit', {}))
        self.context_collector = ContextCollector(config.get('context', {}))
        
        # Статистика
        self.stats = {
            'total_requests': 0,
            'successful_generations': 0,
            'validation_failures': 0,
            'security_rejections': 0,
            'average_execution_time': 0.0
        }
        
        logger.info("CodeGenerationEngine инициализирован")
    
    async def generate_code(self, request: CodeGenerationRequest) -> CodeGenerationResult:
        """
        Основная функция генерации кода
        
        Args:
            request: Запрос на генерацию кода
            
        Returns:
            CodeGenerationResult: Результат генерации
        """
        start_time = time.time()
        self.stats['total_requests'] += 1
        
        # Создание результата по умолчанию
        result = CodeGenerationResult(
            success=False,
            status=CodeGenerationStatus.PENDING,
            generated_code={},
            metadata={},
            recommendations=[],
            warnings=[],
            errors=[],
            request_id=request.request_id,
            execution_time=0.0
        )
        
        try:
            # Логирование начала операции
            await self.audit_logger.log_generation_start(request)
            
            # Обновление статуса
            result.status = CodeGenerationStatus.IN_PROGRESS
            
            # 1. Валидация входных данных
            validation_result = self._validate_input(request)
            if not validation_result['valid']:
                result.errors.extend(validation_result['errors'])
                result.status = CodeGenerationStatus.FAILED
                return result
            
            # 2. Сбор контекста из 1С
            context = await self._collect_context(request)
            
            # 3. Выбор оптимального шаблона
            template = await self.template_manager.get_template(request.object_type, request.prompt)
            
            # 4. Формирование промпта для LLM
            prompt = await self._build_llm_prompt(request, template, context)
            
            # 5. Генерация кода через LLM
            generated_code = await self._generate_code_via_llm(prompt, template)
            
            if not generated_code:
                result.errors.append("LLM не вернул код")
                result.status = CodeGenerationStatus.FAILED
                return result
            
            # 6. Валидация сгенерированного кода
            validation_result = await self.code_validator.validate_code(
                generated_code, context
            )
            
            if not validation_result['valid']:
                result.errors.extend(validation_result['errors'])
                result.warnings.extend(validation_result['warnings'])
                result.status = CodeGenerationStatus.VALIDATION_FAILED
                self.stats['validation_failures'] += 1
                return result
            
            # 7. Проверка безопасности
            security_result = await self.security_manager.analyze_security(
                generated_code, request
            )
            
            if security_result['risk_level'] == 'critical':
                result.errors.append(f"Код отклонен по соображениям безопасности: {security_result['description']}")
                result.status = CodeGenerationStatus.SECURITY_REJECTED
                self.stats['security_rejections'] += 1
                return result
            
            # 8. Пост-обработка кода
            processed_code = await self._post_process_code(generated_code, template)
            
            # 9. Формирование результата
            result.success = True
            result.status = CodeGenerationStatus.COMPLETED
            result.generated_code = processed_code
            result.metadata = {
                'generation_time': time.time() - start_time,
                'template_used': template['id'] if template else 'none',
                'context_size': len(context),
                'validation_score': validation_result.get('score', 0),
                'security_risk': security_result['risk_level']
            }
            result.validation_score = validation_result.get('score')
            result.security_status = security_result['risk_level']
            
            # 10. Генерация рекомендаций
            result.recommendations = self._generate_recommendations(
                validation_result, security_result, processed_code
            )
            
            self.stats['successful_generations'] += 1
            
            # Логирование успешного завершения
            await self.audit_logger.log_generation_success(request, result)
            
        except Exception as e:
            # Обработка исключений
            result.errors.append(f"Критическая ошибка генерации: {str(e)}")
            result.status = CodeGenerationStatus.FAILED
            logger.error(f"Ошибка генерации кода для запроса {request.request_id}: {e}")
            
            await self.audit_logger.log_generation_error(request, str(e))
        
        finally:
            # Обновление статистики времени выполнения
            execution_time = time.time() - start_time
            result.execution_time = execution_time
            
            # Обновление среднего времени выполнения
            self.stats['average_execution_time'] = (
                (self.stats['average_execution_time'] * (self.stats['total_requests'] - 1) + execution_time) 
                / self.stats['total_requests']
            )
        
        return result
    
    async def validate_code(self, code: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Валидация существующего кода
        
        Args:
            code: Код для валидации
            context: Контекст валидации
            
        Returns:
            Результат валидации
        """
        return await self.code_validator.validate_code(code, context or {})
    
    async def optimize_code(self, code: str, optimization_goal: str = "performance") -> Dict[str, Any]:
        """
        Оптимизация кода
        
        Args:
            code: Код для оптимизации
            optimization_goal: Цель оптимизации
            
        Returns:
            Результат оптимизации
        """
        # Валидация входного кода
        validation_result = await self.code_validator.validate_code(code)
        
        if not validation_result['valid']:
            return {
                'success': False,
                'error': 'Код не прошел валидацию',
                'validation_errors': validation_result['errors']
            }
        
        # Генерация оптимизированного кода
        optimization_prompt = self._build_optimization_prompt(code, optimization_goal)
        
        try:
            optimized_code = await self.llm_client.generate_code(optimization_prompt)
            
            # Валидация оптимизированного кода
            optimized_validation = await self.code_validator.validate_code(optimized_code)
            
            return {
                'success': True,
                'original_code': code,
                'optimized_code': optimized_code,
                'optimization_improvements': self._compare_code_quality(code, optimized_code),
                'validation_result': optimized_validation
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Ошибка оптимизации: {str(e)}'
            }
    
    async def get_statistics(self) -> Dict[str, Any]:
        """
        Получение статистики работы движка
        
        Returns:
            Словарь со статистикой
        """
        stats = self.stats.copy()
        
        # Вычисление дополнительных метрик
        if stats['total_requests'] > 0:
            stats['success_rate'] = stats['successful_generations'] / stats['total_requests']
            stats['validation_failure_rate'] = stats['validation_failures'] / stats['total_requests']
            stats['security_rejection_rate'] = stats['security_rejections'] / stats['total_requests']
        else:
            stats['success_rate'] = 0.0
            stats['validation_failure_rate'] = 0.0
            stats['security_rejection_rate'] = 0.0
        
        # Добавление информации о компонентах
        stats['components'] = {
            'llm_client': self.llm_client.get_status(),
            'template_manager': self.template_manager.get_status(),
            'code_validator': self.code_validator.get_status(),
            'security_manager': self.security_manager.get_status()
        }
        
        return stats
    
    def _validate_input(self, request: CodeGenerationRequest) -> Dict[str, Any]:
        """Валидация входных данных запроса"""
        errors = []
        
        # Проверка обязательных полей
        if not request.prompt or len(request.prompt.strip()) < 10:
            errors.append("Промпт должен содержать минимум 10 символов")
        
        if len(request.prompt) > 2000:
            errors.append("Промпт слишком длинный (максимум 2000 символов)")
        
        # Проверка типа объекта
        valid_object_types = ["processing", "report", "catalog", "document", "register", "common_module"]
        if request.object_type not in valid_object_types:
            errors.append(f"Неподдерживаемый тип объекта: {request.object_type}")
        
        # Проверка стиля кода
        valid_styles = ["standard", "compact", "detailed", "functional"]
        if request.code_style not in valid_styles:
            errors.append(f"Неподдерживаемый стиль кода: {request.code_style}")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }
    
    async def _collect_context(self, request: CodeGenerationRequest) -> Dict[str, Any]:
        """Сбор контекста для генерации"""
        try:
            context = await self.context_collector.collect_context(request)
            return context
        except Exception as e:
            logger.warning(f"Ошибка сбора контекста: {e}")
            return {}
    
    async def _build_llm_prompt(self, request: CodeGenerationRequest, template: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Построение промпта для LLM"""
        
        # Базовая структура промпта
        prompt_parts = [
            "You are an expert 1C developer assistant.",
            f"Generate 1C code based on the following requirements:",
            f"Description: {request.prompt}",
            f"Object type: {request.object_type}",
            f"Code style: {request.code_style}"
        ]
        
        # Добавление информации о контексте
        if context:
            prompt_parts.append(f"Current configuration context: {json.dumps(context, ensure_ascii=False)}")
        
        # Добавление требований к стилю
        if request.use_standards:
            prompt_parts.append("Follow 1C development standards and best practices")
        
        if request.include_comments:
            prompt_parts.append("Include detailed comments in Russian")
        
        # Добавление информации о шаблоне
        if template:
            prompt_parts.append(f"Use template: {template['name']}")
            if template.get('description'):
                prompt_parts.append(f"Template description: {template['description']}")
        
        # Требования к формату вывода
        prompt_parts.extend([
            "",
            "Return code in the following JSON format:",
            "{",
            '  "manager_module": "// Manager module code",',
            '  "object_module": "// Object module code",',
            '  "form": "// Form code (if applicable)",',
            '  "macros": ["// Macro 1", "// Macro 2"]',
            "}"
        ])
        
        return "\n".join(prompt_parts)
    
    async def _generate_code_via_llm(self, prompt: str, template: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """Генерация кода через LLM"""
        try:
            # Генерация кода
            llm_response = await self.llm_client.generate_code(prompt)
            
            if not llm_response:
                return None
            
            # Парсинг ответа LLM
            try:
                # Попытка парсинга как JSON
                if llm_response.strip().startswith('{'):
                    code_data = json.loads(llm_response)
                else:
                    # Парсинг как обычного текста с разделителями
                    code_data = self._parse_plain_text_response(llm_response)
                
                # Валидация структуры ответа
                required_keys = ['manager_module', 'object_module']
                if not all(key in code_data for key in required_keys):
                    logger.warning("LLM ответ не содержит всех необходимых частей кода")
                    return None
                
                return code_data
                
            except json.JSONDecodeError as e:
                logger.error(f"Ошибка парсинга JSON ответа LLM: {e}")
                # Попытка восстановления
                return self._attempt_response_recovery(llm_response)
        
        except Exception as e:
            logger.error(f"Ошибка генерации через LLM: {e}")
            return None
    
    def _parse_plain_text_response(self, response: str) -> Dict[str, str]:
        """Парсинг ответа LLM в текстовом формате"""
        result = {
            'manager_module': '',
            'object_module': '',
            'form': '',
            'macros': []
        }
        
        lines = response.split('\n')
        current_section = None
        
        for line in lines:
            line = line.strip()
            
            # Определение секции по маркерам
            if 'модуль менеджера' in line.lower() or 'manager' in line.lower():
                current_section = 'manager_module'
            elif 'модуль объекта' in line.lower() or 'object' in line.lower():
                current_section = 'object_module'
            elif 'форма' in line.lower() or 'form' in line.lower():
                current_section = 'form'
            elif 'макет' in line.lower() or 'macro' in line.lower():
                current_section = 'macros'
            elif line.startswith('//') and current_section:
                # Добавление комментария к соответствующей секции
                if current_section == 'macros':
                    result[current_section].append(line)
                else:
                    result[current_section] += line + '\n'
        
        return result
    
    def _attempt_response_recovery(self, response: str) -> Optional[Dict[str, str]]:
        """Попытка восстановления поврежденного ответа LLM"""
        
        # Простое восстановление - разделение на базовые секции
        try:
            # Поиск ключевых слов в тексте
            sections = {
                'manager_module': '',
                'object_module': '',
                'form': '',
                'macros': []
            }
            
            # Поиск кода процедур и функций
            if 'Процедура' in response or 'Функция' in response:
                sections['object_module'] = response
            
            # Если ничего не найдено, возвращаем весь текст как модуль объекта
            if not sections['object_module']:
                sections['object_module'] = response
            
            return sections
            
        except Exception as e:
            logger.error(f"Ошибка восстановления ответа: {e}")
            return None
    
    async def _post_process_code(self, code: Dict[str, str], template: Dict[str, Any]) -> Dict[str, str]:
        """Пост-обработка сгенерированного кода"""
        
        processed_code = {}
        
        for section, code_content in code.items():
            if code_content:
                # Очистка кода
                cleaned_code = self._clean_code(code_content)
                
                # Форматирование кода
                formatted_code = self._format_code(cleaned_code, section)
                
                # Применение шаблонных элементов
                if template:
                    formatted_code = self._apply_template_elements(formatted_code, template, section)
                
                processed_code[section] = formatted_code
        
        return processed_code
    
    def _clean_code(self, code: str) -> str:
        """Очистка кода от лишних символов"""
        
        # Удаление лишних пробелов и переводов строк
        lines = code.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # Удаление trailing пробелов
            cleaned_line = line.rstrip()
            
            # Пропуск пустых строк в начале и конце
            if cleaned_line or cleaned_lines:
                cleaned_lines.append(cleaned_line)
        
        return '\n'.join(cleaned_lines)
    
    def _format_code(self, code: str, section_type: str) -> str:
        """Форматирование кода согласно стандартам"""
        
        # Базовое форматирование
        formatted_code = code
        
        # Добавление заголовка для модулей
        if section_type in ['manager_module', 'object_module']:
            header = f"// =====================================\n"
            header += f"// {section_type.replace('_', ' ').title()}\n"
            header += f"// Сгенерировано автоматически\n"
            header += f"// Дата: {time.strftime('%d.%m.%Y %H:%M')}\n"
            header += f"// =====================================\n\n"
            
            formatted_code = header + formatted_code
        
        return formatted_code
    
    def _apply_template_elements(self, code: str, template: Dict[str, Any], section_type: str) -> str:
        """Применение элементов шаблона"""
        
        # Если у шаблона есть специфические элементы для секции
        template_elements = template.get('elements', {})
        
        if section_type in template_elements:
            element_template = template_elements[section_type]
            
            # Простая замена плейсхолдеров
            for placeholder, value in element_template.items():
                if placeholder in code:
                    code = code.replace(f"{{{placeholder}}}", value)
        
        return code
    
    def _generate_recommendations(self, validation_result: Dict[str, Any], security_result: Dict[str, Any], code: Dict[str, str]) -> List[str]:
        """Генерация рекомендаций"""
        
        recommendations = []
        
        # Рекомендации на основе валидации
        if validation_result.get('score', 0) < 80:
            recommendations.append("Рекомендуется улучшить качество кода согласно стандартам 1С")
        
        # Рекомендации на основе безопасности
        if security_result['risk_level'] == 'medium':
            recommendations.append("Код требует дополнительной проверки безопасности")
        
        # Общие рекомендации
        recommendations.extend([
            "Протестировать сгенерированный код в тестовой среде",
            "Добавить unit-тесты для критических функций",
            "Провести код-ревью с опытным разработчиком",
            "Документировать сложные алгоритмы"
        ])
        
        return recommendations
    
    def _build_optimization_prompt(self, code: str, optimization_goal: str) -> str:
        """Построение промпта для оптимизации кода"""
        
        prompt = f"""Optimize the following 1C code for {optimization_goal}:

```{code}```

Please provide the optimized version maintaining the same functionality but improving:
- Code readability and maintainability
- Performance optimization
- Following 1C best practices
- Proper error handling
- Security considerations

Return the optimized code in the same structure format."""
        
        return prompt
    
    def _compare_code_quality(self, original: str, optimized: str) -> Dict[str, Any]:
        """Сравнение качества оригинального и оптимизированного кода"""
        
        # Простые метрики сравнения
        return {
            'original_lines': len(original.split('\n')),
            'optimized_lines': len(optimized.split('\n')),
            'improvement_percentage': ((len(original) - len(optimized)) / len(original)) * 100 if original else 0,
            'readability_improvement': 'estimated',  # В реальной системе - сложный анализ
            'performance_improvement': 'estimated'
        }