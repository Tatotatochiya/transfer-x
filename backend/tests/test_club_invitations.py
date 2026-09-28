"""Clubs join by invitation: staff invite an owner, who accepts once."""

from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from app.config import settings
from tests.conftest import _auth_headers, _register


@pytest_asyncio.fixture
async def staff(client: AsyncClient, db) -> dict:
    from app.auth.models import User

    tokens = await _register(client, "staff_inv@test.com", club_name="TransferX Staff")
    user = (await db.execute(select(User).where(User.email == "staff_inv@test.com"))).scalar_one()
    user.is_superuser = True
    await db.commit()
    return tokens


async def _invite(client, staff, email="owner@newclub.com", club_name="New Club FC"):
    return await client.post(
        "/admin/club-invitations", json={"email": email, "club_name": club_name}, headers=_auth_headers(staff)
    )


def _token(invitation: dict) -> str:
    return invitation["accept_url"].split("token=")[1]


@pytest.mark.asyncio
async def test_invite_preview_accept_once(client, staff):
    resp = await _invite(client, staff)
    assert resp.status_code == 201, resp.text
    token = _token(resp.json())

    preview = await client.get(f"/auth/club-invitations/{token}")
    assert preview.status_code == 200
    assert preview.json()["club_name"] == "New Club FC"
    assert preview.json()["email"] == "owner@newclub.com"

    accepted = await client.post(f"/auth/club-invitations/{token}/accept", json={"password": "password123"})
    assert accepted.status_code == 201, accepted.text
    me = await client.get("/clubs/me", headers=_auth_headers(accepted.json()))
    assert me.status_code == 200
    assert me.json()["name"] == "New Club FC"
    assert me.json()["finance"] is not None

    # Single use: the link is dead once accepted.
    again = await client.post(f"/auth/club-invitations/{token}/accept", json={"password": "password123"})
    assert again.status_code == 409
    assert (await client.get(f"/auth/club-invitations/{token}")).status_code == 404


@pytest.mark.asyncio
async def test_token_is_stored_hashed(client, staff, db):
    from app.clubs.models import ClubInvitation

    token = _token((await _invite(client, staff)).json())
    row = (await db.execute(select(ClubInvitation))).scalar_one()
    assert row.token_hash != token
    assert token not in str(row.__dict__)


@pytest.mark.asyncio
async def test_revoked_invitation_cannot_be_used(client, staff):
    inv = (await _invite(client, staff)).json()
    resp = await client.post(f"/admin/club-invitations/{inv['id']}/revoke", headers=_auth_headers(staff))
    assert resp.status_code == 200, resp.text
    token = _token(inv)
    assert (await client.get(f"/auth/club-invitations/{token}")).status_code == 404
    accept = await client.post(f"/auth/club-invitations/{token}/accept", json={"password": "password123"})
    assert accept.status_code == 409


@pytest.mark.asyncio
async def test_expired_invitation_cannot_be_used(client, staff, db):
    from app.clubs.models import ClubInvitation

    token = _token((await _invite(client, staff)).json())
    row = (await db.execute(select(ClubInvitation))).scalar_one()
    row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    await db.commit()
    assert (await client.get(f"/auth/club-invitations/{token}")).status_code == 404
    accept = await client.post(f"/auth/club-invitations/{token}/accept", json={"password": "password123"})
    assert accept.status_code == 409


@pytest.mark.asyncio
async def test_refuses_existing_account_existing_club_and_duplicates(client, staff):
    await _register(client, "taken@test.com", club_name="Taken FC")
    assert (await _invite(client, staff, email="taken@test.com", club_name="Other FC")).status_code == 400
    assert (await _invite(client, staff, email="fresh@test.com", club_name="Taken FC")).status_code == 400
    assert (await _invite(client, staff, email="twice@test.com", club_name="Twice FC")).status_code == 201
    assert (await _invite(client, staff, email="twice@test.com", club_name="Twice FC 2")).status_code == 400


@pytest.mark.asyncio
async def test_only_staff_can_invite(client):
    club = await _register(client, "plain@test.com", club_name="Plain FC")
    resp = await client.post(
        "/admin/club-invitations", json={"email": "x@test.com", "club_name": "X FC"}, headers=_auth_headers(club)
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_club_self_registration_is_refused(client):
    settings.allow_club_self_registration = False
    try:
        resp = await client.post(
            "/auth/register", json={"email": "self@test.com", "password": "password123", "club_name": "Self FC"}
        )
        assert resp.status_code == 403
    finally:
        settings.allow_club_self_registration = True


@pytest.mark.asyncio
async def test_short_password_refused(client, staff):
    token = _token((await _invite(client, staff)).json())
    resp = await client.post(f"/auth/club-invitations/{token}/accept", json={"password": "short"})
    assert resp.status_code == 422
