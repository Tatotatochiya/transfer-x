"""Notifications carry the player and club they're about, for links and
pictures, and never name an anonymous buyer."""

import pytest
from httpx import AsyncClient

from tests.conftest import _auth_headers
from tests.test_ai_assist import _offer, buyer, seller  # noqa: F401 (fixtures)


async def _latest(client, club, type_):
    items = (await client.get("/notifications", headers=_auth_headers(club))).json()["items"]
    return next(n for n in items if n["type"] == type_)


@pytest.mark.asyncio
async def test_offer_notifications_name_player_and_club_but_not_an_anonymous_buyer(client: AsyncClient, buyer, seller, db):  # noqa: F811
    offer = await _offer(client, buyer, seller, db, anonymous=True)

    received = await _latest(client, seller, "OFFER_RECEIVED")
    assert received["player"]["name"] == "Deal Player" and received["player"]["id"] == offer["player_id"]
    assert received["club"] is None and received["related_club_id"] is None  # the buyer is anonymous

    resp = await client.post(f"/offers/{offer['id']}/counter", json={"fee_amount": 6_000_000}, headers=_auth_headers(seller))
    assert resp.status_code == 200, resp.text
    countered = await _latest(client, buyer, "OFFER_COUNTERED")
    assert countered["club"]["name"] == "Selling Side FC"  # the seller is never hidden
    assert countered["player"]["name"] == "Deal Player"
