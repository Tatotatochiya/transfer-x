---
title: "Feature Spec: Scheduled Data Refresh, Job Tracking and Slack Status"
last_updated: 2026-10-10
status: Proposed — ready to build (Slack details pending)
owner: "TODO — assign a Product Owner"
---

# Feature Spec: Scheduled Data Refresh, Job Tracking and Slack Status

## Purpose

Refresh player stats from API-Football twice a day without anyone running a script. Recompute valuations once a day on fresh stats. Show every scheduled job, running or due, in one admin page. Post one Slack message per refresh run.

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

1. **`job_runs` and the run recorder:** migration, model, and a context manager that records start and finish. In-app scheduler jobs report through it.
2. **The worker:** `app/jobs/daily_refresh.py` with steps, UK-time gate, lock and quota guard. Run with `--force` on dev to measure duration and API calls.
3. **Move `valuation_compute`** out of the web app (D3).
4. **Slack:** `app/common/slack.py`, the run message, in-app failure messages and the overdue check, with a fake webhook in tests.
5. **Admin → Jobs page:** API and UI, including Run refresh now.
6. **Railway service and the Slack webhook** (product owner), then watch the first two runs.

Estimate: about 1.5–2 days, plus the Railway setup.

## Open items

> **TODO:** Slack workspace, channel and webhook URL (product owner, to follow).

> **TODO:** confirm the reserve of 500 requests suits any other API-Football use (admin vendor pages, profile backfills).

## Related

- [Valuation Model v2](./valuation-model-v2.md): the daily recompute this moves
- [Player Profile Ledger](./player-profile-ledger/README.md): the injury and history data this keeps current
- `backend/app/vendor/`: the sync code the worker reuses
