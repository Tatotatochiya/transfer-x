"""Lite L8, decisions from email: GET changes nothing, money needs the
recipient signed in, a token works once, and a changed offer is refused."""
import uuid
from urllib.parse import parse_qs, urlparse

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.auth.models import User
from app.lite import email_actions
from app.lite.models import ActionToken, HeldAction, HeldActionChannel
from tests.conftest import _auth_headers, _register
from tests.test_deals import _create_player_for_seller, _get_club_id, _give_budget

pytestmark = pytest.mark.asyncio


async def _setup(client, db, anonymous=True):
    seller_tokens = await _register(client, "l8_seller@test.com", club_name="Email Sellers")
    buyer = _auth_headers(await _register(client, "l8_buyer@test.com", club_name="Email Buyers"))
    seller = _auth_headers(seller_tokens)
    await _give_budget(db)
    player = await _create_player_for_seller(client, seller)
    offer = (await client.post("/offers", json={"player_id": player["id"], "fee_amount": 5_000_000, "is_anonymous": anonymous,
                                                "to_club_id": await _get_club_id(client, seller)}, headers=buyer)).json()
    user = (await db.execute(select(User).where(User.email == "l8_seller@test.com"))).scalar_one()
    buttons = await email_actions.offer_buttons(db, user, uuid.UUID(offer["id"]))
    await db.commit()
    return seller, buyer, offer, buttons


def _link(buttons, label_start):
    url = next(u for label, u in buttons if label.startswith(label_start))
    parsed = urlparse(url)
    token = parsed.path.rsplit("/", 1)[1]
    q = {k: v[0] for k, v in parse_qs(parsed.query).items()}
    return token, q


async def test_buttons_and_a_side_effect_free_preview(client: AsyncClient, db):
    seller, _buyer, offer, buttons = await _setup(client, db)
    assert [label for label, _ in buttons][1:] == ["Accept £5m", "Say no"]
    assert buttons[0][0].startswith("Ask for £")
    token, q = _link(buttons, "Say no")
    view = (await client.get(f"/lite/confirm/{token}", params=q)).json()
    assert view["state"] == "ready" and view["label"] == "Say no" and view["needs_sign_in"] is False
    assert "Email Buyers" not in str(view)  # the anonymous buyer stays masked
    assert "@" not in str(view)  # nor the recipient's address: links get forwarded
    # Opening it changed nothing.
    assert (await db.execute(select(HeldAction))).first() is None
    assert (await db.execute(select(ActionToken.used_at))).scalar_one() is None


async def test_saying_no_needs_only_the_token_and_works_once(client: AsyncClient, db):
    _seller, _buyer, offer, buttons = await _setup(client, db)
    token, q = _link(buttons, "Say no")
    resp = await client.post(f"/lite/confirm/{token}", json={"action": "reject"})
    assert resp.status_code == 200, resp.text
    held = (await db.execute(select(HeldAction))).scalar_one()
    assert held.kind == "reject" and held.channel == HeldActionChannel.EMAIL
    assert (await client.post(f"/lite/confirm/{token}", json={"action": "reject"})).status_code == 410
    # And it can be undone within its 10 seconds, from the same link.
    assert (await client.post(f"/lite/confirm/{token}/undo")).status_code == 204


async def test_money_needs_the_recipient_signed_in(client: AsyncClient, db):
    seller, buyer, offer, buttons = await _setup(client, db)
    token, q = _link(buttons, "Accept")
    assert (await client.post(f"/lite/confirm/{token}", json={"action": "accept"})).status_code == 401
    assert (await client.post(f"/lite/confirm/{token}", json={"action": "accept"}, headers=buyer)).status_code == 403
    resp = await client.post(f"/lite/confirm/{token}", json={"action": "accept"}, headers=seller)
    assert resp.status_code == 200, resp.text


async def test_a_changed_offer_is_refused(client: AsyncClient, db):
    seller, buyer, offer, buttons = await _setup(client, db, anonymous=False)
    token, q = _link(buttons, "Say no")
    # The buyer raises the offer after the email went out.
    assert (await client.post(f"/offers/{offer['id']}/improve", json={"fee_amount": 6_000_000}, headers=buyer)).status_code == 200
    assert (await client.get(f"/lite/confirm/{token}", params=q)).json()["state"] == "changed"
    resp = await client.post(f"/lite/confirm/{token}", json={"action": "reject"})
    assert resp.status_code == 409 and "changed" in resp.json()["detail"]


async def test_digest_email_carries_buttons():
    from app.notifications.email import render_digest_html

    out = render_digest_html([("Offer · Leeds", "https://x/offers/1", [("Accept £5m", "https://x/lite/confirm/t?action=accept")])],
                             "https://x/dashboard")
    assert "Accept £5m" in out and "/lite/confirm/t?action=accept" in out
