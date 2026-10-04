"""The Transfers board (Phase 3, product ADR 0008): each player once, at
its furthest point, from both sides, with anonymous buyers kept hidden."""
import pytest
from httpx import AsyncClient

from tests.conftest import _auth_headers, _register
from tests.test_deals import _create_player_for_seller, _get_club_id, _give_budget

pytestmark = pytest.mark.asyncio


def _cards(board, column=None):
    if column == "closed":
        return board["closed"]
    cols = board["columns"] if column is None else [c for c in board["columns"] if c["key"] == column]
    return [card for c in cols for card in c["cards"]]


async def _board(client, headers, side="BOTH"):
    resp = await client.get("/board", params={"side": side}, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


async def test_a_transfer_moves_across_the_board_for_both_clubs(client: AsyncClient, db):
    seller = _auth_headers(await _register(client, "board_seller@test.com", club_name="Board Sellers"))
    buyer = _auth_headers(await _register(client, "board_buyer@test.com", club_name="Board Buyers"))
    rival = _auth_headers(await _register(client, "board_rival@test.com", club_name="Board Rivals"))
    await _give_budget(db)
    player = await _create_player_for_seller(client, seller)
    resp = await client.post("/sales", json={"player_id": player["id"], "sale_type": "OPEN_TO_OFFERS",
                                             "asking_price": 6_000_000}, headers=seller)
    assert resp.status_code == 201, resp.text

    board = await _board(client, seller)
    (card,) = _cards(board)
    assert card["column"] == "talking" and card["kind"] == "listing" and card["side"] == "SELLING"
    assert [c["key"] for c in board["columns"]] == ["talking", "offers", "fee_agreed", "terms", "paperwork", "done"]

    seller_club = await _get_club_id(client, seller)
    offer = (await client.post("/offers", json={"player_id": player["id"], "to_club_id": seller_club,
                                                "fee_amount": 5_000_000, "is_anonymous": True}, headers=buyer)).json()
    await client.post("/offers", json={"player_id": player["id"], "to_club_id": seller_club,
                                       "fee_amount": 4_000_000}, headers=rival)

    board = await _board(client, seller)
    (card,) = _cards(board)  # one card for the player, not one per offer
    assert card["column"] == "offers" and card["whose_move"] == "your" and card["others"] == 1
    # The anonymous buyer stays hidden from the seller; the named rival may lead the card instead.
    assert "Board Buyers" not in str(board)
    assert board["counts"]["your_move"] == 1

    bboard = await _board(client, buyer)
    (bcard,) = _cards(bboard)
    assert bcard["side"] == "BUYING" and bcard["column"] == "offers" and bcard["whose_move"] == "their"
    assert bcard["counterparty"] == "Board Sellers"

    assert (await client.post(f"/offers/{offer['id']}/accept", headers=seller)).status_code == 200
    (card,) = _cards(await _board(client, seller))
    assert card["column"] == "fee_agreed" and card["kind"] == "deal" and card["counterparty"] == "Board Buyers"
    (bcard,) = _cards(await _board(client, buyer))
    assert bcard["column"] == "fee_agreed"

    # The rival's offer went nowhere: it's in their Closed drawer, not a column.
    rboard = await _board(client, rival)
    assert _cards(rboard) == [] and len(rboard["closed"]) == 1

    # The side filter.
    assert _cards(await _board(client, seller, "BUYING")) == []
    assert len(_cards(await _board(client, seller, "SELLING"))) == 1


async def test_enquiries_sit_in_talking_and_strangers_get_nothing(client: AsyncClient, db):
    seller = _auth_headers(await _register(client, "board_seller2@test.com", club_name="Enquiry Sellers"))
    buyer = _auth_headers(await _register(client, "board_buyer2@test.com", club_name="Enquiry Buyers"))
    player = await _create_player_for_seller(client, seller)
    resp = await client.post("/enquiries", json={"player_id": player["id"], "body": "Would you sell?"}, headers=buyer)
    assert resp.status_code == 201, resp.text

    (card,) = _cards(await _board(client, seller))
    assert card["column"] == "talking" and card["kind"] == "enquiry" and card["whose_move"] == "your"
    (bcard,) = _cards(await _board(client, buyer))
    assert bcard["side"] == "BUYING" and bcard["whose_move"] == "their"

    stranger = _auth_headers(await _register(client, "board_stranger@test.com", club_name="Strangers"))
    assert _cards(await _board(client, stranger)) == []


async def test_history_keeps_everything_that_ended_and_can_be_searched(client: AsyncClient, db):
    seller = _auth_headers(await _register(client, "hist_seller@test.com", club_name="History Sellers"))
    buyer = _auth_headers(await _register(client, "hist_buyer@test.com", club_name="History Buyers"))
    await _give_budget(db)
    player = await _create_player_for_seller(client, seller)
    seller_club = await _get_club_id(client, seller)
    enquiry = (await client.post("/enquiries", json={"player_id": player["id"], "body": "Available?"}, headers=buyer)).json()
    assert (await client.post(f"/enquiries/{enquiry['id']}/close", headers=seller)).status_code == 200
    offer = (await client.post("/offers", json={"player_id": player["id"], "to_club_id": seller_club,
                                                "fee_amount": 3_000_000}, headers=buyer)).json()
    assert (await client.post(f"/offers/{offer['id']}/reject", headers=seller)).status_code == 200

    hist = (await client.get("/board/history", headers=buyer)).json()
    assert hist["total"] == 2
    assert {c["detail"] for c in hist["items"]} == {"Enquiry closed", "Offer rejected"}
    # The active board doesn't show the closed enquiry; history does.
    assert all(c["kind"] != "enquiry" for c in (await client.get("/board", headers=buyer)).json()["closed"])

    assert (await client.get("/board/history", params={"q": "nobody"}, headers=buyer)).json()["total"] == 0
    assert (await client.get("/board/history", params={"q": "history sell"}, headers=buyer)).json()["total"] == 2
    assert (await client.get("/board/history", params={"outcome": "completed"}, headers=buyer)).json()["total"] == 0
    assert (await client.get("/board/history", params={"side": "SELLING"}, headers=buyer)).json()["total"] == 0
    assert (await client.get("/board/history", params={"side": "SELLING"}, headers=seller)).json()["total"] == 2
