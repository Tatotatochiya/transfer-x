"""Every tunable of the market-v2 fair-value model in one place.

market-v2 keeps boxscore-v1's per-position performance score (same feature
tables, same norms — imported from constants.py, not duplicated) and adds the
things a transfer market actually prices: multi-season evidence, position-
specific ageing, youth potential, trajectory, recent form, contract length,
availability, and what comparable profiles have really been sold for.

Nothing numeric belongs anywhere else in the v2 modules. Any change here must
update the fixtures in tests/test_valuation_v2.py in the same commit.
See docs/feature_spec/valuation-model-v2.md for the reasoning behind each value.
"""

MODEL_VERSION_V2 = "market-v2"

# ── Stage A: performance evidence ─────────────────────────────────────────────

# Up to this many seasons blend into the performance score, newest first.
SEASONS_CONSIDERED = 3
# Weight multiplier by season age (0 = latest). Applied on top of minutes.
SEASON_RECENCY_WEIGHTS: tuple[float, ...] = (1.00, 0.55, 0.30)
# A season only counts toward the blend with at least this many minutes.
SEASON_MIN_MINUTES = 450

# Bayesian shrinkage: score_shrunk = (M·s + K·prior) / (M + K), M = recency-
# weighted minutes. Stops a 500-minute hot streak pricing like a full season.
SHRINKAGE_PRIOR_SCORE = 40.0  # a typical squad player at his level
SHRINKAGE_MINUTES = 600.0

# API-Football ids for UEFA club competitions: their stats count toward the
# season's performance, but never decide the player's league coefficient.
EUROPEAN_CUP_LEAGUE_IDS: frozenset[str] = frozenset({"2", "3", "848"})

# ── Stage B: intrinsic value curve ────────────────────────────────────────────

# GBP value of a hypothetical score-50 player in a coefficient-1.0 league,
# at peak age, by position.
BASE_ANCHORS_V2: dict[str, float] = {
    "GK": 9_000_000.0,
    "DEF": 14_000_000.0,
    "MID": 19_500_000.0,
    "FWD": 19_000_000.0,
}
# Score → value multiple, interpolated linearly in log space between knots.
# Replaces v1's single (score/50)^2.2 power curve, which could not fit the
# market: the box-score score compresses the top end (elite ≈ 72, average
# ≈ 48) while fees differ ~10× across that gap. A curve steep enough for the
# middle explodes at the top, so the slope eases above 70.
VALUE_CURVE_KNOTS: tuple[tuple[float, float], ...] = (
    (0.0, 0.03),
    (30.0, 0.15),
    (40.0, 0.40),
    (50.0, 1.00),
    (60.0, 2.30),
    (70.0, 4.80),
    (80.0, 7.80),
    (90.0, 10.50),
    (100.0, 12.50),
)

# League coefficient, keyed by API-Football league id. Replaces v1's three
# coarse tiers: within the old Tier 1 the Premier League carries a clear
# market premium. Ids are the same set v1 seeded (Tier-2 ids still need
# verifying against world_leagues — a wrong id degrades to the default).
LEAGUE_COEFFICIENTS: dict[str, float] = {
    "39": 1.00,  # Premier League
    "140": 0.80,  # La Liga
    "135": 0.75,  # Serie A
    "78": 0.75,  # Bundesliga
    "61": 0.62,  # Ligue 1
    "94": 0.38,  # Primeira Liga
    "88": 0.33,  # Eredivisie
    "40": 0.36,  # Championship (parachute money, PL-adjacent buyers)
    "71": 0.30,  # Brazil Série A
    "144": 0.28,  # Belgian Pro League
    "203": 0.26,  # Süper Lig
    "253": 0.20,  # MLS
    "179": 0.18,  # Scottish Premiership
}
DEFAULT_LEAGUE_COEFFICIENT = 0.13

# ── Stage C: age, potential, trajectory ───────────────────────────────────────

# Peak window (first, last peak age) by position. Goalkeepers peak later.
PEAK_WINDOWS: dict[str, tuple[int, int]] = {
    "GK": (27, 31),
    "DEF": (25, 29),
    "MID": (24, 28),
    "FWD": (24, 28),
}
# Post-peak decline: factor = exp(−a·y − b·y²), y = years past peak end.
# Accelerating because resale value vanishes as well as ability fading.
DECLINE_LINEAR = 0.08
DECLINE_QUADRATIC = 0.015
AGE_FACTOR_FLOOR_V2 = 0.18
AGE_FACTOR_UNKNOWN_V2 = 0.85

# Youth potential premium: 1 + POTENTIAL_MAX × youth_weight × quality.
#   youth_weight: 1.0 at ≤ POTENTIAL_FULL_AGE, falling to 0 at the position's
#                 peak start as ((peak_start − age) / (peak_start − 19))^1.5 —
#                 the premium fades fast once a player is past ~21.
#   quality:      clamp((score − POTENTIAL_SCORE_FLOOR) / POTENTIAL_SCORE_SPAN, 0, 1)
#                 — only a young player already performing earns the premium.
#   evidence:     min(1, weighted minutes / POTENTIAL_FULL_EVIDENCE_MINUTES)
#                 — and only once he has done it for long enough to believe.
POTENTIAL_MAX = 1.20
POTENTIAL_FULL_AGE = 19
POTENTIAL_YOUTH_EXPONENT = 1.5
POTENTIAL_SCORE_FLOOR = 35.0
POTENTIAL_SCORE_SPAN = 35.0
POTENTIAL_FULL_EVIDENCE_MINUTES = 2000.0

