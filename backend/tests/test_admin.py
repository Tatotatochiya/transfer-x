"""Admin endpoint tests — M7."""

import uuid
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from tests.conftest import _auth_headers, _register

pytestmark = pytest.mark.asyncio


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def superuser(client, db):
    """Register a user then promote to superuser directly in DB."""
    tokens = await _register(client, "admin@test.com", club_name="Admin Club")
    from app.auth.models import User

    result = await db.execute(select(User).where(User.email == "admin@test.com"))
    user = result.scalar_one()
    user.is_superuser = True
    await db.commit()
    return tokens


@pytest_asyncio.fixture
async def regular_user(client):
    return await _register(client, "regular@test.com", club_name="Regular Club")


def _su_headers(tokens: dict) -> dict:
    return _auth_headers(tokens)


# ── Tests ─────────────────────────────────────────────────────────────────────


async def test_admin_requires_superuser(client: AsyncClient, regular_user: dict):
    resp = await client.get("/admin/stats", headers=_auth_headers(regular_user))
    assert resp.status_code == 403


async def test_admin_stats(client: AsyncClient, superuser: dict):
    resp = await client.get("/admin/stats", headers=_su_headers(superuser))
    assert resp.status_code == 200
    data = resp.json()
    for key in ("total_users", "total_clubs", "total_players", "active_sales", "open_offers", "active_deals"):
        assert key in data
        assert isinstance(data[key], int)
        assert data[key] >= 0


async def test_list_users(client: AsyncClient, superuser: dict):
    resp = await client.get("/admin/users", headers=_su_headers(superuser))
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1
    assert isinstance(data["items"], list)


async def test_list_users_search(client: AsyncClient, superuser: dict):
    resp = await client.get("/admin/users?search=admin", headers=_su_headers(superuser))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    # All returned emails contain "admin"
    for item in data["items"]:
        assert "admin" in item["email"]


async def test_get_user_by_id(client: AsyncClient, superuser: dict, db):
    from app.auth.models import User

    result = await db.execute(select(User).where(User.email == "admin@test.com"))
    user = result.scalar_one()

    resp = await client.get(f"/admin/users/{user.id}", headers=_su_headers(superuser))
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "admin@test.com"
    assert data["is_superuser"] is True


async def test_get_user_not_found(client: AsyncClient, superuser: dict):
    random_id = uuid.uuid4()
    resp = await client.get(f"/admin/users/{random_id}", headers=_su_headers(superuser))
    assert resp.status_code == 404


