from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.management_api import router
from src.services.rentgen.executive_dashboard import build_executive_dashboard


class FakeStore:
    def summary(self):
        return {
            "total_modules": 4,
            "avg_maintainability": 62.5,
            "modules_with_issues": 2,
            "by_domain": [
                {"domain": "Sales", "count": 3, "avg_maintainability": 44.0},
                {"domain": "HR", "count": 1, "avg_maintainability": 82.0},
            ],
        }

    def get_stats(self):
        return {"call_edges": 1234, "modules": 4, "quality_modules": 4}

    def hotspots(self, limit=40, domain=None, min_fan_in=0):
        return [
            {
                "module_path": "CommonModules/Sales/Ext/Module.bsl",
                "domain": "Sales",
                "risk": 84,
                "fan_in": 18,
                "maintainability_score": 41,
                "reasons": [{"factor": "fan_in", "detail": "18"}],
            },
            {
                "module_path": "CommonModules/HR/Ext/Module.bsl",
                "domain": "HR",
                "risk": 35,
                "fan_in": 2,
                "maintainability_score": 82,
                "reasons": [],
            },
        ][:limit]


def fake_offline_readiness(strict=False, include_metadata=True):
    return {
        "decision": {"status": "pass", "score": 96, "fails": 0, "warnings": 0},
        "summary": {"checks": 6, "passes": 6, "warnings": 0, "fails": 0, "external_env": 0},
        "runtime": {
            "its_rag_mode": "offline",
            "metadata_scan": "included" if include_metadata else "skipped",
        },
    }


def test_executive_dashboard_builds_manager_decision(monkeypatch):
    monkeypatch.setattr(
        "src.services.rentgen.executive_dashboard.build_offline_readiness",
        fake_offline_readiness,
    )

    report = build_executive_dashboard(
        FakeStore(),
        coverage_items=[
            {"id": "quality", "status": "done", "stage": "review", "priority": "P0"},
            {"id": "governance", "status": "partial", "stage": "governance", "priority": "P1"},
        ],
    )

    assert report["available"] is True
    assert report["kpis"]["modules"] == 4
    assert report["kpis"]["call_edges"] == 1234
    assert report["risk_summary"]["high_hotspots"] == 1
    assert report["governance"]["summary"]["red_areas"] == 1
    # HONESTY: coverage reflects the real mix (done=1.0 + partial=0.55)/2 = 77.5 -> 78,
    # never a hardcoded 100/fixed +25.
    assert report["coverage"]["score"] == round((1.0 + 0.55) / 2 * 100)
    assert report["coverage"]["score"] < 100
    assert report["kpis"]["coverage_score"] == report["coverage"]["score"]
    coverage_ws = next(w for w in report["workstreams"] if w["id"] == "coverage")
    assert coverage_ws["status"] == "watch"
    assert report["offline"]["runtime"]["metadata_scan"] == "skipped"
    assert any(action["owner"] == "delivery lead" for action in report["manager_actions"])
    assert "Executive Dashboard" in report["markdown"]


def test_executive_dashboard_coverage_na_without_items(monkeypatch):
    # No coverage signal -> score is n/a (None), weight is dropped and the rest is
    # re-normalised, instead of fabricating a 0 or 100 coverage contribution.
    monkeypatch.setattr(
        "src.services.rentgen.executive_dashboard.build_offline_readiness",
        fake_offline_readiness,
    )

    report = build_executive_dashboard(FakeStore(), coverage_items=[])

    assert report["coverage"]["score"] is None
    assert report["coverage"]["available"] is False
    assert report["kpis"]["coverage_score"] is None
    coverage_ws = next(w for w in report["workstreams"] if w["id"] == "coverage")
    assert coverage_ws["status"] == "unknown"
    # Decision score is still produced from the other (available) signals.
    assert report["decision"]["score"] > 0


def test_executive_dashboard_api(monkeypatch):
    monkeypatch.setattr("src.api.management_api.store_or_none", lambda: FakeStore())
    monkeypatch.setattr(
        "src.services.rentgen.executive_dashboard.build_offline_readiness",
        fake_offline_readiness,
    )

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    response = client.get("/api/v1/management/executive")

    assert response.status_code == 200
    payload = response.json()
    assert payload["decision"]["score"] > 0
    assert payload["kpis"]["modules"] == 4
    assert payload["manager_actions"]
