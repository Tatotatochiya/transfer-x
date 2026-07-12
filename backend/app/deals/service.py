"""M4 — Deal lifecycle service layer."""

import uuid
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal

from sqlalchemy import select, update, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app import clubs as clubs_module
from app.audit import service as audit_service
from app.common.filters import apply_date_range
from app.deals.models import (
    ClauseStatus,
    ClauseType,
    Deal,
    DealClause,
    DealInstalment,
    DealNote,
    DealStage,
    DealStatus,
    DealType,
    MedicalCheck,
    MedicalStatus,
    PersonalTerms,
)
from app.players import service as players_service
from app.players.models import Contract, Player

# Item 5: window staff have to execute a fully-agreed deal before it's flagged overdue.
_DEAL_SLA_DAYS = 14


def _load_options():
    return [
        selectinload(Deal.buyer_club),
        selectinload(Deal.seller_club),
        selectinload(Deal.player),
        selectinload(Deal.deal_notes).selectinload(DealNote.author_club),
        selectinload(Deal.sale),
        selectinload(Deal.offer),
        selectinload(Deal.clauses),
        selectinload(Deal.instalments),
        selectinload(Deal.personal_terms),
        selectinload(Deal.medical_check),
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
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = 1,
    page_size: int = 30,
) -> tuple[list[Deal], int]:
    from sqlalchemy import func, or_

    q = select(Deal).options(*_load_options()).where(
        or_(Deal.buyer_club_id == club_id, Deal.seller_club_id == club_id)
    )
    if status:
        q = q.where(Deal.status == status)
    q = apply_date_range(q, Deal.created_at, date_from, date_to)

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
    actor_club_id: uuid.UUID | None = None,
    is_staff: bool = False,
    is_mandated_agent: bool = False,
    actor_user_id: uuid.UUID | None = None,
) -> Deal:
    """Advance deal to next stage.

    Stage rules:
    - AGREEMENT → PERSONAL_TERMS: clubs or staff. Every deal — mandated or not —
      passes through personal-terms consent; a mandated deal instead reaches
      PERSONAL_TERMS via the AGENT_NEGOTIATION branch below and never sits at
      AGREEMENT in the first place (see offers/service.py _maybe_invite_agent).
    - AGENT_NEGOTIATION → PERSONAL_TERMS: the mandated agent, clubs, or staff,
      once both sides agreed — the agent runs this stage end to end, so they
      trigger its exit too, same as they can act as the player's proxy above.
    - PERSONAL_TERMS → PAPERWORK: clubs or staff, once the player has consented
    - PAPERWORK → CONFIRMED: staff only (clubs get 403 hint via ValueError).
      Item 5: this also flips status to PENDING_COMPLETION with an SLA
      deadline — everything is agreed, only administrative execution is left.
    - CONFIRMED → COMPLETED: clubs or staff (triggers player transfer)
    """
    if deal.status not in (DealStatus.IN_PROGRESS, DealStatus.PENDING_COMPLETION):
        raise ValueError("Only IN_PROGRESS or PENDING_COMPLETION deals can be advanced")

    _require_party(deal, actor_club_id, is_staff, is_mandated_agent)

    stage = deal.stage

    if stage == DealStage.AGREEMENT:
        # TRA-60: this used to skip straight to PAPERWORK, letting a deal with no
        # agent complete without the player ever consenting to personal terms.
        deal.stage = DealStage.PERSONAL_TERMS

    elif stage == DealStage.AGENT_NEGOTIATION:
        # TRA-127: the club must be AGREED on commission before advancing.
        # Personal terms are a separate proposal + consent, at PERSONAL_TERMS.
        from app.agents.models import AgentNegotiation, AgreementStatus, NegotiationStatus

        neg_result = await db.execute(
            select(AgentNegotiation).where(AgentNegotiation.deal_id == deal.id)
        )
        neg = neg_result.scalar_one_or_none()
        if neg is None:
            raise ValueError("No agent negotiation record found for this deal")
        if neg.club_agreement != AgreementStatus.AGREED:
            raise ValueError("Club has not yet agreed to the agent's commission terms")
        neg.status = NegotiationStatus.TERMS_AGREED
        neg.agreed_at = datetime.now(timezone.utc)
        # TRA-59: copy agreed commission onto deal for quick reads
        deal.agent_commission_pct = neg.commission_pct
        deal.agent_commission_amount = neg.commission_amount
        deal.commission_payer = neg.commission_payer
        deal.commission_agent_id = neg.agent_id
        deal.stage = DealStage.PERSONAL_TERMS

        # TRA-132: create PENDING commission record
        if neg.commission_amount and neg.agent_id:
            from app.agents.service import create_commission_from_negotiation
            await create_commission_from_negotiation(
                db,
                deal_id=deal.id,
                agent_id=neg.agent_id,
                amount=neg.commission_amount,
                pct=neg.commission_pct,
                payer=neg.commission_payer.value if neg.commission_payer else None,
            )

    elif stage == DealStage.PERSONAL_TERMS:
        from app.agents.models import AgreementStatus

        pt = await get_personal_terms(db, deal.id)
        if pt is None:
            raise ValueError("Personal terms have not been set yet")
        if pt.player_consent != AgreementStatus.AGREED:
            raise ValueError("Player has not consented to the personal terms")
        deal.stage = DealStage.PAPERWORK

    elif stage == DealStage.PAPERWORK:
        if not is_staff:
            raise PermissionError("TransferX is handling the paperwork — staff only action")
        # TRA-61: block if medical check exists and is FAILED (missing = not yet done, allowed)
        mc_result = await db.execute(
            select(MedicalCheck).where(MedicalCheck.deal_id == deal.id)
        )
        mc = mc_result.scalar_one_or_none()
        if mc is not None and mc.status == MedicalStatus.FAILED:
            raise ValueError("Cannot advance: medical check has failed")
        deal.stage = DealStage.CONFIRMED
        # Item 5: everything is agreed — this is now purely administrative
        # execution, with an SLA so it doesn't just sit here indefinitely.
        deal.status = DealStatus.PENDING_COMPLETION
        deal.sla_deadline = datetime.now(timezone.utc) + timedelta(days=_DEAL_SLA_DAYS)

    elif stage == DealStage.CONFIRMED:
        mc_result = await db.execute(select(MedicalCheck).where(MedicalCheck.deal_id == deal.id))
        mc = mc_result.scalar_one_or_none()
        if mc is not None and mc.status == MedicalStatus.FAILED:
            raise ValueError("Cannot complete: medical check has failed")
        deal.stage = DealStage.COMPLETED
        await _complete_deal(db, deal)
        await audit_service.emit(
            db,
            entity_type="DEAL", entity_id=deal.id,
            action="DEAL_COMPLETED",
            actor_user_id=actor_user_id,
            description=f"Deal completed — player transferred",
        )
        return deal

    elif stage == DealStage.COMPLETED:
        raise ValueError("Deal is already completed")

    await audit_service.emit(
        db,
        entity_type="DEAL", entity_id=deal.id,
        action="STAGE_ADVANCED",
        actor_user_id=actor_user_id,
        payload={"from_stage": stage.value, "to_stage": deal.stage.value},
        description=f"Deal advanced from {stage.value} to {deal.stage.value}",
    )
    await db.flush()
    return deal


