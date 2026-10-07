"""Valuation orchestration: eligibility → provider → engine → persist (TRA-91)."""
import logging
import uuid
from dataclasses import asdict
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.players.models import Player
from app.sales.models import Sale, SaleStatus, SaleType
from app.valuation import engine, engine_v2
from app.valuation.constants import CURRENCY, MIN_MINUTES
from app.valuation.constants_v2 import MODEL_VERSION_V2
from app.valuation.features_v2 import MarketFeatureProvider, build_comparables_index
from app.valuation.inputs_v2 import CompRecord, FeatureSetV2, SeasonFeatures
from app.valuation.models import PlayerValuation
from app.valuation.schemas import (
    ValuationBreakdownEntry,
    ValuationDivergence,
    ValuationDriver,
    ValuationResponse,
)

logger = logging.getLogger(__name__)

_provider = MarketFeatureProvider()


def _serialize_season(season: SeasonFeatures) -> dict:
    data = asdict(season.features)
    if data["stats_updated_at"] is not None:
        data["stats_updated_at"] = data["stats_updated_at"].isoformat()
    return {
        "season": season.season,
        "minutes": season.minutes,
        "league_id": season.league_id,
        "league_name": season.league_name,
        "score": round(engine_v2.season_score(season), 3),
        "features": data,
    }


def _serialize_features(fs: FeatureSetV2) -> dict:
    """Full input snapshot, so any stored number can be rebuilt by hand."""
    return {
        "player_id": fs.player_id,
        "position": fs.position,
        "age": fs.age,
        # v1-compatible keys the response reads for its context lines
        "minutes": fs.seasons[0].minutes,
        "league_id": fs.seasons[0].league_id,
        "seasons": [_serialize_season(s) for s in fs.seasons],
        "recent_games": [asdict(g) for g in fs.recent_games],
        "contract_years_remaining": fs.contract_years_remaining,  # unrounded: exact replay
        "contract_source": fs.contract_source,
        "release_clause_gbp": fs.release_clause_gbp,
        "games_missed_injured": fs.games_missed_injured,
        "games_available_total": fs.games_available_total,
    }


def _serialize_breakdown(rows: list[engine.BreakdownRow]) -> list[dict]:
    ordered = sorted(rows, key=lambda r: r.contribution, reverse=True)
    return [
        {
            "key": r.key,
            "label": r.label,
            "value": r.value,
            "norm": round(r.norm, 4),
            "weight": r.weight,
            "contribution": round(r.contribution, 3),
        }
        for r in ordered
    ]


def _serialize_drivers(drivers: list[engine_v2.Driver]) -> list[dict]:
    return [
        {
            "key": d.key,
            "label": d.label,
            "detail": d.detail,
            "factor": round(d.factor, 4) if d.factor is not None else None,
            "value_after": round(d.value_after, -3),
        }
        for d in drivers
    ]


async def compute_and_store_valuation(
    db: AsyncSession, player: Player, comps: list[CompRecord] | None = None
) -> PlayerValuation | None:
    """Compute and append a market-v2 valuation row, or return None if the
    player is ineligible (no position / no vendor stats / latest season below
    the minutes floor). Ineligible players get no row — never a made-up number.

    `comps` is the comparable-transfers index; the batch job builds it once and
    passes it in, a single recompute builds its own."""
    if player.position is None:
        return None
    features = await _provider.get_features(db, player)
    if features is None or features.seasons[0].minutes < MIN_MINUTES:
        return None
    if comps is None:
        comps = await build_comparables_index(db)

    outcome = engine_v2.compute_valuation_v2(features, comps)
    breakdown = engine.compute_breakdown(features.latest)

    row = PlayerValuation(
        player_id=uuid.UUID(str(player.id)),
        fair_value=Decimal(str(outcome.fair_value)),
        fair_value_low=Decimal(str(outcome.fair_value_low)),
        fair_value_high=Decimal(str(outcome.fair_value_high)),
        currency=CURRENCY,
        performance_score=Decimal(str(round(outcome.performance.score, 2))),
        confidence=outcome.confidence,
        model_version=MODEL_VERSION_V2,
        league_tier=outcome.league_tier,
        # Age and youth potential combined, so the existing "Age 19 (×1.62)"
        # line in the UI stays truthful about what age does to the number.
        age_factor=Decimal(str(round(outcome.age_factor * outcome.potential, 2))),
        inputs_json={
            "features": _serialize_features(features),
            "breakdown": _serialize_breakdown(breakdown),
            "drivers": _serialize_drivers(outcome.drivers),
            # Unrounded: compute_valuation_v2(..., market=MarketRate(**this))
            # replays the row exactly without the whole comparables index.
            "market": asdict(outcome.market),
            "factors": {
                "league_coefficient": outcome.league_coefficient,
                "age_factor": round(outcome.age_factor, 6),
                "potential": round(outcome.potential, 6),
                "intrinsic_value": round(outcome.intrinsic_value, 2),
                "band": round(outcome.band, 4),
                "score_raw": round(outcome.performance.raw_score, 6),
                "score_unrounded": round(outcome.performance.score, 6),
                "weighted_minutes": round(outcome.performance.weighted_minutes, 1),
            },
        },
    )
    db.add(row)
    await db.flush()
    return row


