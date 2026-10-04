"""M4 — Offer endpoints."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.clubs import service as clubs_service
from app.common.schemas import Paginated
from app.database import get_db
from app.clubs.capabilities import Capability, require_club_capability
from app.deps import get_buyer_user, get_current_user, get_optional_user
from app.offers import actions, service
from app.offers.models import OfferStatus
from app.offers.schemas import (
    OfferDecisionRequest,
    OfferCounterRequest,
    OfferCreateRequest,
    OfferImproveRequest,
    OfferMessageRequest,
    OfferMessageResponse,
    OfferResponse,
)
from app.sales.schemas import DealStubResponse, OrderBookResponse

router = APIRouter(tags=["offers"])

# TRA-151: offers are market actions — MANAGER and above; SCOUT/READONLY get 403.
_market_write = require_club_capability(Capability.MARKET_WRITE)


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


def _buyer_is_masked(offer, viewer_club_id: uuid.UUID | None) -> bool:
    """Should this viewer be kept from knowing who the buying club is?

    Anonymity ends at acceptance — that is the bargain the buyer strikes: stay
    undisclosed while the seller decides, be named the moment they agree. An
    offer that is rejected, withdrawn or left to expire therefore stays
    anonymous permanently, which is the point: interest that came to nothing
    was never disclosed.

    Administrators are not special-cased here because they never reach this
    path — `admin/router.py` validates `OfferResponse` straight off the ORM row,
    so staff already see the real club. If that ever changes, it has to opt out
    of masking explicitly rather than inherit it by accident.
    """
    if not offer.is_anonymous:
        return False
    if offer.status == OfferStatus.ACCEPTED:   # revealed on acceptance
        return False
    return str(viewer_club_id) != str(offer.from_club_id)   # the buyer sees themselves


def _mask_buyer(resp: OfferResponse, offer) -> OfferResponse:
    """Strip every field that would identify the buying club.

    The name is the obvious one; the ids matter just as much, because anyone
    holding `from_club_id` can read the club straight off `GET /clubs/{id}`.
    `to_club_id` and the seller's own actions are left alone — only the buyer
    is being concealed, and the seller already knows themselves.
    """
    buyer_id = str(offer.from_club_id)
    resp.from_club = None
    resp.from_club_id = None
    resp.buyer_league_name = offer.from_club.masking_league if offer.from_club else None

    if str(resp.last_actor_club_id) == buyer_id:
        resp.last_actor_club_id = None

    for message in resp.messages:
        if str(message.sender_club_id) == buyer_id:
            message.sender_club_id = None
            message.sender_club = None

    for event in resp.events:
        if str(event.actor_club_id) == buyer_id:
            event.actor_club_id = None

    return resp


def _offer_response(offer, viewer_club_id: uuid.UUID, deal=None) -> OfferResponse:
    """B1: whose_move is relative to the viewer's own club, so it can't be a
    plain model_validate() attribute — set it explicitly here instead. `deal` is
    likewise passed in rather than looked up, so list endpoints can batch.

    This is also the single chokepoint where an anonymous buyer is masked. Doing
    it here rather than per-endpoint is deliberate: the identity leaks through
    five separate fields, and a display-layer guard that misses one makes the
    anonymity fake while looking correct (the failure mode ADR 0003 documents).
    """
    resp = OfferResponse.model_validate(offer)
    resp.whose_move = service.compute_offer_whose_move(offer, viewer_club_id)
    if deal is not None:
        from app.players.schemas import ActiveDealStub

        resp.deal = ActiveDealStub.model_validate(deal)
    if _buyer_is_masked(offer, viewer_club_id):
        resp = _mask_buyer(resp, offer)
    return resp


async def _offer_page(db: AsyncSession, offers, viewer_club_id: uuid.UUID) -> list[OfferResponse]:
    """One deal query for the whole page, never one per row."""
    from app.deals import service as deals_service

    deals = await deals_service.get_deals_by_offer_ids(db, [o.id for o in offers])
    return [_offer_response(o, viewer_club_id, deals.get(o.id)) for o in offers]


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
        items=await _offer_page(db, offers, club.id),
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
        items=await _offer_page(db, offers, club.id),
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
    return _offer_response(offer, club.id) if offer else None


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
    from app.deals import service as deals_service

    deals = await deals_service.get_deals_by_offer_ids(db, [offer.id])
    return _offer_response(offer, club.id, deals.get(offer.id))


# ── Actions (logic in offers/actions.py) ──────────────────────────────────────


def _http(exc: actions.OfferActionError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


def _pending(result: actions.ActionResult) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={"status": "PENDING_APPROVAL", "approval_id": str(result.approval.id)},
    )


@router.post("/offers", response_model=OfferResponse, status_code=status.HTTP_201_CREATED)
async def create_offer(
    body: OfferCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_buyer_user),
    _write: User = Depends(_market_write),
):
    club = await _get_club_or_403(db, current_user)
    try:
        result = await actions.create_offer(db, current_user, club, body)
    except actions.OfferActionError as exc:
        raise _http(exc)
    if result.approval is not None:
        return _pending(result)
    return _offer_response(result.offer, club.id)


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
        result = await actions.counter_offer(db, current_user, club, offer, body)
    except actions.OfferActionError as exc:
        raise _http(exc)
    return _offer_response(result.offer, club.id)


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
        result = await actions.improve_offer(db, current_user, club, offer, body)
    except actions.OfferActionError as exc:
        raise _http(exc)
    return _offer_response(result.offer, club.id)


@router.post("/offers/{offer_id}/accept", response_model=DealStubResponse)
async def accept_offer(
    offer_id: uuid.UUID,
    body: OfferDecisionRequest | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _write: User = Depends(_market_write),
):
    club = await _get_club_or_403(db, current_user)
    offer = await _get_offer_or_404(db, offer_id)
    try:
        result = await actions.accept_offer(db, current_user, club, offer, ai_assisted=bool(body and body.ai_assisted))
    except actions.OfferActionError as exc:
        raise _http(exc)
    if result.approval is not None:
        return _pending(result)
    return DealStubResponse.model_validate(result.deal)


@router.post("/offers/{offer_id}/reject", response_model=OfferResponse)
async def reject_offer(
    offer_id: uuid.UUID,
    body: OfferDecisionRequest | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _write: User = Depends(_market_write),
):
    club = await _get_club_or_403(db, current_user)
    offer = await _get_offer_or_404(db, offer_id)
    try:
        result = await actions.reject_offer(db, current_user, club, offer, ai_assisted=bool(body and body.ai_assisted))
    except actions.OfferActionError as exc:
        raise _http(exc)
    return _offer_response(result.offer, club.id)


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
        result = await actions.withdraw_offer(db, current_user, club, offer)
    except actions.OfferActionError as exc:
        raise _http(exc)
    return _offer_response(result.offer, club.id)


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
        msg = await actions.add_message(db, current_user, club, offer, body.body)
    except actions.OfferActionError as exc:
        raise _http(exc)
    return OfferMessageResponse.model_validate(msg)
