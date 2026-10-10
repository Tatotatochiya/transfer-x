---
title: "Feature Spec: Scheduled Data Refresh, Jobs, Monitoring and Slack"
last_updated: 2026-10-10
status: Built 2026-10-10 — Railway stats-worker service and Slack webhook pending (product owner)
owner: "TODO — assign a Product Owner"
---

# Feature Spec: Scheduled Data Refresh, Jobs, Monitoring and Slack

## Purpose

Refresh player stats from API-Football twice a day without anyone running a script, and recompute valuations once a day on fresh stats. Then give platform admins one place in TransferX to see:
- every scheduled job, running or due, and what each run logged;
- the errors happening across the web app and the worker;
- the health of the platform.

Slack gets one message per refresh run, plus alerts.

## Today

- **API-Football data is only fetched by hand.** Someone runs `scripts/sync_leagues.py` or uses the admin vendor endpoints. The daily `enrichment_sync` job is a different feed (ETV and Transfermarkt valuations and wages).
- **Every scheduled job runs inside the web app.** About 16 APScheduler jobs run in the FastAPI process (`app/main.py`).
  - Each "daily" job also runs about 15 seconds after every restart. That includes `valuation_compute`, so every deploy appends a valuation row for every eligible player.
- **The admin Health page shows only each in-app job's last run** (`scheduler_job_runs`, migration 0092). There's no history, no "running now", and nothing about work done outside the web app.

## Decisions (2026-10-10)

| # | Decision |
|---|---|
| D1 | The refresh runs as a **separate Railway cron service** (`stats-worker`), built from the same repo and `backend/` code. It runs one command and exits. Not a separate codebase, and no queue system. |
| D2 | **Twice a day, at 17:00 and 22:00 UK time.** The API-Football Pro plan (7,500 requests a day) covers both runs comfortably. |
| D3 | The **daily valuation recompute moves into the worker**, after the 22:00 run only. It's removed from the web app's scheduler, so deploys no longer trigger it. One run a day keeps the append-only history at one row per player per day. |
| D4 | **One Slack message per run**, success or failure. Plus a message when an in-app job fails and when a refresh is overdue. Slack workspace and channel details to follow. |
| D5 | Running and scheduled jobs are tracked in an **admin Jobs page**. |
| D6 | **Everything stays inside TransferX:** no Cronicle, Healthchecks.io or Sentry. Job tracking, run logs, error tracking and health are built in the admin area (2026-10-10). |
| D7 | **TransferX is not a general log store.** It keeps logs for each job run, warnings and errors grouped into issues, and per-minute request figures, each with retention. Full raw logs stay in Railway, linked from the admin pages. |

## How it works

### The worker service

Command: `python -m app.jobs.daily_refresh` (`--force` runs regardless of the time; `--steps` runs a subset).

**UK time from a UTC cron.** Railway's cron uses UTC, and UK time moves an hour between winter (GMT) and summer (BST).
- The cron is `0 16,17,21,22 * * *`.
- The job runs only if the local time in `Europe/London` is 17:00 or 22:00, and otherwise exits within a second as "skipped".
- So exactly two runs happen each day, all year.

**Steps, in order.** Each is isolated: one league failing doesn't stop the others.

| Step | What | Runs at |
|---|---|---|
| 1. `stats` | Current-season player stats for the configured leagues (today the 11 in `sync_leagues.py`), using `sync_league`. Past seasons don't change and are skipped. | 17:00, 22:00 |
| 2. `injuries` | Current-season injuries for each league (`sync_league_injuries`) | 17:00, 22:00 |
| 3. `form` | Team fixture counts and recent ratings, then `compute_all_form` | 17:00, 22:00 |
| 4. `valuations` | `compute_all_valuations` (one comparables index for the run) | 22:00 only |
| 5. Report | Finish the run record and post to Slack | both |

