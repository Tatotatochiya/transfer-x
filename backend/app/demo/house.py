"""House clubs acting on their own in demos (demo mode, step 3).

A background job (`tick`, every few seconds with DEMO_ENABLED) finds the
offers and deals open demo runs made where it's a house club's move, and
makes it, as the club's owner, through the same actions a person would
use. Each move is journaled under the run (so Reset undoes it) and
labelled "Automated (demo)" where the tester will see it.

What a house club does, by its personality:
- **An offer for one of its players:** priced against the listing's asking
  price, else the model's value, else his last transfer fee, else his market
  value. With no price at all, a hard or fair club counters once, then accepts. It accepts at or above its accept level,
  counters at its asking level, and rejects a fee below its floor. After
  MAX_COUNTERS counters it takes anything above the midpoint and walks away
  otherwise. A loan offer is accepted.
- **Its side of a deal:** the player's agent (if nobody uses the agent's
  account) proposes a 5% commission paid by the buyer; the player (if he
  has no account in use) agrees personal terms; the club signs the
  transfer agreement.
The buying club's own steps (agreeing commission, proposing terms, the
medical, registration, completing) stay with the tester.

Speed: "instant" acts on the next tick; "realistic" waits REALISTIC_SECONDS
after the tester's last move, as a real club would take its time.
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
HALF_M = Decimal("500000")


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _money(v: Decimal) -> str:
    m = float(v) / 1e6
    return f"£{m:g}m" if m >= 1 else f"£{float(v) / 1e3:,.0f}k"


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
    """{row id: run id} for the rows open demo runs inserted into `table`."""
    import json

    from app.demo import journal
    from app.demo.models import DemoChange, DemoRun

    out = {}
    for key, run_id in (await db.execute(
            select(DemoChange.pk, DemoChange.run_id).join(DemoRun, DemoRun.id == DemoChange.run_id)
            .where(DemoRun.status == "ACTIVE", DemoChange.op == "insert", DemoChange.table_name == table))).all():
        raw = json.loads(key).get("id")
        try:
            out[journal.dec(raw) if isinstance(raw, dict) else uuid.UUID(str(raw))] = run_id
        except (TypeError, ValueError):
            continue
    return out


async def _unused(db: AsyncSession, user_id: uuid.UUID | None) -> bool:
    from app.auth.models import User

    if user_id is None:
        return True
    user = await db.get(User, user_id)
    return user is None or user.last_active_at is None


# ── Offers ───────────────────────────────────────────────────────────────────


async def _answer_offer(db: AsyncSession, offer_id: uuid.UUID, run_id: uuid.UUID) -> str | None:
    from app.auth.models import User
    from app.clubs.models import Club
    from app.demo.models import DemoRun
    from app.lite.service import player_prices
    from app.offers import actions
    from app.deals.models import DealType
    from app.offers.models import Offer, OfferEvent, OfferEventType, OfferStatus
    from app.offers.schemas import OfferCounterRequest
    from app.players.models import Player

    db.sync_session.info["demo_run_id"] = run_id
    offer = await db.get(Offer, offer_id)
    if offer is None or offer.status not in (OfferStatus.SENT, OfferStatus.COUNTERED) or offer.to_club_id is None:
        return None
    house = await db.get(Club, offer.to_club_id)
    if house is None or not house.house_club or offer.last_actor_club_id == house.id:
        return None  # not a house club's player, or waiting on the tester
    run = await db.get(DemoRun, run_id)
    if not _due(offer.last_action_at, getattr(run, "speed", "instant"), datetime.now(timezone.utc)):
        return None
    owner = await db.get(User, house.user_id)
    player = await db.get(Player, offer.player_id)
    # He's the house club's player (it received the offer), never a free agent here.
    price = (await player_prices(db, [player], owned={player.id})).get(player.id) if player is not None else None
    reference = Decimal(str(price[0])) if price and price[0] else None
    if reference is None and player is not None:
        # No listing and no model value: what he last went for, else his market value.
        from app.players.last_fee import last_transfer_fees

        last = (await last_transfer_fees(db, [player.id])).get(player.id)
        if last:
            reference = Decimal(str(last["fee_gbp"]))
        elif player.market_value:
            reference = Decimal(str(player.market_value))
    counters = (await db.execute(select(func.count()).select_from(OfferEvent).where(
        OfferEvent.offer_id == offer.id, OfferEvent.event_type == OfferEventType.COUNTERED,
        OfferEvent.actor_club_id == house.id))).scalar_one()
    action, ask, reason = decide(offer.fee_amount, reference, house.house_personality, counters,
                                 loan=offer.deal_type == DealType.LOAN)

    await actions.add_message(db, owner, house, offer, LABEL + reason)
    offer = await db.get(Offer, offer_id)
    if action == "accept":
        await actions.accept_offer(db, owner, house, offer)
    elif action == "counter":
        await actions.counter_offer(db, owner, house, offer, OfferCounterRequest(fee_amount=ask))
    else:
        await actions.reject_offer(db, owner, house, offer)
    return action


# ── Deals ────────────────────────────────────────────────────────────────────


async def _deal_step(db: AsyncSession, deal_id: uuid.UUID, run_id: uuid.UUID) -> str | None:
    from app.agents.models import AgentDealInvitation, AgreementStatus, CommissionPayer, InvitationStatus
    from app.auth.models import AgentProfile, PlayerProfile
    from app.clubs.models import Club
    from app.deals import service as deals
    from app.deals.models import DealStage, DealStatus
    from app.demo.models import DemoRun

    db.sync_session.info["demo_run_id"] = run_id
    deal = await deals.get_deal_by_id(db, deal_id)
    if deal is None or deal.status != DealStatus.IN_PROGRESS or deal.seller_club_id is None:
        return None
    house = await db.get(Club, deal.seller_club_id)
    if house is None or not house.house_club:
        return None
    run = await db.get(DemoRun, run_id)
    if not _due(deal.updated_at, getattr(run, "speed", "instant"), datetime.now(timezone.utc)):
        return None
    owner_id = house.user_id

    if deal.stage == DealStage.AGENT_NEGOTIATION:
        invitation = (await db.execute(select(AgentDealInvitation).where(
            AgentDealInvitation.deal_id == deal.id))).scalars().first()
        if invitation is None:
            return None
        agent = await db.get(AgentProfile, invitation.agent_id)
        if agent is None or not await _unused(db, agent.user_id):
            return None
        neg = await deals.get_agent_negotiation(db, deal.id)
        if neg is not None and neg.commission_pct is not None:
            return None  # proposed: the buying club's move
        if invitation.status == InvitationStatus.PENDING:
            invitation.status = InvitationStatus.ACCEPTED
        await deals.upsert_negotiation_terms(db, deal, agent.id, {
            "commission_pct": COMMISSION_PCT, "commission_payer": CommissionPayer.BUYER,
        }, actor_user_id=agent.user_id)
        await deals.add_note(db, deal, author_club_id=house.id,
                             body=LABEL + "The player's agent proposed a 5% commission, paid by the buying club.")
        await db.commit()
        return "agent_terms"

    if deal.stage == DealStage.PERSONAL_TERMS:
        pt = await deals.get_personal_terms(db, deal.id)
        if pt is None or getattr(pt.player_consent, "value", pt.player_consent) != "PENDING":
            return None
        profile = (await db.execute(select(PlayerProfile).where(PlayerProfile.player_id == deal.player_id))).scalars().first()
        if profile is not None and not await _unused(db, profile.user_id):
            return None  # a real player answers for himself
        await deals.player_consent_to_terms(db, deal, AgreementStatus.AGREED, actor_user_id=owner_id)
        await deals.add_note(db, deal, author_club_id=house.id, body=LABEL + "The player agreed the personal terms.")
        await db.commit()
        return "consent"

    if deal.stage == DealStage.PAPERWORK and "agreement_seller" in deals.outstanding_paperwork_for(deal, house.id):
        await deals.complete_paperwork_step(db, deal, "sign-agreement", actor_club_id=house.id, actor_user_id=owner_id)
        await deals.add_note(db, deal, author_club_id=house.id,
                             body=LABEL + f"{house.name} signed its side of the transfer agreement.")
        await db.commit()
        return "signed"
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
    made = 0
    for kind, rows, fn in (("offer", offers, _answer_offer), ("deal", deal_rows, _deal_step)):
        for row_id, run_id in rows.items():
            async with session_factory() as db:
                try:
                    if await fn(db, row_id, run_id):
                        made += 1
                except Exception:
                    await db.rollback()
                    logger.warning("Demo house club couldn't act on %s %s", kind, row_id, exc_info=True)
    return made
