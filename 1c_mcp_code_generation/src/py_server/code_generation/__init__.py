
#!/usr/bin/env python3
"""
1C AI MCP Code Generation Package

Главный модуль пакета для генерации кода 1С через MCP протокол.
Обеспечивает интеграцию с существующей системой 1C AI MCP.

Версия: 1.0
Дата: 30.10.2025
"""

from .engine import (CodeGenerationEngine, CodeGenerationRequest,
                     CodeGenerationResult, CodeGenerationStatus)

__version__ = "1.0.0"
__author__ = "MiniMax Agent"
__description__ = "1C AI MCP Code Generation System"

# Экспорт основных классов
__all__ = [
    'CodeGenerationEngine',
    'CodeGenerationRequest', 
    'CodeGenerationResult',
    'CodeGenerationStatus'
]

def create_engine(config: dict):
    """
    Фабричная функция для создания движка генерации кода
    
    Args:
        config: Конфигурация движка
        
    Returns:
        CodeGenerationEngine: Инициализированный движок
    """
    return CodeGenerationEngine(config)

def get_version():
    """Получение версии пакета"""
    return __version__

# Проверка совместимости версий
def check_compatibility():
    """Проверка совместимости компонентов системы"""
    
    compatibility_checks = {
        'python_version': '3.8+',
        'required_packages': [
            'asyncio',
            'json', 
            'logging',
            'typing',
            'dataclasses',
            'enum',
            'time'
        ]
    }
    
    try:
        import sys
        if sys.version_info < (3, 8):
            raise RuntimeError(f"Требуется Python 3.8+, текущая версия: {sys.version}")
        
        # Проверка наличия всех необходимых пакетов
        import importlib.util
        
        for package in compatibility_checks['required_packages']:
            if importlib.util.find_spec(package) is None:
                raise RuntimeError(f"Не найден пакет: {package}")
        
        return {
            'compatible': True,
            'version': __version__,
            'python_version': sys.version,
            'message': 'Система совместима'
        }
        
    except Exception as e:
        return {
            'compatible': False,
            'version': __version__,
            'error': str(e),
            'message': 'Система несовместима'
        }

# Константы системы
SYSTEM_CONSTANTS = {
    'MAX_PROMPT_LENGTH': 2000,
    'MAX_CODE_SIZE': 50000,
    'DEFAULT_TIMEOUT': 30,
    'VALIDATION_TIMEOUT': 10,
    'SECURITY_TIMEOUT': 5,
    'SUPPORTED_OBJECT_TYPES': [
        'processing',
        'report', 
        'catalog',
        'document',
        'register',
        'common_module'
    ],
    'SUPPORTED_CODE_STYLES': [
        'standard',
        'compact',
        'detailed',
        'functional'
    ],
    'VALIDATION_LEVELS': [
        'basic',
        'standard', 
        'full',
        'strict'
    ],
    'SECURITY_RISK_LEVELS': [
        'low',
        'medium',
        'high',
        'critical'
    ]
}

def validate_config(config: dict) -> dict:
    """
    Валидация конфигурации системы
    
    Args:
        config: Конфигурация для проверки
        
    Returns:
        dict: Результат валидации
    """
    errors = []
    warnings = []
    
    # Проверка обязательных секций
    required_sections = ['llm', 'templates', 'validation', 'security']
    for section in required_sections:
        if section not in config:
            errors.append(f"Отсутствует обязательная секция: {section}")
    
    # Проверка LLM конфигурации
    if 'llm' in config:
        llm_config = config['llm']
        if 'provider' not in llm_config:
            errors.append("В секции llm отсутствует параметр provider")
        if 'api_key' not in llm_config and llm_config.get('provider') != 'mock':
            warnings.append("Рекомендуется указать api_key для production использования")
    
    # Проверка валидации
    if 'validation' in config:
        validation_config = config['validation']
        if 'enabled_checks' not in validation_config:
            warnings.append("Рекомендуется явно указать enabled_checks в валидации")
    
    # Проверка безопасности
    if 'security' in config:
        security_config = config['security']
        if 'max_code_size' not in security_config:
            warnings.append(f"Рекомендуется указать max_code_size (по умолчанию: {SYSTEM_CONSTANTS['MAX_CODE_SIZE']})")
    
    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'warnings': warnings,
        'recommended_defaults': {
            'max_prompt_length': SYSTEM_CONSTANTS['MAX_PROMPT_LENGTH'],
            'max_code_size': SYSTEM_CONSTANTS['MAX_CODE_SIZE'],
            'default_timeout': SYSTEM_CONSTANTS['DEFAULT_TIMEOUT']
        }
    }

