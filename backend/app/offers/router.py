"""M4 — Offer endpoints."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.approvals import service as approvals_service
from app.approvals.models import ApprovalActionType
from app.auth.models import User
from app.clubs import service as clubs_service
from app.common.schemas import Paginated
from app.database import get_db
from app.clubs.capabilities import Capability, require_club_capability
from app.deps import get_buyer_user, get_current_user, get_optional_user
from app.notifications import service as notif_service
from app.transfer_window import service as window_service
from app.notifications.models import NotificationType
from app.offers import service
from app.offers.models import OfferStatus
from app.offers.schemas import (
    OfferCounterRequest,
    OfferCreateRequest,
    OfferImproveRequest,
    OfferMessageRequest,
    OfferMessageResponse,
    OfferResponse,
)
from app.sales.schemas import DealStubResponse, OrderBookResponse
from app.ws.manager import manager as ws_manager

router = APIRouter(tags=["offers"])

# TRA-151: offers are market actions — MANAGER and above; SCOUT/READONLY get 403.
_market_write = require_club_capability(Capability.MARKET_WRITE)


async def _db_notify_offer(
    db: AsyncSession,
    offer,
    *,
    recipient_club_id,
    ntype: NotificationType,
    message: str,
) -> None:
    """Create DB notifications for an offer event, role-routed per club
    (TRA-152). Must be called before commit."""
    if recipient_club_id is None:
        return
    await notif_service.notify_club(
        db,
        uuid.UUID(str(recipient_club_id)),
        type=ntype,
        message=message,
        link=f"/offers/{offer.id}",
        related_player_id=offer.player_id,
    )


async def _notify_player_of_offer(db: AsyncSession, offer) -> None:
    """TRA-76: if the player has their own login, let them know a club has made an offer."""
    from app.auth.models import PlayerProfile

    result = await db.execute(select(PlayerProfile).where(PlayerProfile.player_id == offer.player_id))
    player_profile = result.scalar_one_or_none()
    if player_profile is None:
        return
    await notif_service.create_notification(
        db,
        recipient_user_id=player_profile.user_id,
        type=NotificationType.OFFER_RECEIVED,
        message="A club has made an offer for your transfer",
        link="/player/profile",
        related_player_id=offer.player_id,
    )


async def _notify_offer_parties(db: AsyncSession, offer_id: uuid.UUID) -> None:
    """Push OFFER_UPDATED to every member of both parties of an offer."""
    offer = await service.get_offer_by_id(db, offer_id)
    if offer is None:
        return
    user_ids: list[uuid.UUID] = []
    for club_id in [offer.from_club_id, offer.to_club_id]:
        if club_id is None:
            continue
        user_ids += await notif_service.club_member_user_ids(db, uuid.UUID(str(club_id)))
    await ws_manager.broadcast_to_users(
        list(set(user_ids)),
        {"type": "OFFER_UPDATED", "id": str(offer_id)},
    )


async def _get_club_or_403(db: AsyncSession, user: User):
    club = await clubs_service.get_club_for_user(db, user.id)
    if club is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No club profile")
    return club


async def _get_offer_or_404(db: AsyncSession, offer_id: uuid.UUID):
    offer = await service.get_offer_by_id(db, offer_id)
    if offer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found")
    return offer


# ── Competition (player-scoped order book) ────────────────────────────────────


@router.get("/offers/competition/{player_id}", response_model=OrderBookResponse)
async def get_offer_competition(
    player_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
) -> OrderBookResponse:
    """Player-scoped order book — works for both sale-linked and standalone offers."""
    my_club_id = None
    if current_user:
        club = await clubs_service.get_club_for_user(db, current_user.id)
        if club:
            my_club_id = club.id
    return await service.get_offer_competition(db, player_id, my_club_id)


# ── List ──────────────────────────────────────────────────────────────────────


@router.get("/offers/received", response_model=Paginated[OfferResponse])
async def list_received_offers(
    offer_status: OfferStatus | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = 1,
    page_size: int = 30,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    club = await _get_club_or_403(db, current_user)
    offers, total = await service.list_offers(
        db, club_id=club.id, direction="received", status=offer_status,
        date_from=date_from, date_to=date_to, page=page, page_size=page_size,
    )
    return Paginated(
        items=[OfferResponse.model_validate(o) for o in offers],
        total=total, page=page, page_size=page_size,
    )


@router.get("/offers/sent", response_model=Paginated[OfferResponse])
async def list_sent_offers(
    offer_status: OfferStatus | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = 1,
    page_size: int = 30,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    club = await _get_club_or_403(db, current_user)
    offers, total = await service.list_offers(
        db, club_id=club.id, direction="sent", status=offer_status,
        date_from=date_from, date_to=date_to, page=page, page_size=page_size,
    )
    return Paginated(
        items=[OfferResponse.model_validate(o) for o in offers],
        total=total, page=page, page_size=page_size,
    )


# ── Active offer check (must be before /{offer_id} to avoid UUID parse collision) ──


@router.get("/offers/active-for-player/{player_id}", response_model=OfferResponse | None)
async def get_active_offer_for_player(
    player_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the caller's active (SENT/COUNTERED) offer for a player, or null."""
    club = await _get_club_or_403(db, current_user)
    offer = await service.get_active_offer_for_buyer(db, player_id, club.id)
    return OfferResponse.model_validate(offer) if offer else None


