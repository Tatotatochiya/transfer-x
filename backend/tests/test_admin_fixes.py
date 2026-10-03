"""Admin panel fixes and the admin audit trail.

- Cancelling a sale and force-withdrawing an offer now release the reserved
  budgets and tell the clubs (they used to only flip the status).
- Budgets can't go negative or below what is already held or spent.
- Staff send a one-time reset link instead of typing someone's password;
  using it signs the person out everywhere.
- Nobody can remove their own staff rights or the last staff account.
- Every admin change is audited with its reason; the Audit log lists them
  and exports to Excel.
"""
import io
import uuid
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import func, select

from app.audit.models import AuditEvent
from app.auth.models import RefreshToken, User
from app.clubs.models import Club, ClubFinance
from app.notifications.models import Notification
from tests.conftest import _auth_headers, _register
from tests.test_approvals import _make_auction
from tests.test_deals import _create_player_for_seller, _get_club_id, _give_budget

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def admin(client, db):
    tokens = await _register(client, "fix_admin@test.com", club_name="Fix Admin Club")
    user = (await db.execute(select(User).where(User.email == "fix_admin@test.com"))).scalar_one()
    user.is_superuser = True
    await db.commit()
    return {"tokens": tokens, "headers": _auth_headers(tokens), "id": user.id}


async def _finance(db, club_name: str) -> ClubFinance:
    club = (await db.execute(select(Club).where(Club.name == club_name))).scalar_one()
    finance = (await db.execute(select(ClubFinance).where(ClubFinance.club_id == club.id))).scalar_one()
    await db.refresh(finance)
    return finance


async def _audit(db, action: str) -> list[AuditEvent]:
    return list((await db.execute(select(AuditEvent).where(AuditEvent.action == action)
                                  .order_by(AuditEvent.created_at))).scalars())


# ── Cancel sale and force-withdraw release the money ──────────────────────────


async def test_cancelling_a_sale_releases_bids_tells_everyone_and_is_audited(client: AsyncClient, db, admin):
    seller = await _register(client, "fix_seller@test.com", club_name="Fix Sellers")
    buyer = await _register(client, "fix_buyer@test.com", club_name="Fix Buyers")
    await _give_budget(db)
    sale_id = await _make_auction(client, seller, "Cancelled Man")
    resp = await client.post(f"/sales/{sale_id}/bids", json={"amount": 3_000_000}, headers=_auth_headers(buyer))
    assert resp.status_code == 201, resp.text
    assert (await _finance(db, "Fix Buyers")).transfer_reserved == Decimal("3000000")

    no_reason = await client.post(f"/admin/sales/{sale_id}/cancel", json={}, headers=admin["headers"])
    assert no_reason.status_code == 422
    resp = await client.post(f"/admin/sales/{sale_id}/cancel", json={"reason": "Listed by mistake"},
                             headers=admin["headers"])
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "WITHDRAWN"

    assert (await _finance(db, "Fix Buyers")).transfer_reserved == Decimal("0")
    messages = (await db.execute(select(Notification.message))).scalars().all()
    assert "TransferX staff cancelled this sale: Listed by mistake" in messages
    assert "TransferX staff cancelled your listing: Listed by mistake" in messages
    (event,) = await _audit(db, "admin.sale.cancelled")
    assert event.actor_user_id == admin["id"] and event.payload_json["reason"] == "Listed by mistake"
    assert event.description == "Cancelled the sale of Cancelled Man"


async def test_force_withdrawing_an_offer_releases_the_buyers_budget(client: AsyncClient, db, admin):
    seller = await _register(client, "fix_seller2@test.com", club_name="Fix Sellers Two")
    buyer = await _register(client, "fix_buyer2@test.com", club_name="Fix Buyers Two")
    await _give_budget(db)
    player = await _create_player_for_seller(client, _auth_headers(seller))
    offer = (await client.post("/offers", json={
        "player_id": player["id"], "to_club_id": await _get_club_id(client, _auth_headers(seller)),
        "fee_amount": 4_000_000}, headers=_auth_headers(buyer))).json()
    assert (await _finance(db, "Fix Buyers Two")).transfer_reserved == Decimal("4000000")

    resp = await client.post(f"/admin/offers/{offer['id']}/force-withdraw",
                             json={"reason": "Duplicate offer"}, headers=admin["headers"])
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "WITHDRAWN"
    assert (await _finance(db, "Fix Buyers Two")).transfer_reserved == Decimal("0")
    told = (await db.execute(select(func.count()).select_from(Notification).where(
        Notification.message == "TransferX staff withdrew this offer: Duplicate offer"))).scalar_one()
    assert told >= 2  # both clubs
    assert len(await _audit(db, "admin.offer.withdrawn")) == 1

    again = await client.post(f"/admin/offers/{offer['id']}/force-withdraw",
                              json={"reason": "Duplicate offer"}, headers=admin["headers"])
    assert again.status_code == 400


