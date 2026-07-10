"""Every tunable of the fair-value model in one place (TRA-91).

Nothing numeric belongs anywhere else in the valuation module. Any change to
a constant here must update the worked-example fixtures in
tests/test_valuation.py in the same commit — they are the regression net for
tuning (see docs/feature_spec/fair-value-vs-asking-signal.md §4).
"""
import enum

MODEL_VERSION = "boxscore-v1"
CURRENCY = "GBP"
STATS_VENDOR = "api_sports_v3"

# ── Eligibility ───────────────────────────────────────────────────────────────

MIN_MINUTES = 450  # ≈ 5 full matches; below this, no valuation at all

# ── Enums (defined here, not models.py, so engine.py stays DB-import-free) ────


class ValuationConfidence(str, enum.Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class DivergenceBand(str, enum.Enum):
    WELL_BELOW = "WELL_BELOW"
    BELOW = "BELOW"
    IN_LINE = "IN_LINE"
    ABOVE = "ABOVE"
    WELL_ABOVE = "WELL_ABOVE"


# ── Fair-value curve ──────────────────────────────────────────────────────────

# GBP value of a hypothetical score-50 player in a Tier-1 league, by position.
BASE_ANCHORS: dict[str, float] = {
    "GK": 8_000_000.0,
    "DEF": 12_000_000.0,
    "MID": 15_000_000.0,
    "FWD": 18_000_000.0,
}

SCORE_MIDPOINT = 50.0
CURVE_EXPONENT = 2.2
CURVE_FLOOR = 0.05  # (score/50)^2.2 never contributes less than this

VALUE_ROUNDING_GBP = 100_000
# Hard floor on any displayed value — keeps the calibration invariant
# "no player below £100k" true even at (tier 3 × curve floor × age ≥35).
MIN_FAIR_VALUE_GBP = 100_000.0

# ── League tiers (D4 — static, hand-maintained; keyed by API-Football league id)
#
# Tier 1 ids verified against backfill_2025.py. Tier 2 ids are API-Football's
# canonical public ids, seeded as forward-provisioning: no ingestion path syncs
# these leagues yet (only the top-5 plus UCL/EL, ids 2/3, are ever synced), so
# they could not be confirmed against the dev world_leagues table — re-verify
# whichever league id is first actually synced. A wrong id here degrades
# conservatively (the league falls to Tier 3), never inflates.

LEAGUE_TIERS: dict[str, int] = {
    # Tier 1 — Premier League, La Liga, Serie A, Bundesliga, Ligue 1
    "39": 1,
    "140": 1,
    "135": 1,
    "78": 1,
    "61": 1,
    # Tier 2 — Championship, Eredivisie, Primeira Liga, Belgian Pro League,
    # Süper Lig, Scottish Premiership, Brazil Série A, MLS
    "40": 2,
    "88": 2,
    "94": 2,
    "144": 2,
    "203": 2,
    "179": 2,
    "71": 2,
    "253": 2,
}
DEFAULT_LEAGUE_TIER = 3  # everything else, incl. any unknown league id
TIER_MULTIPLIERS: dict[int, float] = {1: 1.00, 2: 0.40, 3: 0.15}

# ── Age curve ─────────────────────────────────────────────────────────────────

# (age up to and including, factor) — scanned in order; ages past the last
# band get AGE_FACTOR_OLDEST.
AGE_FACTOR_BANDS: list[tuple[int, float]] = [
    (18, 0.80),
    (20, 0.90),
    (23, 0.98),
    (27, 1.00),
    (28, 0.92),
    (29, 0.85),
    (30, 0.75),
    (31, 0.65),
    (32, 0.55),
    (33, 0.45),
    (34, 0.38),
]
AGE_FACTOR_OLDEST = 0.30  # ≥ 35
AGE_FACTOR_UNKNOWN = 0.85  # age and birth_date both null (confidence capped MEDIUM)

# ── Rating normalisation (all positions) ──────────────────────────────────────

RATING_NORM_BASE = 6.0  # norm = clamp((avg_rating − 6.0) / 2.0, 0, 1)
RATING_NORM_SPAN = 2.0
RATING_NULL_NORM = 0.5  # null avg_rating → fixed norm, confidence capped MEDIUM

# ── Position feature tables ───────────────────────────────────────────────────
#
# (feature_key, display label, norm kind, norm params, weight); weights sum 100.
# Norm kinds:
#   "benchmark"      → clamp(value / param, 0, 1)
#   "range"          → clamp((value − param[0]) / param[1], 0, 1)
#   "inverted_range" → clamp((param[0] − value) / param[1], 0, 1)
#   "rating"         → clamp((avg_rating − 6.0) / 2.0, 0, 1); 0.5 when null

FeatureSpec = tuple[str, str, str, float | tuple[float, float] | None, int]

POSITION_FEATURES: dict[str, list[FeatureSpec]] = {
    "FWD": [
        ("goals_per90", "Goals per 90", "benchmark", 0.80, 35),
        ("assists_per90", "Assists per 90", "benchmark", 0.40, 15),
        ("shots_on_target_per90", "Shots on target per 90", "benchmark", 1.60, 10),
        ("key_passes_per90", "Key passes per 90", "benchmark", 1.80, 10),
        ("dribbles_success_per90", "Successful dribbles per 90", "benchmark", 1.80, 10),
        ("rating", "Average rating", "rating", None, 20),
    ],
    "MID": [
        ("goals_per90", "Goals per 90", "benchmark", 0.35, 15),
        ("assists_per90", "Assists per 90", "benchmark", 0.35, 20),
        ("key_passes_per90", "Key passes per 90", "benchmark", 2.20, 20),
        ("pass_accuracy", "Pass accuracy", "range", (70.0, 20.0), 10),
        ("duels_won_rate", "Duels won", "range", (0.40, 0.25), 10),
        ("defensive_actions_per90", "Defensive actions per 90", "benchmark", 4.50, 10),
        ("rating", "Average rating", "rating", None, 15),
    ],
    "DEF": [
        ("defensive_actions_per90", "Defensive actions per 90", "benchmark", 6.00, 30),
        ("duels_won_rate", "Duels won", "range", (0.45, 0.25), 20),
        ("pass_accuracy", "Pass accuracy", "range", (70.0, 20.0), 15),
        ("goals_plus_assists_per90", "Goals + assists per 90", "benchmark", 0.15, 10),
        ("rating", "Average rating", "rating", None, 25),
    ],
    "GK": [
        ("saves_per90", "Saves per 90", "benchmark", 3.00, 30),
        ("goals_conceded_per90", "Goals conceded per 90", "inverted_range", (1.6, 1.2), 30),
        ("pass_accuracy", "Pass accuracy", "range", (60.0, 25.0), 15),
        ("rating", "Average rating", "rating", None, 25),
    ],
}

# ── Confidence ────────────────────────────────────────────────────────────────

HIGH_MIN_MINUTES = 1800
HIGH_MAX_STALENESS_DAYS = 60
MEDIUM_MIN_MINUTES = 900
MEDIUM_MAX_STALENESS_DAYS = 120

CONFIDENCE_BANDS: dict[ValuationConfidence, float] = {
    ValuationConfidence.HIGH: 0.15,
    ValuationConfidence.MEDIUM: 0.30,
    ValuationConfidence.LOW: 0.45,
}

# ── Divergence bands (pct thresholds, applied to the rounded pct) ─────────────

DIVERGENCE_WELL_BELOW_MAX = -25.0  # pct ≤ −25 → WELL_BELOW
DIVERGENCE_BELOW_MAX = -10.0       # −25 < pct ≤ −10 → BELOW
DIVERGENCE_ABOVE_MIN = 10.0        # +10 ≤ pct < +30 → ABOVE
DIVERGENCE_WELL_ABOVE_MIN = 30.0   # pct ≥ +30 → WELL_ABOVE

# ── API ───────────────────────────────────────────────────────────────────────

BATCH_MAX_IDS = 50
