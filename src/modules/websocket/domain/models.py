"""Domain models for WebSocket module."""

from pydantic import BaseModel


class WebSocketMessage(BaseModel):
    type: str
    data: dict | None = None
