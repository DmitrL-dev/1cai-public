"""
Unit tests for ConnectionPool edge cases.
"""

import asyncio

import pytest

from src.ai.connection_pool import ConnectionPool


@pytest.mark.asyncio
async def test_connection_pool_concurrent_access_same_key():
    """Тест конкурентного доступа к одному и тому же ключу."""
    pool = ConnectionPool(max_size=5, timeout=60)

    async def get_session_concurrent():
        session = await pool.get_session("http://test.com")
        await asyncio.sleep(0.001)  # Небольшая задержка
        return session

    # Конкурентный доступ к одному ключу
    tasks = [get_session_concurrent() for _ in range(10)]
    sessions = await asyncio.gather(*tasks)

    # Все должны получить одну и ту же сессию
    first_session = sessions[0]
    assert all(
        s is first_session for s in sessions
    ), "All concurrent requests should get the same session"

    await pool.close_all()


@pytest.mark.asyncio
async def test_connection_pool_handles_closed_session_gracefully():
    """Тест graceful обработки закрытых сессий."""
    pool = ConnectionPool(max_size=3, timeout=60)

    # Создаем сессию
    session1 = await pool.get_session("http://test1.com")
    assert session1 is not None

    # Закрываем сессию напрямую
    if not session1.closed:
        await session1.close()

    # При следующем запросе должна быть создана новая сессия
    session2 = await pool.get_session("http://test1.com")
    assert session2 is not None
    assert session2 is not session1  # Новая сессия

    await pool.close_all()


@pytest.mark.asyncio
async def test_connection_pool_eviction_under_load():
    """Тест eviction при высокой нагрузке."""
    pool = ConnectionPool(max_size=3, timeout=60)

    # Создаем сессии для заполнения пула
    sessions = []
    for i in range(3):
        session = await pool.get_session(f"http://test{i}.com")
        sessions.append(session)

    # Добавляем новую сессию - должна вытесниться самая старая
    new_session = await pool.get_session("http://test3.com")

    # Проверяем, что старая сессия больше не в пуле
    old_session = await pool.get_session("http://test0.com")
    assert old_session is not sessions[0]  # Новая сессия

    await pool.close_all()


@pytest.mark.asyncio
async def test_connection_pool_close_session():
    """Тест явного закрытия сессии по ключу."""
    pool = ConnectionPool(max_size=5, timeout=60)

    session = await pool.get_session("http://test.com")
    assert session is not None

    # Закрываем сессию
    await pool.close_session("http://test.com")

    # При следующем запросе должна быть создана новая сессия
    new_session = await pool.get_session("http://test.com")
    assert new_session is not session
    assert new_session is not None

    await pool.close_all()


@pytest.mark.asyncio
async def test_connection_pool_acquire_context_manager():
    """Тест использования acquire как context manager."""
    pool = ConnectionPool(max_size=3, timeout=60)

    async with pool.acquire("http://test.com") as session:
        assert session is not None
        assert not session.closed

    # После выхода из контекста сессия должна остаться в пуле
    session2 = await pool.get_session("http://test.com")
    assert session2 is not None

    await pool.close_all()


@pytest.mark.asyncio
async def test_connection_pool_max_size_zero():
    """Тест поведения при max_size=0 (должен обработать корректно)."""
    pool = ConnectionPool(max_size=0, timeout=60)

    # Должен создать сессию даже при max_size=0
    session = await pool.get_session("http://test.com")
    assert session is not None

    await pool.close_all()


@pytest.mark.asyncio
async def test_connection_pool_empty_key():
    """Тест обработки пустого ключа."""
    pool = ConnectionPool(max_size=5, timeout=60)

    session = await pool.get_session("")
    assert session is not None

    # Пустой ключ должен работать (хотя это edge case)
    session2 = await pool.get_session("")
    assert session2 is session  # Та же сессия для пустого ключа

    await pool.close_all()
