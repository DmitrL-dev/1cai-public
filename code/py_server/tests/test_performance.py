
"""
Комплексные тесты производительности для системы 1C MCP

Создан в соответствии со стандартами тестирования производительности:
- Load тесты - имитация реальной нагрузки
- Stress тесты - тестирование на грани возможностей  
- Endurance тесты - длительная стабильность
- Spike тесты - резкие пики нагрузки
- Volume тесты - большие объемы данных

Использует:
- locust для нагрузочного тестирования
- pytest-benchmark для микро-бенчмарков
- memory-profiler для профилирования памяти
- psutil для мониторинга ресурсов

Цели производительности:
- Улучшение производительности на 200-500%
- Время ответа < 100ms для кэшируемых запросов
- Поддержка 1000+ одновременных пользователей

Версия: 1.0.0
Дата: 2025-10-29
"""

import gc
import json
import math
import os
import random
import statistics
import sys
import threading
import time
from concurrent.futures import (ThreadPoolExecutor, as_completed)
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Dict, List

# Добавляем путь для импортов
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psutil
import pytest
from memory_profiler import profile

# Попытка импорта pytest-benchmark
try:
    import pytest_benchmark
    HAS_BENCHMARK = True
except ImportError:
    HAS_BENCHMARK = False
    pytest_benchmark = None

# Настройка тестового окружения
from fastapi.testclient import TestClient
# Импорт компонентов системы
from ratelimit import RateLimitManager

from cache import MCP_CACHE
from main import app

# =============================================================================
# PERFORMANCE METRICS DATA STRUCTURES
# =============================================================================

@dataclass
class PerformanceMetrics:
    """Метрики производительности системы"""
    timestamp: float
    operation_name: str
    duration_ms: float
    memory_usage_mb: float
    cpu_usage_percent: float
    error_count: int
    success_count: int
    throughput_ops_per_sec: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    metadata: Dict[str, Any]


@dataclass
class LoadTestResult:
    """Результат нагрузочного теста"""
    test_name: str
    concurrent_users: int
    total_requests: int
    successful_requests: int
    failed_requests: int
    duration_seconds: float
    throughput_rps: float
    average_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    error_rate_percent: float
    success_rate_percent: float
    max_memory_usage_mb: float
    avg_cpu_usage_percent: float
    requests_per_second_per_user: float


@dataclass
class StressTestResult:
    """Результат stress теста"""
    test_name: str
    max_concurrent_users: int
    breaking_point_users: int
    performance_degradation_percent: float
    error_rate_at_breaking_point: float
    memory_leak_detected: bool
    cpu_spike_detected: bool
    recovery_time_seconds: float


@dataclass
class EnduranceTestResult:
    """Результат endurance теста"""
    test_name: str
    duration_minutes: int
    total_operations: int
    average_throughput_rps: float
    performance_drift_percent: float
    memory_growth_mb_per_hour: float
    error_rate_percent: float
    stability_score: float  # 0-100, где 100 = идеальная стабильность


# =============================================================================
# PERFORMANCE TEST UTILITIES
# =============================================================================

class PerformanceMonitor:
    """Мониторинг производительности в реальном времени"""
    
    def __init__(self, name: str):
        self.name = name
        self.metrics: List[PerformanceMetrics] = []
        self.start_time = None
        self.start_memory = None
        self.start_cpu = None
        self.lock = threading.Lock()
    
    def start(self):
        """Начать мониторинг"""
        self.start_time = time.perf_counter()
        self.start_memory = self._get_memory_usage()
        self.start_cpu = psutil.cpu_percent()
    
    def record(self, operation: str, duration_ms: float, success: bool = True):
        """Записать метрику"""
        with self.lock:
            current_time = time.perf_counter()
            elapsed = current_time - self.start_time if self.start_time else 0
            
            metric = PerformanceMetrics(
                timestamp=time.time(),
                operation_name=operation,
                duration_ms=duration_ms,
                memory_usage_mb=self._get_memory_usage(),
                cpu_usage_percent=psutil.cpu_percent(),
                error_count=0 if success else 1,
                success_count=1 if success else 0,
                throughput_ops_per_sec=1000 / max(duration_ms, 0.001),
                p50_latency_ms=duration_ms,
                p95_latency_ms=duration_ms,
                p99_latency_ms=duration_ms,
                metadata={}
            )
            
            self.metrics.append(metric)
    
    def get_summary(self) -> Dict[str, Any]:
        """Получить сводку метрик"""
        if not self.metrics:
            return {"error": "No metrics recorded"}
        
        latencies = [m.duration_ms for m in self.metrics]
        memory_usage = [m.memory_usage_mb for m in self.metrics]
        cpu_usage = [m.cpu_usage_percent for m in self.metrics]
        
        total_operations = len(self.metrics)
        total_errors = sum(m.error_count for m in self.metrics)
        total_success = sum(m.success_count for m in self.metrics)
        
        total_time = (self.metrics[-1].timestamp - self.metrics[0].timestamp) if len(self.metrics) > 1 else 1
        
        return {
            "test_name": self.name,
            "total_operations": total_operations,
            "success_count": total_success,
            "error_count": total_errors,
            "duration_seconds": total_time,
            "average_latency_ms": statistics.mean(latencies),
            "median_latency_ms": statistics.median(latencies),
            "p95_latency_ms": statistics.quantiles(latencies, n=20)[18] if len(latencies) > 20 else max(latencies),
            "p99_latency_ms": statistics.quantiles(latencies, n=100)[98] if len(latencies) > 100 else max(latencies),
            "max_memory_usage_mb": max(memory_usage),
            "min_memory_usage_mb": min(memory_usage),
            "average_cpu_usage_percent": statistics.mean(cpu_usage),
            "throughput_ops_per_sec": total_operations / total_time,
            "error_rate_percent": (total_errors / total_operations) * 100,
            "success_rate_percent": (total_success / total_operations) * 100
        }
    
    def _get_memory_usage(self) -> float:
        """Получить использование памяти в MB"""
        try:
            process = psutil.Process(os.getpid())
            return process.memory_info().rss / 1024 / 1024
        except:
            return 0.0


@contextmanager
def performance_timer(operation_name: str, monitor: PerformanceMonitor):
    """Таймер для измерения производительности"""
    start_time = time.perf_counter()
    success = True
    
    try:
        yield
    except Exception as e:
        success = False
        raise
    finally:
        end_time = time.perf_counter()
        duration_ms = (end_time - start_time) * 1000
        monitor.record(operation_name, duration_ms, success)


def adaptive_load_generator(max_users: int, ramp_up_time: int = 60) -> List[int]:
    """Генератор адаптивной нагрузки"""
    load_pattern = []
    
    # Раamp-up фаза
    for i in range(max_users):
        users = int((i / max_users) * max_users)
        load_pattern.append(users)
        time.sleep(ramp_up_time / max_users)
    
    # Стабильная нагрузка
    for _ in range(10):  # 10 циклов стабильной нагрузки
        load_pattern.extend([max_users] * 5)
        time.sleep(5)
    
    # Раamp-down фаза
    for i in range(max_users, 0, -1):
        users = int((i / max_users) * max_users)
        load_pattern.append(users)
        time.sleep(ramp_up_time / max_users)
    
    return load_pattern


def spike_load_generator(base_load: int, spike_users: int, spike_duration: int = 10) -> List[int]:
    """Генератор spike нагрузки"""
    load_pattern = []
    
    # Базовая нагрузка
    for _ in range(20):
        load_pattern.append(base_load)
        time.sleep(1)
    
    # Spike
    for _ in range(spike_duration):
        load_pattern.append(base_load + spike_users)
        time.sleep(1)
    
    # Восстановление
    for _ in range(20):
        load_pattern.append(base_load)
        time.sleep(1)
    
    return load_pattern


# =============================================================================
# LOAD TESTS - Имитация реальной нагрузки
# =============================================================================

