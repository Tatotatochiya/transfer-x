"""market-v2 valuation model tests.

Engine tests pin each factor's shape against constants_v2.py; service tests
check the DB-side inputs (multi-season aggregation, contract precedence,
availability, the comparables index) and the audit replay. A change to
constants_v2.py must update the expectations here in the same commit.
"""

import math
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from app.players.models import Contract, Player, PlayerPosition, PlayerTransfer
from app.stats.models import (
    PlayerFixtureRating,
    PlayerInjuryFixture,
    PlayerStats,
    TeamSeasonFixtures,
)
from app.valuation import engine_v2, service
from app.valuation.constants import ValuationConfidence
from app.valuation.constants_v2 import (
    AVAILABILITY_MAX_DISCOUNT,
    FEE_ANCHOR_FACTOR_BOUNDS,
    FEE_ANCHOR_RECENCY_YEARS,
    FEE_ANCHOR_SOURCE_CREDIBILITY,
    MARKET_FACTOR_BOUNDS,
    POTENTIAL_MAX,
    TRAJECTORY_MAX,
)
from app.valuation.engine_v2 import MarketRate
from app.valuation.features import FeatureSet
from app.valuation.features_v2 import (
    build_comparables_index,
    build_last_fee,
    build_seasons,
    reference_season,
)
from app.valuation.inputs_v2 import (
    CompRecord,
    FeatureSetV2,
    LastFee,
    RecentGame,
    SeasonFeatures,
    features_from_snapshot,
)
from app.valuation.models import PlayerValuation
from tests.conftest import _auth_headers, _register
from tests.test_deals import _get_club_id

FRESH = datetime.now(timezone.utc) - timedelta(days=1)


# ── Builders ──────────────────────────────────────────────────────────────────


def _season(
    pos="FWD",
    age=25,
    league="39",
    minutes=2700,
    season=2025,
    rating=7.6,
    g=24,
    a=9,
    sot=54,
    kp=45,
    drb=60,
    **extra,
) -> SeasonFeatures:
    n90 = minutes / 90
    fs = FeatureSet(
        player_id="p",
        position=pos,
        age=age,
        minutes=minutes,
        league_id=league,
        season=season,
        stats_updated_at=FRESH,
        avg_rating=rating,
        pass_accuracy=extra.get("pa", 0.0),
        duels_won_rate=extra.get("dw", 0.0),
        goals_per90=g / n90,
        assists_per90=a / n90,
        goals_plus_assists_per90=(g + a) / n90,
        shots_on_target_per90=sot / n90,
        key_passes_per90=kp / n90,
        dribbles_success_per90=drb / n90,
        defensive_actions_per90=extra.get("defa", 0) / n90,
        saves_per90=0.0,
        goals_conceded_per90=0.0,
    )
    return SeasonFeatures(season, minutes, league, fs)


def _fs(**overrides) -> FeatureSetV2:
    base = dict(player_id="p", position="FWD", age=25, seasons=[_season()])
    base.update(overrides)
    return FeatureSetV2(**base)


def _comp(ratio: float, **overrides) -> CompRecord:
    base = dict(
        player_id=str(uuid.uuid4()),
        player_name="Comp",
        position="FWD",
        age_at_transfer=25,
        score_at_transfer=80.0,
        league_coefficient=1.0,
        intrinsic_gbp=50_000_000.0,
        fee_gbp_today=50_000_000.0 * ratio,
        years_ago=0.5,
        source="REPORTED",
        fee_display="€ 1M",
        transfer_date="2025-07-01",
    )
    base.update(overrides)
    return CompRecord(**base)


def _last_fee(fee=60_000_000.0, years=1.0, **overrides) -> LastFee:
    base = dict(
        fee_gbp=fee,
        transfer_date="2025-07-01",
        years_since=years,
        source="REPORTED",
        age_at_transfer=24,
        score_at_transfer=None,
        minutes_at_transfer=2700.0,
        league_coefficient_at_transfer=1.0,
    )
    base.update(overrides)
    return LastFee(**base)


# ── Engine: performance evidence ──────────────────────────────────────────────


def test_single_full_season_shrinks_toward_prior():
    perf = engine_v2.performance_evidence([_season()])
    # raw = v1 Example A score 90.58; shrunk (2700·90.58 + 600·40) / 3300
    assert perf.raw_score == pytest.approx(90.583, abs=0.01)
    assert perf.score == pytest.approx((2700 * 90.5833 + 600 * 40) / 3300, abs=0.01)


def test_small_sample_shrinks_much_harder():
    big = engine_v2.performance_evidence([_season(minutes=2700)])
    small = engine_v2.performance_evidence([_season(minutes=600, g=5, a=2, sot=12, kp=10, drb=13)])
    assert small.score < big.score - 10


def test_older_season_blends_with_lower_weight():
    latest = _season(g=24)
    weak_prev = _season(season=2024, g=6, a=2, rating=6.6)
    both = engine_v2.performance_evidence([latest, weak_prev])
    alone = engine_v2.performance_evidence([latest])
    assert both.raw_score < alone.raw_score  # a weaker year pulls it down …
    assert both.raw_score > engine_v2.season_score(weak_prev) + 0.5 * (  # … but < half way
        engine_v2.season_score(latest) - engine_v2.season_score(weak_prev)
    )