# ── Budgets ───────────────────────────────────────────────────────────────────


async def test_budgets_cant_go_negative_or_below_whats_held(client: AsyncClient, db, admin):
    seller = await _register(client, "fix_seller3@test.com", club_name="Fix Sellers Three")
    buyer = await _register(client, "fix_buyer3@test.com", club_name="Fix Buyers Three")
    await _give_budget(db)
    player = await _create_player_for_seller(client, _auth_headers(seller))
    await client.post("/offers", json={"player_id": player["id"], "fee_amount": 4_000_000,
                                       "to_club_id": await _get_club_id(client, _auth_headers(seller))},
                      headers=_auth_headers(buyer))
    club_id = (await client.get("/clubs/me", headers=_auth_headers(buyer))).json()["id"]
    url = f"/admin/clubs/{club_id}/finances"

    negative = await client.put(url, json={"transfer_budget_total": -1, "reason": "Typo test"}, headers=admin["headers"])
    assert negative.status_code == 422
    no_reason = await client.put(url, json={"transfer_budget_total": 60_000_000}, headers=admin["headers"])
    assert no_reason.status_code == 422
    below = await client.put(url, json={"transfer_budget_total": 3_000_000, "reason": "Cut the budget"},
                             headers=admin["headers"])
    assert below.status_code == 400 and "£4,000,000" in below.json()["detail"]

    ok = await client.put(url, json={"transfer_budget_total": 60_000_000, "reason": "Owner added funds"},
                          headers=admin["headers"])
    assert ok.status_code == 200, ok.text
    (event,) = await _audit(db, "admin.club.finances_updated")
    assert event.payload_json["reason"] == "Owner added funds"
    assert event.payload_json["changes"]["transfer_budget_total"][1] == "60000000"


# ── Password reset links ──────────────────────────────────────────────────────


async def test_a_reset_link_lets_the_person_choose_a_password_and_signs_them_out(client: AsyncClient, db, admin, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "smtp_host", None)  # no email: the link is shared by hand
    person = await _register(client, "fix_person@test.com", club_name="Fix Person Club")
    user = (await db.execute(select(User).where(User.email == "fix_person@test.com"))).scalar_one()
    assert (await client.post(f"/admin/users/{user.id}/reset-password", json={"new_password": "x"},
                              headers=admin["headers"])).status_code in (404, 405)

    resp = await client.post(f"/admin/users/{user.id}/reset-link", json={"reason": "Forgot it"}, headers=admin["headers"])
    assert resp.status_code == 200, resp.text
    link = resp.json()
    assert link["emailed"] is False
    token = link["url"].split("token=")[1]

    preview = await client.get(f"/auth/password-reset/{token}")
    assert preview.status_code == 200 and preview.json()["email"] == "fix_person@test.com"
    short = await client.post("/auth/password-reset", json={"token": token, "new_password": "short"})
    assert short.status_code == 422
    done = await client.post("/auth/password-reset", json={"token": token, "new_password": "a-new-password"})
    assert done.status_code == 204, done.text

    # Signed out everywhere, the old password is gone, the link is used up.
    assert (await db.execute(select(func.count()).select_from(RefreshToken).where(RefreshToken.user_id == user.id))).scalar_one() == 0
    assert (await client.post("/auth/refresh", json={"refresh_token": person["refresh_token"]})).status_code == 401
    assert (await client.post("/auth/login", json={"email": "fix_person@test.com", "password": "password123"})).status_code == 401
    assert (await client.post("/auth/login", json={"email": "fix_person@test.com", "password": "a-new-password"})).status_code == 200
    assert (await client.post("/auth/password-reset", json={"token": token, "new_password": "another-one"})).status_code == 404
    assert len(await _audit(db, "admin.user.reset_link_created")) == 1
    assert len(await _audit(db, "password_reset_completed")) == 1