async def test_update_user_deactivate(client: AsyncClient, superuser: dict, regular_user: dict, db):
    from app.auth.models import User

    result = await db.execute(select(User).where(User.email == "regular@test.com"))
    user = result.scalar_one()

    resp = await client.patch(
        f"/admin/users/{user.id}",
        json={"is_active": False},
        headers=_su_headers(superuser),
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


async def test_list_clubs(client: AsyncClient, superuser: dict):
    resp = await client.get("/admin/clubs", headers=_su_headers(superuser))
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert data["total"] >= 1


async def test_list_clubs_search(client: AsyncClient, superuser: dict):
    resp = await client.get("/admin/clubs?search=Admin", headers=_su_headers(superuser))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    for item in data["items"]:
        assert "admin" in item["name"].lower()


async def test_get_club_detail(client: AsyncClient, superuser: dict, db):
    from app.clubs.models import Club

    result = await db.execute(select(Club).where(Club.name == "Admin Club"))
    club = result.scalar_one()

    resp = await client.get(f"/admin/clubs/{club.id}", headers=_su_headers(superuser))
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Admin Club"
    assert "finance" in data  # may be null but key must exist


async def test_update_club_role(client: AsyncClient, superuser: dict, db):
    from app.clubs.models import Club

    result = await db.execute(select(Club).where(Club.name == "Admin Club"))
    club = result.scalar_one()

    resp = await client.patch(
        f"/admin/clubs/{club.id}",
        json={"role": "BUYER"},
        headers=_su_headers(superuser),
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "BUYER"


async def test_update_club_finances(client: AsyncClient, superuser: dict):
    # Get superuser's club via /clubs/me
    resp = await client.get("/clubs/me", headers=_su_headers(superuser))
    assert resp.status_code == 200
    club_id = resp.json()["id"]

    resp = await client.put(
        f"/admin/clubs/{club_id}/finances",
        json={"transfer_budget_total": 50000000},
        headers=_su_headers(superuser),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert float(data["transfer_budget_total"]) == 50000000.0


async def test_admin_list_players(client: AsyncClient, superuser: dict, db):
    # Create a player via the API
    resp = await client.post(
        "/players",
        json={"name": "Private Player", "age": 25, "position": "FWD", "visibility": "PRIVATE"},
        headers=_su_headers(superuser),
    )
    assert resp.status_code == 201
    player_id = resp.json()["id"]

    # Verify via admin endpoint
    resp = await client.get("/admin/players", headers=_su_headers(superuser))
    assert resp.status_code == 200
    data = resp.json()
    player_ids = [p["id"] for p in data["items"]]
    assert player_id in player_ids


async def test_admin_list_sales(client: AsyncClient, superuser: dict, db):
    from app.clubs.models import Club
    from app.players.models import Player
    from app.sales.service import create_sale
    from app.sales.models import SaleType

    # Get superuser's club
    result = await db.execute(select(Club).where(Club.name == "Admin Club"))
    club = result.scalar_one()

    # Create a player
    from app.players.service import create_player
    player = await create_player(db, created_by_user_id=club.user_id, name="Sale Player")
    await db.flush()

    # Create a sale
    await create_sale(
        db,
        player_id=player.id,
        seller_club_id=club.id,
        sale_type=SaleType.FIXED_PRICE,
    )
    await db.commit()

    resp = await client.get("/admin/sales", headers=_su_headers(superuser))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert isinstance(data["items"], list)


async def test_admin_stats_counts_correctly(client: AsyncClient, superuser: dict, db):
    # Register two more users
    await _register(client, "extra1@test.com", club_name="Extra Club 1")
    await _register(client, "extra2@test.com", club_name="Extra Club 2")

    # Create a player
    resp = await client.post(
        "/players",
        json={"name": "Stats Test Player", "age": 22, "position": "MID"},
        headers=_su_headers(superuser),
    )
    assert resp.status_code == 201

    # Check stats
    resp = await client.get("/admin/stats", headers=_su_headers(superuser))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_users"] >= 2
    assert data["total_players"] >= 1


# ── H1 admin audit: reason-required interventions ──────────────────────────────


async def _give_budget(db, amount=Decimal("50000000")):
    from app.clubs.models import ClubFinance

    result = await db.execute(select(ClubFinance))
    for f in result.scalars():
        f.transfer_budget_total = amount
    await db.commit()


async def test_admin_force_withdraw_offer_requires_reason(client: AsyncClient, superuser: dict, db):
    """Buyer = superuser's own club, seller = a fresh club — cheapest way to get
    a live SENT offer without a dedicated buyer/seller fixture pair in this file."""
    seller = await _register(client, "offer_seller@test.com", club_name="Offer Seller FC")
    sel_headers = _su_headers(seller)
    player_resp = await client.post(
        "/players", json={"name": "Force Withdraw Player", "position": "MID"}, headers=sel_headers,
    )
    assert player_resp.status_code == 201, player_resp.text
    player = player_resp.json()
    seller_club_id = (await client.get("/clubs/me", headers=sel_headers)).json()["id"]

    await _give_budget(db)
    offer_resp = await client.post(
        "/offers",
        json={"player_id": player["id"], "to_club_id": seller_club_id, "fee_amount": 5_000_000},
        headers=_su_headers(superuser),
    )
    assert offer_resp.status_code == 201, offer_resp.text
    offer_id = offer_resp.json()["id"]

    # No reason — must be refused
    resp = await client.post(
        f"/admin/offers/{offer_id}/force-withdraw", json={"reason": ""}, headers=_su_headers(superuser),
    )
    assert resp.status_code == 400
    assert "reason" in resp.json()["detail"].lower()

    # With a reason — must succeed
    resp = await client.post(
        f"/admin/offers/{offer_id}/force-withdraw",
        json={"reason": "Duplicate offer raised in error"},
        headers=_su_headers(superuser),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "WITHDRAWN"


async def test_admin_cancel_sale_requires_reason_and_releases_bid_budget(
    client: AsyncClient, superuser: dict, db,
):
    """C1/C2 were fixed as a necessary side effect of H1: admin_cancel_sale now
    delegates to the real withdraw_sale cleanup instead of assigning a
    SaleStatus member that didn't exist. This pins both: the crash is gone,
    and a bidder's reserved budget is actually released."""
    seller = await _register(client, "cancel_sale_seller@test.com", club_name="Cancel Sale Seller FC")
    sel_headers = _su_headers(seller)
    player_resp = await client.post(
        "/players", json={"name": "Cancel Sale Player", "position": "FWD"}, headers=sel_headers,
    )
    assert player_resp.status_code == 201, player_resp.text
    player = player_resp.json()

    sale_resp = await client.post(
        "/sales",
        json={
            "player_id": player["id"], "sale_type": "AUCTION",
            "asking_price": 5_000_000, "min_increment": 500_000,
        },
        headers=sel_headers,
    )
    assert sale_resp.status_code == 201, sale_resp.text
    sale_id = sale_resp.json()["id"]

    await _give_budget(db)
    bid_resp = await client.post(
        f"/sales/{sale_id}/bids", json={"amount": 5_000_000}, headers=_su_headers(superuser),
    )
    assert bid_resp.status_code == 201, bid_resp.text

    finance_before = (await client.get("/clubs/me", headers=_su_headers(superuser))).json()["finance"]
    assert Decimal(finance_before["transfer_reserved"]) == Decimal("5000000")

    # No reason — must be refused, sale stays OPEN
    resp = await client.post(
        f"/admin/sales/{sale_id}/cancel", json={"reason": ""}, headers=_su_headers(superuser),
    )
    assert resp.status_code == 400
    assert "reason" in resp.json()["detail"].lower()

    # With a reason — must succeed, and the bidder's reservation is released
    resp = await client.post(
        f"/admin/sales/{sale_id}/cancel",
        json={"reason": "Player withdrew from the market"},
        headers=_su_headers(superuser),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "WITHDRAWN"

    finance_after = (await client.get("/clubs/me", headers=_su_headers(superuser))).json()["finance"]
    assert Decimal(finance_after["transfer_reserved"]) == Decimal("0")


async def test_admin_remove_staff_requires_reason(client: AsyncClient, superuser: dict, db):
    from app.clubs.models import Club

    result = await db.execute(select(Club).where(Club.name == "Admin Club"))
    club_id = str(result.scalar_one().id)

    create_resp = await client.post(
        f"/admin/clubs/{club_id}/staff",
        json={"email": "remove_me_staff@test.com", "password": "password123", "role": "READONLY"},
        headers=_su_headers(superuser),
    )
    assert create_resp.status_code == 201, create_resp.text
    staff_id = create_resp.json()["id"]

    # No reason at all — must be refused
    resp = await client.delete(f"/admin/clubs/{club_id}/staff/{staff_id}", headers=_su_headers(superuser))
    assert resp.status_code == 422  # missing required query param

    # Blank reason — must be refused
    resp = await client.delete(
        f"/admin/clubs/{club_id}/staff/{staff_id}?reason=", headers=_su_headers(superuser),
    )
    assert resp.status_code == 400
    assert "reason" in resp.json()["detail"].lower()

    # With a reason — must succeed
    resp = await client.delete(
        f"/admin/clubs/{club_id}/staff/{staff_id}?reason=Account+compromised", headers=_su_headers(superuser),
    )
    assert resp.status_code == 204


# ── H2 admin audit: six-stage deal visibility ───────────────────────────────────


async def _create_deal_via_offer(client: AsyncClient, buyer: dict, seller: dict, db, fee: float = 5_000_000) -> dict:
    await _give_budget(db)
    sel_headers = _su_headers(seller)
    buy_headers = _su_headers(buyer)
    player_resp = await client.post(
        "/players", json={"name": "Stage Test Player", "position": "FWD"}, headers=sel_headers,
    )
    assert player_resp.status_code == 201, player_resp.text
    seller_club_id = (await client.get("/clubs/me", headers=sel_headers)).json()["id"]

    offer_resp = await client.post(
        "/offers",
        json={"player_id": player_resp.json()["id"], "to_club_id": seller_club_id, "fee_amount": fee},
        headers=buy_headers,
    )
    assert offer_resp.status_code == 201, offer_resp.text
    deal_resp = await client.post(f"/offers/{offer_resp.json()['id']}/accept", headers=sel_headers)
    assert deal_resp.status_code == 200, deal_resp.text
    return deal_resp.json()


async def test_deals_by_stage_covers_all_active_stages(client: AsyncClient, superuser: dict, db):
    """H2: AGENT_NEGOTIATION and PERSONAL_TERMS used to be dropped from the
    zero-init dict entirely — a deal parked there was invisible on the
    dashboard pipeline bar and the deals kanban board."""
    from app.admin.service import get_deals_by_stage
    from app.deals.models import Deal, DealStage

    buyer = await _register(client, "stage_buyer@test.com", club_name="Stage Buyer FC")
    seller = await _register(client, "stage_seller@test.com", club_name="Stage Seller FC")
    deal = await _create_deal_via_offer(client, buyer, seller, db)

    result = await db.execute(select(Deal).where(Deal.id == uuid.UUID(deal["id"])))
    d = result.scalar_one()
    d.stage = DealStage.AGENT_NEGOTIATION
    await db.commit()

    by_stage = await get_deals_by_stage(db)
    assert set(by_stage.keys()) == {
        "AGREEMENT", "AGENT_NEGOTIATION", "PERSONAL_TERMS", "PAPERWORK", "CONFIRMED",
    }
    assert by_stage["AGENT_NEGOTIATION"] == 1


async def test_health_report_flags_stalled_agent_negotiation(client: AsyncClient, superuser: dict, db):
    """H2: the 3-day staleness check used to only look at DealStage.AGREEMENT —
    a deal stalled with an agent or on personal terms never raised a health
    issue at all."""
    from datetime import datetime, timedelta, timezone

    from app.admin.service import get_health_report
    from app.deals.models import Deal, DealStage

    buyer = await _register(client, "health_buyer@test.com", club_name="Health Buyer FC")
    seller = await _register(client, "health_seller@test.com", club_name="Health Seller FC")
    deal = await _create_deal_via_offer(client, buyer, seller, db)

    result = await db.execute(select(Deal).where(Deal.id == uuid.UUID(deal["id"])))
    d = result.scalar_one()
    d.stage = DealStage.PERSONAL_TERMS
    d.updated_at = datetime.now(timezone.utc) - timedelta(days=4)
    await db.commit()

    report = await get_health_report(db)
    deal_issues = [i for i in report["issues"] if i["category"] == "deals" and i["count"] >= 1]
    assert any(
        any(item["id"] == str(d.id) for item in issue["details"])
        for issue in deal_issues
    ), f"Stalled PERSONAL_TERMS deal not flagged: {report['issues']}"
