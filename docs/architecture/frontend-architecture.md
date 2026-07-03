---
title: "Frontend Architecture"
last_updated: 2026-07-03
status: Active
owner: "TODO — assign a Technical Lead"
---

# Frontend Architecture

## Purpose

Documents the React frontend's structure — directory layout, key patterns, and where to find things.

## Scope

In scope: directory layout, routing/role-gating approach, state management patterns.
Out of scope: individual component API detail, backend contract detail (see [`../engineering/api-reference.md`](../engineering/api-reference.md)).

## Table of Contents

- [Directory layout](#directory-layout)
- [Routing and role gating](#routing-and-role-gating)
- [State management](#state-management)
- [Related documents](#related-documents)

## Directory layout

| Directory | Contents |
|---|---|
| `src/pages/` | Route-level page components, grouped by area (auth, dashboard, market, sales, offers, deals, club, scouting, players, world, transfers, notifications, admin, agent, player) |
| `src/components/` | Reusable components, grouped by domain (players, clubs, sales, offers, deals, scouting, agent, ai, verification, ui, layout) |
| `src/hooks/` | Shared hooks (auth, WebSocket, deadline countdown, page tracking, AI streaming) |
| `src/store/` | Zustand stores (auth, preferences) |
| `src/lib/` | API client, formatting utilities, analytics |
| `src/types/` | TypeScript types mirroring backend schemas and enums |
| `src/context/` | React context providers (compare tray, confirm dialog, toasts) |

> **TODO:** Confirm this list against the current `frontend/src/` directory if it's been a while since this was last verified.

## Routing and role gating

Routes are role-gated by account type (club, agent, player, admin) at the router level.

> **TODO:** Document the routing/role-gating pattern in more detail — which routes are public vs. protected vs. role-specific, and how that's enforced.

## State management

TanStack Query handles server state; Zustand handles client state (notably auth tokens).

> **TODO:** Expand on conventions — when to use Query vs. local state vs. Zustand.

## Related documents

- [`system-overview.md`](./system-overview.md) — where this fits in the overall stack
- [`authentication-and-permissions.md`](./authentication-and-permissions.md) — the auth model this frontend implements
- [`../engineering/getting-started.md`](../engineering/getting-started.md) — how to run the frontend locally
- [`../engineering/coding-standards.md`](../engineering/coding-standards.md) — frontend conventions
