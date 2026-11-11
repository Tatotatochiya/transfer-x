---
title: "Responsive Behaviour"
last_updated: 2026-11-11
status: Active
owner: "TODO — assign a Design Owner"
---

# Responsive behaviour

Every screen must work on phone, tablet and desktop. **Read this before building a screen.**
Responsive rules aren't a pass at the end: the component structure has to allow for them from
the first commit.

## Breakpoints

Tailwind's defaults, used as follows:

| Name | Range | Layout |
|---|---|---|
| Mobile | `< 640px` | Single column, drawer nav, tables become cards |
| Tablet | `640px – 1023px` | Two columns, drawer nav, tables scroll |
| Desktop | `≥ 1024px` | Full layout, persistent sidebar |
| Wide | `≥ 1280px` | Content capped at 1280px, centred |

Design at 1280px. The design files are drawn at desktop width.

## Navigation

**Desktop (≥1024px):** persistent 232px white sidebar, always expanded, labels always visible.
No icon-only rail — icon rails cost recognition for infrequent users, which is exactly this
audience.

Compact since 2026-10-02 ([spec](../feature_spec/compact-sidebar/README.md)), so a club's whole
nav fits a 13-inch laptop (about 790px of page) without scrolling:

- Rows are 32px, with a bare 16px icon (no tile), and 12px between groups.
- Notifications is a bell with its unread count in the 52px logo row, not a nav row.
- The footer is one account button opening a menu upwards: Settings, Notification settings,
  Switch to Lite mode (clubs only) and Log out.
- The nav still scrolls when the window is shorter than it; focus outlines are inset so the
  scroll container never clips them.

**Tablet and mobile (<1024px):** the sidebar becomes an off-canvas drawer.

- A sticky top app bar appears, 56px tall, white, `1px solid #e4e7ec` bottom border, containing:
  hamburger (44×44 target) · TransferX logotype · a badge showing total "your move" count ·
  search icon · notifications bell (44×44) · avatar.
- The drawer slides from the left, 280px wide, full height, with the **same content and the same
  labels** as the desktop sidebar. Never a condensed version. Its rows, the account button and the
  account menu's items stay 48px tall for touch. Escape with the account menu open closes only
  the menu.
- Backdrop `rgba(20,23,31,0.4)`. Tapping it or pressing Escape closes the drawer.
- The drawer traps focus while open and returns focus to the hamburger on close.
- Body scroll locks while the drawer is open.

## Grids, tier by tier

| Tier | Desktop | Tablet | Mobile |
|---|---|---|---|
| 1 — Waiting on you | Full width, one row per item | Full width, one row per item | One **card** per item (see below) |
| 2 — Standing figures | 4 columns | 2 columns | 2 columns |
| 3 — Working panels | 3 columns | 2 columns | 1 column |
| 4 — Reference | 3 columns | 2 columns | 1 column |

Use `grid-template-columns: repeat(auto-fit, minmax(<min>, 1fr))` so the reflow is driven by
available width rather than a media query:

- Tier 2: `minmax(150px, 1fr)`
- Tier 3: `minmax(320px, 1fr)`
- Tier 4: `minmax(280px, 1fr)`

Tier 2 keeps two columns on a 375px phone — four figures in two rows, which reads better than
four full-width bands.

## Tier-1 rows on mobile

The desktop tier-1 row is horizontal: title and description, amount, deadline, action button.
Below 640px this becomes a stacked card:

```
┌─────────────────────────────────┐
│ COUNTER-OFFER      6 hours      │  ← overline + deadline, deadline right-aligned
│ Marcus Webb                     │  ← 17px/700
│ Ashfield United countered…      │  ← 13px, max 2 lines
│ ─────────────────────────────── │
│ Their offer  Your valuation     │  ← two facts only, side by side
│ £4.2M        £4.8M              │
│ ─────────────────────────────── │
│ [        Respond         ]      │  ← full width, 48px tall
│ [        Accept          ]      │  ← full width, 48px tall
└─────────────────────────────────┘
```

Rules:

- **Two facts maximum on mobile**, chosen in this priority order: their offer, your valuation,
  gap, wage effect. Drop the rest — do not shrink them.
- Buttons go full width and stack, 48px tall, 8px apart, primary on top.
- The description clamps to 2 lines (`-webkit-line-clamp: 2`).

## Tables

**Below 640px, every table becomes a stacked list of cards. Never a horizontal scroll on mobile.**
Horizontal scrolling inside a page that also scrolls vertically is the single worst pattern for
this audience.

Card shape, using the offer table as the example:

```
┌─────────────────────────────────┐
│ Elian Vos              £4.9M    │  ← primary identifier left, primary value right
│ Castlebrook                     │  ← secondary line, muted
│ Their move          1 day ago   │  ← state left (coloured), timestamp right
└─────────────────────────────────┘
```

