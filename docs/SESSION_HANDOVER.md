---
title: "Session Handover"
last_updated: 2026-10-11
status: Active
owner: "TODO — assign a Documentation Owner"
---

# Session Handover

## Purpose

The single, current handover note between one working session and the next, human or Claude. Read it at the start of every session, right after [`PRODUCT_SPEC.md`](./PRODUCT_SPEC.md).

## Scope

In scope: the latest session's summary, what's in motion now.
Out of scope: history ([`CHANGELOG.md`](./CHANGELOG.md)). This file is overwritten, not appended to.

## How this file works

Overwritten at the end of each session by the [`session-lifecycle`](../.claude/skills/session-lifecycle/SKILL.md) skill. It holds exactly one thing: the latest summary.

## Latest Session Summary

## Session Summary — 2026-10-11

**Where things are**
- **Code:** `main` holds everything; PRs #31–#38 were merged this session. The docs review is on branch `docs-review`.
- **Railway** (project `ravishing-laughter`, production):
  - deploys `main` automatically;
  - is at migration `0100`;
  - runs `backend`, `frontend`, `Postgres` and the new `stats-worker` (cron 17:00 and 22:00 UK).
- **Local tooling:**
  - The Railway CLI is installed at `~/.local/bin/railway` and linked to the project.
  - `gh` is authenticated.
  - Commits are authored per command as `Tatotatochiya <aashishpradhan@outlook.com>`.
- **Local dev database** is at `0100`. Its competitions were moved to the 2026/27 season by a live refresh.

**Completed work** (detail in [`CHANGELOG.md`](./CHANGELOG.md)):
- **AI analyst, phases A and B** (Ask TransferX at `/ask`): 17 read-only, club-scoped tools, charts, Excel export and "Ask about this". Eval 71/72.
- **Transfers board:** Buying and Selling lanes. **My Club:** "in play" status on squad rows.
- **Valuation model v2** (`market-v2`), shipped uncalibrated by decision.
- **Scheduled data refresh** (the `stats-worker`) with Admin Jobs (run logs, live tail, Run refresh now), Errors (grouped issues from API, worker and browsers) and request health. Slack posting is built and waits for a webhook.
- **Railway setup with the CLI:** the `stats-worker` service and its variables, and `FRONTEND_BASE_URL` on the backend.
- **Docs review** (this branch):
  - every main doc rewritten from the code;
  - the design system moved to `docs/design-system/`;
  - build-only files removed (prototypes, session plans, screenshots, the August audit, the redesign plan);
  - open audit findings carried into `IMPLEMENTATION_STATUS.md`;
  - the root `README.md` rewritten.

**Important decisions** (product owner):
- Ship valuation v2 before calibration; calibration is a TODO.
- The refresh runs twice a day (17:00 and 22:00 UK). Valuations are recomputed only after the 22:00 run, and moved out of the web app.
- Keep jobs, logs and errors inside TransferX (no Cronicle, Healthchecks or Sentry).
- Refresh all 11 production competitions, cups and club friendlies included.

**Outstanding work**
- **Product owner:**
  - send the Slack webhook (set `SLACK_WEBHOOK_URL` on `backend` and `stats-worker`);
  - choose an SMTP provider for Railway;
  - do the real-phone notification test ([runbook](./feature_spec/phased-plan-2026-q4/phase-0-runbook.md)).
- **Valuation calibration:** run `scripts/valuation_backtest.py` against production, then tune the anchors and curve ([spec](./feature_spec/valuation-model-v2.md#calibration-archetypes-not-a-backtest)).
- **Watch the first production refreshes** on Admin → Jobs. The first run moves every competition to 2026/27 and adds cup and friendlies squads.
- **Known gaps:** see [`IMPLEMENTATION_STATUS.md`](./IMPLEMENTATION_STATUS.md#known-gaps).

**Risks**
- **Shared password on Railway:** every Railway account shares one password. Fine for a demo, not for a real club.
- **Season switch:** players with under 450 minutes in the new season keep their last valuation, so values can lag early in a season.
- **AI state in memory:** the cache and rate limit need a shared store before a second API process.
- **Two places run jobs:** the web app (APScheduler) and the `stats-worker`. A long job added to the web app would slow requests; put it in the worker.

**Recommended next task**
- Set the Slack webhook and check the first two production refreshes. Then do valuation calibration against production data.

**Checks, as of 2026-10-11:**
- Backend 877 passed.
- vitest 250 passed.
- `tsc -b` 0 errors.

## Related documents

- [`PRODUCT_SPEC.md`](./PRODUCT_SPEC.md): read first
- [`IMPLEMENTATION_STATUS.md`](./IMPLEMENTATION_STATUS.md): verified state and gaps
- [`CHANGELOG.md`](./CHANGELOG.md): history