**Safeguards**
- **One run at a time.** A Postgres advisory lock covers the whole run. A manual run and the cron run can't overlap; the second one records "skipped: already running".
- **API quota.** The client reads API-Football's `x-ratelimit-requests-remaining` header.
  - It stops calling the API before the remaining requests fall below a reserve (500), and marks the run "partial".
  - The next run starts with whatever the stopped run didn't finish.
- **Expected calls:** roughly 400–600 a run, so about 1,200 a day out of 7,500.
- **Leagues as configuration:** the league list lives in one constant, not in a script, so adding a league is a one-line change.

### Job tracking

**A new table, `job_runs`** (one migration), records every run of every job: worker steps, manual runs, and in-app scheduler jobs.

| Column | |
|---|---|
| `id`, `job` | e.g. `daily_refresh`, `daily_refresh.stats`, `valuation_compute`, `close_expired_sales` |
| `trigger` | `cron`, `manual` (with `triggered_by_user_id`) or `scheduler` |
| `status` | `running`, `succeeded`, `partial`, `failed` or `skipped` |
| `started_at`, `finished_at`, `duration_ms` | |
| `summary` | JSON counts, e.g. leagues, players updated, injuries, valuations, API calls used and remaining |
| `error` | Truncated message |

**Writing and keeping runs**
- A run inserts `running` when it starts and updates the row when it ends.
- A `running` row older than 2 hours is shown as **"lost"**: the process died without finishing.
- In-app jobs that run every few seconds or minutes record only failures and the first success after a failure, so the table doesn't fill with routine success rows. Their last run stays in `scheduler_job_runs`, as today.
- Runs are kept for 90 days.

`vendor_sync_runs` stays as the per-operation detail for vendor calls. A `job_runs` row links to the vendor rows written during it.

**Admin → Jobs page** (new, next to Health):
- **Scheduled:** every job, with its schedule in words ("17:00 and 22:00 UK", "every 5 minutes"), where it runs (worker or web app), its last run with status, and its next run.
  - The worker's next run comes from D2.
  - The web app's next run comes from APScheduler's `next_run_time`.
- **Running now:** any `running` row, and how long it has been going.
- **Recent runs:** newest first, filterable by job and status. A row opens its summary and error.
- **Run refresh now:** for platform admins. It starts the same job in the web app as a background task, under the same lock and recorded as `manual`. It's meant for occasional use, such as after adding a league. The two scheduled runs stay in the worker.

### Slack

**Delivery.** A Slack Incoming Webhook stored as `SLACK_WEBHOOK_URL` on both Railway services. `app/common/slack.py` provides `post(text, blocks)`.
- It never raises: a Slack outage must not fail a job.
- It does nothing when the variable isn't set, as in dev and tests.

**Messages**
- **Each refresh run, exactly one message:**
  > ✅ Data refresh, 22:00 · 6m 12s · 11 leagues · 4,980 players updated · 312 injuries · 2,425 valuations · API calls 438 (6,624 left today)
  - Partial runs say ⚠️ and show what didn't finish.
  - Failed runs say ❌, name the failed step and the error, and link to Admin → Jobs.
- **When an in-app job fails:** posted from the existing listener in `app/common/jobs.py`, at most once per job per hour, with a recovery message when it next succeeds.
- **When a refresh is overdue:** an hourly check in the web app posts "No data refresh since <time>" if the last successful refresh is more than 7 hours old during the day, or past the next expected run. A cron run that never starts can't report on itself, so this catches it.

**Confidentiality.** Slack messages carry counts, durations and errors only. They never include club names, fees, bids, or player-level deal information.

## Monitoring (D6, D7)

Everything below is for platform admins only, under Admin.

### Run logs

**Capture.** While a job runs, a logging handler collects that run's log lines at INFO and above. Stored in `job_run_logs`: run id, time, level, logger, message.
- Lines are flushed every 5 seconds, so a running job can be followed live.
- Capped at 5,000 lines a run. Past the cap, a final line says how many were dropped.

