"""TRA-91 — fair-value valuation signal tests.

The worked examples A/B/C are exact fixtures from
docs/feature_spec/fair-value-vs-asking-signal.md, within its stated tolerances:
performance_score ± 0.05, money ± £100,000, divergence ± 0.2 pct-points.
They are the regression net for any future tuning of valuation/constants.py —
a constant change must update these expectations in the same commit.
"""
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from app.stats.models import PlayerStats
from app.valuation import engine
from app.valuation.constants import DivergenceBand, ValuationConfidence
from app.valuation.features import FeatureSet
from app.valuation.models import PlayerValuation
from tests.conftest import _auth_headers, _register

FRESH = datetime.now(timezone.utc) - timedelta(days=1)


def _features(**overrides) -> FeatureSet:
    base = dict(
        player_id=str(uuid.uuid4()),
        position="FWD",
        age=25,
        minutes=2700,
        league_id="39",
        season=2025,
        stats_updated_at=FRESH,
        avg_rating=7.6,
        pass_accuracy=0.0,
        duels_won_rate=0.0,
        goals_per90=0.0,
        assists_per90=0.0,
        goals_plus_assists_per90=0.0,
        shots_on_target_per90=0.0,
        key_passes_per90=0.0,
        dribbles_success_per90=0.0,
        defensive_actions_per90=0.0,
        saves_per90=0.0,
        goals_conceded_per90=0.0,
    )
    base.update(overrides)
    return FeatureSet(**base)


# ── Worked example A — elite Tier-1 forward ───────────────────────────────────


def _example_a_features() -> FeatureSet:
    n90 = 2700 / 90
    return _features(
        position="FWD",
        age=25,
        minutes=2700,
        league_id="39",
        avg_rating=7.6,
        goals_per90=24 / n90,
        assists_per90=9 / n90,
        goals_plus_assists_per90=33 / n90,
        shots_on_target_per90=54 / n90,
        key_passes_per90=45 / n90,
        dribbles_success_per90=60 / n90,
    )


def test_example_a_score_and_value():
    features = _example_a_features()
    score = engine.compute_performance_score(features)
    assert abs(score - 90.58) <= 0.05

    outcome = engine.compute_fair_value(features, score)
    assert outcome.confidence == ValuationConfidence.HIGH
    assert outcome.league_tier == 1
    assert outcome.age_factor == 1.00
    assert abs(outcome.fair_value - 66_500_000) <= 100_000
    assert abs(outcome.fair_value_low - 56_600_000) <= 100_000
    assert abs(outcome.fair_value_high - 76_500_000) <= 100_000

    divergence = engine.compute_divergence(outcome.fair_value, 80_000_000)
    assert abs(divergence.pct - 20.3) <= 0.2
    assert divergence.band == DivergenceBand.ABOVE


# ── Worked example B — young rotation midfielder ──────────────────────────────


def test_example_b_score_and_value():
    n90 = 1080 / 90
    features = _features(
        position="MID",
        age=20,
        minutes=1080,
        league_id="39",
        avg_rating=7.0,
        pass_accuracy=84,
        duels_won_rate=66 / 120,
        goals_per90=2 / n90,
        assists_per90=3 / n90,
        goals_plus_assists_per90=5 / n90,
        key_passes_per90=20 / n90,
        defensive_actions_per90=(18 + 12 + 2) / n90,
    )
    score = engine.compute_performance_score(features)
    assert abs(score - 63.01) <= 0.05

    outcome = engine.compute_fair_value(features, score)
    assert outcome.confidence == ValuationConfidence.MEDIUM  # 1080 min < 1800
    assert outcome.age_factor == 0.90
    assert abs(outcome.fair_value - 22_500_000) <= 100_000
    assert abs(outcome.fair_value_low - 15_700_000) <= 100_000
    assert abs(outcome.fair_value_high - 29_200_000) <= 100_000


# ── Worked example C — veteran Tier-2 defender ────────────────────────────────


