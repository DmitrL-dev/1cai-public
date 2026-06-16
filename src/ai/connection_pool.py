
"""
Connection Pool для AI Clients
-------------------------------

Пул соединений для переиспользования HTTP соединений между AI клиентами.
Улучшает производительность за счет переиспользования TCP соединений.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Dict, Optional

import aiohttp

logger = logging.getLogger(__name__)


class ConnectionPool:
    """
    Пул соединений для HTTP клиентов.

    Позволяет переиспользовать aiohttp.ClientSession между разными клиентами
    для улучшения производительности.
    """

    def __init__(self, max_size: int = 10, timeout: int = 60):
        """
        Инициализация пула соединений.

        Args:
            max_size: Максимальный размер пула
            timeout: Таймаут для соединений в секундах
        """
        self.max_size = max_size
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._sessions: Dict[str, aiohttp.ClientSession] = {}
        self._lock = asyncio.Lock()

    async def get_session(self, key: str) -> aiohttp.ClientSession:
        """
        Получить или создать HTTP сессию.

        Args:
            key: Ключ для идентификации сессии (например, URL провайдера)

        Returns:
            aiohttp.ClientSession
        """
        async with self._lock:
            if key not in self._sessions:
                # Если max_size > 0, проверяем переполнение
                if self.max_size > 0 and len(self._sessions) >= self.max_size:
                    # Закрываем старую сессию (FIFO)
                    oldest_key = next(iter(self._sessions))
                    old_session = self._sessions.pop(oldest_key)
                    if not old_session.closed:
                        try:
                            await old_session.close()
                        except Exception:
                            pass

                # Создаем новую сессию
                session = aiohttp.ClientSession(timeout=self.timeout)
                # Только если max_size > 0, добавляем в пул для переиспользования
                if self.max_size > 0:
                    self._sessions[key] = session
                    logger.debug(
                        "Created new session in pool",
                        extra={"key": key, "pool_size": len(self._sessions)},
                    )
                else:
                    # При max_size=0 не сохраняем в пул (каждая сессия новая)
                    logger.debug(
                        "Created new session (pool disabled, max_size=0)",
                        extra={"key": key},
                    )
                    return session

            session = self._sessions[key]
            # Проверяем, закрыта ли сессия
            if hasattr(session, "closed") and session.closed:
                # Пересоздаем закрытую сессию
                try:
                    await session.close()
                except Exception:
                    pass
                session = aiohttp.ClientSession(timeout=self.timeout)
                self._sessions[key] = session
                logger.debug("Recreated closed session in pool", extra={"key": key})

            return session

    @asynccontextmanager
    async def acquire(self, key: str):
        """
        Context manager для получения сессии из пула.

        Args:
            key: Ключ для идентификации сессии

        Yields:
            aiohttp.ClientSession
        """
        session = await self.get_session(key)
        try:
            yield session
        except Exception as e:
            logger.error(
                "Error in connection pool session",
                extra={"key": key, "error": str(e)},
                exc_info=True,
            )
            raise

    async def close_session(self, key: str) -> None:
        """
        Закрыть сессию по ключу.

        Args:
            key: Ключ сессии
        """
        async with self._lock:
            if key in self._sessions:
                session = self._sessions.pop(key)
                if not session.closed:
                    await session.close()
                logger.debug("Closed session in pool", extra={"key": key})

    async def close_all(self) -> None:
        """Закрыть все сессии в пуле."""
        async with self._lock:
            for key, session in self._sessions.items():
                if not session.closed:
                    await session.close()
            self._sessions.clear()
            logger.debug("Closed all sessions in pool")

    async def __aenter__(self):
        """Context manager вход."""
        return self

    async def __aexit__(self, exc_type, exc, tb):
        """Context manager выход."""
        await self.close_all()


# Глобальный пул соединений (singleton)
_global_pool: Optional[ConnectionPool] = None


def get_global_pool() -> ConnectionPool:
    """
    Получить глобальный пул соединений.

    Returns:
        ConnectionPool singleton
    """
    global _global_pool
    if _global_pool is None:
        _global_pool = ConnectionPool(max_size=10, timeout=60)
    return _global_pool


async def close_global_pool() -> None:
    """Закрыть глобальный пул соединений."""
    global _global_pool
    if _global_pool is not None:
        await _global_pool.close_all()
        _global_pool = None
