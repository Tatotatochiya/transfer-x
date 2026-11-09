---
title: "Offer page, answer first"
last_updated: 2026-11-09
status: Implemented 2026-11-09
owner: "TODO — assign a Product Owner"
---

# Offer page, answer first

Written against `Tatotatochiya/transfer-x` `main` at `f8acbf7` (8 Nov 2026). Route: `/offers/:id`. Page: `frontend/src/pages/offers/OfferDetailPage.tsx` (809 lines today).

**Goal.** On every device, before any scrolling, the offer page answers four questions: **who and how much, what did they just change, what can I do about it, and how far apart are we.** Countering never needs a scroll: on phones and tablets it opens a sheet, and on a laptop it opens in place.

**Design reference.** `TransferX - Offer Room Focus.dc.html` in this folder (needs `support.js` beside it):
- **Now**: where the scroll goes today.
- **A**: phone deciding, phone counter sheet, iPad, laptop.
- **B**: the status card in eight states.
- **C**: countering on a laptop.
- Then where everything moved, and notes.

The mock uses sample data. Where this README and the mock disagree, **this README wins** (§15).

**Revised 2026-11-09 after review, then built.** The review fixes are in "Review revisions" below; what the build did differently is in "Deviations" at the end.

**Sister spec.** `docs/feature_spec/deal-room-focus/README.md` (the deal room). Both pages use the same header, status card, progress line, tabs, rail and More menu. **Build the deal room first.** This spec reuses its shared pieces (§5.1). If they don't exist yet, build them as that spec describes, then come back.

**Scope.** Frontend only. It uses endpoints that already exist, including `POST /offers/:id/improve` (§3, D6) and `GET /lite/offers/:id` (§5.3). No API, model, migration or permission changes. If you find you need one, stop and ask.

---

## Review revisions (2026-11-09)

These correct or settle points in the sections below; where they disagree, these win.

- **R1. Capitalise the other club at the start of a sentence.** The Lite card names a masked buyer in lower case ("an undisclosed Premier League club"), so headlines run it through `cap()`: "An undisclosed Premier League club bid …".
- **R2. Which event each row reads.** Row 7 (your move) names the **other side's** latest move, and row 8 (waiting) **your** latest. The backend lets a buyer raise on their own turn without handing the turn back, so "the last event" can be the viewer's own raise. Legacy offers with no events read as SENT.
- **R3. "A fee-only counter sends the same body" is true of the moved logic, not `{ fee_amount }` in general.** Today's counter always sends `wage_weekly` and `contract_years` when the offer has them. The page test uses an offer with neither, so the body is `{ fee_amount }`.
- **R4. `diffDraft` takes the draft's full terms**, the same object the live rule check reads, not the request body: the body leaves out unchanged structure but always carries fee, wage and years.
- **R5. The sheet must tolerate a confirm on top of it.** "Discard your counter?" opens a Modal over the Sheet. The Sheet ignores Escape and Tab while focus is outside it, so the two focus traps don't fight.
- **R6. Raise is offered only while waiting (row 8)**, as the table says. On the buyer's own turn they counter instead.
- **R7. The payment, add-ons and sell-on disclosure renders `DealStructureFields` without its own `<details>`** (a new `bare` prop); otherwise it is two disclosures deep.
- **R8. Backend: a raise that sends only a fee keeps the wage as it is.** `improve_own_offer` fell back to `offer.wage_weekly or 0`, so a raise on an offer with no wage set it to £0/wk. D6 makes this path reachable from the page, so it is fixed (one line, with a test) despite "no backend changes".
- **R9. `useLiteOfferCard` gains an `enabled` argument**, so the page can ask only for a party's offers.
- **R10. "Where it stands" needs a second round.** With one round there is nothing to compare and the card read "Show all 1 round"; it is hidden until a counter or raise.

---

## 0. Before you start

1. Follow the repo's `session-lifecycle` skill. Read `docs/PRODUCT_SPEC.md`, `docs/SESSION_HANDOVER.md`, `docs/design-system/RESPONSIVE.md`, `docs/design-system/TOKENS.md`, the deal room spec, and the "Offer detail" section of `docs/design-system/SCREENS.md`.
2. Apply `engineering-standards` and `product-principles`. This page accepts multi-million-pound offers, reserves budget and handles a confidential valuation.
3. Work on a branch `offer-room-focus`, in the order in §12. The page must keep working after every step.
4. Read all of `OfferDetailPage.tsx` first. Keep every mutation, endpoint, payload, invalidation, toast and confirmation as it is, unless §3 says otherwise. **The `CounterForm` submit logic (what it sends, and its diffing against the current offer) is a move, not a rewrite.**
5. If the code differs from this spec, say so in your summary rather than quietly picking one.

---

## 1. Why

Estimated from the code for a seller answering a round-3 counter on a permanent offer (2 instalments, a sell-on, about five messages). Phone: 390px, about 700px of page visible. Laptop: 1280 × 790.

| | Phone today | Laptop today |
|---|---|---|
| Accept / Counter / Reject | ~1,110px (screen 2) | ~1,090px, under the fold |
| Tapping Counter opens the form at | ~2,400px (screen 4), **under the conversation** | ~2,300px |
| "Submit counter" | ~2,750px | ~2,650px |
| Whose move it is | grey 12px text inside the Actions card | same |
| Offer deadline (`expires_at`) | not shown anywhere | not shown |
| Your valuation and the gap | not shown | not shown |
| Order book | its own tab | rail; **on tablet, under everything (~3,000px)** |

**Causes:**
- Five cards sit before the actions: Offer, Parties, What changed, Terms, Actions.
- The counter form is rendered inside the Conversation card, after every message.
- Reject and Withdraw are full-width red buttons with the same weight as Accept.
- The Lite card's endpoint already returns the valuation, a suggested counter and the deadline, but this page never asks for them.

---

## 2. Success criteria

