"""
WebSocket Manager for Real-Time Updates
Версия: 2.1.0

Улучшения:
- Улучшена обработка ошибок
- Structured logging
- Input validation
- Connection timeout handling
"""

import asyncio
from typing import Any, Dict, Optional, Set

from fastapi import WebSocket

from src.utils.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


class ConnectionManager:
    """
    WebSocket connection manager

    Features:
    - Connection pooling by user/tenant
    - Broadcast to all connections
    - Send to specific user/tenant
    - Room-based messaging
    """

    def __init__(self):
        # Active connections
        self.active_connections: Set[WebSocket] = set()

        # User connections (user_id → WebSocket)
        self.user_connections: Dict[str, Set[WebSocket]] = {}

        # Tenant connections (tenant_id → WebSocket)
        self.tenant_connections: Dict[str, Set[WebSocket]] = {}

        # Room connections (room_id → WebSocket)
        self.room_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(
        self,
        websocket: WebSocket,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        timeout: float = 10.0,
    ):
        """
        Accept new WebSocket connection

        Args:
            websocket: WebSocket connection
            user_id: User ID (optional)
            tenant_id: Tenant ID (optional)
            timeout: Connection timeout (seconds)
        """
        try:
            # Input validation
            if user_id and not isinstance(user_id, str):
                raise ValueError(f"Invalid user_id type: {type(user_id)}")
            if tenant_id and not isinstance(tenant_id, str):
                raise ValueError(f"Invalid tenant_id type: {type(tenant_id)}")

            # Accept connection with timeout
            await asyncio.wait_for(websocket.accept(), timeout=timeout)

            self.active_connections.add(websocket)

            if user_id:
                if user_id not in self.user_connections:
                    self.user_connections[user_id] = set()
                self.user_connections[user_id].add(websocket)

            if tenant_id:
                if tenant_id not in self.tenant_connections:
                    self.tenant_connections[tenant_id] = set()
                self.tenant_connections[tenant_id].add(websocket)

            logger.info(
                "WebSocket connected",
                extra={
                    "user_id": user_id,
                    "tenant_id": tenant_id,
                    "total_connections": len(self.active_connections),
                },
            )
        except asyncio.TimeoutError:
            logger.error(
                "WebSocket connection timeout",
                extra={"user_id": user_id, "tenant_id": tenant_id, "timeout": timeout},
            )
            raise
        except Exception as e:
            logger.error(
                "WebSocket connection error",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "user_id": user_id,
                    "tenant_id": tenant_id,
                },
                exc_info=True,
            )
            raise

    def disconnect(
        self, websocket: WebSocket, user_id: str = None, tenant_id: str = None
    ):
        """Remove WebSocket connection с input validation"""
        # Input validation
        if user_id and not isinstance(user_id, str):
            logger.warning(
                "Invalid user_id type in disconnect",
                extra={"user_id_type": type(user_id).__name__},
            )
            user_id = None

        if tenant_id and not isinstance(tenant_id, str):
            logger.warning(
                "Invalid tenant_id type in disconnect",
                extra={"tenant_id_type": type(tenant_id).__name__},
            )
            tenant_id = None

        self.active_connections.discard(websocket)

        if user_id and user_id in self.user_connections:
            self.user_connections[user_id].discard(websocket)
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]

        if tenant_id and tenant_id in self.tenant_connections:
            self.tenant_connections[tenant_id].discard(websocket)
            if not self.tenant_connections[tenant_id]:
                del self.tenant_connections[tenant_id]

        logger.info(
            "WebSocket disconnected",
            extra={
                "user_id": user_id,
                "tenant_id": tenant_id,
                "total_connections": len(self.active_connections),
            },
        )

    async def send_personal_message(
        self, message: Dict[str, Any], user_id: str, timeout: float = 5.0
    ):
        """
        Send message to specific user (all their connections)

        Args:
            message: Message to send
            user_id: User ID
            timeout: Send timeout (seconds)
        """
        # Input validation
        if not user_id or not isinstance(user_id, str):
            logger.warning(
                f"Invalid user_id for send_personal_message: {user_id}",
                extra={"user_id": user_id, "message_type": type(message).__name__},
            )
            return

        if not isinstance(message, dict):
            logger.warning(
                f"Invalid message type: {type(message)}",
                extra={"user_id": user_id, "message_type": type(message).__name__},
            )
            return

        if user_id in self.user_connections:
            disconnected = []
            for websocket in self.user_connections[user_id]:
                try:
                    await asyncio.wait_for(
                        websocket.send_json(message), timeout=timeout
                    )
                except asyncio.TimeoutError:
                    logger.warning(
                        f"Send message timeout to user {user_id}",
                        extra={"user_id": user_id, "timeout": timeout},
                    )
                    disconnected.append(websocket)
                except Exception as e:
                    # Connection closed or error
                    logger.warning(
                        f"Failed to send message to user {user_id}: {e}",
                        extra={"user_id": user_id, "error_type": type(e).__name__},
                    )
                    disconnected.append(websocket)

            # Clean up disconnected connections
            for ws in disconnected:
                self.disconnect(ws, user_id=user_id)

    async def send_to_tenant(
        self, message: Dict[str, Any], tenant_id: str, timeout: float = 5.0
    ):
        """Send message to all users in tenant с input validation"""
        # Input validation
        if not tenant_id or not isinstance(tenant_id, str):
            logger.warning(
                "Invalid tenant_id for send_to_tenant",
                extra={
                    "tenant_id": tenant_id,
                    "tenant_id_type": type(tenant_id).__name__ if tenant_id else None,
                },
            )
            return

        if not isinstance(message, dict):
            logger.warning(
                "Invalid message type for send_to_tenant",
                extra={"tenant_id": tenant_id, "message_type": type(message).__name__},
            )
            return

        if tenant_id in self.tenant_connections:
            disconnected = []
            for websocket in self.tenant_connections[tenant_id]:
                try:
                    await asyncio.wait_for(
                        websocket.send_json(message), timeout=timeout
                    )
                except asyncio.TimeoutError:
                    logger.warning(
                        f"Send message timeout to tenant {tenant_id}",
                        extra={"tenant_id": tenant_id, "timeout": timeout},
                    )
                    disconnected.append(websocket)
                except Exception as e:
                    logger.warning(
                        f"Failed to send message to tenant {tenant_id}: {e}",
                        extra={"tenant_id": tenant_id, "error_type": type(e).__name__},
                    )
                    disconnected.append(websocket)

            # Clean up disconnected connections
            for ws in disconnected:
                self.disconnect(ws, tenant_id=tenant_id)

    async def send_to_room(
        self, message: Dict[str, Any], room_id: str, timeout: float = 5.0
    ):
        """Send message to all connections in room с input validation"""
        # Input validation
        if not room_id or not isinstance(room_id, str):
            logger.warning(
                "Invalid room_id for send_to_room",
                extra={
                    "room_id": room_id,
                    "room_id_type": type(room_id).__name__ if room_id else None,
                },
            )
            return

        if not isinstance(message, dict):
            logger.warning(
                "Invalid message type for send_to_room",
                extra={"room_id": room_id, "message_type": type(message).__name__},
            )
            return

        if room_id in self.room_connections:
            disconnected = []
            for websocket in self.room_connections[room_id]:
                try:
                    await asyncio.wait_for(
                        websocket.send_json(message), timeout=timeout
                    )
                except asyncio.TimeoutError:
                    logger.warning(
                        f"Send message timeout to room {room_id}",
                        extra={"room_id": room_id, "timeout": timeout},
                    )
                    disconnected.append(websocket)
                except Exception as e:
                    logger.warning(
                        f"Failed to send message to room {room_id}: {e}",
                        extra={"room_id": room_id, "error_type": type(e).__name__},
                    )
                    disconnected.append(websocket)

            # Clean up disconnected connections
            for ws in disconnected:
                self.disconnect(ws)
                if room_id in self.room_connections:
                    self.room_connections[room_id].discard(ws)

    async def broadcast(self, message: Dict[str, Any], timeout: float = 5.0):
        """Broadcast message to all active connections с input validation"""
        # Input validation
        if not isinstance(message, dict):
            logger.warning(
                "Invalid message type for broadcast",
                extra={"message_type": type(message).__name__},
            )
            return

        disconnected = []
        for websocket in self.active_connections.copy():
            try:
                await asyncio.wait_for(websocket.send_json(message), timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning(
                    "Broadcast message timeout",
                    extra={
                        "timeout": timeout,
                        "total_connections": len(self.active_connections),
                    },
                )
                disconnected.append(websocket)
            except Exception as e:
                logger.warning(
                    f"Failed to broadcast message: {e}",
                    extra={"error_type": type(e).__name__},
                )
                disconnected.append(websocket)

        # Clean up disconnected connections
        for ws in disconnected:
            self.disconnect(ws)

    def join_room(self, websocket: WebSocket, room_id: str):
        """Add connection to room"""
        if room_id not in self.room_connections:
            self.room_connections[room_id] = set()
        self.room_connections[room_id].add(websocket)

    def leave_room(self, websocket: WebSocket, room_id: str):
        """Remove connection from room"""
        if room_id in self.room_connections:
            self.room_connections[room_id].discard(websocket)

    def get_stats(self) -> Dict:
        """Get connection statistics"""
        return {
            "total_connections": len(self.active_connections),
            "users_connected": len(self.user_connections),
            "tenants_connected": len(self.tenant_connections),
            "active_rooms": len(self.room_connections),
        }


# Global instance
manager = ConnectionManager()


# Example WebSocket endpoint:
"""
from fastapi import WebSocket, WebSocketDisconnect
from src.services.websocket_manager import manager

@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await manager.connect(websocket, user_id=user_id)

    try:
        while True:
            # Receive message
            data = await websocket.receive_json()

            # Process message
            if data['type'] == 'subscribe':
                manager.join_room(websocket, data['room_id'])

            elif data['type'] == 'message':
                # Broadcast to room
                await manager.send_to_room({
                    'type': 'message',
                    'from': user_id,
                    'text': data['text']
                }, data['room_id'])

    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id=user_id)
"""
