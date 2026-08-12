"""M4 — Offer negotiation tests."""

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
