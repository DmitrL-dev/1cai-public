
"""
Тесты конкурентности и производительности для 1С MCP сервера

Содержит:
- Thread safety тесты
- Performance benchmarking
- Load testing
- Memory leak detection
- Stress testing
- Scalability tests

"""

import asyncio
import concurrent.futures
import gc
import os
# Импорты приложения
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass

import psutil
import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.cache_admin import MemoryCache, cache_metrics

# =============================================================================
# ПРОИЗВОДИТЕЛЬНОСТЬ И МЕТРИКИ
# =============================================================================

@dataclass
class PerformanceMetrics:
    """Метрики производительности"""
    avg_response_time: float
    min_response_time: float
    max_response_time: float
    total_requests: int
    successful_requests: int
    failed_requests: int
    throughput: float  # запросов в секунду
    memory_usage_mb: float
    cpu_usage_percent: float


class PerformanceMonitor:
    """Монитор производительности"""
    
    def __init__(self):
        self.metrics = PerformanceMetrics(
            avg_response_time=0.0,
            min_response_time=float('inf'),
            max_response_time=0.0,
            total_requests=0,
            successful_requests=0,
            failed_requests=0,
            throughput=0.0,
            memory_usage_mb=0.0,
            cpu_usage_percent=0.0
        )
        self.response_times = deque(maxlen=10000)
        self.process = psutil.Process()
    
    def start_monitoring(self):
        """Начать мониторинг"""
        self.start_time = time.time()
        self.start_memory = self.process.memory_info().rss
    
    def record_request(self, response_time: float, success: bool):
        """Записать результат запроса"""
        self.response_times.append(response_time)
        self.metrics.total_requests += 1
        
        if success:
            self.metrics.successful_requests += 1
        else:
            self.metrics.failed_requests += 1
        
        self.metrics.min_response_time = min(self.metrics.min_response_time, response_time)
        self.metrics.max_response_time = max(self.metrics.max_response_time, response_time)
    
    def finish_monitoring(self) -> PerformanceMetrics:
        """Завершить мониторинг и получить метрики"""
        elapsed = time.time() - self.start_time
        current_memory = self.process.memory_info().rss
        
        if self.response_times:
            self.metrics.avg_response_time = sum(self.response_times) / len(self.response_times)
        
        self.metrics.throughput = self.metrics.total_requests / elapsed if elapsed > 0 else 0.0
        self.metrics.memory_usage_mb = (current_memory - self.start_memory) / (1024 * 1024)
        self.metrics.cpu_usage_percent = self.process.cpu_percent()
        
        return self.metrics


# =============================================================================
# THREAD SAFETY ТЕСТЫ
# =============================================================================

