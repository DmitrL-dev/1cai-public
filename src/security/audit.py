"""Security audit logging utilities."""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Optional


class AuditLogger:
    """Append-only JSONL audit logger."""

    def __init__(self, log_path: Optional[Path] = None) -> None:
        env_path = os.getenv("AUDIT_LOG_PATH", "logs/security_audit.log")
        self._path = log_path or Path(env_path)
        self._lock = Lock()

    @property
    def path(self) -> Path:
        return self._path

    def log_action(
        self,
        *,
        actor: str,
        action: str,
        target: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        timestamp = datetime.now(timezone.utc)
        entry = {
            "timestamp": timestamp.isoformat(timespec="seconds"),
            "actor": actor,
            "action": action,
            "target": target,
            "metadata": metadata or {},
        }

        self._path.parent.mkdir(parents=True, exist_ok=True)

        with self._lock:
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and not loop.is_closed():
            loop.create_task(
                self._write_db(timestamp, actor, action, target, metadata or {})
            )
        # если нет активного event loop, просто пропускаем запись в БД (файл уже сохранён)

    async def _write_db(
        self,
        timestamp: datetime,
        actor: str,
        action: str,
        target: Optional[str],
        metadata: Dict[str, Any],
    ) -> None:
        try:
            from src.database import get_pool

            pool = get_pool()
        except Exception:  # noqa: BLE001
            return

        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO security_audit_log (timestamp, actor, action, target, metadata)
                    VALUES ($1, $2, $3, $4, $5)
                    """,
                    timestamp,
                    actor,
                    action,
                    target,
                    metadata,
                )
        except Exception:  # noqa: BLE001
            # Fallback silently; file log already captured the event
            return


_audit_logger = AuditLogger()


def get_audit_logger() -> AuditLogger:
    return _audit_logger


__all__ = ["AuditLogger", "get_audit_logger"]