def get_default_config() -> dict:
    """
    Получение конфигурации по умолчанию
    
    Returns:
        dict: Конфигурация с настройками по умолчанию
    """
    return {
        'llm': {
            'provider': 'mock',  # Для демонстрации, в production использовать 'openai' или 'anthropic'
            'model': 'gpt-4',
            'temperature': 0.3,
            'max_tokens': 4000,
            'timeout': 30
        },
        'templates': {
            'enabled': True,
            'auto_learning': True,
            'cache_enabled': True,
            'cache_ttl': 3600,  # 1 час
            'custom_templates_path': './custom_templates'
        },
        'validation': {
            'enabled': True,
            'timeout': 10,
            'enabled_checks': ['syntax', 'standards', 'security', 'performance'],
            'strict_mode': False,
            'auto_fix': False
        },
        'security': {
            'enabled': True,
            'timeout': 5,
            'max_code_size': SYSTEM_CONSTANTS['MAX_CODE_SIZE'],
            'risk_thresholds': {
                'low': 0.3,
                'medium': 0.6,
                'high': 0.8,
                'critical': 0.95
            },
            'blocked_patterns': [
                'eval(',
                'exec(',
                'os.system',
                'subprocess'
            ]
        },
        'audit': {
            'enabled': True,
            'log_level': 'INFO',
            'log_file': './logs/generation.log',
            'retention_days': 30
        },
        'context': {
            'enabled': True,
            'cache_enabled': True,
            'cache_ttl': 1800,  # 30 минут
            'include_metadata': True,
            'include_performance_hints': True
        },
        'performance': {
            'max_concurrent_requests': 10,
            'request_queue_size': 100,
            'cache_enabled': True,
            'response_cache_ttl': 600,  # 10 минут
            'metrics_enabled': True
        }
    }

# Дополнительные утилиты
def format_generation_result(result: CodeGenerationResult) -> dict:
    """
    Форматирование результата генерации для API
    
    Args:
        result: Результат генерации
        
    Returns:
        dict: Отформатированный результат
    """
    return {
        'success': result.success,
        'status': result.status.value,
        'generated_code': result.generated_code,
        'metadata': result.metadata,
        'recommendations': result.recommendations,
        'warnings': result.warnings,
        'errors': result.errors,
        'request_id': result.request_id,
        'execution_time': result.execution_time,
        'validation_score': result.validation_score,
        'security_status': result.security_status
    }

def create_sample_request() -> CodeGenerationRequest:
    """
    Создание примера запроса на генерацию
    
    Returns:
        CodeGenerationRequest: Пример запроса
    """
    return CodeGenerationRequest(
        prompt="Создать обработку для массового изменения цен товаров с возможностью фильтрации по категории и применения процентного или абсолютного изменения",
        object_type="processing",
        code_style="standard",
        include_comments=True,
        use_standards=True,
        request_id="sample_001"
    )

# Инициализация системы
def initialize_system(config: dict = None) -> tuple:
    """
    Инициализация всей системы генерации кода
    
    Args:
        config: Конфигурация системы (опционально)
        
    Returns:
        tuple: (engine, status_info)
    """
    
    # Использование конфигурации по умолчанию если не указана
    if config is None:
        config = get_default_config()
    
    # Проверка совместимости
    compatibility = check_compatibility()
    if not compatibility['compatible']:
        raise RuntimeError(f"Система несовместима: {compatibility['error']}")
    
    # Валидация конфигурации
    validation = validate_config(config)
    if not validation['valid']:
        raise ValueError(f"Некорректная конфигурация: {', '.join(validation['errors'])}")
    
    # Создание движка
    engine = create_engine(config)
    
    status_info = {
        'system_version': __version__,
        'compatibility': compatibility,
        'configuration': validation,
        'status': 'initialized'
    }
    
    return engine, status_info

# Служебная информация
SYSTEM_INFO = {
    'name': '1C AI MCP Code Generation System',
    'version': __version__,
    'author': __author__,
    'description': __description__,
    'constants': SYSTEM_CONSTANTS,
    'supported_languages': ['1C', 'BSL'],
    'supported_platforms': ['1C Enterprise 8.3'],
    'license': 'Proprietary',
    'repository': '1c-ai-mcp-code-generation'
}

def get_system_info() -> dict:
    """Получение информации о системе"""
    return SYSTEM_INFO.copy()

if __name__ == "__main__":
    # Демонстрация работы системы
    print(f"1C AI MCP Code Generation System v{__version__}")
    print(f"Описание: {__description__}")
    
    # Проверка совместимости
    compatibility = check_compatibility()
    print(f"Совместимость: {'✅ OK' if compatibility['compatible'] else '❌ FAIL'}")
    
    if not compatibility['compatible']:
        print(f"Ошибка: {compatibility['error']}")
    
    # Инициализация системы
    try:
        engine, status = initialize_system()
        print(f"Статус инициализации: {status['status']}")
        
        # Создание примера запроса
        sample_request = create_sample_request()
        print(f"Пример запроса создан: {sample_request.request_id}")
        
        print("Система готова к использованию!")
        
    except Exception as e:
        print(f"Ошибка инициализации: {e}")