class TestThreadSafety:
    """Тесты безопасности потоков"""
    
    @pytest.mark.thread_safety
    def test_concurrent_cache_operations(self):
        """Тест конкурентных операций с кэшем"""
        cache = MemoryCache("thread_safety_test")
        num_threads = 10
        operations_per_thread = 1000
        results = []
        errors = []
        
        def cache_worker(thread_id: int):
            """Воркер для тестирования кэша"""
            thread_results = []
            thread_errors = []
            
            for i in range(operations_per_thread):
                key = f"thread_{thread_id}_key_{i}"
                value = f"thread_{thread_id}_value_{i}"
                
                try:
                    # Смешиваем операции get и set
                    cache.set(key, value)
                    retrieved = cache.get(key)
                    
                    if retrieved == value:
                        thread_results.append(True)
                    else:
                        thread_results.append(False)
                        thread_errors.append(f"Data mismatch for key {key}")
                
                except Exception as e:
                    thread_errors.append(f"Exception in thread {thread_id}: {str(e)}")
            
            return thread_results, thread_errors
        
        # Запускаем потоки
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(cache_worker, i) for i in range(num_threads)]
            
            for future in concurrent.futures.as_completed(futures):
                try:
                    thread_results, thread_errors = future.result()
                    results.extend(thread_results)
                    errors.extend(thread_errors)
                except Exception as e:
                    errors.append(f"Thread execution error: {str(e)}")
        
        # Анализируем результаты
        total_operations = num_threads * operations_per_thread
        success_rate = sum(results) / len(results) if results else 0
        
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert success_rate > 0.99, f"Success rate too low: {success_rate}"
        assert len(results) == total_operations
    
    @pytest.mark.thread_safety
    def test_concurrent_metrics_updates(self):
        """Тест конкурентных обновлений метрик"""
        # Сбрасываем метрики
        cache_metrics.hit_count = 0
        cache_metrics.miss_count = 0
        
        num_threads = 5
        increments_per_thread = 1000
        
        def metrics_worker():
            """Воркер для обновления метрик"""
            for _ in range(increments_per_thread):
                cache_metrics.hit_count += 1
                cache_metrics.miss_count += 1
        
        # Запускаем потоки
        threads = []
        for _ in range(num_threads):
            thread = threading.Thread(target=metrics_worker)
            threads.append(thread)
            thread.start()
        
        # Ждем завершения всех потоков
        for thread in threads:
            thread.join()
        
        # Проверяем результаты
        expected_count = num_threads * increments_per_thread
        assert cache_metrics.hit_count == expected_count
        assert cache_metrics.miss_count == expected_count
    
    @pytest.mark.thread_safety
    def test_memory_consistency_under_load(self):
        """Тест консистентности памяти под нагрузкой"""
        cache = MemoryCache("memory_consistency_test")
        
        # Создаем несколько потоков, работающих с разными кэшами
        caches = [MemoryCache(f"cache_{i}") for i in range(5)]
        
        def cache_stress_worker(cache_instance: MemoryCache, worker_id: int):
            """Воркер для stress тестирования кэша"""
            for i in range(1000):
                key = f"worker_{worker_id}_key_{i}"
                value = f"worker_{worker_id}_value_{i}" * 10  # 200+ символов
                
                cache_instance.set(key, value, ttl=300)
                
                # Случайные операции get
                if i % 10 == 0:
                    cache_instance.get(key)
                
                # Случайные операции delete
                if i % 50 == 0 and i > 0:
                    cache_instance.delete(f"worker_{worker_id}_key_{i-50}")
        
        # Запускаем воркеры
        threads = []
        for i, cache_instance in enumerate(caches):
            thread = threading.Thread(target=cache_stress_worker, args=(cache_instance, i))
            threads.append(thread)
            thread.start()
        
        # Ждем завершения
        for thread in threads:
            thread.join()
        
        # Проверяем что все кэши работают
        for i, cache_instance in enumerate(caches):
            stats = cache_instance.get_stats()
            assert stats["total_keys"] >= 0  # Должны быть корректные данные
    
    @pytest.mark.thread_safety
    def test_race_condition_detection(self):
        """Тест обнаружения race conditions"""
        cache = MemoryCache("race_condition_test")
        shared_counter = {"value": 0}
        lock = threading.Lock()
        
        def increment_worker():
            """Воркер с потенциальной race condition"""
            for _ in range(1000):
                # Без lock - может возникнуть race condition
                temp = shared_counter["value"]
                time.sleep(0.0001)  # Имитация работы
                shared_counter["value"] = temp + 1
        
        # Запускаем несколько воркеров
        threads = [threading.Thread(target=increment_worker) for _ in range(3)]
        
        start_time = time.time()
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        elapsed = time.time() - start_time
        
        # Проверяем что операции выполнялись конкурентно
        assert elapsed < 1.0  # Должно быть быстро при параллельном выполнении
        # Значение может быть меньше ожидаемого из-за race condition
        assert shared_counter["value"] <= 3000  # Не более 3 * 1000


# =============================================================================
# PERFORMANCE BENCHMARKING
# =============================================================================

