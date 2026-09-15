"""Owned local EDT workspace and transport; no arbitrary backend connection."""
import asyncio
from contextlib import asynccontextmanager, contextmanager, ExitStack, nullcontext
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
import secrets
import socket
import subprocess
import time

from ._windows_source_tree import pinned_directory
from .edt_execution import EDTClient, guarded_wait, write_record
from .edt_profiles import authorize_run, pinned_runtime
from .errors import CoreError
from .native_process import OwnedProcess
from .native_resources import DiskBudget, project_slot, reserve_run
from .platform_check import _pin_inputs
from .snapshots import validate_operation_id

_ACTIVE_ADMISSION = ContextVar("active_edt_admission", default=None)


def _command(definition, workspace):
    java = definition["java"]["path"]
    vm = [
        "-Xmx4g",
        "-Dorg.osgi.framework.bundle.parent=ext",
        "-Dosgi.module.lock.timeout=240",
        "-Dlog4j.formatMsgNoLookups=true",
        "-Dlog4j2.formatMsgNoLookups=true",
        "-DnativeFormBufferedLayoutRender=true",
        "--add-modules=ALL-SYSTEM",
    ]
    vm += [
        "--add-opens=java.base/" + package + "=ALL-UNNAMED"
        for package in (
            "java.lang",
            "java.lang.constant",
            "java.lang.ref",
            "java.nio",
            "java.time",
            "sun.nio.ch",
            "java.net",
        )
    ]
    return [
        java,
        *vm,
        "-jar",
        str(Path(definition["runtime_root"]) / definition["launcher"]),
        "-data",
        str(workspace),
        "-clean",
        "-nosplash",
        "-consoleLog",
        "--launcher.suppressErrors",
    ]


def _preferences(workspace, port, token):
    prefs = workspace / ".metadata/.plugins/org.eclipse.core.runtime/.settings"
    prefs.mkdir(parents=True)
    text = (
        "eclipse.preferences.version=1\nmcpServerAutoStart=true\n"
        f"mcpServerPort={port}\nmcpAllowRemoteAccess=false\nmcpAuthToken={token}\n"
        "mcpUpdateCheckInterval=never\nmcpDestructiveConsentLevel=per_tool\n"
        "mcpDestructiveAllowedTools=rename_metadata_object\n"
    )
    (prefs / "com.ditrix.edt.mcp.server.prefs").write_text(text, "utf-8")


@dataclass
class _EDTAdmission:
    ctx: object
    profile_id: str
    operation_id: str
    plan: dict
    run: Path
    definition: dict
    job: object
    active: bool = True
    consumed: bool = False

    def claim(self, ctx, profile_id, operation_id, plan):
        if not self.active or self.consumed:
            raise CoreError(
                "EDT_RECONCILIATION_REQUIRED",
                "EDT admission is closed or already consumed",
            )
        if (
            self.ctx is not ctx
            or self.profile_id != profile_id
            or self.operation_id != operation_id
            or self.plan != plan
        ):
            raise CoreError(
                "EDT_INPUT_INVALID", "EDT admission belongs to another request"
            )
        self.consumed = True


@contextmanager
def edt_admission(ctx, profile_id, operation_id, *, plan):
    """Reserve one run before workflow artifacts while holding runtime ownership."""
    from .metadata_plans import validate_plan

    authorize_run(ctx, profile_id)
    plan = validate_plan(ctx, plan)
    validate_operation_id(operation_id)
    root = ctx.state.path.parent
    with project_slot(root) as job, pinned_runtime(ctx, profile_id) as definition:
        parent = root / "metadata-runs"
        parent.mkdir(exist_ok=True)
        with pinned_directory(parent):
            run = parent / operation_id
            try:
                receipt = reserve_run(root, run)
            except FileExistsError as exc:
                raise CoreError(
                    "EDT_RECONCILIATION_REQUIRED",
                    "Operation directory already exists; do not restart",
                ) from exc
            with pinned_directory(run):
                write_record(run / "runtime-admission.json", receipt)
                admitted = _EDTAdmission(
                    ctx, profile_id, operation_id, plan, run, definition, job
                )
                token = _ACTIVE_ADMISSION.set(admitted)
                try:
                    yield admitted
                finally:
                    admitted.active = False
                    _ACTIVE_ADMISSION.reset(token)