# Trajectory: latest vs previous season score, both with ≥ TRAJECTORY_MIN_MINUTES.
# factor = 1 + clamp(Δ / TRAJECTORY_DELTA_SPAN, −1, 1) × TRAJECTORY_MAX × emphasis
# emphasis = 1.0 for age ≤ TRAJECTORY_FULL_AGE, else TRAJECTORY_VETERAN_EMPHASIS.
TRAJECTORY_MIN_MINUTES = 900
TRAJECTORY_DELTA_SPAN = 20.0
TRAJECTORY_MAX = 0.10
TRAJECTORY_FULL_AGE = 23
TRAJECTORY_VETERAN_EMPHASIS = 0.5

# ── Stage D: recent form ──────────────────────────────────────────────────────

# Recency-weighted rating over the latest fixtures vs the season average.
# Deliberately small: form is noisy, and fair value should not chase it.
FORM_MIN_GAMES = 3
FORM_MIN_MINUTES_PER_GAME = 20
FORM_MAX_GAMES = 5
FORM_RECENCY_DECAY = 0.85  # weight of game k (0 = latest) = decay^k
FORM_SENSITIVITY = 0.08  # factor change per rating point above season avg
FORM_MAX_EFFECT = 0.08  # ± cap

# ── Stage E: contract ─────────────────────────────────────────────────────────

# (years remaining, factor) knots, linearly interpolated; beyond the last knot
# the factor is 1.0. Six months out a club can sign a pre-contract for free,
# so the fee collapses toward zero leverage.
CONTRACT_KNOTS: tuple[tuple[float, float], ...] = (
    (0.0, 0.30),
    (0.5, 0.50),
    (1.0, 0.70),
    (2.0, 0.88),
    (3.0, 1.00),
)
CONTRACT_FACTOR_UNKNOWN = 1.00  # no data → neutral, noted in the drivers

# ── Stage F: availability ─────────────────────────────────────────────────────

AVAILABILITY_SEASONS = 2
AVAILABILITY_FREE_ABOVE = 0.90  # ≥ 90% available → no discount
AVAILABILITY_FULL_DISCOUNT_AT = 0.50
AVAILABILITY_MAX_DISCOUNT = 0.20
# Matches missed for these reasons are discipline, not durability. Same terms
# as the injury-availability risk profile's D4, so the two signals agree.
AVAILABILITY_EXCLUDE_REASON_PATTERN = r"suspend|red card|yellow card|\bban\b"

# ── Stage G: market rate from comparable transfers ────────────────────────────

COMPS_LOOKBACK_DAYS = 3 * 365
COMPS_MIN_FEE_GBP = 500_000.0
# Fees are restated in today's money at this annual rate of fee inflation.
FEE_INFLATION_PER_YEAR = 0.06
# Reported fees are in their own currency; converted with the fx module's
# static fallback rates (£1 = €1.17 = $1.33) so a valuation is reproducible.
# Similarity kernel: w = exp(−|Δage|/AGE_SCALE) × exp(−|Δscore|/SCORE_SCALE)
#                        × exp(−years_ago/RECENCY_SCALE) × league × source.
COMPS_AGE_SCALE = 3.0
COMPS_SCORE_SCALE = 15.0
COMPS_RECENCY_SCALE = 2.0
# League similarity: exp(−|ln(coef_target / coef_comp)|) / LEAGUE_SCALE) —
# Premier League vs Ligue 1 ≈ 0.62, vs Eredivisie ≈ 0.36.
COMPS_LEAGUE_SCALE = 1.0
COMPS_SOURCE_WEIGHTS: dict[str, float] = {"TRANSFERX": 1.5, "REPORTED": 1.0}
COMPS_RATIO_CLIP = (0.25, 4.0)
COMPS_MIN_COUNT = 3
COMPS_MIN_WEIGHT = 0.05  # comps lighter than this are not "similar" at all
# Shrinkage of the market log-ratio toward 0: n_eff / (n_eff + K).
COMPS_SHRINKAGE_K = 4.0
MARKET_FACTOR_BOUNDS = (0.65, 1.60)
COMPS_MAX_REPORTED = 8  # top comps by weight returned for display

# ── Stage H: confidence ───────────────────────────────────────────────────────

# Levels reuse v1's rules (constants.py); v2 widens the band for players whose
# value is mostly potential, and narrows it slightly when the market agrees.
YOUTH_BAND_WIDENING_AGE = 21
YOUTH_BAND_WIDENING = 0.10
COMPS_BAND_NARROWING = 0.03  # applied when ≥ COMPS_MIN_COUNT comps were used
