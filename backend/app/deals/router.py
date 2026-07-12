"""M4 — Deal lifecycle endpoints."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.clubs import service as clubs_service
from app.common.schemas import Paginated
from app.database import get_db
from app.deals import room_service, service
from app.deals.models import ClauseStatus, DealStage, DealStatus
from app.deals.schemas import (
    AgentNegotiationResponse,
    ClubTransferStat,
    CollapseRequest,
    CompletedStats,
    CreateClauseRequest,
    CreateInstalmentsRequest,
    DealClauseResponse,
    DealInstalmentResponse,
    DealNoteRequest,
    DealNoteResponse,
    DealResponse,
    MedicalCheckResponse,
    NegotiationRespondRequest,
    OngoingStats,
    PersonalTermsResponse,
    PositionBreakdown,
    SetPersonalTermsRequest,
    TransferActivityItem,
    TransferAnalytics,
    UpdateClauseStatusRequest,
    UpdateDealRequest,
    UpdateNegotiationTermsRequest,
    UpsertMedicalCheckRequest,
)
from app.clubs.capabilities import Capability, ensure_club_capability, require_club_capability
from app.deps import get_current_user
from app.notifications import service as notif_service
from app.notifications.models import NotificationType
from app.players import service as players_service
from app.ws.manager import manager as ws_manager

router = APIRouter(tags=["deals"])

# TRA-151: deal lifecycle writes — MANAGER and above; SCOUT/READONLY get 403.
# Mixed-caller endpoints (advance, personal terms) check inside their club branch.
_deal_write = require_club_capability(Capability.DEAL_WRITE)


async def _get_club_or_403(db: AsyncSession, user: User):
    # TRA-146: owner-or-staff — staff act for their club here; write endpoints
    # are role-gated by DEAL_WRITE, so this resolver widening grants no writes
    # to SCOUT/READONLY (the D4 sequencing invariant).
    club = await clubs_service.get_club_for_user(db, user.id)
    if club is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No club profile")
    return club


async def _notify_deal_parties(db: AsyncSession, deal_id: uuid.UUID) -> None:
    """Push DEAL_UPDATED to every member of both clubs involved in a deal."""
    deal = await service.get_deal_by_id(db, deal_id)
    if deal is None:
        return
    user_ids: list[uuid.UUID] = []
    for club_id in [deal.buyer_club_id, deal.seller_club_id]:
        if club_id is None:
            continue
        user_ids += await notif_service.club_member_user_ids(db, uuid.UUID(str(club_id)))
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
    """Create DB notifications for both parties of a deal, role-routed per club
    (TRA-152). Must be called before commit."""
    player_id = deal.player_id
    deal_link = f"/deals/{deal.id}"
    for club_id in [deal.buyer_club_id, deal.seller_club_id]:
        if club_id is None:
            continue
        await notif_service.notify_club(
            db,
            uuid.UUID(str(club_id)),
            type=ntype,
            message=message,
            link=deal_link,
            related_player_id=player_id,
        )


async def _notify_personal_terms_sent(
    db: AsyncSession, deal, pt, *, consent_was_reset: bool = False
) -> None:
    """TRA-76: notify the player and mandated agent that personal terms are ready for review.

    Item 9: editing terms silently reset a player's prior AGREED consent back to
    PENDING with no indication anything changed. When consent_was_reset is True,
    say so explicitly instead of sending the generic first-proposal message.
    """
    from app.auth.models import AgentProfile, PlayerProfile

    pp_result = await db.execute(select(PlayerProfile).where(PlayerProfile.player_id == deal.player_id))
    player_profile = pp_result.scalar_one_or_none()
    if player_profile is not None:
        message = (
            "The proposed terms have changed, which resets your previous agreement — "
            "please review and respond again"
            if consent_was_reset
            else "Personal terms have been proposed for your transfer — review and respond"
        )
        await notif_service.create_notification(
            db,
            recipient_user_id=player_profile.user_id,
            type=NotificationType.DEAL_PERSONAL_TERMS_SENT,
            message=message,
            link="/player/profile",
            related_player_id=deal.player_id,
        )

    if pt.agent_id is not None:
        agent_result = await db.execute(select(AgentProfile).where(AgentProfile.id == pt.agent_id))
        agent = agent_result.scalar_one_or_none()
        if agent is not None:
            await notif_service.create_notification(
                db,
                recipient_user_id=agent.user_id,
                type=NotificationType.DEAL_PERSONAL_TERMS_SENT,
                message="Personal terms saved — awaiting player consent",
                link=f"/deals/{deal.id}",
                related_player_id=deal.player_id,
            )


async def _get_deal_or_404(db: AsyncSession, deal_id: uuid.UUID):
    deal = await service.get_deal_by_id(db, deal_id)
    if deal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")
    return deal


async def _build_deal_response(
    db: AsyncSession,
    deal,
    *,
    caller_user_type: str | None = None,
    caller_club_id: uuid.UUID | None = None,
) -> DealResponse:
    """TRA-137: field-scoped — commission terms hidden from players; medical
    data hidden from the selling club (GDPR: special-category personal data).
    """
    is_player = caller_user_type == "PLAYER"
    is_seller = (
        caller_club_id is not None
        and caller_club_id == deal.seller_club_id
        and not is_player
    )
    personal_terms = None
    if deal.personal_terms is not None:
        personal_terms = await _build_personal_terms_response(db, deal.personal_terms, deal)
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
        option_exercised=deal.option_exercised,
        seller_wage_contribution_weekly=deal.seller_wage_contribution_weekly,
        sell_on_pct=deal.sell_on_pct,
        fee_disclosed=deal.fee_disclosed,
        clauses=deal.clauses,
        instalments=deal.instalments,
        agent_commission_pct=None if is_player else deal.agent_commission_pct,
        agent_commission_amount=None if is_player else deal.agent_commission_amount,
        commission_payer=None if is_player else deal.commission_payer,
        commission_agent_id=None if is_player else deal.commission_agent_id,
        personal_terms=personal_terms,
        medical_check=None if is_seller else deal.medical_check,
        notes=deal.notes,
        completed_at=deal.completed_at,
        created_at=deal.created_at,
        updated_at=deal.updated_at,
        is_auction_deal=deal.is_auction_deal,
        buyer_club=deal.buyer_club,
        seller_club=deal.seller_club,
        player=deal.player,
        deal_notes=deal.deal_notes,
        sla_deadline=deal.sla_deadline,
        sla_escalated_at=deal.sla_escalated_at,
        confirmed_at=deal.confirmed_at,
    )


# ── Public transfer feed ──────────────────────────────────────────────────────


def _to_transfer_item(deal) -> TransferActivityItem:
    """Build a public TransferActivityItem, respecting the club's fee disclosure choice."""
    from app.deals.schemas import ClubSummary, PlayerSummary
    return TransferActivityItem(
        id=deal.id,
        player=PlayerSummary.model_validate(deal.player) if deal.player else None,
        buyer_club=ClubSummary.model_validate(deal.buyer_club) if deal.buyer_club else None,
        seller_club=ClubSummary.model_validate(deal.seller_club) if deal.seller_club else None,
        agreed_fee=deal.agreed_fee if deal.fee_disclosed else None,
        is_auction_deal=deal.is_auction_deal,
        completed_at=deal.completed_at,
        created_at=deal.created_at,
    )


