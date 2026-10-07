"""market-v2 valuation engine — pure functions, no DB access, no side effects.

fair_value = anchor[position]
             × league_coefficient
             × curve(performance)            ← v1 per-position score, multi-season, shrunk
             × age_factor × potential        ← position-specific peak, youth premium
             × trajectory × form             ← improving / in-form players
             × contract × availability       ← years left, injury record
             × market_rate                   ← what similar profiles actually sold for
             (capped at a public release clause)

Every factor is reported as a "driver" so the number can be rebuilt by hand in
the UI, the same way v1's breakdown explains its score.
"""

import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.valuation import engine as v1
from app.valuation.constants import CONFIDENCE_BANDS, ValuationConfidence
from app.valuation.constants_v2 import (
    AGE_FACTOR_FLOOR_V2,
    AGE_FACTOR_UNKNOWN_V2,
    AVAILABILITY_FREE_ABOVE,
    AVAILABILITY_FULL_DISCOUNT_AT,
    AVAILABILITY_MAX_DISCOUNT,
    BASE_ANCHORS_V2,
    COMPS_AGE_SCALE,
    COMPS_BAND_NARROWING,
    COMPS_LEAGUE_SCALE,
    COMPS_MAX_REPORTED,
    COMPS_MIN_COUNT,
    COMPS_MIN_WEIGHT,
    COMPS_RATIO_CLIP,
    COMPS_RECENCY_SCALE,
    COMPS_SCORE_SCALE,
    COMPS_SHRINKAGE_K,
    COMPS_SOURCE_WEIGHTS,
    CONTRACT_FACTOR_UNKNOWN,
    CONTRACT_KNOTS,
    DECLINE_LINEAR,
    DECLINE_QUADRATIC,
    DEFAULT_LEAGUE_COEFFICIENT,
    FORM_MAX_EFFECT,
    FORM_MAX_GAMES,
    FORM_MIN_GAMES,
    FORM_MIN_MINUTES_PER_GAME,
    FORM_RECENCY_DECAY,
    FORM_SENSITIVITY,
    LEAGUE_COEFFICIENTS,
    MARKET_FACTOR_BOUNDS,
    PEAK_WINDOWS,
    POTENTIAL_FULL_AGE,
    POTENTIAL_FULL_EVIDENCE_MINUTES,
    POTENTIAL_MAX,
    POTENTIAL_SCORE_FLOOR,
    POTENTIAL_SCORE_SPAN,
    POTENTIAL_YOUTH_EXPONENT,
    SEASON_MIN_MINUTES,
    SEASON_RECENCY_WEIGHTS,
    SHRINKAGE_MINUTES,
    SHRINKAGE_PRIOR_SCORE,
    TRAJECTORY_DELTA_SPAN,
    TRAJECTORY_FULL_AGE,
    TRAJECTORY_MAX,
    TRAJECTORY_MIN_MINUTES,
    TRAJECTORY_VETERAN_EMPHASIS,
    VALUE_CURVE_KNOTS,
    YOUTH_BAND_WIDENING,
    YOUTH_BAND_WIDENING_AGE,
)
from app.valuation.inputs_v2 import CompRecord, FeatureSetV2, RecentGame, SeasonFeatures

clamp = v1.clamp


# ── Result types ──────────────────────────────────────────────────────────────


@dataclass
class Driver:
    """One step of the value build-up: factor applied and value after it."""

    key: str
    label: str
    detail: str
    factor: float | None  # None for the starting anchor
    value_after: float


@dataclass
class MarketRate:
    factor: float
    comps_used: int
    effective_n: float
    weighted_median_ratio: float | None
    top_comps: list[dict] = field(default_factory=list)


@dataclass
class PerformanceEvidence:
    raw_score: float  # minutes × recency weighted blend of season scores
    score: float  # after shrinkage toward the prior — the one that's priced
    weighted_minutes: float
    seasons_used: int


@dataclass
class ValuationOutcomeV2:
    fair_value: float
    fair_value_low: float
    fair_value_high: float
    confidence: ValuationConfidence
    performance: PerformanceEvidence
    league_coefficient: float
    league_tier: int  # v1 tier of the same league, kept for the existing API field
    age_factor: float
    potential: float
    intrinsic_value: float  # before contract / availability / form / market
    market: MarketRate
    drivers: list[Driver]
    band: float


# ── Stage A: performance evidence ─────────────────────────────────────────────


