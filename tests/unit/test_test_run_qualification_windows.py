"""Real Windows retained state, pins and permissions; only the native runner is mocked.

The constructed runner bytes are explicit inputs. Nothing here qualifies 1C.
"""
from dataclasses import replace
import os
from pathlib import Path
import subprocess
from uuid import uuid4

import pytest

import run_qualification_support as support
import test_platform_proposal as fixtures
import test_test_profiles as profile_fixtures
from project_access_test_support import force_legacy_membership
from rentgen_core.errors import CoreError
from rentgen_core import test_execution as execution
from rentgen_core import test_profiles as profiles
from rentgen_core import test_run_qualification as qualification

project, scanner, candidate = fixtures.project, fixtures.scanner, fixtures.candidate
definition = profile_fixtures.definition
pytestmark, LIMITS = fixtures.pytestmark, fixtures.LIMITS


def completed(ctx, raw, definition, monkeypatch, outcomes=("failed", "passed")):
    profile_id = profiles.register_profile(ctx, definition)["profile_id"]

    def run(platform, ibcmd, engine, modules, before, after, target, folder, authorize):
        authorize()
        tests, files = support.runner_outputs(
            str(folder),
            modules,
            target=target,
            baseline=(before / target).read_bytes(),
            candidate=(after / target).read_bytes(),
            outcomes=outcomes,
        )
        for name, data in files.items():
            path = folder / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        return tests

    monkeypatch.setattr(execution, "run_yaxunit", run)
    operation = str(uuid4())
    report = execution.check_proposal_tests(
        ctx, raw, profile_id, operation, limits=LIMITS
    )
    state_only = replace(ctx, snapshot=None, sources=None, graph=None)
    return state_only, operation, report, profile_id


def snapshot(folder):
    return {
        p.relative_to(folder).as_posix(): p.read_bytes()
        for p in sorted(folder.rglob("*"))
        if p.is_file()
    }


def statuses(dossier):
    return {row["id"]: (row["status"], row["detail"]) for row in dossier["checks"]}


def test_retained_run_qualifies_read_only_and_after_profile_disable(
    candidate, definition, monkeypatch
):
    ctx, raw, _ = candidate
    state, operation, report, profile_id = completed(ctx, raw, definition, monkeypatch)
    folder = state.state.path.parent / "test-runs" / operation
    before = snapshot(folder)
    dossier = qualification.qualify_test_run(state, operation)
    assert dossier["qualification"] == "consistent", statuses(dossier)
    assert dossier["report_sha256"] == report["report_sha256"]
    assert dossier["test_result"] == {
        "status": "passed",
        "baseline": "failed",
        "candidate": "passed",
    }
    assert dossier["evidence"] == "local_unattested"
    assert dossier["execution"] == "not_performed"
    assert snapshot(folder) == before
    profiles.disable_profile(ctx, profile_id)
    Path(definition["platform"]["path"]).unlink()
    again = qualification.qualify_test_run(state, operation)
    assert again["qualification"] == "consistent"
    assert again["profile"] == {"profile_id": profile_id, "enabled": False}
    assert snapshot(folder) == before


def test_retained_inputs_are_pinned_during_qualification(
    candidate, definition, monkeypatch
):
    ctx, raw, _ = candidate
    state, operation, report, _ = completed(ctx, raw, definition, monkeypatch)
    folder = state.state.path.parent / "test-runs" / operation
    target = report["source_ref"]["relative_path"]
    original = qualification.evaluate
    attempts = []

    def evaluate(bundle):
        for path in (folder / "candidate" / target, folder / "candidate.junit.xml"):
            with pytest.raises(OSError):
                path.write_bytes(b"tamper during read")
            attempts.append(path)
        return original(bundle)

    monkeypatch.setattr(qualification, "evaluate", evaluate)
    assert qualification.qualify_test_run(state, operation)["qualification"] == (
        "consistent"
    )
    assert len(attempts) == 2


def test_tampered_retained_junit_and_missing_settings_are_reported(
    candidate, definition, monkeypatch
):
    ctx, raw, _ = candidate
    state, operation, _, _ = completed(ctx, raw, definition, monkeypatch)
    folder = state.state.path.parent / "test-runs" / operation
    junit = folder / "baseline.junit.xml"
    junit.write_bytes(junit.read_bytes().replace(b'<failure message="constructed"/>', b""))
    dossier = qualification.qualify_test_run(state, operation)
    assert dossier["qualification"] == "inconsistent"
    assert statuses(dossier)["junit_exit"] == ("mismatch", "BASELINE_JUNIT_INVALID")
    (folder / "candidate-settings.json").unlink()
    assert statuses(qualification.qualify_test_run(state, operation))[
        "runner_settings"
    ] == ("missing", "CANDIDATE_SETTINGS_JSON_ABSENT")