async def check_deal_sla_breaches(db: AsyncSession) -> int:
    """Flag PENDING_COMPLETION deals past their SLA deadline and notify both
    clubs — the escalation the gap list found entirely missing (item 5)."""
    from app.notifications import service as notif_service
    from app.notifications.models import NotificationType

    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Deal).where(
            Deal.status == DealStatus.PENDING_COMPLETION,
            Deal.sla_deadline < now,
            Deal.sla_escalated_at.is_(None),
        )
    )
    deals = list(result.scalars())

    count = 0
    for deal in deals:
        deal.sla_escalated_at = now
        await audit_service.emit(
            db,
            entity_type="DEAL", entity_id=deal.id,
            action="DEAL_SLA_BREACHED",
            description="Deal has been PENDING_COMPLETION past its SLA deadline",
        )
        for club_id in {deal.buyer_club_id, deal.seller_club_id}:
            if club_id is None:
                continue
            await notif_service.notify_club(
                db,
                club_id,
                type=NotificationType.DEAL_SLA_BREACHED,
                message="A deal has been awaiting completion paperwork past its expected deadline",
                link=f"/deals/{deal.id}",
                related_player_id=deal.player_id,
            )
        count += 1

    if count:
        await db.flush()
    return count


async def collapse_deal(
    db: AsyncSession,
    deal: Deal,
    *,
    actor_club_id: uuid.UUID,
    is_staff: bool = False,
    actor_user_id: uuid.UUID | None = None,
    reason: str | None = None,
) -> Deal:
    """Collapse a deal — releases buyer's committed budget.

    Item 4: a collapsed deal used to leave the world exactly as it was at the
    moment of acceptance — the originating sale stayed CLOSED forever and past
    bidders were never told they could come back. Reopen the sale (if any) and
    let every club that had bid on it know it's live again.

    reason is stored in the audit trail and forwarded to the counterparty
    notification.  For CONFIRMED/PENDING_COMPLETION deals a reason is required
    — walking away after paperwork is signed needs an explanation on record.
    """
    if deal.status in (DealStatus.COMPLETED, DealStatus.COLLAPSED):
        raise ValueError(f"Deal is already {deal.status}")

    _require_party(deal, actor_club_id, is_staff)

    if not is_staff and deal.stage in (DealStage.CONFIRMED, DealStage.COMPLETED):
        if not reason or not reason.strip():
            raise ValueError(
                "A reason is required to collapse a deal that has reached the CONFIRMED stage — "
                "the counterparty and audit trail must record why."
            )

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
    audit_description = "Deal collapsed — committed budget released"
    if reason and reason.strip():
        audit_description += f". Reason: {reason.strip()}"
    await audit_service.emit(
        db,
        entity_type="DEAL", entity_id=deal.id,
        action="DEAL_COLLAPSED",
        actor_user_id=actor_user_id,
        payload={"reason": reason.strip() if reason else None},
        description=audit_description,
    )

    if deal.sale_id:
        await _reopen_sale_after_collapse(db, deal)

    await db.flush()
    return deal


