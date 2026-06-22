"""Вспомогательные функции для управления ролями и правами пользователей."""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, Optional

if TYPE_CHECKING:  # pragma: no cover
    from src.modules.auth.domain.models import CurrentUser


async def enrich_user_from_db(user: "CurrentUser") -> "CurrentUser":
    """Обогащает объект пользователя ролями и правами из БД.

    Args:
        user: Объект пользователя (CurrentUser).

    Returns:
        CurrentUser: Обновленный объект пользователя с загруженными ролями.
    """
    try:
        from src.database import get_pool

        pool = get_pool()
    except Exception:  # noqa: BLE001
        return user

    async with pool.acquire() as conn:
        rows_roles = await conn.fetch(
            "SELECT role FROM user_roles WHERE user_id = $1",
            user.user_id,
        )
        rows_permissions = await conn.fetch(
            "SELECT permission FROM user_permissions WHERE user_id = $1",
            user.user_id,
        )

    def _merge(original: Iterable[str], new_values: Iterable[str]) -> list[str]:
        merged = list(original)
        for value in new_values:
            if value not in merged:
                merged.append(value)
        return merged

    user.roles = _merge(user.roles, [row["role"] for row in rows_roles])
    user.permissions = _merge(
        user.permissions, [row["permission"] for row in rows_permissions]
    )
    return user


async def grant_role(
    user_id: str,
    role: str,
    assigned_by: Optional[str] = None,
    reason: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> None:
    """Назначает роль пользователю.

    Args:
        user_id: ID пользователя.
        role: Название роли.
        assigned_by: Кто назначил роль (опционально).
        reason: Причина назначения (опционально).
        metadata: Дополнительные данные (опционально).

    Raises:
        RuntimeError: Если пул БД не инициализирован.
    """
    try:
        from src.database import get_pool

        pool = get_pool()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("Database pool not initialised") from exc

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO user_roles (user_id, role, assigned_by)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id, role) DO NOTHING
            """,
            user_id,
            role,
            assigned_by,
        )
        await conn.execute(
            """
            INSERT INTO user_role_assignments (current_role, previous_role, assigned_by, assigned_user_id, reason, metadata)
            VALUES ($1, NULL, $2, $3, $4, $5)
            """,
            role,
            assigned_by or "system",
            user_id,
            reason,
            metadata or {},
        )


async def revoke_role(
    user_id: str,
    role: str,
    revoked_by: Optional[str] = None,
    reason: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> None:
    """Отызвает роль у пользователя.

    Args:
        user_id: ID пользователя.
        role: Название роли.
        revoked_by: Кто отозвал роль (опционально).
        reason: Причина отзывания (опционально).
        metadata: Дополнительные данные (опционально).

    Raises:
        RuntimeError: Если пул БД не инициализирован.
    """
    try:
        from src.database import get_pool

        pool = get_pool()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("Database pool not initialised") from exc

    async with pool.acquire() as conn:
        deleted = await conn.execute(
            "DELETE FROM user_roles WHERE user_id = $1 AND role = $2",
            user_id,
            role,
        )
        if deleted:
            await conn.execute(
                """
                INSERT INTO user_role_assignments (current_role, previous_role, assigned_by, assigned_user_id, reason, metadata)
                VALUES (NULL, $1, $2, $3, $4, $5)
                """,
                role,
                revoked_by or "system",
                user_id,
                reason,
                metadata or {},
            )


async def grant_permission(
    user_id: str, permission: str, assigned_by: Optional[str] = None
) -> None:
    """Назначает отдельное право (permission) пользователю.

    Args:
        user_id: ID пользователя.
        permission: Название права.
        assigned_by: Кто назначил (опционально).

    Raises:
        RuntimeError: Если пул БД не инициализирован.
    """
    try:
        from src.database import get_pool

        pool = get_pool()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("Database pool not initialised") from exc

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO user_permissions (user_id, permission, assigned_by)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id, permission) DO NOTHING
            """,
            user_id,
            permission,
            assigned_by,
        )


async def revoke_permission(user_id: str, permission: str) -> None:
    """Отызвает право у пользователя.

    Args:
        user_id: ID пользователя.
        permission: Название права.

    Raises:
        RuntimeError: Если пул БД не инициализирован.
    """
    try:
        from src.database import get_pool

        pool = get_pool()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("Database pool not initialised") from exc

    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM user_permissions WHERE user_id = $1 AND permission = $2",
            user_id,
            permission,
        )