def test_tiny_older_season_is_ignored():
    with_tiny = engine_v2.performance_evidence([_season(), _season(season=2024, minutes=200, g=0)])
    assert with_tiny.seasons_used == 1


# ── Engine: curve, league ─────────────────────────────────────────────────────


def test_value_curve_is_one_at_fifty_and_monotonic():
    assert engine_v2.value_curve(50) == pytest.approx(1.0)
    values = [engine_v2.value_curve(s) for s in range(0, 101, 5)]
    assert values == sorted(values)


def test_value_curve_log_linear_between_knots():
    # halfway between (60, 1.278) and (70, 2.222) is their geometric mean
    assert engine_v2.value_curve(65) == pytest.approx(math.sqrt(1.278 * 2.222))


def test_premier_league_premium_over_other_top_five():
    assert engine_v2.league_coefficient("39") > engine_v2.league_coefficient("140")
    assert engine_v2.league_coefficient("140") > engine_v2.league_coefficient("61")
    assert engine_v2.league_coefficient("999999") == engine_v2.league_coefficient(None)


# ── Engine: age, potential, trajectory ────────────────────────────────────────


def test_no_youth_discount_and_position_specific_decline():
    assert engine_v2.age_factor("FWD", 18) == 1.0
    assert engine_v2.age_factor("FWD", 28) == 1.0
    assert engine_v2.age_factor("FWD", 29) < 1.0
    # goalkeepers peak later: a 30-year-old keeper has lost nothing
    assert engine_v2.age_factor("GK", 30) == 1.0
    assert (
        engine_v2.age_factor("FWD", 33)
        < engine_v2.age_factor("FWD", 31)
        < engine_v2.age_factor("FWD", 29)
    )


def test_decline_accelerates():
    drops = [
        engine_v2.age_factor("MID", a) / engine_v2.age_factor("MID", a - 1) for a in range(30, 35)
    ]
    assert drops == sorted(drops, reverse=True)


def test_potential_requires_youth_quality_and_evidence():
    full = engine_v2.potential_premium("FWD", 18, 75.0, 3000)
    assert full == pytest.approx(1 + POTENTIAL_MAX)
    assert engine_v2.potential_premium("FWD", 24, 75.0, 3000) == 1.0  # at peak start
    assert engine_v2.potential_premium("FWD", 18, 30.0, 3000) == 1.0  # not performing
    assert engine_v2.potential_premium("FWD", 18, 75.0, 500) < 1 + POTENTIAL_MAX / 3  # unproven
    assert engine_v2.potential_premium("FWD", 21, 75.0, 3000) < engine_v2.potential_premium(
        "FWD", 19, 75.0, 3000
    )


def test_trajectory_rewards_improvement_more_for_young_players():
    improving = [_season(g=24), _season(season=2024, g=10, a=3, rating=7.0)]
    young, delta = engine_v2.trajectory_factor(improving, 21)
    veteran, _ = engine_v2.trajectory_factor(improving, 30)
    assert delta > 0
    assert 1.0 < veteran < young <= 1 + TRAJECTORY_MAX


def test_trajectory_neutral_without_two_real_seasons():
    assert engine_v2.trajectory_factor([_season()], 21) == (1.0, None)
    short = [_season(), _season(season=2024, minutes=500)]
    assert engine_v2.trajectory_factor(short, 21) == (1.0, None)


# ── Engine: form, contract, availability ──────────────────────────────────────


def test_form_needs_enough_games_and_is_capped():
    hot = [RecentGame(9.5, 90)] * 5
    factor, recent = engine_v2.form_factor(hot, 7.0)
    assert factor == pytest.approx(1.08) and recent == pytest.approx(9.5)
    assert engine_v2.form_factor([RecentGame(9.0, 90)] * 2, 7.0) == (1.0, None)
    assert engine_v2.form_factor([RecentGame(9.0, 10)] * 5, 7.0) == (1.0, None)  # cameo minutes
    assert engine_v2.form_factor(hot, None) == (1.0, None)


def test_contract_factor_knots_and_interpolation():
    assert engine_v2.contract_factor(None) == 1.0
    assert engine_v2.contract_factor(5.0) == 1.0
    assert engine_v2.contract_factor(3.0) == pytest.approx(1.0)
    assert engine_v2.contract_factor(0.5) == pytest.approx(0.50)
    assert engine_v2.contract_factor(1.5) == pytest.approx((0.70 + 0.88) / 2)
    assert engine_v2.contract_factor(-0.2) == pytest.approx(0.30)  # expired → floor


def test_availability_discount():
    assert engine_v2.availability_factor(None) == 1.0
    assert engine_v2.availability_factor(0.95) == 1.0
    assert engine_v2.availability_factor(0.70) == pytest.approx(1 - AVAILABILITY_MAX_DISCOUNT / 2)
    assert engine_v2.availability_factor(0.30) == pytest.approx(1 - AVAILABILITY_MAX_DISCOUNT)


# ── Engine: market rate ───────────────────────────────────────────────────────


def test_market_needs_minimum_comps():
    m = engine_v2.market_rate(
        [_comp(1.5), _comp(1.5)], player_id="p", position="FWD", age=25, score=80.0, coef=1.0
    )
    assert m.factor == 1.0 and m.comps_used == 2