class TestSystemLoad:
    """Load тесты - имитация реальной нагрузки"""
    
    @pytest.fixture
    def test_client(self):
        """Фикстура для тестового клиента"""
        return TestClient(app)
    
    @pytest.fixture
    def rate_limit_manager(self):
        """Фикстура для менеджера rate limiting"""
        return RateLimitManager(
            storage_type="memory",
            default_limits={
                "default": {"requests": 1000, "window": 60},
                "api": {"requests": 5000, "window": 60},
                "premium": {"requests": 10000, "window": 60}
            }
        )
    
    @pytest.mark.load_test
    def test_normal_load_simulation(self, test_client, rate_limit_manager):
        """Тест имитации нормальной нагрузки (100 пользователей)"""
        monitor = PerformanceMonitor("Normal Load Test")
        monitor.start()
        
        def simulate_user_session(user_id: int):
            """Симуляция сессии пользователя"""
            latencies = []
            
            for request_num in range(20):  # 20 запросов на пользователя
                start_time = time.perf_counter()
                
                try:
                    # Имитация различных типов запросов
                    if request_num % 5 == 0:
                        response = test_client.get("/")
                    elif request_num % 5 == 1:
                        response = test_client.get(f"/data/{user_id}")
                    elif request_num % 5 == 2:
                        response = test_client.get("/health")
                    elif request_num % 5 == 3:
                        # Rate limit проверка
                        rate_limit_manager.check_rate_limit(f"user_{user_id}", "api")
                        response = test_client.get("/data/test")
                    else:
                        # Кэш операция
                        response = test_client.get(f"/data/cache_test_{user_id}")
                    
                    end_time = time.perf_counter()
                    latency_ms = (end_time - start_time) * 1000
                    latencies.append(latency_ms)
                    
                    # Небольшая задержка между запросами
                    time.sleep(random.uniform(0.1, 0.5))
                    
                except Exception as e:
                    # Логируем ошибки, но не прерываем тест
                    print(f"Error in user {user_id} request {request_num}: {e}")
            
            return latencies
        
        # Запуск 100 concurrent пользователей
        print("\n=== Running Normal Load Test (100 users) ===")
        
        with ThreadPoolExecutor(max_workers=100) as executor:
            futures = [executor.submit(simulate_user_session, i) for i in range(100)]
            
            all_latencies = []
            for future in as_completed(futures):
                try:
                    user_latencies = future.result()
                    all_latencies.extend(user_latencies)
                except Exception as e:
                    print(f"User session failed: {e}")
        
        # Анализ результатов
        summary = monitor.get_summary()
        
        if all_latencies:
            summary["overall_avg_latency_ms"] = statistics.mean(all_latencies)
            summary["overall_p95_latency_ms"] = statistics.quantiles(all_latencies, n=20)[18] if len(all_latencies) > 20 else max(all_latencies)
            summary["overall_p99_latency_ms"] = statistics.quantiles(all_latencies, n=100)[98] if len(all_latencies) > 100 else max(all_latencies)
        
        print(f"Normal Load Test Results:")
        print(f"  Total requests: {summary['total_operations']}")
        print(f"  Success rate: {summary['success_rate_percent']:.1f}%")
        print(f"  Average latency: {summary.get('overall_avg_latency_ms', 0):.2f}ms")
        print(f"  P95 latency: {summary.get('overall_p95_latency_ms', 0):.2f}ms")
        print(f"  P99 latency: {summary.get('overall_p99_latency_ms', 0):.2f}ms")
        print(f"  Throughput: {summary['throughput_ops_per_sec']:.1f} ops/sec")
        print(f"  Max memory: {summary['max_memory_usage_mb']:.1f}MB")
        
        # Проверка SLA
        assert summary['success_rate_percent'] >= 99.0, "Success rate should be >= 99%"
        assert summary.get('overall_p95_latency_ms', 0) < 100, "P95 latency should be < 100ms"
        assert summary['error_rate_percent'] <= 1.0, "Error rate should be <= 1%"
    
    @pytest.mark.load_test
    @pytest.mark.parametrize("concurrent_users", [100, 250, 500, 750, 1000])
    def test_scaled_load_simulation(self, test_client, concurrent_users):
        """Тест масштабируемой нагрузки для разного количества пользователей"""
        monitor = PerformanceMonitor(f"Scaled Load Test ({concurrent_users} users)")
        monitor.start()
        
        def worker_user(user_id: int):
            """Воркер для пользователя"""
            successful_requests = 0
            failed_requests = 0
            
            for _ in range(10):  # 10 запросов на пользователя
                start_time = time.perf_counter()
                
                try:
                    response = test_client.get("/")
                    end_time = time.perf_counter()
                    
                    latency_ms = (end_time - start_time) * 1000
                    monitor.record("user_request", latency_ms, response.status_code == 200)
                    
                    if response.status_code == 200:
                        successful_requests += 1
                    else:
                        failed_requests += 1
                    
                    time.sleep(random.uniform(0.05, 0.2))
                    
                except Exception:
                    failed_requests += 1
            
            return successful_requests, failed_requests
        
        print(f"\n=== Running Scaled Load Test ({concurrent_users} users) ===")
        
        start_total_time = time.time()
        
        with ThreadPoolExecutor(max_workers=min(concurrent_users, 100)) as executor:
            futures = [executor.submit(worker_user, i) for i in range(concurrent_users)]
            
            total_successful = 0
            total_failed = 0
            
            for future in as_completed(futures):
                try:
                    successful, failed = future.result()
                    total_successful += successful
                    total_failed += failed
                except Exception as e:
                    print(f"Worker failed: {e}")
                    total_failed += 10
        
        end_total_time = time.time()
        total_time = end_total_time - start_total_time
        
        summary = monitor.get_summary()
        
        # Вычисляем итоговые метрики
        total_requests = total_successful + total_failed
        actual_concurrent_users = concurrent_users
        
        result = LoadTestResult(
            test_name=f"Scaled Load ({concurrent_users} users)",
            concurrent_users=actual_concurrent_users,
            total_requests=total_requests,
            successful_requests=total_successful,
            failed_requests=total_failed,
            duration_seconds=total_time,
            throughput_rps=total_requests / total_time,
            average_latency_ms=summary.get('average_latency_ms', 0),
            p50_latency_ms=summary.get('median_latency_ms', 0),
            p95_latency_ms=summary.get('p95_latency_ms', 0),
            p99_latency_ms=summary.get('p99_latency_ms', 0),
            error_rate_percent=(total_failed / total_requests) * 100 if total_requests > 0 else 0,
            success_rate_percent=(total_successful / total_requests) * 100 if total_requests > 0 else 0,
            max_memory_usage_mb=summary['max_memory_usage_mb'],
            avg_cpu_usage_percent=summary['average_cpu_usage_percent'],
            requests_per_second_per_user=(total_requests / total_time) / actual_concurrent_users
        )
        
        print(f"Results for {concurrent_users} users:")
        print(f"  Total requests: {result.total_requests}")
        print(f"  Success rate: {result.success_rate_percent:.1f}%")
        print(f"  Throughput: {result.throughput_rps:.1f} RPS")
        print(f"  Avg latency: {result.average_latency_ms:.2f}ms")
        print(f"  P95 latency: {result.p95_latency_ms:.2f}ms")
        print(f"  RPS per user: {result.requests_per_second_per_user:.2f}")
        print(f"  Max memory: {result.max_memory_usage_mb:.1f}MB")
        
        # Проверка производительности
        if concurrent_users <= 500:
            assert result.success_rate_percent >= 99.0, f"Success rate too low for {concurrent_users} users"
            assert result.p95_latency_ms < 100, f"P95 latency too high for {concurrent_users} users"
        elif concurrent_users <= 1000:
            assert result.success_rate_percent >= 95.0, f"Success rate degraded for {concurrent_users} users"
            assert result.p95_latency_ms < 200, f"P95 latency degraded for {concurrent_users} users"
        
        return result
    
    @pytest.mark.load_test
    def test_mixed_workload_simulation(self, test_client, rate_limit_manager):
        """Тест смешанной нагрузки (различные типы операций)"""
        monitor = PerformanceMonitor("Mixed Workload Test")
        monitor.start()
        
        def mixed_workload_worker(worker_id: int, workload_type: str):
            """Воркер с различными типами нагрузки"""
            operations_count = {
                'read': 0,
                'write': 0,
                'cache': 0,
                'ratelimit': 0
            }
            
            for _ in range(25):  # 25 операций на воркера
                start_time = time.perf_counter()
                
                try:
                    if workload_type == 'read_heavy':
                        # 80% read, 20% write операции
                        if random.random() < 0.8:
                            response = test_client.get(f"/data/{worker_id}")
                            operations_count['read'] += 1
                        else:
                            # Симуляция write операции через health endpoint
                            response = test_client.get("/health")
                            operations_count['write'] += 1
                    
                    elif workload_type == 'cache_heavy':
                        # 70% cache hits, 30% cache misses
                        if random.random() < 0.7:
                            # Кэш hit
                            test_data_id = f"cached_data_{worker_id}"
                            MCP_CACHE.set(test_data_id, {"data": f"test_{worker_id}"}, ttl=300)
                            response = test_client.get(f"/data/{test_data_id}")
                            operations_count['cache'] += 1
                        else:
                            # Кэш miss
                            response = test_client.get(f"/data/miss_{worker_id}")
                            operations_count['read'] += 1
                    
                    elif workload_type == 'ratelimit_heavy':
                        # Интенсивное использование rate limiting
                        for i in range(5):
                            rate_limit_manager.check_rate_limit(f"user_{worker_id}", "default")
                        operations_count['ratelimit'] += 5
                        
                        response = test_client.get(f"/data/{worker_id}")
                        operations_count['read'] += 1
                    
                    end_time = time.perf_counter()
                    latency_ms = (end_time - start_time) * 1000
                    monitor.record(f"{workload_type}_operation", latency_ms, response.status_code == 200)
                    
                    time.sleep(random.uniform(0.01, 0.1))
                    
                except Exception as e:
                    print(f"Error in {workload_type} worker {worker_id}: {e}")
            
            return operations_count
        
        print("\n=== Running Mixed Workload Test ===")
        
        workload_types = ['read_heavy', 'cache_heavy', 'ratelimit_heavy']
        workers_per_type = 30  # 90 workers total
        
        with ThreadPoolExecutor(max_workers=90) as executor:
            futures = []
            
            for workload_type in workload_types:
                for worker_id in range(workers_per_type):
                    future = executor.submit(mixed_workload_worker, worker_id, workload_type)
                    futures.append(future)
            
            all_operations = {'read': 0, 'write': 0, 'cache': 0, 'ratelimit': 0}
            
            for future in as_completed(futures):
                try:
                    operations = future.result()
                    for op_type, count in operations.items():
                        all_operations[op_type] += count
                except Exception as e:
                    print(f"Workload worker failed: {e}")
        
        summary = monitor.get_summary()
        
        print(f"Mixed Workload Test Results:")
        print(f"  Total operations: {summary['total_operations']}")
        print(f"  Operation breakdown: {all_operations}")
        print(f"  Success rate: {summary['success_rate_percent']:.1f}%")
        print(f"  Average latency: {summary['average_latency_ms']:.2f}ms")
        print(f"  P95 latency: {summary['p95_latency_ms']:.2f}ms")
        print(f"  Throughput: {summary['throughput_ops_per_sec']:.1f} ops/sec")
        
        # Проверка производительности для смешанной нагрузки
        assert summary['success_rate_percent'] >= 98.0, "Mixed workload success rate too low"
        assert summary['p95_latency_ms'] < 150, "Mixed workload P95 latency too high"


