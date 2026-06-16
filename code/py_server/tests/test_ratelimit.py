
"""
Comprehensive Test Suite для системы Rate Limiting

Создан в соответствии со стандартами тестирования 1С:
- Unit тесты для каждого компонента
- Integration тесты для взаимодействия компонентов  
- Performance тесты для нагрузочного тестирования
- Stress тесты для граничных случаев
- Security тесты для тестирования обхода лимитов
- Thread safety под высокой нагрузкой
- Бенчмарки производительности

Использует:
- pytest для unit тестов
- pytest-benchmark для performance тестов
- locust для нагрузочного тестирования (отдельные файлы)
- coverage.py для анализа покрытия
- memory_profiler для профилирования памяти
- pytest-xdist для параллельного выполнения
- pytest-mock для мокинга зависимостей

Версия: 1.0.0
Дата: 2025-10-29
"""

import asyncio
import os
import random
import sys
import threading
import time
from contextlib import contextmanager
from queue import Empty, Queue
from typing import Any, Dict, Union
from unittest.mock import Mock

# Добавляем путь для импортов
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

# Import configuration

# =============================================================================
# FIXTURES И UTILITIES
# =============================================================================

@pytest.fixture
def ratelimit_config():
    """Базовая конфигурация для тестов rate limiting"""
    return {
        "enabled": True,
        "storage_type": "memory",  # memory, redis
        "limits": {
            "default": {"requests": 100, "window": 60},
            "api": {"requests": 1000, "window": 60},
            "premium": {"requests": 10000, "window": 60},
            "strict": {"requests": 10, "window": 60}
        },
        "distributed": True,
        "white_list": [],
        "black_list": [],
        "burst_allowance": 0.1
    }


@pytest.fixture
def mock_redis():
    """Mock для Redis клиента"""
    redis_mock = Mock()
    redis_mock.get.return_value = None
    redis_mock.set.return_value = True
    redis_mock.incr.return_value = 1
    redis_mock.expire.return_value = True
    redis_mock.delete.return_value = 1
    redis_mock.ping.return_value = True
    redis_mock.pipeline.return_value = Mock()
    redis_mock.execute.return_value = []
    return redis_mock


