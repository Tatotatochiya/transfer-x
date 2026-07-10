"""M3 — Sales + Bidding service layer."""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app import clubs as clubs_module
from app.clubs.models import ClubFinance
from app.common.filters import apply_date_range
from app.deals.models import Deal, DealStage, DealStatus
from app.sales.models import Bid, BidStatus, Sale, SaleEvent, SaleEventType, SaleStatus, SaleType


# ── Sale CRUD ─────────────────────────────────────────────────────────────────


async def create_sale(
    db: AsyncSession,
    *,
    player_id: uuid.UUID,
    seller_club_id: uuid.UUID,
    sale_type: SaleType,
    asking_price: Decimal | None = None,
    reserve_price: Decimal | None = None,
    min_increment: Decimal = Decimal("500000"),
    deadline: datetime | None = None,
    notes: str | None = None,
) -> Sale:
    sale = Sale(
        player_id=player_id,
        seller_club_id=seller_club_id,
        sale_type=sale_type,
        asking_price=asking_price,
        reserve_price=reserve_price,
        min_increment=min_increment,
        deadline=deadline,
        notes=notes,
        status=SaleStatus.OPEN,
    )
    db.add(sale)
    await db.flush()

    event = SaleEvent(
        sale_id=sale.id,
        event_type=SaleEventType.CREATED,
        actor_club_id=seller_club_id,
    )
    db.add(event)
    await db.flush()
    return sale


