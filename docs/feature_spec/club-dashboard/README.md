---
title: "Club Dashboard: the club's front door"
last_updated: 2026-11-22
status: Active (building)
owner: "TODO — assign a Product Owner"
---

# Club Dashboard: the club's front door

Written against `Tatotatochiya/transfer-x` `main` at `b76d879` (22 Nov 2026).

**Scope:**
- **Frontend:** `pages/dashboard/DashboardPage.tsx` and `components/dashboard/*`, the club details form in `pages/club/MyClubPage.tsx`, and the sidebar's club card.
- **Backend:** two nullable colour columns on `clubs`, editable through the existing `PATCH /clubs/me`.

There are no new endpoints. Every figure on the new Dashboard comes from queries the page or the app already makes.

**The problem.**
- **Nothing on the page is the club's.** It says "Dashboard" with "Arsenal · Premier League" underneath, and the crest appears nowhere.
- **On a phone, what needs you is far down.** The name banner and the setup checklist push "Waiting on you" down to about 690px. The page is about 2,360px long.
- **The same transfer shows up repeatedly.** Listings, offers and deals are three panels (empty ones still take space), and a your-move deal appears both in "Waiting on you" and in "Active deals".
- **The squad is one number:** "Squad 25 · Fully covered".

**Goal.**
- The page opens with **one band in the club's colours**, with the crest, the club's name, its league and the season.
- Under the band, in order on every device:
  1. **Needs you**
  2. **Money**
  3. **Your squad** (a card per team, once teams exist)
  4. **Transfers in progress** (one list)
  5. **For you** (market and AI)
  6. **Recently completed**
- Club colour stays **inside the band** and on the sidebar's crest ring. Buttons, links and statuses keep TransferX's colours, so red still means "needs you" and blue still means "tap this".

**Design reference.** `TransferX - Club Dashboard.dc.html` in the design handoff folder `design_handoff_club_dashboard/` (needs `support.js` and `dashboard-2026-11-22/`), kept outside the repo like earlier handoffs. It has today's captures, a laptop frame, a tablet frame, a phone frame, four band variations and the colour setting. **Where this README and the mock disagree, this README wins** (§13). The biggest difference: the mock's under-18 and women's cards are illustrations (§5).

---

## 0. Before you start

1. Follow `session-lifecycle`. Read:
   - `docs/PRODUCT_SPEC.md`
   - `docs/SESSION_HANDOVER.md`
   - `docs/design-system/TOKENS.md` (type roles, colour roles)
   - `docs/design-system/RESPONSIVE.md`
   - `docs/feature_spec/club-team-roles-and-onboarding.md`
   - **`docs/feature_spec/leagues-and-club-teams/README.md` and product ADR 0013 (proposed).** The Dashboard's team cards must follow that model, not invent their own (§5).
2. Apply `product-principles` and `engineering-standards`. Branch `club-dashboard`. Build in the order in §10.
3. Follow TOKENS.md:
   - role utilities only
   - nothing under 13px
   - categories neutral
   - red only for "needs you", errors and urgent deadlines
   - violet only for the AI
   - `designSystem.test.ts` must stay green with no new allowlist entries
4. **The club's colours are an exception to the colour roles, allowed only in the band and the sidebar crest ring** (§3). Add that rule to TOKENS.md in the same PR (§12), with an inline style or CSS variables, not new Tailwind colour tokens.
5. Don't change `GET /clubs/me/dashboard`, the sidebar badges or what counts as "waiting on you". The sidebar splits that count into a Transfers badge and an Approvals badge (`Sidebar.tsx`, `WAITING_ROUTE`); the Dashboard's "Needs you" count must equal their sum, which is `waiting_on_you.length` (§4.2).

---

## 1. Success criteria

- [ ] **Brand colours on the club.** `clubs` has `brand_primary` and `brand_secondary`: nullable `#RRGGBB`, set and cleared by a club admin (`CLUB_ADMIN`) from My Club's club details, and validated by the backend.
- [ ] **The band.** The Dashboard opens with a band in the club's primary colour, with:
  - the crest on a white disc
  - the club's name as the page's `h1`
  - league, season and city
  - on 640px and wider, a "N waiting on you" pill and a window pill
  - a 6px stripe in the secondary colour

  With no colours set, it's a white card (§3.4).
