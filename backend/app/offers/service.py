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
from app.common.schemas import WhoseMove
from app.deals.models import Deal, DealStage, DealStatus, DealType
from app.offers.models import Offer, OfferEvent, OfferEventType, OfferMessage, OfferStatus

_OFFER_EXPIRY_DAYS = 7
_TERMINAL = {OfferStatus.ACCEPTED, OfferStatus.REJECTED, OfferStatus.WITHDRAWN, OfferStatus.EXPIRED}


def _is_terminal(status: OfferStatus) -> bool:
    return status in _TERMINAL


def compute_offer_whose_move(offer: Offer, viewer_club_id: uuid.UUID | None) -> WhoseMove:
    """B1: mirrors offerWhoseMove() in frontend/src/lib/whoseMove.ts exactly."""
    if _is_terminal(offer.status):
        return WhoseMove.NEITHER
    return WhoseMove.THEIR if offer.last_actor_club_id == viewer_club_id else WhoseMove.YOUR


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


def _reservation(
    *,
    deal_type: DealType,
    fee_amount: Decimal | None,
    loan_fee: Decimal | None,
    add_ons: dict | None,
    wage_weekly: Decimal | None,
    wage_split_pct: Decimal | None,
) -> tuple[Decimal, Decimal]:
    """What a buying club must have free to hold this offer: (transfer, weekly wage).

    Two things this centralises that were previously wrong or absent:

    A loan's money is `loan_fee`, not `fee_amount` — the two are mutually
    exclusive and validation enforces that — so reserving against `fee_amount`
    would reserve nothing at all for a loan.

    **Wage has never been reserved by any offer path.** `reserve_budget` has
    accepted a `wage_weekly` argument with a real affordability check behind it
    (`clubs/service.py:414`) since it was written, and not one of the six budget
    calls in this module ever passed one — so a club could commit to wages it
    had no room for and only find out at completion, when `_complete_deal` adds
    the wage regardless. That is a permanent-transfer bug that loans merely
    surfaced; it is fixed here for every offer type.

    For a loan the buyer carries only their agreed share, so a loan with no fee
    still costs real budget. A null split means the loanee pays all of it.
    """
    if deal_type == DealType.LOAN:
        transfer = (loan_fee or Decimal("0")) + _add_ons_total(add_ons)
        share = wage_split_pct if wage_split_pct is not None else Decimal("1")
        wage = (wage_weekly or Decimal("0")) * share
    else:
        transfer = (fee_amount or Decimal("0")) + _add_ons_total(add_ons)
        wage = wage_weekly or Decimal("0")
    return transfer, wage.quantize(Decimal("0.01"))


def _offer_reservation(offer: Offer, **overrides) -> tuple[Decimal, Decimal]:
    """`_reservation` for an existing offer, with named fields overridden."""
    fields = {
        "deal_type": offer.deal_type,
        "fee_amount": offer.fee_amount,
        "loan_fee": offer.loan_fee,
        "add_ons": offer.add_ons,
        "wage_weekly": offer.wage_weekly,
        "wage_split_pct": offer.wage_split_pct,
    }
    fields.update({k: v for k, v in overrides.items() if v is not None})
    return _reservation(**fields)


def approval_amount(
    *,
    deal_type: DealType,
    fee_amount: Decimal | None,
    loan_fee: Decimal | None,
    option_to_buy: Decimal | None,
    obligation_to_buy: bool,
) -> Decimal | None:
    """The figure a spending-approval threshold (D7) is tested against.

    A permanent offer's is its transfer fee, as it always was. A loan carries no
    `fee_amount` — validation forbids one — so testing that field let every loan
    past the threshold, however much it committed the club to. A loan's
    commitment is its loan fee plus, when it carries an obligation to buy, the
    purchase price: an obligation is a sale agreed now and paid later. An option
    is not counted, because it is a right the club may never use.
    """
    if deal_type == DealType.LOAN:
        total = loan_fee or Decimal("0")
        if obligation_to_buy and option_to_buy is not None:
            total += option_to_buy
        return total
    return fee_amount


