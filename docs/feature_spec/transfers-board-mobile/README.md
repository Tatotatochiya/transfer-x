---
title: "Transfers board: a list on phones and tablets, a roomier board on laptops"
last_updated: 2026-11-14
status: Implemented 2026-11-14
owner: "TODO — assign a Product Owner"
---

# Transfers board: a list on phones and tablets, a roomier board on laptops

Written against `Tatotatochiya/transfer-x` `main` at `81c1034` (14 Nov 2026).

**Scope.** Frontend only:
- `frontend/src/pages/board/BoardPage.tsx`
- its test
- new components under `frontend/src/components/board/`
- one change to `components/account/NamePrompt.tsx`

**No API change.** `GET /board` already returns, for every card:
- `column`
- `side`
- `kind`
- `whose_move`
- `deadline`
- `link`
- `detail`
- `chased`
- `others`
- `updated_at`

**The problem.** The Transfers board (`/board`) has six stage columns per lane, and each lane scrolls sideways on its own. On a 390px phone about 1.3 columns fit. With Arsenal's demo data (5 transfers, 2 waiting on you):
- Both players being bought are off-screen to the right.
- A "your move" card is half cut off.
- 9 of 12 visible column slots say "None".
- The first card sits at about 725px of an 844px screen, under the name banner, title, buttons, switch and search.

On a tablet only 2.5 columns fit. On a 1280 laptop all six fit, but names are cut to "R. Gr…" and "M. …", and Paperwork and Completed are empty in both lanes.

**Goal.**
- **Below 1280px:** the same data as **a list grouped by whose move it is**, with each transfer's stage shown on its row and stage chips to filter. Tapping a row opens the transfer's page.
- **From 1280px:** the board stays, columns empty in every lane shrink to a thin strip, and a "Waiting on you" strip sits above the lanes.

**Design reference.** `TransferX - Transfers Board Mobile.dc.html` in this folder (needs `support.js` and `transfers-board-2026-11-14/` beside it). It has today's captures marked up, two phone frames, a tablet frame and a laptop frame. Where this README and the mock disagree, **this README wins** (§12).

---

## 0. Before you start

1. Follow `session-lifecycle`. Read:
   - `docs/PRODUCT_SPEC.md`
   - `docs/SESSION_HANDOVER.md`
   - product ADR 0008 (the board)
   - `docs/design-system/TOKENS.md` (type roles and colour roles, from the type-and-colour spec)
   - `docs/design-system/RESPONSIVE.md`
2. Apply `product-principles` and `engineering-standards`. Branch `transfers-board-mobile`. Build in the order in §9.
3. Follow the type and colour rules now in TOKENS.md:
   - role utilities only (`text-body`, `text-small`, `text-caption`, `text-section`, `eyebrow`)
   - nothing under 13px
   - stage is a category, so neutral
   - red only for "your move", "chased" and urgent deadlines
   - blue only for what you can tap or have selected
   - `designSystem.test.ts` must stay green
4. Don't change the board API, its ordering or its counts. If you find the frontend needs a field the API doesn't send, stop and say so.

---

## 1. Success criteria

- [ ] **Phone (390 × 844).** The first transfer row's top edge is **≤ 300px** from the top of the viewport, with the name banner not shown (§6). Every open transfer is reachable by scrolling **down only**: no sideways scrolling anywhere on the page.
- [ ] **Below 1280px**, transfers are grouped as **Waiting on you → In progress → Listed, no offers yet → Completed**. Empty groups are hidden.
- [ ] Each row shows:
  - player
  - position
  - buying from / selling to and the club
  - fee (compact)
  - deadline, if any
  - stage (bars and name)
  - what's happening, if it adds anything to the stage name
  - "+N more", chased and stalled badges, as on today's cards
- [ ] **Stage chips** show only stages with at least one transfer (after the side and search filters), each with its count, plus "All". Picking one filters the list. The choice is in the URL (`?stage=`).
- [ ] **Tapping a row** goes to `card.link`. No pop-up below 1280px.
- [ ] **From 1280px:**
  - the board as today, except any column empty in every shown lane renders as a 52px strip
  - a "Waiting on you" strip above the lanes when `counts.your_move > 0`
  - player names don't truncate at 1280 when four columns are open
