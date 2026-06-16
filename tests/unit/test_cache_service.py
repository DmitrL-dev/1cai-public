
import asyncio
from datetime import datetime, timedelta

import pytest

import src.services.caching_service as caching_module
from src.services.caching_service import (
    CacheService,
    cache_result,
    memory_cache,
    memory_cache_ttl,
)


@pytest.fixture(autouse=True)
def reset_cache_state():
    """Очищаем глобальное состояние памяти перед и после каждого теста."""
    memory_cache.clear()
    memory_cache_ttl.clear()
    caching_module._cache_service = None
    yield
    memory_cache.clear()
    memory_cache_ttl.clear()
    caching_module._cache_service = None


@pytest.fixture(autouse=True)
def disable_redis(monkeypatch):
    """Заставляем CacheService всегда использовать in-memory fallback."""

    def fake_from_url(*args, **kwargs):
        raise ConnectionError("Redis недоступен в тестовом окружении")

    monkeypatch.setattr("src.services.caching_service.aioredis.from_url", fake_from_url)


@pytest.mark.asyncio
async def test_set_and_get_memory_fallback():
    service = CacheService()

    payload = {"value": 42}
    await service.set("key:memory", payload, ttl=60)

    cached = await service.get("key:memory")
    assert cached == payload


@pytest.mark.asyncio
async def test_ttl_expiration_removes_entry():
    service = CacheService()
    await service.set("expiring:key", {"foo": "bar"}, ttl=1)

    # Принудительно истечём TTL
    memory_cache_ttl["expiring:key"] = datetime.now() - timedelta(seconds=1)

    cached = await service.get("expiring:key")
    assert cached is None
    assert "expiring:key" not in memory_cache
    assert "expiring:key" not in memory_cache_ttl


def test_generate_key_stable_and_unique():
    service = CacheService()
    key1 = service.generate_key("prefix", 1, b=2)
    key2 = service.generate_key("prefix", 1, b=2)
    key3 = service.generate_key("prefix", 2, b=2)

    assert key1 == key2
    assert key1 != key3


@pytest.mark.asyncio
async def test_clear_pattern_removes_matching_entries():
    service = CacheService()
    await service.set("report:123", {"status": "ok"})
    await service.set("report:456", {"status": "warn"})
    await service.set("other:789", {"status": "skip"})

    await service.clear_pattern("report:*")

    assert await service.get("report:123") is None
    assert await service.get("report:456") is None
    # Неподходящий по паттерну ключ остаётся
    assert await service.get("other:789") == {"status": "skip"}


@pytest.mark.asyncio
async def test_cache_result_decorator_caches_async_call():
    calls = []

    @cache_result(ttl=60, key_prefix="tests")
    async def expensive_operation(x):
        calls.append(x)
        await asyncio.sleep(0)  # имитируем асинхронность
        return {"data": x}

    first = await expensive_operation(10)
    second = await expensive_operation(10)

    assert first == second == {"data": 10}
    assert calls == [10]
