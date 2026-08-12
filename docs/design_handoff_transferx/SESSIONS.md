# Work breakdown — 13 sessions

Ordered by dependency. Each session is scoped to roughly one working session with Claude Code:
enough to be a coherent chunk, small enough to review properly before moving on.

**Do not run sessions in parallel and do not skip ahead.** Sessions 1–2 change the foundation
every later session builds on; starting a page before the primitives are done means doing it
twice.

Each session below lists: what to do, which files it touches, what to read first, and a
definition of done. "Reference" means the design file to open in a browser and match.

---

## Session 0 — Setup and guard rails

**Do:**
- Copy `CLAUDE.md` from this package to the repo root. Merge it if one already exists.
- Read `TOKENS.md` and `RESPONSIVE.md` in full.
- Create a branch. All 13 sessions land on it; do not merge to main until Session 12 passes.
- Run the existing test suite and record the baseline. 28 backend test files exist; know which
  pass before you start.

**Done when:** the baseline is recorded and `CLAUDE.md` is in place.

---

## Session 1 — Design tokens

**Do:**
- Replace the `:root` block in `frontend/src/index.css` with an `@theme` block carrying every
  token from `TOKENS.md`. Tailwind v4 is CSS-first — no `tailwind.config.js` changes.
- Set the page background to `#f7f8fa` and base text to `#14171f` on `body`.
- Add the focus-visible ring rule globally.
- Add `prefers-reduced-motion` handling.

**Touches:** `src/index.css` only.

**Done when:** the app builds, every page renders in light colours (broken and ugly is expected
at this point), and no component references a removed variable.

---

## Session 2 — UI primitives

The highest-leverage session. Roughly 35 of 53 pages inherit their look from these files.

**Do:** restyle every component in `src/components/ui/` to the new tokens. At minimum:
`Badge`, `Button`, `Card`, `Panel`, `Table`, `PageHeader`, `StatCard`, `EmptyState`, `Modal`,
`Input`, `Select`, `Tabs`, `Tooltip`, `Spinner`, `Alert`.

Specific changes beyond colour:

- `Badge` gains a `move` variant taking `your` / `their` / `neither` (see README, "whose move").
- `Card` gains a `tier` prop: `1 | 2 | 3 | 4`, applying the ring, shadow and background from the
  four-tier table.
- `Button` gains the five variants in `TOKENS.md` and the mobile touch-target sizing.
- `EmptyState` loses any illustration and becomes a single line of 14px secondary text.
- `Table` is rebuilt as `ResponsiveTable` per `RESPONSIVE.md` — column definitions with a
  `priority`, and a `renderCard` for below 640px. **This is the biggest single piece of work in
  the session; do it last and give it its own review.**

**Reference:** `TransferX - Board v2.dc.html` for every visual value.

**Done when:** a page that only composes primitives — pick any admin page — looks correct with no
changes to the page file itself.

---

## Session 3 — App shell and navigation

**Do:**
- `AppShell.tsx`: white 232px sidebar on desktop, off-canvas drawer below 1024px, sticky top app
  bar below 1024px. Focus trap, Escape to close, body scroll lock, backdrop.
- `Sidebar.tsx`: light styling, four groups (Market / My Deals / Club / Scouting), count badges
  — alert-red badge when the count represents "your move" items, neutral otherwise, **no badge
  background at all when the count is zero or absent**.
- `GlobalSearch.tsx`: restyle only. Behaviour unchanged.

**Reference:** `TransferX - Board v2.dc.html` (desktop chrome), `RESPONSIVE.md` (drawer rules).

**Done when:** navigation works at 375 / 768 / 1024 / 1280px, keyboard-only navigation reaches
every item, and the drawer returns focus correctly on close.

---

## Session 4 — Dashboard

The flagship screen and the reference implementation of the four-tier hierarchy.

**Do:** rebuild `pages/dashboard/DashboardPage.tsx` as four tiers — "Waiting on you" band,
standing figures, three working panels, three reference panels, completed transfers table.

Every row in tier 3 carries a "whose move" badge. Tier 1 is empty-safe.

**Depends on:** the "whose move" API field. If it is not ready, build the UI against a temporary
client-side derivation in **one** helper module, `lib/whoseMove.ts`, marked with a TODO, so
there is a single place to delete later.

**Reference:** `TransferX - Board v2.dc.html`.

**Done when:** it matches the reference at 1280px, reflows per `RESPONSIVE.md`, and renders
correctly with zero waiting items, zero listings, and zero deals.

---

## Session 5 — Offer inbox and offer detail

**Do:** `pages/offers/` — tier-1 band for offers needing a decision, with their offer, your
valuation, deadline and inline negotiation history; a quiet table for everything else. Filter
chips: All / Your move / Their move / Accepted / Rejected.

Offer detail becomes the two-pane layout from `RESPONSIVE.md`, with the approval requirement
stated **before** the action buttons, not after.

**Reference:** `TransferX - Board v2 Screens.dc.html` (click "Inbox").

**Done when:** the two-pane layout collapses correctly to a segmented control on mobile.

