"""M7 — Admin endpoints (superuser only)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin import service as admin_service
from app.admin.schemas import (
    ActivityItem,
    AdminClubDetailResponse,
    AdminClubFinanceResponse,
    AdminClubResponse,
    AdminClubUpdateRequest,
    AdminCreateClubRequest,
    AdminCreateUserRequest,
    AdminDealResponse,
    AdminFinancesUpdateRequest,
    AdminPlayerUpdateRequest,
    AdminResetPasswordRequest,
    AdminStatsResponse,
    AdminUserResponse,
    AdminUserUpdateRequest,
    BroadcastRequest,
    BroadcastResponse,
    ClubStaffResponse,
    CreateStaffRequest,
    HealthReport,
    ImportSquadRequest,
    ImportSquadResult,
    ImportWorldTeamRequest,
    PaginatedClubs,
    PaginatedUsers,
    UpdateStaffRoleRequest,
)
from app.auth.models import User
from app.database import get_db
from app.deps import get_current_superuser
from app.offers.schemas import OfferResponse
from app.players.schemas import PlayerResponse
from app.sales.schemas import SaleResponse

router = APIRouter(prefix="/admin", tags=["admin"])


# ── Users ─────────────────────────────────────────────────────────────────────


@router.get("/users", response_model=PaginatedUsers)
async def list_users(
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> PaginatedUsers:
    users, total = await admin_service.list_users(db, search=search, page=page, page_size=page_size)
    return PaginatedUsers(
        items=[AdminUserResponse.model_validate(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/users/{user_id}", response_model=AdminUserResponse)
async def get_user(
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> AdminUserResponse:
    user = await admin_service.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return AdminUserResponse.model_validate(user)


@router.post("/users", response_model=AdminUserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: AdminCreateUserRequest,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> AdminUserResponse:
    try:
        user = await admin_service.create_user(db, body.email, body.password)
        await db.commit()
        await db.refresh(user)
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return AdminUserResponse.model_validate(user)


@router.post("/users/{user_id}/reset-password", response_model=AdminUserResponse)
async def reset_password(
    user_id: uuid.UUID,
    body: AdminResetPasswordRequest,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> AdminUserResponse:
    user = await admin_service.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    await admin_service.reset_password(db, user, body.new_password)
    await db.commit()
    await db.refresh(user)
    return AdminUserResponse.model_validate(user)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> None:
    from sqlalchemy.exc import IntegrityError

    if user_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete your own account")
    user = await admin_service.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    try:
        await admin_service.delete_user(db, user)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete: user has associated data (deals, sales, etc.). Remove those first.",
        )


@router.patch("/users/{user_id}", response_model=AdminUserResponse)
async def update_user(
    user_id: uuid.UUID,
    body: AdminUserUpdateRequest,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> AdminUserResponse:
    user = await admin_service.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    await admin_service.update_user(
        db, user, is_active=body.is_active, is_superuser=body.is_superuser
    )
    await db.commit()
    await db.refresh(user)
    return AdminUserResponse.model_validate(user)


# ── Clubs ─────────────────────────────────────────────────────────────────────


@router.post("/clubs", response_model=AdminClubDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_club(
    body: AdminCreateClubRequest,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> AdminClubDetailResponse:
    try:
        club = await admin_service.create_club(
            db,
            user_id=body.user_id,
            name=body.name,
            role=body.role,
            country=body.country,
            league_name=body.league_name,
            transfer_budget=body.transfer_budget,
            wage_budget=body.wage_budget,
        )
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    club = await admin_service.get_club_by_id(db, club.id)
    return AdminClubDetailResponse.model_validate(club)


@router.get("/clubs", response_model=PaginatedClubs)
async def list_clubs(
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> PaginatedClubs:
    clubs, total = await admin_service.list_clubs(db, search=search, page=page, page_size=page_size)
    return PaginatedClubs(
        items=[AdminClubResponse.model_validate(c) for c in clubs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/clubs/{club_id}", response_model=AdminClubDetailResponse)
async def get_club(
    club_id: uuid.UUID,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> AdminClubDetailResponse:
    club = await admin_service.get_club_by_id(db, club_id)
    if club is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Club not found")
    return AdminClubDetailResponse.model_validate(club)


@router.delete("/clubs/{club_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_club(
    club_id: uuid.UUID,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> None:
    from sqlalchemy.exc import IntegrityError

    club = await admin_service.get_club_by_id(db, club_id)
    if club is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Club not found")
    try:
        await admin_service.delete_club(db, club)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete: club has active sales, deals, or contracted players. Remove those first.",
        )


@router.patch("/clubs/{club_id}", response_model=AdminClubResponse)
async def update_club(
    club_id: uuid.UUID,
    body: AdminClubUpdateRequest,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> AdminClubResponse:
    club = await admin_service.get_club_by_id(db, club_id)
    if club is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Club not found")
    await admin_service.update_club(db, club, name=body.name, role=body.role, country=body.country)
    await db.commit()
    await db.refresh(club)
    return AdminClubResponse.model_validate(club)


@router.put("/clubs/{club_id}/finances", response_model=AdminClubFinanceResponse)
async def update_club_finances(
    club_id: uuid.UUID,
    body: AdminFinancesUpdateRequest,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> AdminClubFinanceResponse:
    club = await admin_service.get_club_by_id(db, club_id)
    if club is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Club not found")
    finance = await admin_service.update_club_finances(
        db,
        club,
        transfer_budget_total=body.transfer_budget_total,
        wage_budget_total_weekly=body.wage_budget_total_weekly,
    )
    await db.commit()
    await db.refresh(finance)
    return AdminClubFinanceResponse.model_validate(finance)


# ── Players (all, no visibility filter) ───────────────────────────────────────


@router.get("/players")
async def list_all_players(
    search: str | None = Query(None),
    position: str | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> dict:
    players, total = await admin_service.admin_list_players(
        db, search=search, position=position, status=status, page=page, page_size=page_size
    )
    return {
        "items": [PlayerResponse.model_validate(p) for p in players],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/players/{player_id}", response_model=PlayerResponse)
async def get_player(
    player_id: uuid.UUID,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> PlayerResponse:
    player = await admin_service.admin_get_player(db, player_id)
    if player is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found")
    return PlayerResponse.model_validate(player)


@router.patch("/players/{player_id}", response_model=PlayerResponse)
async def update_player(
    player_id: uuid.UUID,
    body: AdminPlayerUpdateRequest,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> PlayerResponse:
    player = await admin_service.admin_get_player(db, player_id)
    if player is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found")
    try:
        await admin_service.admin_update_player(
            db, player,
            name=body.name,
            age=body.age,
            nationality=body.nationality,
            position=body.position,
            visibility=body.visibility,
            status=body.status,
            open_to_offers=body.open_to_offers,
            photo_url=body.photo_url,
            current_club_id=body.current_club_id,
            clear_club=body.clear_club,
        )
        await db.commit()
    except (ValueError, Exception) as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    player = await admin_service.admin_get_player(db, player_id)
    return PlayerResponse.model_validate(player)


# ── Sales (all statuses) ──────────────────────────────────────────────────────


@router.get("/sales")
async def list_all_sales(
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> dict:
    sales, total = await admin_service.admin_list_sales(
        db, status=status, page=page, page_size=page_size
    )
    return {
        "items": [SaleResponse.model_validate(s) for s in sales],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/sales/{sale_id}/cancel", response_model=SaleResponse)
async def cancel_sale(
    sale_id: uuid.UUID,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> SaleResponse:
    from app.sales.service import get_sale_by_id
    from app.sales.router import _enrich_sale_response

    sale = await get_sale_by_id(db, sale_id)
    if sale is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sale not found")
    try:
        await admin_service.admin_cancel_sale(db, sale)
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    sale = await get_sale_by_id(db, sale_id)
    return _enrich_sale_response(sale)


# ── Deals (all) ───────────────────────────────────────────────────────────────


@router.get("/deals")
async def list_all_deals(
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> dict:
    deals, total = await admin_service.admin_list_deals(
        db, status=status, page=page, page_size=page_size
    )
    return {
        "items": [AdminDealResponse.model_validate(d) for d in deals],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ── World import ──────────────────────────────────────────────────────────────


@router.post(
    "/world/teams/{team_id}/import-club",
    response_model=AdminClubDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
async def import_world_team_as_club(
    team_id: uuid.UUID,
    body: ImportWorldTeamRequest,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> AdminClubDetailResponse:
    try:
        club = await admin_service.import_world_team_as_club(
            db,
            world_team_id=team_id,
            user_id=body.user_id,
            role=body.role,
            transfer_budget=body.transfer_budget,
            wage_budget=body.wage_budget,
        )
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    club = await admin_service.get_club_by_id(db, club.id)
    return AdminClubDetailResponse.model_validate(club)


@router.post("/world/teams/{team_id}/import-squad", response_model=ImportSquadResult)
async def import_world_team_squad(
    team_id: uuid.UUID,
    body: ImportSquadRequest,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> ImportSquadResult:
    try:
        result = await admin_service.import_world_team_squad(
            db, world_team_id=team_id, club_id=body.club_id
        )
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return ImportSquadResult(**result)


# ── Offers (all) ──────────────────────────────────────────────────────────────


@router.get("/offers")
async def list_all_offers(
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> dict:
    offers, total = await admin_service.admin_list_offers(
        db, status=status, page=page, page_size=page_size
    )
    return {
        "items": [OfferResponse.model_validate(o) for o in offers],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/offers/{offer_id}/force-withdraw", response_model=OfferResponse)
async def force_withdraw_offer(
    offer_id: uuid.UUID,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> OfferResponse:
    from app.offers.service import get_offer_by_id

    offer = await get_offer_by_id(db, offer_id)
    if offer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found")
    try:
        await admin_service.admin_force_withdraw_offer(db, offer)
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    offer = await get_offer_by_id(db, offer_id)
    return OfferResponse.model_validate(offer)


# ── Club staff ────────────────────────────────────────────────────────────────


@router.get("/clubs/{club_id}/staff", response_model=list[ClubStaffResponse])
async def list_club_staff(
    club_id: uuid.UUID,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> list[ClubStaffResponse]:
    staff = await admin_service.list_club_staff_with_users(db, club_id)
    return [ClubStaffResponse.model_validate(s) for s in staff]


@router.post(
    "/clubs/{club_id}/staff",
    response_model=ClubStaffResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_club_staff(
    club_id: uuid.UUID,
    body: CreateStaffRequest,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> ClubStaffResponse:
    # Verify club exists
    club = await admin_service.get_club_by_id(db, club_id)
    if club is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Club not found")

    try:
        staff, _user = await admin_service.create_staff_user(
            db,
            club_id=club_id,
            email=body.email,
            password=body.password,
            role=body.role,
            created_by_user_id=current_user.id,
        )
        await db.commit()
        await db.refresh(staff)
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    staff = await admin_service.get_staff_by_id(db, staff.id)
    return ClubStaffResponse.model_validate(staff)


@router.patch("/clubs/{club_id}/staff/{staff_id}", response_model=ClubStaffResponse)
async def update_club_staff(
    club_id: uuid.UUID,
    staff_id: uuid.UUID,
    body: UpdateStaffRoleRequest,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> ClubStaffResponse:
    staff = await admin_service.get_staff_by_id(db, staff_id)
    if staff is None or staff.club_id != uuid.UUID(str(club_id)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff not found")

    try:
        staff = await admin_service.update_staff_role(db, staff, body.role)
        await db.commit()
        await db.refresh(staff)
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    staff = await admin_service.get_staff_by_id(db, staff.id)
    return ClubStaffResponse.model_validate(staff)


@router.delete("/clubs/{club_id}/staff/{staff_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_club_staff(
    club_id: uuid.UUID,
    staff_id: uuid.UUID,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> None:
    staff = await admin_service.get_staff_by_id(db, staff_id)
    if staff is None or staff.club_id != uuid.UUID(str(club_id)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff not found")

    await admin_service.delete_staff(db, staff)
    await db.commit()


# ── System stats ──────────────────────────────────────────────────────────────


@router.get("/stats", response_model=AdminStatsResponse)
async def system_stats(
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> AdminStatsResponse:
    stats = await admin_service.get_system_stats(db)
    return AdminStatsResponse(**stats)


# ── Activity feed ──────────────────────────────────────────────────────────────


@router.get("/activity", response_model=list[ActivityItem])
async def activity_feed(
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> list[ActivityItem]:
    items = await admin_service.get_activity_feed(db, limit=limit)
    return [ActivityItem(**item) for item in items]


# ── Broadcast notification ─────────────────────────────────────────────────────


@router.post("/notifications/broadcast", response_model=BroadcastResponse)
async def broadcast_notification(
    body: BroadcastRequest,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> BroadcastResponse:
    count = await admin_service.broadcast_notification(db, message=body.message, link=body.link)
    await db.commit()
    return BroadcastResponse(recipients=count)


# ── Health check ───────────────────────────────────────────────────────────────


@router.get("/health", response_model=HealthReport)
async def health_check(
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> HealthReport:
    report = await admin_service.get_health_report(db)
    return HealthReport(**report)
