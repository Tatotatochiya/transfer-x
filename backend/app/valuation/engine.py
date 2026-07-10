"""Pure valuation scoring engine — no DB access, no side effects (D3).

Same FeatureSet in ⇒ same outputs out (pass `now` explicitly for full
determinism across the staleness boundary). House precedent for the idiom
(clamped weighted blend, floats internally, Decimal only at the persistence
boundary) is app/vendor/form.py::compute_form_score.
"""
from dataclasses import dataclass
from datetime import datetime, timezone

from app.valuation.constants import (
    AGE_FACTOR_BANDS,
    AGE_FACTOR_OLDEST,
    AGE_FACTOR_UNKNOWN,
    BASE_ANCHORS,
    CONFIDENCE_BANDS,
    CURVE_EXPONENT,
    CURVE_FLOOR,
    DEFAULT_LEAGUE_TIER,
    DIVERGENCE_ABOVE_MIN,
    DIVERGENCE_BELOW_MAX,
    DIVERGENCE_WELL_ABOVE_MIN,
    DIVERGENCE_WELL_BELOW_MAX,
    HIGH_MAX_STALENESS_DAYS,
    HIGH_MIN_MINUTES,
    LEAGUE_TIERS,
    MEDIUM_MAX_STALENESS_DAYS,
    MEDIUM_MIN_MINUTES,
    MIN_FAIR_VALUE_GBP,
    POSITION_FEATURES,
    RATING_NORM_BASE,
    RATING_NORM_SPAN,
    RATING_NULL_NORM,
    SCORE_MIDPOINT,
    TIER_MULTIPLIERS,
    VALUE_ROUNDING_GBP,
    DivergenceBand,
    ValuationConfidence,
)
from app.valuation.features import FeatureSet


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


@dataclass
class BreakdownRow:
    key: str
    label: str
    value: str  # display form of the raw input ("0.80", "7.6", "84")
    norm: float
    weight: int
    contribution: float


@dataclass
class ValuationOutcome:
    fair_value: float
    fair_value_low: float
    fair_value_high: float
    confidence: ValuationConfidence
    league_tier: int
    tier_multiplier: float
    age_factor: float
    curve: float


@dataclass
class Divergence:
    reference_price: float
    pct: float
    band: DivergenceBand


def _feature_norm(features: FeatureSet, key: str, kind: str, params) -> tuple[float, str]:
    """Returns (norm in [0,1], display string of the raw value)."""
    if kind == "rating":
        if features.avg_rating is None:
            return RATING_NULL_NORM, "—"
        norm = clamp((features.avg_rating - RATING_NORM_BASE) / RATING_NORM_SPAN, 0.0, 1.0)
        return norm, f"{features.avg_rating:.1f}"

    value: float = getattr(features, key)
    if kind == "benchmark":
        norm = clamp(value / params, 0.0, 1.0)
    elif kind == "range":
        lo, span = params
        norm = clamp((value - lo) / span, 0.0, 1.0)
    elif kind == "inverted_range":
        hi, span = params
        norm = clamp((hi - value) / span, 0.0, 1.0)
    else:  # pragma: no cover — constants table is the only caller
        raise ValueError(f"Unknown norm kind: {kind}")

    if key == "pass_accuracy":
        display = f"{value:.0f}"
    else:
        display = f"{value:.2f}"
    return norm, display


def compute_breakdown(features: FeatureSet) -> list[BreakdownRow]:
    """One row per weighted feature for the player's position, full precision."""
    rows: list[BreakdownRow] = []
    for key, label, kind, params, weight in POSITION_FEATURES[features.position]:
        norm, display = _feature_norm(features, key, kind, params)
        rows.append(
            BreakdownRow(
                key=key,
                label=label,
                value=display,
                norm=norm,
                weight=weight,
                contribution=weight * norm,
            )
        )
    return rows


def compute_performance_score(features: FeatureSet) -> float:
    """Σ (weight × norm), range [0, 100]. Unrounded — round only at persistence."""
    total = sum(row.contribution for row in compute_breakdown(features))
    return clamp(total, 0.0, 100.0)


def _age_factor(age: int | None) -> float:
    if age is None:
        return AGE_FACTOR_UNKNOWN
    for max_age, factor in AGE_FACTOR_BANDS:
        if age <= max_age:
            return factor
    return AGE_FACTOR_OLDEST


def _staleness_days(stats_updated_at: datetime | None, now: datetime) -> int | None:
    if stats_updated_at is None:
        return None
    ts = stats_updated_at
    if ts.tzinfo is not None:
        ts = ts.astimezone(timezone.utc).replace(tzinfo=None)
    ref = now.astimezone(timezone.utc).replace(tzinfo=None) if now.tzinfo else now
    return (ref - ts).days


def _round_value(raw: float) -> float:
    return max(round(raw / VALUE_ROUNDING_GBP) * VALUE_ROUNDING_GBP, MIN_FAIR_VALUE_GBP)


def compute_fair_value(
    features: FeatureSet, score: float, now: datetime | None = None
) -> ValuationOutcome:
    """Stage 4 + 5: fair value with confidence band.

    `score` must be the unrounded performance score. The band applies to the
    unrounded value; each bound is then rounded to £100k.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    tier = LEAGUE_TIERS.get(features.league_id or "", DEFAULT_LEAGUE_TIER)
    multiplier = TIER_MULTIPLIERS[tier]
    age_factor = _age_factor(features.age)
    curve = max((score / SCORE_MIDPOINT) ** CURVE_EXPONENT, CURVE_FLOOR)
    raw = BASE_ANCHORS[features.position] * multiplier * curve * age_factor

    days = _staleness_days(features.stats_updated_at, now)
    if (
        features.minutes >= HIGH_MIN_MINUTES
        and features.avg_rating is not None
        and days is not None
        and days <= HIGH_MAX_STALENESS_DAYS
    ):
        confidence = ValuationConfidence.HIGH
    elif (
        features.minutes >= MEDIUM_MIN_MINUTES
        and days is not None
        and days <= MEDIUM_MAX_STALENESS_DAYS
    ):
        confidence = ValuationConfidence.MEDIUM
    else:
        confidence = ValuationConfidence.LOW
    # Null rules cap confidence at MEDIUM (applied after the table).
    if confidence == ValuationConfidence.HIGH and (
        features.avg_rating is None or features.age is None
    ):
        confidence = ValuationConfidence.MEDIUM

    band = CONFIDENCE_BANDS[confidence]
    return ValuationOutcome(
        fair_value=_round_value(raw),
        fair_value_low=_round_value(raw * (1 - band)),
        fair_value_high=_round_value(raw * (1 + band)),
        confidence=confidence,
        league_tier=tier,
        tier_multiplier=multiplier,
        age_factor=age_factor,
        curve=curve,
    )


def compute_divergence(fair_value: float, reference_price: float) -> Divergence:
    """Stage 6 — computed at read time against the stored rounded fair value."""
    pct = round((reference_price - fair_value) / fair_value * 100.0, 1)
    if pct <= DIVERGENCE_WELL_BELOW_MAX:
        band = DivergenceBand.WELL_BELOW
    elif pct <= DIVERGENCE_BELOW_MAX:
        band = DivergenceBand.BELOW
    elif pct < DIVERGENCE_ABOVE_MIN:
        band = DivergenceBand.IN_LINE
    elif pct < DIVERGENCE_WELL_ABOVE_MIN:
        band = DivergenceBand.ABOVE
    else:
        band = DivergenceBand.WELL_ABOVE
    return Divergence(reference_price=reference_price, pct=pct, band=band)
