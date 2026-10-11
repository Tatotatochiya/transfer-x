---
title: "Coding Standards"
last_updated: 2026-10-11
status: Active
owner: "TODO — assign a Technical Owner"
---

# Coding Standards

## Purpose

Conventions for contributing code to TransferX, backend and frontend. The engineering principles behind them (small changes, permissions first, explicit trade-offs) are in the `engineering-standards` skill under `.claude/skills/`.

## Scope

In scope: structure, patterns and tooling specific to this codebase.
Out of scope: testing ([`testing-strategy.md`](./testing-strategy.md)), architecture ([`../architecture/README.md`](../architecture/README.md)).

## Table of Contents

- [Backend](#backend)
- [Frontend](#frontend)
- [Writing for users](#writing-for-users)
- [Git and pull requests](#git-and-pull-requests)
- [Related documents](#related-documents)

## Backend

- **Layout.** Each module has `models.py` / `schemas.py` / `service.py` / `router.py`. Routers stay thin, and other modules are reached through their service layer.
- **Permissions.** Club writes need a capability (`require_club_capability` / `ensure_club_capability`). Deals and the deal room check the caller is a party. A failed check is 403, never a misleading 404.
- **Money.** Reserve, commit, spend through `clubs/service.py`, with row locks (`select_for_update(of=…)`) on every money path. Amounts are `Decimal`.
- **Confidentiality.** Mask anonymous buyers server-side (`common/masking.py`). Never send another club's contract terms. AI facts are built from what the asking club may see.
- **Audit.** Deal actions and every admin change write an `AuditEvent`. Destructive admin actions need a reason.
- **Datetimes** are timezone-aware UTC.
- **Lint:** `ruff check --select F` on files you touch. The wider codebase has older warnings; don't add to them.
- **Logging.** Never log passwords, tokens, wages or fees (`tests/test_monitoring.py` checks auth and finance code). Warnings and errors land in Admin → Errors.

## Frontend

- **Data.** Server data through TanStack Query, via `lib/api.ts`.
- **Building blocks.** UI primitives come from `components/ui/`, and players and clubs are linked with `PlayerLink` / `ClubLink`.
- **Money.** Formatted with the helpers in `lib/money.ts` / `lib/utils.ts`, in pounds, with an estimate beside them when a currency is chosen.
- **Visual rules.** Follow [`../design-system/`](../design-system/README.md): tokens, four tiers, "whose move", an 11px type floor and 44px touch targets.
- **TypeScript.** Strict. `npx tsc -b` must stay at 0 errors.
- **Browser storage.** Per-device conveniences only, each read and write wrapped in try/catch.

## Writing for users

Plain, specific sentences that say what happened and what to do next. Name the club, player and amount, and avoid jargon. An error says what went wrong, not just "Failed".

## Git and pull requests

- **Branches.** Branch from `main` for each piece of work.
- **Pull requests.** Each is self-contained with a summary and test plan. `main` deploys to Railway.
- **Commit messages** explain why, not only what.

## Related documents

- [`testing-strategy.md`](./testing-strategy.md)
- [`../architecture/backend-architecture.md`](../architecture/backend-architecture.md)
- [`../architecture/frontend-architecture.md`](../architecture/frontend-architecture.md)
