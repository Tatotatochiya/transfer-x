"""Admin analytics: events in, reports out.

The admin Analytics tab was empty everywhere because the frontend posted
events to a path only the dev proxy served. These cover the backend end to
end: events from signed-out and signed-in visitors, and every report the tab
reads, which had never been exercised (two of them were raw Postgres SQL).
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from tests.conftest import _auth_headers, _register


async def _superuser(client, db, email="analytics_admin@test.com"):
    from app.auth.models import User

    tokens = await _register(client, email)
    (await db.execute(select(User).where(User.email == email))).scalar_one().is_superuser = True
    await db.commit()
    return tokens


@pytest.mark.asyncio
async def test_events_are_stored_and_every_report_reads_them(client: AsyncClient, db):
    visitor = await _register(client, "analytics_club@clubs-example.com", club_name="Tracked FC")
    s1, s2 = str(uuid.uuid4()), str(uuid.uuid4())

    # A signed-in visitor: two pages, time on the first.
    resp = await client.post("/analytics/events", headers=_auth_headers(visitor), json={"events": [
        {"session_id": s1, "event_type": "PAGE_VIEW", "path": "/dashboard"},
        {"session_id": s1, "event_type": "PAGE_LEAVE", "path": "/dashboard", "duration_ms": 4000},
        {"session_id": s1, "event_type": "PAGE_VIEW", "path": "/players/market"},
    ]})
    assert resp.status_code == 204, resp.text
    # A signed-out visitor.
    resp = await client.post("/analytics/events", json={"events": [
        {"session_id": s2, "event_type": "PAGE_VIEW", "path": "/dashboard"},
    ]})
    assert resp.status_code == 204, resp.text

    admin = await _superuser(client, db)
    h = _auth_headers(admin)

    overview = (await client.get("/analytics/overview", headers=h)).json()
    assert (overview["page_views_today"], overview["unique_sessions_today"], overview["dau_today"]) == (3, 2, 1)
    assert overview["total_events_today"] == 4 and overview["dau_7d"] == 0.1  # 1 user-day / 7, to one decimal

    pages = {p["path"]: p for p in (await client.get("/analytics/pages?days=7", headers=h)).json()}
    assert pages["/dashboard"]["views"] == 2 and pages["/dashboard"]["unique_sessions"] == 2
    assert pages["/dashboard"]["avg_duration_ms"] == 4000

    [user] = (await client.get("/analytics/users?days=7", headers=h)).json()
    assert user["email"] == "analytics_club@clubs-example.com" and user["page_views"] == 2

    [today] = (await client.get("/analytics/trend?days=7", headers=h)).json()
    assert (today["page_views"], today["unique_sessions"]) == (3, 2)

    sessions = (await client.get("/analytics/sessions", headers=h)).json()
    assert {s["session_id"] for s in sessions} == {s1, s2}


@pytest.mark.asyncio
async def test_reports_are_for_staff_only(client: AsyncClient, db):
    club = await _register(client, "analytics_nosy@clubs-example.com", club_name="Nosy FC")
    for path in ("/analytics/overview", "/analytics/pages", "/analytics/users", "/analytics/trend", "/analytics/sessions"):
        assert (await client.get(path, headers=_auth_headers(club))).status_code == 403