async def _reopen_sale_after_collapse(db: AsyncSession, deal: Deal) -> None:
    """Re-list the originating sale and tell past bidders it's live again."""
    from app.notifications import service as notif_service
    from app.notifications.models import NotificationType
    from app.sales.models import Bid, Sale, SaleStatus

    sale_result = await db.execute(
        select(Sale).where(Sale.id == deal.sale_id).with_for_update()
    )
    sale = sale_result.scalar_one_or_none()
    if sale is None or sale.status != SaleStatus.CLOSED:
        return

    sale.status = SaleStatus.OPEN

    bids_result = await db.execute(select(Bid).where(Bid.sale_id == sale.id))
    bidder_club_ids = {b.buyer_club_id for b in bids_result.scalars()}
    bidder_club_ids.discard(deal.buyer_club_id)  # already notified via DEAL_COLLAPSED

    for club_id in bidder_club_ids:
        await notif_service.notify_club(
            db,
            club_id,
            type=NotificationType.SALE_REOPENED,
            message="A deal for a player you bid on has collapsed — the sale is open again",
            link=f"/sales/{sale.id}",
            related_player_id=sale.player_id,
        )


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


async def staff_complete(db: AsyncSession, deal: Deal, *, actor_user_id: uuid.UUID | None = None) -> Deal:
    """Staff override: force deal to COMPLETED, creating contract."""
    if deal.status == DealStatus.COMPLETED:
        raise ValueError("Deal is already completed")
    if deal.status == DealStatus.COLLAPSED:
        raise ValueError("Cannot complete a collapsed deal")

    mc_result = await db.execute(select(MedicalCheck).where(MedicalCheck.deal_id == deal.id))
    mc = mc_result.scalar_one_or_none()
    if mc is not None and mc.status == MedicalStatus.FAILED:
        raise ValueError("Cannot complete: medical check has failed")

    deal.stage = DealStage.COMPLETED
    await _complete_deal(db, deal)
    await audit_service.emit(
        db,
        entity_type="DEAL", entity_id=deal.id,
        action="DEAL_COMPLETED",
        actor_user_id=actor_user_id,
        description="Deal force-completed by staff",
    )
    return deal


