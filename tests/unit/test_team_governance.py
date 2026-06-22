import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.ai.mcp.server import TOOLS, handle_rentgen_team_governance
from src.api.team_governance_api import router
from src.services.rentgen.team_governance import build_team_governance


class FakeStore:
    def summary(self):
        return {
            "total_modules": 3,
            "avg_maintainability": 55.0,
            "modules_with_issues": 2,
            "by_domain": [
                {"domain": "Sales", "count": 2, "avg_maintainability": 42.0},
                {"domain": "HR", "count": 1, "avg_maintainability": 78.0},
            ],
        }

    def hotspots(self, limit=40, domain=None, min_fan_in=0):
        items = [
            {
                "module_path": "CommonModules/Sales/Ext/Module.bsl",
                "domain": "Sales",
                "risk": 85,
                "fan_in": 20,
                "reasons": [{"factor": "fan_in", "detail": "20", "weight": 10}],
            },
            {
                "module_path": "CommonModules/HR/Ext/Module.bsl",
                "domain": "HR",
                "risk": 35,
                "fan_in": 2,
                "reasons": [],
            },
        ]
        return items[:limit]


def test_team_governance_builds_owners_sla_and_snapshot(tmp_path):
    owners = tmp_path / "owners.json"
    snapshots = tmp_path / "snapshots.json"
    owners.write_text(
        json.dumps(
            [
                {
                    "id": "sales",
                    "name": "Sales Platform",
                    "lead": "lead",
                    "domains": ["Sales"],
                }
            ]
        ),
        encoding="utf-8",
    )

    report = build_team_governance(
        FakeStore(),
        limit=10,
        save_snapshot=True,
        owner_map_path=owners,
        snapshot_path=snapshots,
    )

    sales = next(area for area in report["areas"] if area["domain"] == "Sales")
    assert report["available"] is True
    assert sales["owner"]["name"] == "Sales Platform"
    assert sales["status"] == "red"
    assert report["release_board"]["review_queue"][0]["module_path"].endswith(
        "Module.bsl"
    )
    assert report["stored_snapshot"]["total"] == 1
    assert "Team Governance" in report["markdown"]


def test_team_governance_api_exposes_board(monkeypatch):
    monkeypatch.setattr(
        "src.api.team_governance_api.store_or_none", lambda: FakeStore()
    )

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    response = client.get("/api/v1/team-governance/board?limit=10")

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["areas"] == 2
    assert payload["summary"]["red_areas"] == 1


@pytest.mark.asyncio
async def test_mcp_team_governance_tool_is_registered(monkeypatch):
    monkeypatch.setattr("src.api._rentgen_store.store_or_none", lambda: FakeStore())

    names = {tool.name for tool in TOOLS}
    report = await handle_rentgen_team_governance({"limit": 10})

    assert "rentgen_team_governance" in names
    assert report["summary"]["review_queue"] == 2
    assert report["areas"][0]["owner"]["source"] in {
        "inferred-domain",
        "team_owners.json",
    }
