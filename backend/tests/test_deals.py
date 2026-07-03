"""M4 — Deal lifecycle tests."""

import uuid
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient

from tests.conftest import _auth_headers, _register


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def buyer(client: AsyncClient) -> dict:
    return await _register(client, "buyer_deal@test.com", club_name="Deal Buyer FC")


@pytest_asyncio.fixture
async def seller(client: AsyncClient) -> dict:
    return await _register(client, "seller_deal@test.com", club_name="Deal Seller FC")


async def _give_budget(db, amount: Decimal = Decimal("100000000")):
    from app.clubs.models import ClubFinance
    from sqlalchemy import select

    result = await db.execute(select(ClubFinance))
    for f in result.scalars():
        f.transfer_budget_total = amount
    await db.commit()


async def _create_player_for_seller(client: AsyncClient, seller_headers: dict) -> dict:
    resp = await client.post("/players", json={"name": "Deal Player", "position": "FWD"}, headers=seller_headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _get_club_id(client: AsyncClient, headers: dict) -> str:
    resp = await client.get("/clubs/me", headers=headers)
    return resp.json()["id"]


async def _create_deal_via_offer(
    client: AsyncClient,
    buyer: dict,
    seller: dict,
    db,
    fee: float = 5_000_000,
) -> dict:
    """Create a deal by making and accepting an offer."""
    await _give_budget(db)
    sel_headers = _auth_headers(seller)
    buy_headers = _auth_headers(buyer)
    player = await _create_player_for_seller(client, sel_headers)
    seller_club_id = await _get_club_id(client, sel_headers)

    offer_resp = await client.post(
        "/offers",
        json={"player_id": player["id"], "to_club_id": seller_club_id, "fee_amount": fee},
        headers=buy_headers,
    )
    offer_id = offer_resp.json()["id"]

    deal_resp = await client.post(f"/offers/{offer_id}/accept", headers=sel_headers)
    assert deal_resp.status_code == 200, deal_resp.text
    return deal_resp.json()


async def _create_deal_via_bid(
    client: AsyncClient,
    buyer: dict,
    seller: dict,
    db,
) -> dict:
    """Create a deal by placing and accepting a bid on an auction."""
    await _give_budget(db)
    sel_headers = _auth_headers(seller)
    buy_headers = _auth_headers(buyer)
    player = await _create_player_for_seller(client, sel_headers)

    sale_resp = await client.post(
        "/sales",
        json={"player_id": player["id"], "sale_type": "AUCTION", "asking_price": 5_000_000},
        headers=sel_headers,
    )
    sale_id = sale_resp.json()["id"]

    bid_resp = await client.post(
        f"/sales/{sale_id}/bids", json={"amount": 5_000_000}, headers=buy_headers
    )
    bid_id = bid_resp.json()["id"]

    deal_resp = await client.post(f"/sales/{sale_id}/bids/{bid_id}/accept", headers=sel_headers)
    assert deal_resp.status_code == 200, deal_resp.text
    return deal_resp.json()


async def _register_player_account(client: AsyncClient, email: str, player_id: str) -> dict:
    resp = await client.post("/auth/register", json={
        "email": email, "password": "password123",
        "user_type": "PLAYER", "player_id": player_id,
    })
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _advance_through_personal_terms(
    client: AsyncClient, deal_id: str, buyer: dict, db,
) -> None:
    """Advance a deal from AGREEMENT through PERSONAL_TERMS to PAPERWORK.

    No player account exists in the generic `buyer`/`seller` fixtures, so
    consent here goes through a dedicated, throwaway superuser account rather
    than a real player. Deliberately does NOT touch buyer/seller's own
    superuser status — callers like test_paperwork_stage_blocked_for_clubs
    rely on them staying regular (non-staff) club accounts afterward. Real
    player consent is covered separately by
    test_player_can_consent_to_personal_terms_without_agent below.
    """
    from app.auth.models import User
    from sqlalchemy import select

    buy_h = _auth_headers(buyer)
    r = await client.post(f"/deals/{deal_id}/advance", headers=buy_h)
    assert r.json()["stage"] == "PERSONAL_TERMS", r.text

    r = await client.put(
        f"/deals/{deal_id}/personal-terms",
        json={"wage_weekly": 50000, "signing_bonus": 100000, "length_years": 4},
        headers=buy_h,
    )
    assert r.status_code == 200, r.text

    consent_email = f"consent-staff-{uuid.uuid4()}@test.com"
    consent_tokens = await _register(client, consent_email)
    result = await db.execute(select(User).where(User.email == consent_email))
    result.scalar_one().is_superuser = True
    await db.commit()

    r = await client.post(
        f"/deals/{deal_id}/personal-terms/player-consent",
        json={"agreement": "AGREED"},
        headers=_auth_headers(consent_tokens),
    )
    assert r.status_code == 200, r.text

    r = await client.post(f"/deals/{deal_id}/advance", headers=buy_h)
    assert r.json()["stage"] == "PAPERWORK", r.text


# ── Deal retrieval ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_deal_accessible_to_buyer(client: AsyncClient, buyer: dict, seller: dict, db):
    deal = await _create_deal_via_offer(client, buyer, seller, db)
    resp = await client.get(f"/deals/{deal['id']}", headers=_auth_headers(buyer))
    assert resp.status_code == 200
    assert resp.json()["status"] == "IN_PROGRESS"


@pytest.mark.asyncio
async def test_deal_accessible_to_seller(client: AsyncClient, buyer: dict, seller: dict, db):
    deal = await _create_deal_via_offer(client, buyer, seller, db)
    resp = await client.get(f"/deals/{deal['id']}", headers=_auth_headers(seller))
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_deal_list_for_club(client: AsyncClient, buyer: dict, seller: dict, db):
    await _create_deal_via_offer(client, buyer, seller, db)
    resp = await client.get("/deals", headers=_auth_headers(buyer))
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


# ── Stage advancement ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_advance_agreement_to_personal_terms(client: AsyncClient, buyer: dict, seller: dict, db):
    """TRA-60 regression: AGREEMENT must route to PERSONAL_TERMS, not skip straight
    to PAPERWORK — a deal with no agent still owes the player a consent step."""
    deal = await _create_deal_via_offer(client, buyer, seller, db)
    resp = await client.post(f"/deals/{deal['id']}/advance", headers=_auth_headers(buyer))
    assert resp.status_code == 200
    assert resp.json()["stage"] == "PERSONAL_TERMS"


@pytest.mark.asyncio
async def test_cannot_skip_personal_terms_consent(client: AsyncClient, buyer: dict, seller: dict, db):
    """TRA-60 regression: without player consent, a deal cannot reach PAPERWORK —
    previously a single /advance call took AGREEMENT straight to PAPERWORK."""
    deal = await _create_deal_via_offer(client, buyer, seller, db)
    buy_h = _auth_headers(buyer)

    r = await client.post(f"/deals/{deal['id']}/advance", headers=buy_h)
    assert r.json()["stage"] == "PERSONAL_TERMS"

    # No personal terms have been proposed yet — advancing again must fail.
    r = await client.post(f"/deals/{deal['id']}/advance", headers=buy_h)
    assert r.status_code == 400
    assert "personal terms" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_paperwork_stage_blocked_for_clubs(client: AsyncClient, buyer: dict, seller: dict, db):
    """Clubs cannot advance past PAPERWORK — only staff can."""
    deal = await _create_deal_via_offer(client, buyer, seller, db)
    await _advance_through_personal_terms(client, deal["id"], buyer, db)

    # Try to advance again as club — should get 403
    resp = await client.post(f"/deals/{deal['id']}/advance", headers=_auth_headers(buyer))
    assert resp.status_code == 403
    assert "paperwork" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_full_stage_progression_via_staff(client: AsyncClient, buyer: dict, seller: dict, db):
    """Staff can complete all stages including PAPERWORK."""
    deal = await _create_deal_via_offer(client, buyer, seller, db)
    deal_id = deal["id"]

    # AGREEMENT → PERSONAL_TERMS → PAPERWORK
    await _advance_through_personal_terms(client, deal_id, buyer, db)

    # Register an admin/superuser for the staff-only step below
    await _make_superuser(db)

    # PAPERWORK → CONFIRMED (staff — use buyer who is now superuser)
    r = await client.post(f"/deals/{deal_id}/advance", headers=_auth_headers(buyer))
    assert r.json()["stage"] == "CONFIRMED"

    # CONFIRMED → COMPLETED
    r = await client.post(f"/deals/{deal_id}/advance", headers=_auth_headers(buyer))
    assert r.json()["stage"] == "COMPLETED"
    assert r.json()["status"] == "COMPLETED"


# ── Personal terms without an agent (TRA-60) ────────────────────────────────────


@pytest.mark.asyncio
async def test_buying_club_can_set_personal_terms(client: AsyncClient, buyer: dict, seller: dict, db):
    """With no mandated agent, the buying club proposes personal terms directly."""
    deal = await _create_deal_via_offer(client, buyer, seller, db)
    buy_h = _auth_headers(buyer)
    await client.post(f"/deals/{deal['id']}/advance", headers=buy_h)

    resp = await client.put(
        f"/deals/{deal['id']}/personal-terms",
        json={"wage_weekly": 60000, "signing_bonus": 250000, "length_years": 3},
        headers=buy_h,
    )
    assert resp.status_code == 200, resp.text
    assert Decimal(resp.json()["wage_weekly"]) == Decimal("60000")
    assert resp.json()["player_consent"] == "PENDING"


@pytest.mark.asyncio
async def test_seller_cannot_set_personal_terms(client: AsyncClient, buyer: dict, seller: dict, db):
    """Only the buying club (who is signing the player) can propose terms — not the seller."""
    deal = await _create_deal_via_offer(client, buyer, seller, db)
    await client.post(f"/deals/{deal['id']}/advance", headers=_auth_headers(buyer))

    resp = await client.put(
        f"/deals/{deal['id']}/personal-terms",
        json={"wage_weekly": 60000},
        headers=_auth_headers(seller),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_player_can_consent_to_personal_terms_without_agent(
    client: AsyncClient, buyer: dict, seller: dict, db,
):
    """TRA-60 end-to-end: with no agent involved, the buying club proposes terms
    and the actual player (their own account, not a staff override) consents."""
    deal = await _create_deal_via_offer(client, buyer, seller, db)
    buy_h = _auth_headers(buyer)

    r = await client.post(f"/deals/{deal['id']}/advance", headers=buy_h)
    assert r.json()["stage"] == "PERSONAL_TERMS"

    r = await client.put(
        f"/deals/{deal['id']}/personal-terms",
        json={"wage_weekly": 70000, "signing_bonus": 0, "length_years": 5},
        headers=buy_h,
    )
    assert r.status_code == 200, r.text

    player_tokens = await _register_player_account(client, "player_terms@test.com", deal["player_id"])
    player_h = _auth_headers(player_tokens)

    r = await client.post(
        f"/deals/{deal['id']}/personal-terms/player-consent",
        json={"agreement": "AGREED"},
        headers=player_h,
    )
    assert r.status_code == 200, r.text
    assert r.json()["player_consent"] == "AGREED"

    r = await client.post(f"/deals/{deal['id']}/advance", headers=buy_h)
    assert r.json()["stage"] == "PAPERWORK"


@pytest.mark.asyncio
async def test_player_decline_collapses_deal(client: AsyncClient, buyer: dict, seller: dict, db):
    """A player declining personal terms collapses the deal, same as the agent path."""
    deal = await _create_deal_via_offer(client, buyer, seller, db)
    buy_h = _auth_headers(buyer)
    await client.post(f"/deals/{deal['id']}/advance", headers=buy_h)
    await client.put(
        f"/deals/{deal['id']}/personal-terms",
        json={"wage_weekly": 70000},
        headers=buy_h,
    )

    player_tokens = await _register_player_account(client, "player_decline@test.com", deal["player_id"])
    resp = await client.post(
        f"/deals/{deal['id']}/personal-terms/player-consent",
        json={"agreement": "DECLINED"},
        headers=_auth_headers(player_tokens),
    )
    assert resp.status_code == 200, resp.text

    deal_check = await client.get(f"/deals/{deal['id']}", headers=buy_h)
    assert deal_check.json()["status"] == "COLLAPSED"


# ── Collapse deal ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_collapse_deal(client: AsyncClient, buyer: dict, seller: dict, db):
    deal = await _create_deal_via_offer(client, buyer, seller, db)
    resp = await client.post(f"/deals/{deal['id']}/collapse", headers=_auth_headers(buyer))
    assert resp.status_code == 200
    assert resp.json()["status"] == "COLLAPSED"


@pytest.mark.asyncio
async def test_cannot_collapse_completed_deal(client: AsyncClient, buyer: dict, seller: dict, db):
    deal = await _create_deal_via_offer(client, buyer, seller, db)

    # Make everyone superuser to complete the deal quickly
    from app.auth.models import User
    from sqlalchemy import select

    result = await db.execute(select(User))
    for u in result.scalars():
        u.is_superuser = True
    await db.commit()

    await client.post(f"/deals/{deal['id']}/staff/complete", headers=_auth_headers(buyer))
    resp = await client.post(f"/deals/{deal['id']}/collapse", headers=_auth_headers(buyer))
    assert resp.status_code == 400


# ── Deal notes ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_add_note_to_deal(client: AsyncClient, buyer: dict, seller: dict, db):
    deal = await _create_deal_via_offer(client, buyer, seller, db)
    resp = await client.post(
        f"/deals/{deal['id']}/notes",
        json={"body": "Awaiting medical clearance"},
        headers=_auth_headers(buyer),
    )
    assert resp.status_code == 201
    assert resp.json()["body"] == "Awaiting medical clearance"


@pytest.mark.asyncio
async def test_deal_notes_visible_in_detail(client: AsyncClient, buyer: dict, seller: dict, db):
    deal = await _create_deal_via_offer(client, buyer, seller, db)
    await client.post(
        f"/deals/{deal['id']}/notes",
        json={"body": "Note one"},
        headers=_auth_headers(buyer),
    )
    await client.post(
        f"/deals/{deal['id']}/notes",
        json={"body": "Note two"},
        headers=_auth_headers(seller),
    )
    resp = await client.get(f"/deals/{deal['id']}", headers=_auth_headers(buyer))
    assert len(resp.json()["deal_notes"]) == 2


# ── Staff endpoints ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_staff_complete_deal(client: AsyncClient, buyer: dict, seller: dict, db):
    deal = await _create_deal_via_offer(client, buyer, seller, db)

    from app.auth.models import User
    from sqlalchemy import select

    result = await db.execute(select(User))
    for u in result.scalars():
        u.is_superuser = True
    await db.commit()

    resp = await client.post(f"/deals/{deal['id']}/staff/complete", headers=_auth_headers(buyer))
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "COMPLETED"
    assert data["stage"] == "COMPLETED"


@pytest.mark.asyncio
async def test_non_staff_cannot_use_staff_endpoints(client: AsyncClient, buyer: dict, seller: dict, db):
    deal = await _create_deal_via_offer(client, buyer, seller, db)
    resp = await client.post(f"/deals/{deal['id']}/staff/complete", headers=_auth_headers(buyer))
    assert resp.status_code == 403


# ── Auction deal ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_auction_deal_is_flagged(client: AsyncClient, buyer: dict, seller: dict, db):
    deal = await _create_deal_via_bid(client, buyer, seller, db)
    resp = await client.get(f"/deals/{deal['id']}", headers=_auth_headers(buyer))
    assert resp.json()["is_auction_deal"] is True


@pytest.mark.asyncio
async def test_offer_deal_not_flagged_as_auction(client: AsyncClient, buyer: dict, seller: dict, db):
    deal = await _create_deal_via_offer(client, buyer, seller, db)
    resp = await client.get(f"/deals/{deal['id']}", headers=_auth_headers(buyer))
    assert resp.json()["is_auction_deal"] is False


# ── Finance settlement tests (TRA-51) ──────────────────────────────────────────


async def _give_wage_budget(db, amount: Decimal = Decimal("1000000")):
    from app.clubs.models import ClubFinance
    from sqlalchemy import select

    result = await db.execute(select(ClubFinance))
    for f in result.scalars():
        f.wage_budget_total_weekly = amount
    await db.commit()


async def _get_finance(client: AsyncClient, headers: dict) -> dict:
    r = await client.get("/clubs/me", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["finance"]


async def _make_superuser(db) -> None:
    from app.auth.models import User
    from sqlalchemy import select

    result = await db.execute(select(User))
    for u in result.scalars():
        u.is_superuser = True
    await db.commit()


async def _staff_complete(client: AsyncClient, deal_id: str, headers: dict) -> dict:
    r = await client.post(f"/deals/{deal_id}/staff/complete", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.asyncio
async def test_completion_settles_buyer_transfer_finance(
    client: AsyncClient, buyer: dict, seller: dict, db
):
    """Fee moves from transfer_committed → transfer_spent; remaining is unchanged."""
    deal = await _create_deal_via_offer(client, buyer, seller, db, fee=5_000_000)
    buy_h = _auth_headers(buyer)

    before = await _get_finance(client, buy_h)
    await _make_superuser(db)
    await _staff_complete(client, deal["id"], buy_h)
    after = await _get_finance(client, buy_h)

    fee = Decimal("5000000")
    assert Decimal(before["transfer_committed"]) - Decimal(after["transfer_committed"]) == fee
    assert Decimal(after["transfer_spent"]) - Decimal(before["transfer_spent"]) == fee
    # remaining is unchanged — committed→spent nets to zero
    assert Decimal(after["transfer_remaining"]) == Decimal(before["transfer_remaining"])


@pytest.mark.asyncio
async def test_completion_credits_seller_transfer_finance(
    client: AsyncClient, buyer: dict, seller: dict, db
):
    """Seller's transfer_budget_total rises by the agreed fee on completion."""
    deal = await _create_deal_via_offer(client, buyer, seller, db, fee=5_000_000)
    sel_h = _auth_headers(seller)

    before = await _get_finance(client, sel_h)
    await _make_superuser(db)
    await _staff_complete(client, deal["id"], _auth_headers(buyer))
    after = await _get_finance(client, sel_h)

    fee = Decimal("5000000")
    assert Decimal(after["transfer_remaining"]) - Decimal(before["transfer_remaining"]) == fee


@pytest.mark.asyncio
async def test_money_conservation_on_completion(
    client: AsyncClient, buyer: dict, seller: dict, db
):
    """Σ(transfer_budget_total − transfer_spent) is conserved across both clubs."""
    deal = await _create_deal_via_offer(client, buyer, seller, db, fee=5_000_000)
    buy_h, sel_h = _auth_headers(buyer), _auth_headers(seller)

    buyer_before = await _get_finance(client, buy_h)
    seller_before = await _get_finance(client, sel_h)

    await _make_superuser(db)
    await _staff_complete(client, deal["id"], buy_h)

    buyer_after = await _get_finance(client, buy_h)
    seller_after = await _get_finance(client, sel_h)

    def liquid(f):
        return Decimal(f["transfer_budget_total"]) - Decimal(f["transfer_spent"])

    assert liquid(buyer_before) + liquid(seller_before) == liquid(buyer_after) + liquid(seller_after)


@pytest.mark.asyncio
async def test_completion_settles_buyer_wage(
    client: AsyncClient, buyer: dict, seller: dict, db
):
    """agreed_wage_weekly ends up in the buyer's wage_reserved_weekly on completion."""
    from app.deals.models import Deal
    from sqlalchemy import update as sa_update

    deal = await _create_deal_via_offer(client, buyer, seller, db, fee=5_000_000)
    await _give_wage_budget(db)

    wage = Decimal("50000")
    await db.execute(
        sa_update(Deal).where(Deal.id == uuid.UUID(deal["id"])).values(agreed_wage_weekly=wage)
    )
    await db.commit()

    buy_h = _auth_headers(buyer)
    before = await _get_finance(client, buy_h)
    await _make_superuser(db)
    await _staff_complete(client, deal["id"], buy_h)
    after = await _get_finance(client, buy_h)

    assert Decimal(after["wage_reserved_weekly"]) - Decimal(before["wage_reserved_weekly"]) == wage


@pytest.mark.asyncio
async def test_completion_releases_seller_wage(
    client: AsyncClient, buyer: dict, seller: dict, db
):
    """Seller's wage_reserved_weekly drops by the departing player's wage on completion."""
    from app.clubs.models import ClubFinance
    from app.players.models import Player
    from app.players import service as players_service
    from sqlalchemy import select

    deal = await _create_deal_via_offer(client, buyer, seller, db, fee=5_000_000)
    await _give_wage_budget(db)

    # Fetch the player and create an active contract at a known wage.
    old_wage = Decimal("40000")
    player_result = await db.execute(select(Player).where(Player.id == uuid.UUID(deal["player_id"])))
    player = player_result.scalar_one()

    sel_club_r = await client.get("/clubs/me", headers=_auth_headers(seller))
    seller_club_id = sel_club_r.json()["id"]

    # create_contract doesn't touch finance — seed wage_reserved_weekly manually
    # to simulate that the seller had this wage reserved before completion.
    await players_service.create_contract(
        db, player=player, club_id=uuid.UUID(seller_club_id), wage_weekly=old_wage
    )
    seller_fin = (
        await db.execute(select(ClubFinance).where(ClubFinance.club_id == uuid.UUID(seller_club_id)))
    ).scalar_one()
    seller_fin.wage_reserved_weekly = old_wage
    await db.commit()

    # Snapshot AFTER setup so baseline includes the reserved wage.
    sel_h = _auth_headers(seller)
    before = await _get_finance(client, sel_h)

    await _make_superuser(db)
    await _staff_complete(client, deal["id"], _auth_headers(buyer))
    after = await _get_finance(client, sel_h)

    assert Decimal(before["wage_reserved_weekly"]) - Decimal(after["wage_reserved_weekly"]) == old_wage


@pytest.mark.asyncio
async def test_collapse_releases_committed_budget(
    client: AsyncClient, buyer: dict, seller: dict, db
):
    """Collapse returns the fee from transfer_committed back to transfer_remaining."""
    deal = await _create_deal_via_offer(client, buyer, seller, db, fee=5_000_000)
    buy_h = _auth_headers(buyer)

    before = await _get_finance(client, buy_h)
    await client.post(f"/deals/{deal['id']}/collapse", headers=buy_h)
    after = await _get_finance(client, buy_h)

    fee = Decimal("5000000")
    assert Decimal(after["transfer_remaining"]) - Decimal(before["transfer_remaining"]) == fee
    assert Decimal(after["transfer_committed"]) == Decimal("0")


@pytest.mark.asyncio
async def test_double_complete_is_rejected(
    client: AsyncClient, buyer: dict, seller: dict, db
):
    """Completing an already-completed deal returns HTTP 400."""
    deal = await _create_deal_via_offer(client, buyer, seller, db)
    buy_h = _auth_headers(buyer)
    await _make_superuser(db)

    await _staff_complete(client, deal["id"], buy_h)  # first — succeeds

    r = await client.post(f"/deals/{deal['id']}/staff/complete", headers=buy_h)
    assert r.status_code == 400


# NOTE: Concurrent-completion overspend guard is NOT tested here.
# It requires two parallel DB sessions against a real Postgres instance;
# SQLite ignores SELECT FOR UPDATE so the test would be a false pass.
