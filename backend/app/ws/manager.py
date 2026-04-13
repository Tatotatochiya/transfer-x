"""In-process WebSocket connection manager.

Each authenticated user may hold multiple connections (multiple tabs).
Events are JSON-serialisable dicts, e.g.:
  {"type": "SALE_UPDATED",  "id": "<sale_id>"}
  {"type": "BID_PLACED",    "sale_id": "<sale_id>"}
  {"type": "OFFER_UPDATED", "id": "<offer_id>"}
  {"type": "DEAL_UPDATED",  "id": "<deal_id>"}
"""

import asyncio
import logging
import uuid
from collections import defaultdict

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        # user_id → set of active WebSocket connections
        self._connections: dict[uuid.UUID, set[WebSocket]] = defaultdict(set)

    def connect(self, user_id: uuid.UUID, ws: WebSocket) -> None:
        self._connections[user_id].add(ws)

    def disconnect(self, user_id: uuid.UUID, ws: WebSocket) -> None:
        self._connections[user_id].discard(ws)
        if not self._connections[user_id]:
            del self._connections[user_id]

    async def send_to_user(self, user_id: uuid.UUID, payload: dict) -> None:
        sockets = list(self._connections.get(user_id, []))
        if not sockets:
            return
        dead: list[WebSocket] = []
        for ws in sockets:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(user_id, ws)

    async def broadcast_to_users(self, user_ids: list[uuid.UUID], payload: dict) -> None:
        await asyncio.gather(*(self.send_to_user(uid, payload) for uid in user_ids))


# Singleton — imported by routers and the WS endpoint
manager = ConnectionManager()
