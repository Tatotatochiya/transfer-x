"""market-v2 feature provider and comparable-transfers index (DB side).

Turns database state into the plain dataclasses of inputs_v2.py; the engine
never sees an ORM object. Every input here is data TransferX already holds —
nothing is fetched from a vendor at valuation time.

Confidentiality: the holding club's private contract fields (wage, signing
date, its own `club_valuation`, notes) are never read. End date and release
clause are already public to rival clubs (see test_contract_confidentiality).
"""

import re
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.players.models import Contract, Player, PlayerTransfer
from app.stats.models import (
    PlayerFixtureRating,
    PlayerInjuryFixture,
    PlayerStats,
    TeamSeasonFixtures,
)
from app.valuation import engine_v2
from app.valuation.constants import STATS_VENDOR
from app.valuation.constants_v2 import (
    AVAILABILITY_EXCLUDE_REASON_PATTERN,
    AVAILABILITY_SEASONS,
    COMPS_LOOKBACK_DAYS,
    COMPS_MIN_FEE_GBP,
    EUROPEAN_CUP_LEAGUE_IDS,
    FEE_INFLATION_PER_YEAR,
    FORM_MAX_GAMES,
    LEAGUE_COEFFICIENTS,
    SEASON_MIN_MINUTES,
    SEASONS_CONSIDERED,
)
from app.valuation.features import FeatureSet, _floor_years
from app.valuation.inputs_v2 import CompRecord, FeatureSetV2, RecentGame, SeasonFeatures

# Static rates (units per £1), the fx module's offline fallback — static on
# purpose so a stored valuation can be reproduced from its inputs.
GBP_PER = {"EUR": 1.17, "USD": 1.33}
_EXCLUDE_REASON = re.compile(AVAILABILITY_EXCLUDE_REASON_PATTERN, re.IGNORECASE)
_CHUNK = 500


# ── Season aggregation (shared by target and comparables) ─────────────────────


def _int_season(raw) -> int | None:
    try:
        return int(str(raw))
    except (TypeError, ValueError):
        return None


def _rows_for_season(rows: list[PlayerStats]) -> list[PlayerStats]:
    """Club rows worth aggregating for one season: every row in a domestic
    league the model knows, plus UEFA club cups. A player in an unlisted league
    keeps v1's rule for his domestic football — the single biggest-minutes row
    (other unlisted rows may be cups or youth sides we can't tell apart) — plus
    any European games, so he is never valued on his cup run alone."""

    def league(r: PlayerStats) -> str:
        return r.league_id or ""

    cups = [r for r in rows if league(r) in EUROPEAN_CUP_LEAGUE_IDS]
    domestic = [r for r in rows if league(r) in LEAGUE_COEFFICIENTS]
    if domestic:
        return domestic + cups
    others = [r for r in rows if r not in cups]
    if not others:
        return cups
    best = min(others, key=lambda r: (-(r.minutes or 0), -(r.appearances or 0), league(r)))
    return [best] + cups


def _primary_league(rows: list[PlayerStats]) -> PlayerStats:
    domestic = [r for r in rows if (r.league_id or "") not in EUROPEAN_CUP_LEAGUE_IDS] or rows
    return sorted(domestic, key=lambda r: (-(r.minutes or 0), r.league_id or ""))[0]


