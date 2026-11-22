---
title: "Design System"
last_updated: 2026-11-11
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

Every row that represents a live negotiation shows **Your move**, **Their move** or **Neither**. A colour is never the only signal: each state has a text label. **Your move** is red (needs you), **Their move** grey, turning amber "Stalled" after 3 days; never blue, which is only for what you can tap.

The value is a `whose_move` field computed on the server, so the dashboard, the board, the lists, the sidebar counts and the daily digest all agree. The frontend reads it; it doesn't work it out again (except for offers listed without it, `lib/whoseMove.ts`):
- `compute_offer_whose_move` (offers);
- `compute_deal_whose_move` (deals);
- `compute_sale_whose_move` (listings);
- `enquiries.service.whose_move` (enquiries).

**Deals in particular** (2026-11-14, from whose terms are on the table, [ADR 0012](../product/decisions/0012-commission-and-personal-terms-are-negotiated.md)):
- **Agent commission**, for the buying club: yours when the agent's proposal is waiting for you, or once it's agreed (move it on); theirs while the agent proposes or answers your counter. The selling club isn't part of it: neither.
- **Personal terms**, for the buying club: yours to propose them when there's no agent, to answer the player side's terms, or to record the answer of a player with no account or agent; theirs while your terms are with the player or his agent. Once agreed, yours for both clubs (either moves it on). Otherwise neither for the selling club.
- **Paperwork** is yours while any of your checklist steps are outstanding.
- **Confirmed** is yours.
- **Agreement** is neither (either club may move it on, and neither is waited on). A stalled move is chased with a [reminder](../feature_spec/move-reminders/README.md), not by flipping whose move it is.

## Ending a transfer

Any answer that ends a transfer (declining the agent's commission, declining personal terms for the player or as the player, the buying club declining the player side's terms, or recording that the player declined) opens `EndTransferDialog` before anything is sent. It says the deal collapses and who is told, offers **Counter instead** where a counter is possible, and takes an optional reason that both sides see. On the status card a decline is the quiet third action, in red, under Accept and Counter. `src/test/endTransfer.test.ts` fails if a DECLINED answer is sent from a file that doesn't use the dialog ([ADR 0012](../product/decisions/0012-commission-and-personal-terms-are-negotiated.md)). Rejecting or withdrawing an offer, and collapsing a deal, have their own confirmations.

## Settled decisions

Decided during and after the redesign:
- **Dark theme is a preference** (Account settings), not the default. `prefers-color-scheme` is deliberately not followed, because dark hasn't been reviewed screen by screen.
- **Tables become stacked cards below 640px** (`ResponsiveTable`). There's never a horizontal scroll on a phone.
- **No present-value figures** on instalment schedules: nominal amounts only, until finance provides a discount rate.
- **Squad minimums** default to 2 GK, 4 DEF, 4 MID and 3 FWD.
- **Plain naming:** "Dashboard", not "War Room".
- **Freshness stamps** must reflect how the data is actually refreshed (polling, focus refetch or WebSocket).
- **One type scale, one meaning per colour** (2026-11-11, [`type-and-colour`](../feature_spec/type-and-colour/README.md)): seven roles with a 13px floor and 15px body; positions and other categories are neutral; violet is only the AI; the dark accent is blue. A test enforces both.

## Documents

| File | What it covers |
|---|---|
| [`RULES.md`](./RULES.md) | The twelve non-negotiables (tokens only, type roles and the 13px floor, colour meanings, touch targets, focus rings …) |
| [`TOKENS.md`](./TOKENS.md) | Every colour and colour role, the type roles, money format, spacing, radius and shadow. The tokens live in `frontend/src/index.css`, light and dark |
| [`RESPONSIVE.md`](./RESPONSIVE.md) | Breakpoints and the mobile and tablet rules |
| [`SCREENS.md`](./SCREENS.md) | Per-screen layout as designed. Screens added since (the board, Lite, Ask) follow the same rules |
