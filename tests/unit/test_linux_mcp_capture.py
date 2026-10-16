"""Actual Linux source SDK stdio acceptance; not installed/offline SDK closure."""
import asyncio
import base64
from contextlib import asynccontextmanager
from datetime import timedelta
import hashlib
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
from time import monotonic
from uuid import uuid4

import pytest

from test_linux_capture import scanner

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(
    sys.platform != "linux" or platform.machine() not in {"x86_64", "amd64"},
    reason="Actual Linux/amd64 Go capture through real SDK stdio subprocess",
)
CALLER = "CommonModules/Caller/Ext/Module.bsl"
CALLEE = "CommonModules/Callee/Ext/Module.bsl"


def command(*args):
    result = subprocess.run([sys.executable, "-m", "rentgen_core", *map(str, args)],
        cwd=ROOT, capture_output=True, timeout=30)
    assert result.returncode == 0, "Fixture CLI command failed: " + str(args[0])
    assert not result.stderr and len(result.stdout) <= 1024**2
    document = json.loads(result.stdout)
    assert "result" in document
    return document["result"]


@pytest.fixture
def local_project(tmp_path):
    private = tmp_path.resolve() / "private"; private.mkdir(mode=0o700)
    profile = private / "identity" / "identity.json"
    registry = private / "registry.sqlite3"
    command("identity-init", "--identity-profile", profile)
    common = ["--registry", registry, "--identity-profile", profile]
    command("registry-init", *common)
    source = tmp_path.resolve() / "source"; source.mkdir()
    images = {
        CALLER: b"Procedure Caller() Export\nValue = Callee.Target();\nEndProcedure\n",
        CALLEE: b"Function Target() Export\nReturn 1;\nEndFunction\n",
        "Configuration.xml": b"<Configuration/>", "fixture.bin": b"\xff\0",
    }
    for relative, raw in images.items():
        path = source / relative; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
    registered = command("project-register", *common, "--source-root", source,
        "--state-root", private / "state", "--name", "Owned SDK capture fixture")
    return dict(profile=profile, registry=registry, common=common, source=source,
                project_id=registered["project_id"], images=images, private=private)


async def call(session, name, args):
    result = await session.call_tool(name, args, read_timeout_seconds=timedelta(seconds=90))
    error = (result.structuredContent or {}).get("error", {})
    assert not result.isError, (name, error.get("code"))
    return result.structuredContent["result"]


@asynccontextmanager
async def server(project, scanner_backend, stderr_path, monkeypatch, *, observe_request=None):
    """Observe the original SDK process factory; do not replace its subprocess."""
    import anyio
    from mcp import ClientSession, StdioServerParameters
    import mcp.client.stdio as transport

    processes = []
    original = transport._create_platform_compatible_process
    async def record_process(*args, **kwargs):
        process = await original(*args, **kwargs)
        processes.append(process)
        return process
    class ObservedWrite:
        def __init__(self, stream): self.stream = stream
        async def send(self, message):
            root = message.message.root
            if getattr(root, "method", None) == "tools/call" and root.params.get("name") == "rentgen_capture":
                observe_request(root.id)
            await self.stream.send(message)
        async def __aenter__(self): await self.stream.__aenter__(); return self
        async def __aexit__(self, *args): return await self.stream.__aexit__(*args)
        async def aclose(self): await self.stream.aclose()
    args = ["-m", "rentgen_core.stdio_mcp", "--registry", str(project["registry"]),
            "--identity-profile", str(project["profile"]), "--project", project["project_id"]]
    if scanner_backend is not None:
        args += ["--scanner", str(scanner_backend.scanner_executable),
                 "--scanner-sha256", scanner_backend.scanner_sha256]
    params = StdioServerParameters(command=sys.executable, args=args, cwd=str(ROOT))
    with monkeypatch.context() as patched, stderr_path.open("w", encoding="utf-8") as errors:
        patched.setattr(transport, "_create_platform_compatible_process", record_process)
        try:
            with anyio.fail_after(120):
                async with transport.stdio_client(params, errlog=errors) as (read, write):
                    async with ClientSession(read, ObservedWrite(write) if observe_request else write) as session:
                        await session.initialize()
                        assert len(processes) == 1
                        yield session, processes[0].pid
        finally:
            # The SDK's real context closes stdin, waits and escalates if needed.
            # Its process object must show that it reaped this exact child.
            assert all(process.returncode is not None for process in processes)
    assert stderr_path.stat().st_size <= 1024**2  # Keep fixture diagnostics private.


