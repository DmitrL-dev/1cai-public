import time
from threading import Lock
from typing import Any, Dict

from src.config import settings
from src.resilience.error_recovery import CircuitBreaker


class ResourceManager:
    """
    Manages resources, statistics, and circuit breakers for EmbeddingService.
    """

    def __init__(self):
        self.device_stats = {
            "cpu_requests": 0,
            "gpu_requests": 0,
            "hybrid_requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "total_tokens_processed": 0,
        }
        self._stats_lock = Lock()

        self._device_performance = {
            "cpu": {"avg_time": 0.0, "request_count": 0, "last_update": time.time()},
            "gpu": {"avg_time": 0.0, "request_count": 0, "last_update": time.time()},
        }
        self._performance_lock = Lock()

        self._gpu_circuit_breaker = CircuitBreaker(
            failure_threshold=settings.embedding_gpu_cb_threshold,
            recovery_timeout=settings.embedding_gpu_cb_timeout,
            expected_exception=Exception,
        )
        self._cpu_circuit_breaker = CircuitBreaker(
            failure_threshold=settings.embedding_cpu_cb_threshold,
            recovery_timeout=settings.embedding_cpu_cb_timeout,
            expected_exception=Exception,
        )

    def update_stats(self, device: str, tokens: int = 0, cache_hit: bool = False):
        with self._stats_lock:
            if cache_hit:
                self.device_stats["cache_hits"] += 1
            else:
                self.device_stats["cache_misses"] += 1
                if device == "gpu":
                    self.device_stats["gpu_requests"] += 1
                elif device == "cpu":
                    self.device_stats["cpu_requests"] += 1
                elif device == "hybrid":
                    self.device_stats["hybrid_requests"] += 1

                self.device_stats["total_tokens_processed"] += tokens

    def update_performance(self, device: str, duration: float, items_count: int):
        if items_count == 0:
            return
        with self._performance_lock:
            if device not in self._device_performance:
                return
            perf = self._device_performance[device]
            time_per_item = duration / items_count
            alpha = 0.3
            if perf["request_count"] == 0:
                perf["avg_time"] = time_per_item
            else:
                perf["avg_time"] = (
                    alpha * time_per_item + (1 - alpha) * perf["avg_time"]
                )
            perf["request_count"] += 1
            perf["last_update"] = time.time()

    def get_circuit_breaker(self, device: str) -> CircuitBreaker:
        if device == "gpu":
            return self._gpu_circuit_breaker
        return self._cpu_circuit_breaker

    def get_stats(self) -> Dict[str, Any]:
        with self._stats_lock:
            return self.device_stats.copy()
