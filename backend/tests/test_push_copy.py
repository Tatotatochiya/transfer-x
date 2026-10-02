"""Mobile notifications, phase 3 (docs/feature_spec/mobile-notifications §3.2):
what a push says, the shared rule for naming an anonymous buyer, and
deadlines written in each recipient's timezone."""
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.common.masking import buyer_is_masked, buyer_name, masked_name
from app.notifications.copy import DEADLINE, TIME_LEFT, TIME_REMAINING, money, render
from app.notifications.models import Notification, NotificationType
from tests.conftest import _auth_headers, _register
from tests.test_deals import _create_player_for_seller, _get_club_id, _give_budget

LONDON = ZoneInfo("Europe/London")
NOW = datetime(2026, 10, 2, 9, 0, tzinfo=timezone.utc)  # a Friday


# ── Money and deadlines ───────────────────────────────────────────────────────


@pytest.mark.parametrize("value, text", [
    (18_000_000, "£18m"), (19_500_000, "£19.5m"), (6_750_000, "£6.8m"), (850_000, "£850k"),
    (Decimal("1200000.00"), "£1.2m"), (900, "£900"),
])
def test_money(value, text):
    assert money(value) == text


def test_deadlines_are_written_in_the_recipients_timezone():
    friday_6pm_london = datetime(2026, 10, 2, 17, 0, tzinfo=timezone.utc)
    assert render(f"reply by {DEADLINE}", friday_6pm_london, LONDON, NOW) == "reply by today 18:00"
    # The same moment is already Saturday in Singapore, where it is also Friday 17:00 now.
    assert render(f"reply by {DEADLINE}", friday_6pm_london, ZoneInfo("Asia/Singapore"), NOW) == "reply by tomorrow 01:00"
    assert render(f"by {DEADLINE}", NOW + timedelta(days=3), LONDON, NOW) == "by Mon 10:00"
    # A week out is the date, not "Fri", which on a Friday reads as tonight.
    assert render(f"by {DEADLINE}", NOW + timedelta(days=7), LONDON, NOW) == "by 9 Oct"
    assert render(f"by {DEADLINE}", NOW + timedelta(days=12), LONDON, NOW) == "by 14 Oct"


@pytest.mark.parametrize("delta, left", [
    (timedelta(minutes=47), "47 minutes left"), (timedelta(hours=1, minutes=5), "1 hour left"),
    (timedelta(hours=5), "5 hours left"), (timedelta(days=2, hours=3), "2 days left"), (timedelta(minutes=-5), "no time left"),
])
def test_time_left(delta, left):
    assert render(TIME_LEFT, NOW + delta, LONDON, NOW) == left
    assert render(f"ends in {TIME_REMAINING}", NOW + delta, LONDON, NOW) == "ends in " + left.removesuffix(" left")


def test_text_without_tokens_is_untouched():
    assert render("Plain message {not a token}", None, LONDON, NOW) == "Plain message {not a token}"
    assert render(None, NOW, LONDON, NOW) is None


# ── The masking rule ──────────────────────────────────────────────────────────


def _offer(anonymous=True, status="SENT"):
    from app.offers.models import OfferStatus
    buyer_id = uuid.uuid4()
    return SimpleNamespace(is_anonymous=anonymous, status=OfferStatus(status), from_club_id=buyer_id), buyer_id


def test_an_anonymous_buyer_is_hidden_from_everyone_but_itself_until_accepted():
    offer, buyer_id = _offer()
    assert buyer_is_masked(offer, uuid.uuid4())
    assert buyer_is_masked(offer, None)
    assert not buyer_is_masked(offer, buyer_id)
    accepted, _ = _offer(status="ACCEPTED")
    assert not buyer_is_masked(accepted, uuid.uuid4())
    named, _ = _offer(anonymous=False)
    assert not buyer_is_masked(named, uuid.uuid4())


def test_masked_names():
    club = SimpleNamespace(name="Secret Buyers FC", masking_league="Premier League")
    assert masked_name(club) == "A Premier League club"
    assert masked_name(club, capitalise=False) == "a Premier League club"
    assert masked_name(SimpleNamespace(name="X", masking_league=None)) == "An undisclosed club"
    offer, buyer_id = _offer()
    assert buyer_name(offer, club, uuid.uuid4()) == "A Premier League club"
    assert buyer_name(offer, club, buyer_id) == "Secret Buyers FC"


