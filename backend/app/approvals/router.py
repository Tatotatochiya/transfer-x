"""Spending-authority approval endpoints (Phase 5).

Decision endpoints are APPROVE_ACTIONS (owner + sporting director); the
requester may cancel their own pending request; the threshold policy is
TEAM_MANAGE (owner only).
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.approvals import service
from app.approvals.models import ApprovalStatus, PendingApproval
from app.approvals.schemas import (
    ApprovalPolicyResponse,
    ApprovalPolicyUpdateRequest,
    ApprovalRejectRequest,
    PendingApprovalResponse,
)
from app.auth.models import User
from app.clubs import service as clubs_service
from app.clubs.capabilities import Capability, ensure_club_capability, require_club_capability
from app.database import get_db
from app.deps import get_current_user

router = APIRouter(tags=["approvals"])

_approve_actions = require_club_capability(Capability.APPROVE_ACTIONS)
_team_manage = require_club_capability(Capability.TEAM_MANAGE)


async def _get_club_or_403(db: AsyncSession, user: User):
    club = await clubs_service.get_club_for_user(db, user.id)
    if club is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No club profile")
    return club


async def _to_response(db: AsyncSession, approval: PendingApproval) -> PendingApprovalResponse:
    resp = PendingApprovalResponse.model_validate(approval)
    requester = await db.get(User, approval.requested_by_user_id) if approval.requested_by_user_id else None
    resp.requested_by_email = requester.email if requester else None
    resp.requested_by_name = requester.full_name if requester else None
    return resp


@router.get("/clubs/me/approvals", response_model=list[PendingApprovalResponse])
async def list_approvals(
    approval_status: ApprovalStatus | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """APPROVE_ACTIONS holders see the club's full queue; other members see
    only requests they made themselves (their 'pending approval' page state)."""
    club = await _get_club_or_403(db, current_user)
    try:
        await ensure_club_capability(db, current_user, Capability.APPROVE_ACTIONS)
        requester_filter = None
    except HTTPException:
        requester_filter = current_user.id
    approvals = await service.list_approvals(
        db, club.id, status=approval_status, requested_by_user_id=requester_filter
    )
    return [await _to_response(db, a) for a in approvals]


@router.get("/clubs/me/approvals/{approval_id}", response_model=PendingApprovalResponse)
async def get_approval(
    approval_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """One approval, for its decision sheet: the player and the budget after.
    Deciders see any of the club's; others only their own requests."""
    from app.approvals.models import ApprovalActionType as A
    from app.clubs.models import ClubFinance
    from app.notifications.copy import approval_player

    club = await _get_club_or_403(db, current_user)
    approval = await service.get_approval(db, approval_id, club.id)
    if approval is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval not found")
    try:
        await ensure_club_capability(db, current_user, Capability.APPROVE_ACTIONS)
    except HTTPException:
        if approval.requested_by_user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval not found")
    resp = await _to_response(db, approval)
    resp.player_id, resp.player_name = await approval_player(db, approval)
    if approval.action_type in (A.PLACE_BID, A.CREATE_OFFER, A.EXERCISE_OPTION):
        finance = (await db.execute(select(ClubFinance).where(ClubFinance.club_id == club.id))).scalar_one_or_none()
        if finance is not None:
            resp.budget_after = max(finance.transfer_remaining - approval.amount, 0)
    return resp


@router.post("/clubs/me/approvals/{approval_id}/approve", response_model=PendingApprovalResponse)
async def approve_approval(
    approval_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _cap: User = Depends(_approve_actions),
):
    club = await _get_club_or_403(db, current_user)
    approval = await service.get_approval(db, approval_id, club.id)
    if approval is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval not found")
    try:
        approval = await service.approve_and_execute(db, approval, current_user)
        await db.commit()
    except PermissionError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    await db.refresh(approval)
    return await _to_response(db, approval)


@router.post("/clubs/me/approvals/{approval_id}/reject", response_model=PendingApprovalResponse)
async def reject_approval(
    approval_id: uuid.UUID,
    body: ApprovalRejectRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _cap: User = Depends(_approve_actions),
):
    club = await _get_club_or_403(db, current_user)
    approval = await service.get_approval(db, approval_id, club.id)
    if approval is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval not found")
    try:
        approval = await service.reject_approval(db, approval, current_user, body.reason)
        await db.commit()
    except PermissionError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    await db.refresh(approval)
    return await _to_response(db, approval)


@router.post("/clubs/me/approvals/{approval_id}/cancel", response_model=PendingApprovalResponse)
async def cancel_approval(
    approval_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Requester withdraws their own pending request — no capability needed
    beyond membership; the service enforces requester identity."""
    club = await _get_club_or_403(db, current_user)
    approval = await service.get_approval(db, approval_id, club.id)
    if approval is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval not found")
    try:
        approval = await service.cancel_approval(db, approval, current_user)
        await db.commit()
    except PermissionError as exc:
        await db.rollback()
        code = status.HTTP_409_CONFLICT if "already" in str(exc) else status.HTTP_403_FORBIDDEN
        raise HTTPException(status_code=code, detail=str(exc))
    await db.refresh(approval)
    return await _to_response(db, approval)


# ── Threshold policy (TEAM_MANAGE) ────────────────────────────────────────────


@router.get("/clubs/me/approval-policy", response_model=ApprovalPolicyResponse)
async def get_approval_policy(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _cap: User = Depends(_team_manage),
):
    club = await _get_club_or_403(db, current_user)
    threshold = club.finance.approval_threshold if club.finance else None
    return ApprovalPolicyResponse(approval_threshold=threshold)


@router.patch("/clubs/me/approval-policy", response_model=ApprovalPolicyResponse)
async def set_approval_policy(
    body: ApprovalPolicyUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _cap: User = Depends(_team_manage),
):
    """Set (or clear, with null) the club's single approval threshold (D7)."""
    club = await _get_club_or_403(db, current_user)
    if club.finance is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Club finance record not found")
    if body.approval_threshold is not None and body.approval_threshold < 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Threshold cannot be negative")
    club.finance.approval_threshold = body.approval_threshold
    await db.commit()
    return ApprovalPolicyResponse(approval_threshold=body.approval_threshold)
