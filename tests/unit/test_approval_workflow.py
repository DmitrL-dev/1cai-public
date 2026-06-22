import os

os.environ.setdefault("JWT_SECRET", "unit-test-secret-key-please-rotate")

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from src.api.approval_api import router
from src.middleware.jwt_user_context import JWTUserContextMiddleware, require_auth
from src.modules.auth.application.service import AuthService
from src.modules.auth.infrastructure.config import AuthSettings
from src.services import audit_log
from src.services.rentgen import approval_workflow as approvals

_JWT_SECRET = "unit-test-secret-key-please-rotate"


def _auth_service() -> AuthService:
    return AuthService(
        AuthSettings(
            jwt_secret=_JWT_SECRET,
            demo_users=(
                '[{"username":"developer","password":"pw","user_id":"u-dev",'
                '"roles":["developer"],"permissions":[]},'
                '{"username":"architect","password":"pw","user_id":"u-arch",'
                '"roles":["architect"],"permissions":[]}]'
            ),
        )
    )


def _token(service: AuthService, username: str) -> str:
    user = service.authenticate_user(username, "pw")
    assert user is not None
    return service.create_access_token(user)


def test_approval_workflow_create_approve_validate_and_use(tmp_path):
    store = tmp_path / "approvals.json"
    record = approvals.create_approval_record(
        tool_name="write_module_source",
        actor="developer",
        approval_reason="Approved after impact review and test selection.",
        risk="write",
        approval_ticket="CHG-42",
        argument_constraints={"modulePath": "CommonModules/X/Ext/Module.bsl"},
        path=store,
    )

    pending_validation = approvals.validate_approval_for_call(
        record["id"],
        tool_name="write_module_source",
        actor="developer",
        risk="write",
        arguments={"modulePath": "CommonModules/X/Ext/Module.bsl"},
        path=store,
    )
    approved = approvals.update_approval_status(
        record["id"],
        status="approved",
        actor="architect",
        decision_reason="Scope and tests reviewed.",
        path=store,
    )
    valid_validation = approvals.validate_approval_for_call(
        record["id"],
        tool_name="write_module_source",
        actor="developer",
        risk="write",
        arguments={"modulePath": "CommonModules/X/Ext/Module.bsl"},
        path=store,
    )
    mismatch_validation = approvals.validate_approval_for_call(
        record["id"],
        tool_name="write_module_source",
        actor="developer",
        risk="write",
        arguments={"modulePath": "CommonModules/Y/Ext/Module.bsl"},
        path=store,
    )
    used = approvals.update_approval_status(
        record["id"], status="used", actor="developer", path=store
    )
    used_validation = approvals.validate_approval_for_call(
        record["id"],
        tool_name="write_module_source",
        actor="developer",
        risk="write",
        path=store,
    )

    assert record["status"] == "requested"
    assert pending_validation["valid"] is False
    assert pending_validation["reason"] == "status_requested"
    assert approved["status"] == "approved"
    assert valid_validation["valid"] is True
    assert mismatch_validation["valid"] is False
    assert mismatch_validation["reason"] == "argument_mismatch:modulePath"
    assert used["status"] == "used"
    assert used_validation["valid"] is False
    assert used_validation["reason"] == "status_used"


def test_approval_api_requires_auth(tmp_path, monkeypatch):
    """Unauthenticated approval creation is rejected (C1/C3)."""
    monkeypatch.setattr(approvals, "STORE_PATH", tmp_path / "approvals.json")
    service = _auth_service()
    app = FastAPI()
    app.add_middleware(JWTUserContextMiddleware, auth_service=service)
    app.include_router(router, dependencies=[Depends(require_auth)])
    client = TestClient(app)

    resp = client.post(
        "/api/v1/approvals/edt-mcp",
        json={
            "tool_name": "write_module_source",
            "approval_reason": "Approved after impact review and test selection.",
        },
    )
    assert resp.status_code == 401


def test_approval_api_create_approve_and_validate(tmp_path, monkeypatch):
    monkeypatch.setattr(approvals, "STORE_PATH", tmp_path / "approvals.json")
    monkeypatch.setattr(audit_log, "LOG_PATH", tmp_path / "audit_log.ndjson")
    service = _auth_service()

    app = FastAPI()
    app.add_middleware(JWTUserContextMiddleware, auth_service=service)
    app.include_router(router, dependencies=[Depends(require_auth)])
    client = TestClient(app)

    dev_auth = {"Authorization": f"Bearer {_token(service, 'developer')}"}
    arch_auth = {"Authorization": f"Bearer {_token(service, 'architect')}"}

    # Actor is taken from the principal (the token), NOT the body.
    created = client.post(
        "/api/v1/approvals/edt-mcp",
        headers=dev_auth,
        json={
            "tool_name": "write_module_source",
            "approval_reason": "Approved after impact review and test selection.",
            "approval_ticket": "CHG-42",
            "argument_constraints": {"modulePath": "CommonModules/X/Ext/Module.bsl"},
        },
    )
    assert created.status_code == 200
    assert created.json()["record"]["actor"] == "developer"
    approval_id = created.json()["record"]["id"]

    # Separation of duties: the requester (developer) cannot approve.
    self_approve = client.post(
        f"/api/v1/approvals/{approval_id}/approve",
        headers=dev_auth,
        json={"decision_reason": "self"},
    )
    assert self_approve.status_code == 403

    # A different principal (architect) approves.
    approved = client.post(
        f"/api/v1/approvals/{approval_id}/approve",
        headers=arch_auth,
        json={"decision_reason": "Reviewed."},
    )
    assert approved.status_code == 200
    assert approved.json()["record"]["status"] == "approved"
    assert approved.json()["record"]["approved_by"] == "architect"

    validation = client.post(
        "/api/v1/approvals/edt-mcp/validate",
        headers=dev_auth,
        json={
            "approval_id": approval_id,
            "tool_name": "write_module_source",
            "arguments": {"modulePath": "CommonModules/X/Ext/Module.bsl"},
        },
    )
    assert validation.status_code == 200
    assert validation.json()["valid"] is True

    listed = client.get("/api/v1/approvals?kind=edt_mcp_call", headers=dev_auth)
    assert listed.json()["total"] == 1
    events = audit_log.list_events(
        category="approval", path=tmp_path / "audit_log.ndjson", limit=10
    )
    actions = {item["action"] for item in events["items"]}
    assert {"approval.requested", "approval.approved"} <= actions