async def staff_collapse(
    db: AsyncSession, deal: Deal, *, actor_user_id: uuid.UUID | None = None, reason: str | None = None,
) -> Deal:
    """Staff override: force deal to COLLAPSED."""
    return await collapse_deal(
        db, deal, actor_club_id=deal.buyer_club_id, is_staff=True, actor_user_id=actor_user_id, reason=reason,
    )


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

    # For LOAN deals use loan_fee if set, otherwise agreed_fee.
    fee = (
        deal.loan_fee
        if deal.deal_type == DealType.LOAN and deal.loan_fee is not None
        else deal.agreed_fee
    ) or Decimal("0")

    # Use the wage the player actually consented to (PersonalTerms), not the
    # club-to-club figure from the original bid/offer.  The two can diverge when
    # the bid carried a wage estimate that was later revised during PERSONAL_TERMS.
    pt = await get_personal_terms(db, deal.id)
    new_wage = (
        pt.wage_weekly
        if pt is not None and pt.wage_weekly is not None
        else deal.agreed_wage_weekly
    ) or Decimal("0")

    # Derive a contract end-date from the length the player agreed to.
    contract_end_date: date | None = None
    if pt is not None and pt.length_years is not None:
        today = date.today()
        try:
            contract_end_date = today.replace(year=today.year + pt.length_years)
        except ValueError:
            # Feb 29 → Feb 28 in non-leap target year
            contract_end_date = today.replace(year=today.year + pt.length_years, day=28)

    # TRA-58: if an instalment schedule exists, transfer_spent is driven by mark-paid, not here.
    inst_count_result = await db.execute(
        select(func.count()).where(DealInstalment.deal_id == deal.id)
    )
    has_instalments = (inst_count_result.scalar_one() or 0) > 0

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

    # Buyer: fee committed → spent (skipped when instalments drive spending); wage committed → reserved.
    if buyer_fin:
        if fee > 0:
            buyer_fin.transfer_committed = max(Decimal("0"), buyer_fin.transfer_committed - fee)
            if not has_instalments:
                buyer_fin.transfer_spent += fee
        if new_wage > 0:
            buyer_fin.wage_committed_weekly = max(
                Decimal("0"), buyer_fin.wage_committed_weekly - new_wage
            )
            buyer_fin.wage_reserved_weekly += new_wage

    # Seller: credit fee to budget; release the departing player's wage (clamped).
    # Item 7: when an instalment schedule exists, the seller is credited
    # per-instalment in mark_instalment_paid as each one actually gets paid —
    # crediting the full fee here too would let the seller spend money before
    # the buyer has actually paid it.
    if seller_fin:
        if fee > 0 and not has_instalments:
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

    # TRA-57: surface sell-on obligation if a prior completed deal had sell_on_pct.
    if deal.seller_club_id and fee > 0:
        prior_result = await db.execute(
            select(Deal)
            .where(
                Deal.player_id == deal.player_id,
                Deal.id != deal.id,
                Deal.status == DealStatus.COMPLETED,
                Deal.sell_on_pct.is_not(None),
                Deal.seller_club_id.is_not(None),
            )
            .order_by(Deal.completed_at.desc())
            .limit(1)
        )
        prior_deal = prior_result.scalar_one_or_none()
        if prior_deal and prior_deal.sell_on_pct and prior_deal.sell_on_pct > 0:
            from app.clubs.models import Club
            from app.notifications import service as notif_service
            from app.notifications.models import NotificationType

            club_result = await db.execute(
                select(Club).where(Club.id == prior_deal.seller_club_id)
            )
            original_seller = club_result.scalar_one_or_none()
            if original_seller:
                pct = float(prior_deal.sell_on_pct) * 100
                obligation = fee * prior_deal.sell_on_pct
                await notif_service.create_notification(
                    db,
                    recipient_user_id=original_seller.user_id,
                    type=NotificationType.DEAL_SELL_ON,
                    message=(
                        f"Sell-on clause triggered: {player.name} has been resold. "
                        f"You are owed {pct:.1f}% (≈£{obligation:,.0f})"
                    ),
                    link=f"/deals/{deal.id}",
                    related_player_id=deal.player_id,
                )

    # Clear open_to_offers — the flag belongs to the seller's context; new owner decides fresh
    player.open_to_offers = False

    # Create new contract with buyer (also normalizes player status internally).
    # wage_weekly and end_date come from PersonalTerms — the terms the player
    # actually consented to — not the original club-to-club bid figure.
    await players_service.create_contract(
        db,
        player=player,
        club_id=deal.buyer_club_id,
        wage_weekly=new_wage if new_wage > 0 else None,
        end_date=contract_end_date,
    )

    # TRA-132: confirm any pending commission for this deal
    from app.agents.models import AgentCommission as _AgentCommission
    from app.agents.service import confirm_commission
    comm_result = await db.execute(
        select(_AgentCommission).where(_AgentCommission.deal_id == deal.id)
    )
    existing_commission = comm_result.scalar_one_or_none()
    if existing_commission:
        await confirm_commission(db, existing_commission)

    await db.flush()


# ── TRA-61: medical check ────────────────────────────────────────────────────