- [ ] **Phone, 390 × 700 of page:** the player, the fee, the status card (headline, what changed, Accept and Counter) and the deadline are visible without scrolling, for the main states in §13.
- [ ] **Phone and tablet:** tapping Counter shows the counter form at once, with **Send counter always on screen** (pinned to the sheet's footer).
- [ ] **Laptop, 1280 × 790 (including the 56px desktop header):** header, status card, "Where it stands", the top of the terms **and** the conversation rail are visible without scrolling. Counter opens in place, with Send visible without scrolling.
- [ ] A counter that changes only the fee sends **exactly the same request body** as today.
- [ ] Every action available today is available to the same people, with the same confirmations. The only new action is Raise your offer (D6), and it has a confirmation.
- [ ] The selling club's valuation is **never** visible to the buyer, and an anonymous buyer stays masked everywhere: header, status card, sheet, More menu, page title (§9).
- [ ] No horizontal scroll at 375px. No text below 13px or lighter than `text-text-muted`. Tap targets at least 44px below 1024px.
- [ ] Lint, typecheck and `vitest` pass. The new tests in §13 exist and pass.

---

## 3. Decisions

### Decided

- **D1. The deal room's four blocks:** header, status card, progress ("Where it stands"), then sections (tabs below 1024px; main column plus rail from 1024px).
- **D2. One status card replaces** the Offer card's status badge, the Parties card's role, the "Waiting for … to respond" line, the What changed card and the Actions card. Its content comes from a pure function, `getOfferStatus` (§5.4).
- **D3. Countering opens a `Sheet` below 1024px** (full height on phones, a 560px centred dialog on tablets). **From 1024px it opens inside the status card.** Never under the conversation.
- **D4. Fee first.** The counter form leads with the fee field and up to three one-tap amounts (suggested, your valuation, your last figure). The other fields keep the current terms, and payment, add-ons and sell-on sit behind a disclosure.
- **D5. Tabs below 1024px**, on tablets too: Terms · Messages · Other bids (the seller's label; the buyer sees "Your ranking"). From 1024px, main column tabs Terms · Offer history, and a rail with Messages · Other bids / Your ranking. This matches deal room D3; RESPONSIVE.md's "rail below the content" rule no longer applies to this page.
- **D6. Wire up "Raise your offer"** for a buyer who is waiting. `POST /offers/:id/improve` exists ("the buyer raises their own pending offer without waiting for a reply") but no screen calls it. It gets a confirmation, because it reserves more budget (§5.7).
- **D7. Accept is the blue button, Counter sits beside it at equal size, and Reject becomes a text button** under them. Withdraw moves to More. Every confirmation is unchanged.
- **D8. The AI is next to the action, not in the way.**
  - "✦ Suggest a counter" sits inside the counter form and fills it the same way today's "Use these terms" does (`prefill` with `ai_assisted: true`).
  - The full Offer advisor and "Where this negotiation stands" move into one "✦ Advice on this offer" disclosure in the Terms tab, unchanged inside.
  - "Ask TransferX about this offer" moves to More.
- **D9. Keep the phone redirect.** A phone opened from a notification still goes to the Lite offer card (`?from=push`, below 640px). Revisit after release.

### Open questions (build the default unless told otherwise)

- **Q1. Showing "waiting for approval" after Accept returns 202.** The offer doesn't say an acceptance is pending approval, so the page can't show it. **Default: unchanged** (the info toast only). Write a follow-up ticket.
- **Q2. Asking price in the gap line.** The mock's examples say "under your £2.4M asking price", but the offer doesn't carry the listing's asking price. **Default: use the valuation only** (`your_valuation` from the Lite card, seller only). No extra fetch.

---

## 4. Layout

### Phone, below 640px

```
┌──────────────────────────────┐ AppShell top bar (unchanged)
│ ← Back                More ⋯ │
│ (MW) Marcus Webb             │ h1
│      Forward · Meridian FC → Ashfield United
│ £4.2M · Permanent · 2 instalments
├──────────────────────────────┤
│ YOUR MOVE · reply by 18:00 today
│ Ashfield United countered at £4.2M
│ That's £600K under your £4.8M valuation.
│ Fee        £5.0M → £4.2M     │  what changed, up to 4 rows
│ Payment    On completion → 2 instalments
│ Sell-on    None → 10%        │
│ [ Accept £4.2M ][  Counter  ]│ 48px, 2 columns
│        Reject this offer     │ text button, 44px
├──────────────────────────────┤
│ Where it stands     Round 3  │
│ ○────●═══════●──────○        │ their first · their offer · your valuation · your ask
│ Show all 3 rounds ⌄          │
├──────────────────────────────┤
│ [Terms][Messages][Other bids]│
│ …                            │
└──────────────────────────────┘
```

### Counter sheet, below 1024px

```
┌──────────────────────────────┐
│ Counter Ashfield United    × │ header, fixed
│ Their offer: £4.2M · 2 instalments · 10% sell-on
├──────────────────────────────┤ scrolls
│ Fee you'll accept            │
│ [ £4,600,000              ]  │ 56px, 22px/700
│ [ £4.6M      Suggested    ]  │ one-tap amounts, 44px each
│ [ £4.8M      Your valuation ]│
│ [ £5.0M      Your last ask ] │
│ Wage a week   Contract years │
│ Payment, add-ons and sell-on ›  2 instalments · 10% sell-on
│ rule checks (TermsWarnings)  │
│ [ ✦ Suggest a counter ]      │
├──────────────────────────────┤ fixed footer
│ £4.6M: £400K more than their offer, £200K under your valuation
│ [         Send counter         ]
└──────────────────────────────┘
```

### Tablet, 640–1023px

The same order as the phone, with these differences:
- **Header:** the fee sits on the right.
- **Status card:** the text and changes are on the left, and the buttons stack in a 220px column on the right.
- **Track:** full width.
- **Terms:** two columns.
- **Counter:** opens the same sheet, centred, 560px wide, up to 90vh tall.

### Laptop, 1024px and wider

```
Sidebar │ ← Back
        │ (MW) Marcus Webb                                    £4.2M   [More ⋯]
        │      Forward · Meridian FC → Ashfield United · offer made 3 Nov
        │ ┌ YOUR MOVE · reply by 18:00 today ───────────────────────────────────────┐
        │ │ Ashfield United countered at £4.2M │ Fee £5.0M → £4.2M   │ [Accept £4.2M] │
        │ │ That's £600K under your valuation. │ Payment … → …       │ [Counter]      │
        │ │                                    │ Sell-on None → 10%  │  Reject …      │
        │ └──────────────────────────────────────────────────────────────────────────┘
        │ ┌ Where it stands · Round 3 · all rounds │ ○──●══●──○ track                ┐
        │ ┌ Terms | Offer history ───────────────┐ ┌ Messages | Other bids · 3 ┐ 340px
        │ │ Their offer (2 columns)              │ │ conversation …            │ sticky
```

When Counter is pressed on a laptop, the status card becomes the counter form (mock section C):
- **Left:** the fields. Fee, wage and years sit on one row, the one-tap amounts beneath them, then the structure disclosure.
- **Right:** a 330px "What {Other} will see" panel.
- **Footer:** Send counter, Cancel, and on the right "✦ Suggest a counter".

---

## 5. Components

### 5.1 Shared with the deal room (extract, don't copy)

When you start this work, move these out of `components/deals/` into **`components/transfer/`**. The deal room keeps using them, and its visuals must not change:

| Shared piece | From the deal room spec | Generalise to |
|---|---|---|
| `TransferHeader` | `DealHeader` §5.1 | props: `player`, `routeFrom`, `routeTo` (nodes, so a masked buyer can be text), `facts`, `badges`, `lgSubExtra`, `moreMenu` |
| `StatusCardShell` | `DealStatusCard` §5.3 (container, tone ring, overline + meta, `h2` headline, body, button column layout, focus-after-success) | `tone`, `overline`, `meta`, `headline`, `body`, `children` (middle column), `actions` (right column) |
| `SegmentedControl` | §5.5 | already generic |
| `useMediaQuery` | §5.5 | already generic |
| `Menu` / `MoreMenu` | §5.7 | `items: { label, onSelect \| to, danger?, dividerBefore? }[]` |

### 5.2 `OfferDetailPage.tsx` after the change

Its jobs: queries, side and turn flags (computed **exactly as today**: `isBuyer`, `isSeller`, `isParty`, `isActive`, `isMyTurn`, `canMarketWrite`, `canAct`, `canWithdraw`), the redirects (accepted-to-deal for parties, phone push to Lite), the status derivation and layout. Target: under 300 lines. Move the rest into the files in §10.

### 5.3 Data

- **Offer:** `GET /offers/:id`, unchanged.
- **Lite card:** `useLiteOfferCard(id)` from `hooks/useLite.ts`, **enabled only when `isParty`**, because the endpoint 404s for anyone else. It provides `your_valuation` (seller only, confidential), `counter_suggestion` (only on your move, permanent only), `expires_at`, `disabled_reason` and `other_club` (already masked).
  - **The page must work if this query fails or is loading.** Without it, leave out the gap sentence and the Suggested / Your valuation amounts, and take `expires_at` from the offer.
- **Order books:** `SellerOrderBook` / `BuyerOrderBook`, unchanged props.
- **Invalidations:** every offer mutation (accept, reject, withdraw, counter, improve) also invalidates `["lite", "offer-card", id]`.

### 5.4 `offerStatus.ts`: pure derivation

```ts
export type OfferTone = "you" | "wait" | "info" | "done" | "closed";

export type OfferAction =
  | { kind: "accept"; label: string; highlight?: boolean }   // highlight = ?from=push&action=accept
  | { kind: "counter"; label: "Counter" }
  | { kind: "reject"; label: "Reject this offer" }
  | { kind: "raise"; label: "Raise your offer" }
  | { kind: "open-messages"; label: string }
  | { kind: "view-deal"; label: "View the deal" };

export interface OfferStatusView {
  tone: OfferTone;
  overline: string;
  meta?: string;
  headline: string;
  body?: string;
  changes: TermChange[];        // from lib/offerChanges.lastChange, only when the OTHER side made the last move
  primary?: OfferAction;
  secondary?: OfferAction;
  tertiary?: OfferAction;       // reject, rendered as a danger text button
}

export interface OfferViewer {
  side: "buyer" | "seller" | null;
  isMyTurn: boolean;            // exactly as the page computes it today
  canWrite: boolean;            // can("MARKET_WRITE")
  card?: LiteOfferCard;         // may be undefined
  pushAction: string | null;
  myClubId?: string;
  now?: Date;
}

export function getOfferStatus(offer: Offer, viewer: OfferViewer): OfferStatusView;
```

**Names used in the copy:**
- **P:** `offer.player?.name`, else "the player".
- **Other:** for the buyer, `offer.to_club?.name ?? "the selling club"`. For the seller, `card?.other_club ?? buyerLabel(offer, "the buying club")`, which is masked when anonymous.
- **Amount:** `offerHeadline(offer)`, which already says "£450K loan fee" for loans.
- **Fee:** `formatCurrency(offer.fee_amount)` (permanent only).

**Deadline meta (`replyBy`):** from `card?.expires_at ?? offer.expires_at`.
- Today: "reply by HH:mm today".
- Tomorrow: "reply by HH:mm tomorrow".
- Within 6 days: "reply by {Weekday d Mon}".
- Otherwise: "reply by {formatDate}".
- When it is under 24 hours away, colour the whole overline `text-danger-text`.

The first matching row wins:

| # | When | Tone | Overline · meta | Headline | Body | Actions |
|---|---|---|---|---|---|---|
| 1 | `ACCEPTED` (only non-parties get here; parties are redirected) | done | "Accepted" · formatDate(last_action_at) | "This offer became a deal" | none | sec: view-deal, when `offer.deal` |
| 2 | `REJECTED` | closed | "Rejected" · formatDate(last_action_at) | last actor is me: "You rejected {Other}'s {Amount} offer". Other party: "{Other} rejected your {Amount} offer". Non-party: "This offer was rejected" | "The terms and conversation stay here as the record." | none |
| 3 | `WITHDRAWN` | closed | "Withdrawn" · date | buyer: "You withdrew your {Amount} offer"; seller: "{Other} withdrew their {Amount} offer"; non-party: "This offer was withdrawn" | same as row 2 | none |
| 4 | `EXPIRED` | closed | "Expired" · formatDate(expires_at) | "This offer expired without an answer" | same | none |
| 5 | open, not a party | info | `offerStatusLabel(status)` | "{buyerLabel} offered {Amount} for {P}" | none | none |
| 6 | open, party, `isMyTurn`, **not** `canWrite` | info | "Your club's move" | as row 7 | `card?.disabled_reason ?? "Your role can see offers but can't answer them."` | none |
| 7 | open, party, `isMyTurn`, `canWrite` | you | "Your move" · replyBy | the last event (from `offer.events`): SENT "{Other} bid {Amount} for {P}"; COUNTERED "{Other} countered at {Amount}"; IMPROVED "{Other} raised their offer to {Amount}". A **loan** uses "{Other} offered to take {P} on loan" / "{Other} countered the loan terms" / "{Other} improved the loan terms" | see below | primary accept; secondary counter; tertiary reject |
| 8 | open, party, not my turn | wait | "Waiting on {Other}" · "{n} days" when `daysSince(last_action_at) >= 1`, else "since HH:mm" | my last event: SENT "{Other} are considering your {Amount} offer"; COUNTERED "{Other} are considering your {Amount} counter"; IMPROVED "{Other} are considering your raised {Amount} offer" | expiry, if any: "It expires {replyBy without 'reply by'}." Buyer with `canWrite` adds " You can raise it now or wait for their answer." | buyer with `canWrite`: secondary raise. Seller: secondary open-messages "Message {Other}" |

**Body for row 7**, built in this order, leaving out empty parts:
1. **The gap (permanent, seller, `card.your_valuation` present):**
   - fee < valuation: "That's {formatCurrency(val − fee)} under your {formatCurrency(val)} valuation."
   - fee ≥ valuation: "That's at or above your {formatCurrency(val)} valuation."
   - Never for the buyer (§9).
2. **Loan with an obligation:** "If you accept, he transfers permanently for {option_to_buy} when the loan ends{, conditional on: …}." Loan with an option only: "{Other} may buy him for {option_to_buy} during the loan." This is the same wording as `acceptMessage()`.

**Accept label:** permanent "Accept {Fee}"; loan "Accept the loan". Set `highlight` when `pushAction === "accept"`, as today.

**`changes`:** `lastChange(offer)` when the change exists and `actorClubId !== myClubId`. Show up to 4; if there are more, add a fifth line, a link button "and {n} more changes" that opens the Terms tab.

### 5.5 `OfferStatusCard.tsx`

Built on `StatusCardShell`.
- **Changes list:** rows `flex justify-between gap-2.5 border-t border-rule py-2 text-sm`. The label is `text-text-secondary`. The value is `<s className="text-text-muted">{was}</s> <span aria-hidden>→</span> <span className="sr-only">changed to</span> <strong className="text-text">{now}</strong>`.
  - Below `lg` it sits under the body.
  - At `lg` and up it is the shell's middle column, `w-[320px]`, without top rules.
- **Buttons:**
  - Below `sm`: `grid grid-cols-2 gap-2` holding Accept (primary) and Counter (secondary), both `min-h-12`. The tertiary goes under them as `min-h-11 w-full text-[15px] font-semibold text-danger-text-alt`.
  - `sm` to `lg`: a 220px column with Accept, Counter, then Reject.
  - At `lg` and up: a 200px column, buttons `min-h-11`, Reject `min-h-8 text-sm`.
- **Highlight:** keep `ring-2 ring-accent ring-offset-2` on Accept when highlighted, plus today's line above the buttons: "From your notification: accept this offer?".
- **Action wiring:**
  - **accept:** today's confirm. The title is "Accept loan" / "Accept offer", the message is `acceptMessage(offer)` and the button is "Accept". Then `acceptMutation`, with today's 202 approval toast and the navigation to the deal.
  - **reject:** today's danger confirm ("Reject this offer?").
  - **counter:** opens the counter (§5.6).
  - **raise:** opens Raise (§5.7).
  - **open-messages:** `tab=messages` (as the deal room does).
  - **view-deal:** `navigate(/deals/:id)`.
- **Errors:** show any mutation error under the buttons (`text-sm text-danger-text`), as today's `mutError`.
- **Focus:** after a success, focus the headline.

### 5.6 Counter: `CounterForm` restyled, with a new container

**Logic.** Keep everything inside `CounterForm`: its state, `handleSubmit` and its body diffing, `structureError`, the live `useOfferCheck` and `TermsWarnings`, `prefill` with `ai_assisted`, and `startFee`. Move it to `components/offers/CounterForm.tsx` and change only its layout and the props below:

```ts
{
  offer; prefill?; startFee?;
  card?: LiteOfferCard;         // for the one-tap amounts and the footer comparison
  myLastFee?: number | null;    // from the rounds (§5.8): my side's latest fee
  layout: "sheet" | "inline";
  onDone: () => void;           // success or cancel
  onSuggest?: () => void;       // "✦ Suggest a counter"; omit when AI is unavailable
  formId: string;               // so a footer button outside the <form> can submit it
}
```

**Fields, permanent offer:**
1. **Fee.** The label reads "Fee you'll accept" for the seller and "Fee you'll pay" for the buyer, `text-[15px] font-semibold`. The input is `CurrencyInput`, `min-h-14 text-[22px] font-bold ring-2 ring-accent` (`lg:min-h-12 lg:text-lg`).
2. **One-tap amounts.** Leave out nulls and drop duplicate amounts, keeping the first:
   - `card.counter_suggestion`, labelled "Suggested"
   - `card.your_valuation` (seller), labelled "Your valuation"
   - `myLastFee`, labelled "Your last ask" for the seller or "Your last offer" for the buyer

   Each is a `<button type="button">` that sets the fee and shows `aria-pressed` when it equals the fee.
   - Sheet: full-width rows, `min-h-11`, amount on the left in bold, label on the right.
   - Inline: pills, `h-9 rounded-full`.
3. **Wage a week** and **Contract years** (`grid grid-cols-2 gap-3`; inline: a third column after the fee, `grid-cols-[2fr_1fr_1fr]`). Inputs are `min-h-12` below `lg`. Labels are visible, 15px (`lg:` 14px), with `htmlFor`.
4. **Payment, add-ons and sell-on.** A `<button aria-expanded>` row, `min-h-16` (inline `min-h-[52px]`). The sub-line summarises the current structure ("2 instalments · 10% sell-on · no add-ons"). Expanded, it renders `DealStructureFields` unchanged.

**Fields, loan offer.** The same fields as today, in this order: Loan fee (with the large style), "Borrowing club pays (% of wage)", Loan starts / Loan ends (2 columns), Purchase price, the obligation checkbox and conditions, Early recall. Checkboxes get `min-h-11` rows below `lg`. No one-tap amounts (there is no suggestion for loans).

**Under the fields:**
- `TermsWarnings` (unchanged).
- The prefill note (unchanged).
- The form error (unchanged copy).

**Suggest a counter.** Below the fields in the sheet, or in the footer's right side when inline: `<button>` "✦ Suggest a counter". It uses the page's existing advisor hook (`useOfferAdvice(offer.id, offer.last_action_at, true)` once clicked).
- When `suggested_terms` arrives, the page calls `setPrefill(terms)`, which re-keys the form exactly as `onUseTerms` does today.
- While it loads, the button shows a spinner and "Thinking…".
- If the advice has no `suggested_terms`, show its `summary` under the button at 14px muted.
- Render it only when `useAIStatus().data?.available`.

**Footer comparison.** Permanent offers only, recomputed as the fee changes: "{newFee}: {formatCurrency(|newFee − theirFee|)} more/less than their offer". Seller with a valuation adds ", {formatCurrency(|val − newFee|)} under/over your valuation". Write "the same as their offer" when they're equal.

**Containers:**
- **New primitive `components/ui/Sheet.tsx`:**
  - Props: `open`, `onClose`, `title`, `subtitle?`, `footer`, `children`.
  - `role="dialog"`, `aria-modal`, `aria-labelledby`, focus trap, body scroll lock, Escape and the × button (`aria-label="Close without sending"`) both call `onClose`.
  - Below 640px: `fixed inset-0`, full height. The header is fixed, the body `overflow-y-auto`, and the footer fixed with `shadow-[0_-4px_12px_rgba(16,24,40,0.06)]` and `pb-[max(16px,env(safe-area-inset-bottom))]`.
  - 640–1023px: a centred dialog, `w-[560px] max-h-[90vh]`, `rounded-2xl`, over the backdrop `bg-ink/40`.
  - On open, focus goes to the fee input; on close, back to the Counter button.
- **Dirty check:** if any field differs from the opening values, `onClose` asks with `useConfirm` ("Discard your counter?", "Discard", danger) before closing.
- **Sheet usage:** title "Counter {Other}", subtitle "Their offer: {Amount} · {payment summary} · {sell-on}", footer the comparison line plus `<Button type="submit" form={formId} variant="primary" size="lg" className="w-full">Send counter</Button>`.
- **Inline (≥1024px):** the status card's content is replaced, with the card ring changing to `ring-2 ring-accent`.
  - Header: "Counter {Other}" at 20px/700, with replyBy at 14px muted on the right.
  - Body: `flex gap-8`. The form takes `flex-1`, and a `w-[330px] rounded-xl bg-surface-inset p-4` panel on the right is "What {Other} will see".
  - The panel lists the live diff of the draft against the current offer, as was → now rows, using a new `diffDraft(offer, draftBody)` in `lib/offerChanges.ts` that **reuses the same PERMANENT / LOAN label and format tables**. Under the rows: "Everything else stays as they offered it." With no changes yet: "Change a term to see it here."
  - Footer (`border-t border-rule pt-3.5`): Send counter (primary), Cancel (secondary), then "✦ Suggest a counter" on the right.
- **Opening the counter:**
  - The status card's Counter button.
  - `?action=counter` on load (today's behaviour; ≥640px, since phones with `from=push` are redirected).
  - `?from=push&action=counter&amount=…` sets `startFee`, as today.
  - The advisor's "Use these terms" in the Terms tab opens it with `prefill`.
- **On success:** close, invalidate (today's keys plus the Lite card), and focus the status card headline. The new card will read "Waiting on {Other}".

### 5.7 Raise your offer (D6)

`RaiseOfferForm` uses the same containers as the counter (sheet below 1024px, inline at 1024px and up). Title: "Raise your offer to {Other}".
- **Permanent:** "New fee" (`CurrencyInput`, large style). Optional "Wage a week" (`wage_weekly`).
- **Loan:** "New loan fee" (`loan_fee`).
- **Client check:** the new amount must be higher than the current one. Error: "Your new offer must be higher than {Amount}." The server also refuses anything that lowers the value; show its message through `getApiError`.
- **Confirm** (`useConfirm`): title "Raise your offer?", message "{Other} is told straight away. The extra {formatCurrency(delta)} is reserved from your transfer budget." (Leave out the second sentence when there's no fee delta.) Button "Raise offer".
- **Submit:** `POST /offers/:id/improve` with only the fields that changed (`fee_amount` | `loan_fee`, `wage_weekly`).
- **Success:** toast "Offer raised. {Other} has been told." (`success`). Invalidate the same keys as counter. Focus the headline.
- Requires `isBuyer && isActive && canMarketWrite`, which is the existing `canWithdraw` condition.

### 5.8 `OfferStanding.tsx`: "Where it stands"

**`offerRounds(offer, myClubId)`** goes in `lib/offerChanges.ts`:
- One round per event of type `SENT` / `COUNTERED` / `IMPROVED`, in order.
- Each round: `{ side: "me" | "them", kind, at, fee: number | null }`.
- `fee` is `payload.fee_amount` (`payload.loan_fee` on a loan `IMPROVED`) when present. Otherwise carry the previous round's fee forward, because a counter that didn't change the fee sends none.
- For non-parties, `side` comes from the buyer/seller club rather than "me/them".

**Card:** `rounded-xl bg-surface px-4 py-3.5 ring-1 ring-border`.
- Title row: "Where it stands" (15px/600), and on the right "Round {n}" (14px muted).
- **Track** (permanent, at least 2 distinct amounts among the markers):
  - **Markers:**
    - "Their first": the other side's first fee, hollow, `ring-danger`.
    - "Their offer": their latest fee, filled `bg-danger`, value in `text-danger-text`.
    - "Your valuation": seller with `card.your_valuation` only. Filled `bg-accent`, value in `text-accent-active`.
    - "Your ask" (seller) or "Your offer" (buyer): my latest fee, hollow, `ring-accent`.
    - Drop a marker that duplicates another's amount, keeping the later one.
  - **Scale:** linear between the smallest and largest marker. The 6px track is `bg-border-quiet`. The span between their latest and my nearest figure (valuation if shown, else my latest) is shaded `bg-danger-ring`.
  - **Labels** (value 13px/700 over a label 12px muted): below the track by default. A marker within 18% of the previous marker puts its label above. Labels at the ends align to the edge (left/right), and the rest centre.
  - **Accessibility:** the track is `role="img"` with an `aria-label` that reads every marker and the gap, e.g. "Their offer £4.2M. Your valuation £4.8M. Your ask £5.0M. Gap £600K."
- **Below 1024px:** `<button aria-expanded>` "Show all {n} rounds" / "Hide rounds" (`min-h-11`), listing the rounds newest first. Each row has "{You | Other} {offered | countered | raised}" (15px/600), the date (13px muted) and the fee (15px/700, right). The latest row also gets the change summary from `lastChange`.
- **1024px and up:** one row. The title block on the left is 150px with "Round {n} · all rounds", where "all rounds" switches the main tab to Offer history. The track fills the rest.
- **Loans, or fewer than 2 amounts:** no track. Show the title row and the rounds disclosure only.

### 5.9 Sections

- `useMediaQuery("(min-width: 1024px)")` decides tabs or rail; render one, never both.
- URL param `tab`, with `replace: true`. Values: `terms` (default), `messages`, `bids`, `history`. Below 1024px, `history` opens Terms with the rounds disclosure expanded.
- **Below 1024px (parties):** `SegmentedControl` with Terms · Messages · Other bids (the buyer sees "Your ranking").
- **1024px and up (parties):** `grid grid-cols-[minmax(0,1fr)_340px] items-start gap-5`.
  - Main column: `Tabs` with Terms · Offer history.
  - Rail: `<aside aria-label="Messages and other bids">`, `sticky top-20 max-h-[calc(100vh-104px)]`, with a small `SegmentedControl`: Messages · "Other bids · {n}" (n from the order book once loaded; leave it out until then).
- **Non-parties:** no tabs and no rail. Show `OfferTermsCard`, then the read-only `OfferThread` (as today), at `max-w-2xl`.

**Tab contents:**
- **Terms:** `OfferTermsCard`, then the "✦ Advice on this offer" disclosure (parties, open offers, AI available), then `DemoOfferControls` (unchanged; it renders only in demo builds).
- **Messages:** `ConversationPanel context={{ offerId }} timeline={offerTimeline(offer)} placeholder=…`, unchanged.
- **Other bids / Your ranking:** `SellerOrderBook` / `BuyerOrderBook`, with today's props.
- **Offer history (1024px and up):** the full rounds list from §5.8, plus "Offer made {formatDate(created_at)}".

**`OfferTermsCard.tsx`** (`OfferTerms` restyled to match the deal room's `DealTermsCard`):
- Heading: "Their offer" when the last move was theirs, "Your offer" when it was yours, "The offer" for non-parties. 17px/700.
- **Rows** (`grid sm:grid-cols-2 sm:gap-x-8`; each row has a label at 15px secondary, a value at 16px/600 and an optional note at 13px):
  - Permanent: Fee (with `<Estimate>` as today), Payment (instalments expand in place), Add-ons (expand), Sell-on, Wage, Contract, Ends.
  - Loan: Period, Loan fee, Wage share, Purchase, Conditional on, Early recall. Keep the binding-obligation callout underneath.
  - Use today's copy and formatters.
- **Changed markers:** a row whose label appears in `lastChange(offer).changes` gets the note "Changed · was {was}", or "New" when `was` is "None", in `text-accent-active font-semibold`. This applies whichever side made the change.
- **Footer** (14px muted): "Offer made {formatDate(created_at)} · changed {relative last_action_at}".
- **"✦ Advice on this offer" disclosure** (`min-h-16` button): `OfferAdvisor` (with `onUseTerms` wired to open the counter with `prefill`) followed by `NegotiationSummaryPanel`, both unchanged.

### 5.10 `OfferMoreMenu`

Uses the shared `MoreMenu`. Items, in order; leave out what doesn't apply, and if nothing is left, hide the trigger:
1. "View the listing" (`offer.sale_id`): link to `/sales/:sale_id`.
2. "Ask TransferX about this offer" (party): link to `askAboutPath("offer", offer.id, playerName)`.
3. Divider, then "Withdraw offer…" (`canWithdraw`, `text-danger-text-alt`): today's confirm ("Withdraw this offer?", "Withdraw", danger), then `withdrawMutation`.

### 5.11 `OfferHeader`

Uses `TransferHeader`.
- **Avatar:** `player.photo_url`, or the initials in position colours.
- **`h1`:** `PlayerLink`.
- **Sub-line:** position · seller (`ClubLink`) → buyer. The buyer is a `ClubLink` when it is known. When `isBuyerMasked(offer)`, it is plain text from `buyerLabel(offer)` plus an "Anonymous" badge in today's style. At `lg`, add "· offer made {formatDate(created_at)}".
- **Facts:** `offerHeadline(offer)` · "Permanent" / "Loan" · payment ("On completion" or "{n} instalments"; loans use `loanPeriod(offer)`).
- **Accepted, for non-parties:** keep a small "Offer {status}" note beside the facts, as today.

### 5.12 `useOfferActions(offer)`

Move `acceptMutation`, `rejectMutation`, `withdrawMutation` and the counter mutation into one hook, plus the new `improve`. Keep identical endpoints, invalidations, toasts and navigation, and add the Lite card key to each.

---

## 6. What is removed or moved

| Today | Goes to |
|---|---|
| "← Back" button | `TransferHeader` "← Back" (same `navigate(-1)`) |
| Offer card: player, position | header |
| Offer card: status badge | status card |
| Offer card: "View the deal →" | status card row 1 (non-parties; parties are redirected) |
| Offer card: "View listing →", Ask about this | More |
| Parties card: buyer (with Anonymous), seller | header route |
| Parties card: date | header (`lg`), Terms footer, Offer history |
| `OfferChanges` ("What changed" table) | status card changes list + Changed notes on terms rows. Delete the component. |
| Terms card, `OfferTerms` | `OfferTermsCard` |
| Actions card: Accept, Counter, Reject | status card |
| Actions card: waiting spinner line | status card, waiting tone |
| Actions card: Withdraw offer | More |
| `OfferAdvisor`, `NegotiationSummaryPanel` cards | "✦ Advice on this offer" disclosure; "✦ Suggest a counter" in the form |
| Conversation card | Messages tab / rail |
| `CounterForm` at the bottom of the Conversation card | `Sheet` below 1024px; inline in the status card from 1024px |
| Mobile "Detail \| Order book" switch and the two-pane container | `SegmentedControl` tabs; main column plus rail |
| Order book rail | "Other bids" / "Your ranking" tab; rail segment |
| `DemoOfferControls` | end of the Terms tab |

---

## 7. Responsive summary

| | Phone < 640 | Tablet 640–1023 | Desktop ≥ 1024 |
|---|---|---|---|
| Status card buttons | Accept + Counter side by side, Reject text below | 220px column | 200px column |
| Changes list | under the body | under the body | middle column, 320px |
| Where it stands | track + rounds disclosure | same, wider | one row, title block + track |
| Counter / Raise | full-height sheet | 560px centred sheet | inline in the status card |
| Sections | segmented tabs | segmented tabs | main tabs + 340px sticky rail |
| Terms card | 1 column | 2 columns | 2 columns |

---

## 8. Accessibility

- One `h1` (the player). The status card headline is an `h2`; the sheet title is the dialog's label.
- Struck-through "was" values carry a screen-reader "changed to" (§5.5). Changes never rely on colour or strikethrough alone.
- The price track is a labelled image (§5.8). Every figure also appears as text.
- The sheet traps focus, returns focus to its opener and closes on Escape (with the discard check).
- One-tap amounts use `aria-pressed`. Disclosures use `aria-expanded` and `aria-controls`.
- After any action succeeds, focus moves to the status card headline.
- Touch targets: 44px minimum below 1024px; the main buttons and Send are 48px.
- Check at 200% zoom at 1280px: the layout falls back to tabs, and the sheet stays usable.

---

## 9. Permissions and confidentiality

No viewer gains anything. Keep these guards:

- **`your_valuation` is confidential to the selling club.** Read it only from the Lite card, which already sends it only to the seller. Never compute or show a gap for the buyer, and never put the valuation in a message, toast, URL or `aria-label` on the buyer's side.
- **Anonymous buyers stay masked** in the header, status card, sheet title, More menu, rail and document title. Use `buyerLabel` / `card.other_club`, never `from_club_id` lookups.
- **Accept, Counter and Reject** need `isParty && isActive && isMyTurn && MARKET_WRITE` (unchanged). **Withdraw and Raise** need `isBuyer && isActive && MARKET_WRITE`.
- **Order books** are shown to parties only (unchanged).
- **The Lite card query** is enabled for parties only.
- **Redirects:** accepted offers send parties to the deal, and the phone push goes to Lite (unchanged).

The only change in what anyone can do is **D6**: buyers can raise a pending offer, which the backend already allows.

---

## 10. Files

**New**
- `frontend/src/components/transfer/TransferHeader.tsx`, `StatusCardShell.tsx`, `MoreMenu.tsx` (extracted, §5.1)
- `frontend/src/components/ui/Sheet.tsx`
- `frontend/src/components/offers/offerStatus.ts` (+ `offerStatus.test.ts`)
- `frontend/src/components/offers/OfferHeader.tsx`
- `frontend/src/components/offers/OfferStatusCard.tsx`
- `frontend/src/components/offers/OfferStanding.tsx`
- `frontend/src/components/offers/OfferTermsCard.tsx`
- `frontend/src/components/offers/OfferMoreMenu.tsx`
- `frontend/src/components/offers/CounterForm.tsx` (moved from the page)
- `frontend/src/components/offers/RaiseOfferForm.tsx`
- `frontend/src/hooks/useOfferActions.ts`
- `frontend/src/pages/offers/OfferDetailPage.test.tsx`

**Changed**
- `frontend/src/pages/offers/OfferDetailPage.tsx`
- `frontend/src/lib/offerChanges.ts`: add `offerRounds`, `diffDraft` (+ tests)
- the deal room components, to use the extracted shared pieces (no visual change)

**Deleted**
- `OfferChanges` and `OfferTerms` (the inline components in the page)

---

## 11. Copy rules

Same as the deal room spec §11:
- Plain sentences.
- No enum names.
- Money through `formatCurrency` / `offerHeadline`.
- Dates through `formatDate`, plus the replyBy rules above.
- "Your move" only when the viewer can act.
- Never state the valuation to the buyer.

---

## 12. Build order (one commit each; the page works after every step)

1. **Shared.** Extract `TransferHeader`, `StatusCardShell` and `MoreMenu` from the deal room components. Build `Sheet`. The deal room tests still pass.
2. **Logic.** `offerStatus.ts`, `offerRounds` and `diffDraft`, with tests. `useOfferActions` (moved mutations, plus the Lite card invalidation and `improve`).
3. **Top of the page.** `OfferHeader`, `OfferStatusCard` and `OfferStanding`, plus the Lite card query. Remove the Offer, Parties, What changed and Actions cards. Withdraw temporarily stays as a plain button until step 6.
4. **Counter.** Move `CounterForm` and restyle it. Build the sheet and inline containers, "✦ Suggest a counter" and the footer comparison. Remove the form from the Conversation card. Check that the request bodies are unchanged.
5. **Sections.** `OfferTermsCard` and the advice disclosure. Tabs below 1024px; main column plus rail from 1024px; the `?tab=` param. Remove the old two-pane container.
6. **More and Raise.** `OfferMoreMenu` (Withdraw moves here) and `RaiseOfferForm` with its confirm.
7. **Finish.** Tests (§13), manual checks, docs (§14), changelog.

---

## 13. Tests

**`offerStatus.test.ts`** (table-driven, with an `Offer` fixture factory and events):
- A new bid for the seller, with a valuation above the fee (gap sentence), with a valuation at or below the fee, and with no Lite card (no gap).
- Seller receiving a counter; seller receiving a raise (IMPROVED).
- Buyer receiving a counter: no valuation text even when a card is passed with `your_valuation` set (a guard test).
- Waiting: buyer with `MARKET_WRITE` (raise secondary), buyer without (no actions), seller (open-messages).
- Your move without `MARKET_WRITE`: info, `disabled_reason` copy.
- Loan with an obligation and with an option only: accept label "Accept the loan" and the binding body.
- Anonymous buyer: Other is the masked label.
- Rejected by me, rejected by them, withdrawn (both sides), expired, accepted for a non-party.
- replyBy: today, tomorrow, within a week and later; the overline turns red under 24h.
- Changes: shown only when the other side made the last move; capped at 4, with "and n more".

**`offerChanges.test.ts`:**
- `offerRounds`: fee carried forward for a counter without a fee, and a loan raise using `loan_fee`.
- `diffDraft`: a fee-only change, a structure change, no change.

**`OfferDetailPage.test.tsx`:**
- `h1` is the player. The status card shows "Accept £4.2M" and "Counter".
- Below 1024px: Counter opens a dialog with the fee focused. Tapping the "Your valuation" amount sets the fee. Send posts `/offers/:id/counter` with `{ fee_amount }` only (the same body as today for a fee-only change). The sheet closes, and the headline is focused.
- Closing a dirty sheet asks to discard.
- From 1024px: Counter turns the status card into the form, and "What … will see" lists the fee change.
- `?from=push&action=counter&amount=21000000` at 1024px and up opens the counter with that fee; `action=accept` highlights Accept.
- Accept: a loan with an obligation shows `acceptMessage` in the confirm. A 202 shows the approval toast and doesn't navigate.
- Reject uses the danger confirm. Withdraw appears only in More, and only for the buyer.
- Raise: the waiting buyer sees "Raise your offer". A lower amount shows the client error. A higher one shows the confirm with the reserved delta, then posts `/offers/:id/improve` with `{ fee_amount }`.
- The Lite card query failing still renders the page (no gap line, no suggested amounts).
- A non-party sees the read-only layout, with no tabs, no rail and no More.
- An anonymous buyer is never named anywhere on the seller's page.

**Manual checks** (with the demo scenario generator's offers):
- **375 × 667, 390 × 844:** a seller with a new bid, a seller with a counter, a buyer waiting, a loan with an obligation, an anonymous buyer.
- **The sheet on an iPhone:** footer above the home indicator; the keyboard doesn't cover Send (scroll the focused input into view).
- **768 × 1024:** centred sheet, tabs.
- **1024 × 700 and 1280 × 790:** inline counter; rail scrolls inside itself.
- Dark theme; 200% zoom.

---

## 14. Docs to update (`documentation-standards`)

- `docs/design-system/SCREENS.md`, "Offer detail": replace it with this layout and link this spec.
- `docs/design-system/RESPONSIVE.md`, "Two-pane screens": the offer page, like the deal room, uses tabs on tablets.
- `docs/feature_spec/README.md`: add this spec under in progress, and move it when done.
- `docs/CHANGELOG.md`: note D3 (where the counter opens), D6 (Raise your offer) and D7 (Withdraw moved to More).
- `docs/IMPLEMENTATION_STATUS.md` and `docs/SESSION_HANDOVER.md`, per the skills.
- Open follow-up tickets for Q1 (pending approval state) and Q2 (asking price), if wanted.
- This file: set `status: Implemented {date}` and add "Deviations".

---

## 15. Where the mock differs (the spec wins)

- **Asking price.** The mock's "under your £2.4M asking price" becomes the valuation sentence, or nothing (Q2).
- **Deadlines.** "Reply by" and "due by" copy follows the replyBy rules, from `expires_at`.
- **The rail tab's count** ("Other bids · 3") appears only once the order book has loaded.
- **The mock's loan headline** "Riverside want Adrian Kofi on loan, then to buy him" is "{Other} offered to take {P} on loan", with the obligation in the body (row 7).
- **The track's labels** use the collision rule in §5.8, not the mock's fixed positions.
- **Back** goes back in history, as today.
- **"Accept £4.2M" is built from `formatCurrency`**, so it reads however the app formats money (e.g. "£4,200,000" if that's the house format).
- **Sample data.** The mock's messages, rounds, clubs and amounts are samples.

---

## Deviations (2026-11-09 build)

- **One pass, not seven commits.** Built on `offer-room-focus` as one change; the page worked after each part locally but the steps were not committed separately. The step-3 interim (Withdraw as a plain button) was skipped.
- **Lint can't run**: the repo has no eslint dependency or config. `tsc -b` and `vitest` pass.
- **One backend change** (R8), against "frontend only".
- **"Where it stands" is hidden with a single round** (R10).
- **No document title change.** The page never set one, so there is nothing to mask.
- **The changes list renders once**, by breakpoint (`useMediaQuery`), rather than twice with CSS.
- **The rail's "Other bids · n"** reads the order book's cached `active_count` (seller only); the buyer's tab is "Your ranking" with no count.
- **Accept {fee} wraps onto two lines on a 390px phone** for an eight-figure fee ("Accept £40,000,000"); it still fits the fold.
- **Checked on screen** with the one open local offer (Chelsea → Manchester City, round 1, permanent, no valuation): phone 390 (seller, buyer), iPad 768 (seller), laptop 1280×790 (seller countering, buyer waiting). Every fold target held and nothing scrolled sideways. **Not checked on screen:** a track with several rounds, a loan, an anonymous buyer, a valuation gap, dark theme, 200% zoom, a real iPhone. The tests cover the logic for each.
- **Follow-up tickets not opened:** Q1 (pending-approval state after a 202) and Q2 (asking price in the gap line).