**Viewing.** On the Jobs page, a run opens to its log:
- a level filter (all / warnings and up / errors) and a search box;
- for a running job, a live tail that polls every 3 seconds and stops when the run ends.

**Retention:** 30 days.

### Error tracking

**Capture.** A logging handler at WARNING and above in both services (web app and worker), plus FastAPI's handler for uncaught request exceptions.

**Grouping.** Each event is grouped into an **issue** by a fingerprint: service, logger, exception type, and the message with numbers, UUIDs and quoted values stripped out.

**Storage**
- **Each issue** keeps its title, level, service, status (open / resolved / ignored), first seen, last seen, a count, and a 24-hour sparkline.
- **The last 20 events per issue** keep the traceback and context: request method and path, status code, request id, user id. Request bodies, headers and query values are never stored.

**Admin → Errors page**
- Issues sorted by last seen, filterable by service, level and status.
- An issue opens to its recent events and tracebacks.
- Admins can mark an issue resolved or ignored. A resolved issue that happens again reopens and counts as new for Slack.

**Frontend errors.** Browser errors (`window.onerror` and unhandled promise rejections) are posted to `POST /monitoring/client-errors`, rate-limited per user, and grouped the same way under service `web`.

**Writing safely**
- Events go through an in-memory queue to a background writer, so logging never blocks a request.
- The writer ignores its own logs, so it can't loop on itself.
- Counts for a busy issue are batched.

**Retention:** events 30 days, issues 90 days after last seen.

### Health

The existing Admin → Health page gains three sections:
- **Requests:** a middleware aggregates requests per minute into `request_minutes` (endpoint pattern, count, 5xx count, p50 and p95 latency).
  - The page shows the last 24 hours: requests, error rate, and the slowest and most-failing endpoints.
  - Retention: 14 days.
- **Dependencies, checked when the page loads:**
  - database reachable, and its connection pool;
  - SMTP configured and reachable;
  - API-Football quota remaining (from the last response);
  - push (VAPID) configured;
  - Slack webhook configured.
- **Jobs:** each job's last run, as today, with a link to the Jobs page.

### Slack alerts from monitoring

Alerts are rate-limited, and carry titles and counts only:
- a **new issue** (or a resolved one that reopens) at ERROR level;
- a **spike:** one issue more than 50 times in 10 minutes, or the 5xx rate above 5% for 5 minutes;
- **recovery,** when a spike ends.

### Privacy

- **No Slack tracebacks:** Slack never receives tracebacks or event context. It gets a title (truncated to 120 characters) and a link.
- **Admins only:** run logs and error events can contain personal data from log messages, so only platform admins can see them, retention is limited, and they're listed in [`security-and-compliance/`](../security-and-compliance/) as a data store.
- **Log hygiene:** log messages must not include passwords, tokens, wages or fees. The existing code already follows this; a test checks the auth and finance modules' log calls.

## Railway setup (one-off)

1. **New service** from the same GitHub repo:
   - root `backend`;
   - start command `python -m app.jobs.daily_refresh`;
   - cron schedule `0 16,17,21,22 * * *`;
   - restart policy "never".
2. **Variables:** `DATABASE_URL` (a reference to the database variable), `APISPORTS_KEY`, `SLACK_WEBHOOK_URL`, and the other settings `app.config` requires.
3. **Slack:** api.slack.com → create an app → Incoming Webhooks → add to the chosen channel → copy the URL.
4. Deploy the web app with `valuation_compute` removed from its scheduler (D3).

## Build order

**Part 1: the refresh and job tracking** (about 1.5–2 days)
1. **`job_runs` and the run recorder:** migration, model, and a context manager that records start and finish. In-app scheduler jobs report through it.
2. **The worker:** `app/jobs/daily_refresh.py` with steps, UK-time gate, lock and quota guard. Run with `--force` on dev to measure duration and API calls.
3. **Move `valuation_compute`** out of the web app (D3).
4. **Slack:** `app/common/slack.py`, the run message, in-app failure messages and the overdue check, with a fake webhook in tests.
5. **Admin → Jobs page:** API and UI, including Run refresh now.
6. **Railway service and the Slack webhook** (product owner), then watch the first two runs.

