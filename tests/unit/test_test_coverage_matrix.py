import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.ai.mcp.server import TOOLS, handle_rentgen_test_coverage_matrix
from src.api import rentgen_api
from src.services.rentgen import test_inventory
from src.services.rentgen.test_coverage_matrix import build_test_coverage_matrix


MODULE = "Documents/Order/Ext/ObjectModule.bsl"


class FakeStore:
    def get_module_risk(self, module_path):
        return {
            "module_path": module_path,
            "risk": 74,
            "maintainability_score": 30,
            "has_n_plus_one": False,
            "has_select_star": False,
        }

    def module_impact(self, module_path, max_depth=5, max_edges=600):
        return {
            "canonical": {
                "object_name": "Order",
                "module_kind": "ObjectModule",
                "source": "fake",
            },
            "graph_modules": [
                {
                    "name": "Order.ObjectModule",
                    "object_name": "Order",
                    "module_kind": "ObjectModule",
                    "fan_in": 1,
                    "fan_out": 2,
                    "n_subs": 3,
                    "max_complexity": 5,
                }
            ],
            "entry_subroutines": 2,
            "total": 320,
            "impacted_modules": [{"module": "CommonModules/Sales/Ext/Module.bsl", "edges": 4}],
        }

    def hotspots_for_graph_modules(self, module_names, limit=10):
        return []


def _make_test_inventory(tmp_path, monkeypatch):
    tests_root = tmp_path / "tests" / "bsl"
    tests_root.mkdir(parents=True)
    (tests_root / "order_tests.bsl").write_text(
        """// yaxunit
Procedure TestOrderPostingCreditLimit()
    // Order posting credit limit
EndProcedure
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(test_inventory, "ROOT", tmp_path)
    test_inventory.build_test_inventory.cache_clear()


def test_test_coverage_matrix_finds_exact_local_tests(tmp_path, monkeypatch):
    _make_test_inventory(tmp_path, monkeypatch)

    report = build_test_coverage_matrix(FakeStore(), changed_modules=[MODULE])
    row = report["modules"][0]

    assert report["summary"]["changed_modules"] == 1
    assert report["summary"]["covered"] == 1
    assert row["coverage_status"] == "covered"
    assert row["exact_tests"][0]["selector"] == "TestOrderPostingCreditLimit"
    assert row["priority"] == "high"
    assert "Risk-Driven Test Coverage Matrix" in report["markdown"]


def test_test_coverage_matrix_api(tmp_path, monkeypatch):
    _make_test_inventory(tmp_path, monkeypatch)
    monkeypatch.setattr(rentgen_api, "store_or_none", lambda: FakeStore())

    app = FastAPI()
    app.include_router(rentgen_api.router)
    client = TestClient(app)

    response = client.post("/rentgen/test-coverage-matrix", json={"changed_modules": [MODULE]})

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["covered"] == 1
    assert payload["modules"][0]["exact_tests"]


@pytest.mark.asyncio
async def test_mcp_test_coverage_matrix_tool_is_registered(tmp_path, monkeypatch):
    _make_test_inventory(tmp_path, monkeypatch)
    monkeypatch.setattr("src.api._rentgen_store.store_or_none", lambda: FakeStore())

    result = await handle_rentgen_test_coverage_matrix({"changed_modules": [MODULE]})

    assert "rentgen_test_coverage_matrix" in {tool.name for tool in TOOLS}
    assert result["store"] is True
    assert result["summary"]["covered"] == 1
