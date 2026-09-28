"""Players join by invitation from the club that owns them."""

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.config import settings
from tests.conftest import _auth_headers, _register
from tests.test_deals import _create_deal_via_offer, _create_player_for_seller


@pytest_asyncio.fixture
async def club(client: AsyncClient) -> dict:
    return await _register(client, "club_pinv@test.com", club_name="Inviting FC")


@pytest_asyncio.fixture
async def other_club(client: AsyncClient) -> dict:
    return await _register(client, "other_pinv@test.com", club_name="Other FC")


async def _invite(client, club, player_id, email="player@inviting.com"):
    return await client.post(
        "/clubs/me/player-invitations", json={"player_id": player_id, "email": email}, headers=_auth_headers(club)
    )


def _token(inv: dict) -> str:
    assert "/join/player?token=" in inv["accept_url"]
    return inv["accept_url"].split("token=")[1]


@pytest.mark.asyncio
async def test_invite_preview_accept_once(client, club):
    player = await _create_player_for_seller(client, _auth_headers(club))
    resp = await _invite(client, club, player["id"])
    assert resp.status_code == 201, resp.text
    token = _token(resp.json())

    status_before = (await client.get(f"/clubs/me/players/{player['id']}/account", headers=_auth_headers(club))).json()
    assert status_before["has_account"] is False
    assert status_before["invitation"]["email"] == "player@inviting.com"
    assert status_before["invitation"]["accept_url"] is None  # the link is shown once, at creation

    preview = await client.get(f"/auth/player-invitations/{token}")
    assert preview.status_code == 200
    assert preview.json()["player_name"] == player["name"]
    assert preview.json()["club_name"] == "Inviting FC"

    accepted = await client.post(f"/auth/player-invitations/{token}/accept", json={"password": "password123"})
    assert accepted.status_code == 201, accepted.text
    me = (await client.get("/auth/me", headers=_auth_headers(accepted.json()))).json()
    assert me["user_type"] == "PLAYER"

    status_after = (await client.get(f"/clubs/me/players/{player['id']}/account", headers=_auth_headers(club))).json()
    assert status_after["has_account"] is True

    again = await client.post(f"/auth/player-invitations/{token}/accept", json={"password": "password123"})
    assert again.status_code == 409
    assert (await client.get(f"/auth/player-invitations/{token}")).status_code == 404


@pytest.mark.asyncio
async def test_only_the_owning_club_can_invite(client, club, other_club):
    player = await _create_player_for_seller(client, _auth_headers(club))
    resp = await _invite(client, other_club, player["id"])
    assert resp.status_code == 404
    status = await client.get(f"/clubs/me/players/{player['id']}/account", headers=_auth_headers(other_club))
    assert status.status_code == 404


@pytest.mark.asyncio
async def test_refuses_duplicates_and_existing_accounts(client, club):
    player = await _create_player_for_seller(client, _auth_headers(club))
    assert (await _invite(client, club, player["id"])).status_code == 201
    # A second live invitation for the same player.
    assert (await _invite(client, club, player["id"], email="second@inviting.com")).status_code == 400
    # An email that already has an account.
    other = await _create_player_for_seller(client, _auth_headers(club))
    assert (await _invite(client, club, other["id"], email="club_pinv@test.com")).status_code == 400


@pytest.mark.asyncio
async def test_player_with_an_account_cannot_be_invited_again(client, club):
    player = await _create_player_for_seller(client, _auth_headers(club))
    token = _token((await _invite(client, club, player["id"])).json())
    await client.post(f"/auth/player-invitations/{token}/accept", json={"password": "password123"})
    resp = await _invite(client, club, player["id"], email="new@inviting.com")
    assert resp.status_code == 400
    assert "already has" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_revoked_invitation_is_dead(client, club):
    player = await _create_player_for_seller(client, _auth_headers(club))
    inv = (await _invite(client, club, player["id"])).json()
    revoked = await client.post(f"/clubs/me/player-invitations/{inv['id']}/revoke", headers=_auth_headers(club))
    assert revoked.status_code == 200, revoked.text
    token = _token(inv)
    assert (await client.get(f"/auth/player-invitations/{token}")).status_code == 404
    accept = await client.post(f"/auth/player-invitations/{token}/accept", json={"password": "password123"})
    assert accept.status_code == 409
    # A fresh invitation can follow a revoked one.
    assert (await _invite(client, club, player["id"])).status_code == 201


@pytest.mark.asyncio
async def test_player_self_registration_is_refused(client, club):
    player = await _create_player_for_seller(client, _auth_headers(club))
    settings.allow_player_self_registration = False
    try:
        resp = await client.post("/auth/register", json={
            "email": "impostor@test.com", "password": "password123", "user_type": "PLAYER", "player_id": player["id"],
        })
        assert resp.status_code == 403
    finally:
        settings.allow_player_self_registration = True


@pytest.mark.asyncio
async def test_invited_player_answers_his_own_terms(client, db):
    """Once invited, the player accepts his own terms; the buying club can no
    longer record them for him (that is only for a player with no account)."""
    buyer = await _register(client, "buyer_pinv@test.com", club_name="Buying FC")
    seller = await _register(client, "seller_pinv@test.com", club_name="Selling FC")
    deal = await _create_deal_via_offer(client, buyer, seller, db)
    player_id = deal["player_id"]

    token = _token((await _invite(client, seller, player_id, email="star@selling.com")).json())
    player_tokens = (await client.post(f"/auth/player-invitations/{token}/accept", json={"password": "password123"})).json()

    await client.post(f"/deals/{deal['id']}/advance", headers=_auth_headers(buyer))
    await client.put(f"/deals/{deal['id']}/personal-terms", json={"wage_weekly": 50000}, headers=_auth_headers(buyer))

    by_club = await client.post(
        f"/deals/{deal['id']}/personal-terms/player-consent", json={"agreement": "AGREED"},
        headers=_auth_headers(buyer),
    )
    assert by_club.status_code == 403

    by_player = await client.post(
        f"/deals/{deal['id']}/personal-terms/player-consent", json={"agreement": "AGREED"},
        headers=_auth_headers(player_tokens),
    )
    assert by_player.status_code == 200, by_player.text
    assert by_player.json()["player_consent"] == "AGREED"
