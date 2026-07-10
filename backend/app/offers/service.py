"""M4 — Offer negotiation service layer."""

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app import clubs as clubs_module
from app.audit import service as audit_service
from app.common.filters import apply_date_range
from app.deals.models import Deal, DealStage, DealStatus
from app.offers.models import Offer, OfferEvent, OfferEventType, OfferMessage, OfferStatus

_OFFER_EXPIRY_DAYS = 7
_TERMINAL = {OfferStatus.ACCEPTED, OfferStatus.REJECTED, OfferStatus.WITHDRAWN, OfferStatus.EXPIRED}


def _is_terminal(status: OfferStatus) -> bool:
    return status in _TERMINAL


def _add_ons_total(add_ons: dict | None) -> Decimal:
    """Sum the numeric entries of a freeform add_ons dict.

    Item 3: add_ons has no fixed schema (clubs can put anything in it), so
    only values that actually look like a monetary amount count toward
    budget reservation — non-numeric entries (flags, notes) are ignored.
    """
    if not add_ons:
        return Decimal("0")
    total = Decimal("0")
    for value in add_ons.values():
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float, Decimal)):
            total += Decimal(str(value))
    return total


def _load_options():
    return [
        selectinload(Offer.player),
        selectinload(Offer.from_club),
        selectinload(Offer.to_club),
        selectinload(Offer.messages).selectinload(OfferMessage.sender_club),
        selectinload(Offer.events),
    ]


async def get_offer_by_id(db: AsyncSession, offer_id: uuid.UUID) -> Offer | None:
    result = await db.execute(
        select(Offer).where(Offer.id == offer_id).options(*_load_options())
    )
    return result.scalar_one_or_none()