def season_score(season: SeasonFeatures) -> float:
    return v1.compute_performance_score(season.features)


def performance_evidence(seasons: list[SeasonFeatures]) -> PerformanceEvidence:
    """Minutes × recency weighted blend of up to len(SEASON_RECENCY_WEIGHTS)
    season scores, shrunk toward a squad-player prior by total evidence."""
    total_w = 0.0
    total_ws = 0.0
    used = 0
    for idx, season in enumerate(seasons[: len(SEASON_RECENCY_WEIGHTS)]):
        if season.minutes < SEASON_MIN_MINUTES and idx > 0:
            continue  # the latest season always counts (eligibility checked it)
        w = season.minutes * SEASON_RECENCY_WEIGHTS[idx]
        total_w += w
        total_ws += w * season_score(season)
        used += 1
    if total_w <= 0:
        return PerformanceEvidence(SHRINKAGE_PRIOR_SCORE, SHRINKAGE_PRIOR_SCORE, 0.0, 0)
    raw = total_ws / total_w
    shrunk = (total_w * raw + SHRINKAGE_MINUTES * SHRINKAGE_PRIOR_SCORE) / (
        total_w + SHRINKAGE_MINUTES
    )
    return PerformanceEvidence(raw, clamp(shrunk, 0.0, 100.0), total_w, used)


# ── Stage B: intrinsic value ──────────────────────────────────────────────────


def league_coefficient(league_id: str | None) -> float:
    return LEAGUE_COEFFICIENTS.get(league_id or "", DEFAULT_LEAGUE_COEFFICIENT)


def value_curve(score: float) -> float:
    """Score → value multiple, log-linear between VALUE_CURVE_KNOTS."""
    score = clamp(score, VALUE_CURVE_KNOTS[0][0], VALUE_CURVE_KNOTS[-1][0])
    for (x0, y0), (x1, y1) in zip(VALUE_CURVE_KNOTS, VALUE_CURVE_KNOTS[1:]):
        if score <= x1:
            t = (score - x0) / (x1 - x0)
            return math.exp(math.log(y0) + t * (math.log(y1) - math.log(y0)))
    return VALUE_CURVE_KNOTS[-1][1]


# ── Stage C: age, potential, trajectory ───────────────────────────────────────


def age_factor(position: str, age: int | None) -> float:
    """1.0 up to the end of the position's peak window, then an accelerating
    decline. Youth is not discounted here — the market prices it as upside,
    which `potential_premium` handles."""
    if age is None:
        return AGE_FACTOR_UNKNOWN_V2
    _, peak_end = PEAK_WINDOWS[position]
    years_past = age - peak_end
    if years_past <= 0:
        return 1.0
    factor = math.exp(-DECLINE_LINEAR * years_past - DECLINE_QUADRATIC * years_past**2)
    return max(factor, AGE_FACTOR_FLOOR_V2)


def potential_premium(
    position: str, age: int | None, score: float, weighted_minutes: float
) -> float:
    """Premium a buyer pays for years of improvement still to come. Scales with
    youth (full at ≤19, nothing from peak start), with how well the player is
    already performing, and with how much evidence there is that he can — an
    unproven teenager or a 600-minute flash earns little of it."""
    if age is None:
        return 1.0
    peak_start, _ = PEAK_WINDOWS[position]
    if age >= peak_start:
        return 1.0
    if age <= POTENTIAL_FULL_AGE:
        youth = 1.0
    else:
        youth = ((peak_start - age) / (peak_start - POTENTIAL_FULL_AGE)) ** POTENTIAL_YOUTH_EXPONENT
    quality = clamp((score - POTENTIAL_SCORE_FLOOR) / POTENTIAL_SCORE_SPAN, 0.0, 1.0)
    evidence = min(1.0, weighted_minutes / POTENTIAL_FULL_EVIDENCE_MINUTES)
    return 1.0 + POTENTIAL_MAX * youth * quality * evidence


