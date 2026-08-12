---
title: "API Reference"
last_updated: 2026-08-11
status: Active
owner: "TODO — assign a Technical Lead"
---

# API Reference

## Purpose

Points to where the authoritative API reference lives, and gives a navigational map of router prefixes. The API reference itself is **not duplicated here** — FastAPI generates it automatically from the code, which is the only way it can never go stale.

## Scope

In scope: where to find the live API reference, and a prefix-to-module map for navigation.
Out of scope: a hand-maintained list of endpoints (this would immediately duplicate, and drift from, the auto-generated reference).

## Table of Contents

- [Live reference](#live-reference)
- [Router prefix map](#router-prefix-map)
- [Related documents](#related-documents)

## Live reference

Running locally, the interactive Swagger UI is available at `http://localhost:8001/docs` (see [`getting-started.md`](./getting-started.md)). This is always current, since FastAPI generates it directly from the route definitions.

## Router prefix map

| Prefix | Module |
|---|---|
| `/auth` | Authentication |
| `/clubs` | Club profiles, staff, finance |
| `/players` | Player records, contracts |
| `/sales` | Listings, bids |
| `/offers` | Direct offers |
| `/deals` | Deal lifecycle, deal room |
| `/agents` | Agent profiles, invitations, negotiation |
| `/mandates` | Agent–player mandates |
| `/notifications` | In-app/email notifications |
| `/admin` | Superuser administration |
| `/ws` | WebSocket real-time updates |
| `/valuation` | Fair-value model valuations (TRA-91) — single/batch reads, staff recompute |
| `/clubs/me/membership`, `/clubs/me/staff` | Club role/capability membership (TRA-151) + owner team management & invitations (TRA-86) |
| `/auth/invitations/{token}` | Public staff-invitation preview + accept (single-use tokenised link) |
| `/clubs/me/approvals`, `/clubs/me/approval-policy` | Spending-authority approvals: queue, decisions, threshold policy |
| `/clubs/me/dashboard` | "Waiting on you" aggregate across offers/deals/sales/approvals (`dashboard` module, B2) |
| `/clubs/me/commitments` | Row-level breakdown of committed/reserved budget (`clubs` module, B5) |
| `/clubs/me/contract-cliff` | Windowed contract-expiry aggregation with value-at-risk (`clubs` module, B6) — separate from `/clubs/me/expiring-contracts`' flat list |

> **TODO:** Complete this table against the current router mounts in `backend/app/main.py` — this is a starting point, not verified exhaustive as of this writing.

## Related documents

- [`../architecture/backend-architecture.md`](../architecture/backend-architecture.md) — what each module is responsible for
- [`getting-started.md`](./getting-started.md) — how to run the backend locally to access the live reference