- [ ] **Band type.** The club's name uses the Title role (`text-title-sm sm:text-title`), the page `h1` in TOKENS.md. Display is for hero figures only.
- [ ] **Band contrast.** The band's text is white or ink, whichever reaches 4.5:1 on the primary. A unit test covers the choice for white-text, ink-text and darkened colours (§3.3). Dark mode uses a darkened primary that is checked the same way.
- [ ] **Needs you** is one card that merges:
  - the server's `waiting_on_you` items
  - for people who don't approve, their own requests awaiting approval
  - housekeeping rows: setup, name, contracts about to run out

  Its count equals the sidebar's Transfers and Approvals badges added together (`waiting_on_you.length`). The old `WaitingOnYouBand`, the inline approvals link, `OnboardingChecklist` and `NamePrompt` no longer render separately on the Dashboard.
- [ ] **Transfers in progress** is one list built from `GET /board?side=BOTH`, using the Transfers board's `TransferRow` and `StageSteps`. Each transfer appears once. It replaces the three working panels.
- [ ] **Your squad:** one card for the club's squad (players, average age, position split, contracts ending within six months, aged 21 or under, squad needs). It's written so it can render one card per team when Phase B of the leagues-and-teams spec ships (§5).
- [ ] **On a 390 × 844 phone:** with no transfer-window or deadline banner showing, the "Needs you" heading's top edge is **≤ 220px** from the top of the viewport, and the page is **≤ 1,700px** long with the demo club's data. A banner, when it shows, sits between the band and Needs you and pushes it down by its own height; that's accepted, because a banner is the one thing more urgent.
- [ ] **Club colour appears nowhere except the band and the sidebar's crest ring.**
- [ ] Lint, typecheck and `vitest` pass. Alembic upgrade and downgrade run clean. Checked by hand at 390, 768, 1024 and 1280, in light and dark, with colours set and not set.

---

## 2. Decisions

- **D1. A club admin sets the colours.**
  - Stored on the club, set from My Club with two suggestions read from the crest image (when the browser can read it), two swatches and hex inputs.
  - No colours means the white band. This is the default for every club, and nothing is derived automatically without an admin choosing.
- **D2. The club colour is confined to the band and the sidebar crest ring.** It never colours buttons, links, tabs, badges, charts or text outside the band. Other clubs' pages never take on a club's colours.
- **D3. The band carries the page's identity.** The club's name is the `h1`. The browser title stays "Dashboard · TransferX". The `PageHeader` "Dashboard" title goes.
- **D4. Teams follow ADR 0013.**
  - Until Phase B ships, a club has one team, so the Dashboard shows **one squad card**. Its heading is "Your squad", and the card is called "First team".
  - When teams exist, the same component renders one card per team the viewer can see, and the heading becomes "Your teams".
  - **No player tagging is added here.** ADR 0013 rejects tagging players by team.
  - **Under-18s are not a team kind in ADR 0013.** See Q1.
- **D5. "Needs you" keeps the server's verdict.**
  - The counted rows are exactly `waiting_on_you`, the list the sidebar's Transfers and Approvals badges count between them.
  - Housekeeping rows (setup, name, contracts about to run out) sit under an "Also" divider. They aren't counted and don't touch the badge.
- **D6. The Dashboard is the same for everyone at the club.** What differs is what the server and capabilities already make differ: approvals only for approvers, "List" only with `MARKET_WRITE`.
- **D7. The setup checklist becomes one row** ("Finish setting up · 3 of 6 left") that opens the full checklist in a `Sheet`. The checklist's steps and dismissal stay as they are.

### Open questions (build the default unless told otherwise)

- **Q1. Under-18s / academy.**
  - ADR 0013 has FIRST and WOMEN teams only.
  - **Default:** no under-18 card. The squad card's "Aged 21 or under" line is the only youth view.
  - The alternative is a decision for the leagues-and-teams spec: add a YOUTH (or ACADEMY) team kind, with or without its own budget. Don't add it here.
- **Q2. A greeting in the band** ("Good afternoon, Aashish").
  - **Default:** yes, from 640px, when the user has a name, using local time (before 12:00 "Good morning", before 18:00 "Good afternoon", otherwise "Good evening").
  - Without a name, the greeting doesn't show.
- **Q3. Colour suggestions from the crest.**
  - Crest URLs are on other hosts, and a browser can only read the image's pixels if the host allows it (CORS).
  - **Default:** try in the browser. If the image can't be read, show no suggestions, only swatches and hex inputs.
  - Don't fetch crest images on the server for this. An arbitrary URL fetch is a server-side request risk.

---

