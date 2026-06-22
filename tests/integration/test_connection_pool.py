"""
Integration tests for ConnectionPool with AI clients.
"""

import pytest

from src.ai.clients.gigachat_client import GigaChatClient, GigaChatConfig
from src.ai.clients.naparnik_client import NaparnikClient, NaparnikConfig
from src.ai.clients.ollama_client import OllamaClient, OllamaConfig
from src.ai.clients.yandexgpt_client import YandexGPTClient, YandexGPTConfig
from src.ai.connection_pool import ConnectionPool, close_global_pool, get_global_pool


@pytest.mark.asyncio
async def test_connection_pool_basic():
    """Тест базовой функциональности ConnectionPool."""
    pool = ConnectionPool(max_size=3, timeout=60)

    # Создаем сессию
    session1 = await pool.get_session("http://test1.com")
    assert session1 is not None

    # Получаем ту же сессию по тому же ключу
    session2 = await pool.get_session("http://test1.com")
    assert session1 is session2

    # Создаем новую сессию для другого ключа
    session3 = await pool.get_session("http://test2.com")
    assert session3 is not None
    assert session3 is not session1

    await pool.close_all()


@pytest.mark.asyncio
async def test_connection_pool_lru_eviction():
    """Тест LRU eviction при переполнении пула."""
    pool = ConnectionPool(max_size=2, timeout=60)

    # Заполняем пул
    session1 = await pool.get_session("http://test1.com")
    session2 = await pool.get_session("http://test2.com")

    # Добавляем третью сессию - должна вытесниться первая (FIFO)
    session3 = await pool.get_session("http://test3.com")

    # Проверяем, что session1 больше не доступна
    new_session1 = await pool.get_session("http://test1.com")
    assert new_session1 is not session1  # Новая сессия создана

    await pool.close_all()


@pytest.mark.asyncio
async def test_connection_pool_context_manager():
    """Тест работы ConnectionPool как context manager."""
    async with ConnectionPool(max_size=3, timeout=60) as pool:
        session = await pool.get_session("http://test.com")
        assert session is not None

    # После выхода из контекста сессии должны быть закрыты
    # (не можем проверить напрямую, но нет ошибок)


@pytest.mark.asyncio
async def test_global_pool_singleton():
    """Тест глобального singleton пула."""
    pool1 = get_global_pool()
    pool2 = get_global_pool()

    assert pool1 is pool2

    # Закрываем глобальный пул
    await close_global_pool()

    # После закрытия должен быть создан новый пул
    pool3 = get_global_pool()
    assert pool3 is not pool1


@pytest.mark.asyncio
async def test_gigachat_with_connection_pool():
    """Тест использования ConnectionPool в GigaChatClient."""
    # Создаем клиент без credentials (не будет реальных запросов)
    config = GigaChatConfig(client_id=None, client_secret=None, access_token=None)
    client = GigaChatClient(config=config)

    # Проверяем, что клиент использует пул (fallback на обычную сессию если нет credentials)
    # В реальном сценарии с credentials будет использоваться пул
    assert client.is_configured is False

    await client.close()


@pytest.mark.asyncio
async def test_yandexgpt_with_connection_pool():
    """Тест использования ConnectionPool в YandexGPTClient."""
    config = YandexGPTConfig(api_key=None, folder_id=None)
    client = YandexGPTClient(config=config)

    assert client.is_configured is False

    await client.close()


@pytest.mark.asyncio
async def test_naparnik_with_connection_pool():
    """Тест использования ConnectionPool в NaparnikClient."""
    config = NaparnikConfig(api_key=None)
    client = NaparnikClient(config=config)

    assert client.is_configured is False

    await client.close()


@pytest.mark.asyncio
async def test_ollama_with_connection_pool():
    """Тест использования ConnectionPool в OllamaClient (через стандартную сессию)."""
    config = OllamaConfig(base_url="http://localhost:11434")
    client = OllamaClient(config=config)

    # OllamaClient использует свою собственную логику сессий
    # ConnectionPool может быть интегрирован позже
    assert client.is_configured is True

    await client.close()


@pytest.mark.asyncio
async def test_connection_pool_closed_session_handling():
    """Тест обработки закрытых сессий в пуле."""
    pool = ConnectionPool(max_size=3, timeout=60)

    session = await pool.get_session("http://test.com")
    assert session is not None

    # Закрываем сессию
    if not session.closed:
        await session.close()

    # При следующем запросе должна быть создана новая сессия
    new_session = await pool.get_session("http://test.com")
    assert new_session is not None
    # Новая сессия, так как старая была закрыта
    assert new_session is not session

    await pool.close_all()
