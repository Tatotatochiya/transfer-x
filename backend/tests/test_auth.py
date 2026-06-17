"""
Auth endpoint tests — M1.

Covers: register, login, refresh, logout, /me, error cases.
Uses SQLite in-memory via conftest.py fixtures.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import service as auth_service

pytestmark = pytest.mark.asyncio


# ── Helpers ───────────────────────────────────────────────────────────────────


async def register(client: AsyncClient, email: str, password: str) -> dict:
    resp = await client.post("/auth/register", json={"email": email, "password": password})
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── Register ──────────────────────────────────────────────────────────────────


async def test_register_returns_tokens(client: AsyncClient):
    data = await register(client, "user@example.com", "strongpassword")
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


async def test_register_duplicate_email(client: AsyncClient):
    await register(client, "dup@example.com", "password123")
    resp = await client.post(
        "/auth/register", json={"email": "dup@example.com", "password": "other"}
    )
    assert resp.status_code == 409
    assert "already registered" in resp.json()["detail"]


async def test_register_invalid_email(client: AsyncClient):
    resp = await client.post(
        "/auth/register", json={"email": "not-an-email", "password": "password123"}
    )
    assert resp.status_code == 422


# ── Login ─────────────────────────────────────────────────────────────────────


async def test_login_success(client: AsyncClient):
    await register(client, "login@example.com", "mypassword")
    resp = await client.post(
        "/auth/login", json={"email": "login@example.com", "password": "mypassword"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data


async def test_login_wrong_password(client: AsyncClient):
    await register(client, "wrongpw@example.com", "correctpassword")
    resp = await client.post(
        "/auth/login", json={"email": "wrongpw@example.com", "password": "wrongpassword"}
    )
    assert resp.status_code == 401


async def test_login_unknown_email(client: AsyncClient):
    resp = await client.post(
        "/auth/login", json={"email": "nobody@example.com", "password": "password"}
    )
    assert resp.status_code == 401


# ── /me ───────────────────────────────────────────────────────────────────────


async def test_me_returns_user(client: AsyncClient):
    tokens = await register(client, "me@example.com", "password123")
    resp = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "me@example.com"
    assert data["is_active"] is True
    assert data["is_superuser"] is False


async def test_me_no_token(client: AsyncClient):
    resp = await client.get("/auth/me")
    assert resp.status_code == 401


async def test_me_invalid_token(client: AsyncClient):
    resp = await client.get("/auth/me", headers={"Authorization": "Bearer invalidtoken"})
    assert resp.status_code == 401


# ── Refresh ───────────────────────────────────────────────────────────────────


async def test_refresh_issues_new_tokens(client: AsyncClient):
    tokens = await register(client, "refresh@example.com", "password123")
    resp = await client.post(
        "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    # Refresh token is always a new random value; access token may be identical if
    # issued within the same second (same exp), so only assert on refresh token.
    assert data["refresh_token"] != tokens["refresh_token"]


async def test_refresh_old_token_invalidated(client: AsyncClient):
    """After rotating, the old refresh token must not work again."""
    tokens = await register(client, "rotate@example.com", "password123")
    original_refresh = tokens["refresh_token"]

    # First use — should succeed
    resp = await client.post("/auth/refresh", json={"refresh_token": original_refresh})
    assert resp.status_code == 200

    # Second use of original — must fail (it was deleted on rotation)
    resp2 = await client.post("/auth/refresh", json={"refresh_token": original_refresh})
    assert resp2.status_code == 401


async def test_refresh_unknown_token(client: AsyncClient):
    resp = await client.post("/auth/refresh", json={"refresh_token": "unknowntoken"})
    assert resp.status_code == 401


# ── Logout ────────────────────────────────────────────────────────────────────


async def test_logout_revokes_refresh_token(client: AsyncClient):
    tokens = await register(client, "logout@example.com", "password123")
    resp = await client.post("/auth/logout", json={"refresh_token": tokens["refresh_token"]})
    assert resp.status_code == 204

    # Refresh token should now be invalid
    resp2 = await client.post(
        "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert resp2.status_code == 401


async def test_logout_unknown_token_is_silent(client: AsyncClient):
    """Logging out a token that doesn't exist should succeed silently (idempotent)."""
    resp = await client.post("/auth/logout", json={"refresh_token": "nosuchtoken"})
    assert resp.status_code == 204


