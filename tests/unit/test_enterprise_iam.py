import os

os.environ.setdefault("JWT_SECRET", "unit-test-secret-key-please-rotate")

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from src.api.enterprise_api import router
from src.middleware.jwt_user_context import JWTUserContextMiddleware, require_auth
from src.modules.auth.application.service import AuthService
from src.modules.auth.infrastructure.config import AuthSettings as ModuleAuthSettings
from src.security.auth import AuthSettings
from src.services import audit_log, enterprise_iam


_JWT_SECRET = "unit-test-secret-key-please-rotate"


def _auth_service() -> AuthService:
    return AuthService(
        ModuleAuthSettings(
            jwt_secret=_JWT_SECRET,
            demo_users=(
                '[{"username":"iam-admin","password":"pw","user_id":"u-iam",'
                '"roles":["admin"],"permissions":[]},'
                '{"username":"arch","password":"pw","user_id":"u-arch",'
                '"roles":["architect"],"permissions":["project:erp:write"]}]'
            ),
        )
    )


def _bearer(service: AuthService, username: str) -> dict:
    user = service.authenticate_user(username, "pw")
    assert user is not None
    return {"Authorization": f"Bearer {service.create_access_token(user)}"}


def test_enterprise_iam_readiness_boundaries_and_access(tmp_path):
    path = tmp_path / "enterprise_iam.json"
    saved = enterprise_iam.save_iam_config(
        {
            "providers": [
                {"id": "local-jwt", "type": "local_jwt", "enabled": True},
                {"id": "oidc", "type": "oidc", "enabled": True, "issuer": "https://idp.example", "client_id": "1cai"},
            ],
            "boundaries": [],
        },
        path=path,
    )
    boundary = enterprise_iam.upsert_project_boundary(
        {
            "tenant_id": "tenant-a",
            "project_id": "erp",
            "name": "ERP",
            "allowed_roles": ["architect"],
            "allowed_permissions": ["project:erp:write"],
            "data_roots": ["data/configs/erp"],
        },
        path=path,
    )
    allowed = enterprise_iam.check_project_access(
        tenant_id="tenant-a",
        project_id="erp",
        roles=["developer", "architect"],
        permissions=[],
        action="metadata.import",
        path=path,
    )
    denied = enterprise_iam.check_project_access(
        tenant_id="tenant-a",
        project_id="erp",
        roles=["viewer"],
        permissions=[],
        action="metadata.import",
        path=path,
    )
    readiness = enterprise_iam.iam_readiness(
        path=path,
        auth_settings=AuthSettings(jwt_secret="secret", service_tokens='{"svc":{"token":"t","name":"svc"}}'),
    )
    events = audit_log.list_events(category="iam", path=tmp_path / "audit_log.ndjson")

    assert saved["validation"] == []
    assert boundary["project_id"] == "erp"
    assert allowed["allowed"] is True
    assert denied["allowed"] is False
    assert readiness["status"] == "pass"
    assert events["total"] >= 2


def test_enterprise_iam_rejects_invalid_provider(tmp_path):
    try:
        enterprise_iam.save_iam_config(
            {"providers": [{"id": "bad", "type": "unknown", "enabled": True}], "boundaries": []},
            path=tmp_path / "enterprise_iam.json",
        )
    except ValueError as exc:
        assert "high-severity" in str(exc)
    else:
        raise AssertionError("Expected invalid provider to be rejected")


def test_enterprise_api_requires_auth_and_admin(tmp_path, monkeypatch):
    """IAM config / boundary writes are admin-only; reads need auth (H4)."""
    monkeypatch.setattr(enterprise_iam, "CONFIG_PATH", tmp_path / "enterprise_iam.json")
    service = _auth_service()
    app = FastAPI()
    app.add_middleware(JWTUserContextMiddleware, auth_service=service)
    app.include_router(router, dependencies=[Depends(require_auth)])
    client = TestClient(app)

    body = {
        "providers": [{"id": "local-jwt", "type": "local_jwt", "enabled": True}],
        "boundaries": [],
    }

    # Anonymous -> 401
    assert client.put("/api/v1/enterprise/iam/config", json=body).status_code == 401
    # Non-admin (architect) -> 403
    arch = _bearer(service, "arch")
    assert (
        client.put("/api/v1/enterprise/iam/config", json=body, headers=arch).status_code
        == 403
    )


def test_enterprise_api_exposes_readiness_config_boundaries_and_access(tmp_path, monkeypatch):
    monkeypatch.setattr(enterprise_iam, "CONFIG_PATH", tmp_path / "enterprise_iam.json")
    service = _auth_service()

    app = FastAPI()
    app.add_middleware(JWTUserContextMiddleware, auth_service=service)
    app.include_router(router, dependencies=[Depends(require_auth)])
    client = TestClient(app)

    admin = _bearer(service, "iam-admin")
    arch = _bearer(service, "arch")

    saved = client.put(
        "/api/v1/enterprise/iam/config",
        headers=admin,
        json={
            "providers": [
                {"id": "local-jwt", "type": "local_jwt", "enabled": True},
                {"id": "oidc", "type": "oidc", "enabled": True, "issuer": "https://idp.example"},
            ],
            "boundaries": [],
        },
    )
    boundary = client.post(
        "/api/v1/enterprise/projects/boundaries",
        headers=admin,
        json={
            "tenant_id": "tenant-a",
            "project_id": "erp",
            "allowed_roles": ["architect"],
            "allowed_permissions": ["project:erp:write"],
        },
    )
    # access-check derives roles/permissions from the principal, not the body.
    # The architect principal holds project:erp:write -> allowed.
    access = client.post(
        "/api/v1/enterprise/projects/access-check",
        headers=arch,
        json={"tenant_id": "tenant-a", "project_id": "erp", "action": "release"},
    )
    # The guarded resource enforces the boundary on the request path (H7).
    guarded_ok = client.get(
        "/api/v1/enterprise/projects/tenant-a/erp/guarded-resource", headers=arch
    )
    boundaries = client.get(
        "/api/v1/enterprise/projects/boundaries?tenant_id=tenant-a", headers=admin
    )
    readiness = client.get("/api/v1/enterprise/iam/readiness", headers=admin)

    assert saved.status_code == 200
    assert boundary.json()["tenant_id"] == "tenant-a"
    assert access.json()["allowed"] is True
    assert guarded_ok.status_code == 200
    assert guarded_ok.json()["granted"] is True
    assert boundaries.json()["total"] == 1
    assert readiness.json()["summary"]["providers"] >= 2
