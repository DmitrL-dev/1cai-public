
"""
Конфигурация системы мониторинга.
Настройки для Prometheus, Sentry, алертинга и других компонентов.
"""

import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class Environment(Enum):
    """Окружения"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


@dataclass
class PrometheusConfig:
    """Конфигурация Prometheus"""
    enabled: bool = True
    port: int = 8000
    path: str = "/metrics"
    service_name: str = "mcp_server"
    registry: Optional[str] = None
    metrics_prefix: str = "mcp"
    custom_buckets: List[float] = None
    enable_default_metrics: bool = True
    
    def __post_init__(self):
        if self.custom_buckets is None:
            self.custom_buckets = [0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0]
            
    def to_dict(self) -> Dict[str, Any]:
        return {
            'enabled': self.enabled,
            'port': self.port,
            'path': self.path,
            'service_name': self.service_name,
            'registry': self.registry,
            'metrics_prefix': self.metrics_prefix,
            'custom_buckets': self.custom_buckets,
            'enable_default_metrics': self.enable_default_metrics
        }


@dataclass
class SentryConfig:
    """Конфигурация Sentry"""
    enabled: bool = False
    dsn: Optional[str] = None
    environment: str = Environment.PRODUCTION.value
    service_name: str = "mcp_server"
    release: Optional[str] = None
    debug: bool = False
    traces_sample_rate: float = 0.1
    profiles_sample_rate: float = 0.1
    before_send_timeout: int = 10
    before_send_transaction_timeout: int = 5
    max_breadcrumbs: int = 100
    max_value_length: int = 1024
    
    def __post_init__(self):
        if not self.dsn:
            self.dsn = os.getenv('SENTRY_DSN')
            
        self.environment = os.getenv('ENVIRONMENT', self.environment)
        self.debug = os.getenv('SENTRY_DEBUG', 'false').lower() == 'true'
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            'enabled': self.enabled,
            'dsn': self.dsn,
            'environment': self.environment,
            'service_name': self.service_name,
            'release': self.release,
            'debug': self.debug,
            'traces_sample_rate': self.traces_sample_rate,
            'profiles_sample_rate': self.profiles_sample_rate,
            'before_send_timeout': self.before_send_timeout,
            'before_send_transaction_timeout': self.before_send_transaction_timeout,
            'max_breadcrumbs': self.max_breadcrumbs,
            'max_value_length': self.max_value_length
        }


@dataclass
class AlertConfig:
    """Конфигурация алертинга"""
    enabled: bool = True
    retention_days: int = 30
    escalation_rules: Dict[str, Dict[str, Any]] = None
    channels: Dict[str, Dict[str, Any]] = None
    max_alerts_per_hour: int = 100
    
    def __post_init__(self):
        if self.escalation_rules is None:
            self.escalation_rules = {
                'critical': {
                    'escalation_delay_minutes': 5,
                    'escalation_channels': ['email', 'slack', 'telegram'],
                    'max_escalation_level': 3
                },
                'high': {
                    'escalation_delay_minutes': 15,
                    'escalation_channels': ['slack', 'telegram'],
                    'max_escalation_level': 2
                },
                'medium': {
                    'escalation_delay_minutes': 60,
                    'escalation_channels': ['telegram'],
                    'max_escalation_level': 1
                }
            }
            
        if self.channels is None:
            self.channels = {
                'email': {
                    'enabled': False,
                    'smtp_server': os.getenv('SMTP_SERVER', ''),
                    'smtp_port': int(os.getenv('SMTP_PORT', '587')),
                    'username': os.getenv('SMTP_USERNAME', ''),
                    'password': os.getenv('SMTP_PASSWORD', ''),
                    'from_email': os.getenv('ALERT_FROM_EMAIL', 'alerts@mcp-server.local'),
                    'to_emails': os.getenv('ALERT_TO_EMAILS', '').split(',')
                },
                'slack': {
                    'enabled': bool(os.getenv('SLACK_WEBHOOK_URL')),
                    'webhook_url': os.getenv('SLACK_WEBHOOK_URL', ''),
                    'channel': os.getenv('SLACK_CHANNEL', '#alerts')
                },
                'telegram': {
                    'enabled': bool(os.getenv('TELEGRAM_BOT_TOKEN')),
                    'bot_token': os.getenv('TELEGRAM_BOT_TOKEN', ''),
                    'chat_id': os.getenv('TELEGRAM_CHAT_ID', '')
                }
            }
            
    def to_dict(self) -> Dict[str, Any]:
        return {
            'enabled': self.enabled,
            'retention_days': self.retention_days,
            'escalation_rules': self.escalation_rules,
            'channels': self.channels,
            'max_alerts_per_hour': self.max_alerts_per_hour
        }


@dataclass
class OpenTelemetryConfig:
    """Конфигурация OpenTelemetry"""
    enabled: bool = False
    service_name: str = "mcp_server"
    service_version: str = "1.0.0"
    environment: str = Environment.PRODUCTION.value
    traces_endpoint: Optional[str] = None
    metrics_endpoint: Optional[str] = None
    logs_endpoint: Optional[str] = None
    jaeger_endpoint: Optional[str] = None
    zipkin_endpoint: Optional[str] = None
    traces_sample_rate: float = 0.1
    
    def __post_init__(self):
        self.traces_endpoint = os.getenv('OTEL_EXPORTER_OTLP_TRACES_ENDPOINT')
        self.metrics_endpoint = os.getenv('OTEL_EXPORTER_OTLP_METRICS_ENDPOINT')
        self.logs_endpoint = os.getenv('OTEL_EXPORTER_OTLP_LOGS_ENDPOINT')
        self.jaeger_endpoint = os.getenv('JAEGER_ENDPOINT')
        self.zipkin_endpoint = os.getenv('ZIPKIN_ENDPOINT')
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            'enabled': self.enabled,
            'service_name': self.service_name,
            'service_version': self.service_version,
            'environment': self.environment,
            'traces_endpoint': self.traces_endpoint,
            'metrics_endpoint': self.metrics_endpoint,
            'logs_endpoint': self.logs_endpoint,
            'jaeger_endpoint': self.jaeger_endpoint,
            'zipkin_endpoint': self.zipkin_endpoint,
            'traces_sample_rate': self.traces_sample_rate
        }


@dataclass
class MonitoringThresholds:
    """Пороговые значения для мониторинга"""
    # Ошибки
    error_rate_threshold: float = 0.01  # 1% ошибок
    validation_error_threshold: float = 0.005  # 0.5% ошибок валидации
    transport_error_threshold: float = 0.003  # 0.3% транспортных ошибок
    integration_error_threshold: float = 0.001  # 0.1% ошибок интеграции
    
    # Производительность
    response_time_threshold_ms: int = 200  # 200ms
    operation_duration_threshold_ms: int = 1000  # 1s
    integration_timeout_threshold_ms: int = 30000  # 30s
    database_query_threshold_ms: int = 500  # 500ms
    
    # Ресурсы
    cpu_usage_threshold: float = 80.0  # 80%
    memory_usage_threshold: float = 85.0  # 85%
    disk_usage_threshold: float = 90.0  # 90%
    active_requests_threshold: int = 100
    queue_size_threshold: int = 50
    
    # Circuit Breaker
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_timeout_seconds: int = 60
    circuit_breaker_success_threshold: int = 3
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'error_rate_threshold': self.error_rate_threshold,
            'validation_error_threshold': self.validation_error_threshold,
            'transport_error_threshold': self.transport_error_threshold,
            'integration_error_threshold': self.integration_error_threshold,
            'response_time_threshold_ms': self.response_time_threshold_ms,
            'operation_duration_threshold_ms': self.operation_duration_threshold_ms,
            'integration_timeout_threshold_ms': self.integration_timeout_threshold_ms,
            'database_query_threshold_ms': self.database_query_threshold_ms,
            'cpu_usage_threshold': self.cpu_usage_threshold,
            'memory_usage_threshold': self.memory_usage_threshold,
            'disk_usage_threshold': self.disk_usage_threshold,
            'active_requests_threshold': self.active_requests_threshold,
            'queue_size_threshold': self.queue_size_threshold,
            'circuit_breaker_failure_threshold': self.circuit_breaker_failure_threshold,
            'circuit_breaker_timeout_seconds': self.circuit_breaker_timeout_seconds,
            'circuit_breaker_success_threshold': self.circuit_breaker_success_threshold
        }


@dataclass
class MonitoringConfig:
    """Основная конфигурация мониторинга"""
    environment: Environment = Environment.PRODUCTION
    prometheus: PrometheusConfig = None
    sentry: SentryConfig = None
    alerts: AlertConfig = None
    opentelemetry: OpenTelemetryConfig = None
    thresholds: MonitoringThresholds = None
    
    # SLO/SLI метрики
    availability_target: float = 0.995  # 99.5%
    latency_target_p95_ms: int = 200  # <200ms для 95% запросов
    latency_target_p99_ms: int = 500  # <500ms для 99% запросов
    error_rate_target: float = 0.001  # <0.1%
    
    # Интервалы сбора метрик
    metrics_collection_interval_seconds: int = 15
    health_check_interval_seconds: int = 30
    cleanup_interval_seconds: int = 3600
    
    def __post_init__(self):
        if self.prometheus is None:
            self.prometheus = PrometheusConfig()
        if self.sentry is None:
            self.sentry = SentryConfig()
        if self.alerts is None:
            self.alerts = AlertConfig()
        if self.opentelemetry is None:
            self.opentelemetry = OpenTelemetryConfig()
        if self.thresholds is None:
            self.thresholds = MonitoringThresholds()
            
    def to_dict(self) -> Dict[str, Any]:
        return {
            'environment': self.environment.value,
            'prometheus': self.prometheus.to_dict(),
            'sentry': self.sentry.to_dict(),
            'alerts': self.alerts.to_dict(),
            'opentelemetry': self.opentelemetry.to_dict(),
            'thresholds': self.thresholds.to_dict(),
            'availability_target': self.availability_target,
            'latency_target_p95_ms': self.latency_target_p95_ms,
            'latency_target_p99_ms': self.latency_target_p99_ms,
            'error_rate_target': self.error_rate_target,
            'metrics_collection_interval_seconds': self.metrics_collection_interval_seconds,
            'health_check_interval_seconds': self.health_check_interval_seconds,
            'cleanup_interval_seconds': self.cleanup_interval_seconds
        }


# Глобальная конфигурация
_global_config: Optional[MonitoringConfig] = None


def get_config() -> MonitoringConfig:
    """Получение глобальной конфигурации мониторинга"""
    global _global_config
    if _global_config is None:
        _global_config = load_config()
    return _global_config


def load_config(config_file: Optional[str] = None) -> MonitoringConfig:
    """
    Загрузка конфигурации мониторинга
    
    Args:
        config_file: Путь к файлу конфигурации (JSON/YAML)
        
    Returns:
        Экземпляр MonitoringConfig
    """
    config = MonitoringConfig()
    
    if config_file and os.path.exists(config_file):
        try:
            if config_file.endswith('.json'):
                import json
                with open(config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            elif config_file.endswith(('.yaml', '.yml')):
                import yaml
                with open(config_file, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
            else:
                raise ValueError("Неподдерживаемый формат файла конфигурации")
                
            # Применение конфигурации из файла
            apply_config_data(config, data)
            
        except Exception as e:
            print(f"Ошибка загрузки конфигурации из файла {config_file}: {e}")
            
    # Переопределение переменными окружения
    apply_env_overrides(config)
    
    return config


def apply_config_data(config: MonitoringConfig, data: Dict[str, Any]):
    """Применение данных конфигурации"""
    if 'environment' in data:
        config.environment = Environment(data['environment'])
        
    if 'prometheus' in data:
        prometheus_data = data['prometheus']
        config.prometheus = PrometheusConfig(**prometheus_data)
        
    if 'sentry' in data:
        sentry_data = data['sentry']
        config.sentry = SentryConfig(**sentry_data)
        
    if 'alerts' in data:
        alert_data = data['alerts']
        config.alerts = AlertConfig(**alert_data)
        
    if 'opentelemetry' in data:
        otel_data = data['opentelemetry']
        config.opentelemetry = OpenTelemetryConfig(**otel_data)
        
    if 'thresholds' in data:
        threshold_data = data['thresholds']
        config.thresholds = MonitoringThresholds(**threshold_data)
        
    # SLO/SLI настройки
    if 'availability_target' in data:
        config.availability_target = data['availability_target']
    if 'latency_target_p95_ms' in data:
        config.latency_target_p95_ms = data['latency_target_p95_ms']
    if 'latency_target_p99_ms' in data:
        config.latency_target_p99_ms = data['latency_target_p99_ms']
    if 'error_rate_target' in data:
        config.error_rate_target = data['error_rate_target']


def apply_env_overrides(config: MonitoringConfig):
    """Применение переопределений из переменных окружения"""
    # Environment
    env = os.getenv('ENVIRONMENT', config.environment.value)
    config.environment = Environment(env)
    
    # Prometheus
    prometheus_enabled = os.getenv('PROMETHEUS_ENABLED', '').lower() == 'true'
    if prometheus_enabled is not None:
        config.prometheus.enabled = prometheus_enabled
        
    prometheus_port = os.getenv('PROMETHEUS_PORT')
    if prometheus_port:
        config.prometheus.port = int(prometheus_port)
        
    # Sentry
    sentry_enabled = os.getenv('SENTRY_ENABLED', '').lower() == 'true'
    if sentry_enabled is not None:
        config.sentry.enabled = sentry_enabled
        
    traces_sample_rate = os.getenv('SENTRY_TRACES_SAMPLE_RATE')
    if traces_sample_rate:
        config.sentry.traces_sample_rate = float(traces_sample_rate)
        
    # OpenTelemetry
    otel_enabled = os.getenv('OTEL_ENABLED', '').lower() == 'true'
    if otel_enabled is not None:
        config.opentelemetry.enabled = otel_enabled
        
    traces_sample_rate = os.getenv('OTEL_TRACES_SAMPLE_RATE')
    if traces_sample_rate:
        config.opentelemetry.traces_sample_rate = float(traces_sample_rate)


def save_config(config: MonitoringConfig, config_file: str):
    """
    Сохранение конфигурации в файл
    
    Args:
        config: Конфигурация для сохранения
        config_file: Путь к файлу для сохранения
    """
    try:
        data = config.to_dict()
        
        if config_file.endswith('.json'):
            import json
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        elif config_file.endswith(('.yaml', '.yml')):
            import yaml
            with open(config_file, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
        else:
            raise ValueError("Неподдерживаемый формат файла конфигурации")
            
        print(f"Конфигурация сохранена в {config_file}")
        
    except Exception as e:
        print(f"Ошибка сохранения конфигурации: {e}")


def create_default_config_file(filename: str = "monitoring_config.json"):
    """Создание файла конфигурации по умолчанию"""
    config = MonitoringConfig()
    save_config(config, filename)


def validate_config(config: MonitoringConfig) -> List[str]:
    """
    Валидация конфигурации мониторинга
    
    Args:
        config: Конфигурация для проверки
        
    Returns:
        Список ошибок валидации
    """
    errors = []
    
    # Проверка Prometheus
    if config.prometheus.enabled:
        if not (1024 <= config.prometheus.port <= 65535):
            errors.append(f"Некорректный порт Prometheus: {config.prometheus.port}")
            
    # Проверка Sentry
    if config.sentry.enabled and not config.sentry.dsn:
        errors.append("Sentry включен, но DSN не указан")
        
    if not (0.0 <= config.sentry.traces_sample_rate <= 1.0):
        errors.append(f"Некорректный traces_sample_rate: {config.sentry.traces_sample_rate}")
        
    # Проверка алертов
    if config.alerts.enabled:
        for channel_name, channel_config in config.alerts.channels.items():
            if channel_config.get('enabled'):
                if channel_name == 'email':
                    required_fields = ['smtp_server', 'username', 'password', 'from_email']
                    for field in required_fields:
                        if not channel_config.get(field):
                            errors.append(f"Email канал: отсутствует поле {field}")
                elif channel_name == 'slack':
                    if not channel_config.get('webhook_url'):
                        errors.append("Slack канал: отсутствует webhook_url")
                elif channel_name == 'telegram':
                    required_fields = ['bot_token', 'chat_id']
                    for field in required_fields:
                        if not channel_config.get(field):
                            errors.append(f"Telegram канал: отсутствует поле {field}")
                            
    # Проверка OpenTelemetry
    if config.opentelemetry.enabled:
        if not (0.0 <= config.opentelemetry.traces_sample_rate <= 1.0):
            errors.append(f"Некорректный OTEL traces_sample_rate: {config.opentelemetry.traces_sample_rate}")
            
    # Проверка SLO targets
    if not (0.0 <= config.availability_target <= 1.0):
        errors.append(f"Некорректный availability_target: {config.availability_target}")
        
    if config.latency_target_p95_ms <= 0:
        errors.append(f"Некорректный latency_target_p95_ms: {config.latency_target_p95_ms}")
        
    if config.error_rate_target < 0.0 or config.error_rate_target > 1.0:
        errors.append(f"Некорректный error_rate_target: {config.error_rate_target}")
        
    return errors


# Инициализация конфигурации
def init_config(config_file: Optional[str] = None) -> MonitoringConfig:
    """
    Инициализация глобальной конфигурации мониторинга
    
    Args:
        config_file: Путь к файлу конфигурации
        
    Returns:
        Инициализированная конфигурация
    """
    global _global_config
    _global_config = load_config(config_file)
    
    # Валидация
    validation_errors = validate_config(_global_config)
    if validation_errors:
        print("Ошибки валидации конфигурации:")
        for error in validation_errors:
            print(f"  - {error}")
            
    return _global_config