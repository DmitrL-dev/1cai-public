import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.ai.mcp.server import TOOLS, handle_rentgen_offline_readiness
from src.api.offline_readiness_api import router
from src.services.rentgen.metadata_graph import build_metadata_graph
from src.services.rentgen.offline_readiness import (
    EXTERNAL_ENV_KEYS,
    build_offline_readiness,
)


def _make_offline_root(tmp_path):
    root = tmp_path
    (root / "data").mkdir()
    (root / "data" / "rentgen.db").write_bytes(b"")

    config = root / "data" / "configs" / "unpacked"
    docs = root / "docs" / "its_forms" / "sections"
    model = root / "models" / "qwen-bsl-lora"
    (config / "Documents").mkdir(parents=True)
    docs.mkdir(parents=True)
    model.mkdir(parents=True)

    (config / "Configuration.xml").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject><Configuration uuid="cfg"><Properties><Name>Demo</Name></Properties></Configuration></MetaDataObject>""",
        encoding="utf-8",
    )
    (config / "Documents" / "Order.xml").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject><Document uuid="doc"><Properties><Name>Order</Name></Properties></Document></MetaDataObject>""",
        encoding="utf-8",
    )
    (docs / "managed_forms.txt").write_text(
        "Managed form offline context", encoding="utf-8"
    )
    return root


def _clear_external_env(monkeypatch):
    for key in EXTERNAL_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("ITS_RAG_MODE", "offline")


def test_offline_readiness_passes_with_local_artifacts(tmp_path, monkeypatch):
    root = _make_offline_root(tmp_path)
    _clear_external_env(monkeypatch)
    build_metadata_graph.cache_clear()

    report = build_offline_readiness(root=root)

    assert report["decision"]["status"] == "pass"
    assert report["summary"]["metadata_objects"] == 1
    assert report["summary"]["its_docs"] == 1
    assert report["external_env"] == []
    assert "No known external" in report["markdown"]


def test_offline_readiness_strict_fails_on_external_env(tmp_path, monkeypatch):
    root = _make_offline_root(tmp_path)
    _clear_external_env(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "external-key")
    build_metadata_graph.cache_clear()

    report = build_offline_readiness(strict=True, root=root)
    external_check = next(
        item for item in report["checks"] if item["id"] == "external-env"
    )

    assert report["decision"]["status"] == "fail"
    assert external_check["status"] == "fail"
    assert report["summary"]["external_env"] == 1


def test_offline_readiness_api_exposes_analysis(tmp_path, monkeypatch):
    root = _make_offline_root(tmp_path)
    _clear_external_env(monkeypatch)
    monkeypatch.setattr("src.services.rentgen.offline_readiness.REPO_ROOT", root)
    build_metadata_graph.cache_clear()

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    response = client.get("/api/v1/offline-readiness/analyze")

    assert response.status_code == 200
    payload = response.json()
    assert payload["decision"]["status"] == "pass"
    assert payload["summary"]["checks"] >= 6


@pytest.mark.asyncio
async def test_mcp_offline_readiness_tool_is_registered(tmp_path, monkeypatch):
    root = _make_offline_root(tmp_path)
    _clear_external_env(monkeypatch)
    monkeypatch.setattr("src.services.rentgen.offline_readiness.REPO_ROOT", root)
    build_metadata_graph.cache_clear()

    names = {tool.name for tool in TOOLS}
    report = await handle_rentgen_offline_readiness({"strict": False})

    assert "rentgen_offline_readiness" in names
    assert report["decision"]["status"] == "pass"
    assert report["runtime"]["its_rag_mode"] == "offline"
