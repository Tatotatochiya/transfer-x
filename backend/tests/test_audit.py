"""TRA-141 — deal audit-log scoping tests."""

import csv
import io
import uuid as _uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from tests.conftest import _auth_headers, _register


async def _give_budget(db, amount: Decimal = Decimal("100000000")):
    from app.clubs.models import ClubFinance

    result = await db.execute(select(ClubFinance))
    for f in result.scalars():
        f.transfer_budget_total = amount
    await db.commit()


async def _create_deal(client: AsyncClient, db) -> dict:
    """Buyer + seller, a player owned by the seller, and a deal via accepted offer."""
    buyer = await _register(client, "buyer_audit@test.com", club_name="Audit Buyer FC")
    seller = await _register(client, "seller_audit@test.com", club_name="Audit Seller FC")
    await _give_budget(db)

    sel_headers = _auth_headers(seller)
    buy_headers = _auth_headers(buyer)

    player_resp = await client.post(
        "/players", json={"name": "Audit Player", "position": "FWD"}, headers=sel_headers
    )
    player = player_resp.json()
    seller_club_id = (await client.get("/clubs/me", headers=sel_headers)).json()["id"]

    offer_resp = await client.post(
        "/offers",
        json={"player_id": player["id"], "to_club_id": seller_club_id, "fee_amount": 5_000_000},
        headers=buy_headers,
    )
    offer_id = offer_resp.json()["id"]
    deal_resp = await client.post(f"/offers/{offer_id}/accept", headers=sel_headers)
    assert deal_resp.status_code == 200, deal_resp.text

    return {"deal": deal_resp.json(), "buyer": buyer, "seller": seller}


@pytest.mark.asyncio
async def test_participant_can_read_audit_log(client: AsyncClient, db):
    ctx = await _create_deal(client, db)
    deal_id = ctx["deal"]["id"]

    resp = await client.get(f"/deals/{deal_id}/audit-log", headers=_auth_headers(ctx["buyer"]))
    assert resp.status_code == 200
    events = resp.json()
    assert len(events) >= 1
    assert any(e["action"] == "DEAL_CREATED" for e in events)


@pytest.mark.asyncio
async def test_non_participant_cannot_read_audit_log(client: AsyncClient, db):
    """TRA-141: only deal participants (or staff) may read a deal's audit log."""
    ctx = await _create_deal(client, db)
    deal_id = ctx["deal"]["id"]
    outsider = await _register(client, "outsider_audit@test.com", club_name="Outsider Audit FC")

    resp = await client.get(f"/deals/{deal_id}/audit-log", headers=_auth_headers(outsider))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_non_participant_cannot_export_audit_log_csv(client: AsyncClient, db):
    ctx = await _create_deal(client, db)
    deal_id = ctx["deal"]["id"]
    outsider = await _register(client, "outsider_audit_csv@test.com", club_name="Outsider Audit CSV FC")

    resp = await client.get(f"/deals/{deal_id}/audit-log/export.csv", headers=_auth_headers(outsider))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_nonexistent_deal_audit_log_404s(client: AsyncClient, db):
    resp = await client.get(
        "/deals/00000000-0000-0000-0000-000000000000/audit-log",
        headers=_auth_headers(await _register(client, "solo_audit@test.com", club_name="Solo FC")),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_audit_log_csv_resolves_actor_labels(client: AsyncClient, db):
    """CSV export must not leak raw actor UUIDs — TRA-141 resolves them via
    room_service.label_for_user. No current write path populates actor_user_id
    on a DEAL audit event, so this stamps one directly to exercise the
    export's label-resolution code path in isolation."""
    from app.audit.models import AuditEvent
    from app.auth.models import User

    ctx = await _create_deal(client, db)
    deal_id = ctx["deal"]["id"]

    user_result = await db.execute(select(User).where(User.email == "seller_audit@test.com"))
    seller_user = user_result.scalar_one()

    db.add(AuditEvent(
        entity_type="DEAL",
        entity_id=_uuid.UUID(deal_id),
        actor_user_id=seller_user.id,
        action="TEST_EVENT",
        description="test event with a real actor",
    ))
    await db.commit()

    resp = await client.get(
        f"/deals/{deal_id}/audit-log/export.csv", headers=_auth_headers(ctx["seller"])
    )
    assert resp.status_code == 200

    rows = list(csv.reader(io.StringIO(resp.text)))
    header, data_rows = rows[0], rows[1:]
    assert header[2] == "actor"

    test_row = next(r for r in data_rows if r[1] == "TEST_EVENT")
    assert test_row[2] == "Audit Seller FC"
