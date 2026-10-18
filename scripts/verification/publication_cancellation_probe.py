"""Actual Windows SDK cancellation at private test barriers; no production flags."""
import asyncio
from contextlib import asynccontextmanager, closing
from dataclasses import asdict
from datetime import timedelta
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
from uuid import uuid4

TABLES = ("snapshots", "publication_receipts", "snapshot_events", "snapshot_outbox")


def require(value, message):
    if not value:
        raise ValueError(message)


def save(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value), encoding="utf-8")
    temporary.replace(path)


def inventory(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file()}


def view(state):
    with closing(sqlite3.connect(state.as_uri() + "?mode=ro", uri=True)) as db:
        db.execute("PRAGMA query_only=ON")
        return dict(counts={name: db.execute("SELECT count(*) FROM " + name).fetchone()[0] for name in TABLES},
                    head=list(db.execute("SELECT snapshot_id,revision FROM project_head").fetchone()),
                    fingerprint=hashlib.sha256("\n".join(db.iterdump()).encode()).hexdigest())


def server_main(config_path):
    """Only the test host installs barriers; actual Core/SDK still execute normally."""
    from rentgen_core import publication, stdio_mcp
    from rentgen_core.errors import CoreError

    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    directory = Path(config_path).parent
    selected = fired = False
    actual = stdio_mcp.capture_and_publish
    def boundary(name, **values):
        nonlocal fired
        if not selected or fired or name != config["phase"]:
            return
        fired = True
        require(values["ctx"].project_id == config["project"], "Barrier project differs")
        save(directory / "ready.json", dict(phase=name, operation_id=config["operation"],
             pid=os.getpid(), catalog=asdict(values["catalog"])))
        end = time.monotonic() + 45
        while not (directory / "release").exists():
            require(time.monotonic() < end, "Cancellation test barrier expired")
            time.sleep(.01)
    def capture(ctx, **kwargs):
        nonlocal selected
        selected = kwargs["operation_id"] == config["operation"]
        outcome = dict(outcome="unexpected", operation_id=kwargs["operation_id"])
        try:
            result = actual(ctx, **kwargs)
            outcome["outcome"] = "success"
            return result
        except CoreError as exc:
            outcome.update(outcome="error", code=exc.code)
            raise
        finally:
            if selected:
                save(directory / "drained.json", outcome)
            selected = False
    publication._boundary = boundary
    stdio_mcp.capture_and_publish = capture
    args = ["--registry", config["registry"], "--project", config["project"]]
    if config["scanner"] is not None:
        args += ["--scanner", config["scanner"]]
    return stdio_mcp.main(args)


