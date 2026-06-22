"""
Performance tests for ConnectionPool.
"""

import asyncio
import time

import pytest

from src.ai.connection_pool import ConnectionPool


@pytest.mark.asyncio
async def test_connection_pool_concurrent_access():
    """Тест производительности при конкурентном доступе к пулу."""
    pool = ConnectionPool(max_size=10, timeout=60)

    async def get_session(key: str):
        session = await pool.get_session(key)
        # Имитация небольшой задержки
        await asyncio.sleep(0.001)
        return session

    # Конкурентный доступ к пулу
    start_time = time.time()
    tasks = [get_session(f"http://test{i}.com") for i in range(20)]
    sessions = await asyncio.gather(*tasks)
    end_time = time.time()

    # Все сессии должны быть получены
    assert len(sessions) == 20

    # Время выполнения должно быть приемлемым (< 1 секунда для 20 запросов)
    duration = end_time - start_time
    assert duration < 1.0, f"Too slow: {duration:.3f}s for 20 concurrent requests"

    await pool.close_all()


@pytest.mark.asyncio
async def test_connection_pool_reuse_performance():
    """Тест производительности переиспользования сессий."""
    pool = ConnectionPool(max_size=5, timeout=60)

    # Создаем сессии
    sessions = []
    for i in range(5):
        session = await pool.get_session(f"http://test{i}.com")
        sessions.append(session)

    # Переиспользуем сессии (должно быть быстрее)
    start_time = time.time()
    for _ in range(100):
        for i in range(5):
            session = await pool.get_session(f"http://test{i}.com")
            assert session is sessions[i]  # Та же сессия

    end_time = time.time()
    duration = end_time - start_time

    # 500 операций должны выполняться очень быстро (< 0.5 секунды)
    assert duration < 0.5, f"Too slow: {duration:.3f}s for 500 reuse operations"

    await pool.close_all()


@pytest.mark.asyncio
async def test_connection_pool_eviction_performance():
    """Тест производительности при частой eviction."""
    pool = ConnectionPool(max_size=3, timeout=60)

    start_time = time.time()

    # Создаем много сессий, что приводит к частой eviction
    for i in range(100):
        await pool.get_session(f"http://test{i}.com")

    end_time = time.time()
    duration = end_time - start_time

    # 100 операций с eviction должны выполняться быстро (< 1 секунды)
    assert duration < 1.0, f"Too slow: {duration:.3f}s for 100 eviction operations"

    await pool.close_all()


@pytest.mark.asyncio
async def test_connection_pool_memory_efficiency():
    """Тест эффективности использования памяти (проверка утечек)."""
    import gc

    # Object enumeration lives in `gc`, not `sys` (the original `sys.get_objects`
    # does not exist and raised AttributeError). Collect first so previously
    # created-but-unreferenced pools don't inflate the baseline.
    gc.collect()
    initial_size = len(
        [obj for obj in gc.get_objects() if isinstance(obj, ConnectionPool)]
    )

    # Создаем и закрываем много пулов
    for _ in range(10):
        pool = ConnectionPool(max_size=5, timeout=60)
        for i in range(10):
            await pool.get_session(f"http://test{i}.com")
        await pool.close_all()
        del pool

    # Проверяем, что пулы корректно удаляются (нет утечек)
    # (Упрощенная проверка - в реальности нужны более сложные инструменты)
    gc.collect()
    final_size = len(
        [obj for obj in gc.get_objects() if isinstance(obj, ConnectionPool)]
    )
    # Глобальный пул остается
    assert final_size <= initial_size + 1
