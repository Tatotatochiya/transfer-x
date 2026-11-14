"""House clubs acting on their own in demos (demo mode, step 3).

A background job (`tick`, every few seconds with DEMO_ENABLED) finds the
offers and deals open demo runs made where it's a house club's move, and
makes it, as the club's owner, through the same actions a person would
use. Each move is journaled under the run (so Reset undoes it) and
labelled "Automated (demo)" where the tester will see it.

What a house club does, by its personality (selling, buying, and as a
rival bidder):
- **An offer for one of its players:** priced against the listing's asking
  price, else the model's value, else his last transfer fee, else his market
  value. With no price at all, a hard or fair club counters once, then accepts. It accepts at or above its accept level,
  counters at its asking level, and rejects a fee below its floor. After
  MAX_COUNTERS counters it takes anything above the midpoint and walks away
  otherwise. A loan offer is accepted.
- **Its side of a deal:** the player's agent (unless someone is signed in as
  him, SIGNED_IN) proposes a 5% commission paid by the buyer, takes a counter
  within a point of it and meets a lower one halfway. He asks for personal
  terms (four years, 10% over the current wage); the player's side takes a
  club's terms at 95% of that and meets lower ones halfway; after two rounds
  either takes what's offered. The club signs the transfer agreement.
- **An enquiry about one of its players:** it replies with roughly what it
  would take, then points the tester at an offer.
- **A player the tester lists:** two house clubs make offers, at their
  opening share of his price (BUYER). A tester's counter is accepted up
  to the club's top share, met halfway otherwise, and after MAX_COUNTERS
  counters the club walks away. Buying, it does every buyer's step of the
  deal: personal terms, the commission, signing, the medical, registration
  and completing.
- **A rival.** When the tester bids for a house club's player, another house
  club sometimes bids too (the run's `rivals`: never, sometimes, always). The
  seller weighs the best offer and, if the rival's is higher, says only "We
  have a better offer on the table" and asks the tester to improve; after two
  counters it takes the rival's.
The tester's own steps stay with the tester.

Speed: "instant" acts on the next tick; "realistic" waits REALISTIC_SECONDS
after the tester's last move, as a real club would take its time; the
house's own steps in a row follow each other straight away. A reminder from
the tester (on_reminder) skips the wait; "Make them move now" (make,
make_deal_move) is the tester choosing the move.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# (accept at, counter at, walk away below), as a share of the reference price.
TERMS = {"hard": (1.10, 1.20, 0.80), "fair": (0.95, 1.00, 0.70), "eager": (0.85, 0.95, 0.60)}
MAX_COUNTERS = 2
REALISTIC_SECONDS = 180
SPEEDS = ("instant", "realistic")
COMMISSION_PCT = Decimal("0.05")
LABEL = "Automated (demo): "
CHOSEN = "Automated (demo, the tester's choice): "
HALF_M = Decimal("500000")


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _money(v: Decimal) -> str:
    m = float(v) / 1e6
    return f"£{m:g}m" if m >= 1 else f"£{float(v) / 1e3:,.0f}k"


def _pct(v: Decimal) -> str:
    return f"{float(v) * 100:g}%"


def _round_half_pct(v: Decimal) -> Decimal:
    """To the nearest half a percentage point."""
    return (v * 200).quantize(Decimal("1"), rounding=ROUND_HALF_UP) / 200


async def _rounds_by(db: AsyncSession, deal_id: uuid.UUID, kind: str, side: str) -> int:
    from app.deals.models import TermProposal

    return (await db.execute(select(func.count()).select_from(TermProposal).where(
        TermProposal.deal_id == deal_id, TermProposal.kind == kind, TermProposal.side == side))).scalar_one()


def _round_half_m(v: Decimal) -> Decimal:
    return max(HALF_M, (v / HALF_M).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * HALF_M)


def decide(fee: Decimal | None, reference: Decimal | None, personality: str | None, counters_so_far: int,
           *, loan: bool = False) -> tuple[str, Decimal | None, str]:
    """(action, counter fee, reason): "accept" | "counter" | "reject"."""
    if loan:
        return "accept", None, "A loan suits us."
    if fee is None:
        return "accept", None, "We'll take that."
    if reference is None or reference <= 0:
        # No price to judge it by: a hard or fair club still asks for more, once.
        bump = {"hard": Decimal("1.3"), "fair": Decimal("1.15")}.get(personality or "fair")
        if bump is None or counters_so_far >= 1:
            return "accept", None, f"{_money(fee)} works for us."
        ask = max(_round_half_m(fee * bump), _round_half_m(fee + HALF_M))
        return "counter", ask, f"We'd do it for {_money(ask)}."
    accept_at, ask_at, floor = TERMS.get(personality or "fair", TERMS["fair"])
    share = fee / reference
    if share >= Decimal(str(accept_at)):
        return "accept", None, f"{_money(fee)} works for us."
    if share < Decimal(str(floor)):
        return "reject", None, f"{_money(fee)} is too far from what he's worth to us."
    if counters_so_far >= MAX_COUNTERS:
        if share >= Decimal(str((accept_at + floor) / 2)):
            return "accept", None, f"Let's get it done at {_money(fee)}."
        return "reject", None, "We've been as flexible as we can. We'll keep him."
    ask = max(_round_half_m(reference * Decimal(str(ask_at))), _round_half_m(fee + HALF_M))
    return "counter", ask, f"We'd do it for {_money(ask)}."


def _due(last: datetime | None, speed: str, now: datetime) -> bool:
    if speed != "realistic" or last is None:
        return True
    return _aware(last) <= now - timedelta(seconds=REALISTIC_SECONDS)


async def _demo_rows(db: AsyncSession, table: str) -> dict[uuid.UUID, uuid.UUID]:
    from app.demo.service import open_demo_rows

    return await open_demo_rows(db, table)


# Someone using TransferX refreshes their session at least hourly (access
# tokens last 60 minutes), so a sign-in inside this window means they're here.
SIGNED_IN = timedelta(hours=2)


async def _available(db: AsyncSession, user_id: uuid.UUID | None) -> bool:
    """Whether the house may answer for this agent or player: nobody is signed
    in as him right now. Ever having signed in isn't enough to stop him: one
    tester trying the agent's side once would stall every demo deal of his."""
    from app.auth.models import User

    if user_id is None:
        return True
    user = await db.get(User, user_id)
    if user is None or user.last_active_at is None:
        return True
    return _aware(user.last_active_at) < datetime.now(timezone.utc) - SIGNED_IN


