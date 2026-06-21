"""Extension Safety API for 1C update and vendor-delivery checks."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.api._rentgen_store import store_or_none
from src.services.rentgen.extension_safety import build_extension_safety

router = APIRouter(prefix="/api/v1/extension-safety", tags=["Extension Safety"])


class ExtensionSafetyRequest(BaseModel):
    config_path: str | None = Field(default=None, max_length=2000)
    changed_modules: list[str] = Field(default_factory=list, max_length=200)
    extension_limit: int = Field(default=40, ge=1, le=200)
    max_files_per_extension: int = Field(default=1200, ge=1, le=10000)
    max_depth: int = Field(default=5, ge=1, le=12)
    max_edges: int = Field(default=300, ge=1, le=5000)


@router.post("/analyze")
def analyze(req: ExtensionSafetyRequest) -> dict[str, Any]:
    """Analyze local 1C extensions, risky hooks, rights and graph impact."""

    try:
        return build_extension_safety(
            store_or_none(),
            config_path=req.config_path,
            changed_modules=req.changed_modules,
            extension_limit=req.extension_limit,
            max_files_per_extension=req.max_files_per_extension,
            max_depth=req.max_depth,
            max_edges=req.max_edges,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/health")
def health() -> dict[str, Any]:
    report = build_extension_safety()
    return {
        "status": report["decision"]["status"],
        "extensions": report["summary"]["extensions"],
        "risk_score": report["decision"]["risk_score"],
    }
