"""The notifications page's filters: unread, tier, category, player, club and
a search over player, club and wording; "Mark these read" marks only what
they show. New offer and deal notifications record the other club, never an
anonymous buyer."""
import pytest
from httpx import AsyncClient

from tests.conftest import _auth_headers
from tests.test_ai_assist import _offer, buyer, outsider, seller  # noqa: F401 (fixtures)

pytestmark = pytest.mark.asyncio


async def _list(client, who, **params):
    r = await client.get("/notifications", headers=_auth_headers(who), params=params)
    assert r.status_code == 200, r.text
    return r.json()


async def test_the_filters(client: AsyncClient, buyer, seller, outsider, db):  # noqa: F811
    named = await _offer(client, buyer, seller, db)  # from Hidden Buyer FC, named
    other = await client.post("/offers", headers=_auth_headers(outsider), json={
        "player_id": named["player_id"], "to_club_id": named["to_club_id"], "fee_amount": 6_000_000,
        "wage_weekly": 20000, "contract_years": 3})
    assert other.status_code == 201, other.text

    everything = await _list(client, seller)
    received = [n for n in everything["items"] if n["type"] == "OFFER_RECEIVED"]
    assert len(received) == 2
    # The other club is recorded on new offer notifications.
    assert {n["club"]["name"] for n in received} == {"Hidden Buyer FC", "Nosy Neighbours FC"}

    found = await _list(client, seller, q="nosy")
    assert [n["club"]["name"] for n in found["items"]] == ["Nosy Neighbours FC"]
    assert (await _list(client, seller, q="deal player"))["total"] >= 2  # the player's name
    assert (await _list(client, seller, player_id=named["player_id"]))["total"] >= 2
    nosy_id = received[0]["club"]["id"] if received[0]["club"]["name"] == "Nosy Neighbours FC" else received[1]["club"]["id"]
    assert (await _list(client, seller, club_id=nosy_id))["total"] == 1

    assert all(n["tier"] == "YOUR_MOVE" for n in (await _list(client, seller, tier="YOUR_MOVE"))["items"])
    assert (await _list(client, seller, tier="YOUR_MOVE"))["total"] >= 2
    assert (await _list(client, seller, category="deals"))["total"] == 0
    assert (await _list(client, seller, category="offers"))["total"] >= 2
    r = await client.get("/notifications", headers=_auth_headers(seller), params={"tier": "SOON"})
    assert r.status_code == 422

    # "Mark these read": only the filtered ones.
    unread_before = (await _list(client, seller, unread=True))["total"]
    r = await client.post("/notifications/read-all", headers=_auth_headers(seller), params={"club_id": nosy_id})
    assert r.status_code == 200 and r.json()["count"] == unread_before - 1, r.text
    assert (await _list(client, seller, unread=True, club_id=nosy_id))["total"] == 0
    assert (await _list(client, seller, unread=True))["total"] == unread_before - 1


async def test_an_anonymous_buyer_is_never_recorded_or_found(client: AsyncClient, buyer, seller, db):  # noqa: F811
    await _offer(client, buyer, seller, db, anonymous=True)
    received = next(n for n in (await _list(client, seller))["items"] if n["type"] == "OFFER_RECEIVED")
    assert received["club"] is None and received["related_club_id"] is None
    assert (await _list(client, seller, q="hidden buyer"))["total"] == 0


def test_search_ignores_accents():
    """Football names carry accents: "estev" finds Estêvão, "odeg" Ødegaard.
    On Postgres the column side is folded with translate() to the same letters."""
    from app.notifications.service import _ACCENTED, _PLAIN, _fold

    assert [_fold(n) for n in ("Estêvão", "Ødegaard", "Mbappé", "Bayındır", "Miściur")] == [
        "estevao", "odegaard", "mbappe", "bayindir", "misciur"]
    assert len(_ACCENTED) == len(_PLAIN) and _PLAIN.isascii()
