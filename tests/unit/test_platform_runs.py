"""Native operation identity, retained results and failed/interrupted histories."""
import json
from pathlib import Path
from threading import Event, Thread
from uuid import uuid4

import pytest

import rentgen_core as api
import rentgen_core.platform_check as implementation
from rentgen_core.native_platform import NativePlatform
from rentgen_core.platform_check import check_proposal_platform_json
from rentgen_core.platform_runs import get_platform_run
from rentgen_core.platform_runs import write_record
from rentgen_core.proposals import create_proposal_presentation
from project_access_test_support import force_legacy_membership
import test_platform_proposal as fixtures

project, scanner, candidate = fixtures.project, fixtures.scanner, fixtures.candidate
pytestmark, LIMITS = fixtures.pytestmark, fixtures.LIMITS


@pytest.fixture
def counted(monkeypatch):
    calls = []

    def check(self, before, after, target, run, authorize):
        calls.append(run)
        return {"baseline": {"status": "passed"}, "candidate": {"status": "passed"}}

    monkeypatch.setattr(NativePlatform, "check", check)
    return calls


def test_completed_replay_needs_no_executable_and_does_not_compile(candidate, counted):
    ctx, raw, platform = candidate
    operation = str(uuid4())
    first = check_proposal_platform_json(
        ctx, raw, platform, limits=LIMITS, operation_id=operation
    )
    platform.executable.unlink()
    again = check_proposal_platform_json(
        ctx, raw, platform, limits=LIMITS, operation_id=operation
    )
    assert first == again
    assert len(counted) == 1
    saved = get_platform_run(ctx, operation)
    assert saved["status"] == "completed" and saved["report"] == first
    assert saved["request"]["requested_by"]["id"] == ctx.principal.id
    assert saved["request"]["admission"]["retention"] == "retain_all_no_eviction"
    assert saved["request"]["admission"]["retained_run_limit"] == 256
    assert saved["request"]["admission"]["reserve_bytes"] == 8 * 1024**3


def test_get_result_does_not_resolve_missing_sources_or_snapshot(
    candidate, counted, monkeypatch
):
    ctx, raw, platform = candidate
    first = check_proposal_platform_json(ctx, raw, platform, limits=LIMITS)
    from dataclasses import replace

    state_only = replace(ctx, sources=None, snapshot=None, graph=None)
    platform.executable.unlink()
    assert get_platform_run(state_only, first["run_id"])["report"] == first


def test_operation_id_cannot_be_rebound(candidate, counted):
    ctx, raw, platform = candidate
    operation = str(uuid4())
    check_proposal_platform_json(
        ctx, raw, platform, limits=LIMITS, operation_id=operation
    )
    ref = ctx.sources.resolve("base", json.loads(raw)["source_ref"]["relative_path"])
    other = create_proposal_presentation(
        ctx, ref, ctx.sources.read_source(ref).replace(b"1", b"3"), limits=LIMITS
    ).canonical_json
    with pytest.raises(api.CoreError) as error:
        check_proposal_platform_json(
            ctx, other, platform, limits=LIMITS, operation_id=operation
        )
    assert error.value.code == "PLATFORM_RUN_CONFLICT"
    assert len(counted) == 1


def test_abrupt_exit_after_request_never_implicitly_retries(
    candidate, counted, monkeypatch
):
    ctx, raw, platform = candidate
    operation = str(uuid4())

    def stop(name):
        if name == "request_published":
            raise SystemExit("simulated process loss")

    monkeypatch.setattr(implementation, "_boundary", stop)
    with pytest.raises(SystemExit):
        check_proposal_platform_json(
            ctx, raw, platform, limits=LIMITS, operation_id=operation
        )
    monkeypatch.setattr(implementation, "_boundary", lambda name: None)
    assert get_platform_run(ctx, operation)["status"] == "incomplete"
    with pytest.raises(api.CoreError) as error:
        check_proposal_platform_json(
            ctx, raw, platform, limits=LIMITS, operation_id=operation
        )
    assert error.value.code == "PLATFORM_RUN_INCOMPLETE"
    assert not counted