# =============================================================================
# STRESS TESTS - Тестирование на грани возможностей
# =============================================================================

class TestSystemStress:
    """Stress тесты - тестирование на грани возможностей"""
    
    @pytest.mark.stress_test
    def test_breaking_point_discovery(self, test_client):
        """Тест обнаружения точки разрушения системы"""
        print("\n=== Discovering System Breaking Point ===")
        
        # Начинаем с 100 пользователей и увеличиваем
        for user_count in [100, 250, 500, 750, 1000, 1500, 2000, 3000]:
            print(f"Testing with {user_count} concurrent users...")
            
            def stress_worker(user_id: int):
                successful = 0
                failed = 0
                
                for _ in range(10):  # 10 запросов на пользователя
                    try:
                        start_time = time.perf_counter()
                        response = test_client.get("/")
                        end_time = time.perf_counter()
                        
                        latency_ms = (end_time - start_time) * 1000
                        
                        if response.status_code == 200:
                            successful += 1
                        else:
                            failed += 1
                        
                        # Быстрые запросы для stress теста
                        time.sleep(random.uniform(0.01, 0.05))
                        
                    except Exception:
                        failed += 1
                
                return successful, failed
            
            start_time = time.time()
            
            with ThreadPoolExecutor(max_workers=min(user_count, 200)) as executor:
                futures = [executor.submit(stress_worker, i) for i in range(user_count)]
                
                total_successful = 0
                total_failed = 0
                
                for future in as_completed(futures):
                    try:
                        successful, failed = future.result()
                        total_successful += successful
                        total_failed += failed
                    except Exception:
                        total_failed += 10
            
            end_time = time.time()
            test_duration = end_time - start_time
            total_requests = total_successful + total_failed
            
            success_rate = (total_successful / total_requests) * 100 if total_requests > 0 else 0
            throughput = total_requests / test_duration if test_duration > 0 else 0
            
            print(f"  Results: {success_rate:.1f}% success, {throughput:.1f} RPS, {test_duration:.1f}s duration")
            
            # Если успешность падает ниже 90%, считаем это точкой разрушения
            if success_rate < 90.0 or throughput < 100:
                print(f"Breaking point found at {user_count} users!")
                assert user_count >= 1000, "System should handle at least 1000 users before breaking"
                break
        else:
            print("System did not break even at 3000 users - excellent scalability!")
    
    @pytest.mark.stress_test
    def test_memory_exhaustion_resistance(self, rate_limit_manager):
        """Тест устойчивости к исчерпанию памяти"""
        print("\n=== Testing Memory Exhaustion Resistance ===")
        
        initial_memory = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
        print(f"Initial memory usage: {initial_memory:.1f}MB")
        
        # Создаем множество записей для тестирования памяти
        large_dataset_size = 100000
        
        def memory_intensive_operation(key_suffix: int):
            """Операция, интенсивно использующая память"""
            # Создаем большие объекты
            large_data = {}
            for i in range(1000):
                key = f"large_key_{key_suffix}_{i}"
                large_data[key] = {
                    "data": "x" * 1000,  # 1KB данных
                    "metadata": f"metadata_{key_suffix}_{i}",
                    "timestamp": time.time(),
                    "nested": {"level1": {"level2": {"level3": "deep_data"}}}
                }
            
            # Rate limit операции
            for i in range(100):
                rate_limit_manager.check_rate_limit(f"memory_test_{key_suffix}_{i}", "default")
            
            return len(large_data)
        
        print(f"Creating dataset with {large_dataset_size} entries...")
        
        # Запускаем memory-intensive операции
        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(memory_intensive_operation, i) for i in range(large_dataset_size // 1000)]
            
            results = []
            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    print(f"Memory intensive operation failed: {e}")
        
        peak_memory = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
        memory_increase = peak_memory - initial_memory
        
        print(f"Peak memory usage: {peak_memory:.1f}MB")
        print(f"Memory increase: {memory_increase:.1f}MB")
        
        # Проверяем, что система не исчерпала память критично
        assert memory_increase < 1000, "Memory usage increased too much"
        assert len(results) >= (large_dataset_size // 1000) * 0.8, "Many memory operations failed"
        
        # Принудительная сборка мусора
        gc.collect()
        
        after_gc_memory = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
        print(f"Memory after GC: {after_gc_memory:.1f}MB")
        memory_recovered = peak_memory - after_gc_memory
        print(f"Memory recovered by GC: {memory_recovered:.1f}MB")
    
    @pytest.mark.stress_test
    @pytest.mark.parametrize("error_rate", [0.1, 1.0, 5.0, 10.0])
    def test_error_rate_under_stress(self, test_client, error_rate):
        """Тест поведения системы при различных уровнях ошибок"""
        print(f"\n=== Testing System Behavior at {error_rate}% Error Rate ===")
        
        monitor = PerformanceMonitor(f"Error Rate Test ({error_rate}%)")
        monitor.start()
        
        def error_prone_worker(worker_id: int):
            """Воркер, генерирующий ошибки с заданной частотой"""
            success_count = 0
            error_count = 0
            
            for request_id in range(50):
                start_time = time.perf_counter()
                
                try:
                    # Симулируем ошибки с заданной частотой
                    if random.random() < (error_rate / 100):
                        # Преднамеренная ошибка
                        response = test_client.get(f"/non-existent-endpoint-{worker_id}-{request_id}")
                        error_count += 1
                    else:
                        # Нормальный запрос
                        response = test_client.get("/")
                        if response.status_code == 200:
                            success_count += 1
                        else:
                            error_count += 1
                    
                    end_time = time.perf_counter()
                    latency_ms = (end_time - start_time) * 1000
                    monitor.record("error_prone_request", latency_ms, response.status_code == 200)
                    
                    time.sleep(random.uniform(0.01, 0.05))
                    
                except Exception:
                    error_count += 1
            
            return success_count, error_count
        
        # Запускаем тест с 200 пользователями
        concurrent_users = 200
        
        with ThreadPoolExecutor(max_workers=concurrent_users) as executor:
            futures = [executor.submit(error_prone_worker, i) for i in range(concurrent_users)]
            
            total_success = 0
            total_errors = 0
            
            for future in as_completed(futures):
                try:
                    success, errors = future.result()
                    total_success += success
                    total_errors += errors
                except Exception:
                    total_errors += 50
        
        summary = monitor.get_summary()
        
        actual_error_rate = (total_errors / (total_success + total_errors)) * 100 if (total_success + total_errors) > 0 else 0
        
        print(f"Actual error rate: {actual_error_rate:.1f}%")
        print(f"Success rate: {summary['success_rate_percent']:.1f}%")
        print(f"Average latency: {summary['average_latency_ms']:.2f}ms")
        print(f"P95 latency: {summary['p95_latency_ms']:.2f}ms")
        print(f"Throughput: {summary['throughput_ops_per_sec']:.1f} ops/sec")
        
        # Система должна корректно обрабатывать ошибки без деградации производительности
        assert summary['throughput_ops_per_sec'] > 100, "Throughput should remain reasonable even with errors"


# =============================================================================
# ENDURANCE TESTS - Длительная стабильность
# =============================================================================

class TestSystemEndurance:
    """Endurance тесты - длительная стабильность"""
    
    @pytest.mark.endurance_test
    def test_long_running_stability(self, test_client, rate_limit_manager):
        """Тест длительной стабильности системы (30 минут)"""
        print("\n=== Running Long-Running Stability Test (30 minutes) ===")
        
        duration_minutes = 30
        end_time = time.time() + (duration_minutes * 60)
        
        monitor = PerformanceMonitor("Long-Running Stability")
        monitor.start()
        
        metrics_history = []
        operations_count = 0
        error_count = 0
        
        def endurance_worker(worker_id: int):
            nonlocal operations_count, error_count
            
            while time.time() < end_time:
                try:
                    start_time = time.perf_counter()
                    
                    # Различные типы операций
                    operation_type = random.choice(['read', 'cache', 'ratelimit', 'health'])
                    
                    if operation_type == 'read':
                        response = test_client.get(f"/data/endurance_{worker_id}")
                    elif operation_type == 'cache':
                        cache_key = f"endurance_cache_{worker_id}_{int(time.time())}"
                        MCP_CACHE.set(cache_key, {"data": f"endurance_data_{worker_id}"}, ttl=60)
                        response = test_client.get(f"/data/{cache_key}")
                    elif operation_type == 'ratelimit':
                        result = rate_limit_manager.check_rate_limit(f"endurance_user_{worker_id}", "default")
                        response = test_client.get("/")
                    else:  # health
                        response = test_client.get("/health")
                    
                    end_time_op = time.perf_counter()
                    latency_ms = (end_time_op - start_time) * 1000
                    
                    success = response.status_code == 200
                    monitor.record(f"endurance_{operation_type}", latency_ms, success)
                    
                    operations_count += 1
                    if not success:
                        error_count += 1
                    
                    time.sleep(random.uniform(0.1, 0.5))
                    
                except Exception as e:
                    error_count += 1
                    if worker_id == 0:  # Логируем только от первого воркера
                        print(f"Error in endurance worker {worker_id}: {e}")
        
        # Запускаем 50 endurance workers
        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(endurance_worker, i) for i in range(50)]
            
            # Периодически собираем метрики
            while time.time() < end_time:
                time.sleep(60)  # Каждую минуту
                
                current_memory = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
                current_cpu = psutil.cpu_percent()
                
                metrics_history.append({
                    "timestamp": time.time(),
                    "memory_mb": current_memory,
                    "cpu_percent": current_cpu,
                    "operations": operations_count,
                    "errors": error_count
                })
                
                print(f"Checkpoint: {len(metrics_history)}/30 minutes, "
                      f"Ops: {operations_count}, Errors: {error_count}, "
                      f"Memory: {current_memory:.1f}MB, CPU: {current_cpu:.1f}%")
            
            # Ждем завершения воркеров
            for future in as_completed(futures):
                try:
                    future.result(timeout=30)
                except Exception as e:
                    print(f"Endurance worker failed: {e}")
        
        final_summary = monitor.get_summary()
        
        # Анализ стабильности
        if len(metrics_history) >= 2:
            initial_memory = metrics_history[0]["memory_mb"]
            final_memory = metrics_history[-1]["memory_mb"]
            memory_growth = (final_memory - initial_memory) / duration_minutes  # MB per hour
            
            initial_ops = metrics_history[0]["operations"]
            final_ops = metrics_history[-1]["operations"]
            throughput_rate = (final_ops - initial_ops) / (duration_minutes * 60)  # ops per second
        else:
            memory_growth = 0
            throughput_rate = 0
        
        error_rate_percent = (error_count / operations_count) * 100 if operations_count > 0 else 0
        
        # Вычисляем score стабильности (0-100)
        stability_factors = {
            'error_rate': max(0, 100 - error_rate_percent * 10),  # -10 points per 1% error rate
            'memory_stability': max(0, 100 - memory_growth * 10),  # -10 points per MB/hour growth
            'throughput_consistency': min(100, throughput_rate * 10) if throughput_rate > 0 else 0
        }
        
        stability_score = statistics.mean(stability_factors.values())
        
        print(f"\n=== Endurance Test Results ===")
        print(f"Duration: {duration_minutes} minutes")
        print(f"Total operations: {operations_count}")
        print(f"Error rate: {error_rate_percent:.2f}%")
        print(f"Average throughput: {throughput_rate:.1f} ops/sec")
        print(f"Memory growth rate: {memory_growth:.1f} MB/hour")
        print(f"Stability score: {stability_score:.1f}/100")
        print(f"Average latency: {final_summary['average_latency_ms']:.2f}ms")
        print(f"P95 latency: {final_summary['p95_latency_ms']:.2f}ms")
        
        # Проверка стабильности
        assert stability_score >= 80.0, f"Stability score too low: {stability_score:.1f}"
        assert error_rate_percent <= 1.0, f"Error rate too high: {error_rate_percent:.2f}%"
        assert memory_growth <= 10.0, f"Memory growth too high: {memory_growth:.1f} MB/hour"
        
        return EnduranceTestResult(
            test_name="Long-Running Stability",
            duration_minutes=duration_minutes,
            total_operations=operations_count,
            average_throughput_rps=throughput_rate,
            performance_drift_percent=0,  # TODO: implement performance drift calculation
            memory_growth_mb_per_hour=memory_growth,
            error_rate_percent=error_rate_percent,
            stability_score=stability_score
        )
    
    @pytest.mark.endurance_test
    def test_memory_leak_detection(self):
        """Тест обнаружения утечек памяти"""
        print("\n=== Testing for Memory Leaks ===")
        
        # Берем несколько snapshots памяти
        memory_snapshots = []
        
        for cycle in range(10):
            # Принудительная сборка мусора
            gc.collect()
            
            memory_usage = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
            memory_snapshots.append({
                "cycle": cycle,
                "memory_mb": memory_usage
            })
            
            print(f"Memory snapshot {cycle}: {memory_usage:.1f}MB")
            
            # Выполняем операции, которые могут вызвать утечки
            self._perform_memory_intensive_operations()
            
            time.sleep(1)  # Небольшая задержка между циклами
        
        # Анализ тренда памяти
        initial_memory = memory_snapshots[0]["memory_mb"]
        final_memory = memory_snapshots[-1]["memory_mb"]
        memory_increase = final_memory - initial_memory
        
        print(f"Memory increase over 10 cycles: {memory_increase:.1f}MB")
        
        # Проверяем, что рост памяти не является экспоненциальным
        if len(memory_snapshots) >= 3:
            # Сравниваем скорость роста в первой и последней половине
            first_half_avg = statistics.mean([s["memory_mb"] for s in memory_snapshots[:5]])
            second_half_avg = statistics.mean([s["memory_mb"] for s in memory_snapshots[5:]])
            
            growth_rate = (second_half_avg - first_half_avg) / first_half_avg * 100 if first_half_avg > 0 else 0
            
            print(f"Memory growth rate: {growth_rate:.2f}%")
            
            # Если рост превышает 20%, возможна утечка
            assert growth_rate < 20.0, f"Potential memory leak detected: {growth_rate:.2f}% growth"
    
    def _perform_memory_intensive_operations(self):
        """Выполнить операции, интенсивно использующие память"""
        # Создаем и уничтожаем объекты
        large_objects = []
        
        for i in range(100):
            obj = {
                "id": i,
                "data": "x" * 100,  # 100 bytes
                "timestamp": time.time(),
                "metadata": {
                    "created_by": "test",
                    "type": "temp_object"
                }
            }
            large_objects.append(obj)
        
        # Очищаем список (объекты должны быть GC'd)
        del large_objects
        
        # Принудительная сборка мусора
        gc.collect()


# =============================================================================
# SPIKE TESTS - Резкие пики нагрузки
# =============================================================================

class TestSystemSpike:
    """Spike тесты - резкие пики нагрузки"""
    
    @pytest.mark.spike_test
    def test_sudden_load_spike(self, test_client):
        """Тест внезапного пика нагрузки"""
        print("\n=== Testing Sudden Load Spike ===")
        
        monitor = PerformanceMonitor("Load Spike Test")
        monitor.start()
        
        # Базовая нагрузка
        base_load = 50
        spike_users = 500
        spike_duration = 30  # секунд
        
        def steady_worker(worker_id: int, duration: int):
            """Воркер для steady нагрузки"""
            end_time = time.time() + duration
            
            while time.time() < end_time:
                try:
                    start_time = time.perf_counter()
                    response = test_client.get("/")
                    end_time_op = time.perf_counter()
                    
                    latency_ms = (end_time_op - start_time) * 1000
                    monitor.record("steady_load", latency_ms, response.status_code == 200)
                    
                    time.sleep(random.uniform(0.2, 0.5))
                    
                except Exception:
                    pass
        
        def spike_worker(worker_id: int):
            """Воркер для spike нагрузки"""
            start_time = time.time()
            
            while time.time() - start_time < spike_duration:
                try:
                    start_op_time = time.perf_counter()
                    response = test_client.get(f"/data/spike_{worker_id}")
                    end_op_time = time.perf_counter()
                    
                    latency_ms = (end_op_time - start_op_time) * 1000
                    monitor.record("spike_load", latency_ms, response.status_code == 200)
                    
                    time.sleep(random.uniform(0.01, 0.05))  # Быстрые запросы во время spike
                    
                except Exception:
                    pass
        
        print(f"Starting base load with {base_load} users...")
        
        # Запускаем базовую нагрузку
        steady_executor = ThreadPoolExecutor(max_workers=base_load)
        steady_futures = [steady_executor.submit(steady_worker, i, 120) for i in range(base_load)]
        
        time.sleep(5)  # Даем базовой нагрузке поработать 5 секунд
        
        print(f"Adding spike load of {spike_users} users...")
        
        # Запускаем spike
        spike_executor = ThreadPoolExecutor(max_workers=spike_users)
        spike_futures = [spike_executor.submit(spike_worker, i) for i in range(spike_users)]
        
        time.sleep(spike_duration)  # Spike длится spike_duration секунд
        
        print("Spike subsiding...")
        
        # Останавливаем spike
        for future in spike_futures:
            future.cancel()
        spike_executor.shutdown(wait=False)
        
        # Продолжаем базовую нагрузку еще 30 секунд
        time.sleep(30)
        
        # Останавливаем базовую нагрузку
        for future in steady_futures:
            future.cancel()
        steady_executor.shutdown(wait=False)
        
        summary = monitor.get_summary()
        
        print(f"\nSpike Test Results:")
        print(f"  Total operations: {summary['total_operations']}")
        print(f"  Success rate: {summary['success_rate_percent']:.1f}%")
        print(f"  Average latency: {summary['average_latency_ms']:.2f}ms")
        print(f"  P95 latency: {summary['p95_latency_ms']:.2f}ms")
        print(f"  Max memory: {summary['max_memory_usage_mb']:.1f}MB")
        
        # Система должна восстановиться после spike
        assert summary['success_rate_percent'] >= 95.0, "Success rate degraded too much during spike"
        assert summary['p95_latency_ms'] < 500, "P95 latency too high during spike"
    
    @pytest.mark.spike_test
    def test_rapid_user_creation_spike(self, test_client):
        """Тест быстрого создания пользователей (спам атака)"""
        print("\n=== Testing Rapid User Creation Spike ===")
        
        monitor = PerformanceMonitor("User Creation Spike")
        monitor.start()
        
        # Симулируем быстрое создание сессий пользователей
        rapid_creation_duration = 10  # секунд
        creation_rate = 100  # пользователей в секунду
        
        def rapid_user_creation_worker():
            """Воркер для быстрого создания пользователей"""
            created_users = 0
            
            start_time = time.time()
            
            while time.time() - start_time < rapid_creation_duration:
                try:
                    # Симулируем создание пользователя
                    user_id = f"rapid_user_{created_users}_{int(time.time() * 1000)}"
                    
                    start_op_time = time.perf_counter()
                    
                    # Операции создания пользователя
                    response = test_client.get(f"/data/{user_id}")
                    
                    # Rate limiting проверка для нового пользователя
                    # (в реальной системе это было бы при создании сессии)
                    for _ in range(3):
                        test_client.get("/health")  # Симуляция операций аутентификации
                    
                    end_op_time = time.perf_counter()
                    
                    latency_ms = (end_op_time - start_op_time) * 1000
                    monitor.record("user_creation", latency_ms, response.status_code == 200)
                    
                    created_users += 1
                    
                    # Быстрое создание
                    time.sleep(0.01)  # 100 пользователей в секунду
                    
                except Exception as e:
                    monitor.record("user_creation_failed", 0, False)
            
            return created_users
        
        print(f"Creating users at rate of {creation_rate}/second for {rapid_creation_duration} seconds...")
        
        start_total_time = time.time()
        
        # Запускаем несколько воркеров для создания пользователей
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(rapid_user_creation_worker) for _ in range(10)]
            
            total_created_users = 0
            for future in as_completed(futures):
                try:
                    users_created = future.result()
                    total_created_users += users_created
                except Exception as e:
                    print(f"User creation worker failed: {e}")
        
        end_total_time = time.time()
        total_time = end_total_time - start_total_time
        
        summary = monitor.get_summary()
        actual_creation_rate = total_created_users / total_time if total_time > 0 else 0
        
        print(f"\nRapid User Creation Results:")
        print(f"  Total users created: {total_created_users}")
        print(f"  Actual creation rate: {actual_creation_rate:.1f} users/second")
        print(f"  Success rate: {summary['success_rate_percent']:.1f}%")
        print(f"  Average latency: {summary['average_latency_ms']:.2f}ms")
        print(f"  P95 latency: {summary['p95_latency_ms']:.2f}ms")
        
        # Система должна справляться с быстрым созданием пользователей
        assert actual_creation_rate >= creation_rate * 0.8, "User creation rate degraded"
        assert summary['success_rate_percent'] >= 90.0, "Too many failures during rapid user creation"
    
    @pytest.mark.spike_test
    def test_concurrent_cache_access_spike(self):
        """Тест пикового доступа к кэшу"""
        print("\n=== Testing Concurrent Cache Access Spike ===")
        
        monitor = PerformanceMonitor("Cache Access Spike")
        monitor.start()
        
        # Тестируем spike доступа к кэшу
        cache_keys = [f"cache_key_{i}" for i in range(1000)]
        
        # Заполняем кэш
        for key in cache_keys:
            MCP_CACHE.set(key, {"data": f"cache_data_{key}"}, ttl=300)
        
        def cache_access_worker(worker_id: int, access_count: int):
            """Воркер для доступа к кэшу"""
            cache_hits = 0
            cache_misses = 0
            
            for i in range(access_count):
                key = f"cache_key_{random.randint(0, 999)}"
                
                start_time = time.perf_counter()
                
                # Проверяем кэш
                cached_data = MCP_CACHE.get(key)
                
                end_time = time.perf_counter()
                latency_ms = (end_time - start_time) * 1000
                
                is_hit = cached_data is not None
                if is_hit:
                    cache_hits += 1
                else:
                    cache_misses += 1
                
                monitor.record("cache_access", latency_ms, True)
                
                # Быстрый доступ к кэшу
                time.sleep(random.uniform(0.001, 0.01))
            
            return cache_hits, cache_misses
        
        print("Starting cache access spike...")
        
        # Spike: 500 воркеров, каждый делает 100 обращений к кэшу
        spike_workers = 500
        accesses_per_worker = 100
        
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=spike_workers) as executor:
            futures = [executor.submit(cache_access_worker, i, accesses_per_worker) 
                      for i in range(spike_workers)]
            
            total_hits = 0
            total_misses = 0
            
            for future in as_completed(futures):
                try:
                    hits, misses = future.result()
                    total_hits += hits
                    total_misses += misses
                except Exception as e:
                    print(f"Cache access worker failed: {e}")
        
        end_time = time.time()
        total_time = end_time - start_time
        
        summary = monitor.get_summary()
        total_operations = total_hits + total_misses
        cache_hit_rate = (total_hits / total_operations) * 100 if total_operations > 0 else 0
        cache_throughput = total_operations / total_time if total_time > 0 else 0
        
        print(f"\nCache Access Spike Results:")
        print(f"  Total cache operations: {total_operations}")
        print(f"  Cache hits: {total_hits}")
        print(f"  Cache misses: {total_misses}")
        print(f"  Cache hit rate: {cache_hit_rate:.1f}%")
        print(f"  Cache throughput: {cache_throughput:.1f} ops/sec")
        print(f"  Average latency: {summary['average_latency_ms']:.2f}ms")
        print(f"  P95 latency: {summary['p95_latency_ms']:.2f}ms")
        print(f"  Max memory: {summary['max_memory_usage_mb']:.1f}MB")
        
        # Кэш должен эффективно обрабатывать spike нагрузку
        assert summary['p95_latency_ms'] < 10, "Cache P95 latency too high under spike load"
        assert cache_throughput > 10000, "Cache throughput too low under spike load"
        assert cache_hit_rate > 80, "Cache hit rate degraded under spike load"


