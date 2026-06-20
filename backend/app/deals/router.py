"""M4 — Deal lifecycle endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.clubs import service as clubs_service
from app.common.schemas import Paginated
from app.database import get_db
from app.deals import service
from app.deals.models import DealStatus
from app.deals.schemas import (
    AgentNegotiationResponse,
    ClubTransferStat,
    CompletedStats,
    CreateClauseRequest,
    CreateInstalmentsRequest,
    DealClauseResponse,
    DealInstalmentResponse,
    DealNoteRequest,
    DealNoteResponse,
    DealResponse,
    NegotiationRespondRequest,
    OngoingStats,
    PositionBreakdown,
    TransferActivityItem,
    TransferAnalytics,
    UpdateClauseStatusRequest,
    UpdateDealRequest,
    UpdateNegotiationTermsRequest,
)
from app.deps import get_current_user
from app.notifications import service as notif_service
from app.notifications.models import NotificationType
from app.ws.manager import manager as ws_manager

router = APIRouter(tags=["deals"])


async def _get_club_or_403(db: AsyncSession, user: User):
    club = await clubs_service.get_club_by_user_id(db, user.id)
    if club is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No club profile")
    return club


async def _notify_deal_parties(db: AsyncSession, deal_id: uuid.UUID) -> None:
    """Push DEAL_UPDATED to both clubs involved in a deal."""
    deal = await service.get_deal_by_id(db, deal_id)
    if deal is None:
        return
    user_ids = []
    for club_id in [deal.buyer_club_id, deal.seller_club_id]:
        if club_id is None:
            continue
        club = await clubs_service.get_club_by_id(db, uuid.UUID(str(club_id)))
        if club:
            user_ids.append(club.user_id)
    await ws_manager.broadcast_to_users(
        list(set(user_ids)),
        {"type": "DEAL_UPDATED", "id": str(deal_id)},
    )


async def _db_notify_deal_parties(
    db: AsyncSession,
    deal,
    *,
    ntype: NotificationType,
    message: str,
) -> None:
    """Create DB notifications for both parties of a deal. Must be called before commit."""
    player_id = deal.player_id
    deal_link = f"/deals/{deal.id}"
    for club_id in [deal.buyer_club_id, deal.seller_club_id]:
        if club_id is None:
            continue
        club = await clubs_service.get_club_by_id(db, uuid.UUID(str(club_id)))
        if club:
            await notif_service.create_notification(
                db,
                recipient_user_id=club.user_id,
                type=ntype,
                message=message,
                link=deal_link,
                related_player_id=player_id,
            )


async def _get_deal_or_404(db: AsyncSession, deal_id: uuid.UUID):
    deal = await service.get_deal_by_id(db, deal_id)
    if deal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")
    return deal


def _build_deal_response(deal) -> DealResponse:
    return DealResponse(
        id=deal.id,
        sale_id=deal.sale_id,
        bid_id=deal.bid_id,
        offer_id=deal.offer_id,
        buyer_club_id=deal.buyer_club_id,
        seller_club_id=deal.seller_club_id,
        player_id=deal.player_id,
        agreed_fee=deal.agreed_fee,
        agreed_wage_weekly=deal.agreed_wage_weekly,
        status=deal.status,
        stage=deal.stage,
        deal_type=deal.deal_type,
        loan_start=deal.loan_start,
        loan_end=deal.loan_end,
        loan_fee=deal.loan_fee,
        option_to_buy=deal.option_to_buy,
        obligation_to_buy=deal.obligation_to_buy,
        obligation_conditions=deal.obligation_conditions,
        sell_on_pct=deal.sell_on_pct,
        clauses=deal.clauses,
        instalments=deal.instalments,
        notes=deal.notes,
        completed_at=deal.completed_at,
        created_at=deal.created_at,
        updated_at=deal.updated_at,
        is_auction_deal=deal.is_auction_deal,
        buyer_club=deal.buyer_club,
        seller_club=deal.seller_club,
        player=deal.player,
        deal_notes=deal.deal_notes,
    )


# ── Public transfer feed ──────────────────────────────────────────────────────


@router.get("/transfers/analytics", response_model=TransferAnalytics)
async def get_transfer_analytics(
    db: AsyncSession = Depends(get_db),
):
    """Market-wide transfer analytics — no auth required."""
    data = await service.get_transfer_analytics(db)

    def _to_item(deal) -> TransferActivityItem | None:
        if deal is None:
            return None
        return TransferActivityItem.model_validate(deal)

    def _to_club_stat(raw) -> ClubTransferStat | None:
        if raw is None:
            return None
        from app.deals.schemas import ClubSummary
        return ClubTransferStat(
            club=ClubSummary.model_validate(raw["club"]),
            count=raw["count"],
            total_spend=raw["total_spend"],
        )

    c = data["completed"]
    o = data["ongoing"]
    return TransferAnalytics(
        completed=CompletedStats(
            total_count=c["total_count"],
            total_spend=c["total_spend"],
            avg_fee=c["avg_fee"],
            highest_fee_deal=_to_item(c["highest_fee_deal"]),
            top_transfers=[TransferActivityItem.model_validate(d) for d in c["top_transfers"]],
            most_active_buyer=_to_club_stat(c["most_active_buyer"]),
            most_active_seller=_to_club_stat(c["most_active_seller"]),
            by_position=[PositionBreakdown(**p) for p in c["by_position"]],
            auction_count=c["auction_count"],
            offer_count=c["offer_count"],
            recent_30d_count=c["recent_30d_count"],
            recent_30d_spend=c["recent_30d_spend"],
        ),
        ongoing=OngoingStats(
            total_count=o["total_count"],
            by_stage=o["by_stage"],
            total_committed_fees=o["total_committed_fees"],
        ),
    )


@router.get("/transfers", response_model=Paginated[TransferActivityItem])
async def list_transfers(
    page: int = 1,
    page_size: int = 30,
    position: str | None = None,
    is_auction: bool | None = None,
    club_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Public feed of completed transfers — no auth required."""
    deals, total = await service.list_transfer_activity(
        db, page=page, page_size=page_size,
        position=position, is_auction=is_auction, club_id=club_id,
    )
    items = [TransferActivityItem.model_validate(d) for d in deals]
    return Paginated(items=items, total=total, page=page, page_size=page_size)


