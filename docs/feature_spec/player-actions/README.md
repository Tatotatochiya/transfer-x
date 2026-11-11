---
title: "One blue button: top bar and player page actions"
last_updated: 2026-11-09
status: Implemented
owner: "TODO — assign a Product Owner"
---

# One blue button: top bar and player page actions

**Implemented 2026-11-10** on branch `player-actions`. Where the build differs from the text below, see [Review revisions](#review-revisions) and [Deviations](#deviations).

Written against `Tatotatochiya/transfer-x` `main` at `e91795b` (9 Nov 2026).

**Pages:**
- The top bar: `frontend/src/components/layout/MarketActions.tsx`, used twice in `AppShell.tsx`.
- The player page: `frontend/src/pages/market/PlayerMarketDetailPage.tsx`, route `/players/market/:id` (826 lines).

**The problem.** On another club's player page there are two blue buttons that both read like "buy him":
- **"Buy a player"** in the top bar ("Buy" on phones) is a link to Browse Players, so on a player page it takes you away from the player.
- **"Make Offer"** on the page is the real action.

Next to them, **"✦ Ask about this"** asks the AI and **"Ask about him"** sends a message to the player's club. On a phone the header's six buttons wrap onto three rows, and Make Offer is on the last one.

**Goal.**
- The top bar is navigation and never blue.
- The player page has **one** blue button: the action that fits the player's situation.
- Every label says what it does.
- On phones the page's actions are pinned to the bottom of the screen.

**Design reference.** `TransferX - Player Actions.dc.html` in this folder (needs `support.js` and the `player-actions-2026-11-09/` images beside it):
- **Now:** real captures.
- **A:** the top bar.
- **B:** the player page on phone (clickable) and laptop.
- **C:** the seven situations.
- A labels table.

Where this README and the mock disagree, **this README wins** (§13).

**Scope.** Frontend only. No API, permission or behaviour changes: every action, endpoint, confirmation and redirect stays as it is. If you find you need a backend change, stop and ask.

---

## 0. Before you start

1. Follow `session-lifecycle`. Read `docs/PRODUCT_SPEC.md`, `docs/SESSION_HANDOVER.md`, `docs/design-system/RESPONSIVE.md` and `TOKENS.md`, plus the deal room and offer room specs (`docs/feature_spec/deal-room-focus/`, `offer-room-focus/`). They introduced `TransferHeader` and `MoreMenu`, which this spec reuses.
2. Apply `product-principles`. The release clause, free-agent signing and pre-contract all create **binding deals**, and their confirmations stay exactly as they are.
3. Branch `player-actions`. Build in the order in §10.
4. Read `PlayerMarketDetailPage.tsx` lines 330–760 before changing anything. Every visibility condition in the action block (`isMyPlayer`, `canList`, `listingsKnown`, `listingId`, `isAgent`, `isPlayerAccount`, `isOffPlatform`, `isFreeAgentPlayer`, `inPreContractWindow`, `can("MARKET_WRITE")`, `active_deal`, `active_loan`) must keep **exactly** its current meaning. This change decides **where and how** each action shows, not **whether** it's allowed.
5. If the code differs from this spec, say so in your summary.

---

## 1. Success criteria

**Top bar**
- [ ] No blue button in the top bar, on any page, at any size.
- [ ] The top bar's buttons read "Find players" / "Sell a player" (laptop) and "Players" / "Sell" (phone, tablet).
- [ ] They go where they go today (`/players/market`, `/sales/new`), for the same people.

**Player page**
- [ ] The player page shows **at most one** `variant="primary"` button, at every size, in every situation in §4.
- [ ] Below 1024px, the situation's primary and secondary actions sit in a bottom bar pinned to the screen, 48px tall, above the iOS home indicator. The header shows no duplicate of them.
- [ ] Nothing that today depends on a hover `title` tooltip (disabled Make Offer, the deal-in-progress reason, the role reason) is left that way. The reason is visible text.
- [ ] "Ask about him" no longer exists. It's "Ask his club", or "Ask {parent club}" for a player on loan (§4).
- [ ] "✦ Ask about this" on the player page becomes "✦ Ask TransferX about him", in More.
- [ ] Every confirmation dialog (release clause, free agent, pre-contract, listing) is unchanged in title, message and button.
- [ ] Lint, typecheck and `vitest` pass. The new tests in §11 exist.

---

## 2. Decisions

- **D1. Top bar: outlined navigation.** In `MarketActions.tsx`, both links use the quiet style: `bg-transparent text-text-secondary hover:bg-surface-inset hover:text-text`, no ring on desktop, `ring-1 ring-input-border` on the compact (mobile) variant so they still read as tappable. Each gets a 16px icon (people for Find, tag for Sell), `aria-hidden`.
- **D2. Top bar labels:** "Buy a player" becomes **"Find players"**, compact "Buy" becomes **"Players"**. "Sell a player" and compact "Sell" stay. The accessible names are "Find players" and "Sell a player" at every size (set `aria-label` on the compact version).
- **D3. Player page main action** is chosen by the player's situation (§4). It is the page's only `variant="primary"` button.
- **D4. The player page uses the shared header.** Extend `TransferHeader` with:
  - an optional `sub` (used instead of `routeFrom` / `routeTo` when given)
  - an optional `actions` slot
  - making `amount` optional

  The deal and offer pages pass what they pass today, with no visual change. Drop the breadcrumb ("← Back · Market / name") for "← Back", as on deal and offer.
- **D5. Header actions, at 1024px and up,** in this order: **Shortlist** (secondary, icon and label) · the situation's **secondary action** · the **primary** · **More ⋯**. Compare, ✦ Ask TransferX, View club and the release clause go in More (§5).
- **D6. Below 1024px, a bottom action bar** (`PlayerActionBar`) holds the situation's secondary (left) and primary (right, wider). Shortlist becomes an icon button (44 × 44, `aria-label="Shortlist {name}"`) beside More in the header's back row. The header shows no other action buttons.
- **D7. Plain labels** (§6), in sentence case to match the rest of the app.
- **D8. No disabled buttons with tooltip reasons.** When an action is blocked, show the reason as a sentence (`PlayerActionNote`) and offer the useful next step instead.

### Open question

- **Q1. Phone top-bar wording.** The mock uses "Players". The alternatives are "Find", or dropping that button on phones (Browse Players is in the drawer). **Default: "Players".**

---

## 3. Layout

### Phone and tablet, below 1024px

```
┌──────────────────────────────┐ AppShell top bar: ☰ · [Players] [Sell] · 🔍 · 🔔 · avatar
│ ← Back             [⌑] [More ⋯]│ Shortlist icon + More
│ (JP) João Pedro              │ h1 22px
│      Forward · Chelsea · 24 · Brazil
│ (badges: FWD, Contracted, Listed, n active offers)
│ PlayerActionNote, if any      │ one sentence (§4)
│ facts strip, tabs, ledger …   │ unchanged
│                              │
├──────────────────────────────┤ PlayerActionBar, fixed
│ [ Ask his club ][ Make an offer ]│ 48px, safe-area padding
└──────────────────────────────┘
```

- **Bottom bar:** `fixed inset-x-0 bottom-0 z-30 lg:hidden border-t border-border bg-surface px-4 pt-2.5 pb-[max(14px,env(safe-area-inset-bottom))] shadow-[0_-4px_12px_rgba(16,24,40,0.06)]`.
  - The grid is `grid-cols-[1fr_1.3fr] gap-2` when there are two actions, `grid-cols-1` when there's one.
  - When the bar shows, the page gets bottom padding equal to its height, so the last content isn't hidden.
- **`CompareBar`** (fixed bottom) sits **above** the action bar on this page: offset it by the bar's height when both show.
- **No actions in the situation** (agent, player account, off-platform with Shortlist only in the header): no bar, no padding.

### Laptop, 1024px and up

```
← Back
(JP) João Pedro                          [⌑ Shortlist] [Ask his club] [Make an offer] [More ⋯]
     Forward · Chelsea · 24 · Brazil · 182 cm · Born …
     badges
PlayerActionNote, if any
facts strip, tabs …
```

---

## 4. Situations: what the page shows

Compute these once, in the page, from the **existing** flags, as `const situation = playerSituation({...})`. Use a pure function in `lib/playerSituation.ts`. **The first matching row wins.**

| # | When (existing flags) | Primary | Secondary | Note (`PlayerActionNote`) | Extra in More |
|---|---|---|---|---|---|
| 1 | `!isAuthenticated && !isOffPlatform` | "Sign in to make an offer" → `/login` | none | none | none |
| 2 | `isAgent \|\| isPlayerAccount` | none | none | none | View club |
| 3 | `isMyPlayer` with `canList`, listings loaded, not listed | "List for sale" (opens `ListPlayerModal`, as today) | none | none | Compare, ✦ Ask TransferX |
| 4 | `isMyPlayer` with `canList`, listed | "View listing" → `/sales/:listingId` | none | none | same |
| 5 | `isMyPlayer` otherwise (on loan to you, no `MARKET_WRITE`, listings loading) | none | none | loan: "He's on loan to you from {parent}. Only {parent} can sell him." No rights: none | same |
| 6 | `player.active_deal?.status === "IN_PROGRESS"` and the viewer's club is the deal's buyer or seller | "View the deal" → `/deals/:active_deal.id` | none | "Your deal with {other club} is at {stage label}. New offers are paused until it finishes or falls through." | Compare, ✦ Ask TransferX, View club |
| 7 | `active_deal IN_PROGRESS`, viewer not a party | none | none | "A transfer for him is in progress. New offers are paused until it finishes or falls through." | same |
| 8 | `isOffPlatform` | none | none | today's copy: "{club} is not on TransferX, so an offer could not be answered. Shortlist him to follow his form and contract." | same |
| 9 | not `can("MARKET_WRITE")` (signed-in club member) | none | none | "Your role can't send offers. Ask your club's owner or sporting director." | same |
| 10 | `isFreeAgentPlayer` | "Sign him" (today's `handleSignFreeAgent`, same confirm) | none | "Free agent. There's no fee: you agree his wage and contract." | same |
| 11 | `inPreContractWindow` | "Make an offer" → `/offers/new?player_id=…` | "Offer a pre-contract" (today's `handlePreContract`, same confirm) | "His contract ends {formatDate(contractEndDate)}. You can agree a free move for then, or buy him now." | Ask his club, release clause (if any), Compare, ✦ Ask TransferX, View club |
| 12 | otherwise (club on TransferX, you can trade) | "Make an offer" → `/offers/new?player_id=…` | "Ask his club" (opens `AskAboutPlayerModal`, as today) | none | release clause (if any), Compare, ✦ Ask TransferX, View club |

**Notes on the table:**
- **Row 6 is new behaviour in presentation only.** Today the page disables Make Offer and shows a `DealBanner` that already names both clubs and the stage to every viewer. Keep `DealBanner` as it is for non-parties (row 7), and for parties replace it with the row-6 note. The deal link appears **only** when `myClub.id` is the deal's `buyer_club.id` or `seller_club.id`: never link a non-party to a deal they can't open.
- **"Ask his club" on a loaned player:** label it "Ask {parent club name}" when `player.active_loan?.parent_club?.name` exists. The modal already addresses the parent club (`ownerName`). Keep the existing conditions for the enquiry: `isAuthenticated && !isAgent && can("MARKET_WRITE") && !isFreeAgentPlayer && !isOffPlatform`.
- **Release clause** (`player.active_contract?.release_clause != null`, `can("MARKET_WRITE")`, not agent, no deal in progress): **a More item** labelled "Pay the release clause ({formatCurrency(clause)})…". It runs today's `handleTriggerReleaseClause`, with the same danger confirm. In the menu it uses `danger: true` and `dividerBefore: true`. It is never the primary: it's rare, binding and expensive, and the confirm explains it.
- **The `DealBanner` "Recently transferred" (COMPLETED) variant** is unchanged and doesn't affect actions.
- **The competition chip ("n active offers")** for your own player is unchanged.

---

## 5. More menu (`MoreMenu`)

Items, in this order. Leave out what doesn't apply; if nothing is left, hide the trigger.

1. "Ask his club" (row 11 only, where it isn't the secondary). Opens the enquiry modal.
2. "Compare with others": toggles `useCompare` as today. When he's already in compare, the label reads "Remove from compare".
3. "✦ Ask TransferX about him": a link to `askAboutPath("player", player.id, player.name)`, the same as `AskAboutButton`. Shown when `isAuthenticated && !isAgent && !isPlayerAccount`, as today.
4. "View {club name}": `ClubLink`'s target (club or world team). Only when there's a club.
5. Divider, then "Pay the release clause ({amount})…" (§4), danger.

Shortlist is **not** in More: it stays a visible secondary button (laptop) or icon button (phone), using `AddToShortlistButton` with today's condition (`!isMyPlayer`).

---

## 6. Labels

| Today | After |
|---|---|
| Buy a player / Buy (top bar) | Find players / Players |
| Sell a player / Sell (top bar) | unchanged text; outlined style |
| Make Offer | Make an offer |
| Ask about him | Ask his club (or Ask {parent club} on loan) |
| ✦ Ask about this (player page) | ✦ Ask TransferX about him (in More) |
| Compare | Compare with others / Remove from compare (in More) |
| Sign Free Agent | Sign him |
| Offer Pre-Contract | Offer a pre-contract |
| Trigger release clause (£X) | Pay the release clause (£X)… (in More) |
| Sign in to make offer | Sign in to make an offer |
| List for sale / View listing | unchanged |
| Make Offer, disabled, role reason in a tooltip | no button; the row-9 sentence |

Keep the **confirmation dialogs' wording** unchanged, including "Trigger clause" on the release-clause confirm button. Only the entry points are renamed. Changing binding-action confirm copy needs a product decision.

`AskAboutButton` elsewhere (deal, offer, club pages) is out of scope. Leave it.

---

## 7. Components

**New**
- `lib/playerSituation.ts`: `playerSituation(input): { kind, primary?, secondary?, note?, more: MoreKey[] }`. A pure function, no React. `input` holds the flags in §4, plus `myClubId`, `activeDeal`, `contractEndDate`, the club and parent-club names, and `hasReleaseClause`.
- `components/players/PlayerActions.tsx`: renders the laptop header actions (D5) from the situation and wires each action to the page's existing handlers.
- `components/players/PlayerActionBar.tsx`: the fixed bottom bar (§3) below 1024px. It renders nothing when there are no primary or secondary actions.
- `components/players/PlayerActionNote.tsx`: `rounded-xl px-4 py-3 text-[15px] leading-normal`. Neutral tone `bg-surface-inset text-text-secondary`; info tone (row 6) `bg-accent-bg text-accent-active`. It sits under the header badges, above `RealWorldMoveBanner`.

**Changed**
- `components/layout/MarketActions.tsx`: D1, D2. Update `MarketActions.test.tsx`: the link names become "Find players" and "Sell a player" at both sizes (compact via `aria-label`). The visible compact text is "Players" / "Sell".
- `components/transfer/TransferHeader.tsx`: optional `sub`, `actions` and `amount` (D4). No change for the deal and offer pages; their tests must pass untouched.
- `pages/market/PlayerMarketDetailPage.tsx`:
  - The header becomes `TransferHeader`. Keep the badges row, the loan line and the meta items as `sub` content.
  - The old action block (lines ~622–752) is replaced by `PlayerActions` / `PlayerActionBar` / `PlayerActionNote`, plus the More items.
  - The handlers, mutations, modals (`ListPlayerModal`, `AskAboutPlayerModal`) and confirms stay in the page, unchanged.
  - The breadcrumb is removed.
- `components/players/CompareBar.tsx`: accepts a bottom offset (CSS variable `--action-bar-h`, default 0) so it sits above the action bar.

**Deleted**
- The page's inline action block and `DealBanner`'s use for parties (the component stays for non-parties and COMPLETED).

---

## 8. Accessibility

- One `h1` (the player).
- The bottom bar is a `<div role="region" aria-label="Actions for {name}">`. Its buttons are real `<button>`s or `<Link>`s, 48px.
- The More trigger uses `aria-haspopup="menu"` and `aria-expanded`, with keyboard behaviour from `MoreMenu`.
- `PlayerActionNote` is plain text in the reading order, not `aria-live`. It doesn't change while you're on the page.
- With no disabled buttons left (D8), every reason is visible.
- Top bar links keep visible focus rings; the quiet style must still show `focus-visible:outline-2 outline-accent`.
- Contrast: `text-text-secondary` on white passes 4.5:1. Don't use `text-text-muted` for the top-bar labels.

---

## 9. Permissions and behaviour (unchanged)

- Who sees each action is exactly as today (§4 uses the existing flags).
- Every action is unchanged: same endpoints, payloads, confirmations, redirects and invalidations. That covers the release clause, free-agent signing and pre-contract (each makes a binding deal, then goes to `/deals/:id`), the enquiry modal, listing and compare.
- **"View the deal" (row 6) only for the two clubs on the deal.** Non-parties keep today's banner text and get no link.
- The top bar shows for the same users as today (`MarketActions` guard unchanged).

---

## 10. Build order (one commit each)

1. **Top bar:** `MarketActions` style and labels, plus its test.
2. **Logic:** `lib/playerSituation.ts` with its table-driven test (§11).
3. **Shared header:** `TransferHeader` gains the optional `sub`, `actions` and `amount`. The deal and offer page tests still pass.
4. **Player page header:** `TransferHeader` with `PlayerActions`, `PlayerActionNote` and the More menu. Remove the breadcrumb and the old action block.
5. **Phone bar:** `PlayerActionBar` below 1024px, the page bottom padding, and the `CompareBar` offset.
6. **Finish:** page tests, manual checks, docs (§12).

---

## 11. Tests

**`playerSituation.test.ts`.** One case per row in §4, plus these extras:
- Pre-contract with a release clause: the clause in More, "Ask his club" in More.
- A loaned-in player: row 5 with the loan note.
- A deal in progress where the viewer is the seller: row 6.
- A deal in progress where the viewer is neither club: row 7, no deal link.
- A player on loan elsewhere: the secondary is "Ask {parent club}".
- Signed out, off-platform: no primary.

**`MarketActions.test.tsx` (updated):**
- Links named "Find players" (`/players/market`) and "Sell a player" (`/sales/new`) at both sizes.
- Visible compact text "Players" / "Sell".
- Neither link uses the primary (`bg-accent`) class.
- Hidden for the same users as today.

**`PlayerMarketDetailPage.test.tsx`** (new; mock `matchMedia` per case):
- Another club's player, from 1024px: the header shows Shortlist, "Ask his club", "Make an offer" and More, and exactly one primary button. "Make an offer" links to `/offers/new?player_id=…`. More holds Compare, "✦ Ask TransferX about him" and "View Chelsea".
- Below 1024px: the bottom bar shows "Ask his club" and "Make an offer". The header has no Make an offer, and the Shortlist icon button is labelled "Shortlist João Pedro".
- Release clause: not a visible button. In More, "Pay the release clause (£X)…" opens the **existing** confirm ("Trigger release clause?" / "Trigger clause"), and confirming posts to `/players/:id/trigger-release-clause`.
- Free agent: the primary is "Sign him", with the existing confirm, then posting to `/players/:id/sign-free-agent`.
- Pre-contract: the primary is "Make an offer", the secondary is "Offer a pre-contract" with the existing confirm. The note shows the end date.
- Deal in progress, viewer is the buyer: "View the deal" links to `/deals/:id`, and the note names the other club and the stage. Viewer not a party: no link, today's banner text.
- No `MARKET_WRITE`: no primary, the role sentence shows, and no disabled button.
- Own player, not listed: "List for sale" opens the modal. Listed: "View listing".
- Off-platform: no primary, today's sentence, Shortlist still shown.
- Agent and player accounts: no bar, no primary.
- Signed out: "Sign in to make an offer" goes to `/login`.

**Manual checks:**
- 375 × 667 and 390 × 844: the bar clears the home indicator, the last content isn't hidden, and CompareBar (with a player added) sits above the bar.
- 768 × 1024: the bar shows; no header actions.
- 1024 and 1280: header actions on one line with the name truncating, not wrapping. The More menu stays on screen at the right edge.
- Top bar on every page at all three sizes: no blue button. The page's own primary is the only blue on screen.
- Dark theme; 200% zoom.

---

## 12. Docs (`documentation-standards`)

- **`docs/design-system/SCREENS.md`, "Player profile":** the header, the situations table (§4) and the bottom bar.
- **`docs/design-system/RESPONSIVE.md`:**
  - "Sticky elements": the player page's bottom action bar below 1024px, and CompareBar stacking above it.
  - A rule under "Buttons": **one primary button per screen; the top bar never has one.**
- **`docs/CHANGELOG.md`:** the top-bar labels and style, the player page's actions and labels, and the release clause moving to More.
- **`docs/feature_spec/README.md`:** add this spec.
- **The 29 Oct product decision** ("Buy and Sell front and centre"): note that they stay on every page, restyled as navigation.

---

## 13. Where the mock differs (this README wins)

- **The mock's phone facts strip and season card are placeholders.** Keep today's `FactsStrip`, tabs and ledger, unchanged.
- **The mock shows "View Chelsea" in More.** Use the player's actual club (or world team) name, and leave it out when there isn't one.
- **Row 6 copy.** The mock reads "Your deal with Chelsea is at Paperwork". Use `dealStageLabel(active_deal.stage)` and the other club's name, and only for the deal's own clubs.
- **The mock's "Hamburger SV" off-platform card is sample text.** Use today's sentence with the real club name.
- **The release clause confirm keeps today's wording** ("Trigger release clause?" / "Trigger clause"). The mock only shows the More item.
- **The laptop mock omits the badges row** (FWD, Contracted, Listed). Keep it under the name.

---

## Review revisions

- **R1. The deal rows (6, 7) are checked before the own-player rows (3–5).** In the table's order, a club's own player with a deal in progress would match row 3 and offer an enabled "List for sale"; today that button is disabled during a deal. The selling club now gets row 6 ("View the deal" and the sentence) instead.
- **R2. Row 7 shows today's banner only, not also the row-7 sentence.** §4's notes keep `DealBanner` for non-parties, and it already says the same thing; both together repeated it.
- **R3. The row-6 stage is lower case** ("is at paperwork"), as `lib/badges` already writes a stage mid-sentence.
- **R4. The release clause is offered only in rows 11 and 12.** Today's button also showed for a player at a club off TransferX; there it could never work (no club on the platform to trigger it against), and §4 lists it only in those rows.
- **R5. `AddToShortlistButton` gained a `size="icon"` (44 × 44) and a `label`** for the phone's back-row button, and its default size became `bg-surface` with a 44px floor below 1024px, to sit with the header's other buttons. Its other uses (compact rows and cards) are unchanged.
- **R6. `Button` exports `buttonClasses`,** so an action that is a link looks exactly like a button. No visual change elsewhere.

- **R7 (follow-up, 2026-11-11). With your club's offer open, rows 11 and 12 show "View your offer"** (→ `/offers/:id`) instead of "Make an offer", which only led to the new-offer page's "you already have an offer" notice; the server refuses a second. The sentence says where it stands: "Your {amount} offer is with {club}." or, on your move, "{club} countered at {amount}. It's your move." It reads `GET /offers/active-for-player/:id`, the new-offer page's own duplicate check, only where an offer could be made. "Offer a pre-contract" stays beside it: the server allows it, and starting one closes every open offer, ours included. An offer captured for internal approval isn't an offer yet, so it still reads "Make an offer".
- **R8 (follow-up). Below 1024px the page leaves room for the compare tray (96px) as well as the bar**, and the testers' Start demo button sits above the bar (it covered the blue button).

## Deviations

- **Code that differs from the spec:**
  - The pre-contract button showed for a player at a club off TransferX (it wasn't excluded), but the server always refuses it ("no current club"). Row 8 now wins, so that dead button is gone.
  - Compare showed for everyone, signed out and agents included. §4 gives signed-out viewers no More items and agents only "View club", so they lose Compare on this page.
- **An agent's page keeps one blue button of its own,** "Represent this player" in the side panel; the situation gives agents no primary, so the page still has at most one.
- **Checked on screen** (local demo data, Manchester City): another club's player at 390 (bar, end of page clear of it, CompareBar above the bar), 768, 1024 and 1280 with More open; own player (List for sale); a free agent (Sign him and the sentence); a player at a club off TransferX; dark theme at 1280. No horizontal scroll.
- **Not checked:** a real iPhone's home indicator, 200% zoom, a release clause on screen (no local player has one; covered by tests), a live deal for each side (tests).

