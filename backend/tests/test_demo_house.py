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


# ── House clubs as buyers and rivals ─────────────────────────────────────────


def test_a_buying_house_club_meets_halfway_then_walks():
    from app.demo.house import decide_buyer

    m = Decimal(1_000_000)
    assert decide_buyer(10 * m, 10 * m, "fair", 0)[0] == "accept"  # within 105%
    assert decide_buyer(12 * m, 10 * m, "fair", 0)[:2] == ("counter", Decimal("10.5") * m)
    assert decide_buyer(12 * m, 10 * m, "fair", 2)[0] == "withdraw"
    assert decide_buyer(11 * m, 10 * m, "eager", 0)[0] == "accept"  # eager goes to 115%


async def _second_house(client, db, name="House Wanderers") -> dict:
    tokens = await _register(client, f"{name.lower().replace(' ', '_')}@demo-example.com", club_name=name)
    tokens["email"] = f"{name.lower().replace(' ', '_')}@demo-example.com"
    await _give_budget(db)
    await _house(db, tokens)
    return tokens


async def test_house_clubs_bid_for_a_listed_player_and_buy_him(client: AsyncClient, db, demo):
    from app.deals.models import Deal
    from app.offers.models import Offer, OfferMessage
    from app.players.models import Player
    from app.valuation.models import PlayerValuation, ValuationConfidence

    await _second_house(client, db)
    mine = await _create_player_for_seller(client, demo["h"])
    db.add(PlayerValuation(player_id=uuid.UUID(mine["id"]), fair_value=Decimal(10_000_000),
                           fair_value_low=Decimal(8_000_000), fair_value_high=Decimal(12_000_000),
                           performance_score=Decimal("60"), confidence=list(ValuationConfidence)[0],
                           model_version="test", league_tier=1, age_factor=Decimal("1")))
    await db.commit()
    await _start(client, demo["tester"])
    sale = await client.post("/sales", headers=demo["h"], json={
        "player_id": mine["id"], "sale_type": "OPEN_TO_OFFERS", "asking_price": 12_000_000})
    assert sale.status_code == 201, sale.text
    assert await _tick(demo) == 1
    bids = (await db.execute(select(Offer).where(Offer.player_id == uuid.UUID(mine["id"])))).scalars().all()
    assert len(bids) == 2 and all(b.fee_amount >= Decimal(8_000_000) for b in bids)
    assert await _tick(demo) == 0  # bid once; now the tester's move

    bid_id = max(bids, key=lambda b: b.fee_amount).id
    countered = await client.post(f"/offers/{bid_id}/counter", headers=demo["h"], json={"fee_amount": 20_000_000})
    assert countered.status_code == 200, countered.text
    await _tick(demo)
    db.expire_all()
    bid = await db.get(Offer, bid_id)
    assert bid.status.value == "COUNTERED" and bid.fee_amount < Decimal(20_000_000)
    said = [m.body for m in (await db.execute(select(OfferMessage).where(OfferMessage.offer_id == bid_id))).scalars()]
    assert any(b.startswith("Automated (demo): Our best is") for b in said)

    accepted = await client.post(f"/offers/{bid_id}/accept", headers=demo["h"])
    assert accepted.status_code == 200, accepted.text
    deal_id = (await db.execute(select(Deal.id).where(Deal.player_id == uuid.UUID(mine["id"])))).scalar_one()
    # The buying house club works through every step it owns.
    for _ in range(12):
        await _tick(demo)
        db.expire_all()
        deal = await db.get(Deal, deal_id)
        if deal.stage.value == "PAPERWORK" and deal.agreement_signed_by_seller_at is None and deal.agreement_signed_by_buyer_at:
            r = await client.post(f"/deals/{deal_id}/paperwork/sign-agreement", headers=demo["h"])
            assert r.status_code == 200, r.text
        if deal.status.value == "COMPLETED":
            break
    db.expire_all()
    deal = await db.get(Deal, deal_id)
    assert deal.status.value == "COMPLETED"
    house_buyer = deal.buyer_club_id
    assert (await db.get(Player, uuid.UUID(mine["id"]))).current_club_id == house_buyer

    report = (await client.post("/demo/run/reset", headers=demo["h"])).json()
    assert report["skipped"] == []
    db.expire_all()
    assert (await db.get(Player, uuid.UUID(mine["id"]))).current_club_id != house_buyer
    assert (await db.execute(select(Deal))).scalars().all() == []


