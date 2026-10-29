"""The demo change journal: every row a demo inserts, changes or deletes.

A session belongs to a demo run when `session.info["demo_run_id"]` is set:
by `get_current_user` for a tester with an active run, or for a "play as
this house club" tab. A session with no run joins one the moment it
changes a row a run inserted (a job expiring a demo offer, the other side
answering it): whatever else that flush changes is the demo's doing too.

Two hooks record it, both before anything is committed:
- `after_flush`: ORM inserts, updates (only the changed columns, before and
  after) and deletes (the whole row);
- `do_orm_execute`: bulk `update()` / `delete()` statements, by reading the
  rows they match before and after.

`service.reset` plays the journal backwards. Tables that are append-only
records (the audit log, monitoring, analytics) aren't journaled: they keep
what happened, demo or not.
"""
from __future__ import annotations

import enum
import json
import time
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import event, inspect, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ClauseElement

SKIP_TABLES = frozenset({
    "demo_runs", "demo_changes", "audit_events", "job_runs", "job_run_logs", "scheduler_job_runs",
    "error_issues", "error_events", "request_minutes", "analytics_events", "assistant_queries",
    "ai_suggestion_events", "vendor_sync_states", "vendor_sync_runs", "vendor_fetch_log",
    "refresh_tokens", "push_deliveries", "player_views", "player_search_views",
})
SKIP_COLUMNS = frozenset({("users", "last_active_at")})

ACTIVE_CACHE_SECONDS = 5
_active = {"until": 0.0, "any": False}


def forget_active_cache() -> None:
    """After a run starts or ends in this process, check again at once."""
    _active["until"] = 0.0


# ── Values as tagged JSON ────────────────────────────────────────────────────


def enc(v):
    if isinstance(v, uuid.UUID):
        return {"$u": str(v)}
    if isinstance(v, datetime):
        return {"$dt": v.isoformat()}
    if isinstance(v, date):
        return {"$d": v.isoformat()}
    if isinstance(v, Decimal):
        return {"$n": str(v)}
    if isinstance(v, enum.Enum):
        return {"$e": v.name}
    return v


def dec(v, column=None):
    if isinstance(v, dict) and len(v) == 1:
        (tag, raw), = v.items()
        if tag == "$u":
            return uuid.UUID(raw)
        if tag == "$dt":
            return datetime.fromisoformat(raw)
        if tag == "$d":
            return date.fromisoformat(raw)
        if tag == "$n":
            return Decimal(raw)
        if tag == "$e":
            enum_class = getattr(getattr(column, "type", None), "enum_class", None)
            return enum_class[raw] if enum_class is not None else raw
    return v


def pk_key(values: dict) -> str:
    """The canonical text of a primary key, for lookups."""
    return json.dumps({k: enc(v) for k, v in values.items()}, sort_keys=True, default=str)


def same(a, b) -> bool:
    """Whether two column values are equal, allowing for timezone and number types."""
    if isinstance(a, datetime) and isinstance(b, datetime):
        a = a if a.tzinfo else a.replace(tzinfo=timezone.utc)
        b = b if b.tzinfo else b.replace(tzinfo=timezone.utc)
        return a == b
    if isinstance(a, (Decimal, float, int)) and isinstance(b, (Decimal, float, int)) \
            and not isinstance(a, bool) and not isinstance(b, bool):
        return Decimal(str(a)) == Decimal(str(b))
    if isinstance(a, enum.Enum) or isinstance(b, enum.Enum):
        return getattr(a, "name", a) == getattr(b, "name", b) or getattr(a, "value", a) == getattr(b, "value", b)
    return a == b


# ── Which run, if any ────────────────────────────────────────────────────────


def _enabled() -> bool:
    from app.config import settings

    return settings.demo_enabled


def _any_active(conn) -> bool:
    now = time.monotonic()
    if now >= _active["until"]:
        from app.demo.models import DemoRun

        _active["any"] = conn.execute(
            select(DemoRun.id).where(DemoRun.status == "ACTIVE").limit(1)).first() is not None
        _active["until"] = now + ACTIVE_CACHE_SECONDS
    return _active["any"]


def _run_inserting(conn, keys: list[tuple[str, str]]):
    """The active run that inserted any of these (table, pk) rows, or None."""
    from app.demo.models import DemoChange, DemoRun

    if not keys:
        return None
    by_table: dict[str, list[str]] = {}
    for table, key in keys:
        by_table.setdefault(table, []).append(key)
    for table, pks in by_table.items():
        row = conn.execute(
            select(DemoChange.run_id).join(DemoRun, DemoRun.id == DemoChange.run_id)
            .where(DemoRun.status == "ACTIVE", DemoChange.op == "insert",
                   DemoChange.table_name == table, DemoChange.pk.in_(pks)).limit(1)).first()
        if row is not None:
            return row[0]
    return None


def _session_run(session: Session, conn, touched: list[tuple[str, str]]):
    if session.info.get("demo_resetting") or not _enabled():
        return None
    run_id = session.info.get("demo_run_id")
    if run_id is None and _any_active(conn):
        run_id = _run_inserting(conn, touched)
        if run_id is not None:
            session.info["demo_run_id"] = run_id
            session.info["demo_run_adopted"] = True  # until this transaction ends
    return run_id


