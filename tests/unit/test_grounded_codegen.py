import pytest
from fastapi.testclient import TestClient

from src.ai.mcp.server import TOOLS, app as mcp_app, handle_rentgen_generate_grounded
from src.services.bsl_diagnostics import analyze_bsl
from src.services.rentgen.grounded_codegen import generate_grounded_bsl


def _metadata_object():
    return {
        "type": "Document",
        "name": "SalesOrder",
        "synonym": "Sales order",
        "ref": "Document.SalesOrder",
        "path": "Documents/SalesOrder",
        "counts": {
            "forms": 2,
            "modules": 1,
            "attributes": 6,
            "rights": 4,
        },
        "modules": [
            {
                "path": "Documents/SalesOrder/Ext/ObjectModule.bsl",
                "name": "ObjectModule",
                "type": "object",
                "size": 1024,
            }
        ],
        "forms": [],
        "rights": None,
    }


def _change_plan():
    return {
        "changed_modules": ["Documents/SalesOrder/Ext/ObjectModule.bsl"],
        "total_impact_edges": 325,
        "total_impacted_modules": 42,
        "modules": [
            {
                "module_path": "Documents/SalesOrder/Ext/ObjectModule.bsl",
                "impact_total": 325,
                "quality": {"risk": 74},
                "performance_risks": [{"severity": "high", "factor": "query-in-loop"}],
                "impacted_hotspots": [{"module_path": "CommonModules/Sales/Ext/Module.bsl"}],
                "covering_tests": [
                    {
                        "id": "mapped:sales-order",
                        "framework": "YAxUnit",
                        "selector": "SalesOrderPosting",
                        "priority": "high",
                        "status": "mapped",
                        "reason": "Exact local test match.",
                        "command": "YAxUnit/Vanessa: run SalesOrderPosting",
                        "confidence": 0.9,
                    }
                ],
            }
        ],
        "caveats": [],
    }


def test_grounded_codegen_is_deterministic_and_context_rich():
    kwargs = {
        "prompt": "Create safe posting helper for sales order",
        "code_type": "function",
        "module_path": "Documents/SalesOrder/Ext/ObjectModule.bsl",
        "metadata_obj": _metadata_object(),
        "change_plan": _change_plan(),
        "its_context": [{"section_title": "Posting documents", "source_file": "its.md", "score": 0.9}],
    }

    first = generate_grounded_bsl(**kwargs)
    second = generate_grounded_bsl(**kwargs)

    assert first["code"] == second["code"]
    assert first["provider"]["mode"] == "local-grounded-template"
    assert first["provider"]["deterministic"] is True
    assert "Function GeneratedFunctionSalesOrderDocumentsSalesOrder" in first["code"]
    assert "Document.SalesOrder" in first["code"]
    assert "edges=325" in first["code"]
    assert "TODO" not in first["code"]
    assert 'Result.Insert("status", "guarded-review-ready")' in first["code"]
    assert 'Result.Insert("requiresOwnerDecision", True)' in first["code"]
    assert first["artifact"]["language"] == "bsl"
    assert any(control["id"] == "rentgen-risk" for control in first["risk_controls"])
    assert any(action["selector"] == "SalesOrderPosting" for action in first["test_actions"])
    assert first["test_actions"][0]["status"] == "guarded-contract"

    diagnostics = analyze_bsl(first["code"], module_path=kwargs["module_path"])
    assert diagnostics["metrics"]["functions"] == 1
    assert diagnostics["metrics"]["procedures"] == 0
    assert not diagnostics["diagnostics"]


def test_grounded_codegen_never_returns_todo_scaffolds():
    prompt = "Create posting command with audit"

    procedure = generate_grounded_bsl(
        prompt=prompt,
        code_type="procedure",
        module_path="Documents/SalesOrder/Ext/ObjectModule.bsl",
        metadata_obj=_metadata_object(),
        change_plan=_change_plan(),
    )
    test = generate_grounded_bsl(
        prompt=prompt,
        code_type="test",
        module_path="Documents/SalesOrder/Ext/ObjectModule.bsl",
        metadata_obj=_metadata_object(),
        change_plan=_change_plan(),
    )

    for generated in (procedure, test):
        assert "TODO" not in generated["code"]
        assert "guarded-review-ready" in generated["code"]
        assert "RENTGEN-GUARD" in generated["code"]

    assert 'OperationContract.Insert("requiresRightsReview", True)' in procedure["code"]
    assert "Assert(Result <> Undefined);" in test["code"]


def test_bsl_diagnostics_supports_english_aliases():
    code = """
Function UnsafeQuery(Context) Export
    For Each Row In Context.Rows Do
        Query = New Query("SELECT * FROM Catalog.Products");
        Query.Execute();
    EndDo;
    SetPrivilegedMode(True);
    Execute("Message('x')");
EndFunction
"""

    result = analyze_bsl(code)
    codes = {diagnostic["code"] for diagnostic in result["diagnostics"]}

    assert result["metrics"]["functions"] == 1
    assert result["metrics"]["metadata_refs"] == 1
    assert {"select-star", "query-in-loop", "privileged-mode", "dynamic-execute", "undocumented-export"} <= codes


@pytest.mark.asyncio
async def test_mcp_grounded_generation_tool_is_registered_and_callable():
    assert "rentgen_generate_grounded" in {tool.name for tool in TOOLS}

    result = await handle_rentgen_generate_grounded(
        {
            "prompt": "Create status function",
            "type": "function",
            "include_its_context": False,
            "include_requirement_impact": False,
        }
    )

    assert result["artifact"]["provider"] == "local-grounded-template"
    assert result["grounding"]["provider"]["deterministic"] is True
    assert result["diagnostics"]["metrics"]["functions"] == 1


def test_mcp_alias_routes_support_mounted_backend_paths():
    client = TestClient(mcp_app)

    tools_response = client.get("/tools")
    root_response = client.get("/")

    assert tools_response.status_code == 200
    assert root_response.status_code == 200
    assert "rentgen_generate_grounded" in {
        tool["name"] for tool in tools_response.json()["tools"]
    }
