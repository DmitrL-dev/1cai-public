"""EDT shares native admission while retaining its session and outcome semantics."""
import asyncio
from contextlib import asynccontextmanager, contextmanager, nullcontext
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
import test_metadata_plans as fixtures

from rentgen_core import edt_runtime as runtime, metadata_plans as plans
from rentgen_core import metadata_runs, native_resources as resources
from rentgen_core.errors import CoreError

project, scanner, captured, pytestmark = (
    fixtures.project,
    fixtures.scanner,
    fixtures.captured,
    fixtures.pytestmark,
)


@pytest.fixture
def owned_runtime(captured, monkeypatch):
    import httpx
    import mcp
    import mcp.client.streamable_http

    ctx, request = captured
    operation = str(uuid4())
    state = SimpleNamespace(
        ctx=ctx,
        plan=plans.create_plan(ctx, request),
        profile="a" * 64,
        operation=operation,
        root=ctx.state.path.parent,
        run=metadata_runs.run_path(ctx, operation),
        processes=[],
        calls=[],
        call_error=None,
    )
    limits = resources.DiskLimits(
        run_bytes=1024**2, project_bytes=4 * 1024**2, free_bytes=0
    )
    monkeypatch.setattr(resources, "DiskLimits", lambda: limits)
    monkeypatch.setattr(
        resources.shutil,
        "disk_usage",
        lambda root: SimpleNamespace(free=64 * 1024**3),
    )
    monkeypatch.setattr(runtime, "authorize_run", lambda *args: None)
    monkeypatch.setattr(
        runtime,
        "pinned_runtime",
        lambda *args: nullcontext(
            {
                "java": {"path": "fake-java.exe"},
                "runtime_root": "owned",
                "launcher": "launcher.jar",
            }
        ),
    )

    class Process:
        def __init__(self, command, java, stdout, stderr, *, parent_job):
            self.closed = False
            self.stdout, self.stderr = stdout, stderr
            state.processes.append(self)

        def poll(self):
            return None

        def close(self):
            self.closed = True

    class HTTPClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, *args, **kwargs):
            return SimpleNamespace(status_code=200)

    class Session(HTTPClient):
        def __init__(self, *args):
            pass

        async def initialize(self):
            return SimpleNamespace(
                serverInfo=SimpleNamespace(name="edt-mcp-server", version="2.16.1"),
                model_dump=lambda **kwargs: {
                    "serverInfo": {"name": "edt-mcp-server", "version": "2.16.1"}
                },
            )

        async def call_tool(self, name, arguments):
            state.calls.append(name)
            if state.call_error is not None:
                raise state.call_error
            return SimpleNamespace(
                isError=False,
                structuredContent={"success": True},
                model_dump=lambda **kwargs: {
                    "isError": False,
                    "structuredContent": {"success": True},
                },
            )

    @asynccontextmanager
    async def transport(*args, **kwargs):
        yield None, None, None

    monkeypatch.setattr(runtime, "OwnedProcess", Process)
    monkeypatch.setattr(httpx, "AsyncClient", HTTPClient)
    monkeypatch.setattr(mcp, "ClientSession", Session)
    monkeypatch.setattr(mcp.client.streamable_http, "streamablehttp_client", transport)
    return state


async def _execute(state):
    async with runtime.edt_session(
        state.ctx, state.profile, state.operation, plan=state.plan
    ):
        pass


def test_pre_admitted_session_reserves_once_and_handle_is_single_use(
    owned_runtime, monkeypatch
):
    state = owned_runtime
    reserved = []
    original = runtime.reserve_run

    def reserve(root, run):
        reserved.append(run)
        return original(root, run)

    monkeypatch.setattr(runtime, "reserve_run", reserve)

    async def consume(admission):
        async with runtime.edt_session(
            state.ctx,
            state.profile,
            state.operation,
            plan=state.plan,
            admission=admission,
        ):
            pass

    with runtime.edt_admission(
        state.ctx, state.profile, state.operation, plan=state.plan
    ) as admission:
        assert state.run.is_dir()
        assert not state.processes
        asyncio.run(consume(admission))
        with pytest.raises(CoreError) as error:
            asyncio.run(consume(admission))
        assert error.value.code == "EDT_RECONCILIATION_REQUIRED"
    with pytest.raises(CoreError):
        asyncio.run(consume(admission))
    assert reserved == [state.run]
    assert len(state.processes) == 1 and state.processes[0].closed


