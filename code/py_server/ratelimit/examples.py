
"""
Примеры использования алгоритмов rate limiting.

Демонстрирует различные сценарии применения:
- API лимиты
- Контроль burst трафика
- Многопользовательские системы
- Интеграция с веб-фреймворками
"""

import threading
import time

from sliding_window import (FixedWindowCounter, MultiWindowTracker,
                            RateLimitManager, SlidingWindowAlgorithm,
                            TokenBucket, rate_limit)


def example_api_rate_limiting():
    """
    Пример: Rate limiting для API с различными лимитами для разных клиентов.
    
    Сценарий: API с лимитами 1000 req/min для обычных пользователей,
    100 req/min для анонимных пользователей, 10000 req/min для premium.
    """
    print("Пример 1: Rate limiting для API")
    print("-" * 40)
    
    manager = RateLimitManager()
    
    # Конфигурируем алгоритмы для разных типов пользователей
    manager.add_algorithm("user_standard", SlidingWindowAlgorithm(limit=1000, window_seconds=60))
    manager.add_algorithm("user_anonymous", SlidingWindowAlgorithm(limit=100, window_seconds=60))
    manager.add_algorithm("user_premium", SlidingWindowAlgorithm(limit=10000, window_seconds=60))
    
    # Симуляция запросов от разных пользователей
    test_scenarios = [
        ("standard_user_1", "user_standard"),
        ("anonymous_user_1", "user_anonymous"),
        ("premium_user_1", "user_premium"),
    ]
    
    for user_id, algorithm_name in test_scenarios:
        print(f"\nТестирование пользователя {user_id} (алгоритм: {algorithm_name}):")
        
        for i in range(5):
            allowed, info = manager.check_rate_limit(algorithm_name, user_id)
            status = "✅ Разрешен" if allowed else "❌ Запрещен"
            print(f"  Запрос {i+1}: {status} - Счетчик: {info.get('current_count', 'N/A')}")
            
            # Небольшая задержка для реалистичности
            time.sleep(0.1)
    
    print("\nСравнение производительности алгоритмов:")
    results = manager.compare_algorithms(test_requests=500)
    
    for algo_name, metrics in results.items():
        print(f"  {algo_name}: {metrics['requests_per_second']:.2f} RPS")


def example_burst_traffic_control():
    """
    Пример: Контроль burst трафика с помощью Token Bucket.
    
    Сценарий: API должен поддерживать кратковременные всплески
    до 50 запросов, но ограничивать среднюю скорость до 10 req/s.
    """
    print("\n\nПример 2: Контроль burst трафика")
    print("-" * 40)
    
    # Token Bucket с поддержкой всплесков
    token_bucket = TokenBucket(capacity=50, refill_rate=10.0)  # 50 токенов, восстановление 10/сек
    
    print("Сценарий: Начальная загрузка 50 токенов + восстановление 10/сек")
    print("Тестирование burst трафика:")
    
    # Первая серия запросов - используем burst
    print("\n Burst запросы (первые 50 должны пройти быстро):")
    burst_start = time.time()
    
    for i in range(60):
        allowed, info = token_bucket.check_rate_limit("burst_test")
        if i % 10 == 0:
            tokens = info.get('available_tokens', 0)
            print(f"  Запрос {i+1}: {'✅' if allowed else '❌'} (токены: {tokens:.1f})")
        elif not allowed:
            break
    
    burst_duration = time.time() - burst_start
    print(f"  Burst завершен за {burst_duration:.2f} секунд")
    
    # Ждем восстановления токенов
    print("\nОжидание восстановления токенов...")
    time.sleep(3)  # Ждем 3 секунды (должно восстановиться ~30 токенов)
    
    print("\nЗапросы после восстановления:")
    for i in range(15):
        allowed, info = token_bucket.check_rate_limit("burst_test")
        tokens = info.get('available_tokens', 0)
        status = "✅" if allowed else "❌"
        print(f"  Запрос {i+1}: {status} (токены: {tokens:.1f})")
        time.sleep(0.1)


