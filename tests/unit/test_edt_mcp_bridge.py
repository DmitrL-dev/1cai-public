import httpx
import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.ai.mcp.server import (
    TOOLS,
    handle_edt_mcp_call,
    handle_edt_mcp_connection_config,
    handle_edt_mcp_live_tools,
    handle_edt_mcp_plan,
    handle_edt_mcp_status,
    handle_edt_mcp_toolsets,
)
from src.api.edt_mcp_api import router
from src.services.edt_mcp_bridge import (
    build_connection_config,
    call_live_edt_mcp_tool,
    check_edt_mcp_status,
    classify_edt_mcp_tool,
    guard_edt_mcp_tool_call,
    list_edt_mcp_toolsets,
    list_live_edt_mcp_tools,
    normalize_edt_mcp_base_url,
    plan_edt_mcp_workflow,
)
from src.services.rentgen import approval_workflow as approvals


class FakeAuditLogger:
    def __init__(self):
        self.entries = []

    def log_action(self, **kwargs):
        self.entries.append(kwargs)


def test_edt_mcp_catalog_has_high_value_toolsets():
    catalog = list_edt_mcp_toolsets()
    toolset_ids = {item["id"] for item in catalog["toolsets"]}
    tool_names = {tool for item in catalog["toolsets"] for tool in item["tools"]}

    assert {"core", "code", "forms", "testing", "metadata"} <= toolset_ids
    assert "validate_query" in tool_names
    assert "get_form_layout_snapshot" in tool_names
    assert "run_yaxunit_tests" in tool_names
    assert catalog["license"]["public"] == "AGPL-3.0"


def test_edt_mcp_plan_maps_query_and_forms_to_native_tools():
    query_plan = plan_edt_mcp_workflow("validate query and then change module code")
    form_plan = plan_edt_mcp_workflow("review form layout snapshot")

    assert "query_validation" in query_plan["matched_workflows"]
    assert "validate_query" in query_plan["edt_tools"]
    assert "rentgen_generate_grounded" in query_plan["one_cai_tools"]
    assert "form_review" in form_plan["matched_workflows"]
    assert "get_form_layout_snapshot" in form_plan["edt_tools"]
    assert "forms" in form_plan["toolsets_to_enable"]


def test_edt_mcp_connection_config_contains_client_snippets():
    config = build_connection_config("http://localhost:8765/")
    config_from_mcp_url = build_connection_config("http://localhost:8765/mcp")

    assert config["mcp_url"] == "http://localhost:8765/mcp"
    assert config_from_mcp_url["base_url"] == "http://localhost:8765"
    assert config_from_mcp_url["mcp_url"] == "http://localhost:8765/mcp"
    assert "vscode" in config["clients"]
    assert "cursor" in config["clients"]
    assert any(
        "nativeFormBufferedLayoutRender" in item for item in config["edt_preconditions"]
    )


def test_edt_mcp_rejects_remote_base_url_by_default():
    with pytest.raises(ValueError):
        normalize_edt_mcp_base_url("http://example.com:8765")

    assert (
        normalize_edt_mcp_base_url("http://127.0.0.1:8765/mcp")
        == "http://127.0.0.1:8765"
    )


def test_edt_mcp_api_exposes_catalog_plan_and_config():
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    catalog = client.get("/api/v1/edt-mcp/toolsets")
    plan = client.post("/api/v1/edt-mcp/plan", json={"task": "run YAxUnit tests"})
    config = client.get(
        "/api/v1/edt-mcp/connection-config?base_url=http://localhost:8765"
    )
    remote_config = client.get(
        "/api/v1/edt-mcp/connection-config?base_url=http://example.com:8765"
    )

    assert catalog.status_code == 200
    assert catalog.json()["summary"]["toolsets"] >= 9
    assert plan.status_code == 200
    assert "run_yaxunit_tests" in plan.json()["edt_tools"]
    assert config.status_code == 200
    assert config.json()["mcp_url"].endswith("/mcp")
    assert remote_config.status_code == 400


