"""Internal ALM artifact graph API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.services.rentgen import artifact_graph

router = APIRouter(prefix="/api/v1/artifacts", tags=["Artifacts"])


class ArtifactRequest(BaseModel):
    id: str | None = Field(default=None, max_length=120)
    type: str = Field(..., min_length=1, max_length=80)
    title: str = Field(..., min_length=1, max_length=240)
    description: str | None = Field(default=None, max_length=4000)
    status: str | None = Field(default="draft", max_length=80)
    owner: str | None = Field(default=None, max_length=160)
    risk: str | None = Field(default=None, max_length=40)
    priority: str | None = Field(default=None, max_length=40)
    tags: list[str] = Field(default_factory=list)
    source: str | None = Field(default=None, max_length=240)
    attributes: dict[str, Any] = Field(default_factory=dict)


class ArtifactPatch(BaseModel):
    title: str | None = Field(default=None, max_length=240)
    description: str | None = Field(default=None, max_length=4000)
    status: str | None = Field(default=None, max_length=80)
    owner: str | None = Field(default=None, max_length=160)
    risk: str | None = Field(default=None, max_length=40)
    priority: str | None = Field(default=None, max_length=40)
    tags: list[str] | None = None
    source: str | None = Field(default=None, max_length=240)
    attributes: dict[str, Any] | None = None


class LinkRequest(BaseModel):
    source_id: str = Field(..., min_length=1, max_length=160)
    target_id: str = Field(..., min_length=1, max_length=160)
    type: str = Field(..., min_length=1, max_length=80)
    rationale: str | None = Field(default=None, max_length=1000)
    status: str = Field(default="active", max_length=80)
    suspect: bool = False
    attributes: dict[str, Any] = Field(default_factory=dict)


def _handle_error(exc: Exception) -> HTTPException:
    if isinstance(exc, KeyError):
        return HTTPException(404, str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(400, str(exc))
    return HTTPException(500, str(exc))


@router.post("")
def create_artifact(req: ArtifactRequest) -> dict[str, Any]:
    """Create an internal ALM artifact."""

    try:
        return artifact_graph.create_artifact(req.model_dump(exclude_none=True))
    except Exception as exc:
        raise _handle_error(exc) from exc


@router.get("")
def artifacts(
    type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    owner: str | None = Query(default=None),
    query: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    """List internal ALM artifacts."""

    return artifact_graph.list_artifacts(
        artifact_type=type,
        status=status,
        owner=owner,
        query=query,
        limit=limit,
    )


@router.get("/health")
def health() -> dict[str, Any]:
    """Return artifact graph store health."""

    return artifact_graph.health()


@router.get("/matrix")
def matrix() -> dict[str, Any]:
    """Return requirements-oriented coverage matrix."""

    return artifact_graph.coverage_matrix()


@router.get("/{artifact_id}")
def artifact_details(artifact_id: str) -> dict[str, Any]:
    """Return one artifact."""

    item = artifact_graph.get_artifact(artifact_id)
    if item is None:
        raise HTTPException(404, f"Artifact not found: {artifact_id}")
    return item


@router.patch("/{artifact_id}")
def patch_artifact(artifact_id: str, req: ArtifactPatch) -> dict[str, Any]:
    """Patch one artifact."""

    patch = req.model_dump(exclude_unset=True, exclude_none=True)
    try:
        return artifact_graph.update_artifact(artifact_id, patch)
    except Exception as exc:
        raise _handle_error(exc) from exc


@router.post("/links")
def create_link(req: LinkRequest) -> dict[str, Any]:
    """Create a traceability link between artifacts."""

    try:
        return artifact_graph.link_artifacts(
            source_id=req.source_id,
            target_id=req.target_id,
            link_type=req.type,
            rationale=req.rationale,
            status=req.status,
            suspect=req.suspect,
            attributes=req.attributes,
        )
    except Exception as exc:
        raise _handle_error(exc) from exc


@router.get("/{artifact_id}/trace")
def trace(
    artifact_id: str,
    depth: int = Query(default=4, ge=0, le=12),
    direction: str = Query(default="both", pattern="^(in|out|both)$"),
) -> dict[str, Any]:
    """Trace incoming/outgoing links around an artifact."""

    try:
        return artifact_graph.trace_artifact(
            artifact_id, depth=depth, direction=direction
        )
    except Exception as exc:
        raise _handle_error(exc) from exc