def test_market_premium_is_shrunk_and_bounded():
    comps = [_comp(1.5) for _ in range(4)]
    m = engine_v2.market_rate(comps, player_id="p", position="FWD", age=25, score=80.0, coef=1.0)
    assert m.weighted_median_ratio == pytest.approx(1.5)
    assert 1.0 < m.factor < 1.5  # pulled toward 1 by shrinkage
    many = [_comp(10.0, source="TRANSFERX") for _ in range(50)]
    m = engine_v2.market_rate(many, player_id="p", position="FWD", age=25, score=80.0, coef=1.0)
    assert m.factor == MARKET_FACTOR_BOUNDS[1]


def test_market_ignores_other_positions_and_own_transfers():
    comps = [_comp(2.0, position="DEF") for _ in range(5)] + [
        _comp(2.0, player_id="p") for _ in range(5)
    ]
    m = engine_v2.market_rate(comps, player_id="p", position="FWD", age=25, score=80.0, coef=1.0)
    assert m.comps_used == 0 and m.factor == 1.0


def test_similar_comps_outweigh_dissimilar_ones():
    near = [_comp(1.6) for _ in range(4)]
    far = [
        _comp(0.5, age_at_transfer=33, score_at_transfer=50.0, league_coefficient=0.2)
        for _ in range(4)
    ]
    m = engine_v2.market_rate(
        near + far, player_id="p", position="FWD", age=25, score=80.0, coef=1.0
    )
    assert m.factor > 1.0


# ── Engine: last-fee anchor (market-v3) ───────────────────────────────────────


def test_fee_above_model_raises_value_and_below_lowers_it():
    base = engine_v2.compute_valuation_v2(_fs())
    up = engine_v2.compute_valuation_v2(_fs(last_fee=_last_fee(fee=200_000_000.0)))
    down = engine_v2.compute_valuation_v2(_fs(last_fee=_last_fee(fee=10_000_000.0)))
    assert up.fair_value > base.fair_value
    assert down.fair_value < base.fair_value
    driver = next(d for d in up.drivers if d.key == "fee_anchor")
    assert driver.factor != 1.0
    assert up.fee_anchor.applied is True


def test_fee_anchor_factor_is_bounded():
    lo, hi = FEE_ANCHOR_FACTOR_BOUNDS
    huge = engine_v2.compute_valuation_v2(_fs(last_fee=_last_fee(fee=1_000_000_000.0)))
    tiny = engine_v2.compute_valuation_v2(_fs(last_fee=_last_fee(fee=100_000.0)))
    assert huge.fee_anchor.factor == pytest.approx(hi)
    assert tiny.fee_anchor.factor == pytest.approx(lo)


def test_fee_anchor_weight_falls_with_age_of_fee():
    recent = engine_v2.compute_valuation_v2(
        _fs(last_fee=_last_fee(fee=200_000_000.0, years=0.5))
    )
    older = engine_v2.compute_valuation_v2(
        _fs(last_fee=_last_fee(fee=200_000_000.0, years=3.0))
    )
    assert 1.0 < older.fee_anchor.factor < recent.fee_anchor.factor


def test_old_reported_fee_is_not_applied_and_says_why():
    base = engine_v2.compute_valuation_v2(_fs())
    out = engine_v2.compute_valuation_v2(
        _fs(last_fee=_last_fee(fee=100_000_000.0, years=6.0, transfer_date="2020-07-01"))
    )
    assert out.fair_value == base.fair_value
    assert out.fee_anchor.applied is False
    assert "2020" in out.fee_anchor.reason
    assert "too old" in out.fee_anchor.reason
    neutral = next(d for d in out.drivers if d.key == "fee_anchor")
    assert neutral.factor == 1.0


def test_a_skip_reason_names_thin_evidence_not_age():
    out = engine_v2.compute_valuation_v2(
        _fs(last_fee=_last_fee(fee=100_000_000.0, years=0.5, minutes_at_transfer=540))
    )
    assert out.fee_anchor.applied is False
    assert "little playing time on record" in out.fee_anchor.reason
    assert "too old" not in out.fee_anchor.reason


def test_a_skip_reason_names_an_unknown_source():
    out = engine_v2.compute_valuation_v2(
        _fs(last_fee=_last_fee(fee=100_000_000.0, source="UNKNOWN", years=0.5))
    )
    assert out.fee_anchor.applied is False
    assert "weakly sourced" in out.fee_anchor.reason


def test_a_skip_reason_names_the_release_clause():
    out = engine_v2.compute_valuation_v2(
        _fs(last_fee=_last_fee(fee=200_000_000.0, basis="RELEASE_CLAUSE"))
    )
    assert out.fee_anchor.applied is False
    assert "release clause" in out.fee_anchor.reason


def test_a_later_free_move_stops_the_anchor():
    base = engine_v2.compute_valuation_v2(_fs())
    out = engine_v2.compute_valuation_v2(
        _fs(
            last_fee=_last_fee(
                fee=100_000_000.0,
                years=3.0,
                transfer_date="2022-07-01",
                later_free_move="2025-08-01",
            )
        )
    )
    assert out.fair_value == base.fair_value
    assert out.fee_anchor.applied is False
    assert "free transfer" in out.fee_anchor.reason
    assert "2022" in out.fee_anchor.reason


