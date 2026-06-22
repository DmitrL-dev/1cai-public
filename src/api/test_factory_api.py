"""Test Factory API for executable YAxUnit/Vanessa test packages."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.api._rentgen_store import store_or_none
from src.services.rentgen.change_plan import extract_diff_modules
from src.services.rentgen.test_factory import build_test_factory

router = APIRouter(prefix="/api/v1/test-factory", tags=["Test Factory"])


class TestFactoryRequest(BaseModel):
    client_name: str = Field(default="Demo client", min_length=1, max_length=200)
    release_name: str | None = Field(default=None, max_length=160)
    changed_modules: list[str] = Field(default_factory=list, max_length=200)
    diff: str | None = Field(default=None, max_length=2_000_000)
    max_depth: int = Field(default=5, ge=1, le=10)
    max_edges: int = Field(default=600, ge=1, le=5000)
    hotspot_limit: int = Field(default=10, ge=1, le=100)
    match_limit: int = Field(default=10, ge=1, le=50)


def _build_report(req: TestFactoryRequest) -> dict[str, Any]:
    changed_modules = list(
        dict.fromkeys(req.changed_modules + extract_diff_modules(req.diff))
    )
    store = store_or_none()
    return build_test_factory(
        store,
        changed_modules=changed_modules,
        diff=req.diff,
        client_name=req.client_name,
        release_name=req.release_name,
        max_depth=req.max_depth,
        max_edges=req.max_edges,
        hotspot_limit=req.hotspot_limit,
        match_limit=req.match_limit,
    )


@router.post("/build")
def build(req: TestFactoryRequest) -> dict[str, Any]:
    """Build run-now tests, generated skeletons, manual checks and evidence routes."""

    return _build_report(req)


@router.get("/health")
def health() -> dict[str, Any]:
    report = _build_report(TestFactoryRequest(changed_modules=[]))
    return {
        "status": report["decision"]["status"],
        "score": report["decision"]["score"],
        "changed_modules": report["summary"]["changed_modules"],
        "generation_tasks": report["summary"]["generation_tasks"],
    }
