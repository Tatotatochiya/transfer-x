import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
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
    UpdateMeRequest,
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


def _set_names(user: User, first: str, last: str) -> None:
    """Names given while joining; blank ones are asked for later."""
    if first.strip():
        user.first_name = first.strip()
    if last.strip():
        user.last_name = last.strip()


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, request: Request, db: AsyncSession = Depends(get_db)) -> TokenResponse:
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
    _set_names(user, body.first_name, body.last_name)

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

    access_token, refresh_token = await auth_service.start_session(db, user, request.headers.get("user-agent"))
    await db.commit()
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)) -> TokenResponse:
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
    access_token, refresh_token = await auth_service.start_session(db, user, request.headers.get("user-agent"))
    user.last_active_at = datetime.now(timezone.utc)
    await db.commit()
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, request: Request, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    try:
        new_refresh_token, user, sid = await auth_service.rotate_refresh_token(
            db, body.refresh_token, request.headers.get("user-agent"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))

    access_token = auth_service.create_access_token(user.id, user.email, sid=sid)
    user.last_active_at = datetime.now(timezone.utc)
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


class PasswordResetPreview(BaseModel):
    email: str
    expires_at: datetime


class PasswordResetRequest(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    new_password: str = Field(min_length=8, max_length=200)


@router.get("/password-reset/{token}", response_model=PasswordResetPreview)
async def preview_password_reset(token: str, db: AsyncSession = Depends(get_db)):
    """What the reset page shows: whose password this sets. 404 for any link
    that is not live, with no hint as to why."""
    row = await auth_service.live_password_reset(db, token)
    user = await db.get(User, row.user_id) if row else None
    if row is None or user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This link has expired or has already been used")
    return PasswordResetPreview(email=user.email, expires_at=row.expires_at)


@router.post("/password-reset", status_code=status.HTTP_204_NO_CONTENT)
async def complete_password_reset(body: PasswordResetRequest, db: AsyncSession = Depends(get_db)) -> None:
    """Choose a new password with a one-time link. Signs the person out on
    every device; they then sign in with the new password."""
    from app.audit import service as audit_service

    try:
        user = await auth_service.complete_password_reset(db, body.token, body.new_password)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    await audit_service.emit(
        db, entity_type="user", entity_id=user.id, action="password_reset_completed", actor_user_id=user.id,
        description="Password changed with a reset link; signed out everywhere",
    )
    await db.commit()


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
    token: str, body: InvitationAcceptRequest, request: Request, db: AsyncSession = Depends(get_db)
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
    _set_names(user, body.first_name, body.last_name)
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
    access_token, refresh_token = await auth_service.start_session(db, user, request.headers.get("user-agent"))
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
    token: str, body: InvitationAcceptRequest, request: Request, db: AsyncSession = Depends(get_db)
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
    _set_names(user, body.first_name, body.last_name)
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
            message=f"{user.display_label} accepted your invitation and now has a player account",
            link=f"/players/market/{inv.player_id}", related_player_id=inv.player_id,
        )
    access_token, refresh_token = await auth_service.start_session(db, user, request.headers.get("user-agent"))
    await db.commit()
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/invitations/{token}/accept", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def accept_invitation(
    token: str,
    body: InvitationAcceptRequest,
    request: Request,
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
    _set_names(user, body.first_name, body.last_name)

    club = await clubs_service.get_club_by_id(db, invitation.club_id)
    await audit_service.emit(
        db,
        entity_type="CLUB",
        entity_id=invitation.club_id,
        action="STAFF_JOINED",
        actor_user_id=user.id,
        payload={"email": user.email, "role": staff.role.value},
        description=f"{user.display_label} joined as {staff.role.value}",
    )
    # Account/administrative event → owner only (D5).
    if club is not None:
        await notif_service.create_notification(
            db,
            recipient_user_id=club.user_id,
            type=NotificationType.STAFF_INVITATION,
            message=f"{user.display_label} accepted your invitation and joined as {staff.role.value.replace('_', ' ').title()}",
            link="/club/team",
        )

    access_token, refresh_token = await auth_service.start_session(db, user, request.headers.get("user-agent"))
    await db.commit()
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.get("/me", response_model=UserResponse)
async def me(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    club, _role = await clubs_service.get_club_and_role_for_user(db, current_user.id)
    resp = UserResponse.model_validate(current_user)
    resp.has_club = club is not None
    staff_id = getattr(request.state, "view_as_by", None)
    if staff_id:
        import uuid as _uuid

        staff = await db.get(User, _uuid.UUID(staff_id))
        resp.viewed_by = staff.display_label if staff else "TransferX staff"
    return resp


@router.patch("/me", response_model=UserResponse)
async def update_me(
    body: UpdateMeRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Set your first and last name."""
    first, last = body.first_name.strip(), body.last_name.strip()
    if not first or not last:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Enter your first and last name")
    current_user.first_name, current_user.last_name = first, last
    await db.commit()
    return await me(request, current_user, db)


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


# ── Signed-in devices (Phase 1) ───────────────────────────────────────────────


def _device_label(ua: str | None) -> str:
    """'Chrome on Mac', 'Safari on iPhone', or 'Unknown device'."""
    if not ua:
        return "Unknown device"
    os_name = next((name for key, name in (
        ("iPhone", "iPhone"), ("iPad", "iPad"), ("Android", "Android"), ("Windows", "Windows"),
        ("Macintosh", "Mac"), ("CrOS", "ChromeOS"), ("Linux", "Linux"),
    ) if key in ua), None)
    browser = next((name for key, name in (
        ("Edg/", "Edge"), ("OPR/", "Opera"), ("Firefox/", "Firefox"), ("CriOS/", "Chrome"),
        ("Chrome/", "Chrome"), ("Safari/", "Safari"),
    ) if key in ua), None)
    if browser and os_name:
        return f"{browser} on {os_name}"
    return browser or os_name or "Unknown device"


def _current_sid(request: Request) -> str | None:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        return None
    try:
        return auth_service.decode_access_token(auth[7:]).get("sid")
    except Exception:
        return None


@router.get("/sessions")
async def list_sessions(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Where you're signed in, most recently used first."""
    from app.auth.models import RefreshToken

    rows = (await db.execute(
        select(RefreshToken).where(RefreshToken.user_id == current_user.id)
    )).scalars().all()
    current = _current_sid(request)
    sessions: dict = {}
    for rt in rows:  # one row per session normally; keep the latest if not
        s = sessions.get(rt.session_id)
        if s is None or (rt.last_used_at or rt.created_at) > (s.last_used_at or s.created_at):
            sessions[rt.session_id] = rt
    out = [{
        "id": str(rt.session_id),
        "device": _device_label(rt.user_agent),
        "signed_in_at": rt.signed_in_at or rt.created_at,
        "last_used_at": rt.last_used_at or rt.created_at,
        "current": current is not None and str(rt.session_id) == current,
    } for rt in sessions.values()]
    out.sort(key=lambda s: (not s["current"], -s["last_used_at"].timestamp()))
    return out


async def _end_sessions(db: AsyncSession, user: User, keep: str | None = None, only: uuid.UUID | None = None) -> int:
    from sqlalchemy import delete

    from app.auth.models import RefreshToken

    q = delete(RefreshToken).where(RefreshToken.user_id == user.id)
    if only is not None:
        q = q.where(RefreshToken.session_id == only)
    if keep:
        q = q.where(RefreshToken.session_id != uuid.UUID(keep))
    result = await db.execute(q)
    return result.rowcount or 0


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def sign_out_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Sign out one device. It stops working at its next request."""
    if not await _end_sessions(db, current_user, only=session_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="That device is already signed out")
    await db.commit()


@router.post("/sessions/sign-out-others")
async def sign_out_other_sessions(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Sign out everywhere except this device."""
    ended = await _end_sessions(db, current_user, keep=_current_sid(request))
    await db.commit()
    return {"signed_out": ended}


# ── Your data (GDPR, Phase 1) ─────────────────────────────────────────────────


class _CloseAccountBody(BaseModel):
    password: str
    confirm: str


@router.get("/me/export")
async def export_my_data(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Your personal data as a JSON file."""
    import json

    from fastapi.responses import Response

    from app.audit import service as audit_service
    from app.auth import privacy

    data = await privacy.export_user_data(db, current_user)
    await audit_service.emit(
        db, entity_type="USER", entity_id=current_user.id, action="DATA_EXPORTED",
        actor_user_id=current_user.id, description="Downloaded their personal data",
    )
    await db.commit()
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return Response(
        content=json.dumps(data, indent=2, ensure_ascii=False, default=str),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="transferx-my-data-{day}.json"'},
    )


@router.get("/me/close-check")
async def can_close_account(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Whether this account can be closed here, and if not, why."""
    from app.auth import privacy

    try:
        await privacy.check_can_close(db, current_user)
        return {"can_close": True, "reason": None}
    except privacy.CannotClose as exc:
        return {"can_close": False, "reason": str(exc)}


@router.post("/me/close", status_code=status.HTTP_204_NO_CONTENT)
async def close_my_account(
    body: _CloseAccountBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Close your account: your details are erased; the records others rely
    on (audit trail, deal comments, messages) stay, without your name."""
    from app.audit import service as audit_service
    from app.auth import privacy

    if body.confirm.strip().upper() != "DELETE":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Type DELETE to confirm')
    if not auth_service.verify_password(body.password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="That password isn't right")
    try:
        await privacy.close_account(db, current_user)
    except privacy.CannotClose as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    await audit_service.emit(
        db, entity_type="USER", entity_id=current_user.id, action="ACCOUNT_CLOSED",
        actor_user_id=current_user.id, description="Closed their account and erased their personal details",
    )
    await db.commit()