@event.listens_for(Session, "after_commit")
@event.listens_for(Session, "after_soft_rollback")
def _end_adoption(session: Session, *args) -> None:
    """A session that joined a run by touching a demo row leaves it when the
    transaction ends: a job's next transaction may have nothing to do with it."""
    if session.info.pop("demo_run_adopted", None):
        session.info.pop("demo_run_id", None)


# ── ORM flushes ──────────────────────────────────────────────────────────────


def _table(obj):
    mapper = inspect(obj).mapper
    return mapper, mapper.persist_selectable


def _pk(mapper, table, obj) -> dict:
    values = mapper.primary_key_from_instance(obj)
    return {c.name: v for c, v in zip(mapper.primary_key, values)}


def _column_attrs(mapper, table):
    for prop in mapper.column_attrs:
        col = prop.columns[0]
        if getattr(col, "table", None) is table:
            yield prop.key, col


@event.listens_for(Session, "after_flush")
def _after_flush(session: Session, flush_context) -> None:
    if not _enabled() or session.info.get("demo_resetting"):
        return
    conn = session.connection()
    records, touched = [], []
    for obj in list(session.dirty) + list(session.deleted):
        mapper, table = _table(obj)
        if table.name not in SKIP_TABLES:
            touched.append((table.name, pk_key(_pk(mapper, table, obj))))
    run_id = _session_run(session, conn, touched)
    if run_id is None:
        return

    for obj in session.new:
        mapper, table = _table(obj)
        if table.name in SKIP_TABLES:
            continue
        records.append({"table_name": table.name, "pk": pk_key(_pk(mapper, table, obj)), "op": "insert",
                        "before": None, "after": None})
    for obj in session.dirty:
        mapper, table = _table(obj)
        if table.name in SKIP_TABLES or not session.is_modified(obj, include_collections=False):
            continue
        state = inspect(obj)
        before, after = {}, {}
        for key, col in _column_attrs(mapper, table):
            if (table.name, col.name) in SKIP_COLUMNS:
                continue
            hist = state.attrs[key].history
            if not (hist.added or hist.deleted):
                continue
            old = hist.deleted[0] if hist.deleted else None
            new = hist.added[0] if hist.added else None
            before[col.name] = enc(old)
            # A SQL expression's result isn't known here: reset restores it unchecked.
            after[col.name] = {"$sql": True} if isinstance(new, ClauseElement) else enc(new)
        if before:
            records.append({"table_name": table.name, "pk": pk_key(_pk(mapper, table, obj)), "op": "update",
                            "before": before, "after": after})
    for obj in session.deleted:
        mapper, table = _table(obj)
        if table.name in SKIP_TABLES:
            continue
        state = inspect(obj)
        row = {}
        for key, col in _column_attrs(mapper, table):
            hist = state.attrs[key].history
            value = hist.deleted[0] if hist.deleted else state.dict.get(key)
            row[col.name] = enc(value)
        records.append({"table_name": table.name, "pk": pk_key(_pk(mapper, table, obj)), "op": "delete",
                        "before": row, "after": None})
    _write(conn, run_id, records)


def _write(conn, run_id, records: list[dict]) -> None:
    from app.demo.models import DemoChange

    if records:
        conn.execute(DemoChange.__table__.insert(), [{**r, "run_id": run_id} for r in records])


# ── Bulk update() and delete() statements ───────────────────────────────────


def _row_pk(table, row) -> dict:
    return {c.name: row[c.name] for c in table.primary_key.columns}


@event.listens_for(Session, "do_orm_execute")
def _bulk(orm_execute_state):
    if not (orm_execute_state.is_update or orm_execute_state.is_delete):
        return None
    session = orm_execute_state.session
    if not _enabled() or session.info.get("demo_resetting"):
        return None
    stmt = orm_execute_state.statement
    mapper = orm_execute_state.bind_mapper
    table = mapper.local_table if mapper is not None else getattr(stmt, "table", None)
    if table is None or getattr(table, "name", None) in SKIP_TABLES:
        return None
    conn = session.connection()
    if session.info.get("demo_run_id") is None and not _any_active(conn):
        return None
    where = stmt.whereclause
    rows_before = conn.execute(select(table).where(where) if where is not None else select(table)).mappings().all()
    if not rows_before:
        return None
    touched = [(table.name, pk_key(_row_pk(table, r))) for r in rows_before]
    run_id = _session_run(session, conn, touched)
    if run_id is None:
        return None

    result = orm_execute_state.invoke_statement()
    records = []
    if orm_execute_state.is_delete:
        for r in rows_before:
            records.append({"table_name": table.name, "pk": pk_key(_row_pk(table, r)), "op": "delete",
                            "before": {k: enc(v) for k, v in r.items()}, "after": None})
    else:
        pk_cols = list(table.primary_key.columns)
        for r in rows_before:
            cond = [c == r[c.name] for c in pk_cols]
            now = conn.execute(select(table).where(*cond)).mappings().first()
            if now is None:
                continue
            before = {k: enc(v) for k, v in r.items() if (table.name, k) not in SKIP_COLUMNS and not same(v, now[k])}
            if before:
                after = {k: enc(now[k]) for k in before}
                records.append({"table_name": table.name, "pk": pk_key(_row_pk(table, r)), "op": "update",
                                "before": before, "after": after})
    _write(conn, run_id, records)
    return result