async def test_a_rival_bids_and_the_seller_asks_the_tester_to_improve(client: AsyncClient, db, demo):
    from app.offers.models import Offer, OfferMessage

    await _second_house(client, db)
    await _start(client, demo["tester"])
    await client.patch("/demo/run", headers=demo["h"], json={"rivals": "always"})
    offer = await _offer(client, demo, 8_000_000)
    mine_id = uuid.UUID(offer["id"])
    await _tick(demo)
    db.expire_all()
    mine = await db.get(Offer, mine_id)
    rivals = [o for o in (await db.execute(select(Offer).where(Offer.player_id == mine.player_id))).scalars()
              if o.id != mine_id]
    assert len(rivals) == 1 and rivals[0].fee_amount > Decimal(8_000_000)
    rival_id, rival_fee = rivals[0].id, rivals[0].fee_amount
    assert mine.status.value == "COUNTERED" and mine.fee_amount > rival_fee
    said = [m.body for m in (await db.execute(select(OfferMessage).where(OfferMessage.offer_id == mine_id))).scalars()]
    assert "Automated (demo): We have a better offer on the table. Can you improve?" in said
    assert not any("House Wanderers" in b for b in said)  # the rival isn't named

    # The tester meets the price: a deal, and the rival's bid is turned down.
    assert (await client.post(f"/offers/{mine_id}/accept", headers=demo["h"])).status_code == 200
    await _tick(demo)
    db.expire_all()
    assert (await db.get(Offer, rival_id)).status.value == "REJECTED"


async def test_two_testers_demos_dont_share_a_player(client: AsyncClient, db, demo):
    from app.auth.models import User

    other = await _register(client, "h_other@demo-example.com", club_name="Other Testers")
    (await db.execute(select(User).where(User.email == "h_other@demo-example.com"))).scalar_one().can_demo = True
    await db.commit()
    await _start(client, demo["tester"])
    await _offer(client, demo, 9_000_000)
    await _start(client, other)
    clash = await client.post("/offers", headers=_auth_headers(other), json={
        "player_id": demo["player"]["id"], "to_club_id": demo["house_id"], "fee_amount": 9_500_000})
    assert clash.status_code == 409 and "another tester's demo" in clash.text


# ── "Make them answer now" ───────────────────────────────────────────────────


async def test_the_tester_can_make_the_house_club_move_now(client: AsyncClient, db, demo):
    from app.auth.models import User
    from app.offers.models import Offer, OfferMessage

    await _start(client, demo["tester"])
    await client.patch("/demo/run", headers=demo["h"], json={"speed": "realistic", "rivals": "never"})
    offer = await _offer(client, demo, 8_000_000)
    oid = offer["id"]
    controls = (await client.get(f"/demo/offers/{oid}", headers=demo["h"])).json()
    assert controls["in_demo"] and controls["house_move"] and controls["house_club"] == "House Rovers"
    assert controls["actions"] == ["accept", "counter", "reject"]

    made = await client.post(f"/demo/offers/{oid}/make", headers=demo["h"], json={"action": "counter", "fee_amount": 15_000_000})
    assert made.status_code == 200, made.text
    db.expire_all()
    row = await db.get(Offer, uuid.UUID(oid))
    assert (row.status.value, row.fee_amount) == ("COUNTERED", Decimal(15_000_000))
    said = [m.body for m in (await db.execute(select(OfferMessage).where(OfferMessage.offer_id == uuid.UUID(oid)))).scalars()]
    assert "Automated (demo, the tester's choice): We'd do it for £15m." in said
    # Now it's the tester's move: nothing to make the house club do.
    assert (await client.get(f"/demo/offers/{oid}", headers=demo["h"])).json()["house_move"] is False
    assert (await client.post(f"/demo/offers/{oid}/make", headers=demo["h"], json={"action": "accept"})).status_code == 409

    # Not someone else's demo offer, nor one outside a demo.
    other = await _register(client, "h_peeker@demo-example.com", club_name="Peekers")
    (await db.execute(select(User).where(User.email == "h_peeker@demo-example.com"))).scalar_one().can_demo = True
    await db.commit()
    await _start(client, other)
    assert (await client.get(f"/demo/offers/{oid}", headers=_auth_headers(other))).json() == {"in_demo": False}
    assert (await client.post(f"/demo/offers/{oid}/make", headers=_auth_headers(other), json={"action": "accept"})).status_code == 404


