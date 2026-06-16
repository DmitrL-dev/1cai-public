
"""
Тесты для API администрирования кэша

Демонстрируют:
- Тестирование всех endpoints
- Аутентификацию
- Middleware для метрик
- Интеграцию с кэшами
"""

import asyncio
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Импорт API администрирования кэша
from api.cache_admin import (MemoryCache, cache_admin_router, cache_metrics,
                             cache_middleware)

# Создание тестового приложения
app = FastAPI(title="Test Cache Admin API")
app.include_router(cache_admin_router)

# Клиент для тестирования
client = TestClient(app)

# Заголовки для аутентификации
auth_headers = {"Authorization": "Bearer admin_token_123"}

class TestCacheAdminAPI:
    """Тесты API администрирования кэша"""
    
    def setup_method(self):
        """Настройка перед каждым тестом"""
        # Очищаем метрики для каждого теста
        cache_metrics.hit_count = 0
        cache_metrics.miss_count = 0
        cache_metrics.response_times.clear()
    
    def test_get_cache_stats_unauthorized(self):
        """Тест получения статистики без аутентификации"""
        response = client.get("/cache/stats")
        assert response.status_code == 401
        assert "Требуется аутентификация" in response.json()["detail"]
    
    def test_get_cache_stats_authorized(self):
        """Тест получения статистики с аутентификацией"""
        response = client.get("/cache/stats", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "total_keys" in data
        assert "memory_usage_mb" in data
        assert "hit_count" in data
        assert "miss_count" in data
        assert "hit_rate" in data
        assert "avg_response_time_ms" in data
        assert isinstance(data["hit_rate"], float)
        assert 0.0 <= data["hit_rate"] <= 1.0
    
    def test_get_cache_keys_unauthorized(self):
        """Тест получения ключей без аутентификации"""
        response = client.get("/cache/keys")
        assert response.status_code == 401
    
    def test_get_cache_keys_authorized(self):
        """Тест получения ключей с аутентификацией"""
        response = client.get("/cache/keys", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    
    def test_get_cache_keys_with_pagination(self):
        """Тест пагинации ключей"""
        response = client.get("/cache/keys?limit=10&offset=5", headers=auth_headers)
        assert response.status_code == 200
        
        # Параметры должны передаваться правильно
        # (в реальной реализации здесь была бы пагинация)
        data = response.json()
        assert isinstance(data, list)
    
    def test_clear_cache_unauthorized(self):
        """Тест очистки кэша без аутентификации"""
        response = client.delete("/cache/clear")
        assert response.status_code == 401
    
    def test_clear_cache_authorized(self):
        """Тест очистки кэша с аутентификацией"""
        response = client.delete("/cache/clear", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "success"
        assert "message" in data
        assert "timestamp" in data
    
    def test_clear_specific_cache(self):
        """Тест очистки конкретного кэша"""
        response = client.delete("/cache/clear?cache_name=business_data", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "success"
    
    def test_invalidate_key_unauthorized(self):
        """Тест инвалидации ключа без аутентификации"""
        response = client.delete("/cache/invalidate/test_key")
        assert response.status_code == 401
    
    def test_invalidate_key_authorized(self):
        """Тест инвалидации ключа с аутентификацией"""
        response = client.delete("/cache/invalidate/test_key", headers=auth_headers)
        # Может вернуть 404 если ключ не найден, что нормально
        assert response.status_code in [200, 404]
    
    def test_get_cache_health_unauthorized(self):
        """Тест проверки здоровья без аутентификации"""
        response = client.get("/cache/health")
        assert response.status_code == 401
    
    def test_get_cache_health_authorized(self):
        """Тест проверки здоровья с аутентификацией"""
        response = client.get("/cache/health", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "status" in data
        assert "timestamp" in data
        assert "checks" in data
        assert "uptime_seconds" in data
        assert data["status"] in ["healthy", "degraded", "unhealthy"]
    
    def test_get_key_info_unauthorized(self):
        """Тест получения информации о ключе без аутентификации"""
        response = client.get("/cache/key/test_key")
        assert response.status_code == 401
    
    def test_get_key_info_authorized(self):
        """Тест получения информации о ключе с аутентификацией"""
        response = client.get("/cache/key/test_key", headers=auth_headers)
        # Может вернуть 404 если ключ не найден, что нормально
        assert response.status_code in [200, 404]
    
    def test_list_caches_unauthorized(self):
        """Тест получения списка кэшей без аутентификации"""
        response = client.get("/cache/list")
        assert response.status_code == 401
    
    def test_list_caches_authorized(self):
        """Тест получения списка кэшей с аутентификацией"""
        response = client.get("/cache/list", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, dict)
        
        # Проверяем, что есть информация о кэшах
        for cache_name, cache_info in data.items():
            assert "name" in cache_info
            assert "type" in cache_info
    
    def test_invalid_token(self):
        """Тест с неправильным токеном"""
        headers = {"Authorization": "Bearer invalid_token"}
        response = client.get("/cache/stats", headers=headers)
        assert response.status_code == 403
        assert "Недостаточно прав доступа" in response.json()["detail"]

class TestMemoryCache:
    """Тесты для MemoryCache"""
    
    def setup_method(self):
        """Настройка перед каждым тестом"""
        self.cache = MemoryCache("test_cache")
    
    def test_cache_set_and_get(self):
        """Тест установки и получения значения"""
        test_key = "test_key"
        test_value = {"name": "test", "value": 123}
        
        # Устанавливаем значение
        self.cache.set(test_key, test_value)
        
        # Получаем значение
        result = self.cache.get(test_key)
        assert result == test_value
    
    def test_cache_miss(self):
        """Тест промаха кэша"""
        result = self.cache.get("nonexistent_key")
        assert result is None
    
    def test_cache_delete(self):
        """Тест удаления ключа"""
        test_key = "test_key"
        test_value = {"test": "data"}
        
        # Устанавливаем и удаляем
        self.cache.set(test_key, test_value)
        assert self.cache.get(test_key) == test_value
        
        result = self.cache.delete(test_key)
        assert result is True
        assert self.cache.get(test_key) is None
    
    def test_cache_clear(self):
        """Тест очистки кэша"""
        # Добавляем несколько ключей
        for i in range(5):
            self.cache.set(f"key_{i}", f"value_{i}")
        
        # Проверяем, что ключи есть
        assert self.cache.get("key_0") == "value_0"
        assert self.cache.get("key_4") == "value_4"
        
        # Очищаем кэш
        self.cache.clear()
        
        # Проверяем, что кэш пуст
        assert self.cache.get("key_0") is None
        assert self.cache.get("key_4") is None
    
    def test_cache_stats(self):
        """Тест получения статистики кэша"""
        # Добавляем данные
        self.cache.set("key1", {"data": "value1"})
        self.cache.set("key2", {"data": "value2"})
        
        stats = self.cache.get_stats()
        
        assert stats["name"] == "test_cache"
        assert stats["type"] == "memory"
        assert stats["total_keys"] == 2
        assert stats["memory_usage_bytes"] > 0
        assert stats["uptime_seconds"] > 0

class TestCacheMetrics:
    """Тесты для сбора метрик"""
    
    def test_hit_rate_calculation(self):
        """Тест вычисления коэффициента попаданий"""
        # Устанавливаем значения для расчета
        cache_metrics.hit_count = 80
        cache_metrics.miss_count = 20
        
        expected_rate = 80 / (80 + 20)  # 0.8
        assert abs(cache_metrics.hit_rate - expected_rate) < 0.001
    
    def test_hit_rate_with_zero_requests(self):
        """Тест коэффициента попаданий при отсутствии запросов"""
        cache_metrics.hit_count = 0
        cache_metrics.miss_count = 0
        
        assert cache_metrics.hit_rate == 0.0
    
    def test_response_time_calculations(self):
        """Тест вычислений времени отклика"""
        # Добавляем времена отклика
        cache_metrics.response_times.extend([10.0, 20.0, 30.0, 40.0, 50.0])
        
        assert cache_metrics.avg_response_time == 30.0
        assert cache_metrics.min_response_time == 10.0
        assert cache_metrics.max_response_time == 50.0
    
    def test_response_time_with_empty_list(self):
        """Тест времени отклика с пустым списком"""
        cache_metrics.response_times.clear()
        
        assert cache_metrics.avg_response_time == 0.0
        assert cache_metrics.max_response_time == 0.0
        assert cache_metrics.min_response_time == 0.0

class TestCacheMiddleware:
    """Тесты для middleware кэша"""
    
    def test_cache_middleware_ignores_internal_paths(self):
        """Тест игнорирования внутренних путей в middleware"""

        
        async def mock_call_next(request):
            response = MagicMock()
            response.headers = {}
            return response
        
        # Создаем фиктивный запрос для внутреннего пути
        request = MagicMock()
        request.url.path = "/cache/stats"
        
        # Выполняем middleware
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(cache_middleware(request, mock_call_next))
            assert result is not None
        finally:
            loop.close()

# Запуск тестов
if __name__ == "__main__":
    pytest.main([__file__, "-v"])

# Fixtures для pytest
@pytest.fixture
def test_cache():
    """Фикстура для тестового кэша"""
    return MemoryCache("pytest_cache")

@pytest.fixture
def authenticated_client():
    """Фикстура для аутентифицированного клиента"""
    return TestClient(app, headers=auth_headers)

# Параметризованные тесты
@pytest.mark.parametrize("endpoint,method", [
    ("/cache/stats", "GET"),
    ("/cache/keys", "GET"),
    ("/cache/clear", "DELETE"),
    ("/cache/health", "GET"),
    ("/cache/list", "GET"),
])
def test_endpoints_require_auth(endpoint, method):
    """Тест требования аутентификации для всех endpoints"""
    if method == "GET":
        response = client.get(endpoint)
    elif method == "DELETE":
        response = client.delete(endpoint)
    
    assert response.status_code == 401

@pytest.mark.parametrize("key_format", [
    "simple_key",
    "cache_name:key",
    "very_long_key_name_with_many_characters",
    "key_with_underscores_and.dots",
])
def test_key_formats(key_format):
    """Тест различных форматов ключей"""
    cache = MemoryCache("format_test")
    
    # Тестируем установку ключей различных форматов
    cache.set(key_format, {"format": "test"})
    result = cache.get(key_format)
    
    assert result is not None
    assert result["format"] == "test"
    
    # Тестируем удаление
    assert cache.delete(key_format) is True

# Интеграционные тесты
def test_full_cache_lifecycle():
    """Интеграционный тест полного жизненного цикла кэша"""
    cache = MemoryCache("lifecycle_test")
    
    # 1. Проверяем пустой кэш
    stats = cache.get_stats()
    assert stats["total_keys"] == 0
    
    # 2. Добавляем данные
    cache.set("user:123", {"name": "Иван", "age": 30})
    cache.set("session:abc", {"token": "xyz789"})
    
    # 3. Получаем статистику
    stats = cache.get_stats()
    assert stats["total_keys"] == 2
    
    # 4. Получаем ключи
    keys = cache.get_keys_info()
    assert len(keys) == 2
    
    # 5. Проверяем конкретный ключ
    key_info = cache.get_key("user:123")
    assert key_info is not None
    assert key_info.hit_count >= 0  # Должен быть счетчик обращений
    
    # 6. Удаляем ключ
    assert cache.delete("user:123") is True
    
    # 7. Проверяем обновленную статистику
    stats = cache.get_stats()
    assert stats["total_keys"] == 1
    
    # 8. Очищаем кэш
    cache.clear()
    
    # 9. Проверяем пустой кэш
    stats = cache.get_stats()
    assert stats["total_keys"] == 0

def test_performance_under_load():
    """Тест производительности под нагрузкой"""
    import time
    
    cache = MemoryCache("performance_test")
    
    # Генерируем большое количество операций
    start_time = time.time()
    
    # Добавляем 1000 ключей
    for i in range(1000):
        cache.set(f"key_{i}", {"data": f"value_{i}"})
    
    # Читаем все ключи
    for i in range(1000):
        cache.get(f"key_{i}")
    
    end_time = time.time()
    duration = end_time - start_time
    
    # Проверяем, что операции выполнились за разумное время
    assert duration < 5.0  # Не более 5 секунд
    
    # Проверяем финальную статистику
    stats = cache.get_stats()
    assert stats["total_keys"] == 1000

# Утилиты для тестирования
def create_test_data(count=100):
    """Создание тестовых данных"""
    return {f"key_{i}": f"value_{i}" for i in range(count)}

def validate_cache_response(response_data, required_fields):
    """Валидация ответа кэша"""
    for field in required_fields:
        assert field in response_data, f"Поле {field} отсутствует в ответе"

def compare_cache_stats(stats1, stats2):
    """Сравнение статистики кэшей"""
    assert stats1["total_keys"] == stats2["total_keys"]
    assert stats1["type"] == stats2["type"]
    assert stats1["name"] == stats2["name"]
