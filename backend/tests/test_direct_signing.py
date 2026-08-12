"""Item 13 (scoped) — free-agent signing and pre-contract (Bosman) deals."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient

from tests.conftest import _auth_headers, _register

pytestmark = pytest.mark.asyncio


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def seller(client: AsyncClient) -> dict:
    return await _register(client, "sign_seller@test.com", club_name="Sign Seller FC")


@pytest_asyncio.fixture
async def buyer(client: AsyncClient) -> dict:
    return await _register(client, "sign_buyer@test.com", club_name="Sign Buyer FC")


async def _give_budget(db, amount: Decimal = Decimal("100000000")):
    from app.clubs.models import ClubFinance
    from sqlalchemy import select

    result = await db.execute(select(ClubFinance))
    for f in result.scalars():
        f.transfer_budget_total = amount
    await db.commit()


async def _create_free_agent(client: AsyncClient, headers: dict) -> dict:
    resp = await client.post(
        "/players", json={"name": "Free Player", "position": "MID"}, headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_contracted_player(
    client: AsyncClient, sel_headers: dict, end_date: date,
) -> dict:
    player_resp = await client.post(
        "/players", json={"name": "Contracted Player", "position": "DEF"}, headers=sel_headers,
    )
    player = player_resp.json()
    seller_club_id = (await client.get("/clubs/me", headers=sel_headers)).json()["id"]
    resp = await client.post(
        f"/players/{player['id']}/contracts",
        json={"club_id": seller_club_id, "wage_weekly": "40000", "end_date": end_date.isoformat()},
        headers=sel_headers,
    )
    assert resp.status_code == 201, resp.text
    return player


# ── Free-agent signing ────────────────────────────────────────────────────────


async def test_sign_free_agent_creates_deal(client: AsyncClient, buyer: dict, db):
    buy_headers = _auth_headers(buyer)
    player = await _create_free_agent(client, buy_headers)

    resp = await client.post(f"/players/{player['id']}/sign-free-agent", headers=buy_headers)
    assert resp.status_code == 200, resp.text
    deal = resp.json()
    assert deal["status"] == "IN_PROGRESS"
    assert deal["stage"] == "AGREEMENT"
    assert deal["seller_club_id"] is None
    assert float(deal["agreed_fee"]) == 0


async def test_cannot_sign_contracted_player_as_free_agent(
    client: AsyncClient, buyer: dict, seller: dict, db,
):
    sel_headers, buy_headers = _auth_headers(seller), _auth_headers(buyer)
    player = await _create_contracted_player(client, sel_headers, date.today() + timedelta(days=400))

    resp = await client.post(f"/players/{player['id']}/sign-free-agent", headers=buy_headers)
    assert resp.status_code == 400
    assert "free agent" in resp.json()["detail"].lower()


# ── ADR 0003: vendor-imported players are EXTERNAL, never free agents ────────


async def _make_vendor_player(client: AsyncClient, db, headers: dict, name: str = "Vendor Star") -> dict:
    """A player as the stats vendor imports them: a real-world club in
    `team_name`, no TransferX contract. Before ADR 0003 this stored as
    FREE_AGENT, which made them signable for nothing."""
    import uuid as uuid_mod

    from sqlalchemy import select

    from app.players import service as players_service
    from app.players.models import Player

    resp = await client.post("/players", json={"name": name, "position": "FWD"}, headers=headers)
    assert resp.status_code == 201, resp.text
    created = resp.json()

    player = (
        await db.execute(select(Player).where(Player.id == uuid_mod.UUID(created["id"])))
    ).scalar_one()
    player.team_name = "Barcelona"
    await players_service.normalize_player_status(db, player)
    await db.commit()
    return created


async def test_vendor_player_is_external_not_free_agent(client: AsyncClient, buyer: dict, db):
    buy_headers = _auth_headers(buyer)
    player = await _make_vendor_player(client, db, buy_headers)

    detail = (await client.get(f"/players/market/{player['id']}", headers=buy_headers)).json()
    assert detail["status"] == "EXTERNAL"


async def test_cannot_sign_vendor_player_as_free_agent(client: AsyncClient, buyer: dict, db):
    """The exploit this ADR closes: every vendor-imported professional was
    stored FREE_AGENT, and sign_free_agent gated on nothing else."""
    buy_headers = _auth_headers(buyer)
    player = await _make_vendor_player(client, db, buy_headers)

    resp = await client.post(f"/players/{player['id']}/sign-free-agent", headers=buy_headers)
    assert resp.status_code == 400
    assert "outside transferx" in resp.json()["detail"].lower()


async def test_vendor_player_returns_to_external_when_contract_lapses(
    client: AsyncClient, buyer: dict, seller: dict, db,
):
    """A vendor player signed to a TransferX club and then released must fall
    back to EXTERNAL — not FREE_AGENT, which would make them free to sign."""
    import uuid as uuid_mod

    from sqlalchemy import select

    from app.players.models import Player

    sel_headers, buy_headers = _auth_headers(seller), _auth_headers(buyer)
    player = await _make_vendor_player(client, db, sel_headers, name="Vendor Loanee")
    seller_club_id = (await client.get("/clubs/me", headers=sel_headers)).json()["id"]

    contract = await client.post(
        f"/players/{player['id']}/contracts",
        json={"club_id": seller_club_id, "wage_weekly": "25000"},
        headers=sel_headers,
    )
    assert contract.status_code == 201, contract.text

    fresh = (
        await db.execute(select(Player).where(Player.id == uuid_mod.UUID(player["id"])))
    ).scalar_one()
    await db.refresh(fresh)
    assert fresh.status.value == "CONTRACTED"

    released = await client.delete(
        f"/players/{player['id']}/contracts/{contract.json()['id']}", headers=sel_headers
    )
    assert released.status_code in (200, 204), released.text

    await db.refresh(fresh)
    assert fresh.status.value == "EXTERNAL"

    resp = await client.post(f"/players/{player['id']}/sign-free-agent", headers=buy_headers)
    assert resp.status_code == 400


# ── Pre-contract (Bosman) ─────────────────────────────────────────────────────


async def test_pre_contract_within_window_succeeds(client: AsyncClient, buyer: dict, seller: dict, db):
    sel_headers, buy_headers = _auth_headers(seller), _auth_headers(buyer)
    player = await _create_contracted_player(client, sel_headers, date.today() + timedelta(days=90))

    resp = await client.post(f"/players/{player['id']}/pre-contract", headers=buy_headers)
    assert resp.status_code == 200, resp.text
    deal = resp.json()
    assert deal["deal_type"] == "PRE_CONTRACT"
    assert float(deal["agreed_fee"]) == 0
    assert deal["seller_club_id"] is not None


async def test_pre_contract_outside_window_rejected(client: AsyncClient, buyer: dict, seller: dict, db):
    sel_headers, buy_headers = _auth_headers(seller), _auth_headers(buyer)
    player = await _create_contracted_player(client, sel_headers, date.today() + timedelta(days=400))

    resp = await client.post(f"/players/{player['id']}/pre-contract", headers=buy_headers)
    assert resp.status_code == 400
    assert "final" in resp.json()["detail"].lower()


async def test_pre_contract_expired_contract_rejected(client: AsyncClient, buyer: dict, seller: dict, db):
    sel_headers, buy_headers = _auth_headers(seller), _auth_headers(buyer)
    player = await _create_contracted_player(client, sel_headers, date.today() - timedelta(days=10))

    resp = await client.post(f"/players/{player['id']}/pre-contract", headers=buy_headers)
    assert resp.status_code == 400
    assert "expired" in resp.json()["detail"].lower()


async def test_cannot_pre_contract_own_player(client: AsyncClient, seller: dict, db):
    sel_headers = _auth_headers(seller)
    player = await _create_contracted_player(client, sel_headers, date.today() + timedelta(days=90))

    resp = await client.post(f"/players/{player['id']}/pre-contract", headers=sel_headers)
    assert resp.status_code == 400
    assert "own player" in resp.json()["detail"].lower()


async def test_pre_contract_rejects_rival_offers(client: AsyncClient, buyer: dict, seller: dict, db):
    from sqlalchemy import select

    from app.auth.models import User
    from app.notifications.models import Notification, NotificationType

    sel_headers, buy_headers = _auth_headers(seller), _auth_headers(buyer)
    player = await _create_contracted_player(client, sel_headers, date.today() + timedelta(days=90))
    seller_club_id = (await client.get("/clubs/me", headers=sel_headers)).json()["id"]

    rival = await _register(client, "precontract_rival@test.com", club_name="Precontract Rival FC")
    rival_headers = _auth_headers(rival)
    await _give_budget(db)
    rival_offer = await client.post(
        "/offers",
        json={"player_id": player["id"], "to_club_id": seller_club_id, "fee_amount": 5_000_000},
        headers=rival_headers,
    )
    assert rival_offer.status_code == 201

    resp = await client.post(f"/players/{player['id']}/pre-contract", headers=buy_headers)
    assert resp.status_code == 200, resp.text

    rival_offer_after = await client.get(f"/offers/{rival_offer.json()['id']}", headers=rival_headers)
    assert rival_offer_after.json()["status"] == "REJECTED"
