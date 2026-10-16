"""Pure admission and SDK cancellation controls, not native Linux acceptance."""

import asyncio
import json
from threading import Event
from types import SimpleNamespace
from uuid import uuid4

import pytest
from mcp import types
from mcp.server.lowlevel.server import request_ctx

from rentgen_core import capabilities, stdio_mcp
from rentgen_core.context import Principal


_SOURCE_READS = {"source-list", "source-read", "graph-resolve", "impact"}
_LEGACY_RETAINED = {
    "source-list", "snapshot-diff", "source-read", "graph-resolve", "impact",
    "proposal-create", "proposal-diff", "draft-save", "draft-start", "draft-edit",
    "edt-inventory", "metadata-plan", "metadata-summary", "metadata-search",
    "metadata-object",
}


@pytest.mark.parametrize("platform", ["win32", "linux", "darwin"])
def test_v1_alias_preserves_windows_contract_without_opening_linux_writers(monkeypatch, platform):
    monkeypatch.setattr(capabilities, "_platform", platform)
    report = capabilities.capability_report()
    assert report["contract_version"] == 1
    groups = report["capabilities"]
    assert set(groups["snapshot.retained.read"]["operations"]) == _LEGACY_RETAINED
    assert set(groups["snapshot.source.read"]["operations"]) == _SOURCE_READS
    assert groups["snapshot.compare.read"]["operations"] == ["snapshot-diff"]
    assert groups["snapshot.retained.read"]["supported"] is (platform == "win32")
    for operation in _SOURCE_READS | {"capture", "snapshot-diff"}:
        assert capabilities.operation_supported(operation) is (platform != "darwin")
    navigation = {"metadata-summary", "metadata-search", "metadata-object"}
    authoring = {"proposal-create", "proposal-diff", "draft-save", "draft-start", "draft-edit"}
    assert set(groups["snapshot.metadata.read"]["operations"]) == navigation
    assert set(groups["draft.authoring"]["operations"]) == authoring
    for operation in navigation | authoring:
        assert capabilities.operation_supported(operation) is (platform != "darwin")
    for operation in _LEGACY_RETAINED - _SOURCE_READS - navigation - authoring - {"snapshot-diff"}:
        assert capabilities.operation_supported(operation) is (platform == "win32")
    assert not capabilities.operation_supported("unreviewed-source-command")


@pytest.mark.parametrize("platform", ["linux", "win32"])
def test_execute_dispatch_preserves_capture_cancellation_and_authority(monkeypatch, platform):
    monkeypatch.setattr(stdio_mcp, "sys", SimpleNamespace(platform=platform))
    monkeypatch.setattr(capabilities, "_platform", platform)
    project, operation = str(uuid4()), str(uuid4())
    principal = Principal("fixture", "local_os")
    context, builder = object(), object()
    observed = []

    def state_context(who, project_id, *, permissions):
        assert who is principal and project_id == project
        assert permissions == {"analysis:run"}
        return context

    cancelled = lambda: True

    def capture(ctx, **kwargs):
        assert ctx is context and kwargs["builder"] is builder
        assert kwargs["operation_id"] == operation
        assert kwargs["expected_head"].project_id == project
        if platform == "linux":
            assert kwargs["cancelled"] is cancelled
            assert kwargs["cancelled"]() is True
        else:
            assert "cancelled" not in kwargs
        observed.append(True)
        return {"controlled_dispatch": True}

    monkeypatch.setattr(stdio_mcp, "capture_and_publish", capture)
    runtime = SimpleNamespace(state_context=state_context, graph_builder=builder)
    result = stdio_mcp._execute(
        runtime, principal, "rentgen_capture",
        {"project_id": project, "operation_id": operation,
         "expected_head": {"project_id": project, "revision": 0,
                           "snapshot": None, "source_revision": 1}},
        cancelled=cancelled,
    )
    assert not result.isError, result
    assert result.structuredContent["result"] == {"controlled_dispatch": True}
    assert observed == [True]


@pytest.mark.parametrize("platform,name", [
    ("linux", "rentgen_capture"), ("win32", "rentgen_capture"),
    ("linux", "rentgen_capabilities"),
])
def test_sdk_worker_observes_cancel_until_completion_and_releases_request(monkeypatch, platform, name):
    monkeypatch.setattr(stdio_mcp, "sys", SimpleNamespace(platform=platform))
    cancellations = stdio_mcp._WorkerCancellations()
    entered, release = Event(), Event()
    observed, retained = [], []
    request_id = "bounded-capture"

    def execute(*args, protocol_request_id=None, scope=None, **kwargs):
        assert protocol_request_id == request_id
        if platform == "linux" and name == "rentgen_capture":
            retained.append(kwargs["cancelled"])
            observed.append(kwargs["cancelled"]())
        else:
            assert kwargs == {}
        entered.set()
        if not release.wait(5):
            raise RuntimeError("Controlled SDK worker was not released")
        if retained:
            observed.append(retained[0]())
        return types.CallToolResult(content=[], structuredContent={"controlled_worker": True})

    monkeypatch.setattr(stdio_mcp, "_execute", execute)

    async def run():
        server = stdio_mcp.create_server(
            object(), Principal("fixture", "local_os"), cancellations=cancellations
        )
        token = request_ctx.set(SimpleNamespace(request_id=request_id))
        task = None
        try:
            task = asyncio.create_task(server.request_handlers[types.CallToolRequest](
                types.CallToolRequest(params=types.CallToolRequestParams(name=name, arguments={}))
            ))
            async with asyncio.timeout(5):
                while not entered.is_set():
                    await asyncio.sleep(.001)
                assert cancellations.active == {request_id: False}
                notification = json.dumps({"jsonrpc": "2.0", "method": "notifications/cancelled",
                                           "params": {"requestId": request_id}})
                assert cancellations.duplicate(notification) is False
                assert cancellations.duplicate(notification) is True
                assert cancellations.active == {request_id: True}
                release.set()
                result = await task
                assert result.root.structuredContent == {"controlled_worker": True}
                assert not result.root.isError
        finally:
            release.set()
            if task is not None and not task.done():
                await task
            request_ctx.reset(token)

    asyncio.run(run())
    assert cancellations.active == {}
    if retained:
        assert observed == [False, True]
        assert retained[0]() is False
    else:
        assert observed == []