# ── Detail ────────────────────────────────────────────────────────────────────


@router.get("/offers/{offer_id}", response_model=OfferResponse)
async def get_offer(
    offer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    club = await _get_club_or_403(db, current_user)
    offer = await _get_offer_or_404(db, offer_id)
    if club.id not in (offer.from_club_id, offer.to_club_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a party to this offer")
    return OfferResponse.model_validate(offer)


# ── Create ────────────────────────────────────────────────────────────────────


@router.post("/offers", response_model=OfferResponse, status_code=status.HTTP_201_CREATED)
async def create_offer(
    body: OfferCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_buyer_user),
    _write: User = Depends(_market_write),
):
    club = await _get_club_or_403(db, current_user)

    if not current_user.is_superuser and not await window_service.is_transfer_allowed(db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Transfer window is closed. Offers cannot be made outside of a transfer window.",
        )

    # Guard: one active offer per (buyer, player) at a time
    existing = await service.get_active_offer_for_buyer(db, body.player_id, club.id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": "You already have an active offer for this player.", "offer_id": str(existing.id)},
        )

    # Guard: cannot make offers while a deal is already in progress for this player
    from app.deals import service as deals_service
    active_deal = await deals_service.get_active_deal_for_player(db, body.player_id)
    if active_deal and active_deal.status == "IN_PROGRESS":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This player already has a transfer deal in progress. New offers cannot be made at this time.",
        )

    # Phase 5 (D7): a MANAGER's offer at/above the club threshold is captured
    # as a pending approval after the guards above — nothing executed yet.
    from app.players import service as players_service
    _player = await players_service.get_player_by_id(db, body.player_id)
    _pname = _player.name if _player else "a player"
    approval = await approvals_service.maybe_capture(
        db,
        current_user=current_user,
        club=club,
        action_type=ApprovalActionType.CREATE_OFFER,
        amount=body.fee_amount,
        payload={
            "player_id": str(body.player_id),
            "to_club_id": str(body.to_club_id) if body.to_club_id else None,
            "sale_id": str(body.sale_id) if body.sale_id else None,
            "fee_amount": str(body.fee_amount),
            "wage_weekly": str(body.wage_weekly) if body.wage_weekly else None,
            "contract_years": body.contract_years,
            "contract_end_date": body.contract_end_date.isoformat() if body.contract_end_date else None,
            "add_ons": body.add_ons,
            "expires_at": body.expires_at.isoformat() if body.expires_at else None,
        },
        summary=f"Offer £{body.fee_amount:,.0f} for {_pname}",
    )
    if approval is not None:
        await db.commit()
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={"status": "PENDING_APPROVAL", "approval_id": str(approval.id)},
        )

    try:
        offer = await service.create_offer(
            db,
            player_id=body.player_id,
            from_club_id=club.id,
            to_club_id=body.to_club_id,
            sale_id=body.sale_id,
            fee_amount=body.fee_amount,
            wage_weekly=body.wage_weekly,
            contract_years=body.contract_years,
            contract_end_date=body.contract_end_date,
            add_ons=body.add_ons,
            expires_at=body.expires_at,
        )
        await _db_notify_offer(
            db, offer,
            recipient_club_id=offer.to_club_id,
            ntype=NotificationType.OFFER_RECEIVED,
            message="You have received a new offer",
        )
        await _notify_player_of_offer(db, offer)
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    offer = await service.get_offer_by_id(db, offer.id)
    await _notify_offer_parties(db, offer.id)
    return OfferResponse.model_validate(offer)


# ── Counter ───────────────────────────────────────────────────────────────────


@router.post("/offers/{offer_id}/counter", response_model=OfferResponse)
async def counter_offer(
    offer_id: uuid.UUID,
    body: OfferCounterRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _write: User = Depends(_market_write),
):
    club = await _get_club_or_403(db, current_user)
    offer = await _get_offer_or_404(db, offer_id)

    try:
        await service.counter_offer(
            db,
            offer,
            actor_club_id=club.id,
            fee_amount=body.fee_amount,
            wage_weekly=body.wage_weekly,
            contract_years=body.contract_years,
            contract_end_date=body.contract_end_date,
            add_ons=body.add_ons,
            expires_at=body.expires_at,
        )
        other_club_id = offer.to_club_id if offer.from_club_id == club.id else offer.from_club_id
        await _db_notify_offer(
            db, offer,
            recipient_club_id=other_club_id,
            ntype=NotificationType.OFFER_COUNTERED,
            message="A counter offer has been submitted",
        )
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    offer = await service.get_offer_by_id(db, offer_id)
    await _notify_offer_parties(db, offer_id)
    return OfferResponse.model_validate(offer)


