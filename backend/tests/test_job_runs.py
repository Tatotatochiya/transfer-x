"""Health's scheduled-job history survives an API restart (migration 0092)."""
from types import SimpleNamespace

import pytest

from app.common import jobs

pytestmark = pytest.mark.asyncio


async def test_runs_are_saved_throttled_and_read_back(db, monkeypatch):
    saved: list = []

    async def fake_save(job_id, run):
        saved.append((job_id, run["last_ok"]))

    monkeypatch.setattr(jobs, "_save", fake_save)
    monkeypatch.setattr(jobs, "_saved", {})
    jobs.on_job_event(SimpleNamespace(job_id="j", exception=None))
    jobs.on_job_event(SimpleNamespace(job_id="j", exception=None))  # within a minute, same outcome: not saved
    jobs.on_job_event(SimpleNamespace(job_id="j", exception=ValueError("boom")))  # outcome changed: saved
    for t in list(jobs._tasks):
        await t
    assert saved == [("j", True), ("j", False)]


async def test_saved_runs_fill_in_after_a_restart(db):
    from datetime import datetime, timezone

    db.add(jobs.SchedulerJobRun(job_id="expire_stale_offers", last_run_at=datetime.now(timezone.utc),
                                last_ok=False, last_error="boom"))
    await db.commit()
    runs = await jobs.saved_runs(db)
    assert runs["expire_stale_offers"]["last_ok"] is False
    assert runs["expire_stale_offers"]["last_error"] == "boom"