- [ ] Both / Buying / Selling, search, History, New listing, Closed and the remembered side (`localStorage` and `?side=`) all still work at every width.
- [ ] Lint, typecheck and `vitest` pass. `designSystem.test.ts` passes with no new allowlist entries. Checked by hand at 390, 768, 1024 and 1280, light and dark.

---

## 2. Decisions

- **D1. List below 1280px, board from 1280px.** Use `useMediaQuery("(min-width: 1280px)")` (as `DealDetailPage` does for 1024). **Why 1280, not 1024:** the sidebar appears at `lg` (1024), leaving about 728px of content at 1024 wide. Six columns at about 110px each is worse than a list. At 1280 there's about 984px.
- **D2. Group by whose move it is**, not by stage. Stage becomes a property of the row. This follows the deal and offer room redesigns: what needs you comes first.
- **D3. Stage is neutral.** Five short grey bars and the stage name. Completed transfers use the Completed colour (success); that's the only coloured stage.
- **D4. Below 1280px a row is a link** to the transfer's page (offer, deal, enquiry or listing). The pop-up (`CardDetail`, with the conversation) stays for laptops only. The offer and deal pages are built for phones now, so the pop-up is an extra step.
- **D5. The phone header shrinks:**
  - title and one line of counts
  - the side switch full width
  - search and a ⋯ menu as 44px icon buttons
  - History and New listing move into the ⋯ menu below 640px
- **D6. The name banner** (`NamePrompt`) shows on the Dashboard only, not on every page. It's 170px on a phone and has nothing to do with transfers. **See Q1.**

### Open questions (build the default unless told otherwise)

- **Q1. The name banner on Dashboard only.** **Default:** yes, on every width. Alternative: keep it everywhere on laptops and limit it to the Dashboard below 1024px.
- **Q2. A conversation side panel on tablets** (tap a row, see the conversation beside the list). **Default:** not in this change. Rows open the page.

---

## 3. Data: from board to list

The page already fetches `Board` (`columns`, `closed`, `counts`) for the chosen side. Add a pure helper module `frontend/src/components/board/boardList.ts` (unit tested, §8):

```ts
export const STAGES = ["talking", "offers", "fee_agreed", "terms", "paperwork"] as const; // + "done"
export type GroupKey = "yours" | "progress" | "listed" | "done";

/** Flatten the board's columns into rows, keeping the API's order inside each column. */
export function boardRows(board: Board): BoardCard[];

/** Which group a card belongs to. */
export function groupOf(c: BoardCard): GroupKey {
  if (c.column === "done") return "done";
  if (c.whose_move === "your") return "yours";
  if (c.kind === "listing") return "listed";
  return "progress";
}

/** 1–5 for the five open stages, 6 for done. */
export function stageStep(column: string): number;

/** Groups in display order, each sorted; empty groups dropped. */
export function groupRows(rows: BoardCard[]): { key: GroupKey; label: string; hint?: string; rows: BoardCard[] }[];

/** Count per stage, for the chips, after side and search filters, before the stage filter. Zero stages omitted. */
export function stageCounts(rows: BoardCard[], labels: Record<string, string>): { key: string; label: string; count: number }[];
```

**Group order and sorting:**

| Group | Label | Hint | Sort |
|---|---|---|---|
| `yours` | Waiting on you | — | Soonest deadline first (no deadline last), then most recently updated |
| `progress` | In progress | nothing for you yet | Furthest stage first, then most recently updated |
| `listed` | Listed, no offers yet | — | Most recently updated |
| `done` | Completed | — | Most recently updated |

Use the column labels from the API (`board.columns[].label`) for stage names; don't hard-code them. Completed cards don't get a chip. The "Completed" group is enough.

**The detail line.** Show `card.detail` after the stage name, **unless** it equals the stage label, case-insensitive. ("Fee agreed" on a Fee agreed card says nothing new.) Today's detail strings join with " · ". Keep them as they come: "Countered · your move". (The mock writes "Countered, your move"; follow the API.)