def source_args(project, snapshot, relative=CALLEE):
    return dict(project_id=project["project_id"], snapshot_id=snapshot,
                layer_id="base", relative_path=relative)


async def read_exact(session, project, snapshot, expected):
    result = await call(session, "rentgen_source_read", source_args(project, snapshot))
    raw = base64.b64decode(result["data"], validate=True)
    assert raw == expected and result["size_bytes"] == len(expected)
    assert result["raw_sha256"] == hashlib.sha256(expected).hexdigest()


def test_native_sdk_stdio_capture_read_graph_replay_and_historical_bytes(local_project, scanner, tmp_path, monkeypatch):
    project = local_project
    async def scenario():
        operation = str(uuid4())
        async with server(project, scanner, tmp_path / "capture-sdk.stderr", monkeypatch) as (session, _):
            names = {tool.name for tool in (await session.list_tools()).tools}
            assert {"rentgen_capture", "rentgen_source_list", "rentgen_source_read",
                    "rentgen_graph_resolve", "rentgen_impact", "rentgen_publication_receipt"} <= names
            assert "rentgen_proposal_live_apply" not in names
            head = await call(session, "rentgen_project_head", {"project_id": project["project_id"]})
            first = await call(session, "rentgen_capture", dict(project_id=project["project_id"],
                operation_id=operation, expected_head=head))
            snapshot = first["snapshot"]["snapshot_id"]
            assert first["head"]["revision"] == head["revision"] + 1
            page_args = dict(project_id=project["project_id"], snapshot_id=snapshot, kind="module", limit=1)
            page = await call(session, "rentgen_source_list", page_args)
            assert len(page["entries"]) == 1 and page["next_cursor"]
            following = await call(session, "rentgen_source_list", page_args | {"cursor": page["next_cursor"]})
            assert following["next_cursor"] is None
            assert {entry["ref"]["relative_path"] for entry in page["entries"] + following["entries"]} == {CALLER, CALLEE}
            await read_exact(session, project, snapshot, project["images"][CALLEE])
            resolved = await call(session, "rentgen_graph_resolve", source_args(project, snapshot))
            assert [row["source_path"] for row in resolved["result"]["graph_modules"]] == ["base/" + CALLEE]
            impacted = await call(session, "rentgen_impact", source_args(project, snapshot) | {"depth": 5})
            assert impacted["result"]["entry_subroutines"] == 1 and impacted["result"]["total"] == 1
            changed = project["images"][CALLEE].replace(b"Return 1", b"Return 2")
            (project["source"] / CALLEE).write_bytes(changed)
            second = await call(session, "rentgen_capture", dict(project_id=project["project_id"],
                operation_id=str(uuid4()), expected_head=first["head"]))
            assert second["snapshot"] != first["snapshot"]
            assert second["head"]["revision"] == first["head"]["revision"] + 1
        # Source location is now unavailable. Start a fresh real SDK server with
        # no scanner: only committed receipts and retained snapshots may serve it.
        project["source"].rename(tmp_path / "source-relocated")
        async with server(project, None, tmp_path / "replay-sdk.stderr", monkeypatch) as (session, _):
            replay = await call(session, "rentgen_capture", dict(project_id=project["project_id"],
                operation_id=operation, expected_head=head))
            assert replay == first
            receipt = await call(session, "rentgen_publication_receipt", dict(project_id=project["project_id"], operation_id=operation))
            assert receipt == first
            await read_exact(session, project, snapshot, project["images"][CALLEE])
            await read_exact(session, project, second["snapshot"]["snapshot_id"], changed)
            old = await call(session, "rentgen_graph_resolve", source_args(project, snapshot))
            assert old == resolved
    asyncio.run(scenario())


