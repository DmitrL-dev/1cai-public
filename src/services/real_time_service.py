
"""
Real-Time Service
Версия: 2.1.0

Улучшения:
- Input validation
- Structured logging
- Улучшена обработка ошибок
- Timeout handling
"""

import asyncio
import re
from datetime import datetime
from typing import Any, Dict, Set

from fastapi import WebSocket

from src.utils.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


class RealTimeManager:
    """
    Manages WebSocket connections and broadcasts updates

    Features:
    - Connection management
    - Topic-based subscriptions
    - Broadcast to specific topics
    - Automatic reconnection handling
    """

    def __init__(self):
        # Active connections: topic → set of websockets
        self.connections: Dict[str, Set[WebSocket]] = {}
        self.connection_metadata: Dict[WebSocket, Dict] = {}

    async def connect(self, websocket: WebSocket, topic: str = "general", timeout: float = 10.0):
        """
        Accept new WebSocket connection

        Args:
            websocket: WebSocket connection
            topic: Topic to subscribe to
            timeout: Connection timeout (seconds)
        """
        # Input validation
        if not topic or not isinstance(topic, str):
            raise ValueError(f"Invalid topic: {topic}")

        # Sanitize topic (prevent injection)
        topic = re.sub(r"[^a-zA-Z0-9_.-]", "", topic)
        if not topic:
            topic = "general"

        # Validate topic length
        if len(topic) > 100:
            logger.warning(
                f"Topic too long, truncating: {topic}",
                extra={"original_topic": topic, "topic_length": len(topic)},
            )
            topic = topic[:100]

        try:
            await asyncio.wait_for(websocket.accept(), timeout=timeout)

            if topic not in self.connections:
                self.connections[topic] = set()

            self.connections[topic].add(websocket)
            self.connection_metadata[websocket] = {
                "topic": topic,
                "connected_at": datetime.now(),
                "messages_sent": 0,
            }

            logger.info(
                f"Client connected to topic '{topic}'",
                extra={
                    "topic": topic,
                    "total_connections": len(self.connections[topic]),
                },
            )

            # Send welcome message with timeout
            await asyncio.wait_for(
                self.send_to_client(
                    websocket,
                    {
                        "type": "connected",
                        "topic": topic,
                        "timestamp": datetime.now().isoformat(),
                    },
                ),
                timeout=5.0,
            )
        except asyncio.TimeoutError:
            logger.error(
                f"WebSocket connection timeout after {timeout}s",
                extra={"topic": topic, "timeout": timeout},
            )
            raise
        except Exception as e:
            logger.error(
                f"Error connecting WebSocket: {e}",
                extra={"topic": topic, "error_type": type(e).__name__},
                exc_info=True,
            )
            raise

    async def disconnect(self, websocket: WebSocket):
        """Disconnect client"""
        try:
            topic = self.connection_metadata.get(websocket, {}).get("topic")

            if topic and topic in self.connections:
                self.connections[topic].discard(websocket)

                if not self.connections[topic]:
                    del self.connections[topic]

            if websocket in self.connection_metadata:
                del self.connection_metadata[websocket]

            logger.info("Client disconnected", extra={"topic": topic})

        except Exception as e:
            logger.error(
                "Error during disconnect",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "topic": topic if "topic" in locals() else None,
                },
                exc_info=True,
            )

    async def send_to_client(self, websocket: WebSocket, message: Dict[str, Any], timeout: float = 5.0):
        """
        Send message to specific client

        Args:
            websocket: WebSocket connection
            message: Message to send
            timeout: Send timeout (seconds)
        """
        # Input validation
        if not isinstance(message, dict):
            logger.warning(
                f"Invalid message type: {type(message)}",
                extra={"message_type": type(message).__name__},
            )
            return

        try:
            await asyncio.wait_for(websocket.send_json(message), timeout=timeout)

            if websocket in self.connection_metadata:
                self.connection_metadata[websocket]["messages_sent"] += 1

        except asyncio.TimeoutError:
            logger.warning(f"Send message timeout after {timeout}s", extra={
                           "timeout": timeout})
            await self.disconnect(websocket)
        except Exception as e:
            logger.error(
                f"Error sending to client: {e}",
                extra={
                    "error_type": type(e).__name__,
                    "message_type": message.get("type", "unknown"),
                },
                exc_info=True,
            )
            await self.disconnect(websocket)

    async def broadcast_to_topic(self, topic: str, message: Dict[str, Any], timeout: float = 5.0):
        """
        Broadcast message to all clients subscribed to topic с input validation

        Args:
            topic: Topic name
            message: Message to broadcast
            timeout: Send timeout (seconds)
        """
        # Input validation
        if not topic or not isinstance(topic, str):
            logger.warning(
                "Invalid topic for broadcast_to_topic",
                extra={
                    "topic": topic,
                    "topic_type": type(topic).__name__ if topic else None,
                },
            )
            return

        if not isinstance(message, dict):
            logger.warning(
                "Invalid message type for broadcast_to_topic",
                extra={"topic": topic, "message_type": type(message).__name__},
            )
            return

        # Sanitize topic
        topic = re.sub(r"[^a-zA-Z0-9_.-]", "", topic)
        if not topic:
            logger.warning("Topic sanitized to empty, skipping broadcast")
            return

        if topic not in self.connections:
            logger.debug("No connections for topic", extra={"topic": topic})
            return

        # Add metadata
        message["topic"] = topic
        message["timestamp"] = datetime.now().isoformat()

        # Broadcast to all clients
        disconnected = []

        for websocket in self.connections[topic].copy():
            try:
                await asyncio.wait_for(websocket.send_json(message), timeout=timeout)

                if websocket in self.connection_metadata:
                    self.connection_metadata[websocket]["messages_sent"] += 1

            except asyncio.TimeoutError:
                logger.warning(
                    f"Send timeout to client on topic '{topic}'",
                    extra={"topic": topic, "timeout": timeout},
                )
                disconnected.append(websocket)
            except Exception as e:
                logger.warning(
                    f"Failed to send to client: {e}",
                    extra={"topic": topic, "error_type": type(e).__name__},
                )
                disconnected.append(websocket)

        # Clean up disconnected clients
        for ws in disconnected:
            await self.disconnect(ws)

        logger.info(
            f"Broadcasted to {len(self.connections[topic])} clients on topic '{topic}'",
            extra={
                "topic": topic,
                "clients_count": len(self.connections[topic]),
                "disconnected_count": len(disconnected),
            },
        )

    async def broadcast_dashboard_update(self, dashboard_type: str, data: Dict[str, Any]):
        """
        Broadcast dashboard data update

        Args:
            dashboard_type: owner, executive, pm, developer, team_lead, ba
            data: Dashboard data
        """
        await self.broadcast_to_topic(
            f"dashboard_{dashboard_type}",
            {"type": "dashboard_update", "dashboard": dashboard_type, "data": data},
        )

    async def broadcast_notification(self, user_id: str, notification: Dict[str, Any]):
        """Send notification to specific user"""
        await self.broadcast_to_topic(f"user_{user_id}", {"type": "notification", "notification": notification})

    async def broadcast_system_alert(self, alert: Dict[str, Any]):
        """Broadcast system-wide alert"""
        await self.broadcast_to_topic("system", {"type": "alert", "alert": alert})

    def get_stats(self) -> Dict[str, Any]:
        """Get connection statistics"""
        total_connections = sum(len(clients) for clients in self.connections.values())

        return {
            "total_connections": total_connections,
            "topics": list(self.connections.keys()),
            "connections_per_topic": {topic: len(clients) for topic, clients in self.connections.items()},
            "total_messages_sent": sum(meta["messages_sent"] for meta in self.connection_metadata.values()),
        }


# Global instance
real_time_manager = RealTimeManager()


# Helper for background tasks moved to src/modules/dashboard/tasks/updater.py
