---
title: "API Reference"
last_updated: 2026-10-11
status: Active
owner: "TODO — assign a Technical Owner"
---

# API Reference

## Purpose

Where the authoritative API reference lives, and a map of URL prefixes to modules. Endpoints aren't listed by hand: FastAPI generates the reference from the code, so it can't go stale.

## Scope

In scope: the live reference and a prefix map.
Out of scope: a hand-kept endpoint list.

## Table of Contents

- [Live reference](#live-reference)
- [Prefix map](#prefix-map)
- [Related documents](#related-documents)

## Live reference

Swagger UI at `http://localhost:8001/docs` locally, and the raw schema at `/openapi.json`.

## Prefix map

Verified against the router mounts in `backend/app/main.py` on 2026-10-11.

| Prefix | Module |
|---|---|
| `/auth` | Sign-in, refresh, sessions and devices, invitations (`/auth/invitations/{token}`), password reset, account data |
| `/users/me/preferences` | Lite and display preferences (`lite`) |
| `/clubs` | Clubs, `/clubs/me/*` (membership, staff, finance, commitments, contract cliff, squad check, dashboard, approvals and the approval policy) |
| `/players` | Players, the market, contracts, ledger, invitations; batch stats and form under `/players/stats/batch` and `/players/form/batch` |
| `/sales` | Listings and bids |
| `/offers` | Offers, counters, messages, the order book |
| `/enquiries` | Enquiries |
| `/deals` | Deals, the deal room, paperwork, personal terms, audit log |
| `/transfers` | Public transfer activity; `/transfers/window` for transfer windows |
| `/loans` | Loans (also under `/clubs/me/loans` and `/admin/loans`) |
| `/board` | The Transfers board |
| `/conversation` | One conversation per transfer |
| `/lite` | Lite home, buy flow (search by name, candidates with paging), offer cards, held sends, team contact, email confirmations |
| `/ai` | The assistant, Ask TransferX (`/ai/ask`), the analyst (`/ai/analyst`, `/ai/analyst/export`) |
| `/valuation` | Fair-value reads and staff recompute |
| `/agents`, `/mandates`, `/negotiations` | Agents, mandates, agent negotiation messages |
| `/scouting` | Shortlists and interest |
| `/notifications` | Notifications, preferences, push subscriptions |
| `/verification` | Verification requests |
| `/world`, `/fixtures`, `/stats`, `/vendor` | Reference data, fixtures, stats, API-Football syncs |
| `/fx` | Exchange rates for display |
| `/deadline` | Deadline day: the club's open transfers against the window's close (club members) |
| `/search` | Global search (⌘K, shortlists); signed-in only |
| `/analytics` | Usage events |
| `/admin` | Staff administration, including `/admin/jobs`, `/admin/errors`, `/admin/health` and `/admin/real-world-moves` (list, bulk apply, dismiss) and `/admin/deals/{id}/…` (staff tools for a stuck deal) |
| `/monitoring/client-errors` | Browser error reports |
| `/health` | Liveness check |
| `/ws` | WebSocket |

## Related documents

- [`../architecture/backend-architecture.md`](../architecture/backend-architecture.md): what each module owns
