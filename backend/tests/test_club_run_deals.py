"""Clubs run a deal end to end: auction deals, and personal-terms consent
recorded by the buying club for a player with no account or agent (ADR 0006)."""

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from tests.conftest import _auth_headers, _register
from tests.test_deals import _create_deal_via_offer, _create_player_for_seller, _get_club_id, _give_budget


@pytest_asyncio.fixture
async def buyer(client: AsyncClient) -> dict:
    return await _register(client, "buyer_run@test.com", club_name="Run Buyer FC")


@pytest_asyncio.fixture
async def seller(client: AsyncClient) -> dict:
    return await _register(client, "seller_run@test.com", club_name="Run Seller FC")


@pytest_asyncio.fixture
async def rival(client: AsyncClient) -> dict:
    return await _register(client, "rival_run@test.com", club_name="Run Rival FC")


async def _audit(db, entity_id: str, action: str):
    from app.audit.models import AuditEvent

    return (await db.execute(
        select(AuditEvent).where(AuditEvent.entity_id == uuid.UUID(entity_id), AuditEvent.action == action)
    )).scalars().all()


async def _deal_at_personal_terms(client, buyer, seller, db) -> str:
    deal = await _create_deal_via_offer(client, buyer, seller, db)
    resp = await client.post(f"/deals/{deal['id']}/advance", headers=_auth_headers(buyer))
    assert resp.status_code == 200, resp.text
    assert resp.json()["stage"] == "PERSONAL_TERMS"
    return deal["id"]


async def _propose_terms(client, buyer, deal_id):
    resp = await client.put(
        f"/deals/{deal_id}/personal-terms", json={"wage_weekly": 50000, "length_years": 3},
        headers=_auth_headers(buyer),
    )
    assert resp.status_code == 200, resp.text


# ── Consent recorded by the buying club ──────────────────────────────────────


@pytest.mark.asyncio
async def test_buying_club_records_consent_for_unrepresented_player(client, buyer, seller, db):
    deal_id = await _deal_at_personal_terms(client, buyer, seller, db)
    await _propose_terms(client, buyer, deal_id)

    resp = await client.post(
        f"/deals/{deal_id}/personal-terms/player-consent", json={"agreement": "AGREED"},
        headers=_auth_headers(buyer),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["player_consent"] == "AGREED"

    # Audited as the club's record, not the player's own consent.
    events = await _audit(db, deal_id, "PERSONAL_TERMS_CONSENT")
    assert events and events[-1].payload_json["recorded_by"] == "BUYING_CLUB"

    advanced = await client.post(f"/deals/{deal_id}/advance", headers=_auth_headers(buyer))
    assert advanced.status_code == 200, advanced.text
    assert advanced.json()["stage"] == "PAPERWORK"


@pytest.mark.asyncio
async def test_seller_and_third_club_cannot_record_consent(client, buyer, seller, rival, db):
    deal_id = await _deal_at_personal_terms(client, buyer, seller, db)
    await _propose_terms(client, buyer, deal_id)
    for club in (seller, rival):
        resp = await client.post(
            f"/deals/{deal_id}/personal-terms/player-consent", json={"agreement": "AGREED"},
            headers=_auth_headers(club),
        )
        assert resp.status_code in (403, 404), resp.text
    deal = (await client.get(f"/deals/{deal_id}", headers=_auth_headers(buyer))).json()
    assert deal["personal_terms"]["player_consent"] == "PENDING"


@pytest.mark.asyncio
async def test_cannot_advance_before_consent(client, buyer, seller, db):
    deal_id = await _deal_at_personal_terms(client, buyer, seller, db)
    await _propose_terms(client, buyer, deal_id)
    resp = await client.post(f"/deals/{deal_id}/advance", headers=_auth_headers(buyer))
    assert resp.status_code == 400
    assert "consent" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_collapsed_deal_refuses_terms_and_consent(client, buyer, seller, db):
    """Regression: a collapsed deal keeps its stage, and the stage check alone
    let terms be proposed and consented to after it fell through."""
    deal_id = await _deal_at_personal_terms(client, buyer, seller, db)
    await _propose_terms(client, buyer, deal_id)
    collapse = await client.post(f"/deals/{deal_id}/collapse", headers=_auth_headers(seller))
    assert collapse.status_code == 200, collapse.text

    terms = await client.put(
        f"/deals/{deal_id}/personal-terms", json={"wage_weekly": 60000}, headers=_auth_headers(buyer)
    )
    assert terms.status_code == 400
    consent = await client.post(
        f"/deals/{deal_id}/personal-terms/player-consent", json={"agreement": "AGREED"},
        headers=_auth_headers(buyer),
    )
    assert consent.status_code == 400


# ── Auction deals run by the clubs ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_accepted_bid_releases_rival_offers_and_clubs_advance(client, buyer, seller, rival, db):
    await _give_budget(db)
    sel_headers = _auth_headers(seller)
    player = await _create_player_for_seller(client, sel_headers)
    seller_club_id = await _get_club_id(client, sel_headers)

    sale = await client.post(
        "/sales", json={"player_id": player["id"], "sale_type": "AUCTION", "asking_price": 5_000_000},
        headers=sel_headers,
    )
    assert sale.status_code == 201, sale.text
    sale_id = sale.json()["id"]

    # A rival approaches the seller directly, outside the auction.
    rival_offer = await client.post(
        "/offers", json={"player_id": player["id"], "to_club_id": seller_club_id, "fee_amount": 4_000_000},
        headers=_auth_headers(rival),
    )
    assert rival_offer.status_code == 201, rival_offer.text
    rival_before = (await client.get("/clubs/me", headers=_auth_headers(rival))).json()["finance"]

    bid = await client.post(f"/sales/{sale_id}/bids", json={"amount": 6_000_000}, headers=_auth_headers(buyer))
    assert bid.status_code == 201, bid.text
    deal = await client.post(f"/sales/{sale_id}/bids/{bid.json()['id']}/accept", headers=sel_headers)
    assert deal.status_code == 200, deal.text
    deal_id = deal.json()["id"]

    # The rival's offer is closed and its reservation released.
    offer = (await client.get(f"/offers/{rival_offer.json()['id']}", headers=_auth_headers(rival))).json()
    assert offer["status"] == "REJECTED"
    rival_after = (await client.get("/clubs/me", headers=_auth_headers(rival))).json()["finance"]
    assert float(rival_after["transfer_reserved"]) < float(rival_before["transfer_reserved"])

    assert await _audit(db, deal_id, "DEAL_CREATED")

    # No staff needed: the buying club moves the deal on.
    advanced = await client.post(f"/deals/{deal_id}/advance", headers=_auth_headers(buyer))
    assert advanced.status_code == 200, advanced.text
    assert advanced.json()["stage"] == "PERSONAL_TERMS"
