"""Plain-value inputs for the market-v2 engine — no ORM, no DB imports.

Kept separate from features_v2.py (which talks to the database) so the engine
and its tests import nothing but dataclasses, exactly as v1's engine consumes
only a FeatureSet (D3).
"""

from dataclasses import dataclass, field
from datetime import datetime

from app.valuation.features import FeatureSet


@dataclass
class SeasonFeatures:
    """One season's performance inputs, built as a v1 FeatureSet so the v1
    per-position scoring tables are reused unchanged."""

    season: int
    minutes: int
    league_id: str | None  # the domestic league that sets the coefficient
    features: FeatureSet
    league_name: str | None = None


@dataclass
class RecentGame:
    rating: float
    minutes: int


@dataclass
class FeatureSetV2:
    player_id: str
    position: str
    age: int | None
    seasons: list[SeasonFeatures]  # newest first; seasons[0] is the latest
    recent_games: list[RecentGame] = field(default_factory=list)  # newest first
    contract_years_remaining: float | None = None
    contract_source: str | None = None  # "TRANSFERX" (Contract table) | "VENDOR"
    release_clause_gbp: float | None = None
    games_missed_injured: int | None = None  # over AVAILABILITY_SEASONS
    games_available_total: int | None = None

    @property
    def latest(self) -> FeatureSet:
        return self.seasons[0].features

    @property
    def availability(self) -> float | None:
        if not self.games_available_total:
            return None
        missed = self.games_missed_injured or 0
        return max(0.0, 1.0 - missed / self.games_available_total)


@dataclass
class CompRecord:
    """A transfer of another player, restated so it can be compared: the fee in
    today's GBP against what the model's intrinsic value said at the time."""

    player_id: str
    player_name: str
    position: str
    age_at_transfer: int
    score_at_transfer: float  # shrunk performance score from pre-transfer seasons
    league_coefficient: float  # of the league he was sold from
    intrinsic_gbp: float  # anchor × league × curve × age × potential, at the time
    fee_gbp_today: float  # converted and inflated to today's money
    years_ago: float
    source: str  # "TRANSFERX" | "REPORTED"
    fee_display: str
    transfer_date: str  # ISO date
    from_team: str | None = None
    to_team: str | None = None
    # The pre-transfer season he was judged on — kept for the backtest's v1
    # baseline (scripts/valuation_backtest.py); not used by the engine.
    reference: SeasonFeatures | None = None

    @property
    def ratio(self) -> float:
        return self.fee_gbp_today / self.intrinsic_gbp if self.intrinsic_gbp > 0 else 0.0


def features_from_snapshot(snapshot: dict) -> FeatureSetV2:
    """Inverse of the service's serialisation of a FeatureSetV2 into
    PlayerValuation.inputs_json["features"] — audit replay of a stored row."""
    seasons = []
    for entry in snapshot["seasons"]:
        raw = dict(entry["features"])
        if raw.get("stats_updated_at"):
            raw["stats_updated_at"] = datetime.fromisoformat(raw["stats_updated_at"])
        seasons.append(
            SeasonFeatures(
                season=entry["season"],
                minutes=entry["minutes"],
                league_id=entry["league_id"],
                features=FeatureSet(**raw),
                league_name=entry.get("league_name"),
            )
        )
    return FeatureSetV2(
        player_id=snapshot["player_id"],
        position=snapshot["position"],
        age=snapshot["age"],
        seasons=seasons,
        recent_games=[RecentGame(**g) for g in snapshot.get("recent_games", [])],
        contract_years_remaining=snapshot.get("contract_years_remaining"),
        contract_source=snapshot.get("contract_source"),
        release_clause_gbp=snapshot.get("release_clause_gbp"),
        games_missed_injured=snapshot.get("games_missed_injured"),
        games_available_total=snapshot.get("games_available_total"),
    )