@asynccontextmanager
async def edt_session(ctx, profile_id, operation_id, *, plan, admission=None):
    """Internal backend session with validated, retained snapshot inputs.

    An existing operation directory is never restarted. It requires reconciliation
    by the metadata workflow, which also owns snapshot/UUID and apply semantics.
    """
    import httpx
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client
    from .metadata_plans import materialize, validate_plan

    authorize_run(ctx, profile_id)
    plan = validate_plan(ctx, plan)
    validate_operation_id(operation_id)
    root = ctx.state.path.parent
    boundary = (
        edt_admission(ctx, profile_id, operation_id, plan=plan)
        if admission is None
        else nullcontext(admission)
    )
    with boundary as admitted:
        if (
            type(admitted) is not _EDTAdmission
            or _ACTIVE_ADMISSION.get() is not admitted
        ):
            raise CoreError(
                "EDT_INPUT_INVALID", "Expected an active EDT admission handle"
            )
        admitted.claim(ctx, profile_id, operation_id, plan)
        run, definition, job = admitted.run, admitted.definition, admitted.job
        with pinned_directory(run), ExitStack() as input_pins:
            # Keep the snapshot-bound runtime request's exact schema stable.
            write_record(
                run / "runtime-request.json",
                {
                    "schema": 1,
                    "project_id": ctx.project_id,
                    "operation_id": operation_id,
                    "profile_id": profile_id,
                    "plan": plan,
                },
            )
            budget = DiskBudget(root, run)
            budget.check(force=True)
            inventory = materialize(ctx, plan, run / "input")
            input_pins.enter_context(_pin_inputs(run / "input", inventory))
            workspace = run / "workspace"
            token = secrets.token_hex(32)
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            _preferences(workspace, port, token)
            command = _command(definition, workspace)
            with (run / "stdout.log").open("xb") as stdout, (run / "stderr.log").open(
                "xb"
            ) as stderr:
                process = OwnedProcess(
                    subprocess.list2cmdline(command),
                    definition["java"]["path"],
                    stdout,
                    stderr,
                    parent_job=job,
                )
                deadline = time.monotonic() + 600

                def check():
                    authorize_run(ctx, profile_id)
                    budget.check()
                    if process.poll() is not None:
                        raise CoreError(
                            "EDT_PROCESS_EXITED", "EDT exited during the operation"
                        )
                    if time.monotonic() >= deadline:
                        raise CoreError(
                            "EDT_RUNTIME_TIMEOUT",
                            "EDT session exceeded its lifetime",
                        )

                async def health():
                    async with httpx.AsyncClient(trust_env=False, timeout=3) as client:
                        while True:
                            try:
                                response = await client.get(
                                    f"http://127.0.0.1:{port}/health",
                                    headers={"Authorization": "Bearer " + token},
                                )
                                if response.status_code == 200:
                                    return
                                if response.status_code in {401, 403}:
                                    raise CoreError(
                                        "EDT_AUTH_FAILED",
                                        "EDT rejected the owned session token",
                                    )
                            except httpx.TransportError:
                                pass
                            await asyncio.sleep(1)

                def client_factory(headers=None, timeout=None, auth=None):
                    return httpx.AsyncClient(
                        headers=headers, timeout=timeout, auth=auth, trust_env=False
                    )

                try:
                    await guarded_wait(health(), check, 300)
                    async with streamablehttp_client(
                        f"http://127.0.0.1:{port}/mcp",
                        headers={"Authorization": "Bearer " + token},
                        timeout=90,
                        sse_read_timeout=120,
                        httpx_client_factory=client_factory,
                    ) as (read, write, _):
                        async with ClientSession(read, write) as session:
                            initialized = await guarded_wait(
                                session.initialize(), check, 30
                            )
                            if (
                                initialized.serverInfo.name != "edt-mcp-server"
                                or initialized.serverInfo.version != "2.16.1"
                            ):
                                raise CoreError(
                                    "EDT_RUNTIME_MISMATCH",
                                    "Unexpected EDT MCP server identity",
                                )
                            write_record(
                                run / "initialize.json",
                                initialized.model_dump(mode="json"),
                            )
                            client = EDTClient(session, run, check)
                            await client._call(
                                "enable_toolset",
                                {"toolsets": ["project", "metadata", "forms"]},
                            )
                            yield client
                            check()
                finally:
                    process.close()
            authorize_run(ctx, profile_id)
            budget.check(force=True)
            if job.active():
                raise CoreError(
                    "NATIVE_EXECUTOR_BUSY", "EDT descendants have not exited"
                )
            write_record(
                run / "runtime-closed.json",
                {"status": "closed", "metadata_verified": False},
            )
