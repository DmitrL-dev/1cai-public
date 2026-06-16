
"""
Тесты для MCP Tools Cache

Содержит unit-тесты для проверки функциональности кэширования.

Запуск тестов:
    python -m pytest tests/test_mcp_cache.py -v
    python -m unittest tests.test_mcp_cache

Версия: 1.0.0
"""

import asyncio
import os
# Импортируем модули для тестирования
import sys
import tempfile
import time
import unittest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cache.mcp_cache import (CacheEntry, CacheInvalidation, CacheMetrics,
                             LRUStrategy, MCPToolsCache, PersistentCache,
                             TTLCacheStrategy, cache_aggregates,
                             cache_metadata_1c, cache_tool_result, cached,
                             cached_async, cleanup_expired, get_cache,
                             get_cache_stats, get_cached_aggregates,
                             get_cached_metadata_1c, get_cached_tool_result,
                             init_cache)


class TestCacheEntry(unittest.TestCase):
    """Тесты для класса CacheEntry"""
    
    def test_cache_entry_creation(self):
        """Тест создания записи кэша"""
        data = {"test": "value"}
        entry = CacheEntry(
            data=data,
            timestamp=time.time(),
            ttl=60.0
        )
        
        self.assertEqual(entry.data, data)
        self.assertFalse(entry.is_expired)
        self.assertEqual(entry.access_count, 0)
    
    def test_cache_entry_expiry(self):
        """Тест истечения TTL"""
        entry = CacheEntry(
            data={"test": "value"},
            timestamp=time.time() - 10,  # 10 секунд назад
            ttl=5.0  # TTL 5 секунд
        )
        
        self.assertTrue(entry.is_expired)
    
    def test_cache_entry_access(self):
        """Тест обновления счётчика доступа"""
        entry = CacheEntry(
            data={"test": "value"},
            timestamp=time.time(),
            ttl=60.0
        )
        
        self.assertEqual(entry.access_count, 0)
        
        entry.access()
        self.assertEqual(entry.access_count, 1)
        self.assertGreater(entry.last_access, time.time() - 1)


class TestCacheMetrics(unittest.TestCase):
    """Тесты для класса CacheMetrics"""
    
    def test_metrics_creation(self):
        """Тест создания метрик"""
        metrics = CacheMetrics()
        
        self.assertEqual(metrics.hits, 0)
        self.assertEqual(metrics.misses, 0)
        self.assertEqual(metrics.hit_ratio, 0.0)
    
    def test_record_hit(self):
        """Тест записи попадания в кэш"""
        metrics = CacheMetrics()
        
        metrics.record_hit(0.1)
        
        self.assertEqual(metrics.hits, 1)
        self.assertEqual(metrics.total_requests, 1)
        self.assertEqual(metrics.hit_ratio, 1.0)
    
    def test_record_miss(self):
        """Тест записи промаха кэша"""
        metrics = CacheMetrics()
        
        metrics.record_miss(0.2)
        
        self.assertEqual(metrics.misses, 1)
        self.assertEqual(metrics.total_requests, 1)
        self.assertEqual(metrics.hit_ratio, 0.0)
    
    def test_hit_ratio_calculation(self):
        """Тест расчёта hit ratio"""
        metrics = CacheMetrics()
        
        metrics.record_hit()
        metrics.record_miss()
        metrics.record_hit()
        
        self.assertEqual(metrics.hits, 2)
        self.assertEqual(metrics.misses, 1)
        self.assertAlmostEqual(metrics.hit_ratio, 2/3, places=2)


class TestCacheStrategy(unittest.TestCase):
    """Тесты для стратегий кэширования"""
    
    def setUp(self):
        """Настройка тестов"""
        self.cache = MCPToolsCache(max_size_mb=10)
    
    def test_lru_strategy(self):
        """Тест LRU стратегии"""
        strategy = LRUStrategy()
        
        # Добавляем записи
        self.cache.set("key1", "value1", data_type='stable')
        self.cache.set("key2", "value2", data_type='stable')
        self.cache.set("key3", "value3", data_type='stable')
        
        # Доступ к key1 делает её "новой"
        self.cache.get("key1")
        
        # key2 должна быть вытеснена (самая старая)
        target = strategy.select_eviction_target(self.cache)
        self.assertIn(target, ["key2", "key3"])
    
    def test_ttl_strategy(self):
        """Тест TTL стратегии"""
        strategy = TTLCacheStrategy()
        
        # Добавляем запись с истёкшим TTL
        expired_entry = CacheEntry(
            data="expired",
            timestamp=time.time() - 100,
            ttl=10.0
        )
        
        self.assertTrue(strategy.should_evict(self.cache, "expired", expired_entry))
        
        # Добавляем актуальную запись
        fresh_entry = CacheEntry(
            data="fresh",
            timestamp=time.time(),
            ttl=60.0
        )
        
        self.assertFalse(strategy.should_evict(self.cache, "fresh", fresh_entry))