def trajectory_factor(seasons: list[SeasonFeatures], age: int | None) -> tuple[float, float | None]:
    """(factor, score delta) from the latest vs previous season, when both have
    enough minutes to mean something. Matters more for young players."""
    if len(seasons) < 2:
        return 1.0, None
    latest, previous = seasons[0], seasons[1]
    if latest.minutes < TRAJECTORY_MIN_MINUTES or previous.minutes < TRAJECTORY_MIN_MINUTES:
        return 1.0, None
    delta = season_score(latest) - season_score(previous)
    emphasis = (
        1.0 if (age is not None and age <= TRAJECTORY_FULL_AGE) else TRAJECTORY_VETERAN_EMPHASIS
    )
    factor = 1.0 + clamp(delta / TRAJECTORY_DELTA_SPAN, -1.0, 1.0) * TRAJECTORY_MAX * emphasis
    return factor, delta


# ── Stage D: form ─────────────────────────────────────────────────────────────


def form_factor(
    recent: list[RecentGame], season_avg_rating: float | None
) -> tuple[float, float | None]:
    """(factor, recent weighted rating). Neutral without enough rated games or
    a season average to compare against."""
    games = [g for g in recent if g.minutes >= FORM_MIN_MINUTES_PER_GAME][:FORM_MAX_GAMES]
    if len(games) < FORM_MIN_GAMES or season_avg_rating is None:
        return 1.0, None
    weights = [FORM_RECENCY_DECAY**k for k in range(len(games))]
    recent_avg = sum(w * g.rating for w, g in zip(weights, games)) / sum(weights)
    effect = clamp(
        (recent_avg - season_avg_rating) * FORM_SENSITIVITY, -FORM_MAX_EFFECT, FORM_MAX_EFFECT
    )
    return 1.0 + effect, recent_avg


# ── Stage E/F: contract and availability ──────────────────────────────────────


def contract_factor(years_remaining: float | None) -> float:
    if years_remaining is None:
        return CONTRACT_FACTOR_UNKNOWN
    years = max(years_remaining, 0.0)
    for (x0, y0), (x1, y1) in zip(CONTRACT_KNOTS, CONTRACT_KNOTS[1:]):
        if years <= x1:
            return y0 + (y1 - y0) * (years - x0) / (x1 - x0)
    return CONTRACT_KNOTS[-1][1]


def availability_factor(availability: float | None) -> float:
    if availability is None or availability >= AVAILABILITY_FREE_ABOVE:
        return 1.0
    span = AVAILABILITY_FREE_ABOVE - AVAILABILITY_FULL_DISCOUNT_AT
    severity = clamp((AVAILABILITY_FREE_ABOVE - availability) / span, 0.0, 1.0)
    return 1.0 - AVAILABILITY_MAX_DISCOUNT * severity


# ── Intrinsic value (shared by target and comparables) ────────────────────────


def intrinsic_value(
    position: str, league_coef: float, perf: PerformanceEvidence, age: int | None
) -> float:
    """What the player's output is worth before deal-specific adjustments.
    Used identically for the target and for every comparable at transfer time,
    so their fee/intrinsic ratios measure the market, not the model's shape."""
    return (
        BASE_ANCHORS_V2[position]
        * league_coef
        * value_curve(perf.score)
        * age_factor(position, age)
        * potential_premium(position, age, perf.score, perf.weighted_minutes)
    )


# ── Stage G: market rate ──────────────────────────────────────────────────────


def comp_similarity(
    comp: CompRecord, position: str, age: int | None, score: float, coef: float
) -> float:
    if comp.position != position:
        return 0.0
    age_gap = abs(comp.age_at_transfer - age) if age is not None else COMPS_AGE_SCALE
    league_gap = (
        abs(math.log(coef / comp.league_coefficient)) if comp.league_coefficient > 0 else 3.0
    )
    return (
        math.exp(-age_gap / COMPS_AGE_SCALE)
        * math.exp(-abs(comp.score_at_transfer - score) / COMPS_SCORE_SCALE)
        * math.exp(-comp.years_ago / COMPS_RECENCY_SCALE)
        * math.exp(-league_gap / COMPS_LEAGUE_SCALE)
        * COMPS_SOURCE_WEIGHTS.get(comp.source, 1.0)
    )


def weighted_median(values: list[float], weights: list[float]) -> float:
    pairs = sorted(zip(values, weights))
    half = sum(weights) / 2.0
    running = 0.0
    for value, weight in pairs:
        running += weight
        if running >= half:
            return value
    return pairs[-1][0]


