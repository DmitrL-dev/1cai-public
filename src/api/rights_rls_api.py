"""Rights & RLS API for 1C role security gates."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from src.services.rentgen.rights_rls import build_rights_rls

router = APIRouter(prefix="/api/v1/rights-rls", tags=["Rights & RLS"])


@router.get("/analyze")
def analyze(
    config_path: str | None = Query(default=None, max_length=2000),
    baseline_path: str | None = Query(default=None, max_length=2000),
    role_limit: int = Query(default=120, ge=1, le=1000),
    object_limit: int = Query(default=400, ge=1, le=5000),
) -> dict[str, Any]:
    """Return role/object/action matrix, RLS signals and release security gate."""

    try:
        return build_rights_rls(
            config_path=config_path,
            baseline_config_path=baseline_path,
            role_limit=role_limit,
            object_limit=object_limit,
        )
    except ValueError as exc:
        # confine_path rejected a caller-supplied path outside the allowed data
        # roots (path traversal / arbitrary-file-read). Surface as 400, not 500.
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/health")
def health() -> dict[str, Any]:
    report = build_rights_rls(role_limit=20, object_limit=50)
    return {
        "status": report["decision"]["status"],
        "score": report["decision"]["score"],
        "roles": report["summary"]["roles"],
    }
