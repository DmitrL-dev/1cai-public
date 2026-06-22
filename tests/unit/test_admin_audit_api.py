"""Unit tests for admin audit endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.api.admin_audit import AuditEntry, list_audit_entries
from src.security.auth import CurrentUser


@pytest.mark.asyncio()
async def test_list_audit_entries(monkeypatch):
    fake_row = {
        "id": 1,
        "timestamp": datetime(2025, 11, 7, 12, 0, tzinfo=timezone.utc),
        "actor": "admin",
        "action": "test.action",
        "target": "resource-1",
        "metadata": {"key": "value"},
    }

    current_user = CurrentUser(
        user_id="admin-1", username="admin", roles=["admin"], permissions=[]
    )

    async def fake_fetch(limit, offset, actor, action):
        entry = AuditEntry(
            id=fake_row["id"],
            timestamp=fake_row["timestamp"].isoformat(),
            actor=fake_row["actor"],
            action=fake_row["action"],
            target=fake_row["target"],
            metadata=fake_row["metadata"],
        )
        return [entry], 1

    monkeypatch.setattr("src.api.admin_audit._fetch_audit_entries", fake_fetch)

    response = await list_audit_entries(
        current_user=current_user,
        limit=10,
        offset=0,
    )

    assert response.total == 1
    assert response.items[0].actor == "admin"
    assert response.items[0].metadata["key"] == "value"
