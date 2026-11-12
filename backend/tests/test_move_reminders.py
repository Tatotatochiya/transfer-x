"""Move reminders (docs/feature_spec/move-reminders)."""
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.models import AuditEvent
from app.deals.models import Deal, DealStage, DealStatus
from app.notifications.models import Notification, NotificationType
from app.offers.models import OfferEvent
from app.players.models import Player
from app.reminders.models import MoveReminder
from tests.conftest import _auth_headers, _register
from tests.test_deals import _create_player_for_seller, _get_club_id, _give_budget

pytestmark = pytest.mark.asyncio

NOW = datetime.now(timezone.utc)


async def _register_agent(client: AsyncClient, email: str, name: str = "Sofia Reyes") -> dict:
    resp = await client.post("/auth/register", json={
        "email": email, "password": "password123", "user_type": "AGENT",
        "display_name": name, "agency_name": "Agency", "country": "England",
    })
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _user_id(client: AsyncClient, tokens: dict) -> uuid.UUID:
    return uuid.UUID((await client.get("/auth/me", headers=_auth_headers(tokens))).json()["id"])


async def _agent_deal(client: AsyncClient, db: AsyncSession, *, idle: timedelta) -> dict:
    """Tottenham buying L. Hall from Newcastle, waiting on the agent's commission."""
    buyer = await _register(client, "spurs@rem.com", club_name="Tottenham")
    seller = await _register(client, "toon@rem.com", club_name="Newcastle")
    agent = await _register_agent(client, "sofia@rem.com")
    profile = (await client.get("/agents/me", headers=_auth_headers(agent))).json()
    player = Player(name="L. Hall", position="DEF")
    db.add(player)
    await db.commit()
    deal = Deal(
        buyer_club_id=uuid.UUID(await _get_club_id(client, _auth_headers(buyer))),
        seller_club_id=uuid.UUID(await _get_club_id(client, _auth_headers(seller))),
        player_id=player.id, agreed_fee=Decimal("34500000"),
        status=DealStatus.IN_PROGRESS, stage=DealStage.AGENT_NEGOTIATION,
        commission_agent_id=uuid.UUID(profile["id"]),
    )
    db.add(deal)
    await db.commit()
    await _idle(db, deal.id, idle)
    return {"deal": deal, "player": player, "buyer": buyer, "seller": seller, "agent": agent}


async def _idle(db: AsyncSession, deal_id, idle: timedelta) -> None:
    await db.execute(update(Deal).where(Deal.id == deal_id).values(updated_at=NOW - idle))
    await db.commit()


async def _notes(db: AsyncSession, user_id) -> list[Notification]:
    return list((await db.execute(
        select(Notification).where(Notification.recipient_user_id == user_id,
                                   Notification.type.in_([NotificationType.MOVE_REMINDER, NotificationType.MOVE_ESCALATED]))
    )).scalars())


# ── Deals ─────────────────────────────────────────────────────────────────────

async def test_not_before_a_day_of_waiting(client, db):
    ctx = await _agent_deal(client, db, idle=timedelta(hours=3))
    st = (await client.get(f"/reminders/deal/{ctx['deal'].id}", headers=_auth_headers(ctx["buyer"]))).json()
    assert st["holder"] == {"kind": "agent", "name": "Sofia Reyes"}
    assert st["can_send"] is False
    assert st["reason"].startswith("You can send a reminder from")


async def test_the_buyer_reminds_the_agent(client, db):
    ctx = await _agent_deal(client, db, idle=timedelta(days=3))
    url = f"/reminders/deal/{ctx['deal'].id}"
    st = (await client.get(url, headers=_auth_headers(ctx["buyer"]))).json()
    assert st["can_send"] is True and st["would_escalate"] is False
    assert st["preview"] == "Tottenham is waiting for your commission proposal for L. Hall (£34.5M) · 3 days"

    resp = await client.post(url, json={"note": "We need this by Friday"}, headers=_auth_headers(ctx["buyer"]))
    assert resp.status_code == 200, resp.text
    after = resp.json()
    assert after["can_send"] is False and "You reminded them" in after["reason"]
    assert after["last"]["by"] == "Tottenham" and after["last"]["by_you"] is True
    assert after["last"]["note"] == "We need this by Friday"
    agent_view = (await client.get(url, headers=_auth_headers(ctx["agent"]))).json()
    assert agent_view["last"]["by"] == "Tottenham" and agent_view["last"]["by_you"] is False

    told = await _notes(db, await _user_id(client, ctx["agent"]))
    assert len(told) == 1 and told[0].type == NotificationType.MOVE_REMINDER
    assert told[0].link == f"/deals/{ctx['deal'].id}"
    assert "“We need this by Friday”" in (told[0].body or "")

    event = (await db.execute(select(AuditEvent).where(AuditEvent.entity_id == ctx["deal"].id))).scalars().one()
    assert event.entity_type == "DEAL" and event.action == "MOVE_REMINDER"
    assert event.description == "Tottenham sent a reminder to Sofia Reyes: “We need this by Friday”"

    again = await client.post(url, json={}, headers=_auth_headers(ctx["buyer"]))
    assert again.status_code == 409 and "You reminded them" in again.json()["detail"]


