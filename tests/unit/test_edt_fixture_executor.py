"""Owned fixture execution records outcomes without launching the 1C platform."""
from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from uuid import uuid4

import pytest
from project_access_test_support import force_legacy_membership

import rentgen_core as core
from rentgen_core import edt_command as commands
from rentgen_core import edt_fixture_executor as executor
from rentgen_core import native_resources as resources
from rentgen_core.edt_inventory import exported_inventory
from rentgen_core.errors import CoreError
from rentgen_core.manifests import canonical_bytes, sha256

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows owned fixture")


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    (source / "keep.txt").write_bytes(b"live source")
    principal = core.Principal("owner", "local_os")
    registry = core.ProjectRegistry.create(tmp_path / "registry.sqlite3")
    registered = registry.register(
        principal, source_root=source, state_root=tmp_path / "state", display_name="A"
    )
    ctx = core.ContextResolver(registry).resolve_context(
        principal, core.Explicit(registered.project_id)
    )
    root = ctx.state.path.parent
    inputs = root / "fixture-inputs" / "created"
    inputs.mkdir(parents=True)
    (inputs / "Configuration.xml").write_bytes(b"<configuration />")
    binary = root / "toolchain" / "ibcmd.exe"
    binary.parent.mkdir()
    binary.write_bytes(b"fake ibcmd fixture binary")
    profile = commands.IBCmdProfile(
        str(binary), commands.SUPPORTED_VERSION, sha256(binary.read_bytes())
    )
    rows = exported_inventory(inputs, authorize=lambda: None)
    request = commands.FixtureCommandRequest(
        str(uuid4()), sha256(canonical_bytes(rows))
    )
    plan = commands.plan_fixture_commands(profile, request, fixture_root=str(root))
    state = SimpleNamespace(
        ctx=ctx,
        root=root,
        inputs=inputs,
        binary=binary,
        profile=profile,
        request=request,
        plan=plan,
        run=Path(plan.commands[0].cwd),
        calls=[],
        mode="success",
        closed=[],
        source=source,
        at_launch=None,
    )
    limits = resources.DiskLimits(
        run_bytes=8 * 1024**2, project_bytes=64 * 1024**2, free_bytes=0
    )
    monkeypatch.setattr(executor, "DISK_LIMITS", limits)

    class Process:
        def __init__(self, command, executable, stdout, stderr, *, parent_job, cwd):
            index = len(state.calls)
            assert cwd == str(state.run)
            assert executable == str(binary)
            assert command == subprocess.list2cmdline(state.plan.commands[index].argv)
            assert (state.run / "request.json").is_file()
            assert (state.run / f"{index + 1:03d}-request.json").is_file()
            state.calls.append(command)
            if state.at_launch:
                state.at_launch()
            self.index = index
            self.returncode = 9 if state.mode == "nonzero" else 0
            if state.mode == "output":
                stdout.write(b"x" * (2 * 1024**2 + 1))
                stdout.flush()
            if state.mode == "success":
                if index == 0:
                    (state.run / "infobase").mkdir()
                    (state.run / "infobase" / "1Cv8.1CD").write_bytes(b"owned base")
                elif index == 1:
                    (state.run / "candidate.cf").write_bytes(b"candidate")
                else:
                    (state.run / "roundtrip").mkdir()
                    (state.run / "roundtrip" / "Configuration.xml").write_bytes(
                        b"<configuration />"
                    )

        def poll(self):
            if state.mode == "timeout":
                raise TimeoutError("injected timeout")
            return self.returncode

        def close(self):
            state.closed.append(self.index)
            if state.mode == "cleanup":
                raise CoreError("NATIVE_CLEANUP_TIMEOUT", "injected cleanup failure")

    monkeypatch.setattr(executor, "OwnedProcess", Process)
    return state


def execute(state):
    return executor.execute_fixture_commands(
        state.ctx,
        state.plan,
        state.profile,
        state.request,
        fixture_root=str(state.root),
        input_root=str(state.inputs),
    )


def read_result(state):
    return executor.get_fixture_result(
        state.ctx, state.request.operation_id, fixture_root=str(state.root)
    )


