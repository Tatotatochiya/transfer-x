"""TRA-151: club role capabilities — the single source of truth for what each
club role may do.

D1/D2 (club-team-roles-and-onboarding spec): five fixed roles (OWNER is the
club's primary account, not a ClubStaff row; the other four live in StaffRole),
one static capability matrix, one dependency. Check order: superuser bypass
first (house pattern — see docs/architecture/authentication-and-permissions.md),
then owner → all capabilities, then staff → matrix, else 403.

The UI never re-derives this matrix — it consumes it via GET /clubs/me/membership (D3).
"""
import enum
import uuid

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.database import get_db


class Capability(str, enum.Enum):
    SCOUTING_WRITE = "SCOUTING_WRITE"   # shortlists, player interest
    MARKET_WRITE = "MARKET_WRITE"       # sales, bids, offers, squad player edits
    DEAL_WRITE = "DEAL_WRITE"           # deal lifecycle, terms, clauses, deal-room writes
    CLUB_ADMIN = "CLUB_ADMIN"           # club profile, finance budgets, verification request
    TEAM_MANAGE = "TEAM_MANAGE"         # invite/remove staff, change roles, approval policy
    APPROVE_ACTIONS = "APPROVE_ACTIONS" # decide pending approvals


# Viewing is not a capability — club data visibility comes from membership itself.
ROLE_CAPABILITIES: dict[str, frozenset[Capability]] = {
    "OWNER": frozenset(Capability),
    "SPORTING_DIRECTOR": frozenset({
        Capability.SCOUTING_WRITE,
        Capability.MARKET_WRITE,
        Capability.DEAL_WRITE,
        Capability.CLUB_ADMIN,
        Capability.APPROVE_ACTIONS,
    }),
    "MANAGER": frozenset({
        Capability.SCOUTING_WRITE,
        Capability.MARKET_WRITE,
        Capability.DEAL_WRITE,
    }),
    "SCOUT": frozenset({
        Capability.SCOUTING_WRITE,
    }),
    "READONLY": frozenset(),
}


def capabilities_for_role(role: str) -> list[Capability]:
    """Sorted capability list for a role — for the membership endpoint."""
    return sorted(ROLE_CAPABILITIES.get(role, frozenset()), key=lambda c: c.value)


async def ensure_club_capability(db: AsyncSession, user: User, cap: Capability) -> None:
    """Raise 403 unless the user's club role grants `cap`.

    Safe on mixed-caller endpoints only inside the club branch — a user with no
    club membership always 403s here.
    """
    if user.is_superuser:
        return
    from app.clubs import service as clubs_service
    role = await clubs_service.get_club_membership_role(db, uuid.UUID(str(user.id)))
    if role is None or cap not in ROLE_CAPABILITIES.get(role, frozenset()):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Your club role does not allow this action ({cap.value} required)",
        )


async def ensure_capability_if_club_member(db: AsyncSession, user: User, cap: Capability) -> None:
    """Like ensure_club_capability, but a no-op for non-club users (agents,
    players) — for shared surfaces like the deal room where those callers are
    authorized by the participant check instead.
    """
    if user.is_superuser:
        return
    from app.clubs import service as clubs_service
    role = await clubs_service.get_club_membership_role(db, uuid.UUID(str(user.id)))
    if role is None:
        return
    if cap not in ROLE_CAPABILITIES.get(role, frozenset()):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Your club role does not allow this action ({cap.value} required)",
        )


def require_club_capability(cap: Capability):
    """FastAPI dependency: 403 unless the caller's club role grants `cap`.

    Superuser bypass first, always. Use only on endpoints whose non-superuser
    callers are exclusively club members; mixed-caller endpoints must call
    ensure_club_capability inside their club branch instead.
    """
    async def _dep(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        await ensure_club_capability(db, current_user, cap)
        return current_user

    return _dep