# ── List + detail ─────────────────────────────────────────────────────────────


@router.get("/deals", response_model=Paginated[DealResponse])
async def list_deals(
    deal_status: DealStatus | None = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    club = await _get_club_or_403(db, current_user)
    deals, total = await service.list_deals(
        db, club_id=club.id, status=deal_status, page=page, page_size=page_size
    )
    return Paginated(
        items=[_build_deal_response(d) for d in deals],
        total=total, page=page, page_size=page_size,
    )


@router.get("/deals/{deal_id}", response_model=DealResponse)
async def get_deal(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    club = await _get_club_or_403(db, current_user)
    deal = await _get_deal_or_404(db, deal_id)
    parties = {deal.buyer_club_id, deal.seller_club_id}
    if club.id not in parties and not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a party to this deal")
    return _build_deal_response(deal)


# ── Stage advancement ─────────────────────────────────────────────────────────


@router.post("/deals/{deal_id}/advance", response_model=DealResponse)
async def advance_deal(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    club = await _get_club_or_403(db, current_user)
    deal = await _get_deal_or_404(db, deal_id)

    try:
        await service.advance_deal(
            db, deal, actor_club_id=club.id, is_staff=current_user.is_superuser
        )
        if deal.status == DealStatus.COMPLETED:
            player_name = deal.player.name if deal.player else "the player"
            await _db_notify_deal_parties(
                db, deal,
                ntype=NotificationType.DEAL_COMPLETED,
                message=f"Transfer of {player_name} completed",
            )
        await db.commit()
    except PermissionError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    deal = await service.get_deal_by_id(db, deal_id)
    await _notify_deal_parties(db, deal_id)
    return _build_deal_response(deal)


# ── Collapse ──────────────────────────────────────────────────────────────────


@router.post("/deals/{deal_id}/collapse", response_model=DealResponse)
async def collapse_deal(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    club = await _get_club_or_403(db, current_user)
    deal = await _get_deal_or_404(db, deal_id)

    try:
        await service.collapse_deal(
            db, deal, actor_club_id=club.id, is_staff=current_user.is_superuser
        )
        player_name = deal.player.name if deal.player else "the player"
        await _db_notify_deal_parties(
            db, deal,
            ntype=NotificationType.DEAL_COLLAPSED,
            message=f"Deal for {player_name} has collapsed",
        )
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    deal = await service.get_deal_by_id(db, deal_id)
    await _notify_deal_parties(db, deal_id)
    return _build_deal_response(deal)


# ── Notes ─────────────────────────────────────────────────────────────────────


@router.post("/deals/{deal_id}/notes", response_model=DealNoteResponse, status_code=status.HTTP_201_CREATED)
async def add_note(
    deal_id: uuid.UUID,
    body: DealNoteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    club = await _get_club_or_403(db, current_user)
    deal = await _get_deal_or_404(db, deal_id)

    try:
        note = await service.add_note(db, deal, author_club_id=club.id, body=body.body)
        await db.commit()
        await db.refresh(note)
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return DealNoteResponse.model_validate(note)


# ── Staff endpoints ───────────────────────────────────────────────────────────


@router.post("/deals/{deal_id}/staff/complete", response_model=DealResponse)
async def staff_complete_deal(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Staff only")
    deal = await _get_deal_or_404(db, deal_id)

    try:
        await service.staff_complete(db, deal)
        player_name = deal.player.name if deal.player else "the player"
        await _db_notify_deal_parties(
            db, deal,
            ntype=NotificationType.DEAL_COMPLETED,
            message=f"Transfer of {player_name} completed",
        )
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    deal = await service.get_deal_by_id(db, deal_id)
    await _notify_deal_parties(db, deal_id)
    return _build_deal_response(deal)


@router.post("/deals/{deal_id}/staff/collapse", response_model=DealResponse)
async def staff_collapse_deal(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Staff only")
    deal = await _get_deal_or_404(db, deal_id)

    try:
        await service.staff_collapse(db, deal)
        player_name = deal.player.name if deal.player else "the player"
        await _db_notify_deal_parties(
            db, deal,
            ntype=NotificationType.DEAL_COLLAPSED,
            message=f"Deal for {player_name} has collapsed",
        )
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    deal = await service.get_deal_by_id(db, deal_id)
    await _notify_deal_parties(db, deal_id)
    return _build_deal_response(deal)


# ── TRA-56: update deal terms (loan / sell-on) ────────────────────────────────


@router.patch("/deals/{deal_id}", response_model=DealResponse)
async def update_deal(
    deal_id: uuid.UUID,
    body: UpdateDealRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    club = await _get_club_or_403(db, current_user)
    deal = await _get_deal_or_404(db, deal_id)

    try:
        updates = body.model_dump(exclude_unset=True)
        await service.update_deal(
            db, deal,
            actor_club_id=club.id,
            is_staff=current_user.is_superuser,
            updates=updates,
        )
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    deal = await service.get_deal_by_id(db, deal_id)
    return _build_deal_response(deal)


# ── TRA-57: deal clauses ──────────────────────────────────────────────────────


@router.post(
    "/deals/{deal_id}/clauses",
    response_model=DealClauseResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_clause(
    deal_id: uuid.UUID,
    body: CreateClauseRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    club = await _get_club_or_403(db, current_user)
    deal = await _get_deal_or_404(db, deal_id)

    try:
        clause = await service.add_clause(
            db, deal,
            actor_club_id=club.id,
            clause_type=body.clause_type,
            trigger_description=body.trigger_description,
            amount=body.amount,
            cap=body.cap,
        )
        await db.commit()
        await db.refresh(clause)
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return DealClauseResponse.model_validate(clause)


@router.get("/deals/{deal_id}/clauses", response_model=list[DealClauseResponse])
async def list_clauses(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    club = await _get_club_or_403(db, current_user)
    deal = await _get_deal_or_404(db, deal_id)
    parties = {deal.buyer_club_id, deal.seller_club_id}
    if club.id not in parties and not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a party to this deal")
    return [DealClauseResponse.model_validate(c) for c in deal.clauses]


@router.patch("/deals/{deal_id}/clauses/{clause_id}/status", response_model=DealClauseResponse)
async def update_clause_status(
    deal_id: uuid.UUID,
    clause_id: uuid.UUID,
    body: UpdateClauseStatusRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    club = await _get_club_or_403(db, current_user)
    deal = await _get_deal_or_404(db, deal_id)

    try:
        clause = await service.update_clause_status(
            db, deal, clause_id,
            actor_club_id=club.id,
            is_staff=current_user.is_superuser,
            new_status=body.status,
        )
        await db.commit()
        await db.refresh(clause)
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return DealClauseResponse.model_validate(clause)


# ── TRA-58: instalment schedule ───────────────────────────────────────────────


@router.post(
    "/deals/{deal_id}/instalments",
    response_model=list[DealInstalmentResponse],
    status_code=status.HTTP_201_CREATED,
)
async def set_instalments(
    deal_id: uuid.UUID,
    body: CreateInstalmentsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    club = await _get_club_or_403(db, current_user)
    deal = await _get_deal_or_404(db, deal_id)

    items = [{"due_date": i.due_date, "amount": i.amount} for i in body.instalments]
    try:
        instalments = await service.set_instalments(
            db, deal, actor_club_id=club.id, items=items
        )
        await db.commit()
        for inst in instalments:
            await db.refresh(inst)
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return [DealInstalmentResponse.model_validate(i) for i in instalments]


@router.get("/deals/{deal_id}/instalments", response_model=list[DealInstalmentResponse])
async def list_instalments(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    club = await _get_club_or_403(db, current_user)
    deal = await _get_deal_or_404(db, deal_id)
    parties = {deal.buyer_club_id, deal.seller_club_id}
    if club.id not in parties and not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a party to this deal")
    return [DealInstalmentResponse.model_validate(i) for i in deal.instalments]


# ── TRA-127: agent negotiation ────────────────────────────────────────────────


def _build_neg_response(neg, *, caller_user_type: str) -> AgentNegotiationResponse:
    """Return a negotiation response, nulling out fields the caller should not see."""
    is_agent_or_staff = caller_user_type in ("AGENT", "STAFF", "ADMIN")
    is_club = caller_user_type == "CLUB"
    is_player = caller_user_type == "PLAYER"

    return AgentNegotiationResponse(
        id=neg.id,
        deal_id=neg.deal_id,
        agent_id=neg.agent_id,
        status=neg.status,
        club_agreement=neg.club_agreement,
        player_agreement=neg.player_agreement,
        # Club-side: shown to agent/staff + clubs
        commission_pct=neg.commission_pct if (is_agent_or_staff or is_club) else None,
        commission_amount=neg.commission_amount if (is_agent_or_staff or is_club) else None,
        commission_payer=neg.commission_payer if (is_agent_or_staff or is_club) else None,
        additional_conditions=neg.additional_conditions if (is_agent_or_staff or is_club) else None,
        # Player-side: shown to agent/staff + player
        proposed_wage_weekly=neg.proposed_wage_weekly if (is_agent_or_staff or is_player) else None,
        proposed_signing_bonus=neg.proposed_signing_bonus if (is_agent_or_staff or is_player) else None,
        proposed_length_years=neg.proposed_length_years if (is_agent_or_staff or is_player) else None,
        created_at=neg.created_at,
        agreed_at=neg.agreed_at,
    )


@router.get("/deals/{deal_id}/agent-negotiation", response_model=AgentNegotiationResponse)
async def get_agent_negotiation(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deal = await _get_deal_or_404(db, deal_id)
    neg = await service.get_agent_negotiation(db, deal.id)
    if neg is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No negotiation found")
    return _build_neg_response(neg, caller_user_type=current_user.user_type.value)


@router.patch("/deals/{deal_id}/agent-negotiation/terms", response_model=AgentNegotiationResponse)
async def update_negotiation_terms(
    deal_id: uuid.UUID,
    body: UpdateNegotiationTermsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.auth.models import AgentProfile, UserType
    if current_user.user_type != UserType.AGENT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Agent access required")

    profile_result = await db.execute(
        select(AgentProfile).where(AgentProfile.user_id == current_user.id)
    )
    agent_profile = profile_result.scalar_one_or_none()
    if agent_profile is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Agent profile not found")

    deal = await _get_deal_or_404(db, deal_id)
    updates = body.model_dump(exclude_unset=True)

    try:
        neg = await service.upsert_negotiation_terms(db, deal, agent_profile.id, updates)
        await db.commit()
        await db.refresh(neg)
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return _build_neg_response(neg, caller_user_type="AGENT")


@router.post("/deals/{deal_id}/agent-negotiation/club-respond", response_model=AgentNegotiationResponse)
async def club_respond_to_negotiation(
    deal_id: uuid.UUID,
    body: NegotiationRespondRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    club = await _get_club_or_403(db, current_user)
    deal = await _get_deal_or_404(db, deal_id)

    try:
        neg = await service.club_respond_to_negotiation(db, deal, club.id, body.agreement)
        await db.commit()
        await db.refresh(neg)
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return _build_neg_response(neg, caller_user_type="CLUB")


@router.post("/deals/{deal_id}/agent-negotiation/player-respond", response_model=AgentNegotiationResponse)
async def player_respond_to_negotiation(
    deal_id: uuid.UUID,
    body: NegotiationRespondRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.auth.models import AgentProfile, PlayerProfile, UserType

    deal = await _get_deal_or_404(db, deal_id)

    # Allow: mandated agent OR the player linked to this deal
    if current_user.user_type == UserType.AGENT:
        neg = await service.get_agent_negotiation(db, deal.id)
        if neg is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No negotiation found")
        profile_r = await db.execute(select(AgentProfile).where(AgentProfile.user_id == current_user.id))
        profile = profile_r.scalar_one_or_none()
        if profile is None or profile.id != neg.agent_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not the mandated agent")
    elif current_user.user_type == UserType.PLAYER:
        pp_r = await db.execute(select(PlayerProfile).where(PlayerProfile.user_id == current_user.id))
        pp = pp_r.scalar_one_or_none()
        if pp is None or pp.player_id != deal.player_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not the player for this deal")
    elif not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Agent or player access required")

    try:
        neg = await service.player_respond_to_negotiation(db, deal, body.agreement)
        await db.commit()
        await db.refresh(neg)
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return _build_neg_response(neg, caller_user_type=current_user.user_type.value)


@router.patch("/deals/{deal_id}/instalments/{instalment_id}/paid", response_model=DealInstalmentResponse)
async def mark_instalment_paid(
    deal_id: uuid.UUID,
    instalment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    club = await _get_club_or_403(db, current_user)
    deal = await _get_deal_or_404(db, deal_id)

    try:
        inst = await service.mark_instalment_paid(
            db, deal, instalment_id,
            actor_club_id=club.id,
            is_staff=current_user.is_superuser,
        )
        await db.commit()
        await db.refresh(inst)
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return DealInstalmentResponse.model_validate(inst)