async def _tester_moved_at(db: AsyncSession, entity_type: str, entity_id: uuid.UUID, run) -> datetime | None:
    """When the tester last did something on this deal: "After a few minutes"
    counts from there, so the house's own steps in a row don't each wait."""
    from app.audit.models import AuditEvent

    return (await db.execute(select(func.max(AuditEvent.created_at)).where(
        AuditEvent.entity_type == entity_type, AuditEvent.entity_id == entity_id,
        AuditEvent.actor_user_id == run.user_id))).scalar_one()


# ── Prices ───────────────────────────────────────────────────────────────────

# As a buyer: (opening bid, most it will pay), as a share of the reference price.
BUYER = {"hard": (0.85, 0.95), "fair": (0.95, 1.05), "eager": (1.05, 1.15)}
LISTING_BIDDERS = 2
RIVAL_EVERY = 3  # "sometimes": about one offer in three draws a rival
RIVALS = ("never", "sometimes", "always")


async def _reference(db: AsyncSession, player, *, owned: bool) -> Decimal | None:
    """What the player is worth for the decision: a listing's asking price,
    else the model's value, else his last transfer fee, else his market value."""
    from app.lite.service import player_prices
    from app.players.last_fee import last_transfer_fees

    if player is None:
        return None
    price = (await player_prices(db, [player], owned={player.id} if owned else frozenset())).get(player.id)
    if price and price[0]:
        return Decimal(str(price[0]))
    last = (await last_transfer_fees(db, [player.id])).get(player.id)
    if last:
        return Decimal(str(last["fee_gbp"]))
    return Decimal(str(player.market_value)) if player.market_value else None


def decide_buyer(asked: Decimal | None, reference: Decimal | None, personality: str | None,
                 counters_so_far: int) -> tuple[str, Decimal | None, str]:
    """A house club buying, answering the tester's counter: (action, fee, reason),
    action "accept" | "counter" | "withdraw"."""
    if asked is None:
        return "accept", None, "Agreed."
    _open, top_share = BUYER.get(personality or "fair", BUYER["fair"])
    top = (reference or asked) * Decimal(str(top_share)) if reference else asked
    if asked <= top:
        return "accept", None, f"{_money(asked)} it is."
    if counters_so_far >= MAX_COUNTERS:
        return "withdraw", None, "That's more than we can go to. We'll look elsewhere."
    bid = min(_round_half_m((asked + top) / 2), _round_half_m(top))
    bid = min(bid, asked - HALF_M)
    return "counter", bid, f"Our best is {_money(bid)}."


def _seed(value: uuid.UUID) -> int:
    return int(value.hex, 16)


async def _house_clubs(db: AsyncSession, *, exclude: set, seed: int, n: int) -> list:
    from app.clubs.models import Club

    clubs = [c for c in (await db.execute(select(Club).where(Club.house_club.is_(True)).order_by(Club.id))).scalars()
             if c.id not in exclude]
    if not clubs:
        return []
    start = seed % len(clubs)
    return (clubs[start:] + clubs[:start])[:n]


async def _counters_by(db: AsyncSession, offer_id: uuid.UUID, club_id: uuid.UUID) -> int:
    from app.offers.models import OfferEvent, OfferEventType

    return (await db.execute(select(func.count()).select_from(OfferEvent).where(
        OfferEvent.offer_id == offer_id, OfferEvent.event_type == OfferEventType.COUNTERED,
        OfferEvent.actor_club_id == club_id))).scalar_one()


