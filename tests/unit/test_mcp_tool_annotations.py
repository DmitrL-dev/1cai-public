"""Actual SDK tool listings describe source writes without granting authority."""

import asyncio

import pytest
from mcp import types

from rentgen_core.context import Principal
from rentgen_core.errors import CoreError
from rentgen_core.stdio_mcp import McpScope, create_server


@pytest.fixture(autouse=True)
def windows_adapter_contract(monkeypatch):
    from rentgen_core import capabilities
    monkeypatch.setattr(capabilities, "_platform", "win32")


def _listed(scope=None):
    server = create_server(object(), Principal("fixture", "local_os"), scope=scope)
    result = asyncio.run(
        server.request_handlers[types.ListToolsRequest](
            types.ListToolsRequest(method="tools/list")
        )
    )
    return {tool.name: tool for tool in result.root.tools}


@pytest.mark.parametrize("family", ["proposal", "metadata"])
@pytest.mark.parametrize("action", ["apply", "undo", "recover"])
def test_live_source_writers_are_not_advertised_as_read_only_or_additive(family, action):
    annotation = _listed()[f"rentgen_{family}_live_{action}"].annotations
    assert annotation.readOnlyHint is False
    assert annotation.destructiveHint is True
    assert annotation.openWorldHint is False


@pytest.mark.parametrize("family", ["proposal", "metadata"])
def test_live_status_remains_read_only(family):
    annotation = _listed()[f"rentgen_{family}_live_status"].annotations
    assert annotation.readOnlyHint is True
    assert annotation.destructiveHint is False


def test_managed_repair_scope_cannot_advertise_or_admit_live_writes():
    allowed = {
        "rentgen_draft_start", "rentgen_draft_read",
        "rentgen_draft_edit", "rentgen_draft_check",
    }
    scope = McpScope(allowed_tools=allowed)
    assert set(_listed(scope)) == allowed
    with pytest.raises(CoreError) as error:
        scope.require_tool("rentgen_proposal_live_apply")
    assert error.value.code == "MCP_TOOL_FORBIDDEN"


def test_draft_revision_write_remains_additive_but_not_read_only():
    annotation = _listed()["rentgen_draft_edit"].annotations
    assert annotation.readOnlyHint is False
    assert annotation.destructiveHint is False
