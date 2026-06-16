
"""
Performance Monitoring
Версия: 2.1.0

Улучшения:
- Structured logging
- Улучшена обработка ошибок

Мониторинг производительности системы в реальном времени
"""

import time
from datetime import datetime
from functools import wraps
from typing import Any, Dict

from src.utils.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


class PerformanceMonitor:
    """
    Performance monitoring и metrics collection

    Собирает:
    - Request latency
    - Throughput (RPS)
    - Error rates
    - Cache hit rates
    - Database query times
    """

    def __init__(self):
        self.metrics = {
            "requests_total": 0,
            "requests_success": 0,
            "requests_error": 0,
            "total_latency_ms": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "db_queries": 0,
            "db_query_time_ms": 0,
        }

        self.latency_buckets = {
            "<100ms": 0,
            "100-500ms": 0,
            "500ms-1s": 0,
            "1s-5s": 0,
            ">5s": 0,
        }
        self.latency_history: list[float] = []

    def track_request(self, latency_ms: float, success: bool = True):
        """Трекинг HTTP request с input validation"""
        # Input validation
        if not isinstance(latency_ms, (int, float)) or latency_ms < 0:
            logger.warning(
                "Invalid latency_ms in track_request",
                extra={
                    "latency_ms": latency_ms,
                    "latency_type": type(latency_ms).__name__,
                },
            )
            return

        if not isinstance(success, bool):
            logger.warning(
                "Invalid success in track_request",
                extra={"success": success, "success_type": type(success).__name__},
            )
            success = True  # Default to True

        # Limit history size to prevent memory issues
        max_history_size = 10000
        if len(self.latency_history) >= max_history_size:
            # Keep only recent entries
            self.latency_history = self.latency_history[-max_history_size // 2 :]
            logger.debug(
                "Latency history truncated", extra={"max_size": max_history_size}
            )

        self.metrics["requests_total"] += 1

        if success:
            self.metrics["requests_success"] += 1
        else:
            self.metrics["requests_error"] += 1

        self.metrics["total_latency_ms"] += latency_ms
        self.latency_history.append(latency_ms)

        # Buckets
        if latency_ms < 100:
            self.latency_buckets["<100ms"] += 1
        elif latency_ms < 500:
            self.latency_buckets["100-500ms"] += 1
        elif latency_ms < 1000:
            self.latency_buckets["500ms-1s"] += 1
        elif latency_ms < 5000:
            self.latency_buckets["1s-5s"] += 1
        else:
            self.latency_buckets[">5s"] += 1

    def track_cache(self, hit: bool):
        """Трекинг cache operations с input validation"""
        if not isinstance(hit, bool):
            logger.warning(
                "Invalid hit in track_cache",
                extra={"hit": hit, "hit_type": type(hit).__name__},
            )
            return

        if hit:
            self.metrics["cache_hits"] += 1
        else:
            self.metrics["cache_misses"] += 1

    def track_db_query(self, duration_ms: float):
        """Трекинг database queries с input validation"""
        if not isinstance(duration_ms, (int, float)) or duration_ms < 0:
            logger.warning(
                "Invalid duration_ms in track_db_query",
                extra={
                    "duration_ms": duration_ms,
                    "duration_type": type(duration_ms).__name__,
                },
            )
            return

        self.metrics["db_queries"] += 1
        self.metrics["db_query_time_ms"] += duration_ms

    def get_metrics(self) -> Dict[str, Any]:
        """Получение текущих метрик"""

        total_requests = self.metrics["requests_total"]

        return {
            "requests": {
                "total": total_requests,
                "success": self.metrics["requests_success"],
                "error": self.metrics["requests_error"],
                "error_rate": self.metrics["requests_error"] / max(total_requests, 1),
            },
            "latency": {
                "avg_ms": self.metrics["total_latency_ms"] / max(total_requests, 1),
                "p50": self._calculate_percentile(50),
                "p95": self._calculate_percentile(95),
                "p99": self._calculate_percentile(99),
                "buckets": self.latency_buckets,
            },
            "cache": {
                "hits": self.metrics["cache_hits"],
                "misses": self.metrics["cache_misses"],
                "hit_rate": self.metrics["cache_hits"]
                / max(self.metrics["cache_hits"] + self.metrics["cache_misses"], 1),
            },
            "database": {
                "queries": self.metrics["db_queries"],
                "avg_query_time_ms": self.metrics["db_query_time_ms"]
                / max(self.metrics["db_queries"], 1),
            },
            "timestamp": datetime.now().isoformat(),
        }

    def _calculate_percentile(self, percentile: int) -> float:
        """
        Расчет REAL percentile из latency buckets

        Args:
            percentile: Percentile to calculate (50, 95, 99)

        Returns:
            float: Calculated percentile in milliseconds
        """
        # Input validation
        if not isinstance(percentile, int) or percentile < 0 or percentile > 100:
            logger.warning(
                "Invalid percentile in _calculate_percentile",
                extra={
                    "percentile": percentile,
                    "percentile_type": type(percentile).__name__,
                },
            )
            return 0.0

        if not self.latency_history:
            # Fallback to bucket-based approximation
            return self._calculate_percentile_from_buckets(percentile)

        # Use actual latency values if available
        sorted_latencies = sorted(self.latency_history)
        n = len(sorted_latencies)

        if n == 0:
            return 0.0

        # Calculate index
        index = (percentile / 100) * (n - 1)

        if index.is_integer():
            return float(sorted_latencies[int(index)])

        # Interpolate
        lower_idx = int(index)
        upper_idx = min(lower_idx + 1, n - 1)
        fraction = index - lower_idx

        lower_val = sorted_latencies[lower_idx]
        upper_val = sorted_latencies[upper_idx]

        return float(lower_val + fraction * (upper_val - lower_val))

    def _calculate_percentile_from_buckets(self, percentile: int) -> float:
        """Approximate percentile from histogram buckets с input validation"""
        # Input validation
        if not isinstance(percentile, int) or percentile < 0 or percentile > 100:
            logger.warning(
                "Invalid percentile in _calculate_percentile_from_buckets",
                extra={
                    "percentile": percentile,
                    "percentile_type": type(percentile).__name__,
                },
            )
            return 0.0

        total_requests = sum(self.latency_buckets.values())

        if total_requests == 0:
            return 0.0

        # Find bucket containing the percentile
        target_count = (percentile / 100) * total_requests
        cumulative = 0

        bucket_midpoints = {
            "<100ms": 50,
            "100-500ms": 300,
            "500ms-1s": 750,
            "1s-5s": 3000,
            ">5s": 6000,
        }

        for bucket_name, bucket_midpoint in bucket_midpoints.items():
            cumulative += self.latency_buckets.get(bucket_name, 0)
            if cumulative >= target_count:
                return float(bucket_midpoint)

        return 500.0  # Default to highest bucket

    def reset(self):
        """Сброс всех метрик"""
        self.metrics = {k: 0 for k in self.metrics.keys()}
        self.latency_buckets = {k: 0 for k in self.latency_buckets.keys()}
        self.latency_history.clear()


# Global instance
performance_monitor = PerformanceMonitor()


# Decorator для автоматического трекинга
def track_performance(func):
    """Decorator для трекинга производительности функции"""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        success = True

        try:
            result = await func(*args, **kwargs)
            return result
        except Exception as e:
            success = False
            raise
        finally:
            latency_ms = (time.time() - start_time) * 1000
            performance_monitor.track_request(latency_ms, success)

    return wrapper