def test_manual_draft_cli_and_sdk_share_history_without_live_writes(local_project, scanner, tmp_path, monkeypatch):
    project = local_project
    replacement = project["images"][CALLEE].replace(b"Return 1", b"Return 2")

    async def scenario():
        async with server(project, scanner, tmp_path / "draft-sdk.stderr", monkeypatch) as (session, _):
            head = await call(session, "rentgen_project_head", {"project_id": project["project_id"]})
            captured = await call(session, "rentgen_capture", dict(project_id=project["project_id"],
                operation_id=str(uuid4()), expected_head=head))
            pin = dict(project_id=project["project_id"], snapshot_id=captured["snapshot"]["snapshot_id"])
            page = await call(session, "rentgen_source_list", pin | {"kind": "module"})
            ref = next(row["ref"] for row in page["entries"] if row["ref"]["relative_path"] == CALLEE)
            proposed = await call(session, "rentgen_proposal_create", pin | {
                "source_ref": ref, "replacement_base64": base64.b64encode(replacement).decode("ascii")})
            assert proposed["diff"]["status"] == "complete" and "Return 2" in proposed["diff"]["text"]
            raw_draft = str(uuid4())
            saved = await call(session, "rentgen_draft_save", pin | {
                "draft_id": raw_draft, "operation_id": str(uuid4()), "expected_revision": 0,
                "title": "Raw SDK draft", "proposal": proposed["proposal"]})
            assert saved["draft"]["revision"] == 1
            draft = str(uuid4())
            started = await call(session, "rentgen_draft_start", pin | {
                "draft_id": draft, "operation_id": str(uuid4()), "title": "SDK draft", "source_ref": ref})
            assert started["draft"]["revision"] == 1
            edit_args = pin | {"draft_id": draft, "operation_id": str(uuid4()), "expected_revision": 1,
                              "edits": [{"old_text": "Return 1", "new_text": "Return 2"}]}
            edited = await call(session, "rentgen_draft_edit", edit_args)
            assert edited["draft"]["revision"] == 2
            assert await call(session, "rentgen_draft_edit", edit_args) == edited
            rejected = await session.call_tool("rentgen_draft_edit", edit_args | {"operation_id": str(uuid4())})
            assert rejected.isError and rejected.structuredContent["error"]["code"] == "DRAFT_CONFLICT"
            history = await call(session, "rentgen_draft_history", {"project_id": project["project_id"], "draft_id": draft})
            assert [row["revision"] for row in history["draft"]["items"]] == [2, 1]
            assert await call(session, "rentgen_project_head", {"project_id": project["project_id"]}) == captured["head"]
            await read_exact(session, project, pin["snapshot_id"], project["images"][CALLEE])
            return pin, ref, draft, captured["head"]

    pin, ref, sdk_draft, head = asyncio.run(scenario())
    common = [*project["common"], "--project", project["project_id"]]
    selected = [*common, "--snapshot", pin["snapshot_id"]]
    ref_path, edits_path = tmp_path / "source-ref.json", tmp_path / "edits.json"
    ref_path.write_text(json.dumps(ref), encoding="utf-8")
    edits_path.write_text(json.dumps([{"old_text": "Return 2", "new_text": "Return 3"}]), encoding="utf-8")
    # The separate CLI process sees the SDK's exact revision and advances it.
    edited = command("draft-edit", *selected, "--draft-id", sdk_draft, "--expected-revision", 2,
                     "--operation-id", str(uuid4()), "--edits-json", edits_path)
    assert edited["revision"] == 3
    history = command("draft-history", *common, "--draft-id", sdk_draft)
    assert [row["revision"] for row in history["items"]] == [3, 2, 1]
    readback = command("draft-get", *common, "--draft-id", sdk_draft)
    assert readback["receipt"] == edited
    assert base64.b64decode(readback["proposal"]["replacement"]["base64"], validate=True) == replacement.replace(b"Return 2", b"Return 3")
    started = command("draft-start", *selected, "--draft-id", str(uuid4()),
                      "--operation-id", str(uuid4()), "--source-ref-json", ref_path, "--title", "CLI draft")
    assert started["revision"] == 1
    replacement_path = tmp_path / "replacement.bsl"
    replacement_path.write_bytes(replacement)
    proposed = command("proposal-create", *selected, "--source-ref-json", ref_path, "--replacement-file", replacement_path)
    proposal_path = tmp_path / "proposal.json"
    proposal_path.write_text(json.dumps(proposed["proposal"]), encoding="utf-8")
    diff = command("proposal-diff", *selected, "--proposal-json", proposal_path)
    assert diff["diff"]["status"] == "complete" and "Return 2" in diff["diff"]["text"]
    saved = command("draft-save", *selected, "--draft-id", str(uuid4()), "--expected-revision", 0,
                    "--operation-id", str(uuid4()), "--proposal-json", proposal_path, "--title", "CLI raw draft")
    assert saved["revision"] == 1
    assert command("project-head", *common) == head
    assert {name: (project["source"] / name).read_bytes() for name in project["images"]} == project["images"]


