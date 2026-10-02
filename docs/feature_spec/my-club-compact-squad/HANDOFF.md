# Handoff: My Club, compact squad list

## Overview
Today the Squad tab on My Club draws each player as a separate card. A card is about 76px tall plus an 8px gap, with the form score on a second line and a label above every value. A 25-player squad fills four to five screens.

This change swaps those cards for **one table**:
- **One row per player.** Rows are 40px by default, or 48px in a "comfortable" setting.
- **Column labels appear once**, in a header row.
- **Position group headers stay**, as thin bands inside the table.

Every field, rule and action the current row has is kept. Nothing about behaviour changes. This is a layout change only.

Two smaller changes on the same tab:
- The four `FigureCard`s become one thin strip, about 56px tall.
- The right-hand rail drops below the table when the viewport is narrow.

## About the design file
`TransferX - My Club Squad Compact.dc.html` is a **design reference built in HTML**, not production code. Open it in a browser to try it:
- The chips filter the list.
- Clicking a value under "Yours" edits it inline.
- The Tweaks panel has `density` (Compact / Comfortable).

Rebuild it in the existing React + Tailwind v4 frontend using the semantic tokens already in `index.css` (see `design_handoff_transferx/TOKENS.md`). The mock uses light-theme hex values. **Use the token classes, not the hex values**, so dark mode keeps working.

The mock data is invented. The live page also renders `TopPerformers` above the list; that is out of scope here, so leave it where it is.

## Fidelity
**High-fidelity.** Sizes, spacing, colours and behaviour are final.

## Files to change
| File | Change |
|---|---|
| `frontend/src/components/players/SquadTable.tsx` | Main rewrite: `PlayerRow` becomes a grid row, `PositionGroup` becomes a band plus rows, and the table header is new |
| `frontend/src/pages/club/MyClubPage.tsx` | The four `FigureCard`s become one `FigureStrip`; the body grid becomes wrapping flex |
| `frontend/src/components/clubs/SquadRail.tsx` | No logic change. Spacing tightens slightly (optional) |

Keep all existing props on `SquadTable`: `players, showContractDetails, formScores, fairValues, onUnlist, unlistingIds, onSetValuation, openListings, loanedIn, onList, listBlockedReason`. Add one: `density?: "compact" | "comfortable"`, defaulting to `"compact"`. Optionally persist it in localStorage under `squad.density`.

---

## 1. Page layout (`MyClubPage`)

### Body
Replace `grid grid-cols-1 gap-6 lg:grid-cols-[1fr_260px]` with wrapping flex, so the rail falls below the table whenever the main column would drop under 640px:

```tsx
<div className="flex flex-wrap items-start gap-6">
  <div className="min-w-0 flex-[999_1_640px] flex flex-col gap-3.5">{/* tabs, strip, chips, table */}</div>
  <aside className="flex-[1_1_260px] max-w-full space-y-3 lg:sticky lg:top-6 h-fit">{/* SquadRail etc. */}</aside>
</div>
```

### Header
The header is unchanged, with two fixes:
- `h1`: add `leading-[1.35]` so a wrapped name doesn't overlap the subtitle.
- Header buttons: add `whitespace-nowrap`.

### Tabs
Unchanged.

### Figure strip (replaces the 4 `FigureCard`s)
One card holding four cells, so the strip costs one row of height instead of a ~110px card grid.

- **Container:** `grid grid-cols-4 rounded-xl bg-surface ring-1 ring-border overflow-hidden`. Below `sm`, use `grid-cols-2`.
- **Cell:** `px-4 py-3 flex flex-col gap-0.5`.
  - Every cell after the first gets a left rule: `shadow-[inset_1px_0_0_var(--color-rule)]`. In the 2-column layout, use a top rule on the second row instead.
  - Label: `text-xs font-semibold text-text-secondary`.
  - Value: `text-xl font-bold tabular-nums` (20px).
  - Unit suffix (e.g. "/wk"): inline, `text-[13px] font-normal text-text-muted`.

| Label | Value | Rule |
|---|---|---|
| Contracts < 12mo | count | `text-warning-text` when > 0 |
| Listed | `openListings.size` | |
| Average age | 1 dp, or `—` | |
| Wage room | `formatCurrency(wage_remaining_weekly)` + ` /wk` | |

---

## 2. Toolbar (top of `SquadTable`)
A flex row: `flex flex-wrap items-center justify-between gap-2`.