def build_season(
    player_id: str, position: str, age: int | None, season: int, rows: list[PlayerStats]
) -> SeasonFeatures:
    """Aggregate a season's rows into one v1 FeatureSet: counts summed, rates
    minutes-weighted, so a mid-season move or a European run is all counted."""
    rows = _rows_for_season(rows)
    primary = _primary_league(rows)
    minutes = sum(r.minutes or 0 for r in rows)
    n90 = minutes / 90.0 if minutes > 0 else 0.0

    def total(attr: str) -> int:
        return sum(getattr(r, attr) or 0 for r in rows)

    def per90(*attrs: str) -> float:
        return sum(total(a) for a in attrs) / n90 if n90 > 0 else 0.0

    def minutes_weighted(attr: str) -> float | None:
        pairs = [
            (float(getattr(r, attr)), r.minutes or 0) for r in rows if getattr(r, attr) is not None
        ]
        weight = sum(m for _, m in pairs)
        if not pairs:
            return None
        if weight == 0:
            return sum(v for v, _ in pairs) / len(pairs)
        return sum(v * m for v, m in pairs) / weight

    duels_total = total("duels_total")
    rating = minutes_weighted("avg_rating")
    updated = [r.updated_at for r in rows if r.updated_at is not None]
    fs = FeatureSet(
        player_id=player_id,
        position=position,
        age=age,
        minutes=minutes,
        league_id=primary.league_id,
        season=season,
        stats_updated_at=max(updated) if updated else None,
        avg_rating=rating,
        pass_accuracy=minutes_weighted("pass_accuracy") or 0.0,
        duels_won_rate=total("duels_won") / duels_total if duels_total else 0.0,
        goals_per90=per90("goals"),
        assists_per90=per90("assists"),
        goals_plus_assists_per90=per90("goals", "assists"),
        shots_on_target_per90=per90("shots_on_target"),
        key_passes_per90=per90("key_passes"),
        dribbles_success_per90=per90("dribbles_success"),
        defensive_actions_per90=per90("tackles_total", "interceptions", "blocks"),
        saves_per90=per90("saves"),
        goals_conceded_per90=per90("goals_conceded"),
    )
    return SeasonFeatures(
        season=season,
        minutes=minutes,
        league_id=primary.league_id,
        features=fs,
        league_name=primary.league_name,
    )


def build_seasons(
    player_id: str,
    position: str,
    age: int | None,
    rows: list[PlayerStats],
    *,
    up_to_season: int | None = None,
) -> list[SeasonFeatures]:
    """Newest-first seasons (at most SEASONS_CONSIDERED), optionally only those
    at or before `up_to_season` — how a comparable is seen as of its transfer."""
    by_season: dict[int, list[PlayerStats]] = defaultdict(list)
    for row in rows:
        season = _int_season(row.season)
        if season is None or (up_to_season is not None and season > up_to_season):
            continue
        by_season[season].append(row)
    seasons = [
        build_season(player_id, position, age, s, by_season[s])
        for s in sorted(by_season, reverse=True)
    ]
    return seasons[:SEASONS_CONSIDERED]


def _current_age(player: Player, today: date) -> int | None:
    if player.birth_date is not None:
        return _floor_years(player.birth_date, today)
    return player.age


# ── Target player ─────────────────────────────────────────────────────────────


@dataclass
class _ContractInfo:
    years: float | None
    source: str | None
    release_clause: float | None


async def _contract_info(db: AsyncSession, player: Player, today: date) -> _ContractInfo:
    """A TransferX contract always beats the vendor's expiry (ADR 0001)."""
    result = await db.execute(
        select(Contract)
        .where(Contract.player_id == player.id, Contract.is_active.is_(True))
        .order_by(Contract.end_date.desc().nulls_last())
    )
    contract = result.scalars().first()
    if contract is not None and contract.end_date is not None:
        return _ContractInfo(
            (contract.end_date - today).days / 365.25,
            "TRANSFERX",
            float(contract.release_clause) if contract.release_clause else None,
        )
    if player.contract_expiry is not None:
        return _ContractInfo((player.contract_expiry - today).days / 365.25, "VENDOR", None)
    return _ContractInfo(None, None, None)


