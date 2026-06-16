
"""
Примеры конфигурации для RequestTracker
Демонстрирует различные настройки для разных сценариев
"""

import os
from typing import Any, Dict

# Конфигурация для разработки
DEVELOPMENT_CONFIG = {
    "use_redis": False,
    "redis_url": "redis://localhost:6379",
    "geoip_db_path": "/usr/share/GeoIP/GeoLite2-City.mmdb"
}

# Конфигурация для продакшена
PRODUCTION_CONFIG = {
    "use_redis": True,
    "redis_url": os.getenv("REDIS_URL", "redis://redis:6379"),
    "geoip_db_path": "/usr/share/GeoIP/GeoLite2-City.mmdb"
}

# Конфигурация для тестирования
TESTING_CONFIG = {
    "use_redis": False,
    "redis_url": "redis://localhost:6379",
    "geoip_db_path": None  # GeoIP не нужен в тестах
}

# Конфигурация для высокой нагрузки
HIGH_LOAD_CONFIG = {
    "use_redis": True,
    "redis_url": "redis://redis-cluster:6379",  # Redis Cluster
    "geoip_db_path": "/usr/share/GeoIP/GeoLite2-City.mmdb",
    # Увеличиваем размеры кэшей
    "ip_tracker_max_size": 100000,
    "user_tracker_max_size": 50000,
    "tool_tracker_max_size": 20000,
    "distributed_tracker_max_size": 200000
}

# Конфигурация для 1С интеграции
ONEC_CONFIG = {
    "use_redis": True,
    "redis_url": os.getenv("REDIS_URL", "redis://localhost:6379"),
    "geoip_db_path": "/usr/share/GeoIP/GeoLite2-City.mmdb",
    # Специальные настройки для 1С
    "ip_tracker_ttl": 86400,  # 24 часа
    "user_tracker_ttl": 86400,  # 24 часа
    "tool_tracker_ttl": 3600,  # 1 час
    # Лимиты для 1С инструментов
    "tool_limits": {
        "database_query": {"per_minute": 200, "per_hour": 5000},
        "file_operation": {"per_minute": 100, "per_hour": 2000},
        "report_generation": {"per_minute": 20, "per_hour": 500},
        "external_api": {"per_minute": 50, "per_hour": 1000},
        "mcp_integration": {"per_minute": 150, "per_hour": 3000}
    }
}

# Лимиты пользователей для 1С
ONEC_USER_TIERS = {
    "free": {"requests_per_minute": 60, "requests_per_hour": 1000},
    "employee": {"requests_per_minute": 100, "requests_per_hour": 2000},
    "manager": {"requests_per_minute": 300, "requests_per_hour": 8000},
    "administrator": {"requests_per_minute": 1000, "requests_per_hour": 50000}
}

# Конфигурация для мультиарендной архитектуры
MULTITENANT_CONFIG = {
    "use_redis": True,
    "redis_url": "redis://redis:6379",
    "geoip_db_path": "/usr/share/GeoIP/GeoLite2-City.mmdb",
    # Изоляция данных по арендаторам
    "tenant_isolation": True,
    "default_tenant": "default",
    "tenant_limits": {
        "enterprise": {
            "requests_per_minute": 2000,
            "requests_per_hour": 100000,
            "concurrent_requests": 100
        },
        "professional": {
            "requests_per_minute": 1000,
            "requests_per_hour": 50000,
            "concurrent_requests": 50
        },
        "standard": {
            "requests_per_minute": 500,
            "requests_per_hour": 25000,
            "concurrent_requests": 25
        },
        "basic": {
            "requests_per_minute": 100,
            "requests_per_hour": 5000,
            "concurrent_requests": 10
        }
    }
}

# Конфигурация для compliance и аудита
COMPLIANCE_CONFIG = {
    "use_redis": True,
    "redis_url": "redis://redis:6379",
    "geoip_db_path": "/usr/share/GeoIP/GeoLite2-City.mmdb",
    # Увеличенные TTL для соответствия требованиям
    "ip_tracker_ttl": 86400 * 30,  # 30 дней
    "user_tracker_ttl": 86400 * 30,  # 30 дней
    "tool_tracker_ttl": 86400 * 7,  # 7 дней
    # Детальное логирование
    "detailed_logging": True,
    "audit_trail": True,
    "data_retention_days": 365,
    # Обязательная геолокация
    "require_geolocation": True,
    "blocked_countries": ["CN", "RU", "KP"]  # Пример списка
}

