"""Real state/SDK disclosure controls; constructed verify DTOs prove no file validity."""
import asyncio
from copy import deepcopy
from dataclasses import asdict
import io
import json
from uuid import uuid4

import pytest
from mcp import types

from rentgen_core import capabilities, stdio_mcp, mcp_generations as subject
from rentgen_core.errors import CoreError
from project_access_test_support import force_legacy_membership
from test_generation_attribution import project, catalog, commit


@pytest.mark.parametrize("platform", ["linux", "win32", "darwin"])
def test_sdk_inventory_and_readonly_scope(project, monkeypatch, platform):
    ctx, runtime = project
    monkeypatch.setattr(capabilities, "_platform", platform)
    server = stdio_mcp.create_server(runtime, ctx.principal)
    listing = asyncio.run(server.request_handlers[types.ListToolsRequest](types.ListToolsRequest(method="tools/list")))
    tools = {tool.name: tool for tool in listing.root.tools}
    for name in subject.TOOLS:
        assert (name in tools) is (platform != "darwin")
        if name in tools:
            assert tools[name].annotations.readOnlyHint and not tools[name].annotations.destructiveHint
        args = dict(project_id=ctx.project_id, generation_relpath="generations/" + str(uuid4()))
        restricted = stdio_mcp.McpScope(project_id=ctx.project_id, allowed_tools={"rentgen_project_head"})
        with pytest.raises(CoreError) as error:
            stdio_mcp.validate_arguments(name, args, scope=restricted)
        assert error.value.code == "MCP_TOOL_FORBIDDEN"
        restricted = stdio_mcp.McpScope(project_id=str(uuid4()), allowed_tools={name})
        with pytest.raises(CoreError) as error:
            stdio_mcp.validate_arguments(name, args, scope=restricted)
        assert error.value.code == "MCP_PROJECT_FORBIDDEN"


@pytest.mark.parametrize("name", subject.TOOLS)
@pytest.mark.parametrize("change", [{"generation_relpath": "../private"}, {"generation_relpath": "generations/" + "A" * 64},
    {"generation_relpath": None}, {"snapshot_id": "a" * 64}, {"principal": "other"}, {"state_root": "/private"}])
def test_schema_refuses_paths_and_caller_authority(project, name, change):
    args = dict(project_id=project[0].project_id, generation_relpath="generations/" + str(uuid4()))
    with pytest.raises(CoreError) as error:
        stdio_mcp.validate_arguments(name, args | change)
    assert error.value.code == "INVALID_ARGUMENT"


def response(project, monkeypatch, kind="attribution"):
    ctx, runtime = project
    entry = catalog(ctx)
    commit(ctx, entry)
    monkeypatch.setattr(capabilities, "_platform", "linux")
    args = dict(project_id=ctx.project_id, generation_relpath=entry.generation_relpath)
    if kind in {"attribution", "error"}:
        name = "rentgen_generation_attribution" if kind == "attribution" else "rentgen_generation_verify"
        if kind == "error": args["generation_relpath"] = "generations/" + str(uuid4())
        reply = stdio_mcp._execute(runtime, ctx.principal, name, args, protocol_request_id="request-7")
    else:
        # Constructed transport value: retained IO is exercised by native/installed tests.
        scope = dict(family="generation", permissions=["project:read"], project_id=ctx.project_id,
            generation_relpath=entry.generation_relpath, kind="generation_verification", request_id=str(uuid4()),
            protocol_request_id="request-7", snapshot_id=entry.snapshot.snapshot_id,
            catalog_sha256=subject.digest(asdict(entry)))
        value = dict(catalog=asdict(entry), validation={"private": "PRIVATE_GENERATION_DETAIL"},
                     physical_state="verified_at_read", removal_permitted=False)
        reply = subject._reply(dict(result={"generation_verification": value}, request_id=scope["request_id"]), scope)
    document = dict(jsonrpc="2.0", id="request-7", result=reply.model_dump(by_alias=True, mode="json", exclude_none=True))
    return document, entry


def emit(project, document, mutate=None):
    ctx, runtime = project
    stream = io.BytesIO()
    guard = stdio_mcp._GuardedOutput(stream, runtime, ctx.principal)
    if mutate:
        original = guard._bytes
        done = False
        def encode(value):
            nonlocal done
            raw = original(value)
            if not done:
                done = True
                mutate()
            return raw
        guard._bytes = encode
    guard._write(json.dumps(document))
    return json.loads(stream.getvalue())["result"], stream.getvalue()


@pytest.mark.parametrize("kind", ["attribution", "verification", "error"])
def test_scope_is_private_and_representations_equal(project, monkeypatch, kind):
    document, _ = response(project, monkeypatch, kind)
    result, raw = emit(project, document)
    assert result["isError"] is (kind == "error")
    assert json.loads(result["content"][0]["text"]) == result["structuredContent"]
    assert b"rentgenOutputScope" not in raw
    if kind == "error": assert result["structuredContent"]["error"]["code"] == "GENERATION_UNREFERENCED"


