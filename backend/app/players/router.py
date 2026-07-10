import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.common.schemas import Paginated
from app.database import get_db
from app.deps import get_buyer_user, get_current_user, get_current_player_profile, get_optional_user, get_seller_user
from app.clubs.capabilities import Capability, require_club_capability
from app.players import service as players_service
from app.players.models import PlayerPosition, PlayerStatus, PlayerVisibility
from app.players.schemas import (
    ActiveDealStub,
    ContractCreateRequest,
    ContractResponse,
    PlayerCreateRequest,
    PlayerDetailResponse,
    PlayerResponse,
    PlayerTransferResponse,
    PlayerInjuryResponse,
    PlayerUpdateRequest,
)
from app.sales.schemas import DealStubResponse

router = APIRouter(tags=["players"])

# TRA-151: squad management (create/edit players, contracts) is a market action.
_market_write = require_club_capability(Capability.MARKET_WRITE)


# ── Player market (public / optional auth) ────────────────────────────────────


@router.get("/market", response_model=Paginated[PlayerResponse])
async def player_market(
    position: PlayerPosition | None = Query(None),
    status: PlayerStatus | None = Query(None),
    open_to_offers: bool | None = Query(None),
    search: str | None = Query(None),
    min_age: int | None = Query(None, ge=14, le=50),
    max_age: int | None = Query(None, ge=14, le=50),
    nationality: str | None = Query(None),
    club_search: str | None = Query(None),
    min_goals: int | None = Query(None, ge=0),
    min_assists: int | None = Query(None, ge=0),
    min_appearances: int | None = Query(None, ge=0),
    min_avg_rating: float | None = Query(None, ge=0, le=10),
    min_form_score: float | None = Query(None, ge=0, le=100),
    min_market_value: Decimal | None = Query(None, ge=0),
    max_market_value: Decimal | None = Query(None, ge=0),
    contract_expiry_within_months: int | None = Query(None, ge=1, le=36),
    sort_by: str = Query("name", pattern="^(name|age|goals|assists|appearances|avg_rating|form_score)$"),
    sort_dir: str = Query("asc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
) -> Paginated[PlayerResponse]:
    players, total = await players_service.list_market_players(
        db,
        is_authenticated=current_user is not None,
        position=position.value if position else None,
        status=status.value if status else None,
        open_to_offers=open_to_offers,
        search=search,
        min_age=min_age,
        max_age=max_age,
        nationality=nationality,
        club_search=club_search,
        min_goals=min_goals,
        min_assists=min_assists,
        min_appearances=min_appearances,
        min_avg_rating=min_avg_rating,
        min_form_score=min_form_score,
        min_market_value=min_market_value,
        max_market_value=max_market_value,
        contract_expiry_within_months=contract_expiry_within_months,
        sort_by=sort_by,
        sort_dir=sort_dir,
        page=page,
        page_size=page_size,
    )
    return Paginated(
        items=[PlayerResponse.model_validate(p) for p in players],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/market/{player_id}", response_model=PlayerDetailResponse)
async def player_market_detail(
    player_id: uuid.UUID,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
) -> PlayerDetailResponse:
    player = await players_service.get_player_by_id(db, player_id)
    if player is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found")

    from app.players.models import PlayerVisibility
    if player.visibility == PlayerVisibility.PRIVATE:
        # Private: only owner can see
        if current_user is None or player.created_by_user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found")
    elif player.visibility == PlayerVisibility.CLUBS_ONLY and current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Login required")

    from app.deals import service as deals_service

    active_contract = next((c for c in player.contracts if c.is_active), None)
    data = PlayerDetailResponse.model_validate(player)
    if active_contract and current_user is not None:
        data.active_contract = ContractResponse.model_validate(active_contract)

    deal = await deals_service.get_active_deal_for_player(db, player_id)
    if deal:
        data.active_deal = ActiveDealStub.model_validate(deal)

    data.is_verified_player = await players_service.is_player_verified(db, player_id)

    return data


# ── Direct-signing pathways (items 13 & 14) ───────────────────────────────────


async def _resolve_direct_signing_context(db: AsyncSession, player_id: uuid.UUID, current_user: User):
    """Shared preamble for direct-signing endpoints that bypass the normal
    offer/bid pipeline: resolve the buyer's club, check the transfer window,
    fetch the player, and block if a deal is already in progress."""
    from app.clubs import service as clubs_service
    from app.deals import service as deals_service
    from app.transfer_window import service as window_service

    club = await clubs_service.get_club_for_user(db, current_user.id)
    if club is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No club profile")

    if not current_user.is_superuser and not await window_service.is_transfer_allowed(db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Transfer window is closed. Transfers cannot be made outside of a transfer window.",
        )

    player = await players_service.get_player_by_id(db, player_id)
    if player is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found")

    active_deal = await deals_service.get_active_deal_for_player(db, player_id)
    if active_deal and active_deal.status == "IN_PROGRESS":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This player already has a transfer deal in progress.",
        )

    return club, player


@router.post("/{player_id}/trigger-release-clause", response_model=DealStubResponse)
async def trigger_release_clause(
    player_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_buyer_user),
    _write: User = Depends(_market_write),
):
    """Item 14: a buyer meeting the release clause bypasses the seller's
    consent — that's the clause's whole point. No fee is taken from the
    request body; the amount is always the contract's own release_clause
    figure."""
    club, player = await _resolve_direct_signing_context(db, player_id, current_user)

    try:
        deal = await players_service.trigger_release_clause(db, player, buyer_club_id=club.id)
        await db.commit()
        await db.refresh(deal)
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return DealStubResponse.model_validate(deal)