async def test_the_holder_cant_remind_themselves(client, db):
    ctx = await _agent_deal(client, db, idle=timedelta(days=3))
    st = (await client.get(f"/reminders/deal/{ctx['deal'].id}", headers=_auth_headers(ctx["agent"]))).json()
    assert st["can_send"] is False and st["reason"] == "It's your move."


async def test_a_non_party_gets_404(client, db):
    ctx = await _agent_deal(client, db, idle=timedelta(days=3))
    outsider = await _register(client, "nosy@rem.com", club_name="Nosy FC")
    resp = await client.get(f"/reminders/deal/{ctx['deal'].id}", headers=_auth_headers(outsider))
    assert resp.status_code == 404
    resp = await client.post(f"/reminders/deal/{ctx['deal'].id}", json={}, headers=_auth_headers(outsider))
    assert resp.status_code == 404


async def test_the_third_reminder_escalates_to_the_player_and_the_other_club(client, db):
    ctx = await _agent_deal(client, db, idle=timedelta(days=4))
    deal = ctx["deal"]
    # Two earlier reminders the agent ignored (TransferX's, since the deal last moved).
    for hours in (60, 30):
        db.add(MoveReminder(subject_type="deal", subject_id=deal.id, move_key="deal:AGENT_NEGOTIATION:propose-commission",
                            holder_kind="agent", holder_id=deal.commission_agent_id, automatic=True,
                            created_at=NOW - timedelta(hours=hours)))
    await db.commit()
    player_account = await client.post("/auth/register", json={
        "email": "hall@rem.com", "password": "password123", "user_type": "PLAYER", "player_id": str(ctx["player"].id),
    })
    assert player_account.status_code == 201, player_account.text

    url = f"/reminders/deal/{deal.id}"
    assert (await client.get(url, headers=_auth_headers(ctx["buyer"]))).json()["would_escalate"] is True
    assert (await client.post(url, json={}, headers=_auth_headers(ctx["buyer"]))).status_code == 200

    agent_notes = await _notes(db, await _user_id(client, ctx["agent"]))
    assert [n.type for n in agent_notes] == [NotificationType.MOVE_ESCALATED]
    assert agent_notes[0].body == "This is reminder number 3."
    player_notes = await _notes(db, await _user_id(client, player_account.json()))
    assert len(player_notes) == 1 and "waiting on Sofia Reyes" in player_notes[0].message
    assert len(await _notes(db, await _user_id(client, ctx["seller"]))) == 1
    # The club that escalated isn't told about its own escalation.
    assert await _notes(db, await _user_id(client, ctx["buyer"])) == []


async def test_a_week_of_waiting_escalates(client, db):
    ctx = await _agent_deal(client, db, idle=timedelta(days=8))
    st = (await client.get(f"/reminders/deal/{ctx['deal'].id}", headers=_auth_headers(ctx["buyer"]))).json()
    assert st["can_send"] is True and st["would_escalate"] is True


async def test_a_movement_resets_the_cooldown(client, db):
    ctx = await _agent_deal(client, db, idle=timedelta(days=3))
    url = f"/reminders/deal/{ctx['deal'].id}"
    assert (await client.post(url, json={}, headers=_auth_headers(ctx["buyer"]))).status_code == 200
    # The reminder went out two days ago; the deal moved since (a day ago) and
    # is waiting on the agent again.
    await db.execute(update(MoveReminder).values(created_at=NOW - timedelta(days=2)))
    await _idle(db, ctx["deal"].id, timedelta(hours=25))
    st = (await client.get(url, headers=_auth_headers(ctx["buyer"]))).json()
    assert st["can_send"] is True and st["would_escalate"] is False


# ── Offers ────────────────────────────────────────────────────────────────────

async def _offer(client, db, *, anonymous: bool = False, idle: timedelta = timedelta(days=2)):
    buyer = await _register(client, "chelsea@rem.com", club_name="Chelsea")
    seller = await _register(client, "city@rem.com", club_name="Man City")
    await _give_budget(db)
    player = await _create_player_for_seller(client, _auth_headers(seller))
    resp = await client.post("/offers", json={
        "player_id": player["id"], "to_club_id": await _get_club_id(client, _auth_headers(seller)),
        "fee_amount": 30_000_000, "is_anonymous": anonymous,
    }, headers=_auth_headers(buyer))
    assert resp.status_code == 201, resp.text
    offer = resp.json()
    await db.execute(update(OfferEvent).where(OfferEvent.offer_id == uuid.UUID(offer["id"]))
                     .values(created_at=NOW - idle))
    await db.commit()
    return offer, buyer, seller


