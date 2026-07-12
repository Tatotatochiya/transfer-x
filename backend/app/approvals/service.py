"""Spending-authority approvals — capture, decide, execute (Phase 5 / D7).

Capture happens inside the four money-committing actions after their request
validation; execution replays the stored payload through the *same* service
calls, so budget, transfer window, and auction state are all re-validated
fresh. A stale approval fails soft into APPROVED_FAILED with a reason — never
a 500, never a partial execution.
"""
import logging
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.approvals.models import ApprovalActionType, ApprovalStatus, PendingApproval
from app.auth.models import User
from app.clubs.models import Club
from app.notifications.models import NotificationType

logger = logging.getLogger(__name__)

APPROVAL_TTL_HOURS = 24


# ── Capture ───────────────────────────────────────────────────────────────────


async def maybe_capture(
    db: AsyncSession,
    *,
    current_user: User,
    club: Club,
    action_type: ApprovalActionType,
    amount: Decimal,
    payload: dict,
    summary: str | None = None,
) -> PendingApproval | None:
    """Capture the action as a pending approval if it must be escalated,
    else return None (caller executes normally).

    Escalates only when: the caller is MANAGER-role staff (owner and
    SPORTING_DIRECTOR are exempt — D7), the club has a threshold set, and
    amount ≥ threshold. Superusers are never escalated (bypass-first).
    """
    if current_user.is_superuser:
        return None
    from app.clubs import service as clubs_service

    role = await clubs_service.get_club_membership_role(db, uuid.UUID(str(current_user.id)))
    if role != "MANAGER":
        return None
    threshold = club.finance.approval_threshold if club.finance else None
    if threshold is None or Decimal(amount) < threshold:
        return None

    approval = PendingApproval(
        club_id=uuid.UUID(str(club.id)),
        action_type=action_type,
        payload_json=payload,
        amount=Decimal(str(amount)),
        requested_by_user_id=uuid.UUID(str(current_user.id)),
        status=ApprovalStatus.PENDING,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=APPROVAL_TTL_HOURS),
        summary=summary,
    )
    db.add(approval)
    await db.flush()
    await _notify_approvers(db, approval, club)
    return approval


async def _notify_approvers(db: AsyncSession, approval: PendingApproval, club: Club) -> None:
    """D5: approval requests reach OWNER + SPORTING_DIRECTORs."""
    from app.clubs.models import ClubStaff, StaffRole
    from app.notifications.service import create_notification

    recipient_ids = [club.user_id]
    staff_result = await db.execute(
        select(ClubStaff.user_id).where(
            ClubStaff.club_id == uuid.UUID(str(club.id)),
            ClubStaff.role == StaffRole.SPORTING_DIRECTOR,
        )
    )
    recipient_ids += [uuid.UUID(str(uid)) for uid in staff_result.scalars()]
    for uid in recipient_ids:
        await create_notification(
            db,
            recipient_user_id=uid,
            type=NotificationType.APPROVAL_REQUESTED,
            message=f"Approval needed: {approval.summary or approval.action_type.value} (£{approval.amount:,.0f})",
            link="/club/approvals",
        )


async def _notify_requester(
    db: AsyncSession, approval: PendingApproval, message: str
) -> None:
    from app.notifications.service import create_notification

    await create_notification(
        db,
        recipient_user_id=uuid.UUID(str(approval.requested_by_user_id)),
        type=NotificationType.APPROVAL_DECIDED,
        message=message,
        link="/club/approvals",
    )


# ── Queries ───────────────────────────────────────────────────────────────────


async def get_approval(
    db: AsyncSession, approval_id: uuid.UUID, club_id: uuid.UUID
) -> PendingApproval | None:
    result = await db.execute(
        select(PendingApproval).where(
            PendingApproval.id == uuid.UUID(str(approval_id)),
            PendingApproval.club_id == uuid.UUID(str(club_id)),
        )
    )
    return result.scalar_one_or_none()


async def list_approvals(
    db: AsyncSession,
    club_id: uuid.UUID,
    *,
    status: ApprovalStatus | None = None,
    requested_by_user_id: uuid.UUID | None = None,
) -> list[PendingApproval]:
    q = select(PendingApproval).where(PendingApproval.club_id == uuid.UUID(str(club_id)))
    if status is not None:
        q = q.where(PendingApproval.status == status)
    if requested_by_user_id is not None:
        q = q.where(PendingApproval.requested_by_user_id == uuid.UUID(str(requested_by_user_id)))
    result = await db.execute(q.order_by(PendingApproval.created_at.desc()))
    return list(result.scalars())