@router.post("/{player_id}/sign-free-agent", response_model=DealStubResponse)
async def sign_free_agent(
    player_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_buyer_user),
    _write: User = Depends(_market_write),
):
    """Item 13: sign a FREE_AGENT player directly — no seller, no fee, no
    offer/bid negotiation pipeline."""
    club, player = await _resolve_direct_signing_context(db, player_id, current_user)

    try:
        deal = await players_service.create_free_agent_deal(db, player, buyer_club_id=club.id)
        await db.commit()
        await db.refresh(deal)
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return DealStubResponse.model_validate(deal)


@router.post("/{player_id}/pre-contract", response_model=DealStubResponse)
async def sign_pre_contract(
    player_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_buyer_user),
    _write: User = Depends(_market_write),
):
    """Item 13: a Bosman pre-contract agreement — sign now, join for free once
    the current contract expires. Only legal in the contract's final six months."""
    club, player = await _resolve_direct_signing_context(db, player_id, current_user)

    try:
        deal = await players_service.create_pre_contract_deal(db, player, buyer_club_id=club.id)
        await db.commit()
        await db.refresh(deal)
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return DealStubResponse.model_validate(deal)


# ── Seller's own players ──────────────────────────────────────────────────────


@router.get("", response_model=Paginated[PlayerResponse])
async def list_my_players(
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    current_user: User = Depends(get_seller_user),
    db: AsyncSession = Depends(get_db),
) -> Paginated[PlayerResponse]:
    players, total = await players_service.list_own_players(
        db, created_by_user_id=current_user.id, page=page, page_size=page_size
    )
    return Paginated(
        items=[PlayerResponse.model_validate(p) for p in players],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=PlayerResponse, status_code=status.HTTP_201_CREATED)
async def create_player(
    body: PlayerCreateRequest,
    current_user: User = Depends(get_seller_user),
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(_market_write),
) -> PlayerResponse:
    player = await players_service.create_player(
        db, created_by_user_id=current_user.id, **body.model_dump()
    )
    await db.commit()
    await db.refresh(player)
    return PlayerResponse.model_validate(player)


# ── Player self-service (PLAYER user type) ───────────────────────────────────


class _PlayerSelfUpdateBody(BaseModel):
    visibility: PlayerVisibility | None = None
    open_to_offers: bool | None = None


@router.get("/me", response_model=PlayerDetailResponse)
async def get_my_player_profile(
    player_profile=Depends(get_current_player_profile),
    db: AsyncSession = Depends(get_db),
) -> PlayerDetailResponse:
    player = await players_service.get_player_by_id(db, player_profile.player_id)
    if player is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found")
    data = PlayerDetailResponse.model_validate(player)
    data.is_verified_player = player_profile.verified
    return data


@router.patch("/me", response_model=PlayerDetailResponse)
async def update_my_player_profile(
    body: _PlayerSelfUpdateBody,
    player_profile=Depends(get_current_player_profile),
    db: AsyncSession = Depends(get_db),
) -> PlayerDetailResponse:
    player = await players_service.get_player_by_id(db, player_profile.player_id)
    if player is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found")
    updates = body.model_dump(exclude_none=True)
    if updates:
        await players_service.update_player(db, player, **updates)
        await db.commit()
        await db.refresh(player)
    return PlayerDetailResponse.model_validate(player)


