"""M3 — Sales + Bidding endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.clubs import service as clubs_service
from app.common.schemas import Paginated
from app.database import get_db
from app.deps import get_buyer_user, get_current_user, get_optional_user, get_seller_user, require_club_write_access
from app.notifications import service as notif_service
from app.notifications.models import NotificationType
from app.sales import service
from app.sales.models import Bid, BidStatus, Sale, SaleStatus, SaleType
from app.transfer_window import service as window_service
from app.ws.manager import manager as ws_manager
from app.sales.schemas import (
    BidCreateRequest,
    BidResponse,
    DealStubResponse,
    OrderBookResponse,
    SaleCreateRequest,
    SaleResponse,
)

router = APIRouter(tags=["sales"])


def _enrich_sale_response(sale: Sale) -> SaleResponse:
    """Build SaleResponse, populating computed auction fields."""
    from app.sales.service import get_best_bid_amount, get_minimum_next_bid, is_reserve_met

    active_bids = [b for b in (sale.bids or []) if b.status == BidStatus.ACTIVE]
    best = get_best_bid_amount(sale.bids or [])
    min_next = get_minimum_next_bid(sale) if sale.bids is not None else None
    reserve_ok = is_reserve_met(sale) if sale.bids is not None else False

    return SaleResponse(
        id=sale.id,
        player_id=sale.player_id,
        seller_club_id=sale.seller_club_id,
        sale_type=sale.sale_type,
        asking_price=sale.asking_price,
        reserve_price=sale.reserve_price,
        min_increment=sale.min_increment,
        deadline=sale.deadline,
        notes=sale.notes,
        status=sale.status,
        created_at=sale.created_at,
        updated_at=sale.updated_at,
        player=sale.player,
        seller_club=sale.seller_club,
        bid_count=len(active_bids),
        best_bid=best,
        minimum_next_bid=min_next,
        reserve_met=reserve_ok,
    )


# ── List + detail ─────────────────────────────────────────────────────────────


@router.get("/sales", response_model=Paginated[SaleResponse])
async def list_sales(
    status: SaleStatus | None = None,
    sale_type: SaleType | None = None,
    seller_club_id: uuid.UUID | None = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    _current_user: User | None = Depends(get_optional_user),
):
    sales, total = await service.list_sales(
        db,
        status=status,
        sale_type=sale_type,
        seller_club_id=seller_club_id,
        page=page,
        page_size=page_size,
    )
    return Paginated(
        items=[_enrich_sale_response(s) for s in sales],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/sales/{sale_id}", response_model=SaleResponse)
async def get_sale(
    sale_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _current_user: User | None = Depends(get_optional_user),
):
    sale = await service.get_sale_by_id(db, sale_id)
    if sale is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sale not found")
    return _enrich_sale_response(sale)


@router.get("/sales/{sale_id}/order-book", response_model=OrderBookResponse)
async def get_sale_order_book(
    sale_id: uuid.UUID,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
) -> OrderBookResponse:
    """Order book for a sale. Seller sees full info; buyer sees anonymised tiers (requires own bid/offer)."""
    sale = await service.get_sale_by_id(db, sale_id)
    if sale is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sale not found")

    my_club_id: uuid.UUID | None = None
    if current_user is not None:
        club, _ = await clubs_service.get_club_and_role_for_user(db, current_user.id)
        if club is not None:
            my_club_id = club.id

    return await service.get_order_book(db, sale, my_club_id)


# ── Create ────────────────────────────────────────────────────────────────────


@router.post("/sales", response_model=SaleResponse, status_code=status.HTTP_201_CREATED)
async def create_sale(
    body: SaleCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_seller_user),
    _write: User = Depends(require_club_write_access),
):
    club = await clubs_service.get_club_for_user(db, current_user.id)
    if club is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No club profile found")

    if not await window_service.is_transfer_allowed(db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Transfer window is closed. Sales cannot be created outside of a transfer window.",
        )

    # Guard: cannot list a player for sale while a deal is already in progress for them
    from app.deals import service as deals_service
    active_deal = await deals_service.get_active_deal_for_player(db, body.player_id)
    if active_deal and active_deal.status == "IN_PROGRESS":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This player already has a transfer deal in progress and cannot be listed for sale.",
        )

    try:
        sale = await service.create_sale(
            db,
            player_id=body.player_id,
            seller_club_id=club.id,
            sale_type=body.sale_type,
            asking_price=body.asking_price,
            reserve_price=body.reserve_price,
            min_increment=body.min_increment,
            deadline=body.deadline,
            notes=body.notes,
        )
        await db.commit()
        await db.refresh(sale)
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    sale = await service.get_sale_by_id(db, sale.id)
    return _enrich_sale_response(sale)


# ── Withdraw ──────────────────────────────────────────────────────────────────


@router.post("/sales/{sale_id}/withdraw", response_model=SaleResponse)
async def withdraw_sale(
    sale_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _write: User = Depends(require_club_write_access),
):
    club = await clubs_service.get_club_for_user(db, current_user.id)
    if club is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No club profile")

    sale = await service.get_sale_by_id(db, sale_id)
    if sale is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sale not found")
    if sale.seller_club_id != club.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your sale")

    try:
        await service.withdraw_sale(db, sale, actor_club_id=club.id)
        await db.commit()
        await db.refresh(sale)
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    sale = await service.get_sale_by_id(db, sale.id)
    await ws_manager.send_to_user(
        current_user.id,
        {"type": "SALE_UPDATED", "id": str(sale_id)},
    )
    return _enrich_sale_response(sale)


# ── Bid ───────────────────────────────────────────────────────────────────────


@router.post(
    "/sales/{sale_id}/bids", response_model=BidResponse, status_code=status.HTTP_201_CREATED
)
async def place_bid(
    sale_id: uuid.UUID,
    body: BidCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_buyer_user),
    _write: User = Depends(require_club_write_access),
):
    club = await clubs_service.get_club_for_user(db, current_user.id)
    if club is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No club profile")

    # Capture current best bidder before placing (for OUTBID detection)
    from sqlalchemy import select as sa_select
    prev_best_result = await db.execute(
        sa_select(Bid)
        .where(Bid.sale_id == sale_id, Bid.status == BidStatus.ACTIVE, Bid.buyer_club_id != club.id)
        .order_by(Bid.amount.desc())
        .limit(1)
    )
    prev_best_bid = prev_best_result.scalar_one_or_none()

    try:
        bid = await service.place_bid(
            db,
            sale_id=sale_id,
            buyer_club_id=club.id,
            amount=body.amount,
            wage_offer_weekly=body.wage_offer_weekly,
            notes=body.notes,
        )

        # Notify seller of new/upgraded bid
        _sale = await service.get_sale_by_id(db, sale_id)
        if _sale:
            seller_club = await clubs_service.get_club_by_id(db, uuid.UUID(str(_sale.seller_club_id)))
            if seller_club:
                player_name = _sale.player.name if _sale.player else "a player"
                await notif_service.create_notification(
                    db,
                    recipient_user_id=seller_club.user_id,
                    type=NotificationType.AUCTION_BID_RECEIVED,
                    message=f"New bid received on {player_name}",
                    link=f"/sales/{sale_id}",
                    related_player_id=_sale.player_id,
                )
            # OUTBID: notify the previously-best competing bidder if new bid beats them
            if prev_best_bid and bid.amount > prev_best_bid.amount:
                outbid_club = await clubs_service.get_club_by_id(db, uuid.UUID(str(prev_best_bid.buyer_club_id)))
                if outbid_club:
                    player_name = _sale.player.name if _sale.player else "a player"
                    await notif_service.create_notification(
                        db,
                        recipient_user_id=outbid_club.user_id,
                        type=NotificationType.OUTBID,
                        message=f"You have been outbid on {player_name}",
                        link=f"/sales/{sale_id}",
                        related_player_id=_sale.player_id,
                    )

        await db.commit()
        await db.refresh(bid)
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    # WS push to seller
    _sale_ws = await service.get_sale_by_id(db, sale_id)
    if _sale_ws:
        seller_club = await clubs_service.get_club_by_id(db, uuid.UUID(str(_sale_ws.seller_club_id)))
        if seller_club:
            await ws_manager.send_to_user(
                seller_club.user_id,
                {"type": "BID_PLACED", "sale_id": str(sale_id)},
            )

    return BidResponse.model_validate(bid)


@router.get("/sales/{sale_id}/bids", response_model=list[BidResponse])
async def list_bids(
    sale_id: uuid.UUID,
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return bids for a sale.
    - Seller: sees all bids (active + history when include_inactive=True)
    - Buyer: sees only their own bids
    """
    club = await clubs_service.get_club_for_user(db, current_user.id)
    if club is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No club profile")

    sale = await service.get_sale_by_id(db, sale_id)
    if sale is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sale not found")

    is_seller = sale.seller_club_id == club.id

    if include_inactive and is_seller:
        bids = list(sale.bids)
    else:
        bids = [b for b in sale.bids if b.status == BidStatus.ACTIVE]

    if not is_seller:
        bids = [b for b in bids if b.buyer_club_id == club.id]

    bids.sort(key=lambda b: b.created_at, reverse=True)
    return [BidResponse.model_validate(b) for b in bids]