@router.get("/transfers/analytics", response_model=TransferAnalytics)
async def get_transfer_analytics(
    db: AsyncSession = Depends(get_db),
):
    """Market-wide transfer analytics — no auth required."""
    data = await service.get_transfer_analytics(db)

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
            highest_fee_deal=_to_transfer_item(c["highest_fee_deal"]) if c["highest_fee_deal"] else None,
            top_transfers=[_to_transfer_item(d) for d in c["top_transfers"]],
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
    items = [_to_transfer_item(d) for d in deals]
    return Paginated(items=items, total=total, page=page, page_size=page_size)


# ── List + detail ─────────────────────────────────────────────────────────────


@router.get("/deals", response_model=Paginated[DealResponse])
async def list_deals(
    deal_status: DealStatus | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = 1,
    page_size: int = 30,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    club = await _get_club_or_403(db, current_user)
    deals, total = await service.list_deals(
        db, club_id=club.id, status=deal_status, date_from=date_from, date_to=date_to,
        page=page, page_size=page_size,
    )
    return Paginated(
        items=[await _build_deal_response(db, d) for d in deals],
        total=total, page=page, page_size=page_size,
    )


@router.get("/deals/{deal_id}", response_model=DealResponse)
async def get_deal(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """TRA-137: any legitimate participant (buyer/seller club, mandated agent,
    the player, staff) can load the deal — not just clubs."""
    deal = await _get_deal_or_404(db, deal_id)
    if not await room_service.is_deal_participant(db, deal, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a party to this deal")
    club = await clubs_service.get_club_for_user(db, current_user.id)
    return await _build_deal_response(
        db, deal,
        caller_user_type=current_user.user_type.value,
        caller_club_id=club.id if club else None,
    )


# ── Stage advancement ─────────────────────────────────────────────────────────


@router.post("/deals/{deal_id}/advance", response_model=DealResponse)
async def advance_deal(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.auth.models import AgentProfile, UserType

    deal = await _get_deal_or_404(db, deal_id)

    actor_club_id: uuid.UUID | None = None
    is_mandated_agent = False
    if current_user.is_superuser:
        pass  # staff needs no club — is_staff already bypasses the party check below
    elif current_user.user_type == UserType.AGENT and deal.stage == DealStage.AGENT_NEGOTIATION:
        neg = await service.get_agent_negotiation(db, deal.id)
        if neg is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No negotiation found")
        profile_r = await db.execute(select(AgentProfile).where(AgentProfile.user_id == current_user.id))
        profile = profile_r.scalar_one_or_none()
        if profile is None or profile.id != neg.agent_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not the mandated agent")
        is_mandated_agent = True
    else:
        club = await _get_club_or_403(db, current_user)
        # TRA-151: mixed-caller endpoint — capability checked in the club branch
        # only (agents are authorized by the mandate check above).
        await ensure_club_capability(db, current_user, Capability.DEAL_WRITE)
        actor_club_id = club.id

    try:
        await service.advance_deal(
            db, deal, actor_club_id=actor_club_id, is_staff=current_user.is_superuser,
            is_mandated_agent=is_mandated_agent, actor_user_id=current_user.id,
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
    return await _build_deal_response(db, deal)


# ── Collapse ──────────────────────────────────────────────────────────────────


@router.post("/deals/{deal_id}/collapse", response_model=DealResponse)
async def collapse_deal(
    deal_id: uuid.UUID,
    body: CollapseRequest = CollapseRequest(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _write: User = Depends(_deal_write),
):
    club = await _get_club_or_403(db, current_user)
    deal = await _get_deal_or_404(db, deal_id)

    try:
        await service.collapse_deal(
            db, deal, actor_club_id=club.id, is_staff=current_user.is_superuser,
            actor_user_id=current_user.id, reason=body.reason,
        )
        player_name = deal.player.name if deal.player else "the player"
        reason_suffix = f": {body.reason.strip()}" if body.reason and body.reason.strip() else ""
        await _db_notify_deal_parties(
            db, deal,
            ntype=NotificationType.DEAL_COLLAPSED,
            message=f"Deal for {player_name} has collapsed{reason_suffix}",
        )
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    deal = await service.get_deal_by_id(db, deal_id)
    await _notify_deal_parties(db, deal_id)
    return await _build_deal_response(db, deal)


# ── Notes ─────────────────────────────────────────────────────────────────────


@router.post("/deals/{deal_id}/notes", response_model=DealNoteResponse, status_code=status.HTTP_201_CREATED)
async def add_note(
    deal_id: uuid.UUID,
    body: DealNoteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _write: User = Depends(_deal_write),
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
        await service.staff_complete(db, deal, actor_user_id=current_user.id)
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
    return await _build_deal_response(db, deal)


@router.post("/deals/{deal_id}/staff/collapse", response_model=DealResponse)
async def staff_collapse_deal(
    deal_id: uuid.UUID,
    body: CollapseRequest = CollapseRequest(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Staff only")
    deal = await _get_deal_or_404(db, deal_id)

    try:
        await service.staff_collapse(db, deal, actor_user_id=current_user.id, reason=body.reason)
        player_name = deal.player.name if deal.player else "the player"
        reason_suffix = f": {body.reason.strip()}" if body.reason and body.reason.strip() else ""
        await _db_notify_deal_parties(
            db, deal,
            ntype=NotificationType.DEAL_COLLAPSED,
            message=f"Deal for {player_name} has collapsed{reason_suffix}",
        )
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    deal = await service.get_deal_by_id(db, deal_id)
    await _notify_deal_parties(db, deal_id)
    return await _build_deal_response(db, deal)


# ── TRA-56: update deal terms (loan / sell-on) ────────────────────────────────


@router.patch("/deals/{deal_id}", response_model=DealResponse)
async def update_deal(
    deal_id: uuid.UUID,
    body: UpdateDealRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _write: User = Depends(_deal_write),
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
            actor_user_id=current_user.id,
        )
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    deal = await service.get_deal_by_id(db, deal_id)
    return await _build_deal_response(db, deal)


# ── M9: exercise loan option to buy ──────────────────────────────────────────


@router.post("/deals/{deal_id}/exercise-option", response_model=DealResponse, status_code=status.HTTP_201_CREATED)
async def exercise_option(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _write: User = Depends(_deal_write),
):
    """Loaning club exercises the option to buy, creating a new permanent deal at the agreed option price."""
    club = await _get_club_or_403(db, current_user)
    deal = await _get_deal_or_404(db, deal_id)

    try:
        new_deal = await service.exercise_option(
            db, deal,
            actor_club_id=club.id,
            is_staff=current_user.is_superuser,
            actor_user_id=current_user.id,
        )
        player_name = deal.player.name if deal.player else "the player"
        await _db_notify_deal_parties(
            db, new_deal,
            ntype=NotificationType.DEAL_COMPLETED,
            message=f"Option to buy exercised for {player_name} — new permanent deal created",
        )
        await db.commit()
    except (ValueError, PermissionError) as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST if isinstance(exc, ValueError) else status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        )

    new_deal = await service.get_deal_by_id(db, new_deal.id)
    return await _build_deal_response(db, new_deal)


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
    _write: User = Depends(_deal_write),
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
            actor_user_id=current_user.id,
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
    _write: User = Depends(_deal_write),
):
    club = await _get_club_or_403(db, current_user)
    deal = await _get_deal_or_404(db, deal_id)

    try:
        clause = await service.update_clause_status(
            db, deal, clause_id,
            actor_club_id=club.id,
            is_staff=current_user.is_superuser,
            new_status=body.status,
            actor_user_id=current_user.id,
        )
        if clause.status == ClauseStatus.TRIGGERED:
            player_name = deal.player.name if deal.player else "the player"
            await _db_notify_deal_parties(
                db, deal,
                ntype=NotificationType.DEAL_CLAUSE_TRIGGERED,
                message=f"{clause.clause_type.value.title()} clause triggered on {player_name}'s transfer — £{clause.amount:,.0f} owed",
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
    _write: User = Depends(_deal_write),
):
    club = await _get_club_or_403(db, current_user)
    deal = await _get_deal_or_404(db, deal_id)

    items = [{"due_date": i.due_date, "amount": i.amount} for i in body.instalments]
    try:
        instalments = await service.set_instalments(
            db, deal, actor_club_id=club.id, items=items, actor_user_id=current_user.id,
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


# ── TRA-61: medical check ────────────────────────────────────────────────────


@router.get("/deals/{deal_id}/medical-check", response_model=MedicalCheckResponse)
async def get_medical_check(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Medical data is special-category personal data (GDPR). Only the buying
    club and platform staff may read it — the selling club cannot."""
    deal = await _get_deal_or_404(db, deal_id)
    if not current_user.is_superuser:
        club = await clubs_service.get_club_for_user(db, current_user.id)
        if club is None or club.id != deal.buyer_club_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Medical records are only accessible to the buying club and platform staff",
            )
    mc = await service.get_medical_check(db, deal.id)
    if mc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No medical check found")
    return mc


@router.put("/deals/{deal_id}/medical-check", response_model=MedicalCheckResponse)
async def upsert_medical_check(
    deal_id: uuid.UUID,
    body: UpsertMedicalCheckRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """The buying club's medical team records the outcome. Staff may also update it."""
    deal = await _get_deal_or_404(db, deal_id)

    if current_user.is_superuser:
        actor_club_id = None
    else:
        club = await clubs_service.get_club_for_user(db, current_user.id)
        if club is None or club.id != deal.buyer_club_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the buying club or platform staff may record a medical check",
            )
        actor_club_id = club.id

    try:
        mc = await service.upsert_medical_check(
            db, deal, status=body.status, notes=body.notes,
            is_staff=current_user.is_superuser, actor_club_id=actor_club_id,
            actor_user_id=current_user.id,
        )
        await db.commit()
        await db.refresh(mc)
    except (ValueError, PermissionError) as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return mc


# ── TRA-60: personal terms ───────────────────────────────────────────────────


async def _build_personal_terms_response(db: AsyncSession, pt, deal) -> PersonalTermsResponse:
    return PersonalTermsResponse(
        id=pt.id,
        deal_id=pt.deal_id,
        agent_id=pt.agent_id,
        wage_weekly=pt.wage_weekly,
        signing_bonus=pt.signing_bonus,
        length_years=pt.length_years,
        player_consent=pt.player_consent,
        player_has_account=await players_service.player_has_account(db, deal.player_id),
        agreed_at=pt.agreed_at,
        created_at=pt.created_at,
        buyer_club_id=deal.buyer_club_id,
        buyer_club_name=deal.buyer_club.name if deal.buyer_club else "Unknown club",
    )


@router.get("/deals/{deal_id}/personal-terms", response_model=PersonalTermsResponse)
async def get_personal_terms(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deal = await _get_deal_or_404(db, deal_id)
    if not await room_service.is_deal_participant(db, deal, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a party to this deal")
    pt = await service.get_personal_terms(db, deal.id)
    if pt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No personal terms found")
    return await _build_personal_terms_response(db, pt, deal)


@router.put("/deals/{deal_id}/personal-terms", response_model=PersonalTermsResponse)
async def set_personal_terms(
    deal_id: uuid.UUID,
    body: SetPersonalTermsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Agent, the buying club (when there's no mandated agent), or staff sets/updates personal terms."""
    from app.auth.models import AgentProfile, UserType

    deal = await _get_deal_or_404(db, deal_id)

    agent_profile_id = None
    if current_user.user_type == UserType.AGENT:
        profile_r = await db.execute(select(AgentProfile).where(AgentProfile.user_id == current_user.id))
        profile = profile_r.scalar_one_or_none()
        if profile is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Agent profile not found")
        neg = await service.get_agent_negotiation(db, deal.id)
        if neg is None or neg.agent_id != profile.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not the mandated agent for this deal")
        agent_profile_id = profile.id
    elif current_user.user_type == UserType.CLUB:
        # TRA-60: without a mandated agent, the buying club is who proposes personal
        # terms to the player — mirroring how a real club's contract offer works.
        club = await clubs_service.get_club_for_user(db, current_user.id)
        if club is None or club.id != deal.buyer_club_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the buying club can propose personal terms",
            )
        # TRA-151: mixed-caller endpoint — capability checked in the club branch only.
        await ensure_club_capability(db, current_user, Capability.DEAL_WRITE)
    elif not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Buying club, agent, or admin access required")

    try:
        existing_pt = await service.get_personal_terms(db, deal.id)
        consent_was_reset = existing_pt is not None and existing_pt.player_consent == "AGREED"
        pt = await service.set_personal_terms(
            db, deal,
            agent_profile_id=agent_profile_id,
            wage_weekly=body.wage_weekly,
            signing_bonus=body.signing_bonus,
            length_years=body.length_years,
            actor_user_id=current_user.id,
        )
        await _notify_personal_terms_sent(db, deal, pt, consent_was_reset=consent_was_reset)
        await db.commit()
        await db.refresh(pt)
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return await _build_personal_terms_response(db, pt, deal)


@router.post("/deals/{deal_id}/personal-terms/player-consent", response_model=PersonalTermsResponse)
async def player_consent_to_terms(
    deal_id: uuid.UUID,
    body: NegotiationRespondRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Player consents to or declines personal terms. A mandated agent may act
    as their proxy only when the player has no account of their own — the
    same rule used for the club-side of AGENT_NEGOTIATION."""
    from app.auth.models import AgentProfile, PlayerProfile, UserType

    deal = await _get_deal_or_404(db, deal_id)

    if current_user.user_type == UserType.PLAYER:
        pp_r = await db.execute(select(PlayerProfile).where(PlayerProfile.user_id == current_user.id))
        pp = pp_r.scalar_one_or_none()
        if pp is None or pp.player_id != deal.player_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not the player for this deal")
    elif current_user.user_type == UserType.AGENT:
        pt = await service.get_personal_terms(db, deal.id)
        if pt is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No personal terms set")
        profile_r = await db.execute(select(AgentProfile).where(AgentProfile.user_id == current_user.id))
        profile = profile_r.scalar_one_or_none()
        if profile is None or pt.agent_id != profile.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not the mandated agent")
        if await players_service.player_has_account(db, deal.player_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Player has their own account and must respond themselves",
            )
    elif not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Player or agent access required")

    try:
        pt = await service.player_consent_to_terms(db, deal, body.agreement, actor_user_id=current_user.id)
        player_name = deal.player.name if deal.player else "The player"
        decision = "agreed to" if pt.player_consent == "AGREED" else "declined"
        await _db_notify_deal_parties(
            db, deal,
            ntype=NotificationType.PERSONAL_TERMS_DECISION,
            message=f"{player_name} has {decision} the proposed personal terms",
        )
        await db.commit()
        await db.refresh(pt)
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return await _build_personal_terms_response(db, pt, deal)


# ── TRA-127: agent negotiation ────────────────────────────────────────────────


def _build_neg_response(neg, *, caller_user_type: str) -> AgentNegotiationResponse:
    """Return a negotiation response, nulling out fields the caller should not see."""
    is_agent_or_staff = caller_user_type in ("AGENT", "STAFF", "ADMIN")
    is_club = caller_user_type == "CLUB"

    return AgentNegotiationResponse(
        id=neg.id,
        deal_id=neg.deal_id,
        agent_id=neg.agent_id,
        status=neg.status,
        club_agreement=neg.club_agreement,
        # Shown to agent/staff + the buying club — personal terms live in
        # PersonalTerms now, not here, so there's no player-side to gate.
        commission_pct=neg.commission_pct if (is_agent_or_staff or is_club) else None,
        commission_amount=neg.commission_amount if (is_agent_or_staff or is_club) else None,
        commission_payer=neg.commission_payer if (is_agent_or_staff or is_club) else None,
        additional_conditions=neg.additional_conditions if (is_agent_or_staff or is_club) else None,
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
        neg = await service.upsert_negotiation_terms(db, deal, agent_profile.id, updates, actor_user_id=current_user.id)
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
    _write: User = Depends(_deal_write),
):
    club = await _get_club_or_403(db, current_user)
    deal = await _get_deal_or_404(db, deal_id)

    try:
        neg = await service.club_respond_to_negotiation(db, deal, club.id, body.agreement, actor_user_id=current_user.id)
        await db.commit()
        await db.refresh(neg)
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return _build_neg_response(neg, caller_user_type="CLUB")


@router.patch("/deals/{deal_id}/instalments/{instalment_id}/paid", response_model=DealInstalmentResponse)
async def mark_instalment_paid(
    deal_id: uuid.UUID,
    instalment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _write: User = Depends(_deal_write),
):
    club = await _get_club_or_403(db, current_user)
    deal = await _get_deal_or_404(db, deal_id)

    try:
        inst = await service.mark_instalment_paid(
            db, deal, instalment_id,
            actor_club_id=club.id,
            is_staff=current_user.is_superuser,
            actor_user_id=current_user.id,
        )
        await db.commit()
        await db.refresh(inst)
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return DealInstalmentResponse.model_validate(inst)
