"""Staff-entered transfer fees (market-v3): the admin API, the anchor it
feeds, and the vendor sync it survives."""
import uuid
from datetime import date, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from app.audit.models import AuditEvent
from app.auth.models import User
from app.players.models import PlayerTransfer
from tests.conftest import _auth_headers, _register
from tests.test_valuation_v2 import _player, _stats

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def admin(client, db):
    tokens = await _register(client, "fee_admin@test.com", club_name="Fee Admin FC")
    user = (await db.execute(select(User).where(User.email == "fee_admin@test.com"))).scalar_one()
    user.is_superuser = True
    await db.commit()
    return {"tokens": tokens, "headers": _auth_headers(tokens), "id": user.id}


def _body(**overrides) -> dict:
    body = {
        "amount": 105_000_000,
        "currency": "GBP",
        "transfer_date": "2023-07-15",
        "from_club": "Ajax",
        "to_club": "Arsenal",
        "source_note": "BBC Sport, 15 Jul 2023",
    }
    body.update(overrides)
    return body


def _vendor_move(p, day, fee="€ 60M"):
    return PlayerTransfer(player_id=p.id, vendor="api_sports_v3", transfer_date=day,
                          transfer_type="Transfer", fee_display=fee,
                          team_out_name="Ajax", team_in_name="Arsenal")


def _url(player_id) -> str:
    return f"/admin/players/{player_id}/transfer-fees"


# ── Permissions and validation ───────────────────────────────────────────────


async def _delete(client, url: str, headers: dict, reason: str | None = "Wrong figure, see statement"):
    """DELETE with the reason the endpoint requires (httpx's delete() takes no body)."""
    return await client.request("DELETE", url, json={"reason": reason} if reason is not None else None,
                                headers=headers)


async def test_the_fee_endpoints_are_superuser_only(client: AsyncClient, db):
    regular = await _register(client, "fee_regular@test.com", club_name="Regular FC")
    p = await _player(db)
    h = _auth_headers(regular)
    assert (await client.get(_url(p.id), headers=h)).status_code == 403
    assert (await client.post(_url(p.id), json=_body(), headers=h)).status_code == 403
    assert (await _delete(client, f"{_url(p.id)}/{uuid.uuid4()}", h)).status_code == 403


async def test_an_unknown_player_is_a_404(client, db, admin):
    assert (await client.get(_url(uuid.uuid4()), headers=admin["headers"])).status_code == 404
    assert (await client.post(_url(uuid.uuid4()), json=_body(),
                              headers=admin["headers"])).status_code == 404


@pytest.mark.parametrize(
    "override",
    [
        {"source_note": ""},  # required
        {"source_note": "abcd"},  # too short
        {"transfer_date": (date.today() + timedelta(days=1)).isoformat()},  # future
        {"currency": "JPY"},
        {"amount": 0},
        {"amount": 500_000_001},
        {"source_url": "ftp://example.com/fee"},
    ],
)
async def test_bad_input_is_rejected(client, db, admin, override):
    p = await _player(db)
    resp = await client.post(_url(p.id), json=_body(**override), headers=admin["headers"])
    assert resp.status_code == 422, resp.text


# ── Add ───────────────────────────────────────────────────────────────────────


async def test_adding_a_fee_shows_it_as_the_last_transfer(client, db, admin):
    p = await _player(db)
    await _stats(db, p)
    db.add(_vendor_move(p, date(2023, 7, 10), "€ 60M"))
    await db.commit()

    recent = (date.today() - timedelta(days=100)).isoformat()
    resp = await client.post(_url(p.id), json=_body(transfer_date=recent), headers=admin["headers"])
    assert resp.status_code == 201, resp.text
    created = resp.json()
    assert (created["vendor"], created["fee_display"], created["fee_gbp"]) == (
        "manual", "£ 105M", 105_000_000)
    assert created["fee_basis"] == "PERMANENT"
    assert created["entered_by_user_id"] == str(admin["id"])
    assert (created["from_club"], created["to_club"]) == ("Ajax", "Arsenal")

    rows = (await client.get(_url(p.id), headers=admin["headers"])).json()
    assert rows[0]["id"] == created["id"]  # newest first
    assert {r["vendor"] for r in rows} == {"manual", "api_sports_v3"}

    valuation = (await client.get(f"/valuation/players/{p.id}", headers=admin["headers"])).json()
    assert valuation["last_transfer"]["source"] == "Staff-entered"
    assert valuation["fee_anchor"]["applied"] is True

    # The note is the staff's: never in the public ledger or the valuation,
    # signed in or not. The admin list above still has it.
    ledger = (await client.get(f"/players/market/{p.id}/ledger", headers=admin["headers"])).json()
    assert ledger["last_transfer"]["source"] == "Staff-entered"
    public = (await client.get(f"/players/market/{p.id}/ledger")).text
    assert "BBC Sport" not in public and "BBC Sport" not in str(valuation)
    assert rows[0]["source_note"] == "BBC Sport, 15 Jul 2023"