async def get_sale_by_id(db: AsyncSession, sale_id: uuid.UUID) -> Sale | None:
    result = await db.execute(
        select(Sale)
        .where(Sale.id == sale_id)
        .options(
            selectinload(Sale.player),
            selectinload(Sale.seller_club),
            selectinload(Sale.bids).selectinload(Bid.buyer_club),
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
) -> tuple[list[Sale], int]:
    from sqlalchemy import func

    q = select(Sale).options(
        selectinload(Sale.player),
        selectinload(Sale.seller_club),
        selectinload(Sale.bids).selectinload(Bid.buyer_club),
    )
    if status:
        q = q.where(Sale.status == status)
    if sale_type:
        q = q.where(Sale.sale_type == sale_type)
    if seller_club_id:
        q = q.where(Sale.seller_club_id == seller_club_id)
    q = apply_date_range(q, Sale.created_at, date_from, date_to)

    total_result = await db.execute(select(func.count()).select_from(q.subquery()))
    total = total_result.scalar_one()

    rows = await db.execute(
        q.order_by(Sale.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    return list(rows.scalars()), total


async def withdraw_sale(db: AsyncSession, sale: Sale, actor_club_id: uuid.UUID) -> Sale:
    """Withdraw an OPEN sale. Releases all active bid reservations."""
    # Lock the sale row so concurrent bid placements are blocked until we finish
    locked_result = await db.execute(
        select(Sale).where(Sale.id == sale.id).with_for_update()
    )
    sale = locked_result.scalar_one()

    if sale.status != SaleStatus.OPEN:
        raise ValueError("Only OPEN sales can be withdrawn")

    from app.notifications import service as notif_service
    from app.notifications.models import NotificationType
    from app.offers.models import Offer, OfferEvent, OfferEventType, OfferStatus

    # Read active bids after acquiring the lock — no concurrent bids can be added now
    active_bids_result = await db.execute(
        select(Bid).where(Bid.sale_id == sale.id, Bid.status == BidStatus.ACTIVE)
    )
    active_bids = list(active_bids_result.scalars())

    for bid in active_bids:
        bid.status = BidStatus.WITHDRAWN
        await clubs_module.service.release_budget(
            db,
            club_id=bid.buyer_club_id,
            transfer_amount=bid.reserved_transfer_amount,
            wage_weekly=bid.reserved_wage_weekly,
        )
        # Item 1: bidders were never told the sale they bid on was pulled.
        await notif_service.notify_club(
            db,
            bid.buyer_club_id,
            type=NotificationType.OUTBID,
            message="This sale has been withdrawn by the seller",
            link=f"/sales/{sale.id}",
            related_player_id=sale.player_id,
        )

    # Item 1: direct offers made against this listing (OPEN_TO_OFFERS sales)
    # otherwise survive the withdrawal untouched and remain acceptable.
    linked_offers_result = await db.execute(
        select(Offer).where(
            Offer.sale_id == sale.id,
            Offer.status.in_([OfferStatus.SENT, OfferStatus.COUNTERED]),
        )
    )
    for offer in linked_offers_result.scalars():
        reserved = offer.reserved_transfer_amount
        if reserved and reserved > 0:
            await clubs_module.service.release_budget(
                db, club_id=offer.from_club_id, transfer_amount=reserved
            )
            offer.reserved_transfer_amount = Decimal("0")
        offer.status = OfferStatus.REJECTED
        db.add(OfferEvent(
            offer_id=offer.id,
            event_type=OfferEventType.REJECTED,
            payload={"reason": "sale_withdrawn"},
        ))
        await notif_service.notify_club(
            db,
            offer.from_club_id,
            type=NotificationType.OFFER_REJECTED,
            message="The sale you offered on has been withdrawn by the seller",
            link=f"/offers/{offer.id}",
            related_player_id=offer.player_id,
        )

    sale.status = SaleStatus.WITHDRAWN
    db.add(
        SaleEvent(
            sale_id=sale.id,
            event_type=SaleEventType.SALE_WITHDRAWN,
            actor_club_id=actor_club_id,
        )
    )
    await db.flush()
    return sale


# ── Auction helpers ───────────────────────────────────────────────────────────


def get_best_bid_amount(bids: list[Bid]) -> Decimal | None:
    active = [b for b in bids if b.status == BidStatus.ACTIVE]
    if not active:
        return None
    return max(b.amount for b in active)


def get_minimum_next_bid(sale: Sale) -> Decimal:
    best = get_best_bid_amount(sale.bids)
    if best is None:
        # No bids yet — start at asking_price or 1
        return sale.asking_price or Decimal("1")
    return best + sale.min_increment


def is_reserve_met(sale: Sale) -> bool:
    if sale.reserve_price is None:
        return True
    best = get_best_bid_amount(sale.bids)
    if best is None:
        return False
    return best >= sale.reserve_price


# ── Bid placement (concurrency-safe) ─────────────────────────────────────────


async def place_bid(
    db: AsyncSession,
    *,
    sale_id: uuid.UUID,
    buyer_club_id: uuid.UUID,
    amount: Decimal,
    wage_offer_weekly: Decimal | None = None,
    notes: str | None = None,
) -> Bid:
    """Place a bid on an AUCTION sale.

    Uses SELECT FOR UPDATE on the Sale row to prevent concurrent bids.
    Raises ValueError on business rule violations.
    """
    # Lock the sale row
    result = await db.execute(
        select(Sale)
        .where(Sale.id == sale_id)
        .with_for_update()
        .options(selectinload(Sale.bids))
    )
    sale = result.scalar_one_or_none()

    if sale is None:
        raise ValueError("Sale not found")
    if sale.status != SaleStatus.OPEN:
        raise ValueError("Sale is not open for bidding")
    if sale.sale_type != SaleType.AUCTION:
        raise ValueError("Bid can only be placed on AUCTION sales")
    if sale.seller_club_id == buyer_club_id:
        raise ValueError("Cannot bid on your own sale")

    # Check deadline
    if sale.deadline and datetime.now(timezone.utc) > sale.deadline:
        sale.status = SaleStatus.EXPIRED
        db.add(SaleEvent(sale_id=sale.id, event_type=SaleEventType.SALE_EXPIRED))
        await db.flush()
        raise ValueError("Sale deadline has passed")

    min_bid = get_minimum_next_bid(sale)
    if amount < min_bid:
        raise ValueError(f"Bid must be at least {min_bid}")

    # Check if this club already has an active bid
    existing_result = await db.execute(
        select(Bid).where(
            Bid.sale_id == sale_id,
            Bid.buyer_club_id == buyer_club_id,
            Bid.status == BidStatus.ACTIVE,
        )
    )
    existing_bid = existing_result.scalar_one_or_none()

    wage_weekly = wage_offer_weekly or Decimal("0")

    if existing_bid:
        # Upgrade bid — release old reservation, reserve new amount
        delta_transfer = amount - existing_bid.reserved_transfer_amount
        delta_wage = wage_weekly - existing_bid.reserved_wage_weekly

        if delta_transfer > 0 or delta_wage > 0:
            # Need additional funds reserved
            await clubs_module.service.reserve_budget(
                db,
                club_id=buyer_club_id,
                transfer_amount=max(Decimal("0"), delta_transfer),
                wage_weekly=max(Decimal("0"), delta_wage),
            )
        elif delta_transfer < 0 or delta_wage < 0:
            # Releasing surplus
            await clubs_module.service.release_budget(
                db,
                club_id=buyer_club_id,
                transfer_amount=max(Decimal("0"), -delta_transfer),
                wage_weekly=max(Decimal("0"), -delta_wage),
            )

        existing_bid.amount = amount
        existing_bid.wage_offer_weekly = wage_offer_weekly
        existing_bid.reserved_transfer_amount = amount
        existing_bid.reserved_wage_weekly = wage_weekly
        existing_bid.notes = notes
        bid = existing_bid
        event_type = SaleEventType.BID_REPLACED
    else:
        # Reserve budget for new bid
        await clubs_module.service.reserve_budget(
            db,
            club_id=buyer_club_id,
            transfer_amount=amount,
            wage_weekly=wage_weekly,
        )

        bid = Bid(
            sale_id=sale_id,
            buyer_club_id=buyer_club_id,
            amount=amount,
            wage_offer_weekly=wage_offer_weekly,
            notes=notes,
            status=BidStatus.ACTIVE,
            reserved_transfer_amount=amount,
            reserved_wage_weekly=wage_weekly,
        )
        db.add(bid)
        await db.flush()
        event_type = SaleEventType.BID_PLACED

    db.add(
        SaleEvent(
            sale_id=sale_id,
            event_type=event_type,
            actor_club_id=buyer_club_id,
            bid_id=bid.id,
            amount=amount,
        )
    )
    await db.flush()
    return bid


# ── Accept bid (creates Deal) ─────────────────────────────────────────────────


async def accept_bid(
    db: AsyncSession,
    *,
    sale_id: uuid.UUID,
    bid_id: uuid.UUID,
    actor_club_id: uuid.UUID,
) -> Deal:
    """Accept a bid, close the sale, and create a Deal.

    Commits the winning bid's reservation; releases all other bids.
    """
    result = await db.execute(
        select(Sale)
        .where(Sale.id == sale_id)
        .with_for_update()
        .options(selectinload(Sale.bids))
    )
    sale = result.scalar_one_or_none()

    if sale is None:
        raise ValueError("Sale not found")
    if sale.status != SaleStatus.OPEN:
        raise ValueError("Sale is not open")
    if sale.seller_club_id != actor_club_id:
        raise ValueError("Only the seller can accept a bid")

    # Find winning bid
    bid_result = await db.execute(
        select(Bid).where(Bid.id == bid_id, Bid.sale_id == sale_id, Bid.status == BidStatus.ACTIVE)
    )
    winning_bid = bid_result.scalar_one_or_none()
    if winning_bid is None:
        raise ValueError("Bid not found or not active")

    # Release all OTHER active bids
    from app.notifications import service as notif_service
    from app.notifications.models import NotificationType

    for bid in sale.bids:
        if bid.id != bid_id and bid.status == BidStatus.ACTIVE:
            bid.status = BidStatus.REJECTED
            await clubs_module.service.release_budget(
                db,
                club_id=bid.buyer_club_id,
                transfer_amount=bid.reserved_transfer_amount,
                wage_weekly=bid.reserved_wage_weekly,
            )
            # Item 1: losing bidders get their budget back but were never told why.
            await notif_service.notify_club(
                db,
                bid.buyer_club_id,
                type=NotificationType.OUTBID,
                message="Your bid was not accepted — this sale has closed",
                link=f"/sales/{sale_id}",
                related_player_id=sale.player_id,
            )

    # Commit winning bid budget
    await clubs_module.service.commit_budget(
        db,
        club_id=winning_bid.buyer_club_id,
        transfer_amount=winning_bid.reserved_transfer_amount,
        wage_weekly=winning_bid.reserved_wage_weekly,
    )

    winning_bid.status = BidStatus.ACCEPTED
    sale.status = SaleStatus.CLOSED

    db.add(
        SaleEvent(
            sale_id=sale_id,
            event_type=SaleEventType.BID_ACCEPTED,
            actor_club_id=actor_club_id,
            bid_id=bid_id,
            amount=winning_bid.amount,
        )
    )
    db.add(
        SaleEvent(
            sale_id=sale_id,
            event_type=SaleEventType.SALE_CLOSED,
            actor_club_id=actor_club_id,
        )
    )

    deal = Deal(
        sale_id=sale_id,
        bid_id=bid_id,
        buyer_club_id=winning_bid.buyer_club_id,
        seller_club_id=sale.seller_club_id,
        player_id=sale.player_id,
        agreed_fee=winning_bid.amount,
        agreed_wage_weekly=winning_bid.wage_offer_weekly,
        status=DealStatus.IN_PROGRESS,
        stage=DealStage.AGREEMENT,
    )
    db.add(deal)
    await db.flush()
    return deal


# ── Background job: close expired sales ──────────────────────────────────────


async def close_expired_sales(db: AsyncSession) -> int:
    """Find OPEN AUCTION sales past deadline, expire them, release all bid reservations.

    Returns the number of sales expired.
    """
    now = datetime.now(timezone.utc)

    # Find expired open auction sales
    result = await db.execute(
        select(Sale)
        .where(
            Sale.status == SaleStatus.OPEN,
            Sale.sale_type == SaleType.AUCTION,
            Sale.deadline < now,
        )
        .options(selectinload(Sale.bids))
        .with_for_update(skip_locked=True)
    )
    expired_sales = list(result.scalars())

    from app.notifications import service as notif_service
    from app.notifications.models import NotificationType

    count = 0
    for sale in expired_sales:
        for bid in sale.bids:
            if bid.status == BidStatus.ACTIVE:
                bid.status = BidStatus.REJECTED
                await clubs_module.service.release_budget(
                    db,
                    club_id=bid.buyer_club_id,
                    transfer_amount=bid.reserved_transfer_amount,
                    wage_weekly=bid.reserved_wage_weekly,
                )
                # Item 1: tell bidders the auction lapsed, not just release their funds silently.
                await notif_service.notify_club(
                    db,
                    bid.buyer_club_id,
                    type=NotificationType.OUTBID,
                    message="This auction closed with no accepted bid — your reservation has been released",
                    link=f"/sales/{sale.id}",
                    related_player_id=sale.player_id,
                )
        sale.status = SaleStatus.EXPIRED
        db.add(SaleEvent(sale_id=sale.id, event_type=SaleEventType.SALE_EXPIRED))
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
    from app.sales.schemas import OrderBookClubSummary, OrderBookEntry, OrderBookResponse
    from app.offers import service as offers_svc
    from app.offers.models import OfferStatus

    is_seller = my_club_id is not None and str(my_club_id) == str(sale.seller_club_id)

    if sale.sale_type == SaleType.AUCTION:
        # ── AUCTION: order book of bids ──
        result = await db.execute(
            select(Bid)
            .where(Bid.sale_id == sale.id)
            .options(selectinload(Bid.buyer_club))
            .order_by(Bid.amount.desc())
        )
        all_bids = list(result.scalars())
        active_bids = [b for b in all_bids if b.status == BidStatus.ACTIVE]
        active_count = len(active_bids)

        # Build entries: active first (ranked), then inactive (rank=0)
        def bid_sort_key(b: Bid):
            return (b.status != BidStatus.ACTIVE, -float(b.amount or 0))

        entries: list[OrderBookEntry] = []
        rank = 1
        for bid in sorted(all_bids, key=bid_sort_key):
            is_active = bid.status == BidStatus.ACTIVE
            entry = OrderBookEntry(
                rank=rank if is_active else 0,
                kind="bid",
                id=bid.id,
                club=OrderBookClubSummary(
                    id=bid.buyer_club.id,
                    name=bid.buyer_club.name,
                    crest_url=getattr(bid.buyer_club, "crest_url", None),
                ) if bid.buyer_club else None,
                fee_amount=bid.amount,
                wage_weekly=bid.wage_offer_weekly,
                status=bid.status.value,
                is_countered=False,
                is_active=is_active,
                last_action_at=bid.updated_at,
            )
            entries.append(entry)
            if is_active:
                rank += 1

        if is_seller:
            best = max((b.amount for b in active_bids if b.amount), default=None)
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
            return OrderBookResponse(
                sale_id=sale.id,
                role="seller",
                active_count=active_count,
                entries=entries,
                summary=" · ".join(parts),
            )
        else:
            my_bid = next(
                (b for b in active_bids if my_club_id and str(b.buyer_club_id) == str(my_club_id)),
                None,
            )
            if my_bid is None:
                return OrderBookResponse(sale_id=sale.id, role="buyer", active_count=active_count)
            active_amounts = [b.amount for b in active_bids if b.amount is not None]
            sorted_amounts = sorted(active_amounts, reverse=True)
            my_rank = (sorted_amounts.index(my_bid.amount) + 1) if my_bid.amount in sorted_amounts else None
            band = _band_width(max(active_amounts)) if active_amounts else Decimal("5000000")
            other_amounts = [
                b.amount for b in active_bids
                if str(b.buyer_club_id) != str(my_club_id) and b.amount is not None
            ]
            tiers = _compute_tiers(other_amounts, my_bid.amount, band)
            my_entry = next((e for e in entries if str(e.id) == str(my_bid.id)), None)
            return OrderBookResponse(
                sale_id=sale.id,
                role="buyer",
                active_count=active_count,
                tiers=tiers,
                your_rank=my_rank,
                is_leading=my_rank == 1,
                your_entry=my_entry,
            )

    else:
        # ── OPEN_TO_OFFERS / FIXED_PRICE: order book of offers ──
        all_offers = await offers_svc.list_offers_for_sale(db, sale.id)
        _active_statuses = {OfferStatus.SENT, OfferStatus.COUNTERED}
        active_offers = [o for o in all_offers if o.status in _active_statuses]
        active_count = len(active_offers)

        def offer_sort_key(o):
            return (o.status not in _active_statuses, -float(o.fee_amount or 0))

        entries = []
        rank = 1
        for offer in sorted(all_offers, key=offer_sort_key):
            is_active = offer.status in _active_statuses
            is_countered = offer.status == OfferStatus.COUNTERED
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
                is_countered=is_countered,
                is_active=is_active,
                last_action_at=offer.last_action_at,
            )
            entries.append(entry)
            if is_active:
                rank += 1

        if is_seller:
            best = max((o.fee_amount for o in active_offers if o.fee_amount), default=None)
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
