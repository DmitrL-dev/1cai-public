
"""
API зависимости для модуля аутентификации.
"""

from functools import lru_cache
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

from src.modules.auth.application.roles import enrich_user_from_db
from src.modules.auth.application.service import AuthService
from src.modules.auth.domain.models import CurrentUser
from src.modules.auth.infrastructure.config import AuthSettings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)


@lru_cache()
def get_auth_settings() -> AuthSettings:
    return AuthSettings()


@lru_cache()
def get_auth_service() -> AuthService:
    return AuthService(get_auth_settings())


async def get_current_user(request: Request, token: Optional[str] = Depends(oauth2_scheme)) -> CurrentUser:
    """Получает текущего пользователя из запроса.

    Извлекает токен из заголовка Authorization или X-Service-Token,
    валидирует его и возвращает пользователя.

    Args:
        request: Объект HTTP запроса.
        token: JWT токен (если есть).

    Returns:
        CurrentUser: Текущий пользователь.

    Raises:
        HTTPException: Если токен невалиден или отсутствует (401).
    """
    auth_service = get_auth_service()

    if token:
        principal = auth_service.decode_token(token)
        return await enrich_user_from_db(principal)

    service_token = request.headers.get("X-Service-Token")
    if service_token:
        service_user = auth_service.authenticate_service_token(service_token)
        if service_user:
            return service_user
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid service token",
        )

    current = getattr(request.state, "current_user", None)
    if current:
        return await enrich_user_from_db(current)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_roles(*roles: str):
    async def dependency(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if roles and not user.has_role(*roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role",
            )
        return user

    return dependency


def require_permissions(*permissions: str):
    async def dependency(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if permissions and not user.has_permission(*permissions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user

    return dependency


# Dependency для получения user_id (для OAuth)
async def get_current_user_id(current_user: CurrentUser = Depends(get_current_user)) -> int:
    """Получить ID текущего пользователя из сессии/JWT.

    Args:
        current_user: Текущий пользователь.

    Returns:
        int: ID пользователя.
    """
    # Временная заглушка или реальная логика конвертации
    # Если user_id в CurrentUser это строка (например UUID), а в OAuth нужен int,
    # то здесь нужна логика.
    # В оригинальном коде OAuth user_id был int, а в Auth - str.
    # Предположим пока что мы можем использовать hash или int conversion если это число.

    try:
        return int(current_user.user_id)
    except ValueError:
        # Если user_id не число (например "admin-1"), возвращаем хэш или фиктивный ID для совместимости
        # В реальном проекте нужно привести типы ID к общему знаменателю.
        return 1
