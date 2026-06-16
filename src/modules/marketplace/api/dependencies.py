
"""
Marketplace API Dependencies
Версия: 2.1.0

FastAPI dependencies для Marketplace модуля
"""

from starlette.requests import Request

from src.infrastructure.repositories.marketplace import MarketplaceRepository


def get_marketplace_repository(request: Request) -> MarketplaceRepository:
    """
    Получение Marketplace Repository из app state

    Args:
        request: FastAPI Request объект

    Returns:
        MarketplaceRepository: Инициализированный репозиторий

    Raises:
        RuntimeError: Если репозиторий не инициализирован
    """
    repo = getattr(request.app.state, "marketplace_repo", None)
    if repo is None:
        raise RuntimeError("Marketplace repository is not initialized")
    return repo