def test_pre_admitted_handle_cannot_be_rebound_to_another_operation(owned_runtime):
    state = owned_runtime

    async def rebound(admission):
        async with runtime.edt_session(
            state.ctx, state.profile, str(uuid4()), plan=state.plan, admission=admission
        ):
            pass

    with runtime.edt_admission(
        state.ctx, state.profile, state.operation, plan=state.plan
    ) as admission:
        with pytest.raises(CoreError):
            asyncio.run(rebound(admission))
    assert not state.processes
    assert not (state.run / "runtime-request.json").exists()


def test_copied_admission_handle_cannot_bypass_runtime_ownership(owned_runtime):
    from dataclasses import replace

    state = owned_runtime

    async def consume(admission):
        async with runtime.edt_session(
            state.ctx,
            state.profile,
            state.operation,
            plan=state.plan,
            admission=admission,
        ):
            pass

    with runtime.edt_admission(
        state.ctx, state.profile, state.operation, plan=state.plan
    ) as admission:
        with pytest.raises(CoreError):
            asyncio.run(consume(replace(admission)))
        assert not state.processes
        assert not (state.run / "runtime-request.json").exists()


def test_session_records_admission_without_changing_request_readback(owned_runtime):
    state = owned_runtime

    async def session():
        async with runtime.edt_session(
            state.ctx, state.profile, state.operation, plan=state.plan
        ):
            with pytest.raises(CoreError) as busy:
                with resources.project_slot(state.root):
                    pass
            assert busy.value.code == "NATIVE_EXECUTOR_BUSY"

    asyncio.run(session())
    admission = json.loads((state.run / "runtime-admission.json").read_bytes())
    assert admission["policy"] == "native-admission-v1"
    assert admission["retention"] == "retain_all_no_eviction"
    assert admission["retained_run_limit"] == 256
    assert admission["reserve_bytes"] == 1024**2
    assert metadata_runs._request(state.ctx, state.run, state.operation) == {
        "schema": 1,
        "project_id": state.ctx.project_id,
        "operation_id": state.operation,
        "profile_id": state.profile,
        "plan": state.plan,
    }
    assert json.loads((state.run / "runtime-closed.json").read_bytes()) == {
        "status": "closed",
        "metadata_verified": False,
    }
    assert len(state.processes) == 1 and state.processes[0].closed
    assert state.processes[0].stdout.closed and state.processes[0].stderr.closed


@pytest.mark.parametrize(
    "refusal, code",
    [
        ("retention", "NATIVE_RETENTION_LIMIT"),
        ("free", "NATIVE_STORAGE_LIMIT"),
        ("project", "NATIVE_STORAGE_LIMIT"),
        ("unsafe", "NATIVE_STORAGE_INVALID"),
        ("busy", "NATIVE_ADMISSION_BUSY"),
    ],
)
def test_pre_admission_refusal_creates_no_operation_artifacts(
    owned_runtime, monkeypatch, refusal, code
):
    state = owned_runtime
    previous = state.root / "metadata-runs" / str(uuid4())
    previous.mkdir(parents=True)
    evidence = previous / "runtime-request.json"
    evidence.write_bytes(b"retained intent")
    held = nullcontext()
    if refusal == "retention":
        monkeypatch.setattr(resources, "RETAINED_RUN_LIMIT", 1)
    elif refusal == "free":
        monkeypatch.setattr(
            resources.shutil, "disk_usage", lambda root: SimpleNamespace(free=0)
        )
    elif refusal == "project":
        (previous / "workspace").write_bytes(b"x" * (3 * 1024**2))
    elif refusal == "unsafe":
        (previous.parent / "unexpected-file").write_bytes(b"retained")
    else:
        held = resources._file_slot(
            state.root, "native-admission.lock", "NATIVE_ADMISSION_BUSY"
        )
    with held, pytest.raises(CoreError) as error:
        asyncio.run(_execute(state))
    assert error.value.code == code
    assert error.value.details["admitted"] is False
    assert error.value.details["run_id"] == state.operation
    assert not state.run.exists()
    assert state.processes == [] and state.calls == []
    assert evidence.read_bytes() == b"retained intent"
    with resources.project_slot(state.root):
        pass


