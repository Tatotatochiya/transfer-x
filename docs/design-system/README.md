---
title: "Design System"
last_updated: 2026-10-11
status: Active
owner: "TODO — assign a Design Owner"
---

# Design System

## Purpose

The visual and interaction rules every TransferX screen follows. It came from the August 2026 UI redesign (shipped 2026-08-13), and the frontend code cites it. The redesign's build files (HTML prototypes, session plan, test baseline) have been removed; git history has them.

## Scope

In scope: the principle, the four tiers, "whose move", tokens, responsive rules and per-screen layout.
Out of scope: frontend code structure ([`../architecture/frontend-architecture.md`](../architecture/frontend-architecture.md)).

## Table of Contents

- [The principle](#the-principle)
- [The four tiers](#the-four-tiers)
- ["Whose move"](#whose-move)
- [Settled decisions](#settled-decisions)
- [Documents](#documents)

## The principle

> Everything stays visible, but the things waiting on *you* are physically louder than everything else, and every row says whose move it is.

The audience is club directors and sporting directors, often 35+ and non-technical, who use TransferX a few times a week. It's a light status board with explicit hierarchy, Inter type, and icons as inline 24×24 SVG with a 2px stroke (`components/layout/Icon.tsx`).

## The four tiers

Every club-facing screen uses the same four tiers, top to bottom (`components/ui/Card.tsx`):

| Tier | What goes in it | Treatment |
|---|---|---|
| 1 — Waiting on you | Items that can't progress without this user | Full-width card, red hairline ring and tinted header, a primary button on every row |
| 2 — Standing figures | Budget, wage room, window clock, squad size | White cards, 28px bold value, optional progress bar |
| 3 — Working panels | Listings, offers, deals in motion | White cards; every row carries a "whose move" label |
| 4 — Reference | Squad gaps, shortlist hits, expiring contracts, history | Off-white cards, grey headers, deliberately quiet |

When tier 1 is empty it's a single line, "Nothing is waiting on you", with no illustration.

## "Whose move"

Every row that represents a live negotiation shows **Your move**, **Their move** or **Neither**. A colour is never the only signal: each state has a text label.

The value is a `whose_move` field computed on the server, so the dashboard, the board, the lists, the sidebar counts and the daily digest all agree:
- `compute_offer_whose_move` (offers);
- `compute_deal_whose_move` (deals);
- `compute_sale_whose_move` (listings);
- `enquiries.service.whose_move` (enquiries).

**Deals in particular:**
- **Paperwork** is yours while any of your checklist steps are outstanding.
- **Confirmed** is yours.
- **Agent negotiation** is theirs, until the agent has been silent for 72 hours; then it's yours to chase.

## Settled decisions

Decided during and after the redesign:
- **Dark theme is a preference** (Account settings), not the default. `prefers-color-scheme` is deliberately not followed, because dark hasn't been reviewed screen by screen.
- **Tables become stacked cards below 640px** (`ResponsiveTable`). There's never a horizontal scroll on a phone.
- **No present-value figures** on instalment schedules: nominal amounts only, until finance provides a discount rate.
- **Squad minimums** default to 2 GK, 4 DEF, 4 MID and 3 FWD.
- **Plain naming:** "Dashboard", not "War Room".
- **Freshness stamps** must reflect how the data is actually refreshed (polling, focus refetch or WebSocket).

## Documents

| File | What it covers |
|---|---|
| [`RULES.md`](./RULES.md) | The ten non-negotiables (tokens only, type floor, touch targets, focus rings …) |
| [`TOKENS.md`](./TOKENS.md) | Every colour, type size, spacing, radius and shadow. The tokens live in `frontend/src/index.css`, light and dark |
| [`RESPONSIVE.md`](./RESPONSIVE.md) | Breakpoints and the mobile and tablet rules |
| [`SCREENS.md`](./SCREENS.md) | Per-screen layout as designed. Screens added since (the board, Lite, Ask) follow the same rules |
