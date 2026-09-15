"""MCP contract tests for the bounded direct BSL writer."""

from types import SimpleNamespace

from rentgen_core import stdio_mcp
from test_stdio_native_archive import OPERATION, PROJECT, SNAPSHOT, _Runtime


def _proposal():
    return {
        "domain": "rentgen.source-proposal",
        "schema_version": 1,
        "source_ref": {
            "snapshot": {
                "project_id": PROJECT,
                "snapshot_id": SNAPSHOT,
                "manifest_hash": SNAPSHOT,
            },
            "layer_id": "base",
            "relative_path": "CommonModules/Test/Ext/Module.bsl",
            "raw_sha256": "a" * 64,
        },
        "original": {"size_bytes": 1, "raw_sha256": "a" * 64},
        "replacement": {
            "size_bytes": 1,
            "raw_sha256": "b" * 64,
            "base64": "Mg==",
        },
        "policy": {
            "encoding": "utf-8",
            "bom": False,
            "newline": "lf",
            "original_final_newline": True,
            "replacement_final_newline": True,
        },
        "content_id": "c" * 64,
    }


def _head():
    return {
        "project_id": PROJECT,
        "revision": 1,
        "source_revision": 1,
        "snapshot": {
            "project_id": PROJECT,
            "snapshot_id": SNAPSHOT,
            "manifest_hash": SNAPSHOT,
        },
    }


def test_mcp_exposes_direct_bsl_apply_recovery_contract():
    apply = {
        "project_id": PROJECT,
        "snapshot_id": SNAPSHOT,
        "operation_id": OPERATION,
        "expected_head": _head(),
        "proposal": _proposal(),
    }
    stdio_mcp.validate_arguments("rentgen_proposal_live_apply", apply)
    for name, args in (
        (
            "rentgen_proposal_live_undo",
            {"project_id": PROJECT, "operation_id": OPERATION},
        ),
        (
            "rentgen_proposal_live_status",
            {"project_id": PROJECT, "operation_id": OPERATION},
        ),
        (
            "rentgen_proposal_live_recover",
            {"project_id": PROJECT, "operation_id": OPERATION, "target": "original"},
        ),
    ):
        stdio_mcp.validate_arguments(name, args)


def test_mcp_dispatches_direct_bsl_apply_with_source_edit_scope(monkeypatch):
    runtime = _Runtime()
    principal = SimpleNamespace(id="tester", authority="local_os")
    calls = []

    monkeypatch.setattr(
        "rentgen_core.proposals.parse_proposal",
        lambda *args, **kwargs: "validated-proposal",
    )

    def fake_apply(ctx, operation_id, proposal, *, expected_head):
        calls.append((ctx, operation_id, proposal, expected_head))
        return {
            "schema": 1,
            "status": "applied",
            "live_source_written": True,
            "changed_paths": ["CommonModules/Test/Ext/Module.bsl"],
        }

    monkeypatch.setattr("rentgen_core.proposal_live_apply.apply_live", fake_apply)
    result = stdio_mcp._execute(
        runtime,
        principal,
        "rentgen_proposal_live_apply",
        {
            "project_id": PROJECT,
            "snapshot_id": SNAPSHOT,
            "operation_id": OPERATION,
            "expected_head": _head(),
            "proposal": _proposal(),
        },
        protocol_request_id=11,
        scope=stdio_mcp.McpScope(
            project_id=PROJECT,
            allowed_tools={"rentgen_proposal_live_apply"},
        ),
    )

    assert result.isError is False
    assert result.structuredContent["result"]["proposal_live"]["status"] == "applied"
    assert result.meta["rentgenOutputScope"]["permissions"] == [
        "analysis:run",
        "project:read",
        "source:edit",
    ]
    assert calls[0][1] == OPERATION
    assert calls[0][2] == "validated-proposal"
    assert calls[0][3].project_id == PROJECT
