"""Operations incident workflows for 1cAI."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.api._rentgen_store import store_or_none
from src.services.rentgen.incident_response import build_incident_report

router = APIRouter(prefix="/api/v1/operations", tags=["Operations"])


class IncidentReportRequest(BaseModel):
    incident_title: str = Field(default="Production incident", min_length=1)
    description: str | None = None
    symptoms: list[str] = Field(default_factory=list)
    log_path: str | None = None
    changed_modules: list[str] = Field(default_factory=list)
    min_duration_ms: float = Field(default=100.0, ge=0)
    top_n: int = Field(default=20, ge=1, le=50)
    module_limit: int = Field(default=12, ge=1, le=50)
    max_depth: int = Field(default=5, ge=1, le=12)
    max_edges: int = Field(default=300, ge=1, le=5000)
    include_team: bool = True


@router.post("/incident-report")
def incident_report(req: IncidentReportRequest) -> dict[str, Any]:
    return build_incident_report(
        store_or_none(),
        incident_title=req.incident_title,
        description=req.description,
        symptoms=req.symptoms,
        log_path=req.log_path,
        changed_modules=req.changed_modules,
        min_duration_ms=req.min_duration_ms,
        top_n=req.top_n,
        module_limit=req.module_limit,
        max_depth=req.max_depth,
        max_edges=req.max_edges,
        include_team=req.include_team,
    )


@router.get("/health")
def operations_health() -> dict[str, str]:
    return {"status": "ok"}