def test_hardlink_and_junction_evidence_never_verify(
    candidate, definition, monkeypatch, tmp_path
):
    ctx, raw, _ = candidate
    state, operation, _, _ = completed(ctx, raw, definition, monkeypatch)
    folder = state.state.path.parent / "test-runs" / operation
    os.link(folder / "candidate" / "Configuration.xml", tmp_path / "alias.xml")
    dossier = qualification.qualify_test_run(state, operation)
    assert statuses(dossier)["input_inventories"] == (
        "mismatch",
        "CANDIDATE_TREE_UNSAFE",
    )
    (tmp_path / "alias.xml").unlink()
    engine = folder / "engine-with-tests"
    moved = tmp_path / "engine-elsewhere"
    engine.rename(moved)
    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(engine), str(moved)],
        check=True,
        capture_output=True,
    )
    dossier = qualification.qualify_test_run(state, operation)
    assert statuses(dossier)["engine_source"] == (
        "mismatch",
        "ENGINE_WITH_TESTS_TREE_UNSAFE",
    )


def test_permissions_are_checked_before_and_after_and_limits_apply(
    candidate, definition, monkeypatch
):
    ctx, raw, _ = candidate
    state, operation, _, _ = completed(ctx, raw, definition, monkeypatch)
    with pytest.raises(CoreError) as error:
        qualification.qualify_test_run(
            state, operation, limits=qualification.QualificationLimits(tree_entries=1)
        )
    assert error.value.code == "TEST_RUN_QUALIFY_LIMIT"
    original = qualification.evaluate

    def revoke(bundle):
        with ctx.state.transaction(ctx.principal, write=True) as tx:
            force_legacy_membership(tx, ctx.principal, {"project:admin"})
        return original(bundle)

    monkeypatch.setattr(qualification, "evaluate", revoke)
    with pytest.raises(CoreError) as error:
        qualification.qualify_test_run(state, operation)
    assert error.value.code == "PROJECT_FORBIDDEN"
    monkeypatch.setattr(qualification, "evaluate", original)
    with pytest.raises(CoreError) as error:
        qualification.qualify_test_run(state, operation)
    assert error.value.code == "PROJECT_FORBIDDEN"


def test_failed_technical_run_is_explicit_and_not_retried(
    candidate, definition, monkeypatch
):
    ctx, raw, _ = candidate
    profile_id = profiles.register_profile(ctx, definition)["profile_id"]
    calls = []

    def fail(*args):
        calls.append(1)
        raise CoreError("PLATFORM_TIMEOUT", "Interrupted native test")

    monkeypatch.setattr(execution, "run_yaxunit", fail)
    operation = str(uuid4())
    with pytest.raises(CoreError):
        execution.check_proposal_tests(ctx, raw, profile_id, operation, limits=LIMITS)
    state = replace(ctx, snapshot=None, sources=None, graph=None)
    dossier = qualification.qualify_test_run(state, operation)
    assert dossier["run_status"] == "failed"
    assert dossier["failure_code"] == "PLATFORM_TIMEOUT"
    assert dossier["qualification"] == "incomplete"
    assert calls == [1]
    with pytest.raises(CoreError) as error:
        qualification.qualify_test_run(state, str(uuid4()))
    assert error.value.code == "PLATFORM_RUN_NOT_FOUND"


def test_cli_returns_the_same_dossier_without_writing(
    candidate, definition, monkeypatch, tmp_path, capsys
):
    import json

    from rentgen_core import cli

    ctx, raw, _ = candidate
    state, operation, _, _ = completed(ctx, raw, definition, monkeypatch)
    folder = state.state.path.parent / "test-runs" / operation
    before = snapshot(folder)
    monkeypatch.setattr(cli, "current_local_principal", lambda: ctx.principal)
    argv = [
        "test-run-qualify",
        "--registry",
        str(tmp_path / "registry.sqlite3"),
        "--project",
        ctx.project_id,
        "--operation-id",
        operation,
    ]
    assert cli.main(argv) == 0
    value = json.loads(capsys.readouterr().out)["result"]
    assert value == qualification.qualify_test_run(state, operation)
    assert value["qualification"] == "consistent"
    assert snapshot(folder) == before
