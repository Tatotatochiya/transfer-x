"""M5 — Notification tests."""

from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient

from tests.conftest import _auth_headers, _register


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def notif_user(client: AsyncClient) -> dict:
    return await _register(client, "notif_user@test.com", club_name="Notif Club")


@pytest_asyncio.fixture
async def other_notif_user(client: AsyncClient) -> dict:
    return await _register(client, "other_notif@test.com", club_name="Other Notif Club")


async def _seed_notification(db, user_id, message: str = "Test notification", is_read: bool = False):
    from app.notifications.models import Notification, NotificationType
    import uuid

    n = Notification(
        recipient_user_id=user_id,
        type=NotificationType.PLAYER_AVAILABLE,
        message=message,
        is_read=is_read,
    )
    db.add(n)
    await db.commit()
    await db.refresh(n)
    return n


async def _get_user_id(db, email: str):
    from app.auth.models import User
    from sqlalchemy import select

    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one().id


# ── Basic notification endpoints ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_notifications_empty(client: AsyncClient, notif_user: dict):
    resp = await client.get("/notifications", headers=_auth_headers(notif_user))
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


@pytest.mark.asyncio
async def test_list_notifications_shows_own(client: AsyncClient, notif_user: dict, db):
    user_id = await _get_user_id(db, "notif_user@test.com")
    await _seed_notification(db, user_id, "You have been outbid")
    await _seed_notification(db, user_id, "New offer received")

    resp = await client.get("/notifications", headers=_auth_headers(notif_user))
    assert resp.status_code == 200
    assert resp.json()["total"] == 2


@pytest.mark.asyncio
async def test_notifications_not_shared_between_users(
    client: AsyncClient, notif_user: dict, other_notif_user: dict, db
):
    user_id = await _get_user_id(db, "notif_user@test.com")
    await _seed_notification(db, user_id, "Private notification")

    resp = await client.get("/notifications", headers=_auth_headers(other_notif_user))
    assert resp.json()["total"] == 0


# ── Unread count ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_unread_count(client: AsyncClient, notif_user: dict, db):
    user_id = await _get_user_id(db, "notif_user@test.com")
    await _seed_notification(db, user_id, "Unread 1")
    await _seed_notification(db, user_id, "Unread 2")
    await _seed_notification(db, user_id, "Read already", is_read=True)

    resp = await client.get("/notifications/unread-count", headers=_auth_headers(notif_user))
    assert resp.status_code == 200
    assert resp.json()["count"] == 2


@pytest.mark.asyncio
async def test_unread_count_zero_initially(client: AsyncClient, notif_user: dict):
    resp = await client.get("/notifications/unread-count", headers=_auth_headers(notif_user))
    assert resp.json()["count"] == 0


# ── Mark read ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_mark_one_notification_read(client: AsyncClient, notif_user: dict, db):
    user_id = await _get_user_id(db, "notif_user@test.com")
    n = await _seed_notification(db, user_id)

    resp = await client.post(f"/notifications/{n.id}/read", headers=_auth_headers(notif_user))
    assert resp.status_code == 200
    assert resp.json()["is_read"] is True

    count_resp = await client.get("/notifications/unread-count", headers=_auth_headers(notif_user))
    assert count_resp.json()["count"] == 0


@pytest.mark.asyncio
async def test_cannot_mark_other_users_notification(
    client: AsyncClient, notif_user: dict, other_notif_user: dict, db
):
    user_id = await _get_user_id(db, "notif_user@test.com")
    n = await _seed_notification(db, user_id)

    resp = await client.post(f"/notifications/{n.id}/read", headers=_auth_headers(other_notif_user))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_mark_all_read(client: AsyncClient, notif_user: dict, db):
    user_id = await _get_user_id(db, "notif_user@test.com")
    await _seed_notification(db, user_id, "N1")
    await _seed_notification(db, user_id, "N2")
    await _seed_notification(db, user_id, "N3")

    resp = await client.post("/notifications/read-all", headers=_auth_headers(notif_user))
    assert resp.status_code == 200
    assert resp.json()["count"] == 0

    count_resp = await client.get("/notifications/unread-count", headers=_auth_headers(notif_user))
    assert count_resp.json()["count"] == 0


# ── PLAYER_AVAILABLE fan-out ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_player_available_notification_on_free_agent(
    client: AsyncClient, notif_user: dict, db
):
    """When a contracted player becomes a free agent, shortlisting clubs get notified."""
    headers = _auth_headers(notif_user)
    user_id = await _get_user_id(db, "notif_user@test.com")

    # Create a second club that will scout the player
    scout_tokens = await _register(client, "scout_notif@test.com", club_name="Scout FC")
    scout_headers = _auth_headers(scout_tokens)

    # Get club IDs
    notif_club_resp = await client.get("/clubs/me", headers=headers)
    notif_club_id = notif_club_resp.json()["id"]

    # Create a player under notif_user's club
    player = (await client.post("/players", json={"name": "Scout Target", "position": "FWD"}, headers=headers)).json()

    # Give notif_user's club budget to create a contract
    from app.clubs.models import ClubFinance
    from sqlalchemy import select

    result = await db.execute(select(ClubFinance))
    for f in result.scalars():
        f.transfer_budget_total = Decimal("50000000")
    await db.commit()

    # Contract the player
    await client.post(
        f"/players/{player['id']}/contracts",
        json={"club_id": notif_club_id, "wage_weekly": 5000},
        headers=headers,
    )

    # Scout club shortlists the player
    sl = (await client.post("/scouting/shortlists", json={"name": "Watching"}, headers=scout_headers)).json()
    await client.post(
        f"/scouting/shortlists/{sl['id']}/items",
        json={"player_id": player["id"]},
        headers=scout_headers,
    )

    # Get scout user_id
    scout_user_id = await _get_user_id(db, "scout_notif@test.com")

    # Deactivate the contract → player becomes free agent → notification triggered
    contract_resp = await client.get(f"/players/{player['id']}", headers=headers)
    # Get active contract id from player detail
    player_detail_resp = await client.get(f"/players/market/{player['id']}", headers=headers)
    player_data = player_detail_resp.json()

    # Delete the contract via API
    contracts_resp = await client.get(f"/players/{player['id']}/contracts", headers=headers)
    # Since there's no list contracts endpoint, use the DB directly
    import uuid as uuid_mod
    from app.players.models import Contract
    contracts_result = await db.execute(
        select(Contract).where(Contract.player_id == uuid_mod.UUID(player["id"]), Contract.is_active == True)
    )
    contract = contracts_result.scalar_one_or_none()
    if contract:
        await client.delete(
            f"/players/{player['id']}/contracts/{contract.id}", headers=headers
        )

    # Scout club should now have a PLAYER_AVAILABLE notification
    from app.notifications.models import Notification, NotificationType
    await db.rollback()  # Ensure we see committed data
    notif_result = await db.execute(
        select(Notification).where(
            Notification.recipient_user_id == scout_user_id,
            Notification.type == NotificationType.PLAYER_AVAILABLE,
        )
    )
    notifications = list(notif_result.scalars())
    assert len(notifications) >= 1
    assert str(player["id"]) in str(notifications[0].related_player_id)