def example_multi_level_limits():
    """
    Пример: Многоуровневые лимиты с MultiWindowTracker.
    
    Сценарий: API с лимитами по времени (минута, час, день)
    и разными алгоритмами для оптимального контроля.
    """
    print("\n\nПример 3: Многоуровневые лимиты")
    print("-" * 40)
    
    # Конфигурация многоуровневых лимитов
    window_configs = [
        {
            "name": "per_minute",
            "type": "sliding_window",
            "limit": 60,
            "window_seconds": 60
        },
        {
            "name": "per_hour", 
            "type": "fixed_window",
            "limit": 1000,
            "window_seconds": 3600
        },
        {
            "name": "burst_protection",
            "type": "token_bucket",
            "capacity": 10,
            "refill_rate": 2.0
        }
    ]
    
    multi_tracker = MultiWindowTracker(window_configs)
    
    print("Конфигурация лимитов:")
    print("  - 60 запросов в минуту (sliding window)")
    print("  - 1000 запросов в час (fixed window)")
    print("  - Burst protection: 10 токенов, восстановление 2/сек")
    print()
    
    # Тестирование многоуровневых лимитов
    print("Тестирование многоуровневых лимитов:")
    
    for i in range(10):
        allowed, info = multi_tracker.check_rate_limit("api_user")
        overall = "✅ Разрешен" if allowed else "❌ Запрещен"
        
        print(f"  Запрос {i+1}: {overall}")
        
        if not allowed:
            denied_by = info.get('denied_by', 'unknown')
            print(f"    Запрещен алгоритмом: {denied_by}")
        
        # Показываем детали первого запроса
        if i == 0:
            print("    Детали лимитов:")
            for result in info.get('results', []):
                window_name = result['window_name']
                algo_type = result['algorithm_type']
                allowed_win = "✅" if result['allowed'] else "❌"
                print(f"      {window_name} ({algo_type}): {allowed_win}")
        
        time.sleep(0.05)  # Небольшая задержка


def example_concurrent_users():
    """
    Пример: Многопользовательская система с конкурентными запросами.
    
    Сценарий: 10 пользователей одновременно делают запросы,
    каждый со своими лимитами.
    """
    print("\n\nПример 4: Многопользовательская система")
    print("-" * 40)
    
    # Создаем алгоритмы для каждого пользователя
    users = {}
    for i in range(10):
        user_id = f"user_{i+1}"
        # Разные лимиты для разных пользователей
        limit = 10 + (i * 5)  # 10, 15, 20, 25, ... запросов
        users[user_id] = SlidingWindowAlgorithm(limit=limit, window_seconds=60)
    
    print(f"Создано {len(users)} пользователей с разными лимитами")
    
    # Функция для симуляции пользователя
    def simulate_user(user_id: str, algorithm, num_requests: int):
        results = {"user": user_id, "allowed": 0, "denied": 0}
        
        for i in range(num_requests):
            allowed, _ = algorithm.check_rate_limit(user_id)
            if allowed:
                results["allowed"] += 1
            else:
                results["denied"] += 1
            
            time.sleep(0.01)  # 10ms между запросами
        
        return results
    
    # Запуск симуляции в потоках
    threads = []
    start_time = time.time()
    
    print("\nЗапуск симуляции (каждый пользователь делает 20 запросов):")
    
    for user_id, algorithm in users.items():
        thread = threading.Thread(
            target=lambda u=user_id, a=algorithm: simulate_user(u, a, 20)
        )
        threads.append(thread)
        thread.start()
    
    # Ожидание завершения всех потоков
    for thread in threads:
        thread.join()
    
    end_time = time.time()
    total_time = end_time - start_time
    
    print(f"\nСимуляция завершена за {total_time:.2f} секунд")
    print("\nРезультаты по пользователям:")
    
    for user_id, algorithm in users.items():
        metrics = algorithm.get_metrics()
        print(f"  {user_id}: Разрешено {metrics['allowed_requests']}, Запрещено {metrics['denied_requests']}")


