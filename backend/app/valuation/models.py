"""TRA-91: append-only player valuation history.

"Latest" = max computed_at per player; rows are never updated or deleted —
the history is the audit trail and the future trend-chart data.
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, Numeric, String, Uuid
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.valuation.constants import ValuationConfidence


class PlayerValuation(Base):
    __tablename__ = "player_valuations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    player_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("players.id", ondelete="CASCADE"), nullable=False
    )
    fair_value: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    fair_value_low: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    fair_value_high: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="GBP")
    performance_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    confidence: Mapped[ValuationConfidence] = mapped_column(
        SAEnum(ValuationConfidence, name="valuationconfidence"), nullable=False
    )
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    league_tier: Mapped[int] = mapped_column(Integer, nullable=False)
    age_factor: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False)
    # Full FeatureSet + per-feature norms/contributions snapshot: any historical
    # number is fully explainable. Plain JSON everywhere except Postgres, which
    # gets real JSONB — bare JSONB would break the SQLite test suite.
    inputs_json: Mapped[dict | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    # Python-side default (not server_default) so same-second recomputes still
    # order deterministically at microsecond precision.
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("ix_player_valuations_player_id_computed_at", "player_id", "computed_at"),
    )
