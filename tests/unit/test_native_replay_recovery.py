"""Windows retained journals and authorization; native engines are injected."""
from dataclasses import replace
from uuid import uuid4

import pytest

import test_platform_proposal as fixtures
import test_test_profiles as profile_fixtures
from project_access_test_support import force_legacy_membership
from rentgen_core import platform_check, test_execution, test_profiles
from rentgen_core.errors import CoreError
from rentgen_core.native_platform import NativePlatform
from rentgen_core.platform_runs import get_platform_run

project, scanner, candidate = fixtures.project, fixtures.scanner, fixtures.candidate
definition = profile_fixtures.definition
pytestmark, LIMITS = fixtures.pytestmark, fixtures.LIMITS


@pytest.fixture(params=["platform-checks", "test-runs"])
def run(request, candidate, monkeypatch):
    ctx, raw, platform = candidate
    operation = str(uuid4())
    namespace = request.param
    calls = []

    def compile(*args):
        calls.append(1)
        return {"baseline": {"status": "passed"}, "candidate": {"status": "passed"}}

    def tests(*args):
        calls.append(1)
        return {"status": "passed", "baseline": {"status": "passed"},
                "candidate": {"status": "passed"}, "isolated_infobases": True}

    monkeypatch.setattr(NativePlatform, "check", compile)
    monkeypatch.setattr(test_execution, "run_yaxunit", tests)
    if namespace == "test-runs":
        definition = request.getfixturevalue("definition")
        profile = test_profiles.register_profile(ctx, definition)["profile_id"]
        invoke = lambda: test_execution.check_proposal_tests(
            ctx, raw, profile, operation, limits=LIMITS
        )
    else:
        invoke = lambda: platform_check.check_proposal_platform_json(
            ctx, raw, platform, operation_id=operation, limits=LIMITS
        )
    return ctx, operation, namespace, invoke, calls


@pytest.mark.parametrize("partial_request", [False, True])
def test_loss_before_request_publication_preserves_unknown_run(
    run, monkeypatch, partial_request
):
    ctx, operation, namespace, invoke, calls = run
    folder = ctx.state.path.parent / namespace / operation

    def stop(ctx, path, name, value):
        assert name == "request"
        if partial_request:
            (path / "request.tmp").write_bytes(b'{"schema":')
        raise SystemExit("simulated process loss before request publication")

    with monkeypatch.context() as patch:
        patch.setattr(platform_check, "write_record", stop)
        with pytest.raises(SystemExit):
            invoke()
    inventory = {p.name: p.read_bytes() for p in folder.iterdir()}
    state_only = replace(ctx, snapshot=None, sources=None, graph=None)
    saved = get_platform_run(state_only, operation, namespace=namespace)
    assert saved == {"run_id": operation, "request": None, "status": "incomplete"}
    for _ in range(2):
        with pytest.raises(CoreError) as error:
            invoke()
        assert error.value.code == "PLATFORM_RUN_INCOMPLETE"
        assert error.value.details == {
            "run_id": operation, "status": "incomplete", "request_recorded": False,
        }
        assert {p.name: p.read_bytes() for p in folder.iterdir()} == inventory
    assert not calls
    # Neither result lookup nor retry may reveal this state after revocation.
    with ctx.state.transaction(ctx.principal, write=True) as tx:
        force_legacy_membership(tx, ctx.principal, {"project:read"})
    for action in (invoke, lambda: get_platform_run(state_only, operation, namespace=namespace)):
        with pytest.raises(CoreError) as error:
            action()
        assert error.value.code == "PROJECT_FORBIDDEN"
    assert not calls


def test_legacy_report_remains_readable_but_not_replayable(run):
    ctx, operation, namespace, invoke, calls = run
    report = invoke()
    folder = ctx.state.path.parent / namespace / operation
    (folder / "request.json").unlink()
    state_only = replace(ctx, snapshot=None, sources=None, graph=None)
    saved = get_platform_run(state_only, operation, namespace=namespace)
    assert saved["status"] == "completed" and saved["request"] is None
    assert saved["report"] == report
    with pytest.raises(CoreError) as error:
        invoke()
    assert error.value.code == "PLATFORM_RUN_CONFLICT"
    assert calls == [1]


def test_corrupt_request_does_not_become_unknown_run(run):
    ctx, operation, namespace, invoke, calls = run
    folder = ctx.state.path.parent / namespace / operation
    folder.mkdir(parents=True)
    (folder / "request.json").write_bytes(b'{"schema":')
    for action in (invoke, lambda: get_platform_run(ctx, operation, namespace=namespace)):
        with pytest.raises(CoreError) as error:
            action()
        assert error.value.code == "PLATFORM_RUN_CORRUPT"
    assert not calls
