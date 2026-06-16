
"""Tests for audit logger."""

import json
from pathlib import Path

from src.security.audit import AuditLogger


def test_audit_logger_writes_json(tmp_path: Path) -> None:
    log_path = tmp_path / "audit.log"
    logger = AuditLogger(log_path=log_path)

    logger.log_action(
        actor="user-1", action="test.action", target="resource", metadata={"value": 1}
    )

    content = log_path.read_text(encoding="utf-8").strip()
    assert content
    record = json.loads(content)
    assert record["actor"] == "user-1"
    assert record["action"] == "test.action"
    assert record["target"] == "resource"
    assert record["metadata"]["value"] == 1
