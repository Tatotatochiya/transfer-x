"""Lite mode routes (docs/feature_spec/lite-mode)."""
import uuid
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.database import get_db
from app.deps import get_current_user, get_optional_user
from app.lite import service
from app.lite.schemas import (
    LiteHomeResponse,
    LiteResumeRequest,
    PreferencesResponse,
    PreferencesUpdateRequest,
)

router = APIRouter(tags=["lite"])


@router.get("/users/me/preferences", response_model=PreferencesResponse)
async def get_my_preferences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await service.get_preferences(db, current_user)


@router.patch("/users/me/preferences", response_model=PreferencesResponse)
async def update_my_preferences(
    body: PreferencesUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    prefs = await service.update_preferences(
        db, current_user, lite_mode=body.lite_mode, text_scale=body.text_scale,
        **body.model_dump(include=set(service.PUSH_FIELDS), exclude_none=True),
    )
    await db.commit()
    return prefs


# ── Lite home (BACKEND.md §2) ────────────────────────────────────────────────


@router.get("/lite/home", response_model=LiteHomeResponse)
async def lite_home(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Everything the Lite home shows, in one request. Never calls a model."""
    try:
        return await service.lite_home(db, current_user)
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lite mode is for club members")


@router.put("/lite/resume", status_code=status.HTTP_204_NO_CONTENT)
async def set_resume(
    body: LiteResumeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remember the unfinished Lite flow, for "Carry on where you left off"."""
    try:
        await service.set_resume(db, current_user, title=body.title, href=body.href)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    await db.commit()


@router.delete("/lite/resume", status_code=status.HTTP_204_NO_CONTENT)
async def clear_resume(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await service.clear_resume(db, current_user)
    await db.commit()


# ── Buy flow (BACKEND.md §2a) ────────────────────────────────────────────────


@router.get("/lite/buy/squad")
async def buy_squad_counts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """How many players the club has in each position, for "You have none"."""
    from app.clubs.service import get_club_and_role_for_user

    club, _ = await get_club_and_role_for_user(db, current_user.id)
    if club is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lite mode is for club members")
    return {"counts": await service.squad_counts(db, club.id)}


@router.get("/lite/buy/candidates")
async def buy_candidates(
    position: str,
    band: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Three players the club could make an offer for now, picked by TransferX
    (decision 3). The model only rewords the reasons when it can."""
    try:
        return await service.buy_candidates(db, current_user, position=position, band=band)
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lite mode is for club members")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


# ── Action cards (L4, README "Screen 5") ─────────────────────────────────────


@router.get("/lite/offer-draft")
async def offer_draft(
    player_id: uuid.UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """What a new bid's card starts from. Describes only: confirming the card
    calls POST /offers, and its money panel is POST /ai/offer-check."""
    try:
        return await service.offer_draft(db, current_user, player_id=player_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.get("/lite/offers/{offer_id}")
async def offer_card(
    offer_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """An offer the club is party to, as an action card (anonymous buyers
    masked). Accept, counter and reject go to the existing offer endpoints."""
    try:
        return await service.offer_card(db, current_user, offer_id=offer_id)
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found")


@router.get("/lite/ask/suggestions")
async def ask_suggestions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Questions to tap before the first one is asked, from the club's state.
    No model call."""
    try:
        return {"suggestions": await service.ask_suggestions(db, current_user)}
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lite mode is for club members")


# ── Held sends for undo and plain progress (L6, architecture ADR 0007) ───────

from datetime import datetime, timezone  # noqa: E402

from pydantic import BaseModel, Field  # noqa: E402


class HoldRequest(BaseModel):
    kind: str = Field(pattern="^(bid|counter|accept|reject)$")
    # bid: the offer's terms (as POST /offers); counter: {offer_id, fee_amount};
    # accept and reject: {offer_id}.
    payload: dict
    ai_assisted: bool = False


async def _action_view(db: AsyncSession, action, now: datetime) -> dict:
    from app.lite import held

    return {
        "id": str(action.id),
        "kind": action.kind,
        "status": action.status.value,
        "execute_at": held._utc(action.execute_at).isoformat(),
        "result": action.result_json,
        "error": action.error,
        "progress": await held.progress(db, action, now),
    }


@router.post("/lite/actions", status_code=status.HTTP_201_CREATED)
async def hold_action(
    body: HoldRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Confirm a Lite action: checked now (an error shows on the card), then
    held for 10 seconds before it is sent, so it can be undone. Nothing is
    sent, notified or reserved while it is held."""
    from app.lite import held

    action = await held.hold(db, current_user, kind=body.kind, payload=body.payload, ai_assisted=body.ai_assisted)
    await db.commit()
    return await _action_view(db, action, datetime.now(timezone.utc))


@router.post("/lite/actions/{action_id}/undo")
async def undo_action(
    action_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Cancel a held action before it is sent. 409 once it has been."""
    from app.lite import held

    action = await held.undo(db, current_user, action_id)
    await db.commit()
    return await _action_view(db, action, datetime.now(timezone.utc))


@router.get("/lite/actions/{action_id}")
async def get_action(
    action_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """The action's status and its five plain progress steps."""
    from app.lite.models import HeldAction

    action = await db.get(HeldAction, action_id)
    if action is None or action.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return await _action_view(db, action, datetime.now(timezone.utc))


@router.get("/lite/deals/{deal_id}/progress")
async def deal_progress(
    deal_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """A deal's plain steps, for a club that is party to it."""
    from app.clubs import service as clubs_service
    from app.deals import service as deals_service
    from app.lite import held

    club = await clubs_service.get_club_for_user(db, current_user.id)
    deal = await deals_service.get_deal_by_id(db, deal_id)
    if deal is None or club is None or club.id not in (deal.buyer_club_id, deal.seller_club_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")
    return await held.deal_progress(db, deal, club.id)


# ── Team contact (BACKEND.md §6, L7) ─────────────────────────────────────────


class TeamContactResponse(BaseModel):
    name: str | None  # first name, or null for "your team"
    label: str        # "Sam" or "your team", ready for "Ask {label}"


class AskTeamRequest(BaseModel):
    subject_type: Literal["player", "offer", "deal", "general"] = "general"
    subject_id: uuid.UUID | None = None
    text: str = Field(min_length=1, max_length=1000)


async def _lite_club(db: AsyncSession, user: User):
    from app.clubs import service as clubs_service

    club, _ = await clubs_service.get_club_and_role_for_user(db, user.id)
    if club is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No club profile")
    return club


@router.get("/lite/team-contact", response_model=TeamContactResponse)
async def get_team_contact(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TeamContactResponse:
    """Who "Ask {name}" goes to: the club's chosen Lite contact, else its
    first sporting director or manager, else "your team"."""
    from app.lite import team

    contact = await team.team_contact(db, await _lite_club(db, current_user), current_user)
    return TeamContactResponse(name=contact["name"] if contact else None,
                               label=contact["name"] if contact else "your team")


@router.post("/lite/ask-team")
async def ask_team(
    body: AskTeamRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.lite import team

    club = await _lite_club(db, current_user)
    try:
        result = await team.ask_team(db, club, current_user, subject_type=body.subject_type,
                                     subject_id=body.subject_id, text=body.text)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    await db.commit()
    return result


# ── Decisions from email (BACKEND.md §7, L8) ─────────────────────────────────


class EmailConfirmRequest(BaseModel):
    action: Literal["counter", "accept", "reject"]
    amount: Decimal | None = None


@router.get("/lite/confirm/{token}")
async def view_email_decision(
    token: str,
    action: Literal["counter", "accept", "reject"],
    amount: Decimal | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
) -> dict:
    """What an email button would do. Changes nothing: mail scanners open links."""
    from app.lite import email_actions

    return await email_actions.view(db, token, action, amount, current_user)


@router.post("/lite/confirm/{token}")
async def confirm_email_decision(
    token: str,
    body: EmailConfirmRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
) -> dict:
    """Hold the decision for 10 seconds, like any Lite send. Accepting or
    countering needs the email's recipient signed in; saying no doesn't."""
    from app.lite import email_actions

    result = await email_actions.confirm(db, token, body.action, body.amount, current_user)
    await db.commit()
    return result


@router.post("/lite/confirm/{token}/undo", status_code=status.HTTP_204_NO_CONTENT)
async def undo_email_decision(token: str, db: AsyncSession = Depends(get_db)) -> None:
    from app.lite import email_actions

    await email_actions.undo(db, token)
    await db.commit()
