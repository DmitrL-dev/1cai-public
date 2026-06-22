"""
OpenTelemetry Setup for Distributed Tracing
Версия: 2.1.0

Улучшения:
- Structured logging
- Улучшена обработка ошибок

Best Practices from top companies (Google, Microsoft, AWS, etc.)

Features:
- Automatic instrumentation for FastAPI, asyncpg, httpx, redis
- Export to Prometheus, Jaeger, OTLP
- Custom spans for business logic
- Correlation IDs for request tracking
"""

import os
from typing import Optional

from src.infrastructure.logging.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger

# Try to import OpenTelemetry (optional dependency)
try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.exporter.prometheus import PrometheusMetricReader
    from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from opentelemetry.instrumentation.redis import RedisInstrumentor
    from opentelemetry.metrics import set_meter_provider
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

    OPENTELEMETRY_AVAILABLE = True
except ImportError:
    OPENTELEMETRY_AVAILABLE = False
    logger.warning(
        "OpenTelemetry not installed. Install with: pip install opentelemetry-api opentelemetry-sdk",
        extra={"source_module": "opentelemetry_setup"},
    )


def setup_opentelemetry(
    service_name: str = "1c-ai-stack",
    service_version: str = "2.2.0",
    otlp_endpoint: Optional[str] = None,
    enable_console_exporter: bool = False,
) -> bool:
    """
    Setup OpenTelemetry for distributed tracing

    Args:
        service_name: Name of the service
        service_version: Version of the service
        otlp_endpoint: OTLP endpoint URL (e.g., "http://jaeger:4317")
        enable_console_exporter: Enable console exporter for debugging

    Returns:
        bool: True if setup successful, False otherwise
    """
    if not OPENTELEMETRY_AVAILABLE:
        logger.warning(
            "OpenTelemetry not available, skipping setup",
            extra={"service_name": service_name, "service_version": service_version},
        )
        return False

    try:
        # Create resource with service information
        resource = Resource.create(
            {
                "service.name": service_name,
                "service.version": service_version,
                "service.namespace": os.getenv("SERVICE_NAMESPACE", "production"),
            }
        )

        # Setup tracer provider
        tracer_provider = TracerProvider(resource=resource)

        # Add span processors
        if otlp_endpoint:
            otlp_exporter = OTLPSpanExporter(
                endpoint=otlp_endpoint,
                insecure=os.getenv("OTLP_INSECURE", "false").lower() == "true",
            )
            tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
            logger.info(
                f"✅ OTLP exporter configured: {otlp_endpoint}",
                extra={
                    "otlp_endpoint": otlp_endpoint,
                    "service_name": service_name,
                    "service_version": service_version,
                },
            )

        if (
            enable_console_exporter
            or os.getenv("OTEL_CONSOLE_EXPORTER", "false").lower() == "true"
        ):
            console_exporter = ConsoleSpanExporter()
            tracer_provider.add_span_processor(BatchSpanProcessor(console_exporter))
            logger.info(
                "✅ Console exporter enabled", extra={"service_name": service_name}
            )

        trace.set_tracer_provider(tracer_provider)

        # Setup metrics
        metric_reader = PrometheusMetricReader()
        meter_provider = MeterProvider(
            resource=resource,
            metric_readers=[metric_reader],
        )
        set_meter_provider(meter_provider)

        logger.info(
            "✅ OpenTelemetry setup completed",
            extra={
                "service_name": service_name,
                "service_version": service_version,
                "otlp_configured": bool(otlp_endpoint),
                "console_exporter": enable_console_exporter,
            },
        )
        return True

    except Exception as e:
        logger.error(
            f"Failed to setup OpenTelemetry: {e}",
            extra={
                "service_name": service_name,
                "service_version": service_version,
                "error_type": type(e).__name__,
            },
            exc_info=True,
        )
        return False


def instrument_fastapi_app(app):
    """
    Instrument FastAPI application with OpenTelemetry

    Args:
        app: FastAPI application instance
    """
    if not OPENTELEMETRY_AVAILABLE:
        return

    try:
        FastAPIInstrumentor.instrument_app(app)
        logger.info(
            "✅ FastAPI instrumented with OpenTelemetry",
            extra={"app_name": getattr(app, "title", "unknown")},
        )
    except Exception as e:
        logger.error(
            f"Failed to instrument FastAPI: {e}",
            extra={"error_type": type(e).__name__},
            exc_info=True,
        )


def instrument_asyncpg():
    """Instrument asyncpg with OpenTelemetry"""
    if not OPENTELEMETRY_AVAILABLE:
        return

    try:
        AsyncPGInstrumentor().instrument()
        logger.info("✅ asyncpg instrumented with OpenTelemetry")
    except Exception as e:
        logger.error(
            f"Failed to instrument asyncpg: {e}",
            extra={"error_type": type(e).__name__},
            exc_info=True,
        )


def instrument_httpx():
    """Instrument httpx with OpenTelemetry"""
    if not OPENTELEMETRY_AVAILABLE:
        return

    try:
        HTTPXClientInstrumentor().instrument()
        logger.info("✅ httpx instrumented with OpenTelemetry")
    except Exception as e:
        logger.error(
            f"Failed to instrument httpx: {e}",
            extra={"error_type": type(e).__name__},
            exc_info=True,
        )


def instrument_redis():
    """Instrument redis with OpenTelemetry"""
    if not OPENTELEMETRY_AVAILABLE:
        return

    try:
        RedisInstrumentor().instrument()
        logger.info("✅ redis instrumented with OpenTelemetry")
    except Exception as e:
        logger.error(
            f"Failed to instrument redis: {e}",
            extra={"error_type": type(e).__name__},
            exc_info=True,
        )


def get_tracer(name: str):
    """
    Get tracer for custom spans

    Usage:
        tracer = get_tracer(__name__)
        with tracer.start_as_current_span("custom_operation"):
            # Your code here
            pass
    """
    if not OPENTELEMETRY_AVAILABLE:
        # Return no-op tracer
        class NoOpTracer:
            def start_as_current_span(self, *args, **kwargs):
                return NoOpSpan()

        class NoOpSpan:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

        return NoOpTracer()

    return trace.get_tracer(name)


def get_meter(name: str):
    """
    Get meter for custom metrics

    Usage:
        meter = get_meter(__name__)
        counter = meter.create_counter("requests_total")
        counter.add(1, {"endpoint": "/api/test"})
    """
    if not OPENTELEMETRY_AVAILABLE:
        # Return no-op meter
        class NoOpMeter:
            def create_counter(self, *args, **kwargs):
                return NoOpCounter()

            def create_histogram(self, *args, **kwargs):
                return NoOpHistogram()

        class NoOpCounter:
            def add(self, *args, **kwargs):
                pass

        class NoOpHistogram:
            def record(self, *args, **kwargs):
                pass

        return NoOpMeter()

    from opentelemetry.metrics import get_meter

    return get_meter(name)
