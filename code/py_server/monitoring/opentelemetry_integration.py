
"""
Интеграция с OpenTelemetry для распределенной трассировки, метрик и логирования.
Поддержка Jaeger, Zipkin и других экспортеров.
"""

import logging
import os
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Dict, Optional

from opentelemetry import metrics, trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.exporter.otlp.proto.grpc.log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import \
    OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import \
    OTLPSpanExporter
from opentelemetry.exporter.zipkin.json import ZipkinExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


class OpenTelemetryIntegration:
    """Класс для интеграции с OpenTelemetry"""
    
    def __init__(self, service_name: str = "mcp_server",
                 service_version: str = "1.0.0",
                 environment: str = "production"):
        """
        Инициализация OpenTelemetry интеграции
        
        Args:
            service_name: Имя сервиса
            service_version: Версия сервиса
            environment: Окружение
        """
        self.service_name = service_name
        self.service_version = service_version
        self.environment = environment
        
        self.tracer_provider: Optional[TracerProvider] = None
        self.meter_provider: Optional[MeterProvider] = None
        self.log_provider: Optional[LoggerProvider] = None
        self.tracer = None
        self.meter = None
        self.logger = None
        
        self._initialized = False
        
        # Загрузка конфигурации
        self._load_config()
        
    def _load_config(self):
        """Загрузка конфигурации из переменных окружения"""
        self.jaeger_endpoint = os.getenv('JAEGER_ENDPOINT')
        self.zipkin_endpoint = os.getenv('ZIPKIN_ENDPOINT')
        self.otlp_traces_endpoint = os.getenv('OTEL_EXPORTER_OTLP_TRACES_ENDPOINT')
        self.otlp_metrics_endpoint = os.getenv('OTEL_EXPORTER_OTLP_METRICS_ENDPOINT')
        self.otlp_logs_endpoint = os.getenv('OTEL_EXPORTER_OTLP_LOGS_ENDPOINT')
        self.traces_sample_rate = float(os.getenv('OTEL_TRACES_SAMPLE_RATE', '0.1'))
        
    def initialize(self) -> bool:
        """
        Инициализация OpenTelemetry
        
        Returns:
            True если инициализация успешна
        """
        try:
            self._setup_tracing()
            self._setup_metrics()
            self._setup_logging()
            
            self._initialized = True
            logging.info("OpenTelemetry успешно инициализирован")
            return True
            
        except Exception as e:
            logging.error(f"Ошибка инициализации OpenTelemetry: {e}")
            return False
            
    def _setup_tracing(self):
        """Настройка трассировки"""
        # Создание провайдера трассировки
        self.tracer_provider = TracerProvider(
            resource={
                "service.name": self.service_name,
                "service.version": self.service_version,
                "deployment.environment": self.environment
            }
        )
        
        # Настройка sampler
        from opentelemetry.sdk.trace.sampling import TraceIdRatioBased
        sampler = TraceIdRatioBased(self.traces_sample_rate)
        self.tracer_provider.set_sampler(sampler)
        
        # Добавление экспортеров трассировки
        if self.jaeger_endpoint:
            jaeger_exporter = JaegerExporter(
                agent_host_name="localhost",
                agent_port=6831
            )
            span_processor = BatchSpanProcessor(jaeger_exporter)
            self.tracer_provider.add_span_processor(span_processor)
            
        if self.zipkin_endpoint:
            zipkin_exporter = ZipkinExporter(
                endpoint=self.zipkin_endpoint
            )
            span_processor = BatchSpanProcessor(zipkin_exporter)
            self.tracer_provider.add_span_processor(span_processor)
            
        if self.otlp_traces_endpoint:
            otlp_exporter = OTLPSpanExporter(
                endpoint=self.otlp_traces_endpoint,
                timeout=10
            )
            span_processor = BatchSpanProcessor(otlp_exporter)
            self.tracer_provider.add_span_processor(span_processor)
            
        # Установка глобального провайдера
        trace.set_tracer_provider(self.tracer_provider)
        self.tracer = trace.get_tracer(
            self.service_name,
            self.service_version
        )
        
    def _setup_metrics(self):
        """Настройка метрик"""
        # Создание провайдера метрик
        self.meter_provider = MeterProvider(
            resource={
                "service.name": self.service_name,
                "service.version": self.service_version,
                "deployment.environment": self.environment
            }
        )
        
        # Настройка экспортера метрик
        if self.otlp_metrics_endpoint:
            metric_reader = PeriodicExportingMetricReader(
                exporter=OTLPMetricExporter(
                    endpoint=self.otlp_metrics_endpoint,
                    timeout=10
                ),
                export_interval_millis=15000
            )
            self.meter_provider.add_metric_reader(metric_reader)
            
        # Установка глобального провайдера
        metrics.set_meter_provider(self.meter_provider)
        self.meter = metrics.get_meter(
            self.service_name,
            self.service_version
        )
        
    def _setup_logging(self):
        """Настройка логирования"""
        # Создание провайдера логов
        self.log_provider = LoggerProvider(
            resource={
                "service.name": self.service_name,
                "service.version": self.service_version,
                "deployment.environment": self.environment
            }
        )
        
        # Настройка экспортера логов
        if self.otlp_logs_endpoint:
            log_processor = BatchLogProcessor(
                exporter=OTLPLogExporter(
                    endpoint=self.otlp_logs_endpoint,
                    timeout=10
                )
            )
            self.log_provider.add_log_processor(log_processor)
            
        # Установка глобального провайдера
        from opentelemetry._logs import set_logger_provider
        set_logger_provider(self.log_provider)
        
        # Создание логгера
        self.logger = self.log_provider.get_logger("mcp_server")
        
    @contextmanager
    def trace_operation(self, operation_name: str, 
                       attributes: Optional[Dict[str, Any]] = None):
        """
        Контекстный менеджер для трассировки операций
        
        Args:
            operation_name: Название операции
            attributes: Атрибуты span
        """
        if not self._initialized:
            yield
            return
            
        with self.tracer.start_as_current_span(operation_name) as span:
            if attributes:
                for key, value in attributes.items():
                    span.set_attribute(key, str(value))
                    
            try:
                yield span
                span.set_status(trace.Status(trace.StatusCode.OK))
            except Exception as e:
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                span.set_attribute("error", True)
                span.set_attribute("error.message", str(e))
                raise
                
    def create_counter(self, name: str, description: str, unit: str = "1"):
        """Создание счетчика"""
        if not self._initialized:
            return None
        return self.meter.create_counter(name, description, unit)
        
    def create_histogram(self, name: str, description: str, unit: str = "s"):
        """Создание гистограммы"""
        if not self._initialized:
            return None
        return self.meter.create_histogram(name, description, unit)
        
    def create_gauge(self, name: str, description: str, unit: str = "1"):
        """Создание gauge"""
        if not self._initialized:
            return None
        return self.meter.create_up_down_counter(name, description, unit)
        
    def log_info(self, message: str, **attributes):
        """Логирование информационного сообщения"""
        if not self._initialized:
            return
        self.logger.info(message, extra=attributes)
        
    def log_error(self, message: str, **attributes):
        """Логирование ошибки"""
        if not self._initialized:
            return
        self.logger.error(message, extra=attributes)
        
    def set_correlation_attributes(self, span, correlation_id: str):
        """Установка атрибутов корреляции"""
        if span and correlation_id:
            span.set_attribute("correlation.id", correlation_id)
            
    def instrument_fastapi(self, app):
        """Автоматическая инструментация FastAPI приложения"""
        try:
            FastAPIInstrumentor.instrument_app(app)
            logging.info("FastAPI автоматически инструментирован")
        except Exception as e:
            logging.error(f"Ошибка инструментации FastAPI: {e}")
            
    def instrument_requests(self):
        """Автоматическая инструментация библиотеки requests"""
        try:
            RequestsInstrumentor().instrument()
            logging.info("Requests библиотека автоматически инструментирована")
        except Exception as e:
            logging.error(f"Ошибка инструментации Requests: {e}")
            
    def instrument_sqlalchemy(self, engine):
        """Автоматическая инструментация SQLAlchemy"""
        try:
            SQLAlchemyInstrumentor.instrument(engine=engine)
            logging.info("SQLAlchemy автоматически инструментирован")
        except Exception as e:
            logging.error(f"Ошибка инструментации SQLAlchemy: {e}")


