"""MCP contract tests for the bounded direct BSL writer."""

import json
from types import SimpleNamespace

import pytest

from rentgen_core import cli, stdio_mcp
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


@pytest.mark.parametrize("family", ["metadata", "proposal"])
def test_live_status_transports_preserve_unknown_write_outcome(monkeypatch, capsys, family):
    """Transport-only DTO contract; native journal behavior is tested separately."""
    runtime = _Runtime()
    principal = SimpleNamespace(id="tester", authority="local_os")
    status = {"schema": 1, "project_id": PROJECT, "operation_id": OPERATION,
              "status": "OUTCOME_UNKNOWN", "phase": "applying", "live_source_written": None}
    monkeypatch.setattr(f"rentgen_core.{family}_live_apply.get_live_status", lambda *a: status)
    tool = f"rentgen_{family}_live_status"
    args = {"project_id": PROJECT, "operation_id": OPERATION}
    argv = [f"{family}-live-status", "--registry", "unused.sqlite3",
            "--project", PROJECT, "--operation-id", OPERATION]
    if family == "metadata":
        args["snapshot_id"] = SNAPSHOT
        argv += ["--snapshot", SNAPSHOT]
    result = stdio_mcp._execute(runtime, principal, tool, args,
        scope=stdio_mcp.McpScope(project_id=PROJECT, allowed_tools={tool}))
    assert result.isError is False
    assert result.structuredContent["result"][f"{family}_live"] == status
    assert json.loads(result.content[0].text) == result.structuredContent

    monkeypatch.setattr(cli, "_runtime", lambda _: runtime)
    monkeypatch.setattr(cli, "current_local_principal", lambda: principal)
    assert cli.main(argv) == 0
    output = capsys.readouterr()
    assert not output.err
    assert json.loads(output.out)["result"] == status


@pytest.fixture(autouse=True)
def windows_dispatch_contract(monkeypatch):
    """These tests inject Windows-native operations; not Linux capability acceptance."""
    from rentgen_core import capabilities
    monkeypatch.setattr(capabilities, "_platform", "win32")
