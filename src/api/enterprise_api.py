"""Enterprise readiness API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.middleware.jwt_user_context import principal_actor, require_auth, require_roles
from src.services.enterprise_iam import (
    check_project_access,
    enforce_project_access,
    iam_readiness,
    list_project_boundaries,
    load_iam_config,
    save_iam_config,
    upsert_project_boundary,
)

router = APIRouter(prefix="/api/v1/enterprise", tags=["Enterprise"])

# Roles permitted to mutate IAM config / tenant-project boundaries. Changing
# these controls who can access which tenant's data, so it is admin-only.
_IAM_ADMIN_ROLES = ("admin", "iam_admin", "security_admin")


class IAMConfigRequest(BaseModel):
    providers: list[dict[str, Any]] = Field(default_factory=list)
    boundaries: list[dict[str, Any]] = Field(default_factory=list)


class ProjectBoundaryRequest(BaseModel):
    project_id: str = Field(..., min_length=1, max_length=160)
    tenant_id: str = Field(..., min_length=1, max_length=160)
    name: str | None = Field(default=None, max_length=240)
    allowed_roles: list[str] = Field(default_factory=list)
    allowed_permissions: list[str] = Field(default_factory=list)
    data_roots: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AccessCheckRequest(BaseModel):
    project_id: str = Field(..., min_length=1, max_length=160)
    tenant_id: str = Field(..., min_length=1, max_length=160)
    action: str = Field(..., min_length=1, max_length=160)


@router.get("/iam/readiness")
def readiness() -> dict[str, Any]:
    """Return enterprise IAM readiness report."""

    return iam_readiness()


@router.get("/iam/config")
def config() -> dict[str, Any]:
    """Return enterprise IAM provider and boundary config."""

    return load_iam_config()


@router.put("/iam/config")
def save_config(
    req: IAMConfigRequest,
    principal: Any = Depends(require_roles(*_IAM_ADMIN_ROLES)),
) -> dict[str, Any]:
    """Replace enterprise IAM config after validation (admin only)."""

    try:
        return save_iam_config(req.model_dump(), actor=principal_actor(principal))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/projects/boundaries")
def upsert_boundary(
    req: ProjectBoundaryRequest,
    principal: Any = Depends(require_roles(*_IAM_ADMIN_ROLES)),
) -> dict[str, Any]:
    """Create or update a project/tenant boundary (admin only)."""

    try:
        return upsert_project_boundary(
            req.model_dump(), actor=principal_actor(principal)
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/projects/boundaries")
def boundaries(tenant_id: str | None = Query(default=None)) -> dict[str, Any]:
    """List project/tenant boundaries."""

    return list_project_boundaries(tenant_id=tenant_id)


@router.post("/projects/access-check")
def access_check(
    req: AccessCheckRequest,
    principal: Any = Depends(require_auth),
) -> dict[str, Any]:
    """Check whether the authenticated principal may act on a project boundary.

    Roles/permissions are taken from the verified principal (the token), NOT
    from the request body, so a caller cannot grant themselves access by
    claiming roles they do not hold.
    """

    return check_project_access(
        tenant_id=req.tenant_id,
        project_id=req.project_id,
        roles=list(getattr(principal, "roles", []) or []),
        permissions=list(getattr(principal, "permissions", []) or []),
        action=req.action,
    )


@router.get("/projects/{tenant_id}/{project_id}/guarded-resource")
def guarded_resource(
    tenant_id: str,
    project_id: str,
    principal: Any = Depends(require_auth),
) -> dict[str, Any]:
    """Example resource that ENFORCES the project boundary on the request path.

    Demonstrates ``enforce_project_access`` guarding a real request (H7):
    access is denied with 403 unless the authenticated principal's
    roles/permissions satisfy the tenant/project boundary.
    """

    enforce_project_access(
        principal,
        tenant_id=tenant_id,
        project_id=project_id,
        action="read",
    )
    return {
        "tenant_id": tenant_id,
        "project_id": project_id,
        "actor": principal_actor(principal),
        "granted": True,
    }