## 3. Club colours

### 3.1 Backend

- **Migration** (next number after the current head): add `brand_primary VARCHAR(7) NULL` and `brand_secondary VARCHAR(7) NULL` to `clubs`. Downgrade drops them.
- **`Club` model:** two `Mapped[str | None]` columns.
- **`ClubUpdateRequest`:** add both fields as `str | None = None`.
  - Validate `^#[0-9A-Fa-f]{6}$`, store in upper case, and return 422 with "Use a colour like #DB0007" when invalid.
  - **Clearing:** today `update_my_club` drops `None` with `model_dump(exclude_none=True)`, so a colour can't be cleared that way. Accept `""` (empty string) as "clear" for these two fields only, mapped to `NULL` in the router before the update. Leave the behaviour of the other fields unchanged.
  - Setting a secondary without a primary is allowed but has no effect on the band (§3.4).
- **Responses:** add both fields to `ClubResponse` (own club, `GET /clubs/me`). **Not** to `ClubPublicResponse`: other clubs don't need them, and pages for other clubs never use them (D2).
- **Audit:** club detail edits aren't audited today (`clubs/service.update_club`), so these fields aren't either. Renaming a club or changing its league is also unaudited; that gap is out of scope here.
- **Demo mode:** `demo/journal.py` snapshots every column of `clubs` automatically, and its skip list holds only `users.last_active_at` and `deals.updated_at`, so the two columns need nothing.
- **Tests** (`backend/tests`):
  - an admin sets both
  - a lower-case hex is stored in upper case
  - `""` clears
  - `"red"` and `"#FFF"` give 422
  - a non-admin (`SCOUT`) gets 403
  - `GET /clubs/{id}` for another club doesn't include the fields

### 3.2 Setting them (My Club → club details)

Add a **"Club colours"** block to the existing club details form in `MyClubPage.tsx`, under "Crest URL". It's shown only to people with `CLUB_ADMIN`, like the rest of the form.

- **"Suggested from your crest":** up to two pairs (primary + secondary) read from the crest (Q3). Each is a 40px button showing two swatches and a name ("Red and white"); picking one fills both fields.
- **Primary and Secondary:** each a swatch next to a text input (`#RRGGBB`) plus the native `<input type="color">` behind the swatch.
- **Live preview:** the band at phone size (§4.1) with the club's crest and name.
- **Contrast line** under the preview:
  - "✓ White text reads clearly on your primary (5.2 : 1)"
  - or "Text on your primary will be dark, so it reads clearly (10.9 : 1)"
  - Use `text-success-text` for both. This is information, not a warning.
- **"Remove colours"** sends `""` for both.
- **Explanatory line** (`text-small text-text-muted`): "Your colours appear on your Dashboard and next to your crest in the sidebar. Buttons, links and statuses keep TransferX's colours, so they mean the same thing everywhere."

**Crest suggestions** (`lib/crestPalette.ts`):
- Load the crest into an `Image` with `crossOrigin = "anonymous"` and draw it to a 64 × 64 canvas. Add a cache-busting query (`?palette=1`): the page has already shown the crest in an `<img>` without `crossOrigin`, and a browser may reuse that cached copy, which can't be read.
- API-Football's image host (`media.api-sports.io`, most crests) sends `Access-Control-Allow-Origin: *`, so suggestions should work for most clubs.
- Read the pixels in a `try` (a tainted canvas throws). Ignore transparent pixels (alpha < 128) and pixels within 6% of white or black.
- Bucket by hue into 12 bins, then pick the two most common with at least 20° between them.
- Return pairs `[top, second]` and `[top, white or black, whichever contrasts more]`.
- If anything fails, return `[]`.
- Unit test it with a canvas mock or a pure function over a pixel array.

### 3.3 Band colour maths (`lib/brandColour.ts`, unit tested)

```ts
export function contrast(a: string, b: string): number;          // WCAG ratio, #RRGGBB
export const INK = "#14171F";
/** The band's text colour, and the background to use, for a primary in a theme. */
export function bandColours(primary: string, theme: "light" | "dark"): {
  bg: string;            // primary, or darkened (dark theme, or neither text passes)
  text: "#FFFFFF" | typeof INK;
  stripeFallback: string; // used when there's no secondary: white at 90% on dark bg, ink at 100% on light bg
};
```

- **Light theme:**
  - `bg` is the primary.
  - `text` is white when `contrast(primary, white) ≥ 4.5`, otherwise ink when `contrast(primary, ink) ≥ 4.5`.
  - If neither passes, darken the primary by 8% steps (mix with black) until white passes, and use that as `bg`.