async def test_an_older_staff_fee_does_not_become_the_last_transfer(client, db, admin):
    p = await _player(db)
    await _stats(db, p)
    db.add(_vendor_move(p, date(2024, 7, 15)))
    await db.commit()

    resp = await client.post(_url(p.id), json=_body(transfer_date="2019-07-15"),
                             headers=admin["headers"])
    assert resp.status_code == 201, resp.text
    valuation = (await client.get(f"/valuation/players/{p.id}", headers=admin["headers"])).json()
    assert valuation["last_transfer"]["source"] == "API-Football"


async def test_the_stored_row_records_the_staff_source_and_its_weight(client, db, admin):
    from app.valuation.models import PlayerValuation

    p = await _player(db)
    await _stats(db, p)
    transfer_date = (date.today() - timedelta(days=365)).isoformat()
    resp = await client.post(_url(p.id), json=_body(transfer_date=transfer_date),
                             headers=admin["headers"])
    assert resp.status_code == 201, resp.text

    row = (await db.execute(
        select(PlayerValuation).where(PlayerValuation.player_id == p.id))).scalars().one()
    last_fee = row.inputs_json["features"]["last_fee"]
    assert (last_fee["source"], last_fee["basis"]) == ("MANUAL", "PERMANENT")
    # credibility 0.80 (staff-entered) × recency × evidence
    minutes = last_fee["minutes_at_transfer"]
    evidence = 0.60 if minutes is None else min(1.0, minutes / 1800)
    expected = 0.80 * (1 / (1 + last_fee["years_since"] / 3)) * evidence
    assert row.inputs_json["fee_anchor"]["weight"] == pytest.approx(expected)
    assert row.inputs_json["fee_anchor"]["applied"] is True


async def test_a_release_clause_fee_reaches_the_model_with_its_basis(client, db, admin):
    from app.valuation.models import PlayerValuation

    p = await _player(db)
    await _stats(db, p)
    resp = await client.post(_url(p.id), json=_body(basis="RELEASE_CLAUSE"),
                             headers=admin["headers"])
    assert resp.status_code == 201, resp.text
    assert resp.json()["fee_basis"] == "RELEASE_CLAUSE"

    row = (await db.execute(
        select(PlayerValuation).where(PlayerValuation.player_id == p.id))).scalars().one()
    last_fee = row.inputs_json["features"]["last_fee"]
    assert last_fee["basis"] == "RELEASE_CLAUSE"
    # credibility 0.80 × basis weight 0.40 × recency × evidence
    minutes = last_fee["minutes_at_transfer"]
    evidence = 0.60 if minutes is None else min(1.0, minutes / 1800)
    expected = 0.80 * 0.40 * (1 / (1 + last_fee["years_since"] / 3)) * evidence
    assert row.inputs_json["fee_anchor"]["weight"] == pytest.approx(expected)


# ── Delete ────────────────────────────────────────────────────────────────────


