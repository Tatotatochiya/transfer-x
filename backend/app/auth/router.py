from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import service as auth_service
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.auth.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.clubs import service as clubs_service
from app.clubs.schemas import (
    ClubInvitationPreviewResponse,
    InvitationAcceptRequest,
    InvitationPreviewResponse,
    PlayerInvitationPreviewResponse,
)
from app.config import settings
from app.database import get_db

router = APIRouter(tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    from app.auth.models import UserType

    # Clubs join by invitation only: public club sign-up let anyone claim to
    # be any club. Agents and players still register here.
    if body.user_type == UserType.CLUB and not settings.allow_club_self_registration:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Clubs join TransferX by invitation. Contact TransferX to be invited.",
        )

    # Players join by invitation from their club, for the same reason: a
    # player account can accept personal terms, so it must not be claimable
    # by anyone who knows a player's id.
    if body.user_type == UserType.PLAYER and not settings.allow_player_self_registration:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Players join TransferX by invitation from their club.",
        )

    try:
        user = await auth_service.create_user(
            db, email=body.email, password=body.password, user_type=body.user_type
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    if body.user_type == UserType.CLUB:
        club_name = body.club_name.strip() or body.email.split("@")[0]
        club = await clubs_service.create_club(db, user_id=user.id, name=club_name)
        await clubs_service.create_club_finance(db, club_id=club.id)

    elif body.user_type == UserType.AGENT:
        if not body.display_name or not body.agency_name or not body.country:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="display_name, agency_name, and country are required for agent registration",
            )
        try:
            await auth_service.create_agent_profile(
                db,
                user_id=user.id,
                display_name=body.display_name,
                agency_name=body.agency_name,
                country=body.country,
                licence_no=body.licence_no,
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    elif body.user_type == UserType.PLAYER:
        if body.player_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="player_id is required for player registration",
            )
        try:
            await auth_service.create_player_profile(
                db, user_id=user.id, player_id=body.player_id
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    access_token = auth_service.create_access_token(user.id, user.email)
    refresh_token = await auth_service.create_refresh_token(db, user.id)
    await db.commit()
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    """Sign in with an email address or a username (the part of the email
    before the "@")."""
    try:
        user = await auth_service.authenticate_user(db, email=body.email, password=body.password)
    except auth_service.AmbiguousUsername:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="More than one account uses that username — sign in with your email address",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email, username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = auth_service.create_access_token(user.id, user.email)
    refresh_token = await auth_service.create_refresh_token(db, user.id)
    await db.commit()
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    try:
        new_refresh_token, user = await auth_service.rotate_refresh_token(db, body.refresh_token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))

    access_token = auth_service.create_access_token(user.id, user.email)
    await db.commit()
    return TokenResponse(access_token=access_token, refresh_token=new_refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(body: RefreshRequest, db: AsyncSession = Depends(get_db)) -> None:
    await auth_service.revoke_refresh_token(db, body.refresh_token)
    await db.commit()


# ── Staff invitation acceptance (TRA-86, D6) ─────────────────────────────────
# Public, but provisioning-via-emailed-link only — the login page stays
# login-only; this is not open signup.


@router.get("/invitations/{token}", response_model=InvitationPreviewResponse)
async def preview_invitation(token: str, db: AsyncSession = Depends(get_db)) -> InvitationPreviewResponse:
    """Preview a staff invitation. 404 for unknown/expired/revoked/accepted
    tokens alike — no oracle on which failure it was."""
    invitation = await clubs_service.get_live_invitation_by_token(db, token)
    if invitation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")
    club = await clubs_service.get_club_by_id(db, invitation.club_id)
    if club is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")
    return InvitationPreviewResponse(
        club_name=club.name,
        club_crest_url=club.crest_url,
        role=invitation.role,
        email=invitation.email,
        expires_at=invitation.expires_at,
    )


# ── Club invitations: how a club joins TransferX ─────────────────────────────


@router.get("/club-invitations/{token}", response_model=ClubInvitationPreviewResponse)
async def preview_club_invitation(token: str, db: AsyncSession = Depends(get_db)):
    """What the join page shows: which club, and which email. 404 for any
    token that is not live, with no hint as to why."""
    inv = await clubs_service.get_live_club_invitation(db, token)
    if inv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")
    return ClubInvitationPreviewResponse(club_name=inv.club_name, email=inv.email, expires_at=inv.expires_at)


@router.post("/club-invitations/{token}/accept", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def accept_club_invitation(
    token: str, body: InvitationAcceptRequest, db: AsyncSession = Depends(get_db)
) -> TokenResponse:
    """Accept a club invitation: creates the owner's account, the club and its
    finance, and signs the owner straight in."""
    from app.audit import service as audit_service

    if len(body.password) < 8:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Use at least 8 characters")
    try:
        user = await clubs_service.accept_club_invitation(db, token, password=body.password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    club = await clubs_service.get_club_for_user(db, user.id)
    await audit_service.emit(
        db,
        entity_type="CLUB",
        entity_id=club.id,
        action="CLUB_JOINED",
        actor_user_id=user.id,
        payload={"email": user.email},
        description=f"{club.name} joined TransferX by invitation",
    )
    access_token = auth_service.create_access_token(user.id, user.email)
    refresh_token = await auth_service.create_refresh_token(db, user.id)
    await db.commit()
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.get("/player-invitations/{token}", response_model=PlayerInvitationPreviewResponse)
async def preview_player_invitation(token: str, db: AsyncSession = Depends(get_db)) -> PlayerInvitationPreviewResponse:
    """What the player's join page shows. 404 for any token that is not live."""
    from app.players.models import Player

    inv = await clubs_service.get_live_player_invitation(db, token)
    if inv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")
    player = (await db.execute(select(Player).where(Player.id == inv.player_id))).scalar_one()
    return PlayerInvitationPreviewResponse(
        player_name=player.name, invited_by=await clubs_service.player_invitation_inviter(db, inv),
        email=inv.email, expires_at=inv.expires_at,
    )


@router.post("/player-invitations/{token}/accept", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def accept_player_invitation(
    token: str, body: InvitationAcceptRequest, db: AsyncSession = Depends(get_db)
) -> TokenResponse:
    """Accept a player invitation: creates the player's account, linked to his
    player record, and signs him straight in."""
    from app.audit import service as audit_service
    from app.notifications import service as notif_service
    from app.notifications.models import NotificationType

    if len(body.password) < 8:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Use at least 8 characters")
    inv = await clubs_service.get_live_player_invitation(db, token)
    try:
        user = await clubs_service.accept_player_invitation(db, token, password=body.password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    await audit_service.emit(
        db, entity_type="PLAYER", entity_id=inv.player_id, action="PLAYER_JOINED",
        actor_user_id=user.id,
        payload={
            "email": user.email,
            "club_id": str(inv.club_id) if inv.club_id else None,
            "agent_id": str(inv.agent_id) if inv.agent_id else None,
        },
        description=f"Player joined TransferX by invitation from {await clubs_service.player_invitation_inviter(db, inv)}",
    )
    # Tell whoever invited him: the club's owner, or the agent.
    recipient = None
    if inv.club_id is not None:
        club = await clubs_service.get_club_by_id(db, inv.club_id)
        recipient = club.user_id if club else None
    elif inv.agent_id is not None:
        from app.auth.models import AgentProfile

        agent = (await db.execute(select(AgentProfile).where(AgentProfile.id == inv.agent_id))).scalar_one_or_none()
        recipient = agent.user_id if agent else None
    if recipient is not None:
        await notif_service.create_notification(
            db, recipient_user_id=recipient, type=NotificationType.STAFF_INVITATION,
            message=f"{user.email} accepted your invitation and now has a player account",
            link=f"/players/market/{inv.player_id}", related_player_id=inv.player_id,
        )
    access_token = auth_service.create_access_token(user.id, user.email)
    refresh_token = await auth_service.create_refresh_token(db, user.id)
    await db.commit()
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/invitations/{token}/accept", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def accept_invitation(
    token: str,
    body: InvitationAcceptRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Accept a staff invitation: creates the User (explicit user_type=CLUB, D9)
    + ClubStaff row, stamps the invitation, and logs the new member straight in."""
    from app.audit import service as audit_service
    from app.notifications import service as notif_service
    from app.notifications.models import NotificationType

    invitation = await clubs_service.get_live_invitation_by_token(db, token)
    if invitation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")

    try:
        user, staff = await clubs_service.accept_staff_invitation(db, invitation, body.password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    club = await clubs_service.get_club_by_id(db, invitation.club_id)
    await audit_service.emit(
        db,
        entity_type="CLUB",
        entity_id=invitation.club_id,
        action="STAFF_JOINED",
        actor_user_id=user.id,
        payload={"email": user.email, "role": staff.role.value},
        description=f"{user.email} joined as {staff.role.value}",
    )
    # Account/administrative event → owner only (D5).
    if club is not None:
        await notif_service.create_notification(
            db,
            recipient_user_id=club.user_id,
            type=NotificationType.STAFF_INVITATION,
            message=f"{user.email} accepted your invitation and joined as {staff.role.value.replace('_', ' ').title()}",
            link="/club/team",
        )

    access_token = auth_service.create_access_token(user.id, user.email)
    refresh_token = await auth_service.create_refresh_token(db, user.id)
    await db.commit()
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.patch("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    body: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await auth_service.change_password(db, current_user, body.current_password, body.new_password)
        await db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
