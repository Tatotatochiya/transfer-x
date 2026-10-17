---
title: "Database Migrations"
last_updated: 2026-10-11
status: Active
owner: "TODO — assign a Technical Owner"
---

# Database Migrations

## Purpose

How schema changes are made and applied.

## Scope

In scope: tooling, numbering, workflow and known gotchas.
Out of scope: the schema itself ([`../architecture/data-model.md`](../architecture/data-model.md)).

## Table of Contents

- [Tooling](#tooling)
- [Numbering and head](#numbering-and-head)
- [Workflow](#workflow)
- [Gotchas](#gotchas)
- [Related documents](#related-documents)

## Tooling

Alembic, in `backend/migrations/versions/`. Every model module must be imported in `migrations/env.py` for autogenerate to see it.

## Numbering and head

**Numbering.** Migrations are numbered `0001`… with `down_revision` pointing at the previous number. Two early ones have hash ids from a merge.

**Head (2026-10-17):** `0102` (the `DEADLINE_DAY` notification), applied locally. Railway applied `0101` with #41 and applies `0102` on its next deploy.

**Applying.** Both the local `api` container and Railway's `backend` service run `alembic upgrade head` on start (`backend/entrypoint.sh`), so a deploy applies new migrations. The `stats-worker` doesn't run migrations.

## Workflow

```bash
docker compose exec -T api alembic revision -m "short description"   # then rename to the next number
docker compose exec -T api alembic upgrade head
docker compose exec -T api alembic downgrade -1                       # if you need to step back
```

Write `upgrade()` and `downgrade()` by hand, following the existing files. Autogenerate output is a starting point at best.

## Gotchas

- **Tests don't use migrations.** The test suite builds the schema with `Base.metadata.create_all` on SQLite. A migration that drifts from the models passes the tests and then fails on Postgres, so run `alembic upgrade head` locally before shipping.
- **SQLite vs Postgres.** SQLite drops time zones and has no row locks. Compare datetimes timezone-aware, and use `select_for_update(of=…)` with nullable joins.
- **Enums.** A new value in a Postgres enum needs `ALTER TYPE … ADD VALUE` in its own migration step.
- **Railway history.** Railway once had `0059`–`0061` from a force-pushed branch; matching placeholder migrations keep the chain the same in both places. Don't renumber existing migrations.

## Related documents

- [`../architecture/data-model.md`](../architecture/data-model.md): the schema
- [`../operations/environments-and-deployment.md`](../operations/environments-and-deployment.md): deploys
