"""Productization readiness API."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.services.offline_bundle import (
    build_offline_bundle_archive,
    build_offline_bundle_manifest,
    load_offline_bundle_manifest,
    verify_offline_bundle_archive,
    verify_offline_bundle_manifest,
)
from src.services.productization_readiness import (
    list_productization_deliverables,
    productization_markdown_report,
    productization_readiness,
)
from src.services.sbom_inventory import generate_sbom, sbom_markdown_report


router = APIRouter(prefix="/api/v1/productization", tags=["Productization"])


class OfflineBundleManifestRequest(BaseModel):
    profile: str = Field(default="pilot", max_length=40)
    include_paths: list[str] = Field(default_factory=list)
    include_defaults: bool = True
    output_path: str | None = Field(default=None, max_length=500)
    sign: bool = False
    write: bool = True


class OfflineBundleVerifyRequest(BaseModel):
    manifest_path: str | None = Field(default=None, max_length=500)


class OfflineBundleArchiveRequest(OfflineBundleManifestRequest):
    pass


class OfflineBundleArchiveVerifyRequest(BaseModel):
    archive_path: str = Field(..., min_length=1, max_length=500)


class SBOMRequest(BaseModel):
    include_paths: list[str] = Field(default_factory=list)
    include_defaults: bool = True
    output_path: str | None = Field(default=None, max_length=500)
    write: bool = True


@router.get("/readiness")
def readiness() -> dict[str, Any]:
    """Return enterprise productization readiness."""

    return productization_readiness()


@router.get("/deliverables")
def deliverables() -> dict[str, Any]:
    """Return productization deliverable checks."""

    return list_productization_deliverables()


@router.get("/report")
def report() -> dict[str, Any]:
    """Return a compact Markdown readiness report."""

    return productization_markdown_report()


@router.post("/offline-bundle/manifest")
def create_offline_bundle_manifest(req: OfflineBundleManifestRequest) -> dict[str, Any]:
    """Build an offline bundle manifest with hashes and optional env-based signature."""

    try:
        return build_offline_bundle_manifest(
            profile=req.profile,
            include_paths=req.include_paths,
            include_defaults=req.include_defaults,
            output_path=None if req.output_path is None else Path(req.output_path),
            sign=req.sign,
            write=req.write,
        )
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/offline-bundle/manifest")
def get_offline_bundle_manifest() -> dict[str, Any]:
    """Return the latest offline bundle manifest."""

    try:
        return load_offline_bundle_manifest()
    except Exception as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/offline-bundle/verify")
def verify_offline_bundle(req: OfflineBundleVerifyRequest) -> dict[str, Any]:
    """Verify an offline bundle manifest and referenced file hashes."""

    try:
        path = None if req.manifest_path is None else Path(req.manifest_path)
        return verify_offline_bundle_manifest(manifest_path=path)
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/offline-bundle/archive")
def create_offline_bundle_archive(req: OfflineBundleArchiveRequest) -> dict[str, Any]:
    """Build a portable offline ZIP archive with payload and manifest."""

    try:
        return build_offline_bundle_archive(
            profile=req.profile,
            include_paths=req.include_paths,
            include_defaults=req.include_defaults,
            output_path=None if req.output_path is None else Path(req.output_path),
            sign=req.sign,
        )
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/offline-bundle/archive/verify")
def verify_offline_bundle_archive_api(req: OfflineBundleArchiveVerifyRequest) -> dict[str, Any]:
    """Verify a portable offline ZIP archive without extracting it."""

    try:
        return verify_offline_bundle_archive(archive_path=Path(req.archive_path))
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/sbom")
def create_sbom(req: SBOMRequest) -> dict[str, Any]:
    """Generate local dependency/SBOM inventory."""

    try:
        return generate_sbom(
            include_paths=req.include_paths,
            include_defaults=req.include_defaults,
            output_path=None if req.output_path is None else Path(req.output_path),
            write=req.write,
        )
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/sbom/report")
def sbom_report() -> dict[str, Any]:
    """Return local dependency/SBOM inventory as Markdown."""

    return sbom_markdown_report()