async def test_the_buyer_reminds_the_selling_club(client, db):
    offer, buyer, seller = await _offer(client, db)
    url = f"/reminders/offer/{offer['id']}"
    st = (await client.get(url, headers=_auth_headers(buyer))).json()
    assert st["holder"] == {"kind": "club", "name": "Man City"}
    assert st["preview"].startswith("Chelsea is waiting for an answer to the offer for")
    assert (await client.get(url, headers=_auth_headers(seller))).json()["reason"] == "It's your move."
    assert (await client.post(url, json={}, headers=_auth_headers(buyer))).status_code == 200
    told = await _notes(db, await _user_id(client, seller))
    assert len(told) == 1 and "(£30M)" in told[0].message


async def test_an_anonymous_buyer_stays_anonymous_in_the_reminder(client, db):
    offer, buyer, seller = await _offer(client, db, anonymous=True)
    assert (await client.post(f"/reminders/offer/{offer['id']}", json={}, headers=_auth_headers(buyer))).status_code == 200
    told = await _notes(db, await _user_id(client, seller))
    assert len(told) == 1 and "Chelsea" not in told[0].message
    assert told[0].message.startswith("An undisclosed club is waiting for")


# ── Automatic ─────────────────────────────────────────────────────────────────

async def test_automatic_reminders_at_three_and_seven_days(client, db):
    from app.reminders.service import send_automatic

    ctx = await _agent_deal(client, db, idle=timedelta(days=2))
    agent_user = await _user_id(client, ctx["agent"])
    assert await send_automatic(db) == 0

    await _idle(db, ctx["deal"].id, timedelta(days=3, hours=1))
    assert await send_automatic(db) == 1
    await db.commit()
    assert await send_automatic(db) == 0  # once per threshold
    notes = await _notes(db, agent_user)
    assert len(notes) == 1 and notes[0].message.startswith("Tottenham is waiting for your commission proposal")

    await _idle(db, ctx["deal"].id, timedelta(days=7, hours=1))
    # The 3-day reminder was sent "now"; the clock reads from the deal's last movement.
    await db.execute(update(MoveReminder).values(created_at=NOW - timedelta(days=4)))
    await db.commit()
    assert await send_automatic(db) == 1
    await db.commit()
    kinds = [n.type for n in await _notes(db, agent_user)]
    assert NotificationType.MOVE_ESCALATED in kinds


async def test_abandoned_transactions_arent_chased(client, db):
    from app.reminders.service import send_automatic

    await _agent_deal(client, db, idle=timedelta(days=45))
    assert await send_automatic(db) == 0


# ── Who holds the move, by row ────────────────────────────────────────────────

async def _holders_for(db, deal_id):
    from app.reminders.service import holders, load_subject

    db.expire_all()
    return await holders(db, await load_subject(db, "deal", deal_id))


async def test_personal_terms_holders(client, db):
    from app.agents.models import AgreementStatus
    from app.deals.models import PersonalTerms

    ctx = await _agent_deal(client, db, idle=timedelta(days=3))
    deal = ctx["deal"]
    deal.stage, deal.commission_agent_id = DealStage.PERSONAL_TERMS, None
    await db.commit()
    # No terms yet, no agent: the buying club proposes them.
    [h] = await _holders_for(db, deal.id)
    assert (h.kind, h.name, h.what) == ("club", "Tottenham", "personal terms for L. Hall")

    db.add(PersonalTerms(deal_id=deal.id, wage_weekly=Decimal("90000"), length_years=4,
                         player_consent=AgreementStatus.PENDING))
    await db.commit()
    # Proposed, the player has no account and no agent: the buying club records his answer.
    [h] = await _holders_for(db, deal.id)
    assert (h.kind, h.move_key) == ("club", "deal:PERSONAL_TERMS:record")

    await client.post("/auth/register", json={
        "email": "hall2@rem.com", "password": "password123", "user_type": "PLAYER", "player_id": str(ctx["player"].id),
    })
    [h] = await _holders_for(db, deal.id)
    assert (h.kind, h.what) == ("player", "your answer to the personal terms")


async def test_paperwork_holds_only_the_side_with_steps_left(client, db):
    from app.deals import service as deals_service

    ctx = await _agent_deal(client, db, idle=timedelta(days=3))
    deal = ctx["deal"]
    deal.stage = DealStage.PAPERWORK
    await db.commit()
    hs = await _holders_for(db, deal.id)
    expected = {c for c in (deal.buyer_club_id, deal.seller_club_id) if deals_service.outstanding_paperwork_for(deal, c)}
    assert {h.id for h in hs} == expected and all(h.kind == "club" for h in hs)
