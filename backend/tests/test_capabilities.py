"""TRA-151/TRA-146 — club role capabilities + staff deal access.

Matrix-driven permission tests: each staff role against each capability class,
the GET /clubs/me/membership contract, the D4 regression (READONLY staff with
deal visibility gets 403 on every DEAL_WRITE endpoint), and staff deal reads.
"""

import uuid
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient

from tests.conftest import _auth_headers, _register


# ── Fixtures / helpers ────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def club_a(client: AsyncClient) -> dict:
    return await _register(client, "cap_owner_a@test.com", club_name="Cap Club A")


@pytest_asyncio.fixture
async def club_b(client: AsyncClient) -> dict:
    return await _register(client, "cap_owner_b@test.com", club_name="Cap Club B")


async def _get_club_id(client: AsyncClient, headers: dict) -> str:
    resp = await client.get("/clubs/me", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


async def _create_staff(
    client: AsyncClient, db, owner_headers: dict, email: str, role: str
) -> dict:
    """Insert a User + ClubStaff row for the owner's club, return login tokens."""
    from app.auth import service as auth_service
    from app.auth.models import User, UserType
    from app.clubs.models import ClubStaff, StaffRole

    club_id = await _get_club_id(client, owner_headers)
    user = User(
        email=email,
        hashed_password=auth_service.hash_password("password123"),
        user_type=UserType.CLUB,
    )
    db.add(user)
    await db.flush()
    db.add(ClubStaff(club_id=uuid.UUID(club_id), user_id=user.id, role=StaffRole(role)))
    await db.commit()

    resp = await client.post(
        "/auth/login", json={"email": email, "password": "password123"}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _give_budget(db, amount: Decimal = Decimal("100000000")):
    from sqlalchemy import select
    from app.clubs.models import ClubFinance

    result = await db.execute(select(ClubFinance))
    for f in result.scalars():
        f.transfer_budget_total = amount
    await db.commit()


async def _create_player_for(client: AsyncClient, headers: dict, name: str) -> dict:
    resp = await client.post("/players", json={"name": name, "position": "FWD"}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_deal(client: AsyncClient, buyer: dict, seller: dict, db) -> dict:
    """Offer → accept → deal, between club_a (buyer) and club_b (seller)."""
    await _give_budget(db)
    sel_headers = _auth_headers(seller)
    buy_headers = _auth_headers(buyer)
    player = await _create_player_for(client, sel_headers, "Cap Deal Player")
    seller_club_id = await _get_club_id(client, sel_headers)

    offer_resp = await client.post(
        "/offers",
        json={"player_id": player["id"], "to_club_id": seller_club_id, "fee_amount": 5_000_000},
        headers=buy_headers,
    )
    assert offer_resp.status_code == 201, offer_resp.text
    deal_resp = await client.post(
        f"/offers/{offer_resp.json()['id']}/accept", headers=sel_headers
    )
    assert deal_resp.status_code == 200, deal_resp.text
    return deal_resp.json()


# ── Membership endpoint (D3) ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_membership_owner_has_all_capabilities(client: AsyncClient, club_a: dict):
    resp = await client.get("/clubs/me/membership", headers=_auth_headers(club_a))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["role"] == "OWNER"
    assert data["club"]["name"] == "Cap Club A"
    assert set(data["capabilities"]) == {
        "APPROVE_ACTIONS", "CLUB_ADMIN", "DEAL_WRITE",
        "MARKET_WRITE", "SCOUTING_WRITE", "TEAM_MANAGE",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "role,expected",
    [
        (
            "SPORTING_DIRECTOR",
            {"SCOUTING_WRITE", "MARKET_WRITE", "DEAL_WRITE", "CLUB_ADMIN", "APPROVE_ACTIONS"},
        ),
        ("MANAGER", {"SCOUTING_WRITE", "MARKET_WRITE", "DEAL_WRITE"}),
        ("SCOUT", {"SCOUTING_WRITE"}),
        ("READONLY", set()),
    ],
)
async def test_membership_per_staff_role(
    client: AsyncClient, db, club_a: dict, role: str, expected: set
):
    staff = await _create_staff(client, db, _auth_headers(club_a), f"cap_{role.lower()}@test.com", role)
    resp = await client.get("/clubs/me/membership", headers=_auth_headers(staff))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["role"] == role
    assert set(data["capabilities"]) == expected


@pytest.mark.asyncio
async def test_membership_404_without_club(client: AsyncClient, db):
    from app.auth import service as auth_service
    from app.auth.models import User

    user = User(email="cap_noclub@test.com", hashed_password=auth_service.hash_password("password123"))
    db.add(user)
    await db.commit()
    tokens = (
        await client.post("/auth/login", json={"email": "cap_noclub@test.com", "password": "password123"})
    ).json()
    resp = await client.get("/clubs/me/membership", headers=_auth_headers(tokens))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_membership_401_unauthenticated(client: AsyncClient):
    resp = await client.get("/clubs/me/membership")
    assert resp.status_code in (401, 403)  # HTTPBearer returns 403 without header


# ── MARKET_WRITE matrix ───────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "role,allowed",
    [("SPORTING_DIRECTOR", True), ("MANAGER", True), ("SCOUT", False), ("READONLY", False)],
)
async def test_market_write_offer_matrix(
    client: AsyncClient, db, club_a: dict, club_b: dict, role: str, allowed: bool
):
    """Staff of club A make an offer for a club-B player — MANAGER and above only."""
    await _give_budget(db)
    sel_headers = _auth_headers(club_b)
    player = await _create_player_for(client, sel_headers, f"Target {role}")
    seller_club_id = await _get_club_id(client, sel_headers)
    staff = await _create_staff(client, db, _auth_headers(club_a), f"cap_mw_{role.lower()}@test.com", role)

    resp = await client.post(
        "/offers",
        json={"player_id": player["id"], "to_club_id": seller_club_id, "fee_amount": 1_000_000},
        headers=_auth_headers(staff),
    )
    if allowed:
        assert resp.status_code == 201, resp.text
    else:
        assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_market_write_squad_edit_gate(client: AsyncClient, db, club_a: dict):
    """PATCH /clubs/me/players/{id}: READONLY 403s at the gate; MANAGER passes it
    (404 for an unknown player proves the capability check was cleared)."""
    readonly = await _create_staff(client, db, _auth_headers(club_a), "cap_sq_ro@test.com", "READONLY")
    manager = await _create_staff(client, db, _auth_headers(club_a), "cap_sq_mgr@test.com", "MANAGER")
    dummy = str(uuid.uuid4())

    resp = await client.patch(
        f"/clubs/me/players/{dummy}", json={"open_to_offers": True}, headers=_auth_headers(readonly)
    )
    assert resp.status_code == 403
    resp = await client.patch(
        f"/clubs/me/players/{dummy}", json={"open_to_offers": True}, headers=_auth_headers(manager)
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_market_write_offer_message_gate(client: AsyncClient, db, club_a: dict):
    """Offer negotiation messages speak for the club — READONLY 403s (previously ungated)."""
    readonly = await _create_staff(client, db, _auth_headers(club_a), "cap_msg_ro@test.com", "READONLY")
    resp = await client.post(
        f"/offers/{uuid.uuid4()}/messages", json={"body": "hello"}, headers=_auth_headers(readonly)
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_market_write_player_create_gate(client: AsyncClient, db, club_a: dict):
    """POST /players (squad management) — SCOUT/READONLY 403, MANAGER 201."""
    scout = await _create_staff(client, db, _auth_headers(club_a), "cap_pc_scout@test.com", "SCOUT")
    manager = await _create_staff(client, db, _auth_headers(club_a), "cap_pc_mgr@test.com", "MANAGER")

    resp = await client.post(
        "/players", json={"name": "Scout Created", "position": "MID"}, headers=_auth_headers(scout)
    )
    assert resp.status_code == 403
    resp = await client.post(
        "/players", json={"name": "Manager Created", "position": "MID"}, headers=_auth_headers(manager)
    )
    assert resp.status_code == 201, resp.text


# ── SCOUTING_WRITE matrix ─────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "role,allowed",
    [("SPORTING_DIRECTOR", True), ("MANAGER", True), ("SCOUT", True), ("READONLY", False)],
)
async def test_scouting_write_matrix(client: AsyncClient, db, club_a: dict, role: str, allowed: bool):
    staff = await _create_staff(client, db, _auth_headers(club_a), f"cap_sc_{role.lower()}@test.com", role)
    headers = _auth_headers(staff)

    resp = await client.post("/scouting/shortlists", json={"name": f"{role} list"}, headers=headers)
    if allowed:
        assert resp.status_code == 201, resp.text
    else:
        assert resp.status_code == 403, resp.text

    # Viewing comes with membership itself — every role can list shortlists.
    resp = await client.get("/scouting/shortlists", headers=headers)
    assert resp.status_code == 200, resp.text


# ── CLUB_ADMIN matrix ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "role,allowed",
    [("SPORTING_DIRECTOR", True), ("MANAGER", False), ("SCOUT", False), ("READONLY", False)],
)
async def test_club_admin_profile_edit_matrix(
    client: AsyncClient, db, club_a: dict, role: str, allowed: bool
):
    staff = await _create_staff(client, db, _auth_headers(club_a), f"cap_ca_{role.lower()}@test.com", role)
    resp = await client.patch("/clubs/me", json={"city": "Roleville"}, headers=_auth_headers(staff))
    if allowed:
        assert resp.status_code == 200, resp.text
        assert resp.json()["city"] == "Roleville"
    else:
        assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_club_admin_verification_request_matrix(client: AsyncClient, db, club_a: dict):
    sd = await _create_staff(client, db, _auth_headers(club_a), "cap_vr_sd@test.com", "SPORTING_DIRECTOR")
    manager = await _create_staff(client, db, _auth_headers(club_a), "cap_vr_mgr@test.com", "MANAGER")

    resp = await client.post(
        "/verification/requests", json={"notes": "please"}, headers=_auth_headers(sd)
    )
    assert resp.status_code == 201, resp.text
    resp = await client.post(
        "/verification/requests", json={"notes": "please"}, headers=_auth_headers(manager)
    )
    assert resp.status_code == 403, resp.text
    # Reads come with membership: staff see the club's verification requests.
    resp = await client.get("/verification/requests/mine", headers=_auth_headers(manager))
    assert resp.status_code == 200
    assert len(resp.json()) == 1


# ── Staff deal access (TRA-146 / P2) ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_staff_can_read_their_clubs_deal(
    client: AsyncClient, db, club_a: dict, club_b: dict
):
    deal = await _create_deal(client, club_a, club_b, db)
    staff = await _create_staff(client, db, _auth_headers(club_a), "cap_deal_ro@test.com", "READONLY")
    headers = _auth_headers(staff)

    # Deal list + detail
    resp = await client.get("/deals", headers=headers)
    assert resp.status_code == 200
    assert any(d["id"] == deal["id"] for d in resp.json()["items"])
    resp = await client.get(f"/deals/{deal['id']}", headers=headers)
    assert resp.status_code == 200, resp.text

    # Deal room reads
    resp = await client.get(f"/deals/{deal['id']}/comments", headers=headers)
    assert resp.status_code == 200
    resp = await client.get(f"/deals/{deal['id']}/versions", headers=headers)
    assert resp.status_code == 200
    resp = await client.get(f"/deals/{deal['id']}/attachments", headers=headers)
    assert resp.status_code == 200

    # Audit log + CSV export
    resp = await client.get(f"/deals/{deal['id']}/audit-log", headers=headers)
    assert resp.status_code == 200
    resp = await client.get(f"/deals/{deal['id']}/audit-log/export.csv", headers=headers)
    assert resp.status_code == 200

    # Medical-check / personal-terms GETs: 404 (none exist yet) proves the
    # participant gate passed — a scoping failure would be 403.
    resp = await client.get(f"/deals/{deal['id']}/medical-check", headers=headers)
    assert resp.status_code == 404
    resp = await client.get(f"/deals/{deal['id']}/personal-terms", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_unrelated_staff_still_forbidden(
    client: AsyncClient, db, club_a: dict, club_b: dict
):
    deal = await _create_deal(client, club_a, club_b, db)
    outsider = await _register(client, "cap_outsider@test.com", club_name="Cap Outsider FC")
    out_staff = await _create_staff(client, db, _auth_headers(outsider), "cap_out_mgr@test.com", "MANAGER")
    headers = _auth_headers(out_staff)

    assert (await client.get(f"/deals/{deal['id']}", headers=headers)).status_code == 403
    assert (await client.get(f"/deals/{deal['id']}/comments", headers=headers)).status_code == 403
    assert (await client.get(f"/deals/{deal['id']}/audit-log", headers=headers)).status_code == 403


# ── The D4 regression ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_d4_readonly_staff_403_on_every_deal_write(
    client: AsyncClient, db, club_a: dict, club_b: dict
):
    """READONLY staff can see the deal (P2) but every DEAL_WRITE endpoint 403s.
    This is the sequencing invariant that makes TRA-146 safe to ship."""
    deal = await _create_deal(client, club_a, club_b, db)
    staff = await _create_staff(client, db, _auth_headers(club_a), "cap_d4_ro@test.com", "READONLY")
    headers = _auth_headers(staff)
    deal_id = deal["id"]

    # Visibility is there…
    assert (await client.get(f"/deals/{deal_id}", headers=headers)).status_code == 200

    # …but every write 403s.
    writes = [
        ("POST", f"/deals/{deal_id}/advance", None),
        ("POST", f"/deals/{deal_id}/collapse", None),
        ("PATCH", f"/deals/{deal_id}", {"notes": "sneaky"}),
        ("POST", f"/deals/{deal_id}/notes", {"body": "note"}),
        ("POST", f"/deals/{deal_id}/clauses", {
            "clause_type": "APPEARANCE", "trigger_description": "x", "amount": 1000
        }),
        ("PATCH", f"/deals/{deal_id}/clauses/{uuid.uuid4()}/status", {"status": "TRIGGERED"}),
        ("POST", f"/deals/{deal_id}/instalments", {"instalments": [
            {"due_date": "2027-01-01", "amount": 1000}
        ]}),
        ("PATCH", f"/deals/{deal_id}/instalments/{uuid.uuid4()}/paid", None),
        ("PUT", f"/deals/{deal_id}/personal-terms", {"wage_weekly": 1000}),
        ("POST", f"/deals/{deal_id}/agent-negotiation/club-respond", {"agreement": "AGREED"}),
        ("POST", f"/deals/{deal_id}/comments", {"body": "hello"}),
    ]
    for method, url, body in writes:
        resp = await client.request(method, url, json=body, headers=headers)
        assert resp.status_code == 403, f"{method} {url} → {resp.status_code}: {resp.text}"

    # Attachment upload (multipart, not json)
    resp = await client.post(
        f"/deals/{deal_id}/attachments",
        files={"file": ("t.pdf", b"%PDF-1.4", "application/pdf")},
        headers=headers,
    )
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_manager_staff_can_write_to_deal(
    client: AsyncClient, db, club_a: dict, club_b: dict
):
    """MANAGER staff of a participant club can act in the deal room."""
    deal = await _create_deal(client, club_a, club_b, db)
    staff = await _create_staff(client, db, _auth_headers(club_a), "cap_mgr_deal@test.com", "MANAGER")
    headers = _auth_headers(staff)

    resp = await client.post(
        f"/deals/{deal['id']}/comments", json={"body": "manager here"}, headers=headers
    )
    assert resp.status_code == 201, resp.text
    # Comment is labeled with the club's name, not a generic "Club".
    assert resp.json()["author_label"] == "Cap Club A"

    resp = await client.post(
        f"/deals/{deal['id']}/notes", json={"body": "internal note"}, headers=headers
    )
    assert resp.status_code == 201, resp.text


# ── Edge cases ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_removed_staff_loses_access_next_request(client: AsyncClient, db, club_a: dict):
    from sqlalchemy import delete as sa_delete
    from app.clubs.models import ClubStaff

    staff = await _create_staff(client, db, _auth_headers(club_a), "cap_gone@test.com", "MANAGER")
    headers = _auth_headers(staff)
    assert (await client.get("/clubs/me/membership", headers=headers)).status_code == 200

    await db.execute(sa_delete(ClubStaff))
    await db.commit()

    # Valid JWT, but membership checks hit the DB per request.
    assert (await client.get("/clubs/me/membership", headers=headers)).status_code == 404
    resp = await client.post("/scouting/shortlists", json={"name": "x"}, headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_deactivated_staff_user_401s(client: AsyncClient, db, club_a: dict):
    from sqlalchemy import select
    from app.auth.models import User

    staff = await _create_staff(client, db, _auth_headers(club_a), "cap_deact@test.com", "MANAGER")
    headers = _auth_headers(staff)
    assert (await client.get("/clubs/me/membership", headers=headers)).status_code == 200

    result = await db.execute(select(User).where(User.email == "cap_deact@test.com"))
    result.scalar_one().is_active = False
    await db.commit()

    assert (await client.get("/clubs/me/membership", headers=headers)).status_code == 401


@pytest.mark.asyncio
async def test_superuser_bypass_beats_role_matrix(
    client: AsyncClient, db, club_a: dict, club_b: dict
):
    """A superuser who is also READONLY staff is never blocked — bypass first."""
    from sqlalchemy import select
    from app.auth.models import User

    deal = await _create_deal(client, club_a, club_b, db)
    staff = await _create_staff(client, db, _auth_headers(club_a), "cap_super_ro@test.com", "READONLY")
    result = await db.execute(select(User).where(User.email == "cap_super_ro@test.com"))
    result.scalar_one().is_superuser = True
    await db.commit()

    resp = await client.post(
        f"/deals/{deal['id']}/comments", json={"body": "platform staff"},
        headers=_auth_headers(staff),
    )
    assert resp.status_code == 201, resp.text


@pytest.mark.asyncio
async def test_player_and_agent_accounts_unaffected(client: AsyncClient, db, club_a: dict, club_b: dict):
    """Non-club account types see no behaviour change from the capability layer:
    a mandated agent (no club membership) can still write to the deal room."""
    deal = await _create_deal(client, club_a, club_b, db)

    agent_resp = await client.post("/auth/register", json={
        "email": "cap_agent@test.com", "password": "password123", "user_type": "AGENT",
        "display_name": "Cap Agent", "agency_name": "Cap Agency", "country": "England",
    })
    assert agent_resp.status_code == 201, agent_resp.text
    agent_headers = _auth_headers(agent_resp.json())

    # Not a participant → still 403 (unchanged from today)
    resp = await client.post(
        f"/deals/{deal['id']}/comments", json={"body": "agent"}, headers=agent_headers
    )
    assert resp.status_code == 403

    # Invite the agent into the deal (mandate-less invitation row directly)
    from sqlalchemy import select
    from app.agents.models import AgentDealInvitation
    from app.auth.models import AgentProfile, User

    result = await db.execute(
        select(AgentProfile).join(User, User.id == AgentProfile.user_id).where(User.email == "cap_agent@test.com")
    )
    profile = result.scalar_one()
    db.add(AgentDealInvitation(deal_id=uuid.UUID(deal["id"]), agent_id=profile.id))
    await db.commit()

    resp = await client.post(
        f"/deals/{deal['id']}/comments", json={"body": "agent"}, headers=agent_headers
    )
    assert resp.status_code == 201, resp.text


# ── Notification routing (TRA-152 / P3) ──────────────────────────────────────


async def _notifications_for(client: AsyncClient, tokens: dict) -> list[dict]:
    resp = await client.get("/notifications", headers=_auth_headers(tokens))
    assert resp.status_code == 200, resp.text
    return resp.json()["items"]


@pytest.mark.asyncio
async def test_deal_event_routes_to_owner_sd_manager_not_scout_readonly(
    client: AsyncClient, db, club_a: dict, club_b: dict
):
    """An offer to club B notifies its owner + SD + MANAGER; SCOUT and READONLY
    staff get nothing (D5)."""
    sd = await _create_staff(client, db, _auth_headers(club_b), "cap_n_sd@test.com", "SPORTING_DIRECTOR")
    manager = await _create_staff(client, db, _auth_headers(club_b), "cap_n_mgr@test.com", "MANAGER")
    scout = await _create_staff(client, db, _auth_headers(club_b), "cap_n_scout@test.com", "SCOUT")
    readonly = await _create_staff(client, db, _auth_headers(club_b), "cap_n_ro@test.com", "READONLY")

    await _give_budget(db)
    sel_headers = _auth_headers(club_b)
    player = await _create_player_for(client, sel_headers, "Routing Target")
    seller_club_id = await _get_club_id(client, sel_headers)

    resp = await client.post(
        "/offers",
        json={"player_id": player["id"], "to_club_id": seller_club_id, "fee_amount": 2_000_000},
        headers=_auth_headers(club_a),
    )
    assert resp.status_code == 201, resp.text

    def _has_offer_notif(items: list[dict]) -> bool:
        return any(n["type"] == "OFFER_RECEIVED" for n in items)

    assert _has_offer_notif(await _notifications_for(client, club_b))
    assert _has_offer_notif(await _notifications_for(client, sd))
    assert _has_offer_notif(await _notifications_for(client, manager))
    assert not _has_offer_notif(await _notifications_for(client, scout))
    assert not _has_offer_notif(await _notifications_for(client, readonly))


@pytest.mark.asyncio
async def test_market_event_reaches_scout_too(client: AsyncClient, db, club_a: dict):
    """PLAYER_AVAILABLE (scouting family) additionally reaches SCOUT staff."""
    from app.notifications import service as notif_service

    scout = await _create_staff(client, db, _auth_headers(club_a), "cap_pa_scout@test.com", "SCOUT")
    readonly = await _create_staff(client, db, _auth_headers(club_a), "cap_pa_ro@test.com", "READONLY")

    # Shortlist a player as the owner, then flip them open_to_offers.
    player = await _create_player_for(client, _auth_headers(club_a), "Watched One")
    sl = await client.post("/scouting/shortlists", json={"name": "Watch"}, headers=_auth_headers(club_a))
    resp = await client.post(
        f"/scouting/shortlists/{sl.json()['id']}/items",
        json={"player_id": player["id"]},
        headers=_auth_headers(club_a),
    )
    assert resp.status_code == 201, resp.text

    await notif_service.notify_player_available(db, uuid.UUID(player["id"]))
    await db.commit()

    def _has(items: list[dict]) -> bool:
        return any(n["type"] == "PLAYER_AVAILABLE" for n in items)

    assert _has(await _notifications_for(client, club_a))
    assert _has(await _notifications_for(client, scout))
    assert not _has(await _notifications_for(client, readonly))


@pytest.mark.asyncio
async def test_preference_optout_still_suppresses_per_recipient(
    client: AsyncClient, db, club_a: dict, club_b: dict
):
    """A MANAGER who opted out of OFFER_RECEIVED gets nothing even though the
    role mapping includes them; the owner still gets theirs."""
    manager = await _create_staff(client, db, _auth_headers(club_b), "cap_opt_mgr@test.com", "MANAGER")
    resp = await client.patch(
        "/notifications/preferences/OFFER_RECEIVED",
        json={"enabled": False},
        headers=_auth_headers(manager),
    )
    assert resp.status_code == 200, resp.text

    await _give_budget(db)
    player = await _create_player_for(client, _auth_headers(club_b), "Optout Target")
    seller_club_id = await _get_club_id(client, _auth_headers(club_b))
    resp = await client.post(
        "/offers",
        json={"player_id": player["id"], "to_club_id": seller_club_id, "fee_amount": 3_000_000},
        headers=_auth_headers(club_a),
    )
    assert resp.status_code == 201, resp.text

    def _has(items: list[dict]) -> bool:
        return any(n["type"] == "OFFER_RECEIVED" for n in items)

    assert _has(await _notifications_for(client, club_b))
    assert not _has(await _notifications_for(client, manager))
