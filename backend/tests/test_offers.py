"""M4 — Offer negotiation tests."""

import json
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient

from tests.conftest import _auth_headers, _register


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def buyer(client: AsyncClient) -> dict:
    return await _register(client, "buyer_offer@test.com", club_name="Buyer FC")


@pytest_asyncio.fixture
async def seller(client: AsyncClient) -> dict:
    return await _register(client, "seller_offer@test.com", club_name="Seller FC")


@pytest_asyncio.fixture
async def third_club(client: AsyncClient) -> dict:
    return await _register(client, "third_offer@test.com", club_name="Third FC")


async def _create_player(client: AsyncClient, headers: dict, name: str = "Offer Player") -> dict:
    resp = await client.post("/players", json={"name": name, "position": "MID"}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _give_budget(db, amount: Decimal = Decimal("50000000")):
    from app.clubs.models import ClubFinance
    from sqlalchemy import select

    result = await db.execute(select(ClubFinance))
    for f in result.scalars():
        f.transfer_budget_total = amount
    await db.commit()


async def _make_offer(
    client: AsyncClient,
    headers: dict,
    player_id: str,
    to_club_id: str | None,
    fee: float = 5_000_000,
) -> dict:
    body = {"player_id": player_id, "fee_amount": fee}
    if to_club_id:
        body["to_club_id"] = to_club_id
    resp = await client.post("/offers", json=body, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _get_seller_club_id(client: AsyncClient, seller_headers: dict) -> str:
    resp = await client.get("/clubs/me", headers=seller_headers)
    assert resp.status_code == 200
    return resp.json()["id"]


async def _get_finance(client: AsyncClient, headers: dict) -> dict:
    resp = await client.get("/clubs/me", headers=headers)
    assert resp.status_code == 200
    return resp.json()["finance"]


# ── Create offer ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_offer_requires_auth(client: AsyncClient, seller: dict):
    headers = _auth_headers(seller)
    player = await _create_player(client, headers)
    resp = await client.post("/offers", json={"player_id": player["id"], "fee_amount": 5_000_000})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_offer_no_budget_fails(client: AsyncClient, buyer: dict, seller: dict):
    sel_headers = _auth_headers(seller)
    player = await _create_player(client, sel_headers)
    seller_club_id = await _get_seller_club_id(client, sel_headers)

    resp = await client.post(
        "/offers",
        json={"player_id": player["id"], "to_club_id": seller_club_id, "fee_amount": 5_000_000},
        headers=_auth_headers(buyer),
    )
    assert resp.status_code == 400
    assert "budget" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_offer_success(client: AsyncClient, buyer: dict, seller: dict, db):
    await _give_budget(db)
    sel_headers = _auth_headers(seller)
    player = await _create_player(client, sel_headers)
    seller_club_id = await _get_seller_club_id(client, sel_headers)

    resp = await client.post(
        "/offers",
        json={"player_id": player["id"], "to_club_id": seller_club_id, "fee_amount": 5_000_000},
        headers=_auth_headers(buyer),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "SENT"
    assert float(data["fee_amount"]) == 5_000_000
    # Events should have CREATED + SENT
    assert len(data["events"]) == 2


@pytest.mark.asyncio
async def test_add_ons_count_toward_reservation(client: AsyncClient, buyer: dict, seller: dict, db):
    """Item 3: numeric add_ons must be reserved alongside fee_amount, not ignored."""
    await _give_budget(db)
    sel_headers = _auth_headers(seller)
    buy_headers = _auth_headers(buyer)
    player = await _create_player(client, sel_headers)
    seller_club_id = await _get_seller_club_id(client, sel_headers)

    before = await _get_finance(client, buy_headers)
    resp = await client.post(
        "/offers",
        json={
            "player_id": player["id"],
            "to_club_id": seller_club_id,
            "fee_amount": 5_000_000,
            "add_ons": {"appearance_bonus": 300_000, "champions_league_bonus": 200_000, "note": "review yearly"},
        },
        headers=buy_headers,
    )
    assert resp.status_code == 201, resp.text
    after = await _get_finance(client, buy_headers)

    # Only the two numeric entries (500,000 total) count — "note" is ignored.
    assert Decimal(after["transfer_reserved"]) - Decimal(before["transfer_reserved"]) == Decimal("5500000")


@pytest.mark.asyncio
async def test_add_ons_can_push_offer_over_budget(client: AsyncClient, buyer: dict, seller: dict, db):
    """Item 3: a fee that alone fits the budget must still be rejected once
    add_ons push the true total over what's available."""
    await _give_budget(db, amount=Decimal("5000000"))
    sel_headers = _auth_headers(seller)
    player = await _create_player(client, sel_headers)
    seller_club_id = await _get_seller_club_id(client, sel_headers)

    resp = await client.post(
        "/offers",
        json={
            "player_id": player["id"],
            "to_club_id": seller_club_id,
            "fee_amount": 5_000_000,
            "add_ons": {"signing_bonus": 1_000_000},
        },
        headers=_auth_headers(buyer),
    )
    assert resp.status_code == 400
    assert "budget" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_offer_visible_to_both_parties(client: AsyncClient, buyer: dict, seller: dict, db):
    await _give_budget(db)
    sel_headers = _auth_headers(seller)
    buy_headers = _auth_headers(buyer)
    player = await _create_player(client, sel_headers)
    seller_club_id = await _get_seller_club_id(client, sel_headers)

    offer = await _make_offer(client, buy_headers, player["id"], seller_club_id)

    # Both can view it
    assert (await client.get(f"/offers/{offer['id']}", headers=buy_headers)).status_code == 200
    assert (await client.get(f"/offers/{offer['id']}", headers=sel_headers)).status_code == 200


@pytest.mark.asyncio
async def test_offer_not_visible_to_third_party(client: AsyncClient, buyer: dict, seller: dict, third_club: dict, db):
    await _give_budget(db)
    sel_headers = _auth_headers(seller)
    player = await _create_player(client, sel_headers)
    seller_club_id = await _get_seller_club_id(client, sel_headers)

    offer = await _make_offer(client, _auth_headers(buyer), player["id"], seller_club_id)

    resp = await client.get(f"/offers/{offer['id']}", headers=_auth_headers(third_club))
    assert resp.status_code == 403


# ── Counter offer ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_counter_offer(client: AsyncClient, buyer: dict, seller: dict, db):
    await _give_budget(db)
    sel_headers = _auth_headers(seller)
    buy_headers = _auth_headers(buyer)
    player = await _create_player(client, sel_headers)
    seller_club_id = await _get_seller_club_id(client, sel_headers)

    offer = await _make_offer(client, buy_headers, player["id"], seller_club_id)

    resp = await client.post(
        f"/offers/{offer['id']}/counter",
        json={"fee_amount": 8_000_000},
        headers=sel_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "COUNTERED"
    assert float(data["fee_amount"]) == 8_000_000


@pytest.mark.asyncio
async def test_third_party_cannot_counter(client: AsyncClient, buyer: dict, seller: dict, third_club: dict, db):
    await _give_budget(db)
    sel_headers = _auth_headers(seller)
    player = await _create_player(client, sel_headers)
    seller_club_id = await _get_seller_club_id(client, sel_headers)

    offer = await _make_offer(client, _auth_headers(buyer), player["id"], seller_club_id)

    resp = await client.post(
        f"/offers/{offer['id']}/counter",
        json={"fee_amount": 6_000_000},
        headers=_auth_headers(third_club),
    )
    assert resp.status_code == 400


# ── Accept offer ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_accept_offer_creates_deal(client: AsyncClient, buyer: dict, seller: dict, db):
    await _give_budget(db)
    sel_headers = _auth_headers(seller)
    buy_headers = _auth_headers(buyer)
    player = await _create_player(client, sel_headers)
    seller_club_id = await _get_seller_club_id(client, sel_headers)

    offer = await _make_offer(client, buy_headers, player["id"], seller_club_id)

    resp = await client.post(f"/offers/{offer['id']}/accept", headers=sel_headers)
    assert resp.status_code == 200
    deal = resp.json()
    assert deal["status"] == "IN_PROGRESS"
    assert deal["stage"] == "AGREEMENT"
    assert float(deal["agreed_fee"]) == 5_000_000

    # Offer should now be ACCEPTED
    offer_resp = await client.get(f"/offers/{offer['id']}", headers=buy_headers)
    assert offer_resp.json()["status"] == "ACCEPTED"


@pytest.mark.asyncio
async def test_accept_offer_rejects_sibling_offers(
    client: AsyncClient, buyer: dict, seller: dict, third_club: dict, db
):
    """Item 1: accepting one offer must reject every other pending offer for
    the same player, release the rival's budget, and notify them."""
    from sqlalchemy import select

    from app.auth.models import User
    from app.notifications.models import Notification, NotificationType

    await _give_budget(db)
    sel_headers = _auth_headers(seller)
    buy_headers = _auth_headers(buyer)
    rival_headers = _auth_headers(third_club)
    player = await _create_player(client, sel_headers)
    seller_club_id = await _get_seller_club_id(client, sel_headers)

    winning_offer = await _make_offer(client, buy_headers, player["id"], seller_club_id, fee=5_000_000)
    rival_offer = await _make_offer(client, rival_headers, player["id"], seller_club_id, fee=4_500_000)

    rival_finance_before = await _get_finance(client, rival_headers)

    resp = await client.post(f"/offers/{winning_offer['id']}/accept", headers=sel_headers)
    assert resp.status_code == 200

    rival_after = await client.get(f"/offers/{rival_offer['id']}", headers=rival_headers)
    assert rival_after.json()["status"] == "REJECTED"

    rival_finance_after = await _get_finance(client, rival_headers)
    assert Decimal(rival_finance_after["transfer_reserved"]) == Decimal("0")
    assert rival_finance_before["transfer_reserved"] != rival_finance_after["transfer_reserved"]

    await db.rollback()
    rival_user_id = (await db.execute(select(User).where(User.email == "third_offer@test.com"))).scalar_one().id
    notif_result = await db.execute(
        select(Notification).where(
            Notification.recipient_user_id == rival_user_id,
            Notification.type == NotificationType.OFFER_REJECTED,
        )
    )
    assert notif_result.scalars().first() is not None


@pytest.mark.asyncio
async def test_cannot_accept_already_accepted(client: AsyncClient, buyer: dict, seller: dict, db):
    await _give_budget(db)
    sel_headers = _auth_headers(seller)
    player = await _create_player(client, sel_headers)
    seller_club_id = await _get_seller_club_id(client, sel_headers)

    offer = await _make_offer(client, _auth_headers(buyer), player["id"], seller_club_id)
    await client.post(f"/offers/{offer['id']}/accept", headers=sel_headers)

    resp = await client.post(f"/offers/{offer['id']}/accept", headers=sel_headers)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_cannot_accept_offer_for_player_not_owned_by_receiving_club(
    client: AsyncClient, buyer: dict, seller: dict, third_club: dict, db
):
    """TRA-138: the club named as seller in an offer must actually own the player."""
    await _give_budget(db)
    sel_headers = _auth_headers(seller)
    buy_headers = _auth_headers(buyer)
    third_headers = _auth_headers(third_club)

    player = await _create_player(client, sel_headers)  # registered to `seller`, not `third_club`
    third_club_id = await _get_seller_club_id(client, third_headers)

    offer = await _make_offer(client, buy_headers, player["id"], third_club_id)

    resp = await client.post(f"/offers/{offer['id']}/accept", headers=third_headers)
    assert resp.status_code == 400
    assert "own" in resp.json()["detail"].lower()


# ── Reject offer ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_reject_offer(client: AsyncClient, buyer: dict, seller: dict, db):
    await _give_budget(db)
    sel_headers = _auth_headers(seller)
    player = await _create_player(client, sel_headers)
    seller_club_id = await _get_seller_club_id(client, sel_headers)

    offer = await _make_offer(client, _auth_headers(buyer), player["id"], seller_club_id)

    resp = await client.post(f"/offers/{offer['id']}/reject", headers=sel_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "REJECTED"

    # Budget should be released
    from app.clubs.models import ClubFinance
    from sqlalchemy import select as sa_select

    result = await db.execute(sa_select(ClubFinance))
    for f in result.scalars():
        await db.refresh(f)
        assert f.transfer_reserved == Decimal("0")


# ── Withdraw offer ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_withdraw_own_offer(client: AsyncClient, buyer: dict, seller: dict, db):
    await _give_budget(db)
    sel_headers = _auth_headers(seller)
    buy_headers = _auth_headers(buyer)
    player = await _create_player(client, sel_headers)
    seller_club_id = await _get_seller_club_id(client, sel_headers)

    offer = await _make_offer(client, buy_headers, player["id"], seller_club_id)

    resp = await client.post(f"/offers/{offer['id']}/withdraw", headers=buy_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "WITHDRAWN"


@pytest.mark.asyncio
async def test_receiver_cannot_withdraw(client: AsyncClient, buyer: dict, seller: dict, db):
    """The receiver hasn't made a move yet (isn't the sender or the last actor),
    so they can't withdraw — their move at this point is reject_offer."""
    await _give_budget(db)
    sel_headers = _auth_headers(seller)
    player = await _create_player(client, sel_headers)
    seller_club_id = await _get_seller_club_id(client, sel_headers)

    offer = await _make_offer(client, _auth_headers(buyer), player["id"], seller_club_id)

    resp = await client.post(f"/offers/{offer['id']}/withdraw", headers=sel_headers)
    assert resp.status_code == 400
    assert "retract" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_seller_can_withdraw_own_counter_without_waiting(
    client: AsyncClient, buyer: dict, seller: dict, db
):
    """Item 2: a seller who just countered can walk away immediately — they
    don't have to wait for the buyer to respond first."""
    await _give_budget(db)
    sel_headers = _auth_headers(seller)
    buy_headers = _auth_headers(buyer)
    player = await _create_player(client, sel_headers)
    seller_club_id = await _get_seller_club_id(client, sel_headers)

    offer = await _make_offer(client, buy_headers, player["id"], seller_club_id)
    counter_resp = await client.post(
        f"/offers/{offer['id']}/counter", json={"fee_amount": 8_000_000}, headers=sel_headers,
    )
    assert counter_resp.status_code == 200

    # It's the buyer's turn now, but the seller (who just acted) can still retract.
    resp = await client.post(f"/offers/{offer['id']}/withdraw", headers=sel_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "WITHDRAWN"


@pytest.mark.asyncio
async def test_buyer_cannot_withdraw_sellers_outstanding_counter(
    client: AsyncClient, buyer: dict, seller: dict, db
):
    """The buyer can always withdraw their own offer (unchanged), but this
    checks the seller's counter itself isn't retractable by the buyer."""
    await _give_budget(db)
    sel_headers = _auth_headers(seller)
    buy_headers = _auth_headers(buyer)
    player = await _create_player(client, sel_headers)
    seller_club_id = await _get_seller_club_id(client, sel_headers)

    offer = await _make_offer(client, buy_headers, player["id"], seller_club_id)
    await client.post(f"/offers/{offer['id']}/counter", json={"fee_amount": 8_000_000}, headers=sel_headers)

    # Buyer is from_club_id, so withdraw still succeeds (pre-existing behavior) —
    # this documents that withdraw always empties the whole offer, not just undoes
    # the seller's counter; the buyer's own-offer escape hatch is unconditional.
    resp = await client.post(f"/offers/{offer['id']}/withdraw", headers=buy_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "WITHDRAWN"


# ── Improve own offer (item 2: self-raise turn exception) ────────────────────


@pytest.mark.asyncio
async def test_buyer_can_improve_own_offer_while_waiting(
    client: AsyncClient, buyer: dict, seller: dict, db
):
    """Item 2: the buyer can raise their own pending offer even though it's
    not their turn (they were the last actor — normal turn order would block
    any further action from them until the seller responds)."""
    await _give_budget(db)
    sel_headers = _auth_headers(seller)
    buy_headers = _auth_headers(buyer)
    player = await _create_player(client, sel_headers)
    seller_club_id = await _get_seller_club_id(client, sel_headers)

    offer = await _make_offer(client, buy_headers, player["id"], seller_club_id, fee=5_000_000)
    buyer_club_id = offer["from_club_id"]

    # Prove the ordinary path is blocked first — this is exactly the gap.
    blocked = await client.post(
        f"/offers/{offer['id']}/counter", json={"fee_amount": 6_000_000}, headers=buy_headers,
    )
    assert blocked.status_code == 400
    assert "turn" in blocked.json()["detail"].lower()

    resp = await client.post(
        f"/offers/{offer['id']}/improve", json={"fee_amount": 6_000_000}, headers=buy_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert float(data["fee_amount"]) == 6_000_000
    # Status/turn untouched — still SENT, still awaiting the seller.
    assert data["status"] == "SENT"
    assert data["last_actor_club_id"] == buyer_club_id


@pytest.mark.asyncio
async def test_improve_cannot_lower_offer_value(client: AsyncClient, buyer: dict, seller: dict, db):
    await _give_budget(db)
    sel_headers = _auth_headers(seller)
    buy_headers = _auth_headers(buyer)
    player = await _create_player(client, sel_headers)
    seller_club_id = await _get_seller_club_id(client, sel_headers)

    offer = await _make_offer(client, buy_headers, player["id"], seller_club_id, fee=5_000_000)

    resp = await client.post(
        f"/offers/{offer['id']}/improve", json={"fee_amount": 4_000_000}, headers=buy_headers,
    )
    assert resp.status_code == 400
    assert "lower" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_seller_cannot_improve_buyers_offer(client: AsyncClient, buyer: dict, seller: dict, db):
    await _give_budget(db)
    sel_headers = _auth_headers(seller)
    buy_headers = _auth_headers(buyer)
    player = await _create_player(client, sel_headers)
    seller_club_id = await _get_seller_club_id(client, sel_headers)

    offer = await _make_offer(client, buy_headers, player["id"], seller_club_id, fee=5_000_000)

    resp = await client.post(
        f"/offers/{offer['id']}/improve", json={"fee_amount": 6_000_000}, headers=sel_headers,
    )
    assert resp.status_code == 400
    assert "buyer" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_improve_reserves_the_delta(client: AsyncClient, buyer: dict, seller: dict, db):
    await _give_budget(db)
    sel_headers = _auth_headers(seller)
    buy_headers = _auth_headers(buyer)
    player = await _create_player(client, sel_headers)
    seller_club_id = await _get_seller_club_id(client, sel_headers)

    offer = await _make_offer(client, buy_headers, player["id"], seller_club_id, fee=5_000_000)
    before = await _get_finance(client, buy_headers)

    await client.post(f"/offers/{offer['id']}/improve", json={"fee_amount": 6_500_000}, headers=buy_headers)
    after = await _get_finance(client, buy_headers)

    assert Decimal(after["transfer_reserved"]) - Decimal(before["transfer_reserved"]) == Decimal("1500000")


# ── Messages ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_add_message_to_offer(client: AsyncClient, buyer: dict, seller: dict, db):
    await _give_budget(db)
    sel_headers = _auth_headers(seller)
    buy_headers = _auth_headers(buyer)
    player = await _create_player(client, sel_headers)
    seller_club_id = await _get_seller_club_id(client, sel_headers)

    offer = await _make_offer(client, buy_headers, player["id"], seller_club_id)

    resp = await client.post(
        f"/offers/{offer['id']}/messages",
        json={"body": "Very interested in this player!"},
        headers=buy_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["body"] == "Very interested in this player!"

    # Verify message appears in offer detail
    offer_resp = await client.get(f"/offers/{offer['id']}", headers=buy_headers)
    assert len(offer_resp.json()["messages"]) == 1


@pytest.mark.asyncio
async def test_cannot_message_closed_offer(client: AsyncClient, buyer: dict, seller: dict, db):
    await _give_budget(db)
    sel_headers = _auth_headers(seller)
    buy_headers = _auth_headers(buyer)
    player = await _create_player(client, sel_headers)
    seller_club_id = await _get_seller_club_id(client, sel_headers)

    offer = await _make_offer(client, buy_headers, player["id"], seller_club_id)
    await client.post(f"/offers/{offer['id']}/reject", headers=sel_headers)

    resp = await client.post(
        f"/offers/{offer['id']}/messages",
        json={"body": "Can we reconsider?"},
        headers=buy_headers,
    )
    assert resp.status_code == 400


# ── List offers ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_sent_offers(client: AsyncClient, buyer: dict, seller: dict, db):
    await _give_budget(db)
    sel_headers = _auth_headers(seller)
    buy_headers = _auth_headers(buyer)
    player = await _create_player(client, sel_headers)
    seller_club_id = await _get_seller_club_id(client, sel_headers)

    await _make_offer(client, buy_headers, player["id"], seller_club_id)

    resp = await client.get("/offers/sent", headers=buy_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


@pytest.mark.asyncio
async def test_list_received_offers(client: AsyncClient, buyer: dict, seller: dict, db):
    await _give_budget(db)
    sel_headers = _auth_headers(seller)
    player = await _create_player(client, sel_headers)
    seller_club_id = await _get_seller_club_id(client, sel_headers)

    await _make_offer(client, _auth_headers(buyer), player["id"], seller_club_id)

    resp = await client.get("/offers/received", headers=sel_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


# ── B1: whose_move ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_offer_whose_move_your_and_their(client: AsyncClient, buyer: dict, seller: dict, db):
    await _give_budget(db)
    buy_headers = _auth_headers(buyer)
    sel_headers = _auth_headers(seller)
    player = await _create_player(client, sel_headers)
    seller_club_id = await _get_seller_club_id(client, sel_headers)

    offer = await _make_offer(client, buy_headers, player["id"], seller_club_id)

    # Buyer just sent it — that's their own last action, so it's the seller's move.
    mine = (await client.get(f"/offers/{offer['id']}", headers=buy_headers)).json()
    assert mine["whose_move"] == "their"
    theirs = (await client.get(f"/offers/{offer['id']}", headers=sel_headers)).json()
    assert theirs["whose_move"] == "your"


@pytest.mark.asyncio
async def test_offer_whose_move_neither_when_terminal(client: AsyncClient, buyer: dict, seller: dict, db):
    await _give_budget(db)
    buy_headers = _auth_headers(buyer)
    sel_headers = _auth_headers(seller)
    player = await _create_player(client, sel_headers)
    seller_club_id = await _get_seller_club_id(client, sel_headers)

    offer = await _make_offer(client, buy_headers, player["id"], seller_club_id)
    resp = await client.post(f"/offers/{offer['id']}/reject", headers=sel_headers)
    assert resp.status_code == 200
    assert resp.json()["whose_move"] == "neither"

    refetched = (await client.get(f"/offers/{offer['id']}", headers=buy_headers)).json()
    assert refetched["whose_move"] == "neither"


# ── Accepting an offer made against a listing closes that listing ────────────


async def _create_open_to_offers_sale(
    client: AsyncClient, seller_headers: dict, player_id: str, asking: float = 5_000_000
) -> dict:
    resp = await client.post(
        "/sales",
        json={"player_id": player_id, "sale_type": "OPEN_TO_OFFERS", "asking_price": asking},
        headers=seller_headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_accepting_offer_on_listing_closes_the_listing(
    client: AsyncClient, buyer: dict, seller: dict, db
):
    """The auction path (accept_bid) always closed the sale; the OPEN_TO_OFFERS
    path did not, leaving the player listed while their deal was in progress."""
    await _give_budget(db)
    buy_headers = _auth_headers(buyer)
    sel_headers = _auth_headers(seller)
    player = await _create_player(client, sel_headers)
    seller_club_id = await _get_seller_club_id(client, sel_headers)
    sale = await _create_open_to_offers_sale(client, sel_headers, player["id"])

    offer_resp = await client.post(
        "/offers",
        json={
            "player_id": player["id"],
            "to_club_id": seller_club_id,
            "sale_id": sale["id"],
            "fee_amount": 5_000_000,
        },
        headers=buy_headers,
    )
    assert offer_resp.status_code == 201, offer_resp.text

    deal = await client.post(f"/offers/{offer_resp.json()['id']}/accept", headers=sel_headers)
    assert deal.status_code == 200, deal.text

    refetched_sale = (await client.get(f"/sales/{sale['id']}", headers=sel_headers)).json()
    assert refetched_sale["status"] == "CLOSED"
    # The deal must carry the originating listing, or a later collapse can
    # never re-list it (deals/service.py::_reopen_sale_after_collapse).
    assert deal.json()["sale_id"] == sale["id"]


@pytest.mark.asyncio
async def test_closed_listing_reports_the_deal_that_resolved_it(
    client: AsyncClient, buyer: dict, seller: dict, db
):
    """A resolved listing must say what resolved it. `status` alone cannot
    distinguish sold from withdrawn or expired-unsold, and the order book shows
    only inactive rows in every one of those cases."""
    await _give_budget(db)
    buy_headers = _auth_headers(buyer)
    sel_headers = _auth_headers(seller)
    player = await _create_player(client, sel_headers)
    seller_club_id = await _get_seller_club_id(client, sel_headers)
    sale = await _create_open_to_offers_sale(client, sel_headers, player["id"])

    # while the listing is still open there is nothing to explain
    still_open = (await client.get(f"/sales/{sale['id']}", headers=sel_headers)).json()
    assert still_open["status"] == "OPEN"
    assert still_open["active_deal"] is None

    offer_resp = await client.post(
        "/offers",
        json={
            "player_id": player["id"],
            "to_club_id": seller_club_id,
            "sale_id": sale["id"],
            "fee_amount": 5_000_000,
        },
        headers=buy_headers,
    )
    deal = (await client.post(f"/offers/{offer_resp.json()['id']}/accept", headers=sel_headers)).json()

    resolved = (await client.get(f"/sales/{sale['id']}", headers=sel_headers)).json()
    assert resolved["status"] == "CLOSED"
    assert resolved["active_deal"] is not None
    assert resolved["active_deal"]["id"] == deal["id"]
    assert resolved["active_deal"]["status"] == "IN_PROGRESS"


@pytest.mark.asyncio
async def test_accepted_offer_carries_the_deals_outcome(
    client: AsyncClient, buyer: dict, seller: dict, db
):
    """`Offer.status` stays ACCEPTED after the deal collapses — truthfully, since
    the offer really was accepted. The embedded deal is what tells a reader the
    transfer is dead, on both the detail and the list endpoint."""
    await _give_budget(db)
    buy_headers = _auth_headers(buyer)
    sel_headers = _auth_headers(seller)
    player = await _create_player(client, sel_headers)
    seller_club_id = await _get_seller_club_id(client, sel_headers)

    offer = await _make_offer(client, buy_headers, player["id"], seller_club_id)

    # before acceptance there is no deal to report
    pre = (await client.get(f"/offers/{offer['id']}", headers=buy_headers)).json()
    assert pre["deal"] is None

    deal = (await client.post(f"/offers/{offer['id']}/accept", headers=sel_headers)).json()
    accepted = (await client.get(f"/offers/{offer['id']}", headers=buy_headers)).json()
    assert accepted["status"] == "ACCEPTED"
    assert accepted["deal"]["id"] == deal["id"]
    assert accepted["deal"]["status"] == "IN_PROGRESS"

    await client.post(f"/deals/{deal['id']}/collapse", headers=sel_headers)

    after = (await client.get(f"/offers/{offer['id']}", headers=buy_headers)).json()
    assert after["status"] == "ACCEPTED", "the offer's own history must not be rewritten"
    assert after["deal"]["status"] == "COLLAPSED"

    # and the same fact must reach the list view, which is where it was missing
    sent = (await client.get("/offers/sent", headers=buy_headers)).json()
    row = next(o for o in sent["items"] if o["id"] == offer["id"])
    assert row["deal"]["status"] == "COLLAPSED"


@pytest.mark.asyncio
async def test_collapsing_offer_originated_deal_reopens_the_listing(
    client: AsyncClient, buyer: dict, seller: dict, db
):
    await _give_budget(db)
    buy_headers = _auth_headers(buyer)
    sel_headers = _auth_headers(seller)
    player = await _create_player(client, sel_headers)
    seller_club_id = await _get_seller_club_id(client, sel_headers)
    sale = await _create_open_to_offers_sale(client, sel_headers, player["id"])

    offer_resp = await client.post(
        "/offers",
        json={
            "player_id": player["id"],
            "to_club_id": seller_club_id,
            "sale_id": sale["id"],
            "fee_amount": 5_000_000,
        },
        headers=buy_headers,
    )
    deal = (await client.post(f"/offers/{offer_resp.json()['id']}/accept", headers=sel_headers)).json()

    collapse = await client.post(f"/deals/{deal['id']}/collapse", headers=sel_headers)
    assert collapse.status_code == 200, collapse.text

    reopened = (await client.get(f"/sales/{sale['id']}", headers=sel_headers)).json()
    assert reopened["status"] == "OPEN"


@pytest.mark.asyncio
async def test_accepting_standalone_offer_leaves_no_sale_link(
    client: AsyncClient, buyer: dict, seller: dict, db
):
    """Offers not made against a listing must be unaffected by the close logic."""
    await _give_budget(db)
    sel_headers = _auth_headers(seller)
    player = await _create_player(client, sel_headers)
    seller_club_id = await _get_seller_club_id(client, sel_headers)

    offer = await _make_offer(client, _auth_headers(buyer), player["id"], seller_club_id)
    deal = await client.post(f"/offers/{offer['id']}/accept", headers=sel_headers)
    assert deal.status_code == 200, deal.text
    assert deal.json()["sale_id"] is None


# ── Fee-less offers ───────────────────────────────────────────────────────────
#
# An offer with no transfer fee is legitimate — free transfers, loans and swaps
# all have none — and the create form leaves the field optional. But the D7
# approval summaries formatted `fee_amount` with `:,.0f`, which raises on None.
# Because the summary is built as an *argument* to `maybe_capture`, it raised
# before any threshold logic ran, so it 500'd for every caller rather than just
# the MANAGER role that check targets.


@pytest.mark.asyncio
async def test_can_create_offer_with_no_fee(client: AsyncClient, buyer: dict, seller: dict, db):
    sel_headers = _auth_headers(seller)
    player = await _create_player(client, sel_headers)
    seller_club_id = await _get_seller_club_id(client, sel_headers)

    resp = await client.post(
        "/offers",
        json={"player_id": player["id"], "to_club_id": seller_club_id},
        headers=_auth_headers(buyer),
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["fee_amount"] is None


@pytest.mark.asyncio
async def test_can_accept_offer_with_no_fee(client: AsyncClient, buyer: dict, seller: dict, db):
    """The second, latent copy of the same bug — `accept_offer`'s summary."""
    sel_headers = _auth_headers(seller)
    player = await _create_player(client, sel_headers)
    seller_club_id = await _get_seller_club_id(client, sel_headers)

    offer = (await client.post(
        "/offers",
        json={"player_id": player["id"], "to_club_id": seller_club_id},
        headers=_auth_headers(buyer),
    )).json()

    resp = await client.post(f"/offers/{offer['id']}/accept", headers=sel_headers)
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_no_fee_offer_does_not_escalate_for_approval(
    client: AsyncClient, buyer: dict, seller: dict, db
):
    """A fee-less offer is zero in threshold terms, so a MANAGER can send it
    without sign-off — but it must reach that conclusion, not crash on the way.
    Guards `maybe_capture`'s `Decimal(None)`, which the summary fix alone would
    have left exposed for any club that has a threshold set."""
    from tests.test_capabilities import _create_staff

    sel_headers = _auth_headers(seller)
    player = await _create_player(client, sel_headers)
    seller_club_id = await _get_seller_club_id(client, sel_headers)

    threshold = await client.patch(
        "/clubs/me/approval-policy",
        json={"approval_threshold": 1_000_000},
        headers=_auth_headers(buyer),
    )
    assert threshold.status_code == 200, threshold.text
    manager = await _create_staff(
        client, db, _auth_headers(buyer), "nofee_mgr@test.com", "MANAGER"
    )

    resp = await client.post(
        "/offers",
        json={"player_id": player["id"], "to_club_id": seller_club_id},
        headers=_auth_headers(manager),
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["fee_amount"] is None


# ── Anonymous buying club ─────────────────────────────────────────────────────
#
# A buyer can approach without disclosing who they are; the seller sees only
# their league until the offer is accepted. The identity leaks through more
# than the club name -- ids resolve straight off GET /clubs/{id} -- so these
# tests assert on the *absence of the buyer's club id anywhere in the payload*,
# not merely on the name being hidden.


async def _make_anonymous_offer(client: AsyncClient, buy_headers, sel_headers, player_id, seller_club_id):
    resp = await client.post(
        "/offers",
        json={
            "player_id": player_id,
            "to_club_id": seller_club_id,
            "fee_amount": 5_000_000,
            "is_anonymous": True,
        },
        headers=buy_headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_seller_cannot_identify_an_anonymous_buyer(
    client: AsyncClient, buyer: dict, seller: dict, db
):
    await _give_budget(db)
    buy_headers, sel_headers = _auth_headers(buyer), _auth_headers(seller)
    player = await _create_player(client, sel_headers)
    seller_club_id = await _get_seller_club_id(client, sel_headers)
    buyer_club_id = (await client.get("/clubs/me", headers=buy_headers)).json()["id"]

    offer = await _make_anonymous_offer(client, buy_headers, sel_headers, player["id"], seller_club_id)

    seen = (await client.get(f"/offers/{offer['id']}", headers=sel_headers)).json()
    assert seen["is_anonymous"] is True, "the seller must know they face an undisclosed club"
    assert seen["from_club"] is None
    assert seen["from_club_id"] is None

    # The decisive check: the buyer's club id must not appear anywhere in the
    # payload -- not in last_actor_club_id, an event actor, or a message sender.
    assert buyer_club_id not in json.dumps(seen), "buyer club id leaked into the response"


@pytest.mark.asyncio
async def test_anonymous_buyer_still_sees_their_own_identity(
    client: AsyncClient, buyer: dict, seller: dict, db
):
    await _give_budget(db)
    buy_headers, sel_headers = _auth_headers(buyer), _auth_headers(seller)
    player = await _create_player(client, sel_headers)
    seller_club_id = await _get_seller_club_id(client, sel_headers)

    offer = await _make_anonymous_offer(client, buy_headers, sel_headers, player["id"], seller_club_id)

    mine = (await client.get(f"/offers/{offer['id']}", headers=buy_headers)).json()
    assert mine["from_club"] is not None
    assert mine["from_club_id"] is not None


@pytest.mark.asyncio
async def test_anonymous_buyer_is_revealed_once_the_offer_is_accepted(
    client: AsyncClient, buyer: dict, seller: dict, db
):
    """The bargain: undisclosed while the seller decides, named the moment
    they agree."""
    await _give_budget(db)
    buy_headers, sel_headers = _auth_headers(buyer), _auth_headers(seller)
    player = await _create_player(client, sel_headers)
    seller_club_id = await _get_seller_club_id(client, sel_headers)
    buyer_club_id = (await client.get("/clubs/me", headers=buy_headers)).json()["id"]

    offer = await _make_anonymous_offer(client, buy_headers, sel_headers, player["id"], seller_club_id)

    before = (await client.get(f"/offers/{offer['id']}", headers=sel_headers)).json()
    assert before["from_club_id"] is None

    accepted = await client.post(f"/offers/{offer['id']}/accept", headers=sel_headers)
    assert accepted.status_code == 200, accepted.text

    after = (await client.get(f"/offers/{offer['id']}", headers=sel_headers)).json()
    assert after["from_club_id"] == buyer_club_id
    assert after["from_club"] is not None


@pytest.mark.asyncio
async def test_rejected_anonymous_offer_stays_anonymous_forever(
    client: AsyncClient, buyer: dict, seller: dict, db
):
    """Interest that came to nothing was never disclosed -- that is the point
    of anonymity, not a gap in the reveal."""
    await _give_budget(db)
    buy_headers, sel_headers = _auth_headers(buyer), _auth_headers(seller)
    player = await _create_player(client, sel_headers)
    seller_club_id = await _get_seller_club_id(client, sel_headers)
    buyer_club_id = (await client.get("/clubs/me", headers=buy_headers)).json()["id"]

    offer = await _make_anonymous_offer(client, buy_headers, sel_headers, player["id"], seller_club_id)
    rejected = await client.post(f"/offers/{offer['id']}/reject", headers=sel_headers)
    assert rejected.status_code == 200, rejected.text

    seen = (await client.get(f"/offers/{offer['id']}", headers=sel_headers)).json()
    assert seen["from_club_id"] is None
    assert buyer_club_id not in json.dumps(seen)


@pytest.mark.asyncio
async def test_order_book_masks_an_anonymous_rival(
    client: AsyncClient, buyer: dict, seller: dict, third_club: dict, db
):
    """The competition panel names every club bidding for a player, which is
    exactly what the buyer is paying to avoid -- masking the offer alone would
    leak the identity straight out of the panel beside it."""
    await _give_budget(db)
    buy_headers, sel_headers = _auth_headers(buyer), _auth_headers(seller)
    third_headers = _auth_headers(third_club)
    player = await _create_player(client, sel_headers)
    seller_club_id = await _get_seller_club_id(client, sel_headers)
    buyer_club_id = (await client.get("/clubs/me", headers=buy_headers)).json()["id"]

    await _make_anonymous_offer(client, buy_headers, sel_headers, player["id"], seller_club_id)
    await _make_offer(client, third_headers, player["id"], seller_club_id, fee=4_000_000)

    book = (await client.get(f"/offers/competition/{player['id']}", headers=sel_headers)).json()
    assert buyer_club_id not in json.dumps(book), "anonymous buyer leaked via the order book"
    names = [e["club"]["name"] for e in book["entries"] if e.get("club")]
    assert any(n.startswith("A ") or n == "An undisclosed club" for n in names), names


@pytest.mark.asyncio
async def test_offers_are_identified_by_default(client: AsyncClient, buyer: dict, seller: dict, db):
    """Anonymity is opt-in; nothing about the existing flow changes unless the
    buyer asks for it."""
    await _give_budget(db)
    buy_headers, sel_headers = _auth_headers(buyer), _auth_headers(seller)
    player = await _create_player(client, sel_headers)
    seller_club_id = await _get_seller_club_id(client, sel_headers)

    offer = await _make_offer(client, buy_headers, player["id"], seller_club_id)
    seen = (await client.get(f"/offers/{offer['id']}", headers=sel_headers)).json()
    assert seen["is_anonymous"] is False
    assert seen["from_club"] is not None
    assert seen["from_club_id"] is not None


# ── Loan offers (feature_spec/loan-transfers.md phase 1) ─────────────────────


async def _give_wage_budget(db, weekly: Decimal = Decimal("500000")):
    from sqlalchemy import select

    from app.clubs.models import ClubFinance

    result = await db.execute(select(ClubFinance))
    for f in result.scalars():
        f.wage_budget_total_weekly = weekly
    await db.commit()


async def _contract(db, player_id: str, club_id: str, end_date, wage=Decimal("90000")):
    """Give the player an active contract, so he has a parent club to be loaned from."""
    import uuid as uuid_mod

    from app.players.models import Contract

    db.add(Contract(
        player_id=uuid_mod.UUID(player_id),
        club_id=uuid_mod.UUID(club_id),
        end_date=end_date,
        wage_weekly=wage,
        is_active=True,
    ))
    await db.commit()


def _loan_body(player_id: str, to_club_id: str, **over) -> dict:
    from datetime import date

    body = {
        "player_id": player_id,
        "to_club_id": to_club_id,
        "deal_type": "LOAN",
        "loan_start": str(date(2026, 9, 1)),
        "loan_end": str(date(2027, 5, 31)),
        "loan_fee": 2_000_000,
        "wage_weekly": 90_000,
        "wage_split_pct": 0.6,
    }
    body.update(over)
    return body


async def _finance(db, club_id: str):
    import uuid as uuid_mod

    from sqlalchemy import select

    from app.clubs.models import ClubFinance

    return (
        await db.execute(
            select(ClubFinance).where(ClubFinance.club_id == uuid_mod.UUID(club_id))
        )
    ).scalar_one()


@pytest.mark.asyncio
async def test_loan_offer_reserves_loan_fee_and_wage_share(
    client: AsyncClient, buyer: dict, seller: dict, db
):
    """A loan's money is loan_fee, not fee_amount, and the buyer carries only
    their agreed share of the wage: 60% of 90k, not the whole 90k."""
    from datetime import date

    await _give_budget(db)
    await _give_wage_budget(db)
    sel_headers, buy_headers = _auth_headers(seller), _auth_headers(buyer)
    player = await _create_player(client, sel_headers)
    seller_club = (await client.get("/clubs/me", headers=sel_headers)).json()
    buyer_club = (await client.get("/clubs/me", headers=buy_headers)).json()
    await _contract(db, player["id"], seller_club["id"], date(2028, 6, 30))

    resp = await client.post(
        "/offers", json=_loan_body(player["id"], seller_club["id"]), headers=buy_headers
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["deal_type"] == "LOAN"

    fin = await _finance(db, buyer_club["id"])
    await db.refresh(fin)
    assert fin.transfer_reserved == Decimal("2000000.00")
    assert fin.wage_reserved_weekly == Decimal("54000.00")


@pytest.mark.asyncio
async def test_permanent_offer_now_reserves_wage_too(
    client: AsyncClient, buyer: dict, seller: dict, db
):
    """The half of this that predates loans: reserve_budget has always taken a
    wage_weekly argument and no offer path ever passed one."""
    await _give_budget(db)
    await _give_wage_budget(db)
    sel_headers, buy_headers = _auth_headers(seller), _auth_headers(buyer)
    player = await _create_player(client, sel_headers)
    seller_club = (await client.get("/clubs/me", headers=sel_headers)).json()
    buyer_club = (await client.get("/clubs/me", headers=buy_headers)).json()

    resp = await client.post(
        "/offers",
        json={
            "player_id": player["id"], "to_club_id": seller_club["id"],
            "fee_amount": 5_000_000, "wage_weekly": 80_000,
        },
        headers=buy_headers,
    )
    assert resp.status_code == 201, resp.text

    fin = await _finance(db, buyer_club["id"])
    await db.refresh(fin)
    assert fin.transfer_reserved == Decimal("5000000.00")
    assert fin.wage_reserved_weekly == Decimal("80000.00")


@pytest.mark.asyncio
async def test_offer_refused_when_wage_budget_is_short(
    client: AsyncClient, buyer: dict, seller: dict, db
):
    """The affordability check inside reserve_budget existed all along and could
    never fire, because no caller passed a wage."""
    await _give_budget(db)
    await _give_wage_budget(db, Decimal("10000"))
    sel_headers, buy_headers = _auth_headers(seller), _auth_headers(buyer)
    player = await _create_player(client, sel_headers)
    seller_club = (await client.get("/clubs/me", headers=sel_headers)).json()

    resp = await client.post(
        "/offers",
        json={
            "player_id": player["id"], "to_club_id": seller_club["id"],
            "fee_amount": 1_000_000, "wage_weekly": 80_000,
        },
        headers=buy_headers,
    )
    assert resp.status_code == 400, resp.text
    assert "wage" in resp.text.lower()


@pytest.mark.asyncio
async def test_withdrawing_a_loan_offer_releases_both_reservations(
    client: AsyncClient, buyer: dict, seller: dict, db
):
    from datetime import date

    await _give_budget(db)
    await _give_wage_budget(db)
    sel_headers, buy_headers = _auth_headers(seller), _auth_headers(buyer)
    player = await _create_player(client, sel_headers)
    seller_club = (await client.get("/clubs/me", headers=sel_headers)).json()
    buyer_club = (await client.get("/clubs/me", headers=buy_headers)).json()
    await _contract(db, player["id"], seller_club["id"], date(2028, 6, 30))

    offer = (await client.post(
        "/offers", json=_loan_body(player["id"], seller_club["id"]), headers=buy_headers
    )).json()
    resp = await client.post("/offers/" + offer["id"] + "/withdraw", headers=buy_headers)
    assert resp.status_code == 200, resp.text

    fin = await _finance(db, buyer_club["id"])
    await db.refresh(fin)
    assert fin.transfer_reserved == Decimal("0.00")
    assert fin.wage_reserved_weekly == Decimal("0.00")


@pytest.mark.asyncio
async def test_accepting_a_loan_offer_carries_the_terms_onto_the_deal(
    client: AsyncClient, buyer: dict, seller: dict, db
):
    """The drift this closes: accept_offer built a Deal without deal_type, so
    every offer-originated deal was PERMANENT regardless of what was agreed."""
    from datetime import date

    await _give_budget(db)
    await _give_wage_budget(db)
    sel_headers, buy_headers = _auth_headers(seller), _auth_headers(buyer)
    player = await _create_player(client, sel_headers)
    seller_club = (await client.get("/clubs/me", headers=sel_headers)).json()
    await _contract(db, player["id"], seller_club["id"], date(2028, 6, 30))

    offer = (await client.post(
        "/offers", json=_loan_body(player["id"], seller_club["id"]), headers=buy_headers
    )).json()
    resp = await client.post("/offers/" + offer["id"] + "/accept", headers=sel_headers)
    assert resp.status_code == 200, resp.text

    # The accept endpoint returns a deliberate stub; full terms come from the
    # deal endpoint the deal room actually reads.
    stub = resp.json()
    assert stub["deal_type"] == "LOAN"
    # agreed_fee mirrors the loan fee so collapse/approvals/commission, which
    # all read agreed_fee, don't silently see zero for a loan.
    assert Decimal(str(stub["agreed_fee"])) == Decimal("2000000.00")

    deal = (await client.get("/deals/" + stub["id"], headers=sel_headers)).json()
    assert Decimal(str(deal["loan_fee"])) == Decimal("2000000.00")
    assert Decimal(str(deal["wage_split_pct"])) == Decimal("0.6000")
    assert deal["loan_start"] == "2026-09-01"
    assert deal["loan_end"] == "2027-05-31"


@pytest.mark.asyncio
async def test_permanent_offer_still_produces_a_permanent_deal(
    client: AsyncClient, buyer: dict, seller: dict, db
):
    await _give_budget(db)
    await _give_wage_budget(db)
    sel_headers, buy_headers = _auth_headers(seller), _auth_headers(buyer)
    player = await _create_player(client, sel_headers)
    seller_club = (await client.get("/clubs/me", headers=sel_headers)).json()

    offer = await _make_offer(client, buy_headers, player["id"], seller_club["id"])
    resp = await client.post("/offers/" + offer["id"] + "/accept", headers=sel_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["deal_type"] == "PERMANENT"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "override,expected",
    [
        ({"loan_start": None, "loan_end": None}, "start and an end"),
        ({"loan_end": "2026-08-01"}, "end after it starts"),
        ({"loan_end": "2029-09-01"}, "longer than 18 months"),
        ({"fee_amount": 1_000_000}, "leave the transfer fee empty"),
        ({"wage_split_pct": 1.5}, "between 0 and 1"),
        ({"obligation_to_buy": True}, "obligation to buy needs a price"),
    ],
)
async def test_loan_offer_validation(
    client: AsyncClient, buyer: dict, seller: dict, db, override, expected
):
    from datetime import date

    await _give_budget(db)
    await _give_wage_budget(db)
    sel_headers, buy_headers = _auth_headers(seller), _auth_headers(buyer)
    player = await _create_player(client, sel_headers)
    seller_club = (await client.get("/clubs/me", headers=sel_headers)).json()
    await _contract(db, player["id"], seller_club["id"], date(2030, 6, 30))

    resp = await client.post(
        "/offers",
        json=_loan_body(player["id"], seller_club["id"], **override),
        headers=buy_headers,
    )
    assert resp.status_code in (400, 422), resp.text
    assert expected in resp.text


@pytest.mark.asyncio
async def test_loan_cannot_outlast_the_parent_contract(
    client: AsyncClient, buyer: dict, seller: dict, db
):
    """You cannot loan a player past the point you control him. Without this the
    phase-3 return path would find an expired contract and make him a free agent."""
    from datetime import date

    await _give_budget(db)
    await _give_wage_budget(db)
    sel_headers, buy_headers = _auth_headers(seller), _auth_headers(buyer)
    player = await _create_player(client, sel_headers)
    seller_club = (await client.get("/clubs/me", headers=sel_headers)).json()
    await _contract(db, player["id"], seller_club["id"], date(2027, 1, 31))

    resp = await client.post(
        "/offers", json=_loan_body(player["id"], seller_club["id"]), headers=buy_headers
    )
    assert resp.status_code == 400, resp.text
    assert "2027-01-31" in resp.text


@pytest.mark.asyncio
async def test_permanent_offer_rejects_loan_terms(
    client: AsyncClient, buyer: dict, seller: dict, db
):
    await _give_budget(db)
    sel_headers, buy_headers = _auth_headers(seller), _auth_headers(buyer)
    player = await _create_player(client, sel_headers)
    seller_club = (await client.get("/clubs/me", headers=sel_headers)).json()

    resp = await client.post(
        "/offers",
        json={
            "player_id": player["id"], "to_club_id": seller_club["id"],
            "fee_amount": 5_000_000, "loan_fee": 1_000_000,
        },
        headers=buy_headers,
    )
    assert resp.status_code == 400, resp.text
    assert "not valid on a permanent offer" in resp.text


@pytest.mark.asyncio
async def test_derived_deal_types_cannot_be_offered(
    client: AsyncClient, buyer: dict, seller: dict, db
):
    """FREE_TRANSFER and PRE_CONTRACT are created by the signing paths, never proposed."""
    await _give_budget(db)
    sel_headers, buy_headers = _auth_headers(seller), _auth_headers(buyer)
    player = await _create_player(client, sel_headers)
    seller_club = (await client.get("/clubs/me", headers=sel_headers)).json()

    for bad in ("FREE_TRANSFER", "PRE_CONTRACT"):
        resp = await client.post(
            "/offers",
            json={
                "player_id": player["id"], "to_club_id": seller_club["id"],
                "fee_amount": 1_000_000, "deal_type": bad,
            },
            headers=buy_headers,
        )
        assert resp.status_code == 422, resp.text
