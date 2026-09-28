"""An anonymous buyer is shown only as "A {domestic league} club" — never by
name, and never by a European competition, which would narrow the field."""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from tests.conftest import _auth_headers, _register
from tests.test_deals import _create_player_for_seller, _get_club_id, _give_budget


@pytest_asyncio.fixture
async def buyer(client: AsyncClient) -> dict:
    return await _register(client, "buyer_anon@test.com", club_name="Secret Buyers FC")


@pytest_asyncio.fixture
async def seller(client: AsyncClient) -> dict:
    return await _register(client, "seller_anon@test.com", club_name="Open Sellers FC")


async def _set_league(db, club_name: str, league: str | None):
    from app.clubs.models import Club

    club = (await db.execute(select(Club).where(Club.name == club_name))).scalar_one()
    club.league_name = league
    await db.commit()


async def _anonymous_offer(client, buyer, seller, db) -> dict:
    await _give_budget(db)
    player = await _create_player_for_seller(client, _auth_headers(seller))
    resp = await client.post(
        "/offers",
        json={"player_id": player["id"], "to_club_id": await _get_club_id(client, _auth_headers(seller)),
              "fee_amount": 5_000_000, "is_anonymous": True},
        headers=_auth_headers(buyer),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.mark.parametrize(
    "league, expected",
    [
        ("Premier League", "Premier League"),
        ("UEFA Champions League", None),
        ("UEFA Europa League", None),
        ("FA Cup", None),
        ("", None),
        (None, None),
    ],
)
def test_masking_league_shows_only_a_domestic_league(league, expected):
    from app.clubs.models import Club

    assert Club(name="X", league_name=league).masking_league == expected


@pytest.mark.asyncio
async def test_seller_dashboard_does_not_name_an_anonymous_buyer(client, buyer, seller, db):
    """Regression: the War Room row (and so the digest email and the AI
    briefing, which read it) named the buying club of an anonymous offer."""
    await _set_league(db, "Secret Buyers FC", "Premier League")
    await _anonymous_offer(client, buyer, seller, db)

    items = (await client.get("/clubs/me/dashboard", headers=_auth_headers(seller))).json()["waiting_on_you"]
    offer_items = [i for i in items if i["kind"] == "offer"]
    assert offer_items, items
    assert offer_items[0]["club_name"] == "A Premier League club"
    assert "Secret Buyers" not in str(items)


@pytest.mark.asyncio
async def test_competition_is_not_used_as_the_league(client, buyer, seller, db):
    await _set_league(db, "Secret Buyers FC", "UEFA Champions League")
    offer = await _anonymous_offer(client, buyer, seller, db)

    seen = (await client.get(f"/offers/{offer['id']}", headers=_auth_headers(seller))).json()
    assert seen["from_club"] is None
    assert seen["buyer_league_name"] is None

    book = (await client.get(f"/offers/competition/{offer['player_id']}", headers=_auth_headers(seller))).json()
    names = [e["club"]["name"] for e in book["entries"] if e.get("club")]
    assert names == ["An undisclosed club"]
