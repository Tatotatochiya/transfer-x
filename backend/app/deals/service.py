"""M4 — Deal lifecycle service layer."""

import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from sqlalchemy import select, update, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app import clubs as clubs_module
from app.deals.models import Deal, DealNote, DealStage, DealStatus
from app.players import service as players_service
from app.players.models import Contract, Player


def _load_options():
    return [
        selectinload(Deal.buyer_club),
        selectinload(Deal.seller_club),
        selectinload(Deal.player),
        selectinload(Deal.deal_notes).selectinload(DealNote.author_club),
        selectinload(Deal.sale),
        selectinload(Deal.offer),
    ]


_DEAL_CLUB_OPTS = [selectinload(Deal.buyer_club), selectinload(Deal.seller_club)]

_RECENT_DEAL_DAYS = 30


async def get_active_deal_for_player(db: AsyncSession, player_id: uuid.UUID) -> Deal | None:
    """Return the IN_PROGRESS deal for this player, or most recent COMPLETED deal within 30 days."""
    # IN_PROGRESS takes priority
    result = await db.execute(
        select(Deal)
        .where(Deal.player_id == player_id, Deal.status == DealStatus.IN_PROGRESS)
        .options(*_DEAL_CLUB_OPTS)
        .limit(1)
    )
    deal = result.scalar_one_or_none()
    if deal:
        return deal

    cutoff = datetime.now(timezone.utc) - timedelta(days=_RECENT_DEAL_DAYS)
    result = await db.execute(
        select(Deal)
        .where(
            Deal.player_id == player_id,
            Deal.status == DealStatus.COMPLETED,
            Deal.completed_at >= cutoff,
        )
        .options(*_DEAL_CLUB_OPTS)
        .order_by(Deal.completed_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_active_deals_for_players(
    db: AsyncSession, player_ids: list[uuid.UUID]
) -> dict[uuid.UUID, Deal]:
    """Batch version: returns {player_id: deal} for the given set of player IDs.
    Prefers IN_PROGRESS over COMPLETED; only includes COMPLETED within 30 days."""
    if not player_ids:
        return {}

    cutoff = datetime.now(timezone.utc) - timedelta(days=_RECENT_DEAL_DAYS)
    result = await db.execute(
        select(Deal)
        .where(
            Deal.player_id.in_(player_ids),
            or_(
                Deal.status == DealStatus.IN_PROGRESS,
                (Deal.status == DealStatus.COMPLETED) & (Deal.completed_at >= cutoff),
            ),
        )
        .options(*_DEAL_CLUB_OPTS)
        .order_by(Deal.player_id, Deal.status)  # IN_PROGRESS sorts before COMPLETED alphabetically
    )
    deals = list(result.scalars())

    # For each player keep IN_PROGRESS if present, else most recent COMPLETED
    out: dict[uuid.UUID, Deal] = {}
    for deal in deals:
        pid = uuid.UUID(str(deal.player_id))
        existing = out.get(pid)
        if existing is None:
            out[pid] = deal
        elif deal.status == DealStatus.IN_PROGRESS:
            out[pid] = deal  # IN_PROGRESS always wins
    return out


async def get_deal_by_id(db: AsyncSession, deal_id: uuid.UUID) -> Deal | None:
    result = await db.execute(
        select(Deal).where(Deal.id == deal_id).options(*_load_options())
    )
    return result.scalar_one_or_none()


async def list_deals(
    db: AsyncSession,
    *,
    club_id: uuid.UUID,
    status: DealStatus | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Deal], int]:
    from sqlalchemy import func, or_

    q = select(Deal).options(*_load_options()).where(
        or_(Deal.buyer_club_id == club_id, Deal.seller_club_id == club_id)
    )
    if status:
        q = q.where(Deal.status == status)

    total_result = await db.execute(select(func.count()).select_from(q.subquery()))
    total = total_result.scalar_one()
    rows = await db.execute(
        q.order_by(Deal.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    return list(rows.scalars()), total


async def list_transfer_activity(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 30,
    *,
    position: str | None = None,
    is_auction: bool | None = None,
    club_id: uuid.UUID | None = None,
) -> tuple[list[Deal], int]:
    """Public feed of completed transfers, sorted by most recently completed."""
    from app.sales.models import Sale, SaleType

    q = (
        select(Deal)
        .options(
            selectinload(Deal.buyer_club),
            selectinload(Deal.seller_club),
            selectinload(Deal.player),
            selectinload(Deal.sale),
        )
        .where(Deal.status == DealStatus.COMPLETED)
    )
    if position:
        q = q.join(Player, Deal.player_id == Player.id).where(Player.position == position)
    if is_auction is not None:
        if is_auction:
            q = q.join(Sale, Deal.sale_id == Sale.id).where(Sale.sale_type == SaleType.AUCTION)
        else:
            q = q.outerjoin(Sale, Deal.sale_id == Sale.id).where(
                or_(Deal.sale_id.is_(None), Sale.sale_type != SaleType.AUCTION)
            )
    if club_id:
        q = q.where(or_(Deal.buyer_club_id == club_id, Deal.seller_club_id == club_id))

    q = q.order_by(Deal.completed_at.desc())
    total_result = await db.execute(select(func.count()).select_from(q.subquery()))
    total = total_result.scalar_one()
    rows = await db.execute(q.offset((page - 1) * page_size).limit(page_size))
    return list(rows.scalars()), total


async def get_transfer_analytics(db: AsyncSession) -> dict:
    """Compute market-wide analytics across completed and ongoing deals."""
    from app.clubs.models import Club
    from app.sales.models import Sale, SaleType

    load_opts = [
        selectinload(Deal.buyer_club),
        selectinload(Deal.seller_club),
        selectinload(Deal.player),
        selectinload(Deal.sale),
    ]
    cutoff_30d = datetime.now(timezone.utc) - timedelta(days=30)

    # ── Completed aggregates ───────────────────────────────────────────────────
    agg = await db.execute(
        select(
            func.count().label("total_count"),
            func.coalesce(func.sum(Deal.agreed_fee), 0).label("total_spend"),
            func.avg(Deal.agreed_fee).label("avg_fee"),
        ).where(Deal.status == DealStatus.COMPLETED)
    )
    agg_row = agg.one()

    # Recent 30d
    recent = await db.execute(
        select(
            func.count().label("cnt"),
            func.coalesce(func.sum(Deal.agreed_fee), 0).label("spend"),
        ).where(
            Deal.status == DealStatus.COMPLETED,
            Deal.completed_at >= cutoff_30d,
        )
    )
    recent_row = recent.one()

    # Highest fee deal
    highest_result = await db.execute(
        select(Deal).options(*load_opts)
        .where(Deal.status == DealStatus.COMPLETED)
        .order_by(Deal.agreed_fee.desc())
        .limit(1)
    )
    highest_deal = highest_result.scalar_one_or_none()

    # Top 5 transfers
    top_result = await db.execute(
        select(Deal).options(*load_opts)
        .where(Deal.status == DealStatus.COMPLETED)
        .order_by(Deal.agreed_fee.desc())
        .limit(5)
    )
    top_transfers = list(top_result.scalars())

    # Most active buyer
    buyer_result = await db.execute(
        select(Deal.buyer_club_id, func.count().label("cnt"), func.sum(Deal.agreed_fee).label("spend"))
        .where(Deal.status == DealStatus.COMPLETED)
        .group_by(Deal.buyer_club_id)
        .order_by(func.count().desc())
        .limit(1)
    )
    buyer_row = buyer_result.one_or_none()
    most_active_buyer = None
    if buyer_row:
        club_res = await db.execute(select(Club).where(Club.id == buyer_row.buyer_club_id))
        club = club_res.scalar_one_or_none()
        if club:
            most_active_buyer = {"club": club, "count": buyer_row.cnt, "total_spend": buyer_row.spend or Decimal(0)}

    # Most active seller
    seller_result = await db.execute(
        select(Deal.seller_club_id, func.count().label("cnt"), func.sum(Deal.agreed_fee).label("spend"))
        .where(Deal.status == DealStatus.COMPLETED, Deal.seller_club_id.is_not(None))
        .group_by(Deal.seller_club_id)
        .order_by(func.count().desc())
        .limit(1)
    )
    seller_row = seller_result.one_or_none()
    most_active_seller = None
    if seller_row:
        club_res = await db.execute(select(Club).where(Club.id == seller_row.seller_club_id))
        club = club_res.scalar_one_or_none()
        if club:
            most_active_seller = {"club": club, "count": seller_row.cnt, "total_spend": seller_row.spend or Decimal(0)}

    # By position
    pos_result = await db.execute(
        select(Player.position, func.count().label("cnt"), func.coalesce(func.sum(Deal.agreed_fee), 0).label("spend"))
        .join(Player, Deal.player_id == Player.id)
        .where(Deal.status == DealStatus.COMPLETED)
        .group_by(Player.position)
        .order_by(func.count().desc())
    )
    by_position = [
        {"position": row.position or "Unknown", "count": row.cnt, "total_spend": row.spend}
        for row in pos_result
    ]

    # Auction vs offer split
    type_result = await db.execute(
        select(
            func.count().filter(
                Deal.sale_id.is_not(None),
            ).label("with_sale"),
        ).select_from(
            Deal.__table__.outerjoin(Sale.__table__, Deal.sale_id == Sale.id)
        ).where(Deal.status == DealStatus.COMPLETED)
    )
    # Simpler: count auction deals by joining sale
    auction_result = await db.execute(
        select(func.count())
        .select_from(Deal)
        .join(Sale, Deal.sale_id == Sale.id)
        .where(Deal.status == DealStatus.COMPLETED, Sale.sale_type == SaleType.AUCTION)
    )
    auction_count = auction_result.scalar_one()
    offer_count = (agg_row.total_count or 0) - auction_count

    # ── Ongoing stats ──────────────────────────────────────────────────────────
    ongoing_agg = await db.execute(
        select(
            func.count().label("total"),
            func.coalesce(func.sum(Deal.agreed_fee), 0).label("fees"),
        ).where(Deal.status == DealStatus.IN_PROGRESS)
    )
    ongoing_row = ongoing_agg.one()

    stage_result = await db.execute(
        select(Deal.stage, func.count().label("cnt"))
        .where(Deal.status == DealStatus.IN_PROGRESS)
        .group_by(Deal.stage)
    )
    by_stage = {row.stage.value: row.cnt for row in stage_result}

    return {
        "completed": {
            "total_count": agg_row.total_count or 0,
            "total_spend": agg_row.total_spend or Decimal(0),
            "avg_fee": agg_row.avg_fee,
            "highest_fee_deal": highest_deal,
            "top_transfers": top_transfers,
            "most_active_buyer": most_active_buyer,
            "most_active_seller": most_active_seller,
            "by_position": by_position,
            "auction_count": auction_count,
            "offer_count": offer_count,
            "recent_30d_count": recent_row.cnt or 0,
            "recent_30d_spend": recent_row.spend or Decimal(0),
        },
        "ongoing": {
            "total_count": ongoing_row.total or 0,
            "by_stage": by_stage,
            "total_committed_fees": ongoing_row.fees or Decimal(0),
        },
    }


async def advance_deal(
    db: AsyncSession,
    deal: Deal,
    *,
    actor_club_id: uuid.UUID,
    is_staff: bool = False,
) -> Deal:
    """Advance deal to next stage.

    Stage rules:
    - AGREEMENT → PAPERWORK: clubs or staff
    - PAPERWORK → CONFIRMED: staff only (clubs get 403 hint via ValueError)
    - CONFIRMED → COMPLETED: clubs or staff (triggers player transfer)
    """
    if deal.status != DealStatus.IN_PROGRESS:
        raise ValueError("Only IN_PROGRESS deals can be advanced")

    _require_party(deal, actor_club_id, is_staff)

    stage = deal.stage

    if stage == DealStage.AGREEMENT:
        deal.stage = DealStage.PAPERWORK

    elif stage == DealStage.PAPERWORK:
        if not is_staff:
            raise PermissionError("TransferX is handling the paperwork — staff only action")
        deal.stage = DealStage.CONFIRMED

    elif stage == DealStage.CONFIRMED:
        deal.stage = DealStage.COMPLETED
        await _complete_deal(db, deal)
        return deal

    elif stage == DealStage.COMPLETED:
        raise ValueError("Deal is already completed")

    await db.flush()
    return deal


async def collapse_deal(
    db: AsyncSession,
    deal: Deal,
    *,
    actor_club_id: uuid.UUID,
    is_staff: bool = False,
) -> Deal:
    """Collapse a deal — releases buyer's committed budget."""
    if deal.status in (DealStatus.COMPLETED, DealStatus.COLLAPSED):
        raise ValueError(f"Deal is already {deal.status}")

    _require_party(deal, actor_club_id, is_staff)

    # Release committed budget back to available for buyer
    if deal.agreed_fee and deal.agreed_fee > 0:
        finance = await clubs_module.service.get_finance_for_update(db, deal.buyer_club_id)
        if finance:
            finance.transfer_committed = max(Decimal("0"), finance.transfer_committed - deal.agreed_fee)
            if deal.agreed_wage_weekly:
                finance.wage_committed_weekly = max(
                    Decimal("0"), finance.wage_committed_weekly - deal.agreed_wage_weekly
                )

    deal.status = DealStatus.COLLAPSED
    await db.flush()
    return deal


async def add_note(
    db: AsyncSession,
    deal: Deal,
    *,
    author_club_id: uuid.UUID,
    body: str,
) -> DealNote:
    _require_party(deal, author_club_id)
    note = DealNote(deal_id=deal.id, author_club_id=author_club_id, body=body)
    db.add(note)
    await db.flush()
    return note


async def staff_complete(db: AsyncSession, deal: Deal) -> Deal:
    """Staff override: force deal to COMPLETED, creating contract."""
    if deal.status == DealStatus.COMPLETED:
        raise ValueError("Deal is already completed")
    if deal.status == DealStatus.COLLAPSED:
        raise ValueError("Cannot complete a collapsed deal")

    deal.stage = DealStage.COMPLETED
    await _complete_deal(db, deal)
    return deal


async def staff_collapse(db: AsyncSession, deal: Deal) -> Deal:
    """Staff override: force deal to COLLAPSED."""
    return await collapse_deal(db, deal, actor_club_id=deal.buyer_club_id, is_staff=True)


# ── Internal ──────────────────────────────────────────────────────────────────


async def _complete_deal(db: AsyncSession, deal: Deal) -> None:
    """Execute the transfer: settle finance for both clubs, then swap the contract."""
    now = datetime.now(timezone.utc)
    deal.status = DealStatus.COMPLETED
    deal.completed_at = now

    player_result = await db.execute(select(Player).where(Player.id == deal.player_id))
    player = player_result.scalar_one_or_none()
    if player is None:
        raise ValueError("Player not found")

    fee = deal.agreed_fee or Decimal("0")
    new_wage = deal.agreed_wage_weekly or Decimal("0")

    # Capture the seller's outgoing wage BEFORE the contract is deactivated.
    old_wage = Decimal("0")
    if deal.seller_club_id:
        old_wage = (
            await db.execute(
                select(Contract.wage_weekly)
                .where(
                    Contract.player_id == deal.player_id,
                    Contract.club_id == deal.seller_club_id,
                    Contract.is_active == True,  # noqa: E712
                )
                .limit(1)
            )
        ).scalar_one_or_none() or Decimal("0")

    # Lock both finance rows in deterministic order (sorted by club_id) to avoid deadlock.
    club_ids = [deal.buyer_club_id] + ([deal.seller_club_id] if deal.seller_club_id else [])
    finances = {}
    for cid in sorted(club_ids, key=str):
        finances[cid] = await clubs_module.service.get_finance_for_update(db, cid)
    buyer_fin = finances.get(deal.buyer_club_id)
    seller_fin = finances.get(deal.seller_club_id) if deal.seller_club_id else None

    # Buyer: fee committed → spent; wage committed → reserved (clamped — wage commit isn't wired yet).
    if buyer_fin:
        if fee > 0:
            buyer_fin.transfer_committed = max(Decimal("0"), buyer_fin.transfer_committed - fee)
            buyer_fin.transfer_spent += fee
        if new_wage > 0:
            buyer_fin.wage_committed_weekly = max(
                Decimal("0"), buyer_fin.wage_committed_weekly - new_wage
            )
            buyer_fin.wage_reserved_weekly += new_wage

    # Seller: credit fee to budget; release the departing player's wage (clamped).
    if seller_fin:
        if fee > 0:
            seller_fin.transfer_budget_total += fee
        if old_wage > 0:
            seller_fin.wage_reserved_weekly = max(
                Decimal("0"), seller_fin.wage_reserved_weekly - old_wage
            )

    # Deactivate active contracts with the seller
    if deal.seller_club_id:
        await db.execute(
            update(Contract)
            .where(
                Contract.player_id == deal.player_id,
                Contract.club_id == deal.seller_club_id,
                Contract.is_active == True,  # noqa: E712
            )
            .values(is_active=False)
        )

    # Clear open_to_offers — the flag belongs to the seller's context; new owner decides fresh
    player.open_to_offers = False

    # Create new contract with buyer (also normalizes player status internally)
    await players_service.create_contract(
        db,
        player=player,
        club_id=deal.buyer_club_id,
        wage_weekly=deal.agreed_wage_weekly,
    )
    await db.flush()


def _require_party(deal: Deal, club_id: uuid.UUID, is_staff: bool = False) -> None:
    if is_staff:
        return
    parties = {deal.buyer_club_id}
    if deal.seller_club_id:
        parties.add(deal.seller_club_id)
    if club_id not in parties:
        raise ValueError("You are not a party to this deal")
