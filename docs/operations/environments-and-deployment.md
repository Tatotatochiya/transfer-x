---
title: "Environments & Deployment"
last_updated: 2026-10-11
status: Active
owner: "TODO — assign an Operations Owner"
---

# Environments & Deployment

## Purpose

Where TransferX runs and how code gets there.

## Scope

In scope: environments, the deploy process, Railway's services and settings, demo accounts.
Out of scope: local setup ([`../engineering/getting-started.md`](../engineering/getting-started.md)), monitoring ([`monitoring-and-observability.md`](./monitoring-and-observability.md)).

## Table of Contents

- [Environments](#environments)
- [Deployment process](#deployment-process)
- [Railway demo environment](#railway-demo-environment)
- [The stats-worker service](#the-stats-worker-service-scheduled-data-refresh)
- [Email and phone notifications](#email)
- [Data repairs](#data-repairs)
- [Related documents](#related-documents)

## Environments

| Environment | Status |
|---|---|
| Local development | Docker Compose: `db`, `api`, `frontend` (built image), `mailpit` |
| Railway | Project `ravishing-laughter`, environment `production`. Services: `backend`, `frontend`, `Postgres`, `stats-worker`. Holds demo data (20 Premier League clubs, 11 competitions, demo deals at every stage). At migration `0100` on 2026-10-11 |
| Staging | None |
| Production for real clubs | None yet. Railway is a demo environment: every account shares one password (below) |

> **TODO:** Decide what Railway becomes before a real club uses it: separate staging and production, real passwords, SMTP, backups.

## Deployment process

- **Automatic.** Railway deploys `backend`, `frontend` and `stats-worker` when `main` changes, through the GitHub connection.
- **Migrations.** The backend's `entrypoint.sh` runs `alembic upgrade head` before starting, so a deploy migrates the database. The `stats-worker` runs the same image with its own start command, and skips migrations and the web server.
- **Check a deploy:**
  - `railway service list` (status);
  - `railway logs --service backend`;
  - the backend's `/health`;
  - Admin → Health.
- **Roll back:** redeploy an earlier deployment from the Railway dashboard (Deployments → Redeploy). A migration that has already run isn't undone by that.
- **CLI:** the Railway CLI works from a developer machine (`railway login`, then `railway link --project ravishing-laughter`). It was used to set up `stats-worker`.

## Railway demo environment

Seeded 2026-08-25 so a demo can walk the whole transfer pipeline: 9 deals across all seven stages (6 from `scripts/seed_demo.py`, 3 pre-existing). Later live use may have moved them on.

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

Club logins follow the same password. **Every account can sign in with its username**, which is the part of the email before the "@" (e.g. `arsenal`), or with the full email.

All 20 Premier League clubs are clubs on TransferX:
- **The original three:** `arsenal`, `chelsea`, `liverpool`.
- **Added by `scripts/onboard_premier_league_clubs.py`** (locally 2026-09-29, and on Railway): `astonvilla`, `bournemouth`, `brentford`, `brighton`, `burnley`, `crystalpalace`, `everton`, `fulham`, `leeds`, `manchestercity`, `manchesterunited`, `newcastle`, `nottinghamforest`, `sunderland`, `tottenham`, `westham`, `wolves`.

Every club's email is `<username>@transferx.com`. `admin@club.com` is for staff-only actions.

> **Every account on Railway shares the password `password123`**, including the superuser. That is acceptable for a demo environment nobody real depends on, and unacceptable the moment this becomes a staging or production environment — which is part of what the *Decide explicitly what Railway is* TODO above has to settle.

Two things to know before re-running the seed there:

- **`seed_demo.py` reads `settings.database_url`, not `DATABASE_PUBLIC_URL`.** Unlike `sync_leagues.py` and `recompute_valuations_railway.py`, it has no Railway-specific branch — run it with `DATABASE_URL` set to Railway's public URL.
- **Scenario `D3` needs a mandated Arsenal player.** Railway originally had mandates only on Liverpool and Chelsea players, and the script aborts with a clear message rather than picking a substitute. Local's 16 active mandates were mirrored across on 2026-08-25 (Arsenal 4 / Chelsea 5 / Liverpool 7) to close that.

## The stats-worker service (scheduled data refresh)

A second Railway service refreshes API-Football data at 17:00 and 22:00 UK time and recomputes valuations after the 22:00 run ([spec](../feature_spec/scheduled-data-refresh.md)). It runs the same code as `api`, does one refresh, and exits.

**Its settings are on the Railway service, set with the CLI on 2026-10-11:**
- root directory `/backend`;
- start command `python -m app.jobs.daily_refresh`;
- cron `0 16,17,21,22 * * *`;
- restart policy Never.

Railway no longer accepts a per-service config file path; `railway.json` is deprecated in favour of `.railway/railway.ts`. So the worker also picks up `backend/railway.json`, whose restart-on-failure applies to it. For that reason the worker always exits 0 after a refresh, failed or not: the failure is on Admin → Jobs and in Slack. Only a crash exits non-zero.

The image's `entrypoint.sh` runs a command it's given instead of migrations and the web server.

Railway's cron is UTC: the job exits within a second unless it's 17:00 or 22:00 in London, so exactly two runs happen a day through the clock changes.

**Set up (done 2026-10-11)**
1. **Service** `stats-worker`, from the GitHub repo, branch `main`, with the settings above.
2. **Variables:** `DATABASE_URL` = `${{Postgres.DATABASE_URL}}`, `JWT_SECRET_KEY`, `APISPORTS_KEY`, `API_FOOTBALL_BASE_URL`, `FRONTEND_BASE_URL`; add `SLACK_WEBHOOK_URL` once the webhook exists.
3. **Deploy `api`** with migration `0100`. The web app no longer recomputes valuations on start; the worker does.

**Live on Railway since 2026-10-11** (project `ravishing-laughter`, production):
- **Service:** `stats-worker`, connected to GitHub `main`; its first run was at 17:00 UK that day.
- **What it refreshes:** every competition in `world_leagues`. Production has 11: the top five leagues, Champions League, FA Cup, League Cup, Community Shield, FIFA Club World Cup and club friendlies.
  - Keeping all eleven was a product-owner decision (2026-10-11).
  - Syncing a competition also creates a player record for everyone who appears in it, so the cups and friendlies add players from outside the top leagues.
- **`backend`:** has `FRONTEND_BASE_URL` set to the frontend's Railway address since the same day, so links in emails and Slack point at the live app instead of `localhost:5173`.

**Running it by hand:** Admin → Jobs → **Run refresh now** (in the web app), or `railway run python -m app.jobs.daily_refresh --force [--steps stats,injuries,form,valuations]`.

**The first run on a new season** moves each league to API-Football's current season (`world_leagues.season`). Until a player has 450 minutes in the new season, his valuation stays at its last value: no new row is written.

## Email

Locally, email goes to Mailpit (`http://localhost:8025`). A deployed environment has to set real SMTP settings on the API service: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`, `SMTP_USE_TLS`, and `FRONTEND_BASE_URL` so the links in emails point at that environment's front end. Without `SMTP_HOST` every send is skipped and logged. That includes the per-event notification emails and the daily "waiting on you" digest (hourly job, one email per person per day, after 07:00 UTC).

Phone notifications (Web Push, [spec](../feature_spec/mobile-notifications/README.md)) need a VAPID key pair on the API service: `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY` and `VAPID_SUBJECT` (a `mailto:` address). Generate them once per environment with `python scripts/generate_vapid_keys.py`. Changing them later cuts off every device until it turns notifications on again. Without them, nothing is pushed and the app says push is off; in-app and email are unaffected.

Railway has the VAPID keys set on `backend`, so phone push works there.

> **TODO:** Railway has no SMTP configured, so no email is sent there: no invitations, digests or password-reset links. Decide on a provider and a sending domain.

## Data repairs

These one-off scripts aren't migrations, so nothing runs them on deploy. All of them have been run on Railway: verified by read-only queries on 2026-10-11, with no active contract lacking a wage, 21 clubs, 4 active contracts without an end date, and no players wrongly marked EXTERNAL.
- `backfill_contract_wages.py`
- `onboard_premier_league_clubs.py`
- `repair_player_statuses.py`
- `mock_contract_end_dates.py`. **Mock data:** it gives contracts plausible end dates for demos. Replace them with real dates before real use.
- `repair_listings_left_open_after_offer_accepted.py` (a no-op there).

If a new repair script is written, list it here until it has been run on Railway.

## Related documents

- [`../architecture/system-overview.md`](../architecture/system-overview.md) — the system being deployed
- [`../engineering/getting-started.md`](../engineering/getting-started.md) — the local-only equivalent that exists today
- [`monitoring-and-observability.md`](./monitoring-and-observability.md) — how a deployed system would be observed
