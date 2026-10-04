"""Lite L7, team contact: "Ask Sam" reaches the chosen colleague, else the
first sporting director or manager, else everyone who can act."""
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.notifications.models import Notification, NotificationType
from tests.conftest import _auth_headers, _register
from tests.test_deals import _create_player_for_seller
from tests.test_team_management import _invite, _token_from

pytestmark = pytest.mark.asyncio


async def _join(client, owner, email, role, first):
    data = await _invite(client, owner, email, role)
    tokens = (await client.post(f"/auth/invitations/{_token_from(data['accept_url'])}/accept",
                                json={"password": "newpass123", "first_name": first, "last_name": "Test"})).json()
    return tokens


async def _questions(db, user_email):
    from app.auth.models import User

    uid = (await db.execute(select(User.id).where(User.email == user_email))).scalar_one()
    return (await db.execute(select(Notification).where(
        Notification.recipient_user_id == uid, Notification.type == NotificationType.LITE_QUESTION))).scalars().all()


async def test_ask_goes_to_the_named_contact_or_the_first_director(client: AsyncClient, db):
    owner = await _register(client, "team_owner_l7@test.com", club_name="Ask FC")
    oh = _auth_headers(owner)
    # Nobody else yet: "your team", and asking says there's nobody.
    assert (await client.get("/lite/team-contact", headers=oh)).json() == {"name": None, "label": "your team"}
    assert (await client.post("/lite/ask-team", json={"text": "Anyone?"}, headers=oh)).status_code == 422

    await _join(client, owner, "l7_manager@test.com", "MANAGER", "Mia")
    await _join(client, owner, "l7_scout@test.com", "SCOUT", "Sam")
    assert (await client.get("/lite/team-contact", headers=oh)).json()["label"] == "Mia"  # the fallback

    team = (await client.get("/clubs/me/staff", headers=oh)).json()["staff"]
    sam = next(m for m in team if m["email"] == "l7_scout@test.com")
    resp = await client.put(f"/clubs/me/staff/{sam['id']}/lite-contact", json={"on": True}, headers=oh)
    assert resp.status_code == 200 and resp.json()["is_lite_contact"]
    assert (await client.get("/lite/team-contact", headers=oh)).json()["label"] == "Sam"

    player = await _create_player_for_seller(client, oh)
    resp = await client.post("/lite/ask-team", json={"subject_type": "player", "subject_id": player["id"],
                                                     "text": "Is he worth £8m?"}, headers=oh)
    assert resp.status_code == 200 and resp.json()["sent_to"] == "Sam"
    (q,) = await _questions(db, "l7_scout@test.com")
    assert q.message.endswith("asks: Is he worth £8m?") and q.link == f"/players/market/{player['id']}"
    assert await _questions(db, "l7_manager@test.com") == []


async def test_without_a_director_it_goes_to_everyone_who_can_act(client: AsyncClient, db):
    owner = await _register(client, "team_owner_l7b@test.com", club_name="Everyone FC")
    scout = await _join(client, owner, "l7b_scout@test.com", "SCOUT", "Sid")
    # The scout asks: no contact, no director or manager, so the owner (who can act) gets it.
    resp = await client.post("/lite/ask-team", json={"text": "Shall I scout him?"}, headers=_auth_headers(scout))
    assert resp.status_code == 200 and resp.json() == {"sent_to": "your team", "recipients": 1}
    assert len(await _questions(db, "team_owner_l7b@test.com")) == 1
    # An offer the club isn't party to is refused.
    import uuid

    resp = await client.post("/lite/ask-team", json={"subject_type": "offer", "subject_id": str(uuid.uuid4()),
                                                     "text": "?"}, headers=_auth_headers(scout))
    assert resp.status_code == 404