def test_executes_exact_plan_with_durable_intent_and_readable_receipt(fixture):
    result = execute(fixture)
    assert result["status"] == "completed"
    assert result["live_apply_allowed"] is False
    assert result["metadata_verified"] is False
    assert fixture.closed == [0, 1, 2]
    assert len(fixture.calls) == 3
    assert read_result(fixture) == result
    assert (fixture.source / "keep.txt").read_bytes() == b"live source"
    assert (fixture.run / "infobase" / "1Cv8.1CD").read_bytes() == b"owned base"


def test_argv_tampering_refuses_before_admission_or_process(fixture):
    first = replace(
        fixture.plan.commands[0], argv=(fixture.profile.executable, "config", "apply")
    )
    fixture.plan = replace(fixture.plan, commands=(first, *fixture.plan.commands[1:]))
    with pytest.raises(CoreError, match="Invalid ibcmd"):
        execute(fixture)
    assert fixture.calls == [] and not fixture.run.exists()


@pytest.mark.parametrize("change", ["binary", "input"])
def test_changed_bytes_refuse_before_admission(fixture, change):
    target = (
        fixture.binary if change == "binary" else fixture.inputs / "Configuration.xml"
    )
    target.write_bytes(b"changed")
    with pytest.raises(CoreError):
        execute(fixture)
    assert not fixture.run.exists() and fixture.calls == []


@pytest.mark.parametrize("mode", ["timeout", "output", "cleanup"])
def test_unconfirmed_execution_is_retained_and_never_restarted(fixture, mode):
    fixture.mode = mode
    with pytest.raises(CoreError):
        execute(fixture)
    result = read_result(fixture)
    assert result["status"] == "OUTCOME_UNKNOWN"
    assert fixture.closed == [0]
    assert len(fixture.calls) == 1
    assert (fixture.run / "001-request.json").is_file()
    assert (fixture.run / "001-outcome.json").is_file()
    assert not (fixture.run / "002-request.json").exists()
    assert sum(p.stat().st_size for p in fixture.run.glob("*.log")) <= 2 * 1024**2
    with pytest.raises(CoreError) as error:
        execute(fixture)
    assert error.value.code == "EDT_FIXTURE_CONFLICT"
    assert len(fixture.calls) == 1


def test_existing_empty_run_is_not_adopted_or_removed(fixture):
    fixture.run.mkdir(parents=True)
    (fixture.run / "keep").write_bytes(b"foreign")
    with pytest.raises(CoreError) as error:
        execute(fixture)
    assert error.value.code == "EDT_FIXTURE_CONFLICT"
    assert fixture.calls == []
    assert (fixture.run / "keep").read_bytes() == b"foreign"


def test_nonzero_exit_stops_sequence_with_known_failure(fixture):
    fixture.mode = "nonzero"
    with pytest.raises(CoreError):
        execute(fixture)
    assert read_result(fixture)["status"] == "failed"
    assert fixture.closed == [0] and len(fixture.calls) == 1


def test_lost_terminal_receipt_is_unknown_without_replay(fixture):
    execute(fixture)
    (fixture.run / "report.json").unlink()
    assert read_result(fixture)["status"] == "OUTCOME_UNKNOWN"
    with pytest.raises(CoreError):
        execute(fixture)
    assert len(fixture.calls) == 3


def test_readback_rejects_foreign_resealed_receipt(fixture):
    result = execute(fixture)
    result["request_id"] = "f" * 64
    result = executor._seal(
        {k: v for k, v in result.items() if k != "result_id"}, "result_id"
    )
    (fixture.run / "report.json").write_bytes(canonical_bytes(result))
    with pytest.raises(CoreError) as error:
        read_result(fixture)
    assert error.value.code == "EDT_FIXTURE_RECOVERY_REQUIRED"


def test_input_and_binary_are_pinned_through_spawn(fixture):
    def attempt_write():
        for path in (
            fixture.binary,
            fixture.inputs / "Configuration.xml",
            fixture.run / "input" / "Configuration.xml",
        ):
            with pytest.raises(PermissionError):
                path.write_bytes(b"tamper")

    fixture.at_launch = attempt_write
    assert execute(fixture)["status"] == "completed"