def example_web_framework_integration():
    """
    Пример: Интеграция с веб-фреймворком (симуляция Flask/FastAPI).
    
    Демонстрирует использование декоратора @rate_limit
    """
    print("\n\nПример 5: Интеграция с веб-фреймворком")
    print("-" * 40)
    
    # Создаем менеджер
    manager = RateLimitManager()
    manager.add_algorithm("api_default", SlidingWindowAlgorithm(limit=100, window_seconds=60))
    manager.add_algorithm("premium_api", TokenBucket(capacity=200, refill_rate=5.0))
    
    # Симуляция веб-функций с rate limiting
    @rate_limit("api_default", manager)
    def get_user_profile(user_id: str):
        """Получить профиль пользователя (лимит: 100/min)"""
        return {"user_id": user_id, "profile": "данные профиля"}
    
    @rate_limit("premium_api", manager, key_func=lambda user_id, **kwargs: f"premium_{user_id}")
    def get_premium_data(user_id: str):
        """Получить премиум данные (лимит: 200 токенов)"""
        return {"user_id": user_id, "premium_data": "секретная информация"}
    
    # Тестирование функций
    print("Тестирование функций с rate limiting:")
    
    # Обычный API
    print("\nОбычный API (get_user_profile):")
    for i in range(5):
        try:
            result = get_user_profile("user_123")
            print(f"  Запрос {i+1}: ✅ Успех - {result['user_id']}")
        except Exception as e:
            print(f"  Запрос {i+1}: ❌ Ошибка - {e}")
    
    # Премиум API
    print("\nПремиум API (get_premium_data):")
    for i in range(5):
        try:
            result = get_premium_data("premium_user_456")
            print(f"  Запрос {i+1}: ✅ Успех - {result['user_id']}")
        except Exception as e:
            print(f"  Запрос {i+1}: ❌ Ошибка - {e}")


def example_dynamic_limit_adjustment():
    """
    Пример: Динамическое изменение лимитов на основе нагрузки.
    
    Сценарий: Система автоматически корректирует лимиты
    в зависимости от загрузки сервера.
    """
    print("\n\nПример 6: Динамическое изменение лимитов")
    print("-" * 40)
    
    # Базовый алгоритм с возможностью изменения лимитов
    class DynamicSlidingWindow(SlidingWindowAlgorithm):
        def __init__(self, initial_limit: int, window_seconds: int):
            super().__init__(initial_limit, window_seconds)
            self.current_limit = initial_limit
            self.initial_limit = initial_limit
        
        def adjust_limit(self, new_limit: int):
            """Изменить лимит"""
            with self._lock:
                self.current_limit = new_limit
                self.limit = new_limit
                print(f"Лимит изменен с {self.initial_limit} на {new_limit}")
    
    # Создаем динамический алгоритм
    dynamic_algorithm = DynamicSlidingWindow(initial_limit=50, window_seconds=60)
    
    print("Начальный лимит: 50 запросов/минута")
    
    # Тестирование с базовым лимитом
    print("\nТестирование с базовым лимитом:")
    for i in range(10):
        allowed, info = dynamic_algorithm.check_rate_limit("dynamic_test")
        status = "✅" if allowed else "❌"
        current = info.get('current_count', 0)
        limit = info.get('limit', 0)
        print(f"  Запрос {i+1}: {status} ({current}/{limit})")
    
    # Симуляция высокой нагрузки - снижаем лимит
    print("\n⚠️  Обнаружена высокая нагрузка - снижаем лимит до 30")
    dynamic_algorithm.adjust_limit(30)
    
    print("\nТестирование с пониженным лимитом:")
    for i in range(5):
        allowed, info = dynamic_algorithm.check_rate_limit("dynamic_test")
        status = "✅" if allowed else "❌"
        current = info.get('current_count', 0)
        limit = info.get('limit', 0)
        print(f"  Запрос {i+1}: {status} ({current}/{limit})")
    
    # Симуляция нормализации нагрузки - повышаем лимит
    print("\n✅ Нагрузка нормализовалась - повышаем лимит до 70")
    dynamic_algorithm.adjust_limit(70)
    
    print("\nТестирование с повышенным лимитом:")
    for i in range(5):
        allowed, info = dynamic_algorithm.check_rate_limit("dynamic_test")
        status = "✅" if allowed else "❌"
        current = info.get('current_count', 0)
        limit = info.get('limit', 0)
        print(f"  Запрос {i+1}: {status} ({current}/{limit})")