@router.patch("/{player_id}", response_model=PlayerResponse)
async def update_player(
    player_id: uuid.UUID,
    body: PlayerUpdateRequest,
    current_user: User = Depends(get_seller_user),
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(_market_write),
) -> PlayerResponse:
    player = await players_service.get_player_by_id(db, player_id)
    if player is None or player.created_by_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found")

    await players_service.update_player(db, player, **body.model_dump(exclude_none=True))
    await db.commit()
    await db.refresh(player)
    return PlayerResponse.model_validate(player)


# ── Contracts ─────────────────────────────────────────────────────────────────


@router.post("/{player_id}/contracts", response_model=ContractResponse, status_code=status.HTTP_201_CREATED)
async def add_contract(
    player_id: uuid.UUID,
    body: ContractCreateRequest,
    current_user: User = Depends(get_seller_user),
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(_market_write),
) -> ContractResponse:
    player = await players_service.get_player_by_id(db, player_id)
    if player is None or player.created_by_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found")

    contract = await players_service.create_contract(
        db,
        player=player,
        club_id=body.club_id,
        start_date=body.start_date,
        end_date=body.end_date,
        wage_weekly=body.wage_weekly,
        release_clause=body.release_clause,
        notes=body.notes,
    )
    await db.commit()
    return ContractResponse.model_validate(contract)


@router.delete("/{player_id}/contracts/{contract_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_contract(
    player_id: uuid.UUID,
    contract_id: uuid.UUID,
    current_user: User = Depends(get_seller_user),
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(_market_write),
) -> None:
    player = await players_service.get_player_by_id(db, player_id)
    if player is None or player.created_by_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found")

    contract = next((c for c in player.contracts if c.id == contract_id), None)
    if contract is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found")
    if not contract.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Contract already inactive")

    await players_service.deactivate_contract(db, contract, player)
    await db.commit()


# ── Career history ────────────────────────────────────────────────────────────

CAREER_CACHE_HOURS = 24


@router.get("/market/{player_id}/transfers", response_model=list[PlayerTransferResponse])
async def get_player_transfers(
    player_id: uuid.UUID,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
) -> list[PlayerTransferResponse]:
    """Return cached transfer history; auto-refreshes from API if >24h old."""
    from datetime import datetime, timezone, timedelta
    from sqlalchemy import select, func as safunc
    from app.players.models import Player, PlayerTransfer
    from app.config import settings
    from app.vendor.client import ApiFootballClient, VENDOR

    player = await players_service.get_player_by_id(db, player_id)
    if player is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found")

    # Check cache freshness
    cutoff = datetime.now(timezone.utc) - timedelta(hours=CAREER_CACHE_HOURS)
    newest_q = await db.execute(
        select(safunc.max(PlayerTransfer.fetched_at)).where(PlayerTransfer.player_id == player_id)
    )
    newest = newest_q.scalar()
    is_fresh = newest is not None and (
        newest.replace(tzinfo=timezone.utc) if newest.tzinfo is None else newest
    ) > cutoff

    if not is_fresh and player.vendor_id and settings.apisports_key:
        client = ApiFootballClient(settings.apisports_key, settings.api_football_base_url)
        try:
            resp = await client.get_player_transfers(int(player.vendor_id))
            now = datetime.now(timezone.utc)
            # Delete old records and re-insert
            from sqlalchemy import delete
            await db.execute(delete(PlayerTransfer).where(PlayerTransfer.player_id == player_id))
            for item in resp.get("response") or []:
                for t in item.get("transfers") or []:
                    teams = t.get("teams") or {}
                    team_in = teams.get("in") or {}
                    team_out = teams.get("out") or {}
                    date_raw = t.get("date")
                    transfer_date = None
                    if date_raw:
                        try:
                            from datetime import date as ddate
                            transfer_date = ddate.fromisoformat(date_raw)
                        except ValueError:
                            pass
                    # API uses "type" for both the label AND fee:
                    # "Loan" → type=Loan, fee=None
                    # "€ 42M" / "Free" / "N/A" → type=Transfer, fee=value
                    raw_type = t.get("type") or ""
                    is_loan = raw_type.lower() == "loan"
                    transfer_type = "Loan" if is_loan else "Transfer"
                    fee_display = None if is_loan or raw_type in ("", "N/A") else raw_type
                    db.add(PlayerTransfer(
                        player_id=player_id,
                        vendor=VENDOR,
                        transfer_date=transfer_date,
                        transfer_type=transfer_type,
                        team_in_vendor_id=str(team_in.get("id")) if team_in.get("id") else None,
                        team_in_name=team_in.get("name"),
                        team_in_crest_url=team_in.get("logo"),
                        team_out_vendor_id=str(team_out.get("id")) if team_out.get("id") else None,
                        team_out_name=team_out.get("name"),
                        team_out_crest_url=team_out.get("logo"),
                        fee_display=fee_display,
                        fetched_at=now,
                    ))
            await db.commit()
        except Exception:
            pass  # serve whatever is cached

    result = await db.execute(
        select(PlayerTransfer)
        .where(PlayerTransfer.player_id == player_id)
        .order_by(PlayerTransfer.transfer_date.desc().nulls_last())
    )
    return [PlayerTransferResponse.model_validate(r) for r in result.scalars()]