**Left: chips.** Same three as today: `All {n}`, `Contract risk {n}`, `Listed {n}`.
- Sizing: `rounded-[20px] px-3 py-[5px] text-[13px] font-semibold whitespace-nowrap`. This is tighter than the current `px-3.5 py-1.5 rounded-lg`, and matches the 20px chip radius in TOKENS.
- Active: `bg-ink text-white`.
- Inactive: `bg-surface text-text-secondary ring-1 ring-inset ring-input-border hover:ring-accent`.

**Right:** `Sorted by contract risk` (`text-[13px] text-text-muted whitespace-nowrap`).

The `listClosedReason` paragraph stays above the toolbar, unchanged.

---

## 3. Table

### Container
- `rounded-xl bg-surface ring-1 ring-border overflow-x-auto`.
- Inner wrapper: `min-w-[860px]`. Below that width the table scrolls sideways and **columns never wrap**.

### Column grid
All rows (header and players) share one template, exported as a constant so the two can't drift:

```ts
export const SQUAD_COLS = "minmax(240px,2.4fr) 104px 72px 64px 104px 56px 150px";
// Player · Contract · Wage/wk · Model · Yours · Form · Status
```
Use `display:grid; grid-template-columns: SQUAD_COLS; column-gap: 12px; align-items: center; padding: 0 16px`.

If `showContractDetails` is false (other callers of `SquadTable`), drop the Contract, Wage, Model and Yours tracks. The template becomes `minmax(240px,1fr) 56px 150px`.

### Header row
- Height **34px**, `bg-surface-header`, bottom rule `shadow-[inset_0_-1px_0_var(--color-rule)]`.
- Text: `text-[11px] font-semibold uppercase tracking-[0.04em] text-text-muted`. This is the TOKENS overline style; 11px is allowed here.
- Labels: `Player`, `Contract`, `Wage/wk`, `Model`, `Yours`, `Form`, `Status`. Everything from `Wage/wk` onwards is right-aligned.
- Optional: make the header sticky inside the scroll container (`sticky top-0 z-10`). This needs the scroll container to have a max height, so only add it if the page layout allows.

### Position group band
Replaces the `h3` plus status line and its `mb-[22px]` gap.
- `min-h-8` (32px), `flex items-center gap-2.5 px-4 whitespace-nowrap`.
- Background: `bg-surface-quiet`. Bottom rule: `var(--color-rule)`.
- Label: `text-[13px] font-bold text-text`, e.g. "Goalkeepers".
- Status: `text-[13px] font-semibold`. Copy and colours are unchanged: `{total} of {min} minimum — covered` uses `text-success-text`, and `— priority gap` uses `text-danger-text`.
- If the group is empty, add **one row** (row height, `text-[13px] text-text-muted`) with the current copy: `No {label} in the squad.` or `No {label} match this filter.`
- Group order, `POSITION_TARGETS`, "Unpositioned" and the sort (contract months ascending, no contract last) are all unchanged.

### Player row
- **Height:** compact `h-10` (40px), comfortable `h-12` (48px).
- **Base:** bottom rule `shadow-[inset_0_-1px_0_var(--color-rule-faint)]`, `text-[13px] tabular-nums`, `hover:bg-surface-inset` (150ms colour transition).
- **No card, ring or radius per row, and no gap between rows.**
- Every cell: `whitespace-nowrap`. Numeric cells are right-aligned.

