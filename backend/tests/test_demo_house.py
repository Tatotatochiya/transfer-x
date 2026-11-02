"""House clubs acting on their own in demos (app/demo/house.py)."""
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import settings
from tests.conftest import _auth_headers, _register
from tests.test_deals import _create_player_for_seller, _get_club_id, _give_budget
from tests.test_demo import _house, _staff, _start

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def demo_on(monkeypatch):
    monkeypatch.setattr(settings, "demo_enabled", True)


def test_the_decision_follows_the_personality():
    from app.demo.house import decide

    m = Decimal(1_000_000)
    assert decide(10 * m, 10 * m, "fair", 0)[0] == "accept"
    action, ask, _ = decide(8 * m, 10 * m, "fair", 0)
    assert (action, ask) == ("counter", 10 * m)
    assert decide(6 * m, 10 * m, "fair", 0)[0] == "reject"  # below 70%: walks away
    assert decide(10 * m, 10 * m, "hard", 0) == ("counter", 12 * m, "We'd do it for £12m.")
    assert decide(9 * m, 10 * m, "eager", 0)[0] == "accept"
    # After two counters: the midpoint or nothing.
    assert decide(Decimal("8.5") * m, 10 * m, "fair", 2)[0] == "accept"
    assert decide(Decimal("7.5") * m, 10 * m, "fair", 2)[0] == "reject"
    # A counter is always above the offer, and loans are taken.
    assert decide(Decimal("9.6") * m, 10 * m, "hard", 0)[1] == 12 * m
    assert decide(None, None, "fair", 0, loan=True)[0] == "accept"
    # No price to judge by: a hard or fair club asks for more once, an eager one takes it.
    assert decide(5 * m, None, "hard", 0) == ("counter", Decimal("6.5") * m, "We'd do it for £6.5m.")
    assert decide(5 * m, None, "hard", 1)[0] == "accept"
    assert decide(5 * m, None, "eager", 0)[0] == "accept"


@pytest_asyncio.fixture
async def demo(client: AsyncClient, db, db_engine) -> dict:
    from app.auth.models import User
    from app.valuation.models import PlayerValuation, ValuationConfidence

    tester = await _register(client, "h_tester@demo-example.com", club_name="Tester Town")
    house = await _register(client, "h_house@demo-example.com", club_name="House Rovers")
    house["email"] = "h_house@demo-example.com"
    await _staff(client, db, "h_staff@demo-example.com")
    await _give_budget(db)
    (await db.execute(select(User).where(User.email == "h_tester@demo-example.com"))).scalar_one().can_demo = True
    await db.commit()
    club = await _house(db, house)
    player = await _create_player_for_seller(client, _auth_headers(house))
    db.add(PlayerValuation(player_id=uuid.UUID(player["id"]), fair_value=Decimal(10_000_000),
                           fair_value_low=Decimal(8_000_000), fair_value_high=Decimal(12_000_000),
                           performance_score=Decimal("60"), confidence=list(ValuationConfidence)[0],
                           model_version="test", league_tier=1, age_factor=Decimal("1")))
    await db.commit()
    return {"tester": tester, "h": _auth_headers(tester), "house": house, "club": club, "player": player,
            "house_id": await _get_club_id(client, _auth_headers(house)),
            "factory": async_sessionmaker(db_engine, expire_on_commit=False)}


async def _tick(demo) -> int:
    from app.demo.house import tick

    return await tick(demo["factory"])


async def _offer(client, demo, fee) -> dict:
    resp = await client.post("/offers", headers=demo["h"], json={
        "player_id": demo["player"]["id"], "to_club_id": demo["house_id"], "fee_amount": fee})
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_a_house_club_counters_then_accepts_and_does_its_side_of_the_deal(client: AsyncClient, db, demo):
    from app.deals.models import Deal
    from app.offers.models import Offer, OfferMessage

    await _start(client, demo["tester"])
    offer = await _offer(client, demo, 8_000_000)
    assert await _tick(demo) == 1
    db.expire_all()
    row = await db.get(Offer, uuid.UUID(offer["id"]))
    assert row.status.value == "COUNTERED" and row.fee_amount == Decimal(10_000_000)
    messages = (await db.execute(select(OfferMessage).where(OfferMessage.offer_id == row.id))).scalars().all()
    assert any(m.body.startswith("Automated (demo): We'd do it for £10m") for m in messages)
    assert await _tick(demo) == 0  # waiting on the tester now

    accepted = await client.post(f"/offers/{offer['id']}/accept", headers=demo["h"])
    assert accepted.status_code == 200, accepted.text
    deal = (await db.execute(select(Deal).where(Deal.player_id == uuid.UUID(demo["player"]["id"])))).scalar_one()
    deal_id = str(deal.id)

    # The buyer's own steps stay with the tester; the player agrees terms.
    assert (await client.post(f"/deals/{deal_id}/advance", headers=demo["h"])).json()["stage"] == "PERSONAL_TERMS"
    r = await client.put(f"/deals/{deal_id}/personal-terms", headers=demo["h"],
                         json={"wage_weekly": 50000, "signing_bonus": 100000, "length_years": 4})
    assert r.status_code == 200, r.text
    assert await _tick(demo) == 1
    r = await client.post(f"/deals/{deal_id}/advance", headers=demo["h"])
    assert r.json()["stage"] == "PAPERWORK", r.text
    assert await _tick(demo) == 1  # the house club signs its side
    db.expire_all()
    deal = await db.get(Deal, uuid.UUID(deal_id))
    assert deal.agreement_signed_by_seller_at is not None and deal.agreement_signed_by_buyer_at is None

    # Reset undoes the house club's moves with the tester's.
    report = (await client.post("/demo/run/reset", headers=demo["h"])).json()
    assert report["skipped"] == []
    db.expire_all()
    assert (await db.execute(select(Deal))).scalars().all() == []
    assert (await db.execute(select(Offer))).scalars().all() == []