---

## 4. Below 1280px: the list

### 4.1 Header

- **Phone (< 640):**
  - **Row 1:** `h1` "Transfers" (`PageHeader` title style) on the left. On the right, two 44px icon buttons:
    - **Search** (magnifier, `aria-label="Find a player or club"`)
    - **More** (⋯, `aria-label="More"`, `aria-haspopup="menu"`)
  - **Row 2:** the counts line in `text-small text-text-secondary`. "N waiting on you" is in `text-danger-text font-semibold` when N > 0; "· N buying · N selling" follows.
  - **Row 3:** the Both / Buying / Selling switch at **full width**. Keep today's `role="radiogroup"` markup and storage behaviour. Segments `min-h-11`, `text-body`.
  - **Row 4:** stage chips (§4.2).
  - **Search:** tapping it shows a full-width search input between the switch and the chips, focused, with a clear (×) button. It stays open while it has text. Same filter as today (player or club name).
  - **More menu:** a small popover anchored to the button with "+ New listing" (accent text) and "History". Escape and outside clicks close it. Focus goes to the first item.
- **Tablet (640–1279):** title and counts on the left. On the right, the switch (auto width), the search icon and the ⋯ menu. Chips below. Search opens as on phones.

`PageHeader` can take the title and subtitle. Pass the controls as `actions` on 640+. Below 640, render the controls under the header. If `PageHeader` can't do this cleanly, build the header in `BoardPage` and say so.

### 4.2 Stage chips

- A single row that scrolls sideways if it overflows: `overflow-x-auto`, scrollbar hidden, `-mx-4 px-4` on phones so chips run to the edge.
- First chip "All N", then one chip per stage from `stageCounts`, in stage order: "Listed 1 · Offers 1 · Fee agreed 1 · Personal terms 2".
- Chip style:
  - `min-h-9` (36px; the row is a scroller, so 36 is fine, but keep `px-3`)
  - `rounded-full`, `text-small font-semibold`
  - count in `text-text-muted tabular-nums`
  - **Selected:** `bg-accent-bg ring-1 ring-accent-ring text-text`, count `text-accent`
  - **Unselected:** `bg-surface ring-1 ring-input-border text-text-secondary`
- Markup: `role="radiogroup" aria-label="Stage"`, chips `role="radio" aria-checked`.
- State in the URL as `?stage=<column key>` (absent = All), kept alongside `?side=`. If the picked stage drops to zero, for example after a search or a side change, fall back to All.
- Under a filter, the list keeps its grouping. Below the last group show "Showing {Stage} · **Show all N**", where "Show all N" is a text button that clears the filter.

### 4.3 Groups

- Each group is a `<section aria-labelledby>` with a heading: `text-section font-bold`, a count in `text-caption font-semibold text-text-muted tabular-nums`, and the hint in `text-small text-text-muted` if there is one.
- "Waiting on you" has an 8px `bg-danger` dot before the label (`aria-hidden`; the label says it).
- Rows sit in one rounded list: `rounded-2xl bg-surface ring-1 ring-border`, rows divided by `border-t border-rule`.
  - "Waiting on you" uses `ring-danger-ring`.
  - Use `<ul>` / `<li>`.
- 20px between groups.

### 4.4 Row: `components/board/TransferRow.tsx`

The whole row is a `<Link to={card.link}>`. The player's name is plain text, **not** a `PlayerLink`, so links don't nest. `min-h-[64px]`, `px-4 py-3`, `hover:bg-surface-inset`, focus outline accent.

**Phone layout** (stacked):

```
[photo 40]  G. Słonina GK                         £21.5M   ›
            Selling to Chelsea                 2 days left
            ▬▬▭▭▭  Offers · Countered · your move
            [Chased] / [Stalled · 5 days] / +1 more   (when present)
```

- **Photo:** `FallbackImage` with `card.player_photo_url`, initials fallback, 40px, `bg-surface-inset text-text-muted`. The same component `PlayerLink` uses, without the link.
- **Line 1:**
  - name `text-body font-semibold`, truncating
  - position `text-small text-text-muted`
  - fee right-aligned `text-body font-bold tabular-nums` via `formatCompactCurrency`, with `<Estimate>` as on cards today
  - no fee → nothing