def example_monitoring_and_metrics():
    """
    Пример: Мониторинг и сбор метрик производительности.
    
    Демонстрирует сбор детальной статистики
    и мониторинг производительности в реальном времени.
    """
    print("\n\nПример 7: Мониторинг и метрики")
    print("-" * 40)
    
    # Создаем алгоритмы с мониторингом
    algorithms = {
        'sliding': SlidingWindowAlgorithm(limit=100, window_seconds=60),
        'token_bucket': TokenBucket(capacity=50, refill_rate=2.0),
        'fixed_window': FixedWindowCounter(limit=100, window_seconds=60)
    }
    
    manager = RateLimitManager()
    for name, algo in algorithms.items():
        manager.add_algorithm(name, algo)
    
    # Симуляция нагрузки с мониторингом
    print("Симуляция нагрузки с мониторингом:")
    
    start_time = time.time()
    requests_count = 0
    
    # Запускаем мониторинг в отдельном потоке
    def monitor_progress():
        while time.time() - start_time < 10:  # Мониторинг 10 секунд
            time.sleep(2)  # Каждые 2 секунды
            
            for name, algo in algorithms.items():
                metrics = algo.get_metrics()
                allowed_rate = metrics['allowed_percentage']
                avg_time = metrics['avg_response_time_ms']
                print(f"  [{name}] Разрешено: {allowed_rate:.1f}%, Время ответа: {avg_time:.2f}ms")
    
    monitor_thread = threading.Thread(target=monitor_progress)
    monitor_thread.start()
    
    # Генерируем нагрузку
    for _ in range(200):  # 200 запросов быстро
        for name, algo in algorithms.items():
            try:
                algo.check_rate_limit("monitor_test")
                requests_count += 1
            except Exception:
                pass
    
    monitor_thread.join()
    
    # Финальные метрики
    print("\nФинальные метрики:")
    for name, algo in algorithms.items():
        metrics = algo.get_metrics()
        print(f"\n{name}:")
        for key, value in metrics.items():
            if isinstance(value, float):
                print(f"  {key}: {value:.2f}")
            else:
                print(f"  {key}: {value}")


def run_all_examples():
    """Запуск всех примеров"""
    print("ДЕМОНСТРАЦИЯ АЛГОРИТМОВ RATE LIMITING")
    print("=" * 60)
    
    examples = [
        example_api_rate_limiting,
        example_burst_traffic_control,
        example_multi_level_limits,
        example_concurrent_users,
        example_web_framework_integration,
        example_dynamic_limit_adjustment,
        example_monitoring_and_metrics
    ]
    
    for example_func in examples:
        try:
            example_func()
            time.sleep(1)  # Пауза между примерами
        except KeyboardInterrupt:
            print("\nПрервано пользователем")
            break
        except Exception as e:
            print(f"\nОшибка в примере {example_func.__name__}: {e}")
    
    print("\n" + "=" * 60)
    print("ДЕМОНСТРАЦИЯ ЗАВЕРШЕНА")
    print("=" * 60)


if __name__ == "__main__":
    # Запуск всех примеров
    run_all_examples()
    
    # Дополнительно запускаем быстрый бенчмарк
    print("\n\nБыстрый бенчмарк производительности:")
    print("-" * 40)
    
    manager = RateLimitManager()
    manager.add_algorithm("sliding", SlidingWindowAlgorithm(100, 60))
    manager.add_algorithm("token", TokenBucket(50, 1.0))
    manager.add_algorithm("fixed", FixedWindowCounter(100, 60))
    
    results = manager.compare_algorithms(test_requests=1000)
    
    for name, metrics in results.items():
        print(f"{name:15}: {metrics['requests_per_second']:8.2f} RPS, "
              f"{metrics['avg_response_time_ms']:6.2f}ms среднее время ответа")
    
    print(f"\n{manager.get_recommendation()}")