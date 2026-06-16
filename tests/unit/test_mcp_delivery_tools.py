import pytest

from src.ai.mcp.server import (
    TOOLS,
    handle_rentgen_its_context,
    handle_rentgen_its_search,
    handle_rentgen_performer_analyze,
)


TJ_LOG = """12:45:03.456789-3000000,SDBL,p:1:1:1,Usr=Admin,Context='Document.Sales.ObjectModule : 145 : Result = Query.Execute()',Sql='SELECT T1.Name FROM Document123 T1',Sdbl='SELECT Name FROM Document.Sales',Rows=500
12:45:05.000000-100000,TLOCK,p:1:1:1,Usr=Admin,Context='Document.Sales.ObjectModule : 200 : Movements.Write()'
12:45:06.000000-0,TDEADLOCK,p:1:1:1,Usr=Admin,Context='Document.Sales.ObjectModule : 210 : Write()'
"""


@pytest.mark.asyncio
async def test_mcp_delivery_tools_are_registered_and_its_is_offline_first():
    names = {tool.name for tool in TOOLS}

    assert {
        "rentgen_its_search",
        "rentgen_its_context",
        "rentgen_performer_analyze",
        "rentgen_performer_impact",
    } <= names

    search = await handle_rentgen_its_search({"question": "managed form", "limit": 1})
    context = await handle_rentgen_its_context({"question": "managed form", "limit": 1})

    assert search["mode"] == "offline"
    assert "results" in search
    assert context["mode"] == "offline"
    assert "context" in context


@pytest.mark.asyncio
async def test_mcp_performer_analyze_returns_serializable_report(tmp_path):
    log_dir = tmp_path / "rphost_1"
    log_dir.mkdir()
    (log_dir / "26022200.log").write_text(TJ_LOG, encoding="utf-8")

    report = await handle_rentgen_performer_analyze(
        {
            "log_path": str(tmp_path),
            "min_duration_ms": 0.1,
            "top_n": 5,
        }
    )

    assert report["total_events"] == 3
    assert report["hotspots"][0]["module"] == "Document.Sales.ObjectModule"
    assert report["lock_waits_count"] == 1
    assert report["deadlocks_count"] == 1