def test_edt_mcp_safety_gate_classifies_read_write_and_unknown_tools():
    read_tool = classify_edt_mcp_tool("validate_query")
    write_tool = classify_edt_mcp_tool("write_module_source")
    unknown_tool = classify_edt_mcp_tool("dangerous_custom_tool")
    unknown_read_prefix = classify_edt_mcp_tool("get_and_delete_everything")
    annotated_read_tool = classify_edt_mcp_tool(
        "get_new_safe_tool",
        annotations={
            "readOnlyHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )

    assert read_tool["risk"] == "read"
    assert read_tool["requires_confirmation"] is False
    assert write_tool["risk"] == "write"
    assert write_tool["requires_confirmation"] is True
    assert unknown_tool["risk"] == "unknown"
    assert unknown_tool["requires_confirmation"] is True
    assert unknown_read_prefix["risk"] == "unknown"
    assert unknown_read_prefix["requires_confirmation"] is True
    assert annotated_read_tool["risk"] == "read"
    assert annotated_read_tool["requires_confirmation"] is False

    blocked = guard_edt_mcp_tool_call("write_module_source", confirm=False)
    missing_context = guard_edt_mcp_tool_call("write_module_source", confirm=True)
    allowed = guard_edt_mcp_tool_call(
        "write_module_source",
        confirm=True,
        actor="developer",
        approval_reason="Approved for the focused unit test change.",
    )

    assert blocked["allowed"] is False
    assert blocked["blocked"] is True
    assert {"confirm", "actor", "approval_reason"} <= set(blocked["policy"]["missing"])
    assert missing_context["allowed"] is False
    assert {"actor", "approval_reason"} <= set(missing_context["policy"]["missing"])
    assert allowed["allowed"] is True
    assert allowed["policy"]["actor"] == "developer"


def test_edt_mcp_safety_gate_accepts_approved_record(tmp_path, monkeypatch):
    monkeypatch.setattr(approvals, "STORE_PATH", tmp_path / "approvals.json")
    record = approvals.create_approval_record(
        tool_name="write_module_source",
        actor="developer",
        approval_reason="Approved after impact review and test selection.",
        risk="write",
        argument_constraints={"modulePath": "CommonModules/X/Ext/Module.bsl"},
    )
    approvals.update_approval_status(record["id"], status="approved", actor="architect")

    allowed = guard_edt_mcp_tool_call(
        "write_module_source",
        arguments={"modulePath": "CommonModules/X/Ext/Module.bsl"},
        confirm=True,
        actor="developer",
        approval_id=record["id"],
    )
    mismatch = guard_edt_mcp_tool_call(
        "write_module_source",
        arguments={"modulePath": "CommonModules/Y/Ext/Module.bsl"},
        confirm=True,
        actor="developer",
        approval_id=record["id"],
    )

    assert allowed["allowed"] is True
    assert allowed["policy"]["approval_source"] == "record"
    assert allowed["policy"]["approval_validation"]["valid"] is True
    assert mismatch["allowed"] is False
    assert (
        mismatch["policy"]["approval_validation"]["reason"]
        == "argument_mismatch:modulePath"
    )


def test_edt_mcp_strict_policy_requires_approval_record(monkeypatch):
    monkeypatch.setenv("EDT_MCP_REQUIRE_APPROVAL_RECORD", "1")

    blocked = guard_edt_mcp_tool_call(
        "write_module_source",
        confirm=True,
        actor="developer",
        approval_reason="Approved after impact review and test selection.",
    )

    assert blocked["allowed"] is False
    assert "approval_id" in blocked["policy"]["missing"]
    assert blocked["policy"]["requires_approval_record"] is True


@pytest.mark.asyncio
async def test_edt_mcp_call_blocks_write_tool_before_network():
    audit = FakeAuditLogger()
    result = await call_live_edt_mcp_tool(
        "write_module_source",
        {"modulePath": "CommonModules/X/Ext/Module.bsl"},
        base_url="http://127.0.0.1:1",
        confirm=False,
        audit_logger=audit,
    )

    assert result["status"] == "blocked"
    assert result["classification"]["risk"] == "write"
    assert result["policy"]["missing"]
    assert audit.entries
    assert audit.entries[0]["action"] == "edt_mcp.call.blocked"
    assert audit.entries[0]["metadata"]["arguments"]["keys"] == ["modulePath"]


@pytest.mark.asyncio
async def test_edt_mcp_call_requires_actor_and_reason_even_when_confirmed():
    audit = FakeAuditLogger()
    result = await call_live_edt_mcp_tool(
        "write_module_source",
        {"modulePath": "CommonModules/X/Ext/Module.bsl"},
        base_url="http://127.0.0.1:1",
        confirm=True,
        audit_logger=audit,
    )

    assert result["status"] == "blocked"
    assert {"actor", "approval_reason"} <= set(result["policy"]["missing"])
    assert audit.entries[0]["metadata"]["approval"]["reason_present"] is False


@respx.mock
@pytest.mark.asyncio
async def test_edt_mcp_successful_call_consumes_approval_record(tmp_path, monkeypatch):
    monkeypatch.setattr(approvals, "STORE_PATH", tmp_path / "approvals.json")
    record = approvals.create_approval_record(
        tool_name="write_module_source",
        actor="developer",
        approval_reason="Approved after impact review and test selection.",
        risk="write",
        argument_constraints={"modulePath": "CommonModules/X/Ext/Module.bsl"},
    )
    approvals.update_approval_status(record["id"], status="approved", actor="architect")
    base = "http://127.0.0.1:8765"
    respx.post(f"{base}/mcp").mock(
        side_effect=[
            httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": {"serverInfo": {"name": "EDT-MCP"}},
                },
                headers={"Mcp-Session-Id": "session-1"},
            ),
            httpx.Response(202),
            httpx.Response(
                200, json={"jsonrpc": "2.0", "id": 3, "result": {"content": []}}
            ),
        ]
    )

    result = await call_live_edt_mcp_tool(
        "write_module_source",
        {"modulePath": "CommonModules/X/Ext/Module.bsl"},
        base_url=base,
        confirm=True,
        actor="developer",
        approval_id=record["id"],
    )
    stored = approvals.get_approval_record(record["id"])

    assert result["status"] == "ok"
    assert result["policy"]["approval_source"] == "record"
    assert stored["status"] == "used"


