"""People's names (Phase 1): set when joining or in settings, shown to the
club's own team, in approvals and in the admin audit log."""
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.audit.models import AuditEvent
from app.notifications.models import Notification
from tests.conftest import _auth_headers, _register
from tests.test_team_management import _invite, _token_from

pytestmark = pytest.mark.asyncio


async def test_set_your_name_in_settings(client: AsyncClient):
    tokens = await _register(client, "names_owner@test.com", club_name="Names FC")
    headers = _auth_headers(tokens)
    me = (await client.get("/auth/me", headers=headers)).json()
    assert me["full_name"] is None

    blank = await client.patch("/auth/me", json={"first_name": "  ", "last_name": "Smith"}, headers=headers)
    assert blank.status_code == 422
    resp = await client.patch("/auth/me", json={"first_name": " Ana ", "last_name": "Smith"}, headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["first_name"] == "Ana" and resp.json()["full_name"] == "Ana Smith"


async def test_a_new_team_member_is_named_everywhere_their_club_sees(client: AsyncClient, db):
    owner = await _register(client, "names_owner2@test.com", club_name="Named FC")
    data = await _invite(client, owner, "named_scout@test.com", "SCOUT")
    resp = await client.post(f"/auth/invitations/{_token_from(data['accept_url'])}/accept",
                             json={"password": "newpass123", "first_name": "Jo", "last_name": "Bloggs"})
    assert resp.status_code == 201, resp.text

    team = (await client.get("/clubs/me/staff", headers=_auth_headers(owner))).json()
    member = next(m for m in team["staff"] if m["email"] == "named_scout@test.com")
    assert member["name"] == "Jo Bloggs"
    joined = (await db.execute(select(AuditEvent).where(AuditEvent.action == "STAFF_JOINED"))).scalars().one()
    assert joined.description == "Jo Bloggs joined as SCOUT"
    told = (await db.execute(select(Notification.message))).scalars().all()
    assert any(m.startswith("Jo Bloggs accepted your invitation") for m in told)