# ── Offers ───────────────────────────────────────────────────────────────────


async def _rival_offers(db: AsyncSession, player_id: uuid.UUID, seller_id: uuid.UUID, *, open_only: bool = True) -> list:
    """House clubs' offers for this player to the (house) seller: the rivals."""
    from app.clubs.models import Club
    from app.offers.models import Offer, OfferStatus

    q = (select(Offer).join(Club, Club.id == Offer.from_club_id)
         .where(Offer.player_id == player_id, Offer.to_club_id == seller_id, Club.house_club.is_(True)))
    if open_only:
        q = q.where(Offer.status.in_([OfferStatus.SENT, OfferStatus.COUNTERED]))
    return list((await db.execute(q)).scalars())


async def _place_rival(db: AsyncSession, run, offer, seller, reference: Decimal | None) -> None:
    """Another house club bids for the same player, inside the run."""
    from app.auth.models import User
    from app.offers import actions
    from app.offers.schemas import OfferCreateRequest

    [rival] = await _house_clubs(db, exclude={seller.id, offer.from_club_id}, seed=_seed(offer.id), n=1) or [None]
    if rival is None:
        return
    base = reference or offer.fee_amount or Decimal(0)
    if base <= 0:
        return
    share = Decimal(95 + _seed(offer.id) % 21) / 100  # 95% to 115% of his price
    fee = _round_half_m(base * share)
    owner = await db.get(User, rival.user_id)
    db.sync_session.info["demo_run_id"] = run.id
    try:
        await actions.create_offer(db, owner, rival, OfferCreateRequest(
            player_id=offer.player_id, to_club_id=seller.id, fee_amount=fee))
    except actions.OfferActionError as exc:  # no budget, window closed…
        logger.info("Demo rival bid skipped: %s", exc.detail)
    db.sync_session.info["demo_run_id"] = run.id


async def _answer_as_seller(db: AsyncSession, offer, house, run) -> str | None:
    from app.auth.models import User
    from app.deals.models import DealType
    from app.offers import actions
    from app.offers.models import Offer
    from app.offers.schemas import OfferCounterRequest
    from app.players.models import Player

    owner = await db.get(User, house.user_id)
    player = await db.get(Player, offer.player_id)
    reference = await _reference(db, player, owned=True)  # his club received the offer: never a free agent here
    counters = await _counters_by(db, offer.id, house.id)
    offer_id = offer.id

    rivals_mode = getattr(run, "rivals", "sometimes") or "sometimes"
    if (offer.deal_type != DealType.LOAN and counters == 0 and rivals_mode != "never"
            and not await _rival_offers(db, offer.player_id, house.id, open_only=False)
            and (rivals_mode == "always" or _seed(offer.id) % RIVAL_EVERY == 0)):
        await _place_rival(db, run, offer, house, reference)
        offer = await db.get(Offer, offer_id)

    rivals = await _rival_offers(db, offer.player_id, house.id)
    best = max(rivals, key=lambda o: o.fee_amount or 0, default=None)
    fee = offer.fee_amount or Decimal(0)
    if best is not None and (best.fee_amount or 0) > fee and offer.deal_type != DealType.LOAN:
        if counters < MAX_COUNTERS:
            ask = _round_half_m((best.fee_amount or 0) + HALF_M)
            await actions.add_message(db, owner, house, offer, LABEL + "We have a better offer on the table. Can you improve?")
            offer = await db.get(Offer, offer_id)
            await actions.counter_offer(db, owner, house, offer, OfferCounterRequest(fee_amount=ask))
            return "counter"
        await actions.add_message(db, owner, house, offer, LABEL + "We've accepted another club's offer.")
        offer = await db.get(Offer, offer_id)
        await actions.reject_offer(db, owner, house, offer)
        await actions.accept_offer(db, owner, house, await db.get(Offer, best.id))
        return "sold_to_rival"

    action, ask, reason = decide(offer.fee_amount, reference, house.house_personality, counters,
                                 loan=offer.deal_type == DealType.LOAN)
    await actions.add_message(db, owner, house, offer, LABEL + reason)
    offer = await db.get(Offer, offer_id)
    if action == "accept":
        await actions.accept_offer(db, owner, house, offer)
        for rival in rivals:  # the others lose out
            await actions.reject_offer(db, owner, house, await db.get(Offer, rival.id))
    elif action == "counter":
        await actions.counter_offer(db, owner, house, offer, OfferCounterRequest(fee_amount=ask))
    else:
        await actions.reject_offer(db, owner, house, offer)
    return action


