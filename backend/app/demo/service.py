"""Demo runs: start, reset, keep, and the house-club rules (app/demo/journal.py).

Reset plays a run's journal backwards, newest change first, in one
transaction: an inserted row is deleted, a deleted row put back, and each
column an update changed is set back, but only while it still holds the
value the demo left. A column something real has changed since is left as
it is and listed in the report, so a reset never wipes a real change. So is
a row that can't be removed because real data now points at it.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import Base
from app.demo import journal
from app.demo.models import DemoChange, DemoRun

AUTO_RESET_DAYS = 14


def _now() -> datetime:
    return datetime.now(timezone.utc)


def can_demo(user) -> bool:
    from app.config import settings

    return settings.demo_enabled and (user.is_superuser or user.can_demo)


async def active_run(db: AsyncSession, user_id: uuid.UUID) -> DemoRun | None:
    from app.config import settings

    if not settings.demo_enabled:
        return None
    return (await db.execute(select(DemoRun).where(
        DemoRun.user_id == user_id, DemoRun.status == "ACTIVE"))).scalar_one_or_none()


async def change_count(db: AsyncSession, run_id: uuid.UUID) -> int:
    return (await db.execute(select(func.count()).select_from(DemoChange).where(DemoChange.run_id == run_id))).scalar_one()


async def describe(db: AsyncSession, run: DemoRun | None) -> dict | None:
    if run is None:
        return None
    started = run.started_at if run.started_at.tzinfo else run.started_at.replace(tzinfo=timezone.utc)
    return {
        "id": str(run.id), "status": run.status, "started_at": started.isoformat(),
        "resets_on": (started + timedelta(days=AUTO_RESET_DAYS)).date().isoformat() if run.status == "ACTIVE" else None,
        "changes": await change_count(db, run.id), "report": run.report,
    }


async def start(db: AsyncSession, user) -> DemoRun:
    """Open a demo run for the user. Caller commits."""
    from app.clubs.service import get_club_for_user

    if not can_demo(user):
        raise PermissionError("Demo mode isn't available to you.")
    if await active_run(db, user.id) is not None:
        raise ValueError("You already have a demo running. Reset it or keep it first.")
    club = await get_club_for_user(db, user.id)
    run = DemoRun(user_id=user.id, club_id=club.id if club else None, status="ACTIVE")
    db.add(run)
    await db.flush()
    journal.forget_active_cache()
    return run


def _table(name: str):
    return Base.metadata.tables[name]


def _where_pk(table, pk_text: str):
    pk = json.loads(pk_text)
    return [table.c[name] == journal.dec(v, table.c[name]) for name, v in pk.items()]


async def _undo(db: AsyncSession, change: DemoChange, skipped: list[dict]) -> bool:
    table = _table(change.table_name)
    where = _where_pk(table, change.pk)
    if change.op == "insert":
        await db.execute(delete(table).where(*where))
        return True
    if change.op == "delete":
        exists = (await db.execute(select(*table.primary_key.columns).where(*where))).first()
        if exists is None:
            await db.execute(insert(table).values(
                {k: journal.dec(v, table.c[k]) for k, v in (change.before or {}).items() if k in table.c}))
        return True
    current = (await db.execute(select(table).where(*where))).mappings().first()
    if current is None:
        skipped.append({"table": change.table_name, "pk": json.loads(change.pk),
                        "why": "The row no longer exists."})
        return False
    restore, conflicts = {}, []
    for col, old in (change.before or {}).items():
        if col not in table.c:
            continue
        left = (change.after or {}).get(col)
        if isinstance(left, dict) and left.get("$sql"):
            restore[col] = journal.dec(old, table.c[col])
        elif journal.same(current[col], journal.dec(left, table.c[col])):
            restore[col] = journal.dec(old, table.c[col])
        else:
            conflicts.append(col)
    if restore:
        await db.execute(update(table).where(*where).values(restore))
    if conflicts:
        skipped.append({"table": change.table_name, "pk": json.loads(change.pk),
                        "why": f"Changed since the demo, so left as it is: {', '.join(conflicts)}."})
    return bool(restore)


async def reset(db: AsyncSession, run: DemoRun, *, by_user_id: uuid.UUID | None) -> dict:
    """Put back everything the run changed, newest first. Caller commits."""
    if run.status != "ACTIVE":
        raise ValueError("This demo has already ended.")
    db.sync_session.info["demo_resetting"] = True
    db.sync_session.info.pop("demo_run_id", None)
    try:
        await db.flush()
        changes = (await db.execute(select(DemoChange).where(DemoChange.run_id == run.id)
                                    .order_by(DemoChange.id.desc()))).scalars().all()
        undone, skipped = 0, []
        for change in changes:
            try:
                async with db.begin_nested():
                    if await _undo(db, change, skipped):
                        undone += 1
            except Exception as exc:  # e.g. real data now points at a demo row
                skipped.append({"table": change.table_name, "pk": json.loads(change.pk),
                                "why": f"Couldn't be undone: {type(exc).__name__}."})
        report = {"undone": undone, "skipped": skipped}
        run.status, run.ended_at, run.ended_by_user_id = "RESET", _now(), by_user_id
        run.report = report
        await db.flush()
    finally:
        db.sync_session.info.pop("demo_resetting", None)
    # Rows put back with plain SQL: what the session holds is out of date.
    for obj in list(db.sync_session.identity_map.values()):
        if obj is not run:
            db.expire(obj)
    journal.forget_active_cache()
    return report


async def keep(db: AsyncSession, run: DemoRun, *, by_user_id: uuid.UUID | None) -> None:
    """End the run and keep what it changed. Caller commits."""
    if run.status != "ACTIVE":
        raise ValueError("This demo has already ended.")
    db.sync_session.info.pop("demo_run_id", None)
    run.status, run.ended_at, run.ended_by_user_id = "KEPT", _now(), by_user_id
    run.report = {"kept": await change_count(db, run.id)}
    await db.flush()
    journal.forget_active_cache()


async def auto_reset(db: AsyncSession) -> int:
    """Reset runs left open for AUTO_RESET_DAYS. Commits each. Returns how many."""
    cutoff = _now() - timedelta(days=AUTO_RESET_DAYS)
    runs = (await db.execute(select(DemoRun).where(DemoRun.status == "ACTIVE", DemoRun.started_at < cutoff))).scalars().all()
    for run in runs:
        await reset(db, run, by_user_id=None)
        await db.commit()
    return len(runs)


# ── House clubs ──────────────────────────────────────────────────────────────

PERSONALITIES = ("hard", "fair", "eager")
NOT_HOUSE = ("In a demo you can only deal with house clubs (clubs TransferX plays). {club} isn't one, "
             "so a real club would be drawn into your demo.")


async def club_in_use(db: AsyncSession, club) -> bool:
    """Whether anyone uses the club: its owner has ever been active, or it has staff."""
    from app.auth.models import User
    from app.clubs.models import ClubStaff

    owner = await db.get(User, club.user_id)
    if owner is not None and owner.last_active_at is not None:
        return True
    return (await db.execute(select(ClubStaff.id).where(ClubStaff.club_id == club.id).limit(1))).first() is not None


async def guard_counterparty(db: AsyncSession, user, *, club_id: uuid.UUID | None = None,
                             player_id: uuid.UUID | None = None) -> None:
    """In a tester's own demo run, the other side must be a house club.
    Raises PermissionError with the reason. No-op outside a run."""
    from app.clubs.models import Club

    if await active_run(db, user.id) is None:
        return
    if club_id is None and player_id is not None:
        from app.players.models import Player
        from app.players.service import get_owning_club_id

        player = await db.get(Player, player_id)
        club_id = await get_owning_club_id(db, player) if player is not None else None
    if club_id is None:
        return  # a free agent or an outside player: no club drawn in
    club = await db.get(Club, club_id)
    if club is not None and not club.house_club:
        raise PermissionError(NOT_HOUSE.format(club=club.name))


async def guard_demo_row(db: AsyncSession, table: str, pk: dict, *, what: str) -> None:
    """Refuse a request from outside a demo that would act on a row the demo
    made (it would be drawn into the demo and lost on reset). PermissionError."""
    from app.config import settings
    from app.demo.models import DemoChange

    if not settings.demo_enabled:
        return
    row = (await db.execute(
        select(DemoChange.run_id).join(DemoRun, DemoRun.id == DemoChange.run_id)
        .where(DemoRun.status == "ACTIVE", DemoChange.op == "insert", DemoChange.table_name == table,
               DemoChange.pk == journal.pk_key(pk)).limit(1))).first()
    if row is not None and db.sync_session.info.get("demo_run_id") != row[0]:
        raise PermissionError(f"This {what} is part of someone's demo, so it can't be used outside it.")


# ── Keeping demo and test deals out of shared figures ────────────────────────


async def active_demo_ids(db: AsyncSession, table: str) -> set[uuid.UUID]:
    """Ids of the rows active demo runs inserted into `table` (single-column
    `id` keys). Empty with demo mode off."""
    from app.config import settings

    if not settings.demo_enabled:
        return set()
    keys = (await db.execute(
        select(DemoChange.pk).join(DemoRun, DemoRun.id == DemoChange.run_id)
        .where(DemoRun.status == "ACTIVE", DemoChange.op == "insert", DemoChange.table_name == table))).scalars().all()
    out = set()
    for key in keys:
        raw = json.loads(key).get("id")
        try:
            out.add(journal.dec(raw) if isinstance(raw, dict) else uuid.UUID(str(raw)))
        except (TypeError, ValueError):
            continue
    return out


async def shared_deals(db: AsyncSession):
    """A condition on Deal for figures everyone sees (valuations, comparable
    transfers, Recent Transfers): leaves out deals an open demo made and
    deals staff marked as tests."""
    from sqlalchemy import true

    from app.deals.models import Deal

    demo = await active_demo_ids(db, "deals")
    cond = Deal.is_test.is_(False)
    return cond & Deal.id.not_in(demo) if demo else cond & true()