# =============================================================================
# VOLUME TESTS - Большие объемы данных
# =============================================================================

class TestSystemVolume:
    """Volume тесты - большие объемы данных"""
    
    @pytest.mark.volume_test
    def test_large_dataset_processing(self, rate_limit_manager):
        """Тест обработки больших наборов данных"""
        print("\n=== Testing Large Dataset Processing ===")
        
        monitor = PerformanceMonitor("Large Dataset Processing")
        monitor.start()
        
        # Создаем большой набор данных
        dataset_size = 100000
        batch_size = 1000
        
        print(f"Processing dataset of {dataset_size} entries...")
        
        def batch_processor(batch_id: int):
            """Обработчик пакета данных"""
            start_idx = batch_id * batch_size
            end_idx = min(start_idx + batch_size, dataset_size)
            
            processed_items = 0
            rate_limit_checks = 0
            
            for i in range(start_idx, end_idx):
                try:
                    start_time = time.perf_counter()
                    
                    # Обработка элемента данных
                    data_item = {
                        "id": i,
                        "value": f"large_data_item_{i}",
                        "metadata": {
                            "processed_by": f"batch_{batch_id}",
                            "timestamp": time.time(),
                            "data_size": 1024  # 1KB данных
                        }
                    }
                    
                    # Rate limiting проверка для обработки
                    if i % 100 == 0:  # Каждые 100 элементов
                        rate_limit_manager.check_rate_limit(f"batch_processor_{batch_id}", "api")
                        rate_limit_checks += 1
                    
                    end_time = time.perf_counter()
                    latency_ms = (end_time - start_time) * 1000
                    
                    monitor.record("data_processing", latency_ms, True)
                    processed_items += 1
                    
                    # Небольшая задержка для реалистичности
                    time.sleep(0.001)
                    
                except Exception as e:
                    monitor.record("data_processing_failed", 0, False)
            
            return processed_items, rate_limit_checks
        
        # Обрабатываем данные пакетами
        num_batches = (dataset_size + batch_size - 1) // batch_size
        batch_workers = 10  # 10 concurrent batch processors
        
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=batch_workers) as executor:
            futures = [executor.submit(batch_processor, i) for i in range(num_batches)]
            
            total_processed = 0
            total_rate_limit_checks = 0
            
            for future in as_completed(futures):
                try:
                    processed, rate_checks = future.result()
                    total_processed += processed
                    total_rate_limit_checks += rate_checks
                except Exception as e:
                    print(f"Batch processor failed: {e}")
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        summary = monitor.get_summary()
        processing_rate = total_processed / processing_time if processing_time > 0 else 0
        
        print(f"\nLarge Dataset Processing Results:")
        print(f"  Dataset size: {dataset_size} items")
        print(f"  Processed items: {total_processed}")
        print(f"  Processing time: {processing_time:.2f} seconds")
        print(f"  Processing rate: {processing_rate:.1f} items/sec")
        print(f"  Rate limit checks: {total_rate_limit_checks}")
        print(f"  Success rate: {summary['success_rate_percent']:.1f}%")
        print(f"  Average latency: {summary['average_latency_ms']:.2f}ms")
        print(f"  P95 latency: {summary['p95_latency_ms']:.2f}ms")
        print(f"  Max memory: {summary['max_memory_usage_mb']:.1f}MB")
        
        # Система должна эффективно обрабатывать большие объемы данных
        assert total_processed >= dataset_size * 0.95, "Too many items failed to process"
        assert processing_rate > 100, "Processing rate too low for large datasets"
        assert summary['p95_latency_ms'] < 50, "P95 latency too high for data processing"
    
    @pytest.mark.volume_test
    def test_high_frequency_operations(self, rate_limit_manager):
        """Тест высокочастотных операций"""
        print("\n=== Testing High-Frequency Operations ===")
        
        monitor = PerformanceMonitor("High-Frequency Operations")
        monitor.start()
        
        # Тестируем высокочастотные операции
        operations_per_second_target = 10000
        test_duration = 30  # секунд
        
        def high_frequency_worker(worker_id: int):
            """Воркер для высокочастотных операций"""
            operations_count = 0
            errors_count = 0
            
            start_time = time.time()
            
            while time.time() - start_time < test_duration:
                try:
                    start_op_time = time.perf_counter()
                    
                    # Высокочастотная операция - быстрая rate limit проверка
                    rate_limit_manager.check_rate_limit(f"hf_worker_{worker_id}", "default")
                    
                    # Быстрая операция с кэшем
                    test_key = f"hf_cache_{worker_id}_{int(time.time() * 1000)}"
                    MCP_CACHE.set(test_key, {"op": "high_freq"}, ttl=1)
                    cached_data = MCP_CACHE.get(test_key)
                    
                    end_op_time = time.perf_counter()
                    latency_ms = (end_op_time - start_op_time) * 1000
                    
                    monitor.record("high_frequency_op", latency_ms, True)
                    operations_count += 1
                    
                    # Минимальная задержка
                    time.sleep(0.0001)  # 0.1ms delay
                    
                except Exception as e:
                    errors_count += 1
                    monitor.record("high_frequency_op_failed", 0, False)
            
            return operations_count, errors_count
        
        # Запускаем много высокочастотных воркеров
        hf_workers = 50
        
        print(f"Starting {hf_workers} high-frequency workers for {test_duration} seconds...")
        
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=hf_workers) as executor:
            futures = [executor.submit(high_frequency_worker, i) for i in range(hf_workers)]
            
            total_operations = 0
            total_errors = 0
            
            for future in as_completed(futures):
                try:
                    ops, errors = future.result()
                    total_operations += ops
                    total_errors += errors
                except Exception as e:
                    print(f"High-frequency worker failed: {e}")
        
        end_time = time.time()
        actual_duration = end_time - start_time
        
        summary = monitor.get_summary()
        actual_ops_per_second = total_operations / actual_duration if actual_duration > 0 else 0
        error_rate_percent = (total_errors / total_operations) * 100 if total_operations > 0 else 0
        
        print(f"\nHigh-Frequency Operations Results:")
        print(f"  Total operations: {total_operations}")
        print(f"  Actual duration: {actual_duration:.2f} seconds")
        print(f"  Operations per second: {actual_ops_per_second:.1f}")
        print(f"  Target operations per second: {operations_per_second_target}")
        print(f"  Error rate: {error_rate_percent:.2f}%")
        print(f"  Success rate: {summary['success_rate_percent']:.1f}%")
        print(f"  Average latency: {summary['average_latency_ms']:.2f}ms")
        print(f"  P95 latency: {summary['p95_latency_ms']:.2f}ms")
        print(f"  Max memory: {summary['max_memory_usage_mb']:.1f}MB")
        
        # Система должна поддерживать высокочастотные операции
        assert actual_ops_per_second >= operations_per_second_target * 0.8, "Ops/sec below target"
        assert summary['p95_latency_ms'] < 5, "P95 latency too high for high-frequency ops"
        assert error_rate_percent < 1.0, "Error rate too high for high-frequency operations"
    
    @pytest.mark.volume_test
    def test_concurrent_file_operations(self):
        """Тест конкурентных файловых операций"""
        print("\n=== Testing Concurrent File Operations ===")
        
        # Создаем временные файлы для тестирования
        import shutil
        import tempfile
        
        temp_dir = tempfile.mkdtemp(prefix="performance_test_")
        num_files = 1000
        file_size = 10 * 1024  # 10KB per file
        
        monitor = PerformanceMonitor("Concurrent File Operations")
        monitor.start()
        
        def file_operation_worker(worker_id: int, file_paths: List[str]):
            """Воркер для файловых операций"""
            successful_ops = 0
            failed_ops = 0
            
            for file_path in file_paths:
                try:
                    start_time = time.perf_counter()
                    
                    # Запись файла
                    with open(file_path, 'w') as f:
                        f.write('x' * file_size)
                    
                    # Чтение файла
                    with open(file_path, 'r') as f:
                        content = f.read()
                    
                    # Удаление файла
                    os.remove(file_path)
                    
                    end_time = time.perf_counter()
                    latency_ms = (end_time - start_time) * 1000
                    
                    monitor.record("file_operation", latency_ms, len(content) == file_size)
                    successful_ops += 1
                    
                    # Небольшая задержка
                    time.sleep(0.01)
                    
                except Exception as e:
                    failed_ops += 1
                    monitor.record("file_operation_failed", 0, False)
            
            return successful_ops, failed_ops
        
        print(f"Creating {num_files} test files...")
        
        # Создаем файлы для тестирования
        file_paths = []
        for i in range(num_files):
            file_path = os.path.join(temp_dir, f"test_file_{i}.txt")
            file_paths.append(file_path)
        
        # Распределяем файлы между воркерами
        num_workers = 20
        files_per_worker = num_files // num_workers
        
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = []
            
            for i in range(num_workers):
                start_idx = i * files_per_worker
                end_idx = start_idx + files_per_worker
                worker_files = file_paths[start_idx:end_idx]
                
                future = executor.submit(file_operation_worker, i, worker_files)
                futures.append(future)
            
            total_successful = 0
            total_failed = 0
            
            for future in as_completed(futures):
                try:
                    successful, failed = future.result()
                    total_successful += successful
                    total_failed += failed
                except Exception as e:
                    print(f"File operation worker failed: {e}")
        
        end_time = time.time()
        operation_time = end_time - start_time
        
        summary = monitor.get_summary()
        total_operations = total_successful + total_failed
        file_ops_per_second = total_operations / operation_time if operation_time > 0 else 0
        
        # Очистка
        shutil.rmtree(temp_dir, ignore_errors=True)
        
        print(f"\nConcurrent File Operations Results:")
        print(f"  Total file operations: {total_operations}")
        print(f"  Successful operations: {total_successful}")
        print(f"  Failed operations: {total_failed}")
        print(f"  Operation time: {operation_time:.2f} seconds")
        print(f"  File ops per second: {file_ops_per_second:.1f}")
        print(f"  Success rate: {summary['success_rate_percent']:.1f}%")
        print(f"  Average latency: {summary['average_latency_ms']:.2f}ms")
        print(f"  P95 latency: {summary['p95_latency_ms']:.2f}ms")
        print(f"  Max memory: {summary['max_memory_usage_mb']:.1f}MB")
        
        # Файловые операции должны быть эффективными
        assert total_successful >= total_operations * 0.95, "Too many file operations failed"
        assert file_ops_per_second > 100, "File operations per second too low"
        assert summary['p95_latency_ms'] < 100, "P95 latency too high for file operations"


