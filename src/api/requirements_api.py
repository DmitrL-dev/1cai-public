"""Requirement-to-impact API for BA -> architecture -> development workflow."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.api._rentgen_store import store_or_none
from src.services.its_rag.search import ITSSearchService
from src.services.rentgen.artifact_graph import trace_artifact
from src.services.rentgen.change_plan import build_requirement_impact
from src.services.rentgen.requirements_traceability import (
    build_trace_record,
    get_trace,
    list_traces,
    save_trace,
    transition_trace,
)

router = APIRouter(prefix="/api/v1/requirements", tags=["requirements"])

_NO_STORE = (
    "Рентген store not built. Run: python tools/rentgen/build_store.py "
    "(needs data/rentgen_callgraph.ndjson + gabriel_runs/scores.json)."
)


class RequirementImpactRequest(BaseModel):
    text: str = Field(..., min_length=8)
    limit: int = Field(default=6, ge=1, le=20)
    max_depth: int = Field(default=3, ge=1, le=8)
    max_edges: int = Field(default=200, ge=10, le=1000)
    include_its_context: bool = True


class RequirementImpactResponse(BaseModel):
    requirement: str
    candidate_modules: list[dict]
    change_plan: dict
    its_context: list[dict] = Field(default_factory=list)
    caveats: list[str]


class RequirementTraceRequest(RequirementImpactRequest):
    title: str | None = Field(default=None, max_length=200)
    acceptance_criteria: list[str] = Field(default_factory=list)
    save: bool = True


class TraceTransitionRequest(BaseModel):
    status: str = Field(..., min_length=1, max_length=80)
    actor: str = Field(default="system", max_length=160)
    reason: str | None = Field(default=None, max_length=1000)


async def _its_context(text: str, include: bool) -> list[dict[str, Any]]:
    if not include:
        return []
    search = ITSSearchService(mode="offline")
    hits = await search.query(text, limit=3)
    return [
        {
            "section_title": hit.section_title,
            "source_file": hit.source_file,
            "score": hit.score,
            "text": hit.text[:600],
        }
        for hit in hits
    ]


@router.post("/impact", response_model=RequirementImpactResponse)
async def requirement_impact(req: RequirementImpactRequest):
    """Map a business requirement to likely 1C modules and whole-config risk."""
    store = store_or_none()
    if store is None:
        raise HTTPException(503, _NO_STORE)

    result = build_requirement_impact(
        store,
        req.text,
        limit=req.limit,
        max_depth=req.max_depth,
        max_edges=req.max_edges,
    )

    its_context = await _its_context(req.text, req.include_its_context)

    return RequirementImpactResponse(
        requirement=result["requirement"],
        candidate_modules=result["candidate_modules"],
        change_plan=result["change_plan"],
        its_context=its_context,
        caveats=result["caveats"],
    )


@router.post("/trace")
async def requirement_trace(req: RequirementTraceRequest) -> dict[str, Any]:
    """Build and optionally persist requirement -> code/metadata/tests trace links."""

    store = store_or_none()
    if store is None:
        raise HTTPException(503, _NO_STORE)

    impact = build_requirement_impact(
        store,
        req.text,
        limit=req.limit,
        max_depth=req.max_depth,
        max_edges=req.max_edges,
    )
    its_context = await _its_context(req.text, req.include_its_context)
    record = build_trace_record(
        requirement=impact["requirement"],
        candidate_modules=impact["candidate_modules"],
        change_plan=impact["change_plan"],
        its_context=its_context,
        acceptance_criteria=req.acceptance_criteria,
        title=req.title,
        caveats=impact["caveats"],
    )
    if req.save:
        record = save_trace(record)
    return record


@router.get("/traces")
def traces(limit: int = Query(50, ge=1, le=200)) -> dict[str, Any]:
    """List locally stored requirement trace records."""

    return list_traces(limit=limit)


@router.get("/traces/{trace_id}")
def trace_details(trace_id: str) -> dict[str, Any]:
    """Return one locally stored requirement trace record."""

    record = get_trace(trace_id)
    if record is None:
        raise HTTPException(404, f"Requirement trace not found: {trace_id}")
    return record


@router.post("/traces/{trace_id}/transition")
def transition(trace_id: str, req: TraceTransitionRequest) -> dict[str, Any]:
    """Move a requirement trace through the internal review lifecycle."""

    try:
        return transition_trace(
            trace_id, status=req.status, actor=req.actor, reason=req.reason
        )
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/traces/{trace_id}/artifact-trace")
def artifact_trace(
    trace_id: str, depth: int = Query(default=3, ge=0, le=12)
) -> dict[str, Any]:
    """Return Artifact Graph trace for a stored requirement trace."""

    try:
        return trace_artifact(trace_id, depth=depth)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