# ── Pushes created by the real flows ─────────────────────────────────────────


async def _clubs(client):
    seller = await _register(client, "copy_seller@test.com", club_name="Copy Sellers FC")
    buyer = await _register(client, "copy_buyer@test.com", club_name="Copy Buyers FC")
    return seller, buyer


async def _latest(db, type_: NotificationType) -> Notification:
    rows = (await db.execute(select(Notification).where(Notification.type == type_)
                             .order_by(Notification.created_at.desc()))).scalars().all()
    assert rows, f"no {type_.value} notification"
    return rows[0]


async def _offer_for(client, db, seller, buyer, *, anonymous=False, valuation=None, expires_in=None):
    from app.players.models import Contract

    await _give_budget(db)
    player = await _create_player_for_seller(client, _auth_headers(seller))
    if valuation is not None:
        seller_club = uuid.UUID(await _get_club_id(client, _auth_headers(seller)))
        contract = (await db.execute(select(Contract).where(
            Contract.player_id == uuid.UUID(player["id"]), Contract.is_active.is_(True)))).scalars().first()
        if contract is None:
            contract = Contract(player_id=uuid.UUID(player["id"]), club_id=seller_club, is_active=True)
            db.add(contract)
        contract.club_valuation = Decimal(valuation)
        await db.commit()
    body = {"player_id": player["id"], "to_club_id": await _get_club_id(client, _auth_headers(seller)),
            "fee_amount": 5_000_000, "is_anonymous": anonymous}
    if expires_in is not None:
        body["expires_at"] = (datetime.now(timezone.utc) + expires_in).isoformat()
    resp = await client.post("/offers", json=body, headers=_auth_headers(buyer))
    assert resp.status_code == 201, resp.text
    return player, resp.json()


@pytest.mark.asyncio
async def test_offer_received_names_player_amount_buyer_valuation_and_deadline(client: AsyncClient, db):
    seller, buyer = await _clubs(client)
    player, offer = await _offer_for(client, db, seller, buyer, valuation=8_000_000, expires_in=timedelta(hours=30))
    n = await _latest(db, NotificationType.OFFER_RECEIVED)
    assert n.title == f"Offer for {player['name']}: £5m"
    assert n.body == f"Copy Buyers FC · your valuation £8m · reply by {DEADLINE}"
    assert n.group_key == f"offer:{offer['id']}"
    assert n.deadline_at is not None
    assert [a["title"] for a in n.actions_json] == ["Ask for £8m", "Open"]
    assert n.actions_json[0]["url"] == f"/lite/offers/{offer['id']}?action=counter&amount=8000000"

    # The list writes the deadline out and gives the tier.
    items = (await client.get("/notifications", headers=_auth_headers(seller))).json()["items"]
    item = next(i for i in items if i["type"] == "OFFER_RECEIVED")
    assert "{" not in item["body"] and "reply by " in item["body"]
    assert item["tier"] == "YOUR_MOVE"


@pytest.mark.asyncio
async def test_an_anonymous_buyer_is_never_named_in_the_sellers_push(client: AsyncClient, db):
    seller, buyer = await _clubs(client)
    await _offer_for(client, db, seller, buyer, anonymous=True)
    n = await _latest(db, NotificationType.OFFER_RECEIVED)
    assert "Copy Buyers" not in f"{n.title} {n.body} {n.actions_json}"
    # No valuation on record, so that part is left out, and with no figure
    # to ask for there is only Open.
    assert n.body in ("An undisclosed club · reply by {deadline}", "A Premier League club · reply by {deadline}")
    assert [a["action"] for a in n.actions_json] == ["open"]


@pytest.mark.asyncio
async def test_a_counter_says_who_how_much_and_which_way(client: AsyncClient, db):
    seller, buyer = await _clubs(client)
    player, offer = await _offer_for(client, db, seller, buyer, expires_in=timedelta(days=2))
    resp = await client.post(f"/offers/{offer['id']}/counter", json={"fee_amount": 7_000_000}, headers=_auth_headers(seller))
    assert resp.status_code == 200, resp.text
    n = await _latest(db, NotificationType.OFFER_COUNTERED)
    assert n.title == "Copy Sellers FC countered at £7m"
    assert n.body == f"{player['name']} · up from £5m · {TIME_LEFT} to reply"
    assert [a["title"] for a in n.actions_json] == ["Accept £7m", "Open"]
    assert n.actions_json[0]["url"] == f"/lite/offers/{offer['id']}?action=accept"