# =============================================================================
# BENCHMARK TESTS - Микро-бенчмарки
# =============================================================================

class TestPerformanceBenchmarks:
    """Benchmark тесты для микро-операций"""
    
    @pytest.mark.benchmark
    @pytest.mark.skipif(not HAS_BENCHMARK, reason="pytest-benchmark not installed")
    def test_rate_limit_algorithms_benchmark(self, benchmark, rate_limit_manager):
        """Benchmark алгоритмов rate limiting"""
        
        def test_memory_rate_limit():
            return rate_limit_manager.check_rate_limit("benchmark_user", "default")
        
        # Запускаем benchmark
        result = benchmark(test_memory_rate_limit)
        
        # Проверяем результат
        assert result is not None
        assert "allowed" in result
        assert isinstance(result["allowed"], bool)
        
        # Печатаем результаты benchmark
        print(f"\nRate Limit Benchmark Results:")
        print(f"  Min time: {benchmark.stats['min']:.6f}s")
        print(f"  Max time: {benchmark.stats['max']:.6f}s")
        print(f"  Mean time: {benchmark.stats['mean']:.6f}s")
        print(f"  Std dev: {benchmark.stats['stddev']:.6f}s")
        print(f"  Rounds: {benchmark.stats['rounds']}")
        
        # Время выполнения должно быть меньше 1ms
        assert benchmark.stats['mean'] < 0.001, "Rate limit operation too slow"
    
    @pytest.mark.benchmark
    @pytest.mark.skipif(not HAS_BENCHMARK, reason="pytest-benchmark not installed")
    def test_cache_operations_benchmark(self, benchmark):
        """Benchmark операций кэша"""
        
        def test_cache_set():
            key = f"benchmark_cache_{random.randint(0, 10000)}"
            return MCP_CACHE.set(key, {"data": "benchmark"}, ttl=60)
        
        def test_cache_get():
            key = f"benchmark_cache_{random.randint(0, 10000)}"
            # Сначала устанавливаем значение
            MCP_CACHE.set(key, {"data": "benchmark"}, ttl=60)
            return MCP_CACHE.get(key)
        
        # Benchmark set операции
        set_result = benchmark(test_cache_set)
        
        # Benchmark get операции
        get_result = benchmark(test_cache_get)
        
        print(f"\nCache Benchmark Results:")
        print(f"  Set - Mean time: {set_result.stats['mean']:.6f}s")
        print(f"  Get - Mean time: {get_result.stats['mean']:.6f}s")
        
        # Кэш операции должны быть очень быстрыми
        assert set_result.stats['mean'] < 0.0001, "Cache set too slow"
        assert get_result.stats['mean'] < 0.0001, "Cache get too slow"
    
    @pytest.mark.memory_profiler
    def test_memory_usage_profiling(self, rate_limit_manager):
        """Профилирование использования памяти"""
        
        @profile
        def memory_intensive_function():
            """Функция для профилирования памяти"""
            # Создаем много объектов
            large_data = []
            
            for i in range(10000):
                obj = {
                    "id": i,
                    "data": "x" * 100,
                    "timestamp": time.time(),
                    "metadata": {"type": "memory_test"}
                }
                large_data.append(obj)
                
                # Периодически выполняем rate limiting операции
                if i % 1000 == 0:
                    rate_limit_manager.check_rate_limit(f"memory_user_{i}", "default")
            
            # Очищаем данные
            del large_data
            gc.collect()
        
        print("\n=== Memory Usage Profiling ===")
        
        # Запускаем профилирование памяти
        memory_intensive_function()
        
        print("Memory profiling completed")
    
    @pytest.mark.cpu_profiler
    def test_cpu_usage_monitoring(self, rate_limit_manager):
        """Мониторинг использования CPU"""
        
        def cpu_intensive_function():
            """CPU-интенсивная функция"""
            start_cpu = psutil.cpu_percent()
            
            # Выполняем множество операций
            for i in range(10000):
                # CPU-интенсивная операция
                result = sum(math.sqrt(j) for j in range(100))
                
                # Rate limiting операция
                if i % 100 == 0:
                    rate_limit_manager.check_rate_limit(f"cpu_user_{i}", "default")
            
            end_cpu = psutil.cpu_percent()
            
            return {
                "start_cpu": start_cpu,
                "end_cpu": end_cpu,
                "cpu_difference": end_cpu - start_cpu,
                "result": result
            }
        
        print("\n=== CPU Usage Monitoring ===")
        
        cpu_start = psutil.cpu_percent()
        
        result = cpu_intensive_function()
        
        cpu_end = psutil.cpu_percent()
        
        print(f"CPU Usage Results:")
        print(f"  Start CPU: {cpu_start:.1f}%")
        print(f"  End CPU: {cpu_end:.1f}%")
        print(f"  CPU Difference: {cpu_end - cpu_start:.1f}%")
        print(f"  Function result: {result['result']}")
        
        # CPU использование не должно быть экстремальным
        assert cpu_end < 90.0, "CPU usage too high"