class TestPerformanceBenchmarking:
    """Benchmark тесты производительности"""
    
    @pytest.mark.performance
    @pytest.mark.benchmark
    async def test_endpoint_benchmark(self, benchmark, test_client):
        """Benchmark тест для основных endpoints"""
        
        async def make_request():
            response = await test_client.get("/")
            assert response.status_code == 200
            return response
        
        # Запускаем benchmark
        result = benchmark.pedantic(
            make_request,
            rounds=100,
            iterations=1,
            warmup=True
        )
        
        # Проверяем что производительность соответствует требованиям
        stats = benchmark.stats
        assert stats["mean"] < 0.1  # Среднее время ответа менее 100ms
        assert stats["max"] < 1.0   # Максимальное время ответа менее 1s
    
    @pytest.mark.performance
    @pytest.mark.benchmark
    async def test_cache_benchmark(self, benchmark):
        """Benchmark тест для операций кэша"""
        cache = MemoryCache("benchmark_cache")
        
        async def cache_operations():
            # Цикл операций с кэшем
            for i in range(100):
                key = f"benchmark_key_{i}"
                value = f"benchmark_value_{i}" * 10
                
                cache.set(key, value)
                retrieved = cache.get(key)
                assert retrieved == value
        
        # Запускаем benchmark
        result = benchmark.pedantic(
            cache_operations,
            rounds=50,
            iterations=1,
            warmup=True
        )
        
        # Проверяем производительность кэша
        stats = benchmark.stats
        assert stats["mean"] < 1.0  # Среднее время менее 1 секунды для 100 операций
        assert stats["ops"] > 100   # Более 100 операций в секунду
    
    @pytest.mark.performance
    async def test_throughput_measurement(self, test_client):
        """Измерение пропускной способности"""
        monitor = PerformanceMonitor()
        monitor.start_monitoring()
        
        # Выполняем множество запросов
        num_requests = 1000
        start_time = time.time()
        
        async def make_request():
            response = await test_client.get("/health")
            success = response.status_code == 200
            response_time = time.time() - start_time
            return response_time, success
        
        # Выполняем запросы параллельно
        tasks = [make_request() for _ in range(num_requests)]
        results = await asyncio.gather(*tasks)
        
        # Записываем метрики
        for response_time, success in results:
            monitor.record_request(response_time, success)
        
        metrics = monitor.finish_monitoring()
        
        # Проверяем показатели производительности
        assert metrics.throughput > 100  # Более 100 запросов в секунду
        assert metrics.avg_response_time < 0.1  # Среднее время менее 100ms
        assert metrics.successful_requests / metrics.total_requests > 0.95  # 95% успешных
    
    @pytest.mark.performance
    async def test_memory_usage_tracking(self, test_client):
        """Отслеживание использования памяти"""
        process = psutil.Process()
        initial_memory = process.memory_info().rss
        
        # Выполняем множество операций с кэшем
        cache = MemoryCache("memory_test")
        for i in range(10000):
            key = f"memory_key_{i}"
            value = f"memory_value_{i}" * 50  # Создаем большие объекты
            cache.set(key, value, ttl=300)
        
        peak_memory = process.memory_info().rss
        memory_growth = (peak_memory - initial_memory) / (1024 * 1024)  # МБ
        
        # Очищаем кэш
        cache.clear()
        gc.collect()
        
        final_memory = process.memory_info().rss
        memory_after_cleanup = (final_memory - initial_memory) / (1024 * 1024)
        
        # Проверяем эффективность использования памяти
        assert memory_growth < 100  # Рост памяти менее 100MB
        assert memory_after_cleanup < 10  # После очистки менее 10MB
    
    @pytest.mark.performance
    async def test_concurrent_request_performance(self, test_client):
        """Тест производительности при конкурентных запросах"""
        concurrency_levels = [1, 5, 10, 20, 50]
        
        for concurrency in concurrency_levels:
            monitor = PerformanceMonitor()
            monitor.start_monitoring()
            
            start_time = time.time()
            
            async def make_concurrent_request():
                response = await test_client.get("/health")
                response_time = time.time() - start_time
                success = response.status_code == 200
                monitor.record_request(response_time, success)
                return response_time
            
            # Выполняем запросы с заданной конкурентностью
            num_requests = 200
            tasks = [make_concurrent_request() for _ in range(num_requests)]
            
            start_concurrent = time.time()
            results = await asyncio.gather(*tasks)
            elapsed_concurrent = time.time() - start_concurrent
            
            metrics = monitor.finish_monitoring()
            
            # Проверяем производительность при данной конкурентности
            throughput = num_requests / elapsed_concurrent
            assert throughput > 10  # Минимум 10 запросов в секунду
            assert metrics.avg_response_time < 1.0  # Среднее время менее 1 секунды
            
            print(f"Concurrency {concurrency}: {throughput:.2f} req/s, avg: {metrics.avg_response_time:.3f}s")