# ── Agents, the tester's waits, enquiries and reminders ──────────────────────


async def _agent(client, db, demo, *, signed_in: timedelta | None = None):
    """An agent for the house club's player; `signed_in` ago, or never."""
    from app.auth.models import AgentProfile, User
    from app.mandates.models import Mandate, MandateStatus

    email = f"h_agent{uuid.uuid4().hex[:6]}@demo-example.com"
    await client.post("/auth/register", json={
        "email": email, "password": "password123", "user_type": "AGENT",
        "display_name": "Andy Agent", "agency_name": "Andy Sports", "country": "England"})
    user = (await db.execute(select(User).where(User.email == email))).scalar_one()
    user.last_active_at = None if signed_in is None else datetime.now(timezone.utc) - signed_in
    profile = (await db.execute(select(AgentProfile).where(AgentProfile.user_id == user.id))).scalar_one()
    db.add(Mandate(agent_id=profile.id, player_id=uuid.UUID(demo["player"]["id"]), status=MandateStatus.ACTIVE))
    await db.commit()
    return profile


async def _deal_at_terms(client, db, demo) -> str:
    """The tester's offer accepted, the agent's commission agreed: personal terms."""
    from app.deals.models import Deal

    await _start(client, demo["tester"])
    await _offer(client, demo, 10_000_000)
    await _tick(demo)
    deal = (await db.execute(select(Deal).where(Deal.player_id == uuid.UUID(demo["player"]["id"])))).scalar_one()
    deal_id = str(deal.id)
    await _tick(demo)  # the agent proposes his commission
    r = await client.post(f"/deals/{deal_id}/agent-negotiation/club-respond", headers=demo["h"], json={"agreement": "AGREED"})
    assert r.status_code == 200, r.text
    assert (await client.post(f"/deals/{deal_id}/advance", headers=demo["h"])).json()["stage"] == "PERSONAL_TERMS"
    return deal_id


async def test_the_agent_prepares_personal_terms_and_agrees_them_for_the_player(client: AsyncClient, db, demo):
    from app.deals.models import DealNote
    from app.deals.service import get_personal_terms

    agent_id = (await _agent(client, db, demo)).id
    deal_id = await _deal_at_terms(client, db, demo)
    assert await _tick(demo) == 1
    db.expire_all()
    pt = await get_personal_terms(db, uuid.UUID(deal_id))
    assert pt.agent_id == agent_id and pt.length_years == 4 and pt.player_consent == "PENDING"
    assert await _tick(demo) == 1
    db.expire_all()
    assert (await get_personal_terms(db, uuid.UUID(deal_id))).player_consent == "AGREED"
    notes = [n.body for n in (await db.execute(select(DealNote).where(DealNote.deal_id == uuid.UUID(deal_id)))).scalars()]
    assert any(n.startswith("Automated (demo): Andy Agent proposed personal terms: four years at £") for n in notes)
    assert "Automated (demo): Andy Agent agreed the personal terms for the player." in notes
    assert await _tick(demo) == 0  # the tester moves it on to paperwork


async def test_an_agent_signed_in_long_ago_still_answers_but_not_one_signed_in_now(client: AsyncClient, db, demo):
    from app.agents.models import AgentNegotiation
    from app.deals.models import Deal

    await _agent(client, db, demo, signed_in=timedelta(minutes=10))
    await _start(client, demo["tester"])
    await _offer(client, demo, 10_000_000)
    await _tick(demo)
    deal = (await db.execute(select(Deal).where(Deal.player_id == uuid.UUID(demo["player"]["id"])))).scalar_one()
    deal_id = deal.id
    assert await _tick(demo) == 0  # someone is signed in as him: he answers himself

    # The tester can make him move anyway.
    assert (await client.get(f"/demo/deals/{deal_id}", headers=demo["h"])).json() == {"in_demo": True}
    r = await client.post(f"/demo/deals/{deal_id}/make", headers=demo["h"])
    assert r.status_code == 200 and r.json() == {"done": "agent_terms"}, r.text
    db.expire_all()
    assert (await db.execute(select(AgentNegotiation).where(AgentNegotiation.deal_id == deal_id))).scalar_one().commission_pct
    r = await client.post(f"/demo/deals/{deal_id}/make", headers=demo["h"])
    assert r.status_code == 409 and r.json()["detail"] == "Nothing for them to do: it's your move."

    # An agent last signed in days ago is free for the house to play.
    from app.demo.house import _available

    assert await _available(db, None)
    from app.auth.models import AgentProfile, User

    neg = (await db.execute(select(AgentNegotiation).where(AgentNegotiation.deal_id == deal_id))).scalar_one()
    user = await db.get(User, (await db.get(AgentProfile, neg.agent_id)).user_id)
    assert not await _available(db, user.id)
    user.last_active_at = datetime.now(timezone.utc) - timedelta(days=3)
    await db.commit()
    assert await _available(db, user.id)

    # Not a deal in someone else's demo.
    other = await _register(client, "h_peek2@demo-example.com", club_name="Peekers Two")
    assert (await client.get(f"/demo/deals/{deal_id}", headers=_auth_headers(other))).json() == {"in_demo": False}
    assert (await client.post(f"/demo/deals/{deal_id}/make", headers=_auth_headers(other))).status_code == 404