def _require_pending(approval: PendingApproval) -> None:
    """The status machine is one-way — any second transition is a conflict."""
    if approval.status != ApprovalStatus.PENDING:
        raise PermissionError(f"Approval already {approval.status.value}")


# ── Decisions ─────────────────────────────────────────────────────────────────


async def reject_approval(
    db: AsyncSession, approval: PendingApproval, decided_by: User, reason: str | None
) -> PendingApproval:
    _require_pending(approval)
    approval.status = ApprovalStatus.REJECTED
    approval.decided_by_user_id = uuid.UUID(str(decided_by.id))
    approval.decided_at = datetime.now(timezone.utc)
    approval.failure_reason = reason
    await db.flush()
    await _notify_requester(
        db, approval,
        f"Your {approval.action_type.value.replace('_', ' ').lower()} (£{approval.amount:,.0f}) was rejected"
        + (f": {reason}" if reason else ""),
    )
    return approval


async def cancel_approval(db: AsyncSession, approval: PendingApproval, actor: User) -> PendingApproval:
    """Requester withdraws their own pending request."""
    if uuid.UUID(str(approval.requested_by_user_id)) != uuid.UUID(str(actor.id)):
        raise PermissionError("Only the requester can cancel their own approval request")
    _require_pending(approval)
    approval.status = ApprovalStatus.CANCELLED
    approval.decided_at = datetime.now(timezone.utc)
    await db.flush()
    return approval


async def approve_and_execute(
    db: AsyncSession, approval: PendingApproval, decided_by: User
) -> PendingApproval:
    """Execute the captured action with everything re-validated fresh (D7).

    Success → APPROVED_EXECUTED; any domain failure (auction closed, outbid,
    budget insufficient, window shut, entity deleted) → APPROVED_FAILED with
    the reason recorded and both parties notified. Never raises for domain
    failures; raises PermissionError only for status-machine violations.
    """
    _require_pending(approval)
    approval.decided_by_user_id = uuid.UUID(str(decided_by.id))
    approval.decided_at = datetime.now(timezone.utc)

    try:
        await _execute(db, approval)
    except ValueError as exc:
        approval.status = ApprovalStatus.APPROVED_FAILED
        approval.failure_reason = str(exc)
        await db.flush()
        await _notify_requester(
            db, approval,
            f"Approved, but execution failed: {exc}",
        )
        from app.notifications.service import create_notification
        await create_notification(
            db,
            recipient_user_id=uuid.UUID(str(decided_by.id)),
            type=NotificationType.APPROVAL_DECIDED,
            message=f"Execution failed after your approval: {exc}",
            link="/club/approvals",
        )
        return approval

    approval.status = ApprovalStatus.APPROVED_EXECUTED
    await db.flush()
    await _notify_requester(
        db, approval,
        f"Your {approval.action_type.value.replace('_', ' ').lower()} (£{approval.amount:,.0f}) was approved and executed",
    )
    return approval