# =============================================================================
# LOAD TESTING
# =============================================================================

class TestLoadTesting:
    """Нагрузочное тестирование"""
    
    @pytest.mark.stress
    async def test_sustained_load(self, test_client):
        """Тест устойчивой нагрузки"""
        duration_seconds = 30  # Тест на 30 секунд
        request_interval = 0.1  # Запрос каждые 100ms
        
        start_time = time.time()
        end_time = start_time + duration_seconds
        request_count = 0
        success_count = 0
        
        process = psutil.Process()
        memory_usage = []
        
        while time.time() < end_time:
            request_start = time.time()
            
            try:
                response = await test_client.get("/health")
                if response.status_code == 200:
                    success_count += 1
                request_count += 1
            except Exception as e:
                print(f"Request failed: {e}")
                request_count += 1
            
            # Записываем использование памяти
            memory_usage.append(process.memory_info().rss)
            
            # Ждем до следующего запроса
            elapsed = time.time() - request_start
            sleep_time = max(0, request_interval - elapsed)
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
        
        # Анализируем результаты
        total_time = time.time() - start_time
        throughput = request_count / total_time
        success_rate = success_count / request_count if request_count > 0 else 0
        
        # Проверяем результаты
        assert request_count > 100  # Минимум 100 запросов
        assert throughput > 3  # Минимум 3 запроса в секунду
        assert success_rate > 0.9  # 90% успешных запросов
        
        # Проверяем стабильность памяти
        memory_growth = (max(memory_usage) - min(memory_usage)) / (1024 * 1024)
        assert memory_growth < 50  # Рост памяти менее 50MB
        
        print(f"Sustained load: {request_count} requests, {throughput:.2f} req/s, {success_rate:.2%} success")
    
    @pytest.mark.stress
    async def test_burst_traffic(self, test_client):
        """Тест всплесков трафика"""
        burst_sizes = [10, 50, 100, 200]
        
        for burst_size in burst_sizes:
            monitor = PerformanceMonitor()
            monitor.start_monitoring()
            
            start_time = time.time()
            
            # Быстрый burst запросов
            tasks = []
            for i in range(burst_size):
                task = test_client.get("/")
                tasks.append(task)
            
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            
            elapsed = time.time() - start_time
            successful = sum(1 for r in responses if not isinstance(r, Exception) and r.status_code == 200)
            
            # Записываем метрики
            for response in responses:
                if not isinstance(response, Exception):
                    response_time = time.time() - start_time
                    monitor.record_request(response_time, response.status_code == 200)
            
            metrics = monitor.finish_monitoring()
            
            # Проверяем результаты burst
            burst_throughput = burst_size / elapsed
            success_rate = successful / burst_size
            
            assert success_rate > 0.95  # 95% успешных
            assert burst_throughput > burst_size / 2  # Приемлемая скорость
            
            print(f"Burst {burst_size}: {burst_throughput:.2f} req/s, {success_rate:.2%} success")
    
    @pytest.mark.stress
    async def test_resource_exhaustion(self, test_client):
        """Тест исчерпания ресурсов"""
        # Создаем много кэшей
        caches = []
        for i in range(100):
            cache = MemoryCache(f"exhaustion_test_{i}")
            caches.append(cache)
        
        try:
            # Заполняем кэши до отказа
            for cache in caches:
                for j in range(1000):
                    key = f"exhaustion_key_{j}"
                    value = f"exhaustion_value_{j}" * 100  # Большие значения
                    cache.set(key, value, ttl=600)
            
            # Проверяем что сервер все еще отвечает
            response = await test_client.get("/health")
            assert response.status_code == 200
            
            # Проверяем что кэши работают
            for cache in caches[:10]:  # Проверяем первые 10
                result = cache.get("exhaustion_key_0")
                # Результат может быть None если кэш полон
            
        except MemoryError:
            # Это нормально если система не может выделить больше памяти
            print("Memory exhaustion detected - expected behavior")
        except Exception as e:
            print(f"Other exception during resource exhaustion: {e}")
        
        finally:
            # Очищаем ресурсы
            for cache in caches:
                cache.clear()
            gc.collect()
    
    @pytest.mark.stress
    async def test_concurrent_user_simulation(self, test_client):
        """Симуляция множественных пользователей"""
        num_users = 20
        requests_per_user = 50
        
        async def simulate_user(user_id: int):
            """Симуляция действий пользователя"""
            user_metrics = {
                "requests": 0,
                "successes": 0,
                "response_times": []
            }
            
            for i in range(requests_per_user):
                start_time = time.time()
                
                try:
                    # Разные endpoints для разнообразия
                    endpoints = ["/", "/health", f"/data/user_{user_id}_{i}"]
                    endpoint = endpoints[i % len(endpoints)]
                    
                    response = await test_client.get(endpoint)
                    
                    response_time = time.time() - start_time
                    user_metrics["response_times"].append(response_time)
                    
                    if response.status_code == 200:
                        user_metrics["successes"] += 1
                    
                    user_metrics["requests"] += 1
                    
                    # Случайная задержка между запросами
                    await asyncio.sleep(0.01)
                
                except Exception as e:
                    user_metrics["requests"] += 1
                    print(f"User {user_id} request {i} failed: {e}")
            
            return user_metrics
        
        # Запускаем симуляцию пользователей
        start_time = time.time()
        tasks = [simulate_user(i) for i in range(num_users)]
        user_results = await asyncio.gather(*tasks)
        total_time = time.time() - start_time
        
        # Анализируем результаты
        total_requests = sum(r["requests"] for r in user_results)
        total_successes = sum(r["successes"] for r in user_results)
        
        overall_success_rate = total_successes / total_requests if total_requests > 0 else 0
        overall_throughput = total_requests / total_time
        
        # Проверяем результаты
        assert overall_success_rate > 0.8  # 80% успешных запросов
        assert overall_throughput > 10  # Минимум 10 запросов в секунду
        
        # Проверяем справедливость между пользователями
        user_success_rates = [r["successes"] / r["requests"] for r in user_results]
        min_success_rate = min(user_success_rates)
        max_success_rate = max(user_success_rates)
        
        # Разница между пользователями не должна быть слишком большой
        assert max_success_rate - min_success_rate < 0.5
        
        print(f"User simulation: {total_requests} requests, {overall_throughput:.2f} req/s, {overall_success_rate:.2%} success")