async def get_medical_check(db: AsyncSession, deal_id: uuid.UUID) -> MedicalCheck | None:
    result = await db.execute(
        select(MedicalCheck).where(MedicalCheck.deal_id == deal_id)
    )
    return result.scalar_one_or_none()


async def upsert_medical_check(
    db: AsyncSession,
    deal: Deal,
    *,
    status: MedicalStatus,
    notes: str | None = None,
    is_staff: bool = False,
    actor_club_id: uuid.UUID | None = None,
    actor_user_id: uuid.UUID | None = None,
) -> MedicalCheck:
    """Buying club or staff records or updates the medical check for a deal."""
    if not is_staff and actor_club_id != deal.buyer_club_id:
        raise PermissionError("Only the buying club or staff may record a medical check")

    mc = await get_medical_check(db, deal.id)
    if mc is None:
        mc = MedicalCheck(deal_id=deal.id)
        db.add(mc)

    mc.status = status
    mc.notes = notes
    await db.flush()
    await audit_service.emit(
        db,
        entity_type="DEAL", entity_id=deal.id,
        action="MEDICAL_CHECK_UPDATED",
        actor_user_id=actor_user_id,
        payload={"status": status.value},
        description=f"Medical check recorded: {status.value}",
    )
    return mc


# ── TRA-60: personal terms ───────────────────────────────────────────────────


async def get_personal_terms(db: AsyncSession, deal_id: uuid.UUID) -> PersonalTerms | None:
    result = await db.execute(
        select(PersonalTerms).where(PersonalTerms.deal_id == deal_id)
    )
    return result.scalar_one_or_none()


async def set_personal_terms(
    db: AsyncSession,
    deal: Deal,
    *,
    agent_profile_id: uuid.UUID | None,
    wage_weekly: Decimal | None,
    signing_bonus: Decimal | None,
    length_years: int | None,
    actor_user_id: uuid.UUID | None = None,
) -> PersonalTerms:
    """Create or replace the personal-terms record for a deal in PERSONAL_TERMS stage."""
    if deal.stage != DealStage.PERSONAL_TERMS:
        raise ValueError("Deal is not in PERSONAL_TERMS stage")

    pt = await get_personal_terms(db, deal.id)
    if pt is None:
        pt = PersonalTerms(deal_id=deal.id)
        db.add(pt)

    pt.agent_id = agent_profile_id
    pt.wage_weekly = wage_weekly
    pt.signing_bonus = signing_bonus
    pt.length_years = length_years
    # Reset consent whenever terms change
    pt.player_consent = "PENDING"  # type: ignore[assignment]
    pt.agreed_at = None
    await db.flush()
    await audit_service.emit(
        db,
        entity_type="DEAL", entity_id=deal.id,
        action="PERSONAL_TERMS_SET",
        actor_user_id=actor_user_id,
        description="Personal terms proposed to the player",
    )
    return pt


async def player_consent_to_terms(
    db: AsyncSession,
    deal: Deal,
    agreement: "AgreementStatus",  # type: ignore[name-defined]
    actor_user_id: uuid.UUID | None = None,
) -> PersonalTerms:
    """Player agrees or declines personal terms.

    AGREED advances normally.  DECLINED rejects the current proposal and
    returns the deal to PERSONAL_TERMS so the buying club can revise and
    re-propose — a single "no" in real football is the start of negotiation,
    not the death of a transfer worth tens of millions.  Either party can call
    collapse_deal explicitly if they decide to walk away entirely.
    """
    from app.agents.models import AgreementStatus
    from app.notifications import service as notif_service
    from app.notifications.models import NotificationType

    if deal.stage != DealStage.PERSONAL_TERMS:
        raise ValueError("Deal is not in PERSONAL_TERMS stage")

    pt = await get_personal_terms(db, deal.id)
    if pt is None:
        raise ValueError("No personal terms have been set")

    if agreement == AgreementStatus.AGREED:
        pt.player_consent = agreement
        pt.agreed_at = datetime.now(timezone.utc)
        await db.flush()
        await audit_service.emit(
            db,
            entity_type="DEAL", entity_id=deal.id,
            action="PERSONAL_TERMS_CONSENT",
            actor_user_id=actor_user_id,
            payload={"agreement": agreement.value},
            description="Player agreed the personal terms",
        )
    else:
        # Reset to PENDING so the proposer can submit revised terms.
        pt.player_consent = AgreementStatus.PENDING
        pt.agreed_at = None
        await db.flush()
        await audit_service.emit(
            db,
            entity_type="DEAL", entity_id=deal.id,
            action="PERSONAL_TERMS_CONSENT",
            actor_user_id=actor_user_id,
            payload={"agreement": "DECLINED"},
            description="Player declined the personal terms — awaiting revised proposal",
        )
        await notif_service.notify_club(
            db,
            deal.buyer_club_id,
            type=NotificationType.PERSONAL_TERMS_DECISION,
            message="The player has declined your personal terms proposal. Revise and re-submit to continue the deal.",
            link=f"/deals/{deal.id}",
            related_player_id=deal.player_id,
        )

    return pt


