"""M7 — Admin endpoints (superuser only)."""

import asyncio
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin import audit as admin_audit
from app.admin import service as admin_service
from app.admin.schemas import (
    ActivityItem,
    AdminClubDetailResponse,
    AdminClubFinanceResponse,
    AdminClubResponse,
    AdminClubUpdateRequest,
    AdminCreateClubRequest,
    AdminDealResponse,
    AdminFinancesUpdateRequest,
    AdminPlayerUpdateRequest,
    AdminReasonRequest,
    StaffInvitationResult,
    ViewAsResponse,
    AdminResetLinkRequest,
    AdminResetLinkResponse,
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
from app.clubs import service as clubs_service
from app.clubs.schemas import (
    ClubInvitationCreateRequest,
    ClubInvitationResponse,
    PlayerAccountStatusResponse,
    PlayerInvitationCreateRequest,
    PlayerInvitationResponse,
)
from app.database import get_db
from app.deps import get_current_superuser
from app.offers.schemas import OfferResponse
from app.players.schemas import ContractResponse, PlayerResponse
from app.sales.schemas import SaleResponse

router = APIRouter(prefix="/admin", tags=["admin"])


# ── Users ─────────────────────────────────────────────────────────────────────


@router.get("/users", response_model=PaginatedUsers)
async def list_users(
    search: str | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> PaginatedUsers:
    users, total = await admin_service.list_users(
        db, search=search, date_from=date_from, date_to=date_to, page=page, page_size=page_size
    )
    described = await admin_service.describe_users(db, users)

    def _row(u):
        r = AdminUserResponse.model_validate(u)
        r.user_type = getattr(u.user_type, "value", u.user_type)
        for k, v in described.get(u.id, {}).items():
            setattr(r, k, v)
        return r

    return PaginatedUsers(
        items=[_row(u) for u in users],
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


@router.post("/users/{user_id}/reset-link", response_model=AdminResetLinkResponse)
async def create_reset_link(
    user_id: uuid.UUID,
    body: AdminResetLinkRequest,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> AdminResetLinkResponse:
    """A one-time link (24 hours) for the person to choose a new password.
    Staff never set or see the password. Emailed when email is set up, and
    returned so it can be shared by hand where it isn't."""
    from app.auth import service as auth_service
    from app.config import settings
    from app.notifications.email import send_password_reset_email

    user = await admin_service.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    raw, expires_at = await auth_service.create_password_reset(db, user, created_by_user_id=current_user.id)
    await admin_audit.record(
        db, current_user, "user.reset_link_created", entity_type="user", entity_id=user.id,
        description=f"Password reset link created for {user.email}", reason=body.reason,
    )
    await db.commit()
    url = f"{settings.frontend_base_url}/reset-password?token={raw}"
    emailed = bool(settings.smtp_host)
    if emailed:
        asyncio.create_task(send_password_reset_email(user.email, url))
    return AdminResetLinkResponse(url=url, expires_at=expires_at, emailed=emailed)


async def _other_active_superusers(db: AsyncSession, user_id: uuid.UUID) -> int:
    from sqlalchemy import func

    return (await db.execute(select(func.count()).select_from(User).where(
        User.is_superuser.is_(True), User.is_active.is_(True), User.id != user_id,
    ))).scalar_one()


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: uuid.UUID,
    body: AdminReasonRequest,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> None:
    from sqlalchemy.exc import IntegrityError

    if user_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete your own account")
    user = await admin_service.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.is_superuser and user.is_active and await _other_active_superusers(db, user.id) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete the last active TransferX staff account")
    try:
        # Written first, in the same transaction: the event outlives the user.
        await admin_audit.record(
            db, current_user, "user.deleted", entity_type="user", entity_id=user.id,
            description=f"Deleted user {user.email}", reason=body.reason,
            details={"email": user.email, "user_type": user.user_type, "was_superuser": user.is_superuser},
        )
        await admin_service.delete_user(db, user)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete: user has associated data (deals, sales, etc.). Deactivate them instead.",
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
    rights_change = body.is_superuser is not None and body.is_superuser != user.is_superuser
    deactivating = body.is_active is False and user.is_active
    if user.id == current_user.id and (deactivating or body.is_superuser is False):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="You can't deactivate yourself or remove your own staff rights")
    if user.is_superuser and user.is_active and (deactivating or body.is_superuser is False) \
            and await _other_active_superusers(db, user.id) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="TransferX needs at least one active staff account")
    reason = " ".join((body.reason or "").split())
    if (rights_change or deactivating) and len(reason) < 5:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="Give a reason of at least 5 characters")
    before = {"is_active": user.is_active, "is_superuser": user.is_superuser}
    await admin_service.update_user(
        db, user, is_active=body.is_active, is_superuser=body.is_superuser
    )
    changed = admin_audit.changes(before, {"is_active": user.is_active, "is_superuser": user.is_superuser})
    if changed:
        what = []
        if "is_superuser" in changed:
            what.append("granted TransferX staff rights" if user.is_superuser else "removed TransferX staff rights")
        if "is_active" in changed:
            what.append("reactivated" if user.is_active else "deactivated")
        await admin_audit.record(
            db, current_user, "user.updated", entity_type="user", entity_id=user.id,
            description=f"{user.email}: {', '.join(what)}", reason=reason or None, details={"changes": changed},
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
        await admin_audit.record(
            db, current_user, "club.created", entity_type="club", entity_id=club.id,
            description=f"Created club {body.name}",
            details={"transfer_budget": body.transfer_budget, "wage_budget": body.wage_budget},
        )
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    club = await admin_service.get_club_by_id(db, club.id)
    return AdminClubDetailResponse.model_validate(club)


# ── Club invitations — how a club joins TransferX ────────────────────────────


@router.post("/club-invitations", response_model=ClubInvitationResponse, status_code=status.HTTP_201_CREATED)
async def invite_club(
    body: ClubInvitationCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    """Invite a club's owner. The accept link is emailed, and returned once
    here so it can be shared by hand where email is not configured."""
    from app.config import settings
    from app.notifications.email import send_club_invitation_email

    try:
        inv, raw_token = await clubs_service.create_club_invitation(
            db, email=body.email, club_name=body.club_name, invited_by_user_id=current_user.id
        )
        await admin_audit.record(
            db, current_user, "club_invitation.created", entity_type="club_invitation", entity_id=inv.id,
            description=f"Invited {inv.email} to bring {inv.club_name} onto TransferX",
        )
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    accept_url = f"{settings.frontend_base_url}/join?token={raw_token}"
    asyncio.create_task(send_club_invitation_email(inv.email, inv.club_name, accept_url))
    resp = ClubInvitationResponse.model_validate(inv)
    resp.accept_url = accept_url
    return resp


@router.get("/club-invitations", response_model=list[ClubInvitationResponse])
async def list_club_invitations(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
):
    return [ClubInvitationResponse.model_validate(i) for i in await clubs_service.list_club_invitations(db)]


@router.post("/club-invitations/{invitation_id}/revoke", response_model=ClubInvitationResponse)
async def revoke_club_invitation(
    invitation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    try:
        inv = await clubs_service.revoke_club_invitation(db, invitation_id)
        await admin_audit.record(
            db, current_user, "club_invitation.revoked", entity_type="club_invitation", entity_id=inv.id,
            description=f"Revoked the invitation for {inv.email} ({inv.club_name})",
        )
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return ClubInvitationResponse.model_validate(inv)


@router.get("/clubs", response_model=PaginatedClubs)
async def list_clubs(
    search: str | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> PaginatedClubs:
    clubs, total = await admin_service.list_clubs(
        db, search=search, date_from=date_from, date_to=date_to, page=page, page_size=page_size
    )
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
    body: AdminReasonRequest,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> None:
    from sqlalchemy.exc import IntegrityError

    club = await admin_service.get_club_by_id(db, club_id)
    if club is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Club not found")
    try:
        await admin_audit.record(
            db, current_user, "club.deleted", entity_type="club", entity_id=club.id,
            description=f"Deleted club {club.name}", reason=body.reason, details={"name": club.name},
        )
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
    before = {"name": club.name, "role": club.role, "country": club.country}
    await admin_service.update_club(db, club, name=body.name, role=body.role, country=body.country)
    changed = admin_audit.changes(before, {"name": club.name, "role": club.role, "country": club.country})
    if changed:
        await admin_audit.record(
            db, current_user, "club.updated", entity_type="club", entity_id=club.id,
            description=f"Edited club {club.name}", details={"changes": changed},
        )
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
    try:
        finance, changed = await admin_service.update_club_finances(
            db,
            club,
            transfer_budget_total=body.transfer_budget_total,
            wage_budget_total_weekly=body.wage_budget_total_weekly,
        )
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if changed:
        await admin_audit.record(
            db, current_user, "club.finances_updated", entity_type="club", entity_id=club.id,
            description=f"Changed {club.name}'s budgets", reason=body.reason, details={"changes": changed},
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
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> dict:
    players, total = await admin_service.admin_list_players(
        db, search=search, position=position, status=status,
        date_from=date_from, date_to=date_to, page=page, page_size=page_size,
    )
    return {
        "items": [PlayerResponse.model_validate(p) for p in players],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


class AdminPlayerResponse(PlayerResponse):
    # Every contract, past and present: the admin page's Contracts card.
    contracts: list[ContractResponse] = []


@router.get("/players/{player_id}", response_model=AdminPlayerResponse)
async def get_player(
    player_id: uuid.UUID,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> AdminPlayerResponse:
    player = await admin_service.admin_get_player(db, player_id)
    if player is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found")
    return AdminPlayerResponse.model_validate(player)


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
    fields = body.model_dump(exclude_unset=True)
    before = {k: getattr(player, k, None) for k in fields if hasattr(player, k)}
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
        changed = admin_audit.changes(before, {k: getattr(player, k, None) for k in before})
        if changed or body.clear_club:
            await admin_audit.record(
                db, current_user, "player.updated", entity_type="player", entity_id=player.id,
                description=f"Edited player {player.name}",
                details={"changes": changed, **({"cleared_club": True} if body.clear_club else {})},
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
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> dict:
    sales, total = await admin_service.admin_list_sales(
        db, status=status, date_from=date_from, date_to=date_to, page=page, page_size=page_size
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
    body: AdminReasonRequest,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> SaleResponse:
    """Cancel an open sale as TransferX staff. Same effect as the seller
    withdrawing it: every bidder's reservation and every linked offer's
    held budget is released, and the seller and buyers are told why."""
    from app.sales.service import get_sale_by_id
    from app.sales.router import _enrich_sale_response

    sale = await get_sale_by_id(db, sale_id)
    if sale is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sale not found")
    try:
        await admin_service.admin_cancel_sale(db, sale, reason=body.reason)
        player = sale.player.name if sale.player else None
        await admin_audit.record(
            db, current_user, "sale.cancelled", entity_type="sale", entity_id=sale.id,
            description=f"Cancelled the sale of {player}" if player else "Cancelled a sale", reason=body.reason,
        )
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
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> dict:
    deals, total = await admin_service.admin_list_deals(
        db, status=status, date_from=date_from, date_to=date_to, page=page, page_size=page_size
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
        await admin_audit.record(
            db, current_user, "club.imported", entity_type="club", entity_id=club.id,
            description=f"Imported {club.name} from API-Football", details={"world_team_id": team_id},
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
        await admin_audit.record(
            db, current_user, "club.squad_imported", entity_type="club", entity_id=body.club_id,
            description="Imported a squad from API-Football", details={"world_team_id": team_id, "result": result},
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
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> dict:
    offers, total = await admin_service.admin_list_offers(
        db, status=status, date_from=date_from, date_to=date_to, page=page, page_size=page_size
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
    body: AdminReasonRequest,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> OfferResponse:
    """Withdraw an open offer as TransferX staff. Same effect as the buyer
    withdrawing it (the reserved fee and wage are released); both clubs are
    told why."""
    from app.offers.service import get_offer_by_id

    offer = await get_offer_by_id(db, offer_id)
    if offer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found")
    try:
        await admin_service.admin_force_withdraw_offer(db, offer, reason=body.reason)
        await admin_audit.record(
            db, current_user, "offer.withdrawn", entity_type="offer", entity_id=offer.id,
            description="Withdrew an offer", reason=body.reason,
        )
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
    response_model=StaffInvitationResult,
    status_code=status.HTTP_201_CREATED,
)
async def invite_club_staff(
    club_id: uuid.UUID,
    body: CreateStaffRequest,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> StaffInvitationResult:
    """Invite someone to a club's staff, the same invitation the club's own
    Team page sends. They choose their password from the link; staff never
    set one. Emailed when email is set up, and returned to share by hand."""
    from app.clubs.models import StaffRole
    from app.config import settings
    from app.notifications.email import send_staff_invitation_email

    club = await admin_service.get_club_by_id(db, club_id)
    if club is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Club not found")
    try:
        role = StaffRole(body.role)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown role: {body.role}")
    try:
        inv, raw = await clubs_service.create_staff_invitation(
            db, club_id=club.id, email=body.email, role=role, invited_by_user_id=current_user.id,
        )
        await admin_audit.record(
            db, current_user, "staff.invited", entity_type="club", entity_id=club.id,
            description=f"Invited {inv.email} to {club.name}'s staff as {role.value.replace('_', ' ').title()}",
        )
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    accept_url = f"{settings.frontend_base_url}/accept-invite?token={raw}"
    emailed = bool(settings.smtp_host)
    if emailed:
        asyncio.create_task(send_staff_invitation_email(inv.email, club.name, role.value, accept_url))
    return StaffInvitationResult(email=inv.email, role=role.value, accept_url=accept_url,
                                 expires_at=inv.expires_at, emailed=emailed)


@router.post("/clubs/{club_id}/view-as", response_model=ViewAsResponse)
async def view_as_club(
    club_id: uuid.UUID,
    body: AdminReasonRequest,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> ViewAsResponse:
    """See the app exactly as the club's owner does, for 30 minutes, without
    being able to change anything. For support ("why can't I…"). Needs a
    reason, and is audited: looking at a club's private data is itself an
    action worth a record."""
    from app.auth import service as auth_service

    club = await admin_service.get_club_by_id(db, club_id)
    if club is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Club not found")
    owner = await db.get(User, club.user_id)
    if owner is None or not owner.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This club's owner account is not active")
    token, expires_at = auth_service.create_view_as_token(owner.id, owner.email, staff_user_id=current_user.id)
    await admin_audit.record(
        db, current_user, "club.viewed_as", entity_type="club", entity_id=club.id,
        description=f"Viewed TransferX as {club.name} (read-only)", reason=body.reason,
        details={"expires_at": expires_at},
    )
    await db.commit()
    return ViewAsResponse(access_token=token, expires_at=expires_at, club_name=club.name)


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
        old_role = staff.role
        staff = await admin_service.update_staff_role(db, staff, body.role)
        await admin_audit.record(
            db, current_user, "staff.role_changed", entity_type="club", entity_id=club_id,
            description=f"Changed a staff member's role to {body.role}",
            details={"staff_id": staff.id, "user_id": staff.user_id, "changes": {"role": [old_role, staff.role]}},
        )
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

    await admin_audit.record(
        db, current_user, "staff.removed", entity_type="club", entity_id=club_id,
        description="Removed a staff member", details={"staff_id": staff.id, "user_id": staff.user_id, "role": staff.role},
    )
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
    await admin_audit.record(
        db, current_user, "broadcast.sent", entity_type="user", entity_id=current_user.id,
        description=f"Sent a broadcast to {count} users", details={"message": body.message, "link": body.link, "recipients": count},
    )
    await db.commit()
    return BroadcastResponse(recipients=count)


# ── Health check ───────────────────────────────────────────────────────────────


@router.get("/health", response_model=HealthReport)
async def health_check(
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> HealthReport:
    report = await admin_service.get_health_report(db)
    services, jobs = await admin_service.get_services_and_jobs(db)
    return HealthReport(**report, services=services, jobs=jobs)


# ── Player invitations for free agents (migration 0083) ──────────────────────
# A free agent has no club to invite him, so TransferX staff can (as can his
# agent, from the agent side).


@router.post("/player-invitations", response_model=PlayerInvitationResponse, status_code=status.HTTP_201_CREATED)
async def invite_free_agent(
    body: PlayerInvitationCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    from app.audit import service as audit_service

    try:
        inv, raw_token = await clubs_service.create_player_invitation(
            db, player_id=body.player_id, email=body.email, invited_by_user_id=current_user.id, by_staff=True,
        )
        await audit_service.emit(
            db, entity_type="PLAYER", entity_id=inv.player_id, action="PLAYER_INVITED",
            actor_user_id=current_user.id, payload={"email": inv.email, "by": "STAFF"},
            description="TransferX invited the free agent to TransferX",
        )
        await db.commit()
    except LookupError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found")
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    resp = PlayerInvitationResponse.model_validate(inv)
    resp.accept_url = await clubs_service.send_player_invitation(db, inv, raw_token)
    return resp


@router.get("/players/{player_id}/account", response_model=PlayerAccountStatusResponse)
async def player_account_status(
    player_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
):
    """Any player's account status and latest invitation, whoever sent it."""
    from app.players import service as players_service

    invitations = await clubs_service.list_player_invitations(db, staff=True, player_id=player_id)
    return PlayerAccountStatusResponse(
        has_account=await players_service.player_has_account(db, player_id),
        invitation=PlayerInvitationResponse.model_validate(invitations[0]) if invitations else None,
    )


@router.get("/player-invitations", response_model=list[PlayerInvitationResponse])
async def list_free_agent_invitations(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
):
    """Staff-sent invitations (clubs' and agents' are theirs to manage)."""
    from app.clubs.models import PlayerInvitation
    from app.players.models import Player

    rows = (await db.execute(
        select(PlayerInvitation, Player.name).join(Player, Player.id == PlayerInvitation.player_id)
        .where(PlayerInvitation.club_id.is_(None), PlayerInvitation.agent_id.is_(None))
        .order_by(PlayerInvitation.created_at.desc()).limit(200)
    )).all()
    out = []
    for inv, name in rows:
        r = PlayerInvitationResponse.model_validate(inv)
        r.player_name = name
        out.append(r)
    return out


@router.post("/player-invitations/{invitation_id}/revoke", response_model=PlayerInvitationResponse)
async def revoke_free_agent_invitation(
    invitation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
):
    try:
        inv = await clubs_service.revoke_player_invitation(db, invitation_id=invitation_id, staff=True)
        await db.commit()
    except LookupError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return PlayerInvitationResponse.model_validate(inv)


# ── Audit log (admin panel page and Excel export) ────────────────────────────


def _audit_filters(
    q: str | None = Query(None, max_length=200),
    action: str | None = Query(None, max_length=100),
    entity_type: str | None = Query(None, max_length=50),
    actor_id: uuid.UUID | None = Query(None),
    entity_id: uuid.UUID | None = Query(None),
    admin_only: bool = Query(False),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
):
    from app.admin.audit_log import AuditFilters

    return AuditFilters(q=q, action=action, entity_type=entity_type, actor_id=actor_id, entity_id=entity_id,
                        admin_only=admin_only, date_from=date_from, date_to=date_to)


@router.get("/audit-log")
async def audit_log(
    filters=Depends(_audit_filters),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Every audit event, newest first, with who did it and why."""
    from app.admin.audit_log import list_events

    items, total = await list_events(db, filters, page, page_size)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/audit-log/facets")
async def audit_log_facets(
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """The actions and entity types present, for the page's filters."""
    from app.admin.audit_log import facets

    return await facets(db)


@router.get("/audit-log/export.xlsx")
async def audit_log_export(
    filters=Depends(_audit_filters),
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """The filtered log as an Excel workbook (up to 50,000 rows). The export
    is itself recorded: who took a copy of the log, and of what."""
    from datetime import datetime, timezone

    from fastapi.responses import Response

    from app.admin.audit_log import export_xlsx

    data, rows, truncated = await export_xlsx(db, filters, exported_by=current_user.email)
    await admin_audit.record(
        db, current_user, "audit_log.exported", entity_type="user", entity_id=current_user.id,
        description=f"Exported {rows:,} audit log {'row' if rows == 1 else 'rows'} to Excel",
        details={"filters": dict(filters.describe()), "rows": rows, "truncated": truncated},
    )
    await db.commit()
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="transferx-audit-log-{stamp}.xlsx"'},
    )