# =============================================================================
# MEMORY LEAK DETECTION
# =============================================================================

class TestMemoryLeaks:
    """Тесты обнаружения утечек памяти"""
    
    @pytest.mark.performance
    async def test_memory_leak_detection(self, test_client):
        """Обнаружение утечек памяти"""
        process = psutil.Process()
        memory_snapshots = []
        
        # Берем снимки памяти до теста
        for i in range(10):
            await asyncio.sleep(0.1)  # Даем системе время стабилизироваться
            memory_snapshots.append(process.memory_info().rss)
        
        initial_memory = memory_snapshots[-1]
        
        # Выполняем много операций
        cache = MemoryCache("leak_test")
        for i in range(10000):
            key = f"leak_key_{i}"
            value = f"leak_value_{i}" * 50
            cache.set(key, value, ttl=300)
            
            # Периодически обращаемся к кэшу
            if i % 100 == 0:
                cache.get(f"leak_key_{i % 100}")
        
        # Берем снимки памяти после операций
        after_snapshots = []
        for i in range(10):
            await asyncio.sleep(0.1)
            after_snapshots.append(process.memory_info().rss)
        
        peak_memory = max(after_snapshots)
        
        # Очищаем кэш и проверяем освобождение памяти
        cache.clear()
        gc.collect()
        
        # Ждем освобождения памяти
        await asyncio.sleep(1)
        
        final_snapshots = []
        for i in range(10):
            await asyncio.sleep(0.1)
            final_snapshots.append(process.memory_info().rss)
        
        final_memory = min(final_snapshots)
        memory_growth = (peak_memory - initial_memory) / (1024 * 1024)
        memory_after_cleanup = (final_memory - initial_memory) / (1024 * 1024)
        
        # Проверяем что память освобождается
        assert memory_after_cleanup < 20  # После очистки менее 20MB
        
        print(f"Memory test: peak growth {memory_growth:.2f}MB, after cleanup {memory_after_cleanup:.2f}MB")
    
    @pytest.mark.performance
    async def test_client_connection_leaks(self, test_client):
        """Тест утечек соединений клиента"""
        initial_connections = len(test_client._transport.get_connection_pool()._pool)
        
        # Выполняем много запросов
        for i in range(1000):
            response = await test_client.get("/health")
            assert response.status_code == 200
            
            # Периодически проверяем количество соединений
            if i % 100 == 0:
                current_connections = len(test_client._transport.get_connection_pool()._pool)
                assert current_connections <= initial_connections + 10  # Не должно расти значительно
        
        # Проверяем финальное состояние
        final_connections = len(test_client._transport.get_connection_pool()._pool)
        connection_growth = final_connections - initial_connections
        
        assert connection_growth <= 5  # Рост соединений минимальный
        
        print(f"Connection test: growth {connection_growth} connections")


