"""Enquiries — informal questions about a player before any offer."""

import pytest
import pytest_asyncio
from httpx import AsyncClient

from tests.conftest import _auth_headers, _register


@pytest_asyncio.fixture
async def asker(client: AsyncClient) -> dict:
    return await _register(client, "asker_enq@test.com", club_name="Asking Rovers")


@pytest_asyncio.fixture
async def owner(client: AsyncClient) -> dict:
    return await _register(client, "owner_enq@test.com", club_name="Owning United")


@pytest_asyncio.fixture
async def outsider(client: AsyncClient) -> dict:
    return await _register(client, "outsider_enq@test.com", club_name="Outside City")


async def _player(client: AsyncClient, headers: dict) -> dict:
    resp = await client.post("/players", json={"name": "Enquiry Player", "position": "DEF"}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _ask(client, headers, player_id, anonymous=False, body="Would you sell him?"):
    return await client.post(
        "/enquiries", json={"player_id": player_id, "body": body, "is_anonymous": anonymous}, headers=headers
    )


@pytest.mark.asyncio
async def test_anonymous_asker_is_masked_from_the_owner(client, asker, owner):
    player = await _player(client, _auth_headers(owner))
    resp = await _ask(client, _auth_headers(asker), player["id"], anonymous=True)
    assert resp.status_code == 201, resp.text
    enquiry_id = resp.json()["id"]

    seen = (await client.get(f"/enquiries/{enquiry_id}", headers=_auth_headers(owner))).json()
    # Masked by id as well as name: the id would resolve through /clubs/{id}.
    assert seen["asking_club"]["id"] is None
    assert "Asking Rovers" not in seen["asking_club"]["name"]
    assert "Asking Rovers" not in str(seen)
    assert seen["role"] == "owning"
    assert seen["whose_move"] == "your"
    # Messages carry a side, not a club id.
    assert [m["side"] for m in seen["messages"]] == ["theirs"]

    # The asker sees its own name.
    mine = (await client.get(f"/enquiries/{enquiry_id}", headers=_auth_headers(asker))).json()
    assert mine["asking_club"]["name"] == "Asking Rovers"
    assert mine["whose_move"] == "their"


@pytest.mark.asyncio
async def test_open_enquiry_is_revealed_by_name(client, asker, owner):
    player = await _player(client, _auth_headers(owner))
    enquiry_id = (await _ask(client, _auth_headers(asker), player["id"])).json()["id"]
    seen = (await client.get(f"/enquiries/{enquiry_id}", headers=_auth_headers(owner))).json()
    assert seen["asking_club"]["name"] == "Asking Rovers"


@pytest.mark.asyncio
async def test_one_open_enquiry_per_club_per_player(client, asker, owner):
    player = await _player(client, _auth_headers(owner))
    first = (await _ask(client, _auth_headers(asker), player["id"])).json()
    again = await _ask(client, _auth_headers(asker), player["id"], body="Any update?")
    assert again.status_code == 409
    assert again.json()["detail"]["enquiry_id"] == first["id"]


@pytest.mark.asyncio
async def test_cannot_enquire_about_own_player(client, owner):
    player = await _player(client, _auth_headers(owner))
    resp = await _ask(client, _auth_headers(owner), player["id"])
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_third_club_cannot_see_or_join(client, asker, owner, outsider):
    player = await _player(client, _auth_headers(owner))
    enquiry_id = (await _ask(client, _auth_headers(asker), player["id"])).json()["id"]
    h = _auth_headers(outsider)
    assert (await client.get(f"/enquiries/{enquiry_id}", headers=h)).status_code == 404
    assert (await client.post(f"/enquiries/{enquiry_id}/messages", json={"body": "hi"}, headers=h)).status_code == 404
    assert (await client.post(f"/enquiries/{enquiry_id}/close", headers=h)).status_code == 404


@pytest.mark.asyncio
async def test_reply_flips_whose_move(client, asker, owner):
    player = await _player(client, _auth_headers(owner))
    enquiry_id = (await _ask(client, _auth_headers(asker), player["id"])).json()["id"]
    resp = await client.post(
        f"/enquiries/{enquiry_id}/messages", json={"body": "Not below £40m."}, headers=_auth_headers(owner)
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["whose_move"] == "their"
    mine = (await client.get(f"/enquiries/{enquiry_id}", headers=_auth_headers(asker))).json()
    assert mine["whose_move"] == "your"
    assert [m["side"] for m in mine["messages"]] == ["mine", "theirs"]


@pytest.mark.asyncio
async def test_close_then_no_more_replies(client, asker, owner):
    """Regression: closing returned a 500 (an expired column read after commit)."""
    player = await _player(client, _auth_headers(owner))
    enquiry_id = (await _ask(client, _auth_headers(asker), player["id"])).json()["id"]
    resp = await client.post(f"/enquiries/{enquiry_id}/close", headers=_auth_headers(asker))
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "CLOSED"
    assert resp.json()["whose_move"] == "neither"
    reply = await client.post(
        f"/enquiries/{enquiry_id}/messages", json={"body": "hello?"}, headers=_auth_headers(owner)
    )
    assert reply.status_code == 400


@pytest.mark.asyncio
async def test_lists_split_by_box(client, asker, owner):
    player = await _player(client, _auth_headers(owner))
    await _ask(client, _auth_headers(asker), player["id"])
    received = (await client.get("/enquiries?box=received", headers=_auth_headers(owner))).json()
    sent = (await client.get("/enquiries?box=sent", headers=_auth_headers(owner))).json()
    assert len(received) == 1 and sent == []