| Column | Content | Styling and rules |
|---|---|---|
| **Player** | Avatar · name · `{age} · {nationality}` | Flex `items-center gap-2.5 min-w-0`. **Avatar:** 26px circle; the photo if there is one, otherwise the initial at `text-xs font-bold` in the existing `POSITION_COLOUR[pos]` classes. **Name:** a `Link` to `/players/market/{id}`, `text-sm font-semibold text-text hover:text-accent truncate min-w-0`. **Meta:** `text-text-muted shrink-0`. The name truncates first; the meta never does. |
| **Contract** | `MMM yyyy` end date | `font-semibold`, coloured by months left: under 6 `text-danger-text`, 6 to 12 `text-warning-text`, otherwise `text-text-secondary`, none `text-text-muted —`. For a loaned-in player, show `Loan · {end MMM yyyy}` in `text-text-secondary`. |
| **Wage/wk** | `formatCurrency(wage_weekly)` (compact) | `text-text`. `—` if missing. |
| **Model** | `formatCompactCurrency(market)` | `text-text-secondary`. Same source order as today: fair-value model → `market_value`. If missing: `—` in `text-text-muted` with the existing "No model valuation…" `title`. Keep the existing range/confidence `title` too. |
| **Yours** | Club valuation, with the gap shown first | Flex `justify-end items-center gap-1.5`. **Gap** (shown only when `valuationGap()` isn't `in-line`): `▲12%` / `▼18%`, `font-semibold`. `wide` uses `text-warning-text`; `notable` uses `text-text-secondary`. Keep the existing `title`. **Value:** `font-bold text-text`, dotted underline (`underline decoration-dotted decoration-1 underline-offset-[3px]`), click to edit. **Unset:** `+ set` in `font-semibold text-accent`, same underline. **Read-only** (no `onSetValuation`): plain value, no underline. Loaned-in players show `—`. |
| **Form** | Score, plus ▲ / ▼ | Score `font-semibold`. Arrow `ml-[3px]`: ▲ `text-success-text`, ▼ `text-danger-text`, nothing when the trend is flat or null. `—` when there's no score. **This replaces the separate "Form 68 ↑" line under each card.** |
| **Status** | Action or flag | Flex `justify-end items-center gap-2`. The logic is identical to today's, in priority order: **1.** Loaned in → `On loan` (`text-[13px] font-semibold text-accent`) with the existing "not ours to sell" `title`. **2.** Listed → `Listed →` link (`text-accent font-semibold`) to `/sales/{listingId}`, followed by an `Unlist` text button (`font-semibold text-text-muted hover:text-text`, loading state from `unlistingIds`). **3.** Deal in progress → `Transfer pending` (`text-warning-text font-semibold`). **4.** Otherwise, if `onList` is set → `List` button (`px-2.5 py-[3px] rounded-lg text-[13px] font-semibold bg-surface text-text-secondary ring-1 ring-inset ring-input-border hover:bg-surface-inset`), disabled with a `title` when there's a `listBlockedReason`. **5.** Read-only → the flag text, or `—`. |

### Inline valuation edit
- Clicking the value or `+ set` swaps it for an input in the same cell. The row height doesn't change.
- Input: `w-16 rounded-md px-1.5 py-[3px] text-[13px] text-right bg-surface ring-1 ring-inset ring-accent`, `inputMode="numeric"`, `autoFocus`.
- Placeholder: the model figure.
- Keys: Enter or blur commits, Escape cancels.
- Parsing and the `onSetValuation(id, number | null)` call are unchanged from the current `commitValuation`.

### Touch targets
Rows are 40px. On touch devices (`@media (pointer: coarse)`), use the comfortable 48px height for every row. For hit area, give `List`, `Unlist` and the valuation button a negative-margin padding trick (`-my-2 py-2`) so they reach 44px without making the row taller. Follow `RESPONSIVE.md`.

---

## 4. Right rail (`SquadRail`)
- Content and logic unchanged.
- Card padding: `px-[18px] py-[13px]`, with the title and rows inside one `flex flex-col gap-2`, instead of separate header and body blocks.
- Contract cliff rows become one line: `{label} · {count}` on the left (count in `text-text-muted`) and the value on the right, `whitespace-nowrap gap-2`. This replaces the current two-line row.

---

## 5. Density math (why this works)
| | Today | Compact | Comfortable |
|---|---|---|---|
| Height per player | ~76px + 8px gap ≈ 84px | 40px | 48px |
| Group heading | ~22px + 10px + 22px gap ≈ 54px | 32px | 32px |
| 25 players, 4 groups | ~2,316px | ~1,166px | ~1,366px |

---

## 6. Behaviour checklist (must match today)
- [ ] Chip counts use the whole squad. A group's "x of y minimum" uses the unfiltered total.
- [ ] Rows sort by contract months ascending, with no contract last.
- [ ] Loaned-in players never show List, Unlist or a valuation edit.
- [ ] `List` is hidden until `salesData` has loaded (`onList` is undefined until then).
- [ ] `listBlockedReason` disables List and appears as its tooltip. The page-level paragraph remains for touch users.
- [ ] The gap banding stays in step with `backend/app/valuation/constants.py`.
- [ ] `LoansPanel` still renders below the table, including when the squad is empty.
- [ ] Dark mode: tokens only, no `dark:` classes.

## 7. Edge states
- **Empty squad:** the existing `EmptyState` is unchanged.
- **Loading:** a static grey block per row height (no shimmer), 8 rows.
- **Long names:** the name truncates and the full name goes in a `title`. The meta never truncates.
- **Narrow viewport:** the rail drops below, and the table scrolls sideways at a minimum width of 860px. Nothing wraps.

## Files in this folder
- `README.md`: this spec.
- `TransferX - My Club Squad Compact.dc.html`: the interactive design reference.
- `support.js`: the runtime the reference needs to open in a browser.