@router.post("/offers/{offer_id}/improve", response_model=OfferResponse)
async def improve_offer(
    offer_id: uuid.UUID,
    body: OfferImproveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _write: User = Depends(_market_write),
):
    """Item 2: the buyer raises their own pending offer without waiting for a reply."""
    club = await _get_club_or_403(db, current_user)
    offer = await _get_offer_or_404(db, offer_id)

    try:
        await service.improve_own_offer(
            db,
            offer,
            actor_club_id=club.id,
            fee_amount=body.fee_amount,
            wage_weekly=body.wage_weekly,
            add_ons=body.add_ons,
        )
        await _db_notify_offer(
            db, offer,
            recipient_club_id=offer.to_club_id,
            ntype=NotificationType.OFFER_COUNTERED,
            message="The buyer has raised their offer",
        )
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    offer = await service.get_offer_by_id(db, offer_id)
    await _notify_offer_parties(db, offer_id)
    return OfferResponse.model_validate(offer)


# ── Accept ────────────────────────────────────────────────────────────────────


@router.post("/offers/{offer_id}/accept", response_model=DealStubResponse)
async def accept_offer(
    offer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _write: User = Depends(_market_write),
):
    club = await _get_club_or_403(db, current_user)
    offer = await _get_offer_or_404(db, offer_id)

    # Phase 5 (D7): a MANAGER accepting an offer at/above the club threshold is
    # captured as a pending approval instead of executing.
    from app.players import service as players_service
    _player = await players_service.get_player_by_id(db, offer.player_id)
    _pname = _player.name if _player else "a player"
    approval = await approvals_service.maybe_capture(
        db,
        current_user=current_user,
        club=club,
        action_type=ApprovalActionType.ACCEPT_OFFER,
        amount=offer.fee_amount,
        payload={"offer_id": str(offer_id)},
        summary=f"Accept £{offer.fee_amount:,.0f} offer for {_pname}",
    )
    if approval is not None:
        await db.commit()
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={"status": "PENDING_APPROVAL", "approval_id": str(approval.id)},
        )

    try:
        deal = await service.accept_offer(db, offer, actor_club_id=club.id)
        await _db_notify_offer(
            db, offer,
            recipient_club_id=offer.from_club_id,
            ntype=NotificationType.OFFER_ACCEPTED,
            message="Your offer has been accepted",
        )
        await db.commit()
        await db.refresh(deal)
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    await _notify_offer_parties(db, offer_id)
    return DealStubResponse.model_validate(deal)


# ── Reject ────────────────────────────────────────────────────────────────────


@router.post("/offers/{offer_id}/reject", response_model=OfferResponse)
async def reject_offer(
    offer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _write: User = Depends(_market_write),
):
    club = await _get_club_or_403(db, current_user)
    offer = await _get_offer_or_404(db, offer_id)

    try:
        await service.reject_offer(db, offer, actor_club_id=club.id)
        await _db_notify_offer(
            db, offer,
            recipient_club_id=offer.from_club_id,
            ntype=NotificationType.OFFER_REJECTED,
            message="Your offer has been rejected",
        )
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    offer = await service.get_offer_by_id(db, offer_id)
    await _notify_offer_parties(db, offer_id)
    return OfferResponse.model_validate(offer)


# ── Withdraw ──────────────────────────────────────────────────────────────────


@router.post("/offers/{offer_id}/withdraw", response_model=OfferResponse)
async def withdraw_offer(
    offer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _write: User = Depends(_market_write),
):
    club = await _get_club_or_403(db, current_user)
    offer = await _get_offer_or_404(db, offer_id)

    try:
        await service.withdraw_offer(db, offer, actor_club_id=club.id)
        other_club_id = offer.to_club_id if offer.from_club_id == club.id else offer.from_club_id
        await _db_notify_offer(
            db, offer,
            recipient_club_id=other_club_id,
            ntype=NotificationType.OFFER_WITHDRAWN,
            message="An offer has been withdrawn",
        )
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    offer = await service.get_offer_by_id(db, offer_id)
    await _notify_offer_parties(db, offer_id)
    return OfferResponse.model_validate(offer)


# ── Messages ──────────────────────────────────────────────────────────────────


@router.post("/offers/{offer_id}/messages", response_model=OfferMessageResponse, status_code=status.HTTP_201_CREATED)
async def add_message(
    offer_id: uuid.UUID,
    body: OfferMessageRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    # TRA-151: negotiation messages speak for the club — previously ungated.
    _write: User = Depends(_market_write),
):
    club = await _get_club_or_403(db, current_user)
    offer = await _get_offer_or_404(db, offer_id)

    try:
        msg = await service.add_message(db, offer, sender_club_id=club.id, body=body.body)
        other_club_id = offer.to_club_id if offer.from_club_id == club.id else offer.from_club_id
        await _db_notify_offer(
            db, offer,
            recipient_club_id=other_club_id,
            ntype=NotificationType.OFFER_MESSAGE,
            message="New message in your negotiation",
        )
        await db.commit()
        await db.refresh(msg)
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    await _notify_offer_parties(db, offer_id)
    return OfferMessageResponse.model_validate(msg)
