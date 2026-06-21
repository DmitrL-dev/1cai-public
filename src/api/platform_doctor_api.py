"""Platform Doctor API for 1C platform readiness."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from src.services.rentgen.platform_doctor import build_platform_doctor

router = APIRouter(prefix="/api/v1/platform-doctor", tags=["Platform Doctor"])


@router.get("/analyze")
def analyze(
    config_path: str | None = Query(default=None, max_length=2000),
    target_platform_version: str | None = Query(default=None, max_length=80),
) -> dict[str, Any]:
    """Return local platform inventory, upgrade checklist and caveats."""

    try:
        return build_platform_doctor(
            config_path=config_path,
            target_platform_version=target_platform_version,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/health")
def health() -> dict[str, Any]:
    """Small health payload for dashboards and load balancers."""

    report = build_platform_doctor()
    return {
        "status": report["decision"]["status"],
        "score": report["decision"]["score"],
        "checks": len(report["checks"]),
    }
