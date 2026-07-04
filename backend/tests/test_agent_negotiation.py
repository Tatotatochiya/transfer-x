"""TRA-127 — agent negotiation authorization regression tests.

Proves that only the agent actually invited to a deal (via the
AgentDealInvitation created when the deal entered AGENT_NEGOTIATION) can
create that deal's AgentNegotiation record — not just any agent on the
platform who happens to write to it first.
"""

import uuid as _uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.models import AgentDealInvitation
from app.deals.models import Deal, DealStage, DealStatus
from app.players.models import Player

pytestmark = pytest.mark.asyncio


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _register_club(client: AsyncClient, email: str) -> dict:
    resp = await client.post("/auth/register", json={"email": email, "password": "password123"})
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _register_agent(client: AsyncClient, email: str) -> dict:
    resp = await client.post("/auth/register", json={
        "email": email, "password": "password123",
        "user_type": "AGENT",
        "display_name": "Test Agent", "agency_name": "Agency", "country": "England",
    })
    assert resp.status_code == 201, resp.text
    return resp.json()


def _headers(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _setup_invited_deal(client: AsyncClient, db: AsyncSession) -> dict:
    """Deal in AGENT_NEGOTIATION with an invitation for one specific agent, and
    no AgentNegotiation record yet — the exact state where TRA-127 lived: the
    first write to the (currently nonexistent) negotiation record is what used
    to be unguarded.
    """
    buyer_tokens = await _register_club(client, "buyer@negterms.com")
    seller_tokens = await _register_club(client, "seller@negterms.com")
    invited_agent_tokens = await _register_agent(client, "invited@negterms.com")

    buyer_id = (await client.get("/clubs/me", headers=_headers(buyer_tokens))).json()["id"]
    seller_id = (await client.get("/clubs/me", headers=_headers(seller_tokens))).json()["id"]
    invited_agent_profile = (await client.get("/agents/me", headers=_headers(invited_agent_tokens))).json()

    player = Player(name="Negotiation Terms Player", position="MID")
    db.add(player)
    await db.commit()

    deal = Deal(
        buyer_club_id=_uuid.UUID(buyer_id),
        seller_club_id=_uuid.UUID(seller_id),
        player_id=player.id,
        agreed_fee=Decimal("8000000"),
        status=DealStatus.IN_PROGRESS,
        stage=DealStage.AGENT_NEGOTIATION,
    )
    db.add(deal)
    await db.flush()

    invitation = AgentDealInvitation(deal_id=deal.id, agent_id=_uuid.UUID(invited_agent_profile["id"]))
    db.add(invitation)
    await db.commit()

    return {
        "deal_id": str(deal.id),
        "player_id": str(player.id),
        "buyer": buyer_tokens,
        "invited_agent": invited_agent_tokens,
    }


async def _register_player_account(client: AsyncClient, email: str, player_id: str) -> dict:
    resp = await client.post("/auth/register", json={
        "email": email, "password": "password123",
        "user_type": "PLAYER", "player_id": player_id,
    })
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── Tests ─────────────────────────────────────────────────────────────────────


async def test_invited_agent_can_start_negotiation(client: AsyncClient, db: AsyncSession):
    ctx = await _setup_invited_deal(client, db)

    resp = await client.patch(
        f"/deals/{ctx['deal_id']}/agent-negotiation/terms",
        json={"commission_pct": 0.05, "commission_payer": "BUYER"},
        headers=_headers(ctx["invited_agent"]),
    )
    assert resp.status_code == 200, resp.text
    assert Decimal(resp.json()["commission_pct"]) == Decimal("0.05")


async def test_uninvited_agent_cannot_start_negotiation(client: AsyncClient, db: AsyncSession):
    """TRA-127 regression: an agent with no invitation to this deal must not be
    able to insert themselves as its negotiator by writing to it first."""
    ctx = await _setup_invited_deal(client, db)
    rival_agent = await _register_agent(client, "rival@negterms.com")

    resp = await client.patch(
        f"/deals/{ctx['deal_id']}/agent-negotiation/terms",
        json={"commission_pct": 0.10, "commission_payer": "BUYER"},
        headers=_headers(rival_agent),
    )
    assert resp.status_code == 400
    assert "invited" in resp.json()["detail"].lower()


async def test_uninvited_agent_write_does_not_create_a_negotiation_record(
    client: AsyncClient, db: AsyncSession,
):
    """The rejected write must not leave a half-created record behind — the
    invited agent should still see no negotiation exists yet afterwards."""
    ctx = await _setup_invited_deal(client, db)
    rival_agent = await _register_agent(client, "rival-noop@negterms.com")

    await client.patch(
        f"/deals/{ctx['deal_id']}/agent-negotiation/terms",
        json={"commission_pct": 0.10},
        headers=_headers(rival_agent),
    )

    resp = await client.get(
        f"/deals/{ctx['deal_id']}/agent-negotiation", headers=_headers(ctx["invited_agent"]),
    )
    assert resp.status_code == 404


async def test_second_agent_cannot_hijack_existing_negotiation(client: AsyncClient, db: AsyncSession):
    """Once the invited agent has created the negotiation, a different agent
    still cannot take it over on a later write (the pre-existing guard for
    updates — confirmed still correct alongside the new create-time guard)."""
    ctx = await _setup_invited_deal(client, db)

    first = await client.patch(
        f"/deals/{ctx['deal_id']}/agent-negotiation/terms",
        json={"commission_pct": 0.05},
        headers=_headers(ctx["invited_agent"]),
    )
    assert first.status_code == 200, first.text

    rival_agent = await _register_agent(client, "rival2@negterms.com")
    resp = await client.patch(
        f"/deals/{ctx['deal_id']}/agent-negotiation/terms",
        json={"commission_pct": 0.20},
        headers=_headers(rival_agent),
    )
    assert resp.status_code == 400
    assert "mandated" in resp.json()["detail"].lower()


async def test_invited_agent_can_view_deal_before_starting_negotiation(client: AsyncClient, db: AsyncSession):
    """Regression: an invited agent must be able to open the deal room before
    their first negotiation-terms write creates the AgentNegotiation record —
    otherwise they can never reach the UI that makes that write (deadlock)."""
    ctx = await _setup_invited_deal(client, db)

    resp = await client.get(f"/deals/{ctx['deal_id']}", headers=_headers(ctx["invited_agent"]))
    assert resp.status_code == 200, resp.text
    assert resp.json()["id"] == ctx["deal_id"]


async def test_negotiating_agent_can_view_deal_detail(client: AsyncClient, db: AsyncSession):
    """TRA-137: the agent workspace (TRA-128) reads the deal via GET /deals/{id}
    — it must not 403 an agent legitimately negotiating this deal."""
    ctx = await _setup_invited_deal(client, db)
    await client.patch(
        f"/deals/{ctx['deal_id']}/agent-negotiation/terms",
        json={"commission_pct": 0.05},
        headers=_headers(ctx["invited_agent"]),
    )

    resp = await client.get(f"/deals/{ctx['deal_id']}", headers=_headers(ctx["invited_agent"]))
    assert resp.status_code == 200, resp.text
    assert resp.json()["id"] == ctx["deal_id"]


async def test_uninvited_agent_cannot_view_deal_detail(client: AsyncClient, db: AsyncSession):
    """TRA-137: a non-participant gets 403, not a misleading 404."""
    ctx = await _setup_invited_deal(client, db)
    rival_agent = await _register_agent(client, "rival-view@negterms.com")

    resp = await client.get(f"/deals/{ctx['deal_id']}", headers=_headers(rival_agent))
    assert resp.status_code == 403


# ── Agent-triggered advance ─────────────────────────────────────────────────────


async def _advance_to_personal_terms(client: AsyncClient, ctx: dict) -> None:
    """Negotiate commission to AGREED and advance — leaves the deal at
    PERSONAL_TERMS with no PersonalTerms record yet. Personal terms (wage,
    signing bonus, length) are captured once, at that stage — not here."""
    await client.patch(
        f"/deals/{ctx['deal_id']}/agent-negotiation/terms",
        json={"commission_pct": 0.05, "commission_payer": "BUYER"},
        headers=_headers(ctx["invited_agent"]),
    )
    await client.post(
        f"/deals/{ctx['deal_id']}/agent-negotiation/club-respond",
        json={"agreement": "AGREED"},
        headers=_headers(ctx["buyer"]),
    )
    resp = await client.post(
        f"/deals/{ctx['deal_id']}/advance", headers=_headers(ctx["invited_agent"]),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["stage"] == "PERSONAL_TERMS"


async def test_mandated_agent_can_advance_once_club_agreed(client: AsyncClient, db: AsyncSession):
    """Regression: the agent's own 'Advance to Personal Terms' button used to
    500 with 'No club profile' — advance_deal was club-only even though the
    whole AGENT_NEGOTIATION stage is agent-run."""
    ctx = await _setup_invited_deal(client, db)
    await _advance_to_personal_terms(client, ctx)


async def test_uninvited_agent_cannot_advance(client: AsyncClient, db: AsyncSession):
    """A non-mandated agent must not be able to push the deal forward."""
    ctx = await _setup_invited_deal(client, db)
    await client.patch(
        f"/deals/{ctx['deal_id']}/agent-negotiation/terms",
        json={"commission_pct": 0.05},
        headers=_headers(ctx["invited_agent"]),
    )
    rival_agent = await _register_agent(client, "rival-advance@negterms.com")

    resp = await client.post(
        f"/deals/{ctx['deal_id']}/advance", headers=_headers(rival_agent),
    )
    assert resp.status_code == 403


async def test_mandated_agent_cannot_advance_before_club_agreed(client: AsyncClient, db: AsyncSession):
    """The looser party-check for agents must not weaken the existing
    club-must-agree-first business rule."""
    ctx = await _setup_invited_deal(client, db)
    await client.patch(
        f"/deals/{ctx['deal_id']}/agent-negotiation/terms",
        json={"commission_pct": 0.05},
        headers=_headers(ctx["invited_agent"]),
    )

    resp = await client.post(
        f"/deals/{ctx['deal_id']}/advance", headers=_headers(ctx["invited_agent"]),
    )
    assert resp.status_code == 400
    assert "not yet agreed" in resp.json()["detail"].lower()


# ── Set personal terms (mandated-agent ownership) ───────────────────────────────


async def test_mandated_agent_can_set_personal_terms(client: AsyncClient, db: AsyncSession):
    ctx = await _setup_invited_deal(client, db)
    await _advance_to_personal_terms(client, ctx)

    resp = await client.put(
        f"/deals/{ctx['deal_id']}/personal-terms",
        json={"wage_weekly": 55000, "signing_bonus": 5000000, "length_years": 5},
        headers=_headers(ctx["invited_agent"]),
    )
    assert resp.status_code == 200, resp.text
    assert Decimal(resp.json()["wage_weekly"]) == Decimal("55000")


async def test_uninvited_agent_cannot_set_personal_terms(client: AsyncClient, db: AsyncSession):
    """Regression: set_personal_terms accepted a request from ANY agent, not
    just the deal's mandated one — a rival agent could hijack or reset another
    deal's personal terms (and the consent it resets)."""
    ctx = await _setup_invited_deal(client, db)
    await _advance_to_personal_terms(client, ctx)
    rival_agent = await _register_agent(client, "rival-terms@negterms.com")

    resp = await client.put(
        f"/deals/{ctx['deal_id']}/personal-terms",
        json={"wage_weekly": 999999, "length_years": 1},
        headers=_headers(rival_agent),
    )
    assert resp.status_code == 403
    assert "mandated agent" in resp.json()["detail"].lower()


# ── Personal terms consent (mandated-agent proxy) ───────────────────────────────


async def test_mandated_agent_can_consent_for_player_with_no_account(client: AsyncClient, db: AsyncSession):
    """A player who hasn't registered an account has no other way to consent —
    the mandated agent may act as their proxy, same rule as commission."""
    ctx = await _setup_invited_deal(client, db)
    await _advance_to_personal_terms(client, ctx)
    await client.put(
        f"/deals/{ctx['deal_id']}/personal-terms",
        json={"wage_weekly": 55000, "length_years": 5},
        headers=_headers(ctx["invited_agent"]),
    )

    resp = await client.post(
        f"/deals/{ctx['deal_id']}/personal-terms/player-consent",
        json={"agreement": "AGREED"},
        headers=_headers(ctx["invited_agent"]),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["player_consent"] == "AGREED"
    assert resp.json()["player_has_account"] is False


async def test_mandated_agent_cannot_consent_for_player_with_an_account(client: AsyncClient, db: AsyncSession):
    """Once the player has their own account, the proxy escape hatch closes —
    they must consent themselves, matching the frontend's actual behaviour."""
    ctx = await _setup_invited_deal(client, db)
    await _register_player_account(client, "player-with-account-pt@negterms.com", ctx["player_id"])
    await _advance_to_personal_terms(client, ctx)
    await client.put(
        f"/deals/{ctx['deal_id']}/personal-terms",
        json={"wage_weekly": 55000, "length_years": 5},
        headers=_headers(ctx["invited_agent"]),
    )

    resp = await client.post(
        f"/deals/{ctx['deal_id']}/personal-terms/player-consent",
        json={"agreement": "AGREED"},
        headers=_headers(ctx["invited_agent"]),
    )
    assert resp.status_code == 403
    assert "must respond themselves" in resp.json()["detail"].lower()


# ── Agent dashboard invitations vs. deal lifecycle ──────────────────────────────


async def test_invitation_disappears_once_deal_collapses(client: AsyncClient, db: AsyncSession):
    """Regression: list_invitations only filtered on the invitation's own
    status (always PENDING — no accept/decline flow exists yet, TRA-145), never
    the deal's — so a collapsed or completed deal's invitation stuck around on
    the agent dashboard's 'action required' banner forever."""
    from sqlalchemy import select

    ctx = await _setup_invited_deal(client, db)

    resp = await client.get("/agents/me/invitations", headers=_headers(ctx["invited_agent"]))
    assert resp.status_code == 200
    assert any(inv["deal_id"] == ctx["deal_id"] for inv in resp.json())

    deal_result = await db.execute(select(Deal).where(Deal.id == _uuid.UUID(ctx["deal_id"])))
    deal = deal_result.scalar_one()
    deal.status = DealStatus.COLLAPSED
    await db.commit()

    resp = await client.get("/agents/me/invitations", headers=_headers(ctx["invited_agent"]))
    assert resp.status_code == 200
    assert not any(inv["deal_id"] == ctx["deal_id"] for inv in resp.json())


# ── Commission auto-derivation ──────────────────────────────────────────────────


async def test_commission_amount_auto_derives_from_percentage(client: AsyncClient, db: AsyncSession):
    """Regression: commission is naturally negotiated as a percentage, but
    create_commission_from_negotiation only fires when commission_amount is
    set — an agent who only entered a percentage got no AgentCommission
    record at all, ever, for the whole deal."""
    from app.agents.models import AgentCommission, CommissionStatus
    from sqlalchemy import select

    ctx = await _setup_invited_deal(client, db)

    resp = await client.patch(
        f"/deals/{ctx['deal_id']}/agent-negotiation/terms",
        json={"commission_pct": 0.02, "commission_payer": "BUYER"},
        headers=_headers(ctx["invited_agent"]),
    )
    assert resp.status_code == 200, resp.text
    # _setup_invited_deal's agreed_fee is 8,000,000 — 2% of that is 160,000.
    assert Decimal(resp.json()["commission_amount"]) == Decimal("160000.00")

    await client.post(
        f"/deals/{ctx['deal_id']}/agent-negotiation/club-respond",
        json={"agreement": "AGREED"},
        headers=_headers(ctx["buyer"]),
    )
    resp = await client.post(f"/deals/{ctx['deal_id']}/advance", headers=_headers(ctx["invited_agent"]))
    assert resp.status_code == 200, resp.text
    assert resp.json()["stage"] == "PERSONAL_TERMS"
    assert Decimal(resp.json()["agent_commission_amount"]) == Decimal("160000.00")

    comm_result = await db.execute(
        select(AgentCommission).where(AgentCommission.deal_id == _uuid.UUID(ctx["deal_id"]))
    )
    commission = comm_result.scalar_one_or_none()
    assert commission is not None
    assert commission.amount == Decimal("160000.00")
    assert commission.status == CommissionStatus.PENDING


# ── Audit trail coverage ─────────────────────────────────────────────────────────


async def test_negotiation_and_consent_actions_are_audited(client: AsyncClient, db: AsyncSession):
    """Sanity check that the audit trail actually covers the negotiation and
    stage-advance actions added this session, not just the pre-existing
    DEAL_CREATED/DEAL_COMPLETED/DEAL_COLLAPSED events."""
    ctx = await _setup_invited_deal(client, db)
    await _advance_to_personal_terms(client, ctx)

    resp = await client.get(f"/deals/{ctx['deal_id']}/audit-log", headers=_headers(ctx["invited_agent"]))
    assert resp.status_code == 200
    events = resp.json()
    actions = {e["action"] for e in events}
    assert "NEGOTIATION_TERMS_UPDATED" in actions
    assert "NEGOTIATION_CLUB_RESPONDED" in actions
    assert "STAGE_ADVANCED" in actions

    # The agent's own PATCH should be attributed to the agent, not left blank.
    terms_event = next(e for e in events if e["action"] == "NEGOTIATION_TERMS_UPDATED")
    assert terms_event["actor_user_id"] is not None
    assert terms_event["actor_label"] is not None
