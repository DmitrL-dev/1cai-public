"""Test execution evidence API."""

from __future__ import annotations

from typing import Any
import xml.etree.ElementTree as ET

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.services.rentgen.test_evidence import (
    get_test_run,
    import_junit_xml,
    list_test_runs,
    record_test_run,
)
from src.services.rentgen.test_runners import (
    adapter_catalog,
    build_runner_plan,
    create_evidence_bundle,
    import_result_file,
    run_test_adapter,
)


router = APIRouter(prefix="/api/v1/testing", tags=["Testing Evidence"])


class TestRunRequest(BaseModel):
    id: str | None = Field(default=None, max_length=160)
    title: str = Field(..., min_length=1, max_length=240)
    framework: str = Field(..., min_length=1, max_length=80)
    results: list[dict[str, Any]] = Field(default_factory=list)
    change_set_id: str | None = Field(default=None, max_length=160)
    command: str | None = Field(default=None, max_length=1000)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    dry_run: bool = False


class JUnitImportRequest(BaseModel):
    xml_text: str = Field(..., min_length=1)
    title: str = Field(default="JUnit import", max_length=240)
    framework: str = Field(default="JUnit", max_length=80)
    change_set_id: str | None = Field(default=None, max_length=160)


class RunnerPlanRequest(BaseModel):
    adapter: str = Field(..., min_length=1, max_length=80)
    test_files: list[str] = Field(default_factory=list)
    modules: list[str] = Field(default_factory=list)
    selectors: list[str] = Field(default_factory=list)
    manifest_path: str | None = Field(default=None, max_length=1000)
    output_dir: str | None = Field(default=None, max_length=1000)
    report_path: str | None = Field(default=None, max_length=1000)
    cwd: str | None = Field(default=None, max_length=1000)
    env: dict[str, Any] = Field(default_factory=dict)
    timeout: int = Field(default=1800, ge=1, le=86400)
    extra_args: list[str] = Field(default_factory=list)
    change_set_id: str | None = Field(default=None, max_length=160)
    dry_run: bool = True


class RunnerRunRequest(RunnerPlanRequest):
    execute: bool = False
    allow_external: bool = False
    import_results: bool = True


class ResultFileImportRequest(BaseModel):
    result_path: str = Field(..., min_length=1, max_length=1000)
    result_format: str = Field(default="auto", max_length=40)
    title: str | None = Field(default=None, max_length=240)
    framework: str | None = Field(default=None, max_length=80)
    change_set_id: str | None = Field(default=None, max_length=160)


class BundleRequest(BaseModel):
    attachment_paths: list[str] = Field(default_factory=list)
    copy_files: bool = False


def _handle_error(exc: Exception) -> HTTPException:
    if isinstance(exc, PermissionError):
        # Kill switch: test execution disabled on this host.
        return HTTPException(403, str(exc))
    if isinstance(exc, KeyError):
        return HTTPException(404, str(exc))
    if isinstance(exc, FileNotFoundError):
        return HTTPException(404, str(exc))
    if isinstance(exc, (ValueError, ET.ParseError)):
        return HTTPException(400, str(exc))
    return HTTPException(500, str(exc))


@router.post("/runs")
def create_run(req: TestRunRequest) -> dict[str, Any]:
    """Record a test execution run with normalized result evidence."""

    try:
        return record_test_run(
            run_id=req.id,
            title=req.title,
            framework=req.framework,
            results=req.results,
            change_set_id=req.change_set_id,
            command=req.command,
            evidence=req.evidence,
            dry_run=req.dry_run,
        )
    except Exception as exc:
        raise _handle_error(exc) from exc


@router.get("/runs")
def list_runs(
    status: str | None = Query(default=None),
    change_set_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    """List stored test runs."""

    return list_test_runs(status=status, change_set_id=change_set_id, limit=limit)


@router.get("/runs/{run_id}")
def run_details(run_id: str) -> dict[str, Any]:
    """Return one stored test run."""

    item = get_test_run(run_id)
    if item is None:
        raise HTTPException(404, f"Test run not found: {run_id}")
    return item


@router.post("/runs/import")
def import_run(req: JUnitImportRequest) -> dict[str, Any]:
    """Import a JUnit XML result document into the evidence store."""

    try:
        return import_junit_xml(
            xml_text=req.xml_text,
            title=req.title,
            framework=req.framework,
            change_set_id=req.change_set_id,
        )
    except Exception as exc:
        raise _handle_error(exc) from exc


@router.post("/runs/import-junit")
def import_junit(req: JUnitImportRequest) -> dict[str, Any]:
    """Compatibility alias for JUnit XML imports."""

    return import_run(req)


@router.get("/runners")
def runners() -> dict[str, Any]:
    """List supported local test runner adapters."""

    return adapter_catalog()


def _drop_unsafe_runner_inputs(payload: dict[str, Any]) -> dict[str, Any]:
    """Strip request-controlled execution levers (env / cwd / extra_args).

    These were RCE vectors (arbitrary process environment, working directory and
    trailing argv). The service layer also ignores them, but we drop them here so
    they never cross the API boundary.
    """

    for unsafe in ("env", "cwd", "extra_args"):
        payload.pop(unsafe, None)
    return payload


@router.post("/runners/plan")
def runner_plan(req: RunnerPlanRequest) -> dict[str, Any]:
    """Build a deterministic runner command plan without executing it."""

    try:
        return build_runner_plan(**_drop_unsafe_runner_inputs(req.model_dump()))
    except Exception as exc:
        raise _handle_error(exc) from exc


@router.post("/runners/run")
def runner_run(req: RunnerRunRequest) -> dict[str, Any]:
    """Dry-run or explicitly execute a test runner adapter and store evidence."""

    payload = _drop_unsafe_runner_inputs(req.model_dump())
    adapter = payload.pop("adapter")
    execute = bool(payload.pop("execute"))
    allow_external = bool(payload.pop("allow_external"))
    import_results = bool(payload.pop("import_results"))
    payload.pop("dry_run", None)
    try:
        return run_test_adapter(
            adapter,
            execute=execute,
            allow_external=allow_external,
            import_results=import_results,
            **payload,
        )
    except Exception as exc:
        raise _handle_error(exc) from exc


@router.post("/results/import-file")
def import_file(req: ResultFileImportRequest) -> dict[str, Any]:
    """Import JUnit XML, generic JSON or Allure result files from disk."""

    try:
        return import_result_file(**req.model_dump())
    except Exception as exc:
        raise _handle_error(exc) from exc


@router.post("/runs/{run_id}/bundle")
def bundle_run(run_id: str, req: BundleRequest) -> dict[str, Any]:
    """Create a checksum manifest for run evidence attachments."""

    if get_test_run(run_id) is None:
        raise HTTPException(404, f"Test run not found: {run_id}")
    try:
        return create_evidence_bundle(
            run_id,
            attachment_paths=req.attachment_paths,
            copy_files=req.copy_files,
        )
    except Exception as exc:
        raise _handle_error(exc) from exc
