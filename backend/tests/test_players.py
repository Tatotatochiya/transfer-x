"""Player endpoint tests — M2."""

import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import _auth_headers, _register

pytestmark = pytest.mark.asyncio


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _create_player(client, headers, name="Ronaldo", position="FWD") -> dict:
    resp = await client.post(
        "/players", json={"name": name, "age": 25, "position": position}, headers=headers
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── Create player ─────────────────────────────────────────────────────────────


async def test_create_player(client: AsyncClient, auth_headers: dict):
    data = await _create_player(client, auth_headers)
    assert data["name"] == "Ronaldo"
    assert data["position"] == "FWD"
    assert data["status"] == "FREE_AGENT"
    assert data["open_to_offers"] is False


async def test_create_player_requires_auth(client: AsyncClient):
    resp = await client.post("/players", json={"name": "Ghost"})
    assert resp.status_code == 401


async def test_create_player_invalid_position(client: AsyncClient, auth_headers: dict):
    resp = await client.post(
        "/players", json={"name": "X", "position": "STRIKER"}, headers=auth_headers
    )
    assert resp.status_code == 422


# ── List own players ──────────────────────────────────────────────────────────


async def test_list_own_players(client: AsyncClient, auth_headers: dict):
    await _create_player(client, auth_headers, "Player A")
    await _create_player(client, auth_headers, "Player B")
    resp = await client.get("/players", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    names = {p["name"] for p in data["items"]}
    assert "Player A" in names and "Player B" in names


async def test_other_user_cannot_see_my_players(client: AsyncClient, auth_headers: dict):
    await _create_player(client, auth_headers, "Secret Player")
    other_tokens = await _register(client, "other@test.com")
    resp = await client.get("/players", headers=_auth_headers(other_tokens))
    assert resp.json()["total"] == 0


# ── Update player ─────────────────────────────────────────────────────────────


async def test_update_player(client: AsyncClient, auth_headers: dict):
    player = await _create_player(client, auth_headers)
    resp = await client.patch(
        f"/players/{player['id']}",
        json={"name": "Messi", "age": 36},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Messi"
    assert resp.json()["age"] == 36


async def test_update_other_users_player_is_404(client: AsyncClient, auth_headers: dict):
    player = await _create_player(client, auth_headers)
    other_tokens = await _register(client, "other2@test.com")
    resp = await client.patch(
        f"/players/{player['id']}",
        json={"name": "Hacker"},
        headers=_auth_headers(other_tokens),
    )
    assert resp.status_code == 404


# ── Market browse ─────────────────────────────────────────────────────────────


async def test_market_shows_public_players(client: AsyncClient, auth_headers: dict):
    await _create_player(client, auth_headers, "Public Star")
    resp = await client.get("/players/market")  # no auth
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


async def test_market_hides_clubs_only_from_anon(client: AsyncClient, auth_headers: dict):
    resp = await client.post(
        "/players",
        json={"name": "Clubs Only", "visibility": "CLUBS_ONLY"},
        headers=auth_headers,
    )
    player_id = resp.json()["id"]

    anon_resp = await client.get("/players/market")
    ids = [p["id"] for p in anon_resp.json()["items"]]
    assert player_id not in ids

    auth_resp = await client.get("/players/market", headers=auth_headers)
    ids = [p["id"] for p in auth_resp.json()["items"]]
    assert player_id in ids


async def test_market_filter_by_position(client: AsyncClient, auth_headers: dict):
    await _create_player(client, auth_headers, "GK Guy", position="GK")
    await _create_player(client, auth_headers, "FWD Guy", position="FWD")
    resp = await client.get("/players/market?position=GK", headers=auth_headers)
    for p in resp.json()["items"]:
        assert p["position"] == "GK"


async def test_market_detail(client: AsyncClient, auth_headers: dict):
    player = await _create_player(client, auth_headers)
    resp = await client.get(f"/players/market/{player['id']}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Ronaldo"


async def test_market_detail_private_hidden_from_others(client: AsyncClient, auth_headers: dict):
    resp = await client.post(
        "/players", json={"name": "Private", "visibility": "PRIVATE"}, headers=auth_headers
    )
    player_id = resp.json()["id"]
    other_tokens = await _register(client, "voyeur@test.com")
    resp = await client.get(
        f"/players/market/{player_id}", headers=_auth_headers(other_tokens)
    )
    assert resp.status_code == 404


# ── Contracts ─────────────────────────────────────────────────────────────────


async def test_add_contract_normalizes_status(client: AsyncClient, auth_headers: dict):
    player = await _create_player(client, auth_headers)
    assert player["status"] == "FREE_AGENT"

    # Get the owning club's ID
    my_club = (await client.get("/clubs/me", headers=auth_headers)).json()
    club_id = my_club["id"]

    resp = await client.post(
        f"/players/{player['id']}/contracts",
        json={"club_id": club_id, "wage_weekly": "50000.00"},
        headers=auth_headers,
    )
    assert resp.status_code == 201

    # Player should now be CONTRACTED
    detail = await client.get(f"/players/market/{player['id']}", headers=auth_headers)
    assert detail.json()["status"] == "CONTRACTED"
    assert detail.json()["active_contract"] is not None
    assert float(detail.json()["active_contract"]["wage_weekly"]) == 50000.0


async def test_add_contract_replaces_existing(client: AsyncClient, auth_headers: dict):
    player = await _create_player(client, auth_headers)
    my_club = (await client.get("/clubs/me", headers=auth_headers)).json()
    club_id = my_club["id"]

    await client.post(
        f"/players/{player['id']}/contracts",
        json={"club_id": club_id, "wage_weekly": "30000"},
        headers=auth_headers,
    )
    # Second contract replaces the first
    await client.post(
        f"/players/{player['id']}/contracts",
        json={"club_id": club_id, "wage_weekly": "60000"},
        headers=auth_headers,
    )
    detail = (await client.get(f"/players/market/{player['id']}", headers=auth_headers)).json()
    assert float(detail["active_contract"]["wage_weekly"]) == 60000.0


async def test_deactivate_contract_makes_free_agent(client: AsyncClient, auth_headers: dict):
    player = await _create_player(client, auth_headers)
    my_club = (await client.get("/clubs/me", headers=auth_headers)).json()

    contract = (
        await client.post(
            f"/players/{player['id']}/contracts",
            json={"club_id": my_club["id"]},
            headers=auth_headers,
        )
    ).json()

    assert contract["is_active"] is True

    resp = await client.delete(
        f"/players/{player['id']}/contracts/{contract['id']}", headers=auth_headers
    )
    assert resp.status_code == 204

    detail = (await client.get(f"/players/market/{player['id']}", headers=auth_headers)).json()
    assert detail["status"] == "FREE_AGENT"
    assert detail["active_contract"] is None


async def test_deactivate_already_inactive_contract(client: AsyncClient, auth_headers: dict):
    player = await _create_player(client, auth_headers)
    my_club = (await client.get("/clubs/me", headers=auth_headers)).json()

    contract = (
        await client.post(
            f"/players/{player['id']}/contracts",
            json={"club_id": my_club["id"]},
            headers=auth_headers,
        )
    ).json()

    await client.delete(
        f"/players/{player['id']}/contracts/{contract['id']}", headers=auth_headers
    )
    # Second deactivate should 400
    resp = await client.delete(
        f"/players/{player['id']}/contracts/{contract['id']}", headers=auth_headers
    )
    assert resp.status_code == 400


# ── B3: sort by value (fair value vs. nominal market value) ────────────────


async def _set_market_value(db, player_id: str, value):
    from sqlalchemy import select

    from app.players.models import Player

    result = await db.execute(select(Player).where(Player.id == uuid.UUID(player_id)))
    p = result.scalar_one()
    p.market_value = value
    await db.commit()


async def _seed_market_valuation(db, player_id: str, fair_value):
    from decimal import Decimal

    from app.valuation.constants import ValuationConfidence
    from app.valuation.models import PlayerValuation

    db.add(PlayerValuation(
        player_id=uuid.UUID(player_id),
        fair_value=fair_value,
        fair_value_low=fair_value,
        fair_value_high=fair_value,
        performance_score=Decimal("50"),
        confidence=ValuationConfidence.HIGH,
        model_version="test",
        league_tier=1,
        age_factor=Decimal("1.0"),
    ))
    await db.commit()


async def test_market_sort_by_value_ranks_most_undervalued_first(client: AsyncClient, auth_headers: dict, db):
    from decimal import Decimal

    undervalued = await _create_player(client, auth_headers, "Undervalued Star", position="MID")
    overpriced = await _create_player(client, auth_headers, "Overpriced Player", position="MID")
    unvalued = await _create_player(client, auth_headers, "No Valuation Player", position="MID")

    await _set_market_value(db, undervalued["id"], Decimal("1000000"))
    await _seed_market_valuation(db, undervalued["id"], Decimal("10000000"))  # fair value >> market value

    await _set_market_value(db, overpriced["id"], Decimal("10000000"))
    await _seed_market_valuation(db, overpriced["id"], Decimal("1000000"))  # fair value << market value

    resp = await client.get(
        "/players/market?sort_by=value&sort_dir=desc&position=MID&page_size=50", headers=auth_headers
    )
    assert resp.status_code == 200
    ids = [p["id"] for p in resp.json()["items"]]

    assert ids.index(undervalued["id"]) < ids.index(overpriced["id"])
    # No valuation at all sorts last regardless of direction — same nullslast
    # handling every other /players/market sort already gets.
    assert ids.index(overpriced["id"]) < ids.index(unvalued["id"])


# ── B4: wage fit ─────────────────────────────────────────────────────────────


async def _set_player_wage(db, player_id: str, wage_weekly) -> None:
    from sqlalchemy import select

    from app.players.models import Player

    result = await db.execute(select(Player).where(Player.id == uuid.UUID(player_id)))
    p = result.scalar_one()
    p.wage_weekly = wage_weekly
    await db.commit()


async def _set_wage_budget(db, weekly_total) -> None:
    from sqlalchemy import select

    from app.clubs.models import ClubFinance

    result = await db.execute(select(ClubFinance))
    for f in result.scalars():
        f.wage_budget_total_weekly = weekly_total
    await db.commit()


async def test_market_wage_fit_null_for_anonymous(client: AsyncClient, auth_headers: dict, db):
    from decimal import Decimal

    player = await _create_player(client, auth_headers, "Wage Player Anon")
    await _set_player_wage(db, player["id"], Decimal("50000"))

    resp = await client.get("/players/market")  # no auth
    item = next(p for p in resp.json()["items"] if p["id"] == player["id"])
    assert item["wage_fit"] is None


async def test_market_wage_fit_true_when_within_wage_room(client: AsyncClient, auth_headers: dict, db):
    from decimal import Decimal

    await _set_wage_budget(db, Decimal("200000"))
    player = await _create_player(client, auth_headers, "Wage Player Fits")
    await _set_player_wage(db, player["id"], Decimal("50000"))

    resp = await client.get("/players/market", headers=auth_headers)
    item = next(p for p in resp.json()["items"] if p["id"] == player["id"])
    assert item["wage_fit"]["fits"] is True
    assert float(item["wage_fit"]["wage_room_after"]) == 150_000.0


async def test_market_wage_fit_false_when_exceeds_wage_room(client: AsyncClient, auth_headers: dict, db):
    from decimal import Decimal

    await _set_wage_budget(db, Decimal("30000"))
    player = await _create_player(client, auth_headers, "Wage Player Over Budget")
    await _set_player_wage(db, player["id"], Decimal("50000"))

    detail = await client.get(f"/players/market/{player['id']}", headers=auth_headers)
    wage_fit = detail.json()["wage_fit"]
    assert wage_fit["fits"] is False
    assert float(wage_fit["wage_room_after"]) == -20_000.0


async def test_market_wage_fit_null_without_player_wage_figure(client: AsyncClient, auth_headers: dict, db):
    from decimal import Decimal

    await _set_wage_budget(db, Decimal("200000"))
    player = await _create_player(client, auth_headers, "Wage Player No Figure")

    detail = await client.get(f"/players/market/{player['id']}", headers=auth_headers)
    assert detail.json()["wage_fit"] is None
