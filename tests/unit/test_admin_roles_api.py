"""Unit tests for admin role management endpoints."""

from __future__ import annotations

import pytest

from src.api.admin_roles import (
    RoleRequest,
    grant_role_endpoint,
    revoke_permission_endpoint,
)
from src.security.auth import CurrentUser


class DummyAuditLogger:
    def __init__(self) -> None:
        self.records = []

    def log_action(self, **kwargs) -> None:
        self.records.append(kwargs)


@pytest.mark.asyncio()
async def test_grant_role_endpoint(monkeypatch):
    calls = {}

    async def fake_grant_role(
        user_id, role, assigned_by=None, reason=None, metadata=None
    ):  # noqa: ANN001
        calls["grant"] = {
            "user_id": user_id,
            "role": role,
            "assigned_by": assigned_by,
            "reason": reason,
            "metadata": metadata,
        }

    dump_logger = DummyAuditLogger()

    monkeypatch.setattr("src.api.admin_roles.grant_role", fake_grant_role)
    monkeypatch.setattr("src.api.admin_roles.audit_logger", dump_logger)

    current = CurrentUser(
        user_id="admin", username="admin", roles=["admin"], permissions=[]
    )
    payload = RoleRequest(role="moderator", reason="integration")

    response = await grant_role_endpoint("user-123", payload, current)

    assert response.status_code == 204
    assert calls["grant"]["role"] == "moderator"
    assert dump_logger.records[0]["action"] == "admin.role.grant"


@pytest.mark.asyncio()
async def test_revoke_permission_endpoint(monkeypatch):
    calls = {}

    async def fake_revoke_permission(user_id, permission):  # noqa: ANN001
        calls["permission"] = {"user_id": user_id, "permission": permission}

    dump_logger = DummyAuditLogger()

    monkeypatch.setattr("src.api.admin_roles.revoke_permission", fake_revoke_permission)
    monkeypatch.setattr("src.api.admin_roles.audit_logger", dump_logger)

    current = CurrentUser(
        user_id="admin", username="admin", roles=["admin"], permissions=[]
    )

    response = await revoke_permission_endpoint(
        "user-42", "marketplace:submit", current
    )

    assert response.status_code == 204
    assert calls["permission"]["permission"] == "marketplace:submit"
    assert dump_logger.records[0]["action"] == "admin.permission.revoke"