def process_stat(pid):
    try:
        raw = (Path("/proc") / str(pid) / "stat").read_text()
    except FileNotFoundError:
        return None
    fields = raw.rsplit(")", 1)[1].split()
    return fields[0], int(fields[1]), int(fields[19])  # state, parent PID, start ticks


def owned_scanner(server_pid):
    """Inspect only the known test SDK server's own threads and direct children."""
    children = set()
    tasks = list((Path("/proc") / str(server_pid) / "task").glob("*/children"))
    assert len(tasks) <= 64
    for path in tasks:
        try: raw = path.read_bytes()
        except FileNotFoundError: continue
        assert len(raw) <= 4096
        children.update(int(value) for value in raw.split())
    for pid in children:
        try:
            with (Path("/proc") / str(pid) / "cmdline").open("rb") as stream: raw = stream.read(8193)
        except FileNotFoundError:
            continue
        assert len(raw) <= 8192
        args = raw.rstrip(b"\0").split(b"\0")
        status = process_stat(pid)
        if (len(args) == 16 and args[1] == b"--owned-linux-v1"
                and args[2] == str(server_pid).encode() and status is not None and status[1] == server_pid):
            # Owned Go deliberately sets PR_SET_DUMPABLE=0. Its private fds/exe
            # cannot be inspected by this sibling observer after sandbox setup.
            # PID/parent/start identity plus exact owned-protocol argv identify
            # the actual configured child; a live child is necessarily pre-CAS.
            return pid, status[2]
    return None


def same_child(identity, server_pid):
    status = process_stat(identity[0])
    return status if status is not None and status[1:] == (server_pid, identity[1]) else None


def child_alive(identity):
    status = process_stat(identity[0])
    return status if status is not None and status[2] == identity[1] else None


async def wait_child_gone(identity, server_pid):
    deadline = monotonic() + 8
    while child_alive(identity) is not None:
        assert monotonic() < deadline, "Owned scanner was not reaped"
        await asyncio.sleep(0.01)


