"""API маршруты для аутентификации."""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from src.modules.auth.api.dependencies import get_auth_service, get_current_user
from src.modules.auth.api.schemas import TokenResponse
from src.modules.auth.application.service import AuthService
from src.modules.auth.domain.models import CurrentUser

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/token", response_model=TokenResponse)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    """Получение токена доступа (Login).

    Аутентифицирует пользователя по username/password и выдает JWT токен.

    Args:
        form_data: Данные формы (username, password).
        auth_service: Сервис аутентификации.

    Returns:
        TokenResponse: Объект с access token и временем жизни.

    Raises:
        HTTPException: Если неверные учетные данные (401).
    """
    user = auth_service.authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    expires_delta = timedelta(minutes=auth_service.settings.access_token_expire_minutes)
    access_token = auth_service.create_access_token(user, expires_delta=expires_delta)
    return TokenResponse(
        access_token=access_token, expires_in=int(expires_delta.total_seconds())
    )


@router.get("/me", response_model=CurrentUser)
async def read_users_me(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """Получение текущего пользователя.

    Возвращает информацию о текущем аутентифицированном пользователе.

    Args:
        current_user: Текущий пользователь (извлечен из токена).

    Returns:
        CurrentUser: Модель текущего пользователя.
    """
    return current_user
