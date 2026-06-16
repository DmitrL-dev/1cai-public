from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from src.ai.mcp.server import TOOLS, handle_productization_readiness
from src.api.productization_api import router
from src.services import productization_readiness as readiness


def test_productization_readiness_reports_repo_state():
    report = readiness.productization_readiness()

    assert report["status"] in {"pass", "warn"}
    assert report["release_decision"] in {"pilot_ready", "production_candidate"}
    assert report["summary"]["deliverables"] >= 20
    assert report["summary"]["tests_missing"] == 0
    assert report["summary"]["reviews_missing"] == 0
    assert any(item["code"] == "signed-offline-installer-missing" for item in report["findings"])
    assert "Configuration and metadata inventory with graph traceability." in report["non_ai_value"]


def test_productization_readiness_fails_when_required_files_are_missing(tmp_path):
    report = readiness.productization_readiness(root=tmp_path)

    assert report["status"] == "fail"
    assert report["release_decision"] == "blocked"
    assert report["summary"]["high"] > 0
    assert report["summary"]["tests_missing"] > 0
    assert report["summary"]["reviews_missing"] > 0


def test_productization_markdown_report_contains_decision():
    report = readiness.productization_markdown_report()

    assert report["format"] == "markdown"
    assert "# 1cAI productization readiness" in report["content"]
    assert "Decision:" in report["content"]


def test_productization_api_exposes_readiness_deliverables_and_report():
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    readiness_response = client.get("/api/v1/productization/readiness")
    deliverables_response = client.get("/api/v1/productization/deliverables")
    report_response = client.get("/api/v1/productization/report")

    assert readiness_response.status_code == 200
    assert readiness_response.json()["status"] in {"pass", "warn"}
    assert deliverables_response.json()["total"] >= 20
    assert report_response.json()["format"] == "markdown"


@pytest.mark.asyncio
async def test_mcp_productization_tool_is_registered_and_returns_markdown():
    names = {tool.name for tool in TOOLS}
    assert "productization_readiness" in names

    json_report = await handle_productization_readiness({})
    markdown_report = await handle_productization_readiness({"format": "markdown"})

    assert json_report["status"] in {"pass", "warn"}
    assert markdown_report["format"] == "markdown"