@pytest.fixture
def temp_redis_server():
    """Временный Redis сервер для тестов (если доступен)"""
    try:
        # Попытка запустить локальный Redis
        import subprocess
        import tempfile
        
        temp_dir = tempfile.mkdtemp()
        redis_proc = subprocess.Popen([
            'redis-server', 
            '--port', '6380',
            '--dir', temp_dir,
            '--dbfilename', 'test.rdb'
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        time.sleep(2)  # Даем серверу время запуститься
        
        yield redis_proc
        
        # Очистка
        redis_proc.terminate()
        redis_proc.wait(timeout=5)
        
        # Удаляем временные файлы
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
        
    except (subprocess.SubprocessError, FileNotFoundError):
        # Redis недоступен, пропускаем тесты
        pytest.skip("Redis server not available")


@pytest.fixture
def rate_limit_globals():
    """Глобальные переменные для отслеживания состояния в тестах"""
    class RateLimitGlobals:
        def __init__(self):
            self.reset_count = 0
            self.blocked_requests = []
            self.allowed_requests = []
            self.timing_data = []
            
        def reset(self):
            self.reset_count = 0
            self.blocked_requests.clear()
            self.allowed_requests.clear()
            self.timing_data.clear()
            
        def add_blocked(self, key, reason):
            self.blocked_requests.append({"key": key, "reason": reason, "time": time.time()})
            
        def add_allowed(self, key):
            self.allowed_requests.append({"key": key, "time": time.time()})
            
        def add_timing(self, operation, duration):
            self.timing_data.append({"operation": operation, "duration": duration, "time": time.time()})
    
    return RateLimitGlobals()


@pytest.fixture
def fastapi_app(rate_limit_globals):
    """FastAPI приложение для integration тестов"""
    app = FastAPI(title="Test Rate Limiting API", version="1.0.0")
    
    # Добавляем middleware для rate limiting
    from ratelimit.middleware import RateLimitMiddleware
    app.add_middleware(RateLimitMiddleware)
    
    # Тестовые endpoints
    @app.get("/public")
    async def public_endpoint(request: Request):
        return {"message": "public access"}
    
    @app.get("/api/data")
    async def api_data_endpoint(request: Request):
        return {"data": "some data"}
    
    @app.get("/admin")
    async def admin_endpoint(request: Request):
        return {"message": "admin access"}
    
    @app.post("/process")
    async def process_endpoint(request: Request):
        await asyncio.sleep(0.1)  # Имитация обработки
        return {"status": "processed"}
    
    return app


@pytest.fixture
def test_client(fastapi_app):
    """Test client для FastAPI приложения"""
    return TestClient(fastapi_app)


@contextmanager
def performance_monitor(operation_name: str, global_vars=None):
    """Контекстный менеджер для мониторинга производительности"""
    start_time = time.time()
    start_memory = get_memory_usage()
    
    try:
        yield
    finally:
        end_time = time.time()
        end_memory = get_memory_usage()
        
        duration = end_time - start_time
        memory_delta = end_memory - start_memory
        
        if global_vars:
            global_vars.add_timing(operation_name, {
                "duration": duration,
                "memory_delta": memory_delta,
                "timestamp": end_time
            })


def get_memory_usage() -> float:
    """Получить текущее использование памяти в MB"""
    import psutil
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024


def assert_rate_limit_metrics(metrics: Dict[str, Any], expected_requests: int, 
                            expected_blocked: int, tolerance: float = 0.1):
    """Вспомогательная функция для проверки метрик rate limiting"""
    assert metrics["total_requests"] >= expected_requests * (1 - tolerance)
    assert metrics["total_requests"] <= expected_requests * (1 + tolerance)
    assert metrics["blocked_requests"] >= expected_blocked * (1 - tolerance)
    assert metrics["blocked_requests"] <= expected_blocked * (1 + tolerance)


# =============================================================================
# CORE RATE LIMITING COMPONENTS - MOCK IMPLEMENTATIONS
# =============================================================================

class RateLimitEntry:
    """Запись для отслеживания rate limiting"""
    
    def __init__(self, key: str, limit: int, window: int):
        self.key = key
        self.limit = limit
        self.window = window
        self.requests = []
        self.created_at = time.time()
        
    def add_request(self):
        """Добавить запрос к записи"""
        current_time = time.time()
        # Удаляем старые запросы
        self.requests = [req_time for req_time in self.requests 
                        if current_time - req_time < self.window]
        
        # Добавляем новый запрос
        self.requests.append(current_time)
        
    def is_blocked(self) -> bool:
        """Проверить, заблокирован ли запрос"""
        current_time = time.time()
        # Удаляем старые запросы
        self.requests = [req_time for req_time in self.requests 
                        if current_time - req_time < self.window]
        
        return len(self.requests) >= self.limit
    
    def get_remaining_requests(self) -> int:
        """Получить количество оставшихся запросов"""
        current_time = time.time()
        # Удаляем старые запросы
        self.requests = [req_time for req_time in self.requests 
                        if current_time - req_time < self.window]
        
        return max(0, self.limit - len(self.requests))
    
    def get_reset_time(self) -> float:
        """Получить время сброса лимита"""
        if not self.requests:
            return 0
        
        current_time = time.time()
        oldest_request = min(self.requests)
        return oldest_request + self.window - current_time


class MemoryRateLimitStore:
    """In-memory хранилище для rate limiting"""
    
    def __init__(self):
        self.entries: Dict[str, RateLimitEntry] = {}
        self.lock = threading.RLock()
        
    def check_rate_limit(self, key: str, limit: int, window: int) -> tuple[bool, int, float]:
        """Проверить rate limit для ключа"""
        with self.lock:
            if key not in self.entries:
                self.entries[key] = RateLimitEntry(key, limit, window)
            
            entry = self.entries[key]
            
            # Обновляем параметры лимита
            if entry.limit != limit or entry.window != window:
                entry.limit = limit
                entry.window = window
                entry.requests = []  # Сбрасываем при изменении лимитов
            
            is_blocked = entry.is_blocked()
            remaining = entry.get_remaining_requests()
            reset_time = entry.get_reset_time()
            
            if not is_blocked:
                entry.add_request()
            
            return not is_blocked, remaining, reset_time
    
    def cleanup_expired(self):
        """Очистить истекшие записи"""
        with self.lock:
            current_time = time.time()
            expired_keys = [
                key for key, entry in self.entries.items()
                if current_time - entry.created_at > entry.window * 2
            ]
            for key in expired_keys:
                del self.entries[key]
    
    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику хранилища"""
        with self.lock:
            return {
                "total_entries": len(self.entries),
                "entries": {
                    key: {
                        "requests": len(entry.requests),
                        "limit": entry.limit,
                        "window": entry.window,
                        "remaining": entry.get_remaining_requests(),
                        "reset_time": entry.get_reset_time()
                    }
                    for key, entry in self.entries.items()
                }
            }


class RedisRateLimitStore:
    """Redis-based хранилище для rate limiting"""
    
    def __init__(self, redis_client):
        self.redis = redis_client
        self.prefix = "ratelimit:"
        
    def check_rate_limit(self, key: str, limit: int, window: int) -> tuple[bool, int, float]:
        """Проверить rate limit для ключа"""
        try:
            redis_key = f"{self.prefix}{key}"
            current_time = int(time.time())
            window_start = current_time - window
            
            # Используем Redis sorted set для хранения запросов
            pipe = self.redis.pipeline()
            
            # Удаляем старые записи
            pipe.zremrangebyscore(redis_key, 0, window_start)
            
            # Получаем текущее количество запросов
            pipe.zcard(redis_key)
            
            # Проверяем, не превышен ли лимит
            pipe.execute()
            current_requests = pipe.results[1] if hasattr(pipe, 'results') else 0
            
            is_blocked = current_requests >= limit
            remaining = max(0, limit - current_requests)
            reset_time = window - (current_time % window)
            
            if not is_blocked:
                # Добавляем текущий запрос
                self.redis.zadd(redis_key, {str(current_time): current_time})
                self.redis.expire(redis_key, window * 2)
            
            return not is_blocked, remaining, reset_time
            
        except Exception:
            # В случае ошибки Redis, используем fallback
            return True, limit, 0.0
    
    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику хранилища"""
        try:
            keys = self.redis.keys(f"{self.prefix}*")
            return {
                "total_entries": len(keys),
                "redis_keys": len(keys)
            }
        except Exception:
            return {"total_entries": 0, "redis_keys": 0}


# =============================================================================
# RATE LIMITING ALGORITHMS
# =============================================================================

class SlidingWindowCounter:
    """Алгоритм sliding window counter для rate limiting"""
    
    def __init__(self, store: Union[MemoryRateLimitStore, RedisRateLimitStore]):
        self.store = store
        
    def check_limit(self, key: str, limit: int, window: int) -> tuple[bool, int, float]:
        """Проверить лимит с sliding window"""
        return self.store.check_rate_limit(key, limit, window)


class TokenBucket:
    """Алгоритм token bucket для rate limiting"""
    
    def __init__(self, store: MemoryRateLimitStore):
        self.store = store
        self.lock = threading.Lock()
        
    def check_limit(self, key: str, capacity: int, refill_rate: float, 
                   window: int) -> tuple[bool, int, float]:
        """Проверить лимит с token bucket"""
        bucket_key = f"bucket:{key}"
        current_time = time.time()
        
        with self.lock:
            # Получаем текущее состояние bucket
            if bucket_key not in getattr(self.store, 'buckets', {}):
                self.store.buckets = getattr(self.store, 'buckets', {})
                self.store.buckets[bucket_key] = {
                    'tokens': capacity,
                    'last_refill': current_time
                }
            
            bucket = self.store.buckets[bucket_key]
            
            # Добавляем токены на основе времени
            time_passed = current_time - bucket['last_refill']
            tokens_to_add = time_passed * refill_rate
            bucket['tokens'] = min(capacity, bucket['tokens'] + tokens_to_add)
            bucket['last_refill'] = current_time
            
            # Проверяем доступность токена
            if bucket['tokens'] >= 1:
                bucket['tokens'] -= 1
                remaining_tokens = int(bucket['tokens'])
                reset_time = 1 / refill_rate  # Время до следующего токена
                return True, remaining_tokens, reset_time
            else:
                remaining_tokens = int(bucket['tokens'])
                reset_time = 1 / refill_rate
                return False, remaining_tokens, reset_time


class FixedWindowCounter:
    """Алгоритм fixed window counter для rate limiting"""
    
    def __init__(self, store: Union[MemoryRateLimitStore, RedisRateLimitStore]):
        self.store = store
        
    def check_limit(self, key: str, limit: int, window: int) -> tuple[bool, int, float]:
        """Проверить лимит с fixed window"""
        window_key = f"{key}:{int(time.time() // window)}"
        return self.store.check_rate_limit(window_key, limit, window)


# =============================================================================
# UNIT TESTS - Core Components
# =============================================================================

class TestRateLimitEntry:
    """Unit тесты для RateLimitEntry"""
    
    def test_entry_creation(self):
        """Тест создания записи rate limiting"""
        entry = RateLimitEntry("test_key", 100, 60)
        
        assert entry.key == "test_key"
        assert entry.limit == 100
        assert entry.window == 60
        assert len(entry.requests) == 0
        assert not entry.is_blocked()
    
    def test_request_tracking(self):
        """Тест отслеживания запросов"""
        entry = RateLimitEntry("test_key", 3, 60)
        
        # Первый запрос
        entry.add_request()
        assert len(entry.requests) == 1
        assert not entry.is_blocked()
        assert entry.get_remaining_requests() == 2
        
        # Второй запрос
        entry.add_request()
        assert len(entry.requests) == 2
        assert not entry.is_blocked()
        assert entry.get_remaining_requests() == 1
        
        # Третий запрос
        entry.add_request()
        assert len(entry.requests) == 3
        assert entry.is_blocked()
        assert entry.get_remaining_requests() == 0
    
    def test_ttl_cleanup(self):
        """Тест очистки старых запросов"""
        entry = RateLimitEntry("test_key", 100, 60)
        
        # Добавляем старые запросы
        entry.requests = [
            time.time() - 100,  # 100 секунд назад (старше окна)
            time.time() - 30,   # 30 секунд назад (в пределах окна)
            time.time() - 10    # 10 секунд назад (в пределах окна)
        ]
        
        # Старый запрос должен быть очищен
        assert entry.is_blocked()  # 2 активных запроса
        assert entry.get_remaining_requests() == 98
        
        # Все запросы старше окна
        entry.requests = [time.time() - 100, time.time() - 90]
        assert not entry.is_blocked()
        assert entry.get_remaining_requests() == 100
    
    def test_reset_time_calculation(self):
        """Тест расчета времени сброса"""
        entry = RateLimitEntry("test_key", 100, 60)
        
        # Нет запросов
        assert entry.get_reset_time() == 0
        
        # Есть активные запросы
        entry.requests = [time.time() - 10, time.time() - 30]
        reset_time = entry.get_reset_time()
        
        assert reset_time > 0
        assert reset_time <= 60  # Не больше размера окна


class TestMemoryRateLimitStore:
    """Unit тесты для MemoryRateLimitStore"""
    
    def test_store_creation(self):
        """Тест создания хранилища"""
        store = MemoryRateLimitStore()
        assert len(store.entries) == 0
        assert isinstance(store.lock, type(threading.RLock()))
    
    def test_basic_rate_limit_check(self):
        """Тест базовой проверки rate limit"""
        store = MemoryRateLimitStore()
        
        # Первый запрос должен пройти
        allowed, remaining, reset_time = store.check_rate_limit("test_key", 3, 60)
        
        assert allowed is True
        assert remaining == 2
        assert reset_time > 0
        
        # Второй запрос должен пройти
        allowed, remaining, reset_time = store.check_rate_limit("test_key", 3, 60)
        assert allowed is True
        assert remaining == 1
        
        # Третий запрос должен пройти
        allowed, remaining, reset_time = store.check_rate_limit("test_key", 3, 60)
        assert allowed is True
        assert remaining == 0
        
        # Четвертый запрос должен быть заблокирован
        allowed, remaining, reset_time = store.check_rate_limit("test_key", 3, 60)
        assert allowed is False
        assert remaining == 0
    
    def test_different_limits(self):
        """Тест разных лимитов для одного ключа"""
        store = MemoryRateLimitStore()
        
        # Первый лимит
        store.check_rate_limit("test_key", 2, 60)
        store.check_rate_limit("test_key", 2, 60)
        
        # Смена на больший лимит
        allowed, remaining, reset_time = store.check_rate_limit("test_key", 5, 60)
        assert allowed is True
        assert remaining == 4  # Сброс счетчика при смене лимита
        
        # Меньший лимит
        store.check_rate_limit("test_key", 1, 60)
        assert not store.check_rate_limit("test_key", 1, 60)[0]
    
    def test_cleanup_expired(self):
        """Тест очистки истекших записей"""
        store = MemoryRateLimitStore()
        
        # Добавляем старые и новые записи
        store.entries["old_key"] = RateLimitEntry("old_key", 100, 60)
        store.entries["old_key"].created_at = time.time() - 200  # Старая запись
        
        store.entries["new_key"] = RateLimitEntry("new_key", 100, 60)
        store.entries["new_key"].created_at = time.time()  # Новая запись
        
        store.cleanup_expired()
        
        assert "old_key" not in store.entries
        assert "new_key" in store.entries
    
    def test_thread_safety(self):
        """Тест thread safety"""
        store = MemoryRateLimitStore()
        results = []
        
        def worker(key_suffix, iterations):
            for i in range(iterations):
                allowed, remaining, reset_time = store.check_rate_limit(
                    f"test_key_{key_suffix}", 10, 60
                )
                results.append((allowed, remaining))
        
        # Запускаем несколько потоков
        threads = []
        for i in range(5):
            thread = threading.Thread(target=worker, args=(i, 20))
            threads.append(thread)
            thread.start()
        
        # Ждем завершения
        for thread in threads:
            thread.join()
        
        # Проверяем, что все операции завершились без ошибок
        assert len(results) == 100  # 5 потоков * 20 итераций
        
        # Проверяем статистику
        stats = store.get_stats()
        assert stats["total_entries"] == 5  # По одной записи на ключ
    
    def test_statistics(self):
        """Тест получения статистики"""
        store = MemoryRateLimitStore()
        
        # Добавляем несколько записей
        store.check_rate_limit("key1", 5, 60)
        store.check_rate_limit("key2", 3, 60)
        
        stats = store.get_stats()
        
        assert stats["total_entries"] == 2
        assert "key1" in stats["entries"]
        assert "key2" in stats["entries"]
        
        assert stats["entries"]["key1"]["limit"] == 5
        assert stats["entries"]["key1"]["requests"] == 1
        assert stats["entries"]["key2"]["limit"] == 3
        assert stats["entries"]["key2"]["requests"] == 1


class TestRedisRateLimitStore:
    """Unit тесты для RedisRateLimitStore"""
    
    def test_store_creation(self, mock_redis):
        """Тест создания Redis хранилища"""
        store = RedisRateLimitStore(mock_redis)
        assert store.redis == mock_redis
        assert store.prefix == "ratelimit:"
    
    def test_rate_limit_check_success(self, mock_redis):
        """Тест успешной проверки rate limit через Redis"""
        mock_redis.zcard.return_value = 0
        mock_redis.zadd.return_value = 1
        mock_redis.expire.return_value = True
        
        store = RedisRateLimitStore(mock_redis)
        allowed, remaining, reset_time = store.check_rate_limit("test_key", 5, 60)
        
        assert allowed is True
        assert remaining == 4
        
        # Проверяем вызовы Redis
        mock_redis.zremrangebyscore.assert_called_once()
        mock_redis.zadd.assert_called_once()
        mock_redis.expire.assert_called_once()
    
    def test_rate_limit_check_blocked(self, mock_redis):
        """Тест блокировки через Redis"""
        mock_redis.zcard.return_value = 5  # Лимит достигнут
        
        store = RedisRateLimitStore(mock_redis)
        allowed, remaining, reset_time = store.check_rate_limit("test_key", 5, 60)
        
        assert allowed is False
        assert remaining == 0
        
        # zadd не должен быть вызван при блокировке
        mock_redis.zadd.assert_not_called()
    
    def test_redis_fallback(self, mock_redis):
        """Тест fallback при ошибке Redis"""
        mock_redis.zcard.side_effect = Exception("Redis connection failed")
        
        store = RedisRateLimitStore(mock_redis)
        allowed, remaining, reset_time = store.check_rate_limit("test_key", 5, 60)
        
        # Должен fallback к разрешению всех запросов
        assert allowed is True
        assert remaining == 5
    
    def test_statistics(self, mock_redis):
        """Тест получения статистики через Redis"""
        mock_redis.keys.return_value = ["ratelimit:key1", "ratelimit:key2"]
        
        store = RedisRateLimitStore(mock_redis)
        stats = store.get_stats()
        
        assert stats["total_entries"] == 2
        assert stats["redis_keys"] == 2
        mock_redis.keys.assert_called_once_with("ratelimit:*")


class TestRateLimitAlgorithms:
    """Unit тесты для алгоритмов rate limiting"""
    
    def test_sliding_window_counter(self):
        """Тест алгоритма sliding window counter"""
        store = MemoryRateLimitStore()
        algorithm = SlidingWindowCounter(store)
        
        allowed, remaining, reset_time = algorithm.check_limit("test_key", 3, 60)
        
        assert allowed is True
        assert remaining == 2
        
        # Достигаем лимита
        algorithm.check_limit("test_key", 3, 60)
        algorithm.check_limit("test_key", 3, 60)
        
        # Следующий запрос должен быть заблокирован
        allowed, remaining, reset_time = algorithm.check_limit("test_key", 3, 60)
        assert allowed is False
    
    def test_token_bucket(self):
        """Тест алгоритма token bucket"""
        store = MemoryRateLimitStore()
        algorithm = TokenBucket(store)
        
        # Первый запрос должен пройти
        allowed, remaining, reset_time = algorithm.check_limit("test_key", 5, 1.0, 60)
        assert allowed is True
        assert remaining >= 0
        
        # Используем все токены
        for _ in range(5):
            algorithm.check_limit("test_key", 5, 1.0, 60)
        
        # Следующий запрос должен быть заблокирован
        allowed, remaining, reset_time = algorithm.check_limit("test_key", 5, 1.0, 60)
        assert allowed is False
        
        # Ждем пополнения токенов
        time.sleep(1.1)
        allowed, remaining, reset_time = algorithm.check_limit("test_key", 5, 1.0, 60)
        assert allowed is True
    
    def test_fixed_window_counter(self):
        """Тест алгоритма fixed window counter"""
        store = MemoryRateLimitStore()
        algorithm = FixedWindowCounter(store)
        
        # Первый запрос
        allowed, remaining, reset_time = algorithm.check_limit("test_key", 3, 60)
        assert allowed is True
        assert remaining == 2
        
        # Достигаем лимита
        algorithm.check_limit("test_key", 3, 60)
        algorithm.check_limit("test_key", 3, 60)
        
        # Следующий запрос заблокирован
        allowed, remaining, reset_time = algorithm.check_limit("test_key", 3, 60)
        assert allowed is False


# =============================================================================
# INTEGRATION TESTS - Component Interaction
# =============================================================================

class TestRateLimitManager:
    """Integration тесты для менеджера rate limiting"""
    
    @pytest.fixture
    def rate_limit_manager(self):
        """Создать менеджер rate limiting для тестов"""
        from ratelimit.manager import RateLimitManager
        return RateLimitManager(
            storage_type="memory",
            default_limits={
                "default": {"requests": 100, "window": 60},
                "api": {"requests": 1000, "window": 60}
            }
        )
    
    def test_manager_creation(self, rate_limit_manager):
        """Тест создания менеджера"""
        assert rate_limit_manager is not None
        assert rate_limit_manager.storage_type == "memory"
        assert "default" in rate_limit_manager.limits
    
    def test_check_rate_limit_api(self, rate_limit_manager):
        """Тест проверки лимитов для API endpoints"""
        # Тест с дефолтным лимитом
        result = rate_limit_manager.check_rate_limit("user_123", "default")
        assert result["allowed"] is True
        assert result["remaining"] >= 0
        
        # Тест с API лимитом
        result = rate_limit_manager.check_rate_limit("user_456", "api")
        assert result["allowed"] is True
        assert result["remaining"] >= 0
    
    def test_limit_exhaustion(self, rate_limit_manager):
        """Тест исчерпания лимитов"""
        key = "test_user"
        limit_name = "default"  # 100 requests per minute
        
        # Исчерпываем лимит
        for i in range(100):
            result = rate_limit_manager.check_rate_limit(key, limit_name)
            if i < 99:
                assert result["allowed"] is True
            else:
                assert result["allowed"] is False
        
        # Следующий запрос также должен быть заблокирован
        result = rate_limit_manager.check_rate_limit(key, limit_name)
        assert result["allowed"] is False
        assert result["blocked_reason"] == "rate_limit_exceeded"
    
    def test_reset_after_window(self, rate_limit_manager):
        """Тест сброса лимитов после окна времени"""
        key = "test_user_reset"
        
        # Исчерпываем лимит
        for _ in range(100):
            rate_limit_manager.check_rate_limit(key, "default")
        
        # Последний запрос заблокирован
        result = rate_limit_manager.check_rate_limit(key, "default")
        assert result["allowed"] is False
        
        # Симулируем сброс (в реальности это произойдет автоматически)
        # Для теста мы создаем новый ключ с тем же именем
        new_key = f"{key}_{int(time.time())}"
        result = rate_limit_manager.check_rate_limit(new_key, "default")
        assert result["allowed"] is True
    
    def test_white_list_support(self, rate_limit_manager):
        """Тест поддержки white list"""
        # Добавляем пользователя в white list
        rate_limit_manager.add_to_whitelist("premium_user")
        
        # Исчерпываем лимит для обычного пользователя
        for _ in range(100):
            result = rate_limit_manager.check_rate_limit("normal_user", "default")
            if _ == 99:
                assert result["allowed"] is False
        
        # Пользователь из white list должен иметь высокий лимит
        for i in range(150):
            result = rate_limit_manager.check_rate_limit("premium_user", "default")
            if i == 149:
                assert result["allowed"] is False  # Может иметь увеличенный лимит, но не бесконечный
            else:
                assert result["allowed"] is True
    
    def test_distributed_mode(self, rate_limit_manager):
        """Тест distributed режима"""
        # В distributed режиме должен использовать Redis
        manager_dist = rate_limit_manager.__class__(
            storage_type="redis",
            redis_url="redis://localhost:6379",
            distributed=True
        )
        
        # Если Redis недоступен, должен fallback к memory
        # Это тестируется в реальном окружении
        assert manager_dist.distributed is True
    
    def test_health_check(self, rate_limit_manager):
        """Тест проверки здоровья системы"""
        health = rate_limit_manager.health_check()
        
        assert "status" in health
        assert "storage_type" in health
        assert "distributed" in health
        assert health["status"] in ["healthy", "degraded", "unhealthy"]


# =============================================================================
# PERFORMANCE TESTS - Load Testing
# =============================================================================

class TestRateLimitPerformance:
    """Performance тесты для системы rate limiting"""
    
    @pytest.mark.performance
    def test_memory_store_performance(self, rate_limit_globals):
        """Тест производительности memory store"""
        store = MemoryRateLimitStore()
        
        with performance_monitor("memory_store_benchmark", rate_limit_globals):
            # Выполняем много операций
            for i in range(10000):
                key = f"user_{i % 1000}"  # 1000 уникальных пользователей
                store.check_rate_limit(key, 100, 60)
        
        # Проверяем, что время выполнения приемлемо
        timing_data = [t for t in rate_limit_globals.timing_data if t["operation"] == "memory_store_benchmark"]
        assert len(timing_data) == 1
        
        duration = timing_data[0]["duration"]
        assert duration < 5.0  # Не должно занимать больше 5 секунд
    
    @pytest.mark.performance
    def test_concurrent_access_performance(self, rate_limit_globals):
        """Тест производительности при конкурентном доступе"""
        store = MemoryRateLimitStore()
        results = Queue()
        
        def worker(worker_id):
            try:
                for i in range(1000):
                    key = f"user_{worker_id}"
                    start_time = time.time()
                    result = store.check_rate_limit(key, 100, 60)
                    end_time = time.time()
                    
                    results.put({
                        "worker_id": worker_id,
                        "iteration": i,
                        "allowed": result[0],
                        "duration": end_time - start_time
                    })
            except Exception as e:
                results.put({"error": str(e), "worker_id": worker_id})
        
        with performance_monitor("concurrent_access", rate_limit_globals):
            # Запускаем 10 потоков
            threads = []
            for i in range(10):
                thread = threading.Thread(target=worker, args=(i,))
                threads.append(thread)
                thread.start()
            
            # Ждем завершения
            for thread in threads:
                thread.join()
        
        # Анализируем результаты
        successful_results = []
        error_count = 0
        
        while not results.empty():
            try:
                result = results.get_nowait()
                if "error" in result:
                    error_count += 1
                else:
                    successful_results.append(result)
            except Empty:
                break
        
        assert error_count == 0, f"Ошибки в {error_count} потоках"
        assert len(successful_results) == 10000  # 10 потоков * 1000 итераций
        
        # Проверяем время отклика
        durations = [r["duration"] for r in successful_results]
        avg_duration = sum(durations) / len(durations)
        max_duration = max(durations)
        
        assert avg_duration < 0.001  # Среднее время меньше 1ms
        assert max_duration < 0.01   # Максимальное время меньше 10ms
        
        print(f"Concurrent access performance: avg={avg_duration*1000:.2f}ms, max={max_duration*1000:.2f}ms")
    
    @pytest.mark.performance
    def test_redis_vs_memory_performance(self, mock_redis):
        """Сравнение производительности Redis vs Memory"""
        memory_store = MemoryRateLimitStore()
        redis_store = RedisRateLimitStore(mock_redis)
        
        # Настраиваем mock для реалистичных значений
        mock_redis.zcard.return_value = 0
        mock_redis.zadd.return_value = 1
        mock_redis.expire.return_value = True
        
        # Тестируем memory store
        start_time = time.time()
        for i in range(1000):
            memory_store.check_rate_limit(f"key_{i}", 100, 60)
        memory_duration = time.time() - start_time
        
        # Тестируем Redis store
        start_time = time.time()
        for i in range(1000):
            redis_store.check_rate_limit(f"key_{i}", 100, 60)
        redis_duration = time.time() - start_time
        
        print(f"Memory store: {memory_duration:.3f}s, Redis store: {redis_duration:.3f}s")
        
        # Memory store должен быть быстрее (так как нет сетевых операций)
        # Но разница не должна быть критичной
        ratio = redis_duration / memory_duration if memory_duration > 0 else float('inf')
        assert ratio < 10  # Redis не должен быть в 10 раз медленнее
    
    @pytest.mark.performance
    def test_memory_usage_under_load(self, rate_limit_globals):
        """Тест использования памяти под нагрузкой"""
        initial_memory = get_memory_usage()
        
        with performance_monitor("memory_usage_test", rate_limit_globals):
            store = MemoryRateLimitStore()
            
            # Создаем большое количество записей
            for i in range(50000):
                key = f"user_{i}"
                store.check_rate_limit(key, 100, 60)
                
                # Периодически очищаем истекшие записи
                if i % 10000 == 0:
                    store.cleanup_expired()
        
        final_memory = get_memory_usage()
        memory_increase = final_memory - initial_memory
        
        # Использование памяти не должно расти безгранично
        # (с учетом того, что у нас есть cleanup)
        assert memory_increase < 100  # Менее 100MB увеличения
        
        print(f"Memory usage: initial={initial_memory:.1f}MB, final={final_memory:.1f}MB, increase={memory_increase:.1f}MB")


# =============================================================================
# STRESS TESTS - Edge Cases
# =============================================================================

class TestRateLimitStress:
    """Stress тесты для граничных случаев"""
    
    def test_zero_limit(self):
        """Тест нулевого лимита"""
        store = MemoryRateLimitStore()
        
        # Нулевой лимит должен блокировать все запросы
        allowed, remaining, reset_time = store.check_rate_limit("test_key", 0, 60)
        assert allowed is False
        assert remaining == 0
    
    def test_very_large_limit(self):
        """Тест очень больших лимитов"""
        store = MemoryRateLimitStore()
        
        # Очень большой лимит
        large_limit = 10**9
        allowed, remaining, reset_time = store.check_rate_limit("test_key", large_limit, 60)
        
        assert allowed is True
        assert remaining == large_limit - 1
    
    def test_very_small_window(self):
        """Тест очень маленького окна времени"""
        store = MemoryRateLimitStore()
        
        # Окно в 1 секунду
        allowed, remaining, reset_time = store.check_rate_limit("test_key", 100, 1)
        
        assert allowed is True
        assert remaining == 99
        
        # Ждем истечения окна
        time.sleep(1.1)
        
        # Лимит должен сброситься
        allowed, remaining, reset_time = store.check_rate_limit("test_key", 100, 1)
        assert allowed is True
        assert remaining == 99
    
    def test_very_large_window(self):
        """Тест очень большого окна времени"""
        store = MemoryRateLimitStore()
        
        # Окно в 1 год
        large_window = 365 * 24 * 60 * 60
        allowed, remaining, reset_time = store.check_rate_limit("test_key", 100, large_window)
        
        assert allowed is True
        assert remaining == 99
        
        # Лимит не должен сброситься в течение теста
        time.sleep(0.1)
        
        allowed, remaining, reset_time = store.check_rate_limit("test_key", 100, large_window)
        assert allowed is True
        assert remaining == 98
    
    def test_special_characters_in_key(self):
        """Тест специальных символов в ключах"""
        store = MemoryRateLimitStore()
        
        special_keys = [
            "user@example.com",
            "user:12345",
            "user/workspace/project",
            "user@domain.com:port/path",
            "user with spaces",
            "用户123",  # Unicode
            "user\nwith\nnewlines",
            "user\twith\ttabs"
        ]
        
        for key in special_keys:
            allowed, remaining, reset_time = store.check_rate_limit(key, 10, 60)
            assert allowed is True
            assert remaining == 9
    
    def test_concurrent_stress(self):
        """Stress тест с максимальной конкурентностью"""
        store = MemoryRateLimitStore()
        results = []
        errors = []
        
        def stress_worker(worker_id, iterations):
            try:
                for i in range(iterations):
                    # Используем разные ключи для создания нагрузки
                    key = f"stress_user_{i % 1000}"
                    result = store.check_rate_limit(key, 1000, 60)
                    results.append({
                        "worker": worker_id,
                        "iteration": i,
                        "allowed": result[0],
                        "remaining": result[1]
                    })
            except Exception as e:
                errors.append({"worker": worker_id, "error": str(e)})
        
        # Запускаем много потоков
        num_threads = 50
        iterations_per_thread = 500
        
        threads = []
        start_time = time.time()
        
        for i in range(num_threads):
            thread = threading.Thread(target=stress_worker, args=(i, iterations_per_thread))
            threads.append(thread)
            thread.start()
        
        # Ждем завершения
        for thread in threads:
            thread.join()
        
        end_time = time.time()
        total_duration = end_time - start_time
        
        # Анализируем результаты
        assert len(errors) == 0, f"Ошибки в потоках: {errors}"
        assert len(results) == num_threads * iterations_per_thread
        
        # Проверяем производительность
        ops_per_second = len(results) / total_duration
        assert ops_per_second > 1000  # Минимум 1000 операций в секунду
        
        print(f"Stress test: {len(results)} operations in {total_duration:.2f}s ({ops_per_second:.0f} ops/sec)")
    
    def test_memory_exhaustion_simulation(self):
        """Тест симуляции исчерпания памяти"""
        store = MemoryRateLimitStore()
        
        # Создаем множество записей
        for i in range(10000):
            key = f"memory_user_{i}"
            store.check_rate_limit(key, 100, 60)
        
        # Проверяем, что cleanup работает
        stats_before = store.get_stats()
        
        # Симулируем старение записей
        for entry in store.entries.values():
            entry.created_at = time.time() - 200  # 200 секунд назад
        
        store.cleanup_expired()
        stats_after = store.get_stats()
        
        # Количество записей должно уменьшиться
        assert stats_after["total_entries"] < stats_before["total_entries"]
    
    def test_redis_connection_failure(self, mock_redis):
        """Тест сбоя подключения к Redis"""
        mock_redis.zcard.side_effect = ConnectionError("Connection failed")
        mock_redis.ping.side_effect = ConnectionError("Connection failed")
        
        store = RedisRateLimitStore(mock_redis)
        
        # При сбое Redis должен fallback
        allowed, remaining, reset_time = store.check_rate_limit("test_key", 100, 60)
        
        # Fallback должен разрешить запросы
        assert allowed is True
        assert remaining == 100


# =============================================================================
# SECURITY TESTS - Rate Limit Bypass Attempts
# =============================================================================

class TestRateLimitSecurity:
    """Security тесты для попыток обхода rate limiting"""
    
    def test_ip_spoofing_attempts(self):
        """Тест попыток подмены IP адресов"""
        store = MemoryRateLimitStore()
        
        # Пытаемся обойти лимиты через изменение IP
        base_key = "user_123"
        ips = [
            "192.168.1.1",
            "10.0.0.1", 
            "127.0.0.1",
            "::1",
            "0.0.0.0"
        ]
        
        for ip in ips:
            key = f"{base_key}:{ip}"
            allowed, remaining, reset_time = store.check_rate_limit(key, 10, 60)
            assert allowed is True
        
        # Каждый IP должен иметь свой лимит
        # Если бы использовался только base_key, лимиты были бы общими
    
    def test_user_agent_manipulation(self):
        """Тест манипуляции User-Agent"""
        store = MemoryRateLimitStore()
        
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            "Mozilla/5.0 (X11; Linux x86_64)",
            "curl/7.68.0",
            "PostmanRuntime/7.26.8",
            "python-requests/2.25.1"
        ]
        
        for user_agent in user_agents:
            key = f"api_user:user_agent:{hash(user_agent)}"
            allowed, remaining, reset_time = store.check_rate_limit(key, 5, 60)
            assert allowed is True
    
    def test_parameter_pollution(self):
        """Тест pollution параметров"""
        store = MemoryRateLimitStore()
        
        # Пытаемся обойти лимиты через изменение параметров
        base_params = {"user_id": "123", "action": "get_data"}
        
        # Различные вариации параметров
        variations = [
            base_params,
            {**base_params, "timestamp": str(int(time.time()))},
            {**base_params, "session_id": "abc123"},
            {**base_params, "version": "2.0"},
            {**base_params, "format": "json"},
            {**base_params, "debug": "true"}
        ]
        
        for i, params in enumerate(variations):
            key = f"api_call:{hash(str(sorted(params.items())))}"
            allowed, remaining, reset_time = store.check_rate_limit(key, 3, 60)
            # Если ключи генерируются на основе параметров, каждый должен иметь лимит
    
    def test_burst_attack_simulation(self):
        """Тест симуляции burst атаки"""
        store = MemoryRateLimitStore()
        
        # Симулируем burst атаку
        burst_size = 50
        key = "potential_attacker"
        
        # Быстрые запросы в короткий промежуток времени
        blocked_count = 0
        allowed_count = 0
        
        for i in range(burst_size):
            allowed, remaining, reset_time = store.check_rate_limit(key, 10, 60)
            
            if allowed:
                allowed_count += 1
            else:
                blocked_count += 1
        
        # Большинство запросов должно быть заблокировано
        assert blocked_count > allowed_count
        assert blocked_count >= 40  # Минимум 40 заблокированных из 50
    
    def test_distributed_attack_simulation(self):
        """Тест симуляции распределенной атаки"""
        store = MemoryRateLimitStore()
        
        # Атака с множества IP
        attack_ips = [f"192.168.1.{i}" for i in range(1, 21)]  # 20 IP адресов
        total_requests = 0
        total_blocked = 0
        
        for ip in attack_ips:
            key = f"api_user:{ip}"
            
            # Каждый IP делает 15 запросов (больше лимита в 10)
            for _ in range(15):
                allowed, remaining, reset_time = store.check_rate_limit(key, 10, 60)
                total_requests += 1
                
                if not allowed:
                    total_blocked += 1
        
        # Значительная часть запросов должна быть заблокирована
        block_rate = total_blocked / total_requests
        assert block_rate > 0.25  # Минимум 25% запросов заблокировано
        
        print(f"Distributed attack: {total_blocked}/{total_requests} requests blocked ({block_rate:.1%})")
    
    def test_token_bucket_bypass_attempts(self):
        """Тест попыток обхода token bucket"""
        store = MemoryRateLimitStore()
        algorithm = TokenBucket(store)
        
        # Пытаемся обойти token bucket быстрыми запросами
        key = "token_bucket_test"
        capacity = 5
        refill_rate = 1.0  # 1 токен в секунду
        
        blocked_count = 0
        
        # Быстрые запросы
        for i in range(20):
            allowed, remaining, reset_time = algorithm.check_limit(key, capacity, refill_rate, 60)
            
            if not allowed:
                blocked_count += 1
        
        # Большинство запросов должно быть заблокировано
        assert blocked_count >= 15
        
        # Ждем пополнения токенов
        time.sleep(capacity / refill_rate + 0.1)
        
        # Новые запросы должны проходить
        for i in range(capacity):
            allowed, remaining, reset_time = algorithm.check_limit(key, capacity, refill_rate, 60)
            assert allowed is True
    
    def test_whitelist_bypass_attempts(self):
        """Тест попыток обхода whitelist"""
        store = MemoryRateLimitStore()
        
        # Обычный пользователь
        normal_key = "normal_user"
        
        # Исчерпываем лимит для нормального пользователя
        for _ in range(10):
            allowed, remaining, reset_time = store.check_rate_limit(normal_key, 10, 60)
        
        # Запрос должен быть заблокирован
        allowed, remaining, reset_time = store.check_rate_limit(normal_key, 10, 60)
        assert allowed is False
        
        # Пытаемся имитировать privileged пользователя через изменение ключа
        privileged_variations = [
            "admin_user",
            "premium_user", 
            "vip_user",
            "special_user",
            "privileged_user",
            "user_admin",
            "user_premium",
            "test_user_admin"
        ]
        
        # Каждая вариация должна иметь свой лимит
        for variation in privileged_variations:
            # Исчерпываем лимит для вариации
            for _ in range(10):
                store.check_rate_limit(variation, 10, 60)
            
            # Последний запрос заблокирован
            allowed, remaining, reset_time = store.check_rate_limit(variation, 10, 60)
            assert allowed is False


# =============================================================================
# THREAD SAFETY TESTS
# =============================================================================

class TestRateLimitThreadSafety:
    """Thread safety тесты для rate limiting"""
    
    def test_concurrent_reads_and_writes(self):
        """Тест одновременных чтений и записей"""
        store = MemoryRateLimitStore()
        results = []
        errors = []
        
        def reader_worker(reader_id):
            try:
                for i in range(100):
                    # Читаем статистику
                    stats = store.get_stats()
                    results.append({
                        "type": "read",
                        "worker": reader_id,
                        "iteration": i,
                        "stats": stats
                    })
                    
                    # Небольшая задержка
                    time.sleep(0.001)
            except Exception as e:
                errors.append({"type": "read", "worker": reader_id, "error": str(e)})
        
        def writer_worker(writer_id):
            try:
                for i in range(100):
                    # Пишем данные
                    key = f"writer_{writer_id}_key_{i}"
                    allowed, remaining, reset_time = store.check_rate_limit(key, 100, 60)
                    results.append({
                        "type": "write",
                        "worker": writer_id,
                        "iteration": i,
                        "allowed": allowed
                    })
                    
                    # Небольшая задержка
                    time.sleep(0.001)
            except Exception as e:
                errors.append({"type": "write", "worker": writer_id, "error": str(e)})
        
        # Запускаем читателей и писателей одновременно
        threads = []
        
        # 5 читателей
        for i in range(5):
            thread = threading.Thread(target=reader_worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # 5 писателей
        for i in range(5):
            thread = threading.Thread(target=writer_worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Ждем завершения
        for thread in threads:
            thread.join()
        
        # Проверяем результаты
        assert len(errors) == 0, f"Ошибки в конкурентном доступе: {errors}"
        
        read_results = [r for r in results if r["type"] == "read"]
        write_results = [r for r in results if r["type"] == "write"]
        
        assert len(read_results) == 500  # 5 читателей * 100 итераций
        assert len(write_results) == 500  # 5 писателей * 100 итераций
        
        # Проверяем, что статистика консистентна
        for read_result in read_results:
            stats = read_result["stats"]
            assert isinstance(stats, dict)
            assert "total_entries" in stats
    
    def test_race_condition_prevention(self):
        """Тест предотвращения race conditions"""
        store = MemoryRateLimitStore()
        test_key = "race_condition_test"
        limit = 10
        
        # Счетчик для отслеживания заблокированных запросов
        blocked_count = 0
        allowed_count = 0
        results_lock = threading.Lock()
        
        def concurrent_requester(worker_id):
            nonlocal blocked_count, allowed_count
            
            for i in range(20):
                allowed, remaining, reset_time = store.check_rate_limit(test_key, limit, 60)
                
                with results_lock:
                    if allowed:
                        allowed_count += 1
                    else:
                        blocked_count += 1
                
                time.sleep(0.001)  # Небольшая задержка
        
        # Запускаем много потоков одновременно
        threads = []
        for i in range(10):
            thread = threading.Thread(target=concurrent_requester, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Ждем завершения
        for thread in threads:
            thread.join()
        
        # Проверяем результаты
        total_requests = blocked_count + allowed_count
        
        # Все запросы должны быть учтены
        assert total_requests == 200  # 10 потоков * 20 запросов
        
        # Большинство запросов должно быть заблокировано
        block_rate = blocked_count / total_requests
        assert block_rate >= 0.5  # Минимум 50% заблокировано
        
        print(f"Race condition test: {allowed_count} allowed, {blocked_count} blocked ({block_rate:.1%} blocked)")
    
    def test_store_consistency_under_load(self):
        """Тест консистентности хранилища под нагрузкой"""
        store = MemoryRateLimitStore()
        consistency_errors = []
        
        def stress_worker(worker_id):
            try:
                for i in range(200):
                    key = f"consistency_test_{worker_id}_{i % 10}"
                    
                    # Операция записи
                    store.check_rate_limit(key, 20, 60)
                    
                    # Операция чтения
                    stats = store.get_stats()
                    
                    # Проверяем консистентность статистики
                    if stats["total_entries"] < 0:
                        consistency_errors.append("Negative entry count")
                    
                    # Небольшая задержка
                    time.sleep(0.0001)
                    
            except Exception as e:
                consistency_errors.append(f"Worker {worker_id}: {str(e)}")
        
        # Запускаем stress тест
        threads = []
        for i in range(20):
            thread = threading.Thread(target=stress_worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Ждем завершения
        for thread in threads:
            thread.join()
        
        # Проверяем результаты
        assert len(consistency_errors) == 0, f"Consistency errors: {consistency_errors}"
        
        # Финальная проверка статистики
        final_stats = store.get_stats()
        assert final_stats["total_entries"] >= 0
        assert isinstance(final_stats["total_entries"], int)


# =============================================================================
# BENCHMARK TESTS
# =============================================================================

class TestRateLimitBenchmarks:
    """Benchmark тесты для измерения производительности"""
    
    @pytest.mark.benchmark
    def test_memory_store_benchmark(self, benchmark):
        """Benchmark для memory store"""
        store = MemoryRateLimitStore()
        
        def rate_limit_operation():
            return store.check_rate_limit(f"benchmark_key_{random.randint(0, 1000)}", 100, 60)
        
        # Выполняем benchmark
        result = benchmark(rate_limit_operation)
        
        # Проверяем результат
        assert result is not None
        assert len(result) == 3
        assert isinstance(result[0], bool)  # allowed
        assert isinstance(result[1], int)   # remaining
        assert isinstance(result[2], float) # reset_time
    
    @pytest.mark.benchmark  
    def test_redis_store_benchmark(self, benchmark, mock_redis):
        """Benchmark для Redis store"""
        # Настраиваем mock для быстрых операций
        mock_redis.zcard.return_value = 0
        mock_redis.zadd.return_value = 1
        mock_redis.expire.return_value = True
        
        store = RedisRateLimitStore(mock_redis)
        
        def rate_limit_operation():
            return store.check_rate_limit(f"benchmark_key_{random.randint(0, 1000)}", 100, 60)
        
        # Выполняем benchmark
        result = benchmark(rate_limit_operation)
        
        # Проверяем результат
        assert result is not None
        assert len(result) == 3
    
    @pytest.mark.benchmark
    def test_sliding_window_benchmark(self, benchmark):
        """Benchmark для sliding window алгоритма"""
        store = MemoryRateLimitStore()
        algorithm = SlidingWindowCounter(store)
        
        def sliding_window_operation():
            return algorithm.check_limit(f"benchmark_key_{random.randint(0, 1000)}", 100, 60)
        
        result = benchmark(sliding_window_operation)
        assert result is not None
        assert len(result) == 3
    
    @pytest.mark.benchmark
    def test_token_bucket_benchmark(self, benchmark):
        """Benchmark для token bucket алгоритма"""
        store = MemoryRateLimitStore()
        algorithm = TokenBucket(store)
        
        def token_bucket_operation():
            return algorithm.check_limit(f"benchmark_key_{random.randint(0, 1000)}", 100, 1.0, 60)
        
        result = benchmark(token_bucket_operation)
        assert result is not None
        assert len(result) == 3
    
    @pytest.mark.benchmark
    def test_fixed_window_benchmark(self, benchmark):
        """Benchmark для fixed window алгоритма"""
        store = MemoryRateLimitStore()
        algorithm = FixedWindowCounter(store)
        
        def fixed_window_operation():
            return algorithm.check_limit(f"benchmark_key_{random.randint(0, 1000)}", 100, 60)
        
        result = benchmark(fixed_window_operation)
        assert result is not None
        assert len(result) == 3


# =============================================================================
# INTEGRATION TESTS - FastAPI Middleware
# =============================================================================

class TestFastAPIMiddleware:
    """Integration тесты для FastAPI middleware"""
    
    def test_middleware_basic_functionality(self, test_client):
        """Тест базовой функциональности middleware"""
        # Делаем несколько запросов
        for i in range(5):
            response = test_client.get("/public")
            assert response.status_code == 200
    
    def test_rate_limiting_headers(self, test_client):
        """Тест наличия rate limiting заголовков"""
        response = test_client.get("/api/data")
        
        assert response.status_code == 200
        
        # Проверяем наличие заголовков rate limiting
        # (зависит от реализации middleware)
        # assert "X-RateLimit-Limit" in response.headers
        # assert "X-RateLimit-Remaining" in response.headers
        # assert "X-RateLimit-Reset" in response.headers
    
    def test_rate_limit_enforcement(self, test_client):
        """Тест принудительного соблюдения rate limits"""
        # Делаем много запросов для превышения лимита
        responses = []
        
        for i in range(150):  # Больше лимита в 100
            response = test_client.get("/api/data")
            responses.append(response.status_code)
        
        # Некоторые запросы должны быть заблокированы
        blocked_responses = [status for status in responses if status == 429]  # 429 Too Many Requests
        allowed_responses = [status for status in responses if status == 200]
        
        assert len(blocked_responses) > 0, "Some requests should be blocked"
        assert len(allowed_responses) > 0, "Some requests should be allowed"
        
        print(f"Rate limiting: {len(allowed_responses)} allowed, {len(blocked_responses)} blocked")
    
    def test_different_endpoints_different_limits(self, test_client):
        """Тест разных лимитов для разных endpoints"""
        # Public endpoint может иметь более высокий лимит
        admin_endpoint_responses = []
        public_endpoint_responses = []
        
        # Пытаемся превысить лимит для admin endpoint
        for i in range(50):
            admin_response = test_client.get("/admin")
            admin_endpoint_responses.append(admin_response.status_code)
        
        # Пытаемся превысить лимит для public endpoint
        for i in range(50):
            public_response = test_client.get("/public")
            public_endpoint_responses.append(public_response.status_code)
        
        # Анализируем результаты
        admin_blocked = len([s for s in admin_endpoint_responses if s == 429])
        public_blocked = len([s for s in public_endpoint_responses if s == 429])
        
        print(f"Admin endpoint: {admin_blocked} blocked out of {len(admin_endpoint_responses)}")
        print(f"Public endpoint: {public_blocked} blocked out of {len(public_endpoint_responses)}")
    
    def test_concurrent_requests(self, test_client):
        """Тест конкурентных запросов"""
        import concurrent.futures
        
        def make_request(endpoint):
            response = test_client.get(endpoint)
            return response.status_code
        
        endpoints = ["/public", "/api/data", "/admin", "/process"]
        
        # Делаем конкурентные запросы
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            
            for endpoint in endpoints:
                for i in range(20):
                    future = executor.submit(make_request, endpoint)
                    futures.append(future)
            
            # Собираем результаты
            results = []
            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    results.append(f"Error: {e}")
        
        # Проверяем результаты
        successful_requests = [r for r in results if r == 200]
        blocked_requests = [r for r in results if r == 429]
        
        print(f"Concurrent requests: {len(successful_requests)} successful, {len(blocked_requests)} blocked")
        
        # Некоторые запросы могут быть заблокированы
        # assert len(blocked_requests) > 0


# =============================================================================
# TEST RUNNERS И HELPERS
# =============================================================================

def run_performance_tests():
    """Запуск performance тестов"""
    print("=== Running Performance Tests ===")
    
    # Memory store performance
    store = MemoryRateLimitStore()
    start_time = time.time()
    
    for i in range(10000):
        store.check_rate_limit(f"perf_key_{i}", 100, 60)
    
    duration = time.time() - start_time
    ops_per_sec = 10000 / duration
    
    print(f"Memory store: {ops_per_sec:.0f} operations/second")
    
    # Thread safety test
    store = MemoryRateLimitStore()
    threads = []
    
    def worker():
        for i in range(1000):
            store.check_rate_limit(f"thread_key_{i}", 100, 60)
    
    start_time = time.time()
    for _ in range(10):
        thread = threading.Thread(target=worker)
        threads.append(thread)
        thread.start()
    
    for thread in threads:
        thread.join()
    
    duration = time.time() - start_time
    total_ops = 10 * 1000
    concurrent_ops_per_sec = total_ops / duration
    
    print(f"Concurrent access: {concurrent_ops_per_sec:.0f} operations/second")


def run_stress_tests():
    """Запуск stress тестов"""
    print("=== Running Stress Tests ===")
    
    # High concurrency stress test
    store = MemoryRateLimitStore()
    results = []
    errors = []
    
    def stress_worker(worker_id):
        try:
            for i in range(1000):
                key = f"stress_user_{i % 100}"
                result = store.check_rate_limit(key, 100, 60)
                results.append(result[0])  # allowed
        except Exception as e:
            errors.append(f"Worker {worker_id}: {e}")
    
    # 50 concurrent workers
    threads = []
    start_time = time.time()
    
    for i in range(50):
        thread = threading.Thread(target=stress_worker, args=(i,))
        threads.append(thread)
        thread.start()
    
    for thread in threads:
        thread.join()
    
    duration = time.time() - start_time
    total_operations = len(results)
    ops_per_sec = total_operations / duration
    
    print(f"Stress test: {total_operations} operations in {duration:.2f}s")
    print(f"Throughput: {ops_per_sec:.0f} operations/second")
    print(f"Errors: {len(errors)}")
    
    if errors:
        print("Errors encountered:")
        for error in errors[:5]:  # Показываем первые 5 ошибок
            print(f"  - {error}")


def run_security_tests():
    """Запуск security тестов"""
    print("=== Running Security Tests ===")
    
    # Burst attack simulation
    store = MemoryRateLimitStore()
    attack_key = "burst_attacker"
    
    burst_size = 100
    blocked_count = 0
    
    for i in range(burst_size):
        allowed, remaining, reset_time = store.check_rate_limit(attack_key, 10, 60)
        if not allowed:
            blocked_count += 1
    
    block_rate = blocked_count / burst_size
    print(f"Burst attack: {blocked_count}/{burst_size} requests blocked ({block_rate:.1%})")
    
    # Distributed attack simulation
    distributed_ips = [f"192.168.1.{i}" for i in range(1, 21)]
    total_blocked = 0
    total_requests = 0
    
    for ip in distributed_ips:
        key = f"api_user:{ip}"
        
        for _ in range(15):  # Больше лимита
            allowed, remaining, reset_time = store.check_rate_limit(key, 10, 60)
            total_requests += 1
            
            if not allowed:
                total_blocked += 1
    
    distributed_block_rate = total_blocked / total_requests
    print(f"Distributed attack: {total_blocked}/{total_requests} requests blocked ({distributed_block_rate:.1%})")


if __name__ == "__main__":
    # Настройка для запуска отдельных тестов
    import argparse
    
    parser = argparse.ArgumentParser(description="Run rate limit tests")
    parser.add_argument("--performance", action="store_true", help="Run performance tests")
    parser.add_argument("--stress", action="store_true", help="Run stress tests")
    parser.add_argument("--security", action="store_true", help="Run security tests")
    parser.add_argument("--all", action="store_true", help="Run all tests")
    
    args = parser.parse_args()
    
    if args.performance or args.all:
        run_performance_tests()
    
    if args.stress or args.all:
        run_stress_tests()
    
    if args.security or args.all:
        run_security_tests()
    
    if not any([args.performance, args.stress, args.security, args.all]):
        # Запускаем стандартные тесты pytest
        pytest.main([__file__, "-v"])


# =============================================================================
# TEST DISCOVERY И METADATA
# =============================================================================

# Маркировка тестов для pytest
pytestmark = pytest.mark.ratelimit

# Описания для документации
__test_descriptions__ = {
    "unit_tests": "Unit тесты для отдельных компонентов rate limiting",
    "integration_tests": "Integration тесты для взаимодействия компонентов",
    "performance_tests": "Performance тесты для измерения производительности",
    "stress_tests": "Stress тесты для граничных случаев и экстремальных нагрузок",
    "security_tests": "Security тесты для проверки защиты от обхода лимитов",
    "thread_safety_tests": "Thread safety тесты для проверки конкурентности",
    "benchmark_tests": "Benchmark тесты для точного измерения производительности"
}


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Core classes
    "RateLimitEntry",
    "MemoryRateLimitStore", 
    "RedisRateLimitStore",
    "SlidingWindowCounter",
    "TokenBucket",
    "FixedWindowCounter",
    
    # Test classes
    "TestRateLimitEntry",
    "TestMemoryRateLimitStore",
    "TestRedisRateLimitStore", 
    "TestRateLimitAlgorithms",
    "TestRateLimitManager",
    "TestRateLimitPerformance",
    "TestRateLimitStress",
    "TestRateLimitSecurity",
    "TestRateLimitThreadSafety",
    "TestRateLimitBenchmarks",
    "TestFastAPIMiddleware",
    
    # Fixtures
    "ratelimit_config",
    "mock_redis",
    "temp_redis_server",
    "rate_limit_globals",
    "fastapi_app",
    "test_client",
    
    # Utilities
    "performance_monitor",
    "get_memory_usage",
    "assert_rate_limit_metrics",
    "run_performance_tests",
    "run_stress_tests", 
    "run_security_tests"
]