@pytest.mark.asyncio
async def test_edt_mcp_call_rejects_remote_url_even_for_read_tool():
    result = await call_live_edt_mcp_tool(
        "validate_query",
        {"queryText": "SELECT 1"},
        base_url="http://example.com:8765",
        confirm=False,
    )

    assert result["status"] == "invalid_url"
    assert result["available"] is False


@respx.mock
@pytest.mark.asyncio
async def test_edt_mcp_status_reads_health_and_server_info():
    base = "http://127.0.0.1:8765"
    respx.get(f"{base}/health").mock(
        return_value=httpx.Response(200, json={"status": "ok"})
    )
    respx.get(f"{base}/mcp").mock(
        return_value=httpx.Response(200, json={"server": "EDT MCP"})
    )

    status = await check_edt_mcp_status(base)

    assert status["available"] is True
    assert status["status"] == "ok"
    assert status["server_info"]["server"] == "EDT MCP"


@respx.mock
@pytest.mark.asyncio
async def test_edt_mcp_live_tools_uses_json_rpc_and_enriches_risk():
    base = "http://127.0.0.1:8765"
    route = respx.post(f"{base}/mcp").mock(
        side_effect=[
            httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": {"serverInfo": {"name": "EDT-MCP"}},
                },
                headers={"Mcp-Session-Id": "session-1"},
            ),
            httpx.Response(202),
            httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": 2,
                    "result": {
                        "tools": [
                            {"name": "validate_query", "description": "Validate query"},
                            {
                                "name": "write_module_source",
                                "description": "Write module",
                            },
                            {
                                "name": "get_future_read_tool",
                                "description": "Future read tool",
                                "annotations": {
                                    "readOnlyHint": True,
                                    "idempotentHint": True,
                                    "openWorldHint": False,
                                },
                            },
                        ]
                    },
                },
            ),
        ]
    )

    tools = await list_live_edt_mcp_tools(base)

    assert route.called
    assert tools["available"] is True
    assert tools["summary"]["tools"] == 3
    by_name = {item["name"]: item for item in tools["tools"]}
    assert by_name["validate_query"]["classification"]["requires_confirmation"] is False
    assert (
        by_name["write_module_source"]["classification"]["requires_confirmation"]
        is True
    )
    assert (
        by_name["get_future_read_tool"]["classification"]["requires_confirmation"]
        is False
    )
    assert (
        by_name["get_future_read_tool"]["classification"]["source"]
        == "live_annotations"
    )


