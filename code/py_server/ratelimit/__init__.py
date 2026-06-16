
"""
Rate Limiting Module для 1c_mcp
Модуль конфигурируемых лимитов с поддержкой динамических и многоуровневых лимитов
И механизм учета запросов RequestTracker для высокопроизводительного tracking
"""

from .config_limits import (ConfigurationManager, DynamicLimits, LimitConfig,
                            LimitOverrides, LimitValidator, RateLimitRules,
                            TieredLimits)
from .metrics import (  # Основные классы мониторинга; Структуры данных; Enums; Декораторы
    ActiveAlert, AlertManager, AlertRule, AlertSeverity, MetricType,
    PrometheusExporter, RateLimitDashboard, RateLimitMetric, RateLimitMetrics,
    RateLimitMonitoringSystem, RealTimeMonitor, rate_limit_monitoring)
from .request_tracker import (DistributedTracker, IPTracker, RateLimitStats,
                              RequestMetrics, RequestTracker, ToolTracker,
                              UserTracker, create_rate_limit_middleware,
                              get_request_tracker, init_request_tracker,
                              request_tracking_context)

__all__ = [
    # Конфигурация лимитов
    'LimitConfig',
    'DynamicLimits',
    'TieredLimits',
    'RateLimitRules',
    'LimitOverrides',
    'ConfigurationManager',
    'LimitValidator',
    
    # Мониторинг и метрики
    'RateLimitMonitoringSystem',
    'RateLimitMetrics',
    'PrometheusExporter',
    'AlertManager',
    'RateLimitDashboard',
    'RealTimeMonitor',
    'RateLimitMetric',
    'AlertRule',
    'ActiveAlert',
    'AlertSeverity',
    'MetricType',
    'rate_limit_monitoring',
    
    # Трекинг запросов
    'RequestTracker',
    'IPTracker',
    'UserTracker',
    'ToolTracker',
    'DistributedTracker',
    'RequestMetrics',
    'RateLimitStats',
    'get_request_tracker',
    'init_request_tracker',
    'request_tracking_context',
    'create_rate_limit_middleware'
]

__version__ = '1.0.0'

# Автоматическая инициализация системы мониторинга
_default_monitoring_system = None

def get_default_monitoring_system() -> RateLimitMonitoringSystem:
    """Получение системы мониторинга по умолчанию"""
    global _default_monitoring_system
    if _default_monitoring_system is None:
        _default_monitoring_system = RateLimitMonitoringSystem()
    return _default_monitoring_system

def start_monitoring(**kwargs) -> RateLimitMonitoringSystem:
    """Запуск системы мониторинга с настройками по умолчанию"""
    monitoring_system = RateLimitMonitoringSystem(**kwargs)
    monitoring_system.start()
    return monitoring_system

def stop_monitoring():
    """Остановка системы мониторинга по умолчанию"""
    global _default_monitoring_system
    if _default_monitoring_system:
        _default_monitoring_system.stop()
        _default_monitoring_system = None
