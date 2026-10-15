"""Diff admission and real SDK boundary controls; no native Linux qualification."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import asdict
import io
import json
from threading import Event, get_ident
from time import monotonic
from types import SimpleNamespace

import pytest
from mcp import types
from mcp.server.lowlevel.server import request_ctx

from rentgen_core import capabilities, stdio_mcp
from rentgen_core.context import Principal
from rentgen_core.errors import CoreError


PROJECT = "11111111-1111-4111-8111-111111111111"
BEFORE = "a" * 64
AFTER = "b" * 64
PRINCIPAL = Principal("fixture", "local_os")
ARGS = {
    "project_id": PROJECT,
    "before_snapshot_id": BEFORE,
    "after_snapshot_id": AFTER,
}


@pytest.mark.parametrize("platform", ["linux", "win32", "darwin", "freebsd14"])
def test_compare_alias_preserves_broad_group_and_admits_only_reviewed_read(monkeypatch, platform):
    monkeypatch.setattr(capabilities, "_platform", platform)
    report = capabilities.capability_report()
    groups = report["capabilities"]
    assert report["contract_version"] == 1
    assert groups["snapshot.compare.read"]["operations"] == ["snapshot-diff"]
    assert "snapshot-diff" in groups["snapshot.retained.read"]["operations"]
    assert groups["snapshot.retained.read"]["supported"] is (platform == "win32")
    assert capabilities.COMMAND_CAPABILITIES["snapshot-diff"] == "snapshot.compare.read"
    assert capabilities.operation_supported("rentgen_snapshot_diff") is (platform in {"linux", "win32"})
    for hidden in ["metadata-summary", "metadata-object", "draft-save", "proposal-create"]:
        assert capabilities.operation_supported(hidden) is (platform == "win32")


@pytest.mark.parametrize("platform", ["linux", "win32"])
def test_sdk_lists_readonly_diff_and_enforces_startup_scope(monkeypatch, platform):
    monkeypatch.setattr(capabilities, "_platform", platform)
    server = stdio_mcp.create_server(object(), PRINCIPAL)
    listing = asyncio.run(server.request_handlers[types.ListToolsRequest](types.ListToolsRequest(method="tools/list")))
    tools = {tool.name: tool for tool in listing.root.tools}
    annotations = tools["rentgen_snapshot_diff"].annotations
    assert annotations.readOnlyHint is True
    assert annotations.destructiveHint is False
    assert annotations.openWorldHint is False
    restricted = stdio_mcp.McpScope(project_id=PROJECT, allowed_tools={"rentgen_project_head"})
    with pytest.raises(CoreError, match="startup scope"):
        stdio_mcp.validate_arguments("rentgen_snapshot_diff", ARGS, scope=restricted)
    scoped = stdio_mcp.McpScope(project_id=PROJECT, allowed_tools={"rentgen_snapshot_diff"})
    stdio_mcp.validate_arguments("rentgen_snapshot_diff", ARGS, scope=scoped)
    with pytest.raises(CoreError) as error:
        stdio_mcp.validate_arguments("rentgen_snapshot_diff", ARGS | {"project_id": "22222222-2222-4222-8222-222222222222"}, scope=scoped)
    assert error.value.code == "MCP_PROJECT_FORBIDDEN"


@pytest.mark.parametrize("changes", [
    {"before_snapshot_id": None}, {"after_snapshot_id": "latest"},
    {"limit": True}, {"limit": 1.0}, {"limit": 0}, {"limit": 101},
    {"cursor": ""}, {"deadline": 30}, {"cancelled": False},
])
def test_diff_schema_requires_explicit_pair_and_has_no_budget_controls(changes):
    with pytest.raises(CoreError) as error:
        stdio_mcp.validate_arguments("rentgen_snapshot_diff", ARGS | changes)
    assert error.value.code == "INVALID_ARGUMENT"


@pytest.mark.parametrize("platform", ["linux", "win32"])
def test_sdk_diff_worker_keeps_cancel_callback_until_owner_drains(monkeypatch, platform):
    monkeypatch.setattr(stdio_mcp, "sys", SimpleNamespace(platform=platform))
    cancellations = stdio_mcp._WorkerCancellations()
    entered, release = Event(), Event()
    observed, retained = [], []
    request_id = "diff-read-worker"

    def execute(*args, protocol_request_id=None, scope=None, cancelled):
        assert protocol_request_id == request_id
        retained.append(cancelled)
        observed.append(cancelled())
        entered.set()
        assert release.wait(5), "Controlled diff worker did not drain"
        observed.append(cancelled())
        return types.CallToolResult(content=[], structuredContent={"controlled_worker": True})

    monkeypatch.setattr(stdio_mcp, "_execute", execute)

    async def scenario():
        server = stdio_mcp.create_server(object(), PRINCIPAL, cancellations=cancellations)
        token = request_ctx.set(SimpleNamespace(request_id=request_id))
        task = None
        try:
            task = asyncio.create_task(server.request_handlers[types.CallToolRequest](
                types.CallToolRequest(params=types.CallToolRequestParams(name="rentgen_snapshot_diff", arguments=ARGS))
            ))
            async with asyncio.timeout(5):
                while not entered.is_set():
                    await asyncio.sleep(.001)
                notification = json.dumps({"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": request_id}})
                assert cancellations.duplicate(notification) is False
                assert cancellations.duplicate(notification) is True
                assert not task.done(), "SDK detached a live owned read worker"
                release.set()
                result = await task
                assert result.root.structuredContent == {"controlled_worker": True}
        finally:
            release.set()
            if task is not None and not task.done():
                await task
            request_ctx.reset(token)

    asyncio.run(scenario())
    assert observed == [False, True]
    assert cancellations.active == {}
    assert retained[0]() is False


@pytest.fixture
def diff_boundary(monkeypatch):
    """Trusted coordinator seam; these are output controls, not retained IO tests."""
    from rentgen_core import snapshot_diff

    monkeypatch.setattr(capabilities, "_platform", "linux")
    before = {"project_id": PROJECT, "snapshot_id": BEFORE, "manifest_hash": BEFORE}
    after = {"project_id": PROJECT, "snapshot_id": AFTER, "manifest_hash": AFTER}
    value = {
        "before_snapshot": before, "after_snapshot": after,
        "scope": "source_bytes_by_layer_and_path", "identity": "source_path_only",
        "counts": {"added": 1, "removed": 0, "modified": 0, "unchanged": 0},
        "changes": [{"kind": "added", "before": None, "after": {
            "ref": {"snapshot": after, "layer_id": "base", "relative_path": "PRIVATE_CHANGE.xml", "raw_sha256": "c" * 64},
            "size_bytes": 1,
        }}],
        "next_cursor": None,
    }
    scope = snapshot_diff.DiffOutputScope(PROJECT, BEFORE, AFTER, "d" * 64, monotonic() + 30)
    operation = snapshot_diff.DiffOperationResult(value, scope)
    dispatches, authorizations = [], []
    policy = SimpleNamespace(error=None)

    def compare(*args, **kwargs):
        dispatches.append((args, kwargs, get_ident()))
        return operation

    def authorize(runtime, principal, selected):
        assert type(selected) is snapshot_diff.DiffOutputScope
        assert selected == scope
        assert all(type(item) in {str, float} for item in asdict(selected).values())
        authorizations.append((selected, get_ident()))
        if policy.error is not None:
            raise policy.error

    def unexpected(*args, **kwargs):
        pytest.fail("MCP diff must use the pair coordinator before eager snapshot IO")

    runtime = SimpleNamespace(resolve=unexpected, state_context=unexpected)
    monkeypatch.setattr(snapshot_diff, "compare_retained_pair", compare)
    monkeypatch.setattr(snapshot_diff, "authorize_diff_output", authorize)
    return SimpleNamespace(runtime=runtime, operation=operation, dispatches=dispatches, authorizations=authorizations, policy=policy)


def _execute_diff(boundary, protocol_request_id="diff-7", **kwargs):
    return stdio_mcp._execute(
        boundary.runtime, PRINCIPAL, "rentgen_snapshot_diff", ARGS,
        protocol_request_id=protocol_request_id, **kwargs,
    )


def _response(reply, protocol_request_id="diff-7"):
    return types.JSONRPCResponse(
        jsonrpc="2.0", id=protocol_request_id,
        result=reply.model_dump(by_alias=True, mode="json", exclude_none=True),
    ).model_dump(by_alias=True, mode="json", exclude_none=True)


def _emit(boundary, document, *, guard=None):
    stream = io.BytesIO()
    output = stdio_mcp._GuardedOutput(stream, boundary.runtime, PRINCIPAL)
    if guard is not None:
        guard(output)
    output._write(json.dumps(document, ensure_ascii=False, separators=(",", ":")) + "\n")
    return json.loads(stream.getvalue()), stream.getvalue()


def test_execute_diff_uses_pair_coordinator_and_final_worker_gets_only_immutable_scope(diff_boundary):
    cancelled = lambda: False
    reply = _execute_diff(diff_boundary, cancelled=cancelled)
    assert not reply.isError, reply
    args, options, read_thread = diff_boundary.dispatches[0]
    assert args == (diff_boundary.runtime, PRINCIPAL, PROJECT, BEFORE, AFTER)
    assert options == {"limit": 100, "cursor": None, "cancelled": cancelled}
    with ThreadPoolExecutor(max_workers=1) as pool:
        emitted, raw = pool.submit(_emit, diff_boundary, _response(reply)).result(timeout=5)
    assert emitted["result"]["structuredContent"]["result"]["snapshot_diff"] == diff_boundary.operation.value
    assert "_meta" not in emitted["result"]
    assert b"catalog_digest" not in raw and b"deadline" not in raw
    assert diff_boundary.authorizations[-1][1] != read_thread
    assert raw.endswith(b"\n")


@pytest.mark.parametrize("mutation", [
    "drop_scope", "drop_structured", "drop_text", "text_only_error", "pair_text",
    "pair_structured", "both_payloads", "duplicate_text_key", "scope_pair", "scope_permissions",
    "protocol_request", "scope_family", "extra_content", "scope_deadline", "broken_text_only",
])
def test_final_diff_output_refuses_lost_or_divergent_representation(diff_boundary, mutation):
    document = _response(_execute_diff(diff_boundary))
    result = document["result"]
    payload = result["structuredContent"]
    meta = result["_meta"][stdio_mcp._OUTPUT_SCOPE]
    if mutation == "drop_scope":
        result.pop("_meta")
    elif mutation == "drop_structured":
        result.pop("structuredContent")
    elif mutation == "drop_text":
        result["content"] = []
    elif mutation == "text_only_error":
        result["structuredContent"] = {"error": {"code": "CONTROLLED_ERROR"}}
    elif mutation == "pair_text":
        other = deepcopy(payload)
        other["result"]["snapshot_diff"]["after_snapshot"]["snapshot_id"] = BEFORE
        result["content"][0]["text"] = stdio_mcp._json(other)
    elif mutation == "pair_structured":
        payload["result"]["snapshot_diff"]["after_snapshot"]["snapshot_id"] = BEFORE
    elif mutation == "both_payloads":
        payload["result"]["snapshot_diff"]["counts"]["added"] = 99
        result["content"][0]["text"] = stdio_mcp._json(payload)
    elif mutation == "duplicate_text_key":
        result["content"][0]["text"] = '{"result":{"snapshot_diff":"HIDDEN"},' + result["content"][0]["text"][1:]
    elif mutation == "scope_pair":
        meta["after_snapshot_id"] = BEFORE
    elif mutation == "scope_permissions":
        meta["permissions"] = ["project:read", "source:edit"]
    elif mutation == "protocol_request":
        document["id"] = "some-other-request"
    elif mutation == "scope_family":
        meta["family"] = "report"
    elif mutation == "extra_content":
        result["content"].append({"type": "text", "text": "PRIVATE_CHANGE"})
    elif mutation == "scope_deadline":
        meta["deadline"] = True
    elif mutation == "broken_text_only":
        result.pop("_meta")
        result.pop("structuredContent")
        result["content"][0]["text"] += "invalid-trailing-data"
    emitted, raw = _emit(diff_boundary, document)
    assert emitted["result"]["isError"] is True
    assert emitted["result"]["structuredContent"]["error"]["code"] == "PROJECT_ACCESS_UNAVAILABLE"
    assert b"PRIVATE_CHANGE" not in raw and b"HIDDEN" not in raw


def test_final_diff_pair_binding_is_checked_independently_of_payload_hash(diff_boundary):
    document = _response(_execute_diff(diff_boundary))
    result = document["result"]
    payload = result["structuredContent"]
    payload["result"]["snapshot_diff"]["after_snapshot"] = dict(payload["result"]["snapshot_diff"]["before_snapshot"])
    result["content"][0]["text"] = stdio_mcp._json(payload)
    result["_meta"][stdio_mcp._OUTPUT_SCOPE]["payload_sha256"] = stdio_mcp._diff_payload_hash(payload)
    emitted, raw = _emit(diff_boundary, document)
    assert emitted["result"]["isError"] is True
    assert b"PRIVATE_CHANGE" not in raw


@pytest.mark.parametrize("code", ["PROJECT_FORBIDDEN", "DIFF_DEADLINE_EXCEEDED", "SNAPSHOT_CORRUPT"])
def test_diff_rechecks_authority_after_final_encoding_before_write(diff_boundary, code):
    document = _response(_execute_diff(diff_boundary))
    initial_authorizations = len(diff_boundary.authorizations)

    def mutate_after_encoding(output):
        original = output._bytes

        def encoded(document):
            raw = original(document)
            if not document["result"].get("isError"):
                diff_boundary.policy.error = CoreError(code, "Controlled final authority refusal")
            return raw

        output._bytes = encoded

    emitted, raw = _emit(diff_boundary, document, guard=mutate_after_encoding)
    assert len(diff_boundary.authorizations) == initial_authorizations + 1
    assert emitted["result"]["structuredContent"]["error"]["code"] == code
    assert b"PRIVATE_CHANGE" not in raw


def test_diff_wire_cap_counts_duplicate_representations_unicode_escaping_and_protocol_id(diff_boundary):
    from rentgen_core.snapshot_diff import MAX_DIFF_OUTPUT_BYTES

    # The page fits its 1 MiB JSON budget; escaped JSON-in-text plus structured
    # content and the real caller ID exceed the 2 MiB complete SDK wire budget.
    value = diff_boundary.operation.value
    value["boundary_probe"] = "я\n\\\"" * 80_000
    assert len(stdio_mcp._json(value).encode("utf-8")) < 1024**2
    protocol_id = "caller-\nя\\\"" * 1000
    payload = {"result": {"snapshot_diff": value}, "request_id": PROJECT}
    oversized = types.CallToolResult(
        content=[types.TextContent(type="text", text=stdio_mcp._json(payload))],
        structuredContent=payload,
    )
    actual_sdk_wire = types.JSONRPCResponse(
        jsonrpc="2.0", id=protocol_id,
        result=oversized.model_dump(by_alias=True, mode="json", exclude_none=True),
    ).model_dump_json(by_alias=True, exclude_none=True).encode("utf-8") + b"\n"
    assert len(actual_sdk_wire) > MAX_DIFF_OUTPUT_BYTES
    reply = _execute_diff(diff_boundary, protocol_request_id=protocol_id)
    assert reply.isError is True
    assert reply.structuredContent["error"]["code"] == "OUTPUT_LIMIT_EXCEEDED"
    assert "PRIVATE_CHANGE" not in json.dumps(reply.structuredContent)


def test_final_diff_wire_cap_is_repeated_after_sdk_serialization(diff_boundary):
    from rentgen_core.snapshot_diff import MAX_DIFF_OUTPUT_BYTES

    document = _response(_execute_diff(diff_boundary))
    result = document["result"]
    result["structuredContent"]["result"]["snapshot_diff"]["boundary_probe"] = "я\n\\\"" * 85_000
    result["content"][0]["text"] = stdio_mcp._json(result["structuredContent"])
    # Rebind the private digest deliberately to isolate the final wire cap from
    # the independent mutation guard exercised above.
    result["_meta"][stdio_mcp._OUTPUT_SCOPE]["payload_sha256"] = stdio_mcp._diff_payload_hash(result["structuredContent"])
    public = deepcopy(document)
    public["result"].pop("_meta")
    actual_sdk_wire = types.JSONRPCResponse(**public).model_dump_json(by_alias=True, exclude_none=True).encode("utf-8") + b"\n"
    assert len(actual_sdk_wire) > MAX_DIFF_OUTPUT_BYTES
    emitted, raw = _emit(diff_boundary, document)
    assert emitted["result"]["structuredContent"]["error"]["code"] == "OUTPUT_LIMIT_EXCEEDED"
    assert b"PRIVATE_CHANGE" not in raw


def test_nested_metric_named_snapshot_diff_preserves_existing_report_guard():
    request_id = "22222222-2222-4222-8222-222222222222"
    payload = {"result": {"owner_report": {"snapshot_diff": "ordinary report metric"}}, "request_id": request_id}
    document = {"jsonrpc": "2.0", "id": 7, "result": {
        "content": [{"type": "text", "text": stdio_mcp._json(payload)}],
        "structuredContent": payload,
        "_meta": stdio_mcp._wire_scope(SimpleNamespace(project_id=PROJECT), {"project:read"}, request_id, "report"),
    }}
    checked = []
    runtime = SimpleNamespace(state_context=lambda *args, **kwargs: checked.append((args, kwargs)))
    stream = io.BytesIO()
    stdio_mcp._GuardedOutput(stream, runtime, PRINCIPAL)._write(json.dumps(document))
    emitted = json.loads(stream.getvalue())
    assert emitted["result"]["structuredContent"] == payload
    assert "_meta" not in emitted["result"]
    assert checked == [((PRINCIPAL, PROJECT), {"permissions": frozenset({"project:read"})})]


@pytest.mark.parametrize("variant", ["leading_space", "request_first", "escaped_key"])
@pytest.mark.parametrize("corruption", ["trailing", "truncated", "error_flag"])
def test_unscoped_corrupt_text_cannot_disclose_diff_under_alternate_json_format(diff_boundary, variant, corruption):
    document = _response(_execute_diff(diff_boundary))
    result = document["result"]
    payload = result.pop("structuredContent")
    result.pop("_meta")
    text = result["content"][0]["text"]
    if variant == "leading_space":
        text = " \n " + text
    elif variant == "request_first":
        text = stdio_mcp._json({"request_id": payload["request_id"], "result": payload["result"]})
    else:
        text = text.replace("snapshot_diff", "snapshot_\\u0064iff", 1)
    if corruption == "truncated":
        text = text[:text.index("PRIVATE_CHANGE") + len("PRIVATE_CHANGE")]
    else:
        text += "invalid-trailing-data"
        if corruption == "error_flag":
            result["isError"] = True
    result["content"][0]["text"] = text
    emitted, raw = _emit(diff_boundary, document)
    assert emitted["result"]["isError"] is True
    assert emitted["result"]["structuredContent"]["error"]["code"] == "PROJECT_ACCESS_UNAVAILABLE"
    assert b"PRIVATE_CHANGE" not in raw


@pytest.mark.parametrize("payload", [
    {"result": {"snapshot_diff_metric": "ordinary generic JSON"}},
    {"error": {"code": "CONTROLLED_JSON_ERROR", "message": "preserved"}},
])
def test_valid_generic_json_reply_keeps_its_existing_contract(payload):
    stream = io.BytesIO()
    runtime = SimpleNamespace(state_context=lambda *a, **k: pytest.fail("Generic JSON must not acquire project authority"))
    result = {"content": [{"type": "text", "text": stdio_mcp._json(payload)}], "structuredContent": payload}
    if "error" in payload:
        result["isError"] = True
    document = {"jsonrpc": "2.0", "id": 7, "result": result}
    stdio_mcp._GuardedOutput(stream, runtime, PRINCIPAL)._write(json.dumps(document))
    assert json.loads(stream.getvalue())["result"] == result


@pytest.mark.parametrize("is_error", [False, True])
def test_incidental_sdk_plaintext_is_normalized_to_bounded_json_error(is_error):
    stream = io.BytesIO()
    document = {"jsonrpc": "2.0", "id": 7, "result": {
        "content": [{"type": "text", "text": "Incidental SDK validation text"}], "isError": is_error,
    }}
    stdio_mcp._GuardedOutput(stream, object(), PRINCIPAL)._write(json.dumps(document))
    raw = stream.getvalue()
    result = json.loads(raw)["result"]
    assert result["isError"] is True and len(raw) < 1024
    assert result["structuredContent"]["error"]["code"] == "PROJECT_ACCESS_UNAVAILABLE"
    assert b"Incidental SDK validation text" not in raw


def test_protocol_reply_without_text_content_is_not_misclassified():
    document = {"jsonrpc": "2.0", "id": 7, "result": {"tools": []}}
    stream = io.BytesIO()
    stdio_mcp._GuardedOutput(stream, object(), PRINCIPAL)._write(json.dumps(document))
    assert json.loads(stream.getvalue()) == document


@pytest.mark.parametrize("invalid", ['{"result":NaN}', '{"result":1e999}', '{"result":1,"result":2}'])
def test_unscoped_output_refuses_nonfinite_numbers_and_duplicate_json_keys(invalid):
    stream = io.BytesIO()
    document = {"jsonrpc": "2.0", "id": 7, "result": {"content": [{"type": "text", "text": invalid}]}}
    stdio_mcp._GuardedOutput(stream, object(), PRINCIPAL)._write(json.dumps(document))
    assert json.loads(stream.getvalue())["result"]["isError"] is True


def test_duplicate_outer_result_cannot_forward_a_discarded_protected_diff(diff_boundary):
    document = _response(_execute_diff(diff_boundary))
    hidden = json.dumps(document["result"], separators=(",", ":"))
    visible = json.dumps({"content": [{"type": "text", "text": "{}"}], "structuredContent": {}, "isError": True}, separators=(",", ":"))
    frame = '{"jsonrpc":"2.0","id":"diff-7","result":' + hidden + ',"result":' + visible + '}\n'
    stream = io.BytesIO()
    with pytest.raises(ValueError):
        stdio_mcp._GuardedOutput(stream, diff_boundary.runtime, PRINCIPAL)._write(frame)
    assert stream.getvalue() == b""


@pytest.mark.parametrize("invalid", [
    '{"jsonrpc":"2.0","id":1,"id":2,"result":{}}',
    '{"jsonrpc":"2.0","id":1,"result":{"invalid":NaN}}',
    '{"jsonrpc":"2.0","id":1,"result":{"invalid":1e999}}',
    '{"jsonrpc":"2.0","id":1,"result":{}}trailing',
    '[]',
])
def test_ambiguous_outer_frame_is_refused_before_any_write(invalid):
    stream = io.BytesIO()
    with pytest.raises(ValueError):
        stdio_mcp._GuardedOutput(stream, object(), PRINCIPAL)._write(invalid)
    assert stream.getvalue() == b""
