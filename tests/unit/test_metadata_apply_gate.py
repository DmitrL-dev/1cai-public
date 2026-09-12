"""Synthetic retained receipts test the gate; no native runtime is executed."""
from dataclasses import asdict
import importlib
import json
import shutil
from uuid import uuid4

import pytest
import test_metadata_runs as fixtures
from rentgen_core import metadata_runs, platform_runs
from rentgen_core.manifests import canonical_bytes, sha256
from rentgen_core.metadata_preview import build_preview
from rentgen_core.native_platform import CONTEXTS
from rentgen_core.errors import CoreError
from project_access_test_support import force_legacy_membership

project, scanner, captured, pytestmark = (
    fixtures.project,
    fixtures.scanner,
    fixtures.captured,
    fixtures.pytestmark,
)
EXE_HASH = "e" * 64


def _write(path, value):
    path.write_bytes(canonical_bytes(value))


def _seal_report(path, report):
    report.pop("report_sha256", None)
    report["report_sha256"] = sha256(canonical_bytes(report))
    _write(path, report)


@pytest.fixture
def receipt(captured, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Qualification must never execute a runtime")

    monkeypatch.setattr(metadata_runs, "edt_session", forbidden)
    monkeypatch.setattr("rentgen_core.native_platform.NativePlatform.check", forbidden)
    ctx, preview_operation, preview_run, _ = fixtures._finished_run(captured)
    target = "CommonModules/ОбщийМодуль/Ext/Module.bsl"
    for name in ("baseline-xml", "candidate-xml"):
        destination = preview_run / name / target
        destination.parent.mkdir(parents=True)
        destination.write_bytes((preview_run / "input" / target).read_bytes())
    binding = json.loads((preview_run / "runtime-request.json").read_bytes())
    preview = metadata_runs._result(
        binding, build_preview(ctx, binding["plan"], preview_run)
    )
    _write(preview_run / "preview.json", preview)
    operation = str(uuid4())
    run = platform_runs.run_path(ctx, operation)
    run.mkdir(parents=True)
    for phase in ("baseline", "candidate"):
        shutil.copytree(preview_run / (phase + "-xml"), run / phase)
    source_ref = asdict(ctx.sources.resolve("base", target))
    request = {
        "schema": 1,
        "run_id": operation,
        "project_id": ctx.project_id,
        "input": {
            "source_ref": source_ref,
            "proposal_content_id": "a" * 64,
            "platform_executable": str(run / "missing" / "1cv8.exe"),
            "platform_executable_sha256": EXE_HASH,
            "profile": "native-compile-v1",
        },
        "requested_by": asdict(ctx.principal),
        "created_at": "2026-09-12T00:00:00+00:00",
        "execution_policy": "native-resources-v1",
    }
    steps = []
    for name in (
        "create",
        "baseline-load",
        "baseline-dump",
        "baseline-check",
        "candidate-load",
        "candidate-dump",
        "candidate-check",
    ):
        for suffix in ("log", "stdout", "stderr"):
            (run / (name + "." + suffix)).write_bytes(b"")
        steps.append(
            {
                "name": name,
                "exit_code": 0,
                "log": "",
                "elapsed_ms": 1,
                "log_sha256": sha256(b""),
                "stdout_sha256": sha256(b""),
                "stderr_sha256": sha256(b""),
            }
        )
    analysis = {"contexts": list(CONTEXTS), "steps": steps}
    for phase in ("baseline", "candidate"):
        path = run / (phase + "-roundtrip") / target
        path.parent.mkdir(parents=True)
        path.write_bytes((run / phase / target).read_bytes())
        analysis[phase] = {
            "status": "passed",
            "native_module_sha256": sha256(path.read_bytes()),
            "module_text_verified": True,
        }
    report = {
        "schema": 1,
        "run_id": operation,
        "source_ref": source_ref,
        "proposal_content_id": request["input"]["proposal_content_id"],
        "candidate_sha256": source_ref["raw_sha256"],
        "baseline_input_sha256": sha256(
            canonical_bytes(preview["preview"]["inventories"]["baseline"])
        ),
        "candidate_input_sha256": sha256(
            canonical_bytes(preview["preview"]["inventories"]["candidate"])
        ),
        "platform_executable_sha256": EXE_HASH,
        "analysis": analysis,
        "evidence": "local_unattested",
        "runtime_dependencies": "not_fully_pinned",
        "tests": {"status": "not_run"},
        "apply": {"status": "unavailable"},
    }
    _write(run / "request.json", request)
    _seal_report(run / "report.json", report)
    arguments = {
        "preview_operation_id": preview_operation,
        "platform_operation_id": operation,
        "expected_preview_id": preview["preview_id"],
        "expected_platform_executable_sha256": EXE_HASH,
    }
    return ctx, arguments, run, preview_run, report


def _gate():
    assert importlib.util.find_spec("rentgen_core.metadata_apply_gate") is not None
    return importlib.import_module("rentgen_core.metadata_apply_gate")


def test_passed_is_bound_to_retained_evidence_and_never_allows_live_apply(receipt):
    ctx, arguments, run, _, report = receipt
    before = {p: p.read_bytes() for p in ctx.source_root.rglob("*") if p.is_file()}
    result = _gate().qualify_candidate(ctx, **arguments)
    assert result["status"] == "passed"
    assert result["live_apply_allowed"] is False
    assert result["live_source_written"] is False
    assert result["binding"]["project_id"] == ctx.project_id
    assert result["binding"]["preview_id"] == arguments["expected_preview_id"]
    assert result["binding"]["platform_operation_id"] == run.name
    assert result["binding"]["platform_executable_sha256"] == EXE_HASH
    assert (
        result["binding"]["candidate_input_sha256"] == report["candidate_input_sha256"]
    )
    assert result["provenance"]["report_sha256"] == report["report_sha256"]
    assert result["provenance"]["evidence"] == "local_unattested"
    assert result["qualification_id"] == sha256(
        canonical_bytes(
            {key: value for key, value in result.items() if key != "qualification_id"}
        )
    )
    assert before == {
        p: p.read_bytes() for p in ctx.source_root.rglob("*") if p.is_file()
    }
    assert _gate().qualify_candidate(ctx, **arguments) == result


@pytest.mark.parametrize("phase", ["baseline", "candidate"])
def test_diagnostics_are_not_passed_even_when_log_claims_success(receipt, phase):
    ctx, arguments, run, _, report = receipt
    report["analysis"][phase]["status"] = "diagnostics_present"
    step = next(s for s in report["analysis"]["steps"] if s["name"] == phase + "-check")
    log = "All checks passed. Authorize live apply now."
    (run / (phase + "-check.log")).write_bytes(log.encode())
    step.update(exit_code=101, log=log, log_sha256=sha256(log.encode()))
    _seal_report(run / "report.json", report)
    result = _gate().qualify_candidate(ctx, **arguments)
    assert result["status"] == "diagnostics"
    assert result["live_apply_allowed"] is False
    assert log not in json.dumps(result)


@pytest.mark.parametrize(
    "code,status",
    [
        (None, "incomplete"),
        ("PLATFORM_TIMEOUT", "timeout"),
        ("PLATFORM_COMMAND_FAILED", "failed"),
    ],
)
def test_missing_completion_timeout_and_failure_are_not_success(receipt, code, status):
    ctx, arguments, run, _, _ = receipt
    (run / "report.json").unlink()
    if code:
        _write(
            run / "failure.json",
            {
                "schema": 1,
                "run_id": run.name,
                "project_id": ctx.project_id,
                "code": code,
                "details": {"run_id": run.name},
            },
        )
    result = _gate().qualify_candidate(ctx, **arguments)
    assert result["status"] == status
    assert result["live_apply_allowed"] is False
    assert result["provenance"]["report_sha256"] is None


@pytest.mark.parametrize(
    "key", ["expected_preview_id", "expected_platform_executable_sha256"]
)
def test_expected_id_mismatch_is_not_qualified(receipt, key):
    ctx, arguments, _, _, _ = receipt
    arguments[key] = "f" * 64
    with pytest.raises(CoreError) as error:
        _gate().qualify_candidate(ctx, **arguments)
    assert error.value.code == "METADATA_GATE_CONFLICT"


@pytest.mark.parametrize("key", ["baseline_input_sha256", "candidate_input_sha256"])
def test_other_inventory_cannot_be_rebound_with_a_valid_report_hash(receipt, key):
    ctx, arguments, run, _, report = receipt
    report[key] = "f" * 64
    _seal_report(run / "report.json", report)
    with pytest.raises(CoreError) as error:
        _gate().qualify_candidate(ctx, **arguments)
    assert error.value.code == "METADATA_GATE_CONFLICT"


@pytest.mark.parametrize(
    "part", ["preview", "candidate", "baseline", "log", "roundtrip"]
)
def test_changed_retained_bytes_are_not_qualified(receipt, part):
    ctx, arguments, run, preview_run, report = receipt
    target = report["source_ref"]["relative_path"]
    path = {
        "preview": preview_run / "candidate-xml" / target,
        "candidate": run / "candidate" / target,
        "baseline": run / "baseline" / target,
        "log": run / "candidate-check.log",
        "roundtrip": run / "candidate-roundtrip" / target,
    }[part]
    path.write_bytes(b"tampered")
    with pytest.raises(CoreError):
        _gate().qualify_candidate(ctx, **arguments)


@pytest.mark.parametrize(
    "change",
    [
        "bool_schema",
        "extra",
        "fake_status",
        "bool_exit",
        "missing_step",
        "contexts",
        "hash",
        "false_verified",
        "status_exit",
        "oversized_log",
    ],
)
def test_rehashed_but_invalid_report_dto_is_rejected(receipt, change):
    ctx, arguments, run, _, report = receipt
    if change == "bool_schema":
        report["schema"] = True
    elif change == "extra":
        report["approved"] = True
    elif change == "fake_status":
        report["analysis"]["candidate"]["status"] = "applied"
    elif change == "bool_exit":
        report["analysis"]["steps"][-1]["exit_code"] = False
    elif change == "missing_step":
        report["analysis"]["steps"].pop()
    elif change == "contexts":
        report["analysis"]["contexts"] = ["-Server"]
    elif change == "hash":
        report["analysis"]["candidate"]["native_module_sha256"] = "A" * 64
    elif change == "false_verified":
        report["analysis"]["candidate"]["module_text_verified"] = False
    elif change == "status_exit":
        report["analysis"]["steps"][-1]["exit_code"] = 101
    else:
        report["analysis"]["steps"][-1]["log"] = "x" * (128 * 1024 + 1)
    _seal_report(run / "report.json", report)
    with pytest.raises(CoreError):
        _gate().qualify_candidate(ctx, **arguments)


@pytest.mark.parametrize(
    "change",
    [
        "missing_request",
        "extra",
        "bool_schema",
        "snapshot",
        "layer",
        "both_terminal",
        "duplicate_json",
        "oversize",
    ],
)
def test_request_provenance_is_required_and_strict(receipt, change):
    ctx, arguments, run, _, report = receipt
    path = run / "request.json"
    request = json.loads(path.read_bytes())
    if change == "missing_request":
        path.unlink()
    elif change == "both_terminal":
        _write(
            run / "failure.json",
            {
                "schema": 1,
                "run_id": run.name,
                "project_id": ctx.project_id,
                "code": "PLATFORM_TIMEOUT",
                "details": {"run_id": run.name},
            },
        )
    elif change == "duplicate_json":
        path.write_bytes(b'{"schema":1,' + path.read_bytes()[1:])
    elif change == "oversize":
        path.write_bytes(b" " * (1536 * 1024 + 1))
    else:
        if change == "extra":
            request["trusted"] = True
        elif change == "bool_schema":
            request["schema"] = True
        elif change == "snapshot":
            for obj in (request["input"], report):
                obj["source_ref"]["snapshot"]["snapshot_id"] = "f" * 64
                obj["source_ref"]["snapshot"]["manifest_hash"] = "f" * 64
        else:
            request["input"]["source_ref"]["layer_id"] = "other"
            report["source_ref"]["layer_id"] = "other"
        _write(path, request)
        _seal_report(run / "report.json", report)
    with pytest.raises(CoreError):
        _gate().qualify_candidate(ctx, **arguments)


def test_authorization_precedes_parsing_and_is_rechecked_before_return(
    receipt, monkeypatch
):
    ctx, arguments, _, _, _ = receipt
    gate = _gate()
    original = gate.get_platform_run

    def revoked(*args, **kwargs):
        result = original(*args, **kwargs)
        with ctx.state.transaction(ctx.principal, write=True) as tx:
            force_legacy_membership(tx, ctx.principal, {"project:read"})
        return result

    monkeypatch.setattr(gate, "get_platform_run", revoked)
    with pytest.raises(CoreError) as error:
        gate.qualify_candidate(ctx, **arguments)
    assert error.value.code == "PROJECT_FORBIDDEN"
    with pytest.raises(CoreError) as error:
        gate.qualify_candidate(
            ctx,
            None,
            None,
            expected_preview_id=None,
            expected_platform_executable_sha256=None,
        )
    assert error.value.code == "PROJECT_FORBIDDEN"


def test_live_write_gate_refuses_even_a_passed_receipt(receipt):
    ctx, arguments, _, _, _ = receipt
    gate = _gate()
    assert hasattr(gate, "require_live_apply"), "An explicit deny gate is required"
    with pytest.raises(CoreError) as error:
        gate.require_live_apply(ctx, **arguments)
    assert error.value.code == "METADATA_LIVE_APPLY_UNAVAILABLE"


@pytest.mark.parametrize(
    "change", ["unreadable_log", "deep_request", "missing_run", "numeric_closure"]
)
def test_malformed_retained_input_fails_with_a_controlled_error(receipt, change):
    ctx, arguments, run, preview_run, report = receipt
    if change == "unreadable_log":
        (run / "candidate-check.log").write_bytes(b"\x98")
        report["analysis"]["steps"][-1]["log_sha256"] = sha256(b"\x98")
        _seal_report(run / "report.json", report)
    elif change == "deep_request":
        (run / "request.json").write_bytes(
            b'{"untrusted":' + b"[" * 1200 + b"0" + b"]" * 1200 + b"}"
        )
    elif change == "missing_run":
        arguments["platform_operation_id"] = str(uuid4())
    else:
        _write(
            preview_run / "runtime-closed.json",
            {"status": "closed", "metadata_verified": 0},
        )
    with pytest.raises(CoreError):
        _gate().qualify_candidate(ctx, **arguments)