def test_edt_mcp_api_blocks_unconfirmed_write_call():
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    response = client.post(
        "/api/v1/edt-mcp/call",
        json={
            "tool_name": "write_module_source",
            "arguments": {"modulePath": "CommonModules/X/Ext/Module.bsl"},
            "base_url": "http://127.0.0.1:1",
            "confirm": False,
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "blocked"


def test_edt_mcp_api_forwards_actor_and_approval_context(monkeypatch):
    captured = {}

    async def fake_call_live_edt_mcp_tool(tool_name, arguments, **kwargs):
        captured.update({"tool_name": tool_name, "arguments": arguments, **kwargs})
        return {
            "available": True,
            "status": "ok",
            "blocked": False,
            "tool_name": tool_name,
            "classification": {"risk": "write", "requires_confirmation": True},
            "policy": {"actor": kwargs.get("actor"), "missing": []},
        }

    monkeypatch.setattr(
        "src.api.edt_mcp_api.call_live_edt_mcp_tool", fake_call_live_edt_mcp_tool
    )

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    response = client.post(
        "/api/v1/edt-mcp/call",
        headers={"X-1CAI-Actor": "architect"},
        json={
            "tool_name": "write_module_source",
            "arguments": {"modulePath": "CommonModules/X/Ext/Module.bsl"},
            "base_url": "http://127.0.0.1:8765",
            "confirm": True,
            "approval_reason": "Approved after impact review and test selection.",
            "approval_ticket": "CHG-42",
        },
    )

    assert response.status_code == 200
    assert captured["actor"] == "architect"
    assert (
        captured["approval_reason"]
        == "Approved after impact review and test selection."
    )
    assert captured["approval_ticket"] == "CHG-42"


@pytest.mark.asyncio
async def test_edt_mcp_mcp_tools_are_registered():
    names = {tool.name for tool in TOOLS}

    catalog = await handle_edt_mcp_toolsets({})
    plan = await handle_edt_mcp_plan({"task": "rename metadata object safely"})
    config = await handle_edt_mcp_connection_config(
        {"base_url": "http://127.0.0.1:8765"}
    )
    blocked = await handle_edt_mcp_call({"tool_name": "write_module_source"})

    assert {
        "edt_mcp_toolsets",
        "edt_mcp_plan",
        "edt_mcp_connection_config",
        "edt_mcp_status",
        "edt_mcp_live_tools",
        "edt_mcp_call",
    } <= names
    assert catalog["summary"]["tools"] >= 60
    assert "metadata_refactoring" in plan["matched_workflows"]
    assert plan["requires_confirmation"] is True
    assert config["mcp_url"] == "http://127.0.0.1:8765/mcp"
    assert blocked["status"] == "blocked"


@respx.mock
@pytest.mark.asyncio
async def test_edt_mcp_mcp_status_and_live_tools_handlers():
    base = "http://127.0.0.1:8765"
    respx.get(f"{base}/health").mock(
        return_value=httpx.Response(200, json={"status": "ok"})
    )
    respx.get(f"{base}/mcp").mock(
        return_value=httpx.Response(200, json={"server": "EDT MCP"})
    )
    respx.post(f"{base}/mcp").mock(
        side_effect=[
            httpx.Response(
                200,
                json={"jsonrpc": "2.0", "id": 1, "result": {}},
                headers={"Mcp-Session-Id": "s1"},
            ),
            httpx.Response(202),
            httpx.Response(
                200, json={"jsonrpc": "2.0", "id": 2, "result": {"tools": []}}
            ),
        ]
    )

    status = await handle_edt_mcp_status({"base_url": base})
    live = await handle_edt_mcp_live_tools({"base_url": base})

    assert status["available"] is True
    assert live["available"] is True
    assert live["summary"]["tools"] == 0