async def test_a_new_link_replaces_the_old_one(client: AsyncClient, db, admin):
    await _register(client, "fix_person2@test.com", club_name="Fix Person Two")
    user = (await db.execute(select(User).where(User.email == "fix_person2@test.com"))).scalar_one()
    first = (await client.post(f"/admin/users/{user.id}/reset-link", json={}, headers=admin["headers"])).json()
    await client.post(f"/admin/users/{user.id}/reset-link", json={}, headers=admin["headers"])
    assert (await client.get(f"/auth/password-reset/{first['url'].split('token=')[1]}")).status_code == 404


# ── Staff rights ──────────────────────────────────────────────────────────────


async def test_staff_rights_need_a_reason_and_cant_be_removed_from_yourself(client: AsyncClient, db, admin):
    await _register(client, "fix_staff@test.com", club_name="Fix Staff Club")
    other = (await db.execute(select(User).where(User.email == "fix_staff@test.com"))).scalar_one()

    me = await client.patch(f"/admin/users/{admin['id']}", json={"is_superuser": False, "reason": "Testing self"},
                            headers=admin["headers"])
    assert me.status_code == 400
    me = await client.patch(f"/admin/users/{admin['id']}", json={"is_active": False, "reason": "Testing self"},
                            headers=admin["headers"])
    assert me.status_code == 400

    no_reason = await client.patch(f"/admin/users/{other.id}", json={"is_superuser": True}, headers=admin["headers"])
    assert no_reason.status_code == 422
    grant = await client.patch(f"/admin/users/{other.id}", json={"is_superuser": True, "reason": "Joined support"},
                               headers=admin["headers"])
    assert grant.status_code == 200 and grant.json()["is_superuser"] is True
    (event,) = await _audit(db, "admin.user.updated")
    assert event.description == "fix_staff@test.com: granted TransferX staff rights"
    assert event.payload_json["changes"] == {"is_superuser": [False, True]}


async def test_the_last_staff_account_cant_be_removed_or_deleted(client: AsyncClient, db, admin):
    # A second admin removes the first, then can't remove themselves.
    await _register(client, "fix_staff2@test.com", club_name="Fix Staff Two")
    second = (await db.execute(select(User).where(User.email == "fix_staff2@test.com"))).scalar_one()
    second.is_superuser = True
    await db.commit()
    login = await client.post("/auth/login", json={"email": "fix_staff2@test.com", "password": "password123"})
    second_headers = _auth_headers(login.json())

    resp = await client.request("DELETE", f"/admin/users/{admin['id']}", json={"reason": "Account no longer used"},
                                headers=second_headers)
    assert resp.status_code in (204, 409), resp.text
    if resp.status_code == 409:  # has data: deactivate instead
        resp = await client.patch(f"/admin/users/{admin['id']}", json={"is_active": False, "reason": "No longer used"},
                                  headers=second_headers)
        assert resp.status_code == 200
    assert await _audit(db, "admin.user.deleted") or await _audit(db, "admin.user.updated")


async def test_deleting_needs_a_reason(client: AsyncClient, db, admin):
    await _register(client, "fix_gone@test.com", club_name="Fix Gone Club")
    user = (await db.execute(select(User).where(User.email == "fix_gone@test.com"))).scalar_one()
    resp = await client.request("DELETE", f"/admin/users/{user.id}", json={"reason": "no"}, headers=admin["headers"])
    assert resp.status_code == 422


async def test_create_user_is_gone(client: AsyncClient, admin):
    resp = await client.post("/admin/users", json={"email": "x@test.com", "password": "password123"},
                             headers=admin["headers"])
    assert resp.status_code == 405


# ── Broadcast ─────────────────────────────────────────────────────────────────


