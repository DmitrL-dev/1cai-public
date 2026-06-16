"""Offline readiness API for closed enterprise contours."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from src.services.rentgen.offline_readiness import build_offline_readiness

router = APIRouter(prefix="/api/v1/offline-readiness", tags=["Offline Readiness"])


@router.get("/analyze")
def analyze(strict: bool = Query(False)) -> dict[str, Any]:
    """Return a local-only readiness report without network probes."""

    return build_offline_readiness(strict=strict)


@router.get("/health")
def health() -> dict[str, Any]:
    """Small health payload for dashboards and load balancers."""

    report = build_offline_readiness(strict=False, include_metadata=False)
    return {
        "status": report["decision"]["status"],
        "score": report["decision"]["score"],
        "checks": report["summary"]["checks"],
        "external_env": report["summary"]["external_env"],
    }
