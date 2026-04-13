"""M6 — Stats tests."""

import pytest
import pytest_asyncio
from httpx import AsyncClient

from tests.conftest import _auth_headers, _register


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def stats_user(client: AsyncClient) -> dict:
    return await _register(client, "stats@test.com", club_name="Stats FC")


async def _create_player(client: AsyncClient, headers: dict, name: str = "Stats Player") -> dict:
    resp = await client.post("/players", json={"name": name, "position": "MID"}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── Tests ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_player_stats_empty(client: AsyncClient, stats_user: dict):
    """GET before any stats → []."""
    headers = _auth_headers(stats_user)
    player = await _create_player(client, headers)
    resp = await client.get(f"/players/{player['id']}/stats", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_upsert_player_stats(client: AsyncClient, stats_user: dict):
    """PUT stats, verify response fields."""
    headers = _auth_headers(stats_user)
    player = await _create_player(client, headers)
    body = {
        "vendor": "api-football",
        "league_id": "39",
        "season": "2024/25",
        "goals": 10,
        "assists": 5,
        "appearances": 20,
        "avg_rating": "7.50",
        "form_score": "8.00",
    }
    resp = await client.put(f"/players/{player['id']}/stats", json=body, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["vendor"] == "api-football"
    assert data["league_id"] == "39"
    assert data["season"] == "2024/25"
    assert data["goals"] == 10
    assert data["assists"] == 5
    assert data["appearances"] == 20
    assert float(data["avg_rating"]) == 7.50
    assert "id" in data
    assert "player_id" in data


@pytest.mark.asyncio
async def test_upsert_player_stats_updates_in_place(client: AsyncClient, stats_user: dict):
    """Second PUT same vendor/league/season updates, no duplicate."""
    headers = _auth_headers(stats_user)
    player = await _create_player(client, headers)
    body = {"vendor": "api-football", "league_id": "39", "season": "2024/25", "goals": 5}
    await client.put(f"/players/{player['id']}/stats", json=body, headers=headers)

    body2 = {"vendor": "api-football", "league_id": "39", "season": "2024/25", "goals": 15}
    resp = await client.put(f"/players/{player['id']}/stats", json=body2, headers=headers)
    assert resp.status_code == 200

    list_resp = await client.get(f"/players/{player['id']}/stats", headers=headers)
    assert list_resp.status_code == 200
    stats = list_resp.json()
    assert len(stats) == 1
    assert stats[0]["goals"] == 15


@pytest.mark.asyncio
async def test_filter_stats_by_vendor(client: AsyncClient, stats_user: dict):
    """Create stats for 2 vendors, filter by one."""
    headers = _auth_headers(stats_user)
    player = await _create_player(client, headers)
    await client.put(
        f"/players/{player['id']}/stats",
        json={"vendor": "vendor-a", "goals": 3},
        headers=headers,
    )
    await client.put(
        f"/players/{player['id']}/stats",
        json={"vendor": "vendor-b", "goals": 7},
        headers=headers,
    )

    resp = await client.get(f"/players/{player['id']}/stats", params={"vendor": "vendor-a"}, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["vendor"] == "vendor-a"
    assert data[0]["goals"] == 3


@pytest.mark.asyncio
async def test_filter_stats_by_season(client: AsyncClient, stats_user: dict):
    """Filter by season."""
    headers = _auth_headers(stats_user)
    player = await _create_player(client, headers)
    await client.put(
        f"/players/{player['id']}/stats",
        json={"vendor": "v1", "season": "2023/24", "goals": 5},
        headers=headers,
    )
    await client.put(
        f"/players/{player['id']}/stats",
        json={"vendor": "v1", "season": "2024/25", "goals": 10},
        headers=headers,
    )

    resp = await client.get(f"/players/{player['id']}/stats", params={"season": "2024/25"}, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["season"] == "2024/25"
    assert data[0]["goals"] == 10


@pytest.mark.asyncio
async def test_get_player_form_not_found(client: AsyncClient, stats_user: dict):
    """GET form when none exists → 404."""
    headers = _auth_headers(stats_user)
    player = await _create_player(client, headers)
    resp = await client.get(f"/players/{player['id']}/form", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_upsert_player_form(client: AsyncClient, stats_user: dict):
    """PUT form, verify response."""
    headers = _auth_headers(stats_user)
    player = await _create_player(client, headers)
    body = {"form_score": "8.50", "games_considered": 5, "key_metrics": {"goals_pg": 0.5}}
    resp = await client.put(f"/players/{player['id']}/form", json=body, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert float(data["form_score"]) == 8.50
    assert data["games_considered"] == 5
    assert data["key_metrics"] == {"goals_pg": 0.5}
    assert "id" in data
    assert "player_id" in data
    assert "last_updated" in data


@pytest.mark.asyncio
async def test_update_player_form(client: AsyncClient, stats_user: dict):
    """Second PUT updates form_score."""
    headers = _auth_headers(stats_user)
    player = await _create_player(client, headers)
    await client.put(f"/players/{player['id']}/form", json={"form_score": "7.00"}, headers=headers)
    resp = await client.put(f"/players/{player['id']}/form", json={"form_score": "9.00"}, headers=headers)
    assert resp.status_code == 200
    assert float(resp.json()["form_score"]) == 9.00


@pytest.mark.asyncio
async def test_get_player_form(client: AsyncClient, stats_user: dict):
    """GET form after upsert."""
    headers = _auth_headers(stats_user)
    player = await _create_player(client, headers)
    await client.put(f"/players/{player['id']}/form", json={"form_score": "8.00"}, headers=headers)
    resp = await client.get(f"/players/{player['id']}/form", headers=headers)
    assert resp.status_code == 200
    assert float(resp.json()["form_score"]) == 8.00


@pytest.mark.asyncio
async def test_list_snapshots_empty(client: AsyncClient, stats_user: dict):
    """GET snapshots before any → []."""
    headers = _auth_headers(stats_user)
    player = await _create_player(client, headers)
    resp = await client.get(f"/players/{player['id']}/snapshots", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_create_snapshot(client: AsyncClient, stats_user: dict):
    """POST snapshot, verify."""
    headers = _auth_headers(stats_user)
    player = await _create_player(client, headers)
    body = {"vendor": "api-football", "payload": {"goals": 5, "assists": 2}}
    resp = await client.post(f"/players/{player['id']}/snapshots", json=body, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["vendor"] == "api-football"
    assert data["payload"] == {"goals": 5, "assists": 2}
    assert "id" in data
    assert "fetched_at" in data


@pytest.mark.asyncio
async def test_list_snapshots(client: AsyncClient, stats_user: dict):
    """Create 2 snapshots, GET returns both."""
    headers = _auth_headers(stats_user)
    player = await _create_player(client, headers)
    await client.post(
        f"/players/{player['id']}/snapshots",
        json={"vendor": "v1", "payload": {"round": 1}},
        headers=headers,
    )
    await client.post(
        f"/players/{player['id']}/snapshots",
        json={"vendor": "v1", "payload": {"round": 2}},
        headers=headers,
    )
    resp = await client.get(f"/players/{player['id']}/snapshots", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_list_vendor_sync_states_empty(client: AsyncClient, stats_user: dict):
    """GET sync-states → []."""
    headers = _auth_headers(stats_user)
    resp = await client.get("/stats/sync-states", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_upsert_vendor_sync_state_success(client: AsyncClient, stats_user: dict):
    """PUT success=true, verify last_success_at set, error_count=0."""
    headers = _auth_headers(stats_user)
    resp = await client.put("/stats/sync-states/api-football", json={"success": True}, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["vendor"] == "api-football"
    assert data["error_count"] == 0
    assert data["last_error"] is None
    assert data["last_sync_at"] is not None
    assert data["last_success_at"] is not None


@pytest.mark.asyncio
async def test_upsert_vendor_sync_state_failure(client: AsyncClient, stats_user: dict):
    """PUT success=false with error, verify error_count=1; second failure increments to 2."""
    headers = _auth_headers(stats_user)
    resp1 = await client.put(
        "/stats/sync-states/api-football",
        json={"success": False, "error": "Connection timeout"},
        headers=headers,
    )
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["error_count"] == 1
    assert data1["last_error"] == "Connection timeout"
    assert data1["last_success_at"] is None

    resp2 = await client.put(
        "/stats/sync-states/api-football",
        json={"success": False, "error": "Rate limited"},
        headers=headers,
    )
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["error_count"] == 2
    assert data2["last_error"] == "Rate limited"