async def test_deleting_the_staff_fee_restores_the_vendors_figure(client, db, admin):
    p = await _player(db)
    await _stats(db, p)
    db.add(_vendor_move(p, date(2023, 7, 10)))
    await db.commit()
    created = (await client.post(_url(p.id), json=_body(), headers=admin["headers"])).json()

    # Same move as the vendor row (within 60 days): the staff figure wins.
    valuation = (await client.get(f"/valuation/players/{p.id}", headers=admin["headers"])).json()
    assert valuation["last_transfer"]["source"] == "Staff-entered"

    resp = await _delete(client, f"{_url(p.id)}/{created['id']}", admin["headers"])
    assert resp.status_code == 204, resp.text
    valuation = (await client.get(f"/valuation/players/{p.id}", headers=admin["headers"])).json()
    assert valuation["last_transfer"]["source"] == "API-Football"
    assert valuation["last_transfer"]["fee_display"] == "€ 60M"

    remaining = (await client.get(_url(p.id), headers=admin["headers"])).json()
    assert [r["vendor"] for r in remaining] == ["api_sports_v3"]
    resp = await _delete(client, f"{_url(p.id)}/{remaining[0]['id']}", admin["headers"])
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Only staff-entered fees can be removed"


async def test_a_fee_cannot_be_deleted_through_another_player(client, db, admin):
    p = await _player(db)
    other = await _player(db, name="Other Player")
    created = (await client.post(_url(p.id), json=_body(), headers=admin["headers"])).json()
    resp = await _delete(client, f"{_url(other.id)}/{created['id']}", admin["headers"])
    assert resp.status_code == 404


async def test_each_add_and_delete_is_audited(client, db, admin):
    p = await _player(db)
    created = (await client.post(_url(p.id), json=_body(), headers=admin["headers"])).json()
    await _delete(client, f"{_url(p.id)}/{created['id']}", admin["headers"])

    added = (await db.execute(select(AuditEvent).where(
        AuditEvent.action == "admin.player.transfer_fee_added"))).scalars().all()
    removed = (await db.execute(select(AuditEvent).where(
        AuditEvent.action == "admin.player.transfer_fee_removed"))).scalars().all()
    assert len(added) == 1 and len(removed) == 1
    assert added[0].actor_user_id == admin["id"]
    assert added[0].entity_type == "player" and added[0].entity_id == p.id
    assert added[0].payload_json["amount"] == 105_000_000
    assert added[0].payload_json["source_note"] == "BBC Sport, 15 Jul 2023"
    assert removed[0].payload_json["fee_display"] == "£ 105M"
    assert removed[0].payload_json["source_note"] == "BBC Sport, 15 Jul 2023"
    assert removed[0].payload_json["reason"] == "Wrong figure, see statement"


async def test_removing_a_fee_needs_a_reason(client, db, admin):
    p = await _player(db)
    created = (await client.post(_url(p.id), json=_body(), headers=admin["headers"])).json()
    url = f"{_url(p.id)}/{created['id']}"
    assert (await _delete(client, url, admin["headers"], reason=None)).status_code == 422
    assert (await _delete(client, url, admin["headers"], reason="oops")).status_code == 422  # under 5
    assert len((await client.get(_url(p.id), headers=admin["headers"])).json()) == 1


# ── Vendor sync ───────────────────────────────────────────────────────────────


class _StubClient:
    """API-Football's /transfers answer for one move."""

    async def get_player_transfers(self, vendor_id: int) -> dict:
        return {"response": [{"transfers": [{
            "date": "2023-07-15",
            "type": "€ 60M",
            "teams": {"in": {"id": 1, "name": "Arsenal"}, "out": {"id": 2, "name": "Ajax"}},
        }]}]}


async def test_a_staff_fee_survives_the_vendor_refresh(client, db, admin):
    from app.vendor.history import refresh_transfers

    p = await _player(db)
    p.vendor_id = "1234"
    await _stats(db, p)
    await db.commit()
    created = (await client.post(_url(p.id), json=_body(), headers=admin["headers"])).json()

    await refresh_transfers(db, p, _StubClient())
    await db.commit()

    rows = (await client.get(_url(p.id), headers=admin["headers"])).json()
    assert created["id"] in {r["id"] for r in rows}
    assert {r["vendor"] for r in rows} == {"manual", "api_sports_v3"}
    # The staff figure still wins for the same move.
    valuation = (await client.get(f"/valuation/players/{p.id}", headers=admin["headers"])).json()
    assert valuation["last_transfer"]["source"] == "Staff-entered"