- **Line 2:**
  - left, `text-small text-text-secondary`:
    - "Buying from {club}" / "Selling to {club}"
    - if no counterparty: "Buying" / "Selling · listed" for listings
    - with a single side picked, drop the verb: "from Liverpool" / "to Chelsea"
  - right: `timeLeft(card.deadline)?.text` in `text-small`
    - `font-semibold text-danger-text` when `urgent` **or** the row is your move
    - otherwise `text-text-muted`
- **Line 3:** `StageSteps` (§4.5), then `text-caption`:
  - stage name `font-semibold text-text`
  - " · " and the detail, if it adds anything (§3): `font-semibold text-danger-text` when your move, `text-text-secondary` otherwise
- **Line 4, only when present:**
  - `ChasedBadge` / `StalledBadge` (same rules as `Card` today)
  - "+N more" in `text-small text-text-muted`
- **Chevron:** `›` in `text-text-muted`, `aria-hidden`.
- **`aria-label`:** "{name}, {buying from / selling to} {club}, {fee}, {stage}, {detail}, {time left}", parts that exist only.

**Tablet layout (640–1279):** one row in columns, as in the mock:

```
grid-template-columns: 40px minmax(0,1fr) 220px 96px 104px 16px
```

The columns are photo, player (name and position; buying from / selling to under it), stage (bars, stage name, detail under it), fee, due and chevron.

- A header row above the first group uses the `eyebrow` utility, `text-text-secondary`: Player · Stage · Fee · Due.
- Due shows "—" in `text-text-muted` when there's no deadline.
- Badges sit under the player column.

### 4.5 Stage bars: `components/board/StageSteps.tsx`

- Five bars, each 14 × 4px, `rounded-sm`, 3px gap.
- Steps before the current one are `bg-text-muted`, the current one `bg-text`, later ones `bg-border`.
- For `done`: all five `bg-success`, and the stage name is "Complete" in `text-success-text`.
- `role="img"` with `aria-label="Stage {n} of 5: {label}"`, so the bars aren't silent.
- `talking` is step 1 and `paperwork` step 5.

### 4.6 Closed and History

- Keep the "Closed (N)" toggle below the last group. When open, closed cards render as `TransferRow`s in a plain list (no grouping), not today's card grid.
- "Full history →" stays beside the toggle.
- History is also in the ⋯ menu.

### 4.7 Empty, loading, error

Keep today's: `Spinner`, "Couldn't load the board", and "Nothing in progress" with Browse players.

A search with no results shows "No transfers match "{text}"" with a "Clear search" text button.

---

## 5. From 1280px: the board

Keep `Columns`, `Card` and `CardDetail` as they are, with these changes:

1. **Collapsed columns:**
   - A column is collapsed when it has **no cards in any lane shown** (after the search filter). With side BOTH that's both lanes; with one side, that lane. Lanes stay lined up because both get the same set.
   - A collapsed column is `w-[52px] shrink-0`: a dashed `rounded-xl border border-dashed border-border` strip as tall as the lane's tallest column (min 120px), with the count "0" at the top and the label rotated (`[writing-mode:vertical-rl] rotate-180`) in `text-caption font-semibold text-text-muted`.
   - Give it `aria-label="{label}: none"`. Don't make it interactive.
   - Remove the `w-[260px] snap-start` sideways-scroll classes at this width. Open columns are `flex-1 min-w-0`.
2. **Waiting on you strip** (`components/board/WaitingStrip.tsx`):
   - Above the lanes when `counts.your_move > 0`.
   - One rounded bar: `bg-surface ring-1 ring-danger-ring rounded-xl px-4 py-2.5 text-small`.
   - It reads "● Waiting on you", then one item per your-move card (sorted as the "yours" group, §3): **name** + " · " + detail without the trailing "· your move" + the time left (red when urgent).
   - Items are separated by a `text-border` divider and wrap if they don't fit.
   - Each item is a button that opens `CardDetail`, as the card does.
   - It respects the search and side filters.