async def _answer_as_buyer(db: AsyncSession, offer, house) -> str | None:
    """The tester countered a house club's bid for their player."""
    from app.auth.models import User
    from app.offers import actions
    from app.offers.models import Offer
    from app.offers.schemas import OfferCounterRequest
    from app.players.models import Player

    owner = await db.get(User, house.user_id)
    player = await db.get(Player, offer.player_id)
    reference = await _reference(db, player, owned=True)
    action, bid, reason = decide_buyer(offer.fee_amount, reference, house.house_personality,
                                       await _counters_by(db, offer.id, house.id))
    await actions.add_message(db, owner, house, offer, LABEL + reason)
    offer = await db.get(Offer, offer.id)
    if action == "accept":
        await actions.accept_offer(db, owner, house, offer)
    elif action == "counter":
        await actions.counter_offer(db, owner, house, offer, OfferCounterRequest(fee_amount=bid))
    else:
        await actions.withdraw_offer(db, owner, house, offer)
    return action


async def _answer_offer(db: AsyncSession, offer_id: uuid.UUID, run_id: uuid.UUID, *,
                        hurry: bool = False) -> str | None:
    from app.clubs.models import Club
    from app.demo.models import DemoRun
    from app.offers.models import Offer, OfferStatus

    db.sync_session.info["demo_run_id"] = run_id
    offer = await db.get(Offer, offer_id)
    if offer is None or offer.status not in (OfferStatus.SENT, OfferStatus.COUNTERED) or offer.to_club_id is None:
        return None
    seller = await db.get(Club, offer.to_club_id)
    buyer = await db.get(Club, offer.from_club_id)
    if seller is None or buyer is None or (seller.house_club and buyer.house_club):
        return None  # a rival's bid: weighed when the tester's offer is answered
    run = await db.get(DemoRun, run_id)
    if not hurry and not _due(offer.last_action_at, getattr(run, "speed", "instant"), datetime.now(timezone.utc)):
        return None
    if seller.house_club and offer.last_actor_club_id != seller.id:
        return await _answer_as_seller(db, offer, seller, run)
    if buyer.house_club and offer.last_actor_club_id == seller.id:
        return await _answer_as_buyer(db, offer, buyer)
    return None  # waiting on the tester


async def _bid_on_listing(db: AsyncSession, sale_id: uuid.UUID, run_id: uuid.UUID) -> str | None:
    """House clubs make offers for a player the tester listed."""
    from app.auth.models import User
    from app.clubs.models import Club
    from app.demo.models import DemoRun
    from app.offers import actions
    from app.offers.models import Offer
    from app.offers.schemas import OfferCreateRequest
    from app.players.models import Player
    from app.sales.models import Sale, SaleStatus, SaleType

    db.sync_session.info["demo_run_id"] = run_id
    sale = await db.get(Sale, sale_id)
    if sale is None or sale.status != SaleStatus.OPEN:
        return None
    seller = await db.get(Club, sale.seller_club_id)
    if seller is None or seller.house_club:
        return None
    already = (await db.execute(select(Offer.id).join(Club, Club.id == Offer.from_club_id).where(
        Offer.player_id == sale.player_id, Club.house_club.is_(True)).limit(1))).first()
    run = await db.get(DemoRun, run_id)
    if already is not None or not _due(sale.created_at, getattr(run, "speed", "instant"), datetime.now(timezone.utc)):
        return None
    player = await db.get(Player, sale.player_id)
    reference = await _reference(db, player, owned=True)
    asking = Decimal(str(sale.asking_price)) if sale.asking_price else None
    made = 0
    for club in await _house_clubs(db, exclude={seller.id}, seed=_seed(sale.id), n=LISTING_BIDDERS):
        opening, _top = BUYER.get(club.house_personality or "fair", BUYER["fair"])
        base = reference or asking
        if base is None:
            continue
        # Each club sees him a little differently: within 4% either way of its opening share.
        spread = Decimal((_seed(club.id) + _seed(sale.id)) % 9 - 4) / 100
        fee = _round_half_m(base * (Decimal(str(opening)) + spread))
        if sale.sale_type == SaleType.FIXED_PRICE and asking:
            fee = asking
        owner = await db.get(User, club.user_id)
        db.sync_session.info["demo_run_id"] = run_id
        try:
            result = await actions.create_offer(db, owner, club, OfferCreateRequest(
                player_id=sale.player_id, to_club_id=seller.id, fee_amount=fee, sale_id=sale.id))
            if result.offer is not None:
                await actions.add_message(db, owner, club, result.offer,
                                          LABEL + f"{club.name} would like to sign him for {_money(fee)}.")
                made += 1
        except actions.OfferActionError as exc:  # no budget, window closed…
            logger.info("Demo house bid skipped: %s", exc.detail)
        db.sync_session.info["demo_run_id"] = run_id
    return "bids" if made else None


# ── Deals ────────────────────────────────────────────────────────────────────


