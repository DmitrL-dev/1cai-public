"""
Marketplace API Routes
----------------------

This module defines the API endpoints for the 1C AI Marketplace.
It handles:
- Listing available AI plugins/agents.
- Searching for plugins.
- Installing and uninstalling plugins.
- Managing user subscriptions and usage.
- Publishing new plugins (for developers).
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from starlette.requests import Request

from src.middleware.rate_limiter import limiter
from src.modules.marketplace.domain.models import (
    PluginCategory,
    PluginResponse,
    PluginReviewRequest,
    PluginReviewResponse,
    PluginSearchResponse,
    PluginStatsResponse,
    PluginSubmitRequest,
    PluginUpdateRequest,
)
from src.security import CurrentUser, get_current_user, require_roles

if TYPE_CHECKING:
    from src.db.marketplace_repository import MarketplaceRepository
    from src.modules.marketplace.services.marketplace_service import MarketplaceService

router = APIRouter(prefix="/marketplace", tags=["marketplace"])


def get_marketplace_repository(request: Request) -> "MarketplaceRepository":
    """Получает репозиторий маркетплейса из состояния приложения.

    Args:
        request: HTTP запрос, содержащий состояние приложения (app.state).

    Returns:
        MarketplaceRepository: Инициализированный репозиторий маркетплейса.

    Raises:
        RuntimeError: Если репозиторий не инициализирован в app.state.
    """
    # Lazy import

    repo = getattr(request.app.state, "marketplace_repo", None)
    if repo is None:
        raise RuntimeError("Marketplace repository is not initialized")
    return repo


def get_marketplace_service(
    repo: "MarketplaceRepository" = Depends(get_marketplace_repository),
) -> "MarketplaceService":
    """Получает сервис бизнес-логики маркетплейса.

    Args:
        repo: Репозиторий маркетплейса (внедряется через Depends).

    Returns:
        MarketplaceService: Инициализированный сервис.
    """
    # Lazy import
    from src.modules.marketplace.services.marketplace_service import MarketplaceService

    return MarketplaceService(repo)


@router.post(
    "/plugins",
    response_model=PluginResponse,
    status_code=201,
    summary="Submit a new plugin",
)
@limiter.limit("5/minute")
async def submit_plugin(
    request: Request,
    response: Response,
    plugin: PluginSubmitRequest,
    current_user: CurrentUser = Depends(require_roles("developer", "admin")),
    service: "MarketplaceService" = Depends(get_marketplace_service),
) -> PluginResponse:
    """Публикует новый плагин в маркетплейсе.

    Требует наличия роли 'developer' или 'admin'.

    Args:
        request: HTTP запрос.
        response: HTTP ответ.
        plugin: Данные публикуемого плагина.
        current_user: Текущий аутентифицированный пользователь.
        service: Сервис маркетплейса.

    Returns:
        PluginResponse: Созданный плагин с присвоенным ID.

    Raises:
        HTTPException(400): Если данные некорректны или плагин уже существует.
    """
    try:
        persisted = await service.submit_plugin(plugin.model_dump(), current_user)
        return PluginResponse(**persisted)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/plugins",
    response_model=PluginSearchResponse,
    summary="Search plugins",
)
async def search_plugins(
    query: Optional[str] = Query(None, description="Search query"),
    category: Optional[PluginCategory] = Query(None, description="Filter by category"),
    author: Optional[str] = Query(None, description="Filter by author username"),
    sort_by: str = Query("rating", description="Sort field"),
    order: str = Query("desc", description="Sort order"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Results per page"),
    service: "MarketplaceService" = Depends(get_marketplace_service),
) -> PluginSearchResponse:
    """Поиск плагинов по критериям.

    Args:
        query: Поисковая строка (название, описание, теги).
        category: Фильтр по категории плагина.
        author: Фильтр по имени автора.
        sort_by: Поле для сортировки ('rating', 'downloads', 'created_at', 'name').
        order: Порядок сортировки ('asc', 'desc').
        page: Номер страницы (начиная с 1).
        page_size: Количество элементов на странице.
        service: Сервис маркетплейса.

    Returns:
        PluginSearchResponse: Результаты поиска с пагинацией.
    """
    try:
        plugins, total = await service.search_plugins(
            query=query,
            category=category.value if category else None,
            author=author,
            sort_by=sort_by,
            order=order,
            page=page,
            page_size=page_size,
        )

        total_pages = (total + page_size - 1) // page_size if page_size else 1

        return PluginSearchResponse(
            plugins=[PluginResponse(**p) for p in plugins],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/plugins/{plugin_id}", response_model=PluginResponse)
async def get_plugin(
    plugin_id: str,
    service: "MarketplaceService" = Depends(get_marketplace_service),
) -> PluginResponse:
    """Получает детальную информацию о плагине по его ID.

    Args:
        plugin_id: Уникальный идентификатор плагина.
        service: Сервис маркетплейса.

    Returns:
        PluginResponse: Объект плагина.

    Raises:
        HTTPException(404): Если плагин не найден.
    """
    plugin = await service.get_plugin(plugin_id)
    if not plugin:
        raise HTTPException(status_code=404, detail="Plugin not found")
    return PluginResponse(**plugin)


@router.put("/plugins/{plugin_id}", response_model=PluginResponse)
async def update_plugin(
    plugin_id: str,
    update: PluginUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: "MarketplaceService" = Depends(get_marketplace_service),
) -> PluginResponse:
    """Обновляет информацию о плагине.

    Разрешено только автору плагина или администратору.

    Args:
        plugin_id: Уникальный идентификатор плагина.
        update: Данные для обновления (частичное обновление).
        current_user: Текущий пользователь.
        service: Сервис маркетплейса.

    Returns:
        PluginResponse: Обновленный объект плагина.

    Raises:
        HTTPException(404): Если плагин не найден.
        HTTPException(403): Если у пользователя нет прав на редактирование.
    """
    try:
        updated = await service.update_plugin(
            plugin_id, update.model_dump(exclude_unset=True), current_user
        )
        if not updated:
            raise HTTPException(status_code=404, detail="Plugin not found")
        return PluginResponse(**updated)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/plugins/{plugin_id}/artifact", response_model=PluginResponse, status_code=201
)
@limiter.limit("10/minute")
async def upload_plugin_artifact(
    request: Request,
    response: Response,
    plugin_id: str,
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user),
    service: "MarketplaceService" = Depends(get_marketplace_service),
) -> PluginResponse:
    """Загружает файл артефакта (дистрибутив) для плагина.

    Args:
        request: HTTP запрос.
        response: HTTP ответ.
        plugin_id: Уникальный идентификатор плагина.
        file: Загружаемый файл.
        current_user: Текущий пользователь (должен быть автором).
        service: Сервис маркетплейса.

    Returns:
        PluginResponse: Обновленный плагин с информацией о файле.

    Raises:
        HTTPException(403): Нет прав.
        HTTPException(400): Ошибка валидации файла.
        HTTPException(503): Ошибка хранилища.
    """
    try:
        updated = await service.upload_artifact(plugin_id, file, current_user)
        return PluginResponse(**updated)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to store artifact")


@router.delete("/plugins/{plugin_id}")
async def delete_plugin(
    plugin_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    service: "MarketplaceService" = Depends(get_marketplace_service),
) -> Dict[str, Any]:
    """Удаляет плагин.

    Args:
        plugin_id: Уникальный идентификатор плагина.
        current_user: Текущий пользователь (автор или админ).
        service: Сервис маркетплейса.

    Returns:
        Dict[str, Any]: Статус операции.

    Raises:
        HTTPException(404): Плагин не найден.
        HTTPException(403): Нет прав.
    """
    try:
        removed = await service.delete_plugin(plugin_id, current_user)
        if not removed:
            raise HTTPException(status_code=404, detail="Plugin not found")
        return {"status": "removed", "plugin_id": plugin_id}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/plugins/{plugin_id}/install")
async def install_plugin(
    plugin_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    service: "MarketplaceService" = Depends(get_marketplace_service),
) -> Dict[str, Any]:
    """Регистрирует установку плагина пользователем.

    Args:
        plugin_id: Уникальный идентификатор плагина.
        current_user: Текущий пользователь.
        service: Сервис маркетплейса.

    Returns:
        Dict[str, Any]: Статус и ссылка на скачивание.
    """
    updated = await service.record_install(plugin_id, current_user.user_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Plugin not found")

    return {
        "status": "installed",
        "plugin_id": plugin_id,
        "download_url": updated["download_url"],
    }


@router.post("/plugins/{plugin_id}/uninstall")
async def uninstall_plugin(
    plugin_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    service: "MarketplaceService" = Depends(get_marketplace_service),
) -> Dict[str, Any]:
    """Регистрирует удаление плагина пользователем (отписку).

    Args:
        plugin_id: Уникальный идентификатор плагина.
        current_user: Текущий пользователь.
        service: Сервис маркетплейса.

    Returns:
        Dict[str, Any]: Статус операции.
    """
    updated = await service.remove_install(plugin_id, current_user.user_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Plugin not found")
    return {"status": "uninstalled", "plugin_id": plugin_id}


@router.get("/plugins/{plugin_id}/stats", response_model=PluginStatsResponse)
async def get_plugin_stats(
    plugin_id: str,
    service: "MarketplaceService" = Depends(get_marketplace_service),
) -> PluginStatsResponse:
    """Получает статистику по плагину (скачивания, просмотры, рейтинг).

    Args:
        plugin_id: Уникальный идентификатор плагина.
        service: Сервис маркетплейса.

    Returns:
        PluginStatsResponse: Объект статистики.
    """
    stats = await service.get_stats(plugin_id)
    if not stats:
        raise HTTPException(status_code=404, detail="Plugin not found")
    return PluginStatsResponse(**stats)


@router.post("/plugins/{plugin_id}/reviews", response_model=PluginReviewResponse)
async def submit_review(
    plugin_id: str,
    review: PluginReviewRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: "MarketplaceService" = Depends(get_marketplace_service),
) -> PluginReviewResponse:
    """Оставляет отзыв к плагину.

    Args:
        plugin_id: Уникальный идентификатор плагина.
        review: Данные отзыва (рейтинг, текст).
        current_user: Текущий пользователь.
        service: Сервис маркетплейса.

    Returns:
        PluginReviewResponse: Созданный отзыв.
    """
    try:
        stored = await service.create_review(
            plugin_id, review.model_dump(), current_user
        )
        return PluginReviewResponse(**stored)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.get("/plugins/{plugin_id}/reviews")
async def get_plugin_reviews(
    plugin_id: str,
    page: int = 1,
    page_size: int = 10,
    service: "MarketplaceService" = Depends(get_marketplace_service),
) -> Dict[str, Any]:
    """Получает список отзывов к плагину.

    Args:
        plugin_id: Уникальный идентификатор плагина.
        page: Номер страницы.
        page_size: Размер страницы.
        service: Сервис маркетплейса.

    Returns:
        Dict[str, Any]: Список отзывов и метаданные пагинации.
    """
    try:
        reviews, total = await service.list_reviews(plugin_id, page, page_size)
        return {
            "reviews": [PluginReviewResponse(**r) for r in reviews],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if page_size else 1,
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/plugins/{plugin_id}/download")
async def download_plugin(
    plugin_id: str,
    service: "MarketplaceService" = Depends(get_marketplace_service),
) -> Dict[str, Any]:
    """Получает ссылку на скачивание последней версии плагина.

    Args:
        plugin_id: Уникальный идентификатор плагина.
        service: Сервис маркетплейса.

    Returns:
        Dict[str, Any]: URL для скачивания и метаданные файла.
    """
    payload = await service.build_download_payload(plugin_id)
    if not payload:
        raise HTTPException(status_code=404, detail="Plugin not found")
    return payload


@router.get("/categories")
async def get_categories(
    service: "MarketplaceService" = Depends(get_marketplace_service),
) -> Dict[str, Any]:
    """Получает список всех категорий плагинов и количество плагинов в каждой.

    Args:
        service: Сервис маркетплейса.

    Returns:
        Dict[str, Any]: Список категорий со счетчиками.
    """
    category_counts = await service.get_category_counts()
    return {
        "categories": [
            {
                "id": cat.value,
                "name": cat.value.replace("_", " ").title(),
                "count": category_counts.get(cat.value, 0),
            }
            for cat in PluginCategory
        ]
    }


@router.get("/featured")
async def get_featured_plugins(
    limit: int = 6,
    service: "MarketplaceService" = Depends(get_marketplace_service),
) -> Dict[str, Any]:
    """Получает список рекомендованных (featured) плагинов.

    Args:
        limit: Максимальное количество возвращаемых плагинов.
        service: Сервис маркетплейса.

    Returns:
        Dict[str, Any]: Список плагинов.
    """
    featured = await service.get_featured(limit)
    return {"plugins": [PluginResponse(**p) for p in featured]}


@router.get("/trending")
async def get_trending_plugins(
    period: str = "week",
    limit: int = 10,
    service: "MarketplaceService" = Depends(get_marketplace_service),
) -> Dict[str, Any]:
    """Получает список популярных (trending) плагинов за период.

    Args:
        period: Период ('week', 'month', 'all').
        limit: Максимальное количество.
        service: Сервис маркетплейса.

    Returns:
        Dict[str, Any]: Список плагинов.
    """
    plugins = await service.get_trending(limit)
    return {
        "plugins": [PluginResponse(**p) for p in plugins],
        "period": period,
    }


@router.post("/plugins/{plugin_id}/favorite")
async def add_to_favorites(
    plugin_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    service: "MarketplaceService" = Depends(get_marketplace_service),
) -> Dict[str, Any]:
    """Добавляет плагин в избранное текущего пользователя.

    Args:
        plugin_id: Уникальный идентификатор плагина.
        current_user: Текущий пользователь.
        service: Сервис маркетплейса.

    Returns:
        Dict[str, Any]: Статус операции.
    """
    try:
        await service.add_favorite(plugin_id, current_user.user_id)
        return {"status": "added", "plugin_id": plugin_id}
    except Exception:
        raise HTTPException(status_code=404, detail="Plugin not found")


@router.delete("/plugins/{plugin_id}/favorite")
async def remove_from_favorites(
    plugin_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    service: "MarketplaceService" = Depends(get_marketplace_service),
) -> Dict[str, Any]:
    """Удаляет плагин из избранного.

    Args:
        plugin_id: Уникальный идентификатор плагина.
        current_user: Текущий пользователь.
        service: Сервис маркетплейса.

    Returns:
        Dict[str, Any]: Статус операции.
    """
    try:
        await service.remove_favorite(plugin_id, current_user.user_id)
        return {"status": "removed", "plugin_id": plugin_id}
    except Exception:
        raise HTTPException(status_code=404, detail="Plugin not found")


@router.post("/plugins/{plugin_id}/report")
async def report_plugin(
    plugin_id: str,
    reason: str,
    details: Optional[str] = None,
    current_user: CurrentUser = Depends(get_current_user),
    service: "MarketplaceService" = Depends(get_marketplace_service),
) -> Dict[str, Any]:
    """Отправляет жалобу на плагин.

    Args:
        plugin_id: Уникальный идентификатор плагина.
        reason: Причина жалобы.
        details: Дополнительные детали.
        current_user: Текущий пользователь.
        service: Сервис маркетплейса.

    Returns:
        Dict[str, Any]: Статус приема жалобы.
    """
    try:
        await service.report_plugin(plugin_id, reason, details, current_user)
        return {
            "status": "reported",
            "plugin_id": plugin_id,
            "message": "Thank you for your report. We will review it shortly.",
        }
    except Exception:
        raise HTTPException(status_code=404, detail="Plugin not found")


# ==================== Admin Endpoints ====================


@router.post("/admin/plugins/{plugin_id}/approve")
async def approve_plugin(
    plugin_id: str,
    current_user: CurrentUser = Depends(require_roles("admin", "moderator")),
    service: "MarketplaceService" = Depends(get_marketplace_service),
) -> Dict[str, Any]:
    """Одобряет плагин (публикация).

    Доступно только администраторам и модераторам.

    Args:
        plugin_id: Уникальный идентификатор плагина.
        current_user: Текущий пользователь (админ).
        service: Сервис маркетплейса.

    Returns:
        Dict[str, Any]: Статус операции.
    """
    try:
        await service.approve_plugin(plugin_id, current_user)
        return {"status": "approved", "plugin_id": plugin_id}
    except Exception:
        raise HTTPException(status_code=404, detail="Plugin not found")


@router.post("/admin/plugins/{plugin_id}/reject")
async def reject_plugin(
    plugin_id: str,
    reason: str,
    current_user: CurrentUser = Depends(require_roles("admin", "moderator")),
    service: "MarketplaceService" = Depends(get_marketplace_service),
) -> Dict[str, Any]:
    """Отклоняет плагин.

    Доступно только администраторам и модераторам.

    Args:
        plugin_id: Уникальный идентификатор плагина.
        reason: Причина отклонения.
        current_user: Текущий пользователь (админ).
        service: Сервис маркетплейса.

    Returns:
        Dict[str, Any]: Статус операции.
    """
    try:
        await service.reject_plugin(plugin_id, reason, current_user)
        return {"status": "rejected", "plugin_id": plugin_id, "reason": reason}
    except Exception:
        raise HTTPException(status_code=404, detail="Plugin not found")


@router.post("/admin/plugins/{plugin_id}/feature")
async def feature_plugin(
    plugin_id: str,
    featured: bool = True,
    current_user: CurrentUser = Depends(require_roles("admin", "moderator")),
    service: "MarketplaceService" = Depends(get_marketplace_service),
) -> Dict[str, Any]:
    """Устанавливает или снимает метку 'Featured' (Рекомендовано).

    Доступно только администраторам и модераторам.

    Args:
        plugin_id: Уникальный идентификатор плагина.
        featured: True для добавления в рекомендации, False для удаления.
        current_user: Текущий пользователь (админ).
        service: Сервис маркетплейса.

    Returns:
        Dict[str, Any]: Статус операции.
    """
    try:
        await service.set_featured(plugin_id, featured, current_user)
        return {"status": "updated", "plugin_id": plugin_id, "featured": featured}
    except Exception:
        raise HTTPException(status_code=404, detail="Plugin not found")


@router.post("/admin/plugins/{plugin_id}/verify")
async def verify_plugin(
    plugin_id: str,
    verified: bool = True,
    current_user: CurrentUser = Depends(require_roles("admin", "moderator")),
    service: "MarketplaceService" = Depends(get_marketplace_service),
) -> Dict[str, Any]:
    """Устанавливает или снимает метку 'Verified' (Проверено).

    Доступно только администраторам и модераторам.

    Args:
        plugin_id: Уникальный идентификатор плагина.
        verified: True для подтверждения проверки, False для снятия.
        current_user: Текущий пользователь (админ).
        service: Сервис маркетплейса.

    Returns:
        Dict[str, Any]: Статус операции.
    """
    try:
        await service.set_verified(plugin_id, verified, current_user)
        return {"status": "updated", "plugin_id": plugin_id, "verified": verified}
    except Exception:
        raise HTTPException(status_code=404, detail="Plugin not found")