@pytest.mark.parametrize("kind", ["attribution", "verification", "error"])
def test_real_revocation_after_final_encoding_redacts_success_and_errors(project, monkeypatch, kind):
    document, entry = response(project, monkeypatch, kind)
    ctx = project[0]
    def revoke():
        with ctx.state.transaction(ctx.principal, write=True) as tx:
            force_legacy_membership(tx, ctx.principal, set())
    result, raw = emit(project, document, revoke)
    assert result["isError"] and result["structuredContent"]["error"]["code"] == "PROJECT_FORBIDDEN"
    assert entry.generation_relpath.encode() not in raw and b"PRIVATE_GENERATION_DETAIL" not in raw
    assert b"GENERATION_UNREFERENCED" not in raw


@pytest.mark.parametrize("kind", ["attribution", "verification"])
def test_catalog_change_after_encoding_refuses_verified_claim_but_not_past_attribution(project, monkeypatch, kind):
    document, _ = response(project, monkeypatch, kind)
    ctx = project[0]
    def change():
        with ctx.state.transaction(ctx.principal, write=True) as tx:
            tx._connection.execute("UPDATE snapshots SET graph_hash=?", ("e" * 64,))
    result, raw = emit(project, document, change)
    assert result["isError"] is (kind == "verification")
    if kind == "verification":
        assert result["structuredContent"]["error"]["code"] == "SNAPSHOT_CORRUPT"
        assert b"PRIVATE_GENERATION_DETAIL" not in raw


@pytest.mark.parametrize("damage", ["scope", "text", "structured", "divergent", "id", "locator", "project", "kind", "digest", "permissions"])
def test_guard_rejects_lost_or_mismatched_authority(project, monkeypatch, damage):
    document, entry = response(project, monkeypatch, "verification")
    result = document["result"]
    scope = result["_meta"][subject.META]
    if damage == "scope": del result["_meta"]
    elif damage == "text": result["content"] = []
    elif damage == "structured": del result["structuredContent"]
    elif damage == "divergent": result["content"][0]["text"] = "{}"
    elif damage == "id": document["id"] = "another-request"
    elif damage == "locator": scope["generation_relpath"] = "generations/" + str(uuid4())
    elif damage == "project": scope["project_id"] = str(uuid4())
    elif damage == "kind": scope["kind"] = "generation_attribution"
    elif damage == "digest": scope["payload_sha256"] = "0" * 64
    else: scope["permissions"] = ["project:admin"]
    emitted, raw = emit(project, document)
    assert emitted["isError"] and emitted["structuredContent"]["error"]["code"] == "PROJECT_ACCESS_UNAVAILABLE"
    assert b"PRIVATE_GENERATION_DETAIL" not in raw and entry.generation_relpath.encode() not in raw


def test_final_wire_limit_and_authorization_after_limit_encoding(project, monkeypatch):
    document, _ = response(project, monkeypatch, "verification")
    monkeypatch.setattr(subject, "MAX_OUTPUT_BYTES", 500)
    result, raw = emit(project, deepcopy(document))
    assert result["structuredContent"]["error"]["code"] == "OUTPUT_LIMIT_EXCEEDED"
    assert len(raw) <= 500 and b"PRIVATE_GENERATION_DETAIL" not in raw
    ctx = project[0]
    def revoke():
        with ctx.state.transaction(ctx.principal, write=True) as tx:
            force_legacy_membership(tx, ctx.principal, set())
    result, raw = emit(project, document, revoke)
    assert result["structuredContent"]["error"]["code"] == "PROJECT_FORBIDDEN"


def test_revocation_during_initial_error_encoding_is_redacted(project, monkeypatch):
    ctx, runtime = project
    monkeypatch.setattr(capabilities, "_platform", "linux")
    original = subject.canonical
    revoked = False
    def encode(value):
        nonlocal revoked
        text = original(value)
        if type(value) is dict and "error" in value and not revoked:
            revoked = True
            with ctx.state.transaction(ctx.principal, write=True) as tx:
                force_legacy_membership(tx, ctx.principal, set())
        return text
    monkeypatch.setattr(subject, "canonical", encode)
    reply = stdio_mcp._execute(runtime, ctx.principal, "rentgen_generation_verify",
        dict(project_id=ctx.project_id, generation_relpath="generations/" + str(uuid4())))
    assert revoked and reply.structuredContent["error"]["code"] == "PROJECT_FORBIDDEN"


@pytest.mark.parametrize("loss", ["scope", "scope_and_text", "scope_and_structured"])
def test_error_with_lost_scope_is_not_disclosed(project, monkeypatch, loss):
    document, _ = response(project, monkeypatch, "error")
    result = document["result"]
    del result["_meta"]
    if loss == "scope_and_text": result["content"] = []
    if loss == "scope_and_structured": del result["structuredContent"]
    emitted, raw = emit(project, document)
    assert emitted["structuredContent"]["error"]["code"] == "PROJECT_ACCESS_UNAVAILABLE"
    assert b"GENERATION_UNREFERENCED" not in raw


def test_initial_wire_size_includes_sdk_envelope_and_protocol_id(project, monkeypatch):
    document, _ = response(project, monkeypatch)
    scope = document["result"]["_meta"][subject.META]
    scope["protocol_request_id"] = "x" * subject.MAX_OUTPUT_BYTES
    with pytest.raises(CoreError) as error:
        subject._reply(document["result"]["structuredContent"], scope)
    assert error.value.code == "OUTPUT_LIMIT_EXCEEDED"