3. **Header:**
   - The search input moves onto the title line, `w-64`, before the switch.
   - History and + New listing stay as buttons.
   - Drop the separate search row.
4. Lane headings, `Card` and `CardDetail` stay as they are.

---

## 6. Name banner

In `NamePrompt.tsx`, return `null` unless `pathname === "/dashboard"`. Keep its existing rules: no name, not "viewing as", not dismissed this session. There's no `NamePrompt` test today; add `NamePrompt.test.tsx` (§8). (Q1.)

---

## 7. Component layout

| File | What |
|---|---|
| `components/board/boardList.ts` | `boardRows`, `groupOf`, `stageStep`, `groupRows`, `stageCounts`, the detail-dedupe helper |
| `components/board/StageSteps.tsx` | The bars (§4.5) |
| `components/board/TransferRow.tsx` | One row, phone and tablet layouts (§4.4) |
| `components/board/TransferList.tsx` | Groups, the tablet header row, the closed list (§4.3, §4.6) |
| `components/board/StageChips.tsx` | Chips (§4.2) |
| `components/board/BoardMoreMenu.tsx` | ⋯ menu (§4.1) |
| `components/board/WaitingStrip.tsx` | Laptop strip (§5) |
| `pages/board/BoardPage.tsx` | Fetch, side and search state, `?stage=`, picks list or board by `useMediaQuery("(min-width: 1280px)")`; keeps `Card`, `Columns` (with collapsing) and `CardDetail` |

Keep `BoardPage.tsx` under about 300 lines by moving `Card`, `Columns` and `CardDetail` into `components/board/` if needed. Export `BoardCard` and `Board` types from one place.

---

## 8. Tests

**`components/board/boardList.test.ts`:**
- `groupOf`: your move → yours; a listing → listed; `done` → done (even if your move); everything else → progress.
- `groupRows`: the order of groups and the sort inside each; empty groups dropped.
- `stageCounts`: zero stages omitted; done excluded; counts follow the side and search filters.
- `stageStep`: talking 1 … paperwork 5, done 6.
- The detail dedupe: "Fee agreed" on fee_agreed is dropped; "Agent commission · your move" on terms is kept.

