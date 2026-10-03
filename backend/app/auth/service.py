import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
from jose import JWTError, jwt
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import RefreshToken, User
from app.config import settings


def _hash_token(raw: str) -> str:
    """SHA-256 hex digest of a raw refresh-token string."""
    return hashlib.sha256(raw.encode()).hexdigest()


# ── Passwords ─────────────────────────────────────────────────────────────────


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ── JWT ───────────────────────────────────────────────────────────────────────


def create_access_token(user_id: uuid.UUID, email: str) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


VIEW_AS_MINUTES = 30
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
READ_ONLY_DETAIL = "This is a read-only view for TransferX staff. Nothing can be changed here."


def create_view_as_token(club_owner_id: uuid.UUID, email: str, *, staff_user_id: uuid.UUID) -> tuple[str, datetime]:
    """A short-lived, read-only access token that signs in as a club's owner,
    for TransferX staff to see exactly what the club sees ("view as this
    club"). `ro` makes every non-GET request fail (get_current_user); `act`
    names the staff member. No refresh token: it ends after 30 minutes."""
    expire = datetime.now(UTC) + timedelta(minutes=VIEW_AS_MINUTES)
    payload = {
        "sub": str(club_owner_id), "email": email, "exp": expire, "type": "access",
        "ro": True, "act": str(staff_user_id),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm), expire


def decode_access_token(token: str) -> dict:
    """Decode and validate an access token. Raises JWTError on failure."""
    payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    if payload.get("type") != "access":
        raise JWTError("Invalid token type")
    return payload


# ── Refresh tokens ────────────────────────────────────────────────────────────


def _new_refresh_token_string() -> str:
    return secrets.token_urlsafe(32)  # 43 URL-safe chars


async def create_refresh_token(db: AsyncSession, user_id: uuid.UUID) -> str:
    token_str = _new_refresh_token_string()
    token_hash = _hash_token(token_str)
    expires_at = datetime.now(UTC) + timedelta(days=settings.jwt_refresh_token_expire_days)
    db.add(RefreshToken(user_id=user_id, token=token_hash, expires_at=expires_at))
    await db.flush()
    return token_str  # return raw; only the hash is stored


async def rotate_refresh_token(db: AsyncSession, old_token_str: str) -> tuple[str, "User"]:
    """
    Validate old refresh token, delete it, issue a new one.
    Returns (new_token_str, user). Raises ValueError if invalid/expired.
    """
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token == _hash_token(old_token_str))
    )
    rt = result.scalar_one_or_none()

    if rt is None:
        raise ValueError("Refresh token not found")
    if rt.expires_at.replace(tzinfo=UTC) < datetime.now(UTC):
        await db.delete(rt)
        raise ValueError("Refresh token expired")

    user = await db.get(User, rt.user_id)
    if user is None or not user.is_active:
        raise ValueError("User not found or inactive")

    await db.delete(rt)
    new_token_str = await create_refresh_token(db, user.id)
    return new_token_str, user


async def revoke_refresh_token(db: AsyncSession, token_str: str) -> None:
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token == _hash_token(token_str))
    )
    rt = result.scalar_one_or_none()
    if rt:
        await db.delete(rt)


# ── User queries ──────────────────────────────────────────────────────────────


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await db.get(User, user_id)


class AmbiguousUsername(Exception):
    """More than one account shares this username (the part of their emails
    before the "@"), so it cannot say which one is signing in."""


async def get_user_by_login(db: AsyncSession, identifier: str) -> User | None:
    """The user an email address or a username names, ignoring case.

    A username is the part of the email before the "@": "arsenal" signs in as
    arsenal@transferx.com. Two accounts can share one (owner@a.com and
    owner@b.com); that raises AmbiguousUsername rather than guessing.
    """
    ident = identifier.strip().lower()
    if not ident:
        return None
    if "@" in ident:
        return (await db.execute(select(User).where(func.lower(User.email) == ident))).scalar_one_or_none()
    # LIKE, with the pattern's own wildcards escaped: "a_b" must not match "axb@…".
    escaped = ident.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    matches = (await db.execute(
        select(User).where(func.lower(User.email).like(f"{escaped}@%", escape="\\")).limit(2)
    )).scalars().all()
    if len(matches) > 1:
        raise AmbiguousUsername(ident)
    return matches[0] if matches else None


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    """`email` is an email address or a username."""
    user = await get_user_by_login(db, email)
    if user is None or not verify_password(password, user.hashed_password):
        return None
    if not user.is_active:
        return None
    return user


