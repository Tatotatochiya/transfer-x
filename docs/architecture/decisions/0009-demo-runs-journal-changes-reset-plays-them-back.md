---
title: "ADR 0009: Demo Runs Journal Every Change, and Reset Plays the Journal Back"
last_updated: 2026-10-27
status: Accepted
owner: "TODO — assign a Technical Owner"
---

# ADR 0009: Demo Runs Journal Every Change, and Reset Plays the Journal Back

## Context

Testers want to try whole transfers on the real data without playing the other club, and then undo them ([demo mode](../../feature_spec/demo-mode.md)). The product owner chose to do this in the same database as everything else, not in a separate demo copy. A completed transfer touches offers, deals, both clubs' finances, the player, his contracts, notifications and more, across many modules, and any of them can change.

Undoing each feature's effects in that feature's code would mean every module learning about demos, and missing one would leave demo data behind.

## Decision

1. **A generic change journal.** While a session belongs to a demo run, SQLAlchemy session events record every row it inserts, changes (the changed columns, before and after) or deletes (the whole row): `after_flush` for ORM changes, `do_orm_execute` for bulk `update()`/`delete()`. Values are stored as tagged JSON so their types (UUIDs, dates, decimals, enums) come back exactly. Code: `backend/app/demo/journal.py`.
2. **Demo-ness spreads by transaction.** A request belongs to the tester's active run (set in `get_current_user`), or to a play-as tab's run (its token's `demo` claim). A session with no run joins one when it changes a row the run inserted, until that transaction ends. So background jobs and the other side's answers are recorded without knowing about demos.
3. **Reset plays the journal backwards** in one transaction, with a savepoint per change. A column is set back only if it still holds the value the demo left. Anything else is skipped and reported, never overwritten.
4. **Append-only stores aren't journaled:** the audit log, monitoring, analytics.

## Consequences

- No module needs demo code to be undoable. New tables are covered automatically.
- Writes during a demo cost an extra insert per changed row. With no run active, the hooks do nothing more than a cached "any runs?" check every 5 seconds per process.
- Reset is exact for anything the demo alone touched. A row real activity also changed is reported, not fixed: staff decide.
- Effects outside the database (emails, pushes, model calls) can't be undone.
- Shared figures that read completed deals (valuations, comparables) still see demo deals until reset; leaving them out is the next step.
- A transaction that only changes non-demo rows before touching a demo row is recorded only from that point. The safety check stops reset damaging anything it missed.