async def _deal_step(db: AsyncSession, deal_id: uuid.UUID, run_id: uuid.UUID, *,
                     hurry: bool = False, chosen: bool = False) -> str | None:
    """Make the house's next move on a deal, if it has one: the house club's,
    or the agent's or player's when nobody is signed in as them.

    `hurry` skips "After a few minutes" (the tester sent a reminder).
    `chosen` is the tester's "Make them move now": it also answers for an
    agent or player someone is signed in as, and says it was their choice."""
    from app.agents.models import AgentDealInvitation, AgreementStatus, CommissionPayer, InvitationStatus
    from app.auth.models import AgentProfile, PlayerProfile
    from app.clubs.models import Club
    from app.deals import service as deals
    from app.deals.models import DealStage, DealStatus, MedicalStatus
    from app.demo.models import DemoRun
    from app.players.models import Contract

    db.sync_session.info["demo_run_id"] = run_id
    deal = await deals.get_deal_by_id(db, deal_id)
    if deal is None or deal.status not in (DealStatus.IN_PROGRESS, DealStatus.PENDING_COMPLETION):
        return None
    seller = await db.get(Club, deal.seller_club_id) if deal.seller_club_id else None
    buyer = await db.get(Club, deal.buyer_club_id)
    house_seller = seller if seller is not None and seller.house_club else None
    house_buyer = buyer if buyer is not None and buyer.house_club else None
    if house_seller is None and house_buyer is None:
        return None
    run = await db.get(DemoRun, run_id)
    if not (hurry or chosen):
        last = await _tester_moved_at(db, "DEAL", deal.id, run) or deal.created_at
        if not _due(last, getattr(run, "speed", "instant"), datetime.now(timezone.utc)):
            return None
    note_club = (house_buyer or house_seller).id
    label = CHOSEN if chosen else LABEL

    async def may(user_id: uuid.UUID | None) -> bool:
        return chosen or await _available(db, user_id)

    async def done(what: str, note: str) -> str:
        from app.deals.live import deal_updated

        await deals.add_note(db, deal, author_club_id=note_club, body=label + note)
        await db.commit()
        await deal_updated(db, deal_id)  # open deal pages refetch
        return what

    if deal.stage == DealStage.AGREEMENT and house_buyer is not None:
        await deals.advance_deal(db, deal, actor_club_id=house_buyer.id, actor_user_id=house_buyer.user_id)
        return await done("advanced", f"{house_buyer.name} moved the deal on to personal terms.")

    if deal.stage == DealStage.AGENT_NEGOTIATION:
        invitation = (await db.execute(select(AgentDealInvitation).where(
            AgentDealInvitation.deal_id == deal.id))).scalars().first()
        neg = await deals.get_agent_negotiation(db, deal.id)
        if invitation is not None and (neg is None or neg.commission_pct is None):
            agent = await db.get(AgentProfile, invitation.agent_id)
            if agent is None or not await may(agent.user_id):
                return None  # someone is signed in as the agent: he answers for himself
            if invitation.status == InvitationStatus.PENDING:
                invitation.status = InvitationStatus.ACCEPTED
            await deals.upsert_negotiation_terms(db, deal, agent.id, {
                "commission_pct": COMMISSION_PCT, "commission_payer": CommissionPayer.BUYER,
            }, actor_user_id=agent.user_id)
            return await done("agent_terms", "The player's agent proposed a 5% commission, paid by the buying club.")
        if neg is None or neg.commission_pct is None:
            return None
        agreement = getattr(neg.club_agreement, "value", neg.club_agreement)
        if neg.proposed_by == "BUYER" and agreement == "PENDING":
            # The club countered: the agent takes it within a point of his ask,
            # otherwise meets it halfway; after two rounds he takes it.
            agent = await db.get(AgentProfile, neg.agent_id)
            if agent is None or not await may(agent.user_id):
                return None
            rounds = await _rounds_by(db, deal.id, "COMMISSION", "AGENT")
            if neg.commission_pct >= COMMISSION_PCT - Decimal("0.01") or rounds > MAX_COUNTERS:
                await deals.agent_accept_counter(db, deal, agent.id, actor_user_id=agent.user_id)
                return await done("commission_accepted",
                                  f"{agent.display_name} accepted {_pct(neg.commission_pct)} commission.")
            meet = _round_half_pct((COMMISSION_PCT + neg.commission_pct) / 2)
            await deals.upsert_negotiation_terms(db, deal, agent.id, {
                "commission_pct": meet, "commission_payer": neg.commission_payer,
            }, actor_user_id=agent.user_id, note=f"I can meet you at {_pct(meet)}.")
            return await done("commission_countered", f"{agent.display_name} came back at {_pct(meet)} commission.")
        if house_buyer is not None:
            if agreement != "AGREED":
                await deals.club_respond_to_negotiation(db, deal, house_buyer.id, AgreementStatus.AGREED,
                                                        actor_user_id=house_buyer.user_id)
            await deals.advance_deal(db, deal, actor_club_id=house_buyer.id, actor_user_id=house_buyer.user_id)
            return await done("commission_agreed", f"{house_buyer.name} agreed the agent's commission.")
        return None

    if deal.stage == DealStage.PERSONAL_TERMS:
        pt = await deals.get_personal_terms(db, deal.id)
        wage = (await db.execute(select(Contract.wage_weekly).where(
            Contract.player_id == deal.player_id, Contract.is_active.is_(True)))).scalars().first()
        # What his side asks for: four years at 10% over his current wage.
        target = (_round_half_m(Decimal(str(wage)) * Decimal("1.1") * 52) / 52).quantize(Decimal("1")) if wage else Decimal(30000)
        if pt is None:
            # With an agent, he prepares the terms (the deal card says "Waiting on
            # the agent"), whichever side the tester is on. Without one, or with
            # an agent someone is signed in as, a buying house club offers them.
            agent = await db.get(AgentProfile, deal.commission_agent_id) if deal.commission_agent_id else None
            if agent is not None and await may(agent.user_id):
                await deals.set_personal_terms(db, deal, agent_profile_id=agent.id, wage_weekly=target,
                                               signing_bonus=Decimal(0), length_years=4,
                                               actor_user_id=agent.user_id, side="PLAYER")
                return await done("terms_proposed",
                                  f"{agent.display_name} asked for four years at £{target:,.0f} a week.")
            if house_buyer is None:
                return None  # the tester, buying, offers them
            await deals.set_personal_terms(db, deal, agent_profile_id=None, wage_weekly=target,
                                           signing_bonus=Decimal(0), length_years=4,
                                           actor_user_id=house_buyer.user_id, side="BUYER")
            return await done("terms_proposed", f"{house_buyer.name} offered four years at £{target:,.0f} a week.")
        consent = getattr(pt.player_consent, "value", pt.player_consent)
        if consent == "PENDING" and pt.proposed_by == "PLAYER":
            # The player's side's terms: the buying club answers.
            if house_buyer is None:
                return None  # the tester agrees, counters or walks away
            await deals.club_respond_to_terms(db, deal, house_buyer.id, AgreementStatus.AGREED,
                                              actor_user_id=house_buyer.user_id)
            return await done("terms_agreed", f"{house_buyer.name} agreed the personal terms.")
        if consent == "PENDING":
            # The club's terms: the player's side answers, his agent if he has
            # one. It takes 95% of what it asks for, otherwise meets the club
            # halfway; after two rounds it takes what's offered.
            agent = await db.get(AgentProfile, pt.agent_id) if pt.agent_id else None
            profile = (await db.execute(select(PlayerProfile).where(
                PlayerProfile.player_id == deal.player_id))).scalars().first()
            if agent is not None and await may(agent.user_id):
                actor, who, agent_id = agent.user_id, agent.display_name, agent.id
            elif profile is not None and await may(profile.user_id):
                actor, who, agent_id = profile.user_id, "The player", None
            elif agent is None and profile is None:
                actor, who, agent_id = (house_seller or house_buyer).user_id, "The player", None
            else:
                return None  # whoever answers for him is signed in: they answer
            offered = Decimal(str(pt.wage_weekly or 0))
            rounds = await _rounds_by(db, deal.id, "PERSONAL_TERMS", "PLAYER")
            if offered >= target * Decimal("0.95") or rounds >= MAX_COUNTERS:
                await deals.player_consent_to_terms(db, deal, AgreementStatus.AGREED, actor_user_id=actor)
                return await done("consent", f"{who} agreed the personal terms" + (" for the player." if agent_id else "."))
            meet = ((offered + target) / 2).quantize(Decimal("1"))
            await deals.set_personal_terms(db, deal, agent_profile_id=agent_id, wage_weekly=meet,
                                           signing_bonus=pt.signing_bonus, length_years=pt.length_years,
                                           actor_user_id=actor, side="PLAYER",
                                           note=f"He'd sign for £{meet:,.0f} a week.")
            return await done("terms_countered", f"{who} came back at £{meet:,.0f} a week.")
        if consent == "AGREED" and house_buyer is not None:
            await deals.advance_deal(db, deal, actor_club_id=house_buyer.id, actor_user_id=house_buyer.user_id)
            return await done("advanced", f"{house_buyer.name} moved the deal on to paperwork.")
        return None

    if deal.stage == DealStage.PAPERWORK:
        if house_seller is not None and "agreement_seller" in deals.outstanding_paperwork_for(deal, house_seller.id):
            await deals.complete_paperwork_step(db, deal, "sign-agreement", actor_club_id=house_seller.id,
                                                actor_user_id=house_seller.user_id)
            return await done("signed", f"{house_seller.name} signed its side of the transfer agreement.")
        if house_buyer is not None:
            todo = deals.outstanding_paperwork_for(deal, house_buyer.id)
            if "agreement_buyer" in todo:
                await deals.complete_paperwork_step(db, deal, "sign-agreement", actor_club_id=house_buyer.id,
                                                    actor_user_id=house_buyer.user_id)
                return await done("signed", f"{house_buyer.name} signed its side of the transfer agreement.")
            if "medical" in todo:
                await deals.upsert_medical_check(db, deal, status=MedicalStatus.PASSED, notes="Demo medical",
                                                 actor_club_id=house_buyer.id, actor_user_id=house_buyer.user_id)
                return await done("medical", "The player passed his medical.")
            if "registration" in todo:
                await deals.complete_paperwork_step(db, deal, "submit-registration", actor_club_id=house_buyer.id,
                                                    actor_user_id=house_buyer.user_id)
                return await done("registered", f"{house_buyer.name} submitted the registration.")
        return None

    if deal.stage == DealStage.CONFIRMED and house_buyer is not None:
        from app.transfer_window.service import completion_hold as window_hold

        if await window_hold(db, deal) is not None:
            return None  # completes when the window opens, like any club's
        await deals.advance_deal(db, deal, actor_club_id=house_buyer.id, actor_user_id=house_buyer.user_id)
        return await done("completed", f"{house_buyer.name} completed the transfer.")
    return None


