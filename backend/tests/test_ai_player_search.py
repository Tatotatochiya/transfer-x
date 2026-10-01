"""AI player search (POST /ai/player-search): buyable players only by default.

The model only parses the query into filters; it is faked here, so these
tests check the database side.
"""

import json
import uuid

import pytest
from httpx import AsyncClient

from app.config import settings
from tests.conftest import _auth_headers, _register
from tests.test_lite_buy import _player


@pytest.fixture
def fake_parse(monkeypatch):
    """A model that reads every query as "defenders"."""
    from app.ai import service

    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")

    async def fake_chat(messages, *, user_id=None, endpoint=None, **_):
        return json.dumps({"position": "DEF", "interpreted_as": "defenders"})

    monkeypatch.setattr(service, "chat", fake_chat)


@pytest.mark.asyncio
async def test_ai_search_shows_buyable_players_unless_turned_off(client: AsyncClient, db, fake_parse):
    from app.players.models import Player, PlayerStatus

    club = await _register(client, "nl_search@clubs-example.com", club_name="Search FC")
    statuses = {"Signable Sam": PlayerStatus.CONTRACTED, "Free Fred": PlayerStatus.FREE_AGENT,
                "Elsewhere Eli": PlayerStatus.EXTERNAL}
    for name, player_status in statuses.items():
        created = await _player(client, club, name)
        row = await db.get(Player, uuid.UUID(created["id"]))
        row.status = player_status
    await db.commit()

    async def names(body: dict) -> set[str]:
        resp = await client.post("/ai/player-search", json=body, headers=_auth_headers(club))
        assert resp.status_code == 200, resp.text
        return {p["name"] for p in resp.json()["players"]}

    default = await names({"query": "any defenders"})
    assert default == {"Signable Sam", "Free Fred"}
    assert await names({"query": "any defenders", "buyable": False}) == set(statuses)


@pytest.mark.asyncio
async def test_ai_search_filters_by_price_and_contract_and_says_why(client: AsyncClient, db, monkeypatch):
    """Price comes from the fee model (as the Lite buy flow prices him, 30%
    off when his contract ends within a year), the contract from his record,
    and each result says why it matched."""
    from datetime import date, timedelta

    from app.ai import service
    from app.players.models import Player, PlayerStatus
    from tests.test_lite_buy import _value

    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")

    async def fake_chat(messages, *, user_id=None, endpoint=None, **_):
        return json.dumps({"position": "DEF", "max_value": 10_000_000, "contract_ends_within_months": 12,
                           "interpreted_as": "defenders under £10m, contract ending within a year"})

    monkeypatch.setattr(service, "chat", fake_chat)
    club = await _register(client, "nl_price@clubs-example.com", club_name="Price FC")
    soon = date.today() + timedelta(days=200)
    cases = {"Cheap Soon": (6_000_000, soon), "Dear Soon": (16_000_000, soon),
             "Cheap Later": (6_000_000, date.today() + timedelta(days=900)), "Unpriced Soon": (None, soon)}
    for name, (fair, ends) in cases.items():
        created = await _player(client, club, name)
        row = await db.get(Player, uuid.UUID(created["id"]))
        row.status, row.contract_expiry = PlayerStatus.CONTRACTED, ends
        await db.commit()
        if fair:
            await _value(db, created["id"], fair)

    resp = await client.post("/ai/player-search", json={"query": "cheap defenders out of contract soon"},
                             headers=_auth_headers(club))
    assert resp.status_code == 200, resp.text
    players = resp.json()["players"]
    assert [p["name"] for p in players] == ["Cheap Soon"]
    hit = players[0]
    assert (hit["price"], hit["price_basis"]) == (4_200_000, "model, contract ending")
    assert hit["contract_ends"] == soon.isoformat()
    assert "DEF" in hit["why"] and any(w.startswith("contract ends") for w in hit["why"])
