import asyncpg
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException

from src.modules.tenant_management.domain.models import TenantRegistrationRequest
from src.modules.tenant_management.services.tenant_service import (
    TenantManagementService,
)

router = APIRouter(tags=["Tenant Management"])


def get_db_pool() -> asyncpg.Pool:
    """DB pool dependency."""
    from src.database import get_pool

    return get_pool()


def get_tenant_service(
    db_pool: asyncpg.Pool = Depends(get_db_pool),
) -> TenantManagementService:
    return TenantManagementService(db_pool)


@router.post("/register")
async def register_tenant(
    registration: TenantRegistrationRequest,
    service: TenantManagementService = Depends(get_tenant_service),
) -> Dict[str, Any]:
    """Register new tenant."""
    try:
        result = await service.create_tenant(registration)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{tenant_id}/usage")
async def get_tenant_usage(tenant_id: str, service: TenantManagementService = Depends(get_tenant_service)) -> Dict[str, Any]:
    """Get tenant usage metrics."""
    usage = await service.get_tenant_usage(tenant_id)
    if not usage:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return usage
