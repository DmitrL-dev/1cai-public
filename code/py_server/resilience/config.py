
"""
Конфигурация системы устойчивости и circuit breaker
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List


class ServiceType(Enum):
    """Типы сервисов для применения circuit breaker"""
    EXTERNAL_API = "external_api"
    MCP_TOOL = "mcp_tool"
    MCP_RESOURCE = "mcp_resource"
    OAUTH2 = "oauth2"
    DB = "database"
    CACHE = "cache"
    MESSAGE_QUEUE = "message_queue"


class DegradationLevel(Enum):
    """Уровни деградации сервиса"""
    FULL_SERVICE = "full_service"           # Полная функциональность
    CACHED_DATA = "cached_data"             # Только кэшированные данные
    SIMPLIFIED_RESPONSE = "simplified"      # Упрощенные ответы
    MINIMAL_RESPONSE = "minimal"            # Минимальная функциональность


@dataclass
class CircuitBreakerConfig:
    """Конфигурация circuit breaker"""
    # Пороговые значения
    failure_threshold: int = 5              # Количество ошибок для перехода в OPEN
    success_threshold: int = 3              # Успешных запросов для закрытия в HALF_OPEN
    timeout: float = 60.0                   # Таймаут в секундах для автоматического перехода в HALF_OPEN
    
    # Временные окна
    time_window: float = 10.0               # Временное окно для подсчета ошибок (секунды)
    half_open_duration: float = 30.0        # Продолжительность тестирования в HALF_OPEN
    
    # Исключения
    failure_exceptions: List[type] = field(default_factory=lambda: [
        ConnectionError, TimeoutError, OSError, RuntimeError
    ])
    
    # Кэширование для circuit breaker
    enable_caching: bool = True
    cache_ttl: float = 300.0               # Время жизни кэша (секунды)


@dataclass
class RetryPolicyConfig:
    """Конфигурация политики ретраев"""
    # Основные параметры
    max_attempts: int = 3                   # Максимальное количество попыток
    base_delay: float = 0.1                 # Базовая задержка (100ms)
    max_delay: float = 30.0                 # Максимальная задержка
    
    # Экспоненциальная задержка
    exponential_base: float = 2.0           # Основание для экспоненты
    jitter: bool = True                     # Добавлять ли джиттер
    jitter_range: float = 0.1               # Диапазон джиттера (10%)
    
    # Исключения для ретраев
    retryable_exceptions: List[type] = field(default_factory=lambda: [
        ConnectionError, TimeoutError, OSError
    ])
    non_retryable_exceptions: List[type] = field(default_factory=lambda: [
        ValueError, TypeError, PermissionError
    ])


@dataclass
class GracefulDegradationConfig:
    """Конфигурация graceful degradation"""
    # Пороговые значения для переключения уровней
    degradation_threshold: int = 10         # Количество ошибок для начала деградации
    recovery_threshold: int = 3             # Успешных операций для восстановления
    
    # Кэширование fallback данных
    enable_fallback_cache: bool = True
    fallback_cache_ttl: float = 3600.0      # Время жизни fallback кэша (1 час)
    
    # Уведомления
    enable_notifications: bool = True
    notification_interval: float = 300.0    # Интервал между уведомлениями (5 минут)
    
    # Fallback стратегии для различных типов операций
    fallback_strategies: Dict[str, str] = field(default_factory=lambda: {
        "tools_list": "cached_list",
        "tools_call": "minimal_response", 
        "resources_read": "cached_content",
        "prompts_get": "default_prompt"
    })


@dataclass
class ResilienceConfig:
    """Главная конфигурация системы устойчивости"""
    # Настройки circuit breaker для различных сервисов
    circuit_breakers: Dict[ServiceType, CircuitBreakerConfig] = field(default_factory=dict)
    
    # Настройки ретраев
    retry_policies: Dict[str, RetryPolicyConfig] = field(default_factory=dict)
    
    # Настройки деградации
    degradation: GracefulDegradationConfig = field(default_factory=GracefulDegradationConfig)
    
    # Логирование
    enable_logging: bool = True
    log_level: str = "INFO"
    enable_metrics: bool = True


# Глобальная конфигурация по умолчанию
DEFAULT_CONFIG = ResilienceConfig(
    circuit_breakers={
        ServiceType.EXTERNAL_API: CircuitBreakerConfig(
            failure_threshold=5,
            timeout=60.0,
            time_window=10.0
        ),
        ServiceType.MCP_TOOL: CircuitBreakerConfig(
            failure_threshold=3,
            timeout=30.0,
            time_window=5.0
        ),
        ServiceType.DB: CircuitBreakerConfig(
            failure_threshold=3,
            timeout=45.0,
            time_window=15.0
        ),
        ServiceType.OAUTH2: CircuitBreakerConfig(
            failure_threshold=2,
            timeout=120.0,
            time_window=5.0
        )
    },
    retry_policies={
        "default": RetryPolicyConfig(
            max_attempts=3,
            base_delay=0.1,
            max_delay=10.0
        ),
        "external_api": RetryPolicyConfig(
            max_attempts=5,
            base_delay=0.2,
            max_delay=30.0
        ),
        "database": RetryPolicyConfig(
            max_attempts=3,
            base_delay=0.05,
            max_delay=5.0
        )
    },
    degradation=GracefulDegradationConfig()
)


def get_config(service_type: ServiceType = None, retry_policy: str = None) -> ResilienceConfig:
    """
    Получение конфигурации для сервиса
    
    Args:
        service_type: Тип сервиса для circuit breaker
        retry_policy: Имя политики ретраев
        
    Returns:
        Конфигурация системы устойчивости
    """
    config = DEFAULT_CONFIG
    
    # Логирование конфигурации
    if config.enable_logging:
        logger = get_logger()
        logger.info(f"Получена конфигурация для сервиса: {service_type}, политика: {retry_policy}")
    
    return config


def get_circuit_breaker_config(service_type: ServiceType) -> CircuitBreakerConfig:
    """Получение конфигурации circuit breaker для сервиса"""
    default_config = DEFAULT_CONFIG.circuit_breakers.get(service_type)
    if default_config:
        return default_config
    
    # Возвращаем конфигурацию по умолчанию
    return CircuitBreakerConfig()


def get_retry_policy_config(policy_name: str) -> RetryPolicyConfig:
    """Получение конфигурации политики ретраев"""
    config = DEFAULT_CONFIG.retry_policies.get(policy_name)
    if config:
        return config
    
    # Возвращаем конфигурацию по умолчанию
    return RetryPolicyConfig()


def update_config(new_config: ResilienceConfig):
    """Обновление глобальной конфигурации"""
    global DEFAULT_CONFIG
    DEFAULT_CONFIG = new_config


def get_logger():
    """Получение логгера для системы устойчивости"""
    import logging
    logger = logging.getLogger("resilience")
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger