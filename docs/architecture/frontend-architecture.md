---
title: "Frontend Architecture"
last_updated: 2026-10-11
status: Active
owner: "TODO — assign a Technical Owner"
---

# Frontend Architecture

## Purpose

The React frontend's structure: where things live, how routes are guarded, and how state is handled.

## Scope

In scope: directory layout, routing and access, state, styling.
Out of scope: component-level APIs, the backend contract ([`../engineering/api-reference.md`](../engineering/api-reference.md)), visual rules ([`../design-system/README.md`](../design-system/README.md)).

## Table of Contents

- [Directory layout](#directory-layout)
- [Routing and access](#routing-and-access)
- [Two interfaces: the full app and Lite](#two-interfaces-the-full-app-and-lite)
- [State and data](#state-and-data)
- [Styling](#styling)
- [Related documents](#related-documents)

## Directory layout

Verified against `frontend/src/` on 2026-10-11.

| Directory | Contents |
|---|---|
| `pages/` | Route-level pages by area: `auth`, `dashboard`, `board`, `market`, `sales`, `offers`, `enquiries`, `deals`, `club`, `scouting`, `players`, `transfers`, `world`, `ask`, `lite`, `notifications`, `account`, `agent`, `player`, `admin` |
| `components/` | Shared components by domain, plus `ui/` (the design-system primitives) and `layout/` (shell, sidebar, ⌘K search) |
| `hooks/` | Auth, capabilities, WebSocket, deadlines, Lite, assistant, preferences, focus trap |
| `store/` | Zustand stores: `auth`, `preferences`, `fx` |
| `context/` | Providers: theme, toasts, confirm dialog, compare tray |
| `lib/` | API client (`api.ts`, token refresh), money and date formatting, push, browser error reporting |
| `types/` | TypeScript types mirroring the backend schemas |

`public/sw.js` is the service worker. It shows push notifications and caches nothing.

## Routing and access

Routes are declared in `App.tsx` and lazy-loaded. Each one is wrapped in a guard:

| Guard | Who | Otherwise |
|---|---|---|
| `ProtectedRoute` | Anyone signed in | `/login` |
| `ClubRoute` | Club accounts, and TransferX staff | `/` |
| `AgentRoute` | Agents | `/` |
| `PlayerRoute` | Players | `/` |
| `LiteRoute` | Club accounts, in the Lite layout | `/` |
| `/admin/*` (`AdminLayout`) | Superusers | "Staff access required" |

**Where `/` sends people** (`SmartRedirect`): staff to `/admin`, agents to `/agent/pipeline`, players to `/player/profile`, and club members to `/dashboard`. At sign-in, someone who has turned Lite on goes to `/lite` instead (`LoginPage`).

Within a club, what a person can do is decided by their role's capabilities (`useClubCapabilities`, mirroring `clubs/capabilities.py`). The server enforces the same rules ([authentication and permissions](./authentication-and-permissions.md)).

## Two interfaces: the full app and Lite

Lite (`pages/lite/`, `LiteLayout`) is a big-type interface for directors: decide on offers, approvals and bids, with a 10-second undo. It's opt-in per person. Product ADR 0008: Lite decides, the full app operates. Spec: [`lite-mode/`](../feature_spec/lite-mode/README.md).

## State and data

**Server state.** All server data goes through TanStack Query, keyed by resource, with `api.ts` adding the token and refreshing it. Live updates arrive over the WebSocket and invalidate the matching queries.

**Client state.**
- Zustand holds the auth tokens and user, preferences, and FX rates.
- Context holds UI-wide concerns (toasts, confirm, theme).
- Everything else is local component state.
- `localStorage` holds per-device conveniences only (density, a remembered board side). Each read and write is wrapped in try/catch.

## Styling

Tailwind CSS v4, with the design tokens defined as CSS variables in `index.css`, light and dark. The rules (four tiers, "whose move", type sizes, touch targets, responsive patterns) are in [`../design-system/`](../design-system/README.md).

## Related documents

- [`system-overview.md`](./system-overview.md): the stack
- [`authentication-and-permissions.md`](./authentication-and-permissions.md): the access model the guards follow
- [`../design-system/README.md`](../design-system/README.md): visual rules and tokens
- [`../engineering/getting-started.md`](../engineering/getting-started.md): running it locally
