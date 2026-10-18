"""TransferX staff stepping into a deal that has stuck (admin panel).

A deal can stall with no way out: the other club goes quiet, a step waits
on a player with no account, or the clubs disagree about the medical. Each
tool here goes through the deal's own service function, so money, locks and
the stage machine behave exactly as when a club acts, and on top of that:

- it needs a reason, recorded in the admin audit log (`admin.deal.*`);
- both clubs are told what staff did and why.

Tools: collapse, move on a stage, complete, extend the completion deadline,
record a paperwork step for one side, and record the medical.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

PAPERWORK_FOR = {
    # admin step: (deals.service step, which club it's recorded for)
    "buyer_signs_agreement": ("sign-agreement", "buyer"),
    "seller_signs_agreement": ("sign-agreement", "seller"),
    "registration_submitted": ("submit-registration", "buyer"),
}
PAPERWORK_LABEL = {
    "buyer_signs_agreement": "recorded the buying club's signature on the transfer agreement",
    "seller_signs_agreement": "recorded the selling club's signature on the transfer agreement",
    "registration_submitted": "recorded the registration as submitted",
}


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def _deal(db: AsyncSession, deal_id: uuid.UUID):
    from app.deals import service as deals_service

    deal = await deals_service.get_deal_by_id(db, deal_id)
    if deal is None:
        raise LookupError("Deal not found")
    return deal


def _open(deal) -> None:
    from app.deals.models import DealStatus

    if deal.status not in (DealStatus.IN_PROGRESS, DealStatus.PENDING_COMPLETION):
        raise ValueError(f"This deal is {deal.status.value.lower().replace('_', ' ')}, so there's nothing to change.")


async def _record_and_tell(db: AsyncSession, admin, deal, *, action: str, what: str, reason: str,
                           ntype=None, details: dict | None = None) -> None:
    """The admin audit event, and a notification to both clubs with the reason."""
    from app.admin import audit as admin_audit
    from app.notifications import service as notif_service
    from app.notifications.models import NotificationType

    player = deal.player.name if deal.player else "the player"
    await admin_audit.record(
        db, admin, f"deal.{action}", entity_type="DEAL", entity_id=deal.id, reason=reason,
        description=f"TransferX staff {what} ({player})", details=details or {},
    )
    for club_id in {deal.buyer_club_id, deal.seller_club_id} - {None}:
        await notif_service.notify_club(
            db, uuid.UUID(str(club_id)), type=ntype or NotificationType.DEAL_PAPERWORK,
            message=f"TransferX staff {what} on the deal for {player}: {reason}",
            link=f"/deals/{deal.id}", related_player_id=deal.player_id,
        )


async def collapse(db: AsyncSession, admin, deal_id: uuid.UUID, *, reason: str):
    """End the deal for both clubs. The buyer's committed budget is released
    and a listing it came from reopens, as when a club collapses it."""
    from app.deals import service as deals_service
    from app.notifications.models import NotificationType

    deal = await _deal(db, deal_id)
    _open(deal)
    stage = deal.stage.value
    await deals_service.staff_collapse(db, deal, actor_user_id=admin.id)
    await _record_and_tell(db, admin, deal, action="collapsed", what="collapsed the deal", reason=reason,
                           ntype=NotificationType.DEAL_COLLAPSED, details={"stage": stage})
    return deal


async def advance(db: AsyncSession, admin, deal_id: uuid.UUID, *, reason: str):
    """Move the deal on one stage, by the stage machine's own rules."""
    from app.deals import service as deals_service

    deal = await _deal(db, deal_id)
    _open(deal)
    before = deal.stage.value
    await deals_service.advance_deal(db, deal, is_staff=True, actor_user_id=admin.id)
    after = deal.stage.value
    label = after.replace("_", " ").lower()
    await _record_and_tell(db, admin, deal, action="advanced", what=f"moved the deal on to {label}", reason=reason,
                           details={"from_stage": before, "to_stage": after})
    return deal


async def complete(db: AsyncSession, admin, deal_id: uuid.UUID, *, reason: str):
    """Complete the transfer now: the fee settles, the player joins the
    buying club. For a deal whose last steps happened outside TransferX."""
    from app.deals import service as deals_service
    from app.notifications.models import NotificationType

    deal = await _deal(db, deal_id)
    _open(deal)
    stage = deal.stage.value
    await deals_service.staff_complete(db, deal, actor_user_id=admin.id)
    await _record_and_tell(db, admin, deal, action="completed", what="completed the transfer", reason=reason,
                           ntype=NotificationType.DEAL_COMPLETED, details={"from_stage": stage})
    return deal


async def extend_deadline(db: AsyncSession, admin, deal_id: uuid.UUID, *, until: datetime, reason: str):
    """Move the completion deadline of a deal awaiting completion. Clears the
    overdue flag, so the overnight check flags it again if the new date passes."""
    from app.deals.models import DealStatus

    deal = await _deal(db, deal_id)
    _open(deal)
    if deal.status != DealStatus.PENDING_COMPLETION or deal.sla_deadline is None:
        raise ValueError("Only a deal awaiting completion has a completion deadline.")
    until = _aware(until)
    if until <= datetime.now(timezone.utc):
        raise ValueError("The new deadline must be in the future.")
    before = _aware(deal.sla_deadline)
    deal.sla_deadline = until
    deal.sla_escalated_at = None
    await db.flush()
    await _record_and_tell(db, admin, deal, action="deadline_extended",
                           what=f"moved the completion deadline to {until:%d %b %Y %H:%M} UTC", reason=reason,
                           details={"from": before, "to": until})
    return deal


async def record_paperwork(db: AsyncSession, admin, deal_id: uuid.UUID, *, step: str, reason: str):
    """Tick a paperwork step for one club, e.g. a signature made on paper
    that the club hasn't recorded. The checklist moves on exactly as if the
    club had ticked it, finishing the paperwork when it's the last step."""
    from app.deals import service as deals_service

    if step not in PAPERWORK_FOR:
        raise ValueError(f"Unknown paperwork step: {step}")
    deal = await _deal(db, deal_id)
    _open(deal)
    service_step, side = PAPERWORK_FOR[step]
    club_id = deal.buyer_club_id if side == "buyer" else deal.seller_club_id
    if club_id is None:
        raise ValueError("This deal has no selling club, so it has no seller signature.")
    try:
        await deals_service.complete_paperwork_step(db, deal, service_step, actor_club_id=club_id,
                                                    actor_user_id=admin.id)
    except PermissionError as exc:
        raise ValueError(str(exc))
    await _record_and_tell(db, admin, deal, action="paperwork_recorded", what=PAPERWORK_LABEL[step], reason=reason,
                           details={"step": step})
    return deal


async def record_medical(db: AsyncSession, admin, deal_id: uuid.UUID, *, outcome: str, notes: str | None, reason: str):
    """Record or correct the medical, e.g. to settle a dispute between the
    clubs. A pass can finish the paperwork; a fail blocks the deal."""
    from app.deals import service as deals_service
    from app.deals.models import MedicalStatus

    deal = await _deal(db, deal_id)
    _open(deal)
    try:
        status = MedicalStatus(outcome)
    except ValueError:
        raise ValueError("The medical is PASSED, FAILED or PENDING.")
    await deals_service.upsert_medical_check(db, deal, status=status, notes=notes, is_staff=True,
                                             actor_user_id=admin.id)
    await _record_and_tell(db, admin, deal, action="medical_recorded",
                           what=f"recorded the medical as {status.value.lower()}", reason=reason,
                           details={"outcome": status.value, "notes": notes})
    return deal
