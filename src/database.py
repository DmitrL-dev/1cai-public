"""Compatibility exports for legacy database imports.

New code should import from `src.infrastructure.db.connection` directly. This module keeps older
routes and tests importable while they are migrated.
"""

from src.infrastructure.db.connection import (
    check_pool_health,
    close_pool,
    create_pool,
    get_db_connection,
    get_db_pool,
    get_pool,
)

__all__ = [
    "check_pool_health",
    "close_pool",
    "create_pool",
    "get_db_connection",
    "get_db_pool",
    "get_pool",
]