def market_rate(
    comps: list[CompRecord],
    *,
    player_id: str,
    position: str,
    age: int | None,
    score: float,
    coef: float,
) -> MarketRate:
    """How the market has priced similar profiles relative to the model:
    weighted median of log(fee / intrinsic), shrunk toward 0 by the effective
    number of comps, bounded. Fewer than COMPS_MIN_COUNT similar comps → 1.0."""
    lo, hi = COMPS_RATIO_CLIP
    scored: list[tuple[float, CompRecord]] = []
    for comp in comps:
        if comp.player_id == player_id or comp.intrinsic_gbp <= 0:
            continue  # never let a player's own transfer price him
        w = comp_similarity(comp, position, age, score, coef)
        if w >= COMPS_MIN_WEIGHT:
            scored.append((w, comp))
    if len(scored) < COMPS_MIN_COUNT:
        return MarketRate(1.0, len(scored), 0.0, None)

    weights = [w for w, _ in scored]
    log_ratios = [math.log(clamp(c.ratio, lo, hi)) for _, c in scored]
    median_lr = weighted_median(log_ratios, weights)
    n_eff = sum(weights) ** 2 / sum(w * w for w in weights)
    shrink = n_eff / (n_eff + COMPS_SHRINKAGE_K)
    f_lo, f_hi = MARKET_FACTOR_BOUNDS
    factor = clamp(math.exp(shrink * median_lr), f_lo, f_hi)

    top = sorted(scored, key=lambda pair: pair[0], reverse=True)[:COMPS_MAX_REPORTED]
    return MarketRate(
        factor=factor,
        comps_used=len(scored),
        effective_n=n_eff,
        weighted_median_ratio=math.exp(median_lr),
        top_comps=[
            {
                "player_id": c.player_id,
                "player": c.player_name,
                "age": c.age_at_transfer,
                "date": c.transfer_date,
                "from": c.from_team,
                "to": c.to_team,
                "fee_display": c.fee_display,
                "fee_gbp_today": round(c.fee_gbp_today, -5),
                "ratio": round(c.ratio, 2),
                "similarity": round(w, 3),
                "source": c.source,
            }
            for w, c in top
        ],
    )


# ── Orchestration ─────────────────────────────────────────────────────────────

_POSITION_LABEL = {"GK": "goalkeeper", "DEF": "defender", "MID": "midfielder", "FWD": "forward"}


def _age_phase(position: str, age: int | None) -> str:
    if age is None:
        return "age unknown"
    start, end = PEAK_WINDOWS[position]
    if age < start:
        return "pre-peak"
    if age <= end:
        return "peak years"
    return "post-peak"