def test_fee_anchor_overrides_default_to_the_constants():
    """The backtest's --grid overrides must not change production behaviour."""
    fee = _last_fee(fee=200_000_000.0)
    kwargs = dict(
        position="FWD",
        age=25,
        score=80.0,
        coef=1.0,
        contract_f=0.8,
        availability_f=1.0,
        value_before=50_000_000.0,
    )
    default = engine_v2.fee_anchor(fee, **kwargs)
    explicit = engine_v2.fee_anchor(
        fee,
        **kwargs,
        source_credibility=FEE_ANCHOR_SOURCE_CREDIBILITY,
        recency_years=FEE_ANCHOR_RECENCY_YEARS,
    )
    assert (default.factor, default.weight, default.reason) == (
        explicit.factor,
        explicit.weight,
        explicit.reason,
    )


def test_fee_anchor_worked_example():
    """Appendix B, computed from the real constants rather than pasted."""
    fee = LastFee(
        fee_gbp=100_000_000.0,
        transfer_date="2023-07-01",
        years_since=3.3,
        source="REPORTED",
        basis="PERMANENT",
        age_at_transfer=27,
        score_at_transfer=62.0,
        minutes_at_transfer=2700.0,
        league_coefficient_at_transfer=1.0,
    )
    contract = engine_v2.contract_factor(1.6)
    anchor = engine_v2.fee_anchor(
        fee,
        position="MID",
        age=27,
        score=70.0,
        coef=1.0,
        contract_f=contract,
        availability_f=1.0,
        value_before=45_000_000.0,
    )
    fee_today = 100_000_000.0 * (1 + engine_v2.FEE_INFLATION_PER_YEAR) ** 3.3
    anchor_value = fee_today * math.sqrt(70 / 62) * contract
    expected_weight = 0.65 * 1.0 * (1 / (1 + 3.3 / 3)) * 1.0
    expected_factor = math.exp(expected_weight * math.log(anchor_value / 45_000_000.0))
    assert anchor.applied is True
    assert anchor.weight == pytest.approx(expected_weight)
    assert anchor.factor == pytest.approx(expected_factor)
    assert anchor.weight == pytest.approx(0.310, abs=0.001)
    assert anchor.factor == pytest.approx(1.297, abs=0.005)


def test_source_credibility_orders_the_pull():
    def factor(source: str) -> float:
        return engine_v2.compute_valuation_v2(
            _fs(last_fee=_last_fee(fee=200_000_000.0, source=source))
        ).fee_anchor.factor

    assert factor("TRANSFERX") > factor("MANUAL") > factor("REPORTED") > 1.0


def test_release_clause_basis_weighs_less():
    permanent = engine_v2.compute_valuation_v2(
        _fs(last_fee=_last_fee(fee=200_000_000.0))
    )
    clause = engine_v2.compute_valuation_v2(
        _fs(last_fee=_last_fee(fee=200_000_000.0, basis="RELEASE_CLAUSE"))
    )
    assert clause.fee_anchor.factor < permanent.fee_anchor.factor
    assert clause.fee_anchor.applied is False  # weight drops below the minimum


def test_fee_paid_on_little_playing_time_is_skipped():
    out = engine_v2.compute_valuation_v2(
        _fs(last_fee=_last_fee(minutes_at_transfer=300))
    )
    assert out.fee_anchor.applied is False
    assert "playing time" in out.fee_anchor.reason


def test_unknown_pre_move_stats_reduce_the_weight():
    known = engine_v2.compute_valuation_v2(
        _fs(last_fee=_last_fee(fee=200_000_000.0))
    )
    unknown = engine_v2.compute_valuation_v2(
        _fs(last_fee=_last_fee(fee=200_000_000.0, minutes_at_transfer=None))
    )
    assert unknown.fee_anchor.applied is True
    assert unknown.fee_anchor.weight == pytest.approx(known.fee_anchor.weight * 0.6)


def test_outgrown_fee_is_skipped():
    base = engine_v2.compute_valuation_v2(_fs(age=22))
    out = engine_v2.compute_valuation_v2(
        _fs(
            age=22,
            last_fee=_last_fee(
                fee=60_000_000.0,
                years=3.0,
                score_at_transfer=base.performance.score - 20,
            ),
        )
    )
    assert out.fee_anchor.applied is False
    assert "outgrown" in out.fee_anchor.reason


def test_expiring_contract_pulls_the_anchor_down():
    short = engine_v2.compute_valuation_v2(
        _fs(contract_years_remaining=0.5, last_fee=_last_fee(fee=200_000_000.0))
    )
    long = engine_v2.compute_valuation_v2(
        _fs(contract_years_remaining=4.0, last_fee=_last_fee(fee=200_000_000.0))
    )
    assert short.fee_anchor.anchor_value < long.fee_anchor.anchor_value


def test_release_clause_still_caps_after_the_anchor():
    out = engine_v2.compute_valuation_v2(
        _fs(release_clause_gbp=170_000_000.0, last_fee=_last_fee(fee=1_000_000_000.0))
    )
    assert out.drivers[-1].key == "release_clause"
    assert out.fair_value == 170_000_000


def test_no_fee_means_no_anchor_driver():
    out = engine_v2.compute_valuation_v2(_fs())
    assert "fee_anchor" not in {d.key for d in out.drivers}
    assert out.fair_value == engine_v2.compute_valuation_v2(
        _fs(), use_fee_anchor=False
    ).fair_value


