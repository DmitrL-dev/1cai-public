
"""
Бенчмарки для алгоритмов rate limiting.

Проводит comprehensive тестирование производительности:
- Скорость обработки запросов (RPS)
- Время отклика
- Использование памяти
- Точность лимитов
- Производительность при высокой нагрузке
- Поведение под нагрузкой (stress testing)
"""

import concurrent.futures
import gc
import statistics
import time
from typing import Any, Dict, List, Tuple

import matplotlib.pyplot as plt
import psutil
from sliding_window import (FixedWindowCounter, LeakyBucket,
                            SlidingWindowAlgorithm, TokenBucket)


class BenchmarkSuite:
    """Набор бенчмарков для алгоритмов rate limiting"""
    
    def __init__(self):
        self.process = psutil.Process()
        self.results = {}
    
    def measure_memory_usage(self, func, *args, **kwargs) -> Tuple[Any, int]:
        """Измерить использование памяти при выполнении функции"""
        gc.collect()  # Принудительная сборка мусора
        
        memory_before = self.process.memory_info().rss / 1024  # KB
        
        result = func(*args, **kwargs)
        
        memory_after = self.process.memory_info().rss / 1024  # KB
        memory_used = memory_after - memory_before
        
        return result, memory_used
    
    def run_throughput_test(self, algorithm, test_duration: float = 5.0, 
                          concurrent_users: int = 10) -> Dict[str, float]:
        """
        Тест пропускной способности алгоритма.
        
        Args:
            algorithm: Алгоритм для тестирования
            test_duration: Продолжительность теста в секундах
            concurrent_users: Количество одновременных пользователей
            
        Returns:
            Метрики производительности
        """
        print(f"Запуск теста пропускной способности: {concurrent_users} пользователей, {test_duration}s")
        
        results = {
            'total_requests': 0,
            'allowed_requests': 0,
            'denied_requests': 0,
            'errors': 0,
            'start_time': 0,
            'end_time': 0,
            'memory_used_kb': 0
        }
        
        def worker_thread(worker_id: int):
            """Воркер для имитации пользователя"""
            local_stats = {
                'requests': 0,
                'allowed': 0,
                'denied': 0,
                'errors': 0
            }
            
            try:
                end_time = time.time() + test_duration
                
                while time.time() < end_time:
                    try:
                        allowed, _ = algorithm.check_rate_limit(f"user_{worker_id}")
                        local_stats['requests'] += 1
                        
                        if allowed:
                            local_stats['allowed'] += 1
                        else:
                            local_stats['denied'] += 1
                        
                        # Небольшая задержка для реалистичности
                        time.sleep(0.001)  # 1ms
                        
                    except Exception as e:
                        local_stats['errors'] += 1
                        
            except Exception as e:
                print(f"Ошибка в воркере {worker_id}: {e}")
            
            return local_stats
        
        # Запуск воркеров
        start_time = time.time()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_users) as executor:
            futures = [executor.submit(worker_thread, i) for i in range(concurrent_users)]
            
            # Измерение памяти
            def run_test():
                return [future.result() for future in concurrent.futures.as_completed(futures)]
            
            worker_results, memory_used = self.measure_memory_usage(run_test)
        
        end_time = time.time()
        results['start_time'] = start_time
        results['end_time'] = end_time
        results['memory_used_kb'] = memory_used
        
        # Агрегация результатов
        for worker_stats in worker_results:
            results['total_requests'] += worker_stats['requests']
            results['allowed_requests'] += worker_stats['allowed']
            results['denied_requests'] += worker_stats['denied']
            results['errors'] += worker_stats['errors']
        
        # Расчет метрик
        total_time = end_time - start_time
        results['rps'] = results['total_requests'] / total_time
        results['allowed_rps'] = results['allowed_requests'] / total_time
        results['denied_rps'] = results['denied_requests'] / total_time
        results['error_rate'] = results['errors'] / results['total_requests'] * 100 if results['total_requests'] > 0 else 0
        
        return results
    
    def run_response_time_test(self, algorithm, num_requests: int = 1000) -> Dict[str, float]:
        """
        Тест времени отклика алгоритма.
        
        Args:
            algorithm: Алгоритм для тестирования
            num_requests: Количество запросов
            
        Returns:
            Статистика времени отклика
        """
        print(f"Запуск теста времени отклика: {num_requests} запросов")
        
        response_times = []
        
        for i in range(num_requests):
            start_time = time.perf_counter()
            
            try:
                allowed, _ = algorithm.check_rate_limit("response_time_test")
                end_time = time.perf_counter()
                
                response_time_ms = (end_time - start_time) * 1000
                response_times.append(response_time_ms)
                
            except Exception as e:
                print(f"Ошибка при тестировании времени отклика: {e}")
        
        if not response_times:
            return {"error": "Нет данных для анализа"}
        
        return {
            'mean_ms': statistics.mean(response_times),
            'median_ms': statistics.median(response_times),
            'std_ms': statistics.stdev(response_times) if len(response_times) > 1 else 0,
            'min_ms': min(response_times),
            'max_ms': max(response_times),
            'p95_ms': self._percentile(response_times, 95),
            'p99_ms': self._percentile(response_times, 99),
            'total_requests': len(response_times)
        }
    
    def _percentile(self, data: List[float], percentile: int) -> float:
        """Рассчитать перцентиль"""
        sorted_data = sorted(data)
        index = (percentile / 100) * (len(sorted_data) - 1)
        
        if index.is_integer():
            return sorted_data[int(index)]
        else:
            lower_index = int(index)
            upper_index = min(lower_index + 1, len(sorted_data) - 1)
            weight = index - lower_index
            return sorted_data[lower_index] * (1 - weight) + sorted_data[upper_index] * weight
    
    def run_accuracy_test(self, algorithm, limit: int, window_seconds: int, 
                         test_duration: float = 10.0) -> Dict[str, Any]:
        """
        Тест точности соблюдения лимитов.
        
        Args:
            algorithm: Алгоритм для тестирования
            limit: Установленный лимит
            window_seconds: Размер окна в секундах
            test_duration: Продолжительность теста
            
        Returns:
            Анализ точности соблюдения лимитов
        """
        print(f"Запуск теста точности: лимит={limit}, окно={window_seconds}s")
        
        # Быстрая отправка запросов для проверки лимитов
        request_times = []
        allowed_count = 0
        denied_count = 0
        
        start_time = time.time()
        
        while time.time() - start_time < test_duration:
            try:
                allowed, info = algorithm.check_rate_limit("accuracy_test")
                
                request_times.append(time.time())
                
                if allowed:
                    allowed_count += 1
                else:
                    denied_count += 1
                    
            except Exception as e:
                print(f"Ошибка при тестировании точности: {e}")
        
        # Анализ результатов
        results = {
            'total_requests': allowed_count + denied_count,
            'allowed_requests': allowed_count,
            'denied_requests': denied_count,
            'configured_limit': limit,
            'window_seconds': window_seconds,
            'actual_rate_per_second': allowed_count / test_duration,
            'accuracy_score': self._calculate_accuracy(allowed_count, limit, test_duration)
        }
        
        return results
    
    def _calculate_accuracy(self, actual_allowed: int, limit: int, time_window: float) -> float:
        """Рассчитать точность соблюдения лимита"""
        expected_allowed = limit * (time_window / 60)  # Примерное ожидаемое количество
        if expected_allowed == 0:
            return 100.0
        
        error_rate = abs(actual_allowed - expected_allowed) / expected_allowed
        accuracy = max(0, 100 - (error_rate * 100))
        return accuracy
    
    def run_memory_efficiency_test(self, algorithm, num_unique_keys: int = 10000) -> Dict[str, Any]:
        """
        Тест эффективности использования памяти.
        
        Args:
            algorithm: Алгоритм для тестирования
            num_unique_keys: Количество уникальных ключей
            
        Returns:
            Анализ использования памяти
        """
        print(f"Запуск теста эффективности памяти: {num_unique_keys} уникальных ключей")
        
        # Очистка памяти перед тестом
        gc.collect()
        memory_before = self.process.memory_info().rss / 1024  # KB
        
        # Генерация запросов с разными ключами
        for i in range(num_unique_keys):
            try:
                algorithm.check_rate_limit(f"key_{i}")
                
                # Периодическая проверка памяти
                if i % 1000 == 0:
                    current_memory = self.process.memory_info().rss / 1024
                    print(f"  Ключей обработано: {i}, память: {current_memory:.2f} KB")
                    
            except Exception as e:
                print(f"Ошибка при тестировании памяти: {e}")
        
        memory_after = self.process.memory_info().rss / 1024  # KB
        memory_used = memory_after - memory_before
        
        return {
            'memory_used_kb': memory_used,
            'memory_per_key_bytes': (memory_used * 1024) / num_unique_keys,
            'num_keys_tested': num_unique_keys
        }
    
    def run_stress_test(self, algorithm, max_concurrent: int = 100, 
                       duration: float = 30.0) -> Dict[str, Any]:
        """
        Стресс-тест алгоритма под высокой нагрузкой.
        
        Args:
            algorithm: Алгоритм для тестирования
            max_concurrent: Максимальное количество одновременных запросов
            duration: Продолжительность теста
            
        Returns:
            Результаты стресс-теста
        """
        print(f"Запуск стресс-теста: до {max_concurrent} одновременных запросов, {duration}s")
        
        results = {
            'peak_concurrent': 0,
            'total_requests': 0,
            'errors': 0,
            'max_response_time_ms': 0,
            'avg_response_time_ms': 0
        }
        
        def stress_worker(worker_id: int, duration: float):
            """Воркер для стресс-теста"""
            local_stats = {
                'requests': 0,
                'errors': 0,
                'response_times': []
            }
            
            end_time = time.time() + duration
            
            try:
                while time.time() < end_time:
                    try:
                        start_time = time.perf_counter()
                        allowed, _ = algorithm.check_rate_limit(f"stress_user_{worker_id}")
                        end_time_req = time.perf_counter()
                        
                        response_time_ms = (end_time_req - start_time) * 1000
                        local_stats['response_times'].append(response_time_ms)
                        local_stats['requests'] += 1
                        
                        # Максимальная нагрузка без задержек
                        
                    except Exception as e:
                        local_stats['errors'] += 1
                        
            except Exception as e:
                print(f"Ошибка в стресс-воркере {worker_id}: {e}")
            
            return local_stats
        
        # Постепенное увеличение нагрузки
        for concurrent_level in range(10, max_concurrent + 1, 10):
            print(f"  Тестирование уровня нагрузки: {concurrent_level} воркеров")
            
            # Запуск воркеров
            start_time = time.time()
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_level) as executor:
                futures = [executor.submit(stress_worker, i, duration) for i in range(concurrent_level)]
                
                worker_results = [future.result() for future in concurrent.futures.as_completed(futures)]
            
            end_time = time.time()
            
            # Агрегация результатов
            total_requests = sum(w['requests'] for w in worker_results)
            total_errors = sum(w['errors'] for w in worker_results)
            
            # Поиск максимального времени отклика
            all_response_times = []
            for worker_stats in worker_results:
                all_response_times.extend(worker_stats['response_times'])
            
            max_response_time = max(all_response_times) if all_response_times else 0
            avg_response_time = statistics.mean(all_response_times) if all_response_times else 0
            
            # Обновление результатов
            results['peak_concurrent'] = max(results['peak_concurrent'], concurrent_level)
            results['total_requests'] += total_requests
            results['errors'] += total_errors
            results['max_response_time_ms'] = max(results['max_response_time_ms'], max_response_time)
            results['avg_response_time_ms'] = max(results['avg_response_time_ms'], avg_response_time)
            
            # Проверка на деградацию производительности
            if avg_response_time > 100:  # 100ms
                print(f"  Предупреждение: деградация производительности на уровне {concurrent_level}")
                break
        
        return results
    
    def run_comprehensive_benchmark(self, algorithms: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """
        Запуск комплексного бенчмарка для всех алгоритмов.
        
        Args:
            algorithms: Словарь {название: алгоритм}
            
        Returns:
            Полные результаты бенчмарков
        """
        print("Запуск комплексного бенчмарка алгоритмов rate limiting")
        print("=" * 60)
        
        benchmark_results = {}
        
        for name, algorithm in algorithms.items():
            print(f"\nБенчмарк алгоритма: {name}")
            print("-" * 40)
            
            # Сброс алгоритма
            algorithm.reset()
            
            results = {
                'algorithm_name': name,
                'throughput': None,
                'response_time': None,
                'accuracy': None,
                'memory_efficiency': None,
                'stress_test': None
            }
            
            try:
                # Тест пропускной способности
                print("  Выполняется тест пропускной способности...")
                results['throughput'] = self.run_throughput_test(
                    algorithm, test_duration=5.0, concurrent_users=20
                )
                
                # Тест времени отклика
                print("  Выполняется тест времени отклика...")
                results['response_time'] = self.run_response_time_test(
                    algorithm, num_requests=1000
                )
                
                # Тест точности (только для простых алгоритмов)
                if name in ['sliding_window', 'fixed_window', 'token_bucket']:
                    print("  Выполняется тест точности...")
                    results['accuracy'] = self.run_accuracy_test(
                        algorithm, limit=100, window_seconds=60
                    )
                
                # Тест эффективности памяти
                print("  Выполняется тест эффективности памяти...")
                results['memory_efficiency'] = self.run_memory_efficiency_test(
                    algorithm, num_unique_keys=1000
                )
                
                # Стресс-тест (упрощенный)
                print("  Выполняется стресс-тест...")
                results['stress_test'] = self.run_stress_test(
                    algorithm, max_concurrent=50, duration=10.0
                )
                
            except Exception as e:
                print(f"  Ошибка при бенчмарке {name}: {e}")
                results['error'] = str(e)
            
            benchmark_results[name] = results
            
            # Краткий отчет
            if results.get('throughput'):
                print(f"  RPS: {results['throughput']['rps']:.2f}")
            if results.get('response_time'):
                print(f"  Среднее время ответа: {results['response_time']['mean_ms']:.2f}ms")
            if results.get('memory_efficiency'):
                print(f"  Использование памяти: {results['memory_efficiency']['memory_used_kb']:.2f} KB")
        
        return benchmark_results
    
    def generate_report(self, results: Dict[str, Dict[str, Any]]) -> str:
        """
        Сгенерировать детальный отчет по результатам бенчмарков.
        
        Args:
            results: Результаты бенчмарков
            
        Returns:
            Текстовый отчет
        """
        report = []
        report.append("ОТЧЕТ ПО БЕНЧМАРКАМ АЛГОРИТМОВ RATE LIMITING")
        report.append("=" * 60)
        report.append("")
        
        # Общая таблица результатов
        report.append("СРАВНИТЕЛЬНАЯ ТАБЛИЦА ПРОИЗВОДИТЕЛЬНОСТИ")
        report.append("-" * 60)
        report.append(f"{'Алгоритм':<20} {'RPS':<12} {'Время ответа (ms)':<18} {'Память (KB)':<12}")
        report.append("-" * 60)
        
        for name, result in results.items():
            if result.get('error'):
                report.append(f"{name:<20} {'ERROR':<12} {'ERROR':<18} {'ERROR':<12}")
                continue
                
            rps = result.get('throughput', {}).get('rps', 0)
            avg_time = result.get('response_time', {}).get('mean_ms', 0)
            memory = result.get('memory_efficiency', {}).get('memory_used_kb', 0)
            
            report.append(f"{name:<20} {rps:<12.2f} {avg_time:<18.2f} {memory:<12.2f}")
        
        report.append("")
        
        # Детальная информация по каждому алгоритму
        for name, result in results.items():
            report.append(f"ДЕТАЛЬНЫЙ АНАЛИЗ: {name.upper()}")
            report.append("-" * 40)
            
            if result.get('error'):
                report.append(f"ОШИБКА: {result['error']}")
                report.append("")
                continue
            
            # Пропускная способность
            throughput = result.get('throughput', {})
            if throughput:
                report.append("Пропускная способность:")
                report.append(f"  Всего запросов: {throughput.get('total_requests', 0)}")
                report.append(f"  RPS: {throughput.get('rps', 0):.2f}")
                report.append(f"  Разрешено: {throughput.get('allowed_requests', 0)}")
                report.append(f"  Запрещено: {throughput.get('denied_requests', 0)}")
                report.append(f"  Ошибки: {throughput.get('errors', 0)}")
                report.append("")
            
            # Время отклика
            response_time = result.get('response_time', {})
            if response_time:
                report.append("Время отклика:")
                report.append(f"  Среднее: {response_time.get('mean_ms', 0):.2f}ms")
                report.append(f"  Медиана: {response_time.get('median_ms', 0):.2f}ms")
                report.append(f"  P95: {response_time.get('p95_ms', 0):.2f}ms")
                report.append(f"  P99: {response_time.get('p99_ms', 0):.2f}ms")
                report.append(f"  Минимум: {response_time.get('min_ms', 0):.2f}ms")
                report.append(f"  Максимум: {response_time.get('max_ms', 0):.2f}ms")
                report.append("")
            
            # Точность
            accuracy = result.get('accuracy', {})
            if accuracy:
                report.append("Точность лимитов:")
                report.append(f"  Точность: {accuracy.get('accuracy_score', 0):.1f}%")
                report.append(f"  Фактическая скорость: {accuracy.get('actual_rate_per_second', 0):.2f} req/s")
                report.append("")
            
            # Память
            memory = result.get('memory_efficiency', {})
            if memory:
                report.append("Использование памяти:")
                report.append(f"  Всего использовано: {memory.get('memory_used_kb', 0):.2f} KB")
                report.append(f"  На ключ: {memory.get('memory_per_key_bytes', 0):.2f} байт")
                report.append("")
            
            # Стресс-тест
            stress = result.get('stress_test', {})
            if stress:
                report.append("Стресс-тест:")
                report.append(f"  Пиковая нагрузка: {stress.get('peak_concurrent', 0)} воркеров")
                report.append(f"  Всего запросов: {stress.get('total_requests', 0)}")
                report.append(f"  Ошибки: {stress.get('errors', 0)}")
                report.append(f"  Макс. время ответа: {stress.get('max_response_time_ms', 0):.2f}ms")
                report.append("")
            
            report.append("")
        
        # Рекомендации
        report.append("РЕКОМЕНДАЦИИ ПО ВЫБОРУ АЛГОРИТМА")
        report.append("-" * 40)
        
        # Находим лучший по разным критериям
        best_rps = max(results.items(), key=lambda x: x[1].get('throughput', {}).get('rps', 0))
        best_response = min(results.items(), key=lambda x: x[1].get('response_time', {}).get('mean_ms', float('inf')))
        best_memory = min(results.items(), key=lambda x: x[1].get('memory_efficiency', {}).get('memory_used_kb', float('inf')))
        
        report.append(f"Максимальная производительность: {best_rps[0]} ({best_rps[1].get('throughput', {}).get('rps', 0):.2f} RPS)")
        report.append(f"Минимальное время ответа: {best_response[0]} ({best_response[1].get('response_time', {}).get('mean_ms', 0):.2f}ms)")
        report.append(f"Минимальное использование памяти: {best_memory[0]} ({best_memory[1].get('memory_efficiency', {}).get('memory_used_kb', 0):.2f} KB)")
        
        return "\n".join(report)


def create_benchmark_scenarios() -> Dict[str, Dict]:
    """
    Создать типичные сценарии для тестирования.
    
    Returns:
        Словарь сценариев тестирования
    """
    scenarios = {
        'high_throughput': {
            'description': 'Высокая пропускная способность (много коротких запросов)',
            'limit': 1000,
            'window_seconds': 60,
            'capacity': 100,
            'refill_rate': 2.0,
            'leak_rate': 2.0
        },
        'burst_control': {
            'description': 'Контроль всплесков (поддержка burst трафика)',
            'limit': 100,
            'window_seconds': 10,
            'capacity': 50,
            'refill_rate': 1.0,
            'leak_rate': 0.5
        },
        'tight_limits': {
            'description': 'Жесткие лимиты (низкие значения)',
            'limit': 10,
            'window_seconds': 60,
            'capacity': 5,
            'refill_rate': 0.1,
            'leak_rate': 0.1
        },
        'long_window': {
            'description': 'Длинные окна (длительные периоды)',
            'limit': 10000,
            'window_seconds': 3600,
            'capacity': 1000,
            'refill_rate': 10.0,
            'leak_rate': 5.0
        }
    }
    
    return scenarios


def run_complete_benchmark():
    """Запуск полного бенчмарка всех алгоритмов"""
    print("Запуск полного бенчмарка алгоритмов rate limiting")
    print("Это может занять несколько минут...")
    print()
    
    # Создание алгоритмов для тестирования
    algorithms = {
        'sliding_window': SlidingWindowAlgorithm(limit=100, window_seconds=60),
        'token_bucket': TokenBucket(capacity=50, refill_rate=1.0),
        'fixed_window': FixedWindowCounter(limit=100, window_seconds=60),
        'leaky_bucket': LeakyBucket(capacity=10, leak_rate=0.5)
    }
    
    # Создание бенчмарк-сьюта
    suite = BenchmarkSuite()
    
    # Запуск бенчмарков
    results = suite.run_comprehensive_benchmark(algorithms)
    
    # Генерация отчета
    report = suite.generate_report(results)
    
    # Сохранение отчета
    with open('/workspace/code/py_server/ratelimit/benchmark_report.txt', 'w', encoding='utf-8') as f:
        f.write(report)
    
    print("\n" + "="*60)
    print("ОТЧЕТ СОХРАНЕН В: /workspace/code/py_server/ratelimit/benchmark_report.txt")
    print("="*60)
    print()
    
    return results, report


if __name__ == "__main__":
    # Установка matplotlib для генерации графиков
    try:
        import matplotlib
        matplotlib.use('Agg')  # Без GUI
        import matplotlib.pyplot as plt
    except ImportError:
        print("Предупреждение: matplotlib не установлен. Графики не будут созданы.")
        plt = None
    
    # Запуск полного бенчмарка
    results, report = run_complete_benchmark()
    
    print("\nКраткий отчет:")
    print(report[:1000] + "..." if len(report) > 1000 else report)