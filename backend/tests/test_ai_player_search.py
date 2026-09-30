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
