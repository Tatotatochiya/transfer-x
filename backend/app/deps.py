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
    "require_club_write_access",
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


async def require_club_write_access(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Raises 403 if the current user is a read-only staff member."""
    from app.clubs.models import StaffRole
    from app.clubs import service as clubs_service
    staff = await clubs_service.get_staff_by_user_id(db, current_user.id)
    if staff and staff.role == StaffRole.READONLY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Read-only staff cannot perform this action",
        )
    return current_user