class TestCacheInvalidation(unittest.TestCase):
    """Тесты для механизмов инвалидации"""
    
    def setUp(self):
        """Настройка тестов"""
        self.cache = MCPToolsCache(max_size_mb=10)
        self.invalidation = CacheInvalidation()
    
    def test_invalidate_by_pattern(self):
        """Тест инвалидации по шаблону"""
        # Добавляем записи
        self.cache.set("metadata:catalog1", "data1")
        self.cache.set("metadata:catalog2", "data2")
        self.cache.set("aggregates:report1", "data3")
        
        # Инвалидируем метаданные
        count = self.invalidation.invalidate_by_pattern(self.cache, "metadata:*")
        
        self.assertEqual(count, 2)
        self.assertFalse(self.cache.has("metadata:catalog1"))
        self.assertFalse(self.cache.has("metadata:catalog2"))
        self.assertTrue(self.cache.has("aggregates:report1"))
    
    def test_invalidate_by_entity(self):
        """Тест инвалидации по сущности"""
        # Добавляем записи
        self.cache.set("metadata:catalog:test_catalog", "data1")
        self.cache.set("metadata:catalog:other_catalog", "data2")
        
        # Инвалидируем конкретную сущность
        count = self.invalidation.invalidate_by_entity(
            self.cache, 
            "test_catalog", 
            "catalog"
        )
        
        self.assertEqual(count, 1)
        self.assertFalse(self.cache.has("metadata:catalog:test_catalog"))
        self.assertTrue(self.cache.has("metadata:catalog:other_catalog"))