# ── TRA-127: agent negotiation ────────────────────────────────────────────────


async def get_agent_negotiation(db: AsyncSession, deal_id: uuid.UUID):
    from app.agents.models import AgentNegotiation
    result = await db.execute(
        select(AgentNegotiation).where(AgentNegotiation.deal_id == deal_id)
    )
    return result.scalar_one_or_none()


async def upsert_negotiation_terms(
    db: AsyncSession,
    deal: Deal,
    agent_profile_id: uuid.UUID,
    updates: dict,
    actor_user_id: uuid.UUID | None = None,
) -> "AgentNegotiation":  # type: ignore[name-defined]
    """Agent creates or updates commission terms proposed to the buying club."""
    from app.agents.models import AgentDealInvitation, AgentNegotiation, NegotiationStatus

    if deal.stage != DealStage.AGENT_NEGOTIATION:
        raise ValueError("Deal is not in AGENT_NEGOTIATION stage")

    neg = await get_agent_negotiation(db, deal.id)
    if neg is None:
        # TRA-127: the first write to a deal's negotiation creates the record and
        # names its agent_id — so this is the one place that must check the caller
        # is actually who was invited, not just any agent on the platform.
        invitation_result = await db.execute(
            select(AgentDealInvitation).where(
                AgentDealInvitation.deal_id == deal.id,
                AgentDealInvitation.agent_id == agent_profile_id,
            )
        )
        if invitation_result.scalar_one_or_none() is None:
            raise ValueError("Only the agent invited to this deal may start the negotiation")
        neg = AgentNegotiation(deal_id=deal.id, agent_id=agent_profile_id)
        db.add(neg)
    elif neg.agent_id != agent_profile_id:
        raise ValueError("Only the mandated agent may update negotiation terms")
    elif neg.status != NegotiationStatus.IN_PROGRESS:
        raise ValueError("Negotiation is no longer in progress")

    for k, v in updates.items():
        if v is not None:
            setattr(neg, k, v)

    # Commission is naturally negotiated as a percentage ("2% of the fee") —
    # derive the absolute amount from the deal's agreed fee whenever a
    # percentage is set and no explicit amount exists yet, so downstream
    # tracking (AgentCommission, deal.agent_commission_amount) isn't silently
    # blank just because nobody hand-calculated and typed the euro figure.
    if neg.commission_pct is not None and neg.commission_amount is None and deal.agreed_fee:
        neg.commission_amount = (neg.commission_pct * deal.agreed_fee).quantize(Decimal("0.01"))

    # Reset the club's response whenever the agent submits revised terms — the
    # club must explicitly agree or decline again against the new proposal.
    from app.agents.models import AgreementStatus as _AS
    if neg.club_agreement == _AS.DECLINED:
        neg.club_agreement = _AS.PENDING

    await db.flush()
    await audit_service.emit(
        db,
        entity_type="DEAL", entity_id=deal.id,
        action="NEGOTIATION_TERMS_UPDATED",
        actor_user_id=actor_user_id,
        payload={k: str(v) for k, v in updates.items() if v is not None},
        description="Agent updated commission terms",
    )
    return neg


