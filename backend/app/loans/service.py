"""Loan lifecycle — feature_spec/loan-transfers.md phase 2.

Two operations live here: starting a loan (called from `_complete_deal` when a
LOAN deal completes) and ending one. Ending is deliberately a single function
with a reason, because every way a loan can end — running to term, an early
recall, the parent selling the player — has to unwind the same finance and the
same contracts. Phase 3's expiry job and recall endpoint call `end_loan` too.
"""
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app import clubs as clubs_module
from app.audit import service as audit_service
from app.clubs.models import Club
from app.loans.models import LoanEndReason, LoanStatus, PlayerLoan
from app.notifications import service as notif_service
from app.notifications.models import NotificationType
from app.players.models import Contract, Player

# How far ahead both clubs are warned that a loan is running out. Two weeks is
# enough to plan a return or open a renewal without becoming background noise.
LOAN_ENDING_SOON_DAYS = 14


async def _notify_both_clubs(
    db: AsyncSession,
    loan: PlayerLoan,
    *,
    type: NotificationType,
    message: str,
) -> None:
    """Both sides of a loan care about every event in its life."""
    clubs = (
        await db.execute(
            select(Club).where(Club.id.in_([loan.parent_club_id, loan.loanee_club_id]))
        )
    ).scalars().all()
    for club in clubs:
        if club.user_id is None:
            continue
        await notif_service.create_notification(
            db,
            recipient_user_id=club.user_id,
            type=type,
            message=message,
            link=f"/players/market/{loan.player_id}",
            related_player_id=loan.player_id,
        )


async def get_active_loan(db: AsyncSession, player_id: uuid.UUID) -> PlayerLoan | None:
    """The loan currently holding this player's registration, if any."""
    result = await db.execute(
        select(PlayerLoan).where(
            PlayerLoan.player_id == uuid.UUID(str(player_id)),
            PlayerLoan.status == LoanStatus.ACTIVE,
        )
    )
    return result.scalars().first()


async def get_active_loans_for_players(
    db: AsyncSession, player_ids: list[uuid.UUID]
) -> dict[uuid.UUID, PlayerLoan]:
    """Active loans for a list of players in one query — no N+1 for squad views."""
    if not player_ids:
        return {}
    ids = [uuid.UUID(str(p)) for p in player_ids]
    result = await db.execute(
        select(PlayerLoan).where(
            PlayerLoan.player_id.in_(ids), PlayerLoan.status == LoanStatus.ACTIVE
        )
    )
    return {row.player_id: row for row in result.scalars()}


async def start_loan(
    db: AsyncSession,
    *,
    deal,
    player: Player,
    parent_contract: Contract | None,
    loanee_contract: Contract,
    loanee_wage_share: Decimal,
) -> PlayerLoan:
    """Record the loan created by a completing LOAN deal.

    The contract swap itself is done by the caller (`_complete_deal`), because
    it has to happen in the same unit of work as the finance settlement. This
    function records what happened, including the pointer back to the parent's
    suspended contract that makes the return a restore.
    """
    loan = PlayerLoan(
        player_id=uuid.UUID(str(player.id)),
        deal_id=uuid.UUID(str(deal.id)),
        parent_club_id=deal.seller_club_id,
        loanee_club_id=deal.buyer_club_id,
        parent_contract_id=parent_contract.id if parent_contract else None,
        loanee_contract_id=loanee_contract.id,
        start_date=deal.loan_start,
        end_date=deal.loan_end,
        loan_fee=deal.loan_fee,
        wage_split_pct=deal.wage_split_pct,
        loanee_wage_share=loanee_wage_share,
        option_to_buy=deal.option_to_buy,
        obligation_to_buy=deal.obligation_to_buy,
        recall_allowed=deal.recall_allowed,
        status=LoanStatus.ACTIVE,
    )
    db.add(loan)
    await db.flush()

    await audit_service.emit(
        db,
        entity_type="LOAN", entity_id=loan.id,
        action="LOAN_STARTED",
        payload={
            "player_id": str(player.id),
            "parent_club_id": str(deal.seller_club_id),
            "loanee_club_id": str(deal.buyer_club_id),
            "end_date": str(deal.loan_end),
            "loanee_wage_share": str(loanee_wage_share),
        },
        description=f"Loan started — returns {deal.loan_end}",
    )
    await _notify_both_clubs(
        db, loan,
        type=NotificationType.LOAN_STARTED,
        message=f"{player.name} is on loan until {deal.loan_end:%d %b %Y}",
    )
    return loan


