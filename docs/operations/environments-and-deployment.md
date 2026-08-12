---
title: "Environments & Deployment"
last_updated: 2026-08-11
status: Draft
owner: "TODO — assign an Operations Owner"
---

# Environments & Deployment

## Purpose

Documents what environments TransferX runs in and how code gets deployed to them.

## Scope

In scope: environment list, deployment process.
Out of scope: local dev setup (see [`../engineering/getting-started.md`](../engineering/getting-started.md)).

## Table of Contents

- [Environments](#environments)
- [Deployment process](#deployment-process)
- [Related documents](#related-documents)

## Environments

| Environment | Status |
|---|---|
| Local development | Configured — Docker Compose (`db`, `api`, `frontend`) |
| Railway | Live, with a real database (all 11 leagues, valuations, agent accounts — backfilled 2026-08-10). Not a formally promoted staging or production environment; it predates any defined deployment process. |
| Staging | Not yet configured |
| Production | Not yet configured |

> **TODO:** This is an honest current-state snapshot, not a plan. Fill in staging/production once they exist, and turn the gap into a roadmap item in [`../product/roadmap.md`](../product/roadmap.md) if it isn't tracked there already. Decide explicitly what Railway *is* — the row above records that it exists and is live, not that its role is settled.

## Deployment process

> **TODO:** Document the deployment process once one exists — CI/CD pipeline, promotion strategy, rollback procedure.

## Pending data repairs on Railway

One-off repair scripts that have been run locally but **not yet on Railway**. These are not Alembic migrations, so nothing runs them automatically on deploy — each has to be invoked deliberately after the corresponding code change is deployed. Delete a row once it has been run there.

| Script | Why | Run after |
|---|---|---|
| `backend/scripts/repair_listings_left_open_after_offer_accepted.py` | Accepting a direct offer against a listing used to leave that listing `OPEN` and never set `deal.sale_id` (see [`../CHANGELOG.md`](../CHANGELOG.md)). Railway's data will contain the same broken rows. | Deploying the `accept_offer` fix. Running it before the fix is deployed would repair existing rows but not stop new ones appearing. |

Safe to run repeatedly — it is idempotent, and `--dry-run` reports what it would change without writing.

## Related documents

- [`../architecture/system-overview.md`](../architecture/system-overview.md) — the system being deployed
- [`../engineering/getting-started.md`](../engineering/getting-started.md) — the local-only equivalent that exists today
- [`monitoring-and-observability.md`](./monitoring-and-observability.md) — how a deployed system would be observed