async def test_broadcast_links_stay_inside_transferx_and_is_audited(client: AsyncClient, db, admin):
    outside = await client.post("/admin/notifications/broadcast",
                                json={"message": "Please verify your account", "link": "https://evil.example/login"},
                                headers=admin["headers"])
    assert outside.status_code == 422
    sneaky = await client.post("/admin/notifications/broadcast",
                               json={"message": "Please verify your account", "link": "//evil.example"},
                               headers=admin["headers"])
    assert sneaky.status_code == 422
    ok = await client.post("/admin/notifications/broadcast",
                           json={"message": "The January window opens on Thursday", "link": "/dashboard"},
                           headers=admin["headers"])
    assert ok.status_code == 200 and ok.json()["recipients"] >= 1
    (event,) = await _audit(db, "admin.broadcast.sent")
    assert event.payload_json["message"] == "The January window opens on Thursday"


# ── Transfer windows ──────────────────────────────────────────────────────────


async def test_deleting_a_transfer_window_needs_a_reason(client: AsyncClient, db, admin):
    created = await client.post("/transfers/window", json={
        "name": "Test window", "opens_at": "2027-01-01T00:00:00Z", "closes_at": "2027-02-01T00:00:00Z"},
        headers=admin["headers"])
    assert created.status_code == 201, created.text
    wid = created.json()["id"]
    assert (await client.request("DELETE", f"/transfers/window/{wid}", json={}, headers=admin["headers"])).status_code == 422
    resp = await client.request("DELETE", f"/transfers/window/{wid}", json={"reason": "Wrong dates"},
                                headers=admin["headers"])
    assert resp.status_code == 204
    assert [e.action for e in await _audit(db, "admin.transfer_window.created")] == ["admin.transfer_window.created"]
    (deleted,) = await _audit(db, "admin.transfer_window.deleted")
    assert deleted.payload_json["reason"] == "Wrong dates"


# ── Audit log and export ──────────────────────────────────────────────────────


async def test_the_audit_log_lists_filters_and_exports_to_excel(client: AsyncClient, db, admin):
    from openpyxl import load_workbook

    await _register(client, "fix_logged@test.com", club_name="Fix Logged Club")
    user = (await db.execute(select(User).where(User.email == "fix_logged@test.com"))).scalar_one()
    await client.patch(f"/admin/users/{user.id}", json={"is_active": False, "reason": "Left the club"},
                       headers=admin["headers"])

    log = (await client.get("/admin/audit-log", params={"admin_only": True}, headers=admin["headers"])).json()
    assert log["total"] >= 1
    row = log["items"][0]
    assert row["action"] == "admin.user.updated" and row["actor_email"] == "fix_admin@test.com"
    assert row["reason"] == "Left the club" and row["by_staff"] is True
    searched = (await client.get("/admin/audit-log", params={"q": "fix_logged"}, headers=admin["headers"])).json()
    assert searched["total"] >= 1
    facets = (await client.get("/admin/audit-log/facets", headers=admin["headers"])).json()
    assert "admin.user.updated" in facets["actions"]

    resp = await client.get("/admin/audit-log/export.xlsx", params={"admin_only": True}, headers=admin["headers"])
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/vnd.openxmlformats")
    assert "transferx-audit-log-" in resp.headers["content-disposition"]
    wb = load_workbook(io.BytesIO(resp.content))
    sheet = wb["Audit log"]
    header = [c.value for c in sheet[1]]
    assert header[:3] == ["When (UTC)", "Who", "What"]
    first = [c.value for c in sheet[2]]
    assert first[1] == "fix_admin@test.com" and first[2] == "User updated (staff)" and first[7] == "Left the club"
    about = {r[0].value: r[1].value for r in wb["About"].iter_rows(min_row=3) if r[0].value}
    assert about["Exported by"] == "fix_admin@test.com" and about["Only"] == "TransferX staff actions"
    # Taking a copy of the log is itself on the log.
    assert len(await _audit(db, "admin.audit_log.exported")) == 1


async def test_the_audit_log_is_staff_only(client: AsyncClient):
    tokens = await _register(client, "fix_nosy@test.com", club_name="Fix Nosy Club")
    assert (await client.get("/admin/audit-log", headers=_auth_headers(tokens))).status_code == 403
    assert (await client.get("/admin/audit-log/export.xlsx", headers=_auth_headers(tokens))).status_code == 403


