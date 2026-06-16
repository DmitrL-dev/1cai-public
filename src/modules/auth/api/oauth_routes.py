
"""
OAuth API Routes для 1C AI Stack
"""

import logging
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException

from src.database import get_db_pool as get_pool
from src.modules.auth.api.dependencies import get_current_user_id
from src.modules.auth.api.schemas import (
    OAuthAuthorizeResponse,
    OAuthCallbackRequest,
    OAuthCallbackResponse,
    OAuthDisconnectResponse,
    OAuthStatusResponse,
)
from src.modules.auth.application.oauth_service import OAuthService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/oauth", tags=["OAuth"])
oauth_service = OAuthService()


@router.post("/{provider}/authorize", response_model=OAuthAuthorizeResponse)
async def authorize_oauth(provider: str, user_id: int = Depends(get_current_user_id)) -> OAuthAuthorizeResponse:
    """Инициирует процесс OAuth авторизации.

    Генерирует URL для перенаправления пользователя на страницу провайдера.

    Args:
        provider: Имя провайдера (google, github, yandex).
        user_id: ID текущего пользователя.

    Returns:
        OAuthAuthorizeResponse: URL авторизации.

    Raises:
        HTTPException: Если провайдер не найден или ошибка генерации URL.
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            auth_url = await oauth_service.get_authorization_url(provider=provider, db=conn, user_id=user_id)

        logger.info(
            f"OAuth authorization initiated for provider={provider}, user_id={user_id}")

        return OAuthAuthorizeResponse(authorization_url=auth_url, provider=provider)

    except ValueError as e:
        logger.error("Invalid provider: %s", e)
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error("Failed to generate OAuth URL: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{provider}/callback", response_model=OAuthCallbackResponse)
async def oauth_callback(provider: str, request: OAuthCallbackRequest) -> OAuthCallbackResponse:
    """Обрабатывает OAuth callback от провайдера.

    Обменивает код авторизации на токен доступа.

    Args:
        provider: Имя провайдера.
        request: Данные callback (code, state).

    Returns:
        OAuthCallbackResponse: Результат авторизации.

    Raises:
        HTTPException: Если код невалиден или ошибка обмена.
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            result = await oauth_service.exchange_code_for_token(
                provider=provider, code=request.code, state=request.state, db=conn
            )

        logger.info(
            f"OAuth callback successful for provider={provider}, user_id={result['user_id']}")

        return OAuthCallbackResponse(
            status="success", provider=result["provider"], user_id=result["user_id"], expires_in=result["expires_in"]
        )

    except ValueError as e:
        logger.error("Invalid OAuth callback: %s", e)
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error("OAuth callback failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to exchange code for token")


@router.get("/{provider}/status", response_model=OAuthStatusResponse)
async def get_oauth_status(provider: str, user_id: int = Depends(get_current_user_id)) -> OAuthStatusResponse:
    """Проверяет статус подключения OAuth провайдера.

    Args:
        provider: Имя провайдера.
        user_id: ID пользователя.

    Returns:
        OAuthStatusResponse: Статус подключения и время истечения токена.
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            # Попробовать получить токен
            token_data = await oauth_service._get_token_data(conn, provider, user_id)

        if token_data:
            return OAuthStatusResponse(
                connected=True, provider=provider, expires_at=token_data["expires_at"].isoformat()
            )
        else:
            return OAuthStatusResponse(connected=False, provider=provider)

    except Exception as e:
        logger.error("Failed to check OAuth status: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{provider}/disconnect", response_model=OAuthDisconnectResponse)
async def disconnect_oauth(provider: str, user_id: int = Depends(get_current_user_id)) -> OAuthDisconnectResponse:
    """Отключает OAuth провайдера (удаляет токен).

    Args:
        provider: Имя провайдера.
        user_id: ID пользователя.

    Returns:
        OAuthDisconnectResponse: Статус операции.
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await oauth_service.disconnect(provider=provider, user_id=user_id, db=conn)

        logger.info("OAuth disconnected for provider=%s, user_id={user_id}", provider)

        return OAuthDisconnectResponse(status="success", provider=provider)

    except Exception as e:
        logger.error("Failed to disconnect OAuth: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/providers")
async def list_providers() -> Dict:
    """Возвращает список поддерживаемых OAuth провайдеров.

    Returns:
        Dict: Конфигурация провайдеров (имя, настроен ли, scopes).
    """
    providers = {}
    for name, config in oauth_service.providers.items():
        providers[name] = {
            "name": config["name"],
            "configured": bool(config["client_id"] and config["client_secret"]),
            "scopes": config["scope"],
        }

    return {"providers": providers}