# ── Accept bid ────────────────────────────────────────────────────────────────


@router.post("/sales/{sale_id}/bids/{bid_id}/accept", response_model=DealStubResponse)
async def accept_bid(
    sale_id: uuid.UUID,
    bid_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_seller_user),
    _write: User = Depends(require_club_write_access),
):
    club = await clubs_service.get_club_for_user(db, current_user.id)
    if club is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No club profile")

    try:
        deal = await service.accept_bid(
            db,
            sale_id=sale_id,
            bid_id=bid_id,
            actor_club_id=club.id,
        )
        # Notify winning buyer
        buyer_club_notif = await clubs_service.get_club_by_id(db, uuid.UUID(str(deal.buyer_club_id)))
        if buyer_club_notif:
            _sale_notif = await service.get_sale_by_id(db, sale_id)
            player_name = _sale_notif.player.name if _sale_notif and _sale_notif.player else "a player"
            await notif_service.create_notification(
                db,
                recipient_user_id=buyer_club_notif.user_id,
                type=NotificationType.AUCTION_BID_ACCEPTED,
                message=f"Your bid on {player_name} has been accepted",
                link=f"/deals/{deal.id}",
                related_player_id=deal.player_id,
            )
        await db.commit()
        await db.refresh(deal)
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    # Notify buyer + seller that sale is closed and a deal was created
    buyer_club = await clubs_service.get_club_by_id(db, deal.buyer_club_id)
    user_ids = [uid for uid in [
        club.user_id,
        buyer_club.user_id if buyer_club else None,
    ] if uid is not None]
    await ws_manager.broadcast_to_users(
        list(set(user_ids)),
        {"type": "SALE_UPDATED", "id": str(sale_id)},
    )
    await ws_manager.broadcast_to_users(
        list(set(user_ids)),
        {"type": "DEAL_UPDATED", "id": str(deal.id)},
    )

    return DealStubResponse.model_validate(deal)
