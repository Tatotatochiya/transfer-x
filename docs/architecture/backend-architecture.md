---
title: "Backend Architecture"
last_updated: 2026-10-11
status: Active
owner: "TODO — assign a Technical Owner"
---

# Backend Architecture

## Purpose

The FastAPI backend's module layout: what each module owns, and the background jobs.

## Scope

In scope: module boundaries, responsibilities and scheduled work.
Out of scope: endpoint reference ([`../engineering/api-reference.md`](../engineering/api-reference.md)), entities ([`data-model.md`](./data-model.md)).

## Table of Contents

- [Module layout](#module-layout)
- [Background jobs](#background-jobs)
- [Related documents](#related-documents)

## Module layout

Modules live under `backend/app/` and mostly follow `models.py` / `schemas.py` / `service.py` / `router.py`. Cross-module needs go through the other module's service layer. Verified against the directory listing on 2026-10-11.

**Market and deals**

| Module | Responsibility |
|---|---|
| `players` | Players, contracts, transfer history, injuries, the season ledger (`ledger.py`), profile views |
| `sales` | Listings (open to offers by default; auction as an advanced option; fixed price kept for existing listings) and bids |
| `offers` | Offers and counter-offers, including loans and anonymous buyers. The actions live in `actions.py`, which Lite's held sends call too |
| `enquiries` | Pre-offer conversations, open or anonymous |
| `deals` | The deal and its stage machine, the club-run paperwork checklist, and the deal room (`room_*`: terms versions, comments, attachments) |
| `loans` | Loan registration, recall, expiry and conversion of obligations ([ADR 0005](./decisions/0005-loan-registration-separate-from-ownership.md)) |
| `board` | The Transfers board: every player a club is buying or selling, once, at its furthest point (product ADR 0008) |
| `conversation` | One conversation per transfer, read across the existing message stores ([ADR 0008](./decisions/0008-one-conversation-read-across-existing-messages.md)) |
| `transfer_window` | Transfer windows and their enforcement |
| `valuation` | The fair-value model: `market-v2` engine, comparables, append-only `PlayerValuation` history ([spec](../feature_spec/valuation-model-v2.md)) |
| `scouting` | Shortlists and player interest |

**Clubs and people**

| Module | Responsibility |
|---|---|
| `auth` | Sign-in by email or username, JWT, refresh sessions and signed-in devices, password reset, account data export and deletion |
| `clubs` | Clubs, staff and the capability matrix (`capabilities.py`), invitations, finance and budget reservations, the squad check |
| `approvals` | Spending approvals above a club's thresholds |
| `agents`, `mandates` | Agent profiles, deal invitations, negotiation and commission; representation mandates and client alerts |
| `verification` | Verification requests for clubs, agents and players |
| `lite` | Lite mode: preferences, the home, the buy flow, held sends with undo ([ADR 0007](./decisions/0007-held-sends-for-undo.md)), team contact |
| `dashboard` | The club's "waiting on you" aggregate; owns no models |
| `notifications` | In-app notifications, email, the daily digest, Web Push with tiers, quiet hours and the morning summary |
| `admin` | Staff administration, with every change audited with a reason |
| `audit` | The append-only audit log |

**Data, AI and platform**

| Module | Responsibility |
|---|---|
| `vendor` | API-Football client and sync (`sync.py`, `history.py`) |
| `stats` | Season stats, snapshots, form, injury and fixture records, vendor sync bookkeeping |
| `world` | Real-world leagues and teams; `world_leagues` is the list of competitions the data refresh syncs |
| `enrichment` | Valuation and wage provider adapters (no-op while all sources are MANUAL) |
| `fixtures` | Fixture cache |
| `fx` | Exchange rates for display estimates only; deals are in pounds |
| `ai` | The assistant ([ADR 0006](./decisions/0006-ai-assistant-advises-from-scoped-facts.md)) and Ask TransferX's analyst (`ai/analyst/`: read-only, club-scoped tools) |
| `jobs` | Work run outside the web app: `daily_refresh.py`, the stats-worker's data refresh |
| `monitoring` | Job runs and their logs, error tracking, request health, retention ([operations](../operations/monitoring-and-observability.md)) |
| `analytics` | Product usage events |
| `ws` | WebSocket connections for live refresh |
| `common` | Shared schemas, masking, scheduler job records (`jobs.py`), Slack (`slack.py`) |
| `routers` | Health check and global search |

## Background jobs

**In the web app.** These run on APScheduler (`app/main.py`). Each runs shortly after start, then on its interval. Admin → Jobs lists them with their last and next runs.

| Job | Every | What it does |
|---|---|---|
| `execute_held_actions` | 2 s | Sends Lite actions whose undo window has closed |
| `close_expired_sales` | 1 min | Closes listings past their deadline |
| `expire_stale_offers` | 5 min | Expires offers past their validity |
| `release_held_pushes` | 5 min | Sends pushes held back by quiet hours |
| `email_fallback` | 5 min | Emails "your move" pushes left unread for 30 minutes |
| `morning_summary` | 15 min | Morning summary pushes, at each person's time |
| `notify_upcoming_events` | 1 h | Reminders: offers expiring, auctions ending, instalments due |
| `daily_digest` | 1 h | The daily "waiting on you" email, once a day each |
| `refresh_watch` | 1 h | Slack alert when the 17:00 or 22:00 data refresh didn't run |
| `client_alerts` | 6 h | Agents' client alerts (contract expiry, valuation change, interest) |
| `enrichment_sync` | 24 h | External valuation and wage enrichment |
| `approval_expiry` | 24 h | Expires pending approvals and tells the requester |
| `expire_mandates` | 24 h | Expires mandates past their end date |
| `deal_sla` | 24 h | Flags deals stuck in pending completion past their SLA deadline (flags; doesn't collapse) |
| `real_world_alerts` | 1 h | Tells each club which of its players API-Football has at other clubs: one notification listing them, again only when the list grows (`players/real_world.py`) |
| `deadline_reminders` | 15 min | Deadline day: pushes each club with transfers open once at 24, 6 and 2 hours before the window closes (`app/deadline/`) |
| `loan_lifecycle` | 24 h | Returns loans at expiry, warns two weeks ahead, converts obligations |
| `monitoring_retention` | 24 h | Deletes monitoring data past retention |

**In the `stats-worker` service.** `python -m app.jobs.daily_refresh` runs at 17:00 and 22:00 UK time:
- current-season stats, injuries, match ratings and form;
- at 22:00, transfer histories for players at TransferX clubs, then the valuation recompute.

See the [spec](../feature_spec/scheduled-data-refresh.md).

## Related documents

- [`system-overview.md`](./system-overview.md): the services this runs in
- [`data-model.md`](./data-model.md): entities owned by these modules
- [`authentication-and-permissions.md`](./authentication-and-permissions.md): how access is enforced