async def test_a_lowball_is_turned_down_and_a_fair_offer_taken(client: AsyncClient, db, demo):
    from app.offers.models import Offer

    await _start(client, demo["tester"])
    low = await _offer(client, demo, 3_000_000)
    await _tick(demo)
    db.expire_all()
    assert (await db.get(Offer, uuid.UUID(low["id"]))).status.value == "REJECTED"
    fair = await _offer(client, demo, 10_000_000)
    await _tick(demo)
    db.expire_all()
    assert (await db.get(Offer, uuid.UUID(fair["id"]))).status.value == "ACCEPTED"


async def test_realistic_speed_waits_and_real_offers_are_left_alone(client: AsyncClient, db, demo):
    from app.offers.models import Offer

    # Outside a demo, nothing answers for the house club.
    real = await _offer(client, demo, 10_000_000)
    assert await _tick(demo) == 0
    await client.post(f"/offers/{real['id']}/withdraw", headers=demo["h"])

    await _start(client, demo["tester"])
    assert (await client.patch("/demo/run", headers=demo["h"], json={"speed": "realistic"})).json()["speed"] == "realistic"
    assert (await client.patch("/demo/run", headers=demo["h"], json={"speed": "fast"})).status_code == 422
    offer = await _offer(client, demo, 10_000_000)
    assert await _tick(demo) == 0  # a real club would take its time
    await db.execute(update(Offer).where(Offer.id == uuid.UUID(offer["id"]))
                     .values(last_action_at=datetime.now(timezone.utc) - timedelta(minutes=4)))
    await db.commit()
    assert await _tick(demo) == 1


async def test_an_unused_agent_proposes_commission_then_waits_for_the_buying_club(client: AsyncClient, db, demo):
    from app.agents.models import AgentNegotiation, CommissionPayer
    from app.auth.models import AgentProfile, User
    from app.deals.models import Deal
    from app.mandates.models import Mandate, MandateStatus

    await client.post("/auth/register", json={
        "email": "h_agent@demo-example.com", "password": "password123", "user_type": "AGENT",
        "display_name": "Andy Agent", "agency_name": "Andy Sports", "country": "England"})
    agent_user = (await db.execute(select(User).where(User.email == "h_agent@demo-example.com"))).scalar_one()
    agent_user.last_active_at = None  # nobody uses this agent's account
    profile = (await db.execute(select(AgentProfile).where(AgentProfile.user_id == agent_user.id))).scalar_one()
    db.add(Mandate(agent_id=profile.id, player_id=uuid.UUID(demo["player"]["id"]), status=MandateStatus.ACTIVE))
    await db.commit()

    await _start(client, demo["tester"])
    offer = await _offer(client, demo, 10_000_000)
    await _tick(demo)  # accepted
    deal = (await db.execute(select(Deal).where(Deal.player_id == uuid.UUID(demo["player"]["id"])))).scalar_one()
    assert deal.stage.value == "AGENT_NEGOTIATION"
    deal_id = deal.id
    assert await _tick(demo) == 1
    db.expire_all()
    neg = (await db.execute(select(AgentNegotiation).where(AgentNegotiation.deal_id == deal_id))).scalar_one()
    assert neg.commission_pct == Decimal("0.05") and neg.commission_payer == CommissionPayer.BUYER
    assert neg.commission_amount == Decimal("500000.00")
    assert await _tick(demo) == 0  # the buying club's move: agree or not
    assert offer["id"]