def test_use_fee_anchor_false_reproduces_v2():
    with_fee = _fs(last_fee=_last_fee(fee=1_000_000_000.0))
    assert (
        engine_v2.compute_valuation_v2(with_fee, use_fee_anchor=False).fair_value
        == engine_v2.compute_valuation_v2(_fs()).fair_value
    )


# ── Engine: orchestration ─────────────────────────────────────────────────────


def test_drivers_rebuild_the_value():
    fs = _fs(
        contract_years_remaining=1.5,
        recent_games=[RecentGame(8.4, 90)] * 5,
        games_missed_injured=20,
        games_available_total=60,
        last_fee=_last_fee(fee=200_000_000.0),
    )
    out = engine_v2.compute_valuation_v2(fs, [_comp(1.3) for _ in range(5)])
    rebuilt = out.drivers[0].value_after
    for d in out.drivers[1:]:
        rebuilt *= d.factor
    assert rebuilt == pytest.approx(out.drivers[-1].value_after)
    assert abs(rebuilt - out.fair_value) <= 50_000
    keys = [d.key for d in out.drivers]
    assert keys[:4] == ["anchor", "league", "performance", "age"]
    assert {"form", "contract", "availability", "market", "fee_anchor"} <= set(keys)


def test_expiring_contract_halves_value():
    long = engine_v2.compute_valuation_v2(_fs(contract_years_remaining=4.0))
    short = engine_v2.compute_valuation_v2(_fs(contract_years_remaining=0.5))
    assert short.fair_value == pytest.approx(long.fair_value * 0.5, rel=0.01)


def test_release_clause_caps_value_and_band():
    out = engine_v2.compute_valuation_v2(_fs(release_clause_gbp=60_000_000.0))
    assert out.fair_value == 60_000_000
    assert out.fair_value_high <= 60_000_000
    assert out.drivers[-1].key == "release_clause"


def test_youth_widens_band_comps_narrow_it():
    peak = engine_v2.compute_valuation_v2(_fs())
    young = engine_v2.compute_valuation_v2(_fs(age=20))
    with_comps = engine_v2.compute_valuation_v2(_fs(), [_comp(1.0) for _ in range(5)])
    assert young.band > peak.band > with_comps.band


def test_confidence_reuses_v1_rules():
    assert engine_v2.compute_valuation_v2(_fs()).confidence == ValuationConfidence.HIGH
    low = _fs(seasons=[_season(minutes=500, g=4, a=1, sot=9, kp=8, drb=10)])
    assert engine_v2.compute_valuation_v2(low).confidence == ValuationConfidence.LOW


def test_elite_teenager_worth_more_than_same_output_at_27():
    teen = engine_v2.compute_valuation_v2(_fs(age=18))
    prime = engine_v2.compute_valuation_v2(_fs(age=27))
    assert teen.fair_value > prime.fair_value * 1.5


# ── Fee parsing ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "display, expected",
    [
        ("€ 42M", 42e6 / 1.17),
        ("€42.5M", 42.5e6 / 1.17),
        ("£ 15M", 15e6),
        ("$ 3M", 3e6 / 1.33),
        ("€ 500K", 500e3 / 1.17),
        ("€ 1,5M", 1.5e6 / 1.17),
        ("Free", None),
        ("N/A", None),
        (None, None),
    ],
)
def test_parse_fee(display, expected):
    got = engine_v2.parse_fee(display, {"EUR": 1.17, "USD": 1.33})
    assert got == (pytest.approx(expected) if expected is not None else None)


def test_reference_season():
    assert reference_season(date(2025, 7, 15)) == 2024
    assert reference_season(date(2025, 1, 20)) == 2024
    assert reference_season(date(2025, 10, 2)) == 2025


# ── Service: DB inputs ────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def club(client: AsyncClient) -> dict:
    return await _register(client, "v2club@test.com", club_name="V2 FC")


async def _player(db, *, age=25, position=PlayerPosition.FWD, name="V2 Player", **extra) -> Player:
    p = Player(name=name, age=age, position=position, **extra)
    db.add(p)
    await db.commit()
    return p


async def _stats(db, player: Player, **overrides) -> None:
    values = dict(
        player_id=player.id,
        vendor="api_sports_v3",
        league_id="39",
        season="2025",
        minutes=2700,
        appearances=30,
        goals=24,
        assists=9,
        shots_on_target=54,
        key_passes=45,
        dribbles_success=60,
        avg_rating=Decimal("7.6"),
        team_vendor_id="50",
        league_name="Premier League",
    )
    values.update(overrides)
    db.add(PlayerStats(**values))
    await db.commit()


async def test_service_aggregates_mid_season_move(db):
    p = await _player(db)
    await _stats(
        db,
        p,
        minutes=1350,
        goals=12,
        assists=4,
        shots_on_target=27,
        key_passes=22,
        dribbles_success=30,
        appearances=15,
    )
    await _stats(
        db,
        p,
        league_id="140",
        minutes=1350,
        goals=12,
        assists=5,
        shots_on_target=27,
        key_passes=23,
        dribbles_success=30,
        appearances=15,
        league_name="La Liga",
    )
    row = await service.compute_and_store_valuation(db, p, comps=[])
    season = row.inputs_json["features"]["seasons"][0]
    assert season["minutes"] == 2700  # both spells counted
    assert season["features"]["goals_per90"] == pytest.approx(0.8)