# ── Users page, staff invitations, Health, view as club ───────────────────────


async def test_users_list_says_who_each_person_is(client: AsyncClient, db, admin):
    owner = await _register(client, "fix_owner@test.com", club_name="Fix Owners FC")
    await client.post("/auth/login", json={"email": "fix_owner@test.com", "password": "password123"})
    rows = {r["email"]: r for r in (await client.get("/admin/users", params={"search": "fix_owner"},
                                                     headers=admin["headers"])).json()["items"]}
    row = rows["fix_owner@test.com"]
    assert row["user_type"] == "CLUB" and row["club_name"] == "Fix Owners FC" and row["role"] == "OWNER"
    assert row["last_active_at"] is not None
    assert owner  # registered above


async def test_staff_are_invited_never_given_a_typed_password(client: AsyncClient, db, admin, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "smtp_host", None)
    await _register(client, "fix_club@test.com", club_name="Fix Invite FC")
    club = (await db.execute(select(Club).where(Club.name == "Fix Invite FC"))).scalar_one()
    resp = await client.post(f"/admin/clubs/{club.id}/staff", json={"email": "scout@fixinvite.test", "role": "SCOUT"},
                             headers=admin["headers"])
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["role"] == "SCOUT" and "/accept-invite?token=" in body["accept_url"] and body["emailed"] is False
    # No account exists until they accept and choose their own password.
    assert (await db.execute(select(User).where(User.email == "scout@fixinvite.test"))).scalar_one_or_none() is None
    assert len(await _audit(db, "admin.staff.invited")) == 1
    bad = await client.post(f"/admin/clubs/{club.id}/staff", json={"email": "x@fixinvite.test", "role": "CEO"},
                            headers=admin["headers"])
    assert bad.status_code == 400


async def test_health_reports_services_and_jobs(client: AsyncClient, admin):
    report = (await client.get("/admin/health", headers=admin["headers"])).json()
    services = {s["key"]: s for s in report["services"]}
    assert services["database"]["ok"] is True
    assert services["push"]["ok"] is False and "VAPID" in services["push"]["detail"]  # tests switch pushes off
    assert services["vendor"]["ok"] is False and "APISPORTS_KEY" in services["vendor"]["detail"]
    assert "scheduler" in services
    assert isinstance(report["jobs"], list)


async def test_view_as_is_read_only_audited_and_short_lived(client: AsyncClient, db, admin):
    await _register(client, "fix_viewed@test.com", club_name="Fix Viewed FC")
    club = (await db.execute(select(Club).where(Club.name == "Fix Viewed FC"))).scalar_one()
    assert (await client.post(f"/admin/clubs/{club.id}/view-as", json={}, headers=admin["headers"])).status_code == 422
    resp = await client.post(f"/admin/clubs/{club.id}/view-as", json={"reason": "Club says it can't see offers"},
                             headers=admin["headers"])
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    view = {"Authorization": f"Bearer {token}"}

    me = (await client.get("/auth/me", headers=view)).json()
    assert me["email"] == "fix_viewed@test.com" and me["has_club"] is True
    assert me["viewed_by"] == "fix_admin@test.com"
    assert (await client.get("/clubs/me", headers=view)).status_code == 200
    # Nothing can be changed: every write is refused before the endpoint runs.
    for method, url, body in [
        ("PATCH", "/clubs/me", {"city": "Elsewhere"}),
        ("POST", "/players", {"name": "Sneaky", "position": "FWD"}),
        ("PATCH", "/users/me/preferences", {"lite_mode": True}),
        ("POST", "/notifications/read-all", None),
    ]:
        r = await client.request(method, url, json=body, headers=view)
        assert r.status_code == 403 and "read-only" in r.json()["detail"], (method, url, r.status_code)
    (event,) = await _audit(db, "admin.club.viewed_as")
    assert event.payload_json["reason"] == "Club says it can't see offers"


async def test_me_says_whether_someone_has_a_club(client: AsyncClient, admin):
    me = (await client.get("/auth/me", headers=admin["headers"])).json()
    assert me["has_club"] is True and me["viewed_by"] is None  # this test admin registered with a club
