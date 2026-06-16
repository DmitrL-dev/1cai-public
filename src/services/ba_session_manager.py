"""Модуль ba_session_manager.

Управление сессиями бизнес-аналитиков (BA) через WebSocket.
Обеспечивает совместную работу, обмен сообщениями и аудит действий.
"""


from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import WebSocket

logger = logging.getLogger(__name__)

try:
    from src.monitoring.prometheus_metrics import (
        set_ba_session_counts,
        track_ba_session_audit_failure,
        track_ba_session_disconnect,
        track_ba_session_event,
    )
except Exception:  # pragma: no cover - metrics optional

    def set_ba_session_counts(*args: Any, **kwargs: Any) -> None:  # type: ignore[unused-ignore]  # noqa: ANN401
        """Установить метрики количества сессий и участников."""
        return None

    def track_ba_session_event(*args: Any, **kwargs: Any) -> None:  # type: ignore[unused-ignore]  # noqa: ANN401
        """Отследить событие сессии BA."""
        return None

    def track_ba_session_disconnect(*args: Any, **kwargs: Any) -> None:  # type: ignore[unused-ignore]  # noqa: ANN401
        """Отследить отключение от сессии."""
        return None

    def track_ba_session_audit_failure() -> None:  # type: ignore[unused-ignore]
        """Отследить ошибку записи аудита."""
        return None


@dataclass
class Participant:
    """Участник сессии.

    Attributes:
        user_id: ID пользователя.
        role: Роль участника (например, 'analyst').
        websocket: WebSocket соединение.
        joined_at: Время присоединения.
    """
    user_id: str
    role: str
    websocket: WebSocket
    joined_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SessionState:
    """Состояние сессии.

    Attributes:
        session_id: ID сессии.
        topic: Тема обсуждения.
        created_at: Время создания.
        participants: Словарь участников {user_id: Participant}.
        history: История событий сессии.
    """
    session_id: str
    topic: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    participants: Dict[str, Participant] = field(default_factory=dict)
    history: List[Dict[str, Any]] = field(default_factory=list)


