"""Check your squad (Phase 1): every squad player's contract, wage and
valuation, what's missing, and confirming it."""
import uuid
from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.audit.models import AuditEvent
from app.players.models import Contract, Player
from tests.conftest import _auth_headers, _register
from tests.test_deals import _create_player_for_seller, _get_club_id
from tests.test_team_management import _invite, _token_from

pytestmark = pytest.mark.asyncio
NEXT_YEAR = (date.today() + timedelta(days=365)).isoformat()


async def _club(client):
    tokens = await _register(client, f"squad_{uuid.uuid4().hex[:6]}@test.com", club_name="Squad Check FC")
    return _auth_headers(tokens)


async def test_flags_what_is_missing_and_confirming_clears_it(client: AsyncClient, db):
    headers = await _club(client)
    player = await _create_player_for_seller(client, headers)
    club_id = uuid.UUID(await _get_club_id(client, headers))
    # A player placed in the squad with no contract at all (as staff imports can).
    bare = Player(name="Aaron Bare", position="DEF", current_club_id=club_id)
    db.add(bare)
    await db.commit()

    check = (await client.get("/clubs/me/squad-check", headers=headers)).json()
    assert check["total"] == 2 and check["confirmed"] == 0 and check["without_contract"] == 2
    first = check["players"][0]
    assert first["name"] == "Aaron Bare" and first["issues"] == ["NO_CONTRACT"]  # worst first

    resp = await client.post(f"/clubs/me/squad-check/{bare.id}/confirm", headers=headers,
                             json={"end_date": NEXT_YEAR, "wage_weekly": 40000, "club_valuation": 9000000})
    assert resp.status_code == 200, resp.text
    row = resp.json()
    assert row["confirmed"] and row["issues"] == [] and row["contract"]["confirmed_by"]
    contract = (await db.execute(select(Contract).where(Contract.player_id == bare.id, Contract.is_active.is_(True)))).scalar_one()
    assert contract.club_id == club_id and float(contract.wage_weekly) == 40000
    event = (await db.execute(select(AuditEvent).where(AuditEvent.action == "SQUAD_CONTRACT_CONFIRMED"))).scalar_one()
    assert event.payload_json["changes"]["contract"] == "created" and "(created it)" in event.description

    # The one the club added itself has no contract either; confirming without
    # a valuation creates it, and the valuation stays flagged as optional.
    resp = await client.post(f"/clubs/me/squad-check/{player['id']}/confirm", headers=headers,
                             json={"end_date": NEXT_YEAR, "wage_weekly": 25000})
    assert resp.status_code == 200, resp.text
    assert resp.json()["confirmed"] and resp.json()["issues"] == ["NO_VALUATION"]
    check = (await client.get("/clubs/me/squad-check", headers=headers)).json()
    assert check["confirmed"] == 2 and check["without_contract"] == 0 and check["needs_attention"] == 0


async def test_who_can_confirm_and_what_is_refused(client: AsyncClient, db):
    owner_tokens = await _register(client, "squad_owner@test.com", club_name="Squad Rules FC")
    headers = _auth_headers(owner_tokens)
    player = await _create_player_for_seller(client, headers)

    past = (date.today() - timedelta(days=1)).isoformat()
    resp = await client.post(f"/clubs/me/squad-check/{player['id']}/confirm", headers=headers,
                             json={"end_date": past, "wage_weekly": 1000})
    assert resp.status_code == 422
    assert (await client.post(f"/clubs/me/squad-check/{player['id']}/confirm", headers=headers,
                              json={"end_date": NEXT_YEAR, "wage_weekly": 0})).status_code == 422

    # A scout can look but not confirm.
    data = await _invite(client, owner_tokens, "squad_scout@test.com", "SCOUT")
    scout = (await client.post(f"/auth/invitations/{_token_from(data['accept_url'])}/accept",
                               json={"password": "newpass123"})).json()
    assert (await client.get("/clubs/me/squad-check", headers=_auth_headers(scout))).status_code == 200
    assert (await client.post(f"/clubs/me/squad-check/{player['id']}/confirm", headers=_auth_headers(scout),
                              json={"end_date": NEXT_YEAR, "wage_weekly": 1000})).status_code == 403

    # Another club can't touch him.
    other = await _club(client)
    assert (await client.post(f"/clubs/me/squad-check/{player['id']}/confirm", headers=other,
                              json={"end_date": NEXT_YEAR, "wage_weekly": 1000})).status_code == 403
