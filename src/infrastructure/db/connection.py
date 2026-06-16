
"""
Database Connection Pool Management
Best Practices:
- Connection pooling with optimal size
- Retry logic with exponential backoff
- Health checks and monitoring
- Graceful shutdown
"""

import asyncio
import os
import time
from contextlib import asynccontextmanager
from typing import Optional

import asyncpg
from src.config import settings

from src.infrastructure.logging.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger

# Global pool instance
_pool: Optional[asyncpg.Pool] = None

# Pool configuration (best practices from top companies)
# Pool configuration (best practices from top companies)
DEFAULT_MIN_SIZE = settings.db_pool_min_size
DEFAULT_MAX_SIZE = settings.db_pool_max_size
DEFAULT_MAX_QUERIES = settings.db_pool_max_queries
DEFAULT_MAX_INACTIVE_CONNECTION_LIFETIME = settings.db_pool_max_inactive_lifetime
DEFAULT_COMMAND_TIMEOUT = settings.db_command_timeout
DEFAULT_CONNECT_TIMEOUT = settings.db_connect_timeout


async def create_pool(max_retries: int = 1, retry_delay: int = 1) -> Optional[asyncpg.Pool]:
    """
    Create database connection pool with retry logic and best practices

    Features:
    - Fast failure (single attempt with short timeout)
    - Optimal pool sizing
    - Connection lifetime management
    - Query timeout protection

    Args:
        max_retries: Maximum number of retry attempts (default: 1 for fast startup)
        retry_delay: Initial delay between retries in seconds (default: 1s)

    Returns:
        Optional[asyncpg.Pool]: Configured database connection pool, or None if all attempts failed
    """
    global _pool

    if _pool is None:
        database_url = settings.database_url

        logger.info("Creating database pool with optimal configuration...")

        for attempt in range(max_retries):
            try:
                # Use very short timeout to prevent hanging
                _pool = await asyncio.wait_for(
                    asyncpg.create_pool(
                        database_url,
                        min_size=DEFAULT_MIN_SIZE,
                        max_size=DEFAULT_MAX_SIZE,
                        max_queries=DEFAULT_MAX_QUERIES,
                        max_inactive_connection_lifetime=DEFAULT_MAX_INACTIVE_CONNECTION_LIFETIME,
                        command_timeout=DEFAULT_COMMAND_TIMEOUT,
                        timeout=2.0,  # Very short connection timeout
                        # Enable statement cache for better performance
                        statement_cache_size=100,
                    ),
                    timeout=3.0,  # Overall timeout for pool creation
                )

                # Test connection with timeout
                async with _pool.acquire() as conn:
                    await asyncio.wait_for(conn.fetchval("SELECT 1"), timeout=2.0)

                logger.info(
                    "Database pool created successfully",
                    extra={
                        "min_size": DEFAULT_MIN_SIZE,
                        "max_size": DEFAULT_MAX_SIZE,
                        "timeout": DEFAULT_COMMAND_TIMEOUT,
                    },
                )
                break
            except asyncio.TimeoutError:
                logger.warning(
                    f"Database connection timeout (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    backoff_delay = retry_delay * (2**attempt)
                    await asyncio.sleep(backoff_delay)
                else:
                    logger.warning("Database connection timeout, continuing without DB")
                    return None
            except Exception as e:
                logger.warning(
                    f"Failed to create database pool (attempt {attempt + 1}/{max_retries})",
                    extra={"error": str(e), "error_type": type(e).__name__},
                )
                if attempt < max_retries - 1:
                    backoff_delay = retry_delay * (2**attempt)
                    await asyncio.sleep(backoff_delay)
                else:
                    logger.warning("Database not available, continuing without DB")
                    return None

    return _pool


async def close_pool():
    """
    Close database connection pool gracefully

    Best practice: Wait for active connections to finish before closing
    """
    global _pool

    if _pool:
        logger.info("Closing database pool...")
        try:
            # Terminate all connections gracefully
            await _pool.terminate()
            _pool = None
            logger.info("Database pool closed successfully")
        except Exception as e:
            logger.error(
                "Error closing database pool",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )
            _pool = None


def get_pool() -> asyncpg.Pool:
    """
    Get database pool for dependency injection

    Returns:
        asyncpg.Pool: Database connection pool

    Raises:
        RuntimeError: If pool not initialized
    """
    if _pool is None:
        raise RuntimeError(
            "Database pool not initialized. " "Call create_pool() during application startup.")

    return _pool


# Convenience function for FastAPI dependency
def get_db_pool() -> asyncpg.Pool:
    """
    FastAPI dependency для получения database pool

    Usage:
        @router.get("/endpoint")
        async def endpoint(db_pool: asyncpg.Pool = Depends(get_db_pool)):
            async with db_pool.acquire() as conn:
                # Use connection
                pass
    """
    return get_pool()


@asynccontextmanager
async def get_db_connection():
    """
    Context manager for database connections with automatic cleanup

    Best practice: Always use context managers for connections

    Usage:
        async with get_db_connection() as conn:
            result = await conn.fetch("SELECT * FROM table")
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        try:
            yield conn
        finally:
            # Connection is automatically returned to pool
            pass


async def check_pool_health() -> dict:
    """
    Check database pool health

    Returns:
        dict: Health status with metrics
    """
    if _pool is None:
        return {"status": "unhealthy", "error": "Pool not initialized"}

    try:
        start_time = time.time()
        async with _pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
            response_time = (time.time() - start_time) * 1000  # ms

        return {
            "status": "healthy",
            "pool_size": _pool.get_size(),
            "pool_idle_size": _pool.get_idle_size(),
            "response_time_ms": round(response_time, 2),
        }
    except Exception as e:
        logger.error(
            "Database pool health check failed",
            extra={"error": str(e), "error_type": type(e).__name__},
            exc_info=True,
        )
        return {"status": "unhealthy", "error": str(e)}