async def verify(python, scanner, workspace, *, isolated=True, checkout=None):
    from mcp import ClientSession, StdioServerParameters, types
    from mcp.client.stdio import stdio_client
    from mcp.shared.exceptions import McpError

    require(sys.platform == "win32", "Actual Windows host required")
    workspace = Path(workspace).resolve()
    workspace.mkdir()
    source, registry, state = workspace / "source", workspace / "registry.sqlite3", workspace / "state/state.sqlite3"
    source.mkdir()
    module = source / "Module.bsl"
    module.write_bytes(b"Function Value() Export\nReturn 1;\nEndFunction\n")
    cwd = workspace if isolated else Path(checkout).resolve()
    prefix = [str(python), *(["-I"] if isolated else [])]
    def cli(name, *args):
        result = subprocess.run([*prefix, "-m", "rentgen_core", name, "--registry", str(registry), *map(str, args)],
            cwd=cwd, capture_output=True, text=True, encoding="utf-8", timeout=30)
        require(result.returncode == 0 and not result.stderr, "Cancellation fixture CLI failed")
        return json.loads(result.stdout)["result"]
    cli("registry-init")
    project = cli("project-register", "--source-root", source, "--state-root", state.parent,
                  "--name", "Owned cancellation fixture")["project_id"]

    class Write:
        def __init__(self, stream, observed): self.stream, self.observed = stream, observed
        async def send(self, message):
            root = message.message.root
            if getattr(root, "method", None) == "tools/call" and root.params.get("name") == "rentgen_capture":
                self.observed.append(root.id)
            await self.stream.send(message)
        async def __aenter__(self): await self.stream.__aenter__(); return self
        async def __aexit__(self, *args): return await self.stream.__aexit__(*args)
        async def aclose(self): await self.stream.aclose()

    @asynccontextmanager
    async def server(label, phase=None, operation=None, with_scanner=True):
        directory = workspace / label
        directory.mkdir()
        config = directory / "inputs.json"
        save(config, dict(phase=phase, operation=operation, registry=str(registry), project=project,
                          scanner=str(scanner) if with_scanner else None))
        # -c retains the source checkout on sys.path only in source-test mode;
        # the installed gate keeps -I and its outside-checkout working directory.
        launch = "import runpy,sys; sys.argv=sys.argv[1:]; runpy.run_path(sys.argv[0],run_name='__main__')"
        parameters = StdioServerParameters(command=prefix[0], args=[*prefix[1:], "-c", launch,
            str(Path(__file__).resolve()), "server", str(config)], cwd=str(cwd))
        observed = []
        async with stdio_client(parameters) as (read, write):
            async with ClientSession(read, Write(write, observed)) as session:
                await session.initialize()
                yield session, observed, directory

    async def call(session, name, **args):
        reply = await session.call_tool(name, dict(project_id=project, **args), read_timeout_seconds=timedelta(seconds=60))
        require(not reply.isError and json.loads(reply.content[0].text) == reply.structuredContent, "SDK result differs")
        return reply.structuredContent["result"]

    async def marker(path, pending=None):
        end = time.monotonic() + 40
        while True:
            try: return json.loads(path.read_text(encoding="utf-8"))
            except (FileNotFoundError, PermissionError): pass
            require(time.monotonic() < end and (pending is None or not pending.done()), "SDK barrier or drain was not observed")
            await asyncio.sleep(.01)

    cancellations = []
    async def cancel_at(session, observed, directory, phase, operation, head, expected_count):
        before_requests = len(observed)
        pending = asyncio.create_task(call(session, "rentgen_capture", operation_id=operation, expected_head=head))
        try:
            ready = await marker(directory / "ready.json", pending)
            require(ready["phase"] == phase and ready["operation_id"] == operation
                    and ready["catalog"]["snapshot"]["project_id"] == project, "SDK barrier binding differs")
            require(len(observed) == before_requests + 1, "Exact outgoing request ID unavailable")
            paused = view(state)
            require(set(paused["counts"].values()) == {expected_count}, "Publication unit differs at barrier")
            snapshot_id = ready["catalog"]["snapshot"]["snapshot_id"] if phase == "after_commit" else (head["snapshot"]["snapshot_id"] if head["snapshot"] else None)
            require(paused["head"] == [snapshot_id, expected_count], "Head differs at cancellation barrier")
            await session.send_notification(types.ClientNotification(types.CancelledNotification(
                params=types.CancelledNotificationParams(requestId=observed[-1], reason="Owned phase-barrier cancellation"))))
            try:
                await asyncio.wait_for(asyncio.shield(pending), 10)
            except McpError as exc:
                require(exc.error.code == 0 and exc.error.message == "Request cancelled", "SDK cancel acknowledgment differs")
            else:
                raise ValueError("SDK did not acknowledge cancellation while worker was paused")
            (directory / "release").write_text("release", encoding="ascii")
            drained = await marker(directory / "drained.json")
            expected = dict(operation_id=operation, outcome="success")
            if phase == "before_state_transaction":
                expected.update(outcome="error", code="GRAPH_SCANNER_CANCELLED")
            require(drained == expected, "Actual worker result differs after cancellation")
            # The next queued call completes only after the original worker drains.
            current = await call(session, "rentgen_project_head")
            require(view(state) == paused, "Cancellation changed the already observed publication unit")
            cancellations.append(dict(phase=phase, operation_id=operation, request_id=observed[-1],
                acknowledgment=dict(code=0, message="Request cancelled"), worker=drained,
                state=paused, observed_head=current))
            return ready["catalog"], current
        finally:
            (directory / "release").write_text("release", encoding="ascii")
            if not pending.done():
                pending.cancel()
            try: await pending
            except (McpError, asyncio.CancelledError): pass

    cancelled_operation, late_operation = str(uuid4()), str(uuid4())
    async with server("early", "before_state_transaction", cancelled_operation) as (session, observed, directory):
        head = await call(session, "rentgen_project_head")
        orphan_catalog, current = await cancel_at(session, observed, directory, "before_state_transaction", cancelled_operation, head, 0)
        require(current == head, "Early cancellation changed head")
        refused = await session.call_tool("rentgen_publication_receipt", dict(project_id=project, operation_id=cancelled_operation))
        require(refused.isError and refused.structuredContent["error"]["code"] == "PUBLICATION_NOT_FOUND", "Early cancellation has a receipt")
        orphan = state.parent / orphan_catalog["generation_relpath"]
        original = inventory(orphan)
        moved = orphan.with_name(str(uuid4()))
        orphan.rename(moved); moved.rename(orphan)  # Actual Windows handle-release control while server remains alive.
        retry = await call(session, "rentgen_capture", operation_id=cancelled_operation, expected_head=head)
        attribution = await call(session, "rentgen_generation_attribution", generation_relpath=orphan_catalog["generation_relpath"])
        require(attribution["generation_attribution"]["status"] == "unreferenced_at_read" and
                attribution["generation_attribution"]["removal_permitted"] is False, "Cancelled attempt gained authority")
        require(retry["snapshot"] == orphan_catalog["snapshot"] and inventory(orphan) == original, "Retry changed owned cancelled bytes")
        require(len(list((state.parent / "generations").iterdir())) == 2, "Retry did not allocate a new attempt")

    module.write_bytes(module.read_bytes().replace(b"Return 1", b"Return 2"))
    async with server("late", "after_commit", late_operation) as (session, observed, directory):
        late_catalog, current = await cancel_at(session, observed, directory, "after_commit", late_operation, retry["head"], 2)
        late = await call(session, "rentgen_publication_receipt", operation_id=late_operation)
        require(late["snapshot"] == late_catalog["snapshot"] and current == late["head"], "Late cancellation lost exact receipt")
        module.write_bytes(module.read_bytes().replace(b"Return 2", b"Return 3"))
        later = await call(session, "rentgen_capture", operation_id=str(uuid4()), expected_head=late["head"])
    source.rename(workspace / "removed-live-source")
    before = view(state)
    async with server("replay", with_scanner=False) as (session, _, _):
        replay = await call(session, "rentgen_capture", operation_id=late_operation, expected_head=retry["head"])
        require(replay == late and await call(session, "rentgen_project_head") == later["head"], "Late receipt replay changed after later head")
    require(view(state) == before and set(before["counts"].values()) == {3}, "Replay mutated publication state")
    require(inventory(orphan) == original and not source.exists(), "Cancelled attempt or missing live source changed")
    return dict(schema=1, transport="official_sdk_stdio", platform="win32", isolated=isolated,
        probe_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), cancellations=cancellations,
        scope="actual phase-barrier fixture; no active-builder kill, rollback, power-loss or cleanup lease",
        early_operation=cancelled_operation, late_operation=late_operation,
        orphan_catalog=orphan_catalog, retry=retry, late=late, later=later,
        final_counts=before["counts"], state_sha256=before["fingerprint"],
        outcomes=dict(early_cancel_no_publication=True, exact_notification_ids=True, worker_drained=True,
            candidate_handles_closed=True, orphan_bytes_retained=True, retry_new_attempt=True,
            late_commit_receipt_preserved=True, replay_after_later_head=True, replay_without_live_source_or_scanner=True,
            replay_state_unchanged=True))


if __name__ == "__main__":
    require(len(sys.argv) == 3 and sys.argv[1] == "server", "Expected owned server fixture mode")
    raise SystemExit(server_main(sys.argv[2]))
