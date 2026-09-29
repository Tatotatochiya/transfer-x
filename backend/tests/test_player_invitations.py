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
    assert preview.json()["invited_by"] == "Inviting FC"

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


# ── Free agents: invited by TransferX staff or by their agent ────────────────


async def _free_agent(db, name="Free Agent Fred"):
    from app.players.models import Player, PlayerStatus

    p = Player(name=name, status=PlayerStatus.FREE_AGENT)
    db.add(p)
    await db.commit()
    return str(p.id)


async def _external_player(db):
    from app.players.models import Player, PlayerStatus

    p = Player(name="Elsewhere Eric", status=PlayerStatus.EXTERNAL, team_name="Real Somewhere")
    db.add(p)
    await db.commit()
    return str(p.id)


@pytest_asyncio.fixture
async def staff(client: AsyncClient, db) -> dict:
    from sqlalchemy import select

    from app.auth.models import User

    tokens = await _register(client, "staff_pinv@test.com", club_name="TX Staff")
    user = (await db.execute(select(User).where(User.email == "staff_pinv@test.com"))).scalar_one()
    user.is_superuser = True
    await db.commit()
    return tokens


async def _agent_with_mandate(client, db, player_id, *, active=True) -> dict:
    from sqlalchemy import select

    from app.auth.models import AgentProfile, User
    from app.mandates.models import Mandate, MandateStatus

    tokens = (await client.post("/auth/register", json={
        "email": "agent_pinv@test.com", "password": "password123", "user_type": "AGENT",
        "display_name": "Ada Agent", "agency_name": "Ada Sports", "country": "England",
    })).json()
    user = (await db.execute(select(User).where(User.email == "agent_pinv@test.com"))).scalar_one()
    profile = (await db.execute(select(AgentProfile).where(AgentProfile.user_id == user.id))).scalar_one()
    import uuid as _uuid

    db.add(Mandate(agent_id=profile.id, player_id=_uuid.UUID(player_id),
                   status=MandateStatus.ACTIVE if active else MandateStatus.REVOKED))
    await db.commit()
    return tokens


@pytest.mark.asyncio
async def test_staff_invite_a_free_agent(client, staff, db):
    player_id = await _free_agent(db)
    resp = await client.post(
        "/admin/player-invitations", json={"player_id": player_id, "email": "fred@free.com"},
        headers=_auth_headers(staff),
    )
    assert resp.status_code == 201, resp.text
    token = _token(resp.json())
    assert (await client.get(f"/auth/player-invitations/{token}")).json()["invited_by"] == "TransferX"
    listed = (await client.get("/admin/player-invitations", headers=_auth_headers(staff))).json()
    assert listed[0]["player_name"] == "Free Agent Fred"
    accepted = await client.post(f"/auth/player-invitations/{token}/accept", json={"password": "password123"})
    assert accepted.status_code == 201, accepted.text


@pytest.mark.asyncio
async def test_staff_cannot_invite_club_or_external_players(client, staff, club, db):
    club_player = await _create_player_for_seller(client, _auth_headers(club))
    for pid in (club_player["id"], await _external_player(db)):
        resp = await client.post(
            "/admin/player-invitations", json={"player_id": pid, "email": "x@y.com"}, headers=_auth_headers(staff),
        )
        assert resp.status_code == 400, resp.text
        assert "not a free agent" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_only_staff_use_the_admin_route(client, club, db):
    player_id = await _free_agent(db)
    resp = await client.post(
        "/admin/player-invitations", json={"player_id": player_id, "email": "x@y.com"}, headers=_auth_headers(club),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_agent_invites_his_free_agent_client(client, db):
    player_id = await _free_agent(db)
    agent = await _agent_with_mandate(client, db, player_id)
    status_before = (await client.get(f"/agents/me/players/{player_id}/account", headers=_auth_headers(agent))).json()
    assert status_before["has_account"] is False

    resp = await client.post(
        "/agents/me/player-invitations", json={"player_id": player_id, "email": "fred@free.com"},
        headers=_auth_headers(agent),
    )
    assert resp.status_code == 201, resp.text
    token = _token(resp.json())
    assert (await client.get(f"/auth/player-invitations/{token}")).json()["invited_by"] == "your agent Ada Agent"


@pytest.mark.asyncio
async def test_agent_needs_an_active_mandate(client, db):
    player_id = await _free_agent(db)
    agent = await _agent_with_mandate(client, db, player_id, active=False)
    resp = await client.post(
        "/agents/me/player-invitations", json={"player_id": player_id, "email": "fred@free.com"},
        headers=_auth_headers(agent),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_agent_cannot_invite_a_client_who_has_a_club(client, club, db):
    club_player = await _create_player_for_seller(client, _auth_headers(club))
    agent = await _agent_with_mandate(client, db, club_player["id"])
    resp = await client.post(
        "/agents/me/player-invitations", json={"player_id": club_player["id"], "email": "p@club.com"},
        headers=_auth_headers(agent),
    )
    assert resp.status_code == 400
    assert "his club invites him" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_a_club_cannot_invite_a_free_agent(client, club, db):
    player_id = await _free_agent(db)
    assert (await _invite(client, club, player_id)).status_code == 404