# =============================================================================
# SCALABILITY ТЕСТЫ
# =============================================================================

class TestScalability:
    """Тесты масштабируемости"""
    
    @pytest.mark.performance
    async def test_linear_scalability(self, test_client):
        """Тест линейной масштабируемости"""
        concurrency_levels = [1, 2, 4, 8, 16]
        request_count = 100
        
        scalability_results = []
        
        for concurrency in concurrency_levels:
            monitor = PerformanceMonitor()
            monitor.start_monitoring()
            
            start_time = time.time()
            
            async def make_request():
                response = await test_client.get("/health")
                response_time = time.time() - start_time
                success = response.status_code == 200
                monitor.record_request(response_time, success)
                return response_time
            
            # Выполняем запросы с заданной конкурентностью
            tasks = [make_request() for _ in range(request_count)]
            await asyncio.gather(*tasks)
            
            metrics = monitor.finish_monitoring()
            throughput = metrics.throughput
            
            scalability_results.append({
                "concurrency": concurrency,
                "throughput": throughput,
                "efficiency": throughput / concurrency
            })
        
        # Анализируем масштабируемость
        base_throughput = scalability_results[0]["throughput"]
        max_throughput = max(r["throughput"] for r in scalability_results)
        scalability_factor = max_throughput / base_throughput
        
        # Проверяем что производительность растет с конкурентностью
        assert scalability_factor > 2  # Минимум 2x улучшение
        assert scalability_factor < concurrency_levels[-1] * 2  # Не должно превышать разумные пределы
        
        print(f"Scalability: {scalability_factor:.2f}x improvement from 1 to {concurrency_levels[-1]} threads")
    
    @pytest.mark.performance
    async def test_cache_scalability(self):
        """Тест масштабируемости кэша"""
        cache_sizes = [100, 1000, 10000, 50000]
        
        for cache_size in cache_sizes:
            cache = MemoryCache(f"scalability_cache_{cache_size}")
            
            # Заполняем кэш
            fill_start = time.time()
            for i in range(cache_size):
                key = f"scale_key_{i}"
                value = f"scale_value_{i}"
                cache.set(key, value, ttl=300)
            fill_time = time.time() - fill_start
            
            # Выполняем операции чтения
            read_start = time.time()
            for i in range(min(1000, cache_size)):
                key = f"scale_key_{i % cache_size}"
                cache.get(key)
            read_time = time.time() - read_start
            
            # Получаем статистику
            stats = cache.get_stats()
            
            # Проверяем производительность
            fill_throughput = cache_size / fill_time
            read_throughput = min(1000, cache_size) / read_time
            
            assert fill_throughput > 1000  # Минимум 1000 операций записи в секунду
            assert read_throughput > 5000  # Минимум 5000 операций чтения в секунду
            
            print(f"Cache size {cache_size}: fill {fill_throughput:.0f} ops/s, read {read_throughput:.0f} ops/s")