def compute_valuation_v2(
    fs: FeatureSetV2,
    comps: list[CompRecord] | None = None,
    now: datetime | None = None,
    *,
    market: MarketRate | None = None,
) -> ValuationOutcomeV2:
    """`market` replays a stored market result instead of recomputing it from
    `comps` — how a persisted row is reproduced from its own inputs_json
    without storing the whole comparables index."""
    if now is None:
        now = datetime.now(timezone.utc)
    position, age = fs.position, fs.age
    latest = fs.seasons[0]
    drivers: list[Driver] = []

    def step(key: str, label: str, detail: str, factor: float, value: float) -> float:
        value *= factor
        drivers.append(Driver(key, label, detail, factor, value))
        return value

    anchor = BASE_ANCHORS_V2[position]
    value = anchor
    drivers.append(
        Driver(
            "anchor",
            "Position anchor",
            f"Score-50 {_POSITION_LABEL[position]} in a top league, at peak age",
            None,
            value,
        )
    )

    coef = league_coefficient(latest.league_id)
    league_label = latest.league_name or (
        f"League {latest.league_id}" if latest.league_id else "Unknown league"
    )
    value = step("league", "League", f"{league_label} — market coefficient", coef, value)

    perf = performance_evidence(fs.seasons)
    curve = value_curve(perf.score)
    value = step(
        "performance",
        "Performance",
        f"Score {perf.score:.1f}/100 from {perf.seasons_used} season(s)"
        + (
            f" (raw {perf.raw_score:.1f}, shrunk for sample size)"
            if abs(perf.raw_score - perf.score) >= 0.5
            else ""
        ),
        curve,
        value,
    )

    a_factor = age_factor(position, age)
    value = step(
        "age",
        "Age",
        f"Age {age if age is not None else '—'} — {_age_phase(position, age)}",
        a_factor,
        value,
    )

    potential = potential_premium(position, age, perf.score, perf.weighted_minutes)
    if potential != 1.0:
        value = step(
            "potential", "Potential", "Upside still to come at this age and level", potential, value
        )

    intrinsic = value

    traj, delta = trajectory_factor(fs.seasons, age)
    if delta is not None:
        value = step(
            "trajectory",
            "Trajectory",
            f"Score {'+' if delta >= 0 else ''}{delta:.1f} vs last season",
            traj,
            value,
        )

    form, recent_avg = form_factor(fs.recent_games, latest.features.avg_rating)
    if recent_avg is not None:
        value = step(
            "form",
            "Recent form",
            f"Last games rated {recent_avg:.2f} vs season {latest.features.avg_rating:.2f}",
            form,
            value,
        )

    c_factor = contract_factor(fs.contract_years_remaining)
    if fs.contract_years_remaining is None:
        value = step("contract", "Contract", "Expiry unknown — no adjustment", c_factor, value)
    else:
        value = step(
            "contract",
            "Contract",
            f"{max(fs.contract_years_remaining, 0):.1f} years remaining",
            c_factor,
            value,
        )

    avail = fs.availability
    av_factor = availability_factor(avail)
    if avail is not None:
        value = step(
            "availability",
            "Availability",
            f"Available for {avail * 100:.0f}% of matches "
            f"({fs.games_missed_injured or 0} of {fs.games_available_total} missed injured)",
            av_factor,
            value,
        )

    if market is None:
        market = market_rate(
            comps or [],
            player_id=fs.player_id,
            position=position,
            age=age,
            score=perf.score,
            coef=coef,
        )
    if market.comps_used >= COMPS_MIN_COUNT:
        value = step(
            "market",
            "Market rate",
            f"{market.comps_used} comparable transfers paid "
            f"{market.weighted_median_ratio:.2f}× model; "
            f"applied ×{market.factor:.2f} after shrinkage",
            market.factor,
            value,
        )
    else:
        drivers.append(
            Driver(
                "market",
                "Market rate",
                f"Only {market.comps_used} comparable transfer(s) — no market adjustment",
                1.0,
                value,
            )
        )

    # ── Confidence and band ───────────────────────────────────────────────────
    confidence = v1.compute_confidence(latest.features, now)
    band = CONFIDENCE_BANDS[confidence]
    if age is not None and age <= YOUTH_BAND_WIDENING_AGE:
        band += YOUTH_BAND_WIDENING
    if market.comps_used >= COMPS_MIN_COUNT:
        band = max(band - COMPS_BAND_NARROWING, 0.05)

    low, high = value * (1 - band), value * (1 + band)
    clause = fs.release_clause_gbp
    if clause is not None and clause > 0 and value > clause:
        drivers.append(
            Driver(
                "release_clause",
                "Release clause",
                "Capped: no buyer pays above a published release clause",
                clause / value,
                clause,
            )
        )
        value = clause
        high = min(high, clause)
        low = min(low, clause)

    return ValuationOutcomeV2(
        fair_value=v1._round_value(value),
        fair_value_low=v1._round_value(low),
        fair_value_high=v1._round_value(high),
        confidence=confidence,
        performance=perf,
        league_coefficient=coef,
        league_tier=v1.league_tier(latest.league_id),
        age_factor=a_factor,
        potential=potential,
        intrinsic_value=intrinsic,
        market=market,
        drivers=drivers,
        band=band,
    )


# ── Reported-fee parsing (pure; used by the comparables index) ────────────────

_FEE_RE = re.compile(
    r"(?P<cur>[€£$])\s*(?P<num>\d+(?:[.,]\d+)?)\s*(?P<unit>[MmKkBb]|mln|m)?", re.IGNORECASE
)
_UNIT = {"m": 1e6, "mln": 1e6, "k": 1e3, "b": 1e9}


def parse_fee(display: str | None, gbp_per: dict[str, float]) -> float | None:
    """'€ 42M' → GBP float. `gbp_per` maps currency code → units per £1
    (e.g. {"EUR": 1.17, "USD": 1.33}). None for 'Free', 'Loan', 'N/A', etc."""
    if not display:
        return None
    m = _FEE_RE.search(display)
    if not m:
        return None
    amount = float(m.group("num").replace(",", "."))
    unit = (m.group("unit") or "").lower()
    amount *= _UNIT.get(unit, 1.0)
    cur = m.group("cur")
    if cur == "€":
        return amount / gbp_per["EUR"]
    if cur == "$":
        return amount / gbp_per["USD"]
    return amount
