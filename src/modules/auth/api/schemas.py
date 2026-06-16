
"""
API схемы для модуля аутентификации.
"""

from typing import Optional

from pydantic import BaseModel


class TokenResponse(BaseModel):
    """Схема ответа с токеном."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int


class OAuthCallbackRequest(BaseModel):
    """Модель запроса для OAuth callback."""

    code: str
    state: str


class OAuthAuthorizeResponse(BaseModel):
    """Модель ответа для эндпоинта авторизации."""

    authorization_url: str
    provider: str


class OAuthCallbackResponse(BaseModel):
    """Модель ответа для callback эндпоинта."""

    status: str
    provider: str
    user_id: int
    expires_in: int


class OAuthStatusResponse(BaseModel):
    """Модель ответа для статуса подключения."""

    connected: bool
    provider: str
    expires_at: Optional[str] = None


class OAuthDisconnectResponse(BaseModel):
    """Модель ответа для отключения провайдера."""

    status: str
    provider: str
