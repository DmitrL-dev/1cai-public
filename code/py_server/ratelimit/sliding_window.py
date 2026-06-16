
"""
Алгоритмы скользящего окна для точного контроля лимитов запросов
на основе современных стандартов производительности 1С.

Поддерживает:
- Точность до секунды для критичных лимитов
- Оптимизация памяти (heap structure)
- Thread-safe операции
- Метрики производительности
- Сравнительный анализ эффективности
"""

import heapq
import logging
import statistics
import threading
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple


@dataclass
class RateLimitMetrics:
    """Метрики производительности алгоритма rate limiting"""
    algorithm_name: str
    total_requests: int = 0
    allowed_requests: int = 0
    denied_requests: int = 0
    avg_response_time_ms: float = 0.0
    max_response_time_ms: float = 0.0
    min_response_time_ms: float = float('inf')
    memory_usage_kb: int = 0
    
    def __post_init__(self):
        self.response_times: List[float] = []
    
    def record_request(self, response_time_ms: float, allowed: bool):
        """Записать метрику запроса"""
        self.total_requests += 1
        if allowed:
            self.allowed_requests += 1
        else:
            self.denied_requests += 1
        
        self.response_times.append(response_time_ms)
        self.max_response_time_ms = max(self.max_response_time_ms, response_time_ms)
        self.min_response_time_ms = min(self.min_response_time_ms, response_time_ms)
    
    def calculate_metrics(self):
        """Рассчитать финальные метрики"""
        if self.response_times:
            self.avg_response_time_ms = statistics.mean(self.response_times)
            self.min_response_time_ms = min(self.response_times)
        
        return {
            'total_requests': self.total_requests,
            'allowed_requests': self.allowed_requests,
            'denied_requests': self.denied_requests,
            'allowed_percentage': (self.allowed_requests / self.total_requests * 100) if self.total_requests > 0 else 0,
            'avg_response_time_ms': self.avg_response_time_ms,
            'max_response_time_ms': self.max_response_time_ms,
            'min_response_time_ms': self.min_response_time_ms if self.min_response_time_ms != float('inf') else 0,
            'memory_usage_kb': self.memory_usage_kb
        }


class BaseRateLimitAlgorithm:
    """Базовый класс для алгоритмов rate limiting"""
    
    def __init__(self, algorithm_name: str):
        self.metrics = RateLimitMetrics(algorithm_name)
        self._lock = threading.RLock()
        self.logger = logging.getLogger(f"ratelimit.{algorithm_name}")
    
    def check_rate_limit(self, key: str = "default") -> Tuple[bool, Dict[str, Any]]:
        """Проверить лимит запроса. Возвращает (разрешено, информация)"""
        start_time = time.perf_counter()
        
        try:
            with self._lock:
                allowed, info = self._check_rate_limit_impl(key)
            
            response_time_ms = (time.perf_counter() - start_time) * 1000
            self.metrics.record_request(response_time_ms, allowed)
            
            return allowed, info
            
        except Exception as e:
            self.logger.error(f"Ошибка в алгоритме {self.metrics.algorithm_name}: {e}")
            # В случае ошибки разрешаем запрос (fail-safe)
            return True, {"error": str(e)}
    
    def _check_rate_limit_impl(self, key: str) -> Tuple[bool, Dict[str, Any]]:
        """Внутренняя реализация проверки лимита"""
        raise NotImplementedError
    
    def reset(self):
        """Сбросить состояние алгоритма"""
        with self._lock:
            self._reset_impl()
    
    def _reset_impl(self):
        """Внутренняя реализация сброса"""
    
    def get_metrics(self) -> Dict[str, Any]:
        """Получить метрики алгоритма"""
        return self.metrics.calculate_metrics()