def test_example_c_score_and_value():
    n90 = 2430 / 90
    features = _features(
        position="DEF",
        age=33,
        minutes=2430,
        league_id="40",  # Tier 2
        avg_rating=7.1,
        pass_accuracy=78,
        duels_won_rate=174 / 300,
        goals_plus_assists_per90=3 / n90,
        defensive_actions_per90=(62 + 40 + 12) / n90,
    )
    score = engine.compute_performance_score(features)
    assert abs(score - 58.67) <= 0.05

    outcome = engine.compute_fair_value(features, score)
    assert outcome.confidence == ValuationConfidence.HIGH
    assert outcome.league_tier == 2
    assert outcome.age_factor == 0.45
    assert abs(outcome.fair_value - 3_100_000) <= 100_000
    assert abs(outcome.fair_value_low - 2_600_000) <= 100_000
    assert abs(outcome.fair_value_high - 3_500_000) <= 100_000

    divergence = engine.compute_divergence(outcome.fair_value, 2_500_000)
    assert abs(divergence.pct - (-19.4)) <= 0.2
    assert divergence.band == DivergenceBand.BELOW


# ── Engine edge cases and non-functional guarantees ───────────────────────────


def test_engine_is_deterministic():
    now = datetime.now(timezone.utc)
    features = _example_a_features()
    first = (
        engine.compute_performance_score(features),
        engine.compute_fair_value(features, engine.compute_performance_score(features), now=now),
    )
    second = (
        engine.compute_performance_score(features),
        engine.compute_fair_value(features, engine.compute_performance_score(features), now=now),
    )
    assert first == second


def test_engine_source_is_pure():
    """engine.py must import no DB/session machinery — scoring is unit-testable
    without fixtures."""
    source = Path(engine.__file__).read_text(encoding="utf-8")
    for forbidden in ("sqlalchemy", "app.database", "AsyncSession"):
        assert forbidden not in source, f"engine.py must not reference {forbidden}"


def test_score_100_curve_no_overflow():
    n90 = 2700 / 90
    features = _features(
        avg_rating=8.5,  # rating norm clamps to 1.0
        goals_per90=30 / n90,
        assists_per90=15 / n90,
        shots_on_target_per90=60 / n90,
        key_passes_per90=60 / n90,
        dribbles_success_per90=60 / n90,
    )
    score = engine.compute_performance_score(features)
    assert score == 100.0
    outcome = engine.compute_fair_value(features, score)
    # curve = 2^2.2 ≈ 4.59 × anchor — and inside the calibration ceiling
    assert 82_000_000 <= outcome.fair_value <= 83_000_000
    assert outcome.fair_value < 150_000_000


def test_null_rating_uses_fixed_norm_and_caps_confidence():
    features = _example_a_features()
    features.avg_rating = None
    score = engine.compute_performance_score(features)
    # rating row contributes weight × 0.5 = 10 instead of 16
    assert abs(score - (90.5833 - 6.0)) <= 0.05
    outcome = engine.compute_fair_value(features, score)
    assert outcome.confidence != ValuationConfidence.HIGH


def test_null_age_uses_default_factor_and_caps_confidence():
    features = _example_a_features()
    features.age = None
    outcome = engine.compute_fair_value(features, engine.compute_performance_score(features))
    assert outcome.age_factor == 0.85
    assert outcome.confidence == ValuationConfidence.MEDIUM  # HIGH capped by null age


def test_unknown_league_resolves_tier_3():
    features = _example_a_features()
    features.league_id = "999999"
    outcome = engine.compute_fair_value(features, engine.compute_performance_score(features))
    assert outcome.league_tier == 3
    assert outcome.tier_multiplier == 0.15


def test_tier_2_is_exactly_forty_percent_of_tier_1():
    features = _example_a_features()
    score = engine.compute_performance_score(features)
    tier1 = engine.compute_fair_value(features, score)
    features.league_id = "88"
    tier2 = engine.compute_fair_value(features, score)
    # Compare unrounded ratio via the raw components: multiplier is the only delta
    assert tier2.tier_multiplier / tier1.tier_multiplier == pytest.approx(0.40)


