"""A confirmed deal waiting to complete (status PENDING_COMPLETION) still
holds the player: no listing, offer or second deal. And when a closed window
holds completion, it's nobody's move, and the board says why."""
import pytest
from httpx import AsyncClient

from tests.conftest import _auth_headers
from tests.test_deals import _create_deal_via_offer, _set_deal, buyer, rival, seller  # noqa: F401
from tests.test_transfer_windows import _window

pytestmark = pytest.mark.asyncio


async def _confirmed(client, buyer, seller, db) -> dict:
    from app.deals.models import DealStage, DealStatus

    deal = await _create_deal_via_offer(client, buyer, seller, db)
    await _set_deal(db, deal["id"], stage=DealStage.CONFIRMED, status=DealStatus.PENDING_COMPLETION)
    return deal


async def test_a_confirmed_deal_still_holds_the_player(client: AsyncClient, buyer, seller, rival, db):
    deal = await _confirmed(client, buyer, seller, db)
    pid = deal["player_id"]

    player = (await client.get(f"/players/market/{pid}", headers=_auth_headers(seller))).json()
    assert player["active_deal"]["id"] == deal["id"]

    r = await client.post("/sales", headers=_auth_headers(seller), json={
        "player_id": pid, "sale_type": "OPEN_TO_OFFERS", "asking_price": 9_000_000})
    assert r.status_code == 409, r.text
    seller_club = (await client.get("/clubs/me", headers=_auth_headers(seller))).json()["id"]
    r = await client.post("/offers", headers=_auth_headers(rival), json={
        "player_id": pid, "to_club_id": seller_club, "fee_amount": 9_000_000})
    assert r.status_code == 409, r.text


async def test_completion_held_by_a_closed_window_is_nobodys_move(client: AsyncClient, buyer, seller, db):
    deal = await _confirmed(client, buyer, seller, db)
    await _window(db, opens_in_days=40)  # every club's window: closed now, opens in 40 days

    for h in (_auth_headers(buyer), _auth_headers(seller)):
        assert (await client.get(f"/deals/{deal['id']}", headers=h)).json()["whose_move"] == "neither"
        card = next(c for col in (await client.get("/board", headers=h)).json()["columns"]
                    for c in col["cards"] if c["entity_id"] == deal["id"])
        assert (card["whose_move"], card["detail"]) == ("neither", "Completes when the window opens")
        dash = (await client.get("/clubs/me/dashboard", headers=h)).json()["waiting_on_you"]
        assert not [i for i in dash if i["kind"] == "deal" and i["id"] == deal["id"]]


async def test_a_confirmed_deal_that_can_complete_is_ready_to_complete(client: AsyncClient, buyer, seller, db):
    deal = await _confirmed(client, buyer, seller, db)  # no window set up: nothing holds it
    card = next(c for col in (await client.get("/board", headers=_auth_headers(buyer))).json()["columns"]
                for c in col["cards"] if c["entity_id"] == deal["id"])
    assert (card["whose_move"], card["detail"]) == ("your", "Ready to complete · your move")