# Конфигурация для edge computing
EDGE_CONFIG = {
    "use_redis": False,  # Edge nodes обычно автономны
    "redis_url": None,
    "geoip_db_path": "/usr/share/GeoIP/GeoLite2-City.mmdb",
    # Малые размеры кэшей для ограниченных ресурсов
    "ip_tracker_max_size": 10000,
    "user_tracker_max_size": 5000,
    "tool_tracker_max_size": 2000,
    "distributed_tracker_max_size": 5000,
    # Более короткие TTL
    "ip_tracker_ttl": 3600,  # 1 час
    "user_tracker_ttl": 1800,  # 30 минут
    "tool_tracker_ttl": 900,   # 15 минут
    # Локальное агрегирование с периодической синхронизацией
    "local_aggregation": True,
    "sync_interval": 300  # 5 минут
}

# Функция для получения конфигурации по окружению
def get_config_for_environment(env: str = None) -> Dict[str, Any]:
    """
    Получить конфигурацию для конкретного окружения
    
    Args:
        env: Окружение (development/production/testing/high_load/onec/multitenant/compliance/edge)
    
    Returns:
        Словарь с конфигурацией
    """
    if env is None:
        env = os.getenv("ENVIRONMENT", "development")
    
    configs = {
        "development": DEVELOPMENT_CONFIG,
        "production": PRODUCTION_CONFIG,
        "testing": TESTING_CONFIG,
        "high_load": HIGH_LOAD_CONFIG,
        "onec": ONEC_CONFIG,
        "multitenant": MULTITENANT_CONFIG,
        "compliance": COMPLIANCE_CONFIG,
        "edge": EDGE_CONFIG
    }
    
    return configs.get(env, DEVELOPMENT_CONFIG)


# Пример применения конфигурации
async def apply_configuration(config_name: str = "development"):
    """
    Применить конфигурацию к RequestTracker
    
    Args:
        config_name: Имя конфигурации
    """
    from ratelimit import RequestTracker, init_request_tracker
    
    config = get_config_for_environment(config_name)
    print(f"Применяем конфигурацию: {config_name}")
    print(f"Config: {config}")
    
    # Инициализируем с конфигурацией
    await init_request_tracker(config)
    
    # Если есть специальные настройки для инструментов
    if "tool_limits" in config:
        tracker = RequestTracker(**config)
        for tool_name, limits in config["tool_limits"].items():
            tracker.set_tool_limits(tool_name, limits)
        print("Применены кастомные лимиты для инструментов")


# Пример для Docker Compose
DOCKER_COMPOSE_CONFIG = """
version: '3.8'
services:
  app:
    build: .
    environment:
      - ENVIRONMENT=production
      - REDIS_URL=redis://redis:6379
      - USE_REDIS=true
    volumes:
      - ./geoip:/usr/share/GeoIP:ro
    depends_on:
      - redis
      - geoip
  
  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
  
  geoip:
    image: maxminddb/geoipupdate:latest
    environment:
      - MAXMIND_ACCOUNT_ID=${MAXMIND_ACCOUNT_ID}
      - MAXMIND_LICENSE_KEY=${MAXMIND_LICENSE_KEY}
    volumes:
      - ./geoip:/usr/share/GeoIP

volumes:
  redis_data:
"""


if __name__ == "__main__":
    # Примеры использования
    
    print("=== Доступные конфигурации ===")
    configs = [
        "development", "production", "testing", "high_load",
        "onec", "multitenant", "compliance", "edge"
    ]
    
    for config_name in configs:
        config = get_config_for_environment(config_name)
        print(f"{config_name}: use_redis={config['use_redis']}")
    
    print("\n=== Пример применения конфигурации ===")
    import asyncio
    asyncio.run(apply_configuration("onec"))