# ── Enquiries ────────────────────────────────────────────────────────────────


async def _answer_enquiry(db: AsyncSession, enquiry_id: uuid.UUID, run_id: uuid.UUID, *,
                          hurry: bool = False) -> str | None:
    """A house club answers an enquiry about one of its players: the first time
    with roughly what it would take (its counter level, by personality), after
    that by pointing the tester at an offer. It never closes the enquiry."""
    from app.clubs.models import Club
    from app.demo.models import DemoRun
    from app.enquiries import service as enquiries
    from app.enquiries.models import EnquiryStatus
    from app.players.models import Player

    db.sync_session.info["demo_run_id"] = run_id
    enquiry = await enquiries.get_enquiry(db, enquiry_id)
    if enquiry is None or enquiry.status != EnquiryStatus.OPEN:
        return None
    house = await db.get(Club, enquiry.to_club_id)
    if house is None or not house.house_club or enquiry.last_actor_club_id == house.id:
        return None  # not a house club's, or waiting on the tester
    run = await db.get(DemoRun, run_id)
    if not hurry and not _due(enquiry.updated_at, getattr(run, "speed", "instant"), datetime.now(timezone.utc)):
        return None
    player = await db.get(Player, enquiry.player_id)
    name = player.name if player is not None else "him"
    if any(m.sender_club_id == house.id for m in enquiry.messages):
        body = "Our position hasn't changed. Send us an offer and we'll give you an answer."
    else:
        reference = await _reference(db, player, owned=True)
        _accept, ask_at, _floor = TERMS.get(house.house_personality or "fair", TERMS["fair"])
        body = (f"Thanks for asking about {name}. We'd consider offers around "
                f"{_money(_round_half_m(reference * Decimal(str(ask_at))))}. Send one and we'll answer it."
                if reference else f"Thanks for asking about {name}. Send us an offer and we'll answer it.")
    await enquiries.add_message(db, enquiry, sender_club_id=house.id, body=LABEL + body,
                                actor_user_id=house.user_id)
    await db.commit()
    return "replied"


