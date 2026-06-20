
"""Unit tests for the JWT AuthService."""

from datetime import timedelta

import pytest

from src.security.auth import AuthService, AuthSettings


@pytest.fixture()
def auth_service() -> AuthService:
    settings = AuthSettings(
        jwt_secret="unit-test-secret",
        access_token_expire_minutes=30,
        demo_users='[{"username":"unit","password":"secret","user_id":"user-42","roles":["developer"],"permissions":["marketplace:submit"],"full_name":"Unit Tester"}]',
        service_tokens='[{"name":"reporting","token":"svc-secret","roles":["service"],"permissions":["marketplace:read"]}]',
    )
    return AuthService(settings)


def test_authenticate_and_issue_token(auth_service: AuthService) -> None:
    user = auth_service.authenticate_user("unit", "secret")
    assert user is not None

    token = auth_service.create_access_token(user, expires_delta=timedelta(minutes=5))
    current_user = auth_service.decode_token(token)

    assert current_user.user_id == "user-42"
    assert current_user.username == "unit"
    assert current_user.has_role("developer")


def test_invalid_credentials(auth_service: AuthService) -> None:
    assert auth_service.authenticate_user("unit", "wrong") is None


def test_service_token_auth(auth_service: AuthService) -> None:
    principal = auth_service.authenticate_service_token("svc-secret")
    assert principal is not None
    assert principal.user_id == "service:reporting"
    assert principal.has_role("service")


def test_invalid_service_token(auth_service: AuthService) -> None:
    assert auth_service.authenticate_service_token("bad-token") is None


def test_legacy_auth_rejects_missing_users_in_production(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("AUTH_DEMO_USERS", raising=False)

    with pytest.raises(RuntimeError, match="default demo users are disabled"):
        AuthService(AuthSettings(jwt_secret="unit-test-secret"))


def test_legacy_auth_rejects_default_credentials_in_production(monkeypatch) -> None:
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
