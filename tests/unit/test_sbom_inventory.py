from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from src.ai.mcp.server import TOOLS, handle_sbom_generate
from src.api.productization_api import router
from src.services.sbom_inventory import generate_sbom, sbom_markdown_report


def test_sbom_inventory_parses_python_npm_and_docker_sources(tmp_path):
    (tmp_path / "requirements.txt").write_text("fastapi==0.110.0\npytest>=8\n", encoding="utf-8")
    (tmp_path / "package.json").write_text(
        '{"dependencies":{"react":"18.2.0"},"devDependencies":{"vite":"^7.0.0"}}',
        encoding="utf-8",
    )
    (tmp_path / "Dockerfile").write_text("FROM python:3.11-slim\n", encoding="utf-8")

    sbom = generate_sbom(
        root=tmp_path,
        include_defaults=False,
        include_paths=["requirements.txt", "package.json", "Dockerfile"],
        write=False,
    )
    names = {component["name"] for component in sbom["components"]}

    assert {"fastapi", "pytest", "react", "vite", "python"} <= names
    assert sbom["summary"]["components"] >= 5
    assert sbom["summary"]["missing_sources"] == 0


def test_sbom_inventory_rejects_escaping_paths(tmp_path):
    try:
        generate_sbom(root=tmp_path, include_defaults=False, include_paths=["../requirements.txt"], write=False)
    except ValueError as exc:
        assert "escapes repository root" in str(exc)
    else:
        raise AssertionError("Expected escaping path to be rejected")


def test_sbom_markdown_report_contains_summary(tmp_path):
    (tmp_path / "requirements.txt").write_text("fastapi==0.110.0\n", encoding="utf-8")
    report = sbom_markdown_report(root=tmp_path, include_defaults=False, include_paths=["requirements.txt"])

    assert report["format"] == "markdown"
    assert "Components:" in report["content"]
    assert report["sbom"]["summary"]["components"] == 1


def test_productization_api_generates_sbom_without_writing():
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    response = client.post(
        "/api/v1/productization/sbom",
        json={"include_defaults": False, "include_paths": ["docs/productization/SUPPORT_MATRIX.md"], "write": False},
    )
    report = client.get("/api/v1/productization/sbom/report")

    assert response.status_code == 200
    assert response.json()["summary"]["components"] == 0
    assert report.status_code == 200
    assert report.json()["format"] == "markdown"


@pytest.mark.asyncio
async def test_mcp_sbom_tool_is_registered_and_returns_markdown():
    names = {tool.name for tool in TOOLS}
    assert "sbom_generate" in names

    report = await handle_sbom_generate(
        {
            "include_defaults": False,
            "include_paths": ["docs/productization/SUPPORT_MATRIX.md"],
            "write": False,
            "format": "markdown",
        }
    )

    assert report["format"] == "markdown"
    assert "Components:" in report["content"]
