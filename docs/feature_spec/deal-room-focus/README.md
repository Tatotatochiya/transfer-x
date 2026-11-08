---
title: "Deal room, answer first"
last_updated: 2026-11-08
status: Implemented 2026-11-08
owner: "TODO — assign a Product Owner"
---

# Deal room, answer first

Written against `Tatotatochiya/transfer-x` `main` at `cbcbf7a` (8 Nov 2026). Route: `/deals/:id`. Page: `frontend/src/pages/deals/DealDetailPage.tsx` (1,893 lines today).

**Goal.** On every device, before any scrolling, the deal room answers three questions: **who is this deal for, what do I need to do, and how far along is it.** Everything else is one tap away.

**Design reference.** `TransferX - Deal Room Focus.dc.html` (needs `support.js` beside it; kept outside the repo). Section **Now** shows where the scroll goes today, **A** the phone, iPad and laptop layouts, **B** the status card at seven stages, then where every current block goes. The mock uses a simplified deal. Where this README and the mock disagree, **this README wins** (§15 lists the differences).

**Scope.** Frontend only. No API, model, migration or permission changes. If you find you need one, stop and ask.

**Revised 2026-11-08 after review against `main` (`f5c6a53`):** a player viewing his own deal (row 14a), copy for loans, free agents and pre-contracts (§5.2 "Deal kinds"), more than one notice at once (R-e), the no-scroll criterion scoped to the card before any tap, Q1 decided (buyer and agent only), the 13px rule scoped to new and changed components, and notes on the due date and the 1024px switch.

---

## 0. Before you start

1. Follow the repo's `session-lifecycle` skill. Read `docs/PRODUCT_SPEC.md`, `docs/SESSION_HANDOVER.md`, `docs/design-system/RESPONSIVE.md`, `docs/design-system/TOKENS.md` and the "Deal room" section of `docs/design-system/SCREENS.md`.
2. Apply the `engineering-standards` and `product-principles` skills. This page has money, consent and a state machine in it.
3. Work on a branch `deal-room-focus`. Build in the order in §12; each step leaves the page working.
4. Read the whole of `DealDetailPage.tsx` before changing it. Every mutation, endpoint, invalidation, toast and confirmation dialog in it stays exactly as it is, unless §3 says otherwise.
5. If the code differs from what this spec says it does, say so in your summary rather than quietly picking one.

---

## 1. Why

Estimated from the code at Paperwork stage, 390px phone (about 700px of page visible) and 13-inch laptop (790px):

| | Phone today | Laptop today |
|---|---|---|
| First thing on the page | "Blocked on: Paperwork checklist" | same |
| Player's name first appears | ~1,660px (screen 3) | ~1,300px |
| Your button (paperwork step) | ~1,150px (screen 2) | ~900px, just under the fold |
| Advance / Execute Transfer (Actions card) | ~2,250px (screen 4) | ~1,700px |
| Messages and documents | ~4,600px (screen 7) | ~3,800px |
| Total page | ~5,300px | ~4,500px |

What causes it:

- The stage is shown five times before any action: "Blocked on" header, step bar, Next steps panel, three lane cards (a full phone screen when they stack), then a stage banner. "Agreed terms" repeats it again.
- One set of terms is split across six panels (Agreed terms, Deal structure, Payment schedule, Agent commission, Personal terms, Medical). The fee appears three times and the agent four.
- The page has no heading naming the player.
- "Collapse deal…" sits in the Actions card with the same weight as Advance.
- Messages and documents are the last block on the page. RESPONSIVE.md already asks for a Detail / Messages / Documents switch on phones; the page doesn't have one.

---

## 2. Success criteria

Check every item before calling it done.