def test_loss_after_report_publication_recovers_the_committed_result(
    candidate, counted, monkeypatch
):
    ctx, raw, platform = candidate
    operation = str(uuid4())

    def stop(name):
        if name == "report_published":
            raise KeyboardInterrupt()

    monkeypatch.setattr(implementation, "_boundary", stop)
    with pytest.raises(api.CoreError) as error:
        check_proposal_platform_json(
            ctx, raw, platform, limits=LIMITS, operation_id=operation
        )
    assert error.value.code == "PLATFORM_INTERRUPTED"
    assert error.value.details["run_id"] == operation
    result = get_platform_run(ctx, operation)
    assert result["status"] == "completed"
    assert not (counted[0] / "failure.json").exists()
    assert (
        check_proposal_platform_json(
            ctx, raw, platform, limits=LIMITS, operation_id=operation
        )
        == result["report"]
    )
    assert len(counted) == 1


def test_native_failure_is_recorded_and_not_retried(candidate, monkeypatch):
    ctx, raw, platform = candidate
    operation = str(uuid4())

    def failed(*args):
        raise api.CoreError("PLATFORM_TIMEOUT", "Timed out")

    monkeypatch.setattr(NativePlatform, "check", failed)
    with pytest.raises(api.CoreError) as error:
        check_proposal_platform_json(
            ctx, raw, platform, limits=LIMITS, operation_id=operation
        )
    assert error.value.details["run_id"] == operation
    status = get_platform_run(ctx, operation)
    assert (
        status["status"] == "failed" and status["failure"]["code"] == "PLATFORM_TIMEOUT"
    )
    with pytest.raises(api.CoreError) as error:
        check_proposal_platform_json(
            ctx, raw, platform, limits=LIMITS, operation_id=operation
        )
    assert error.value.code == "PLATFORM_RUN_INCOMPLETE"


def test_report_corruption_and_revocation_are_refused(candidate, counted):
    ctx, raw, platform = candidate
    result = check_proposal_platform_json(ctx, raw, platform, limits=LIMITS)
    report = counted[0] / "report.json"
    report.write_bytes(report.read_bytes().replace(b'"local_unattested"', b'"forged"'))
    with pytest.raises(api.CoreError) as error:
        get_platform_run(ctx, result["run_id"])
    assert error.value.code == "PLATFORM_RUN_CORRUPT"
    with ctx.state.transaction(ctx.principal, write=True) as tx:
        force_legacy_membership(tx, ctx.principal, {"project:read"})
    with pytest.raises(api.CoreError) as error:
        get_platform_run(ctx, result["run_id"])
    assert error.value.code == "PROJECT_FORBIDDEN"


def test_atomic_publication_waits_for_a_short_result_reader(
    candidate, tmp_path, monkeypatch
):
    from rentgen_core._windows_source_tree import pinned_directory

    ctx, _, _ = candidate
    run = tmp_path / "publication"
    run.mkdir()
    attempted, errors = Event(), []
    original = Path.rename

    def rename(path, target):
        attempted.set()
        return original(path, target)

    def publish():
        try:
            write_record(ctx, run, "request", {"schema": 1})
        except BaseException as exc:
            errors.append(exc)

    monkeypatch.setattr(Path, "rename", rename)
    with pinned_directory(run):
        worker = Thread(target=publish)
        worker.start()
        assert attempted.wait(2)
        assert not (run / "request.json").exists()
    worker.join(timeout=3)
    assert not worker.is_alive() and not errors
    assert json.loads((run / "request.json").read_bytes()) == {"schema": 1}