async def change_password(db: AsyncSession, user: User, current_password: str, new_password: str) -> None:
    if not verify_password(current_password, user.hashed_password):
        raise ValueError("Current password is incorrect")
    user.hashed_password = hash_password(new_password)
    await db.flush()


async def create_user(
    db: AsyncSession,
    email: str,
    password: str,
    user_type: "UserType | None" = None,
) -> User:
    from app.auth.models import UserType

    existing = await get_user_by_email(db, email)
    if existing:
        raise ValueError("Email already registered")
    user = User(
        email=email,
        hashed_password=hash_password(password),
        user_type=user_type or UserType.CLUB,
    )
    db.add(user)
    await db.flush()
    return user


async def create_agent_profile(
    db: AsyncSession,
    user_id: uuid.UUID,
    display_name: str,
    agency_name: str,
    country: str,
    licence_no: str | None = None,
) -> "AgentProfile":
    from app.auth.models import AgentProfile

    profile = AgentProfile(
        user_id=user_id,
        display_name=display_name,
        agency_name=agency_name,
        licence_no=licence_no,
        country=country,
    )
    db.add(profile)
    await db.flush()
    return profile


async def create_player_profile(
    db: AsyncSession,
    user_id: uuid.UUID,
    player_id: uuid.UUID,
) -> "PlayerProfile":
    from app.auth.models import PlayerProfile

    # Reject if another user already claimed this player
    existing = await db.execute(
        select(PlayerProfile).where(PlayerProfile.player_id == player_id)
    )
    if existing.scalar_one_or_none() is not None:
        raise ValueError("Player record is already claimed by another user")

    profile = PlayerProfile(user_id=user_id, player_id=player_id)
    db.add(profile)
    await db.flush()
    return profile


# ── Password reset links (migration 0089) ────────────────────────────────────

RESET_LINK_HOURS = 24
MIN_PASSWORD_LENGTH = 8


async def create_password_reset(db: AsyncSession, user: User, *, created_by_user_id: uuid.UUID | None) -> tuple[str, datetime]:
    """A new one-time reset token for `user`, replacing any unused one.
    Returns (raw token, expiry); only its hash is stored."""
    from sqlalchemy import update

    from app.auth.models import PasswordResetToken

    now = datetime.now(UTC)
    await db.execute(update(PasswordResetToken).where(
        PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None),
    ).values(used_at=now))
    raw = secrets.token_urlsafe(32)
    expires_at = now + timedelta(hours=RESET_LINK_HOURS)
    db.add(PasswordResetToken(user_id=user.id, token_hash=_hash_token(raw), expires_at=expires_at,
                              created_by_user_id=created_by_user_id))
    await db.flush()
    return raw, expires_at


async def live_password_reset(db: AsyncSession, raw: str):
    """The unused, unexpired token for `raw`, or None (no hint as to why)."""
    from app.auth.models import PasswordResetToken

    row = (await db.execute(select(PasswordResetToken).where(
        PasswordResetToken.token_hash == _hash_token(raw)))).scalar_one_or_none()
    if row is None or row.used_at is not None or row.expires_at.replace(tzinfo=UTC) < datetime.now(UTC):
        return None
    return row


async def complete_password_reset(db: AsyncSession, raw: str, new_password: str) -> User:
    """Set the new password, use up the token, and sign the person out
    everywhere: every refresh token is deleted, so a stolen session ends."""
    from sqlalchemy import delete

    if len(new_password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Use at least {MIN_PASSWORD_LENGTH} characters")
    row = await live_password_reset(db, raw)
    if row is None:
        raise LookupError("This link has expired or has already been used")
    user = await db.get(User, row.user_id)
    if user is None or not user.is_active:
        raise LookupError("This link has expired or has already been used")
    user.hashed_password = hash_password(new_password)
    row.used_at = datetime.now(UTC)
    await db.execute(delete(RefreshToken).where(RefreshToken.user_id == user.id))
    await db.flush()
    return user
