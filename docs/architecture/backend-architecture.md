---
title: "Backend Architecture"
last_updated: 2026-07-03
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
| `clubs` | Club profiles, staff, finance |
| `players` | Player records, contracts |
| `sales` | Listings (auction / fixed price / open to offers), bids |
| `offers` | Direct offer negotiation |
| `deals` | Deal lifecycle and stage machine (includes `deals/room_*` — the deal room: versioned terms, comments, attachments) |
| `agents` | Agent profiles, deal invitations, negotiation, negotiation messaging, commissions |
| `mandates` | Agent–player representation mandates, client alerts |
| `verification` | Verification request workflow (club/agent/player) |
| `notifications` | In-app + email notifications, preferences |
| `audit` | Append-only audit log |
| `scouting` | Shortlists, player interest |
| `stats` | Player statistics and form |
| `vendor` | External stats provider (API-Football) client and sync |
| `enrichment` | Valuation/wage enrichment provider adapters |
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

Scheduled jobs run in-process via APScheduler (see `backend/app/main.py`).

> **TODO:** List the current scheduled jobs and their intervals here — this list changes as the product grows and should be kept current rather than copied once and left stale.

## Related documents

- [`system-overview.md`](./system-overview.md) — where this fits in the overall stack
- [`data-model.md`](./data-model.md) — entities owned by these modules
- [`authentication-and-permissions.md`](./authentication-and-permissions.md) — how `auth` and cross-module authorization work
- [`../engineering/getting-started.md`](../engineering/getting-started.md) — how to run the backend locally