def test_owned_process_honors_explicit_cwd(tmp_path):
    from rentgen_core.native_process import OwnedProcess

    with (tmp_path / "stdout").open("wb") as out, (tmp_path / "stderr").open(
        "wb"
    ) as err:
        with OwnedProcess(
            subprocess.list2cmdline(
                [sys.executable, "-c", "import os;print(os.getcwd())"]
            ),
            sys.executable,
            out,
            err,
            cwd=str(tmp_path),
        ) as process:
            assert process.wait(10) == 0
    assert (tmp_path / "stdout").read_text().strip() == str(tmp_path)


def test_permission_revocation_precedes_new_run_and_stops_next_command(fixture):
    def revoke():
        with fixture.ctx.state.transaction(fixture.ctx.principal, write=True) as tx:
            force_legacy_membership(tx, fixture.ctx.principal, {"project:read"})

    fixture.at_launch = revoke
    with pytest.raises(CoreError):
        execute(fixture)
    assert fixture.closed == [0] and len(fixture.calls) == 1
    with pytest.raises(CoreError) as error:
        read_result(fixture)
    assert error.value.code == "PROJECT_FORBIDDEN"


def test_resealed_foreign_input_locator_is_not_valid_readback(fixture):
    execute(fixture)
    path = fixture.run / "request.json"
    value = json.loads(path.read_bytes())
    value["input_root"] = str(fixture.source)
    value = executor._seal(
        {k: v for k, v in value.items() if k != "request_id"}, "request_id"
    )
    path.write_bytes(canonical_bytes(value))
    (fixture.run / "report.json").unlink()
    with pytest.raises(CoreError):
        read_result(fixture)


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema", True),
        ("step_ids", "invalid"),
        ("cleanup", {"process_tree": "arbitrary", "artifacts": "retained"}),
    ],
)
def test_resealed_invalid_failure_schema_is_rejected(fixture, field, value):
    fixture.mode = "timeout"
    with pytest.raises(CoreError):
        execute(fixture)
    path = fixture.run / "failure.json"
    record = json.loads(path.read_bytes())
    record[field] = value
    record = executor._seal(
        {k: v for k, v in record.items() if k != "result_id"}, "result_id"
    )
    path.write_bytes(canonical_bytes(record))
    with pytest.raises(CoreError) as error:
        read_result(fixture)
    assert error.value.code == "EDT_FIXTURE_RECOVERY_REQUIRED"


def test_completed_fixture_can_be_archived_without_deleting_or_restarting(fixture):
    result = execute(fixture)
    receipt = resources.archive_native_run(
        fixture.ctx,
        fixture.request.operation_id,
        namespace="ibcmd-fixtures",
        profile_id=result["profile_id"],
    )
    assert receipt["status"] == "archived"
    assert read_result(fixture) == result
    assert (fixture.run / "candidate.cf").read_bytes() == b"candidate"
    with pytest.raises(CoreError):
        execute(fixture)
    assert len(fixture.calls) == 3


def test_unknown_fixture_cannot_release_retention_by_archive(fixture):
    fixture.mode = "timeout"
    with pytest.raises(CoreError):
        execute(fixture)
    result = read_result(fixture)
    with pytest.raises(CoreError):
        resources.archive_native_run(
            fixture.ctx,
            fixture.request.operation_id,
            namespace="ibcmd-fixtures",
            profile_id=result["profile_id"],
        )


def test_admin_only_can_archive_valid_fixture_without_execution_permissions(fixture):
    result = execute(fixture)
    with fixture.ctx.state.transaction(fixture.ctx.principal, write=True) as tx:
        force_legacy_membership(
            tx, fixture.ctx.principal, {"project:read", "project:admin"}
        )
    with pytest.raises(CoreError) as error:
        read_result(fixture)
    assert error.value.code == "PROJECT_FORBIDDEN"
    receipt = resources.archive_native_run(
        fixture.ctx,
        fixture.request.operation_id,
        namespace="ibcmd-fixtures",
        profile_id=result["profile_id"],
    )
    assert receipt["status"] == "archived"
    assert len(fixture.calls) == 3
    assert (fixture.run / "candidate.cf").read_bytes() == b"candidate"