def test_zero_duels_no_division_error():
    features = _features(position="MID", avg_rating=7.0, minutes=900, duels_won_rate=0.0)
    score = engine.compute_performance_score(features)
    assert score >= 0.0


def test_minimum_minutes_low_confidence_band():
    features = _example_a_features()
    features.minutes = 450
    score = engine.compute_performance_score(features)
    outcome = engine.compute_fair_value(features, score)
    assert outcome.confidence == ValuationConfidence.LOW
    # ±45% band around the unrounded value, each bound rounded to £100k
    assert outcome.fair_value_low == pytest.approx(outcome.fair_value * 0.55, rel=0.05)
    assert outcome.fair_value_high == pytest.approx(outcome.fair_value * 1.45, rel=0.05)


def test_divergence_band_boundaries():
    cases = [
        (75.0, DivergenceBand.WELL_BELOW),   # −25.0 → ≤ −25
        (76.0, DivergenceBand.BELOW),        # −24.0
        (90.0, DivergenceBand.BELOW),        # −10.0 → ≤ −10
        (90.2, DivergenceBand.IN_LINE),      # −9.8
        (109.8, DivergenceBand.IN_LINE),     # +9.8
        (110.0, DivergenceBand.ABOVE),       # +10.0 → ≥ +10
        (129.8, DivergenceBand.ABOVE),       # +29.8
        (130.0, DivergenceBand.WELL_ABOVE),  # +30.0 → ≥ +30
    ]
    for reference, expected in cases:
        assert engine.compute_divergence(100.0, reference).band == expected, reference


# ── API fixtures ──────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def club(client: AsyncClient) -> dict:
    return await _register(client, "valclub@test.com", club_name="Valuation FC")


@pytest_asyncio.fixture
async def admin(client: AsyncClient, db) -> dict:
    from app.auth.models import User

    tokens = await _register(client, "valadmin@test.com", club_name="Val Admin FC")
    result = await db.execute(select(User).where(User.email == "valadmin@test.com"))
    result.scalar_one().is_superuser = True
    await db.commit()
    return tokens


async def _create_player(
    client: AsyncClient, headers: dict, *, position: str | None = "FWD",
    age: int | None = 25, visibility: str = "PUBLIC", name: str = "Val Player",
) -> dict:
    body: dict = {"name": name, "visibility": visibility}
    if position is not None:
        body["position"] = position
    if age is not None:
        body["age"] = age
    resp = await client.post("/players", json=body, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _add_stats(db, player_id: str, **overrides) -> None:
    values = dict(
        player_id=uuid.UUID(player_id),
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
        avg_rating=7.6,
    )
    values.update(overrides)
    db.add(PlayerStats(**values))
    await db.commit()


async def _recompute(client: AsyncClient, admin: dict, player_id: str) -> dict:
    resp = await client.post(
        f"/valuation/players/{player_id}/recompute", headers=_auth_headers(admin)
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


# ── API: single GET ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_valuation_full_shape(client: AsyncClient, club: dict, admin: dict, db):
    headers = _auth_headers(club)
    player = await _create_player(client, headers)
    await _add_stats(db, player["id"])
    await _recompute(client, admin, player["id"])

    resp = await client.get(
        f"/valuation/players/{player['id']}?reference_price=80000000", headers=headers
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["currency"] == "GBP"
    assert data["model_version"] == "boxscore-v1"
    assert data["confidence"] == "HIGH"
    assert data["league_tier"] == 1
    assert abs(float(data["performance_score"]) - 90.58) <= 0.05
    assert abs(float(data["fair_value"]) - 66_500_000) <= 100_000
    assert abs(float(data["fair_value_low"]) - 56_600_000) <= 100_000
    assert abs(float(data["fair_value_high"]) - 76_500_000) <= 100_000
    assert data["as_of"] is not None
    # breakdown covers every weighted feature, ordered by contribution desc
    assert len(data["breakdown"]) == 6
    contributions = [row["contribution"] for row in data["breakdown"]]
    assert contributions == sorted(contributions, reverse=True)
    assert data["divergence"]["band"] == "ABOVE"
    assert abs(data["divergence"]["pct"] - 20.3) <= 0.2
    assert float(data["divergence"]["reference_price"]) == 80_000_000


@pytest.mark.asyncio
async def test_no_reference_price_no_divergence(client: AsyncClient, club: dict, admin: dict, db):
    headers = _auth_headers(club)
    player = await _create_player(client, headers)
    await _add_stats(db, player["id"])
    await _recompute(client, admin, player["id"])

    resp = await client.get(f"/valuation/players/{player['id']}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["divergence"] is None


@pytest.mark.asyncio
async def test_ineligible_below_minutes_floor(client: AsyncClient, club: dict, admin: dict, db):
    headers = _auth_headers(club)
    player = await _create_player(client, headers)
    await _add_stats(db, player["id"], minutes=449)

    resp = await client.post(
        f"/valuation/players/{player['id']}/recompute", headers=_auth_headers(admin)
    )
    assert resp.status_code == 404
    # no row persisted — never a made-up number
    rows = (await db.execute(select(PlayerValuation))).scalars().all()
    assert rows == []
    resp = await client.get(f"/valuation/players/{player['id']}", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_ineligible_no_position(client: AsyncClient, club: dict, admin: dict, db):
    headers = _auth_headers(club)
    player = await _create_player(client, headers, position=None)
    await _add_stats(db, player["id"])

    resp = await client.post(
        f"/valuation/players/{player['id']}/recompute", headers=_auth_headers(admin)
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_minutes_450_gets_low_confidence(client: AsyncClient, club: dict, admin: dict, db):
    headers = _auth_headers(club)
    player = await _create_player(client, headers)
    await _add_stats(db, player["id"], minutes=450, goals=4, assists=2, shots_on_target=9,
                     key_passes=8, dribbles_success=10)
    data = await _recompute(client, admin, player["id"])
    assert data["confidence"] == "LOW"


@pytest.mark.asyncio
async def test_stats_row_selection_latest_season_then_minutes(
    client: AsyncClient, club: dict, admin: dict, db
):
    headers = _auth_headers(club)
    player = await _create_player(client, headers)
    # older season with huge minutes must lose to latest season
    await _add_stats(db, player["id"], season="2024", minutes=3000, league_id="999999")
    # two rows in the latest season: the 1200-minute Tier-1 row must win
    await _add_stats(db, player["id"], season="2025", minutes=900, league_id="999999")
    await _add_stats(db, player["id"], season="2025", minutes=1200, league_id="39")

    data = await _recompute(client, admin, player["id"])
    assert data["league_tier"] == 1  # picked the 2025 / 1200-minute / league-39 row


# ── API: permissions and visibility ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_unauthenticated_401(client: AsyncClient):
    resp = await client.get(f"/valuation/players/{uuid.uuid4()}")
    assert resp.status_code == 401
    resp = await client.get(f"/valuation/players?ids={uuid.uuid4()}")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_player_account_gets_403_everywhere(client: AsyncClient, club: dict, admin: dict, db):
    headers = _auth_headers(club)
    player = await _create_player(client, headers)
    await _add_stats(db, player["id"])
    await _recompute(client, admin, player["id"])

    resp = await client.post("/auth/register", json={
        "email": "valplayer@test.com", "password": "password123",
        "user_type": "PLAYER", "player_id": player["id"],
    })
    assert resp.status_code == 201, resp.text
    player_headers = _auth_headers(resp.json())

    resp = await client.get(f"/valuation/players/{player['id']}", headers=player_headers)
    assert resp.status_code == 403
    resp = await client.get(f"/valuation/players?ids={player['id']}", headers=player_headers)
    assert resp.status_code == 403
    resp = await client.post(
        f"/valuation/players/{player['id']}/recompute", headers=player_headers
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_private_player_404_for_non_creator(client: AsyncClient, club: dict, admin: dict, db):
    creator_headers = _auth_headers(club)
    player = await _create_player(client, creator_headers, visibility="PRIVATE")
    await _add_stats(db, player["id"])
    await _recompute(client, admin, player["id"])

    other = await _register(client, "valrival@test.com", club_name="Rival FC")
    resp = await client.get(f"/valuation/players/{player['id']}", headers=_auth_headers(other))
    assert resp.status_code == 404
    # creator still sees it
    resp = await client.get(f"/valuation/players/{player['id']}", headers=creator_headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_recompute_requires_superuser(client: AsyncClient, club: dict, db):
    headers = _auth_headers(club)
    player = await _create_player(client, headers)
    await _add_stats(db, player["id"])

    resp = await client.post(f"/valuation/players/{player['id']}/recompute", headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_recompute_appends_new_row(client: AsyncClient, club: dict, admin: dict, db):
    headers = _auth_headers(club)
    player = await _create_player(client, headers)
    await _add_stats(db, player["id"])

    await _recompute(client, admin, player["id"])
    await _recompute(client, admin, player["id"])
    rows = (await db.execute(select(PlayerValuation))).scalars().all()
    assert len(rows) == 2  # append-only: old rows untouched


# ── API: batch endpoint ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_batch_returns_only_eligible_and_visible(
    client: AsyncClient, club: dict, admin: dict, db
):
    headers = _auth_headers(club)
    eligible = await _create_player(client, headers, name="Eligible")
    await _add_stats(db, eligible["id"])
    await _recompute(client, admin, eligible["id"])

    ineligible = await _create_player(client, headers, name="Ineligible")  # no stats

    other = await _register(client, "valowner2@test.com", club_name="Owner2 FC")
    hidden = await _create_player(
        client, _auth_headers(other), name="Hidden", visibility="PRIVATE"
    )
    await _add_stats(db, hidden["id"])
    await _recompute(client, admin, hidden["id"])

    ids = ",".join([eligible["id"], ineligible["id"], hidden["id"], str(uuid.uuid4())])
    resp = await client.get(f"/valuation/players?ids={ids}", headers=headers)
    assert resp.status_code == 200, resp.text
    valuations = resp.json()["valuations"]
    assert set(valuations.keys()) == {eligible["id"]}
    assert valuations[eligible["id"]]["divergence"] is None  # batch never carries divergence


@pytest.mark.asyncio
async def test_batch_caps_at_50_ids(client: AsyncClient, club: dict):
    ids = ",".join(str(uuid.uuid4()) for _ in range(51))
    resp = await client.get(f"/valuation/players?ids={ids}", headers=_auth_headers(club))
    assert resp.status_code == 422


# ── Auditability: inputs_json reproduces the computation ──────────────────────


@pytest.mark.asyncio
async def test_inputs_json_reproduces_stored_outputs(
    client: AsyncClient, club: dict, admin: dict, db
):
    headers = _auth_headers(club)
    player = await _create_player(client, headers)
    await _add_stats(db, player["id"])
    await _recompute(client, admin, player["id"])

    row = (await db.execute(select(PlayerValuation))).scalars().one()
    raw = dict(row.inputs_json["features"])
    if raw["stats_updated_at"] is not None:
        raw["stats_updated_at"] = datetime.fromisoformat(raw["stats_updated_at"])
    features = FeatureSet(**raw)

    score = engine.compute_performance_score(features)
    assert round(score, 2) == float(row.performance_score)
    outcome = engine.compute_fair_value(features, score, now=row.computed_at)
    assert outcome.fair_value == float(row.fair_value)
    assert outcome.fair_value_low == float(row.fair_value_low)
    assert outcome.fair_value_high == float(row.fair_value_high)
    assert outcome.confidence == row.confidence
    assert outcome.league_tier == row.league_tier