async def test_service_eligibility_uses_latest_season_minutes(db):
    p = await _player(db)
    await _stats(db, p, season="2024", minutes=3000)
    await _stats(db, p, season="2025", minutes=400)
    assert await service.compute_and_store_valuation(db, p, comps=[]) is None


async def test_transferx_contract_beats_vendor_expiry(client, club, db):
    club_id = await _get_club_id(client, _auth_headers(club))
    p = await _player(db, contract_expiry=date.today() + timedelta(days=4 * 365))
    await _stats(db, p)
    db.add(
        Contract(
            player_id=p.id,
            club_id=uuid.UUID(club_id),
            is_active=True,
            end_date=date.today() + timedelta(days=180),
            release_clause=Decimal("40000000"),
            club_valuation=Decimal("1"),
        )
    )
    await db.commit()
    row = await service.compute_and_store_valuation(db, p, comps=[])
    feats = row.inputs_json["features"]
    assert feats["contract_source"] == "TRANSFERX"
    assert feats["contract_years_remaining"] == pytest.approx(0.49, abs=0.01)
    # 6 months left → heavy discount; then the public release clause caps it
    assert float(row.fair_value) <= 40_000_000
    # the holding club's private valuation is never an input
    assert "club_valuation" not in str(row.inputs_json)


async def test_vendor_expiry_used_without_a_contract(db):
    p = await _player(db, contract_expiry=date.today() + timedelta(days=365))
    await _stats(db, p)
    row = await service.compute_and_store_valuation(db, p, comps=[])
    assert row.inputs_json["features"]["contract_source"] == "VENDOR"


async def test_availability_counts_injuries_not_suspensions(db):
    p = await _player(db)
    await _stats(db, p)
    db.add(TeamSeasonFixtures(team_vendor_id="50", league_id="39", season="2025", played=38))
    for i in range(10):
        db.add(
            PlayerInjuryFixture(
                player_id=p.id,
                fixture_vendor_id=f"f{i}",
                league_id="39",
                season="2025",
                team_vendor_id="50",
                injury_type="Missing Fixture",
                reason="Hamstring Injury",
            )
        )
    for i in range(4):
        db.add(
            PlayerInjuryFixture(
                player_id=p.id,
                fixture_vendor_id=f"s{i}",
                league_id="39",
                season="2025",
                team_vendor_id="50",
                injury_type="Missing Fixture",
                reason="Suspended",
            )
        )
    await db.commit()
    row = await service.compute_and_store_valuation(db, p, comps=[])
    feats = row.inputs_json["features"]
    assert (feats["games_missed_injured"], feats["games_available_total"]) == (10, 38)
    assert any(d["key"] == "availability" for d in row.inputs_json["drivers"])


async def test_availability_unknown_without_team_fixture_counts(db):
    p = await _player(db)
    await _stats(db, p)
    row = await service.compute_and_store_valuation(db, p, comps=[])
    assert row.inputs_json["features"]["games_available_total"] is None


async def test_recent_form_read_from_fixture_ratings(db):
    p = await _player(db)
    await _stats(db, p)
    for i in range(5):
        db.add(
            PlayerFixtureRating(
                player_id=p.id,
                fixture_vendor_id=f"r{i}",
                fixture_date=date.today() - timedelta(days=7 * i),
                minutes=90,
                rating=Decimal("8.4"),
            )
        )
    await db.commit()
    row = await service.compute_and_store_valuation(db, p, comps=[])
    form = next(d for d in row.inputs_json["drivers"] if d["key"] == "form")
    assert form["factor"] > 1.0


async def test_comparables_index_reported_and_transferx_deduped(client, club, db):
    from app.deals.models import Deal, DealStage, DealStatus, DealType

    buyer = uuid.UUID(await _get_club_id(client, _auth_headers(club)))
    when = date.today() - timedelta(days=200)
    sold = await _player(db, name="Reported Sale", age=24)
    await _stats(db, sold, season=str(reference_season(when)))
    db.add(
        PlayerTransfer(
            player_id=sold.id,
            vendor="api_sports_v3",
            transfer_date=when,
            transfer_type="Transfer",
            fee_display="€ 58.5M",
            team_out_name="A",
            team_in_name="B",
        )
    )
    both = await _player(db, name="Platform Sale", age=26)
    await _stats(db, both, season=str(reference_season(when)))
    db.add(
        PlayerTransfer(
            player_id=both.id,
            vendor="api_sports_v3",
            transfer_date=when,
            transfer_type="Transfer",
            fee_display="€ 99M",
        )
    )
    db.add(
        Deal(
            buyer_club_id=buyer,
            player_id=both.id,
            agreed_fee=Decimal("45000000"),
            status=DealStatus.COMPLETED,
            stage=DealStage.COMPLETED,
            deal_type=DealType.PERMANENT,
            completed_at=datetime.combine(
                when + timedelta(days=10), datetime.min.time(), timezone.utc
            ),
        )
    )
    free = await _player(db, name="Free Move")
    await _stats(db, free, season=str(reference_season(when)))
    db.add(
        PlayerTransfer(
            player_id=free.id,
            vendor="api_sports_v3",
            transfer_date=when,
            transfer_type="Transfer",
            fee_display="Free",
        )
    )
    await db.commit()

    comps = await build_comparables_index(db)
    by_name = {c.player_name: c for c in comps}
    assert set(by_name) == {"Reported Sale", "Platform Sale"}
    assert by_name["Platform Sale"].source == "TRANSFERX"  # the verified fee wins
    reported = by_name["Reported Sale"]
    assert reported.age_at_transfer == 23  # he was a year younger when sold
    assert reported.fee_gbp_today > 58.5e6 / 1.17  # restated in today's money
    assert reported.intrinsic_gbp > 0


