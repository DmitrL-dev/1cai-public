
"""Admin endpoints for managing user roles and permissions."""

from __future__ import annotations

from typing import Dict, Optional

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, Field

from src.security import (
    CurrentUser,
    get_audit_logger,
    grant_permission,
    grant_role,
    require_roles,
    revoke_permission,
    revoke_role,
)

router = APIRouter(prefix="/admin/users", tags=["admin", "roles"])
audit_logger = get_audit_logger()


class RoleRequest(BaseModel):
    role: str = Field(..., min_length=2, max_length=64)
    reason: Optional[str] = Field(default=None, max_length=255)
    metadata: Optional[Dict[str, str]] = None


class PermissionRequest(BaseModel):
    permission: str = Field(..., min_length=2, max_length=128)
    reason: Optional[str] = Field(default=None, max_length=255)
    metadata: Optional[Dict[str, str]] = None


@router.post("/{user_id}/roles", status_code=status.HTTP_204_NO_CONTENT)
async def grant_role_endpoint(
    user_id: str,
    payload: RoleRequest,
    current_user: CurrentUser = Depends(require_roles("admin")),
) -> Response:
    await grant_role(
        user_id,
        payload.role,
        assigned_by=current_user.user_id,
        reason=payload.reason,
        metadata=payload.metadata,
    )
    audit_logger.log_action(
        actor=current_user.user_id,
        action="admin.role.grant",
        target=user_id,
        metadata={"role": payload.role, "reason": payload.reason},
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{user_id}/roles/{role}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_role_endpoint(
    user_id: str,
    role: str,
    current_user: CurrentUser = Depends(require_roles("admin")),
) -> Response:
    await revoke_role(
        user_id,
        role,
        revoked_by=current_user.user_id,
    )
    audit_logger.log_action(
        actor=current_user.user_id,
        action="admin.role.revoke",
        target=user_id,
        metadata={"role": role},
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{user_id}/permissions", status_code=status.HTTP_204_NO_CONTENT)
async def grant_permission_endpoint(
    user_id: str,
    payload: PermissionRequest,
    current_user: CurrentUser = Depends(require_roles("admin")),
) -> Response:
    await grant_permission(
        user_id,
        payload.permission,
        assigned_by=current_user.user_id,
        metadata=payload.metadata,
    )
    audit_logger.log_action(
        actor=current_user.user_id,
        action="admin.permission.grant",
        target=user_id,
        metadata={"permission": payload.permission, "reason": payload.reason},
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/{user_id}/permissions/{permission}", status_code=status.HTTP_204_NO_CONTENT
)
async def revoke_permission_endpoint(
    user_id: str,
    permission: str,
    current_user: CurrentUser = Depends(require_roles("admin")),
) -> Response:
    await revoke_permission(user_id, permission)
    audit_logger.log_action(
        actor=current_user.user_id,
        action="admin.permission.revoke",
        target=user_id,
        metadata={"permission": permission},
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
