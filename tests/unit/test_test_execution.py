"""Real retained state and Windows pins; the test engine boundary is mocked here."""
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest

import test_platform_proposal as fixtures
import test_test_profiles as profile_fixtures
from project_access_test_support import force_legacy_membership
from rentgen_core.errors import CoreError
from rentgen_core.platform_runs import get_platform_run
from rentgen_core import test_execution as execution
from rentgen_core import test_profiles as profiles

project, scanner, candidate = fixtures.project, fixtures.scanner, fixtures.candidate
definition = profile_fixtures.definition
pytestmark, LIMITS = fixtures.pytestmark, fixtures.LIMITS


def test_exact_pinned_inputs_recovery_and_disabled_completed_replay(
    candidate, definition, monkeypatch
):
    ctx, raw, _ = candidate
    profile_id = profiles.register_profile(ctx, definition)["profile_id"]
    calls = []

    def run(platform, ibcmd, engine, modules, before, after, target, folder, authorize):
        authorize()
        calls.append(folder)
        assert (before / target).read_bytes() != (after / target).read_bytes()
        with pytest.raises(OSError):
            (after / target).write_bytes(b"tamper")
        with pytest.raises(OSError):
            engine.write_bytes(b"tamper")
        return {
            "status": "passed",
            "baseline": {"status": "failed"},
            "candidate": {"status": "passed"},
            "isolated_infobases": True,
        }

    monkeypatch.setattr(execution, "run_yaxunit", run)
    operation = str(uuid4())
    result = execution.check_proposal_tests(
        ctx, raw, profile_id, operation, limits=LIMITS
    )
    state_only = replace(ctx, snapshot=None, sources=None, graph=None)
    assert (
        get_platform_run(state_only, operation, namespace="test-runs")["report"]
        == result
    )
    profiles.disable_profile(ctx, profile_id)
    Path(definition["platform"]["path"]).unlink()
    assert (
        execution.check_proposal_tests(ctx, raw, profile_id, operation, limits=LIMITS)
        == result
    )
    assert len(calls) == 1
    with pytest.raises(CoreError) as error:
        execution.check_proposal_tests(ctx, raw, "0" * 64, operation, limits=LIMITS)
    assert error.value.code == "PLATFORM_RUN_CONFLICT"


def test_disabling_running_profile_withholds_success_and_does_not_retry(
    candidate, definition, monkeypatch
):
    ctx, raw, _ = candidate
    profile_id = profiles.register_profile(ctx, definition)["profile_id"]
    calls = []

    def run(*args):
        calls.append(1)
        profiles.disable_profile(ctx, profile_id)
        args[-1]()

    monkeypatch.setattr(execution, "run_yaxunit", run)
    operation = str(uuid4())
    with pytest.raises(CoreError) as error:
        execution.check_proposal_tests(ctx, raw, profile_id, operation, limits=LIMITS)
    assert error.value.code == "TEST_PROFILE_DISABLED"
    assert get_platform_run(ctx, operation, namespace="test-runs")["status"] == "failed"
    with pytest.raises(CoreError):
        execution.check_proposal_tests(ctx, raw, profile_id, operation, limits=LIMITS)
    assert calls == [1]


def test_revoked_access_prevents_report(candidate, definition, monkeypatch):
    ctx, raw, _ = candidate
    profile_id = profiles.register_profile(ctx, definition)["profile_id"]

    def run(*args):
        with ctx.state.transaction(ctx.principal, write=True) as tx:
            force_legacy_membership(tx, ctx.principal, {"project:admin"})
        args[-1]()

    monkeypatch.setattr(execution, "run_yaxunit", run)
    operation = str(uuid4())
    with pytest.raises(CoreError) as error:
        execution.check_proposal_tests(ctx, raw, profile_id, operation, limits=LIMITS)
    assert error.value.code == "PROJECT_FORBIDDEN"
    assert not (
        ctx.state.path.parent / "test-runs" / operation / "report.json"
    ).exists()


def test_test_admission_counts_incomplete_compiler_attempt_and_preserves_it(
    candidate, definition, monkeypatch
):
    from rentgen_core import native_resources

    ctx, raw, _ = candidate
    profile_id = profiles.register_profile(ctx, definition)["profile_id"]
    unknown = ctx.state.path.parent / "platform-checks" / str(uuid4())
    unknown.mkdir(parents=True)
    (unknown / "request.json").write_bytes(b"unknown outcome evidence")
    (unknown / "infobase").mkdir()
    database = unknown / "infobase" / "1Cv8.1CD"
    database.write_bytes(b"retained database")
    calls = []
    monkeypatch.setattr(execution, "run_yaxunit", lambda *args: calls.append(1))
    monkeypatch.setattr(native_resources, "RETAINED_RUN_LIMIT", 1, raising=False)
    operation = str(uuid4())
    with pytest.raises(CoreError) as error:
        execution.check_proposal_tests(ctx, raw, profile_id, operation, limits=LIMITS)
    assert error.value.code == "NATIVE_RETENTION_LIMIT"
    assert error.value.details["admitted"] is False
    assert not (ctx.state.path.parent / "test-runs" / operation).exists()
    assert (unknown / "request.json").read_bytes() == b"unknown outcome evidence"
    assert database.read_bytes() == b"retained database"
    assert not calls


def test_failed_test_retains_scratch_database_request_and_failure(
    candidate, definition, monkeypatch
):
    ctx, raw, _ = candidate
    profile_id = profiles.register_profile(ctx, definition)["profile_id"]
    operation = str(uuid4())
    folder = ctx.state.path.parent / "test-runs" / operation
    scratch = folder / "baseline-extension-properties-data"
    database = folder / "baseline-infobase" / "1Cv8.1CD"

    def fail(*args):
        scratch.mkdir()
        (scratch / "log").write_bytes(b"incomplete scratch")
        database.parent.mkdir()
        database.write_bytes(b"retained database")
        raise CoreError("PLATFORM_TIMEOUT", "Interrupted native test")

    monkeypatch.setattr(execution, "run_yaxunit", fail)
    with pytest.raises(CoreError) as error:
        execution.check_proposal_tests(ctx, raw, profile_id, operation, limits=LIMITS)
    assert error.value.code == "PLATFORM_TIMEOUT"
    assert (scratch / "log").read_bytes() == b"incomplete scratch"
    assert database.read_bytes() == b"retained database"
    saved = get_platform_run(ctx, operation, namespace="test-runs")
    assert saved["request"]["admission"]["retention"] == "retain_all_no_eviction"
    assert saved["status"] == "failed"