_MAX_LOAN_MONTHS = 18


async def validate_offer_terms(
    db: AsyncSession,
    *,
    player_id: uuid.UUID,
    deal_type: DealType,
    fee_amount: Decimal | None,
    loan_start: date | None,
    loan_end: date | None,
    loan_fee: Decimal | None,
    wage_split_pct: Decimal | None,
    option_to_buy: Decimal | None,
    obligation_to_buy: bool,
    recall_allowed: bool,
) -> None:
    """Re-check the loan rules the request schema already checked.

    Deliberately duplicated rather than trusted from the schema layer: every
    other money guard in this module is enforced here too, and `create_offer`
    is callable from paths that never see an `OfferCreateRequest`.
    """
    if deal_type not in (DealType.PERMANENT, DealType.LOAN):
        raise ValueError(
            f"An offer may only be PERMANENT or LOAN, not {deal_type.value} — "
            "free transfers and pre-contracts are created by the signing paths, not offered"
        )

    if deal_type == DealType.PERMANENT:
        if any(v is not None for v in (loan_start, loan_end, loan_fee, wage_split_pct, option_to_buy)):
            raise ValueError("Loan terms are not valid on a permanent offer")
        if obligation_to_buy or recall_allowed:
            raise ValueError("Loan terms are not valid on a permanent offer")
        # A missing fee used to be offered as "No fee — a free transfer or a
        # swap". Neither holds: an out-of-contract player is signed through the
        # free-agent and pre-contract paths, not offered for, and a swap cannot
        # be recorded here at all. A contracted player's transfer always names
        # a fee — £0 is allowed, with a reason (see create_offer).
        if fee_amount is None:
            raise ValueError(
                "A permanent transfer needs a fee — enter £0 if his club is to release him for nothing"
            )
        return

    # ── LOAN ────────────────────────────────────────────────────────────────
    if fee_amount is not None:
        raise ValueError("A loan's money is its loan fee — leave the transfer fee empty")
    if loan_start is None or loan_end is None:
        raise ValueError("A loan needs both a start and an end date")
    if loan_end <= loan_start:
        raise ValueError("A loan must end after it starts")
    if loan_end > loan_start + timedelta(days=_MAX_LOAN_MONTHS * 31):
        raise ValueError(f"A loan may not run longer than {_MAX_LOAN_MONTHS} months")
    if wage_split_pct is not None and not (Decimal("0") <= wage_split_pct <= Decimal("1")):
        raise ValueError("Wage split must be between 0 and 1 — it is a fraction, not a percentage")
    if obligation_to_buy and option_to_buy is None:
        raise ValueError("An obligation to buy needs a price — set the option-to-buy amount")

    # You cannot loan a player past the point you control him. Without this the
    # phase-3 return path would find an expired parent contract and correctly,
    # but very surprisingly, make him a free agent.
    parent = await _parent_contract(db, player_id)
    parent_end = parent.end_date if parent is not None else None
    if parent_end is not None and loan_end > parent_end:
        raise ValueError(
            f"The loan ends {loan_end}, after the player's contract expires "
            f"({parent_end}) — shorten the loan or extend the contract first"
        )


async def _parent_contract(db: AsyncSession, player_id: uuid.UUID):
    """The player's active contract — the parent club's, before any loan."""
    from app.players.models import Contract

    return (
        await db.execute(
            select(Contract).where(
                Contract.player_id == player_id,
                Contract.is_active == True,  # noqa: E712
            )
        )
    ).scalars().first()


async def loan_wage_basis(db: AsyncSession, player_id: uuid.UUID) -> Decimal:
    """The weekly wage a loan's split is a share of: the player's own contract.

    The buyer used to type this, and the loan was then built on whatever they
    typed — a blank meant the borrowing club paid £0, and a wrong figure became
    the wage on his loan contract. It is the parent's contract wage, so it is
    read from there. A contract with no wage on record refuses the loan rather
    than proceeding on £0: the finance of every later step depends on it.
    """
    parent = await _parent_contract(db, player_id)
    if parent is None or not parent.wage_weekly:
        raise ValueError(
            "His contract has no wage on record, so a loan's wage share cannot be worked out — "
            "his club needs to record it first"
        )
    return parent.wage_weekly