**`pages/board/BoardPage.test.tsx`** (jsdom's `matchMedia` returns false, so the default render is the **list**):
- **List:**
  - groups render in order with counts, using a board with one card per group
  - each row is a link to `card.link`
  - a stage chip filters rows and writes `?stage=`
  - chips for empty stages aren't rendered
  - "Show all" clears the filter
  - search filters rows
  - the side switch still writes `localStorage` and refetches
  - "Waiting on you" text uses `text-danger-text`
  - stage bars carry their `aria-label`
- **Board:** mock `window.matchMedia` to return `matches: true` for `(min-width: 1280px)` in a `describe` block, then move today's three tests ("splits both sides…", "shows one set of columns…", "BoardPage colours") into it unchanged. Add:
  - a column empty in both lanes renders as a collapsed strip with `aria-label="{label}: none"`
  - a column with one card in one lane is not collapsed in either lane
  - the waiting strip lists your-move cards, opens `CardDetail` on click, and is absent when `your_move` is 0
**`components/account/NamePrompt.test.tsx`** (new): renders on `/dashboard` for a user with no name, not on `/board`.

---

## 9. Build order (one commit each)

1. `boardList.ts` + tests.
2. `StageSteps`, `TransferRow` (phone layout) and `TransferList`. `BoardPage` renders the list below 1280px. Move the existing board tests into the desktop `describe`.
3. Stage chips + `?stage=`.
4. Phone header: full-width switch, search icon, ⋯ menu.
5. Tablet row layout (640–1279) + header row.
6. Laptop: collapsed columns, waiting strip, search on the title line.
7. `NamePrompt` on the Dashboard only.
8. Docs (§11).

---

## 10. Manual checks

At **390 × 844, 768 × 1024, 1024 × 768 and 1280 × 800**, light and dark, signed in as `arsenal@transferx.com` (demo data):

- The first row's top edge is ≤ 300px at 390 (measure it).
- Nothing scrolls sideways except the chip row.
- Every transfer is reachable.
- Rows open the right page: an offer, a deal, a listing and, if present, an enquiry.
- Chips: counts match, filter works, "Show all" works, and `?stage=` survives a reload.
- Buying / Selling: rows drop the verb, and the counts and chips update.
- Search: on phones it opens and closes, the clear button works, and the no-results message shows.
- ⋯ menu: New listing and History work. Keyboard: Tab, Enter, Escape.
- 1024: the list, with the sidebar showing.
- 1280: the board, Paperwork and Completed collapsed, "R. Gravenberch" and "M. Caicedo" in full, the waiting strip opening the pop-up.
- Text at 200% zoom on 1280 drops to the list layout without breaking.
- The name banner shows on the Dashboard only.

Also run `measure-type.mjs` (from the type-and-colour spec) on `/board`: 0% under 13px at 390 and 1280.

---

## 11. Docs (`documentation-standards`)

- **`docs/design-system/SCREENS.md`:** the Transfers entry becomes "list below 1280, board from 1280", with the groups, stage bars and chips.
- **`docs/design-system/RESPONSIVE.md`:** add the Transfers board to the breakpoint table. 1280 is the board's breakpoint (D1).
- **Product ADR 0008:** a short addendum saying that below 1280px the board shows as a list grouped by whose move it is, with the same data and the same columns as stages.
- **`docs/CHANGELOG.md`** and **`docs/feature_spec/README.md`** (add this spec).
- **This file:** `status: Implemented {date}` with deviations.

---

## 12. Where the mock differs (this README wins)

- **The breakpoint.** The mock says the board starts at 1024 (tablet landscape). This README says **1280** (D1). At 1024 the sidebar leaves too little room for six columns.
- **The mock's ⋯ menu has "Closed this window".** Closed stays as the toggle under the list (§4.6). The menu has New listing and History only.
- **Detail text.** The mock writes "Countered, your move". Use the API's `detail` as it comes ("Countered · your move").
- **The mock's phone top bar** is a sketch of today's app bar. Don't change the app bar.
- **The mock shows "Listed, no offers yet" only below the fold**, and no Completed group because the demo club has no done transfers. Both groups follow §3.
- **The laptop mock's waiting strip items open the page.** This README has them open the pop-up (§5), matching how cards behave at that width.

---

## 13. As built (2026-11-14)

Branch `transfers-board-mobile`. New `frontend/src/components/board/`: `types.ts`, `boardList.ts` (+ test), `StageSteps`, `TransferRow`, `TransferList` (with `ClosedList`), `StageChips`, `BoardMoreMenu`, `WaitingStrip`, and `BoardColumns` (`Card`, `Columns`, `CardDetail`, moved out of the page). `BoardPage.tsx` is 294 lines. `NamePrompt` shows on the Dashboard only (Q1 default).

Checked at 390 × 844, 768 × 1024, 1024 × 768 and 1280 × 800, light and dark, with demo data:
- First row's top edge at **297px** at 390. No sideways scrolling at any width except the chip row.
- At 1280: Fee agreed, Paperwork and Completed collapsed in both lanes; names in full; the waiting strip opens the pop-up.
- No text under 13px on `/board` at 390 or 1280.

### Deviations

- **The header is built in `BoardPage`**, not `PageHeader`: the counts line needs "N waiting on you" in red, and `PageHeader`'s subtitle is plain text. It uses `PageHeader`'s title and subtitle styles.
- **The ⋯ menu reuses `components/transfer/MoreMenu`**, which gained two small props: `triggerAriaLabel` (so the icon trigger is named "More") and an item's `accent` (for "+ New listing"). As everywhere it's used, opening it from the keyboard focuses the first item; a mouse click opens it without moving focus.
- **On phones the stage line wraps** ("Offers · Offer received · your move" on two lines) instead of truncating, which cut off the part that says what's happening. Tablets keep one line with the detail underneath, as specified.
- **The checks used Chelsea's demo data**, not Arsenal's: Arsenal had no open transfers on the local database at the time.
- **"Player names don't truncate at 1280 with four open columns"** was checked with three open columns (the data had no fourth stage in use).
