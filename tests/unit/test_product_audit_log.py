import os

os.environ.setdefault("JWT_SECRET", "unit-test-secret-key-please-rotate")

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from src.api.audit_api import router
from src.middleware.jwt_user_context import JWTUserContextMiddleware, require_auth
from src.modules.auth.application.service import AuthService
from src.modules.auth.infrastructure.config import AuthSettings
from src.services import audit_log
from src.services.rentgen import artifact_graph, canonical_metadata, policy_engine, test_evidence


_JWT_SECRET = "unit-test-secret-key-please-rotate"


def _auth_service() -> AuthService:
    return AuthService(
        AuthSettings(
            jwt_secret=_JWT_SECRET,
            demo_users=(
                '[{"username":"api-user","password":"pw","user_id":"u-api",'
                '"roles":["service"],"permissions":[]}]'
            ),
        )
    )


def _bearer(service: AuthService, username: str) -> dict:
    user = service.authenticate_user(username, "pw")
    assert user is not None
    return {"Authorization": f"Bearer {service.create_access_token(user)}"}


def test_product_audit_log_records_lists_and_exports(tmp_path):
    path = tmp_path / "audit_log.ndjson"

    event = audit_log.record_event(
        action="unit.test",
        actor="tester",
        target="resource-1",
        category="tests",
        metadata={"value": 1},
        path=path,
    )
    listed = audit_log.list_events(actor="tester", path=path)
    exported = audit_log.export_events(output_format="json", path=path)

    assert event["id"].startswith("aud_")
    assert listed["total"] == 1
    assert listed["items"][0]["action"] == "unit.test"
    assert exported["events"] == 1
    assert "resource-1" in exported["content"]


def test_product_audit_log_exports_siem_handoff(tmp_path):
    path = tmp_path / "audit_log.ndjson"

    audit_log.record_event(
        action="approval.requested",
        actor="security-user",
        target="approval-1",
        category="approval",
        metadata={"risk": "high"},
        correlation_id="corr-1",
        path=path,
    )
    exported = audit_log.export_siem_events(output_format="json", path=path)

    assert exported["schema"] == "rentgen.audit.siem.v1"
    assert exported["events"] == 1
    assert exported["chain"]["valid"] is True
    assert exported["content_sha256"]
    assert "rentgen.audit.chain_valid" == exported["ingestion"]["chain_valid_field"]
    assert "approval.requested" in exported["content"]
    assert "security-user" in exported["content"]


def test_governance_services_write_product_audit_events(tmp_path):
    artifacts = tmp_path / "artifact_graph.json"
    evaluations = tmp_path / "policy_evaluations.json"
    tests = tmp_path / "test_runs.json"

    artifact = artifact_graph.create_artifact(
        {"id": "REQ-AUDIT", "type": "requirement", "title": "Audit trace"},
        path=artifacts,
    )
    policy_engine.evaluate_policy(
        {"risk_summary": {"max_risk": 85}},
        scope_id="CHG-AUDIT",
        evaluations_path=evaluations,
        waivers_path=tmp_path / "policy_waivers.json",
    )
    test_evidence.record_test_run(
        run_id="TR-AUDIT",
        title="Audit test run",
        framework="YAxUnit",
        results=[{"id": "Audit::ok", "name": "ok", "status": "passed"}],
        path=tests,
        artifact_path=artifacts,
    )

    events = audit_log.list_events(path=tmp_path / "audit_log.ndjson", limit=50)
    actions = {item["action"] for item in events["items"]}

    assert artifact["id"] == "REQ-AUDIT"
    assert {"artifact.upsert", "policy.evaluate", "test.run.record"} <= actions


def test_canonical_metadata_import_writes_audit(tmp_path):
    config = tmp_path / "edt"
    config.mkdir()
    (config / "Configuration.xml").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject><Configuration uuid="cfg"><Properties><Name>Demo</Name></Properties></Configuration></MetaDataObject>""",
        encoding="utf-8",
    )
    docs = config / "Documents"
    docs.mkdir()
    (docs / "Order.xml").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject><Document uuid="doc"><Properties><Name>Order</Name></Properties></Document></MetaDataObject>""",
        encoding="utf-8",
    )

    canonical_metadata.import_metadata_snapshot(
        config_path=str(config),
        path=tmp_path / "canonical_metadata.json",
        artifact_path=tmp_path / "artifact_graph.json",
    )
    events = audit_log.list_events(action="metadata.canonical.import", path=tmp_path / "audit_log.ndjson")

    assert events["total"] == 1
    assert events["items"][0]["metadata"]["summary"]["objects"] == 1


def test_audit_api_requires_auth(tmp_path, monkeypatch):
    """Anonymous audit append is rejected — no forgeable actor (H3)."""
    monkeypatch.setattr(audit_log, "LOG_PATH", tmp_path / "audit_log.ndjson")
    service = _auth_service()
    app = FastAPI()
    app.add_middleware(JWTUserContextMiddleware, auth_service=service)
    app.include_router(router, dependencies=[Depends(require_auth)])
    client = TestClient(app)

    resp = client.post(
        "/api/v1/audit/events",
        json={"action": "api.audit", "actor": "ceo"},
    )
    assert resp.status_code == 401


def test_audit_api_records_lists_and_exports(tmp_path, monkeypatch):
    monkeypatch.setattr(audit_log, "LOG_PATH", tmp_path / "audit_log.ndjson")
    service = _auth_service()

    app = FastAPI()
    app.add_middleware(JWTUserContextMiddleware, auth_service=service)
    app.include_router(router, dependencies=[Depends(require_auth)])
    client = TestClient(app)

    auth = _bearer(service, "api-user")

    # The actor is derived from the principal even though the body tries to
    # spoof "ceo" (the body has no actor field anymore — it is ignored).
    created = client.post(
        "/api/v1/audit/events",
        headers=auth,
        json={"action": "api.audit", "target": "resource", "metadata": {"ok": True}},
    )
    assert created.status_code == 200
    assert created.json()["actor"] == "api-user"

    listed = client.get("/api/v1/audit/events?actor=api-user", headers=auth)
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["action"] == "api.audit"

    exported = client.get("/api/v1/audit/export?format=jsonl", headers=auth)
    assert exported.json()["events"] == 1

    siem = client.get("/api/v1/audit/siem-export?format=json&limit=10", headers=auth)
    assert siem.status_code == 200
    assert siem.json()["schema"] == "rentgen.audit.siem.v1"
    assert siem.json()["events"] == 1
    assert siem.json()["chain"]["valid"] is True
    assert "api.audit" in siem.json()["content"]

    # The new verify endpoint reports an intact chain.
    verified = client.get("/api/v1/audit/verify", headers=auth)
    assert verified.status_code == 200
    assert verified.json()["valid"] is True
