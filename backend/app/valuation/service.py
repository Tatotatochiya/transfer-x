"""Valuation orchestration: eligibility → provider → engine → persist (TRA-91)."""
import logging
import uuid
from dataclasses import asdict
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.players.models import Player
from app.valuation import engine
from app.valuation.constants import CURRENCY, MIN_MINUTES, MODEL_VERSION
from app.valuation.features import BoxScoreFeatureProvider, FeatureSet
from app.valuation.models import PlayerValuation
from app.valuation.schemas import (
    ValuationBreakdownEntry,
    ValuationDivergence,
    ValuationResponse,
)

logger = logging.getLogger(__name__)

_provider = BoxScoreFeatureProvider()


def _serialize_features(features: FeatureSet) -> dict:
    data = asdict(features)
    if data["stats_updated_at"] is not None:
        data["stats_updated_at"] = data["stats_updated_at"].isoformat()
    return data


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


async def compute_and_store_valuation(db: AsyncSession, player: Player) -> PlayerValuation | None:
    """Compute and append a valuation row, or return None if the player is
    ineligible (no position / no vendor stats / minutes below the floor).
    Ineligible players get no row at all — never a made-up number."""
    if player.position is None:
        return None
    features = await _provider.get_features(db, player)
    if features is None or features.minutes < MIN_MINUTES:
        return None

    breakdown = engine.compute_breakdown(features)
    score = engine.compute_performance_score(features)
    outcome = engine.compute_fair_value(features, score)

    row = PlayerValuation(
        player_id=uuid.UUID(str(player.id)),
        fair_value=Decimal(str(outcome.fair_value)),
        fair_value_low=Decimal(str(outcome.fair_value_low)),
        fair_value_high=Decimal(str(outcome.fair_value_high)),
        currency=CURRENCY,
        performance_score=Decimal(str(round(score, 2))),
        confidence=outcome.confidence,
        model_version=MODEL_VERSION,
        league_tier=outcome.league_tier,
        age_factor=Decimal(str(outcome.age_factor)),
        inputs_json={
            "features": _serialize_features(features),
            "breakdown": _serialize_breakdown(breakdown),
            "factors": {
                "tier_multiplier": outcome.tier_multiplier,
                "age_factor": outcome.age_factor,
                "curve": round(outcome.curve, 6),
                "score_unrounded": round(score, 6),
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


async def compute_all_valuations(db: AsyncSession) -> dict[str, int]:
    """Recompute every player's valuation (daily job). Per-player failures are
    logged and never abort the batch."""
    result = await db.execute(select(Player))
    players = result.scalars().all()

    updated = 0
    skipped_ineligible = 0
    errors = 0
    for player in players:
        try:
            row = await compute_and_store_valuation(db, player)
            if row is None:
                skipped_ineligible += 1
            else:
                updated += 1
        except Exception:
            errors += 1
            logger.exception("Valuation compute failed for player %s", player.id)

    return {"updated": updated, "skipped_ineligible": skipped_ineligible, "errors": errors}


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
        divergence=divergence,
    )