# ── "Make them …": the tester chooses the house club's move ─────────────────

MAKE = {"seller": ("accept", "counter", "reject"), "buyer": ("accept", "counter", "withdraw")}


async def offer_controls(db: AsyncSession, user, offer_id: uuid.UUID) -> dict | None:
    """For a demo offer in the user's own run: which house club, whether it's
    its move, and what the tester can make it do. None when it isn't one."""
    from app.clubs.models import Club
    from app.demo.service import active_run
    from app.offers.models import Offer, OfferStatus

    run = await active_run(db, user.id)
    if run is None or (await _demo_rows(db, "offers")).get(offer_id) != run.id:
        return None
    offer = await db.get(Offer, offer_id)
    if offer is None or offer.to_club_id is None:
        return None
    seller, buyer = await db.get(Club, offer.to_club_id), await db.get(Club, offer.from_club_id)
    if seller.house_club and not buyer.house_club:
        house, side, moves = seller, "seller", offer.last_actor_club_id != seller.id
    elif buyer.house_club and not seller.house_club:
        house, side, moves = buyer, "buyer", offer.last_actor_club_id == seller.id
    else:
        return None
    open_ = offer.status in (OfferStatus.SENT, OfferStatus.COUNTERED)
    return {"offer_id": str(offer.id), "house_club": house.name, "side": side,
            "house_move": open_ and moves, "actions": list(MAKE[side]) if open_ and moves else []}


