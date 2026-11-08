"""M3 — Sales (listings) endpoints. Auctions are retired (product ADR 0011)."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.clubs import service as clubs_service
from app.common.schemas import Paginated
from app.database import get_db
from app.clubs.capabilities import Capability, require_club_capability
from app.deps import get_current_user, get_optional_user, get_seller_user
from app.sales import service
from app.sales.models import ListingAvailability, Sale, SaleStatus, SaleType
from app.ws.manager import manager as ws_manager
from app.sales.schemas import OrderBookResponse, SaleCreateRequest, SaleResponse

router = APIRouter(tags=["sales"])

# TRA-151: listings are market actions — MANAGER and above; SCOUT/READONLY get 403.
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
    """Build SaleResponse. TRA-139: the reserve price is only visible to the
    seller or staff; everyone else gets the listing (asking price, deadline)."""
    is_seller_or_staff = is_staff or (
        viewer_club_id is not None and viewer_club_id == sale.seller_club_id
    )
    return SaleResponse(
        id=sale.id,
        player_id=sale.player_id,
        seller_club_id=sale.seller_club_id,
        sale_type=sale.sale_type,
        availability=sale.availability,
        asking_price=sale.asking_price,
        reserve_price=sale.reserve_price if is_seller_or_staff else None,
        deadline=sale.deadline,
        notes=sale.notes,
        status=sale.status,
        created_at=sale.created_at,
        updated_at=sale.updated_at,
        player=sale.player,
        seller_club=sale.seller_club,
        cancelled_by_staff=sale.staff_cancel_reason is not None,
        staff_cancel_reason=sale.staff_cancel_reason if is_seller_or_staff else None,
    )


# ── List + detail ─────────────────────────────────────────────────────────────


@router.get("/sales", response_model=Paginated[SaleResponse])
async def list_sales(
    status: SaleStatus | None = None,
    sale_type: SaleType | None = None,
    available_for: ListingAvailability | None = None,
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
        available_for=available_for,
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
    # viewers (D6 — the /valuation endpoints require the same). Divergence vs
    # asking_price on any listing type that publishes one, falling back to the
    # legacy Player.market_value when this specific listing didn't set one —
    # asking_price is optional at creation for every type (CreateSalePage never
    # requires it), so a FIXED_PRICE or OPEN_TO_OFFERS
    # sale with none set is a reachable state, not a hypothetical. Same fallback
    # order as the batch (`get_reference_prices`), so a player's row in the
    # market list and this same player's sale page can't disagree. Old
    # auctions (retired, ADR 0011) published no price to compare (D7).
    from app.auth.models import UserType
    from app.valuation import service as valuation_service

    if current_user is not None and current_user.user_type != UserType.PLAYER:
        valuation_row = await valuation_service.get_latest_valuation(db, sale.player_id)
        if valuation_row is not None:
            reference = None
            if sale.sale_type != SaleType.AUCTION:
                reference = (
                    sale.asking_price
                    if sale.asking_price is not None
                    else sale.player.market_value
                )
            resp.fair_value_signal = valuation_service.build_valuation_response(
                valuation_row, reference_price=reference
            )

    # A resolved listing should say what resolved it. Without this the seller sees
    # a CLOSED listing with an empty order book and no way to tell whether an
    # offer was accepted, it expired, or it was withdrawn.
    if sale.status != SaleStatus.OPEN:
        from app.deals import service as deals_service
        from app.players.schemas import ActiveDealStub

        deal = await deals_service.get_active_deal_for_player(db, sale.player_id)
        if deal is not None:
            resp.active_deal = ActiveDealStub.model_validate(deal)
    return resp


@router.get("/sales/{sale_id}/order-book", response_model=OrderBookResponse)
async def get_sale_order_book(
    sale_id: uuid.UUID,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
) -> OrderBookResponse:
    """Order book for a sale. Seller sees full info; buyer sees anonymised tiers (requires own offer)."""
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

    # Guard: cannot list a player for sale while a deal is already in progress for them
    from app.deals import service as deals_service
    active_deal = await deals_service.get_active_deal_for_player(db, body.player_id)
    if active_deal and active_deal.status == "IN_PROGRESS":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This player already has a transfer deal in progress and cannot be listed for sale.",
        )

    # A player has at most one live listing. Checked here for a readable error;
    # the partial unique index uq_sales_one_open_per_player is the actual
    # guarantee, because two concurrent requests can both pass this check.
    if await service.get_open_sale_for_player(db, body.player_id) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This player is already listed. Withdraw that listing before creating another.",
        )

    try:
        sale = await service.create_sale(
            db,
            player_id=body.player_id,
            seller_club_id=club.id,
            sale_type=body.sale_type,
            asking_price=body.asking_price,
            reserve_price=body.reserve_price,
            deadline=body.deadline,
            notes=body.notes,
            availability=body.availability,
        )
        if body.ai_assisted:
            from app.audit import service as audit_service

            await audit_service.emit(
                db, entity_type="SALE", entity_id=sale.id, action="AI_SUGGESTION_USED",
                actor_user_id=current_user.id, payload={"feature": "listing_assistant"},
                description="Guide price taken from the listing assistant",
            )
            from app.ai import tracking
            await tracking.record_used(db, "listing_assistant", current_user.id, ref=body.player_id)
        await db.commit()
        await db.refresh(sale)
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except IntegrityError:
        # The race the check above cannot see: a concurrent request listed him
        # between that check and this commit, and the unique index refused us.
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This player is already listed. Withdraw that listing before creating another.",
        )

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
