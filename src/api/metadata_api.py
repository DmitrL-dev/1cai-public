"""1C EDT metadata graph API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.api._rentgen_store import store_or_none
from src.services.rentgen.metadata_graph import (
    build_metadata_graph,
    get_metadata_object,
    metadata_summary,
    search_metadata,
)
from src.services.rentgen.metadata_data_governance import build_data_governance
from src.services.rentgen.form_designer import build_form_blueprint
from src.services.rentgen.security_posture import build_security_posture
from src.services.rentgen.canonical_metadata import (
    diff_metadata as diff_canonical_metadata,
    diff_rights as diff_canonical_rights,
    get_canonical_object,
    import_metadata_snapshot as import_canonical_metadata_snapshot,
    list_metadata_objects as list_canonical_metadata_objects,
    list_metadata_snapshots as list_canonical_metadata_snapshots,
)
from src.services.rentgen.metadata_insights import (
    create_metadata_snapshot,
    diff_metadata_snapshot,
    list_metadata_snapshots,
    review_forms,
    security_review,
)

router = APIRouter(prefix="/api/v1/metadata", tags=["Metadata Graph"])


class SnapshotRequest(BaseModel):
    name: str | None = Field(default=None, max_length=120)


class DiffRequest(BaseModel):
    snapshot_id: str = Field(..., min_length=1)
    limit: int = Field(default=100, ge=1, le=500)


class FormReviewRequest(BaseModel):
    identifier: str = Field(..., min_length=1)
    form_name: str | None = Field(default=None, max_length=300)


class FormBlueprintRequest(BaseModel):
    identifier: str = Field(..., min_length=1)
    form_kind: str | None = Field(default="auto", max_length=40)
    intent: str | None = Field(default=None, max_length=500)
    include_review: bool = True


class CanonicalImportRequest(BaseModel):
    config_path: str | None = Field(default=None, max_length=1000)
    name: str | None = Field(default=None, max_length=160)
    source: str = Field(default="edt", max_length=80)
    refresh: bool = True


@router.get("/health")
def health() -> dict[str, Any]:
    graph = metadata_summary()
    return {
        "status": "ok" if graph["available"] else "missing",
        "available": graph["available"],
        "config_path": graph["config_path"],
        "total_objects": graph["summary"].get("total_objects", 0),
    }


@router.get("/summary")
def summary() -> dict[str, Any]:
    return metadata_summary()


@router.get("/search")
def search(
    q: str | None = Query(None, min_length=1),
    type: str | None = Query(None, description="Metadata type, e.g. Document, Catalog, Role"),
    limit: int = Query(30, ge=1, le=200),
) -> dict[str, Any]:
    return {"items": search_metadata(q, metadata_type=type, limit=limit)}


@router.get("/object")
def object_details(identifier: str = Query(..., min_length=1)) -> dict[str, Any]:
    obj = get_metadata_object(identifier)
    if obj is None:
        raise HTTPException(404, f"Metadata object not found: {identifier}")
    return obj


@router.post("/import")
def import_canonical(req: CanonicalImportRequest) -> dict[str, Any]:
    """Import EDT metadata into the canonical metadata store."""

    try:
        return import_canonical_metadata_snapshot(
            config_path=req.config_path,
            name=req.name,
            source=req.source,
            refresh=req.refresh,
        )
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/objects")
def canonical_objects(
    type: str | None = Query(default=None, description="Metadata type, e.g. Document, Catalog, Role"),
    group: str | None = Query(default=None, description="Canonical group: data, ui, integration, security, support"),
    q: str | None = Query(default=None, min_length=1),
    limit: int = Query(default=100, ge=1, le=1000),
) -> dict[str, Any]:
    """List canonical metadata objects from the latest imports."""

    return list_canonical_metadata_objects(metadata_type=type, group=group, query=q, limit=limit)


@router.get("/objects/{object_id}")
def canonical_object_details(object_id: str) -> dict[str, Any]:
    """Return one canonical metadata object by id, ref, path or name."""

    obj = get_canonical_object(object_id)
    if obj is None:
        raise HTTPException(404, f"Canonical metadata object not found: {object_id}")
    return obj


@router.get("/canonical-snapshots")
def canonical_snapshots(limit: int = Query(default=50, ge=1, le=200)) -> dict[str, Any]:
    """List canonical metadata snapshots."""

    return list_canonical_metadata_snapshots(limit=limit)


@router.get("/drift")
def canonical_drift(
    before_id: str = Query(..., min_length=1),
    after_id: str | None = Query(default=None, min_length=1),
    limit: int = Query(default=200, ge=1, le=1000),
) -> dict[str, Any]:
    """Compare canonical metadata snapshots."""

    try:
        return diff_canonical_metadata(before_id=before_id, after_id=after_id, limit=limit)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/rights/diff")
def canonical_rights_diff(
    before_id: str = Query(..., min_length=1),
    after_id: str | None = Query(default=None, min_length=1),
    limit: int = Query(default=200, ge=1, le=1000),
) -> dict[str, Any]:
    """Compare role rights between canonical metadata snapshots."""

    try:
        return diff_canonical_rights(before_id=before_id, after_id=after_id, limit=limit)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/object-impact")
def object_impact(
    identifier: str = Query(..., min_length=1),
    max_depth: int = Query(3, ge=1, le=8),
    max_edges: int = Query(150, ge=1, le=1000),
) -> dict[str, Any]:
    obj = get_metadata_object(identifier)
    if obj is None:
        raise HTTPException(404, f"Metadata object not found: {identifier}")

    modules = [module["path"] for module in obj["modules"]]
    store = store_or_none()
    impacts = []
    total_edges = 0
    if store is not None:
        for module_path in modules:
            impact = store.module_impact(module_path, max_depth=max_depth, max_edges=max_edges)
            total_edges += int(impact.get("total", 0))
            impacts.append(impact)

    return {
        "object": {
            "type": obj["type"],
            "name": obj["name"],
            "synonym": obj["synonym"],
            "ref": obj["ref"],
            "path": obj["path"],
            "counts": obj["counts"],
        },
        "modules": modules,
        "rentgen_available": store is not None,
        "total_impact_edges": total_edges,
        "impacts": impacts,
        "caveats": [
            "Impact is module-based; metadata-only references are reported in object details.",
            "Dynamic calls may not be present in the Rentgen graph.",
        ],
    }


@router.post("/snapshots")
def create_snapshot(req: SnapshotRequest) -> dict[str, Any]:
    return create_metadata_snapshot(req.name)


@router.get("/snapshots")
def snapshots() -> dict[str, Any]:
    items = list_metadata_snapshots()
    return {"items": items, "total": len(items)}


@router.post("/diff")
def diff(req: DiffRequest) -> dict[str, Any]:
    try:
        return diff_metadata_snapshot(req.snapshot_id, limit=req.limit)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/security-review")
def security(limit: int = Query(200, ge=1, le=1000)) -> dict[str, Any]:
    return security_review(limit=limit)


@router.get("/security-posture")
def security_posture(
    limit: int = Query(200, ge=1, le=1000),
    module_limit: int = Query(2500, ge=1, le=30000),
    snapshot_id: str | None = Query(None, min_length=1),
) -> dict[str, Any]:
    return build_security_posture(limit=limit, module_limit=module_limit, snapshot_id=snapshot_id)


@router.get("/data-governance")
def data_governance(limit: int = Query(120, ge=1, le=1000)) -> dict[str, Any]:
    return build_data_governance(limit=limit)


@router.post("/form-review")
def form_review(req: FormReviewRequest) -> dict[str, Any]:
    try:
        return review_forms(req.identifier, form_name=req.form_name)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/form-blueprint")
def form_blueprint(req: FormBlueprintRequest) -> dict[str, Any]:
    try:
        return build_form_blueprint(
            req.identifier,
            form_kind=req.form_kind,
            intent=req.intent,
            include_review=req.include_review,
        )
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/refresh")
def refresh() -> dict[str, Any]:
    build_metadata_graph.cache_clear()
    build_data_governance.cache_clear()
    build_security_posture.cache_clear()
    return {"status": "refreshed", **metadata_summary()}
