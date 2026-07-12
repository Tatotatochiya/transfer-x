---
title: "Database Migrations"
last_updated: 2026-07-12
status: Active
owner: "TODO — assign a Technical Lead"
---

# Database Migrations

## Purpose

Documents how database schema changes are managed in TransferX.

## Scope

In scope: migration tooling and workflow.
Out of scope: the schema itself (see [`../architecture/data-model.md`](../architecture/data-model.md)).

## Table of Contents

- [Tooling](#tooling)
- [Current state](#current-state)
- [Workflow](#workflow)
- [Related documents](#related-documents)

## Tooling

Alembic, against SQLAlchemy async models. Migration files live in `backend/migrations/versions/`.

## Current state

As of this writing: 61 numbered migration files plus 2 unnumbered merge/fix revisions, latest (`0061`) adding the medical `WAIVED` status, `Deal.confirmed_at`/`option_exercised`, and `TransferWindow.grace_period_hours` from the 2026-07-12 audit remediation. This number changes frequently — treat it as a snapshot, not a live fact, and check `backend/migrations/versions/` directly if you need the current count.

## Workflow

```bash
cd backend
alembic upgrade head
alembic revision --autogenerate -m "description"
```

> **TODO:** Document any project-specific migration gotchas (e.g. enum handling, nullable foreign key patterns) worth calling out for future contributors — check whether project memory/notes already capture known Alembic issues before writing this from scratch.

## Related documents

- [`../architecture/data-model.md`](../architecture/data-model.md) — the schema these migrations evolve
- [`getting-started.md`](./getting-started.md) — running migrations as part of initial setup
