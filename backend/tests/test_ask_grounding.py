"""Ask is grounded in TransferX's data, not the model's football memory
(ai-analyst spec §7a). Signed in as Chelsea, ⌘K once said "Havertz is
already in your squad", when he is Arsenal's."""
import pytest
from httpx import AsyncClient

from tests.conftest import _auth_headers
from tests.test_ai_assist import buyer, fake_model, seller  # noqa: F401 (fixtures)
from tests.test_deals import _give_budget
from tests.test_lite_buy import _player, _value

pytestmark = pytest.mark.asyncio


async def _ask(client, club, question, lite=False):
    resp = await client.post("/ai/ask", json={"question": question, "lite": lite}, headers=_auth_headers(club))
    assert resp.status_code == 200, resp.text
    return resp.json()


async def test_a_named_player_is_looked_up_and_a_wrong_claim_is_replaced(client: AsyncClient, buyer, seller, db, fake_model):  # noqa: F811
    calls, reply = fake_model
    await _player(client, seller, "K. Havertz", position="FWD")
    # The model, from memory: the player is the asking club's.
    reply["ASK_USER"] = {"answer": "K. Havertz is already in your squad, so you can't bid for him.", "links": []}
    got = await _ask(client, buyer, "is Havertz in our squad?")
    named = calls[-1]["facts"]["players_named_in_the_question"]
    assert len(named) == 1 and named[0]["player"] == "K. Havertz"
    assert named[0]["club"] == "Selling Side FC" and named[0]["is_your_player"] is False
    # The answer is replaced with what TransferX has.
    assert got["answer"].startswith("K. Havertz plays for Selling Side FC")
    assert "isn't listed for sale" in got["answer"]
    assert got["links"][0]["label"] == "K. Havertz"


async def test_a_bid_request_in_the_full_app_opens_the_offer_form(client: AsyncClient, buyer, seller, db, fake_model):  # noqa: F811
    calls, reply = fake_model
    await _give_budget(db)
    target = await _player(client, seller, "K. Havertz", position="FWD")
    await _value(db, target["id"], 10_000_000)
    # The model gives no proposal at all: the request is still read in code.
    reply["ASK_USER"] = {"answer": "Havertz is already in your squad.", "links": []}
    got = await _ask(client, buyer, "place 8m bid on Havertz")
    p = got["proposal"]
    assert (p["kind"], p["player"], p["club"], p["amount"]) == ("bid", "K. Havertz", "Selling Side FC", 8_000_000)
    assert p["card_path"] == f"/offers/new?player_id={target['id']}&fee=8000000&from=ask"
    assert got["answer"] == "I've prepared a £8m bid for K. Havertz (Selling Side FC) for you to check."


async def test_unrelated_words_name_nobody_and_your_own_player_is_yours(client: AsyncClient, buyer, seller, db, fake_model):  # noqa: F811
    calls, reply = fake_model
    await _player(client, buyer, "M. Mount", position="MID")
    reply["ASK_USER"] = {"answer": "M. Mount is in your squad.", "links": []}
    got = await _ask(client, buyer, "is Mount in our squad?")
    named = calls[-1]["facts"]["players_named_in_the_question"]
    assert named[0]["is_your_player"] is True
    assert got["answer"] == "M. Mount is in your squad."  # a true claim stays
    await _ask(client, buyer, "how much budget do we have left this week?")
    assert calls[-1]["facts"]["players_named_in_the_question"] == []
