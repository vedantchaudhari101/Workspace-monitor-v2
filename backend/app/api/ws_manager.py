"""WebSocket connection manager for real-time seat occupancy updates.

Provides a thread-safe-ish asynchronous connection manager to track active
WebSocket connections and broadcast state transitions to all connected clients.
"""
from __future__ import annotations

from typing import List
from fastapi import WebSocket
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ConnectionManager:
    """Manages active WebSocket connections for real-time occupancy updates."""

    def __init__(self) -> None:
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        """Accepts a new WebSocket connection and adds it to the active pool."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(
            "WebSocket client connected",
            extra={"total_connections": len(self.active_connections)},
        )

    def disconnect(self, websocket: WebSocket) -> None:
        """Removes a WebSocket connection from the active pool."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(
            "WebSocket client disconnected",
            extra={"total_connections": len(self.active_connections)},
        )

    async def broadcast(self, message: dict) -> None:
        """Broadcasts a JSON message to all subscribed WebSocket clients.

        Expected format:
        {
            "type": "seat_update",
            "seat_id": str(seat_id),
            "status": "OCCUPIED" | "VACANT"
        }
        """
        disconnected_connections: List[WebSocket] = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(
                    f"Failed to send JSON message over WebSocket: {e}",
                    extra={"websocket": id(connection)},
                )
                disconnected_connections.append(connection)

        # Clean up any stale connections
        for connection in disconnected_connections:
            self.disconnect(connection)


# Global instance for app-wide use
manager = ConnectionManager()
