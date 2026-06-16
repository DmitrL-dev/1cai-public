
"""
Система интеграции с мониторингом для MCP сервера.

Модуль предоставляет:
- Prometheus метрики для отслеживания производительности и ошибок
- Интеграцию с Sentry для отслеживания исключений и APM
- Систему алертинга для критичных ошибок
- Конфигурацию мониторинга
- Поддержку OpenTelemetry для распределенной трассировки

Использование:
    from monitoring import init_monitoring, get_metrics, get_sentry
    
    # Инициализация
    init_monitoring()
    
    # Использование метрик
    metrics = get_metrics()
    metrics.record_error('validation', 'user_input', '123')
    
    # Создание алерта
    from monitoring.alerting import create_error_alert
    await create_error_alert('integration', '1c_connection', '456')

Основные компоненты:
- prometheus_metrics: Метрики Prometheus
- sentry_integration: Интеграция с Sentry
- alerting: Система алертинга
- config: Конфигурация мониторинга
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from .alerting import (Alert, AlertManager, AlertSeverity, AlertStatus,
                       EmailChannel, SlackChannel, TelegramChannel,
                       create_error_alert, create_integration_alert,
                       create_performance_alert, get_alert_manager,
                       init_alert_manager)
from .config import (AlertConfig, MonitoringConfig, MonitoringThresholds,
                     OpenTelemetryConfig, PrometheusConfig, SentryConfig,
                     get_config, init_config)
from .prometheus_metrics import (PrometheusMetrics, get_metrics, init_metrics,
                                 monitor_http_request, monitor_mcp_operation,
                                 record_circuit_breaker_state, record_error)
from .sentry_integration import (SentryIntegration, capture_exception_safe,
                                 capture_message_safe, get_sentry, group_error,
                                 init_sentry, sentry_span, sentry_transaction)

# Настройка логирования
logger = logging.getLogger(__name__)


class MonitoringSystem:
    """
    Основной класс системы мониторинга
    
    Управляет инициализацией и координацией всех компонентов мониторинга.
    """
    
    def __init__(self, config: Optional[MonitoringConfig] = None):
        """
        Инициализация системы мониторинга
        
        Args:
            config: Конфигурация мониторинга
        """
        self.config = config or get_config()
        self.is_initialized = False
        self.components = {}
        
    async def initialize(self) -> bool:
        """
        Инициализация всех компонентов мониторинга
        
        Returns:
            True если инициализация успешна
        """
        try:
            logger.info("Инициализация системы мониторинга...")
            
            # Инициализация Prometheus
            if self.config.prometheus.enabled:
                self.components['prometheus'] = init_metrics(
                    service_name=self.config.prometheus.service_name
                )
                logger.info("Prometheus метрики инициализированы")
                
            # Инициализация Sentry
            if self.config.sentry.enabled:
                self.components['sentry'] = init_sentry(
                    dsn=self.config.sentry.dsn,
                    environment=self.config.sentry.environment,
                    service_name=self.config.sentry.service_name,
                    traces_sample_rate=self.config.sentry.traces_sample_rate
                )
                logger.info("Sentry интеграция инициализирована")
                
            # Инициализация алертинга
            if self.config.alerts.enabled:
                self.components['alerting'] = init_alert_manager(
                    retention_days=self.config.alerts.retention_days
                )
                
                # Добавление каналов уведомлений
                await self._setup_notification_channels()
                logger.info("Система алертинга инициализирована")
                
            # Инициализация OpenTelemetry
            if self.config.opentelemetry.enabled:
                self._setup_opentelemetry()
                logger.info("OpenTelemetry инициализирован")
                
            # Регистрация обработчиков ошибок
            self._setup_error_handlers()
            
            self.is_initialized = True
            logger.info("Система мониторинга успешно инициализирована")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка инициализации системы мониторинга: {e}")
            return False
            
    async def _setup_notification_channels(self):
        """Настройка каналов уведомлений"""
        alert_manager = self.components['alerting']
        
        for channel_name, channel_config in self.config.alerts.channels.items():
            if not channel_config.get('enabled', False):
                continue
                
            try:
                if channel_name == 'email':
                    channel = EmailChannel(
                        name=channel_name,
                        smtp_server=channel_config['smtp_server'],
                        smtp_port=channel_config['smtp_port'],
                        username=channel_config['username'],
                        password=channel_config['password'],
                        from_email=channel_config['from_email'],
                        to_emails=channel_config['to_emails']
                    )
                    alert_manager.add_notification_channel(channel)
                    
                elif channel_name == 'slack':
                    channel = SlackChannel(
                        name=channel_name,
                        webhook_url=channel_config['webhook_url'],
                        channel=channel_config['channel']
                    )
                    alert_manager.add_notification_channel(channel)
                    
                elif channel_name == 'telegram':
                    channel = TelegramChannel(
                        name=channel_name,
                        bot_token=channel_config['bot_token'],
                        chat_id=channel_config['chat_id']
                    )
                    alert_manager.add_notification_channel(channel)
                    
            except Exception as e:
                logger.error(f"Ошибка настройки канала уведомлений {channel_name}: {e}")
                
    def _setup_opentelemetry(self):
        """Настройка OpenTelemetry"""
        try:
            from opentelemetry import trace
            from opentelemetry.exporter.jaeger.thrift import JaegerExporter
            from opentelemetry.exporter.zipkin.json import ZipkinExporter
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor

            # Создание провайдера трассировки
            trace.set_tracer_provider(TracerProvider())
            tracer_provider = trace.get_tracer_provider()
            
            # Добавление Jaeger экспортера
            if self.config.opentelemetry.jaeger_endpoint:
                jaeger_exporter = JaegerExporter(
                    agent_host_name="localhost",
                    agent_port=6831
                )
                span_processor = BatchSpanProcessor(jaeger_exporter)
                tracer_provider.add_span_processor(span_processor)
                
            # Добавление Zipkin экспортера
            if self.config.opentelemetry.zipkin_endpoint:
                zipkin_exporter = ZipkinExporter(
                    endpoint=self.config.opentelemetry.zipkin_endpoint
                )
                span_processor = BatchSpanProcessor(zipkin_exporter)
                tracer_provider.add_span_processor(span_processor)
                
            # Получение трейсера
            self.tracer = trace.get_tracer(
                self.config.opentelemetry.service_name,
                self.config.opentelemetry.service_version
            )
            
            logger.info("OpenTelemetry трейсер настроен")
            
        except ImportError:
            logger.warning("OpenTelemetry не установлен. Установите: pip install opentelemetry-api opentelemetry-sdk")
        except Exception as e:
            logger.error(f"Ошибка настройки OpenTelemetry: {e}")
            
    def _setup_error_handlers(self):
        """Настройка глобальных обработчиков ошибок"""
        import sys
        
        def exception_handler(exc_type, exc_value, exc_traceback):
            """Глобальный обработчик исключений"""
            if issubclass(exc_type, KeyboardInterrupt):
                sys.__excepthook__(exc_type, exc_value, exc_traceback)
                return
                
            logger.error(f"Uncaught exception: {exc_value}", exc_info=(exc_type, exc_value, exc_traceback))
            
            # Отправка в Sentry
            try:
                capture_exception_safe(exc_info=(exc_type, exc_value, exc_traceback))
            except Exception:
                pass
                
        sys.excepthook = exception_handler
        
    def get_status(self) -> Dict[str, Any]:
        """Получение статуса системы мониторинга"""
        status = {
            'initialized': self.is_initialized,
            'components': {}
        }
        
        for name, component in self.components.items():
            status['components'][name] = {
                'enabled': True,
                'status': 'active'
            }
            
        return status
        
    def get_health_info(self) -> Dict[str, Any]:
        """Получение информации о здоровье системы"""
        return {
            'status': 'healthy',
            'version': '1.0.0',
            'components': {
                'prometheus': self.config.prometheus.enabled,
                'sentry': self.config.sentry.enabled,
                'alerts': self.config.alerts.enabled,
                'opentelemetry': self.config.opentelemetry.enabled
            },
            'environment': self.config.environment.value,
            'service_name': self.config.prometheus.service_name
        }
        
    async def shutdown(self):
        """Корректное завершение работы системы мониторинга"""
        logger.info("Завершение работы системы мониторинга")
        
        # Здесь можно добавить очистку ресурсов
        # Например, отправку финальных метрик
        
        self.is_initialized = False


# Глобальный экземпляр системы мониторинга
_monitoring_system: Optional[MonitoringSystem] = None


def init_monitoring(config_file: Optional[str] = None) -> MonitoringSystem:
    """
    Инициализация системы мониторинга
    
    Args:
        config_file: Путь к файлу конфигурации
        
    Returns:
        Экземпляр MonitoringSystem
    """
    global _monitoring_system
    
    # Загрузка конфигурации
    config = init_config(config_file)
    
    # Создание системы мониторинга
    _monitoring_system = MonitoringSystem(config)
    
    # Запуск асинхронной инициализации
    loop = asyncio.get_event_loop()
    if loop.is_running():
        # Создание задачи для асинхронной инициализации
        loop.create_task(_monitoring_system.initialize())
    else:
        # Запуск инициализации в новом цикле
        loop.run_until_complete(_monitoring_system.initialize())
        
    return _monitoring_system


def get_monitoring_system() -> Optional[MonitoringSystem]:
    """Получение экземпляра системы мониторинга"""
    return _monitoring_system


# Утилиты для быстрого доступа к компонентам
def get_prometheus_metrics():
    """Получение метрик Prometheus"""
    return get_metrics()


def get_sentry_client():
    """Получение клиента Sentry"""
    return get_sentry()


def get_alerting_manager():
    """Получение менеджера алертов"""
    return get_alert_manager()


# Декораторы для быстрого использования
def monitor_function(operation_name: str):
    """Декоратор для мониторинга функций"""
    def decorator(func):
        # Мониторинг времени выполнения
        wrapper = monitor_mcp_operation('function', operation_name)(func)
        
        # Добавление обработки исключений через Sentry
        wrapper = sentry_transaction(operation_name)(wrapper)
        
        return wrapper
    return decorator


def track_mcp_operation(operation_type: str, operation: str):
    """Декоратор для отслеживания MCP операций"""
    return monitor_mcp_operation(operation_type, operation)


# Вспомогательные функции
def create_service_info() -> Dict[str, Any]:
    """Создание информации о сервисе"""
    config = get_config()
    return {
        'service_name': config.prometheus.service_name,
        'version': '1.0.0',
        'environment': config.environment.value,
        'monitoring_enabled': {
            'prometheus': config.prometheus.enabled,
            'sentry': config.sentry.enabled,
            'alerts': config.alerts.enabled,
            'opentelemetry': config.opentelemetry.enabled
        }
    }


def export_config(config_file: str):
    """Экспорт конфигурации в файл"""
    from .config import save_config
    config = get_config()
    save_config(config, config_file)


# Автоматическая инициализация при импорте
def _auto_init():
    """Автоматическая инициализация"""
    try:
        # Проверка переменной окружения для автоинициализации
        if os.getenv('AUTO_INIT_MONITORING', 'true').lower() == 'true':
            init_monitoring()
    except Exception as e:
        logger.error(f"Ошибка автоинициализации мониторинга: {e}")


import os

if __name__ != '__main__':
    _auto_init()