async def club_respond_to_negotiation(
    db: AsyncSession,
    deal: Deal,
    club_id: uuid.UUID,
    agreement: "AgreementStatus",  # type: ignore[name-defined]
    actor_user_id: uuid.UUID | None = None,
) -> "AgentNegotiation":  # type: ignore[name-defined]
    """Buying club agrees or declines commission terms.

    AGREED marks the negotiation TERMS_AGREED and the deal advances normally.
    DECLINED rejects the current commission proposal and notifies the agent to
    revise — it does NOT collapse the deal.  Real football commission negotiations
    involve multiple rounds; one "no" is routine, not a deal-breaker.  Either
    party can call collapse_deal explicitly if talks genuinely break down.
    """
    from app.agents.models import AgentNegotiation, AgreementStatus, NegotiationStatus
    from app.auth.models import AgentProfile
    from app.notifications import service as notif_service
    from app.notifications.models import NotificationType

    _require_party(deal, club_id)
    if deal.stage != DealStage.AGENT_NEGOTIATION:
        raise ValueError("Deal is not in AGENT_NEGOTIATION stage")

    neg = await get_agent_negotiation(db, deal.id)
    if neg is None:
        raise ValueError("No agent negotiation record found")
    if neg.status != NegotiationStatus.IN_PROGRESS:
        raise ValueError("Negotiation is no longer in progress")

    neg.club_agreement = agreement
    await db.flush()
    await audit_service.emit(
        db,
        entity_type="DEAL", entity_id=deal.id,
        action="NEGOTIATION_CLUB_RESPONDED",
        actor_user_id=actor_user_id,
        payload={"agreement": agreement.value},
        description=f"Buying club {agreement.value.lower()} the commission terms",
    )

    if agreement == AgreementStatus.DECLINED:
        # Notify the agent so they can revise their proposal.
        agent_result = await db.execute(
            select(AgentProfile).where(AgentProfile.id == neg.agent_id)
        )
        agent = agent_result.scalar_one_or_none()
        if agent is not None:
            await notif_service.create_notification(
                db,
                recipient_user_id=agent.user_id,
                type=NotificationType.NEGOTIATION_MESSAGE,
                message="The buying club has declined your commission proposal. Revise your terms to continue the deal.",
                link=f"/deals/{deal.id}",
                related_player_id=deal.player_id,
            )

    return neg


def _require_party(
    deal: Deal, club_id: uuid.UUID | None, is_staff: bool = False, is_mandated_agent: bool = False,
) -> None:
    if is_staff or is_mandated_agent:
        return
    parties = {deal.buyer_club_id}
    if deal.seller_club_id:
        parties.add(deal.seller_club_id)
    if club_id not in parties:
        raise ValueError("You are not a party to this deal")


# ── TRA-56: loan deal update ──────────────────────────────────────────────────


async def update_deal(
    db: AsyncSession,
    deal: Deal,
    *,
    actor_club_id: uuid.UUID,
    is_staff: bool = False,
    updates: dict,
    actor_user_id: uuid.UUID | None = None,
) -> Deal:
    """Update loan/sell-on fields while deal is still in AGREEMENT stage."""
    if deal.status != DealStatus.IN_PROGRESS:
        raise ValueError("Only IN_PROGRESS deals can be updated")
    if deal.stage != DealStage.AGREEMENT:
        raise ValueError("Deal terms can only be updated at AGREEMENT stage")
    _require_party(deal, actor_club_id, is_staff)

    # TRA-81: capture a pre-edit baseline version the first time this deal's terms are touched.
    from app.deals.room_service import create_terms_version, list_terms_versions
    if not await list_terms_versions(db, deal.id):
        await create_terms_version(db, deal, changed_by_user_id=None)

    for k, v in updates.items():
        setattr(deal, k, v)
    await db.flush()

    await create_terms_version(db, deal, changed_by_user_id=actor_user_id)
    await audit_service.emit(
        db,
        entity_type="DEAL", entity_id=deal.id,
        action="DEAL_STRUCTURE_UPDATED",
        actor_user_id=actor_user_id,
        payload={k: str(v) for k, v in updates.items()},
        description="Deal structure updated — see version history for the full diff",
    )
    return deal


# ── TRA-57: deal clauses ──────────────────────────────────────────────────────


async def add_clause(
    db: AsyncSession,
    deal: Deal,
    *,
    actor_club_id: uuid.UUID,
    clause_type: ClauseType,
    trigger_description: str,
    amount: Decimal,
    cap: Decimal | None,
    actor_user_id: uuid.UUID | None = None,
) -> DealClause:
    if deal.status != DealStatus.IN_PROGRESS:
        raise ValueError("Clauses can only be added to in-progress deals")
    _require_party(deal, actor_club_id)
    clause = DealClause(
        deal_id=deal.id,
        clause_type=clause_type,
        trigger_description=trigger_description,
        amount=amount,
        cap=cap,
    )
    db.add(clause)
    await db.flush()
    await audit_service.emit(
        db,
        entity_type="DEAL", entity_id=deal.id,
        action="CLAUSE_ADDED",
        actor_user_id=actor_user_id,
        payload={"clause_type": clause_type.value, "amount": str(amount)},
        description=f"{clause_type.value.title()} clause added ({amount:,.0f})",
    )
    return clause