def reject_client_loan_wage(deal_type: DealType, wage_weekly: Decimal | None) -> None:
    """A loan's wage is his contract wage, never a proposed figure. Clubs
    negotiate the share (`wage_split_pct`), not the salary."""
    if deal_type == DealType.LOAN and wage_weekly is not None:
        raise ValueError(
            "A loan's wage is his current contract wage — propose the share you pay, not a figure"
        )


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


async def check_new_offer(
    db: AsyncSession,
    *,
    player_id: uuid.UUID,
    deal_type: DealType,
    fee_amount: Decimal | None,
    wage_weekly: Decimal | None,
    loan_start: date | None,
    loan_end: date | None,
    loan_fee: Decimal | None,
    wage_split_pct: Decimal | None,
    option_to_buy: Decimal | None,
    obligation_to_buy: bool,
    recall_allowed: bool,
    no_fee_reason: str | None,
) -> None:
    """Every rule a new offer's terms must pass. Separate from `create_offer`
    so the router can run it before capturing a spending approval — otherwise
    an invalid offer is queued for an approver and only fails once approved."""
    reject_client_loan_wage(deal_type, wage_weekly)
    if (
        deal_type == DealType.PERMANENT
        and fee_amount is not None
        and fee_amount == 0
        and not (no_fee_reason or "").strip()
    ):
        raise ValueError(
            "A £0 offer needs a reason the selling club can read — "
            "for example, releasing him to clear his wages"
        )
    await validate_offer_terms(
        db,
        player_id=player_id,
        deal_type=deal_type,
        fee_amount=fee_amount,
        loan_start=loan_start,
        loan_end=loan_end,
        loan_fee=loan_fee,
        wage_split_pct=wage_split_pct,
        option_to_buy=option_to_buy,
        obligation_to_buy=obligation_to_buy,
        recall_allowed=recall_allowed,
    )
    if deal_type == DealType.LOAN:
        await loan_wage_basis(db, player_id)


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
    is_anonymous: bool = False,
    deal_type: DealType = DealType.PERMANENT,
    loan_start: date | None = None,
    loan_end: date | None = None,
    loan_fee: Decimal | None = None,
    wage_split_pct: Decimal | None = None,
    option_to_buy: Decimal | None = None,
    obligation_to_buy: bool = False,
    recall_allowed: bool = False,
    no_fee_reason: str | None = None,
) -> Offer:
    """Create and immediately send an offer. Reserves budget from from_club.

    `no_fee_reason` is required when a permanent offer's fee is £0, and is
    posted as the offer's first message so the selling club reads why.
    """
    if to_club_id and to_club_id == from_club_id:
        raise ValueError("Cannot make an offer to your own club")

    await check_new_offer(
        db,
        player_id=player_id,
        deal_type=deal_type,
        fee_amount=fee_amount,
        wage_weekly=wage_weekly,
        loan_start=loan_start,
        loan_end=loan_end,
        loan_fee=loan_fee,
        wage_split_pct=wage_split_pct,
        option_to_buy=option_to_buy,
        obligation_to_buy=obligation_to_buy,
        recall_allowed=recall_allowed,
        no_fee_reason=no_fee_reason,
    )
    reason = (no_fee_reason or "").strip()

    if deal_type == DealType.LOAN:
        wage_weekly = await loan_wage_basis(db, player_id)

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
        reserved_wage_weekly=Decimal("0"),
        last_actor_club_id=from_club_id,  # buyer sent it → seller's turn
        is_anonymous=is_anonymous,
        deal_type=deal_type,
        loan_start=loan_start,
        loan_end=loan_end,
        loan_fee=loan_fee,
        wage_split_pct=wage_split_pct,
        option_to_buy=option_to_buy,
        obligation_to_buy=obligation_to_buy,
        recall_allowed=recall_allowed,
    )

    # Reserve budget immediately on send — transfer and wage both, see _reservation.
    reserve, wage_reserve = _reservation(
        deal_type=deal_type,
        fee_amount=fee_amount,
        loan_fee=loan_fee,
        add_ons=add_ons,
        wage_weekly=wage_weekly,
        wage_split_pct=wage_split_pct,
    )
    if reserve > 0 or wage_reserve > 0:
        await clubs_module.service.reserve_budget(
            db, club_id=from_club_id, transfer_amount=reserve, wage_weekly=wage_reserve
        )
        offer.reserved_transfer_amount = reserve
        offer.reserved_wage_weekly = wage_reserve

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

    # Why a £0 offer names no fee, where the selling club reads everything
    # else about the negotiation — and on the record.
    if deal_type == DealType.PERMANENT and fee_amount == 0:
        await add_message(db, offer, sender_club_id=from_club_id, body=f"Why £0: {reason}")
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
    loan_start: date | None = None,
    loan_end: date | None = None,
    loan_fee: Decimal | None = None,
    wage_split_pct: Decimal | None = None,
    option_to_buy: Decimal | None = None,
    obligation_to_buy: bool | None = None,
    recall_allowed: bool | None = None,
) -> Offer:
    """Counter an offer with new terms. Either party can counter.

    A term left as None is unchanged. The merged terms are validated exactly as
    a new offer's are: before this, a counter was never validated at all, so it
    could give a loan a transfer fee, a 500% wage split, or an end date past
    the player's contract — none of which `create_offer` would have allowed.
    """
    _check_not_expired(offer)
    if _is_terminal(offer.status):
        raise ValueError(f"Cannot counter an offer with status {offer.status}")
    if offer.status not in (OfferStatus.SENT, OfferStatus.COUNTERED):
        raise ValueError("Only SENT or COUNTERED offers can be countered")

    # Validate actor is a party to the offer
    _require_party(offer, actor_club_id)
    _require_turn(offer, actor_club_id)
    reject_client_loan_wage(offer.deal_type, wage_weekly)

    changes = {
        "fee_amount": fee_amount,
        "wage_weekly": wage_weekly,
        "loan_start": loan_start,
        "loan_end": loan_end,
        "loan_fee": loan_fee,
        "wage_split_pct": wage_split_pct,
        "option_to_buy": option_to_buy,
        "obligation_to_buy": obligation_to_buy,
        "recall_allowed": recall_allowed,
    }
    changes = {k: v for k, v in changes.items() if v is not None}

    def _merged(field: str):
        return changes.get(field, getattr(offer, field))

    await validate_offer_terms(
        db,
        player_id=offer.player_id,
        deal_type=offer.deal_type,
        fee_amount=_merged("fee_amount"),
        loan_start=_merged("loan_start"),
        loan_end=_merged("loan_end"),
        loan_fee=_merged("loan_fee"),
        wage_split_pct=_merged("wage_split_pct"),
        option_to_buy=_merged("option_to_buy"),
        obligation_to_buy=bool(_merged("obligation_to_buy")),
        recall_allowed=bool(_merged("recall_allowed")),
    )

    # If from_club counters (buyer raises their offer), adjust reservation.
    # Item 3: add_ons now counts toward the reservation too, so recompute
    # whenever either the fee or the add_ons change, not just the fee.
    # A wage or loan-fee change moves the reservation as well, so those count too.
    if actor_club_id == offer.from_club_id and any(
        v is not None for v in (fee_amount, add_ons, wage_weekly, loan_fee, wage_split_pct)
    ):
        old_reserve = offer.reserved_transfer_amount
        old_wage_reserve = offer.reserved_wage_weekly
        new_reserve, new_wage_reserve = _offer_reservation(
            offer,
            fee_amount=fee_amount,
            add_ons=add_ons,
            wage_weekly=wage_weekly,
            loan_fee=loan_fee,
            wage_split_pct=wage_split_pct,
        )
        delta = new_reserve - old_reserve
        wage_delta = new_wage_reserve - old_wage_reserve
        # Take the increases first so an insufficient-budget failure aborts
        # before anything has been given back.
        if delta > 0 or wage_delta > 0:
            await clubs_module.service.reserve_budget(
                db,
                club_id=actor_club_id,
                transfer_amount=max(Decimal("0"), delta),
                wage_weekly=max(Decimal("0"), wage_delta),
            )
        if delta < 0 or wage_delta < 0:
            await clubs_module.service.release_budget(
                db,
                club_id=actor_club_id,
                transfer_amount=max(Decimal("0"), -delta),
                wage_weekly=max(Decimal("0"), -wage_delta),
            )
        offer.reserved_transfer_amount = new_reserve
        offer.reserved_wage_weekly = new_wage_reserve

    # Update terms. `deal_type` is deliberately absent: countering a loan with
    # a permanent offer is a different proposal, not a counter.
    if fee_amount is not None:
        offer.fee_amount = fee_amount
    if wage_weekly is not None:
        offer.wage_weekly = wage_weekly
    if loan_fee is not None:
        offer.loan_fee = loan_fee
    if wage_split_pct is not None:
        offer.wage_split_pct = wage_split_pct
    if loan_start is not None:
        offer.loan_start = loan_start
    if loan_end is not None:
        offer.loan_end = loan_end
    if option_to_buy is not None:
        offer.option_to_buy = option_to_buy
    if obligation_to_buy is not None:
        offer.obligation_to_buy = obligation_to_buy
    if recall_allowed is not None:
        offer.recall_allowed = recall_allowed
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
        # Every term the counter changed, not just the fee — a loan counter
        # changes no fee at all, and its audit entry used to record nothing.
        payload={
            "fee_amount": str(fee_amount) if fee_amount else None,
            "changes": {
                k: v if isinstance(v, bool) else str(v) for k, v in changes.items()
            },
        },
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
    loan_fee: Decimal | None = None,
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
    reject_client_loan_wage(offer.deal_type, wage_weekly)

    if offer.deal_type == DealType.LOAN:
        # A loan never carries a transfer fee. Falling back to `fee_amount or 0`
        # here used to give every improved loan a £0 transfer fee.
        if fee_amount is not None:
            raise ValueError("A loan's money is its loan fee — raise the loan fee instead")
        new_fee = None
    else:
        new_fee = fee_amount if fee_amount is not None else (offer.fee_amount or Decimal("0"))
    new_wage = wage_weekly if wage_weekly is not None else (offer.wage_weekly or Decimal("0"))
    new_loan_fee = loan_fee if loan_fee is not None else offer.loan_fee
    new_add_ons = dict(offer.add_ons or {})
    if add_ons:
        new_add_ons.update(add_ons)

    old_reserve = offer.reserved_transfer_amount
    old_wage_reserve = offer.reserved_wage_weekly
    new_reserve, new_wage_reserve = _offer_reservation(
        offer,
        fee_amount=new_fee,
        loan_fee=new_loan_fee,
        add_ons=new_add_ons,
        wage_weekly=new_wage,
    )
    # Compare what the seller actually receives, not the raw wage: on a loan the
    # buyer's cost is their agreed share, so the share is what may only go up.
    if new_reserve < old_reserve or new_wage_reserve < old_wage_reserve:
        raise ValueError("Improving an offer can only raise its value, not lower it")

    delta = new_reserve - old_reserve
    wage_delta = new_wage_reserve - old_wage_reserve
    if delta > 0 or wage_delta > 0:
        await clubs_module.service.reserve_budget(
            db, club_id=actor_club_id, transfer_amount=delta, wage_weekly=wage_delta
        )
    offer.reserved_transfer_amount = new_reserve
    offer.reserved_wage_weekly = new_wage_reserve

    offer.fee_amount = new_fee
    offer.wage_weekly = new_wage
    offer.loan_fee = new_loan_fee
    offer.add_ons = new_add_ons
    db.add(OfferEvent(
        offer_id=offer.id,
        event_type=OfferEventType.IMPROVED,
        actor_club_id=actor_club_id,
        payload={
            "fee_amount": str(new_fee) if new_fee is not None else None,
            "loan_fee": str(new_loan_fee) if new_loan_fee is not None else None,
        },
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

    # True the buyer's reservation up to the terms actually being accepted.
    # A buyer's own counter already re-reserves, but a *seller's* counter does
    # not — deliberately, since refusing a seller's counter because the buyer
    # is short would tell the seller about the buyer's budget, and the buyer
    # has not agreed to anything yet. So this is where it is squared: after a
    # seller's counter the buyer is the one accepting, a shortfall is refused
    # here and reported to them alone, and a lower counter gives back the
    # difference. Before this, accepting a raised counter committed the old,
    # lower figure while the deal recorded the higher agreed fee.
    reserved = offer.reserved_transfer_amount or Decimal("0")
    wage_reserved = offer.reserved_wage_weekly or Decimal("0")
    target, wage_target = _offer_reservation(offer)
    up, wage_up = max(Decimal("0"), target - reserved), max(Decimal("0"), wage_target - wage_reserved)
    down, wage_down = max(Decimal("0"), reserved - target), max(Decimal("0"), wage_reserved - wage_target)
    if up > 0 or wage_up > 0:
        await clubs_module.service.reserve_budget(
            db, club_id=offer.from_club_id, transfer_amount=up, wage_weekly=wage_up
        )
    if down > 0 or wage_down > 0:
        await clubs_module.service.release_budget(
            db, club_id=offer.from_club_id, transfer_amount=down, wage_weekly=wage_down
        )
    reserved, wage_reserved = target, wage_target

    # Commit the reserved budget from buyer — transfer and wage together, or
    # the wage would stay stuck in `reserved` with nothing left to release it.
    if reserved > 0 or wage_reserved > 0:
        await clubs_module.service.commit_budget(
            db,
            club_id=offer.from_club_id,
            transfer_amount=reserved,
            wage_weekly=wage_reserved,
        )
        offer.reserved_transfer_amount = Decimal("0")
        offer.reserved_wage_weekly = Decimal("0")

    offer.status = OfferStatus.ACCEPTED
    db.add(OfferEvent(
        offer_id=offer.id,
        event_type=OfferEventType.ACCEPTED,
        actor_club_id=actor_club_id,
        payload={},
    ))

    deal = Deal(
        # Carry the originating listing onto the deal: _reopen_sale_after_collapse
        # keys off deal.sale_id, so without this an offer-originated deal could
        # never re-list its sale if it collapsed.
        sale_id=offer.sale_id,
        offer_id=offer.id,
        buyer_club_id=offer.from_club_id,
        seller_club_id=offer.to_club_id,
        player_id=offer.player_id,
        # `agreed_fee` is "the transfer money for this deal, whatever its type",
        # so a loan's fee goes here as well as into `loan_fee`. The duplication
        # is deliberate: collapse_deal releases against agreed_fee, approvals
        # threshold against it, and commission is a share of it — all of which
        # would silently read zero for a loan otherwise. `_complete_deal`
        # already prefers loan_fee when set, and now resolves to the same number.
        agreed_fee=(
            offer.loan_fee if offer.deal_type == DealType.LOAN else offer.fee_amount
        ) or Decimal("0"),
        agreed_wage_weekly=offer.wage_weekly,
        status=DealStatus.IN_PROGRESS,
        stage=DealStage.AGREEMENT,
        deal_type=offer.deal_type,
        loan_start=offer.loan_start,
        loan_end=offer.loan_end,
        loan_fee=offer.loan_fee,
        wage_split_pct=offer.wage_split_pct,
        option_to_buy=offer.option_to_buy,
        obligation_to_buy=offer.obligation_to_buy,
        recall_allowed=offer.recall_allowed,
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

    # ...and so is the listing the offer was made against, for the same reason.
    # accept_bid already closes the sale on the auction path; this is the
    # equivalent for a direct offer accepted against a listing.
    if offer.sale_id is not None:
        from app.sales import service as sales_service

        await sales_service.close_sale_after_offer_accepted(
            db, offer.sale_id, actor_club_id=actor_club_id
        )

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


_ACTIVE_OFFER_STATUSES = {OfferStatus.SENT, OfferStatus.COUNTERED}


def _order_book_club(offer: Offer, my_club_id: uuid.UUID | None):
    """The order book names every club competing for a player, which is exactly
    what an anonymous buyer is avoiding — mask them here too, or the identity
    withheld on the offer itself leaks straight out of the panel beside it.
    Anonymity ends at acceptance, and a club always sees its own entry."""
    from app.sales.schemas import OrderBookClubSummary

    if offer.from_club is None:
        return None
    anonymous = (
        offer.is_anonymous
        and offer.status != OfferStatus.ACCEPTED
        and (my_club_id is None or str(offer.from_club_id) != str(my_club_id))
    )
    if anonymous:
        league = offer.from_club.league_name
        return OrderBookClubSummary(
            id=None,
            name=f"A {league} club" if league else "An undisclosed club",
            crest_url=None,
        )
    return OrderBookClubSummary(
        id=offer.from_club.id,
        name=offer.from_club.name,
        crest_url=getattr(offer.from_club, "crest_url", None),
    )


def order_book_entries(offers: list[Offer], my_club_id: uuid.UUID | None) -> list:
    """Order-book rows for offers — shared by the player-scoped competition view
    and the listing's order book, which used to build them separately and had
    drifted: the listing's copy never masked anonymous buyers.

    Live offers first; within them permanent offers ranked by fee, then loans
    ranked by loan fee. A loan and a permanent offer are not the same kind of
    proposal, so a loan is never ranked as if it were a low transfer bid.
    """
    from app.sales.schemas import OrderBookEntry

    def _key(o: Offer):
        is_loan = o.deal_type == DealType.LOAN
        money = (o.loan_fee if is_loan else o.fee_amount) or 0
        return (o.status not in _ACTIVE_OFFER_STATUSES, is_loan, -float(money))

    entries = []
    rank = 1
    for offer in sorted(offers, key=_key):
        is_active = offer.status in _ACTIVE_OFFER_STATUSES
        entries.append(OrderBookEntry(
            rank=rank if is_active else 0,
            kind="offer",
            id=offer.id,
            club=_order_book_club(offer, my_club_id),
            fee_amount=offer.fee_amount,
            wage_weekly=offer.wage_weekly,
            deal_type=offer.deal_type.value,
            loan_fee=offer.loan_fee,
            status=offer.status.value,
            is_countered=offer.status == OfferStatus.COUNTERED,
            is_active=is_active,
            last_action_at=offer.last_action_at,
        ))
        if is_active:
            rank += 1
    return entries


def loan_summary_parts(active_offers: list[Offer]) -> list[str]:
    """The seller's one-line summary counts loan approaches separately, since
    "Best £30m" says nothing about them."""
    loans = sum(1 for o in active_offers if o.deal_type == DealType.LOAN)
    return [f"{loans} loan {'approach' if loans == 1 else 'approaches'}"] if loans else []


async def get_offer_competition(
    db: AsyncSession,
    player_id: uuid.UUID,
    my_club_id: uuid.UUID | None,
) -> "OrderBookResponse":
    """Player-scoped order book. Works for both sale-linked and standalone offers."""
    from app.sales.schemas import OrderBookResponse
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

    entries = order_book_entries(all_offers, my_club_id)

    if is_seller:
        best = max(
            (o.fee_amount for o in active_offers if o.fee_amount and o.deal_type != DealType.LOAN),
            default=None,
        )
        parts = [f"{active_count} {'club' if active_count == 1 else 'clubs'}"]
        if best:
            parts.append(f"Best {_fmt_millions(best)}")
        parts.extend(loan_summary_parts(active_offers))
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
    reserved = offer.reserved_transfer_amount or Decimal("0")
    wage_reserved = offer.reserved_wage_weekly or Decimal("0")
    if reserved > 0 or wage_reserved > 0:
        await clubs_module.service.release_budget(
            db,
            club_id=offer.from_club_id,
            transfer_amount=reserved,
            wage_weekly=wage_reserved,
        )
        offer.reserved_transfer_amount = Decimal("0")
        offer.reserved_wage_weekly = Decimal("0")
