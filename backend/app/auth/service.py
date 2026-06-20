import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
from jose import JWTError, jwt
from sqlalchemy import select
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


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    user = await get_user_by_email(db, email)
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