async def test_after_a_few_minutes_counts_from_the_testers_move_not_the_houses(client: AsyncClient, db, demo):
    from app.audit.models import AuditEvent
    from app.deals.service import get_personal_terms

    await _agent(client, db, demo)
    deal_id = await _deal_at_terms(client, db, demo)
    assert (await client.patch("/demo/run", headers=demo["h"], json={"speed": "realistic"})).status_code == 200
    assert await _tick(demo) == 0  # the tester just moved the deal on
    await db.execute(update(AuditEvent).where(AuditEvent.entity_id == uuid.UUID(deal_id))
                     .values(created_at=datetime.now(timezone.utc) - timedelta(minutes=4)))
    await db.commit()
    assert await _tick(demo) == 1  # the agent proposes terms…
    assert await _tick(demo) == 1  # …and agrees them, without another wait
    db.expire_all()
    assert (await get_personal_terms(db, uuid.UUID(deal_id))).player_consent == "AGREED"


async def test_a_house_club_answers_an_enquiry(client: AsyncClient, db, demo):
    await _start(client, demo["tester"])
    r = await client.post("/enquiries", headers=demo["h"], json={"player_id": demo["player"]["id"], "body": "Is he available?"})
    assert r.status_code == 201, r.text
    eid = r.json()["id"]
    assert await _tick(demo) == 1
    msgs = (await client.get(f"/enquiries/{eid}", headers=demo["h"])).json()["messages"]
    assert msgs[-1]["body"].endswith("We'd consider offers around £10m. Send one and we'll answer it.")
    assert msgs[-1]["side"] == "theirs"
    assert await _tick(demo) == 0  # the tester's move
    await client.post(f"/enquiries/{eid}/messages", headers=demo["h"], json={"body": "Would £8m do?"})
    assert await _tick(demo) == 1
    msgs = (await client.get(f"/enquiries/{eid}", headers=demo["h"])).json()["messages"]
    assert "Our position hasn't changed" in msgs[-1]["body"]


async def test_a_reminder_in_a_demo_goes_now_and_the_house_answers_it(client: AsyncClient, db, demo):
    from app.offers.models import Offer
    from app.reminders.service import send_automatic

    await _start(client, demo["tester"])
    await client.patch("/demo/run", headers=demo["h"], json={"speed": "realistic"})
    offer = await _offer(client, demo, 10_000_000)
    assert await _tick(demo) == 0  # a real club would take its time

    # Days without movement, but the automatic reminders leave demo offers alone.
    await db.execute(update(Offer).where(Offer.id == uuid.UUID(offer["id"]))
                     .values(last_action_at=datetime.now(timezone.utc) - timedelta(days=4)))
    await db.commit()
    assert await send_automatic(db) == 0
    await db.execute(update(Offer).where(Offer.id == uuid.UUID(offer["id"]))
                     .values(last_action_at=datetime.now(timezone.utc)))
    await db.commit()

    # No day's wait to remind them in a demo; the house answers straight away.
    state = (await client.get(f"/reminders/offer/{offer['id']}", headers=demo["h"])).json()
    assert state["can_send"] is True, state
    r = await client.post(f"/reminders/offer/{offer['id']}", headers=demo["h"], json={})
    assert r.status_code == 200, r.text
    db.expire_all()
    assert (await db.get(Offer, uuid.UUID(offer["id"]))).status.value == "ACCEPTED"