# ── Access token still works after logout ─────────────────────────────────────


async def test_access_token_valid_after_logout(client: AsyncClient):
    """
    Logging out invalidates the refresh token but not the in-flight access token.
    Access tokens are short-lived JWTs — no server-side revocation in M1.
    This is by design; revisit if a blocklist is needed later.
    """
    tokens = await register(client, "afterlogout@example.com", "password123")
    await client.post("/auth/logout", json={"refresh_token": tokens["refresh_token"]})

    resp = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert resp.status_code == 200


# ── Service-layer unit tests ──────────────────────────────────────────────────


async def test_hash_and_verify_password():
    hashed = auth_service.hash_password("mysecret")
    assert auth_service.verify_password("mysecret", hashed)
    assert not auth_service.verify_password("wrong", hashed)


async def test_create_and_decode_access_token(db: AsyncSession):
    import uuid

    user_id = uuid.uuid4()
    token = auth_service.create_access_token(user_id, "test@example.com")
    payload = auth_service.decode_access_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["email"] == "test@example.com"
    assert payload["type"] == "access"


# ── UserType / profile tests (TRA-52) ─────────────────────────────────────────


async def test_default_registration_is_club_type(client: AsyncClient):
    data = await register(client, "club@example.com", "password123")
    resp = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {data['access_token']}"}
    )
    assert resp.json()["user_type"] == "CLUB"


async def test_register_as_agent(client: AsyncClient):
    resp = await client.post("/auth/register", json={
        "email": "agent@example.com",
        "password": "password123",
        "user_type": "AGENT",
        "display_name": "John Agent",
        "agency_name": "Top Agency",
        "country": "England",
    })
    assert resp.status_code == 201, resp.text
    tokens = resp.json()
    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert me.json()["user_type"] == "AGENT"


async def test_agent_registration_missing_required_fields(client: AsyncClient):
    resp = await client.post("/auth/register", json={
        "email": "agent2@example.com",
        "password": "password123",
        "user_type": "AGENT",
    })
    assert resp.status_code == 422


async def test_register_as_player(client: AsyncClient, db: AsyncSession):
    from app.players.models import Player
    import uuid

    player = Player(name="Test Player", position="FWD")
    db.add(player)
    await db.commit()

    resp = await client.post("/auth/register", json={
        "email": "player@example.com",
        "password": "password123",
        "user_type": "PLAYER",
        "player_id": str(player.id),
    })
    assert resp.status_code == 201, resp.text
    tokens = resp.json()
    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert me.json()["user_type"] == "PLAYER"


async def test_player_registration_missing_player_id(client: AsyncClient):
    resp = await client.post("/auth/register", json={
        "email": "player2@example.com",
        "password": "password123",
        "user_type": "PLAYER",
    })
    assert resp.status_code == 422


async def test_player_profile_uniqueness(client: AsyncClient, db: AsyncSession):
    """Two users cannot claim the same player record."""
    from app.players.models import Player
    import uuid

    player = Player(name="Claimed Player", position="MID")
    db.add(player)
    await db.commit()

    await client.post("/auth/register", json={
        "email": "first@example.com",
        "password": "password123",
        "user_type": "PLAYER",
        "player_id": str(player.id),
    })
    resp = await client.post("/auth/register", json={
        "email": "second@example.com",
        "password": "password123",
        "user_type": "PLAYER",
        "player_id": str(player.id),
    })
    assert resp.status_code == 409


async def test_club_registration_still_creates_club(client: AsyncClient):
    """Regression: existing CLUB registration behaviour is unchanged."""
    resp = await client.post("/auth/register", json={
        "email": "newclub@example.com",
        "password": "password123",
        "user_type": "CLUB",
        "club_name": "New Club FC",
    })
    assert resp.status_code == 201
    tokens = resp.json()
    club_resp = await client.get(
        "/clubs/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert club_resp.status_code == 200
    assert club_resp.json()["name"] == "New Club FC"


async def test_agent_registration_does_not_create_club(client: AsyncClient):
    resp = await client.post("/auth/register", json={
        "email": "agent3@example.com",
        "password": "password123",
        "user_type": "AGENT",
        "display_name": "Jane Agent",
        "agency_name": "Agency B",
        "country": "Spain",
    })
    tokens = resp.json()
    club_resp = await client.get(
        "/clubs/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert club_resp.status_code == 404