class BASessionManager:
    """
    Manage collaborative BA sessions over websockets.

    Responsibilities:
    - Maintain active sessions and participants
    - Broadcast events to session members
    - Persist audit log of session activity
    """

    def __init__(self, audit_path: Optional[Path] = None) -> None:
        """Инициализация менеджера сессий.

        Args:
            audit_path: Путь к файлу лога аудита.
        """
        self._sessions: Dict[str, SessionState] = {}
        self._lock = asyncio.Lock()
        self.audit_path = audit_path or Path("logs/audit/ba_sessions.log")
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)

    async def join_session(
        self,
        session_id: str,
        websocket: WebSocket,
        *,
        user_id: str,
        role: str = "analyst",
        topic: Optional[str] = None,
    ) -> SessionState:
        """Присоединить пользователя к сессии.

        Args:
            session_id: ID сессии.
            websocket: WebSocket соединение.
            user_id: ID пользователя.
            role: Роль пользователя.
            topic: Тема сессии (опционально).

        Returns:
            Объект состояния сессии.
        """
        await websocket.accept()
        async with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                session = SessionState(session_id=session_id, topic=topic)
                self._sessions[session_id] = session
            session.topic = topic or session.topic
            participant = Participant(user_id=user_id, role=role, websocket=websocket)
            session.participants[user_id] = participant
            self._write_audit(session_id, "join", {"user_id": user_id, "role": role})
            track_ba_session_event("join")
            self._update_metrics()
            logger.info("User %s joined session %s", user_id, session_id)
            return session

    async def leave_session(self, session_id: str, user_id: str) -> None:
        """Отключить пользователя от сессии.

        Args:
            session_id: ID сессии.
            user_id: ID пользователя.
        """
        async with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return
            participant = session.participants.pop(user_id, None)
            if participant:
                self._write_audit(session_id, "leave", {"user_id": user_id})
                track_ba_session_event("leave")
                logger.info("User %s left session %s", user_id, session_id)
            if not session.participants:
                self._sessions.pop(session_id, None)
                track_ba_session_event("session_closed")
            self._update_metrics()

    async def broadcast(
        self,
        session_id: str,
        message: Dict[str, Any],
        *,
        sender: Optional[str] = None,
    ) -> None:
        """Разослать сообщение всем участникам сессии.

        Args:
            session_id: ID сессии.
            message: Тело сообщения.
            sender: ID отправителя (опционально).
        """
        session = self._sessions.get(session_id)
        if not session:
            return
        payload = {
            **message,
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat(),
        }
        if sender:
            payload["sender"] = sender
        disconnects: List[str] = []
        for participant in list(session.participants.values()):
            try:
                await participant.websocket.send_json(payload)
            except Exception as exc:  # pragma: no cover - network errors
                logger.warning("Failed to send to %s: %s", participant.user_id, exc)
                disconnects.append(participant.user_id)
                track_ba_session_disconnect("send_error")
        for user_id in disconnects:
            await self.leave_session(session_id, user_id)
        event_type = str(payload.get("type") or "message")
        self._append_history(session, {"event_type": event_type, **payload})
        self._write_audit(session_id, event_type, payload)
        track_ba_session_event(event_type)

    async def send_private(
        self, session_id: str, user_id: str, message: Dict[str, Any]
    ) -> None:
        """Отправить личное сообщение участнику.

        Args:
            session_id: ID сессии.
            user_id: ID получателя.
            message: Тело сообщения.
        """
        session = self._sessions.get(session_id)
        if not session:
            return
        participant = session.participants.get(user_id)
        if not participant:
            return
        payload = {
            **message,
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat(),
        }
        await participant.websocket.send_json(payload)
        self._append_history(
            session, {"event_type": "private", "target": user_id, **payload}
        )
        self._write_audit(session_id, "private", {"target": user_id, **payload})
        track_ba_session_event("private")

    def get_session_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Получить текущее состояние сессии.

        Args:
            session_id: ID сессии.

        Returns:
            Словарь с состоянием сессии или None, если сессия не найдена.
        """
        session = self._sessions.get(session_id)
        if not session:
            return None
        return {
            "session_id": session.session_id,
            "topic": session.topic,
            "created_at": session.created_at.isoformat(),
            "participants": [
                {
                    "user_id": participant.user_id,
                    "role": participant.role,
                    "joined_at": participant.joined_at.isoformat(),
                }
                for participant in session.participants.values()
            ],
            "history": session.history[-200:],  # limit for api
        }

    def list_sessions(self) -> List[Dict[str, Any]]:
        """Получить список всех активных сессий.

        Returns:
            Список словарей с краткой информацией о сессиях.
        """
        return [
            {
                "session_id": session.session_id,
                "topic": session.topic,
                "created_at": session.created_at.isoformat(),
                "participants": len(session.participants),
            }
            for session in self._sessions.values()
        ]

    def clear(self) -> None:
        """Utility for tests to reset state."""
        self._sessions.clear()
        set_ba_session_counts(0, 0)

    def _append_history(self, session: SessionState, event: Dict[str, Any]) -> None:
        session.history.append(event)
        if len(session.history) > 500:
            session.history = session.history[-500:]

    def _write_audit(
        self, session_id: str, event_type: str, data: Dict[str, Any]
    ) -> None:
        record = {
            "session_id": session_id,
            "event_type": event_type,
            "data": data,
            "logged_at": datetime.utcnow().isoformat(),
        }
        try:
            with self.audit_path.open("a", encoding="utf-8") as f:
                json.dump(record, f, ensure_ascii=False)
                f.write("\n")
        except Exception as exc:  # pragma: no cover - filesystem
            logger.error("Failed to write audit log: %s", exc)
            track_ba_session_audit_failure()

    def _update_metrics(self) -> None:
        sessions_count = len(self._sessions)
        participants_count = sum(
            len(session.participants) for session in self._sessions.values()
        )
        set_ba_session_counts(sessions_count, participants_count)


ba_session_manager = BASessionManager()