class SlidingWindowAlgorithm(BaseRateLimitAlgorithm):
    """
    Алгоритм скользящего окна с оптимизацией памяти через heap structure.
    
    Особенности:
    - Точность до секунды
    - Оптимизация памяти с помощью heap
    - Thread-safe операции
    - O(log n) для вставки и удаления
    """
    
    def __init__(self, limit: int, window_seconds: int):
        super().__init__("sliding_window")
        self.limit = limit
        self.window_seconds = window_seconds
        
        # Heap для хранения временных меток запросов
        # (timestamp, key) для оптимизации памяти
        self.requests_heap: List[Tuple[int, str]] = []
        
        # Кэш для быстрого доступа к счетчикам ключей
        self.key_counts: Dict[str, int] = defaultdict(int)
        
        # Последняя очистка для оптимизации
        self.last_cleanup = time.time()
    
    def _check_rate_limit_impl(self, key: str) -> Tuple[bool, Dict[str, Any]]:
        current_time = int(time.time())
        window_start = current_time - self.window_seconds
        
        # Периодическая очистка старых записей
        self._cleanup_old_requests(window_start)
        
        # Проверяем текущий лимит
        current_count = self.key_counts[key]
        
        if current_count < self.limit:
            # Разрешаем запрос
            self.requests_heap.append((current_time, key))
            self.key_counts[key] += 1
            heapq.heapify(self.requests_heap)  # Поддерживаем кучу
            
            return True, {
                "limit": self.limit,
                "window_seconds": self.window_seconds,
                "current_count": current_count + 1,
                "window_start": window_start,
                "algorithm": "sliding_window"
            }
        else:
            # Превышен лимит
            return False, {
                "limit": self.limit,
                "window_seconds": self.window_seconds,
                "current_count": current_count,
                "window_start": window_start,
                "reset_time": window_start + self.window_seconds,
                "algorithm": "sliding_window"
            }
    
    def _cleanup_old_requests(self, window_start: int):
        """Очистка старых запросов из heap с оптимизацией"""
        current_time = time.time()
        
        # Очищаем не чаще раза в секунду для производительности
        if current_time - self.last_cleanup < 1.0:
            return
        
        # Удаляем все записи старше window_start
        while self.requests_heap and self.requests_heap[0][0] <= window_start:
            timestamp, key = heapq.heappop(self.requests_heap)
            if self.key_counts[key] > 0:
                self.key_counts[key] -= 1
                # Удаляем ключ из кэша если счетчик равен нулю
                if self.key_counts[key] == 0:
                    del self.key_counts[key]
        
        self.last_cleanup = current_time
    
    def _reset_impl(self):
        """Сброс состояния алгоритма"""
        self.requests_heap.clear()
        self.key_counts.clear()
        self.last_cleanup = time.time()


class TokenBucket(BaseRateLimitAlgorithm):
    """
    Алгоритм Token Bucket для поддержки burst трафика.
    
    Особенности:
    - Поддержка кратковременных всплесков
    - Контролируемое потребление токенов
    - Эффективное восстановление токенов
    """
    
    def __init__(self, capacity: int, refill_rate: float):
        super().__init__("token_bucket")
        self.capacity = capacity
        self.refill_rate = refill_rate
        
        # Состояние каждого ключа
        self.buckets: Dict[str, Dict[str, float]] = {}
        self._lock = threading.RLock()
    
    def _check_rate_limit_impl(self, key: str) -> Tuple[bool, Dict[str, Any]]:
        current_time = time.time()
        
        # Получаем или создаем bucket для ключа
        if key not in self.buckets:
            self.buckets[key] = {
                "tokens": self.capacity,
                "last_refill": current_time
            }
        
        bucket = self.buckets[key]
        
        # Рассчитываем количество токенов для добавления
        time_passed = current_time - bucket["last_refill"]
        tokens_to_add = time_passed * self.refill_rate
        
        # Обновляем количество токенов
        current_tokens = min(self.capacity, bucket["tokens"] + tokens_to_add)
        
        if current_tokens >= 1:
            # Есть токен, потребляем его
            bucket["tokens"] = current_tokens - 1
            bucket["last_refill"] = current_time
            
            return True, {
                "capacity": self.capacity,
                "refill_rate": self.refill_rate,
                "available_tokens": bucket["tokens"],
                "tokens_consumed": 1,
                "algorithm": "token_bucket"
            }
        else:
            # Нет доступных токенов
            bucket["tokens"] = current_tokens
            bucket["last_refill"] = current_time
            
            return False, {
                "capacity": self.capacity,
                "refill_rate": self.refill_rate,
                "available_tokens": current_tokens,
                "next_token_in": 1 / self.refill_rate,
                "algorithm": "token_bucket"
            }
    
    def _reset_impl(self):
        """Сброс состояния алгоритма"""
        with self._lock:
            self.buckets.clear()


