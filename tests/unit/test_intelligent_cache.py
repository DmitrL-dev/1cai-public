"""
Tests for IntelligentCache (intelligent_cache.py).
"""

import time

from src.ai.intelligent_cache import CacheEntry, IntelligentCache


def test_cache_entry_is_expired() -> None:
    """Тест проверки истечения срока действия записи."""
    from datetime import datetime, timedelta

    # Запись без TTL не истекает
    entry = CacheEntry(
        value="test",
        created_at=datetime.utcnow(),
        expires_at=None,
    )
    assert not entry.is_expired()

    # Запись с истёкшим TTL
    entry = CacheEntry(
        value="test",
        created_at=datetime.utcnow() - timedelta(seconds=10),
        expires_at=datetime.utcnow() - timedelta(seconds=5),
    )
    assert entry.is_expired()

    # Запись с действующим TTL
    entry = CacheEntry(
        value="test",
        created_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(seconds=10),
    )
    assert not entry.is_expired()


def test_cache_entry_touch() -> None:
    """Тест обновления времени доступа."""
    from datetime import datetime

    entry = CacheEntry(
        value="test",
        created_at=datetime.utcnow(),
    )
    initial_count = entry.access_count
    initial_time = entry.last_accessed

    time.sleep(0.01)  # Небольшая задержка
    entry.touch()

    assert entry.access_count == initial_count + 1
    assert entry.last_accessed > initial_time


def test_intelligent_cache_get_set() -> None:
    """Тест базовых операций get/set."""
    cache = IntelligentCache(max_size=10)

    # Установить значение
    cache.set("test query", "test value")

    # Получить значение
    value = cache.get("test query")
    assert value == "test value"

    # Получить несуществующее значение
    value = cache.get("nonexistent query")
    assert value is None


def test_intelligent_cache_ttl() -> None:
    """Тест TTL для кэша."""
    cache = IntelligentCache(max_size=10, default_ttl_seconds=1)

    # Установить значение с коротким TTL
    cache.set("test query", "test value", ttl_seconds=1)

    # Значение должно быть доступно сразу
    assert cache.get("test query") == "test value"

    # Подождать истечения TTL
    time.sleep(1.1)

    # Значение должно быть удалено
    assert cache.get("test query") is None


def test_intelligent_cache_query_type_ttl() -> None:
    """Тест TTL на основе типа запроса."""
    cache = IntelligentCache(max_size=10)

    # Установить значение с типом запроса
    cache.set("test query", "test value", query_type="code_generation")

    # Проверить, что TTL установлен правильно
    key = cache._generate_key("test query")
    entry = cache._cache[key]
    assert entry.query_type == "code_generation"
    assert entry.expires_at is not None


def test_intelligent_cache_tags() -> None:
    """Тест инвалидации по тегам."""
    cache = IntelligentCache(max_size=10)

    # Установить значения с тегами
    cache.set("query1", "value1", tags={"tag1", "tag2"})
    cache.set("query2", "value2", tags={"tag2", "tag3"})
    cache.set("query3", "value3", tags={"tag3"})

    # Инвалидировать по тегу tag2
    count = cache.invalidate_by_tags({"tag2"})
    assert count == 2  # query1 и query2 должны быть удалены

    # Проверить, что query3 остался
    assert cache.get("query3") == "value3"
    assert cache.get("query1") is None
    assert cache.get("query2") is None


def test_intelligent_cache_lru_eviction() -> None:
    """Тест LRU eviction при переполнении."""
    cache = IntelligentCache(max_size=3)

    # Заполнить кэш
    cache.set("query1", "value1")
    cache.set("query2", "value2")
    cache.set("query3", "value3")

    # Добавить ещё один запрос (должен вытеснить самый старый)
    cache.set("query4", "value4")

    # query1 должен быть удалён (самый старый)
    assert cache.get("query1") is None
    assert cache.get("query2") == "value2"
    assert cache.get("query3") == "value3"
    assert cache.get("query4") == "value4"


def test_intelligent_cache_metrics() -> None:
    """Тест метрик кэша."""
    cache = IntelligentCache(max_size=10)

    # Сделать несколько операций
    cache.set("query1", "value1")
    cache.get("query1")  # hit
    cache.get("query2")  # miss
    cache.get("query1")  # hit

    metrics = cache.get_metrics()
    assert metrics["hits"] == 2
    assert metrics["misses"] == 1
    assert metrics["hit_rate"] == 2 / 3
    assert metrics["size"] == 1


def test_intelligent_cache_cleanup_expired() -> None:
    """Тест очистки истёкших записей."""
    cache = IntelligentCache(max_size=10)

    # Установить значения с разными TTL
    cache.set("query1", "value1", ttl_seconds=1)
    cache.set("query2", "value2", ttl_seconds=10)

    # Подождать истечения TTL для query1
    time.sleep(1.1)

    # Очистить истёкшие записи
    count = cache.cleanup_expired()
    assert count == 1

    # Проверить, что query1 удалён, а query2 остался
    assert cache.get("query1") is None
    assert cache.get("query2") == "value2"


def test_intelligent_cache_invalidate_by_query_type() -> None:
    """Тест инвалидации по типу запроса."""
    cache = IntelligentCache(max_size=10)

    # Установить значения с разными типами запросов
    cache.set("query1", "value1", query_type="code_generation")
    cache.set("query2", "value2", query_type="reasoning")
    cache.set("query3", "value3", query_type="code_generation")

    # Инвалидировать по типу code_generation
    count = cache.invalidate_by_query_type("code_generation")
    assert count == 2  # query1 и query3 должны быть удалены

    # Проверить результаты
    assert cache.get("query1") is None
    assert cache.get("query2") == "value2"
    assert cache.get("query3") is None
