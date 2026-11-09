"""One conversation per transfer (Phase 3, product ADR 0008): the enquiry,
offer, deal and agent messages between two clubs about one player, read as
one, with each system's visibility and anonymity rules intact."""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.deals.models import Deal
from tests.conftest import _auth_headers, _register
from tests.test_deals import _create_player_for_seller, _get_club_id, _give_budget
from tests.test_negotiation_messages import _headers, _setup_negotiation

pytestmark = pytest.mark.asyncio


async def _conv(client, headers, **ctx):
    resp = await client.get("/conversation", params=ctx, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


async def test_enquiry_then_offer_then_deal_is_one_conversation(client: AsyncClient, db):
    seller = _auth_headers(await _register(client, "conv_seller@test.com", club_name="Conv Sellers"))
    buyer = _auth_headers(await _register(client, "conv_buyer@test.com", club_name="Conv Buyers"))
    await _give_budget(db)
    player = await _create_player_for_seller(client, seller)
    enquiry = (await client.post("/enquiries", json={"player_id": player["id"], "body": "Would you sell?",
                                                     "is_anonymous": True}, headers=buyer)).json()

    # The enquiry is open: both clubs can write, and the asking club stays masked.
    conv = await _conv(client, seller, enquiry_id=enquiry["id"])
    assert [o["key"] for o in conv["can_post_to"]] == ["both_clubs"]
    assert conv["messages"][0]["author"] != "Conv Buyers" and conv["messages"][0]["body"] == "Would you sell?"
    resp = await client.post("/conversation", json={"enquiry_id": enquiry["id"], "audience": "both_clubs",
                                                    "body": "Make us an offer"}, headers=seller)
    assert resp.status_code == 200, resp.text

    offer = (await client.post("/offers", json={"player_id": player["id"], "fee_amount": 5_000_000,
                                                "to_club_id": await _get_club_id(client, seller),
                                                "is_anonymous": True}, headers=buyer)).json()
    # Posting on the transfer now goes to the open offer (and notifies as an offer message).
    resp = await client.post("/conversation", json={"offer_id": offer["id"], "audience": "both_clubs",
                                                    "body": "Here it is"}, headers=buyer)
    assert resp.status_code == 200, resp.text
    conv = await _conv(client, seller, offer_id=offer["id"])
    assert [m["body"] for m in conv["messages"]] == ["Would you sell?", "Make us an offer", "Here it is"]
    assert [m["context"] for m in conv["messages"]] == ["Enquiry", "Enquiry", "Offer"]
    assert "Conv Buyers" not in str(conv)  # still anonymous
    assert conv["messages"][1]["mine"] and conv["messages"][1]["author"] == "You"

    # Accepted: a deal. Shared and private messages; the other club never sees our private one.
    assert (await client.post(f"/offers/{offer['id']}/accept", headers=seller)).status_code == 200
    deal = (await db.execute(select(Deal).where(Deal.offer_id == uuid.UUID(offer["id"])))).scalar_one()
    conv = await _conv(client, buyer, deal_id=str(deal.id))
    assert [o["key"] for o in conv["can_post_to"]] == ["deal_everyone", "our_club"]
    assert conv["live"]["deal_id"] == str(deal.id) and conv["live"]["offer_id"] is None
    await client.post("/conversation", json={"deal_id": str(deal.id), "audience": "deal_everyone", "body": "Welcome"}, headers=buyer)
    await client.post("/conversation", json={"deal_id": str(deal.id), "audience": "our_club", "body": "Keep the bonus low"}, headers=buyer)
    # A mention on a shared message notifies them; one on a private note is dropped.
    seller_owner = (await client.get("/auth/me", headers=seller)).json()["id"]
    await client.post("/conversation", json={"deal_id": str(deal.id), "audience": "deal_everyone", "body": "Over to you",
                                             "mentioned_user_ids": [seller_owner]}, headers=buyer)
    await client.post("/conversation", json={"deal_id": str(deal.id), "audience": "our_club", "body": "Psst",
                                             "mentioned_user_ids": [seller_owner]}, headers=buyer)
    from app.notifications.models import Notification, NotificationType

    pinged = (await db.execute(select(Notification).where(
        Notification.recipient_user_id == uuid.UUID(seller_owner), Notification.type == NotificationType.NEGOTIATION_MESSAGE,
    ))).scalars().all()
    assert len(pinged) == 1
    mine = [m["body"] for m in (await _conv(client, buyer, deal_id=str(deal.id)))["messages"]]
    theirs = [m["body"] for m in (await _conv(client, seller, deal_id=str(deal.id)))["messages"]]
    assert mine[-4:] == ["Welcome", "Keep the bonus low", "Over to you", "Psst"]
    assert "Welcome" in theirs and "Keep the bonus low" not in theirs and "Psst" not in theirs
    # The whole history still reads from the deal.
    assert theirs[:3] == ["Would you sell?", "Make us an offer", "Here it is"]

    # Writing to an audience that isn't open now is refused.
    resp = await client.post("/conversation", json={"deal_id": str(deal.id), "audience": "both_clubs", "body": "x"}, headers=buyer)
    assert resp.status_code == 409


async def test_the_agent_thread_joins_and_strangers_are_refused(client: AsyncClient, db):
    ctx = await _setup_negotiation(client, db)
    neg_id = ctx["negotiation_id"]
    await client.post(f"/negotiations/{neg_id}/messages", json={"thread": "CLUB_SIDE", "body": "My client wants more"},
                      headers=_headers(ctx["agent"]))
    await client.post(f"/negotiations/{neg_id}/messages", json={"thread": "PLAYER_SIDE", "body": "Between us"},
                      headers=_headers(ctx["agent"]))
    from app.agents.models import AgentNegotiation

    deal_id = str((await db.get(AgentNegotiation, uuid.UUID(neg_id))).deal_id)
    conv = await _conv(client, _headers(ctx["buyer"]), deal_id=deal_id)
    bodies = [m["body"] for m in conv["messages"]]
    assert "My client wants more" in bodies and "Between us" not in bodies  # the player side stays private
    assert "with_agent" in [o["key"] for o in conv["can_post_to"]]
    resp = await client.post("/conversation", json={"deal_id": deal_id, "audience": "with_agent", "body": "We can do 10%"},
                             headers=_headers(ctx["buyer"]))
    assert resp.status_code == 200, resp.text
    agent_view = (await client.get(f"/negotiations/{neg_id}/messages", headers=_headers(ctx["agent"]))).json()
    assert "We can do 10%" in str(agent_view)

    stranger = _auth_headers(await _register(client, "conv_stranger@test.com", club_name="Strangers"))
    assert (await client.get("/conversation", params={"deal_id": deal_id}, headers=stranger)).status_code == 403


async def test_unread_counts_the_other_clubs_messages_until_read(client: AsyncClient, db):
    seller = _auth_headers(await _register(client, "unread_seller@test.com", club_name="Unread Sellers"))
    buyer = _auth_headers(await _register(client, "unread_buyer@test.com", club_name="Unread Buyers"))
    await _give_budget(db)
    player = await _create_player_for_seller(client, seller)
    offer = (await client.post("/offers", json={"player_id": player["id"], "fee_amount": 5_000_000,
                                                "to_club_id": await _get_club_id(client, seller)}, headers=buyer)).json()
    for text in ("First", "Second"):
        await client.post("/conversation", json={"offer_id": offer["id"], "audience": "both_clubs", "body": text}, headers=buyer)

    assert (await _conv(client, seller, offer_id=offer["id"]))["unread"] == 2
    assert (await _conv(client, buyer, offer_id=offer["id"]))["unread"] == 0  # their own
    # Reading the conversation doesn't mark it; the read endpoint does.
    assert (await _conv(client, seller, offer_id=offer["id"]))["unread"] == 2
    resp = await client.post("/conversation/read", params={"offer_id": offer["id"]}, headers=seller)
    assert resp.status_code == 204, resp.text
    assert (await _conv(client, seller, offer_id=offer["id"]))["unread"] == 0

    # The test database keeps whole seconds: move what's been read into the past.
    from datetime import timedelta

    from app.conversation.models import ConversationRead
    from app.offers.models import OfferMessage

    for m in (await db.execute(select(OfferMessage))).scalars():
        m.created_at = m.created_at - timedelta(minutes=2)
    for r in (await db.execute(select(ConversationRead))).scalars():
        r.read_at = r.read_at - timedelta(minutes=2)
    await db.commit()
    await client.post("/conversation", json={"offer_id": offer["id"], "audience": "both_clubs", "body": "Third"}, headers=buyer)
    assert (await _conv(client, seller, offer_id=offer["id"]))["unread"] == 1
    # Marking twice is fine (an upsert).
    await client.post("/conversation/read", params={"offer_id": offer["id"]}, headers=seller)
    assert (await client.post("/conversation/read", params={"offer_id": offer["id"]}, headers=seller)).status_code == 204

    stranger = _auth_headers(await _register(client, "unread_stranger@test.com", club_name="Unread Strangers"))
    assert (await client.post("/conversation/read", params={"offer_id": offer["id"]}, headers=stranger)).status_code in (403, 404)
