"""
Metrics Service
"""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from src.infrastructure.logging.structured_logging import StructuredLogger
from src.modules.metrics.domain.models import (
    MetricCollectionRequest,
    MetricRecord,
)

logger = StructuredLogger(__name__).logger


class MetricsService:
    """Service for metrics management (Singleton)"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MetricsService, cls).__new__(cls)
            # Global storage (in-memory)
            cls._instance.metrics_storage: List[MetricRecord] = []
            cls._instance.performance_metrics: Dict[str, List[float]] = {}
        return cls._instance

    def collect_metrics(self, request: MetricCollectionRequest) -> Dict[str, Any]:
        """Collect metrics from services"""
        try:
            timestamp = request.timestamp or datetime.now()

            # Process numeric metrics
            processed_count = 0
            for name, value in request.metrics.items():
                if isinstance(value, (int, float)):
                    record = MetricRecord(
                        metric_type=request.event,
                        service_name=request.service,
                        value=float(value),
                        timestamp=timestamp,
                        tags={"metric_name": name},
                    )
                    self.metrics_storage.append(record)

                    # Update performance metrics if applicable
                    if name in ["latency", "duration", "processing_time"]:
                        if request.service not in self.performance_metrics:
                            self.performance_metrics[request.service] = []
                        self.performance_metrics[request.service].append(float(value))

                    processed_count += 1

            logger.info(
                "Metrics collected",
                extra={
                    "service": request.service,
                    "event": request.event,
                    "count": processed_count,
                },
            )

            return {
                "success": True,
                "processed": processed_count,
                "timestamp": datetime.now(),
            }
        except Exception as e:
            logger.error(f"Error collecting metrics: {e}", exc_info=True)
            raise

    def get_metrics(
        self,
        service: Optional[str] = None,
        metric_type: Optional[str] = None,
        hours_back: int = 24,
        limit: int = 1000,
    ) -> List[MetricRecord]:
        """Get metrics with filtering"""
        start_time = datetime.now() - timedelta(hours=hours_back)
        filtered = [m for m in self.metrics_storage if m.timestamp >= start_time]

        if service:
            filtered = [m for m in filtered if m.service_name == service]

        if metric_type:
            filtered = [m for m in filtered if m.metric_type == metric_type]

        # Sort by timestamp desc and limit
        filtered.sort(key=lambda x: x.timestamp, reverse=True)
        return filtered[:limit]

    def get_performance_metrics(self, service_name: str, hours_back: int = 1) -> Dict[str, Any]:
        """Get performance metrics for service"""
        start_time = datetime.now() - timedelta(hours=hours_back)
        metrics = [
            m
            for m in self.metrics_storage
            if m.service_name == service_name
            and m.timestamp >= start_time
            and m.tags.get("metric_name") in ["latency", "duration", "processing_time"]
        ]

        if not metrics:
            return {"service": service_name, "has_data": False}

        values = [m.value for m in metrics]
        avg_val = sum(values) / len(values)
        max_val = max(values)
        min_val = min(values)

        return {
            "service": service_name,
            "has_data": True,
            "count": len(values),
            "avg_latency": avg_val,
            "max_latency": max_val,
            "min_latency": min_val,
            "p95": sorted(values)[int(len(values) * 0.95)],
            "period": f"{hours_back}h",
        }

    def get_dashboard_overview(self) -> Dict[str, Any]:
        """Get dashboard overview"""
        now = datetime.now()
        last_24h = now - timedelta(hours=24)

        recent_metrics = [m for m in self.metrics_storage if m.timestamp >= last_24h]

        services = set(m.service_name for m in recent_metrics)
        events_count = len(recent_metrics)

        # Calculate error rate (if error metrics exist)
        errors = [m for m in recent_metrics if "error" in m.metric_type.lower()
                                                                              or "fail" in m.metric_type.lower()]
        error_rate = (len(errors) / events_count * 100) if events_count > 0 else 0

        return {
            "total_events_24h": events_count,
            "active_services": list(services),
            "error_rate": round(error_rate, 2),
            "last_update": now,
            "storage_size": len(self.metrics_storage),
        }

    def get_alerts(self) -> List[Dict[str, Any]]:
        """Get active alerts"""
        alerts = []
        now = datetime.now()
        last_1h = now - timedelta(hours=1)

        # Check error spikes
        recent_errors = [
            m
            for m in self.metrics_storage
            if m.timestamp >= last_1h and ("error" in m.metric_type.lower() or "fail" in m.metric_type.lower())
        ]

        if len(recent_errors) > 100:  # Threshold
            alerts.append(
                {
                    "level": "critical",
                    "type": "error_spike",
                    "message": f"High error rate detected: {len(recent_errors)} errors in last hour",
                    "timestamp": now,
                }
            )

        # Check latency spikes
        for service, values in self.performance_metrics.items():
            if values and len(values) > 10:
                recent_values = values[-10:]
                avg_latency = sum(recent_values) / len(recent_values)
                if avg_latency > 1000:  # 1s threshold
                    alerts.append(
                        {
                            "level": "warning",
                            "type": "high_latency",
                            "service": service,
                            "message": f"High latency detected for {service}: {avg_latency:.2f}ms",
                            "timestamp": now,
                        }
                    )

        return alerts

    def clear_old_metrics(self, days_back: int = 30) -> int:
        """Clear old metrics"""
        cutoff = datetime.now() - timedelta(days=days_back)
        initial_count = len(self.metrics_storage)
        self.metrics_storage = [
            m for m in self.metrics_storage if m.timestamp >= cutoff]
        cleared_count = initial_count - len(self.metrics_storage)

        # Also clear performance metrics cache
        for service in self.performance_metrics:
            # Keep only last 1000 values
            if len(self.performance_metrics[service]) > 1000:
                self.performance_metrics[service] = self.performance_metrics[service][-1000:]

        return cleared_count

    def get_stats(self) -> Dict[str, Any]:
        """Get general stats"""
        return {
            "total_records": len(self.metrics_storage),
            "services_tracked": len(self.performance_metrics),
            # Rough estimate
            "memory_usage_approx": f"{len(self.metrics_storage) * 100 / 1024 / 1024:.2f} MB",
        }
