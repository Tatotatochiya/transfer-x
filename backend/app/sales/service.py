"""M3 — Sales (listings) service layer.

Auctions are retired (product ADR 0011): a club lists a player open to
offers, optionally with a date it will hear offers until, and chooses among
the offers. Old auction listings, bids and the deals they produced stay in
the database as history; nothing creates or acts on them any more."""

import logging
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.common.filters import apply_date_range
from app.deals.models import DealType
from app.sales.models import ListingAvailability, Sale, SaleEvent, SaleEventType, SaleStatus, SaleType

AUCTIONS_RETIRED = (
    "Auctions are no longer offered. List him open to offers, with a date you'll hear offers until if you want one."
)

logger = logging.getLogger(__name__)


# ── Sale CRUD ─────────────────────────────────────────────────────────────────


def validate_listing_terms(
    *, sale_type: SaleType, availability: ListingAvailability, asking_price: Decimal | None
) -> None:
    """What a listing may offer.

    No new auctions (ADR 0011). A fixed price is a transfer price; a fixed-price listing may also welcome loan
    approaches ("either") but cannot be loan-only. A loan-only listing is open
    to offers and carries **no asking price**: a figure on it would read as the
    player's price — to buyers, and to the fair-value signal, which compares an
    asking price against the model's valuation of the player.
    """
    if sale_type == SaleType.AUCTION:
        raise ValueError(AUCTIONS_RETIRED)
    if availability == ListingAvailability.TRANSFER:
        return
    if availability == ListingAvailability.LOAN:
        if sale_type != SaleType.OPEN_TO_OFFERS:
            raise ValueError("A loan-only listing is open to offers — a fixed price is a transfer price")
        if asking_price is not None:
            raise ValueError(
                "A loan-only listing has no asking price — clubs propose the loan fee and wage share"
            )


def check_offer_matches_listing(sale: Sale, *, is_loan: bool) -> None:
    """An offer made against a listing must be one the listing invites.
    Otherwise a loan offer could be accepted against a sale listing and close
    it — the seller wanted to sell and got a loan instead."""
    if sale.status != SaleStatus.OPEN:
        raise ValueError("This listing is no longer open")
    if is_loan and sale.availability == ListingAvailability.TRANSFER:
        raise ValueError("This player is listed for a transfer only — his club is not considering loans")
    if not is_loan and sale.availability == ListingAvailability.LOAN:
        raise ValueError("This player is listed for loan only — make a loan offer instead")


async def create_sale(
    db: AsyncSession,
    *,
    player_id: uuid.UUID,
    seller_club_id: uuid.UUID,
    sale_type: SaleType,
    asking_price: Decimal | None = None,
    reserve_price: Decimal | None = None,
    deadline: datetime | None = None,
    notes: str | None = None,
    availability: ListingAvailability = ListingAvailability.TRANSFER,
) -> Sale:
    validate_listing_terms(sale_type=sale_type, availability=availability, asking_price=asking_price)
    if deadline is not None:
        due = deadline if deadline.tzinfo else deadline.replace(tzinfo=timezone.utc)
        if due <= datetime.now(timezone.utc):
            raise ValueError("The deadline has already passed — choose a later one")
    sale = Sale(
        player_id=player_id,
        seller_club_id=seller_club_id,
        sale_type=sale_type,
        availability=availability,
        asking_price=asking_price,
        reserve_price=reserve_price,
        deadline=deadline,
        notes=notes,
        status=SaleStatus.OPEN,
    )
    db.add(sale)
    await db.flush()
    await sync_listed_flag(db, player_id)

    event = SaleEvent(
        sale_id=sale.id,
        event_type=SaleEventType.CREATED,
        actor_club_id=seller_club_id,
    )
    db.add(event)
    await db.flush()
    return sale


async def sync_listed_flag(db: AsyncSession, player_id: uuid.UUID) -> None:
    """Keep `Player.open_to_offers` equal to "he has an open listing".

    There used to be two ways to say a player was available — a quiet "open to
    offers" switch on the squad, and a public listing — and they disagreed: a
    player page could read "Closed to offers" beside "View listing". They are
    one concept now (product decision, 2026-09-27): a player is listed or he
    is not. The flag is kept, because the market filter, badges, scouting and
    AI search all read it, but only listings write it — every place a listing
    opens or closes calls this. Clubs whose shortlist he is on are told when he
    becomes listed, as the switch used to tell them.
    """
    from app.players.models import Player

    player = (await db.execute(select(Player).where(Player.id == player_id))).scalar_one_or_none()
    if player is None:
        return
    listed = await get_open_sale_for_player(db, player_id) is not None
    if player.open_to_offers == listed:
        return
    player.open_to_offers = listed
    await db.flush()
    if listed:
        try:
            from app.notifications.service import notify_player_available

            await notify_player_available(db, player.id)
        except Exception:
            logger.exception("Could not notify clubs that player %s was listed", player_id)


