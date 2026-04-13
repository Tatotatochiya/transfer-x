"""WebSocket endpoint — authenticated via access token query param."""

import logging
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.auth import service as auth_service
from app.ws.manager import manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ws"])


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket, token: str | None = None) -> None:
    """Client connects with ?token=<access_token>.

    On auth failure the connection is rejected (code 4001).
    Afterwards the server only pushes; client messages are ignored.
    """
    if not token:
        await ws.close(code=4001, reason="Missing token")
        return

    try:
        payload = auth_service.decode_access_token(token)
        user_id = uuid.UUID(payload["sub"])
    except Exception:
        await ws.close(code=4001, reason="Invalid token")
        return

    await ws.accept()
    manager.connect(user_id, ws)
    logger.debug("WS connected user=%s", user_id)

    try:
        # Keep alive — we only push from server, but must drain to detect disconnects
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(user_id, ws)
        logger.debug("WS disconnected user=%s", user_id)
