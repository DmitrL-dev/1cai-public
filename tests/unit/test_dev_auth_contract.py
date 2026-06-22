import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from src.middleware.jwt_user_context import JWTUserContextMiddleware, require_auth
from src.modules.auth.api import dependencies as auth_dependencies
from src.modules.auth.api.routes import router as auth_router
from src.modules.auth.application.service import AuthService
from src.modules.auth.infrastructure.config import AuthSettings


def _clear_auth_caches() -> None:
    auth_dependencies.get_auth_settings.cache_clear()
    auth_dependencies.get_auth_service.cache_clear()


@pytest.fixture(autouse=True)
def auth_cache_guard():
    _clear_auth_caches()
    yield
    _clear_auth_caches()


def _client(monkeypatch) -> TestClient:
    monkeypatch.setenv("JWT_SECRET", "unit-test-secret-key-please-rotate")
    monkeypatch.delenv("AUTH_DEMO_USERS", raising=False)
    _clear_auth_caches()

    app = FastAPI()
    app.add_middleware(JWTUserContextMiddleware)
    app.include_router(auth_router, prefix="/api/v1")

    @app.get("/api/v1/protected")
    async def protected(principal=Depends(require_auth)):
        return {"username": principal.username, "roles": principal.roles}

    return TestClient(app)


def test_dev_demo_login_returns_jwt_that_opens_protected_routes(monkeypatch):
    client = _client(monkeypatch)

    login = client.post(
        "/api/v1/auth/token",
        data={"username": "admin", "password": "admin123"},
    )
    assert login.status_code == 200
    payload = login.json()
    token = payload["access_token"]
    assert token
    assert payload["token_type"] == "bearer"
    assert payload["expires_in"] == 3600

    headers = {"Authorization": f"Bearer {token}"}
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["username"] == "admin"
    assert "admin" in me.json()["roles"]

    protected = client.get("/api/v1/protected", headers=headers)
    assert protected.status_code == 200
    assert protected.json()["username"] == "admin"


def test_dev_auth_rejects_fake_or_missing_tokens(monkeypatch):
    client = _client(monkeypatch)

    assert client.get("/api/v1/protected").status_code == 401
    assert (
        client.get(
            "/api/v1/protected",
            headers={"Authorization": "Bearer dev-token"},
        ).status_code
        == 401
    )


def test_module_auth_rejects_missing_users_in_production(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("AUTH_DEMO_USERS", raising=False)

    with pytest.raises(RuntimeError, match="default demo users are disabled"):
        AuthService(AuthSettings(jwt_secret="unit-test-secret"))


def test_module_auth_rejects_default_credentials_in_production(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")

    with pytest.raises(RuntimeError, match="default demo credentials"):
        AuthService(
            AuthSettings(
                jwt_secret="unit-test-secret",
                demo_users=(
                    '[{"username":"admin","password":"admin123",'
                    '"user_id":"admin-1","roles":["admin"]}]'
                ),
            )
        )
