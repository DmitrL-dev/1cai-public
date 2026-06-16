import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.ai.mcp.server import TOOLS, handle_rentgen_incident_report
from src.api.operations_api import router
from src.services.rentgen.incident_response import build_incident_report


TJ_LOG = """12:00:01.000000-3000000,SDBL,p:1:1:1,Usr=Admin,Context='CommonModule.Sales.Module : 42 : Query.Execute()',Sql='SELECT * FROM Sales',Sdbl='SELECT * FROM Sales',Rows=100
12:00:02.000000-200000,TLOCK,p:1:1:1,Usr=Admin,Context='CommonModule.Sales.Module : 50 : Write()'
12:00:03.000000-0,TDEADLOCK,p:1:1:1,Usr=Admin,Context='CommonModule.Sales.Module : 60 : Post()'
"""


class FakeStore:
    def get_module_risk(self, module_path):
        return {
            "module_path": module_path,
            "domain": "Sales",
            "risk": 82,
            "has_n_plus_one": False,
            "has_select_star": True,
            "reasons": [],
        }

    def module_impact(self, module_path, max_depth=5, max_edges=300):
        return {
            "canonical": {"object_name": "Sales", "module_kind": "Module", "source": "runtime_module"},
            "graph_modules": [{"name": "Sales", "fan_in": 12, "fan_out": 3, "n_subs": 2}],
            "entry_subroutines": 2,
            "total": 320,
            "impacted_modules": [{"module": "CriticalPath", "edges": 90}],
        }

    def hotspots_for_graph_modules(self, module_names, limit=8):
        return [
            {
                "module_path": "CommonModules/CriticalPath/Ext/Module.bsl",
                "domain": "Sales",
                "risk": 75,
                "fan_in": 10,
                "reasons": [],
            }
        ][:limit]

    def summary(self):
        return {
            "total_modules": 2,
            "avg_maintainability": 48,
            "modules_with_issues": 1,
            "by_domain": [{"domain": "Sales", "count": 2, "avg_maintainability": 42}],
        }

    def hotspots(self, limit=40, domain=None, min_fan_in=0):
        return [
            {
                "module_path": "CommonModules/Sales/Ext/Module.bsl",
                "domain": "Sales",
                "risk": 82,
                "fan_in": 12,
                "reasons": [],
            }
        ][:limit]


def _tj_dir(tmp_path):
    log_file = tmp_path / "rphost" / "26062200.log"
    log_file.parent.mkdir(parents=True)
    log_file.write_text(TJ_LOG, encoding="utf-8")
    return log_file.parent.parent


def test_incident_report_links_tj_to_modules_tests_and_runbook(tmp_path):
    report = build_incident_report(
        FakeStore(),
        incident_title="Slow posting",
        description="slow timeout lock",
        log_path=str(_tj_dir(tmp_path)),
        changed_modules=["CommonModules/Sales/Ext/Module.bsl"],
        min_duration_ms=1,
        top_n=5,
    )

    assert report["decision"]["status"] in {"critical", "high"}
    assert report["summary"]["hotspots"] == 1
    assert report["summary"]["deadlocks"] == 1
    assert report["module_plan"]
    assert report["test_matrix"]["summary"]["changed_modules"] >= 1
    assert report["recommended_actions"]
    assert "Incident Response" in report["markdown"]


def test_operations_api_exposes_incident_report(tmp_path, monkeypatch):
    monkeypatch.setattr("src.api.operations_api.store_or_none", lambda: FakeStore())

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    response = client.post(
        "/api/v1/operations/incident-report",
        json={
            "incident_title": "Slow posting",
            "description": "slow lock",
            "log_path": str(_tj_dir(tmp_path)),
            "min_duration_ms": 1,
            "top_n": 5,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["hotspots"] == 1
    assert payload["decision"]["severity_score"] > 0


@pytest.mark.asyncio
async def test_mcp_incident_report_tool_is_registered(tmp_path, monkeypatch):
    monkeypatch.setattr("src.api._rentgen_store.store_or_none", lambda: FakeStore())

    names = {tool.name for tool in TOOLS}
    report = await handle_rentgen_incident_report(
        {
            "incident_title": "Slow posting",
            "description": "slow lock",
            "log_path": str(_tj_dir(tmp_path)),
            "min_duration_ms": 1,
            "top_n": 5,
        }
    )

    assert "rentgen_incident_report" in names
    assert report["summary"]["hotspots"] == 1
    assert report["runbook"]
