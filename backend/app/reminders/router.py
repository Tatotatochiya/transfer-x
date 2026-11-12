"""Move reminders (docs/feature_spec/move-reminders §3)."""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.database import get_db
from app.reminders import service
from app.reminders.schemas import LastReminder, ReminderHolder, ReminderState, SendReminder

router = APIRouter(prefix="/reminders", tags=["reminders"])


async def _viewer(db: AsyncSession, user: User, subject_type: str) -> service.Viewer:
    from app.auth.models import AgentProfile
    from app.clubs import service as clubs_service
    from app.clubs.capabilities import ROLE_CAPABILITIES, Capability

    club, role = await clubs_service.get_club_and_role_for_user(db, user.id)
    if club is not None:
        cap = Capability.DEAL_WRITE if subject_type == "deal" else Capability.MARKET_WRITE
        return service.Viewer(user.id, club_id=club.id, can_act=cap in ROLE_CAPABILITIES.get(role, frozenset()))
    agent = (await db.execute(select(AgentProfile).where(AgentProfile.user_id == user.id))).scalar_one_or_none()
    if agent is not None:
        return service.Viewer(user.id, agent_id=agent.id, name=agent.display_name)
    return service.Viewer(user.id, can_act=False)


async def _load(db: AsyncSession, user: User, subject_type: str, subject_id: uuid.UUID):
    # Anyone who isn't a party gets 404, so a transaction's existence isn't revealed.
    if subject_type not in service.SUBJECTS:
        raise HTTPException(404, "Not found")
    s = await service.load_subject(db, subject_type, subject_id)
    v = await _viewer(db, user, subject_type)
    if s is None or not service._is_party(s, v):
        raise HTTPException(404, "Not found")
    return s, v


async def _by(db: AsyncSession, s: service.Subject, r) -> str:
    if r.automatic:
        return "TransferX"
    if r.sender_club_id is None:
        from app.auth.models import AgentProfile

        name = (await db.execute(select(AgentProfile.display_name).where(AgentProfile.user_id == r.sender_user_id))).scalar()
        return name or "The agent"
    return service.sender_label(s, service.Viewer(r.sender_user_id, club_id=r.sender_club_id), None)


async def _response(db: AsyncSession, s: service.Subject, st: service.State, v: service.Viewer) -> ReminderState:
    last = None
    if st.last is not None:
        r = st.last
        mine = not r.automatic and ((v.club_id is not None and r.sender_club_id == v.club_id) or r.sender_user_id == v.user_id)
        last = LastReminder(at=r.created_at, by=await _by(db, s, r), escalated=r.escalated, note=r.note, by_you=mine)
    return ReminderState(
        holder=ReminderHolder(kind=st.holder.kind, name=st.holder.name) if st.holder else None,
        waiting_since=st.waiting_since, can_send=st.can_send, reason=st.reason,
        next_allowed_at=st.next_allowed_at, would_escalate=st.would_escalate,
        preview=st.preview, last=last,
    )


@router.get("/{subject_type}/{subject_id}", response_model=ReminderState)
async def get_state(
    subject_type: str, subject_id: uuid.UUID,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
) -> ReminderState:
    s, v = await _load(db, user, subject_type, subject_id)
    return await _response(db, s, await service.state_for(db, s, v), v)


@router.post("/{subject_type}/{subject_id}", response_model=ReminderState)
async def send_reminder(
    subject_type: str, subject_id: uuid.UUID, body: SendReminder,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
) -> ReminderState:
    s, v = await _load(db, user, subject_type, subject_id)
    try:
        await service.send(db, s, v, note=body.note)
    except service.ReminderError as exc:
        raise HTTPException(exc.status_code, exc.detail)
    await db.commit()
    return await _response(db, s, await service.state_for(db, s, v), v)