def test_retention_limit_refuses_before_allocating_more_evidence(
    candidate, counted, monkeypatch
):
    from rentgen_core import native_resources

    ctx, raw, platform = candidate
    monkeypatch.setattr(native_resources, "RETAINED_RUN_LIMIT", 1, raising=False)
    first = check_proposal_platform_json(ctx, raw, platform, limits=LIMITS)
    folder = counted[0]
    evidence = {
        name: (folder / name).read_bytes() for name in ("request.json", "report.json")
    }
    for _ in range(4):
        operation = str(uuid4())
        with pytest.raises(api.CoreError) as error:
            check_proposal_platform_json(
                ctx, raw, platform, limits=LIMITS, operation_id=operation
            )
        assert error.value.code == "NATIVE_RETENTION_LIMIT"
        assert error.value.details["admitted"] is False
        assert not (folder.parent / operation).exists()
    assert list(folder.parent.iterdir()) == [folder]
    assert evidence == {name: (folder / name).read_bytes() for name in evidence}
    assert (
        check_proposal_platform_json(
            ctx, raw, platform, limits=LIMITS, operation_id=first["run_id"]
        )
        == first
    )
    assert len(counted) == 1


def test_busy_receipt_is_retained_but_cannot_grow_past_admission_limit(
    candidate, counted, monkeypatch
):
    from rentgen_core import native_resources

    ctx, raw, platform = candidate
    monkeypatch.setattr(native_resources, "RETAINED_RUN_LIMIT", 1, raising=False)
    operation = str(uuid4())
    with native_resources.project_slot(ctx.state.path.parent):
        with pytest.raises(api.CoreError) as error:
            check_proposal_platform_json(
                ctx, raw, platform, limits=LIMITS, operation_id=operation
            )
        assert error.value.code == "NATIVE_EXECUTOR_BUSY"
        rejected = str(uuid4())
        with pytest.raises(api.CoreError) as error:
            check_proposal_platform_json(
                ctx, raw, platform, limits=LIMITS, operation_id=rejected
            )
        assert error.value.code == "NATIVE_RETENTION_LIMIT"
    assert get_platform_run(ctx, operation)["status"] == "failed"
    assert not (ctx.state.path.parent / "platform-checks" / rejected).exists()
    with pytest.raises(api.CoreError) as error:
        check_proposal_platform_json(
            ctx, raw, platform, limits=LIMITS, operation_id=operation
        )
    assert error.value.code == "PLATFORM_RUN_INCOMPLETE"
    assert not counted


@pytest.mark.parametrize("boundary", ["pinned_directory", "_file_slot"])
@pytest.mark.parametrize("filesystem_error", [False, True])
def test_admission_exit_failure_retains_uuid_without_reporting_rejection(
    candidate, counted, monkeypatch, boundary, filesystem_error
):
    from contextlib import contextmanager
    from rentgen_core import native_resources

    ctx, raw, platform = candidate
    operation = str(uuid4())
    folder = ctx.state.path.parent / "platform-checks" / operation
    original = getattr(native_resources, boundary)

    @contextmanager
    def failed_exit(*args, **kwargs):
        with original(*args, **kwargs) as value:
            yield value
        if folder.exists():
            if filesystem_error:
                raise OSError("injected exit failure")
            raise api.CoreError("INJECTED_EXIT_FAILURE", "Injected exit failure")

    with monkeypatch.context() as patch:
        patch.setattr(native_resources, boundary, failed_exit)
        with pytest.raises(api.CoreError) as error:
            check_proposal_platform_json(
                ctx, raw, platform, limits=LIMITS, operation_id=operation
            )
    assert error.value.code == "NATIVE_ADMISSION_INCOMPLETE"
    assert error.value.details["admitted"] is True
    assert error.value.details["status"] == "incomplete"
    assert error.value.details["run_id"] == operation
    assert error.value.details["cause"] == (
        "FILESYSTEM_ERROR" if filesystem_error else "INJECTED_EXIT_FAILURE"
    )
    assert folder.is_dir() and not list(folder.iterdir())
    saved = get_platform_run(ctx, operation)
    assert saved["status"] == "incomplete" and saved["request"] is None
    with pytest.raises(api.CoreError) as retry:
        check_proposal_platform_json(
            ctx, raw, platform, limits=LIMITS, operation_id=operation
        )
    assert retry.value.code == "PLATFORM_RUN_CONFLICT"
    assert not counted
    recovered = check_proposal_platform_json(ctx, raw, platform, limits=LIMITS)
    assert recovered["run_id"] != operation and len(counted) == 1
    assert get_platform_run(ctx, operation) == saved