async def test_market_rate_applied_end_to_end(db):
    target = await _player(db, name="Target")
    await _stats(db, target)
    comps = [_comp(1.5) for _ in range(6)]
    row = await service.compute_and_store_valuation(db, target, comps=comps)
    assert row.inputs_json["market"]["comps_used"] == 6
    market = next(d for d in row.inputs_json["drivers"] if d["key"] == "market")
    assert market["factor"] > 1.0


async def test_service_stores_and_serves_the_fee_anchor(client, db):
    viewer = await _register(client, "anchor_viewer@test.com", club_name="Anchor FC")
    p = await _player(db)
    await _stats(db, p)
    db.add(
        PlayerTransfer(
            player_id=p.id,
            vendor="api_sports_v3",
            transfer_date=date.today() - timedelta(days=365),
            transfer_type="Transfer",
            fee_display="€ 60M",
            team_out_name="A",
            team_in_name="B",
        )
    )
    await db.commit()

    row = await service.compute_and_store_valuation(db, p, comps=[])
    assert row.inputs_json["fee_anchor"]["applied"] is True
    assert row.inputs_json["features"]["last_fee"]["source"] == "REPORTED"
    assert row.model_version == "market-v3"

    resp = await client.get(f"/valuation/players/{p.id}", headers=_auth_headers(viewer))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["fee_anchor"]["applied"] is True
    assert any(d["key"] == "fee_anchor" for d in data["drivers"])


async def test_fee_anchor_switched_off_stores_a_market_v2_row(client, db, monkeypatch):
    """Production ships with the anchor off: the same player with the same fee
    is valued, labelled and replayed exactly as market-v2."""
    from app.config import settings

    viewer = await _register(client, "anchor_off@test.com", club_name="Anchor Off FC")
    p = await _player(db)
    await _stats(db, p)
    db.add(
        PlayerTransfer(
            player_id=p.id,
            vendor="api_sports_v3",
            transfer_date=date.today() - timedelta(days=365),
            transfer_type="Transfer",
            fee_display="€ 60M",
            team_out_name="A",
            team_in_name="B",
        )
    )
    await db.commit()

    on = await service.compute_and_store_valuation(db, p, comps=[])
    assert on.inputs_json["fee_anchor"]["applied"] is True

    monkeypatch.setattr(settings, "valuation_fee_anchor_enabled", False)
    off = await service.compute_and_store_valuation(db, p, comps=[])
    await db.commit()
    assert off.model_version == "market-v2"
    assert off.inputs_json["fee_anchor"] is None
    assert off.inputs_json["features"]["last_fee"] is None
    assert all(d["key"] != "fee_anchor" for d in off.inputs_json["drivers"])
    assert off.fair_value != on.fair_value

    # The value is the engine's without the anchor, and the row replays from
    # its own inputs with no knowledge of the switch.
    fs = features_from_snapshot(on.inputs_json["features"])
    assert float(off.fair_value) == engine_v2.compute_valuation_v2(
        fs, [], use_fee_anchor=False
    ).fair_value
    replay = engine_v2.compute_valuation_v2(
        features_from_snapshot(off.inputs_json["features"]),
        market=MarketRate(**off.inputs_json["market"]),
    )
    assert replay.fair_value == float(off.fair_value)

    # The batch job honours the switch too, and never loads the fees.
    counts = await service.compute_all_valuations(db)
    assert counts["fee_anchored"] == 0

    # The last fee is still shown beside the value; there is no anchor to explain.
    resp = await client.get(f"/valuation/players/{p.id}", headers=_auth_headers(viewer))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["model_version"] == "market-v2"
    assert data["fee_anchor"] is None
    assert data["last_transfer"]["source"] == "API-Football"


async def test_own_transfer_still_never_enters_market_rate(db):
    when = date.today() - timedelta(days=200)
    target = await _player(db, name="Self Priced")
    await _stats(db, target, season=str(reference_season(when)))
    db.add(
        PlayerTransfer(
            player_id=target.id,
            vendor="api_sports_v3",
            transfer_date=when,
            transfer_type="Transfer",
            fee_display="€ 50M",
        )
    )
    for i in range(4):
        other = await _player(db, name=f"Comparable {i}")
        await _stats(db, other, season=str(reference_season(when)))
        db.add(
            PlayerTransfer(
                player_id=other.id,
                vendor="api_sports_v3",
                transfer_date=when,
                transfer_type="Transfer",
                fee_display="€ 60M",
            )
        )
    await db.commit()

    comps = await build_comparables_index(db)
    assert str(target.id) in {c.player_id for c in comps}  # his own fee is in the index
    market = engine_v2.market_rate(
        comps, player_id=str(target.id), position="FWD", age=25, score=80.0, coef=1.0
    )
    assert market.comps_used == 4
    assert str(target.id) not in {c["player_id"] for c in market.top_comps}