**Part 2: monitoring** (about 2–2.5 days)

7. **Run logs:** `job_run_logs`, the per-run handler, and the log view with live tail.
8. **Error tracking:** issues and events tables, the logging handler and request-exception hook, fingerprinting, and the Admin → Errors page.
9. **Frontend errors:** the browser hook and `POST /monitoring/client-errors`.
10. **Health:** request-minute middleware, dependency checks, and the new Health sections.
11. **Monitoring alerts** to Slack, and a daily retention clean-up job.

Each part ships on its own. Part 1 is useful without Part 2.

## Build notes (2026-10-10)

**Built as specified (Parts 1 and 2).** The code:
- `app/jobs/daily_refresh.py` (the worker);
- `app/monitoring/` (runs, errors, requests, watch, retention, router; migration `0100`);
- `app/common/slack.py`;
- Admin **Jobs** and **Errors** pages, and new sections on Admin **Health**.

**Changes found while building and running it on dev**

1. **The current season.** Every league was still on season 2025 (2025/26, finished), so the refresh would have synced last season.
   - Each run now asks API-Football for each league's current season (`/leagues?current=true`, one call per league) and moves `world_leagues.season` when it changes.
   - The first dev run moved all 7 leagues to 2026.
   - Until a player reaches 450 minutes in the new season, his valuation stays at its last value.
2. **Stat snapshots only when something changed.** `sync_league` wrote a full snapshot of every player on every sync, which twice a day would be about 5 million rows a year. It now writes one only when appearances, minutes or rating changed.
3. **One stats row per club.** The league sync failed with "multiple rows" for players who moved club within a competition mid-season. The history backfill stores one row per club, and the league sync now matches on the club too.
4. **Recent match ratings come from matches finished since the last run.** That's one `/fixtures` call per league, plus `/fixtures/players` per new match. The old per-team "last 5" sync would cost about 1,300 calls a run.
5. **API-Football's own errors are retried.** A `{"bug": …}` answer is retried twice.
6. **The API key's allowance is 75,000 requests a day,** not 7,500: a bigger plan than Pro. A refresh uses about 290 calls on dev with 7 leagues.
7. **The scheduler's timing warnings** ("missed by", "maximum running instances") aren't captured as errors. Job failures are recorded and alert through the job listener.
8. **Tests can't write monitoring data to a real database.** `tests/conftest.py` points monitoring at the test database, or at nothing.

**Verified on dev**
- **Live refresh:** two runs, `--force`.
  - The second moved 7 leagues to 2026/27 and updated 3,444 players with 1,581 new.
  - It also stored 2,475 injury records and 4 new matches (164 ratings), and updated 6,693 form scores.
  - It used 290 API calls and took 3 minutes 52 seconds.
- **Backend:** 36 new tests in `tests/test_monitoring.py`, and the full suite.
- **Frontend:** 7 new tests (Jobs, Errors, error reporting).
- **Browser:** checked as admin.

## Open items

> **TODO:** Slack workspace, channel and webhook URL (product owner, to follow). Set `SLACK_WEBHOOK_URL` on both Railway services.

> **TODO:** create the `stats-worker` Railway service ([setup](../operations/environments-and-deployment.md#the-stats-worker-service-scheduled-data-refresh)).

> **TODO:** confirm whether non-admin club staff ever need to see job status (assumed not; admins only).

> **TODO:** confirm the reserve of 500 requests suits any other API-Football use (admin vendor pages, profile backfills).

## Related

- [Valuation Model v2](./valuation-model-v2.md): the daily recompute this moves
- [Player Profile Ledger](./player-profile-ledger/README.md): the injury and history data this keeps current
- `backend/app/vendor/`: the sync code the worker reuses