@pytest.mark.asyncio
async def test_an_offer_message_names_a_hidden_buyer_only_by_its_league(client: AsyncClient, db):
    seller, buyer = await _clubs(client)
    player, offer = await _offer_for(client, db, seller, buyer, anonymous=True)
    resp = await client.post(f"/offers/{offer['id']}/messages", json={"body": "Would you take   £6m\nfor him?"},
                             headers=_auth_headers(buyer))
    assert resp.status_code in (200, 201), resp.text
    n = await _latest(db, NotificationType.OFFER_MESSAGE)
    assert n.title.endswith(f" · {player['name']}") and "Copy Buyers" not in n.title
    assert n.body == "Would you take £6m for him?"


@pytest.mark.asyncio
async def test_hidden_amounts_still_apply_to_the_new_wording(client: AsyncClient, db):
    """Review decision 1 covers the new titles too: the lock screen gets the
    generic line, never "Offer for X: £5m"."""
    from app.notifications.push import build_payload
    from app.notifications.tiers import Tier

    seller, buyer = await _clubs(client)
    await _offer_for(client, db, seller, buyer, valuation=8_000_000)
    n = await _latest(db, NotificationType.OFFER_RECEIVED)
    payload = build_payload(n, tier=Tier.YOUR_MOVE, silent=False, hide_amounts=True, badge=None)
    note = payload["notification"]
    assert note["title"] == "New offer received"
    assert note["body"] == "Open TransferX to see the details."
    assert "actions" not in note


@pytest.mark.asyncio
async def test_an_approval_request_says_what_who_and_the_budget_after(client: AsyncClient, db):
    from tests.test_approvals import _create_staff, _set_threshold

    seller, buyer = await _clubs(client)
    await _give_budget(db)
    player = await _create_player_for_seller(client, _auth_headers(seller))
    await _set_threshold(client, buyer, 1_000_000)
    manager = await _create_staff(client, db, _auth_headers(buyer), "copy_mgr@test.com", "MANAGER")
    resp = await client.post("/offers", json={"player_id": player["id"], "fee_amount": 4_200_000,
                                               "to_club_id": await _get_club_id(client, _auth_headers(seller))},
                             headers=_auth_headers(manager))
    assert resp.status_code == 202, resp.text
    n = await _latest(db, NotificationType.APPROVAL_REQUESTED)
    assert n.title == f"Approve a £4.2m offer for {player['name']}?"
    # test_deals._give_budget sets £100m; a captured offer reserves nothing.
    assert n.body == "copy_mgr, Manager · budget after £95.8m"
    assert n.group_key.startswith("approval:") and n.deadline_at is not None


# ── Auctions ──────────────────────────────────────────────────────────────────


def _sale(**kw):
    return SimpleNamespace(id=uuid.uuid4(), deadline=NOW + timedelta(minutes=50), **kw)


def test_outbid_never_names_the_rival_and_offers_the_next_step():
    from app.notifications.copy import outbid

    sale = _sale()
    c = outbid(sale=sale, player="Theo Marsh", best=Decimal("3400000"), next_bid=Decimal("3600000"))
    assert c["title"] == "You've been outbid on Theo Marsh"
    assert render(c["body"], c["deadline_at"], LONDON, NOW) == "Highest bid now £3.4m · ends in 50 minutes"
    assert c["actions"][0] == {"action": "bid", "title": "Bid £3.6m", "url": f"/sales/{sale.id}?bid=3600000"}


def test_auction_ending_for_the_seller_and_for_a_bidder():
    from app.notifications.copy import auction_ending

    sale = _sale()
    seller = auction_ending(sale=sale, player="Yannick Sorel", seller_view=True, best=Decimal("6500000"), bids=6, own_bid=None)
    assert render(seller["title"], sale.deadline, LONDON, NOW) == "50 minutes left on the Yannick Sorel auction"
    assert seller["body"] == "Highest bid £6.5m · 6 bids"
    bidder = auction_ending(sale=sale, player="Yannick Sorel", seller_view=False, best=Decimal("6500000"), bids=6,
                            own_bid=Decimal("6000000"))
    assert bidder["body"] == "Your bid £6m · highest £6.5m"
