---
title: "My Club: compact squad list"
last_updated: 2026-10-02
status: Active
owner: "TODO — assign a Product Owner"
---

# My Club: compact squad list

The design handoff is [`HANDOFF.md`](./HANDOFF.md), with the HTML reference. It replaces the Squad tab's player cards with one table (40px rows, column labels once, position bands), the four figure cards with one strip, and lets the right rail drop below the table on narrow screens. This file records the decisions taken at review (2026-10-02), which override the handoff where they disagree.

## Decisions

1. **One valuation parser, used by the squad table and the player profile.** The squad table read only the digits of what was typed: "18" and "£18m" both saved £18. The profile's facts strip read "18" as £18m. Both now use `parseValuation` (`lib/money.ts`):
   - a plain number under 1,000 is millions ("18" → £18m, "6.7" → £6.7m);
   - "m" and "k" suffixes work ("£18m", "750k");
   - a larger plain number is pounds ("18000000");
   - empty clears.

   This is the one behaviour change; the handoff said parsing was unchanged.
2. **The rail drops below at 880px, not 640px.** The table needs 860px. With the rail's 640px threshold, on 1280–1366px laptops the rail stayed beside the table and the table scrolled sideways. The main column's flex basis is now 880px, so the rail wraps first.
3. **The Wage column uses the compact format** (`formatCompactCurrency`, e.g. "£197k"), matching Model and Yours. The handoff's "formatCurrency (compact)" was ambiguous.

Also: the player name uses the shared `PlayerLink`, and the optional sticky header is left out.

## Progress

- **2026-10-02, built** (branch `my-club-compact-squad`):
  - `SquadTable` rewritten as the grid table; `SQUAD_COLS` shared by header and rows; `SquadTableSkeleton` for loading.
  - `MyClubPage` has the `FigureStrip` and the wrapping flex body. Its header also wraps on a phone: with `whitespace-nowrap` the buttons hid the club name.
  - `SquadRail` uses one-block cards and one-line contract cliff rows.
  - The density switch sits in the toolbar and is stored in `localStorage` under `squad.density`.
  - The valuation input uses `inputMode="decimal"`, not `"numeric"`, so "6.7" can be typed on a phone.
  - Tests: `lib/money.test.ts` (11) and `SquadTable.test.tsx` (6) cover sort order, unfiltered counts, "18" saving £18m, rejected text, loaned-in rows and a disabled List.
  - Checked in the browser as Manchester City at 390, 1280, 1440 and 1536px. The rail sits beside the table from about 1470px; below that it drops under the table, and the table never scrolls sideways.
