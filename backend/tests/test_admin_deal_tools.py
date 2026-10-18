"""Staff tools for a stuck deal (app/admin/deal_tools.py): each goes through
the deal's own service, needs a reason, is in the admin audit log, and tells
both clubs."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from tests.conftest import _auth_headers, _register
from tests.test_deals import _advance_through_personal_terms, _create_deal_via_offer, _get_finance

pytestmark = pytest.mark.asyncio
REASON = "Both clubs confirmed by phone"


@pytest_asyncio.fixture
async def parties(client: AsyncClient, db) -> dict:
    from app.auth.models import User

    buyer = await _register(client, "tools_buyer@clubs-example.com", club_name="Tools Buyers")
    seller = await _register(client, "tools_seller@clubs-example.com", club_name="Tools Sellers")
    staff = await _register(client, "tools_staff@clubs-example.com", club_name="Tools Staff FC")
    user = (await db.execute(select(User).where(User.email == "tools_staff@clubs-example.com"))).scalar_one()
    user.is_superuser = True
    await db.commit()
    return {"buyer": buyer, "seller": seller, "staff": _auth_headers(staff)}


async def _post(client, parties, deal_id, tool, **body):
    return await client.post(f"/admin/deals/{deal_id}/{tool}", json={"reason": REASON, **body}, headers=parties["staff"])


async def _events(db, action):
    from app.audit.models import AuditEvent

    return (await db.execute(select(AuditEvent).where(AuditEvent.action == action))).scalars().all()


async def _told(db, deal_id):
    from app.notifications.models import Notification

    return [n for n in (await db.execute(select(Notification).where(Notification.link == f"/deals/{deal_id}"))).scalars()
            if n.message.startswith("TransferX staff")]


async def test_collapse_releases_the_budget_and_tells_both_clubs_why(client: AsyncClient, db, parties):
    deal = await _create_deal_via_offer(client, parties["buyer"], parties["seller"], db, fee=5_000_000)
    buyer_h = _auth_headers(parties["buyer"])
    assert float((await _get_finance(client, buyer_h))["transfer_committed"]) == 5_000_000

    resp = await _post(client, parties, deal["id"], "collapse")
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "COLLAPSED"
    assert float((await _get_finance(client, buyer_h))["transfer_committed"]) == 0
    [event] = await _events(db, "admin.deal.collapsed")
    assert event.payload_json["reason"] == REASON
    told = await _told(db, deal["id"])
    assert told and all(REASON in n.message for n in told)
    # Twice is refused: it's already over.
    assert (await _post(client, parties, deal["id"], "collapse")).status_code == 409


async def test_advance_follows_the_stage_machine(client: AsyncClient, db, parties):
    deal = await _create_deal_via_offer(client, parties["buyer"], parties["seller"], db)
    resp = await _post(client, parties, deal["id"], "advance")
    assert resp.status_code == 200, resp.text
    assert resp.json()["stage"] == "PERSONAL_TERMS"
    [event] = await _events(db, "admin.deal.advanced")
    assert event.payload_json["from_stage"] == "AGREEMENT" and event.payload_json["to_stage"] == "PERSONAL_TERMS"


async def test_paperwork_and_medical_for_a_side_finish_the_checklist(client: AsyncClient, db, parties):
    deal = await _create_deal_via_offer(client, parties["buyer"], parties["seller"], db)
    await _advance_through_personal_terms(client, deal["id"], parties["buyer"], db)

    for step in ("buyer_signs_agreement", "seller_signs_agreement", "registration_submitted"):
        resp = await _post(client, parties, deal["id"], "paperwork", step=step)
        assert resp.status_code == 200, resp.text
    # Recording the same signature again is refused, as for the club.
    assert (await _post(client, parties, deal["id"], "paperwork", step="buyer_signs_agreement")).status_code == 409

    resp = await _post(client, parties, deal["id"], "medical", outcome="PASSED", notes="Club doctors agreed")
    assert resp.status_code == 200, resp.text
    # The last step done: the deal moves to confirmed, awaiting completion, on a deadline.
    assert (resp.json()["stage"], resp.json()["status"]) == ("CONFIRMED", "PENDING_COMPLETION")
    assert resp.json()["sla_deadline"] is not None
    assert len(await _events(db, "admin.deal.paperwork_recorded")) == 3
    assert len(await _events(db, "admin.deal.medical_recorded")) == 1


async def test_extend_the_completion_deadline(client: AsyncClient, db, parties):
    from app.deals.models import Deal

    deal = await _create_deal_via_offer(client, parties["buyer"], parties["seller"], db)
    # Not awaiting completion yet: it has no completion deadline.
    later = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
    assert (await _post(client, parties, deal["id"], "deadline", until=later)).status_code == 409

    row = await db.get(Deal, uuid.UUID(deal["id"]))
    from app.deals.models import DealStage, DealStatus
    row.stage, row.status = DealStage.CONFIRMED, DealStatus.PENDING_COMPLETION
    row.sla_deadline = datetime.now(timezone.utc) - timedelta(days=1)
    row.sla_escalated_at = datetime.now(timezone.utc)
    await db.commit()

    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    assert (await _post(client, parties, deal["id"], "deadline", until=past)).status_code == 409
    resp = await _post(client, parties, deal["id"], "deadline", until=later)
    assert resp.status_code == 200, resp.text
    db.expire_all()
    row = await db.get(Deal, uuid.UUID(deal["id"]))
    assert row.sla_escalated_at is None  # the overnight check can flag it again
    assert abs((row.sla_deadline.replace(tzinfo=row.sla_deadline.tzinfo or timezone.utc)
                - datetime.fromisoformat(later)).total_seconds()) < 1


async def test_complete_settles_the_transfer(client: AsyncClient, db, parties):
    deal = await _create_deal_via_offer(client, parties["buyer"], parties["seller"], db)
    resp = await _post(client, parties, deal["id"], "complete")
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "COMPLETED"
    assert len(await _events(db, "admin.deal.completed")) == 1


async def test_staff_only_and_a_reason_is_required(client: AsyncClient, db, parties):
    deal = await _create_deal_via_offer(client, parties["buyer"], parties["seller"], db)
    as_club = await client.post(f"/admin/deals/{deal['id']}/collapse", json={"reason": REASON},
                                headers=_auth_headers(parties["buyer"]))
    assert as_club.status_code == 403
    no_reason = await client.post(f"/admin/deals/{deal['id']}/collapse", json={"reason": "no"}, headers=parties["staff"])
    assert no_reason.status_code == 422
    missing = await client.post(f"/admin/deals/{uuid.uuid4()}/collapse", json={"reason": REASON}, headers=parties["staff"])
    assert missing.status_code == 404
    bad_step = await _post(client, parties, deal["id"], "paperwork", step="anything")
    assert bad_step.status_code == 422
