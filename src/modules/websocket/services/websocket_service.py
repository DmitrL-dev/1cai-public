import asyncio
import re
from datetime import datetime
from typing import Dict

from fastapi import WebSocket

from src.services.websocket_manager import manager
from src.utils.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


class WebSocketService:
    """Service for WebSocket operations."""

    async def handle_connection(self, websocket: WebSocket, user_id: str) -> None:
        """Handle WebSocket connection lifecycle."""
        # Input validation
        if not user_id or len(user_id) > 200:
            logger.warning(
                f"Invalid user_id for WebSocket connection: {user_id}",
                extra={"user_id": user_id},
            )
            await websocket.close(code=1008, reason="Invalid user_id")
            return

        # Sanitize user_id
        if not re.match(r"^[a-zA-Z0-9_.-]+$", user_id):
            logger.warning(f"Invalid characters in user_id: {user_id}", extra={
                           "user_id": user_id})
            await websocket.close(code=1008, reason="Invalid user_id format")
            return

        try:
            await manager.connect(websocket, user_id=user_id)

            # Send welcome message
            await asyncio.wait_for(
                websocket.send_json(
                    {
                        "type": "connected",
                        "message": f"Connected to notifications for user {user_id}",
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                ),
                timeout=5.0,
            )

            logger.info("WebSocket connected", extra={"user_id": user_id})

            while True:
                try:
                    data = await asyncio.wait_for(websocket.receive_json(), timeout=300.0)
                except asyncio.TimeoutError:
                    try:
                        await websocket.send_json({"type": "ping"})
                        continue
                    except Exception:
                        break

                if not isinstance(data, dict):
                    logger.warning(
                        "Invalid message format received",
                        extra={"user_id": user_id, "message_type": type(data).__name__},
                    )
                    await websocket.send_json({"type": "error", "message": "Invalid message format"})
                    continue

                message_type = data.get("type", "")

                if message_type == "ping":
                    await websocket.send_json({"type": "pong", "timestamp": datetime.utcnow().isoformat()})

                elif message_type == "subscribe":
                    room_id = data.get("room_id")
                    if room_id:
                        if isinstance(room_id, str) and len(room_id) <= 200:
                            room_id = re.sub(r"[^a-zA-Z0-9_.-]", "", room_id)
                            manager.join_room(websocket, room_id)
                            await websocket.send_json(
                                {
                                    "type": "subscribed",
                                    "room_id": room_id,
                                    "timestamp": datetime.utcnow().isoformat(),
                                }
                            )
                        else:
                            logger.warning(
                                "Invalid room_id in subscribe request",
                                extra={"user_id": user_id, "room_id": room_id},
                            )
                            await websocket.send_json({"type": "error", "message": "Invalid room_id"})
                else:
                    logger.debug(
                        f"Unknown message type: {message_type}",
                        extra={"user_id": user_id, "message_type": message_type},
                    )

        except Exception as e:
            logger.error(
                f"WebSocket error: {e}",
                extra={"user_id": user_id, "error_type": type(e).__name__},
                exc_info=True,
            )
        finally:
            manager.disconnect(websocket, user_id=user_id)
            logger.info("WebSocket disconnected", extra={"user_id": user_id})

    async def notify_user(self, user_id: str, notification_type: str, data: Dict) -> None:
        """Send notification to user via WebSocket."""
        if not user_id or not isinstance(user_id, str):
            logger.warning(
                f"Invalid user_id for notification: {user_id}",
                extra={"user_id": user_id, "notification_type": notification_type},
            )
            return

        if not notification_type or not isinstance(notification_type, str):
            logger.warning(
                f"Invalid notification_type: {notification_type}",
                extra={"user_id": user_id},
            )
            return

        if not isinstance(data, dict):
            logger.warning(
                f"Invalid data type for notification: {type(data)}",
                extra={"user_id": user_id, "notification_type": notification_type},
            )
            return

        message = {
            "type": notification_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
        }

        try:
            await manager.send_personal_message(message, user_id)
            logger.debug(
                "Notification sent",
                extra={"user_id": user_id, "notification_type": notification_type},
            )
        except Exception as e:
            logger.error(
                f"Failed to send notification: {e}",
                extra={
                    "user_id": user_id,
                    "notification_type": notification_type,
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )
