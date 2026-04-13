"""M8 — Vendor sync tests."""

import uuid
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from tests.conftest import _auth_headers, _register

pytestmark = pytest.mark.asyncio

# ── Fake API fixtures ──────────────────────────────────────────────────────────

FAKE_PLAYER_STATS_RESPONSE = {
    "response": [
        {
            "player": {
                "id": 276,
                "name": "N. Neymar",
                "age": 32,
                "nationality": "Brazil",
                "photo": "https://photo.url",
            },
            "statistics": [
                {
                    "team": {"id": 541, "name": "Real Madrid"},
                    "league": {"id": 39, "name": "Premier League", "country": "England", "season": 2024},
                    "games": {"minutes": 90, "rating": "8.0", "position": "Midfielder"},
                    "goals": {"total": 1, "assists": 2},
                }
            ],
        }
    ]
}

FAKE_LEAGUE_PLAYERS_RESPONSE = {
    "paging": {"total": 1},
    "response": [FAKE_PLAYER_STATS_RESPONSE["response"][0]],
}


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def user_tokens(client: AsyncClient) -> dict:
    return await _register(client, "vendor_user@test.com", club_name="Vendor Club")


@pytest_asyncio.fixture
async def superuser(client, db):
    """Register a user then promote to superuser directly in DB."""
    tokens = await _register(client, "vendor_admin@test.com", club_name="Vendor Admin Club")
    from app.auth.models import User

    result = await db.execute(select(User).where(User.email == "vendor_admin@test.com"))
    user = result.scalar_one()
    user.is_superuser = True
    await db.commit()
    return tokens


# ── Pure form computation tests (no DB/mocking) ───────────────────────────────


def test_form_score_basic():
    """compute_form_score with one payload having rating=8.0 and 1 goal in 90 min → form_score > 0."""
    from app.vendor.form import compute_form_score

    payload = {
        "games": {"minutes": 90, "rating": "8.0"},
        "goals": {"total": 1, "assists": 0},
    }
    result = compute_form_score([payload])
    assert result is not None
    assert result["form_score"] > 0
    assert result["goals"] == 1
    assert result["assists"] == 0
    assert result["minutes"] == 90


def test_form_score_windowing():
    """Provide 6 payloads, window_games=5 → only first 5 used."""
    from app.vendor.form import compute_form_score

    # First 5 payloads have rating 8.0, 6th has extreme value 10.0
    payloads = [
        {"games": {"minutes": 90, "rating": "8.0"}, "goals": {"total": 0, "assists": 0}}
        for _ in range(5)
    ]
    payloads.append(
        {"games": {"minutes": 90, "rating": "10.0"}, "goals": {"total": 10, "assists": 10}}
    )

    result_5 = compute_form_score(payloads, window_games=5)
    result_6 = compute_form_score(payloads, window_games=6)

    assert result_5 is not None
    assert result_6 is not None
    # With window=5, only the first 5 (rating=8.0) are used; with window=6 the extreme value is included
    assert result_5["form_score"] < result_6["form_score"]
    assert result_5["games_considered"] == 5
    assert result_6["games_considered"] == 6


def test_form_score_no_ratings():
    """Payload with no ratings → form_score based only on ga_per90."""
    from app.vendor.form import compute_form_score

    payload = {
        "games": {"minutes": 90},
        "goals": {"total": 1, "assists": 0},
    }
    result = compute_form_score([payload])
    assert result is not None
    assert result["avg_rating"] is None
    # ga_per90 = 1/90 * 90 = 1.0 → form_score = 100 * clamp(1.0/1.0, 0, 1) = 100
    assert float(result["form_score"]) == 100.0


def test_form_score_empty():
    """compute_form_score([]) → None."""
    from app.vendor.form import compute_form_score

    assert compute_form_score([]) is None


def test_trend_not_enough_data():
    """compute_trend with only 5 payloads, window=5 → None (need 10)."""
    from app.vendor.form import compute_trend

    payloads = [
        {"games": {"minutes": 90, "rating": "7.0"}, "goals": {"total": 0, "assists": 0}}
        for _ in range(5)
    ]
    assert compute_trend(payloads, window_games=5) is None


def test_trend_computed():
    """compute_trend with 10 payloads (first 5 higher rating, next 5 lower) → trend > 0."""
    from app.vendor.form import compute_trend

    # First 5: rating=9.0 (current window) → higher form score
    # Next 5: rating=5.0 (previous window) → lower form score
    current_payloads = [
        {"games": {"minutes": 90, "rating": "9.0"}, "goals": {"total": 0, "assists": 0}}
        for _ in range(5)
    ]
    previous_payloads = [
        {"games": {"minutes": 90, "rating": "5.0"}, "goals": {"total": 0, "assists": 0}}
        for _ in range(5)
    ]
    payloads = current_payloads + previous_payloads
    trend = compute_trend(payloads, window_games=5)
    assert trend is not None
    assert trend > 0


# ── Sync tests with mocked API ─────────────────────────────────────────────────