async def _availability(
    db: AsyncSession, player: Player, rows: list[PlayerStats], seasons: list[int]
) -> tuple[int | None, int | None]:
    """(games missed injured, games his teams played) over recent seasons, or
    (None, None) when any team-season count is unknown — no guessing."""
    if not seasons:
        return None, None
    season_keys = {str(s) for s in seasons}
    spells = {
        (r.team_vendor_id, r.league_id, str(r.season))
        for r in rows
        if str(r.season) in season_keys and (r.appearances or 0) > 0 and r.team_vendor_id
    }
    if not spells:
        return None, None
    counts = (
        (
            await db.execute(
                select(TeamSeasonFixtures).where(
                    TeamSeasonFixtures.team_vendor_id.in_({t for t, _, _ in spells}),
                    TeamSeasonFixtures.season.in_(season_keys),
                )
            )
        )
        .scalars()
        .all()
    )
    played = {(c.team_vendor_id, c.league_id, c.season): c.played for c in counts}
    if any(played.get(spell) is None for spell in spells):
        return None, None
    total = sum(played[spell] for spell in spells)
    missed_rows = (
        (
            await db.execute(
                select(PlayerInjuryFixture).where(
                    PlayerInjuryFixture.player_id == player.id,
                    PlayerInjuryFixture.injury_type == "Missing Fixture",
                    PlayerInjuryFixture.season.in_(season_keys),
                )
            )
        )
        .scalars()
        .all()
    )
    missed = sum(
        1
        for m in missed_rows
        if (m.team_vendor_id, m.league_id, m.season) in spells
        and not _EXCLUDE_REASON.search(m.reason or "")
    )
    return missed, total


class MarketFeatureProvider:
    """Builds a FeatureSetV2, or None when the player has no usable stats."""

    async def get_features(self, db: AsyncSession, player: Player) -> FeatureSetV2 | None:
        if player.position is None:
            return None
        today = date.today()
        rows = (
            (
                await db.execute(
                    select(PlayerStats).where(
                        PlayerStats.player_id == uuid.UUID(str(player.id)),
                        PlayerStats.vendor == STATS_VENDOR,
                    )
                )
            )
            .scalars()
            .all()
        )
        age = _current_age(player, today)
        seasons = build_seasons(str(player.id), player.position.value, age, list(rows))
        if not seasons:
            return None

        recent = (
            (
                await db.execute(
                    select(PlayerFixtureRating)
                    .where(
                        PlayerFixtureRating.player_id == player.id,
                        PlayerFixtureRating.rating.is_not(None),
                    )
                    .order_by(PlayerFixtureRating.fixture_date.desc().nulls_last())
                    .limit(FORM_MAX_GAMES * 2)
                )
            )
            .scalars()
            .all()
        )

        contract = await _contract_info(db, player, today)
        missed, total = await _availability(
            db, player, list(rows), [s.season for s in seasons[:AVAILABILITY_SEASONS]]
        )
        return FeatureSetV2(
            player_id=str(player.id),
            position=player.position.value,
            age=age,
            seasons=seasons,
            recent_games=[RecentGame(float(g.rating), g.minutes or 0) for g in recent],
            contract_years_remaining=contract.years,
            contract_source=contract.source,
            release_clause_gbp=contract.release_clause,
            games_missed_injured=missed,
            games_available_total=total,
        )


# ── Comparable transfers index ────────────────────────────────────────────────


def reference_season(transfer_date: date) -> int:
    """The season whose stats a buyer had in front of him. API-Football names
    seasons by start year: a July 2025 or January 2025 move both look at 2024."""
    return transfer_date.year - 1 if transfer_date.month <= 9 else transfer_date.year


def _age_at(player: Player, on: date, today: date) -> int | None:
    if player.birth_date is not None:
        return _floor_years(player.birth_date, on)
    if player.age is not None:
        return player.age - int(round((today - on).days / 365.25))
    return None