- **Dark theme:**
  - Start from the primary mixed **25%** with black (`#000`), as the mock's dark band shows. If white then passes, use it.
  - Otherwise apply the light-theme rule to the mixed colour.
  - (An earlier draft said 75%. That turns every club almost black, e.g. Arsenal's `#DB0007` becomes `#370002`, and the band loses the club.)
- **Secondary.** It's used only for the bottom stripe and the sidebar crest ring is the primary. If the secondary equals `bg` (within a contrast of 1.2), use `stripeFallback` instead, so the stripe is visible.
- **Tests:**

  | Input | Result |
  |---|---|
  | `#DB0007` | white, 5.2 |
  | `#F5C400` | ink |
  | `#034694` | white |
  | `#777777` | darkened until white passes |
  | `#DB0007`, dark | `#A40005` (25% darker), white |
  | `#FFFFFF`, dark | `#BFBFBF` (25% darker): white fails, so ink; the test pins the rule |

### 3.4 The band with no colours

- `bg-surface ring-1 ring-border`, text `text-text`, league line `text-text-secondary`.
- The crest disc is `bg-surface-inset` with no ring.
- No stripe.
- For `CLUB_ADMIN` only, an "Add club colours" link (accent, `text-small font-semibold`) on the right goes to `/club#club-colours`. Give the block that id.

---

## 4. Layout

### 4.1 The band (`components/dashboard/ClubBand.tsx`)

The band is a `<header>` with `rounded-2xl overflow-hidden relative`. Its background and text colours come from `bandColours` as inline styles. Expose them as CSS variables `--band-bg` and `--band-text` on the element; don't add Tailwind tokens.

| | Phone (< 640) | Tablet (640–1279) | Laptop (≥ 1280) |
|---|---|---|---|
| Padding | `px-4 pt-4 pb-5` | `px-5 pt-5 pb-6` | `px-7 pt-6 pb-8` |
| Crest disc | 52px | 60px | 76px |
| Greeting (Q2) | hidden | `text-small font-semibold` at 90% | `text-body font-semibold` at 90% |
| Club name (`h1`) | `text-title-sm` | `text-title` | `text-title` |
| Second line | league · season | league · season | league · season · city |
| Pills | hidden | "N waiting on you" only | "N waiting on you" and the window pill, stacked on the right |
| Watermark | none | none | a large faint crest shape in the top right (10% white), `aria-hidden` |

- **Crest disc:** white (`#fff`), `FallbackImage` for `crest_url` (initials fallback in `bg`), ring `0 0 0 3px` of the text colour at 35%.
- **Banners:** `TransferWindowBanner` and `DeadlineBanner` render between the band and Needs you, unchanged (§1, phone target).
- **Season:** from `windowStatus` or the current date. A season runs July to June, so 22 Nov 2026 is "2026/27". Put that in a pure helper with a test.
- **"N waiting on you" pill:**
  - `rounded-full h-[30px] px-3 text-small font-semibold`, background the text colour at 16%, with a dot.
  - It scrolls to the Needs you card (`#needs-you`).
  - Hidden when N is 0.
- **Window pill:**
  - outline style (the text colour at 45%)
  - not enforced → "Window: no deadline set"
  - open with `current_window` → "{name} · closes {relative}"
  - closed → "Window closed"
  - `TransferWindowBanner` and `DeadlineBanner` keep rendering, **below** the band, unchanged.
- **Stripe:** `absolute inset-x-0 bottom-0 h-1.5` in the secondary colour (or `stripeFallback`). There's no stripe in the no-colours state.

### 4.2 Needs you (`components/dashboard/NeedsYouCard.tsx`)

The card is `id="needs-you"`, `rounded-2xl bg-surface`. It has `ring-1 ring-danger-ring` when the count is above 0 and `ring-border` otherwise.

- **Heading:** "Needs you" (`text-section font-bold`) with a `bg-danger` dot when the count is above 0, the count (`text-caption font-semibold text-text-muted tabular-nums`), and on 640px and wider "Most urgent first" (`text-small text-text-muted`) on the right.
- **Counted rows:** `dashboard.waiting_on_you`, in the server's order.
  - **Row:** photo (`FallbackImage`, 36px) · name + position · a sub-line with the reason in `text-danger-text font-semibold`, and "· buying from / selling to {club}" or the club name in `text-text-secondary` · amount (`formatCompactCurrency`) · deadline (`timeLeft`; red when urgent) · action button.
  - **Action button** (`Button size="sm"` primary): the same verbs as today ("Review", "Respond", "Open", "Reply"), going to `item.link`.
  - **Below 640px:** the row stacks (name and amount on line 1, the reason on line 2, the club on line 3). The whole row is the link, with no separate button and a `›`.
- **"Your requests awaiting approval"** (non-approvers with pending requests of their own): one row, not counted, "2 of your requests are awaiting approval", linking to `/club/approvals`. It's placed with the housekeeping rows.
- **"Also" rows** (not counted), under a `text-caption font-semibold text-text-muted` "Also" divider, in this order:
  1. **Contracts running out:** players with `days_remaining ≤ 60` from the existing expiring-contracts query who aren't listed. `ExpiringContractItem` has no listed flag: use the open listings the page already loads (`useOpenListings`). "{Name}'s contract ends in {n} days", with a "List" button when `can("MARKET_WRITE")` (opens `ListPlayerModal`, as today). Show at most 2, then "+N more" linking to `/club`.
  2. **Setup:** when `OnboardingChecklist` would show (steps remaining, not dismissed), "Finish setting up your club · {done} of {total}", with "Continue". It opens a `Sheet` with the full `OnboardingChecklist`. Export a `useOnboardingSteps()` hook from that file so the row and the sheet share one source.
  3. **Name:** when `NamePrompt` would show, "Add your name so your team sees who did what", with "Add name" (to `/account#name`) and a "Not now" text button using the same session key. `NamePrompt` is mounted in `AppShell` but already shows on `/dashboard` only, so it moves into this row: export its "should it show" and "Not now" logic as a hook (`useNamePrompt`) and remove `NamePrompt` from `AppShell`.
- **Empty state** (no counted rows): "Nothing needs you right now." in `text-body text-text-secondary`. Then the Also rows, if any.
- **Cap:** at most 5 counted rows; then "Show all {N}" expands in place.

### 4.3 Money (`components/dashboard/MoneyCard.tsx`)

It reads `myClub.finance`, as `StandingFiguresTier` does today.

- **Transfer budget free:** `transfer_remaining` of `transfer_budget_total`, with a bar.
- **Wage room a week:** `wage_remaining_weekly` of `wage_budget_total_weekly`, with a bar.
- **Committed:** `transfer_reserved + transfer_committed`, labelled "In open offers and deals". On laptops it's a row under the two figures, with the players' names when available from the board query (up to 3). Tablet makes it a third tile. Phone drops it.
- **Bars:**
  - fill `bg-text` for remaining, `bg-text-muted` for the committed part, track `bg-surface-inset`
  - neutral, as today
  - turn `bg-warning-fill` only when remaining is under 10% of the total
- **Link:** "Finance →" to `/club/finance`.

| | Layout |
|---|---|
| Laptop | One card, two figures side by side, the committed row under them |
| Tablet | Three tiles in a row |
| Phone | Two tiles side by side |

Figures use `text-title` on laptop and `text-headline` on tablet and phone, with `tabular-nums`.

### 4.4 Your squad (`components/dashboard/TeamCards.tsx`)

See §5 for the data. One card per team. Today there's exactly one.

- **Heading:** "Your squad" (one team) or "Your teams" (more than one), `text-section font-bold` (TOKENS: every card and section heading), with "My Club →" on the right.
- **Card:** `rounded-2xl bg-surface ring-1 ring-border p-4`.
  - **Title:** the team name ("First team"), with "View →" to `/club`.
  - **Figures:** players (`text-title`) and average age to one decimal (`text-title`), each with a `text-small` label.
  - **Position bar:** GK / DEF / MID / FWD as four neutral segments (`bg-surface-inset text-text-secondary text-caption font-semibold`), widths proportional to the counts, labels "GK 3" (just "3" below 640px).
  - **Lines** (`text-small`, label in `text-text-secondary`, value `font-semibold tabular-nums`):
    - "Contracts ending in 6 months": the count from the expiring-contracts query with `within_days=180`. In `text-warning-text` when above 0.
    - "Aged 21 or under": the count.
    - "Squad needs": "Covered", or "Need 1 GK, 2 DEF" in `text-danger-text`, from `POSITION_TARGETS`. Each need links to `/players/market?position=…`.
- **One team:**
  - Laptop: a single card spanning the row, with the figures, position bar and lines in three columns.
  - Tablet and phone: one full-width card.
- **More than one team (Phase B):**
  - Laptop: a 3-column grid.
  - Tablet: 3 columns.
  - Phone: a sideways scroller with cards 250px wide and dot indicators.

### 4.5 Transfers in progress (`components/dashboard/TransfersInProgress.tsx`)

- **Data:** `useQuery(["board", "BOTH"], …)`, the same key and fetcher as `BoardPage`, so the cache is shared. Rows come from `boardRows(board)`, excluding `done`.
- **Sort:** your move first, then by stage, furthest first.
- **Rows:** `TransferRow` with `layout="phone"` below 640px and `"tablet"` from 640px, `side="BOTH"`.
  - Rows that are your move also appear in Needs you. That's deliberate: this list is the overview, and Needs you is the to-do list.
  - Keep the row's red "your move" detail so the two agree.
- **Count:** heading "Transfers in progress" (`text-section`) with the count, and "Transfers →" to `/board`.
- **Includes the Listed stage** (listed players with no offers yet, and open enquiries), as the board does: it's the overview of everything open.
- **Show:** 4 rows on laptop and tablet, 3 on phones, then "+N more →" to `/board`.
- **Empty:** "Nothing in progress. Browse players →".

### 4.6 For you (right column on laptops, stacked otherwise)

- **For you in the market:** the existing shortlist-hits query, top 3. Each row: name, position, "On your {shortlist} shortlist · now listed", asking price. The rows link to the listing as today. "Shortlists →".
- **`BriefingCard`** and **`ScoutReportPanel`** stay as they are (AI violet). Stack them in this column: briefing first, then the scout report.
- **Recently completed:** the existing completed-deals query, top 2 (phone: 1). Each row: name, position, "Sold to {club} · {date}" / "Signed from {club} · {date}", fee. "History →" goes to `/board/history`. This replaces the `CompletedTransfersTable` table.

### 4.7 Page grid

| Width | Order and columns |
|---|---|
| **≥ 1280** | Band. Then `grid-cols-[minmax(0,1.55fr)_minmax(0,1fr)] gap-5`: Needs you │ Money. Then Your squad, full width. Then the same two-column grid: Transfers in progress │ (Briefing, For you in the market, Scout report, Recently completed) |
| **640–1279** | One column: Band, banners, Needs you, Money (3 tiles), Your squad, Transfers in progress, For you in the market │ Recently completed (2 columns from 768), Briefing, Scout report |
| **< 640** | One column: Band, banners, Needs you, Money (2 tiles), Your squad, Transfers in progress (3), For you in the market, Scout report, Briefing, Recently completed (1) |

Vertical gap: `gap-5` (20px) on laptop, `gap-4` below. 1024–1279 uses the tablet layout because the sidebar leaves about 728px.

### 4.8 What's removed from the Dashboard

| Removed | Replaced by |
|---|---|
| `PageHeader` "Dashboard" | `ClubBand` |
| `OnboardingChecklist` | the setup row (§4.2) |
| `WaitingOnYouBand` | `NeedsYouCard` |
| The inline approvals link | the "your requests awaiting approval" row in Needs you (§4.2) |
| `StandingFiguresTier` | `MoneyCard`; the window and squad figures move to the band and the squad card |
| `WorkingPanel` × 3 | `TransfersInProgress` |
| `ReferencePanel` × 3 | the squad card, For you, and Needs you |
| `CompletedTransfersTable` | Recently completed |

Delete these components if nothing else imports them. `grep` first; `FigureCard` may be used elsewhere. The offers-received, offers-sent, active-deals and open-sales queries go too, since the board query replaces them.

---

## 5. Teams (aligned with ADR 0013)

- **Today: one card from the club's squad.** The page already fetches `/clubs/{id}/players?page_size=100` and the expiring contracts. Compute in a pure helper `squadSummary(players, expiring, today)` in `components/dashboard/squadSummary.ts`, returning:
  - count
  - average age (one decimal, ignoring nulls)
  - counts by position
  - aged 21 or under
  - contracts ending within 180 days
  - gaps against `POSITION_TARGETS`

  Move `POSITION_TARGETS` into that file. Unit test it.
- **Shape it as a list of teams.** `TeamCards` takes `teams: TeamSummary[]` with `{ key, name, summary }`. Today it gets one entry, `{ key: "first", name: "First team", … }`.
  - When Phase B of the leagues-and-teams spec adds `teams`, the page builds one entry per team the viewer can see, with that team's players and contracts.
  - No other Dashboard change is needed.
  - Add a short note to the leagues-and-teams spec's §6.5 ("Surfaces") saying the Dashboard is ready for this.
- **Not in this change:**
  - under-18 or women's cards
  - a team switcher
  - per-team money
  - any player tagging

  The mock's under-18 and women's cards are labelled Sample and show where Phase B and C would land.

---

## 6. Sidebar club card

In `Sidebar.tsx`, the club card's `Avatar` (crest) gets a 2px ring in the club's primary when `brand_primary` is set: an inline `box-shadow: 0 0 0 2px {primary}`. That's the only change. Light and dark use the same primary for the ring; it's a thin line, and contrast doesn't apply to a decorative ring.

---

## 7. Component layout

| File | What |
|---|---|
| `lib/brandColour.ts` (+ test) | `contrast`, `bandColours`, mixing helpers |
| `lib/crestPalette.ts` (+ test) | Suggestions from the crest, or `[]` |
| `lib/season.ts` (+ test) | "2026/27" from a date |
| `components/dashboard/ClubBand.tsx` | §4.1, plus the no-colours state (§3.4) |
| `components/dashboard/NeedsYouCard.tsx` | §4.2 |
| `components/dashboard/MoneyCard.tsx` | §4.3 |
| `components/dashboard/squadSummary.ts` (+ test) | §5 |
| `components/dashboard/TeamCards.tsx` | §4.4 |
| `components/dashboard/TransfersInProgress.tsx` | §4.5 |
| `components/dashboard/MarketForYou.tsx`, `RecentlyCompleted.tsx` | §4.6 |
| `components/club/ClubColoursField.tsx` | §3.2, used in `MyClubPage` |
| `pages/dashboard/DashboardPage.tsx` | Queries and layout only (§4.7). Target under 250 lines |

---

## 8. Tests

**Backend:** §3.1.

**Frontend unit:**
- `brandColour.test.ts`: the cases in §3.3.
- `crestPalette.test.ts`: two distinct hues picked; near-white and transparent pixels ignored; `[]` on a thrown read.
- `season.test.ts`: 30 Jun 2026 → "2025/26"; 1 Jul 2026 → "2026/27".
- `squadSummary.test.ts`: average age with nulls, position counts, gaps, the 180-day count.

**`DashboardPage.test.tsx`** (update; mock the queries as the existing tests do):
- the `h1` is the club's name; "Dashboard" isn't a heading
- the band uses the club's primary as its background and white text for `#DB0007`, and ink for `#F5C400`
- no colours → the white band, with "Add club colours" for an admin only
- the Needs you count equals `waiting_on_you.length`; setup, name and contract rows are under "Also" and not counted
- the setup row opens the checklist in a sheet
- a contract ending in 45 days shows with "List" for `MARKET_WRITE` and without it for a scout
- Transfers in progress shows each board card once, excludes done, shows "+N more" past the limit, and links rows to `card.link`
- the squad card shows the count, average age, position split and "Covered" / "Need 1 GK"
- the money card shows the free budget and wage room, and turns the bar to warning under 10%
- no element outside the band (and the sidebar) has the club's primary in its inline style

**`MyClubPage` tests:**
- the colour block shows for `CLUB_ADMIN` only
- a suggestion fills both fields
- an invalid hex shows the inline error
- "Remove colours" sends `""`
- the contrast line reads white or dark correctly

---

## 9. Manual checks

At **390 × 844, 768 × 1024, 1024 × 768 and 1280 × 800**, in light and dark, signed in as `arsenal@transferx.com` (demo data), then again after setting colours:

1. **No colours:**
   - the white band, with "Add club colours" for an admin
   - nothing else on the page changes colour
2. **Primary `#DB0007`, secondary `#FFFFFF`:**
   - a red band with white text and a white stripe; in dark mode, a darker red
   - the sidebar crest ring is red
   - buttons are still TransferX blue
3. **Primary `#F5C400`, secondary `#14171F`:** ink text and an ink stripe.
4. **Primary `#034694`:** white text. The band doesn't read as a link.
5. **On the phone:**
   - "Needs you" is within 220px of the top
   - the page is ≤ 1,700px long
   - no sideways scroll (except a team scroller once there's more than one team)
6. **Needs you:**
   - the count matches the sidebar's Transfers and Approvals badges added together
   - the Also rows work: "List" opens the modal, "Continue" opens the checklist, "Not now" hides the name row for the session
7. **Transfers in progress:** rows open the right page, and "+N more" goes to the board.
8. **200% zoom at 1280:** nothing overlaps; the band wraps rather than clips.
9. **`measure-type.mjs` on `/dashboard`:** 0% of text under 13px.

---

## 10. Build order (one commit each; the page works after every step)

1. Backend columns, migration, `PATCH` validation and tests.
2. `brandColour`, `season` and `crestPalette` helpers with tests.
3. `ClubColoursField` in My Club (§3.2).
4. `ClubBand` on the Dashboard, replacing `PageHeader`. Sidebar ring (§6).
5. `NeedsYouCard` (replacing `WaitingOnYouBand`, the approvals link, the checklist and the name banner). `NamePrompt` off the Dashboard.
6. `MoneyCard`, `squadSummary` and `TeamCards`.
7. `TransfersInProgress`. Remove the working panels and their queries.
8. For you and Recently completed. Remove the reference panels and the completed table.
9. The layout grid per breakpoint (§4.7). Clean up unused components.
10. Docs (§12).

---

## 11. Risks

- **Club colours spreading.** Someone later uses `--band-bg` for a button. The test in §8 checks for this on the Dashboard. TOKENS.md states the rule (§12).
- **Unreadable band text from an odd colour.** `bandColours` never returns a pair under 4.5:1, and the tests pin it.
- **Crest suggestions failing** for crests on hosts that don't allow cross-origin reads. API-Football's host does, so this should be rare. The swatches and hex inputs always work (Q3). Don't proxy images to get round it.
- **"Needs you" and the sidebar badges disagreeing.** Avoided by counting only `waiting_on_you` (D5).
- **Phase B changes the squad data.** `TeamCards` takes a list, and the Dashboard only builds it, so Phase B changes one function.

---

## 12. Docs (`documentation-standards`)

- **`docs/design-system/TOKENS.md`:** add a "Club colours" rule. A club's own colours appear only in the Dashboard band and the sidebar crest ring, as inline styles from `bandColours`. They're never a token, never on interactive elements, and never on other clubs' pages.
- **`docs/design-system/SCREENS.md`:** replace the Dashboard entry with §4's order and layouts.
- **`docs/design-system/RESPONSIVE.md`:** add the Dashboard to the breakpoint table (laptop layout from 1280).
- **`docs/feature_spec/leagues-and-club-teams/README.md` §6.5:** "The Dashboard's squad card takes a list of teams (README_DESIGN_CHANGE §5)."
- **`docs/CHANGELOG.md`**, **`docs/feature_spec/README.md`** (add this spec), and the API docs for the two new club fields.
- **This file:** `status: Implemented {date}` with deviations.

---

## 13. Where the mock differs (this README wins)

- **Under-18 and women's cards.** The mock shows them with Sample figures. Build one squad card only (§5, Q1). The mock's "Scholarships ending" and "Ready to step up" lines have no data source.
- **The mock's money card says "Committed in deals £27.5M".** Use `transfer_reserved + transfer_committed`, labelled "In open offers and deals". The demo's real figure may differ.
- **The mock has no Briefing card, banners or "Also" rows.** They're kept (§4.1, §4.2, §4.6).
- **The mock's Needs you shows two counted rows**, Caicedo and setup. Setup is an "Also" row, not counted (D5).
- **The mock's phone "Transfers in progress" rows have no photo or club line.** Use `TransferRow` as it is.
- **The mock's crest is a stand-in shield.** Use the club's `crest_url` through `FallbackImage`.
- **The colour setting in the mock is a separate card.** Here it's a block inside My Club's club details form (§3.2).

---

## 14. Review changes (22 Nov 2026)

Checked against `main` at `fda513f` before building. Changed from the handoff:

- **Dark band.** Darkened 25%, not 75% (§3.3), matching the mock.
- **Club name type.** Title role, not Display (§4.1).
- **Sidebar badge.** There are two badges, Transfers and Approvals. "Needs you" equals their sum.
- **Phone target.** Measured with no banner showing.
- **Code facts settled:**
  - `NamePrompt` moves into Needs you; it already showed on the Dashboard only.
  - The demo journal needs nothing.
  - Club edits aren't audited.
  - The listed state comes from `useOpenListings`.
  - Crest suggestions use a cache-busting query.
- **Section headings.** `text-section`.
- **Transfers in progress.** Includes the Listed stage.
