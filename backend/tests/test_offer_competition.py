"""A buyer is told when another club's offer changes their place among the
offers for a player: the first rival appears, or they lose the lead. Never
who, never how much."""
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from tests.conftest import _auth_headers, _register
from tests.test_offers import _create_player, _give_budget, _get_seller_club_id

pytestmark = pytest.mark.asyncio


async def _notes(db, email: str) -> list:
    from app.auth.models import User
    from app.notifications.models import Notification, NotificationType

    db.expire_all()  # see what the requests committed
    user_id = (await db.execute(select(User.id).where(User.email == email))).scalar_one()
    return list((await db.execute(select(Notification).where(
        Notification.recipient_user_id == user_id, Notification.type == NotificationType.OFFER_COMPETITION,
    ).order_by(Notification.created_at))).scalars())


async def _offer(client, headers, player_id, seller_id, fee) -> dict:
    r = await client.post("/offers", json={"player_id": player_id, "to_club_id": seller_id, "fee_amount": fee}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture
async def market(client: AsyncClient, db):
    seller = await _register(client, "comp_seller@test.com", club_name="Seller FC")
    a = await _register(client, "comp_a@test.com", club_name="Alpha FC")
    b = await _register(client, "comp_b@test.com", club_name="Bravo FC")
    c = await _register(client, "comp_c@test.com", club_name="Charlie FC")
    await _give_budget(db)
    player = await _create_player(client, _auth_headers(seller), name="Mo Rival")
    return {"seller": seller, "a": a, "b": b, "c": c, "player": player["id"],
            "seller_id": await _get_seller_club_id(client, _auth_headers(seller))}


async def test_the_first_rival_tells_the_buyer_without_naming_them(client: AsyncClient, db, market):
    m = market
    mine = await _offer(client, _auth_headers(m["a"]), m["player"], m["seller_id"], 10_000_000)
    await _offer(client, _auth_headers(m["b"]), m["player"], m["seller_id"], 12_000_000)

    [note] = await _notes(db, "comp_a@test.com")
    assert note.title == "Another club has made an offer for Mo Rival"
    assert note.body == "Yours is now 2nd of 2."
    assert note.link == f"/offers/{mine['id']}?tab=bids"
    assert str(note.related_club_id) == m["seller_id"], "the club they're dealing with, not the rival"
    text = f"{note.title} {note.body} {note.message}"
    assert "Bravo" not in text and "12" not in text
    # The newcomer and the seller get nothing of this kind.
    assert await _notes(db, "comp_b@test.com") == []
    assert await _notes(db, "comp_seller@test.com") == []


async def test_a_still_leading_buyer_hears_of_the_first_rival(client: AsyncClient, db, market):
    m = market
    await _offer(client, _auth_headers(m["a"]), m["player"], m["seller_id"], 20_000_000)
    await _offer(client, _auth_headers(m["b"]), m["player"], m["seller_id"], 12_000_000)
    [note] = await _notes(db, "comp_a@test.com")
    assert note.body == "Yours is now the leading offer."


async def test_losing_the_lead_is_told_and_slipping_further_back_is_not(client: AsyncClient, db, market):
    m = market
    await _offer(client, _auth_headers(m["a"]), m["player"], m["seller_id"], 10_000_000)
    await _offer(client, _auth_headers(m["b"]), m["player"], m["seller_id"], 12_000_000)
    await _offer(client, _auth_headers(m["c"]), m["player"], m["seller_id"], 15_000_000)

    b_notes = await _notes(db, "comp_b@test.com")
    assert [n.title for n in b_notes] == ["Your offer for Mo Rival is no longer the leading one"]
    assert b_notes[0].body == "Yours is now 2nd of 3."
    # A went from 2nd of 2 to 3rd of 3: no news worth a notification.
    assert len(await _notes(db, "comp_a@test.com")) == 1


async def test_a_buyer_raising_past_the_leader_tells_the_leader(client: AsyncClient, db, market):
    m = market
    mine = await _offer(client, _auth_headers(m["a"]), m["player"], m["seller_id"], 10_000_000)
    await _offer(client, _auth_headers(m["b"]), m["player"], m["seller_id"], 12_000_000)
    r = await client.post(f"/offers/{mine['id']}/improve", json={"fee_amount": 14_000_000}, headers=_auth_headers(m["a"]))
    assert r.status_code == 200, r.text
    assert [n.body for n in await _notes(db, "comp_b@test.com")] == ["Yours is now 2nd of 2."]


async def test_a_sellers_counter_is_not_a_bid(client: AsyncClient, db, market):
    m = market
    mine = await _offer(client, _auth_headers(m["a"]), m["player"], m["seller_id"], 10_000_000)
    await _offer(client, _auth_headers(m["b"]), m["player"], m["seller_id"], 12_000_000)
    # The seller asks A for more than B offered: B hasn't been outbid.
    r = await client.post(f"/offers/{mine['id']}/counter", json={"fee_amount": 18_000_000}, headers=_auth_headers(m["seller"]))
    assert r.status_code == 200, r.text
    assert await _notes(db, "comp_b@test.com") == []