async def build_comparables_index(db: AsyncSession, today: date | None = None) -> list[CompRecord]:
    """Every fee-bearing permanent transfer in the lookback window, restated as
    fee-in-today's-GBP against the model's intrinsic value at the time.

    Two sources: completed TransferX deals (agreed fee — verified) and transfer
    history reported by the stats vendor ("€ 42M"). When both describe the same
    move (same player, within 60 days) the TransferX deal wins. Built once per
    batch run; a single recompute builds it too (one bounded query each)."""
    from app.deals.models import Deal, DealStatus, DealType

    today = today or date.today()
    since = today - timedelta(days=COMPS_LOOKBACK_DAYS)

    events: list[tuple[Player, date, float, str, str, str | None, str | None]] = []
    platform = (
        await db.execute(
            select(Deal, Player)
            .join(Player, Player.id == Deal.player_id)
            .where(
                Deal.status == DealStatus.COMPLETED,
                Deal.deal_type == DealType.PERMANENT,
                Deal.agreed_fee > 0,
                Deal.completed_at.is_not(None),
                Player.position.is_not(None),
            )
        )
    ).all()
    platform_moves: dict[str, list[date]] = defaultdict(list)
    for deal, player in platform:
        on = (
            deal.completed_at.date()
            if isinstance(deal.completed_at, datetime)
            else deal.completed_at
        )
        if on < since:
            continue
        fee = float(deal.agreed_fee)
        platform_moves[str(player.id)].append(on)
        events.append((player, on, fee, "TRANSFERX", f"£{fee / 1e6:.1f}m", None, None))

    reported = (
        await db.execute(
            select(PlayerTransfer, Player)
            .join(Player, Player.id == PlayerTransfer.player_id)
            .where(
                PlayerTransfer.transfer_date >= since,
                PlayerTransfer.transfer_type == "Transfer",
                PlayerTransfer.fee_display.is_not(None),
                Player.position.is_not(None),
            )
        )
    ).all()
    for move, player in reported:
        fee = engine_v2.parse_fee(move.fee_display, GBP_PER)
        if fee is None or fee < COMPS_MIN_FEE_GBP or move.transfer_date is None:
            continue
        if any(
            abs((move.transfer_date - d).days) <= 60 for d in platform_moves.get(str(player.id), [])
        ):
            continue
        events.append(
            (
                player,
                move.transfer_date,
                fee,
                "REPORTED",
                move.fee_display,
                move.team_out_name,
                move.team_in_name,
            )
        )
    if not events:
        return []

    player_ids = list({uuid.UUID(str(p.id)) for p, *_ in events})
    stats_by_player: dict[str, list[PlayerStats]] = defaultdict(list)
    for i in range(0, len(player_ids), _CHUNK):
        chunk = player_ids[i : i + _CHUNK]
        for row in (
            (
                await db.execute(
                    select(PlayerStats).where(
                        PlayerStats.player_id.in_(chunk), PlayerStats.vendor == STATS_VENDOR
                    )
                )
            )
            .scalars()
            .all()
        ):
            stats_by_player[str(row.player_id)].append(row)

    comps: list[CompRecord] = []
    for player, on, fee, source, display, out_team, in_team in events:
        position = player.position.value
        age_then = _age_at(player, on, today)
        if age_then is None:
            continue
        seasons = build_seasons(
            str(player.id),
            position,
            age_then,
            stats_by_player.get(str(player.id), []),
            up_to_season=reference_season(on),
        )
        if not seasons or seasons[0].minutes < SEASON_MIN_MINUTES:
            continue  # nothing to model him on at the time — can't say what he "should" have cost
        perf = engine_v2.performance_evidence(seasons)
        coef = engine_v2.league_coefficient(seasons[0].league_id)
        years_ago = max((today - on).days / 365.25, 0.0)
        comps.append(
            CompRecord(
                player_id=str(player.id),
                player_name=player.name,
                position=position,
                age_at_transfer=age_then,
                score_at_transfer=perf.score,
                league_coefficient=coef,
                intrinsic_gbp=engine_v2.intrinsic_value(position, coef, perf, age_then),
                fee_gbp_today=fee * (1 + FEE_INFLATION_PER_YEAR) ** years_ago,
                years_ago=years_ago,
                source=source,
                fee_display=display,
                transfer_date=on.isoformat(),
                from_team=out_team,
                to_team=in_team,
                reference=seasons[0],
            )
        )
    return comps
