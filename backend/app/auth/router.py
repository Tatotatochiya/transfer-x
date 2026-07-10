from fastapi import APIRouter, Depends, HTTPException, status
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
from app.clubs.schemas import InvitationAcceptRequest, InvitationPreviewResponse
from app.database import get_db

router = APIRouter(tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    from app.auth.models import UserType

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
    user = await auth_service.authenticate_user(db, email=body.email, password=body.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
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
