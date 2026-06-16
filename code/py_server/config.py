
"""
Конфигурация для API администрирования кэша

Включает:
- Настройки для разработки и продакшена
- Переменные окружения
- Конфигурацию кэшей
- Настройки безопасности
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseSettings, Field


class Environment(str, Enum):
    """Варианты окружения"""
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TESTING = "testing"


class CacheConfig(BaseSettings):
    """Конфигурация кэша"""
    type: str = Field(default="memory", description="Тип кэша (memory, redis)")
    connection_string: Optional[str] = Field(default=None, description="Строка подключения к кэшу")
    max_memory_mb: int = Field(default=512, description="Максимальное использование памяти в МБ")
    default_ttl: int = Field(default=3600, description="Время жизни по умолчанию в секундах")
    cleanup_interval: int = Field(default=300, description="Интервал очистки в секундах")


class SecurityConfig(BaseSettings):
    """Конфигурация безопасности"""
    admin_token: str = Field(
        default="admin_token_123",
        description="Токен администратора для API"
    )
    jwt_secret_key: str = Field(
        default="your-super-secret-jwt-key-change-in-production",
        description="Секретный ключ для JWT"
    )
    jwt_algorithm: str = Field(default="HS256", description="Алгоритм JWT")
    jwt_expire_minutes: int = Field(default=60, description="Время жизни JWT в минутах")
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080"],
        description="Разрешенные источники для CORS"
    )
    rate_limit_per_minute: int = Field(default=100, description="Лимит запросов в минуту")


class MetricsConfig(BaseSettings):
    """Конфигурация метрик"""
    enable_metrics: bool = Field(default=True, description="Включить сбор метрик")
    metrics_retention_hours: int = Field(default=24, description="Время хранения метрик в часах")
    response_time_sampling_rate: float = Field(
        default=1.0,
        description="Частота сэмплирования времени отклика (0.0-1.0)"
    )
    memory_tracking_enabled: bool = Field(default=True, description="Включить мониторинг памяти")


class MonitoringConfig(BaseSettings):
    """Конфигурация мониторинга"""
    health_check_interval: int = Field(default=60, description="Интервал проверки здоровья в секундах")
    alert_thresholds: Dict[str, float] = Field(
        default={
            "hit_rate_min": 0.7,
            "response_time_max_ms": 100.0,
            "memory_usage_max_percent": 80.0
        },
        description="Пороги для алертов"
    )
    enable_detailed_logging: bool = Field(default=True, description="Подробное логирование")


class AppConfig(BaseSettings):
    """Основная конфигурация приложения"""
    environment: Environment = Field(default=Environment.DEVELOPMENT, description="Окружение")
    app_name: str = Field(default="1С Server Cache Admin API", description="Название приложения")
    app_version: str = Field(default="1.0.0", description="Версия приложения")
    debug: bool = Field(default=False, description="Режим отладки")
    host: str = Field(default="0.0.0.0", description="Хост для запуска")
    port: int = Field(default=8000, description="Порт для запуска")
    workers: int = Field(default=1, description="Количество воркеров")
    reload: bool = Field(default=False, description="Автоперезагрузка")
    
    # Подконфигурации
    cache: CacheConfig = CacheConfig()
    security: SecurityConfig = SecurityConfig()
    metrics: MetricsConfig = MetricsConfig()
    monitoring: MonitoringConfig = MonitoringConfig()
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Глобальная конфигурация
config = AppConfig()


# Настройки по окружениям
ENVIRONMENT_CONFIGS = {
    Environment.DEVELOPMENT: {
        "debug": True,
        "reload": True,
        "cache": {
            "max_memory_mb": 256,
            "default_ttl": 1800,  # 30 минут
            "cleanup_interval": 60,  # 1 минута
        },
        "security": {
            "cors_origins": ["http://localhost:3000", "http://localhost:8080", "http://localhost:5173"],
            "rate_limit_per_minute": 1000,
        },
        "monitoring": {
            "enable_detailed_logging": True,
            "health_check_interval": 30,
        }
    },
    
    Environment.PRODUCTION: {
        "debug": False,
        "reload": False,
        "cache": {
            "max_memory_mb": 2048,
            "default_ttl": 3600,  # 1 час
            "cleanup_interval": 300,  # 5 минут
        },
        "security": {
            "cors_origins": ["https://yourdomain.com"],
            "rate_limit_per_minute": 100,
        },
        "monitoring": {
            "enable_detailed_logging": False,
            "health_check_interval": 60,
        }
    },
    
    Environment.TESTING: {
        "debug": True,
        "reload": False,
        "cache": {
            "max_memory_mb": 128,
            "default_ttl": 60,
            "cleanup_interval": 10,
        },
        "security": {
            "admin_token": "test_admin_token_123",
            "cors_origins": ["http://localhost:3000"],
            "rate_limit_per_minute": 10000,
        },
        "monitoring": {
            "enable_detailed_logging": False,
            "health_check_interval": 10,
        }
    }
}


def get_config_for_environment(env: Environment = None) -> Dict[str, Any]:
    """
    Получить конфигурацию для конкретного окружения
    
    Args:
        env: Окружение (development/production/testing)
    
    Returns:
        Словарь с настройками
    """
    if env is None:
        env = config.environment
    
    base_config = ENVIRONMENT_CONFIGS.get(env, ENVIRONMENT_CONFIGS[Environment.DEVELOPMENT])
    return base_config


def apply_environment_config(env: Environment = None):
    """
    Применить настройки окружения к конфигурации
    
    Args:
        env: Окружение для применения
    """
    env_config = get_config_for_environment(env)
    
    # Применяем настройки к объекту конфигурации
    for key, value in env_config.items():
        if hasattr(config, key):
            if isinstance(value, dict):
                # Для вложенных конфигураций
                nested_config = getattr(config, key)
                for nested_key, nested_value in value.items():
                    if hasattr(nested_config, nested_key):
                        setattr(nested_config, nested_key, nested_value)
            else:
                setattr(config, key, value)


# Настройки кэшей для различных сценариев
CACHE_CONFIGS = {
    "metadata": {
        "type": "memory",
        "max_size": 1000,
        "ttl": 7200,  # 2 часа
        "description": "Кэш метаданных 1С"
    },
    
    "computations": {
        "type": "memory", 
        "max_size": 500,
        "ttl": 3600,  # 1 час
        "description": "Кэш результатов вычислений"
    },
    
    "http_responses": {
        "type": "redis",
        "max_size": 2000,
        "ttl": 1800,  # 30 минут
        "description": "Кэш HTTP ответов"
    },
    
    "user_sessions": {
        "type": "memory",
        "max_size": 2000,
        "ttl": 3600,  # 1 час
        "description": "Кэш пользовательских сессий"
    },
    
    "reports": {
        "type": "redis",
        "max_size": 100,
        "ttl": 86400,  # 24 часа
        "description": "Кэш отчетов и агрегатов"
    }
}


# Настройки метрик для различных типов операций
METRICS_CONFIGS = {
    "cache_operations": {
        "enabled": True,
        "sampling_rate": 1.0,
        "retention_hours": 24
    },
    
    "api_requests": {
        "enabled": True,
        "sampling_rate": 0.1,  # 10% запросов
        "retention_hours": 168  # 1 неделя
    },
    
    "system_metrics": {
        "enabled": True,
        "sampling_rate": 1.0,
        "retention_hours": 24
    }
}


# Настройки алертов
ALERT_CONFIGS = {
    "hit_rate_low": {
        "threshold": 0.7,
        "severity": "warning",
        "message": "Низкий коэффициент попаданий кэша: {value:.2%}"
    },
    
    "response_time_high": {
        "threshold": 100.0,
        "severity": "warning", 
        "message": "Высокое время отклика кэша: {value:.2f}ms"
    },
    
    "memory_usage_high": {
        "threshold": 80.0,
        "severity": "critical",
        "message": "Высокое использование памяти: {value:.1f}%"
    },
    
    "cache_full": {
        "threshold": 0.95,
        "severity": "critical",
        "message": "Кэш практически заполнен: {value:.1%}"
    }
}


def get_cache_config(cache_name: str) -> Dict[str, Any]:
    """
    Получить конфигурацию для конкретного кэша
    
    Args:
        cache_name: Имя кэша
    
    Returns:
        Конфигурация кэша или базовая конфигурация
    """
    return CACHE_CONFIGS.get(cache_name, {
        "type": "memory",
        "max_size": 100,
        "ttl": config.cache.default_ttl,
        "description": f"Кэш {cache_name}"
    })


def get_metrics_config(metrics_type: str) -> Dict[str, Any]:
    """
    Получить конфигурацию метрик
    
    Args:
        metrics_type: Тип метрик
    
    Returns:
        Конфигурация метрик
    """
    return METRICS_CONFIGS.get(metrics_type, {
        "enabled": True,
        "sampling_rate": 1.0,
        "retention_hours": config.metrics.metrics_retention_hours
    })


def get_alert_config(alert_type: str) -> Dict[str, Any]:
    """
    Получить конфигурацию алерта
    
    Args:
        alert_type: Тип алерта
    
    Returns:
        Конфигурация алерта
    """
    return ALERT_CONFIGS.get(alert_type, {
        "threshold": 0.0,
        "severity": "info",
        "message": f"Алерт {alert_type}"
    })


# Валидация конфигурации
def validate_config() -> List[str]:
    """
    Валидация конфигурации
    
    Returns:
        Список ошибок валидации
    """
    errors = []
    
    # Проверка безопасности
    if config.environment == Environment.PRODUCTION:
        if config.security.admin_token == "admin_token_123":
            errors.append("Небезопасный токен администратора для продакшена")
        
        if config.security.jwt_secret_key == "your-super-secret-jwt-key-change-in-production":
            errors.append("Небезопасный JWT ключ для продакшена")
    
    # Проверка кэшей
    for cache_name, cache_config in CACHE_CONFIGS.items():
        if cache_config["type"] not in ["memory", "redis"]:
            errors.append(f"Неверный тип кэша для {cache_name}: {cache_config['type']}")
        
        if cache_config["max_size"] <= 0:
            errors.append(f"Неверный размер кэша для {cache_name}: {cache_config['max_size']}")
        
        if cache_config["ttl"] <= 0:
            errors.append(f"Неверный TTL для {cache_name}: {cache_config['ttl']}")
    
    # Проверка метрик
    if config.metrics.response_time_sampling_rate < 0.0 or config.metrics.response_time_sampling_rate > 1.0:
        errors.append(f"Неверная частота сэмплирования времени отклика: {config.metrics.response_time_sampling_rate}")
    
    return errors


# Применение настроек окружения при импорте
apply_environment_config()

# Экспорт основных компонентов
__all__ = [
    "config",
    "AppConfig",
    "CacheConfig", 
    "SecurityConfig",
    "MetricsConfig",
    "MonitoringConfig",
    "Environment",
    "get_config_for_environment",
    "apply_environment_config",
    "get_cache_config",
    "get_metrics_config", 
    "get_alert_config",
    "validate_config",
    "CACHE_CONFIGS",
    "METRICS_CONFIGS",
    "ALERT_CONFIGS"
]


if __name__ == "__main__":
    # Вывод текущей конфигурации для отладки
    pass
    
    print("=== Текущая конфигурация ===")
    print(f"Окружение: {config.environment}")
    print(f"Приложение: {config.app_name} v{config.app_version}")
    print(f"Отладка: {config.debug}")
    print(f"Хост: {config.host}:{config.port}")
    
    print("\n=== Конфигурация кэша ===")
    print(f"Тип: {config.cache.type}")
    print(f"Максимальная память: {config.cache.max_memory_mb} МБ")
    print(f"TTL по умолчанию: {config.cache.default_ttl} сек")
    
    print("\n=== Конфигурация безопасности ===")
    print(f"CORS источники: {config.security.cors_origins}")
    print(f"Лимит запросов: {config.security.rate_limit_per_minute}/мин")
    
    print("\n=== Конфигурация метрик ===")
    print(f"Включены: {config.metrics.enable_metrics}")
    print(f"Хранение: {config.metrics.metrics_retention_hours} часов")
    
    # Проверка валидности
    validation_errors = validate_config()
    if validation_errors:
        print("\n=== Ошибки валидации ===")
        for error in validation_errors:
            print(f"❌ {error}")
    else:
        print("\n✅ Конфигурация валидна")