async def make(db: AsyncSession, user, offer_id: uuid.UUID, action: str, fee: Decimal | None) -> str:
    """Make the house club accept, counter (at `fee`, else what it would ask)
    or reject / withdraw now. ValueError when it can't."""
    from app.auth.models import User
    from app.clubs.models import Club
    from app.offers import actions
    from app.offers.models import Offer
    from app.offers.schemas import OfferCounterRequest
    from app.players.models import Player

    controls = await offer_controls(db, user, offer_id)
    if controls is None:
        raise LookupError("Not an offer in your demo.")
    if action not in controls["actions"]:
        raise ValueError("It isn't the house club's move, or it can't do that.")
    run_id = (await _demo_rows(db, "offers"))[offer_id]
    db.sync_session.info["demo_run_id"] = run_id
    offer = await db.get(Offer, offer_id)
    house = await db.get(Club, offer.to_club_id if controls["side"] == "seller" else offer.from_club_id)
    owner = await db.get(User, house.user_id)
    if action == "counter" and fee is None:
        reference = await _reference(db, await db.get(Player, offer.player_id), owned=True)
        if controls["side"] == "seller":
            _a, fee, _r = decide(offer.fee_amount, reference, house.house_personality, 0)
            fee = fee if fee is not None and fee > (offer.fee_amount or 0) else _round_half_m((offer.fee_amount or 0) + HALF_M)
        else:
            _a, fee, _r = decide_buyer(offer.fee_amount, reference, house.house_personality, 0)
            fee = fee if fee is not None and fee < (offer.fee_amount or 0) else _round_half_m((offer.fee_amount or 0) * Decimal("0.9"))
    said = {"accept": "We accept.", "reject": "We'll pass on this one.", "withdraw": "We'll look elsewhere.",
            "counter": f"We'd do it for {_money(fee)}." if fee else ""}[action]
    await actions.add_message(db, owner, house, offer, CHOSEN + said)
    offer = await db.get(Offer, offer_id)
    if action == "accept":
        await actions.accept_offer(db, owner, house, offer)
    elif action == "counter":
        await actions.counter_offer(db, owner, house, offer, OfferCounterRequest(fee_amount=fee))
    elif action == "reject":
        await actions.reject_offer(db, owner, house, offer)
    else:
        await actions.withdraw_offer(db, owner, house, offer)
    return action


# ── Deals: "Make them move now", and reminders ─────────────────────────────


async def _own_row(db: AsyncSession, user, table: str, row_id: uuid.UUID) -> uuid.UUID | None:
    """The run id when `row_id` is a row the user's own open demo made."""
    from app.demo.service import active_run

    run = await active_run(db, user.id)
    if run is None or (await _demo_rows(db, table)).get(row_id) != run.id:
        return None
    return run.id


async def deal_in_demo(db: AsyncSession, user, deal_id: uuid.UUID) -> bool:
    return await _own_row(db, user, "deals", deal_id) is not None


async def make_deal_move(db: AsyncSession, user, deal_id: uuid.UUID) -> str:
    """The tester's "Make them move now" on a deal in their demo: the next
    move that isn't theirs (the house club's, the agent's or the player's),
    straight away. LookupError when it isn't their demo's deal, ValueError
    when there's nothing for anyone else to do."""
    run_id = await _own_row(db, user, "deals", deal_id)
    if run_id is None:
        raise LookupError("Not a deal in your demo.")
    done = await _deal_step(db, deal_id, run_id, chosen=True)
    if done is None:
        raise ValueError("Nothing for them to do: it's your move.")
    return done


SUBJECT_TABLES = {"offer": "offers", "deal": "deals", "enquiry": "enquiries"}


async def on_reminder(db: AsyncSession, user, subject_type: str, subject_id: uuid.UUID) -> str | None:
    """A tester reminded the other side of something in their own demo: the
    house answers now, without waiting for "After a few minutes". An agent or
    player someone is signed in as is left to answer for himself."""
    run_id = await _own_row(db, user, SUBJECT_TABLES[subject_type], subject_id)
    if run_id is None:
        return None
    fn = {"offer": _answer_offer, "deal": _deal_step, "enquiry": _answer_enquiry}[subject_type]
    try:
        return await fn(db, subject_id, run_id, hurry=True)
    except Exception:
        await db.rollback()
        logger.warning("Demo house couldn't answer a reminder on %s %s", subject_type, subject_id, exc_info=True)
        return None


async def tick(session_factory) -> int:
    """Make every house club move that's due. Each in its own session and
    transaction, so one failing stops nothing. Returns how many were made."""
    from app.config import settings

    if not settings.demo_enabled:
        return 0
    async with session_factory() as db:
        offers = await _demo_rows(db, "offers")
        deal_rows = await _demo_rows(db, "deals")
        sales = await _demo_rows(db, "sales")
        enquiry_rows = await _demo_rows(db, "enquiries")
    made = 0
    for kind, rows, fn in (("offer", offers, _answer_offer), ("deal", deal_rows, _deal_step),
                           ("listing", sales, _bid_on_listing), ("enquiry", enquiry_rows, _answer_enquiry)):
        for row_id, run_id in rows.items():
            async with session_factory() as db:
                try:
                    if await fn(db, row_id, run_id):
                        made += 1
                except Exception:
                    await db.rollback()
                    logger.warning("Demo house club couldn't act on %s %s", kind, row_id, exc_info=True)
    return made