async def get_open_sale_for_player(db: AsyncSession, player_id: uuid.UUID) -> Sale | None:
    """The player's live listing, if any. There is at most one — enforced by
    the `uq_sales_one_open_per_player` partial unique index."""
    result = await db.execute(
        select(Sale).where(Sale.player_id == player_id, Sale.status == SaleStatus.OPEN)
    )
    return result.scalars().first()


async def get_sale_by_id(db: AsyncSession, sale_id: uuid.UUID) -> Sale | None:
    result = await db.execute(
        select(Sale)
        .where(Sale.id == sale_id)
        .options(
            selectinload(Sale.player),
            selectinload(Sale.seller_club),
        )
    )
    return result.scalar_one_or_none()


async def list_sales(
    db: AsyncSession,
    *,
    status: SaleStatus | None = None,
    sale_type: SaleType | None = None,
    seller_club_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = 1,
    page_size: int = 30,
    available_for: ListingAvailability | None = None,
) -> tuple[list[Sale], int]:
    """`available_for=LOAN` means "a club could loan him" — loan-only listings
    and those open to either. Likewise TRANSFER. EITHER matches EITHER only."""
    from sqlalchemy import func

    q = select(Sale).options(
        selectinload(Sale.player),
        selectinload(Sale.seller_club),
    )
    if status:
        q = q.where(Sale.status == status)
    if sale_type:
        q = q.where(Sale.sale_type == sale_type)
    if available_for in (ListingAvailability.LOAN, ListingAvailability.TRANSFER):
        q = q.where(Sale.availability.in_([available_for, ListingAvailability.EITHER]))
    elif available_for == ListingAvailability.EITHER:
        q = q.where(Sale.availability == ListingAvailability.EITHER)
    if seller_club_id:
        q = q.where(Sale.seller_club_id == seller_club_id)
    q = apply_date_range(q, Sale.created_at, date_from, date_to)

    total_result = await db.execute(select(func.count()).select_from(q.subquery()))
    total = total_result.scalar_one()

    rows = await db.execute(
        q.order_by(Sale.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    return list(rows.scalars()), total


async def withdraw_sale(
    db: AsyncSession, sale: Sale, actor_club_id: uuid.UUID | None, *, staff_reason: str | None = None,
) -> Sale:
    """Withdraw an OPEN sale. Releases the budget held by offers made against
    it, and tells everyone affected.

    With `staff_reason`, TransferX staff are cancelling it (admin panel): the
    messages say who and why, and the seller is told too. The sale ends
    WITHDRAWN either way (there is no separate cancelled status); the admin
    audit event records that staff did it."""
    # Lock the sale row so a concurrent accept can't close it under us.
    locked_result = await db.execute(
        select(Sale).where(Sale.id == sale.id).with_for_update()
    )
    sale = locked_result.scalar_one()

    if sale.status != SaleStatus.OPEN:
        raise ValueError("Only OPEN sales can be withdrawn")

    from app.notifications import service as notif_service
    from app.notifications.models import NotificationType
    from app.offers.models import Offer, OfferEvent, OfferEventType, OfferStatus

    by_staff = f"TransferX staff cancelled this sale: {staff_reason}" if staff_reason else None

    # Item 1: direct offers made against this listing (OPEN_TO_OFFERS sales)
    # otherwise survive the withdrawal untouched and remain acceptable.
    linked_offers_result = await db.execute(
        select(Offer).where(
            Offer.sale_id == sale.id,
            Offer.status.in_([OfferStatus.SENT, OfferStatus.COUNTERED]),
        )
    )
    from app.offers.service import _release_offer_budget

    for offer in linked_offers_result.scalars():
        # Both the fee and the wage held for the offer (the wage used to be
        # left reserved).
        await _release_offer_budget(db, offer)
        offer.status = OfferStatus.REJECTED
        db.add(OfferEvent(
            offer_id=offer.id,
            event_type=OfferEventType.REJECTED,
            payload={"reason": "sale_withdrawn", **({"staff_reason": staff_reason} if staff_reason else {})},
        ))
        await notif_service.notify_club(
            db,
            offer.from_club_id,
            type=NotificationType.OFFER_REJECTED,
            message=by_staff or "The sale you offered on has been withdrawn by the seller",
            link=f"/offers/{offer.id}",
            related_player_id=offer.player_id,
        )

    if staff_reason and sale.seller_club_id:
        await notif_service.notify_club(
            db,
            sale.seller_club_id,
            # A message from TransferX staff; there is no sale-cancelled type.
            type=NotificationType.SYSTEM_BROADCAST,
            message=f"TransferX staff cancelled your listing: {staff_reason}",
            link=f"/sales/{sale.id}",
            related_player_id=sale.player_id,
        )

    sale.status = SaleStatus.WITHDRAWN
    sale.staff_cancel_reason = staff_reason[:500] if staff_reason else None
    await db.flush()
    await sync_listed_flag(db, sale.player_id)
    db.add(
        SaleEvent(
            sale_id=sale.id,
            event_type=SaleEventType.SALE_WITHDRAWN,
            actor_club_id=actor_club_id,
        )
    )
    await db.flush()
    return sale


async def close_sale_after_offer_accepted(
    db: AsyncSession, sale_id: uuid.UUID, *, actor_club_id: uuid.UUID
) -> None:
    """Close a listing because a direct offer made against it was accepted.

    Without this the listing stayed OPEN forever: the player kept showing as
    "Listed" while his deal was already in progress."""
    result = await db.execute(
        select(Sale)
        .where(Sale.id == sale_id)
        .with_for_update()
    )
    sale = result.scalar_one_or_none()
    if sale is None or sale.status != SaleStatus.OPEN:
        return

    sale.status = SaleStatus.CLOSED
    await db.flush()
    await sync_listed_flag(db, sale.player_id)
    db.add(
        SaleEvent(
            sale_id=sale.id,
            event_type=SaleEventType.SALE_CLOSED,
            actor_club_id=actor_club_id,
        )
    )
    await db.flush()


# ── Background job: close expired sales ──────────────────────────────────────


async def close_expired_sales(db: AsyncSession) -> int:
    """Expire OPEN listings past their deadline.

    An "Open to offers" listing's deadline is optional, and says "we will
    hear offers until…". Offers already made against an expired listing are
    untouched: they run to their own expiry and can still be answered.

    Returns the number of sales expired.
    """
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(Sale)
        .where(
            Sale.status == SaleStatus.OPEN,
            Sale.deadline.is_not(None),
            Sale.deadline < now,
        )
        .with_for_update(skip_locked=True)
    )
    expired_sales = list(result.scalars())

    count = 0
    for sale in expired_sales:
        sale.status = SaleStatus.EXPIRED
        db.add(SaleEvent(sale_id=sale.id, event_type=SaleEventType.SALE_EXPIRED))
        await db.flush()
        await sync_listed_flag(db, sale.player_id)
        count += 1

    if count:
        await db.flush()
    return count


# ── Order book ────────────────────────────────────────────────────────────────


def _band_width(max_amount: Decimal) -> Decimal:
    if max_amount < Decimal("5000000"):
        return Decimal("500000")
    elif max_amount < Decimal("20000000"):
        return Decimal("2000000")
    else:
        return Decimal("5000000")


def _fmt_millions(v: Decimal) -> str:
    m = v / Decimal("1000000")
    if m == m.to_integral_value():
        return f"£{int(m)}M"
    return f"£{float(m):.1f}M"


def _compute_tiers(
    amounts: list[Decimal],
    your_amount: Decimal | None,
    band: Decimal,
) -> list["OrderBookTier"]:
    from math import floor as _floor
    from app.sales.schemas import OrderBookTier
    if not amounts:
        return []
    min_v = min(amounts)
    max_v = max(amounts)
    band_floor = Decimal(str(_floor(float(min_v) / float(band)))) * band
    tiers: list[OrderBookTier] = []
    current = band_floor
    while current <= max_v:
        upper = current + band
        count = sum(1 for a in amounts if current <= a < upper)
        if count > 0:
            includes = your_amount is not None and current <= your_amount < upper
            tiers.append(OrderBookTier(
                label=f"{_fmt_millions(current)}–{_fmt_millions(upper)}",
                count=count,
                includes_yours=includes,
            ))
        current = upper
    tiers.reverse()  # highest tier first
    return tiers


async def get_order_book(
    db: AsyncSession,
    sale: Sale,
    my_club_id: uuid.UUID | None,
) -> "OrderBookResponse":
    from app.sales.schemas import OrderBookResponse
    from app.offers import service as offers_svc
    from app.offers.models import OfferStatus

    is_seller = my_club_id is not None and str(my_club_id) == str(sale.seller_club_id)

    # The offers made against the listing.
    all_offers = await offers_svc.list_offers_for_sale(db, sale.id)
    _active_statuses = {OfferStatus.SENT, OfferStatus.COUNTERED}
    active_offers = [o for o in all_offers if o.status in _active_statuses]
    active_count = len(active_offers)

    # Shared with the player-scoped competition view, including its
    # anonymous-buyer mask — this copy used to build its own rows and named
    # an anonymous buyer to the seller of the very listing they bid on.
    entries = offers_svc.order_book_entries(all_offers, my_club_id)

    if is_seller:
        best = max(
            (o.fee_amount for o in active_offers if o.fee_amount and o.deal_type != DealType.LOAN),
            default=None,
        )
        reserve_met = (
            sale.reserve_price is not None
            and best is not None
            and best >= sale.reserve_price
        )
        parts = [f"{active_count} {'club' if active_count == 1 else 'clubs'}"]
        if best:
            parts.append(f"Best {_fmt_millions(best)}")
        if sale.reserve_price is not None:
            parts.append("Reserve: Met" if reserve_met else "Reserve: Not met")
        parts.extend(offers_svc.loan_summary_parts(active_offers))
        return OrderBookResponse(
            sale_id=sale.id,
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
            return OrderBookResponse(sale_id=sale.id, role="buyer", active_count=active_count)
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
            sale_id=sale.id,
            role="buyer",
            active_count=active_count,
            tiers=tiers,
            your_rank=my_rank,
            is_leading=my_rank == 1,
            your_entry=my_entry,
        )
