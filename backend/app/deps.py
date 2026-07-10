"""
Shared FastAPI dependencies — import from here rather than individual modules.
"""

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import service as auth_service
from app.auth.dependencies import get_current_user, get_current_superuser
from app.auth.models import User
from app.database import get_db

__all__ = [
    "get_db",
    "get_current_user",
    "get_current_superuser",
    "get_optional_user",
    "get_seller_user",
    "get_buyer_user",
]

# ── Optional auth ─────────────────────────────────────────────────────────────

_optional_bearer = HTTPBearer(auto_error=False)


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_optional_bearer),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Returns the authenticated user, or None if no/invalid token provided."""
    if credentials is None:
        return None
    try:
        payload = auth_service.decode_access_token(credentials.credentials)
        user = await auth_service.get_user_by_id(db, uuid.UUID(payload["sub"]))
        return user if (user and user.is_active) else None
    except Exception:
        return None


# ── Role-gated dependencies ───────────────────────────────────────────────────


async def get_seller_user(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Requires the current user's club (owner or staff) to have SELLER or BOTH role."""
    if current_user.is_superuser:
        return current_user
    from app.clubs import service as clubs_service
    club = await clubs_service.get_club_for_user(db, current_user.id)
    if club is None or not clubs_service.can_sell(club.role):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Seller access required")
    return current_user


async def get_buyer_user(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Requires the current user's club (owner or staff) to have BUYER or BOTH role."""
    if current_user.is_superuser:
        return current_user
    from app.clubs import service as clubs_service
    club = await clubs_service.get_club_for_user(db, current_user.id)
    if club is None or not clubs_service.can_buy(club.role):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Buyer access required")
    return current_user


async def get_current_agent_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> "AgentProfile":
    from sqlalchemy import select
    from app.auth.models import AgentProfile, UserType
    if current_user.user_type != UserType.AGENT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Agent access required")
    result = await db.execute(select(AgentProfile).where(AgentProfile.user_id == current_user.id))
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent profile not found")
    return profile


async def get_current_player_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> "PlayerProfile":
    from sqlalchemy import select
    from app.auth.models import PlayerProfile, UserType
    if current_user.user_type != UserType.PLAYER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Player access required")
    result = await db.execute(select(PlayerProfile).where(PlayerProfile.user_id == current_user.id))
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player profile not found")
    return profile