@pytest.mark.parametrize("boundary", ["pinned_directory", "_file_slot"])
@pytest.mark.parametrize("filesystem_error", [False, True])
def test_admission_exit_failure_retains_incomplete_uuid_and_never_restarts(
    owned_runtime, monkeypatch, boundary, filesystem_error
):
    state = owned_runtime
    original = getattr(resources, boundary)

    @contextmanager
    def failed_exit(*args, **kwargs):
        with original(*args, **kwargs) as value:
            yield value
        if state.run.exists():
            if filesystem_error:
                raise OSError("injected exit failure")
            raise CoreError("INJECTED_EXIT_FAILURE", "Injected exit failure")

    with monkeypatch.context() as patch:
        patch.setattr(resources, boundary, failed_exit)
        with pytest.raises(CoreError) as error:
            asyncio.run(_execute(state))
    assert error.value.code == "NATIVE_ADMISSION_INCOMPLETE"
    assert error.value.details == {
        "run_id": state.operation,
        "admitted": True,
        "status": "incomplete",
        "cause": "FILESYSTEM_ERROR" if filesystem_error else "INJECTED_EXIT_FAILURE",
    }
    assert state.run.is_dir() and not list(state.run.iterdir())
    with pytest.raises(CoreError) as replay:
        asyncio.run(_execute(state))
    assert replay.value.code == "EDT_RECONCILIATION_REQUIRED"
    assert state.processes == []
    state.operation = str(uuid4())
    state.run = metadata_runs.run_path(state.ctx, state.operation)
    asyncio.run(_execute(state))
    assert len(state.processes) == 1 and state.processes[0].closed


def test_project_busy_precedes_admission_and_existing_operation_is_not_restarted(
    owned_runtime, monkeypatch
):
    state = owned_runtime
    with resources.project_slot(state.root), pytest.raises(CoreError) as error:
        asyncio.run(_execute(state))
    assert error.value.code == "NATIVE_EXECUTOR_BUSY"
    assert not state.run.exists() and not state.processes
    state.run.mkdir(parents=True)
    request = state.run / "runtime-request.json"
    request.write_bytes(b"old runtime intent")
    monkeypatch.setattr(resources, "RETAINED_RUN_LIMIT", 1)
    with pytest.raises(CoreError) as replay:
        asyncio.run(_execute(state))
    assert replay.value.code == "EDT_RECONCILIATION_REQUIRED"
    assert request.read_bytes() == b"old runtime intent"
    assert not state.processes


def test_unknown_call_closes_process_retains_outcome_and_releases_slot(owned_runtime):
    state = owned_runtime
    state.call_error = OSError("transport failed after request")
    with pytest.raises(CoreError) as error:
        asyncio.run(_execute(state))
    assert error.value.code == "EDT_OUTCOME_UNKNOWN"
    assert state.calls == ["enable_toolset"]
    assert json.loads((state.run / "001-outcome.json").read_bytes()) == {
        "status": "unknown"
    }
    assert (state.run / "001-request.json").exists()
    assert not (state.run / "001-response.json").exists()
    assert not (state.run / "runtime-closed.json").exists()
    assert len(state.processes) == 1 and state.processes[0].closed
    assert state.processes[0].stdout.closed and state.processes[0].stderr.closed
    with pytest.raises(CoreError) as replay:
        asyncio.run(_execute(state))
    assert replay.value.code == "EDT_RECONCILIATION_REQUIRED"
    assert state.calls == ["enable_toolset"]
    with resources.project_slot(state.root):
        pass


@pytest.mark.parametrize("failure", [OSError, asyncio.CancelledError])
def test_session_failure_closes_runtime_and_retains_workspace(owned_runtime, failure):
    state = owned_runtime
    injected = failure("interrupted metadata workflow")

    async def interrupted():
        async with runtime.edt_session(
            state.ctx, state.profile, state.operation, plan=state.plan
        ):
            raise injected

    with pytest.raises(failure) as error:
        asyncio.run(interrupted())
    assert error.value is injected
    assert len(state.processes) == 1 and state.processes[0].closed
    assert state.processes[0].stdout.closed and state.processes[0].stderr.closed
    assert (state.run / "workspace").is_dir()
    assert (state.run / "input").is_dir()
    assert (state.run / "runtime-request.json").exists()
    assert not (state.run / "runtime-closed.json").exists()
    with resources.project_slot(state.root):
        pass
