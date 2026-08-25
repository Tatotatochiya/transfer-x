"""Loan registrations — feature_spec/loan-transfers.md phase 2.

A loan needs two simultaneous relationships (the parent owns, the loanee
registers), but `normalize_player_status` resolves the active contract with
`scalar_one_or_none()`, so two active `Contract` rows raise
`MultipleResultsFound` rather than merely misbehaving. That invariant is load
bearing across the whole player model, so it is preserved exactly: the loanee
holds the one active contract for the duration, and *this* row is what says who
actually owns the player.

`parent_contract_id` is the load-bearing field. It points at the contract
suspended when the loan started, so the return is a restore of the agreement
the parent already had rather than a new one with a guessed wage and end date.
"""
import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Uuid, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class LoanStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"   # ran to term
    RECALLED = "RECALLED"     # parent ended it early
    CONVERTED = "CONVERTED"   # became a permanent move (option, obligation, or a sale)


class LoanEndReason(str, enum.Enum):
    EXPIRED = "EXPIRED"
    RECALLED = "RECALLED"
    OPTION_EXERCISED = "OPTION_EXERCISED"
    OBLIGATION = "OBLIGATION"
    PARENT_SOLD = "PARENT_SOLD"


class PlayerLoan(Base):
    __tablename__ = "player_loans"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    player_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("players.id", ondelete="CASCADE"), nullable=False, index=True
    )
    deal_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("deals.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    parent_club_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("clubs.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    loanee_club_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("clubs.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # The contract suspended at loan start, restored when the loan ends. Null
    # only if the parent somehow had no active contract (a data state that
    # validation should prevent, but the column stays nullable rather than
    # making the loan un-recordable).
    parent_contract_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("contracts.id", ondelete="SET NULL"), nullable=True
    )
    loanee_contract_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("contracts.id", ondelete="SET NULL"), nullable=True
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    loan_fee: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    wage_split_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    # The absolute weekly figure the loanee took on, stored rather than
    # recomputed: the split is a fraction of the *agreed* wage, and unwinding
    # has to give back exactly what was taken even if the underlying contract
    # wage differs.
    loanee_wage_share: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, default=Decimal("0"), server_default="0"
    )
    option_to_buy: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    obligation_to_buy: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    recall_allowed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    status: Mapped[LoanStatus] = mapped_column(
        SAEnum(LoanStatus, name="loanstatus"),
        nullable=False,
        default=LoanStatus.ACTIVE,
        index=True,
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Set the first time the ending-soon warning goes out, so the daily job
    # warns once rather than every day for the last fortnight.
    ending_soon_notified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    end_reason: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # The permanent deal this loan turned into, whether the loanee exercised an
    # option or an obligation crystallised at expiry. Set when the deal is
    # created, not when it completes: it is what stops the daily job starting a
    # second deal for the same obligation on its next run.
    conversion_deal_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("deals.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    player: Mapped["app.players.models.Player"] = relationship(  # type: ignore[name-defined]
        "Player", foreign_keys=[player_id]
    )
    parent_club: Mapped["app.clubs.models.Club"] = relationship(  # type: ignore[name-defined]
        "Club", foreign_keys=[parent_club_id]
    )
    loanee_club: Mapped["app.clubs.models.Club"] = relationship(  # type: ignore[name-defined]
        "Club", foreign_keys=[loanee_club_id]
    )