def test_missing_terminal_readback_rechecks_revoked_permissions(fixture, monkeypatch):
    execute(fixture)
    (fixture.run / "report.json").unlink()
    original = executor._read

    def revoke_after_intent(path, key):
        result = original(path, key)
        if path.name == "request.json":
            with fixture.ctx.state.transaction(fixture.ctx.principal, write=True) as tx:
                force_legacy_membership(tx, fixture.ctx.principal, {"project:read"})
        return result

    monkeypatch.setattr(executor, "_read", revoke_after_intent)
    with pytest.raises(CoreError) as error:
        read_result(fixture)
    assert error.value.code == "PROJECT_FORBIDDEN"


def test_fixture_admission_counts_existing_native_namespaces(fixture, monkeypatch):
    existing = fixture.root / "metadata-runs" / str(uuid4())
    existing.mkdir(parents=True)
    monkeypatch.setattr(resources, "RETAINED_RUN_LIMIT", 1)
    with pytest.raises(CoreError) as error:
        execute(fixture)
    assert error.value.code == "NATIVE_RETENTION_LIMIT"
    assert not fixture.run.exists() and fixture.calls == []


def test_candidate_is_pinned_while_export_process_is_running(fixture):
    def attempt_write():
        if len(fixture.calls) == 3:
            with pytest.raises(PermissionError):
                (fixture.run / "candidate.cf").write_bytes(b"foreign candidate")

    fixture.at_launch = attempt_write
    assert execute(fixture)["status"] == "completed"


def test_actual_deadline_expires_before_following_command(fixture, monkeypatch):
    clock = SimpleNamespace(value=1000)
    monkeypatch.setattr(
        executor,
        "time",
        SimpleNamespace(monotonic=lambda: clock.value, sleep=lambda _: None),
    )
    fixture.at_launch = lambda: setattr(clock, "value", clock.value + 121)
    with pytest.raises(CoreError) as error:
        execute(fixture)
    assert error.value.code == "EDT_FIXTURE_TIMEOUT"
    assert fixture.closed == [0] and len(fixture.calls) == 1


def test_resealed_step_index_cannot_justify_completion(fixture):
    result = execute(fixture)
    path = fixture.run / "001-outcome.json"
    outcome = json.loads(path.read_bytes())
    outcome["index"] = 99
    outcome = executor._seal(
        {k: v for k, v in outcome.items() if k != "outcome_id"}, "outcome_id"
    )
    path.write_bytes(canonical_bytes(outcome))
    result["step_ids"][0] = outcome["outcome_id"]
    result = executor._seal(
        {k: v for k, v in result.items() if k != "result_id"}, "result_id"
    )
    (fixture.run / "report.json").write_bytes(canonical_bytes(result))
    with pytest.raises(CoreError):
        read_result(fixture)


@pytest.mark.parametrize("change_step", [False, True])
def test_unknown_failure_cannot_be_resealed_as_known_failure(fixture, change_step):
    fixture.mode = "timeout"
    with pytest.raises(CoreError):
        execute(fixture)
    path = fixture.run / "failure.json"
    result = json.loads(path.read_bytes())
    result["status"] = "failed"
    if change_step:
        step_path = fixture.run / "001-outcome.json"
        step = json.loads(step_path.read_bytes())
        step["status"] = "failed"
        step = executor._seal(
            {k: v for k, v in step.items() if k != "outcome_id"}, "outcome_id"
        )
        step_path.write_bytes(canonical_bytes(step))
        result["step_ids"][0] = step["outcome_id"]
    result = executor._seal(
        {k: v for k, v in result.items() if k != "result_id"}, "result_id"
    )
    path.write_bytes(canonical_bytes(result))
    with pytest.raises(CoreError):
        read_result(fixture)


def test_real_child_output_is_bounded_through_inherited_pipes(tmp_path):
    from rentgen_core.native_process import OwnedProcess

    capture = executor._Capture(tmp_path, "001", 128)
    try:
        with OwnedProcess(
            subprocess.list2cmdline(
                [sys.executable, "-c", "import sys;sys.stdout.write('x'*1024)"]
            ),
            sys.executable,
            *capture.writers,
            cwd=str(tmp_path),
        ) as process:
            capture.close_writers()
            assert process.wait(10) == 0
    finally:
        capture.finish()
    with pytest.raises(CoreError) as error:
        capture.check()
    assert error.value.code == "EDT_FIXTURE_OUTPUT_LIMIT"
    assert sum(path.stat().st_size for path in tmp_path.glob("*.log")) == 128