async def _execute(db: AsyncSession, approval: PendingApproval) -> None:
    """Replay the stored payload through the same service calls the direct
    path uses — their validations (and only theirs) decide success."""
    payload = approval.payload_json or {}
    club_id = uuid.UUID(str(approval.club_id))

    if approval.action_type == ApprovalActionType.PLACE_BID:
        from app.notifications.service import notify_club
        from app.sales import service as sales_service

        sale_id = uuid.UUID(payload["sale_id"])
        await sales_service.place_bid(
            db,
            sale_id=sale_id,
            buyer_club_id=club_id,
            amount=Decimal(payload["amount"]),
            wage_offer_weekly=Decimal(payload["wage_offer_weekly"]) if payload.get("wage_offer_weekly") else None,
            notes=payload.get("notes"),
        )
        sale = await sales_service.get_sale_by_id(db, sale_id)
        if sale:
            player_name = sale.player.name if sale.player else "a player"
            await notify_club(
                db,
                uuid.UUID(str(sale.seller_club_id)),
                type=NotificationType.AUCTION_BID_RECEIVED,
                message=f"New bid received on {player_name}",
                link=f"/sales/{sale_id}",
                related_player_id=sale.player_id,
            )

    elif approval.action_type == ApprovalActionType.CREATE_OFFER:
        from app.clubs import service as clubs_service
        from app.notifications.service import notify_club
        from app.offers import service as offers_service
        from app.transfer_window import service as window_service

        # Router-level guards, re-checked fresh (D7).
        _club = await clubs_service.get_club_by_id(db, club_id)
        _association = _club.country if _club else None
        if not await window_service.is_transfer_allowed(db, association=_association):
            raise ValueError("Transfer window is closed")
        player_id = uuid.UUID(payload["player_id"])
        existing = await offers_service.get_active_offer_for_buyer(db, player_id, club_id)
        if existing:
            raise ValueError("The club already has an active offer for this player")
        from app.deals import service as deals_service
        active_deal = await deals_service.get_active_deal_for_player(db, player_id)
        if active_deal and active_deal.status == "IN_PROGRESS":
            raise ValueError("This player already has a transfer deal in progress")

        offer = await offers_service.create_offer(
            db,
            player_id=player_id,
            from_club_id=club_id,
            to_club_id=uuid.UUID(payload["to_club_id"]) if payload.get("to_club_id") else None,
            sale_id=uuid.UUID(payload["sale_id"]) if payload.get("sale_id") else None,
            fee_amount=Decimal(payload["fee_amount"]),
            wage_weekly=Decimal(payload["wage_weekly"]) if payload.get("wage_weekly") else None,
            contract_years=payload.get("contract_years"),
            contract_end_date=datetime.fromisoformat(payload["contract_end_date"]).date()
            if payload.get("contract_end_date") else None,
            add_ons=payload.get("add_ons"),
            expires_at=datetime.fromisoformat(payload["expires_at"])
            if payload.get("expires_at") else None,
        )
        if offer.to_club_id:
            await notify_club(
                db,
                uuid.UUID(str(offer.to_club_id)),
                type=NotificationType.OFFER_RECEIVED,
                message="You have received a new offer",
                link=f"/offers/{offer.id}",
                related_player_id=offer.player_id,
            )

    elif approval.action_type == ApprovalActionType.ACCEPT_OFFER:
        from app.notifications.service import notify_club
        from app.offers import service as offers_service

        offer = await offers_service.get_offer_by_id(db, uuid.UUID(payload["offer_id"]))
        if offer is None:
            raise ValueError("The offer no longer exists")
        await offers_service.accept_offer(db, offer, actor_club_id=club_id)
        if offer.from_club_id:
            await notify_club(
                db,
                uuid.UUID(str(offer.from_club_id)),
                type=NotificationType.OFFER_ACCEPTED,
                message="Your offer has been accepted",
                link=f"/offers/{offer.id}",
                related_player_id=offer.player_id,
            )

    elif approval.action_type == ApprovalActionType.ACCEPT_BID:
        from app.notifications.service import notify_club
        from app.sales import service as sales_service

        deal = await sales_service.accept_bid(
            db,
            sale_id=uuid.UUID(payload["sale_id"]),
            bid_id=uuid.UUID(payload["bid_id"]),
            actor_club_id=club_id,
        )
        sale = await sales_service.get_sale_by_id(db, uuid.UUID(payload["sale_id"]))
        player_name = sale.player.name if sale and sale.player else "a player"
        await notify_club(
            db,
            uuid.UUID(str(deal.buyer_club_id)),
            type=NotificationType.AUCTION_BID_ACCEPTED,
            message=f"Your bid on {player_name} has been accepted",
            link=f"/deals/{deal.id}",
            related_player_id=deal.player_id,
        )

    else:  # pragma: no cover — enum is exhaustive
        raise ValueError(f"Unknown approval action type {approval.action_type}")


# ── Expiry job ────────────────────────────────────────────────────────────────


async def expire_stale_approvals(db: AsyncSession) -> int:
    """Daily job: PENDING approvals past their expires_at → EXPIRED, requester notified."""
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(PendingApproval).where(PendingApproval.status == ApprovalStatus.PENDING)
    )
    count = 0
    for approval in result.scalars():
        expires = approval.expires_at
        if expires.tzinfo is None:  # SQLite drops tzinfo
            expires = expires.replace(tzinfo=timezone.utc)
        if expires <= now:
            approval.status = ApprovalStatus.EXPIRED
            approval.decided_at = now
            await db.flush()
            await _notify_requester(
                db, approval,
                f"Your {approval.action_type.value.replace('_', ' ').lower()} "
                f"(£{approval.amount:,.0f}) expired without a decision",
            )
            count += 1
    return count
