"""Deadline-day mode (app/deadline/service.py): open transfers against the
window's close, what each waits on, which are at risk, and the reminders."""
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from tests.conftest import _auth_headers, _register
from tests.test_deals import _get_club_id, _give_budget

pytestmark = pytest.mark.asyncio


async def _window(db, hours_left: float):
    from app.transfer_window.models import TransferWindow

    now = datetime.now(timezone.utc)
    w = TransferWindow(name="Summer", opens_at=now - timedelta(days=60), closes_at=now + timedelta(hours=hours_left))
    db.add(w)
    await db.commit()
    return w


async def _player(client, headers, name):
    resp = await client.post("/players", json={"name": name, "position": "MID"}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _setup(client, db, *, anonymous=False):
    """A seller with two players: one with an offer waiting on the seller,
    one already a deal at the fee-agreed stage."""
    seller_t = await _register(client, "dd_seller@clubs-example.com", club_name="Deadline Sellers")
    buyer_t = await _register(client, "dd_buyer@clubs-example.com", club_name="Deadline Buyers")
    seller, buyer = _auth_headers(seller_t), _auth_headers(buyer_t)
    await _give_budget(db)
    to_club = await _get_club_id(client, seller)
    waiting = await _player(client, seller, "Waiting Wes")
    offer = (await client.post("/offers", json={"player_id": waiting["id"], "to_club_id": to_club,
                                                "fee_amount": 4_000_000, "is_anonymous": anonymous}, headers=buyer)).json()
    agreed = await _player(client, seller, "Agreed Al")
    other = (await client.post("/offers", json={"player_id": agreed["id"], "to_club_id": to_club,
                                                "fee_amount": 6_000_000}, headers=buyer)).json()
    assert (await client.post(f"/offers/{other['id']}/accept", headers=seller)).status_code == 200
    return seller, buyer, offer


async def test_open_transfers_with_whose_move_and_whats_left(client: AsyncClient, db):
    await _window(db, hours_left=10)
    seller, buyer, offer = await _setup(client, db)

    view = (await client.get("/deadline", headers=seller)).json()
    assert view["window"]["state"] == "open" and view["window"]["deadline_mode"] is True
    assert 9.5 < view["window"]["hours_left"] <= 10
    by_name = {i["player_name"]: i for i in view["items"]}
    assert set(by_name) == {"Waiting Wes", "Agreed Al"}
    wes = by_name["Waiting Wes"]
    assert (wes["kind"], wes["needs_you"], wes["next_step"]["label"]) == ("offer", True, "Answer the offer")
    assert wes["steps_left"] == 4 and wes["at_risk"] is True  # 10 hours < 4 steps x 6 hours
    al = by_name["Agreed Al"]
    assert al["kind"] == "deal" and al["stage"] == "Fee agreed" and al["next_step"]["owner"] == "either"
    # What needs the club comes first.
    assert view["items"][0]["needs_you"] is True
    assert view["counts"]["open"] == 2

    # The buyer sees the same transfers from its side: the offer waits on the seller.
    theirs = {i["player_name"]: i for i in (await client.get("/deadline", headers=buyer)).json()["items"]}
    assert theirs["Waiting Wes"]["needs_you"] is False
    assert theirs["Waiting Wes"]["next_step"]["label"] == "Waiting for Deadline Sellers to answer"


async def test_not_deadline_mode_with_time_to_spare_and_no_window(client: AsyncClient, db):
    seller, _buyer, _offer = await _setup(client, db)
    view = (await client.get("/deadline", headers=seller)).json()
    assert view["window"]["state"] == "none" and view["window"]["deadline_mode"] is False
    assert all(i["at_risk"] is False for i in view["items"])  # no close, nothing at risk

    await _window(db, hours_left=24 * 10)
    view = (await client.get("/deadline", headers=seller)).json()
    assert view["window"]["deadline_mode"] is False and view["counts"]["at_risk"] == 0


async def test_an_anonymous_buyer_stays_masked(client: AsyncClient, db):
    await _window(db, hours_left=10)
    seller, _buyer, _offer = await _setup(client, db, anonymous=True)
    view = (await client.get("/deadline", headers=seller)).json()
    assert "Deadline Buyers" not in str([i for i in view["items"] if i["player_name"] == "Waiting Wes"])


async def test_reminders_go_once_per_threshold(client: AsyncClient, db):
    from app.deadline.service import send_reminders
    from app.notifications.models import Notification, NotificationType

    w = await _window(db, hours_left=5)
    await _setup(client, db)
    now = datetime.now(timezone.utc)

    async def sent():
        return (await db.execute(select(Notification).where(Notification.type == NotificationType.DEADLINE_DAY))).scalars().all()

    assert await send_reminders(db, now) == 2  # both clubs have transfers open
    await db.commit()
    first = await sent()
    assert first and all(n.group_key == f"deadline:{w.id}:6" for n in first)
    assert any("waiting on you" in n.message and "1 waiting" in n.message for n in first)

    await send_reminders(db, now + timedelta(minutes=15))  # the job runs again: nobody is told twice
    await db.commit()
    assert len(await sent()) == len(first)

    await send_reminders(db, now + timedelta(hours=3, minutes=30))  # inside 2 hours: the next reminder
    await db.commit()
    assert {n.group_key for n in await sent()} == {f"deadline:{w.id}:6", f"deadline:{w.id}:2"}


async def test_no_reminders_outside_the_last_day_or_for_a_club_with_nothing_open(client: AsyncClient, db):
    from app.deadline.service import send_reminders

    await _window(db, hours_left=30)
    await _setup(client, db)
    assert await send_reminders(db) == 0
    await _register(client, "dd_quiet@clubs-example.com", club_name="Quiet FC")
    assert await send_reminders(db, datetime.now(timezone.utc) + timedelta(hours=8)) == 2  # not Quiet FC


async def test_members_only(client: AsyncClient):
    assert (await client.get("/deadline")).status_code == 401
    agent = (await client.post("/auth/register", json={
        "email": "agent_dd@clubs-example.com", "password": "password123", "user_type": "AGENT",
        "display_name": "DD Agent", "agency_name": "DD Sports", "country": "England",
    })).json()
    assert (await client.get("/deadline", headers=_auth_headers(agent))).status_code == 403