async def get_active_offer_for_buyer(
    db: AsyncSession,
    player_id: uuid.UUID,
    from_club_id: uuid.UUID,
) -> Offer | None:
    """Return an active (SENT or COUNTERED) offer this club already has for the player."""
    result = await db.execute(
        select(Offer)
        .where(
            Offer.player_id == player_id,
            Offer.from_club_id == from_club_id,
            Offer.status.in_([OfferStatus.SENT, OfferStatus.COUNTERED]),
        )
        .options(*_load_options())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def list_offers(
    db: AsyncSession,
    *,
    club_id: uuid.UUID,
    direction: str = "all",  # "sent" | "received" | "all"
    status: OfferStatus | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = 1,
    page_size: int = 30,
) -> tuple[list[Offer], int]:
    from sqlalchemy import func, or_

    q = select(Offer).options(*_load_options())
    if direction == "sent":
        q = q.where(Offer.from_club_id == club_id)
    elif direction == "received":
        q = q.where(Offer.to_club_id == club_id)
    else:
        q = q.where(or_(Offer.from_club_id == club_id, Offer.to_club_id == club_id))
    if status:
        q = q.where(Offer.status == status)
    q = apply_date_range(q, Offer.last_action_at, date_from, date_to)

    total_result = await db.execute(select(func.count()).select_from(q.subquery()))
    total = total_result.scalar_one()
    rows = await db.execute(
        q.order_by(Offer.last_action_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    return list(rows.scalars()), total


async def list_offers_for_sale(
    db: AsyncSession,
    sale_id: uuid.UUID,
) -> list[Offer]:
    """Return all offers tied to a specific sale, eager-loading from_club."""
    result = await db.execute(
        select(Offer)
        .where(Offer.sale_id == sale_id)
        .options(selectinload(Offer.from_club))
        .order_by(Offer.fee_amount.desc().nullsfirst(), Offer.created_at.asc())
    )
    return list(result.scalars())


async def create_offer(
    db: AsyncSession,
    *,
    player_id: uuid.UUID,
    from_club_id: uuid.UUID,
    to_club_id: uuid.UUID | None = None,
    sale_id: uuid.UUID | None = None,
    fee_amount: Decimal | None = None,
    wage_weekly: Decimal | None = None,
    contract_years: int | None = None,
    contract_end_date=None,
    add_ons: dict | None = None,
    expires_at: datetime | None = None,
) -> Offer:
    """Create and immediately send an offer. Reserves budget from from_club."""
    if to_club_id and to_club_id == from_club_id:
        raise ValueError("Cannot make an offer to your own club")

    now = datetime.now(timezone.utc)
    exp = expires_at or (now + timedelta(days=_OFFER_EXPIRY_DAYS))

    offer = Offer(
        player_id=player_id,
        sale_id=sale_id,
        from_club_id=from_club_id,
        to_club_id=to_club_id,
        fee_amount=fee_amount,
        wage_weekly=wage_weekly,
        contract_years=contract_years,
        contract_end_date=contract_end_date,
        add_ons=add_ons or {},
        status=OfferStatus.SENT,
        expires_at=exp,
        reserved_transfer_amount=Decimal("0"),
        last_actor_club_id=from_club_id,  # buyer sent it → seller's turn
    )

    # Reserve budget immediately on send — fee plus any monetary add-ons.
    reserve = (fee_amount or Decimal("0")) + _add_ons_total(add_ons)
    if reserve > 0:
        await clubs_module.service.reserve_budget(
            db, club_id=from_club_id, transfer_amount=reserve
        )
        offer.reserved_transfer_amount = reserve

    db.add(offer)
    await db.flush()

    await audit_service.emit(
        db,
        entity_type="OFFER", entity_id=offer.id,
        action="OFFER_CREATED",
        payload={"fee_amount": str(fee_amount) if fee_amount else None, "player_id": str(player_id)},
        description=f"Offer created by club {from_club_id}",
    )

    db.add(OfferEvent(
        offer_id=offer.id,
        event_type=OfferEventType.CREATED,
        actor_club_id=from_club_id,
        payload={},
    ))
    db.add(OfferEvent(
        offer_id=offer.id,
        event_type=OfferEventType.SENT,
        actor_club_id=from_club_id,
        payload={"fee_amount": str(fee_amount) if fee_amount else None},
    ))
    await db.flush()
    return offer


async def counter_offer(
    db: AsyncSession,
    offer: Offer,
    *,
    actor_club_id: uuid.UUID,
    fee_amount: Decimal | None,
    wage_weekly: Decimal | None = None,
    contract_years: int | None = None,
    contract_end_date=None,
    add_ons: dict | None = None,
    expires_at: datetime | None = None,
) -> Offer:
    """Counter an offer with new terms. Either party can counter."""
    _check_not_expired(offer)
    if _is_terminal(offer.status):
        raise ValueError(f"Cannot counter an offer with status {offer.status}")
    if offer.status not in (OfferStatus.SENT, OfferStatus.COUNTERED):
        raise ValueError("Only SENT or COUNTERED offers can be countered")

    # Validate actor is a party to the offer
    _require_party(offer, actor_club_id)
    _require_turn(offer, actor_club_id)

    # If from_club counters (buyer raises their offer), adjust reservation.
    # Item 3: add_ons now counts toward the reservation too, so recompute
    # whenever either the fee or the add_ons change, not just the fee.
    if actor_club_id == offer.from_club_id and (fee_amount is not None or add_ons is not None):
        old_reserve = offer.reserved_transfer_amount
        effective_fee = fee_amount if fee_amount is not None else (offer.fee_amount or Decimal("0"))
        effective_add_ons = add_ons if add_ons is not None else offer.add_ons
        new_reserve = effective_fee + _add_ons_total(effective_add_ons)
        delta = new_reserve - old_reserve
        if delta > 0:
            await clubs_module.service.reserve_budget(
                db, club_id=actor_club_id, transfer_amount=delta
            )
        elif delta < 0:
            await clubs_module.service.release_budget(
                db, club_id=actor_club_id, transfer_amount=-delta
            )
        offer.reserved_transfer_amount = new_reserve

    # Update terms
    if fee_amount is not None:
        offer.fee_amount = fee_amount
    if wage_weekly is not None:
        offer.wage_weekly = wage_weekly
    if contract_years is not None:
        offer.contract_years = contract_years
    if contract_end_date is not None:
        offer.contract_end_date = contract_end_date
    if add_ons is not None:
        offer.add_ons = add_ons
    if expires_at is not None:
        offer.expires_at = expires_at

    offer.status = OfferStatus.COUNTERED
    offer.last_actor_club_id = actor_club_id  # ball is now with the other party
    db.add(OfferEvent(
        offer_id=offer.id,
        event_type=OfferEventType.COUNTERED,
        actor_club_id=actor_club_id,
        payload={"fee_amount": str(fee_amount) if fee_amount else None},
    ))
    await db.flush()
    return offer


async def improve_own_offer(
    db: AsyncSession,
    offer: Offer,
    *,
    actor_club_id: uuid.UUID,
    fee_amount: Decimal | None = None,
    wage_weekly: Decimal | None = None,
    add_ons: dict | None = None,
) -> Offer:
    """Let the buyer sweeten their own pending offer while waiting for a reply.

    Item 2: turn-taking blocked a buyer from raising their own offer while it
    was out for the seller's consideration (e.g. a deadline-day bump). This is
    a narrow, one-directional exception: only the buyer, only upward, and it
    does NOT hand the turn back — the seller still holds the decision either
    way, so last_actor_club_id is left untouched.
    """
    _check_not_expired(offer)
    if offer.status not in (OfferStatus.SENT, OfferStatus.COUNTERED):
        raise ValueError(f"Cannot improve an offer with status {offer.status}")
    if actor_club_id != offer.from_club_id:
        raise ValueError("Only the buyer can improve their own offer")

    new_fee = fee_amount if fee_amount is not None else (offer.fee_amount or Decimal("0"))
    new_wage = wage_weekly if wage_weekly is not None else (offer.wage_weekly or Decimal("0"))
    new_add_ons = dict(offer.add_ons or {})
    if add_ons:
        new_add_ons.update(add_ons)

    old_reserve = offer.reserved_transfer_amount
    new_reserve = new_fee + _add_ons_total(new_add_ons)
    if new_reserve < old_reserve or new_wage < (offer.wage_weekly or Decimal("0")):
        raise ValueError("Improving an offer can only raise its value, not lower it")

    delta = new_reserve - old_reserve
    if delta > 0:
        await clubs_module.service.reserve_budget(
            db, club_id=actor_club_id, transfer_amount=delta
        )
    offer.reserved_transfer_amount = new_reserve

    offer.fee_amount = new_fee
    offer.wage_weekly = new_wage
    offer.add_ons = new_add_ons
    db.add(OfferEvent(
        offer_id=offer.id,
        event_type=OfferEventType.IMPROVED,
        actor_club_id=actor_club_id,
        payload={"fee_amount": str(new_fee)},
    ))
    await db.flush()
    return offer


async def accept_offer(
    db: AsyncSession,
    offer: Offer,
    *,
    actor_club_id: uuid.UUID,
) -> Deal:
    """Accept an offer. Creates a Deal and commits the buyer's reserved budget."""
    _check_not_expired(offer)
    if offer.status not in (OfferStatus.SENT, OfferStatus.COUNTERED):
        raise ValueError(f"Cannot accept an offer with status {offer.status}")
    _require_party(offer, actor_club_id)
    _require_turn(offer, actor_club_id)

    # TRA-138: the club this offer names as seller must actually own the player
    if offer.to_club_id is not None:
        from app.players import service as players_service
        from app.players.models import Player

        player_result = await db.execute(select(Player).where(Player.id == offer.player_id))
        player = player_result.scalar_one_or_none()
        owning_club_id = await players_service.get_owning_club_id(db, player) if player else None
        if player is None or owning_club_id != offer.to_club_id:
            raise ValueError("Receiving club does not currently own this player")

    # Commit the reserved budget from buyer
    reserved = offer.reserved_transfer_amount
    if reserved > 0:
        await clubs_module.service.commit_budget(
            db, club_id=offer.from_club_id, transfer_amount=reserved
        )
        offer.reserved_transfer_amount = Decimal("0")

    offer.status = OfferStatus.ACCEPTED
    db.add(OfferEvent(
        offer_id=offer.id,
        event_type=OfferEventType.ACCEPTED,
        actor_club_id=actor_club_id,
        payload={},
    ))

    deal = Deal(
        offer_id=offer.id,
        buyer_club_id=offer.from_club_id,
        seller_club_id=offer.to_club_id,
        player_id=offer.player_id,
        agreed_fee=offer.fee_amount or Decimal("0"),
        agreed_wage_weekly=offer.wage_weekly,
        status=DealStatus.IN_PROGRESS,
        stage=DealStage.AGREEMENT,
    )
    db.add(deal)
    await db.flush()

    await audit_service.emit(
        db,
        entity_type="OFFER", entity_id=offer.id,
        action="OFFER_ACCEPTED",
        description=f"Offer accepted — deal {deal.id} created",
    )
    await audit_service.emit(
        db,
        entity_type="DEAL", entity_id=deal.id,
        action="DEAL_CREATED",
        payload={"agreed_fee": str(deal.agreed_fee), "stage": deal.stage.value},
        description="Deal created from accepted offer",
    )

    # Item 1: the player now has an active deal in progress — every other
    # pending offer for them is moot. Reject those, release their reservations,
    # and tell the rival buyers, instead of leaving them locked up for days.
    await reject_offers_for_player(db, offer.player_id, exclude_offer_id=offer.id)

    # TRA-125: if the player has an active mandate, pull the agent in immediately.
    await maybe_invite_agent_for_deal(db, deal)

    return deal


async def reject_offers_for_player(
    db: AsyncSession, player_id: uuid.UUID, *, exclude_offer_id: uuid.UUID | None = None
) -> None:
    """Reject every open offer for this player (except one, if given), release
    the rival buyers' reservations, and notify them.

    Item 1: used whenever the player ends up with a deal via any pathway —
    an accepted offer excludes itself; other deal-creation paths (e.g. item
    14's release-clause trigger) pass no exclusion at all.
    """
    from app.notifications import service as notif_service
    from app.notifications.models import NotificationType

    query = select(Offer).where(
        Offer.player_id == player_id,
        Offer.status.in_([OfferStatus.SENT, OfferStatus.COUNTERED]),
    )
    if exclude_offer_id is not None:
        query = query.where(Offer.id != exclude_offer_id)
    result = await db.execute(query)
    siblings = list(result.scalars())

    for sibling in siblings:
        await _release_offer_budget(db, sibling)
        sibling.status = OfferStatus.REJECTED
        db.add(OfferEvent(
            offer_id=sibling.id,
            event_type=OfferEventType.REJECTED,
            payload={"reason": "player_signed_elsewhere"},
        ))
        await notif_service.notify_club(
            db,
            sibling.from_club_id,
            type=NotificationType.OFFER_REJECTED,
            message="This player has signed elsewhere — your offer has been withdrawn",
            link=f"/offers/{sibling.id}",
            related_player_id=sibling.player_id,
        )

    if siblings:
        await db.flush()


async def maybe_invite_agent_for_deal(db: AsyncSession, deal: Deal) -> None:
    """Check for an active mandate and, if found, transition deal to AGENT_NEGOTIATION.

    Public (not offer-specific) so any deal-creation pathway — accepted offer,
    item 14's release-clause trigger, item 13's free-agent signing — can invite
    the player's agent the same way.
    """
    from app.agents.models import AgentDealInvitation
    from app.auth.models import AgentProfile
    from app.mandates.models import Mandate, MandateStatus
    from app.notifications import service as notif_service
    from app.notifications.models import NotificationType
    from app.players.models import Player

    mandate_result = await db.execute(
        select(Mandate)
        .where(
            Mandate.player_id == deal.player_id,
            Mandate.status == MandateStatus.ACTIVE,
        )
        .order_by(Mandate.exclusive.desc(), Mandate.created_at.desc())
        .limit(1)
    )
    mandate = mandate_result.scalar_one_or_none()
    if mandate is None:
        return

    deal.stage = DealStage.AGENT_NEGOTIATION

    invitation = AgentDealInvitation(deal_id=deal.id, agent_id=mandate.agent_id)
    db.add(invitation)
    await db.flush()

    agent_result = await db.execute(
        select(AgentProfile).where(AgentProfile.id == mandate.agent_id)
    )
    agent = agent_result.scalar_one_or_none()
    if agent is None:
        return

    player_result = await db.execute(
        select(Player).where(Player.id == deal.player_id)
    )
    player = player_result.scalar_one_or_none()
    player_name = player.name if player else "a player"
    fee = deal.agreed_fee or Decimal("0")

    await notif_service.create_notification(
        db,
        recipient_user_id=agent.user_id,
        type=NotificationType.DEAL_AGENT_INVITED,
        message=(
            f"You have been invited to negotiate the transfer of {player_name}. "
            f"Agreed fee: £{fee:,.0f}"
        ),
        link=f"/deals/{deal.id}",
        related_player_id=deal.player_id,
    )


async def reject_offer(
    db: AsyncSession,
    offer: Offer,
    *,
    actor_club_id: uuid.UUID,
) -> Offer:
    """Reject an offer. Releases the buyer's budget reservation."""
    _check_not_expired(offer)
    if offer.status not in (OfferStatus.SENT, OfferStatus.COUNTERED):
        raise ValueError(f"Cannot reject an offer with status {offer.status}")
    _require_party(offer, actor_club_id)
    _require_turn(offer, actor_club_id)

    await _release_offer_budget(db, offer)
    offer.status = OfferStatus.REJECTED
    db.add(OfferEvent(
        offer_id=offer.id,
        event_type=OfferEventType.REJECTED,
        actor_club_id=actor_club_id,
        payload={},
    ))
    await db.flush()
    return offer


async def withdraw_offer(
    db: AsyncSession,
    offer: Offer,
    *,
    actor_club_id: uuid.UUID,
) -> Offer:
    """Withdraw an offer.

    The original sender (from_club) can always withdraw. Item 2: whoever made
    the most recent move — including a seller who just countered — can also
    retract that outstanding proposal without waiting for the other party to
    respond first. A party who is NOT the last actor still can't withdraw;
    their move is reject_offer, which correctly requires the turn.
    """
    _require_party(offer, actor_club_id)
    if actor_club_id != offer.from_club_id and actor_club_id != offer.last_actor_club_id:
        raise ValueError("You can only retract your own most recent offer")
    if _is_terminal(offer.status):
        raise ValueError(f"Cannot withdraw an offer with status {offer.status}")

    await _release_offer_budget(db, offer)
    offer.status = OfferStatus.WITHDRAWN
    db.add(OfferEvent(
        offer_id=offer.id,
        event_type=OfferEventType.WITHDRAWN,
        actor_club_id=actor_club_id,
        payload={},
    ))
    await db.flush()
    return offer


async def add_message(
    db: AsyncSession,
    offer: Offer,
    *,
    sender_club_id: uuid.UUID,
    body: str,
) -> OfferMessage:
    """Add a message to an offer thread."""
    _require_party(offer, sender_club_id)
    if _is_terminal(offer.status):
        raise ValueError("Cannot message on a closed offer")

    msg = OfferMessage(
        offer_id=offer.id,
        sender_club_id=sender_club_id,
        body=body,
    )
    db.add(msg)
    db.add(OfferEvent(
        offer_id=offer.id,
        event_type=OfferEventType.MESSAGE,
        actor_club_id=sender_club_id,
        payload={"body_preview": body[:100]},
    ))
    await db.flush()
    return msg


async def get_offer_competition(
    db: AsyncSession,
    player_id: uuid.UUID,
    my_club_id: uuid.UUID | None,
) -> "OrderBookResponse":
    """Player-scoped order book. Works for both sale-linked and standalone offers."""
    from app.sales.schemas import OrderBookClubSummary, OrderBookEntry, OrderBookResponse
    from app.sales.service import _band_width, _compute_tiers, _fmt_millions

    result = await db.execute(
        select(Offer)
        .where(Offer.player_id == player_id)
        .options(selectinload(Offer.from_club))
        .order_by(Offer.fee_amount.desc().nullsfirst(), Offer.created_at.asc())
    )
    all_offers = list(result.scalars())

    _active = {OfferStatus.SENT, OfferStatus.COUNTERED}
    active_offers = [o for o in all_offers if o.status in _active]
    active_count = len(active_offers)

    # Seller = receives offers (to_club_id matches viewer)
    is_seller = my_club_id is not None and any(
        o.to_club_id is not None and str(o.to_club_id) == str(my_club_id)
        for o in all_offers
    )

    def _sort_key(o: Offer):
        return (o.status not in _active, -float(o.fee_amount or 0))

    entries: list[OrderBookEntry] = []
    rank = 1
    for offer in sorted(all_offers, key=_sort_key):
        is_active = offer.status in _active
        entry = OrderBookEntry(
            rank=rank if is_active else 0,
            kind="offer",
            id=offer.id,
            club=OrderBookClubSummary(
                id=offer.from_club.id,
                name=offer.from_club.name,
                crest_url=getattr(offer.from_club, "crest_url", None),
            ) if offer.from_club else None,
            fee_amount=offer.fee_amount,
            wage_weekly=offer.wage_weekly,
            status=offer.status.value,
            is_countered=offer.status == OfferStatus.COUNTERED,
            is_active=is_active,
            last_action_at=offer.last_action_at,
        )
        entries.append(entry)
        if is_active:
            rank += 1

    if is_seller:
        best = max((o.fee_amount for o in active_offers if o.fee_amount), default=None)
        parts = [f"{active_count} {'club' if active_count == 1 else 'clubs'}"]
        if best:
            parts.append(f"Best {_fmt_millions(best)}")
        return OrderBookResponse(
            role="seller",
            active_count=active_count,
            entries=entries,
            summary=" · ".join(parts),
        )
    else:
        my_offer = next(
            (o for o in active_offers if my_club_id and str(o.from_club_id) == str(my_club_id)),
            None,
        )
        if my_offer is None:
            return OrderBookResponse(role="buyer", active_count=active_count)

        active_amounts = [o.fee_amount for o in active_offers if o.fee_amount is not None]
        sorted_amounts = sorted(active_amounts, reverse=True)
        my_rank = (sorted_amounts.index(my_offer.fee_amount) + 1) if my_offer.fee_amount in sorted_amounts else None
        band = _band_width(max(active_amounts)) if active_amounts else Decimal("5000000")
        other_amounts = [
            o.fee_amount for o in active_offers
            if str(o.from_club_id) != str(my_club_id) and o.fee_amount is not None
        ]
        tiers = _compute_tiers(other_amounts, my_offer.fee_amount, band)
        my_entry = next((e for e in entries if str(e.id) == str(my_offer.id)), None)
        return OrderBookResponse(
            role="buyer",
            active_count=active_count,
            tiers=tiers,
            your_rank=my_rank,
            is_leading=my_rank == 1,
            your_entry=my_entry,
        )


async def expire_stale_offers(db: AsyncSession) -> int:
    """Batch-expire all SENT/COUNTERED offers past their expires_at."""
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Offer)
        .where(
            Offer.status.in_([OfferStatus.SENT, OfferStatus.COUNTERED]),
            Offer.expires_at < now,
        )
        .with_for_update(skip_locked=True)
    )
    offers = list(result.scalars())

    count = 0
    for offer in offers:
        await _release_offer_budget(db, offer)
        offer.status = OfferStatus.EXPIRED
        db.add(OfferEvent(
            offer_id=offer.id,
            event_type=OfferEventType.EXPIRED,
            payload={},
        ))
        count += 1

    if count:
        await db.flush()
    return count


# ── Helpers ───────────────────────────────────────────────────────────────────


def _check_not_expired(offer: Offer) -> None:
    if offer.expires_at is None:
        return
    # SQLite returns naive datetimes; treat them as UTC
    exp = offer.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > exp:
        raise ValueError("Offer has expired")


def _require_party(offer: Offer, club_id: uuid.UUID) -> None:
    if club_id not in (offer.from_club_id, offer.to_club_id):
        raise ValueError("You are not a party to this offer")


def _require_turn(offer: Offer, actor_club_id: uuid.UUID) -> None:
    """Enforce turn order: you cannot act if you were the last to act."""
    if offer.last_actor_club_id is not None and offer.last_actor_club_id == actor_club_id:
        raise ValueError("It is not your turn — waiting for the other party to respond")


async def _release_offer_budget(db: AsyncSession, offer: Offer) -> None:
    reserved = offer.reserved_transfer_amount
    if reserved and reserved > 0:
        await clubs_module.service.release_budget(
            db, club_id=offer.from_club_id, transfer_amount=reserved
        )
        offer.reserved_transfer_amount = Decimal("0")
