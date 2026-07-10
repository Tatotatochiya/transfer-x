"""Feature extraction for the valuation engine (D3 — decoupled from scoring).

A FeatureProvider turns DB state into a FeatureSet; the engine consumes only
the FeatureSet. When an xG-capable vendor lands, a new provider slots in here
and MODEL_VERSION bumps — the engine and persistence layers don't change shape.
Mirrors the protocol style of app/enrichment/protocols.py.
"""
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.players.models import Player
from app.stats.models import PlayerStats
from app.valuation.constants import STATS_VENDOR


@dataclass
class FeatureSet:
    """Everything the scoring engine needs — plain values, no ORM objects."""

    player_id: str
    position: str  # PlayerPosition value: "GK" / "DEF" / "MID" / "FWD"
    age: int | None  # Player.age, else floor-years from birth_date; None if both null
    minutes: int
    league_id: str | None
    season: int | None
    stats_updated_at: datetime | None
    avg_rating: float | None
    pass_accuracy: float  # raw percentage; null in stats → 0.0
    duels_won_rate: float
    goals_per90: float
    assists_per90: float
    goals_plus_assists_per90: float
    shots_on_target_per90: float
    key_passes_per90: float
    dribbles_success_per90: float
    defensive_actions_per90: float
    saves_per90: float
    goals_conceded_per90: float


class FeatureProvider(Protocol):
    """Build a FeatureSet for a player, or None when no usable stats exist."""

    async def get_features(self, db: AsyncSession, player: Player) -> FeatureSet | None: ...


def _floor_years(birth_date: date, today: date) -> int:
    years = today.year - birth_date.year
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        years -= 1
    return years


class BoxScoreFeatureProvider:
    """v1 provider: season-aggregate box-score stats from PlayerStats."""

    async def get_features(self, db: AsyncSession, player: Player) -> FeatureSet | None:
        if player.position is None:
            return None

        result = await db.execute(
            select(PlayerStats).where(
                PlayerStats.player_id == uuid.UUID(str(player.id)),
                PlayerStats.vendor == STATS_VENDOR,
            )
        )
        rows = result.scalars().all()

        # Stage 1 — keep rows whose season parses as an integer, take the
        # latest season, then greatest minutes (ties: greater appearances,
        # then lowest league_id string for determinism).
        candidates: list[tuple[int, PlayerStats]] = []
        for row in rows:
            try:
                candidates.append((int(str(row.season)), row))
            except (TypeError, ValueError):
                continue
        if not candidates:
            return None
        latest_season = max(season for season, _ in candidates)
        pool = [row for season, row in candidates if season == latest_season]
        pool.sort(key=lambda r: (-(r.minutes or 0), -(r.appearances or 0), r.league_id or ""))
        stats = pool[0]

        # Stage 2 — per-90s and rates; null count stats contribute 0.
        minutes = stats.minutes or 0
        n90 = minutes / 90.0 if minutes > 0 else 0.0

        def per90(*counts: int | None) -> float:
            total = sum(c or 0 for c in counts)
            return total / n90 if n90 > 0 else 0.0

        age = player.age
        if age is None and player.birth_date is not None:
            age = _floor_years(player.birth_date, date.today())

        return FeatureSet(
            player_id=str(player.id),
            position=player.position.value,
            age=age,
            minutes=minutes,
            league_id=stats.league_id,
            season=latest_season,
            stats_updated_at=stats.updated_at,
            avg_rating=float(stats.avg_rating) if stats.avg_rating is not None else None,
            pass_accuracy=float(stats.pass_accuracy or 0),
            duels_won_rate=(stats.duels_won or 0) / stats.duels_total if stats.duels_total else 0.0,
            goals_per90=per90(stats.goals),
            assists_per90=per90(stats.assists),
            goals_plus_assists_per90=per90(stats.goals, stats.assists),
            shots_on_target_per90=per90(stats.shots_on_target),
            key_passes_per90=per90(stats.key_passes),
            dribbles_success_per90=per90(stats.dribbles_success),
            defensive_actions_per90=per90(stats.tackles_total, stats.interceptions, stats.blocks),
            saves_per90=per90(stats.saves),
            goals_conceded_per90=per90(stats.goals_conceded),
        )