---

## Session 6 — Deals list and deal room

**Do:**
- Deals list: one card per deal with the stage tracker inline, agreed fee, and whose move.
  `StageTracker.tsx` restyled to the pill row in the reference.
- Deal room: the three parallel negotiation lanes (club-to-club, agent commission, personal
  terms), the **terms diff table** (agreed vs proposed, changed rows tinted, effect column), and
  the message rail with an explicit shared/private banner.

**Note:** the terms diff "effect on you" column needs a present-value calculation that does not
exist yet — see `DECISIONS.md` item 5. Build the column; feed it a stub until the endpoint lands.

**Reference:** `TransferX - Board v2 Screens.dc.html` (list), `TransferX - Radical Bidding.dc.html`
tab "Contract negotiation" (deal room content — restyle chrome to Board v2).

---

## Session 7 — Finance and approvals

**Do:**
- Finance: two budget cards with four-segment bars (spent / committed / reserved / free), the
  approval-threshold card, and the "where the money is committed" table naming what each
  commitment is attached to and what releases it.
- Approvals: tier-1 band for the pending request carrying decision context (reserve, best bid,
  our valuation, squad effect), plus a decided table.

**Reference:** `TransferX - Board v2 Screens.dc.html` (click "Finance", "Approvals").

---

## Session 8 — My Club and squad

**Do:** replace the flat 11-column squad table with position groups, each carrying a verdict line
("1 of 3 minimum — priority gap"). Each player row shows contract end, wage, and a
market-vs-valuation bar. Rail: contract cliff, wage bill by position, age profile.

**Reference:** `TransferX - Radical Screens.dc.html`, tab "Squad". **Chrome must be restyled** —
drop the black band, use tier-2 figure cards.

**Done when:** rows reflow to cards below 640px with contract end and wage surviving, and the
market/valuation bar dropping.

---

## Session 9 — Browse players and player profile

**Do:** persistent left filter rail with saved views; result rows led by an asking-vs-fair-value
bar with a plain-language signal ("15% under fair value"); wage-fit check against actual wage
room; compare tray fixed to the bottom.

Filter rail becomes a bottom sheet below 1024px per `RESPONSIVE.md`.

**Reference:** `TransferX - Radical Screens.dc.html`, tab "Browse players". Restyle chrome.

---

## Session 10 — Listings, auctions and sale detail

**Do:** the bid ladder drawn to scale, with reserve and club valuation as vertical reference
lines through every bar. Seller view gets per-bid accept actions and the "if you accept now"
consequence card. Buyer view gets the bid composer with budget-after bar and the approval
requirement stated before submission.

**Reference:** `TransferX - Radical Bidding.dc.html`, tab "Bidding on a listing" — toggle between
seller and buyer views. Restyle chrome.

**Done when:** the ladder is legible at 375px (bars stay, reference lines stay, wage column
drops).

---

## Session 11 — Everything else

The remaining ~35 pages, which are variations on four archetypes. If Session 2 was done properly,
most need little or no page-level work.

| Archetype | Pages | Work |
|---|---|---|
| Admin table | 17 admin pages | Verify inheritance; fix any bespoke styling |
| List + filter | Transfers, notifications, shortlists, agent pages | Filter chip row + `ResponsiveTable` |
| Form | Account settings, club settings, create listing, register | Input tokens, 44px targets, error styling |
| Auth | Login, register, reset, verify | Centred card, page background, logo |

**Done when:** every route in `App.tsx` has been opened at 375px and 1280px and none is broken.

---

## Session 12 — Responsive and accessibility pass

**Do:**
- Walk every route at 375 / 768 / 1024 / 1280px against the checklist at the end of
  `RESPONSIVE.md`.
- Contrast audit: no text below `#667085` on white; every semantic colour pair passes AA at its
  rendered size.
- Keyboard: every interactive element reachable and visibly focused. Drawer and modals trap
  focus.
- Colour is never the only carrier of meaning — every "your move" badge has its text label.
- 200% zoom at 1280px.

**Done when:** the checklist passes on every route and the test suite is back to the Session 0
baseline or better.

---

## Backend work (parallel track)

Independent of the frontend sessions and can start immediately. Sessions 4–10 are smoother if
these land first.

| # | Work | Blocks |
|---|---|---|
| B1 | `whose_move` field on offers, deals, listings and auction serializers | Session 4 |
| B2 | Dashboard aggregate: waiting-on-you items across offers, deals and approvals in one ranked response | Session 4 |
| B3 | Join club valuation + fair value onto squad and market player responses | Sessions 8, 9 |
| B4 | Wage room and budget-after calculations exposed for the "fits wage room" check | Sessions 9, 10 |
| B5 | Commitment breakdown: what each committed amount is attached to and what releases it | Session 7 |
| B6 | Contract cliff aggregation by expiry window | Session 8 |
| B7 | Present-value effect per changed term in a negotiation | Session 6 |

B7 is the only genuinely new modelling. Everything else is joining or aggregating data the
system already holds.