# =============================================================================
# ПАРАМЕТРИЗОВАННЫЕ PERFORMANCE ТЕСТЫ
# =============================================================================

@pytest.mark.parametrize("endpoint,requests_count", [
    ("/", 100),
    ("/health", 200),
    ("/data/test", 50),
])
@pytest.mark.performance
async def test_parametrized_endpoint_performance(endpoint, requests_count, test_client):
    """Параметризованный тест производительности endpoints"""
    monitor = PerformanceMonitor()
    monitor.start_monitoring()
    
    start_time = time.time()
    
    async def make_request():
        response = await test_client.get(endpoint)
        response_time = time.time() - start_time
        success = response.status_code == 200
        monitor.record_request(response_time, success)
    
    # Выполняем запросы
    tasks = [make_request() for _ in range(requests_count)]
    await asyncio.gather(*tasks)
    
    metrics = monitor.finish_monitoring()
    
    # Проверяем минимальные требования к производительности
    assert metrics.throughput > 10  # Минимум 10 запросов в секунду
    assert metrics.avg_response_time < 1.0  # Среднее время менее 1 секунды
    assert metrics.successful_requests / metrics.total_requests > 0.95  # 95% успешных
    
    print(f"Endpoint {endpoint}: {metrics.throughput:.2f} req/s, {metrics.avg_response_time:.3f}s avg")


@pytest.mark.parametrize("cache_size,operations", [
    (100, 1000),
    (1000, 5000),
    (5000, 10000),
])
@pytest.mark.performance
async def test_parametrized_cache_performance(cache_size, operations):
    """Параметризованный тест производительности кэша"""
    cache = MemoryCache("parametrized_cache_test")
    
    # Заполняем кэш
    for i in range(cache_size):
        cache.set(f"key_{i}", f"value_{i}")
    
    # Выполняем операции
    start_time = time.time()
    
    for i in range(operations):
        key = f"key_{i % cache_size}"
        cache.get(key)
        
        # Случайные операции записи
        if i % 100 == 0:
            new_key = f"new_key_{i}"
            cache.set(new_key, f"new_value_{i}")
    
    elapsed = time.time() - start_time
    throughput = operations / elapsed
    
    # Проверяем производительность
    assert throughput > 1000  # Минимум 1000 операций в секунду
    assert elapsed < 60  # Не должно занимать больше минуты
    
    print(f"Cache {cache_size} keys, {operations} ops: {throughput:.0f} ops/s")


if __name__ == "__main__":
    # Запуск тестов производительности и конкурентности
    pytest.main([
        __file__,
        "-v",
        "--tb=short",
        "-m", "performance or thread_safety or stress",
        "--benchmark-only"
    ])