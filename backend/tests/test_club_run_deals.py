"""Clubs run a deal end to end, and personal-terms consent
recorded by the buying club for a player with no account or agent (ADR 0006)."""

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from tests.conftest import _auth_headers, _register
from tests.test_deals import _create_deal_via_offer


@pytest_asyncio.fixture
async def buyer(client: AsyncClient) -> dict:
    return await _register(client, "buyer_run@test.com", club_name="Run Buyer FC")


@pytest_asyncio.fixture
async def seller(client: AsyncClient) -> dict:
    return await _register(client, "seller_run@test.com", club_name="Run Seller FC")


@pytest_asyncio.fixture
async def rival(client: AsyncClient) -> dict:
    return await _register(client, "rival_run@test.com", club_name="Run Rival FC")


async def _audit(db, entity_id: str, action: str):
    from app.audit.models import AuditEvent

    return (await db.execute(
        select(AuditEvent).where(AuditEvent.entity_id == uuid.UUID(entity_id), AuditEvent.action == action)
    )).scalars().all()


async def _deal_at_personal_terms(client, buyer, seller, db) -> str:
    deal = await _create_deal_via_offer(client, buyer, seller, db)
    resp = await client.post(f"/deals/{deal['id']}/advance", headers=_auth_headers(buyer))
    assert resp.status_code == 200, resp.text
    assert resp.json()["stage"] == "PERSONAL_TERMS"
    return deal["id"]


async def _propose_terms(client, buyer, deal_id):
    resp = await client.put(
        f"/deals/{deal_id}/personal-terms", json={"wage_weekly": 50000, "length_years": 3},
        headers=_auth_headers(buyer),
    )
    assert resp.status_code == 200, resp.text


async def _upload(client, club, deal_id, audience="BUYER_ONLY") -> str:
    resp = await client.post(
        f"/deals/{deal_id}/attachments",
        files={"file": ("signed-terms.pdf", b"%PDF-1.4 signed", "application/pdf")},
        data={"audience": audience},
        headers=_auth_headers(club),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# ── Consent recorded by the buying club ──────────────────────────────────────


@pytest.mark.asyncio
async def test_buying_club_records_consent_for_unrepresented_player(client, buyer, seller, db):
    deal_id = await _deal_at_personal_terms(client, buyer, seller, db)
    await _propose_terms(client, buyer, deal_id)
    evidence_id = await _upload(client, buyer, deal_id)

    resp = await client.post(
        f"/deals/{deal_id}/personal-terms/player-consent",
        json={"agreement": "AGREED", "evidence_attachment_id": evidence_id},
        headers=_auth_headers(buyer),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["player_consent"] == "AGREED"
    assert resp.json()["consent_evidence_attachment_id"] == evidence_id

    # Audited as the club's record, not the player's own consent, with the
    # signed terms it rests on.
    events = await _audit(db, deal_id, "PERSONAL_TERMS_CONSENT")
    assert events and events[-1].payload_json["recorded_by"] == "BUYING_CLUB"
    assert events[-1].payload_json["evidence_attachment_id"] == evidence_id

    advanced = await client.post(f"/deals/{deal_id}/advance", headers=_auth_headers(buyer))
    assert advanced.status_code == 200, advanced.text
    assert advanced.json()["stage"] == "PAPERWORK"


@pytest.mark.asyncio
async def test_recording_agreement_needs_the_buyers_signed_terms(client, buyer, seller, db):
    deal_id = await _deal_at_personal_terms(client, buyer, seller, db)
    await _propose_terms(client, buyer, deal_id)
    url = f"/deals/{deal_id}/personal-terms/player-consent"

    # No document: refused.
    resp = await client.post(url, json={"agreement": "AGREED"}, headers=_auth_headers(buyer))
    assert resp.status_code == 400
    assert "signed terms" in resp.json()["detail"]

    # A document the selling club uploaded is not the buyer's evidence.
    theirs = await _upload(client, seller, deal_id, audience="SHARED")
    resp = await client.post(
        url, json={"agreement": "AGREED", "evidence_attachment_id": theirs}, headers=_auth_headers(buyer)
    )
    assert resp.status_code == 400

    # Recording a decline needs no document (it ends the deal).
    resp = await client.post(url, json={"agreement": "DECLINED"}, headers=_auth_headers(buyer))
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_new_terms_clear_the_signed_copy(client, buyer, seller, db):
    from app.deals.models import PersonalTerms

    deal_id = await _deal_at_personal_terms(client, buyer, seller, db)
    await _propose_terms(client, buyer, deal_id)
    evidence_id = await _upload(client, buyer, deal_id)
    await client.post(
        f"/deals/{deal_id}/personal-terms/player-consent",
        json={"agreement": "AGREED", "evidence_attachment_id": evidence_id}, headers=_auth_headers(buyer),
    )
    await client.put(f"/deals/{deal_id}/personal-terms", json={"wage_weekly": 55000}, headers=_auth_headers(buyer))
    pt = (await client.get(f"/deals/{deal_id}/personal-terms", headers=_auth_headers(buyer))).json()
    assert pt["player_consent"] == "PENDING"
    assert pt["consent_evidence_attachment_id"] is None


@pytest.mark.asyncio
async def test_seller_and_third_club_cannot_record_consent(client, buyer, seller, rival, db):
    deal_id = await _deal_at_personal_terms(client, buyer, seller, db)
    await _propose_terms(client, buyer, deal_id)
    for club in (seller, rival):
        resp = await client.post(
            f"/deals/{deal_id}/personal-terms/player-consent", json={"agreement": "AGREED"},
            headers=_auth_headers(club),
        )
        assert resp.status_code in (403, 404), resp.text
    deal = (await client.get(f"/deals/{deal_id}", headers=_auth_headers(buyer))).json()
    assert deal["personal_terms"]["player_consent"] == "PENDING"


@pytest.mark.asyncio
async def test_cannot_advance_before_consent(client, buyer, seller, db):
    deal_id = await _deal_at_personal_terms(client, buyer, seller, db)
    await _propose_terms(client, buyer, deal_id)
    resp = await client.post(f"/deals/{deal_id}/advance", headers=_auth_headers(buyer))
    assert resp.status_code == 400
    assert "consent" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_collapsed_deal_refuses_terms_and_consent(client, buyer, seller, db):
    """Regression: a collapsed deal keeps its stage, and the stage check alone
    let terms be proposed and consented to after it fell through."""
    deal_id = await _deal_at_personal_terms(client, buyer, seller, db)
    await _propose_terms(client, buyer, deal_id)
    collapse = await client.post(f"/deals/{deal_id}/collapse", headers=_auth_headers(seller))
    assert collapse.status_code == 200, collapse.text

    terms = await client.put(
        f"/deals/{deal_id}/personal-terms", json={"wage_weekly": 60000}, headers=_auth_headers(buyer)
    )
    assert terms.status_code == 400
    # DECLINED needs no document, so the refusal can only be the collapse.
    consent = await client.post(
        f"/deals/{deal_id}/personal-terms/player-consent", json={"agreement": "DECLINED"},
        headers=_auth_headers(buyer),
    )
    assert consent.status_code == 400
    assert "no longer in progress" in consent.json()["detail"]
