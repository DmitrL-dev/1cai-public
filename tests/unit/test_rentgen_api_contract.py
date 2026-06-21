from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api import rentgen_api


class _Store:
    def db_meta(self):
        return {
            "n_subroutines": 10,
            "n_modules": 2,
            "n_call_edges": 30,
            "n_quality": 2,
        }


def _client(monkeypatch, store):
    monkeypatch.setattr(rentgen_api, "store_or_none", lambda: store)
    app = FastAPI()
    app.include_router(rentgen_api.router, prefix="/api/v1")
    return TestClient(app)


def test_rentgen_build_contract_matches_portal_client(monkeypatch):
    client = _client(monkeypatch, _Store())

    response = client.get("/api/v1/rentgen/build", params={"config_path": "C:/demo"})

    assert response.status_code == 200
    assert response.json() == {
        "built": True,
        "meta": {
            "n_subroutines": 10,
            "n_modules": 2,
            "n_call_edges": 30,
            "n_quality": 2,
        },
    }


def test_rentgen_build_reports_missing_store_without_throwing(monkeypatch):
    client = _client(monkeypatch, None)

    response = client.get("/api/v1/rentgen/build")

    assert response.status_code == 200
    assert response.json()["built"] is False
    assert "build_store.py" in response.json()["hint"]