async def test_last_fee_context_uses_pre_move_seasons_only(db):
    from app.players.last_fee import last_transfer_fees
    from app.stats.models import PlayerStats

    p = await _player(db, name="Pre Move")
    await _stats(
        db,
        p,
        season="2023",
        minutes=2700,
        goals=4,
        assists=1,
        shots_on_target=10,
        key_passes=10,
        dribbles_success=10,
    )
    await _stats(
        db,
        p,
        season="2025",
        minutes=2700,
        goals=30,
        assists=12,
        shots_on_target=70,
        key_passes=60,
        dribbles_success=80,
    )
    db.add(
        PlayerTransfer(
            player_id=p.id,
            vendor="api_sports_v3",
            transfer_date=date(2024, 7, 15),
            transfer_type="Transfer",
            fee_display="€ 40M",
        )
    )
    await db.commit()

    fee = (await last_transfer_fees(db, [p.id]))[p.id]
    stats = (
        (await db.execute(select(PlayerStats).where(PlayerStats.player_id == p.id)))
        .scalars()
        .all()
    )
    last_fee = build_last_fee(p, fee, list(stats), date.today())
    expected = engine_v2.performance_evidence(
        build_seasons(str(p.id), "FWD", 25, list(stats), up_to_season=2023)
    )
    assert last_fee.score_at_transfer == pytest.approx(expected.score)
    assert last_fee.minutes_at_transfer == pytest.approx(expected.weighted_minutes)
    # The far better 2025 season did not exist when the buyer paid the fee.
    full = engine_v2.performance_evidence(build_seasons(str(p.id), "FWD", 25, list(stats)))
    assert full.score > last_fee.score_at_transfer + 10


async def test_v2_row_replays_exactly_from_inputs_json(client, club, db):
    club_id = await _get_club_id(client, _auth_headers(club))
    p = await _player(db, age=20)
    await _stats(db, p, season="2024", minutes=1800, goals=8, assists=3)
    await _stats(db, p)
    db.add(
        Contract(
            player_id=p.id,
            club_id=uuid.UUID(club_id),
            is_active=True,
            end_date=date.today() + timedelta(days=500),
        )
    )
    for i in range(4):
        db.add(
            PlayerFixtureRating(
                player_id=p.id,
                fixture_vendor_id=f"q{i}",
                minutes=90,
                fixture_date=date.today() - timedelta(days=i),
                rating=Decimal("7.1"),
            )
        )
    # A last fee in the snapshot, so replay runs the market-v3 anchor too.
    db.add(
        PlayerTransfer(
            player_id=p.id,
            vendor="api_sports_v3",
            transfer_date=date.today() - timedelta(days=400),
            transfer_type="Transfer",
            fee_display="€ 70M",
        )
    )
    await db.commit()
    await service.compute_and_store_valuation(db, p, comps=[_comp(1.2) for _ in range(5)])

    row = (
        (await db.execute(select(PlayerValuation).where(PlayerValuation.player_id == p.id)))
        .scalars()
        .one()
    )
    assert row.inputs_json["fee_anchor"]["applied"] is True
    replay = engine_v2.compute_valuation_v2(
        features_from_snapshot(row.inputs_json["features"]),
        now=row.computed_at,
        market=MarketRate(**row.inputs_json["market"]),
    )
    assert replay.fair_value == float(row.fair_value)
    assert replay.fair_value_low == float(row.fair_value_low)
    assert replay.fair_value_high == float(row.fair_value_high)
    assert replay.confidence == row.confidence
    assert round(replay.performance.score, 2) == float(row.performance_score)


# ── Backtest script ───────────────────────────────────────────────────────────


def test_backtest_rows_predict_each_model_leave_one_out():
    from scripts.valuation_backtest import _metrics, backtest_rows

    comps = [_comp(1.4, reference=_season()) for _ in range(5)]
    comps.append(_comp(1.4))  # no reference season → skipped
    rows = backtest_rows(comps)
    assert len(rows) == 5
    for r in rows:
        assert r["comps_used"] == 5  # the other five, never itself
        assert r["v2_market"] > r["v2_intrinsic"]  # market paid above model
        assert r["v1"] > 0
        # No earlier fee on these comps: the anchor is neutral and changes nothing.
        assert r["prev_fee_gbp"] is None
        assert r["anchor_applied"] is False
        assert r["v3_anchor"] == r["v2_market"]
    summary = _metrics([(r["v2_market"], r["actual"]) for r in rows])
    assert summary["n"] == 5 and summary["median_bias_pct"] < 0  # shrinkage → still under

    with_fee = [_comp(1.4, reference=_season(), prev_fee=_last_fee(fee=200_000_000.0))]
    anchored = backtest_rows(with_fee)
    assert anchored[0]["anchor_applied"] is True
    assert anchored[0]["v3_anchor"] != anchored[0]["v2_market"]


async def test_unlisted_league_player_keeps_domestic_row_alongside_european_games(db):
    p = await _player(db)
    await _stats(db, p, league_id="119", minutes=2400, goals=15, league_name="Superliga")
    await _stats(db, p, league_id="2", minutes=540, goals=2, assists=1, shots_on_target=5,
                 key_passes=6, dribbles_success=8, league_name="UEFA Champions League")
    row = await service.compute_and_store_valuation(db, p, comps=[])
    season = row.inputs_json["features"]["seasons"][0]
    assert season["minutes"] == 2940  # domestic + Champions League
    assert season["league_id"] == "119"  # the domestic league sets the coefficient