# Глобальный экземпляр интеграции
_global_otel: Optional[OpenTelemetryIntegration] = None


def get_otel_integration() -> OpenTelemetryIntegration:
    """Получение глобального экземпляра OpenTelemetry интеграции"""
    global _global_otel
    if _global_otel is None:
        _global_otel = OpenTelemetryIntegration()
    return _global_otel


def init_opentelemetry(service_name: str = "mcp_server",
                     service_version: str = "1.0.0",
                     environment: str = "production") -> OpenTelemetryIntegration:
    """
    Инициализация глобальной OpenTelemetry интеграции
    
    Args:
        service_name: Имя сервиса
        service_version: Версия сервиса
        environment: Окружение
        
    Returns:
        Экземпляр OpenTelemetryIntegration
    """
    global _global_otel
    _global_otel = OpenTelemetryIntegration(
        service_name=service_name,
        service_version=service_version,
        environment=environment
    )
    _global_otel.initialize()
    return _global_otel


# Декораторы для удобного использования
def otel_trace(operation_name: str, attributes: Optional[Dict[str, Any]] = None):
    """Декоратор для создания trace операции"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            otel = get_otel_integration()
            correlation_id = kwargs.get('correlation_id')
            
            with otel.trace_operation(operation_name, attributes) as span:
                if correlation_id:
                    otel.set_correlation_attributes(span, correlation_id)
                    
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if span:
                        span.set_attribute("exception.type", type(e).__name__)
                        span.set_attribute("exception.message", str(e))
                    raise
                    
        return wrapper
    return decorator


def otel_instrument_fastapi():
    """Декоратор для автоматической инструментации FastAPI"""
    def decorator(cls):
        if hasattr(cls, '__bases__'):  # Проверка что это класс
            otel = get_otel_integration()
            otel.instrument_fastapi(cls)
        return cls
    return decorator


# Интеграция с Prometheus метриками
class PrometheusOpenTelemetryBridge:
    """Мост между Prometheus метриками и OpenTelemetry"""
    
    def __init__(self, otel_integration: OpenTelemetryIntegration):
        self.otel = otel_integration
        self.prometheus_counters = {}
        self.prometheus_histograms = {}
        
    def export_prometheus_to_otel(self, prometheus_metrics):
        """Экспорт Prometheus метрик в OpenTelemetry"""
        # Здесь можно реализовать экспорт Prometheus метрик в OpenTelemetry
        # Например, создавать соответствующие счетчики и гистограммы


# Автоматическая инициализация OpenTelemetry
def auto_init_opentelemetry():
    """Автоматическая инициализация OpenTelemetry"""
    if os.getenv('OTEL_AUTO_INIT', 'true').lower() == 'true':
        otel = get_otel_integration()
        if not otel._initialized:
            otel.initialize()
            
            # Автоматическая инструментация популярных библиотек
            try:
                otel.instrument_requests()
            except Exception:
                pass
                
            return True
    return False


# Инициализация при импорте модуля
if __name__ != '__main__':
    auto_init_opentelemetry()