import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, Numeric, String, Uuid, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ClubRole(str, enum.Enum):
    BUYER = "BUYER"
    SELLER = "SELLER"
    BOTH = "BOTH"
    ADMIN = "ADMIN"


class StaffRole(str, enum.Enum):
    """Staff roles — capabilities per role live in app/clubs/capabilities.py.
    The club OWNER is the club's primary User account, not a ClubStaff row."""
    SPORTING_DIRECTOR = "SPORTING_DIRECTOR"  # Deal authority + club admin + approvals
    MANAGER = "MANAGER"    # Market + deal writes (threshold-gated from Phase 5)
    SCOUT = "SCOUT"        # Scouting writes only
    READONLY = "READONLY"  # View-only access


class Club(Base):
    __tablename__ = "clubs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    league_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    crest_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    role: Mapped[ClubRole] = mapped_column(
        SAEnum(ClubRole, name="clubrole"), nullable=False, default=ClubRole.BOTH
    )
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    finance: Mapped["ClubFinance | None"] = relationship(
        "ClubFinance", back_populates="club", uselist=False, cascade="all, delete-orphan"
    )
    staff_members: Mapped[list["ClubStaff"]] = relationship(
        "ClubStaff", back_populates="club", cascade="all, delete-orphan",
        foreign_keys="ClubStaff.club_id",
    )


class ClubFinance(Base):
    __tablename__ = "club_finances"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    club_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("clubs.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    transfer_budget_total: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, default=Decimal("0")
    )
    wage_budget_total_weekly: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, default=Decimal("0")
    )
    transfer_reserved: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, default=Decimal("0")
    )
    wage_reserved_weekly: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, default=Decimal("0")
    )
    transfer_committed: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, default=Decimal("0")
    )
    transfer_spent: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, default=Decimal("0")
    )
    wage_committed_weekly: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, default=Decimal("0")
    )
    # Phase 5 (D7): MANAGER-role money actions at or above this amount are
    # captured as pending approvals instead of executing. Null = feature off.
    approval_threshold: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    club: Mapped["Club"] = relationship("Club", back_populates="finance")

    @property
    def transfer_remaining(self) -> Decimal:
        return (
            self.transfer_budget_total
            - self.transfer_reserved
            - self.transfer_committed
            - self.transfer_spent
        )

    @property
    def wage_remaining_weekly(self) -> Decimal:
        return self.wage_budget_total_weekly - self.wage_reserved_weekly - self.wage_committed_weekly


class ClubStaff(Base):
    """A staff member attached to a club — separate user account from the owner."""
    __tablename__ = "club_staff"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    club_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    role: Mapped[StaffRole] = mapped_column(
        SAEnum(StaffRole, name="staffrole"), nullable=False, default=StaffRole.READONLY
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    club: Mapped["Club"] = relationship("Club", back_populates="staff_members", foreign_keys=[club_id])
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])


class ClubStaffInvitation(Base):
    """TRA-86 (D6): tokenised staff invitation. The raw token is returned exactly
    once at creation and never stored — only its sha256 hash lives here."""
    __tablename__ = "club_staff_invitations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    club_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(254), nullable=False, index=True)
    role: Mapped[StaffRole] = mapped_column(
        SAEnum(StaffRole, name="staffrole"), nullable=False, default=StaffRole.READONLY
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    invited_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    club: Mapped["Club"] = relationship("Club", foreign_keys=[club_id])


class PlayerSearchView(Base):
    """A named, saved filter preset for the player market browser, scoped to a club."""
    __tablename__ = "player_search_views"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    club_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    filters: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
