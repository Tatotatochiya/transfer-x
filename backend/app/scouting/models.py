import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class InterestLevel(str, enum.Enum):
    WATCHING = "WATCHING"
    INTERESTED = "INTERESTED"
    PRIORITY = "PRIORITY"


class InterestStage(str, enum.Enum):
    SCOUTED = "SCOUTED"
    CONTACTED = "CONTACTED"
    NEGOTIATING = "NEGOTIATING"
    DROPPED = "DROPPED"


class Shortlist(Base):
    __tablename__ = "shortlists"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    club_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (UniqueConstraint("club_id", "name", name="uq_shortlists_club_name"),)

    club: Mapped["app.clubs.models.Club"] = relationship(  # type: ignore[name-defined]
        "Club", foreign_keys=[club_id]
    )
    items: Mapped[list["ShortlistItem"]] = relationship(
        "ShortlistItem",
        back_populates="shortlist",
        cascade="all, delete-orphan",
        order_by="ShortlistItem.priority",
    )


class ShortlistItem(Base):
    __tablename__ = "shortlist_items"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shortlist_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("shortlists.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    player_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("players.id", ondelete="CASCADE"), nullable=False, index=True
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("shortlist_id", "player_id", name="uq_shortlist_items_shortlist_player"),
    )

    shortlist: Mapped["Shortlist"] = relationship("Shortlist", back_populates="items")
    player: Mapped["app.players.models.Player"] = relationship(  # type: ignore[name-defined]
        "Player", foreign_keys=[player_id]
    )


class PlayerInterest(Base):
    __tablename__ = "player_interests"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    club_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    player_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("players.id", ondelete="CASCADE"), nullable=False, index=True
    )
    level: Mapped[InterestLevel] = mapped_column(
        SAEnum(InterestLevel, name="interestlevel"),
        nullable=False,
        default=InterestLevel.WATCHING,
    )
    stage: Mapped[InterestStage] = mapped_column(
        SAEnum(InterestStage, name="intereststage"),
        nullable=False,
        default=InterestStage.SCOUTED,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_touched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("club_id", "player_id", name="uq_player_interests_club_player"),
    )

    club: Mapped["app.clubs.models.Club"] = relationship(  # type: ignore[name-defined]
        "Club", foreign_keys=[club_id]
    )
    player: Mapped["app.players.models.Player"] = relationship(  # type: ignore[name-defined]
        "Player", foreign_keys=[player_id]
    )
