"""GDPR (Phase 1): download your data, and close your account, keeping the
records others rely on."""
import json

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.audit.models import AuditEvent
from app.auth.models import User
from app.clubs.models import ClubStaff
from tests.conftest import _auth_headers, _register
from tests.test_team_management import _invite, _token_from

pytestmark = pytest.mark.asyncio


async def _staff_member(client):
    owner = await _register(client, "gdpr_owner@test.com", club_name="GDPR FC")
    data = await _invite(client, owner, "gdpr_scout@test.com", "SCOUT")
    scout = (await client.post(f"/auth/invitations/{_token_from(data['accept_url'])}/accept",
                               json={"password": "newpass123", "first_name": "Sam", "last_name": "Scout"})).json()
    return owner, scout


async def test_download_your_data(client: AsyncClient, db):
    _owner, scout = await _staff_member(client)
    resp = await client.get("/auth/me/export", headers=_auth_headers(scout))
    assert resp.status_code == 200
    assert "attachment" in resp.headers["content-disposition"]
    data = json.loads(resp.content)
    assert data["account"]["email"] == "gdpr_scout@test.com" and data["account"]["first_name"] == "Sam"
    assert data["club"] == {"name": "GDPR FC", "role": "SCOUT"}
    assert any(e["action"] == "STAFF_JOINED" for e in data["your_activity"])
    assert data["signed_in_devices"]
    assert (await db.execute(select(AuditEvent).where(AuditEvent.action == "DATA_EXPORTED"))).scalars().first()


async def test_closing_an_account_erases_details_and_keeps_the_audit_trail(client: AsyncClient, db):
    owner, scout = await _staff_member(client)
    h = _auth_headers(scout)
    me = (await client.get("/auth/me", headers=h)).json()

    assert (await client.post("/auth/me/close", json={"password": "newpass123", "confirm": "nope"}, headers=h)).status_code == 422
    assert (await client.post("/auth/me/close", json={"password": "wrong", "confirm": "DELETE"}, headers=h)).status_code == 403
    assert (await client.post("/auth/me/close", json={"password": "newpass123", "confirm": "DELETE"}, headers=h)).status_code == 204

    user = await db.get(User, __import__("uuid").UUID(me["id"]))
    await db.refresh(user)
    assert user.deleted_at is not None and not user.is_active
    assert user.email.endswith("@closed.invalid") and user.first_name is None
    assert (await db.execute(select(ClubStaff).where(ClubStaff.user_id == user.id))).first() is None
    # The audit trail keeps what they did, without their details.
    actions = (await db.execute(select(AuditEvent.action).where(AuditEvent.actor_user_id == user.id))).scalars().all()
    assert "STAFF_JOINED" in actions and "ACCOUNT_CLOSED" in actions
    # Signed out, and can't sign back in.
    assert (await client.get("/auth/me", headers=h)).status_code == 401
    assert (await client.post("/auth/login", json={"email": "gdpr_scout@test.com", "password": "newpass123"})).status_code == 401
    team = (await client.get("/clubs/me/staff", headers=_auth_headers(owner))).json()
    assert team["staff"] == []


async def test_a_club_owner_is_told_to_contact_transferx(client: AsyncClient):
    owner = await _register(client, "gdpr_owner2@test.com", club_name="Owned FC")
    h = _auth_headers(owner)
    check = (await client.get("/auth/me/close-check", headers=h)).json()
    assert check["can_close"] is False and "own your club" in check["reason"]
    resp = await client.post("/auth/me/close", json={"password": "password123", "confirm": "DELETE"}, headers=h)
    assert resp.status_code == 409
    assert (await client.get("/auth/me", headers=h)).status_code == 200
