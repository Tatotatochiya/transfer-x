"""Loan endpoints — feature_spec/loan-transfers.md phase 3.

Read endpoints so a loan is visible (nothing could display "out on loan" before
these existed), plus recall. Every route is scoped to the caller's own club:
the two parties see the loan, a third club gets a 404 rather than a 403, since
whether a loan exists at all is not theirs to learn.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.models import User
from app.clubs import service as clubs_service
from app.clubs.capabilities import Capability, require_club_capability
from app.database import get_db
from app.deps import get_current_user
from app.loans import service
from app.loans.models import LoanStatus, PlayerLoan
from app.loans.schemas import LoanResponse

router = APIRouter(tags=["loans"])

# Recalling a player is a squad action with financial consequences on both
# sides — the same capability gate the rest of the market uses.
_market_write = require_club_capability(Capability.MARKET_WRITE)

_LOAN_OPTS = [
    selectinload(PlayerLoan.player),
    selectinload(PlayerLoan.parent_club),
    selectinload(PlayerLoan.loanee_club),
]


async def _club_or_403(db: AsyncSession, current_user: User):
    club = await clubs_service.get_club_for_user(db, current_user.id)
    if club is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="No club profile found"
        )
    return club


def _to_response(loan: PlayerLoan, viewer_club_id: uuid.UUID | None) -> LoanResponse:
    resp = LoanResponse.model_validate(loan)
    if viewer_club_id is not None:
        if loan.parent_club_id == viewer_club_id:
            resp.direction = "out"
        elif loan.loanee_club_id == viewer_club_id:
            resp.direction = "in"
    return resp


@router.get("/clubs/me/loans", response_model=list[LoanResponse])
async def list_my_loans(
    direction: str | None = Query(None, pattern="^(out|in)$"),
    status_filter: LoanStatus | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Loans this club is a party to. `out` = players we own who are away,
    `in` = players we have borrowed. Defaults to ACTIVE only, because the
    squad views that consume this only care about live ones."""
    club = await _club_or_403(db, current_user)

    q = select(PlayerLoan).options(*_LOAN_OPTS)
    if direction == "out":
        q = q.where(PlayerLoan.parent_club_id == club.id)
    elif direction == "in":
        q = q.where(PlayerLoan.loanee_club_id == club.id)
    else:
        q = q.where(
            or_(
                PlayerLoan.parent_club_id == club.id,
                PlayerLoan.loanee_club_id == club.id,
            )
        )
    q = q.where(PlayerLoan.status == (status_filter or LoanStatus.ACTIVE))

    rows = (await db.execute(q.order_by(PlayerLoan.end_date))).scalars().all()
    return [_to_response(row, club.id) for row in rows]


@router.get("/loans/{loan_id}", response_model=LoanResponse)
async def get_loan(
    loan_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    loan = (
        await db.execute(
            select(PlayerLoan).where(PlayerLoan.id == loan_id).options(*_LOAN_OPTS)
        )
    ).scalar_one_or_none()
    if loan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loan not found")

    if current_user.is_superuser:
        return _to_response(loan, None)

    club = await clubs_service.get_club_for_user(db, current_user.id)
    if club is None or club.id not in (loan.parent_club_id, loan.loanee_club_id):
        # 404 rather than 403: a third club should not learn the loan exists.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loan not found")
    return _to_response(loan, club.id)


@router.post("/loans/{loan_id}/recall", response_model=LoanResponse)
async def recall(
    loan_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _write: User = Depends(_market_write),
):
    """Parent club ends a loan early. Not window-gated (D8) — a loan ending is
    the agreement running its course, not a new transfer."""
    loan = (
        await db.execute(
            select(PlayerLoan).where(PlayerLoan.id == loan_id).options(*_LOAN_OPTS)
        )
    ).scalar_one_or_none()
    if loan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loan not found")

    club = await _club_or_403(db, current_user)
    if club.id not in (loan.parent_club_id, loan.loanee_club_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loan not found")

    try:
        await service.recall_player(db, loan, actor_club_id=club.id)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    await db.commit()
    # Re-query rather than refresh: commit expires the instance, and a plain
    # refresh does not restore the eager loads the response needs — the
    # relationship access would then lazy-load on an async session and raise
    # MissingGreenlet.
    loan = (
        await db.execute(
            select(PlayerLoan).where(PlayerLoan.id == loan_id).options(*_LOAN_OPTS)
        )
    ).scalar_one()
    return _to_response(loan, club.id)
