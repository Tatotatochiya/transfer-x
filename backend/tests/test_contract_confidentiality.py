"""A club's contract with its player is confidential (player profile ledger, P0).

Rival clubs see the release clause and end date, which the market needs,
never the wage, signing date, the holding club's own valuation or its notes.
That holds on the player page, the club squad list and in what the AI is
told about the player.
"""

import uuid
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from tests.conftest import _auth_headers, _register
from tests.test_deals import _get_club_id

PRIVATE = ("wage_weekly", "start_date", "club_valuation", "notes")


@pytest_asyncio.fixture
async def holder(client: AsyncClient) -> dict:
    return await _register(client, "holder_cc@clubs-example.com", club_name="Holding FC")


@pytest_asyncio.fixture
async def rival(client: AsyncClient) -> dict:
    return await _register(client, "rival_cc@clubs-example.com", club_name="Rival FC")


async def _contracted(client, db, holder) -> dict:
    from app.players.models import Contract

    resp = await client.post("/players", json={"name": "Private Terms", "position": "MID"}, headers=_auth_headers(holder))
    assert resp.status_code == 201, resp.text
    player = resp.json()
    club_id = await _get_club_id(client, _auth_headers(holder))
    resp = await client.post(f"/players/{player['id']}/contracts", json={
        "club_id": club_id, "start_date": "2024-07-01", "end_date": "2028-06-30",
        "wage_weekly": 45000, "release_clause": 30000000, "notes": "Wants to stay",
    }, headers=_auth_headers(holder))
    assert resp.status_code == 201, resp.text
    contract = (await db.execute(select(Contract).where(Contract.player_id == uuid.UUID(player["id"])))).scalar_one()
    contract.club_valuation = Decimal("22000000")
    await db.commit()
    return player


@pytest.mark.asyncio
async def test_player_page_hides_private_terms_from_rival_clubs(client: AsyncClient, db, holder, rival):
    player = await _contracted(client, db, holder)

    own = (await client.get(f"/players/market/{player['id']}", headers=_auth_headers(holder))).json()["active_contract"]
    assert float(own["wage_weekly"]) == 45000 and float(own["club_valuation"]) == 22_000_000
    assert own["notes"] == "Wants to stay" and own["start_date"] == "2024-07-01"

    theirs = (await client.get(f"/players/market/{player['id']}", headers=_auth_headers(rival))).json()["active_contract"]
    assert all(theirs[f] is None for f in PRIVATE)
    assert float(theirs["release_clause"]) == 30_000_000 and theirs["end_date"] == "2028-06-30"

    signed_out = (await client.get(f"/players/market/{player['id']}")).json()
    assert signed_out["active_contract"] is None


@pytest.mark.asyncio
async def test_squad_list_hides_private_terms_from_rival_clubs(client: AsyncClient, db, holder, rival):
    player = await _contracted(client, db, holder)
    club_id = await _get_club_id(client, _auth_headers(holder))

    def row(resp):
        return next(p for p in resp.json()["items"] if p["id"] == player["id"])["active_contract"]

    theirs = row(await client.get(f"/clubs/{club_id}/players", headers=_auth_headers(rival)))
    assert all(theirs[f] is None for f in PRIVATE) and float(theirs["release_clause"]) == 30_000_000
    own = row(await client.get(f"/clubs/{club_id}/players", headers=_auth_headers(holder)))
    assert float(own["wage_weekly"]) == 45000


@pytest.mark.asyncio
async def test_the_ai_is_told_only_the_estimate_about_a_rivals_player(client: AsyncClient, db, holder, rival):
    from app.ai.assist import _player_facts
    from app.ai.context import build_player_context
    from app.players.models import Player

    player = await _contracted(client, db, holder)
    row = await db.get(Player, uuid.UUID(player["id"]))
    row.wage_weekly = Decimal("38000")  # the public (e.g. Capology) estimate
    await db.commit()
    pid = uuid.UUID(player["id"])
    holder_club = uuid.UUID(await _get_club_id(client, _auth_headers(holder)))
    rival_club = uuid.UUID(await _get_club_id(client, _auth_headers(rival)))

    rival_facts = await _player_facts(db, pid, rival_club)
    assert (rival_facts["current_wage_weekly"], rival_facts["current_wage_is_estimate"]) == (38000, True)
    assert (await _player_facts(db, pid, holder_club))["current_wage_weekly"] == 45000

    rival_context = await build_player_context(db, pid, viewer_club_id=rival_club)
    assert "club_valuation" not in rival_context and "wage_weekly" not in rival_context
    assert rival_context["wage_weekly_estimate"] == 38000 and rival_context["release_clause"] == 30_000_000
    own_context = await build_player_context(db, pid, viewer_club_id=holder_club)
    assert own_context["club_valuation"] == 22_000_000