async def test_sync_player_creates_snapshot(client: AsyncClient, db, user_tokens):
    """Sync player, verify snapshot created in DB."""
    headers = _auth_headers(user_tokens)

    # Create player via API
    player_resp = await client.post(
        "/players", json={"name": "Test Player", "position": "MID"}, headers=headers
    )
    assert player_resp.status_code == 201, player_resp.text
    player_id = player_resp.json()["id"]

    # Set vendor_id in DB
    from app.players.models import Player
    result = await db.execute(select(Player).where(Player.id == uuid.UUID(player_id)))
    player = result.scalar_one()
    player.vendor_id = "276"
    await db.commit()

    # Patch the apisports_key setting and mock the API call
    from app.config import settings
    original_key = settings.apisports_key
    settings.apisports_key = "test_key"
    try:
        with patch("app.vendor.client.ApiFootballClient._get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = FAKE_PLAYER_STATS_RESPONSE
            resp = await client.post(
                f"/vendor/sync/players/{player_id}",
                json={"season": 2024, "league_id": 39},
                headers=headers,
            )
    finally:
        settings.apisports_key = original_key

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["snapshots_created"] == 1

    # Verify snapshot in DB
    from app.stats.models import PlayerStatsSnapshot
    await db.rollback()  # refresh session after commit in endpoint
    snap_result = await db.execute(
        select(PlayerStatsSnapshot).where(PlayerStatsSnapshot.player_id == uuid.UUID(player_id))
    )
    snaps = list(snap_result.scalars())
    assert len(snaps) == 1


async def test_sync_player_no_vendor_id(client: AsyncClient, db, user_tokens):
    """Player without vendor_id → 400."""
    headers = _auth_headers(user_tokens)

    player_resp = await client.post(
        "/players", json={"name": "No Vendor Player", "position": "GK"}, headers=headers
    )
    assert player_resp.status_code == 201
    player_id = player_resp.json()["id"]

    from app.config import settings
    original_key = settings.apisports_key
    settings.apisports_key = "test_key"
    try:
        resp = await client.post(
            f"/vendor/sync/players/{player_id}",
            json={"season": 2024, "league_id": 39},
            headers=headers,
        )
    finally:
        settings.apisports_key = original_key

    assert resp.status_code == 400
    assert "vendor_id" in resp.json()["detail"]


async def test_sync_player_creates_stats(client: AsyncClient, db, user_tokens):
    """Sync player, verify PlayerStats row created with correct goals/assists."""
    headers = _auth_headers(user_tokens)

    player_resp = await client.post(
        "/players", json={"name": "Stats Player", "position": "FWD"}, headers=headers
    )
    assert player_resp.status_code == 201
    player_id = player_resp.json()["id"]

    from app.players.models import Player
    result = await db.execute(select(Player).where(Player.id == uuid.UUID(player_id)))
    player = result.scalar_one()
    player.vendor_id = "276"
    await db.commit()

    from app.config import settings
    original_key = settings.apisports_key
    settings.apisports_key = "test_key"
    try:
        with patch("app.vendor.client.ApiFootballClient._get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = FAKE_PLAYER_STATS_RESPONSE
            resp = await client.post(
                f"/vendor/sync/players/{player_id}",
                json={"season": 2024, "league_id": 39},
                headers=headers,
            )
    finally:
        settings.apisports_key = original_key

    assert resp.status_code == 200
    assert resp.json()["stats_updated"] is True

    from app.stats.models import PlayerStats
    await db.rollback()
    stats_result = await db.execute(
        select(PlayerStats).where(PlayerStats.player_id == uuid.UUID(player_id))
    )
    stats_rows = list(stats_result.scalars())
    assert len(stats_rows) == 1
    assert stats_rows[0].goals == 1
    assert stats_rows[0].assists == 2


async def test_sync_league_creates_player(client: AsyncClient, db, superuser):
    """Sync league creates player with vendor_id='276'."""
    headers = _auth_headers(superuser)

    from app.config import settings
    original_key = settings.apisports_key
    settings.apisports_key = "test_key"
    try:
        with patch("app.vendor.client.ApiFootballClient._get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = FAKE_LEAGUE_PLAYERS_RESPONSE
            resp = await client.post(
                "/vendor/sync/league",
                json={"league_id": 39, "season": 2024, "sleep_ms": 0},
                headers=headers,
            )
    finally:
        settings.apisports_key = original_key

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["players_created"] >= 1

    # Verify player with vendor_id="276" exists
    from app.players.models import Player
    await db.rollback()
    p_result = await db.execute(select(Player).where(Player.vendor_id == "276"))
    player = p_result.scalar_one_or_none()
    assert player is not None
    assert player.name == "N. Neymar"


async def test_compute_form_endpoint(client: AsyncClient, db, superuser, user_tokens):
    """Create player + snapshot in DB, compute-form → players_updated=1."""
    # First create a player via the API so it has a valid created_by_user_id
    headers = _auth_headers(user_tokens)
    player_resp = await client.post(
        "/players", json={"name": "Form Player", "position": "MID"}, headers=headers
    )
    assert player_resp.status_code == 201
    player_id = player_resp.json()["id"]

    # Insert a snapshot directly in the DB
    from app.stats.models import PlayerStatsSnapshot
    snap = PlayerStatsSnapshot(
        player_id=uuid.UUID(player_id),
        vendor="api_sports_v3",
        payload={"games": {"minutes": 90, "rating": "7.5"}, "goals": {"total": 1, "assists": 0}},
        fetched_at=datetime.now(),
    )
    db.add(snap)
    await db.commit()

    su_headers = _auth_headers(superuser)
    resp = await client.post(
        "/vendor/compute-form",
        json={"window_games": 5},
        headers=su_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["players_updated"] == 1


async def test_vendor_status(client: AsyncClient, user_tokens):
    """Authenticated GET /vendor/status → list (may be empty)."""
    headers = _auth_headers(user_tokens)
    resp = await client.get("/vendor/status", headers=headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
