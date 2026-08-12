---
title: "Backend Architecture"
last_updated: 2026-08-11
status: Active
owner: "TODO — assign a Technical Lead"
---

# Backend Architecture

## Purpose

Documents the FastAPI backend's module layout — what each module owns and where to find it.

## Scope

In scope: module boundaries and responsibilities.
Out of scope: individual route/endpoint reference (see [`../engineering/api-reference.md`](../engineering/api-reference.md)), entity/schema detail (see [`data-model.md`](./data-model.md)).

## Table of Contents

- [Module layout](#module-layout)
- [Background jobs](#background-jobs)
- [Related documents](#related-documents)

## Module layout

Each module under `backend/app/` follows a `models.py` / `schemas.py` / `service.py` / `router.py` layering.

| Module | Responsibility |
|---|---|
| `auth` | Login/register, JWT issuance, `get_current_user` |
| `clubs` | Club profiles, staff + roles/capabilities (`capabilities.py` — the single capability matrix, TRA-151), staff invitations, finance |
| `approvals` | Spending-authority approvals (Phase 5): threshold capture of MANAGER money actions, decision endpoints, re-validated execution, daily expiry |
| `players` | Player records, contracts |
| `sales` | Listings (auction / fixed price / open to offers), bids |
| `offers` | Direct offer negotiation |
| `deals` | Deal lifecycle and stage machine (includes `deals/room_*` — the deal room: versioned terms, comments, attachments) |
| `dashboard` | Cross-module read aggregation for the club "waiting on you" view (B2) — calls into `offers`/`deals`/`sales`/`approvals`' own service-layer functions, owns no models of its own |
| `agents` | Agent profiles, deal invitations, negotiation, negotiation messaging, commissions |
| `mandates` | Agent–player representation mandates, client alerts |
| `verification` | Verification request workflow (club/agent/player) |
| `notifications` | In-app + email notifications, preferences |
| `audit` | Append-only audit log |
| `scouting` | Shortlists, player interest |
| `stats` | Player statistics and form; also owns `VendorSyncState`/`VendorSyncRun` (current state + full per-run history of every vendor sync operation) |
| `vendor` | External stats provider (API-Football) client and sync — manual/admin-triggered only via `/admin/vendor` (`sync_league`/`sync_team`/`sync_player`/`compute_form`); no scheduled job runs it |
| `enrichment` | Valuation/wage enrichment provider adapters |
| `valuation` | Fair-value model (TRA-91): pure scoring engine + `FeatureProvider` seam, append-only `PlayerValuation` history, daily recompute job |
| `fixtures` | Fixture cache |
| `world` | Real-world team/league reference data |
| `transfer_window` | Transfer window open/close administration and enforcement |
| `analytics` | Product usage analytics ingestion |
| `ai` | AI-assisted features (search, scouting, etc.) |
| `admin` | Superuser administration endpoints |
| `ws` | WebSocket connection manager for real-time updates |
| `common` | Shared schemas |
| `routers` | Cross-cutting routes (health check, global search) |

> **TODO:** Add one-line descriptions for any module above that a reader would find ambiguous, and flag here if this table drifts from the actual `backend/app/` directory listing.

## Background jobs

Scheduled jobs run in-process via APScheduler (see `backend/app/main.py`). Verified against the code 2026-08-08 — two jobs (`expire_mandates`, `deal_sla`) were missing from this table despite being registered; re-grepped the full `add_job` list directly rather than trusting the previous version of this table:

| Job id | Interval | What it does |
|---|---|---|
| `close_expired_sales` | 1 min | Closes sales past their deadline |
| `expire_stale_offers` | 5 min | Expires offers past their validity window |
| `notify_upcoming_events` | 1 h | Reminder notifications for upcoming events |
| `client_alerts` | 6 h | Agent client-roster alerts (contract expiry, valuation change, interest) |
| `enrichment_sync` | 24 h | External valuation/wage enrichment (no-op while all sources are MANUAL) — distinct from the `vendor` module's player-stats sync, which has no scheduled job at all |
| `valuation_compute` | 24 h | Recomputes every player's fair-value model valuation (TRA-91); registered after `enrichment_sync` so it runs on fresher stats |
| `approval_expiry` | 24 h | Expires pending spending approvals past their 24-hour window and notifies requesters |
| `expire_mandates` | 24 h | Expires agent mandates past their validity period |
| `deal_sla` | 24 h | Enforces each deal's `sla_deadline` |

> **TODO:** The last two rows' exact behaviour (e.g. whether `deal_sla` collapses the deal outright or just flags/notifies) hasn't been independently verified against the code — confirm before relying on the specifics.

## Related documents

- [`system-overview.md`](./system-overview.md) — where this fits in the overall stack
- [`data-model.md`](./data-model.md) — entities owned by these modules
- [`authentication-and-permissions.md`](./authentication-and-permissions.md) — how `auth` and cross-module authorization work
- [`../engineering/getting-started.md`](../engineering/getting-started.md) — how to run the backend locally