async def end_loan(
    db: AsyncSession,
    loan: PlayerLoan,
    *,
    reason: LoanEndReason,
    restore_parent: bool = True,
) -> PlayerLoan:
    """End a loan and unwind it.

    `restore_parent=False` is for the cases where the player is not going back
    — the parent sold him, or the loanee bought him. There the caller is about
    to run a permanent transfer that will create the new owner's contract, so
    restoring the parent's would immediately be undone and would briefly leave
    two active contracts, which `normalize_player_status` cannot represent.

    The parent's contract is only restored if it has not expired in the
    meantime. If it has, the player becomes a free agent — correct, and the
    single path in this feature that can turn a squad player into one, which is
    why offer validation refuses a loan that outlasts the parent contract.
    """
    if loan.status != LoanStatus.ACTIVE:
        raise ValueError(f"Loan is already {loan.status.value}")

    now = datetime.now(timezone.utc)
    today = now.date()

    player = (
        await db.execute(select(Player).where(Player.id == loan.player_id))
    ).scalar_one()

    # Loanee: stop paying their share and give up the registration.
    loanee_fin = await clubs_module.service.get_finance_for_update(db, loan.loanee_club_id)
    if loanee_fin and loan.loanee_wage_share > 0:
        loanee_fin.wage_reserved_weekly = max(
            Decimal("0"), loanee_fin.wage_reserved_weekly - loan.loanee_wage_share
        )
    if loan.loanee_contract_id is not None:
        await db.execute(
            update(Contract)
            .where(Contract.id == loan.loanee_contract_id)
            .values(is_active=False)
        )

    parent_contract = None
    if loan.parent_contract_id is not None:
        parent_contract = (
            await db.execute(select(Contract).where(Contract.id == loan.parent_contract_id))
        ).scalar_one_or_none()

    if restore_parent:
        expired = (
            parent_contract is not None
            and parent_contract.end_date is not None
            and parent_contract.end_date < today
        )
        if parent_contract is not None and not expired:
            parent_contract.is_active = True
            # The parent picks the share back up. Their finance kept only the
            # portion they were paying during the loan, so this restores the
            # difference rather than the whole wage.
            parent_fin = await clubs_module.service.get_finance_for_update(
                db, loan.parent_club_id
            )
            if parent_fin and loan.loanee_wage_share > 0:
                parent_fin.wage_reserved_weekly += loan.loanee_wage_share
    else:
        # Not going home: release whatever the parent was still carrying, since
        # the permanent transfer about to run reads the seller's *active*
        # contract for that figure and will find none.
        parent_fin = await clubs_module.service.get_finance_for_update(
            db, loan.parent_club_id
        )
        if parent_fin and parent_contract is not None and parent_contract.wage_weekly:
            retained = max(
                Decimal("0"), parent_contract.wage_weekly - loan.loanee_wage_share
            )
            if retained > 0:
                parent_fin.wage_reserved_weekly = max(
                    Decimal("0"), parent_fin.wage_reserved_weekly - retained
                )

    loan.status = (
        LoanStatus.CONVERTED
        if reason in (LoanEndReason.OPTION_EXERCISED, LoanEndReason.OBLIGATION, LoanEndReason.PARENT_SOLD)
        else LoanStatus.RECALLED
        if reason == LoanEndReason.RECALLED
        else LoanStatus.COMPLETED
    )
    loan.ended_at = now
    loan.end_reason = reason.value
    await db.flush()

    # Only normalize when the player is actually settling somewhere now. In the
    # not-going-home cases the caller creates the new owner's contract straight
    # after, and normalizing here would briefly mark him a free agent.
    if restore_parent:
        from app.players import service as players_service

        await players_service.normalize_player_status(db, player)

    await audit_service.emit(
        db,
        entity_type="LOAN", entity_id=loan.id,
        action="LOAN_ENDED",
        payload={"reason": reason.value, "status": loan.status.value},
        description=f"Loan ended — {reason.value.lower().replace('_', ' ')}",
    )

    if reason == LoanEndReason.RECALLED:
        message = f"{player.name} has been recalled by his parent club"
        notif_type = NotificationType.LOAN_RECALLED
    elif reason == LoanEndReason.PARENT_SOLD:
        message = f"{player.name}'s loan has ended — his parent club has sold him"
        notif_type = NotificationType.LOAN_ENDED
    else:
        message = f"{player.name}'s loan has ended"
        notif_type = NotificationType.LOAN_ENDED
    await _notify_both_clubs(db, loan, type=notif_type, message=message)

    return loan


async def recall_player(
    db: AsyncSession, loan: PlayerLoan, *, actor_club_id: uuid.UUID
) -> PlayerLoan:
    """Parent club ends a loan early. Only if the terms allowed it.

    Not window-gated: a loan ending is the agreement running its course, and
    blocking it outside a transfer window would strand players at the wrong club
    indefinitely (D8).
    """
    if loan.parent_club_id != actor_club_id:
        raise PermissionError("Only the parent club can recall a player")
    if not loan.recall_allowed:
        raise ValueError("This loan was agreed without a recall option")
    return await end_loan(db, loan, reason=LoanEndReason.RECALLED)


async def process_due_loans(db: AsyncSession) -> dict[str, int]:
    """Daily job: return loans that have reached their end date, and warn on
    those about to. An obligation to buy is phase 4 — until then such a loan
    returns like any other and the clubs settle it themselves, which is visible
    rather than silently wrong."""
    now = datetime.now(timezone.utc)
    today = now.date()
    returned = 0
    warned = 0

    due = (
        await db.execute(
            select(PlayerLoan).where(
                PlayerLoan.status == LoanStatus.ACTIVE, PlayerLoan.end_date <= today
            )
        )
    ).scalars().all()
    for loan in due:
        await end_loan(db, loan, reason=LoanEndReason.EXPIRED)
        returned += 1

    soon_cutoff = today + timedelta(days=LOAN_ENDING_SOON_DAYS)
    soon = (
        await db.execute(
            select(PlayerLoan).where(
                PlayerLoan.status == LoanStatus.ACTIVE,
                PlayerLoan.end_date > today,
                PlayerLoan.end_date <= soon_cutoff,
                # Once only, marked on the loan itself. Inferring this from the
                # notifications table meant comparing two independently-defaulted
                # timestamps, which under SQLite is a datetime-vs-string compare
                # that never matches — so the job re-warned every single day.
                PlayerLoan.ending_soon_notified_at.is_(None),
            )
        )
    ).scalars().all()
    for loan in soon:
        player = (
            await db.execute(select(Player).where(Player.id == loan.player_id))
        ).scalar_one_or_none()
        if player is None:
            continue
        await _notify_both_clubs(
            db, loan,
            type=NotificationType.LOAN_ENDING_SOON,
            message=f"{player.name}'s loan ends {loan.end_date:%d %b %Y}",
        )
        loan.ending_soon_notified_at = now
        warned += 1

    return {"returned": returned, "ending_soon_warned": warned}
