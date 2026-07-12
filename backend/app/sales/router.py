"""M3 — Sales + Bidding endpoints."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.approvals import service as approvals_service
from app.approvals.models import ApprovalActionType
from app.auth.models import User
from app.clubs import service as clubs_service
from app.common.schemas import Paginated
from app.database import get_db
from app.clubs.capabilities import Capability, require_club_capability
from app.deps import get_buyer_user, get_current_user, get_optional_user, get_seller_user
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

# TRA-151: sales/bids are market actions — MANAGER and above; SCOUT/READONLY get 403.
_market_write = require_club_capability(Capability.MARKET_WRITE)


async def _resolve_viewer(
    db: AsyncSession, current_user: User | None
) -> tuple[uuid.UUID | None, bool]:
    """Resolve (viewer_club_id, is_staff) for TRA-139 sale response scoping."""
    if current_user is None:
        return None, False
    if current_user.is_superuser:
        return None, True
    club = await clubs_service.get_club_for_user(db, current_user.id)
    return (club.id if club else None), False


def _enrich_sale_response(
    sale: Sale, *, viewer_club_id: uuid.UUID | None = None, is_staff: bool = False
) -> SaleResponse:
    """Build SaleResponse, populating computed auction fields.

    TRA-139: reserve_price/best_bid/bid_count are only visible to the seller or
    staff — everyone else gets the anonymised listing (asking price, deadline).
    minimum_next_bid stays visible to all, since a prospective bidder needs it
    to place a valid bid at all.
    """
    from app.sales.service import get_best_bid_amount, get_minimum_next_bid, is_reserve_met

    from app.sales.service import _live_bids
    live_bids = _live_bids(sale.bids or [])
    best = get_best_bid_amount(sale.bids or [])
    min_next = get_minimum_next_bid(sale) if sale.bids is not None else None
    reserve_ok = is_reserve_met(sale) if sale.bids is not None else False
    is_seller_or_staff = is_staff or (
        viewer_club_id is not None and viewer_club_id == sale.seller_club_id
    )

    return SaleResponse(
        id=sale.id,
        player_id=sale.player_id,
        seller_club_id=sale.seller_club_id,
        sale_type=sale.sale_type,
        asking_price=sale.asking_price,
        reserve_price=sale.reserve_price if is_seller_or_staff else None,
        min_increment=sale.min_increment,
        deadline=sale.deadline,
        notes=sale.notes,
        status=sale.status,
        created_at=sale.created_at,
        updated_at=sale.updated_at,
        player=sale.player,
        seller_club=sale.seller_club,
        bid_count=len(live_bids) if is_seller_or_staff else None,
        best_bid=best if is_seller_or_staff else None,
        minimum_next_bid=min_next,
        reserve_met=reserve_ok,
    )


# ── List + detail ─────────────────────────────────────────────────────────────


@router.get("/sales", response_model=Paginated[SaleResponse])
async def list_sales(
    status: SaleStatus | None = None,
    sale_type: SaleType | None = None,
    seller_club_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = 1,
    page_size: int = 30,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    viewer_club_id, is_staff = await _resolve_viewer(db, current_user)
    sales, total = await service.list_sales(
        db,
        status=status,
        sale_type=sale_type,
        seller_club_id=seller_club_id,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
    return Paginated(
        items=[
            _enrich_sale_response(s, viewer_club_id=viewer_club_id, is_staff=is_staff)
            for s in sales
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/sales/{sale_id}", response_model=SaleResponse)
async def get_sale(
    sale_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    sale = await service.get_sale_by_id(db, sale_id)
    if sale is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sale not found")
    viewer_club_id, is_staff = await _resolve_viewer(db, current_user)
    resp = _enrich_sale_response(sale, viewer_club_id=viewer_club_id, is_staff=is_staff)

    # TRA-91: fair-value signal embed. Null for player-account and anonymous
    # viewers (D6 — the /valuation endpoints require the same). Divergence only
    # vs asking_price on FIXED_PRICE; never vs reserve/bids on auctions (D7).
    from app.auth.models import UserType
    from app.valuation import service as valuation_service

    if current_user is not None and current_user.user_type != UserType.PLAYER:
        valuation_row = await valuation_service.get_latest_valuation(db, sale.player_id)
        if valuation_row is not None:
            reference = (
                sale.asking_price if sale.sale_type == SaleType.FIXED_PRICE else None
            )
            resp.fair_value_signal = valuation_service.build_valuation_response(
                valuation_row, reference_price=reference
            )
    return resp


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
    _write: User = Depends(_market_write),
):
    club = await clubs_service.get_club_for_user(db, current_user.id)
    if club is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No club profile found")

    # TRA-138: a club can only list a player who is actually registered to them
    from app.players import service as players_service
    player = await players_service.get_player_by_id(db, body.player_id)
    owning_club_id = await players_service.get_owning_club_id(db, player) if player else None
    if player is None or owning_club_id != club.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Player is not registered to your club",
        )

    if not current_user.is_superuser and not await window_service.is_transfer_allowed(db, association=club.country):
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
    return _enrich_sale_response(sale, viewer_club_id=club.id, is_staff=current_user.is_superuser)


# ── Withdraw ──────────────────────────────────────────────────────────────────


@router.post("/sales/{sale_id}/withdraw", response_model=SaleResponse)
async def withdraw_sale(
    sale_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _write: User = Depends(_market_write),
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
    _write: User = Depends(_market_write),
):
    club = await clubs_service.get_club_for_user(db, current_user.id)
    if club is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No club profile")

    if not current_user.is_superuser and not await window_service.is_transfer_allowed(db, association=club.country):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Transfer window is closed. Bids cannot be placed outside of a transfer window.",
        )

    # Phase 5 (D7): a MANAGER's bid at/above the club threshold is captured as
    # a pending approval — nothing reserved, nothing executed.
    _sale_for_summary = await service.get_sale_by_id(db, sale_id)
    _player_name = (
        _sale_for_summary.player.name
        if _sale_for_summary and _sale_for_summary.player else "a player"
    )
    approval = await approvals_service.maybe_capture(
        db,
        current_user=current_user,
        club=club,
        action_type=ApprovalActionType.PLACE_BID,
        amount=body.amount,
        payload={
            "sale_id": str(sale_id),
            "amount": str(body.amount),
            "wage_offer_weekly": str(body.wage_offer_weekly) if body.wage_offer_weekly else None,
            "notes": body.notes,
        },
        summary=f"Bid £{body.amount:,.0f} on {_player_name}",
    )
    if approval is not None:
        await db.commit()
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={"status": "PENDING_APPROVAL", "approval_id": str(approval.id)},
        )

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

        # Notify seller of new/upgraded bid — role-routed per club (TRA-152)
        _sale = await service.get_sale_by_id(db, sale_id)
        if _sale:
            player_name = _sale.player.name if _sale.player else "a player"
            await notif_service.notify_club(
                db,
                uuid.UUID(str(_sale.seller_club_id)),
                type=NotificationType.AUCTION_BID_RECEIVED,
                message=f"New bid received on {player_name}",
                link=f"/sales/{sale_id}",
                related_player_id=_sale.player_id,
            )
            # OUTBID: notify the previously-best competing bidder if new bid beats them
            if prev_best_bid and bid.amount > prev_best_bid.amount:
                await notif_service.notify_club(
                    db,
                    uuid.UUID(str(prev_best_bid.buyer_club_id)),
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

    # WS push to every member of the selling club
    _sale_ws = await service.get_sale_by_id(db, sale_id)
    if _sale_ws:
        member_ids = await notif_service.club_member_user_ids(
            db, uuid.UUID(str(_sale_ws.seller_club_id))
        )
        await ws_manager.broadcast_to_users(
            member_ids,
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


# ── Withdraw bid ─────────────────────────────────────────────────────────────


@router.delete("/sales/{sale_id}/bids/{bid_id}", status_code=status.HTTP_204_NO_CONTENT)
async def withdraw_bid(
    sale_id: uuid.UUID,
    bid_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_buyer_user),
    _write: User = Depends(_market_write),
):
    """Buyer withdraws their own active bid, releasing their budget reservation."""
    club = await clubs_service.get_club_for_user(db, current_user.id)
    if club is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No club profile")

    try:
        await service.withdraw_bid(
            db, sale_id=sale_id, bid_id=bid_id, buyer_club_id=club.id
        )
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ── Accept bid ────────────────────────────────────────────────────────────────


@router.post("/sales/{sale_id}/bids/{bid_id}/accept", response_model=DealStubResponse)
async def accept_bid(
    sale_id: uuid.UUID,
    bid_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_seller_user),
    _write: User = Depends(_market_write),
):
    club = await clubs_service.get_club_for_user(db, current_user.id)
    if club is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No club profile")

    if not current_user.is_superuser and not await window_service.is_transfer_allowed(db, association=club.country):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Transfer window is closed. Bids cannot be accepted outside of a transfer window.",
        )

    # Phase 5 (D7): a MANAGER accepting a bid at/above the club threshold is
    # captured as a pending approval instead of executing.
    from sqlalchemy import select as _sa_select
    _bid_row = await db.execute(_sa_select(Bid).where(Bid.id == bid_id, Bid.sale_id == sale_id))
    _bid = _bid_row.scalar_one_or_none()
    if _bid is not None:
        _sale_row = await service.get_sale_by_id(db, sale_id)
        _pname = _sale_row.player.name if _sale_row and _sale_row.player else "a player"
        approval = await approvals_service.maybe_capture(
            db,
            current_user=current_user,
            club=club,
            action_type=ApprovalActionType.ACCEPT_BID,
            amount=_bid.amount,
            payload={"sale_id": str(sale_id), "bid_id": str(bid_id)},
            summary=f"Accept £{_bid.amount:,.0f} bid on {_pname}",
        )
        if approval is not None:
            await db.commit()
            return JSONResponse(
                status_code=status.HTTP_202_ACCEPTED,
                content={"status": "PENDING_APPROVAL", "approval_id": str(approval.id)},
            )

    try:
        deal = await service.accept_bid(
            db,
            sale_id=sale_id,
            bid_id=bid_id,
            actor_club_id=club.id,
        )
        # Notify winning buyer — role-routed per club (TRA-152)
        _sale_notif = await service.get_sale_by_id(db, sale_id)
        player_name = _sale_notif.player.name if _sale_notif and _sale_notif.player else "a player"
        await notif_service.notify_club(
            db,
            uuid.UUID(str(deal.buyer_club_id)),
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
    user_ids = await notif_service.club_member_user_ids(db, club.id)
    user_ids += await notif_service.club_member_user_ids(db, uuid.UUID(str(deal.buyer_club_id)))
    await ws_manager.broadcast_to_users(
        list(set(user_ids)),
        {"type": "SALE_UPDATED", "id": str(sale_id)},
    )
    await ws_manager.broadcast_to_users(
        list(set(user_ids)),
        {"type": "DEAL_UPDATED", "id": str(deal.id)},
    )

    return DealStubResponse.model_validate(deal)
