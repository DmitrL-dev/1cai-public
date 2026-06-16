"""
Session Service
"""
from typing import Any, Dict, List, Optional

from fastapi import WebSocket

from src.services.ba_session_manager import ba_session_manager


class SessionService:
    """Service for managing BA sessions"""

    async def join_session(
        self,
        session_id: str,
        websocket: WebSocket,
        user_id: str,
        role: str,
        topic: Optional[str] = None,
    ) -> None:
        """Join a session"""
        await ba_session_manager.join_session(
            session_id,
            websocket,
            user_id=user_id,
            role=role,
            topic=topic,
        )

    async def leave_session(self, session_id: str, user_id: str) -> None:
        """Leave a session"""
        await ba_session_manager.leave_session(session_id, user_id)

    async def broadcast(self, session_id: str, message: Dict[str, Any], sender: str) -> None:
        """Broadcast a message to a session"""
        await ba_session_manager.broadcast(session_id, message, sender=sender)

    def list_sessions(self) -> List[Dict[str, Any]]:
        """List active sessions"""
        return ba_session_manager.list_sessions()

    def get_session_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session state"""
        return ba_session_manager.get_session_state(session_id)
