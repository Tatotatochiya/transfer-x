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
| Railway | Live, with a real database (all 11 leagues, valuations, agent accounts — backfilled 2026-08-10; demo deal coverage seeded 2026-08-25). At migration `0069`. Not a formally promoted staging or production environment; it predates any defined deployment process. |
| Staging | Not yet configured |
| Production | Not yet configured |

> **TODO:** This is an honest current-state snapshot, not a plan. Fill in staging/production once they exist, and turn the gap into a roadmap item in [`../product/roadmap.md`](../product/roadmap.md) if it isn't tracked there already. Decide explicitly what Railway *is* — the row above records that it exists and is live, not that its role is settled.

## Deployment process

> **TODO:** Document the deployment process once one exists — CI/CD pipeline, promotion strategy, rollback procedure.

What is known, from observation rather than design: the backend entrypoint runs `alembic upgrade head` on boot, so a deploy migrates the database. Deploys are **not** automatic on push to `main` — on 2026-08-25 Railway sat at `0064` for some hours after `0065`–`0069` were pushed, and only caught up on the next deploy. Check `railway deployment list` and the live `alembic_version` before assuming the deployed schema matches `main`.

## Railway demo environment

Seeded 2026-08-25 so a demo can walk the whole transfer pipeline. All seven deal stages are live (9 deals — 6 from `scripts/seed_demo.py`, 3 pre-existing).

| | |
|---|---|
| Front end | https://frontend-production-7d8e.up.railway.app |
| API | https://backend-production-ace3.up.railway.app |

**Agent logins** (password `password123`, as with every dev account — see the warning below the table):

| Agent | Email | Clients | Live deals |
|---|---|---|---|
| Sofia Reyes — Premier Talent Group | `sofia.reyes@premiertalent.com` | 5 (Chelsea) | 1 — at `AGENT_NEGOTIATION` |
| James Mitchell — Elite Sports Management | `james.mitchell@elitesports.com` | 6 (Arsenal + Liverpool) | 2 — at `PERSONAL_TERMS` and `PAPERWORK` |
| Marco Rossi — Global Football Agency | `marco.rossi@globalfootball.com` | 5 (Liverpool) | 0 |

Club logins follow the same password: `arsenal@transferx.com`, `chelsea@transferx.com`, `liverpool@transferx.com`, plus `admin@club.com` for staff-only actions.

> **Every account on Railway shares the password `password123`**, including the superuser. That is acceptable for a demo environment nobody real depends on, and unacceptable the moment this becomes a staging or production environment — which is part of what the *Decide explicitly what Railway is* TODO above has to settle.

Two things to know before re-running the seed there:

- **`seed_demo.py` reads `settings.database_url`, not `DATABASE_PUBLIC_URL`.** Unlike `sync_leagues.py` and `recompute_valuations_railway.py`, it has no Railway-specific branch — run it with `DATABASE_URL` set to Railway's public URL.
- **Scenario `D3` needs a mandated Arsenal player.** Railway originally had mandates only on Liverpool and Chelsea players, and the script aborts with a clear message rather than picking a substitute. Local's 16 active mandates were mirrored across on 2026-08-25 (Arsenal 4 / Chelsea 5 / Liverpool 7) to close that.

## Email

Locally, email goes to Mailpit (`http://localhost:8025`). A deployed environment has to set real SMTP settings on the API service: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`, `SMTP_USE_TLS`, and `FRONTEND_BASE_URL` so the links in emails point at that environment's front end. Without `SMTP_HOST` every send is skipped and logged. That includes the per-event notification emails and the daily "waiting on you" digest (hourly job, one email per person per day, after 07:00 UTC).

> **TODO:** Railway has no SMTP configured, so no email is sent there. Decide on a provider (and a sending domain) before any real club uses it.

## Pending data repairs on Railway

One-off repair scripts that have been run locally but not yet on Railway. These are not Alembic migrations, so nothing runs them automatically on deploy — each has to be invoked deliberately after the corresponding code change is deployed. Delete a row once it has been run there.

| Script | Why | Run locally |
|---|---|---|
| `backend/scripts/backfill_contract_wages.py` | Every active contract had no wage, so after migration `0071`'s release a loan is refused ("His contract has no wage on record") on every player. Gives each such contract a plausible wage and adds it to the club's wage bill. Run `--dry-run` first. Like `seed_demo.py` it reads `settings.database_url`, so set `DATABASE_URL` to Railway's public URL. | 2026-09-26: 106 contracts; Arsenal +£1.58m/wk, Chelsea +£1.59m/wk, Liverpool +£1.19m/wk. A second run touched nothing. |
| `backend/scripts/repair_player_statuses.py` | Players with no club anywhere were stored as EXTERNAL, not FREE_AGENT (ADR 0003), so they could not be signed or invited (ADR 0007). It re-derives each mismatched player's status through `normalize_player_status`; players who become free agents trigger the usual PLAYER_AVAILABLE notification. Idempotent; run `--dry-run` first. | 2026-09-29: 13 players EXTERNAL → FREE_AGENT; a second run found none. |
| `backend/scripts/mock_contract_end_dates.py` | **Mock data, for demos only.** No contract carried an end date, so expiring contracts, the morning briefing, "Who might want him?" and the pricing assistant's discount all showed nothing. It gives every contracted player a plausible end date: 30 June 2027–31, or 31 January 2027 for about 5%. Dates are deterministic by player id, and a real date is never overwritten. Replace with real dates from the clubs or the vendor feed before any real use. | 2026-09-28: 106 active contracts and 5,011 players; each TransferX club has 2 contracts ending within six months. A second run touched nothing. |

`backend/scripts/repair_listings_left_open_after_offer_accepted.py` — deployed and run 2026-08-12. **Verified by direct read-only query against Railway's database, not by trusting the run's own report:** `alembic_version` is at `0063`; zero listings sit `OPEN` behind an `IN_PROGRESS`/`COMPLETED` deal. Worth recording precisely, since it corrects what this doc said before: Railway's data did **not** in fact contain the broken rows this script targets. Of Railway's 8 offers, only 2 were ever made against a listing, and both expired unaccepted — `accept_offer` (where the bug lived) was never invoked with a `sale_id` present there. The three deals that do exist are all from standalone offers, unrelated to this bug. So the repair was correctly a no-op on this environment; the assumption that Railway "carries the same broken rows local did" was untested at the time it was written and turned out to be wrong. Safe to run again regardless — idempotent, `--dry-run` reports what it would change without writing.

## Related documents

- [`../architecture/system-overview.md`](../architecture/system-overview.md) — the system being deployed
- [`../engineering/getting-started.md`](../engineering/getting-started.md) — the local-only equivalent that exists today
- [`monitoring-and-observability.md`](./monitoring-and-observability.md) — how a deployed system would be observed