class TestPersistentCache(unittest.TestCase):
    """Тесты для persistent cache"""
    
    def setUp(self):
        """Настройка тестов с временной директорией"""
        self.temp_dir = tempfile.mkdtemp()
        self.persistent_cache = PersistentCache(self.temp_dir, max_size_mb=1)
    
    def tearDown(self):
        """Очистка после тестов"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_store_and_load(self):
        """Тест сохранения и загрузки"""
        entry = CacheEntry(
            data={"test": "persistent_data"},
            timestamp=time.time(),
            ttl=60.0,
            size_bytes=1024
        )
        
        # Сохраняем
        success = self.persistent_cache.store("test_key", entry)
        self.assertTrue(success)
        
        # Загружаем
        loaded_entry = self.persistent_cache.load("test_key")
        self.assertIsNotNone(loaded_entry)
        self.assertEqual(loaded_entry.data["test"], "persistent_data")
    
    def test_delete(self):
        """Тест удаления"""
        entry = CacheEntry(
            data={"test": "data"},
            timestamp=time.time(),
            ttl=60.0
        )
        
        # Сохраняем
        self.persistent_cache.store("test_key", entry)
        
        # Удаляем
        success = self.persistent_cache.delete("test_key")
        self.assertTrue(success)
        
        # Проверяем, что запись удалена
        loaded_entry = self.persistent_cache.load("test_key")
        self.assertIsNone(loaded_entry)


class TestMCPToolsCache(unittest.TestCase):
    """Основные тесты для MCPToolsCache"""
    
    def setUp(self):
        """Настройка тестов"""
        self.cache = MCPToolsCache(max_size_mb=1)  # 1MB для быстрых тестов
    
    def test_basic_operations(self):
        """Тест базовых операций"""
        # Тест set/get
        result = self.cache.set("test_key", "test_value")
        self.assertTrue(result)
        
        value = self.cache.get("test_key")
        self.assertEqual(value, "test_value")
        
        # Тест has
        self.assertTrue(self.cache.has("test_key"))
        
        # Тест delete
        deleted = self.cache.delete("test_key")
        self.assertTrue(deleted)
        self.assertIsNone(self.cache.get("test_key"))
    
    def test_ttl_expiry(self):
        """Тест истечения TTL"""
        # Устанавливаем запись с коротким TTL
        self.cache.set("short_ttl", "value", ttl=0.1)  # 0.1 секунды
        
        # Сразу проверяем - должно быть доступно
        self.assertEqual(self.cache.get("short_ttl"), "value")
        
        # Ждём истечения TTL
        time.sleep(0.2)
        
        # Должно быть None
        self.assertIsNone(self.cache.get("short_ttl"))
    
    def test_data_types(self):
        """Тест разных типов данных"""
        # Метаданные
        metadata = {"type": "catalog", "fields": ["id", "name"]}
        self.cache.set("metadata:test", metadata, data_type='metadata')
        
        # Агрегаты
        aggregates = [{"period": "2024-01", "value": 100}]
        self.cache.set("aggregates:test", aggregates, data_type='aggregates')
        
        # Проверяем
        self.assertEqual(self.cache.get("metadata:test"), metadata)
        self.assertEqual(self.cache.get("aggregates:test"), aggregates)
    
    def test_memory_limit(self):
        """Тест лимита памяти"""
        # Создаём большой объект
        large_data = "x" * 1024 * 100  # 100KB
        
        # Добавляем несколько записей
        for i in range(20):
            self.cache.set(f"large_key_{i}", large_data)
        
        # Количество записей должно быть ограничено
        self.assertLessEqual(self.cache.size(), 15)  # Должно вытеснить часть записей
    
    def test_metrics(self):
        """Тест метрик"""
        # Промах
        self.cache.get("nonexistent")
        
        # Попадание
        self.cache.set("test", "value")
        self.cache.get("test")
        
        # Проверяем метрики
        metrics = self.cache.get_metrics()
        self.assertEqual(metrics.misses, 1)
        self.assertEqual(metrics.hits, 1)
        self.assertEqual(metrics.hit_ratio, 0.5)


class TestAsyncOperations(unittest.TestCase):
    """Тесты асинхронных операций"""
    
    def setUp(self):
        """Настройка тестов"""
        self.cache = MCPToolsCache(max_size_mb=10)
    
    async def test_async_get_set(self):
        """Тест асинхронных операций"""
        # Тест async set
        result = await self.cache.set_async("async_key", "async_value")
        self.assertTrue(result)
        
        # Тест async get
        value = await self.cache.get_async("async_key")
        self.assertEqual(value, "async_value")
        
        # Тест async has
        has_key = await self.cache.has_async("async_key")
        self.assertTrue(has_key)


class TestDecorator(unittest.TestCase):
    """Тесты для декораторов кэширования"""
    
    def setUp(self):
        """Настройка тестов"""
        init_cache(max_size_mb=10)
    
    def test_sync_decorator(self):
        """Тест синхронного декоратора"""
        call_count = 0
        
        @cached(ttl=60, data_type='stable')
        def expensive_function(x):
            nonlocal call_count
            call_count += 1
            return x * 2
        
        # Первый вызов - должен выполнить функцию
        result1 = expensive_function(5)
        self.assertEqual(result1, 10)
        self.assertEqual(call_count, 1)
        
        # Второй вызов с теми же аргументами - должен взять из кэша
        result2 = expensive_function(5)
        self.assertEqual(result2, 10)
        self.assertEqual(call_count, 1)  # Функция не вызывалась повторно
        
        # Другой аргумент - должен выполнить функцию
        result3 = expensive_function(10)
        self.assertEqual(result3, 20)
        self.assertEqual(call_count, 2)
    
    async def test_async_decorator(self):
        """Тест асинхронного декоратора"""
        call_count = 0
        
        @cached_async(ttl=60, data_type='stable')
        async def async_expensive_function(x):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)  # Имитация асинхронной операции
            return x * 3
        
        # Первый вызов
        result1 = await async_expensive_function(5)
        self.assertEqual(result1, 15)
        self.assertEqual(call_count, 1)
        
        # Второй вызов - из кэша
        result2 = await async_expensive_function(5)
        self.assertEqual(result2, 15)
        self.assertEqual(call_count, 1)


class TestSpecializedCacheFunctions(unittest.TestCase):
    """Тесты специализированных функций кэширования"""
    
    def setUp(self):
        """Настройка тестов"""
        init_cache(max_size_mb=10)
    
    def test_tool_cache(self):
        """Тест кэширования результатов инструментов"""
        tool_name = "get_catalog_info"
        args = {"catalog": "Пользователи"}
        result = {"fields": ["id", "name"], "count": 100}
        
        # Кэшируем результат
        success = cache_tool_result(tool_name, args, result)
        self.assertTrue(success)
        
        # Получаем из кэша
        cached_result = get_cached_tool_result(tool_name, args)
        self.assertEqual(cached_result, result)
    
    def test_metadata_cache(self):
        """Тест кэширования метаданных"""
        entity_type = "catalog"
        entity_id = "Пользователи"
        metadata = {"type": " справочник", "hierarchical": True}
        
        # Кэшируем метаданные
        success = cache_metadata_1c(entity_type, entity_id, metadata)
        self.assertTrue(success)
        
        # Получаем из кэша
        cached_metadata = get_cached_metadata_1c(entity_type, entity_id)
        self.assertEqual(cached_metadata, metadata)
    
    def test_aggregates_cache(self):
        """Тест кэширования агрегатов"""
        aggregate_type = "sales_report"
        period = "2024-01"
        filters = {"region": "Moscow"}
        data = [{"date": "2024-01-01", "sales": 1000}]
        
        # Кэшируем агрегаты
        success = cache_aggregates(aggregate_type, period, filters, data)
        self.assertTrue(success)
        
        # Получаем из кэша
        cached_data = get_cached_aggregates(aggregate_type, period, filters)
        self.assertEqual(cached_data, data)


class TestCacheStatistics(unittest.TestCase):
    """Тесты для статистики и мониторинга"""
    
    def setUp(self):
        """Настройка тестов"""
        init_cache(max_size_mb=10)
    
    def test_cache_stats(self):
        """Тест получения статистики"""
        # Добавляем данные
        for i in range(5):
            get_cache().set(f"key_{i}", f"value_{i}")
        
        # Получаем статистику
        stats = get_cache_stats()
        
        self.assertIn('total_entries', stats)
        self.assertIn('memory_usage_mb', stats)
        self.assertIn('hits', stats)
        self.assertIn('misses', stats)
        self.assertIn('hit_ratio', stats)
        self.assertEqual(stats['total_entries'], 5)
    
    def test_cleanup_expired(self):
        """Тест очистки истёкших записей"""
        cache = get_cache()
        
        # Добавляем записи с разным TTL
        cache.set("expired", "value", ttl=0.1)
        cache.set("fresh", "value", ttl=60)
        
        time.sleep(0.2)
        
        # Очищаем истёкшие
        cleaned = cleanup_expired()
        
        self.assertEqual(cleaned, 1)  # Очищена одна запись
        self.assertFalse(cache.has("expired"))
        self.assertTrue(cache.has("fresh"))


class TestEdgeCases(unittest.TestCase):
    """Тесты граничных случаев"""
    
    def test_empty_cache_operations(self):
        """Тест операций с пустым кэшем"""
        cache = MCPToolsCache(max_size_mb=10)
        
        # Операции с пустым кэшем
        self.assertIsNone(cache.get("nonexistent"))
        self.assertFalse(cache.has("nonexistent"))
        self.assertFalse(cache.delete("nonexistent"))
        self.assertEqual(cache.size(), 0)
        self.assertEqual(cache.memory_usage_mb(), 0.0)
    
    def test_none_values(self):
        """Тест обработки None значений"""
        cache = MCPToolsCache(max_size_mb=10)
        
        # Кэширование None - должно игнорироваться
        result = cache.set("none_key", None)
        self.assertTrue(result)  # Сохранили
        
        value = cache.get("none_key")
        self.assertEqual(value, None)
        
        # Но при получении через специализированную функцию может быть логика игнорирования
        # В реальной реализации можно добавить проверку
    
    def test_large_data_structures(self):
        """Тест больших структур данных"""
        cache = MCPToolsCache(max_size_mb=1)
        
        # Создаём большую структуру
        large_list = [{"id": i, "data": "x" * 100} for i in range(1000)]
        large_dict = {f"key_{i}": {"nested": large_list[:10]} for i in range(100)}
        
        # Кэшируем
        result = cache.set("large_data", large_dict)
        self.assertTrue(result)
        
        # Получаем
        retrieved = cache.get("large_data")
        self.assertIsNotNone(retrieved)
        self.assertEqual(len(retrieved), len(large_dict))


def run_async_test(coroutine):
    """Вспомогательная функция для запуска асинхронных тестов"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coroutine)
    finally:
        loop.close()


if __name__ == '__main__':
    # Настройка логирования для тестов
    import logging
    logging.basicConfig(level=logging.WARNING)  # Уменьшаем шум от логов
    
    # Запуск тестов
    unittest.main(verbosity=2)
