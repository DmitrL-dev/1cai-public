import asyncpg
from typing import Any, Dict
from fastapi import APIRouter, Depends

from src.modules.admin_dashboard.services.admin_service import AdminDashboardService

router = APIRouter(tags=["Admin Dashboard"])


def get_db_pool() -> asyncpg.Pool:
    from src.database import get_pool

    return get_pool()


def get_admin_service(db_pool: asyncpg.Pool = Depends(get_db_pool)) -> AdminDashboardService:
    return AdminDashboardService(db_pool)


@router.get("/stats")
async def get_platform_stats(service: AdminDashboardService = Depends(get_admin_service)) -> Dict[str, Any]:
    """Получает глобальную статистику платформы.

    Returns:
        Dict[str, Any]: Словарь со статистикой (тенанты, пользователи, выручка).
    """
    return await service.get_platform_stats()


@router.get("/tenants/{tenant_id}")
async def get_tenant_details(tenant_id: str, service: AdminDashboardService = Depends(get_admin_service)) -> Dict[str, Any]:
    """Получает детальную информацию о тенанте.

    Args:
        tenant_id: ID тенанта.
        service: Сервис админ-панели.

    Returns:
        Dict[str, Any]: Детали тенанта, пользователи, история использования.
    """
    return await service.get_tenant_details(tenant_id)