def test_native_sdk_real_cancel_notification_stops_owned_child_before_commit(local_project, scanner, tmp_path, monkeypatch):
    from mcp import types
    from mcp.shared.exceptions import McpError
    project = local_project
    # A bounded real scan gives the observer a stable owned-child window. SIGSTOP
    # below provides the deterministic barrier; no elapsed-sleep success claim.
    comments = b"// owned cancellation fixture\n" * 250_000
    (project["source"] / CALLEE).write_bytes(comments + project["images"][CALLEE])
    async def scenario():
        requests = []
        async with server(project, scanner, tmp_path / "cancel-sdk.stderr", monkeypatch,
                          observe_request=requests.append) as (session, server_pid):
            head = await call(session, "rentgen_project_head", {"project_id": project["project_id"]})
            operation = str(uuid4())
            pending = asyncio.create_task(session.call_tool("rentgen_capture",
                dict(project_id=project["project_id"], operation_id=operation, expected_head=head),
                read_timeout_seconds=timedelta(seconds=60)))
            identity = None
            pidfd = None
            try:
                deadline = monotonic() + 25
                while identity is None:
                    assert not pending.done(), "Capture finished before the observed native cancellation barrier"
                    assert monotonic() < deadline, "Actual owned scanner child was not observed"
                    identity = owned_scanner(server_pid)
                    if identity is None: await asyncio.sleep(0.001)
                assert len(requests) == 1
                assert same_child(identity, server_pid) is not None
                assert hasattr(os, "pidfd_open") and hasattr(signal, "pidfd_send_signal"), "Linux pidfd APIs required for owned signal safety"
                pidfd = os.pidfd_open(identity[0])
                assert same_child(identity, server_pid) is not None
                signal.pidfd_send_signal(pidfd, signal.SIGSTOP)
                deadline = monotonic() + 2
                while True:
                    status = same_child(identity, server_pid)
                    assert status is not None and monotonic() < deadline
                    if status[0] == "T": break
                    await asyncio.sleep(0.001)
                await session.send_notification(types.ClientNotification(types.CancelledNotification(
                    params=types.CancelledNotificationParams(requestId=requests[0], reason="Owned fixture cancellation"))))
                try:
                    cancelled = await pending
                except McpError as cancelled:
                    assert cancelled.error.code == 0 and cancelled.error.message == "Request cancelled"
                else:
                    # Worker polling can observe the notification flag before
                    # the SDK responder emits its own cancellation error.
                    assert cancelled.isError and cancelled.structuredContent["error"]["code"] == "GRAPH_SCANNER_CANCELLED"
                # Cancellation acknowledgement precedes worker cleanup. The next
                # tool shares the real worker limiter and proves it drained.
                assert await call(session, "rentgen_project_head", {"project_id": project["project_id"]}) == head
                receipt = await session.call_tool("rentgen_publication_receipt",
                    dict(project_id=project["project_id"], operation_id=operation),
                    read_timeout_seconds=timedelta(seconds=15))
                assert receipt.isError and receipt.structuredContent["error"]["code"] == "PUBLICATION_NOT_FOUND"
                await wait_child_gone(identity, server_pid)
            finally:
                if pidfd is not None and identity is not None and child_alive(identity) is not None:
                    # Touch only this exact child PID/start identity, never any
                    # inherited host process. Killing lets the real owner reap it.
                    try: signal.pidfd_send_signal(pidfd, signal.SIGKILL)
                    except ProcessLookupError: pass
                    await wait_child_gone(identity, server_pid)
                if pidfd is not None:
                    os.close(pidfd)
                if not pending.done():
                    try: await asyncio.wait_for(asyncio.shield(pending), timeout=8)
                    except McpError: pass
                    except asyncio.TimeoutError:
                        # Failure cleanup only: the real notification was sent
                        # above. Cancel/retrieve this local waiter, never leave
                        # an unobserved SDK response task after transport exit.
                        pending.cancel()
                        try: await pending
                        except (McpError, asyncio.CancelledError): pass
                elif not pending.cancelled():
                    pending.exception()  # Retrieve a failure on pre-barrier abort.
    asyncio.run(scenario())
    from rentgen_core.local import LocalRuntime
    from rentgen_core.local_identity import current_local_principal
    owner = current_local_principal(identity_profile=project["profile"])
    ctx = LocalRuntime(project["registry"]).state_context(owner, project["project_id"])
    with ctx.state.transaction(owner) as tx:
        for table in ("snapshots", "publication_receipts", "snapshot_events", "snapshot_outbox"):
            assert tx._connection.execute("SELECT count(*) FROM " + table).fetchone()[0] == 0
