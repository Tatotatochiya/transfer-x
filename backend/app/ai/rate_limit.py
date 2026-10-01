"""Per-user sliding-window rate limiter for AI endpoints (in-memory)."""
from __future__ import annotations

import time
import uuid
from collections import defaultdict, deque

from fastapi import HTTPException, status

_WINDOW_SECONDS = 3600  # 1 hour
_MAX_REQUESTS = 20
# Ask has its own allowance, so a director asking questions doesn't lock out
# the offer advisor (Lite plan, BACKEND.md §3).
_LIMITS = {"default": _MAX_REQUESTS, "ask": 40}

_windows: dict[str, deque[float]] = defaultdict(deque)


def check_rate_limit(user_id: uuid.UUID, bucket: str = "default") -> None:
    key = str(user_id) if bucket == "default" else f"{user_id}:{bucket}"
    limit = _LIMITS.get(bucket, _MAX_REQUESTS)
    now = time.monotonic()
    window = _windows[key]
    while window and now - window[0] > _WINDOW_SECONDS:
        window.popleft()
    if len(window) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"AI rate limit reached: {limit} requests per hour.",
        )
    window.append(now)


def get_rate_limit_status(user_id: uuid.UUID) -> dict:
    key = str(user_id)
    now = time.monotonic()
    window = _windows[key]
    while window and now - window[0] > _WINDOW_SECONDS:
        window.popleft()
    used = len(window)
    return {"used": used, "limit": _MAX_REQUESTS, "remaining": max(0, _MAX_REQUESTS - used)}