async def update_clause_status(
    db: AsyncSession,
    deal: Deal,
    clause_id: uuid.UUID,
    *,
    actor_club_id: uuid.UUID,
    is_staff: bool = False,
    new_status: ClauseStatus,
    actor_user_id: uuid.UUID | None = None,
) -> DealClause:
    _require_party(deal, actor_club_id, is_staff)
    result = await db.execute(
        select(DealClause).where(DealClause.id == clause_id, DealClause.deal_id == deal.id)
    )
    clause = result.scalar_one_or_none()
    if clause is None:
        raise ValueError("Clause not found")
    clause.status = new_status
    await db.flush()
    await audit_service.emit(
        db,
        entity_type="DEAL", entity_id=deal.id,
        action="CLAUSE_STATUS_UPDATED",
        actor_user_id=actor_user_id,
        payload={"clause_type": clause.clause_type.value, "new_status": new_status.value},
        description=f"{clause.clause_type.value.title()} clause marked {new_status.value}",
    )
    return clause


# ── TRA-58: instalment schedule ───────────────────────────────────────────────


async def set_instalments(
    db: AsyncSession,
    deal: Deal,
    *,
    actor_club_id: uuid.UUID,
    items: list[dict],
    actor_user_id: uuid.UUID | None = None,
) -> list[DealInstalment]:
    """Replace the instalment schedule. Total must equal agreed_fee."""
    if deal.status != DealStatus.IN_PROGRESS:
        raise ValueError("Instalments can only be set on in-progress deals")
    if deal.stage != DealStage.AGREEMENT:
        raise ValueError("Instalment schedule must be set at AGREEMENT stage")
    _require_party(deal, actor_club_id)

    total = sum(Decimal(str(item["amount"])) for item in items)
    if total != deal.agreed_fee:
        raise ValueError(
            f"Instalment total ({total}) must equal agreed_fee ({deal.agreed_fee})"
        )

    # Remove existing schedule
    existing = await db.execute(
        select(DealInstalment).where(DealInstalment.deal_id == deal.id)
    )
    for inst in existing.scalars():
        await db.delete(inst)

    new_instalments: list[DealInstalment] = []
    for item in items:
        inst = DealInstalment(
            deal_id=deal.id,
            due_date=item["due_date"],
            amount=Decimal(str(item["amount"])),
        )
        db.add(inst)
        new_instalments.append(inst)

    await db.flush()
    await audit_service.emit(
        db,
        entity_type="DEAL", entity_id=deal.id,
        action="INSTALMENTS_SET",
        actor_user_id=actor_user_id,
        payload={"count": len(new_instalments), "total": str(total)},
        description=f"Payment schedule set — {len(new_instalments)} instalments totalling {total:,.0f}",
    )
    return new_instalments


async def mark_instalment_paid(
    db: AsyncSession,
    deal: Deal,
    instalment_id: uuid.UUID,
    *,
    actor_club_id: uuid.UUID,
    is_staff: bool = False,
    actor_user_id: uuid.UUID | None = None,
) -> DealInstalment:
    """Mark one instalment as paid; increments buyer's transfer_spent."""
    _require_party(deal, actor_club_id, is_staff)
    result = await db.execute(
        select(DealInstalment).where(
            DealInstalment.id == instalment_id,
            DealInstalment.deal_id == deal.id,
        )
    )
    inst = result.scalar_one_or_none()
    if inst is None:
        raise ValueError("Instalment not found")
    if inst.paid:
        raise ValueError("Instalment already marked as paid")

    inst.paid = True
    inst.paid_at = datetime.now(timezone.utc)

    buyer_fin = await clubs_module.service.get_finance_for_update(db, deal.buyer_club_id)
    if buyer_fin:
        buyer_fin.transfer_spent += inst.amount

    # Item 7: seller is credited as each instalment actually lands, not the
    # full fee up front at deal completion.
    if deal.seller_club_id:
        seller_fin = await clubs_module.service.get_finance_for_update(db, deal.seller_club_id)
        if seller_fin:
            seller_fin.transfer_budget_total += inst.amount

    await db.flush()
    await audit_service.emit(
        db,
        entity_type="DEAL", entity_id=deal.id,
        action="INSTALMENT_PAID",
        actor_user_id=actor_user_id,
        payload={"amount": str(inst.amount), "due_date": inst.due_date.isoformat()},
        description=f"Instalment of {inst.amount:,.0f} marked paid",
    )
    return inst
