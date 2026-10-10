---
title: "Monitoring & Observability"
last_updated: 2026-10-10
status: Active
owner: "TODO — assign an Operations Owner"
---

# Monitoring & Observability

## Purpose

How TransferX's health and behaviour are observed: scheduled jobs, logs, errors, request health and alerts. Built per [`feature_spec/scheduled-data-refresh.md`](../feature_spec/scheduled-data-refresh.md). Everything is inside TransferX, under Admin, for platform admins only (decision D6).

## Scope

In scope: what is monitored, where to look, and what alerts.
Out of scope: incident handling (see [`incident-response.md`](./incident-response.md)).

## Table of Contents

- [Where to look](#where-to-look)
- [Jobs](#jobs)
- [Logging](#logging)
- [Errors](#errors)
- [Metrics](#metrics)
- [Alerting](#alerting)
- [Retention](#retention)
- [Related documents](#related-documents)

## Where to look

| Question | Admin page |
|---|---|
| Did the data refresh run, and what did it do? | **Jobs**: scheduled, running now, recent runs, each run's steps and log |
| What's going wrong? | **Errors**: warnings and errors grouped into issues |
| Is the platform healthy right now? | **Health**: services (database, email, push, AI, API-Football, Slack, data refresh), requests in the last 24 hours, web-app jobs, data integrity |
| Everything else (raw logs) | Railway's log view for the `api` and `stats-worker` services |

## Jobs

**Two places run jobs:**
- **The `stats-worker` Railway cron service** runs the data refresh at 17:00 and 22:00 UK time (`app/jobs/daily_refresh.py`), with the valuation recompute after the 22:00 run.
- **The web app** runs about 16 short APScheduler jobs (`app/main.py`).

**Recorded in `job_runs` (migration 0100):**
- every refresh, each of its steps, and manual runs;
- every run of web-app jobs that run hourly or less often;
- for jobs that run every few seconds or minutes, only failures and the first success after a failure.

A run that stays "running" for over 2 hours shows as **lost**, which means its process died.

## Logging

- **Format:** Python `logging` to stdout in both services; Railway keeps the raw logs.
- **Run logs in TransferX:** while a refresh runs, its lines at INFO and above are also kept in `job_run_logs`, at most 5,000 a run. Admin → Jobs shows them with a live tail.
- **Hygiene:** log messages must not contain passwords, tokens, wages or fees. `tests/test_monitoring.py` checks the auth and finance modules.

## Errors

**What's captured**
- WARNING and above from the web app and the worker, plus uncaught request exceptions with their route.
- Browser errors, posted to `POST /monitoring/client-errors`. Each message is sent once per page load, at most 10 a load, and limited server-side per user or address.

**Grouping.** Events are grouped into **issues** by fingerprint: the exception type and the app frame it was raised in, or the logger and message template with ids and numbers removed.

**Per issue:** a count, first and last seen, a 24-hour sparkline, and its newest 20 events with traceback and request context (method, path, status, request id, user id; never bodies or query strings).

**Statuses**
- Admins can mark an issue resolved or ignored.
- A resolved issue that happens again reopens.
- Ignored issues are counted but never alert.
- The scheduler's own timing warnings are not captured.

## Metrics

**Request figures.** `request_minutes` holds requests per endpoint per minute: count, 5xx count, p50 and p95 latency. They're aggregated in memory by `MonitoringMiddleware` and written every 30 seconds. Every response carries an `X-Request-ID`.

**Admin → Health shows:**
- the last 24 hours per hour;
- the slowest endpoints (p95);
- the endpoints with the most server errors.

## Alerting

Slack, through an Incoming Webhook (`SLACK_WEBHOOK_URL` on both services). Messages carry titles and counts only.

| Alert | When |
|---|---|
| Data refresh | One message per run: ✅, ⚠️ partial, or ❌ failed with what didn't finish |
| Refresh didn't run | Hourly check: no cron run for the latest 17:00 or 22:00 slot, 45 minutes after it |
| Web-app job failed / recovered | At most once an hour per job |
| New error / error is back | A new ERROR issue, or a resolved one reopening |
| Error spike / over | One issue 50 times in 10 minutes; and when it drops below 10 |
| Server errors | 5xx above 5% of requests over 5 minutes (20+ requests); and when back to normal |

No webhook set: nothing is posted, and Admin → Health says so.

## Retention

The daily `monitoring_retention` job deletes:
- run logs and error events after 30 days;
- job runs after 90 days;
- issues 90 days after last seen;
- request figures after 14 days.

## Related documents

- [`environments-and-deployment.md`](./environments-and-deployment.md): the `stats-worker` service setup
- [`incident-response.md`](./incident-response.md): what happens when an alert fires
- [`../security-and-compliance/data-privacy-and-legal.md`](../security-and-compliance/data-privacy-and-legal.md): monitoring data as a data store