async def get_latest_valuation(db: AsyncSession, player_id: uuid.UUID) -> PlayerValuation | None:
    result = await db.execute(
        select(PlayerValuation)
        .where(PlayerValuation.player_id == uuid.UUID(str(player_id)))
        .order_by(PlayerValuation.computed_at.desc())
        .limit(1)
    )
    return result.scalars().first()


async def get_latest_valuations(
    db: AsyncSession, player_ids: list[uuid.UUID]
) -> dict[uuid.UUID, PlayerValuation]:
    """Latest valuation per player in one query (row_number over the
    (player_id, computed_at) index) — no N+1."""
    if not player_ids:
        return {}
    ids = [uuid.UUID(str(pid)) for pid in player_ids]
    rn = (
        func.row_number()
        .over(
            partition_by=PlayerValuation.player_id,
            order_by=PlayerValuation.computed_at.desc(),
        )
        .label("rn")
    )
    subq = select(PlayerValuation, rn).where(PlayerValuation.player_id.in_(ids)).subquery()
    latest = aliased(PlayerValuation, subq)
    result = await db.execute(select(latest).where(subq.c.rn == 1))
    rows = result.scalars().all()
    return {row.player_id: row for row in rows}


async def get_reference_prices(
    db: AsyncSession, players: list[Player]
) -> dict[uuid.UUID, Decimal]:
    """Asking price per player, in one query — the batch equivalent of the
    single-player endpoint's `reference_price` param, which a batch cannot take
    as a query arg.

    Source order matches `sales/router.py`: an open listing's asking price, else
    the legacy `Player.market_value`. Auctions are excluded — D7 forbids
    diverging against a starting price or a reserve, and a batch must never
    surface what the detail endpoint withholds. Players with neither are simply
    absent, so their response carries no divergence at all rather than one
    measured against a number nobody asked for.
    """
    if not players:
        return {}
    ids = [uuid.UUID(str(p.id)) for p in players]
    result = await db.execute(
        select(Sale.player_id, Sale.asking_price)
        .where(
            Sale.player_id.in_(ids),
            Sale.status == SaleStatus.OPEN,
            Sale.sale_type != SaleType.AUCTION,
            Sale.asking_price.is_not(None),
        )
        .order_by(Sale.created_at)  # deterministic if a player somehow has two
    )
    asking = {row.player_id: row.asking_price for row in result}

    references: dict[uuid.UUID, Decimal] = {}
    for player in players:
        pid = uuid.UUID(str(player.id))
        reference = asking.get(pid)
        if reference is None:
            reference = player.market_value
        if reference is not None:
            references[pid] = reference
    return references


async def compute_all_valuations(db: AsyncSession) -> dict[str, int]:
    """Recompute every player's valuation (daily job). Per-player failures are
    logged and never abort the batch."""
    result = await db.execute(select(Player))
    players = result.scalars().all()
    comps = await build_comparables_index(db)  # once for the whole run

    updated = 0
    skipped_ineligible = 0
    errors = 0
    for player in players:
        try:
            row = await compute_and_store_valuation(db, player, comps)
            if row is None:
                skipped_ineligible += 1
            else:
                updated += 1
        except Exception:
            errors += 1
            logger.exception("Valuation compute failed for player %s", player.id)

    return {
        "updated": updated,
        "skipped_ineligible": skipped_ineligible,
        "errors": errors,
        "comparables": len(comps),
    }


def build_valuation_response(
    row: PlayerValuation, reference_price: Decimal | None = None
) -> ValuationResponse:
    """Response from a stored row. Divergence is computed here at read time,
    never stored, and always against the stored rounded fair value so the
    displayed numbers reconcile."""
    breakdown = [
        ValuationBreakdownEntry(
            label=entry["label"],
            value=entry["value"],
            norm=entry["norm"],
            weight=entry["weight"],
            contribution=entry["contribution"],
        )
        for entry in (row.inputs_json or {}).get("breakdown", [])
    ]
    divergence = None
    if reference_price is not None and row.fair_value:
        d = engine.compute_divergence(float(row.fair_value), float(reference_price))
        divergence = ValuationDivergence(
            reference_price=reference_price, pct=d.pct, band=d.band
        )
    snapshot = (row.inputs_json or {}).get("features", {})
    # boxscore-v1 rows have no drivers; they render exactly as before.
    drivers = [
        ValuationDriver(**entry) for entry in (row.inputs_json or {}).get("drivers", [])
    ]
    market = (row.inputs_json or {}).get("market") or {}
    return ValuationResponse(
        player_id=row.player_id,
        fair_value=row.fair_value,
        fair_value_low=row.fair_value_low,
        fair_value_high=row.fair_value_high,
        currency=row.currency,
        performance_score=row.performance_score,
        confidence=row.confidence,
        model_version=row.model_version,
        league_tier=row.league_tier,
        age_factor=row.age_factor,
        age=snapshot.get("age"),
        minutes=snapshot.get("minutes"),
        as_of=row.computed_at,
        breakdown=breakdown,
        drivers=drivers,
        comparables_used=market.get("comps_used"),
        divergence=divergence,
    )