- Primary identifier: 14px/600, text colour.
- Primary value (money): 14px/700, right-aligned, text colour.
- Two supporting lines maximum, 12–13px muted.
- The "whose move" state keeps its colour.
- Whole card is the tap target, minimum 64px tall.
- Columns that do not fit are dropped, not truncated. Ranked by importance per table — see
  `SCREENS.md`.

**Between 640px and 1023px**, tables keep table layout with `overflow-x: auto` on the wrapper and
a `min-width` on the table. This is acceptable on tablet, where the page is wide enough that the
scroll is short and obvious.

Implement this once as a `<ResponsiveTable>` primitive that takes column definitions with a
`priority` field and a `renderCard` function. Do not hand-roll it per screen — there are 20+
tables in the app.

## Two-pane screens

Offer detail, deal room and sale detail use a content pane plus a rail (messages, documents,
context).

- **Desktop:** side by side, rail 300–360px, sticky at `top: 24px`. The deal room's and offer
  detail's rails are 340px and sticky at `top: 80px`, below the 56px desktop header.
- **Tablet:** rail moves below the content, full width. **Except the deal room and offer
  detail**, which use the phone's segmented control on tablets too: stacking the rail under the
  terms made the iPad page as long as the old phone page
  ([deal room spec](../feature_spec/deal-room-focus/README.md) D3,
  [offer page spec](../feature_spec/offer-room-focus/README.md) D5). Both rails are 340px and
  sticky at `top: 80px`.
- **Mobile:** rail becomes a segmented control at the top of the page — `Detail | Messages |
  Documents` — showing one section at a time. Do not stack all three; the page becomes
  unnavigably long.

## Filter rails

Browse Players has a sticky left filter rail from 1024px (it scrolls on its own when taller than the screen).

- **Below 1024px:** a "Filters (n)" button in a sticky toolbar opens a `Sheet`: full height on phones, the 560px centred dialog on tablets. Saved views go at the top. The sheet edits a draft: "Show {n} players" applies it with a live count, and closing with unapplied changes asks first.
- The active filters show above the results as removable chips, a horizontally scrollable row below 1024px. That is the one place horizontal scroll is allowed, because the chips are clearly a single-axis strip.

## Grids

Card grids use `grid-template-columns: repeat(auto-fill, minmax(220px, 1fr))`, never breakpoint column counts. Breakpoints measure the window and ignore the sidebar and any rail, which squeezed Browse Players' cards to ~165px at 1280px.

## Touch targets

Minimum 44×44px for anything tappable, below 1024px. This affects:

- Buttons: mobile padding rises to `12px 20px`, and tier-1 buttons to 48px tall.
- Nav items in the drawer: 48px tall.
- Icon-only controls: 44×44 minimum, even where the glyph is 20px.
- Table-card rows: 64px minimum.
- Filter chips: 40px tall on mobile.

## Typography on small screens

Do **not** scale type down. Every role is the same size on every device, except:

| Role | Below 640px | From 640px |
|---|---|---|
| Title (page `h1`) | 22px | 24px |
| Display (hero figure) | 28px | 32px |
| Inputs | 16px below 1024px | 15px from 1024px |

Body is 15px on every device (it was 14px). Never pair a phone size with a smaller desktop size
(`text-body lg:text-small`). See [`TOKENS.md`](./TOKENS.md) "Typography".

## Page padding

| Breakpoint | Padding |
|---|---|
| Desktop | `28px 32px 64px` |
| Tablet | `24px 24px 56px` |
| Mobile | `16px 16px 48px` |

Cards keep their internal padding at all sizes except tier-1 mobile cards, which use 16px.

## Sticky elements

- Top app bar: sticky on mobile and tablet.
- Sidebar: sticky full-height on desktop.
- Rails: sticky on desktop only. Never sticky on mobile — they eat the viewport.
- Compare tray (Browse Players): fixed to the bottom on all sizes, but on mobile it collapses to
  a single bar showing "3 selected · Compare" rather than listing the players.
- Player page action bar: below 1024px the player's primary and secondary actions are fixed to
  the bottom (above the home indicator), and the page pads by its height. The compare tray sits
  above it (`--action-bar-h`), never over it.

## Buttons

- **One primary (blue) button per screen**: the action the screen is for. Everything else is
  secondary, a text button, or in More.
- **The top bar never has one.** Its "Find players" / "Sell a player" are navigation, styled quietly.
- No disabled buttons that explain themselves in a tooltip: say why in a sentence, and offer the
  useful next step.

## What to check before calling a screen done

1. 375px wide (iPhone SE / small Android) — nothing clips, nothing scrolls sideways except an
   explicitly allowed chip strip.
2. 768px (iPad portrait) — two columns, drawer nav, tables scroll cleanly.
3. 1024px — the desktop sidebar appears and the layout does not jump awkwardly at the boundary.
4. 1280px and 1920px — content stays capped at 1280px and centred; the page does not stretch.
5. Zoom to 200% at 1280px — text reflows, nothing is lost. Older users zoom.
