# Handoff: TransferX UI redesign

## Overview

TransferX is a B2B transfer marketplace for football clubs — listings, auctions, offers, deals,
agent negotiation, squad and finance management. Primary users are club directors and sporting
directors, typically 35+, non-technical, using the product a few times a week rather than daily.

This package redesigns the app from a dark, uniform-density dashboard to a **light status board
with explicit hierarchy**. The core principle of the redesign is one sentence:

> Everything stays visible, but the things waiting on *you* are physically louder than
> everything else, and every row says whose move it is.

The chosen direction is **"Board v2"**. An alternative direction ("work queue") was explored and
rejected — it is documented in `TransferX - Board vs Queue.dc.html` for context, but is **not**
what should be built.

## About the design files

The `.dc.html` files in this bundle are **design references written in HTML**. They are
prototypes showing intended look, structure and behaviour. They are **not production code and
must not be copied into the app.**

The task is to recreate these designs in the existing TransferX frontend:
**React 19 + TypeScript + Vite + Tailwind CSS v4 + TanStack Query + React Router**, using the
codebase's established patterns — its `components/ui` primitives, its `api` client, its query
hooks. Every screen in the design maps to a page that already exists in `frontend/src/pages/`.

Open the files in a browser to inspect them. Several have in-design navigation (sidebar items or
tab bars at the top) that switch between screens — see "Files" below for what each contains.

## Fidelity

**High-fidelity.** Colours, type sizes, weights, spacing, radii and copy are all final and should
be matched. Exact values are in `TOKENS.md`. Where the design and this documentation disagree,
this documentation wins.

Two caveats:

1. The designs use **inline styles** because of how they were authored. In the app, these become
   Tailwind utility classes and the token layer described in `TOKENS.md`. Do not port inline
   styles.
2. All data in the designs is **fictional sample data** (Meridian FC, Marcus Webb, Ashfield
   United). It exists to show realistic density. Never ship it.

## What is being changed, and what is not

**Changed:** the visual system (dark → light), the information hierarchy on every club-facing
screen, and the addition of a "whose move is it" state on every row that represents a
negotiation.

**Not changed:** routing, URL structure, data models, permissions, business logic, or the set of
screens. No page is added or removed.

## The four-tier hierarchy

Every club-facing screen uses the same four tiers, top to bottom. This is the spine of the whole
redesign — if a screen does not follow it, it is wrong.

| Tier | What goes in it | Visual treatment |
|---|---|---|
| 1 — Waiting on you | Items that cannot progress without an action from this user | Full-width card, red hairline ring `#f7ccc7`, red-tinted header `#ffeeeb`, primary buttons on every row |
| 2 — Standing figures | The numbers that gate every decision: budget, wage room, window clock, squad size | White cards, 28px bold value, optional progress bar |
| 3 — Working panels | Live listings, offers, deals — things in motion | White cards, `0 0 0 1px #e4e7ec` ring, every row carries a "whose move" label |
| 4 — Reference | Squad gaps, shortlist hits, expiring contracts, history | Off-white `#fbfbfc` cards, `#eaecf0` ring, grey headers, deliberately quiet |

Tier 1 is empty on a quiet day. When it is empty, render a single line — "Nothing is waiting on
you" — not an illustration or an empty-state graphic.

## The "whose move" rule

This is the highest-value change in the redesign and the one most likely to be implemented
wrongly. Every row representing a live negotiation gets one of three states:

| State | Colour | Meaning |
|---|---|---|
| **Your move** | `#ac1922` | This user (or their club) must act before anything happens |
| **Their move** | `#475467` | The counterparty, agent, or player must act |
| **Neither** | `#667085` | Time-based only — listed, awaiting deadline, no action possible |

Derivation is **server-side**, not in the component. It must be a field on the API response, not
a frontend heuristic, so that the dashboard, the list pages and the notification system all agree.
Proposed rule, **to be confirmed with the product owner before Session 3**:

- Offer where `status = COUNTERED` and last actor ≠ current club → **Your move**
- Offer where `status = PENDING` and current club is the recipient → **Your move**
- Offer where current club was the last actor → **Their move**
- Deal at stage `CONFIRMED` awaiting this club's signature → **Your move**
- Deal at `AGENT_NEGOTIATION` where last message is from the agent → **Your move**
- Deal at any stage where the last action was this club's → **Their move**
- Listing with no bids → **Neither**
- Auction where a bid is above reserve and the window is closing → **Your move**

## Documents in this package

| File | What it covers |
|---|---|
| `TOKENS.md` | Every colour, type size, spacing, radius and shadow, with hex values |
| `RESPONSIVE.md` | Breakpoints and the rules for mobile and tablet — **read before building any screen** |
| `SCREENS.md` | Per-screen layout and component specs |
| `SESSIONS.md` | The work broken into 13 sessions, in dependency order, with a definition of done for each |
| `CLAUDE.md` | Drop this into the repo root. Rules that stop drift across sessions. |
| `DECISIONS.md` | Open questions that need a human answer, and when each blocks work |

## Files

| File | Contains |
|---|---|
| `TransferX - Board v2.dc.html` | **The reference for the whole system.** Dashboard, full four-tier hierarchy, sidebar chrome. |
| `TransferX - Board v2 Screens.dc.html` | Offer inbox, Deals, Finance, Approvals. Sidebar items are clickable. |
| `TransferX - Radical Screens.dc.html` | Squad, Browse Players, and a phone layout. **Content structure only — see note below.** |
| `TransferX - Radical Bidding.dc.html` | Sale detail / bid ladder (seller and buyer views), Deal room / contract negotiation. **Content structure only.** |
| `TransferX - Current.dc.html` | The existing dark UI, recreated. Reference for what is being replaced. |
| `TransferX - Board vs Queue.dc.html` | The rejected alternative, kept for context. Do not build. |
| `support.js`, `ios-frame.jsx` | Runtime for the design files. Not part of the app. |

### Note on the "Radical" files

Squad, Browse Players, Sale detail and Deal room were designed before the Board v2 chrome was
settled. Their **content structure is correct and should be built** — the position grouping on
squad, the asking-vs-fair-value bar on browse, the bid ladder drawn against reserve, the terms
diff in the deal room. Their **chrome is not**: they use a black full-width header band that
Board v2 replaced with white "standing figure" cards.

When building those four screens: keep the content, adopt the Board v2 chrome (white sidebar,
`#f7f8fa` page background, white cards, tier-2 figure cards instead of the black band).

## Assets

No new image assets. Icons are inline SVG, 24×24, 2px stroke, matching the existing
`components/layout/Icon.tsx` set. Four new icon names are needed — `check-circle`, `clock`,
`arrow-right`, `menu` — drawn in the same style.

No new fonts. Inter stays, loaded as it is today.