@router.get("/market/{player_id}/injuries", response_model=list[PlayerInjuryResponse])
async def get_player_injuries(
    player_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[PlayerInjuryResponse]:
    """Return cached injury history; auto-refreshes from API if >24h old. Requires auth."""
    from datetime import datetime, timezone, timedelta
    from sqlalchemy import select, func as safunc
    from app.players.models import Player, PlayerInjury
    from app.config import settings
    from app.vendor.client import ApiFootballClient, VENDOR

    player = await players_service.get_player_by_id(db, player_id)
    if player is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found")

    cutoff = datetime.now(timezone.utc) - timedelta(hours=CAREER_CACHE_HOURS)
    newest_q = await db.execute(
        select(safunc.max(PlayerInjury.fetched_at)).where(PlayerInjury.player_id == player_id)
    )
    newest = newest_q.scalar()
    is_fresh = newest is not None and (
        newest.replace(tzinfo=timezone.utc) if newest.tzinfo is None else newest
    ) > cutoff

    if not is_fresh and player.vendor_id and settings.apisports_key:
        client = ApiFootballClient(settings.apisports_key, settings.api_football_base_url)
        try:
            resp = await client.get_player_sidelined(int(player.vendor_id))
            now = datetime.now(timezone.utc)
            from sqlalchemy import delete
            await db.execute(delete(PlayerInjury).where(PlayerInjury.player_id == player_id))
            # API response: each item in "response" IS the sidelined record
            # Format: {"type": "Muscle Injury", "start": "2024-02-18", "end": "2024-03-06"}
            for s in resp.get("response") or []:
                date_raw = s.get("start")
                fixture_date = None
                if date_raw:
                    try:
                        from datetime import date as ddate
                        fixture_date = ddate.fromisoformat(str(date_raw)[:10])
                    except ValueError:
                        pass
                db.add(PlayerInjury(
                    player_id=player_id,
                    vendor=VENDOR,
                    league_name=None,
                    season=None,
                    fixture_date=fixture_date,
                    injury_type=s.get("type"),
                    reason=s.get("reason"),
                    games_absent=None,
                    fetched_at=now,
                ))
            await db.commit()
        except Exception:
            pass

    result = await db.execute(
        select(PlayerInjury)
        .where(PlayerInjury.player_id == player_id)
        .order_by(PlayerInjury.fixture_date.desc().nulls_last())
    )
    return [PlayerInjuryResponse.model_validate(r) for r in result.scalars()]


# ── Representation (mandates) ─────────────────────────────────────────────────


@router.get("/{player_id}/representation")
async def get_player_representation(
    player_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list:
    from sqlalchemy import select as sa_select
    from app.mandates.models import Mandate, MandateStatus
    from app.mandates.schemas import MandateResponse
    result = await db.execute(
        sa_select(Mandate).where(
            Mandate.player_id == player_id,
            Mandate.status == MandateStatus.ACTIVE,
        )
    )
    return [MandateResponse.model_validate(m) for m in result.scalars()]


@router.post("/{player_id}/representation/{mandate_id}/revoke")
async def player_revoke_representation(
    player_id: uuid.UUID,
    mandate_id: uuid.UUID,
    player_profile=Depends(get_current_player_profile),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select

    from app.auth.models import AgentProfile
    from app.mandates.schemas import MandateResponse
    from app.mandates.service import revoke_mandate_as_player
    from app.notifications import service as notif_service
    from app.notifications.models import NotificationType

    if player_profile.player_id != player_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your player record")
    try:
        mandate = await revoke_mandate_as_player(db, mandate_id=mandate_id, player_id=player_id)
        agent_result = await db.execute(select(AgentProfile).where(AgentProfile.id == mandate.agent_id))
        agent = agent_result.scalar_one_or_none()
        if agent is not None:
            await notif_service.create_notification(
                db,
                recipient_user_id=agent.user_id,
                type=NotificationType.REPRESENTATION_REVOKED,
                message="A player has ended your representation mandate",
                link=f"/agent/clients/{mandate.id}",
            )
    except ValueError as exc:
        detail = str(exc)
        if "not found" in detail.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
    await db.commit()
    return MandateResponse.model_validate(mandate)