- [ ] **Phone, 390 × 700 of page (below the 56px top bar):** the player's name, the fee, the whole status card including its primary button, and the progress line are visible without scrolling, at every stage in §13's list. This is the card as it first renders: an inline form opened by a tap (row 9's personal terms, row 13's signed-terms upload) may push the progress line down.
- [ ] **iPad portrait, 768 × 960:** the same, plus the Overview / Messages / Documents control.
- [ ] **Laptop, 1280 × 790 (including the 56px desktop header):** the header, status card, progress line, the top of the Agreed terms card **and** the Messages rail are visible without scrolling.
- [ ] Every action available today is still available to exactly the same people, with the same confirmation dialogs (plus the one new confirmation in D9).
- [ ] Nothing that a viewer can't see today becomes visible to them (§9).
- [ ] Each stage is stated once in the status card and once in the progress line. No other block repeats it.
- [ ] No horizontal scrolling at 375px.
- [ ] In new and changed components: no text below 13px, no text lighter than `text-text-muted`, every tap target at least 44 × 44px below 1024px. Components reused unchanged (`DealTimeline`, `OfferThread`, `ConversationPanel`, the agent and comment threads) keep their sizes; bringing them up is a follow-up.
- [ ] `npm run lint`, `npm run typecheck` (or the repo's equivalents) and `vitest` pass. New tests in §13 exist and pass.

---

## 3. Decisions

### Decided by this design

- **D1. Four blocks, in this order, on every device:** header → status card → progress → sections (tabs, or main column plus rail).
- **D2. One status card replaces** the "Blocked on" header, `DealNextStepsPanel`, `ThreeLanes`, the agent-negotiation / personal-terms / ready-to-execute / completed / collapsed banners, `CommissionProposalView`, `PersonalTermsBanner`, the paperwork checklist block, the consent-recording controls, `SetPersonalTermsForm`'s placement and the Actions card. Its content comes from a **pure function** (`getDealStatus`, §5.2) worked out from the deal, the same way the page works out `clubCanAdvance` today. It doesn't depend on the AI service.
- **D3. Below 1024px (phone and tablet) the sections are tabs:** Overview, Messages, Documents. This changes RESPONSIVE.md's "Two-pane screens" rule for tablets ("rail moves below the content"), because stacking the rail under the terms makes the iPad page as long as today's phone page. Update the doc (§14).
- **D4. From 1024px the sections are a main column plus a 340px rail.** The rail holds Messages / Documents, is sticky and scrolls inside itself. The main column has tabs: Overview, How this was agreed, Activity.
- **D5. Terms become one "Agreed terms" card** (§5.6). The payment schedule and add-ons open in place.
- **D6. "Collapse deal…" moves into a More menu** and opens a dialog. It no longer sits beside the main action.
- **D7. The stage list always includes Personal terms.** `StageTracker` today shows four stages (Agreement, Paperwork, Confirmed, Completed) unless the deal is *currently* at Agent negotiation or Personal terms, so a deal without an agent never shows Personal terms, and a deal with an agent loses two stages once it passes them. The backend (`deals/service.py advance_deal`) sends **every** deal through Personal terms. The new list: Agreement, Agent commission (only when the deal has an agent, same rule as `ThreeLanes.hasAgent` today), Personal terms, Paperwork, Confirmed, Completed.
- **D8. Fix the Agreement-stage button label.** Today it reads `Advance to ${dealStageLabel(nextStage("AGREEMENT"))}`, which is "Advance to Agent Nego…", but the backend moves Agreement → Personal terms. The new label is "Move on to personal terms".
- **D9. Completing a transfer asks for confirmation.** Today "Execute Transfer" fires on one click. It registers the player, can't be undone and is worth millions (`product-principles` §3). Add a `useConfirm` dialog (copy in §5.3). Advancing between earlier stages stays one click, as today.
- **D10. Deal notes stay as they are and move to Activity.** They come back on the deal for every viewer, with the author club shown, so they are shared, not private. (The mock's suggestion to merge them into the club-only channel is withdrawn.)
- **D11. The back button keeps `navigate(-1)`.** Its label becomes "← Back". Destinations don't change.
- **D12. The Next steps AI panel is removed from this page.** Its deterministic steps are what the status card now says, and its advice is reachable through More → "Ask TransferX about this deal". If nothing else imports `DealNextStepsPanel` after this, delete it (and its now-unused hook usage) in the same PR.

### Open questions (each has a default; build the default unless told otherwise)

- **Q1. Who advances from Agent negotiation once the club has agreed commission?** The frontend shows Advance only to the agent (`clubCanAdvance` excludes `atAgentNegotiation`). The backend (`advance_deal`: "the mandated agent, clubs, or staff, once both sides agreed") and the assistant's `deal_steps` ("either") let both clubs do it. **Decided: the agent and the buying club.** Show "Move on to personal terms" to the agent and to the buying club with `DEAL_WRITE` once `club_agreement === "AGREED"`. The selling club has no part in the commission, so it waits (row 19a). Note it in the changelog.
- **Q2. The collapse reason is thrown away.** The page collects "Reason (optional)" but `POST /deals/:id/collapse` is sent with no body, and the endpoint takes none. **Default: remove the reason field** from the dialog. Write a follow-up ticket to store a reason on the audit event. Don't add the backend change in this PR.
- **Q3. Unread count on the Messages tab.** The mock shows a badge; no endpoint gives an unread count for a deal's conversation. **Default: no badge.** Write a follow-up ticket.
- **Q4. Responding to the commission proposal and answering for the player have no confirmation today.** **Default: unchanged** (no new dialogs beyond D9).
- **Q5. Crossing 1024px.** The tabs and the rail are different trees, so rotating an iPad (landscape is exactly 1024px) remounts `ConversationPanel` and loses an unsent draft. **Accepted** for now; a follow-up can keep the draft.

---

## 4. Layout

### Phone, below 640px

```
┌──────────────────────────────┐ AppShell top bar, 56px, fixed (unchanged)
│ ← Back                More ⋯ │ 44px row
│ (BW) Bram Wouters            │ h1, 22px/700
│      MID · Castlebrook → Meridian FC
│ £5.4M · Permanent · 3 instalments
├──────────────────────────────┤ 16px
│ YOUR MOVE · due 12 Nov       │ status card
│ Sign the transfer agreement  │ 19px/700
│ 2 of 4 paperwork steps done. │ 16px body
│ Castlebrook signed on 10 Nov.│
│ [   Mark the agreement signed   ] 48px, full width
│      Show the 4 paperwork steps  ⌄
├──────────────────────────────┤ 12px
│ Step 4 of 6 · Paperwork      │ progress
│ ▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░         │
│ Show all stages ⌄            │
├──────────────────────────────┤ 20px
│ [Overview][Messages][Documents] segmented, 48px
├──────────────────────────────┤
│ Overview content (§5.5)      │
└──────────────────────────────┘
```

### Tablet, 640–1023px

The same order. The changes:
- In the header, the fee moves to the right: 22px/700, with type and payment beneath it.
- In the status card, the text is on the left and the buttons stack in a 220px column on the right. The paperwork checklist is always visible, in two columns, under a rule.
- The progress block shows the stage pills, with a summary sentence beneath them.
- The Agreed terms card uses two columns.

### Laptop, 1024px and wider

```
Sidebar 232 │ ← Back
            │ (BW) Bram Wouters                         £5.4M     [More ⋯]
            │      MID · Castlebrook → Meridian FC · agent Luka Brandt   Permanent · 3 instalments
            │ ┌ YOUR MOVE · due 12 Nov ──────────────────────────────────────────────────────┐
            │ │ Sign the transfer agreement  │ ✓ Castlebrook signed      │ [Mark the agreement signed] │
            │ │ 2 of 4 steps done. …         │ ● You sign the agreement   │ [Message Castlebrook]       │
            │ │                              │ ○ Medical  ○ Registration │                             │
            │ └──────────────────────────────────────────────────────────────────────────────┘
            │ ● Agreement ─ ● Agent ─ ● Personal terms ─ ◉ Paperwork ─ ○ Confirmed ─ ○ Completed
            │ Clubs agreed £5.4M · agent agreed 6% · Bram agreed £38K a week · paperwork 2 of 4
            │ ┌ Overview | How this was agreed | Activity ┐  ┌ Messages | Documents ┐ 340px, sticky
            │ │ Agreed terms (2 columns)                  │  │ conversation …        │
            │ └───────────────────────────────────────────┘  └───────────────────────┘
```

### Spacing

- Page padding is unchanged (AppShell's `px-4 py-6 md:px-6 lg:px-8`).
- Gaps: header → status card 16px; status card → progress 12px; progress → sections 20px (`lg:` 16px).

---

## 5. Components

All new files live in `frontend/src/components/deals/` unless noted. Use the existing tokens (Tailwind `@theme` in `index.css`), never hex.

### 5.1 `DealHeader.tsx`

Props: `deal`, `viewerSide`, `isPlayer`, `moreMenu: ReactNode`.

- **Row 1** (`flex items-center justify-between`):
  - `<button onClick={() => navigate(-1)}>← Back</button>`, styled `-ml-2.5 inline-flex min-h-11 items-center px-2.5 text-[15px] font-medium text-text-secondary hover:text-text`.
  - The More menu on the right, below `lg` only.
- **Row 2** (`flex items-center gap-3.5 lg:gap-4`):
  - **Avatar, 52px circle.** Use `deal.player.photo_url` when there is one. Otherwise show the initials in the position colours (`bg-pos-{gk|def|mid|fwd}-bg text-pos-…-text`, matched from `player.position`), falling back to `bg-accent-avatar text-accent-active`. `aria-hidden`.
  - **Name block** (`min-w-0 flex-1`):
    - `<h1 className="text-[22px] lg:text-2xl font-bold tracking-[-0.01em] leading-tight">`, containing `PlayerLink` without a photo. Fallback "Unknown player".
    - Sub-line, `mt-0.5 text-[15px] text-text-secondary`, joined with " · ":
      - `player.position`, when present.
      - The route: `ClubLink(seller) → ClubLink(buyer)`. With no seller: "Free agent → {buyer}".
      - `lg` only: "agent {agent.display_name}" when `deal.agent`.
  - **`lg` only, right-aligned:** the fee (`<Money>` at `text-2xl font-bold`), with the facts line beneath it at 14px muted. Then the More menu.
- **Row 3, below `lg`:** `mt-2.5 text-[15px] text-text-secondary`, holding the fee (`<Money>` in `text-[17px] font-bold text-text`) and the facts line.
  - **Facts line:** `dealTypeLabel(deal.deal_type)` · payment ("On completion" or "{n} instalments"). For a loan, the loan period (`formatDate(loan_start)–formatDate(loan_end)`) replaces the payment part.
  - Append a small `Badge` "Auction deal" when `deal.is_auction_deal`.
- **No status badge.** The status card says it.

### 5.2 `dealStatus.ts`: pure derivation (the heart of this change)

```ts
export type StatusTone = "you" | "wait" | "info" | "hold" | "done" | "collapsed";

export type StatusAction =
  | { kind: "advance"; label: string }
  | { kind: "complete"; label: "Complete transfer" }
  | { kind: "paperwork"; step: "sign-agreement" | "submit-registration"; label: string }
  | { kind: "record-medical"; label: string }
  | { kind: "commission-respond"; agreement: "AGREED" | "DECLINED"; label: string; danger?: boolean }
  | { kind: "propose-terms"; label: string }               // opens SetPersonalTermsForm inside the card
  | { kind: "record-consent"; label: string }              // file input + "He agreed" (existing flow)
  | { kind: "player-consent"; agreement: "AGREED" | "DECLINED"; label: string; danger?: boolean }
  | { kind: "open-messages"; label: string }
  | { kind: "open-profile"; label: string }                 // the player's own page, where he answers his terms
  | { kind: "show-schedule"; label: string };

export interface DealStatusView {
  tone: StatusTone;
  overline: string;          // "Your move", "Waiting on Castlebrook", "Completed" …
  meta?: string;             // "due 12 Nov", "4 days without movement", a date
  headline: string;          // one sentence, the action or the state
  body?: string;             // one or two plain sentences
  primary?: StatusAction;
  secondary?: StatusAction;
  showChecklist: boolean;    // render deal.paperwork inside the card
  strips: { title: string; body: string }[]; // real-world / window notices, when they aren't the headline
}

export interface StatusViewer {
  side: "buyer" | "seller" | null;   // the viewer's club on this deal
  isAgent: boolean;
  isPlayer: boolean;
  isStaff: boolean;
  canWrite: boolean;                 // can("DEAL_WRITE")
  canSetPersonalTerms: boolean;      // computed exactly as today
  canRecordConsent: boolean;         // computed exactly as today
  canRecordMedical: boolean;         // isStaff || (isBuyer && atPaperwork && IN_PROGRESS && canWrite), as today
  negotiation: AgentNegotiation | null | undefined;
  realWorld: { hold: string | null; window: string | null } | undefined;
  now?: Date;                        // for tests
}

export function getDealStatus(deal: Deal, viewer: StatusViewer): DealStatusView;
```

Keep the permission flags computed in the page, as they are today, and pass them in. `getDealStatus` must not re-derive permissions differently.

**Names used in the copy:**
- **P**: `deal.player?.name`, else "the player".
- **B**: the buyer club's name. **S**: the seller club's name.
- **Other**: the other club from the viewer's side (B or S).
- **A**: `deal.agent?.display_name`, else "the agent".
- **Fee**: `formatCurrency(deal.agreed_fee)`.
- **Commission**: `${(pct*100).toFixed(1)}%` when there is a pct, plus ` (${formatCurrency(amount)})` when there is an amount. Never compute an amount from the pct.

**Deal kinds** (the copy changes with them):
- **Loan** (`deal_type === "LOAN"`): `agreed_fee` is the loan fee. Row 2's headline is "{P} is on loan at {B} until {formatDate(loan_end)}" for the buyer and "{P} joined {B} on loan" for others; leave out "until …" when there's no `loan_end`. Row 24's body says "Both clubs agreed the loan" (no figure when the loan fee is 0).
- **No selling club** (free agent or pre-contract, `seller_club_id == null`): there's no Other club. Row 24's body is "{B} agreed to sign {P}." Wherever a row would say "Message {Other}", it says "Open messages". Row 7 can't occur (every step is the buyer's).
- **No fee** (`agreed_fee` 0 or null): row 2 has no body (no "Paid on completion"), and row 24 names no figure.

**Rules applied after the table:**
- **R-a. A club party without `DEAL_WRITE`, when the row would be `you`:** tone `info`, overline "Your club's move", the same headline, body "Your role can see this deal but can't act on it.", no actions.
- **R-b. Idle meta:** when the tone is `wait` and `daysSince(deal.updated_at) >= 3`, meta is "{n} days without movement".
- **R-c. Due meta:** when the tone is `you` and `deal.sla_deadline` is set, meta is "due {formatDate}". The backend sets `sla_deadline` only on entering Confirmed (and moves it when a closed window holds the deal), so in practice this shows at Confirmed only.
- **R-d. Default secondary:** for a club party, when the tone is `you` and there is no secondary, secondary is `{ kind: "open-messages", label: "Message {Other}" }`. Show it only at `sm` and wider; on a phone the tabs sit right below.
- **R-e. Real-world strips:** on open deals before Confirmed, each real-world `hold` and `window` notice becomes a strip, the hold first (it's the one that needs staff). Both can be present. Use the existing copy from `DealRealWorldNotice`:
  - hold: title "Completion on hold: moved in real life", body is the hold text plus " Talks and paperwork carry on as normal. Only completing the transfer waits."
  - window: title "Completes when the transfer window opens", body is the window text plus " Talks and paperwork carry on as normal. Both clubs are told when it opens."
  - A loan `note` with no hold stays as today (shown, nothing waits): strip title "Moved in real life", body is the note.

**The table.** The first matching row wins.

| # | When | Tone | Overline · meta | Headline | Body | Primary / secondary |
|---|---|---|---|---|---|---|
| 1 | `status === "COLLAPSED"` | collapsed | "Collapsed" · formatDate(updated_at) | "This transfer fell through" | none | none |
| 2 | `status === "COMPLETED"` | done | "Completed" · formatDate(completed_at) | buyer viewer: "{P} is a {B} player"; others: "{P} joined {B}" | the next unpaid instalment: "Next instalment: {amount} due {date}."; all paid: "All instalments are paid."; none: "Paid on completion." | sec: show-schedule "View the payment schedule" (only if instalments) |
| 3 | stage `CONFIRMED`, and realWorld.hold or .window | hold | "Completion on hold" | hold (also when both): "Completion waits: {P} has moved in real life"; window only: "Completes when the transfer window opens" | the strip copy from R-e as the body; when both, the hold's body, and the window notice as a strip | none |
| 4 | stage `CONFIRMED`, club party | you | "Your move" | "Complete the transfer" | "Both clubs finished the paperwork. Completing registers {P} at {B}. It can't be undone." | complete "Complete transfer" |
| 5 | stage `CONFIRMED`, other viewer | info | "Ready to complete" | "The clubs can now complete the transfer" | none | none |
| 6 | stage `PAPERWORK`, club party, an undone step with `owner === side` | you | "Your move" | by the first such step's key: agreement_* "Sign the transfer agreement"; medical "Record the medical result"; registration "Submit the registration" | "{done} of {total} paperwork steps done." plus, if the other side's `agreement_signed_by_*_at` is set, " {Other} signed the agreement on {date}." plus " When every step is done the deal is confirmed." | agreement: paperwork sign-agreement "Mark the agreement signed"; medical: record-medical "Record medical result"; registration: paperwork submit-registration "Mark registration submitted". `showChecklist: true` |
| 7 | stage `PAPERWORK`, club party, otherwise | wait | "Waiting on {Other}" | the first undone step's `label` (backend copy, e.g. "Selling club signs the transfer agreement") | "{done} of {total} paperwork steps done." | sec: open-messages "Message {Other}". `showChecklist: true` |
| 8 | stage `PAPERWORK`, other viewer | info | "Paperwork" | "The clubs are completing the paperwork" | "{done} of {total} steps done." | `showChecklist: true` |
| 9 | stage `PERSONAL_TERMS`, no `personal_terms`, `canSetPersonalTerms` | you | "Your move" | "Propose personal terms to {P}" | "The deal moves on once he accepts them." | propose-terms "Propose terms" |
| 10 | stage `PERSONAL_TERMS`, no `personal_terms` | wait | via agent (`commission_agent_id`): "Waiting on the agent"; else "Waiting on {B}" | via agent: "{A} is preparing {P}'s personal terms"; else "{B} is preparing {P}'s personal terms" | none | club party: open-messages "Open messages" |
| 11 | stage `PERSONAL_TERMS`, consent `AGREED`, club party | you | "Your move" | "Move the deal on to paperwork" | "{P} accepted {formatWage(wage)} for {n} years." (leave out any part that is null) | advance "Move on to paperwork" |
| 12 | stage `PERSONAL_TERMS`, consent `AGREED`, other viewer | wait | "Waiting on the clubs" | "{P} accepted the terms. The clubs move the deal on to paperwork." | none | none |
| 13 | stage `PERSONAL_TERMS`, consent `PENDING`, `canRecordConsent` | you | "Your move" | "Record {P}'s answer to the terms" | "He has no TransferX account or agent. Upload the signed terms to record that he agreed." | primary record-consent "He agreed" (reveals the upload, §5.3); sec player-consent DECLINED "He declined" (danger) |
| 14 | stage `PERSONAL_TERMS`, consent `PENDING`, `isAgent` | you | "Your move" | "Answer for {P}" | has account: "He can answer himself, or you can answer for him."; else: "He has no TransferX account, so you answer for him." | primary player-consent AGREED "Accept for player"; sec player-consent DECLINED "Decline for player" (danger) |
| 14a | stage `PERSONAL_TERMS`, consent `PENDING`, `isPlayer` | you | "Your move" | "Answer the personal terms" | "{B} offers {formatWage(wage)} for {n} years. You answer on your player page." (leave out any part that is null) | open-profile "Answer the terms" (to `/player/profile`, the page with today's answer buttons) |
| 15 | stage `PERSONAL_TERMS`, consent `PENDING` | wait | `terms.agent_id`: "Waiting on the agent"; else "Waiting on {P}" | "{P} hasn't answered the personal terms yet" | **reuse `PersonalTermsBanner`'s body copy** for this case, unchanged | club party: open-messages "Open messages" |
| 16 | stage `AGENT_NEGOTIATION`, `isAgent`, nothing proposed | you | "Your move" | "Propose your commission" | "Set it in the negotiation workspace below. {B} then answers it." | none |
| 17 | stage `AGENT_NEGOTIATION`, `isAgent`, `club_agreement === "PENDING"` | wait | "Waiting on {B}" | "{B} is considering your proposal" | "You asked for {Commission}." | none |
| 18 | stage `AGENT_NEGOTIATION`, `isAgent`, `club_agreement === "DECLINED"` | you | "Your move" | "{B} declined your proposal" | "Change the terms below to send a new one." | none |
| 19 | stage `AGENT_NEGOTIATION`, `club_agreement === "AGREED"`, the agent or the buying club (Q1) | you | "Your move" | "Move the deal on to personal terms" | "{B} agreed {Commission} with {A}." | advance "Move on to personal terms" |
| 19a | stage `AGENT_NEGOTIATION`, `club_agreement === "AGREED"`, the selling club | wait | "Waiting on {B}" | "{B} agreed the agent's commission" | "{B} or {A} moves the deal on to personal terms next." | sec: open-messages "Message {B}" |
| 20 | stage `AGENT_NEGOTIATION`, club party, negotiation missing or nothing proposed | wait | "Waiting on the agent" | "{A} hasn't proposed his commission yet" | "Personal terms start once {B} agrees the commission." | sec: open-messages "Open messages" |
| 21 | stage `AGENT_NEGOTIATION`, buyer, `club_agreement === "PENDING"` | you | "Your move" | "{A} asks for {Commission}" | "Paid by {payer, lower case}." plus, if any, " Conditions: {additional_conditions}" | primary commission-respond AGREED "Accept proposal"; sec commission-respond DECLINED "Decline" (danger) |
| 22 | stage `AGENT_NEGOTIATION`, seller, `club_agreement === "PENDING"` | wait | "Waiting on {B}" | "{B} is answering the agent's commission proposal" | none | sec: open-messages "Message {B}" |
| 23 | stage `AGENT_NEGOTIATION`, club party, `club_agreement === "DECLINED"` | wait | "Waiting on the agent" | "{B} declined the commission proposal" | "{A} can send a new proposal." | sec: open-messages "Open messages" |
| 24 | stage `AGREEMENT`, club party | you | "Your move" | "Move the deal on to personal terms" | "Both clubs agreed {Fee}. Either club can move it on; {P} then has to agree his personal terms." (see "Deal kinds" for loans, no seller and no fee) | advance "Move on to personal terms" (D8) |
| 25 | any other open case (staff, player, non-party) | info | `dealStageLabel(stage)` | "This deal is at {stage label, lower case}" | none | none |

Then apply R-a to R-e.

### 5.3 `DealStatusCard.tsx`

Props: `view: DealStatusView`, `deal`, `viewerSide`, `actions: DealActions` (from `useDealActions`, §5.8), `onOpenMessages()`, `onShowSchedule()`, `onRecordMedical()`.

- **Root:** `<section aria-labelledby="deal-status-headline">`. Classes `rounded-xl bg-surface p-4 sm:px-5 sm:py-[18px] shadow-[0_1px_2px_rgba(16,24,40,0.06)] ring-1`, plus the tone ring:

  | Tone | Ring | Overline colour |
  |---|---|---|
  | you | `ring-danger-ring` | `text-danger-text` |
  | wait | `ring-border` | `text-text-secondary` |
  | info | `ring-border` | `text-text-muted` |
  | hold | `ring-warning-fill/40` | `text-warning-text` |
  | done | `ring-success/30` | `text-success-text` |
  | collapsed | `ring-danger-border` | `text-danger-text-alt` |

- **Overline:** `text-xs font-bold uppercase tracking-[0.05em]`. Meta is appended as `<span className="normal-case tracking-normal text-[13px] font-semibold text-text-secondary"> · {meta}</span>`.
- **Headline:** `<h2 id="deal-status-headline" tabIndex={-1} className="mt-1.5 text-[19px] lg:text-xl font-bold leading-snug text-text">`.
- **Body:** `mt-1.5 text-base leading-normal text-text-secondary`.
- **Layout:**
  - Below `sm`: one column; buttons full width, `min-h-12`, 8px apart, primary first.
  - `sm` to `lg`: `flex flex-wrap gap-5`. Text `flex-[1_1_360px]`, buttons in a `flex-[0_0_220px]` column.
  - `lg` and up: `flex items-center gap-7`. Text `flex-1`, the checklist (when shown) in a `w-[300px]` column, buttons in a `w-[200px]` column.
- **Buttons:**
  - Primary: `Button variant="primary" size="lg"`, `w-full`.
  - Secondary: `variant="secondary"`. Danger secondaries use `variant="secondary"` with `text-danger-text-alt`, never a red fill (red fill is reserved for the confirm step).
- **Checklist** (`showChecklist`):
  - One row per `deal.paperwork` step: 22px circle (done: `bg-success text-white` with ✓; the viewer's next open step: `ring-2 ring-accent`; otherwise `ring-1 ring-input-border`), the label at 15px (`font-semibold text-text` for the viewer's open step, `text-text-secondary` otherwise), and to the right at 13px muted "Done" / "Your move" / "Their move".
  - Below `sm`: hidden behind `<button aria-expanded>` "Show the {n} paperwork steps" / "Hide the steps" (`min-h-11 w-full text-[15px] font-semibold text-accent`).
  - `sm` to `lg`: always shown, under `border-t border-rule pt-3`, in `grid sm:grid-cols-2 gap-3`.
  - `lg` and up: always shown, in the middle column.
- **Strips** (`view.strips`, one block each): `mt-3 rounded-lg bg-warning-bg px-3 py-2.5 text-sm text-warning-text`, with the title in `font-semibold` and the body beneath it.
- **Action wiring** (exact endpoints, invalidations and toasts as today):

  | `kind` | Does |
  |---|---|
  | `advance` | `actions.advance()`. Show the API error under the buttons as today (`advanceError`). |
  | `complete` | `await confirm({ title: "Complete the transfer?", message: "This registers {P} at {B} for {Fee}. It can't be undone.", confirmLabel: "Complete transfer" })`, then `actions.advance()` (D9). |
  | `paperwork` | the existing `PaperworkChecklist.act` flow, including its two confirm dialogs, unchanged |
  | `record-medical` | `onRecordMedical()`, which opens `MedicalResultDialog` (§5.7) |
  | `commission-respond` | `actions.commissionRespond(agreement)` |
  | `propose-terms` | toggles an inline region inside the card that renders the existing `SetPersonalTermsForm` fields and its "Send to player" button. Drop its `Panel` wrapper. Labels become visible `<label htmlFor>` at 14px; inputs `min-h-12` below `lg`. |
  | `record-consent` | the "He agreed" button reveals, inside the card, the existing file input (with its label and help text) and a "Record agreement" button with the existing confirm and `recordAgreementMutation`, disabled until a file is chosen. Before the tap the card shows only the two buttons. |
  | `player-consent` | DECLINED from the buyer (row 13): the existing danger confirm, then `personalTermsConsentMutation`. From the agent (row 14): straight to the mutation, as today. |
  | `open-messages` | `onOpenMessages()` (§5.5) |
  | `open-profile` | a `Link` to `/player/profile` styled as the button |
  | `show-schedule` | `onShowSchedule()`: switches to Overview, opens the schedule row in `DealTermsCard` and scrolls it into view |

- **Focus:** after any action's mutation succeeds, focus the headline (`#deal-status-headline`) so screen readers announce the new state.

### 5.4 `DealProgress.tsx` (replaces `StageTracker.tsx`)

Add `dealStages(deal, negotiation): DealStage[]` to `dealStatus.ts` per D7.

`hasAgent = deal.commission_agent_id != null || negotiation != null || deal.stage === "AGENT_NEGOTIATION" || deal.agent != null`. Today's rule plus `deal.agent`, so the Agent stage doesn't vanish once commission is done.

**Stage states:**
- Indices before the current stage are done.
- The current stage is "now".
- `status === "COMPLETED"`: every stage is done.
- `status === "COLLAPSED"`: every pill is muted and the phone line reads "Collapsed at {stage label}".

**Short labels for pills:** Agreement, Agent, Personal terms, Paperwork, Confirmed, Completed. Long labels for the list: same, but "Agent commission".

**Stage notes** (shared by the phone list and the summary sentence):

| Stage | Done | Now | Next |
|---|---|---|---|
| Agreement | "Clubs agreed {Fee}" | "Clubs are finalising the deal" | none |
| Agent commission | "Agent agreed {pct}%" (or "Commission agreed") | "{A} and {B} are agreeing commission" | "Not started" |
| Personal terms | "{P first name} agreed {formatWage}" (from `agreed_wage_weekly ?? personal_terms.wage_weekly`) | consent PENDING "Waiting for {P}'s answer"; no terms "Terms not proposed yet"; AGREED "{P} accepted" | "Not started" |
| Paperwork | "Paperwork done" | "Paperwork {done} of {total}" | "Not started" |
| Confirmed | "Confirmed" | "Ready to complete" | "When the paperwork is done" |
| Completed | formatDate(completed_at) | none | none |

**Rendering:**
- **Card:** `rounded-xl bg-surface px-4 py-3.5 ring-1 ring-border`.
- **Below `sm`:**
  - "Step {i} of {n} · {label}" at 15px/600, then a 6px bar (`bg-border-quiet` track, `bg-success-dot` fill, width `(i/n)*100%`).
  - Then `<button aria-expanded>` "Show all stages" / "Hide stages" (`min-h-11 text-[15px] font-semibold text-accent`).
  - Expanded: one row per stage. A 22px dot (done ✓ `bg-success`; now `bg-accent`; next `ring-2 ring-input-border` on white), the long label at 15px (now: 700 text; others: 500 secondary), and the note beneath at 14px muted.
- **`sm` and up:**
  - Today's pill row (keep its classes), using `dealStages`, the short labels and `text-[13px]`.
  - Beneath it, a summary sentence (`mt-2.5 text-sm text-text-secondary`): the notes of every done stage plus the current stage's note, joined with " · ".
  - At `lg` it may truncate with an ellipsis on one line; the full text goes in `title`.

Delete `StageTracker.tsx` once nothing imports it.

### 5.5 Sections: tabs and rail

- **New hook `frontend/src/hooks/useMediaQuery.ts`:** `useMediaQuery(query: string): boolean`, using `window.matchMedia` with a change listener. It returns `false` where `matchMedia` is missing. `test/setup.ts` already mocks `matchMedia`; let tests override it.
- `const isDesktop = useMediaQuery("(min-width: 1024px)")`. Render the tabs **or** the rail, never both, so `ConversationPanel` mounts once.
- **URL state:** `useSearchParams`, param `tab`, written with `replace: true`.
  - Values: `overview` (default), `messages`, `documents`, `history`, `activity`.
  - Below 1024px: `history` and `activity` show Overview with that disclosure row open.
  - From 1024px: `messages` and `documents` choose the rail's segment, and `history` and `activity` choose the main tab.
  - A link to `/deals/:id?tab=messages` from notifications therefore works on every device.
- **New primitive `frontend/src/components/ui/SegmentedControl.tsx`:**
  - Props: `items: { key, label }[]`, `active`, `onChange`, `size?: "md" | "sm"`, `ariaLabel`.
  - `role="tablist"`. Each button is `role="tab"` with `aria-selected` and `aria-controls`.
  - Left/Right arrow keys move between tabs.
  - Container: `grid grid-flow-col auto-cols-fr gap-1 rounded-xl bg-border-quiet p-1`.
  - Button: `min-h-12 rounded-[9px] text-[15px]` (sm: `min-h-9 text-sm`). Active: `bg-surface font-semibold text-text shadow-[0_1px_2px_rgba(16,24,40,0.1)]`. Idle: `font-medium text-text-secondary hover:text-text`.
- **Below 1024px:**
  - `SegmentedControl` (Overview · Messages · Documents), then a `role="tabpanel"`.
  - Viewers who can't see the deal room today (anyone but `isParty || isAgent || isPlayer`) get no control and only the Overview content.
- **From 1024px:** `grid grid-cols-[minmax(0,1fr)_340px] items-start gap-5`.
  - **Main column:** the existing `Tabs` component. Overview · "How this was agreed" (only when `deal.offer_id && isParty`) · Activity.
  - **Rail** (only for viewers who can see the deal room; otherwise the main column takes the full width):
    - `<aside aria-label="Messages and documents">`, classes `sticky top-20 flex max-h-[calc(100vh-104px)] flex-col rounded-xl bg-surface ring-1 ring-border`. 56px desktop header + 24px gap = `top-20`; 56 + 24 + 24 bottom = 104.
    - Header `p-3`: `SegmentedControl size="sm"` (Messages · Documents).
    - Body: `min-h-0 flex-1 overflow-y-auto px-3.5 pb-3.5`.
- **`onOpenMessages()`:** sets `tab=messages`. Below 1024px it also scrolls the segmented control to the top of the viewport (`scrollIntoView({ block: "start" })`).

**Overview content, in this order:**
1. `AgentNegotiationWorkspace`: agent at `AGENT_NEGOTIATION`, `IN_PROGRESS`, as today. **Remove its footer "Advance to Personal Terms →" button and the "Awaiting club agreement…" note**; the status card carries them (row 19). Keep "Edit terms" / "Save terms".
2. `TermsDiffSpine`: unchanged.
3. `DealTermsCard` (§5.6).
4. `DealStaffTools`: staff, unchanged.
5. **Below 1024px only:** a card of disclosure rows. Each is a `<button aria-expanded>`, `min-h-16`, with the title at 16px/600, the sub-line at 14px muted and a chevron. The content renders **only when expanded**, so its queries don't fire until then.
   - "How this was agreed": only when `deal.offer_id && isParty`. Sub-line "Offer made {date}". Content: `AgreedOfferHistory`'s inner content (§5.7).
   - "Notes": sub-line "{n} notes" or "No notes yet". Content: the notes list and `NoteForm`, as today, under a caption "Everyone who can open this deal sees these notes."
   - "Activity": sub-line "Everything that happened on this deal". Content: `DealTimeline`.

**Desktop main tabs:**
- "How this was agreed": `AgreedOfferHistory`'s inner content.
- "Activity": a "Notes" section (heading 16px/700, the same caption, list and `NoteForm`) followed by `DealTimeline`.

### 5.6 `DealTermsCard.tsx`

This merges Agreed terms, Deal structure, Add-ons, Payment schedule, Agent commission, Personal terms and Medical.

- **Card:** `rounded-xl bg-surface px-4 pt-3.5 pb-4 sm:px-5 ring-1 ring-border`.
- **Heading:** "Agreed terms", 17px/700.
- **Rows:** `grid sm:grid-cols-2 sm:gap-x-8`. Each row is `flex justify-between gap-3 border-t border-rule py-3`, with the label at 15px `text-text-secondary`, the value at 16px/600 `text-text`, and an optional note beneath the value at 13px muted, right-aligned.
- Expanded lists span both columns (`sm:col-span-2`).

Rows, in order; a row with nothing to show is left out:

| Row | Value | Note / extra | Source today |
|---|---|---|---|
| Fee | `<Money value={deal.agreed_fee}>` | `FairValueBadge` beneath, **never for `isPlayer`** (as today) | Agreed terms card |
| Loan period, Loan fee, Wage share, Purchase, Conditional on, Early recall | port **exactly** from the Deal structure panel's LOAN branch, same copy and formulas | Purchase keeps `text-warning-text` for an obligation | Deal structure |
| Payment (not loan) | "On completion", or a `<button aria-expanded>` "{n} instalments ⌄" | expanded: one line per instalment (date · amount · "Paid {date}" in success text or "Pending" muted), as today | Deal structure + Payment schedule |
| Sell-on | `{(pct*100).toFixed(1)}%` | none | Deal structure |
| Wage | `formatWage(agreed_wage_weekly ?? personal_terms?.wage_weekly)` | "{n}-year contract" (`contract_length_years ?? personal_terms?.length_years`). If it comes from `personal_terms` and consent isn't AGREED, add "Proposed · waiting for {P}" in `text-warning-text` | Agreed terms + Deal structure + Personal terms |
| Signing bonus | `signing_bonus ?? personal_terms?.signing_bonus` | none | same |
| Agent commission | "{pct}% · {amount}" (whichever exist) | "Paid by {payer, lower case}" | Agent commission |
| Add-ons | `<button aria-expanded>` "{n} add-on(s) ⌄" | expanded: the existing clause rows (type, trigger, amount, cap, status pill), unchanged | Add-ons |
| Player consent | AGREED: "Agreed" (success text) with note formatDate(agreed_at); PENDING: "Waiting" (warning text); DECLINED: "Declined" (danger text) | buyer with `consent_evidence_attachment_id`: a "View signed copy" link using the existing blob-download handler | Personal terms |
| Medical | "Passed" (success) / "Failed" (danger) / "In progress" (warning) / "Not recorded yet" (muted) | formatDate(updated_at). When `canRecordMedical`: a text button "Record result" (none or PENDING) or "Change" that opens `MedicalResultDialog` | Medical check |

**Footer:** `mt-2 text-sm text-text-muted`, "Agreed on the offer and fixed for this deal. To change them, collapse the deal and re-approach." This is today's Deal structure copy; show it on every deal.

**Rows that are removed, and where the information lives now:**
- Buyer, Seller → header route.
- Player's agent → header (`lg`) and progress.
- Type → header.
- Stage → progress.
- Created → Activity.
- "Auction deal" → a header badge.

### 5.7 Dialogs and the More menu

- **`MedicalResultDialog.tsx`:** move the edit half of `MedicalCheckPanel` (the radiogroup of Passed / Failed / Still in progress with their effect copy, the notes textarea and the "Record: …" button, plus its mutation, invalidations and toast) into a `Modal` titled "Medical result". Delete the read half (now the terms row), the `OPEN_MEDICAL_FORM` window event, the `#medical-check` anchor and the "Record medical ↓" scroll hack.
- **`CollapseDealDialog.tsx`:** a `Modal` titled "Collapse this deal?".
  - Body: "This cannot be undone. The transfer will fall through and reserved budget will be released." (today's copy).
  - Buttons: "Confirm collapse" (`variant="danger"`, `collapseMutation`) and "Cancel".
  - Reason field per Q2 (default: removed).
- **`DealMoreMenu.tsx`:**
  - The trigger is `<button aria-haspopup="menu" aria-expanded>` "More ⋯" (`min-h-11 lg:min-h-10 rounded-lg px-3.5 text-[15px] lg:text-sm font-semibold text-text-secondary ring-1 ring-inset ring-input-border bg-surface`).
  - The menu is `role="menu"`. Copy the keyboard behaviour of the account menu in `Sidebar.tsx`: arrows, Home/End, Escape returns focus to the trigger, close on outside click, Tab and route change. If the menu logic extracts cleanly into `components/ui/Menu.tsx` with Sidebar's tests still passing, do that; otherwise copy it.
  - Items, in order:
    1. "Ask TransferX about this deal": party only. A `Link` to `askAboutPath("deal", deal.id, playerName)`, the same target as `AskAboutButton`.
    2. A divider, then "Collapse deal…" (`text-danger-text-alt`): only when `clubCanCollapse`. Opens `CollapseDealDialog`.
  - With no items, don't render the trigger.
- **`AgreedOfferHistory`:** remove its `Panel` and `<details>` wrappers. It renders the summary line, `NegotiationSummaryPanel` and `OfferThread`. The disclosure row or the desktop tab provides the container.

### 5.8 `useDealActions.ts` (in `frontend/src/hooks/`)

Move every mutation out of `DealDetailPage` and the inline components into one hook, `useDealActions(dealId)`, which returns:
- `advance`, `collapse`
- `paperwork(step)`, `recordMedical({ status, notes })`
- `commissionRespond(agreement)`, `setPersonalTerms(values)`
- `playerConsent(agreement)`, `recordAgreement(file)`
- each one's `isPending` and error

Keep **identical** endpoints, payloads, `invalidateQueries` keys and toast copy. This is a move, not a rewrite.

### 5.9 `DealRoomPanel.tsx`: split

Split it into two named exports and delete the wrapper's "Deal Room" header and its internal tab bar:

- **`DealMessages`**, same props as today. For clubs (`viewerSide`), `ConversationPanel context={{ dealId }}`. For agents and players, the channel buttons, the private-channel warning banner (keep it, full width and copy unchanged) and `CommentThread` / `NegotiationMessageThread`.
- **`DealDocuments`**: today's `DocumentsTab`.

---

## 6. What is removed from `DealDetailPage.tsx`

| Today | Goes to |
|---|---|
| "← Back to deals" | `DealHeader` "← Back" (D11) |
| `DealRoomHeader` ("Blocked on" + `StageTracker`) | status card headline + `DealProgress` |
| `DealNextStepsPanel` | the status card (D12) |
| `ThreeLanes`, `Lane`, `laneStatus` | `DealProgress` notes. Delete them. |
| `PaperworkChecklist` block | the status card checklist + actions |
| Ready-to-execute, agent-negotiation, completed and collapsed banners | the status card |
| `CommissionProposalView` | status card rows 20–23 (the thread is in Messages → agent channel, as today) |
| `PersonalTermsBanner` | status card rows 10, 12, 15 (its copy is reused) |
| `DealRealWorldNotice` blocks | status card row 3 and R-e. Extract `useDealRealWorld(dealId, open)` from `DealRealWorldNotice.tsx`; keep the file for the hook and update its test to cover the hook. |
| Player card, including `AskAboutButton` | header; More menu |
| Agreed terms, Deal structure, Add-ons, Payment schedule, Agent commission and Personal terms panels | `DealTermsCard` |
| Actions card (Advance, Execute, Collapse, inline collapse panel) | status card primary; More → `CollapseDealDialog` |
| `SetPersonalTermsForm` panel | inside the status card (row 9) |
| Consent recording and agent answer controls | the status card (rows 13, 14) |
| `MedicalCheckPanel` | the terms row + `MedicalResultDialog` |
| `AgreedOfferHistory` panel | disclosure row / desktop tab |
| Deal Notes panel | Activity (D10) |
| Activity Timeline panel | Activity |
| `DealRoomPanel` | tabs below 1024px; rail from 1024px |

After this, `DealDetailPage.tsx` should do only these jobs: queries, permission flags, the status derivation and layout. Target under 400 lines.

---

## 7. Responsive summary

| | Phone < 640 | Tablet 640–1023 | Desktop ≥ 1024 |
|---|---|---|---|
| Header fee | below the name | right of the name | right of the name, 24px |
| More menu | back row, right | back row, right | header row, right |
| Status card buttons | full width, stacked | 220px column, right | 200px column, right |
| Paperwork checklist | behind a toggle | always, 2 columns | always, middle column |
| Progress | "Step n of N" + bar + expander | pills + sentence | pills + sentence |
| Sections | segmented tabs | segmented tabs (D3) | main tabs + 340px sticky rail |
| Terms card | 1 column | 2 columns | 2 columns |
| Notes / history / activity | disclosure rows in Overview | same | main column tabs |

---

## 8. Accessibility

- One `h1` (the player). The status card headline is an `h2`. Card headings inside tabs are `h3`.
- Every disclosure uses a real `<button>` with `aria-expanded` and `aria-controls`.
- The segmented control uses tab semantics with arrow keys (§5.5).
- Focus goes to the status card headline after an action succeeds.
- Colour never carries meaning alone: every state has words ("Your move", "Waiting on…", "Done", "Passed").
- Text contrast: use the token pairs above; nothing lighter than `text-text-muted`.
- Touch: 44px minimum below 1024px; status card buttons 48px.
- Check at 200% zoom at 1280px: content reflows and the rail stays usable (it falls back to the tab layout once the viewport is under 1024 CSS px).

---

## 9. Permissions and confidentiality (unchanged)

No viewer gains anything. Keep every existing guard:

- Fair value: never for `isPlayer`.
- Commission proposal details: club parties (both clubs, as today) and the agent.
- Consent evidence link: buyer only.
- The club-only channel and its warning banner: club members of that side only.
- Write controls: `DEAL_WRITE` (TRA-151). Without it, R-a shows a view-only card.
- Deal room (Messages / Documents): `isParty || isAgent || isPlayer`, as today.
- Staff tools: `isStaff`.
- Medical recording: staff, or the buyer at Paperwork with `DEAL_WRITE`.

The one behaviour change in who can do what is **Q1**: clubs get the Advance button at Agent negotiation after agreement, which the backend already allows.

---

## 10. Files

**New**
- `frontend/src/components/deals/dealStatus.ts` (+ `dealStatus.test.ts`)
- `frontend/src/components/deals/DealHeader.tsx`
- `frontend/src/components/deals/DealStatusCard.tsx`
- `frontend/src/components/deals/DealProgress.tsx`
- `frontend/src/components/deals/DealTermsCard.tsx`
- `frontend/src/components/deals/DealMoreMenu.tsx`
- `frontend/src/components/deals/CollapseDealDialog.tsx`
- `frontend/src/components/deals/MedicalResultDialog.tsx`
- `frontend/src/components/ui/SegmentedControl.tsx`
- `frontend/src/hooks/useMediaQuery.ts`
- `frontend/src/hooks/useDealActions.ts`
- `frontend/src/pages/deals/DealDetailPage.test.tsx`

**Changed**
- `frontend/src/pages/deals/DealDetailPage.tsx`
- `frontend/src/components/deals/DealRoomPanel.tsx` (split)
- `frontend/src/components/deals/DealRealWorldNotice.tsx` (+ test): hook extracted
- `frontend/src/components/ai/Assistant.tsx`: remove `DealNextStepsPanel` if unused
- possibly `frontend/src/components/layout/Sidebar.tsx`: only if the menu logic is extracted to `ui/Menu.tsx`

**Deleted**
- `frontend/src/components/deals/StageTracker.tsx`

**Docs:** see §14.

---

## 11. Copy rules

- Plain sentences, the way a sporting director would say it. No enum names on screen (no "PENDING", no "AGENT_NEGOTIATION"); use `dealStageLabel` or the copy above.
- Money through `formatCurrency` / `formatWage` / `<Money>`. Dates through `formatDate`.
- "Your move" wording only when the viewer can act (R-a otherwise).
- Don't promise outcomes the backend doesn't guarantee (for example payments in the completion copy).

---

## 12. Build order (one commit each; the page works after every step)

1. **Logic.** Write `dealStatus.ts` (`getDealStatus`, `dealStages`, stage notes) with its tests, plus `useMediaQuery`, `SegmentedControl` and `useDealActions` (a move of the existing mutations; no UI change yet).
2. **Top of the page.** Build `DealHeader`, `DealStatusCard` and `DealProgress`, and render them at the top. Remove the "Blocked on" header, Next steps, ThreeLanes, all banners, the paperwork block, `CommissionProposalView`, the consent controls and the Actions card. Collapse temporarily stays reachable through a plain button until step 5. Delete `StageTracker`.
3. **Terms.** Build `DealTermsCard` and `MedicalResultDialog`, and remove the six panels and `MedicalCheckPanel`.
4. **Sections.** Split `DealRoomPanel`. Build the tabs below 1024px and the main column plus rail from 1024px, with the `?tab=` param, disclosure rows and desktop tabs. Move Notes, Activity and How this was agreed.
5. **More menu.** Build `DealMoreMenu` and `CollapseDealDialog`, and remove the temporary button.
6. **Finish.** Tests (§13), manual checks, docs (§14), changelog.

---

## 13. Tests

**`dealStatus.test.ts`** (table-driven; build `Deal` fixtures with a small factory). At least:
- Collapsed. Completed with instalments, both unpaid and all paid. Completed with no instalments.
- Confirmed: club party; on hold (real-world); window closed; staff viewer.
- Paperwork: buyer with the agreement open (and seller already signed: body includes "{S} signed the agreement on …"); buyer with only the medical open; buyer with only the registration open; seller waiting; agent viewer.
- Personal terms: buyer can propose; waiting on agent to propose; consent AGREED (club); consent PENDING with `canRecordConsent`; agent answering; the player himself (row 14a); waiting on player.
- Agent negotiation: agent with nothing proposed; agent waiting; agent declined; club_agreement AGREED for the buyer and the agent (row 19) and the seller (row 19a, Q1); buyer PENDING (`Accept proposal`); seller PENDING; no negotiation record.
- Deal kinds: a completed loan ("on loan at … until …"); a completed free-agent signing (no fee body); Agreement with no selling club.
- Agreement: club party (label "Move on to personal terms", D8).
- R-a: a buyer without `DEAL_WRITE` at Paperwork gets `info` and no actions.
- R-b idle meta at 3 days; R-c due meta from `sla_deadline`; R-d default secondary; R-e strips before Confirmed, including a hold and a window together.

**`dealStages`:**
- A deal with no agent includes Personal terms (D7).
- A deal with `deal.agent` keeps Agent commission at Paperwork.

**`DealDetailPage.test.tsx`** (use the repo's existing test utils and API mocking):
- Renders the player's name as `h1`.
- Paperwork buyer: the status card button "Mark the agreement signed" opens the existing confirm, and confirming posts to `/deals/:id/paperwork/sign-agreement`.
- Confirmed: "Complete transfer" opens the new confirm; cancel posts nothing; confirm posts to `/advance`.
- Below 1024px (`matchMedia` false): the segmented control switches panels and writes `?tab=messages`; `?tab=documents` on load opens Documents.
- From 1024px (`matchMedia` true): the rail renders, and `ConversationPanel` mounts once.
- "Collapse deal…" appears only in the More menu, only with `clubCanCollapse`, and opens the dialog.
- Fair value isn't requested for a player identity (existing behaviour, keep a test).
- No "Blocked on" text, no "Next steps" panel, no "Actions" heading.

**Manual checks** (use the demo scenario generator's deals at every stage, `docs/feature_spec/demo-scenario-generator.md`):
- 375 × 667 and 390 × 844 in Safari or devtools: §2's phone criteria at Agreement, Agent negotiation (club and agent), Personal terms (no account), Paperwork (buyer and seller), Confirmed, on hold, Completed and Collapsed.
- 768 × 1024: tabs, two-column checklist and terms.
- 1024 × 700: the rail scrolls inside itself; nothing clips focus rings.
- 1280 × 790 and 1440 × 900: §2's laptop criteria.
- Dark theme, and 200% zoom at 1280px.

---

## 14. Docs to update (`documentation-standards` skill)

- `docs/design-system/RESPONSIVE.md`, "Two-pane screens":
  - Tablet uses the same segmented control as mobile for the deal room.
  - The rail's sticky `top` is 80px (below the 56px desktop header).
  - Keep the rule for the other two-pane screens unless they are changed too.
- `docs/design-system/SCREENS.md`, "Deal room": replace the "Blocked on" header, three lanes and six-pill description with this layout. Link this spec.
- `docs/feature_spec/README.md`: add this spec to "In progress or planned", then move it to "Implemented" when done.
- `docs/CHANGELOG.md`: note D7, D8, D9, Q1, Q2 and row 14a as user-visible behaviour changes.
- `docs/IMPLEMENTATION_STATUS.md` and `docs/SESSION_HANDOVER.md`, per the skills.
- This file: set `status: Implemented {date}` and add a "Deviations" section for anything built differently.

---

## 15. Where the mock differs from this spec (the spec wins)

- **The back control reads "← Back"** and goes back in history (D11). The mock's "← Transfers" link and laptop breadcrumb are dropped.
- **The header shows no age.** `PlayerSummary` has none.
- **The checklist follows `deal.paperwork`'s order** (buyer signs, seller signs, medical, registration). The mock lists them in a different order.
- **Fees, dates, names and the "due" date are sample data.** The due meta appears only when `sla_deadline` is set.
- **The mock has no More menu contents, dialogs or disclosure rows drawn.** Build them from §5.5–5.7.

---

## Deviations (as built, 2026-11-08)

- **Built in one pass, not six commits.** §12's order was followed, but the work is one change on `deal-room-focus`.
- **`npm run lint` can't run.** `package.json` has the script, but the repo has no eslint dependency or config. Type-check and vitest pass.
- **Commission payer copy** reads "Paid by the buying club" (and "the selling club", "the player") rather than the lower-cased enum.
- **A loan's real-world note** (no hold) shows as a strip on every open stage, including Confirmed, as it did before; R-e only listed stages before Confirmed.
- **Inline pieces moved to their own files** so the page is 324 lines: `AgentNegotiationWorkspace`, `TermsDiffSpine`, `DealTimeline`, `DealNotes`, `AgreedOfferHistory` (all in `components/deals/`). `useDealNextSteps` went with `DealNextStepsPanel`; the backend endpoint `GET /ai/deals/{id}/next-steps` stays, unused by the frontend for now.
- **The agent workspace's "Club: PENDING" chip** now reads "Club: waiting / agreed / declined" (no enum names on screen, §11).
- **Not done here:** the manual device checks in §13 (they need a browser and the demo scenario deals), and the follow-up tickets for Q2 (store a collapse reason), Q3 (unread count), Q5 (keep a draft across 1024px) and the 13px pass on reused components.

