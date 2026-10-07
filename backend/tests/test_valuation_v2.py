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
    MARKET_FACTOR_BOUNDS,
    POTENTIAL_MAX,
    TRAJECTORY_MAX,
)
from app.valuation.engine_v2 import MarketRate
from app.valuation.features import FeatureSet
from app.valuation.features_v2 import build_comparables_index, reference_season
from app.valuation.inputs_v2 import (
    CompRecord,
    FeatureSetV2,
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
    # halfway between (60, 2.30) and (70, 4.80) is their geometric mean
    assert engine_v2.value_curve(65) == pytest.approx(math.sqrt(2.30 * 4.80))


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


# ── Engine: orchestration ─────────────────────────────────────────────────────


def test_drivers_rebuild_the_value():
    fs = _fs(
        contract_years_remaining=1.5,
        recent_games=[RecentGame(8.4, 90)] * 5,
        games_missed_injured=20,
        games_available_total=60,
    )
    out = engine_v2.compute_valuation_v2(fs, [_comp(1.3) for _ in range(5)])
    rebuilt = out.drivers[0].value_after
    for d in out.drivers[1:]:
        rebuilt *= d.factor
    assert rebuilt == pytest.approx(out.drivers[-1].value_after)
    assert abs(rebuilt - out.fair_value) <= 50_000
    keys = [d.key for d in out.drivers]
    assert keys[:4] == ["anchor", "league", "performance", "age"]
    assert {"form", "contract", "availability", "market"} <= set(keys)


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
    await db.commit()
    await service.compute_and_store_valuation(db, p, comps=[_comp(1.2) for _ in range(5)])

    row = (
        (await db.execute(select(PlayerValuation).where(PlayerValuation.player_id == p.id)))
        .scalars()
        .one()
    )
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
    summary = _metrics([(r["v2_market"], r["actual"]) for r in rows])
    assert summary["n"] == 5 and summary["median_bias_pct"] < 0  # shrinkage → still under


async def test_unlisted_league_player_keeps_domestic_row_alongside_european_games(db):
    p = await _player(db)
    await _stats(db, p, league_id="119", minutes=2400, goals=15, league_name="Superliga")
    await _stats(db, p, league_id="2", minutes=540, goals=2, assists=1, shots_on_target=5,
                 key_passes=6, dribbles_success=8, league_name="UEFA Champions League")
    row = await service.compute_and_store_valuation(db, p, comps=[])
    season = row.inputs_json["features"]["seasons"][0]
    assert season["minutes"] == 2940  # domestic + Champions League
    assert season["league_id"] == "119"  # the domestic league sets the coefficient