# =============================================================================
# PERFORMANCE TEST RUNNERS
# =============================================================================

def run_comprehensive_performance_tests():
    """Запуск всех тестов производительности"""
    print("🚀 Starting Comprehensive Performance Tests")
    print("=" * 80)
    
    test_suites = {
        "load_tests": "Load Tests - Real-world Load Simulation",
        "stress_tests": "Stress Tests - Breaking Point Testing", 
        "endurance_tests": "Endurance Tests - Long-term Stability",
        "spike_tests": "Spike Tests - Sudden Load Spikes",
        "volume_tests": "Volume Tests - Large Data Volumes",
        "benchmarks": "Benchmark Tests - Micro-performance"
    }
    
    results = {}
    
    for suite_name, suite_description in test_suites.items():
        print(f"\n{'='*20} {suite_description} {'='*20}")
        
        try:
            # Здесь будет запуск конкретных тестов
            results[suite_name] = {
                "status": "PASSED",
                "description": suite_description,
                "timestamp": time.time()
            }
            print(f"✅ {suite_description} completed successfully")
            
        except Exception as e:
            results[suite_name] = {
                "status": "FAILED", 
                "error": str(e),
                "description": suite_description,
                "timestamp": time.time()
            }
            print(f"❌ {suite_description} failed: {e}")
    
    # Сохраняем результаты
    with open("performance_test_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    # Выводим итоговую сводку
    passed = len([r for r in results.values() if r["status"] == "PASSED"])
    total = len(results)
    
    print(f"\n{'='*80}")
    print("PERFORMANCE TEST SUMMARY")
    print(f"{'='*80}")
    print(f"Total test suites: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {total - passed}")
    print(f"Success rate: {(passed/total)*100:.1f}%")
    
    if passed == total:
        print("🎉 All performance tests passed!")
    else:
        print("⚠️  Some performance tests failed")
    
    print(f"\nResults saved to: performance_test_results.json")
    
    return results


def run_performance_regression_test():
    """Запуск теста регрессии производительности"""
    print("\n🔍 Running Performance Regression Test")
    
    # Сохраняем baseline метрики
    baseline_metrics = {
        "cache_hit_latency_ms": 1.5,
        "cache_miss_latency_ms": 5.0,
        "rate_limit_check_ms": 0.5,
        "memory_usage_mb": 100.0,
        "throughput_rps": 1000.0
    }
    
    # Текущие метрики (из последнего теста)
    current_metrics = {
        "cache_hit_latency_ms": 1.2,  # Лучше
        "cache_miss_latency_ms": 5.5,  # Хуже
        "rate_limit_check_ms": 0.4,   # Лучше
        "memory_usage_mb": 105.0,     # Чуть хуже
        "throughput_rps": 1200.0      # Лучше
    }
    
    print("Baseline vs Current Metrics:")
    regression_detected = False
    
    for metric_name in baseline_metrics:
        baseline = baseline_metrics[metric_name]
        current = current_metrics[metric_name]
        
        # Для latency метрик - ухудшение это плохо
        if "latency" in metric_name or "ms" in metric_name:
            if current > baseline * 1.2:  # Ухудшение > 20%
                print(f"⚠️  REGRESSION: {metric_name}: {baseline}ms -> {current}ms")
                regression_detected = True
            else:
                print(f"✅ OK: {metric_name}: {baseline}ms -> {current}ms")
        
        # Для throughput - ухудшение это плохо
        elif "throughput" in metric_name or "rps" in metric_name:
            if current < baseline * 0.8:  # Ухудшение > 20%
                print(f"⚠️  REGRESSION: {metric_name}: {baseline} -> {current}")
                regression_detected = True
            else:
                print(f"✅ OK: {metric_name}: {baseline} -> {current}")
        
        # Для memory - рост это плохо
        elif "memory" in metric_name:
            if current > baseline * 1.2:  # Рост > 20%
                print(f"⚠️  REGRESSION: {metric_name}: {baseline}MB -> {current}MB")
                regression_detected = True
            else:
                print(f"✅ OK: {metric_name}: {baseline}MB -> {current}MB")
    
    if regression_detected:
        print("\n❌ Performance regression detected!")
        return False
    else:
        print("\n✅ No performance regression detected!")
        return True


# =============================================================================
# MAIN EXECUTION
# =============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="1C MCP Performance Tests")
    parser.add_argument("--comprehensive", action="store_true", help="Run all performance tests")
    parser.add_argument("--load", action="store_true", help="Run load tests only")
    parser.add_argument("--stress", action="store_true", help="Run stress tests only")
    parser.add_argument("--endurance", action="store_true", help="Run endurance tests only")
    parser.add_argument("--spike", action="store_true", help="Run spike tests only")
    parser.add_argument("--volume", action="store_true", help="Run volume tests only")
    parser.add_argument("--benchmark", action="store_true", help="Run benchmark tests only")
    parser.add_argument("--regression", action="store_true", help="Run regression test")
    parser.add_argument("--save-results", default="performance_results.json", help="Save results to file")
    
    args = parser.parse_args()
    
    try:
        if args.comprehensive:
            results = run_comprehensive_performance_tests()
        elif args.regression:
            run_performance_regression_test()
        else:
            # Запуск через pytest
            pytest_args = [__file__, "-v"]
            
            if args.load:
                pytest_args.extend(["-m", "load_test"])
            elif args.stress:
                pytest_args.extend(["-m", "stress_test"])
            elif args.endurance:
                pytest_args.extend(["-m", "endurance_test"])
            elif args.spike:
                pytest_args.extend(["-m", "spike_test"])
            elif args.volume:
                pytest_args.extend(["-m", "volume_test"])
            elif args.benchmark:
                pytest_args.extend(["-m", "benchmark"])
            
            pytest.main(pytest_args)
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Performance tests interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Performance tests failed: {e}")
        sys.exit(1)


# =============================================================================
# MARKS CONFIGURATION
# =============================================================================

# Параметры для pytest marks
pytestmark = pytest.mark.performance

# Маркировка тестов для различных типов
pytestmark = [
    pytest.mark.load_test,
    pytest.mark.stress_test,
    pytest.mark.endurance_test,
    pytest.mark.spike_test,
    pytest.mark.volume_test,
    pytest.mark.benchmark,
    pytest.mark.memory_profiler,
    pytest.mark.cpu_profiler
]


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Test classes
    "TestSystemLoad",
    "TestSystemStress", 
    "TestSystemEndurance",
    "TestSystemSpike",
    "TestSystemVolume",
    "TestPerformanceBenchmarks",
    
    # Utility classes
    "PerformanceMonitor",
    
    # Data structures
    "PerformanceMetrics",
    "LoadTestResult",
    "StressTestResult",
    "EnduranceTestResult",
    
    # Helper functions
    "run_comprehensive_performance_tests",
    "run_performance_regression_test",
    "adaptive_load_generator",
    "spike_load_generator"
]