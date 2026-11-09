---
title: "Browse Players, players first (plus four quick fixes)"
last_updated: 2026-11-09
status: Implemented
owner: "TODO — assign a Product Owner"
---

# Browse Players, players first

**Implemented 2026-11-09.** Part 1 on `quick-fixes-nov`, part 2 on `browse-players-focus`. Where the build differs from the text below, see [Review revisions](#review-revisions) and [Deviations](#deviations).

Written against `Tatotatochiya/transfer-x` `main` at `e91795b` (9 Nov 2026). Route: `/players/market`. Page: `frontend/src/pages/market/PlayerMarketPage.tsx` (429 lines).

**Goal.** On a phone, players appear on the first screen. Everything above the results shrinks to four short rows, and the filter panel moves into a sheet below 1024px.

**Also in this spec: four quick fixes** found in the 9 Nov review. Ship them first, as their own PR (§11, part 1):
1. Player cards overlap on laptops.
2. No fallback when a photo or crest fails to load (app-wide).
3. Two sort buttons only sort the loaded page.
4. The "Asking price" filter is mislabelled.

**Design reference.** `TransferX - Browse Players and App Review.dc.html` in this folder (needs `support.js` and the `review-2026-11-09/` images beside it).
- **Part 1:** today's capture, plus the phone (clickable, with the filter sheet), iPad and laptop designs.
- **Part 2:** the wider review. This spec covers only Browse Players and Part 2 items 1, 3, 4 and 5.

The mock uses sample players. Where this README and the mock disagree, **this README wins** (§14).

**Scope.** Frontend, plus **one small backend change**: a `price` option for `sort_by` on `GET /players/market` (§5.9). No migrations, no permission changes.

**Related.** The deal room and offer room specs (`docs/feature_spec/deal-room-focus/`, `offer-room-focus/`) introduced `Sheet`, `SegmentedControl`, `useMediaQuery` and the `components/transfer/*` pieces. Reuse them.

---

## 0. Before you start

1. Follow `session-lifecycle`. Read `docs/PRODUCT_SPEC.md`, `docs/SESSION_HANDOVER.md`, `docs/design-system/RESPONSIVE.md` ("Filter rails" and "Touch targets") and `TOKENS.md`.
2. Apply `engineering-standards`. The backend change touches a query used by every market search, so test it.
3. Use two branches:
   - `quick-fixes-nov` for part 1 (§11): grid, images, sort, label. Merge it first.
   - `browse-players-focus` for part 2.
4. Read the whole of `PlayerMarketPage.tsx`, `PlayerFilters.tsx`, `ViewSwitcher.tsx`, `NLPlayerSearch.tsx`, `MarketRecommendationsPanel.tsx`, `PlayerCard.tsx` and `PlayerListRow.tsx` first. Keep these working exactly as today:
   - Saved views: create, update, delete, default view on load, "modified" state.
   - All filters and their query params.
   - The form-score and valuation batch queries, including the rule that a player account never fires the valuation call.
   - Compare (`CompareContext`, `CompareBar`) and shortlisting (`AddToShortlistButton`).
5. If the code differs from this spec, say so in your summary rather than quietly picking one.

---

## 1. Why

Measured on the running app with demo data, signed in as a club:

| | Phone 390 | iPad 768 | Laptop 1280 × 790 |
|---|---|---|---|
| First player | ~1,700px (screen 3) | ~1,280px | ~583px |
| Page length (grid, 24 players) | ~4,800px | ~2,600px | ~1,700px |
| Page length (list, 40 players) | ~9,300px | | |

**Before the first player, on a phone:**
- the name banner
- the title
- three budget tiles stacked one per row (~370px)
- AI Player Search
- the full filter rail (~620px; RESPONSIVE.md says phones and tablets get a "Filters (n)" sheet)
- saved views
- Recommended for you
- four sort buttons and the count

**Problems further down:**
- **Grid cards on a phone are ~125px each. List rows are ~150px**, each with a Make offer button.
- **Laptop: cards overlap.** `sm:grid-cols-3 xl:grid-cols-4` counts the window, not the space left after the 232px sidebar and the 250px rail. At 1280px each card is ~165px wide, chips collide and names truncate to "A. A…".

**Sorting:**
- "Best value first" and "Cheapest" sort only the loaded page, client-side. The page's comment says the server can't sort by value, but `sort_by=value` now exists (`players/service.py`, "B3"). There is no server sort by price.
- "Under fair value · on this page" counts only the loaded page.

**The "Asking price" filter** sends `min_market_value` / `max_market_value`, the outside market estimate. That's stored with `market_value_currency`, and EUR is the default the cards assume. It isn't the asking price.

---

## 2. Success criteria

**Part 1, quick fixes**
- [ ] At 1024, 1280 and 1440px, no card is narrower than 220px, and no chip overlaps another.
- [ ] Any player photo or club crest that fails to load shows initials, on every page listed in §5.1. No alt text is ever visible.
- [ ] Every sort option sorts the whole result set on the server. No client-side re-sorting remains, and "Under fair value on this page" is gone.
- [ ] The value filter is labelled for what it filters (§5.4).

**Part 2, Browse Players**
- [ ] **Phone, 390 × 700 of page:** the first player row starts at or above 320px, and at least four players are fully visible without scrolling, with the name banner dismissed. The banner itself is not this spec's job.
- [ ] **iPad, 768 × 960:** the first card row is visible without scrolling.
- [ ] **Laptop, 1280 × 790:** the filter rail and the first two rows of cards are visible.
- [ ] Below 1024px, filters, saved views and the view switch live in a `Sheet`. The rail doesn't render.
- [ ] The toolbar (Filters · Sort · view) stays pinned under the top bar while the results scroll.
- [ ] Every existing filter, saved-view action, compare and shortlist works on all three sizes.
- [ ] Lint, typecheck, `vitest` and the backend `pytest` pass. The new tests in §12 exist.

---

## 3. Decisions

### Decided

- **D1. Four rows above the results** on every size:
  1. Title and count.
  2. One search box.
  3. Toolbar: Filters (n) · Sort · view switch. On laptops the rail replaces the Filters button.
  4. Active filters as removable chips.

  The budget becomes one line of text (D4).
- **D2. One search box.**
  - Name mode, the default, is today's `search` filter.
  - A "✦ Describe" toggle inside the box switches it to the AI search (`useNLPlayerSearch`). Its results replace the list (§5.7).
  - "Club…" stays a filter inside the sheet or rail, not a second box.
  - `NLPlayerSearch`'s own card goes.
- **D3. Below 1024px, filters go in a `Sheet`.** The sheet is full height on phones and the existing 560px centred dialog on tablets. Saved views sit at the top of the sheet. The footer button shows the live count: "Show {n} players".
- **D4. The budget tiles become one line:** "£232.5M to spend · £49.9M a week in wages", from the same `/clubs/me` finance fields, clubs only. Drop "Under fair value".
- **D5. On phones, list view is a compact 72px row** (`PlayerRow`, §5.6).
  - Make offer and Compare leave the phone row: both are on the player page, and compare still works from grid view and from 640px up.
  - Below 640px the page **opens in list view** unless the person picked grid on this page on this device. The preference uses a new `localStorage` key, `playerMarketView.phone`, wrapped in try/catch.
  - From 640px up, the existing preference (`defaultMarketView`, `playerMarketView`) applies unchanged.
- **D6. Sort becomes one "Sort" menu with five options, all on the server:**

  | Label | Params |
  |---|---|
  | Name (A–Z), the default | `sort_by=name&sort_dir=asc` |
  | Best value | `sort_by=value&sort_dir=desc` (exists) |
  | Form | `sort_by=form_score&sort_dir=desc` (exists) |
  | Cheapest | `sort_by=price&sort_dir=asc` (**new**, §5.9) |
  | Youngest | `sort_by=age&sort_dir=asc` (exists) |

  The chosen sort lives in `filters.sort_by` / `sort_dir`, so saved views keep it, as today. Remove `sortChip` and the client-side `useMemo` sort.
- **D7. Recommendations become one row in the results:** "✦ Picks for your squad gaps", clubs only, after the 5th result on phones and in the chip row on laptops. It opens `MarketRecommendationsPanel` in a `Sheet` below 1024px, or expands it in place from 1024px.
- **D8. Paging.** Below 1024px, "Show 24 more" appends the next page (`useInfiniteQuery`), with "Showing {n} of {total}" beneath. From 1024px, `Pagination` stays as it is. Page size stays 24 for grid and 40 for list, as today.
- **D9. Grid columns:** `grid-cols-[repeat(auto-fill,minmax(220px,1fr))]`. That gives 1 column below about 470px, then 2, then 3 at 1280px with the sidebar and rail.
- **D10. One image component with an initials fallback,** used for every player photo and club crest (§5.1).

### Open questions (build the default unless told otherwise)

- **Q1. Do buyers need a real price filter in pounds?** Today's filter is the outside market value in euros. **Default:** keep the filter and label it honestly, "Market value (€ millions)". Write a follow-up ticket for a price filter that matches the new Cheapest sort.
- **Q2. Should "Cheapest" use the contract-ending discount?** The Lite pricing rule (`lite/service._prices`) cuts the model price by 30% when a contract ends within a year. **Default:** no discount in the SQL sort (§5.9). Note the difference in the code comment.

---

## 4. Layout

### Phone, below 640px

```
┌──────────────────────────────┐ AppShell top bar (unchanged)
│ Browse players     89 players│ h1 22px + count 14px muted
│ [🔍 Name, or describe a player   ✦ Describe] 48px
├──────────────────────────────┤ ← sticky under the top bar
│ [⚙ Filters 2][Sort: Best value ⌄][▦]  44px
├──────────────────────────────┤
│ (On TransferX ×)(Under 26 ×) Clear   chips, scroll sideways, 36px
│ £232.5M to spend · £49.9M a week in wages   14px, clubs only
│ ┌──────────────────────────┐ │
│ │ (AI) A. Isak  FWD   £7.4M ⌑│ 72px rows
│ │      Liverpool · 26 · Sweden  Form 57
│ │ …                         │ │
│ │ ✦ Picks for your squad gaps ›  after the 5th row
│ │ …                         │ │
│ └──────────────────────────┘ │
│ [        Show 24 more        ] │
│        Showing 24 of 89       │
└──────────────────────────────┘
```

### iPad, 640–1023px

The same order as the phone, with these differences:
- **Header line:** the budget joins the title line on the right.
- **Search row:** the search box, Filters and Sort sit on one line.
- **Results:** cards in auto-fill columns (3 at 768px).
- **Filters:** the sheet opens as the 560px centred dialog.

### Laptop, 1024px and up

```
Sidebar │ Browse players                    £232.5M to spend · £49.9M a week in wages
        │ ┌ rail 250px ┐ ┌ [🔍 Name, or describe a player  ✦ Describe] [Sort ⌄] 37 of 89 ┐
        │ │ Saved view │ │ (On TransferX ×)(Under 26 ×)          ✦ Picks for your squad gaps › │
        │ │ filters…   │ │ cards, auto-fill minmax(220px,1fr)                                 │
        │ └ sticky ────┘ │ Pagination                                                         │
```

The rail keeps today's contents, in this order: saved views (`ViewSwitcher`), the filters (`PlayerFilters`), then the view switch.

---

## 5. Components and changes

### 5.1 Quick fix: `components/ui/FallbackImage.tsx` (D10)

```ts
interface FallbackImageProps {
  src?: string | null;
  name: string;                    // initials source; never shown as alt text
  kind?: "player" | "club";        // circle for players, rounded square for clubs
  sizeClass: string;               // e.g. "h-12 w-12 text-lg"
  colorClass?: string;             // initials colours; default bg-accent-avatar text-accent-active
  fit?: "cover" | "contain";       // player photos cover with object-top; crests contain with p-1
  className?: string;
  alt?: string;                    // default "" (decorative: the name is always shown beside it)
  loading?: "lazy" | "eager";      // default lazy
}
```

- Render `<img>` while `src` is set and hasn't errored, with `onError={() => setFailed(true)}`.
- Otherwise render the initials: up to two capital letters from the first and last words of `name`, ignoring punctuation. "A. Isak" → "AI", "Arsenal" → "A".
- Reset `failed` when `src` changes.
- The container always has the final size, so the layout never shifts.

**Replace raw `<img>` for player photos and club crests in these files (user-facing first):**
- Components: `PlayerCard`, `PlayerListRow`, `PlayerLink`, `ClubLink`, `Avatar` (crest branch), `TransferHeader`, `SquadTable`, `SellerOrderBook`, `SeasonLedger`, `SquadStatsPanel`, `GlobalSearch`.
- Pages: `MyClubPage`, `ClubDetailPage`, `ClubListPage`, `SaleDetailPage`, `ShortlistDetailPage`, `PlayerMarketDetailPage`, `PlayerComparePage`, `WorldTeamDetailPage`, `LiteOffersPage`, `LiteBuyPage`, `AcceptInvitePage`.
- Then the admin pages in the same pass (`AdminClubsPage`, `AdminWorldImportPage`, `AdminRealWorldMovesPage`, `AdminPlayerDetailPage`, `AdminClubDetailPage`).
- `grep -rn "<img" frontend/src --include=*.tsx` must show only `FallbackImage` and non-photo images (logos, icons) afterwards.

**Keep each call site's colours.** For example, `PlayerCard` keeps its position-coloured initials via `colorClass`.

### 5.2 Quick fix: the grid (D9)

`PlayerMarketPage.tsx` line 392: replace `grid grid-cols-1 gap-3 sm:grid-cols-3 xl:grid-cols-4` with `grid gap-3 grid-cols-[repeat(auto-fill,minmax(220px,1fr))]`. Check `PlayerCard` at 220px: the name truncates with an ellipsis, chips wrap, and the actions stay inside the card.

### 5.3 Quick fix: sort (D6)

- **Backend:** add `price` (§5.9).
- **`PlayerFilterState.sort_by`:** add `"value" | "price"` to the union.
- **`PlayerMarketPage.tsx`:**
  - Replace `SORT_CHIPS` / `sortChip` / `handleSortChip` with a `SORT_OPTIONS` table (the five rows in D6) that sets `filters.sort_by` and `sort_dir` and resets the page to 1.
  - Delete the client-side `players` `useMemo` sort and the stale comment above `SortChip`, and render `data.items` directly.
  - Delete `underFairValueCount`.
- **In part 1**, the existing four chips remain the UI, now calling the server. Add "Name" as the default (none selected). Part 2 replaces the chips with the Sort menu.
- **The active sort's label is the source of truth.** A saved view with `sort_by=value` shows "Sort: Best value".

### 5.4 Quick fix: the value filter label (Q1)

In `PlayerFilters.tsx` (lines ~160–166), replace the section label "Asking price" with "Market value (€ millions)", and the placeholders with "Min" / "Max". Keep the param mapping (`× 1,000,000`, `min_market_value` / `max_market_value`). Also change the active-chip text for this filter (§5.5) to "€{min}–{max}M market value".

### 5.5 `MarketToolbar.tsx` (new)

Props: `filters`, `onChange`, `activeCount`, `view`, `onViewChange`, `onOpenFilters`, `isDesktop`.

- **Below 1024px:** `sticky top-14 z-20 -mx-4 bg-page px-4 pt-2.5 pb-2 md:-mx-6 md:px-6`. The `top-14` sits it under the 56px mobile top bar, and the mobile AppShell bar is fixed. Contents:
  - "Filters" button: `flex-1 min-h-11`, a filter icon, and a count badge (`bg-accent text-white`) when there are active filters.
  - Sort menu button: `flex-1 min-h-11`, "Sort: {label} ⌄".
  - View switch: a 44px icon button with `aria-label` "Switch to grid view" / "Switch to list view".
- **From 1024px:** no Filters button and no view switch (the rail has them). The Sort button sits next to the search box.
- **Sort menu:** the shared `components/transfer/MoreMenu` pattern, with `role="menu"`, items as `role="menuitemradio"` and `aria-checked`, and keyboard behaviour as in the More menu.
- **Active filter chips** (`ActiveFilterChips.tsx`, new):
  - A pure helper `activeFilterChips(filters): { key, label }[]` covers every non-default field except `search` and the sort. Labels: "On TransferX", "MID", "Age 18–25" / "Under 26" / "26 and over", "€5–20M market value", "Contract ends within 12 months", "Form 60+", "Listed", "{nationality}", "Club: {text}", "Goals 10+", "Assists 5+", "Apps 20+", "Rating 7.0+".
  - Each chip is a `<button aria-label="Remove filter {label}">`, `h-9 rounded-full bg-accent-bg text-accent-active text-sm font-semibold`, with ×. Removing one resets that field to `DEFAULT_PLAYER_FILTERS` and the page to 1.
  - After the chips, a "Clear" text button resets everything except `search`.
  - Below 1024px it's one sideways-scrolling row (`overflow-x-auto`, the strip RESPONSIVE.md allows). From 1024px it wraps.
  - "On TransferX" is a default (`buyable: true`) but still shows, because it changes the results a lot.

### 5.6 `PlayerRow.tsx` (new; list view below 640px)

The whole row is a `<Link to={/players/market/:id}>`, unlike today's `PlayerCard`, which is a `div` with `onClick`. The shortlist button sits outside the link.
- **Row:** `flex min-h-[72px] items-center gap-3 py-2.5 pl-3.5 pr-1 border-t border-rule first:border-t-0`.
- **Photo:** `FallbackImage kind="player" sizeClass="h-10 w-10 text-sm"`, initials in position colours (`bg-pos-*-bg text-pos-*-text`).
- **Middle** (`min-w-0 flex-1`):
  - Line 1: the name (16px/600, truncate) and a position badge.
  - Line 2 (14px muted, truncate): `{club or "Free agent"} · {age} · {nationality}`.
  - A "Listed" badge, when `open_to_offers`, goes at the end of line 2.
- **Right** (text-right):
  - Line 1, 15px/700: the price figure. Use the fair-value signal's `reference_price` (the asking price) when present, else its fair value with a "model" note, else "—". This is the same "what would he cost" logic as `PlayerListRow`; extract it to `lib/playerPrice.ts` and use it in both.
  - Line 2, 13px/600: "Form {n}", in success/warning/danger text by band (as `PlayerCard`'s form colours).
- **Shortlist:** `AddToShortlistButton size="compact"`, in a 44 × 44 hit area.
- **Container:** `rounded-xl bg-surface ring-1 ring-border overflow-hidden`.
- **From 640px up**, list view keeps `PlayerListRow` unchanged.

### 5.7 Search (D2): `MarketSearch.tsx` (new)

- **Field:** one `role="search"` form with a visible-on-focus label "Search players". Below 1024px it's `min-h-12`, 16px text (no iOS zoom); from 1024px `min-h-11`. A search icon on the left; the "✦ Describe" toggle button on the right (`aria-pressed`).
- **Name mode:** debounce 300ms, then set `filters.search`. That's today's behaviour, moved here from `PlayerFilters`.
- **Describe mode:**
  - Placeholder: 'Describe a player, e.g. "young left-back with good form"'.
  - Submit runs `useNLPlayerSearch().mutate({ query, buyable: filters.buyable })`, with the same body `NLPlayerSearch` sends today.
  - While it's active, the results area shows:
    - An "Interpreted as: {data.filters.interpreted_as}" line, plus `FilterChips` from `NLPlayerSearch` (export it).
    - The NL players as `PlayerRow`s (adapt `NLPlayerSearchResult` → row props: name, position, `current_club`, age, nationality, `price` with `price_basis`, form). Add a third line in 13px muted with `why.join(" · ")`.
    - "{total} players found".
    - A "Back to all players" button that leaves Describe mode.
  - Pagination is hidden in this mode (the NL endpoint returns one list).
- **`NLPlayerSearch`:** after this, the component is only used through its exported pieces. Delete the card if nothing else imports it.
- **"Club…" search:** moves from the top of `PlayerFilters` to its own field in the sheet and rail, unchanged otherwise.

### 5.8 Filters sheet (D3)

Below 1024px: `Sheet` with title "Filters", subtitle none, `open` from the toolbar.
- **Header:** add a "Clear all" text button. `Sheet` takes a `headerAction?: ReactNode`; add that prop if it doesn't exist, with no visual change elsewhere.
- **Body, in order:**
  1. **Saved view:** `ViewSwitcher` in a compact layout. It gets a `layout?: "rail" | "sheet"` prop. "sheet" renders a full-width select-style button that opens the list, plus "Save as view".
  2. `PlayerFilters` without the search field and without the view switch (the toolbar has it). Its controls grow to 44–48px below 1024px; position buttons are `min-h-11`.
  3. "Club…".
- **Live count:** a debounced (300ms) `GET /players/market` with the draft filters and `page_size=1`, reading `total`. Query key `["players","market","count",draft]`.
- **Footer:** a full-width primary "Show {total} players" (while loading: "Show players").
- **Draft model:** the sheet edits a **draft copy** of the filters. "Show {n} players" applies it and closes. × / Escape closes without applying. With unapplied changes, ask with `useConfirm` ("Discard filter changes?").
- **Saved views in the sheet apply straight away** (as today) and update the draft.

From 1024px the rail renders as today, wrapped in `lg:sticky lg:top-20`, with `MarketSearch` removed from it.

### 5.9 Backend: `sort_by=price`

In `backend/app/players/router.py`, add `price` to the `sort_by` pattern. In `players/service.py`, add a branch next to `value`:

```
price = CASE
  WHEN players.status = 'FREE_AGENT' THEN 0
  ELSE COALESCE(open_sale.asking_price, val_latest.fair_value)
END
```

- `open_sale`: the player's `Sale` with `status = OPEN` and `sale_type != AUCTION`, the same rule as `lite/service._prices`. Join it through a subquery: one row per player, the most recent if there are several.
- `val_latest`: reuse the latest-valuation subquery the `value` branch already builds. Factor it into a small helper used by both branches.
- Nulls sort last, as every other sort here does.
- Add a comment that this is `_prices` without the 30% contract-ending discount (Q2).

**Tests** (`backend/tests/test_players.py`, beside `test_market_sort_by_value_ranks_most_undervalued_first`):
- A free agent first.
- A listed player sorted by asking price, ahead of a model-priced player who costs more.
- No price → last.
- `sort_dir=desc` reverses it.

Update the frontend types (`sort_by` union) and `docs/` API notes if there are any.

### 5.10 `PlayerMarketPage.tsx` after part 2

The page owns:
- the filters state and saved views
- the query (`useQuery` at 1024px and up, `useInfiniteQuery` below)
- the batch form and valuation queries (run per loaded page, as today)
- `isDesktop = useMediaQuery("(min-width: 1024px)")`
- layout

New pieces: `MarketHeader` (title, count, budget line), `MarketSearch`, `MarketToolbar`, `ActiveFilterChips`, `PlayerRow`, the filters `Sheet`, and `RecommendationsRow`.
- **`RecommendationsRow`** is a `<button>`, `min-h-[60px]` inside the list, using the same AI accent classes `MarketRecommendationsPanel` already uses (there's no dedicated AI token). It reads "✦ Picks for your squad gaps" with "Recommended for {club}" underneath.
- **Budget line:** clubs only, when `myClub.finance` exists: "{formatCompact(transfer_remaining)} to spend · {formatCompact(wage_remaining_weekly)} a week in wages". Add `formatCompact` to `lib/utils` if there's no compact formatter. It produces "£232.5M" with a capital M. Don't change other pages' formats in this spec.
- **Results count:** "{total} players" next to the title. From 1024px also "{n} of {total}" next to Sort, when filters are active.
- **Remove** the three `Card tier={2}` tiles and `<NLPlayerSearch>`.

---

## 6. Behaviour kept exactly

- Saved views: default on load, select, modified state, save to view, save as new, rename, delete, set default.
- Every filter param and its mapping (including `× 1,000,000` on the value bounds).
- Batch form and valuation calls, one per loaded page. In infinite mode, one per appended page, keyed by that page's ids. A player account never fires the valuation call.
- Compare: `useCompare`, `CompareBar` fixed at the bottom. On phones the bar must not cover "Show 24 more"; add bottom padding equal to the bar when `compareIds.length > 0`.
- Shortlisting.
- Public (signed-out) access to `/players/market`. With no club: no budget line and no recommendations, and the same layout otherwise.

---

## 7. Responsive summary

| | Phone < 640 | iPad 640–1023 | Laptop ≥ 1024 |
|---|---|---|---|
| Filters | Filters (n) → full-height sheet | Filters (n) → 560px dialog | sticky rail |
| Saved views | top of the sheet | top of the sheet | top of the rail |
| Search | one box, ✦ Describe | same | same, above the results |
| Sort | menu in the sticky toolbar | menu beside search | menu beside search |
| Results | `PlayerRow` list (default) or cards | cards, auto-fill | cards, auto-fill |
| Paging | Show 24 more | Show 24 more | Pagination |
| Recommendations | row after the 5th result | row after the first card row | link in the chip row |
| Budget | one line under the chips | right of the title | right of the title |

---

## 8. Accessibility

- One `h1`, "Browse players". Results are a list (`<ul>`/`<li>`) of links.
- The search form is `role="search"`, and the ✦ toggle uses `aria-pressed`.
- The toolbar's icon button has an `aria-label`. The Sort menu uses `menuitemradio`.
- Chips are buttons named "Remove filter …".
- The sheet traps focus and returns it to the Filters button. The footer count is in an `aria-live="polite"` region.
- After "Show 24 more", move focus to the first new row.
- `FallbackImage` is decorative (`alt=""`), because the name is always beside it.
- Touch targets are 44px minimum below 1024px; the main buttons are 48px.

---

## 9. Permissions and data

- No new data is exposed. The budget line uses the club's own finance (clubs only, as the tiles did).
- The valuation batch stays off for player accounts. In Describe mode, `price` comes from the NL endpoint as today.
- `sort_by=price` reads the asking price only from **open, non-auction** listings, which the market already exposes, and the fair value, which the cards already show. Nothing confidential (such as a club's own valuation) is used.

---

## 10. Files

**Part 1 (quick fixes)**
- **New:**
  - `components/ui/FallbackImage.tsx` (+ test)
- **Changed:**
  - the image call sites in §5.1
  - `PlayerMarketPage.tsx`: grid; server sort; remove the client sort and the fair-value count
  - `PlayerFilters.tsx`: `sort_by` union, value label
  - `backend/app/players/router.py`, `backend/app/players/service.py`, `backend/tests/test_players.py`

**Part 2 (Browse Players)**
- **New:**
  - `components/market/MarketHeader.tsx`
  - `components/market/MarketSearch.tsx`
  - `components/market/MarketToolbar.tsx`
  - `components/market/ActiveFilterChips.tsx` (+ `activeFilterChips` helper and test)
  - `components/market/RecommendationsRow.tsx`
  - `components/players/PlayerRow.tsx` (+ test)
  - `lib/playerPrice.ts` (+ test)
  - `pages/market/PlayerMarketPage.test.tsx`
- **Changed:**
  - `PlayerMarketPage.tsx`
  - `PlayerFilters.tsx` (no search; `layout` sizing below 1024px)
  - `ViewSwitcher.tsx` (`layout="sheet"`)
  - `NLPlayerSearch.tsx` (export `FilterChips`; delete the card if unused)
  - `PlayerListRow.tsx` (use `lib/playerPrice`)
  - `components/ui/Sheet.tsx` (`headerAction`, only if missing)

---

## 11. Build order

**Part 1, branch `quick-fixes-nov`, one commit each:**
1. `FallbackImage` and its tests. Replace the call sites in user-facing components and pages, then admin.
2. The grid columns.
3. Backend `sort_by=price` with its tests. Frontend server sort for all chips; remove the client sort and "Under fair value".
4. The value filter label.
5. Changelog entry. Merge.

**Part 2, branch `browse-players-focus`:**
1. `activeFilterChips`, `lib/playerPrice`, and `PlayerRow` with tests.
2. `MarketHeader` and `MarketSearch` (✦ Describe). Remove the tiles and the `NLPlayerSearch` card.
3. `MarketToolbar` (sticky), the Sort menu, `ActiveFilterChips`.
4. The filters `Sheet` below 1024px (draft, live count, saved views); the rail from 1024px.
5. Phone list as the default (D5), `useInfiniteQuery` "Show 24 more" below 1024px, `RecommendationsRow`.
6. Tests (§12), manual checks, docs (§13).

---

## 12. Tests

**`FallbackImage.test.tsx`:**
- Renders the `img` when `src` is set.
- Fires `error` → shows initials ("A. Isak" → "AI").
- No `src` → initials.
- A new `src` resets it.
- No visible alt text in any state.

**Backend:** §5.9.

**`activeFilterChips.test.ts`:**
- Each field produces the right label.
- Defaults produce only "On TransferX".
- Search and sort never produce a chip.

**`playerPrice.test.ts`:** asking price; model fallback; nothing → "—"; free agent.

**`PlayerRow.test.tsx`:**
- The row is a link to the player.
- The shortlist button doesn't navigate.
- A failed photo shows initials.
- "Listed" appears when `open_to_offers`.

**`PlayerMarketPage.test.tsx`** (with `matchMedia` overridden per case):
- Below 1024px:
  - No rail. The Filters button opens a dialog.
  - Changing the position updates "Show {n} players" from the count call.
  - Applying closes it, adds a chip, and refetches page 1.
  - × with unapplied changes asks to discard.
- Removing the "MID" chip refetches without `position`.
- Sort → Cheapest calls `/players/market` with `sort_by=price&sort_dir=asc`, and the items render in server order. Nothing is re-sorted on the client.
- Below 640px with no stored choice: list view (`PlayerRow`s). After switching to grid, a reload stays grid (`playerMarketView.phone`).
- "Show 24 more" requests page 2 and appends.
- The ✦ Describe toggle → submit calls the NL search with `{ query, buyable }`. "Interpreted as" shows, the rows render with their "why" line, and "Back to all players" restores the list.
- From 1024px: the rail renders with saved views; pagination shows; no Filters button.
- Signed out: no budget line, no recommendations row, and no valuation call. Same for a player account (valuation off).
- Saved view default on load sets the filters and the sort label.

**Manual checks:**
- 375 × 667 and 390 × 844: first player at or above 320px, and four rows visible (§2). The toolbar sticks. The sheet's footer sits above the home indicator. The keyboard doesn't hide the search box.
- 768 × 1024: dialog sheet, three-column cards.
- 1024 × 768, 1280 × 790 and 1440 × 900: no card below 220px, no chip overlap, the rail is sticky.
- With photos blocked (devtools request blocking on the image host): initials everywhere in §5.1.
- Dark theme; 200% zoom at 1280px.

---

## 13. Docs (`documentation-standards`)

- **`docs/design-system/SCREENS.md`, "Browse Players":** describe this layout and link this spec.
- **`docs/design-system/RESPONSIVE.md`:**
  - "Filter rails": the sheet edits a draft and shows a live count; saved views go at the top.
  - Add a "Grids" note: card grids use `auto-fill, minmax(220px, 1fr)`, never breakpoint column counts, because breakpoints ignore the sidebar and rails.
- **`docs/feature_spec/README.md`:** add this spec.
- **`docs/CHANGELOG.md`:**
  - Part 1: server-side sort for every option, the new price sort, image fallbacks, the grid fix, the value filter label.
  - Part 2: the new Browse Players layout.
- **API notes:** `sort_by=price`.
- **Follow-up tickets:** Q1 (a price filter in pounds). The weekly wage ceiling in the demo data (£50M a week) and a sanity warning on the Finance form; out of scope here, from review item 7.

---

## 14. Where the mock differs (this README wins)

- **Filter label.** The mock shows "Market value (€ millions)". The spec agrees; an earlier draft of the review said "Model value (£)", which was wrong.
- **Tablet filters.** The mock describes a 420px panel from the right on iPads. Use the existing `Sheet` tablet dialog (560px, centred) instead, so there's one sheet pattern.
- **Recommendations wording.** The mock says "5 picks". Don't show a number until the panel has loaded its picks: "✦ Picks for your squad gaps".
- **Price figures on rows** follow `lib/playerPrice` (asking price, else model), not the mock's sample numbers.
- **"Buy" and "Sell" in the mock's top bar** are today's AppShell, unchanged by this spec.
- **Sample data.** The mock's players, values and form scores are samples.

---

## Review revisions

Decisions taken while building, where the spec was silent, self-contradictory or would have misbehaved. Each is the default the build ships with.

- **R1. Removing "On TransferX" turns it off.** It is the default (`buyable: true`), so "reset the field to `DEFAULT_PLAYER_FILTERS`" would leave it on and the chip would never go.
- **R2. "Clear" keeps the name search and the sort**, in the chip row, the sheet's "Clear all" and the rail's "Clear all filters" alike. The sort isn't a filter and has no chip; clearing filters shouldn't change it.
- **R3. The name search is now debounced (300ms).** §5.7 calls that today's behaviour; the old rail field set the filter on every keystroke.
- **R4. "Show {n} more" says how many will load:** the page size (24 grid, 40 list) or what remains. The phone list is 40 a page, so it reads "Show 40 more", not the mock's 24.
- **R5. No "{n} of {total}" beside Sort on laptops.** It repeated the title's count and Pagination's "1–24 of 60" without saying anything new.
- **R6. Chips for the two fields §5.5 didn't label:** status ("Free agents", "On TransferX clubs", "At clubs outside TransferX") and a one-sided value range ("€5M+ market value", "Up to €20M market value").
- **R7. The Sort menu is `MoreMenu`** with new optional props (`label`, `menuLabel`, `triggerClassName`, `align`; items with `checked` render as `menuitemradio`). The deal and offer pages' More menus are unchanged. The button shows a short label ("Sort: Name"); the menu shows "Name (A–Z)".
- **R8. Part 1's chips:** picking the active chip again returns to Name (A–Z), the default.
- **R9. The picks row in a grid** goes after the first card row, measured from the grid's real column count, since auto-fill columns aren't known in advance.
- **R10. `formatCompact`** writes thousands as "K" ("£609K") beside "M", so the budget line is consistent when the wage room is under £1M.
- **R11. The rail scrolls on its own** (`max-height: 100vh − 6rem`): saved views plus every filter is taller than a 790px laptop screen, so a plain sticky rail would hide its bottom.
- **R12. The budget line renders once:** in the header from 640px, under the chips below 640px, not twice with one hidden by CSS.
- **R13. `lib/playerPrice`** has two parts: `askingPrice` keeps the list row's `market_value` fallback exactly; `playerPrice` adds the free agent ("Free") and the model fallback for `PlayerRow`.
- **R14. Saved views in the sheet** show their star, rename and delete buttons at 44px all the time; on the rail they still appear on hover.
- **R15. The spec was added to the repo in part 1,** so part 1's changelog link resolves.

## Deviations

- **Code that differs from the spec, left as it was:**
  - `localStorage.playerMarketView` is written but never read: from 640px the first view comes from the account preference (`defaultMarketView`) only. Unchanged, as D5 asks.
  - `PlayerCard` is a clickable `div`, not a link, so grid results are not "a list of links" (§8). Unchanged; the phone list rows are links.
  - The AI player search card was only used here, so it is gone; `NLPlayerSearch.tsx` now holds only `FilterChips`.
- **At 1024px the grid is one column** (439px): beside the sidebar and rail, two need 452px and the scrollbar takes 15px. No card is under 220px, which is the criterion.
- **Checked on screen (local demo data, Manchester City):** phone 390×700 and 375×667 (first player at 315px; five and four rows visible), the filters sheet at 390 and as the 560px dialog at 768, the Sort menu, iPad 768 (three columns), 1024, 1280 and 1440 (narrowest card 224px), dark theme at 390 and 1280, signed out at 390. No horizontal scroll at any size.
- **Not checked:** a real iPhone (sheet footer above the home indicator, keyboard over the search box), blocked photos in devtools (covered by `FallbackImage` tests), 200% zoom. Lint can't run (no eslint in the repo).
- **Follow-up tickets (suggested, not raised):** Q1, a price filter in pounds matching the Cheapest sort; review item 7, the demo data's weekly wage ceiling (£50M a week) and a sanity warning on the Finance form.

- **Follow-ups built 2026-11-09** (branch `follow-ups-nov`): Q1 a price filter in pounds; the admin warning for an implausible weekly wage budget (review item 7). The production club showing about £50M a week still needs its budget corrected by staff.