class FixedWindowCounter(BaseRateLimitAlgorithm):
    """
    Простой счетчик фиксированного окна.
    
    Особенности:
    - Простота реализации
    - Высокая производительность
    - Небольшая погрешность на границах окон
    """
    
    def __init__(self, limit: int, window_seconds: int):
        super().__init__("fixed_window")
        self.limit = limit
        self.window_seconds = window_seconds
        
        # Счетчики по окнам: (window_start, key) -> count
        self.window_counters: Dict[Tuple[int, str], int] = {}
        self.current_window: Dict[str, int] = {}
        
        # Время последнего переключения окна
        self.last_window_switch = int(time.time())
    
    def _check_rate_limit_impl(self, key: str) -> Tuple[bool, Dict[str, Any]]:
        current_time = int(time.time())
        current_window_start = (current_time // self.window_seconds) * self.window_seconds
        
        # Переключаем окно если нужно
        if current_window_start != self.last_window_switch:
            self._switch_window(current_window_start)
        
        current_count = self.current_window.get(key, 0)
        
        if current_count < self.limit:
            # Разрешаем запрос
            self.current_window[key] = current_count + 1
            
            return True, {
                "limit": self.limit,
                "window_seconds": self.window_seconds,
                "current_count": current_count + 1,
                "window_start": current_window_start,
                "window_end": current_window_start + self.window_seconds,
                "algorithm": "fixed_window"
            }
        else:
            # Превышен лимит
            return False, {
                "limit": self.limit,
                "window_seconds": self.window_seconds,
                "current_count": current_count,
                "window_start": current_window_start,
                "window_end": current_window_start + self.window_seconds,
                "reset_time": current_window_start + self.window_seconds,
                "algorithm": "fixed_window"
            }
    
    def _switch_window(self, new_window_start: int):
        """Переключение на новое окно"""
        # Сохраняем старое окно в архив
        if self.current_window:
            window_key = (self.last_window_switch, "archive")
            self.window_counters[window_key] = sum(self.current_window.values())
        
        # Очищаем текущее окно
        self.current_window.clear()
        self.last_window_switch = new_window_start
        
        # Ограничиваем размер архива
        if len(self.window_counters) > 1000:
            # Удаляем самые старые записи
            oldest_keys = sorted(self.window_counters.keys())[:100]
            for key in oldest_keys:
                del self.window_counters[key]
    
    def _reset_impl(self):
        """Сброс состояния алгоритма"""
        self.window_counters.clear()
        self.current_window.clear()
        self.last_window_switch = int(time.time())


class LeakyBucket(BaseRateLimitAlgorithm):
    """
    Алгоритм Leaky Bucket для постоянного потока.
    
    Особенности:
    - Равномерная обработка запросов
    - Контролируемая скорость вывода
    - Предотвращение всплесков
    """
    
    def __init__(self, capacity: int, leak_rate: float):
        super().__init__("leaky_bucket")
        self.capacity = capacity
        self.leak_rate = leak_rate
        
        # Состояние bucket для каждого ключа
        self.buckets: Dict[str, Dict[str, float]] = {}
    
    def _check_rate_limit_impl(self, key: str) -> Tuple[bool, Dict[str, Any]]:
        current_time = time.time()
        
        # Получаем или создаем bucket для ключа
        if key not in self.buckets:
            self.buckets[key] = {
                "water_level": 0.0,
                "last_leak": current_time
            }
        
        bucket = self.buckets[key]
        
        # Рассчитываем утечку
        time_passed = current_time - bucket["last_leak"]
        leaked_water = time_passed * self.leak_rate
        
        # Применяем утечку
        current_water = max(0, bucket["water_level"] - leaked_water)
        
        if current_water < self.capacity:
            # Добавляем запрос в bucket
            bucket["water_level"] = current_water + 1
            bucket["last_leak"] = current_time
            
            return True, {
                "capacity": self.capacity,
                "leak_rate": self.leak_rate,
                "current_level": bucket["water_level"],
                "water_added": 1,
                "algorithm": "leaky_bucket"
            }
        else:
            # Bucket переполнен
            bucket["water_level"] = current_water
            bucket["last_leak"] = current_time
            
            return False, {
                "capacity": self.capacity,
                "leak_rate": self.leak_rate,
                "current_level": current_water,
                "overflow": current_water - self.capacity,
                "next_leak_in": 1 / self.leak_rate,
                "algorithm": "leaky_bucket"
            }
    
    def _reset_impl(self):
        """Сброс состояния алгоритма"""
        self.buckets.clear()


class MultiWindowTracker(BaseRateLimitAlgorithm):
    """
    Комбинированные стратегии rate limiting с несколькими окнами.
    
    Особенности:
    - Множественные уровни ограничений
    - Гибкая настройка стратегий
    - Иерархический контроль
    """
    
    def __init__(self, window_configs: List[Dict[str, Any]]):
        super().__init__("multi_window")
        
        # Конфигурация окон
        self.window_configs = window_configs
        self.algorithms: List[BaseRateLimitAlgorithm] = []
        
        # Инициализируем алгоритмы
        for config in window_configs:
            algo_type = config.get("type")
            if algo_type == "sliding_window":
                algo = SlidingWindowAlgorithm(
                    config["limit"], 
                    config["window_seconds"]
                )
            elif algo_type == "fixed_window":
                algo = FixedWindowCounter(
                    config["limit"], 
                    config["window_seconds"]
                )
            elif algo_type == "token_bucket":
                algo = TokenBucket(
                    config["capacity"], 
                    config["refill_rate"]
                )
            elif algo_type == "leaky_bucket":
                algo = LeakyBucket(
                    config["capacity"], 
                    config["leak_rate"]
                )
            else:
                raise ValueError(f"Неизвестный тип алгоритма: {algo_type}")
            
            self.algorithms.append(algo)
    
    def _check_rate_limit_impl(self, key: str) -> Tuple[bool, Dict[str, Any]]:
        # Проверяем все алгоритмы
        results = []
        
        for i, algo in enumerate(self.algorithms):
            config = self.window_configs[i]
            allowed, info = algo._check_rate_limit_impl(key)
            
            result = {
                "window_name": config.get("name", f"window_{i}"),
                "algorithm_type": config.get("type"),
                "allowed": allowed,
                "info": info
            }
            results.append(result)
            
            # Если любой алгоритм запрещает, общий результат - запрет
            if not allowed:
                return False, {
                    "results": results,
                    "overall_allowed": False,
                    "denied_by": result["window_name"],
                    "algorithm": "multi_window"
                }
        
        # Все алгоритмы разрешили
        return True, {
            "results": results,
            "overall_allowed": True,
            "algorithm": "multi_window"
        }
    
    def _reset_impl(self):
        """Сброс состояния всех алгоритмов"""
        for algo in self.algorithms:
            algo.reset()


class RateLimitManager:
    """
    Менеджер для управления множественными алгоритмами rate limiting.
    
    Особенности:
    - Управление несколькими алгоритмами
    - Сравнительная аналитика
    - Автоматический выбор оптимального алгоритма
    """
    
    def __init__(self):
        self.algorithms: Dict[str, BaseRateLimitAlgorithm] = {}
        self.comparison_results: Dict[str, Dict[str, Any]] = {}
        self.logger = logging.getLogger("ratelimit.manager")
    
    def add_algorithm(self, name: str, algorithm: BaseRateLimitAlgorithm):
        """Добавить алгоритм"""
        self.algorithms[name] = algorithm
        self.logger.info(f"Добавлен алгоритм: {name}")
    
    def check_rate_limit(self, algorithm_name: str, key: str = "default") -> Tuple[bool, Dict[str, Any]]:
        """Проверить лимит с использованием конкретного алгоритма"""
        if algorithm_name not in self.algorithms:
            raise ValueError(f"Алгоритм {algorithm_name} не найден")
        
        return self.algorithms[algorithm_name].check_rate_limit(key)
    
    def compare_algorithms(self, test_requests: int = 1000, key: str = "test") -> Dict[str, Any]:
        """
        Сравнить производительность всех алгоритмов.
        
        Args:
            test_requests: Количество тестовых запросов
            key: Ключ для тестирования
            
        Returns:
            Сравнительные результаты
        """
        self.logger.info(f"Начинаем сравнение алгоритмов с {test_requests} запросами")
        
        for name, algorithm in self.algorithms.copy().items():
            # Сброс алгоритма
            algorithm.reset()
            
            # Тестирование
            start_time = time.perf_counter()
            
            for i in range(test_requests):
                allowed, _ = algorithm.check_rate_limit(key)
                if i % 100 == 0:
                    # Периодический лог прогресса
                    self.logger.debug(f"Алгоритм {name}: {i}/{test_requests} запросов")
            
            end_time = time.perf_counter()
            
            # Сохраняем результаты
            metrics = algorithm.get_metrics()
            metrics["total_test_time_seconds"] = end_time - start_time
            metrics["requests_per_second"] = test_requests / (end_time - start_time)
            
            self.comparison_results[name] = metrics
            
            self.logger.info(f"Алгоритм {name}: {metrics['requests_per_second']:.2f} RPS")
        
        return self.comparison_results
    
    def get_recommendation(self) -> str:
        """Получить рекомендацию по оптимальному алгоритму"""
        if not self.comparison_results:
            return "Необходимо сначала запустить сравнение алгоритмов"
        
        best_algo = max(
            self.comparison_results.items(),
            key=lambda x: x[1]['requests_per_second']
        )
        
        algo_name, metrics = best_algo
        
        recommendation = f"""
Рекомендуемый алгоритм: {algo_name}
- Производительность: {metrics['requests_per_second']:.2f} RPS
- Среднее время ответа: {metrics['avg_response_time_ms']:.2f} ms
- Максимальное время ответа: {metrics['max_response_time_ms']:.2f} ms
- Процент разрешенных запросов: {metrics['allowed_percentage']:.2f}%
        """
        
        return recommendation.strip()
    
    def reset_all(self):
        """Сбросить все алгоритмы"""
        for algorithm in self.algorithms.values():
            algorithm.reset()
        self.comparison_results.clear()


# Функции для создания типичных конфигураций
def create_sliding_window_config(limit: int, window_seconds: int) -> Dict[str, Any]:
    """Создать конфигурацию sliding window"""
    return {
        "type": "sliding_window",
        "limit": limit,
        "window_seconds": window_seconds
    }


def create_token_bucket_config(capacity: int, refill_rate: float) -> Dict[str, Any]:
    """Создать конфигурацию token bucket"""
    return {
        "type": "token_bucket",
        "capacity": capacity,
        "refill_rate": refill_rate
    }


def create_fixed_window_config(limit: int, window_seconds: int) -> Dict[str, Any]:
    """Создать конфигурацию fixed window"""
    return {
        "type": "fixed_window",
        "limit": limit,
        "window_seconds": window_seconds
    }


def create_leaky_bucket_config(capacity: int, leak_rate: float) -> Dict[str, Any]:
    """Создать конфигурацию leaky bucket"""
    return {
        "type": "leaky_bucket",
        "capacity": capacity,
        "leak_rate": leak_rate
    }


def create_multi_window_config() -> List[Dict[str, Any]]:
    """Создать типичную multi-window конфигурацию"""
    return [
        create_sliding_window_config(100, 60),  # 100 запросов в минуту
        create_token_bucket_config(20, 0.5),    # 20 токенов, восстановление 0.5/сек
        create_fixed_window_config(1000, 3600)  # 1000 запросов в час
    ]


# Декоратор для автоматического rate limiting
def rate_limit(algorithm_name: str, manager: RateLimitManager, key_func=None):
    """
    Декоратор для применения rate limiting к функциям.
    
    Args:
        algorithm_name: Имя алгоритма в менеджере
        manager: Экземпляр RateLimitManager
        key_func: Функция для извлечения ключа (по умолчанию использует имя функции)
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Извлекаем ключ
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                key = f"{func.__name__}"
            
            # Проверяем лимит
            allowed, info = manager.check_rate_limit(algorithm_name, key)
            
            if not allowed:
                raise RateLimitExceeded(f"Превышен лимит запросов: {info}")
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


class RateLimitExceeded(Exception):
    """Исключение при превышении лимита запросов"""


if __name__ == "__main__":
    # Пример использования
    logging.basicConfig(level=logging.INFO)
    
    # Создаем менеджер
    manager = RateLimitManager()
    
    # Добавляем алгоритмы
    manager.add_algorithm("sliding", SlidingWindowAlgorithm(100, 60))
    manager.add_algorithm("token_bucket", TokenBucket(50, 1.0))
    manager.add_algorithm("fixed", FixedWindowCounter(100, 60))
    manager.add_algorithm("leaky", LeakyBucket(10, 0.5))
    
    # Создаем multi-window
    multi_config = create_multi_window_config()
    multi_algo = MultiWindowTracker(multi_config)
    manager.add_algorithm("multi", multi_algo)
    
    # Тестируем алгоритмы
    print("Тестирование алгоритмов rate limiting...")
    
    for name in ["sliding", "token_bucket", "fixed", "leaky", "multi"]:
        print(f"\nТестирование {name}:")
        
        for i in range(5):
            allowed, info = manager.check_rate_limit(name, "user_1")
            print(f"  Запрос {i+1}: {'Разрешен' if allowed else 'Запрещен'} - {info}")
    
    # Сравнительный анализ
    print("\nСравнительный анализ производительности...")
    results = manager.compare_algorithms(test_requests=1000)
    
    for algo_name, metrics in results.items():
        print(f"\n{algo_name}:")
        for key, value in metrics.items():
            print(f"  {key}: {value}")
    
    print(f"\n{manager.get_recommendation()}")