---
title: "Incident Response"
last_updated: 2026-10-11
status: Active
owner: "TODO — assign an Operations Owner"
---

# Incident Response

## Purpose

What to do when something breaks on Railway: where to look, how to fix or roll back, and what to record.

## Scope

In scope: the practical steps for today's single Railway environment.
Out of scope: how problems are detected ([`monitoring-and-observability.md`](./monitoring-and-observability.md)).

## Table of Contents

- [Current state](#current-state)
- [Where to look](#where-to-look)
- [Common problems](#common-problems)
- [Fixing and rolling back](#fixing-and-rolling-back)
- [After an incident](#after-an-incident)
- [Related documents](#related-documents)

## Current state

**Today:** Railway holds demo data and no real club depends on it, so there are no on-call rota or response times.

**Signals:**
- Slack alerts, once `SLACK_WEBHOOK_URL` is set;
- Admin → Errors, Jobs and Health;
- Railway's logs.

> **TODO:** Set severity levels, response times and who is called before a real club uses TransferX.

## Where to look

| Question | Look at |
|---|---|
| Is the site up? | `https://backend-production-ace3.up.railway.app/health`, then `railway service list` |
| What's erroring? | Admin → Errors (grouped, with tracebacks and the request); Admin → Health → Requests (5xx rate, failing endpoints) |
| Did a scheduled job fail? | Admin → Jobs (each run, its steps and log) |
| Raw logs | `railway logs --service backend` (or `stats-worker`) |
| Did a deploy cause it? | Railway → Deployments: the time and commit of the latest deploy |

## Common problems

| Symptom | Likely cause | What to do |
|---|---|---|
| Backend won't start after a deploy | A migration failed | `railway logs --service backend`. Fix the migration and push, or roll back (below) |
| "Data refresh didn't run" | `stats-worker` missing, failed to build, or out of quota | Railway → `stats-worker` deployments; Admin → Jobs; run it from Admin → Jobs → Run refresh now |
| Refresh is partial | API-Football quota reserve reached, or one competition failed | The run's "Not done" list in Admin → Jobs; it catches up on the next run |
| Emails not arriving | No SMTP on Railway | Expected until SMTP is set ([environments](./environments-and-deployment.md#email)) |
| No phone pushes | VAPID keys changed or missing | Check `VAPID_*` on `backend`. A changed key needs every device to turn notifications on again |
| A club's budget looks wrong | A money path interrupted mid-way | Admin → Clubs → the club's commitments; budget edits need a reason and are audited |

## Fixing and rolling back

- **Fix forward.** Merge a fix to `main` and Railway deploys it.
- **Roll back.** Railway → the service → Deployments → Redeploy an earlier one. A migration that already ran stays applied. If the old code can't run against the new schema, fix forward instead.
- **Data fixes.** Use a reviewed script under `backend/scripts/`, run with `--dry-run` first. Never hand-edit money rows. Admin actions are audited with a reason.

## After an incident

Record what happened, its cause and the fix in the PR that fixes it. If it changed how something works, add it to `CHANGELOG.md`. If it revealed a gap, add it to the known gaps in `IMPLEMENTATION_STATUS.md`.

## Related documents

- [`monitoring-and-observability.md`](./monitoring-and-observability.md)
- [`environments-and-deployment.md`](./environments-and-deployment.md)
