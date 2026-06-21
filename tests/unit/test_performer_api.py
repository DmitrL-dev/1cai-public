"""Path-confinement contract for the Performer (TJ performance) API.

The performer endpoints accept a caller-supplied ``log_path`` and read it.
``confine_path`` at the API boundary must reject a path outside the allowed
data roots with HTTP 400 (arbitrary-file-read / traversal guard) and must not
leak a stack trace, while still accepting a path under an allowed root.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api import performer_api


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(performer_api.router)
    return TestClient(app, raise_server_exceptions=False)


def test_performer_analyze_rejects_path_outside_data_roots():
    client = _client()

    response = client.post(
        "/api/v1/performer/analyze",
        json={"log_path": r"C:\Windows\win.ini"},
    )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "outside the allowed data roots" in detail


def test_performer_impact_rejects_path_outside_data_roots():
    client = _client()

    response = client.post(
        "/api/v1/performer/impact",
        json={"log_path": r"C:\Windows\win.ini"},
    )

    assert response.status_code == 400
    assert "outside the allowed data roots" in response.json()["detail"]


def test_performer_analyze_accepts_data_root_log(tmp_path):
    # A real .log under an allowed root (tmp) must pass confinement and parse.
    log = tmp_path / "rphost" / "perf.log"
    log.parent.mkdir(parents=True)
    log.write_text(
        "12:00:01.000000-1000,SDBL,p:1:1:1,Usr=Admin,"
        "Context='CommonModule.Safe.Module : 10 : Query()'\n",
        encoding="utf-8",
    )
    client = _client()

    response = client.post(
        "/api/v1/performer/analyze",
        json={"log_path": str(log)},
    )

    assert response.status_code == 200
    body = response.json()
    assert "total_events" in body and body["total_events"] >= 0
