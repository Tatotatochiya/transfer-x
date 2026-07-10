"""TRA-86 — owner-run team management + invitation-based onboarding.

Invitation lifecycle (create → preview → accept → login), token security
(hashed at rest, single-use, dead after expiry/revocation/acceptance),
TEAM_MANAGE gating, role changes, and D10 removal semantics.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient

from tests.conftest import _auth_headers, _register


@pytest_asyncio.fixture
async def owner(client: AsyncClient) -> dict:
    return await _register(client, "team_owner@test.com", club_name="Team FC")


async def _invite(
    client: AsyncClient, owner_tokens: dict, email: str, role: str = "SCOUT"
) -> dict:
    resp = await client.post(
        "/clubs/me/staff/invitations",
        json={"email": email, "role": role},
        headers=_auth_headers(owner_tokens),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _token_from(accept_url: str) -> str:
    return accept_url.split("token=")[1]


# ── Lifecycle ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_invitation_lifecycle_end_to_end(client: AsyncClient, db, owner: dict):
    data = await _invite(client, owner, "new_scout@test.com", "SCOUT")
    assert data["invitation"]["email"] == "new_scout@test.com"
    assert data["invitation"]["role"] == "SCOUT"
    token = _token_from(data["accept_url"])

    # Raw token is never stored — only its hash.
    from sqlalchemy import select
    from app.clubs.models import ClubStaffInvitation
    inv_row = (await db.execute(select(ClubStaffInvitation))).scalars().first()
    assert token not in (inv_row.token_hash or "")
    assert len(inv_row.token_hash) == 64  # sha256 hexdigest

    # Public preview
    resp = await client.get(f"/auth/invitations/{token}")
    assert resp.status_code == 200, resp.text
    preview = resp.json()
    assert preview["club_name"] == "Team FC"
    assert preview["role"] == "SCOUT"
    assert preview["email"] == "new_scout@test.com"

    # Accept → logged straight in
    resp = await client.post(f"/auth/invitations/{token}/accept", json={"password": "newpass123"})
    assert resp.status_code == 201, resp.text
    staff_tokens = resp.json()
    assert "access_token" in staff_tokens

    # The new member has the right membership, explicitly user_type CLUB
    resp = await client.get("/clubs/me/membership", headers=_auth_headers(staff_tokens))
    assert resp.status_code == 200
    assert resp.json()["role"] == "SCOUT"
    me = await client.get("/auth/me", headers=_auth_headers(staff_tokens))
    assert me.json()["user_type"] == "CLUB"

    # Owner's team payload shows the member and no pending invitation
    resp = await client.get("/clubs/me/staff", headers=_auth_headers(owner))
    assert resp.status_code == 200
    team = resp.json()
    assert [s["email"] for s in team["staff"]] == ["new_scout@test.com"]
    assert team["invitations"] == []

    # Owner was notified of the join (account family → owner only)
    resp = await client.get("/notifications", headers=_auth_headers(owner))
    assert any(n["type"] == "STAFF_INVITATION" for n in resp.json()["items"])

    # Club-scoped audit trail exists for both steps
    from app.audit.models import AuditEvent
    events = (await db.execute(select(AuditEvent).where(AuditEvent.entity_type == "CLUB"))).scalars().all()
    actions = {e.action for e in events}
    assert {"STAFF_INVITED", "STAFF_JOINED"} <= actions

    # Token is single-use: preview and accept both 404 now
    assert (await client.get(f"/auth/invitations/{token}")).status_code == 404
    resp = await client.post(f"/auth/invitations/{token}/accept", json={"password": "again123"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_team_manage_is_owner_only(client: AsyncClient, db, owner: dict):
    from tests.test_capabilities import _create_staff

    sd = await _create_staff(client, db, _auth_headers(owner), "team_sd@test.com", "SPORTING_DIRECTOR")
    headers = _auth_headers(sd)

    assert (await client.get("/clubs/me/staff", headers=headers)).status_code == 403
    resp = await client.post(
        "/clubs/me/staff/invitations", json={"email": "x@test.com", "role": "SCOUT"}, headers=headers
    )
    assert resp.status_code == 403


# ── Token security ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_unknown_token_404s(client: AsyncClient):
    assert (await client.get("/auth/invitations/not-a-real-token")).status_code == 404
    resp = await client.post("/auth/invitations/not-a-real-token/accept", json={"password": "x12345678"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_revoked_token_404s(client: AsyncClient, owner: dict):
    data = await _invite(client, owner, "revokee@test.com")
    token = _token_from(data["accept_url"])
    inv_id = data["invitation"]["id"]

    resp = await client.delete(f"/clubs/me/staff/invitations/{inv_id}", headers=_auth_headers(owner))
    assert resp.status_code == 204

    assert (await client.get(f"/auth/invitations/{token}")).status_code == 404
    resp = await client.post(f"/auth/invitations/{token}/accept", json={"password": "x12345678"})
    assert resp.status_code == 404

    # Revoked invitation no longer shows as pending
    team = (await client.get("/clubs/me/staff", headers=_auth_headers(owner))).json()
    assert team["invitations"] == []


@pytest.mark.asyncio
async def test_expired_token_404s(client: AsyncClient, db, owner: dict):
    from sqlalchemy import select
    from app.clubs.models import ClubStaffInvitation

    data = await _invite(client, owner, "late@test.com")
    token = _token_from(data["accept_url"])

    inv = (await db.execute(select(ClubStaffInvitation))).scalars().first()
    inv.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    await db.commit()

    assert (await client.get(f"/auth/invitations/{token}")).status_code == 404
    resp = await client.post(f"/auth/invitations/{token}/accept", json={"password": "x12345678"})
    assert resp.status_code == 404


# ── Conflict paths ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_invite_existing_email_409s_case_insensitively(client: AsyncClient, owner: dict):
    # team_owner@test.com exists (the owner) — invite differs only by case.
    resp = await client.post(
        "/clubs/me/staff/invitations",
        json={"email": "Team_Owner@Test.com", "role": "SCOUT"},
        headers=_auth_headers(owner),
    )
    assert resp.status_code == 409
    assert "already has a TransferX account" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_duplicate_pending_invitation_409s(client: AsyncClient, owner: dict):
    await _invite(client, owner, "dupe@test.com")
    resp = await client.post(
        "/clubs/me/staff/invitations",
        json={"email": "Dupe@test.com", "role": "MANAGER"},
        headers=_auth_headers(owner),
    )
    assert resp.status_code == 409
    assert "pending invitation" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_two_clubs_same_email_second_accept_409s(client: AsyncClient, owner: dict):
    other = await _register(client, "team_owner2@test.com", club_name="Rival FC")
    inv_a = await _invite(client, owner, "wanted@test.com")
    inv_b = await _invite(client, other, "wanted@test.com")  # both creates succeed

    resp = await client.post(
        f"/auth/invitations/{_token_from(inv_a['accept_url'])}/accept",
        json={"password": "first123"},
    )
    assert resp.status_code == 201, resp.text

    # The email now belongs to a User — the second club's token dies at accept.
    resp = await client.post(
        f"/auth/invitations/{_token_from(inv_b['accept_url'])}/accept",
        json={"password": "second123"},
    )
    assert resp.status_code == 409


# ── Role change + removal (D10) ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_role_change_reflected_in_membership(client: AsyncClient, owner: dict):
    data = await _invite(client, owner, "promotee@test.com", "SCOUT")
    accept = await client.post(
        f"/auth/invitations/{_token_from(data['accept_url'])}/accept",
        json={"password": "pass1234"},
    )
    staff_tokens = accept.json()

    team = (await client.get("/clubs/me/staff", headers=_auth_headers(owner))).json()
    staff_id = team["staff"][0]["id"]

    resp = await client.patch(
        f"/clubs/me/staff/{staff_id}",
        json={"role": "SPORTING_DIRECTOR"},
        headers=_auth_headers(owner),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["role"] == "SPORTING_DIRECTOR"

    membership = (await client.get("/clubs/me/membership", headers=_auth_headers(staff_tokens))).json()
    assert membership["role"] == "SPORTING_DIRECTOR"
    assert "CLUB_ADMIN" in membership["capabilities"]


@pytest.mark.asyncio
async def test_removal_deactivates_user_immediately(client: AsyncClient, db, owner: dict):
    data = await _invite(client, owner, "leaver@test.com", "MANAGER")
    accept = await client.post(
        f"/auth/invitations/{_token_from(data['accept_url'])}/accept",
        json={"password": "pass1234"},
    )
    staff_tokens = accept.json()
    assert (await client.get("/clubs/me/membership", headers=_auth_headers(staff_tokens))).status_code == 200

    team = (await client.get("/clubs/me/staff", headers=_auth_headers(owner))).json()
    staff_id = team["staff"][0]["id"]
    resp = await client.delete(f"/clubs/me/staff/{staff_id}", headers=_auth_headers(owner))
    assert resp.status_code == 204

    # Next request with the still-live JWT → 401 (user deactivated, D10)
    assert (await client.get("/clubs/me/membership", headers=_auth_headers(staff_tokens))).status_code == 401
    # And login is dead too
    resp = await client.post("/auth/login", json={"email": "leaver@test.com", "password": "pass1234"})
    assert resp.status_code == 401

    # Staff row is gone from the owner's view
    team = (await client.get("/clubs/me/staff", headers=_auth_headers(owner))).json()
    assert team["staff"] == []

    # Removing a nonexistent staff row (e.g. "yourself") → 404
    resp = await client.delete(f"/clubs/me/staff/{uuid.uuid4()}", headers=_auth_headers(owner))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_staff_of_other_club_not_manageable(client: AsyncClient, owner: dict):
    other = await _register(client, "team_owner3@test.com", club_name="Other FC")
    data = await _invite(client, other, "theirs@test.com", "SCOUT")
    await client.post(
        f"/auth/invitations/{_token_from(data['accept_url'])}/accept", json={"password": "pass1234"}
    )
    their_team = (await client.get("/clubs/me/staff", headers=_auth_headers(other))).json()
    their_staff_id = their_team["staff"][0]["id"]

    # A different club's owner can neither see nor touch them.
    resp = await client.patch(
        f"/clubs/me/staff/{their_staff_id}", json={"role": "MANAGER"}, headers=_auth_headers(owner)
    )
    assert resp.status_code == 404
    resp = await client.delete(f"/clubs/me/staff/{their_staff_id}", headers=_auth_headers(owner))
    assert resp.status_code == 404
