import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.ai.mcp.server import TOOLS, handle_bsl_standards_review
from src.api.quality_api import router
from src.services.rentgen import standards_review as sr
from src.services.rentgen.standards_review import (
    list_standards_findings,
    review_bsl_standards,
    save_standards_review,
)


UNSAFE_CODE = """
Function UnsafeQuery(Rows) Export
    For Each Row In Rows Do
        Query = New Query("SELECT * FROM Catalog.Products");
        Query.Execute();
    EndDo;
    Execute("Message('x')");
EndFunction
"""


class _FakeStore:
    """Minimal Рентген store stub: resolves only whitelisted module paths."""

    def __init__(self, resolving: set[str]):
        self._resolving = resolving

    def resolve_module(self, module_ref: str) -> dict:
        if module_ref in self._resolving:
            return {
                "module_ref": module_ref,
                "canonical": {"source": "module_path"},
                "graph_modules": [{"name": module_ref}],
            }
        return {"module_ref": module_ref, "canonical": {}, "graph_modules": []}


@pytest.fixture
def graph_with(monkeypatch):
    """Patch the lazy store accessor used by the honesty resolution guard."""

    def _install(resolving):
        store = _FakeStore(set(resolving))
        monkeypatch.setattr(
            "src.api._rentgen_store.store_or_none", lambda: store, raising=True
        )
        return store

    return _install


REAL_MODULE = "CommonModules/ОбщегоНазначения/Ext/Module.bsl"
FAKE_MODULE = "CommonModules/Sales/Ext/Module.bsl"


def test_review_maps_diagnostics_to_catalog_and_autofix():
    # Diagnostics themselves are real and deterministic regardless of the graph.
    report = review_bsl_standards(UNSAFE_CODE, module_path=REAL_MODULE)
    rule_ids = {finding["rule_id"] for finding in report["findings"]}

    assert {"select-star", "query-in-loop", "dynamic-execute", "undocumented-export"} <= rule_ids
    assert report["summary"]["findings"] >= 4
    assert report["summary"]["autofixable"] >= 2
    assert report["findings"][0]["standard"].startswith("1c:")
    assert "BSL Standards Review" in report["markdown"]
    assert "resolution" in report


def test_resolving_module_is_persisted(graph_with, tmp_path):
    graph_with({REAL_MODULE})
    path = tmp_path / "standards_findings.json"

    report = review_bsl_standards(UNSAFE_CODE, module_path=REAL_MODULE)
    assert report["resolution"]["resolved"] is True

    stored = save_standards_review(report, path=path)
    listing = list_standards_findings(path=path)

    assert stored["persisted"] is True
    assert stored["module_path"] == REAL_MODULE
    assert listing["total"] == 1


def test_unresolved_module_is_not_persisted(graph_with, tmp_path):
    # HONESTY: a module that does not exist in the Рентген graph (graph_modules=0)
    # must never be stored/served as real configuration analysis.
    graph_with({REAL_MODULE})  # FAKE_MODULE intentionally absent
    path = tmp_path / "standards_findings.json"

    report = review_bsl_standards(UNSAFE_CODE, module_path=FAKE_MODULE)
    assert report["resolution"]["resolved"] is False
    assert report["resolution"]["graph_modules"] == 0

    stored = save_standards_review(report, path=path)
    listing = list_standards_findings(path=path)

    assert stored["persisted"] is False
    assert stored["status"] == "not_available"
    assert stored["reason"] == "module_not_in_graph"
    # Nothing fabricated was written to the store.
    assert listing["total"] == 0
    assert not path.exists()


def test_findings_store_empty_without_seed(tmp_path):
    # The fabricated seed is gone: an untouched store yields zero findings.
    listing = list_standards_findings(path=tmp_path / "nope.json")
    assert listing["total"] == 0
    assert listing["items"] == []


def test_standards_review_api_skips_unresolved_module(tmp_path, monkeypatch):
    monkeypatch.setattr(sr, "STORE_PATH", tmp_path / "standards_findings.json")
    monkeypatch.setattr(
        "src.api._rentgen_store.store_or_none",
        lambda: _FakeStore({REAL_MODULE}),
    )
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    response = client.post(
        "/quality/standards-review",
        json={"code": UNSAFE_CODE, "module_path": FAKE_MODULE, "save": True},
    )
    listing = client.get("/quality/standards-findings").json()

    assert response.status_code == 200
    body = response.json()
    # Diagnostics are still returned for the pasted code...
    assert body["summary"]["findings"] >= 4
    # ...but the unresolved module is NOT persisted as configuration analysis.
    assert body["stored"]["persisted"] is False
    assert listing["total"] == 0


def test_standards_review_api_persists_resolving_module(tmp_path, monkeypatch):
    monkeypatch.setattr(sr, "STORE_PATH", tmp_path / "standards_findings.json")
    monkeypatch.setattr(
        "src.api._rentgen_store.store_or_none",
        lambda: _FakeStore({REAL_MODULE}),
    )
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    response = client.post(
        "/quality/standards-review",
        json={"code": UNSAFE_CODE, "module_path": REAL_MODULE, "save": True},
    )
    listing = client.get("/quality/standards-findings").json()

    assert response.status_code == 200
    assert response.json()["stored"]["persisted"] is True
    assert listing["total"] == 1
    assert listing["items"][0]["summary"]["autofixable"] >= 2


@pytest.mark.asyncio
async def test_mcp_bsl_standards_review_tool_is_registered(tmp_path, monkeypatch):
    monkeypatch.setattr(sr, "STORE_PATH", tmp_path / "standards_findings.json")
    monkeypatch.setattr(
        "src.api._rentgen_store.store_or_none",
        lambda: _FakeStore({REAL_MODULE}),
    )

    result = await handle_bsl_standards_review(
        {"code": UNSAFE_CODE, "module_path": REAL_MODULE, "save": True}
    )

    assert "bsl_standards_review" in {tool.name for tool in TOOLS}
    assert result["summary"]["findings"] >= 4
    assert result["stored"]["persisted"] is True
    assert result["stored"]["module_path"] == REAL_MODULE
