---
title: "Phased plan, Q4 2026"
last_updated: 2026-10-03
status: Active
owner: "TODO — assign a Product Owner"
---

# Phased plan, Q4 2026

From the product and code review of 3 October 2026 (shareable page: https://claude.ai/artifact/QbLF7HTyQywXkD89gKqPGU). Phases are in order; each has a goal, its items, and what "done" means. Sizes are rough: S is days, M about a week, L more. The decisions at the end run alongside, starting now.

## Phase 0 — Finish and ship what's in flight

Goal: everything built in the last fortnight reaches Railway and real phones.

- [x] **Commit and PR Lite L6 and notifications phase 4** (S). Branch `lite-l6-undo`, 749 backend tests passing. It covers:
  - held sends with a 10-second undo, the Sent screen and progress;
  - the decision sheet from a push;
  - the morning summary push and the 30-minute email fallback.

  The decision sheet was checked at phone width. Migrations `0090`, `0091`. Specs: [`lite-mode/SESSIONS.md`](../lite-mode/SESSIONS.md), [`mobile-notifications/README.md`](../mobile-notifications/README.md), [ADR 0007](../../architecture/decisions/0007-held-sends-for-undo.md).
- [ ] **Deploy merged PRs #20–#24 to Railway** (S):
  - run migrations `0088` and `0089`;
  - install the new dependencies `pywebpush` and `openpyxl`;
  - set `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY` and `VAPID_SUBJECT` on the API service.
- [ ] **Real-phone notification test** (S): an iPhone (Home Screen app, iOS 18.4+) and an Android phone in Chrome. Check the test push, an offer push, the decision sheet, quiet hours and the morning summary.
- [x] **Loose ends** (S):
  - decide the agents' start page: **Pipeline** (decided 2026-10-03);
  - the flaky `test_seller_and_third_club_cannot_record_consent`: not reproduced in later runs; left as is, watch for it;
  - refresh `PRODUCT_SPEC.md`;
  - persist the Health page's job history, which resets on restart (migration `0092`);
  - mark staff-cancelled sales as distinct from a seller's withdrawal (migration `0092`).

  The deploy and the real-phone test follow [the Phase 0 runbook](./phase-0-runbook.md).

Done when: Railway runs the latest main, a real iPhone and an Android phone each receive and act on an offer push, and nothing is left on a branch.

## Phase 1 — Trust basics

Goal: nothing a club's finance or legal team would reject on day one.

- [x] **Currency that converts, or no currency setting** (S–M). Decided 2026-10-04: amounts stay in pounds everywhere, since deals are agreed in pounds. Picking EUR or USD adds "≈ €21.1m" next to headline figures, at the ECB's daily rate (`GET /fx/rates`).
- [ ] **Two-factor sign-in and signed-in devices** (M). Two-factor is required for anyone who can approve or complete deals; devices get "Sign out everywhere".
  - [x] Signed-in devices, with sign out per device and "Sign out everywhere else" (migration `0095`). Signing out takes effect at once.
  - [ ] Two-factor sign-in: deferred.
- [x] **People's names** (S): first and last name on users and staff, used in the team list, approvals, approval pushes, audit entries and the admin pages (migration `0093`). Other clubs still see only the club.
- [x] **"Check your squad" at sign-up** (M): `/club/squad-check` confirms each player's contract, wage and valuation, flags what's missing, and creates the contract when there is none (migration `0094`). It's in the first-run checklist, and My Club warns about gaps.
- [x] **GDPR data export and deletion** (S–M): Account settings → Your data. Closing an account erases personal details and keeps audit records (migration `0096`). Club owners and agents with active mandates are sent to TransferX.
- [x] **Code health** (S): 0 TypeScript errors (from 41), and the frontend build now type-checks. Offer logic moved from `offers/router.py` into `offers/actions.py`, which Lite's held sends now call directly.

Done when: a pilot club sees amounts in its own currency, every approver uses two-factor sign-in, and no squad shows a contracted player without a contract.

## Phase 2 — Compliance and completion

Goal: a deal can't reach "Signed" until the steps the authorities require are done.

- [ ] **Registration checklist in the paperwork stage** (L): FIFA TMS entry, the ITC request and receipt, league registration and the work permit. Each has an owner, a due time, a document slot and reminders. It replaces the single `registration` paperwork step.
- [ ] **Work permit eligibility** (M): GBE-criteria guidance on players and on offers to English clubs.
- [ ] **Transfer windows by federation** (M). Today `transfer_windows` has no league or country; the buying club's federation should decide.
- [ ] **A real medical step** (S–M): date, location and attendees, with pass, fail, or pass with conditions (which can reopen the fee).
- [ ] **Deadline-day mode** (M): every open deal by hours left, with what's blocking it, on screen and in pushes.

Done when: a demo deal walks through TMS, ITC, permit and registration with dated steps, and an offer outside the buying club's window is refused with the federation named.

## Phase 3 — Simplify the core

Goal: fewer paths, one place to talk, one board to work from.

- [x] **Transfers board** (L). Built 2026-10-04 at `/board` (product ADR 0008); the old pages sit under "Classic views". Was:: a column per stage, with buying and selling filters. It replaces Listings, My Listings, Offers sent, Offers received, Transfers in progress and Enquiries.
- [x] **One conversation per transfer** (L). Built 2026-10-04: read across the four existing stores rather than migrated ([architecture ADR 0008](../../architecture/decisions/0008-one-conversation-read-across-existing-messages.md)); on the board's card detail and the deal room's Conversation tab. Was:: one conversation per transfer replaces offer messages, enquiry threads, deal-room comments and agent negotiation threads, with audiences (both clubs, internal, club with agent). Existing messages move across.
- [x] **One main way to buy** (M). Already in place: listing defaults to open to offers, auction is under "Advanced", fixed price isn't offered. Was:: enquiry → offer → deal is the default. Auctions and fixed price move behind "advanced".
- [x] **Lite and full app, on purpose** (S decision, then ongoing). Decided 2026-10-04: Lite decides, the full app operates (product ADR 0008). Was:: Lite is where people decide (phone, push, undo, approvals), and the full app is where they operate.
- [x] **Lite L7 and L8** (M each). Built 2026-10-04 (migrations `0097`, `0098`; see [SESSIONS](../lite-mode/SESSIONS.md)). Was: L7 is team contact ("Ask Sam", "Send to Sam"); L8 is decisions from email, with held sends on the `EMAIL` channel.
- [x] **Trim the assistant and notification settings** (S–M). Built 2026-10-04: settings start with four rows (daily summary and the three tiers), every type behind "Show every type"; the admin AI page gives each assistant feature a verdict (Keep, Review, Consider removing, Not enough data yet). No feature is removed until there's real usage. Was: using AI usage tracking and notification settings grouped by tier.
- [x] **Notification follow-ups from phase 4** (S–M). Built 2026-10-04 (see the [notifications spec](../mobile-notifications/README.md)). Was: an approval decision sheet (it needs a page for a single approval), swiping between items, the push action pre-selected on wider screens, and iPhone tap tracking.

Done when: a new club member can find, start and finish a transfer from the board and its conversation.

## Phase 4 — Money and documents in depth

Goal: the numbers and papers a club's finance and legal teams sign off.

- [ ] **Full personal terms** (M): appearance, goal and loyalty bonuses, release clause, image rights, relocation. Today `PersonalTerms` holds only wage, signing bonus and length.
- [ ] **Cost per season** (M): amortised fee plus wages on offers and deals, and the effect on PSR and FFP.
- [ ] **Solidarity contribution, training compensation and the agent fee cap** (M).
- [ ] **Payments that reconcile** (M): instalments confirmed as paid by both sides, overdue escalation, and an accounts export.
- [ ] **Agreements and e-signatures** (L): generated from the agreed terms, signed by both clubs and the player, stored on the deal.

Done when: a completed demo deal produces a signed agreement and a cost schedule a finance lead accepts without re-keying.

## Phase 5 — Planning, agents and players

Goal: help clubs plan the window, not only run deals in it.

- [ ] **Squad lists and quotas** (M): the 25-man list with homegrown counts, and the effect of each deal.
- [ ] **Renewals pipeline** (M): contracts ending within 18 months, with renew, sell or release decisions.
- [ ] **Agent tools** (M): mandate expiry alerts, a client contract calendar, commission tracking.
- [ ] **A private view for players** (S–M): the offer, the proposed terms and the next step.
- [ ] **Valuations that always say something** (M): comparables and a range when the model can't value a player.

Done when: a club can plan its next window in TransferX (renew, sell, buy) within the squad rules.

## Decisions needed (alongside, starting now)

- **Business model:** club subscription, a fee per transfer, or data licensing. [`business-model.md`](../../business/business-model.md) is still TODO. This decides the paying user and which phases matter most.
- **Pilot with 2–3 clubs** before Phase 1 ends, with analytics and AI usage reviewed after four weeks.
- **Data sources** (Phase 2): the Transfermarkt licence, and whether API-Football covers history, injuries and comparables.

## Progress

- **2026-10-04 — Phase 3 built except retiring the classic pages.** On `phase-3-board`: the board, one conversation, the buy path and Lite split decisions, L7 and L8, the settings trim, and the notification follow-ups. Migrations `0097`, `0098`. The classic list pages were retired the same day, once the board had history, search and "+ New listing" (product ADR 0008, update). Moving messages into one table is still open.
- **2026-10-04 — Phase 1 done except two-factor sign-in.** On branch `phase-1-trust`, stacked on `lite-l6-undo`. Migrations `0093`–`0096`.
- **2026-10-04 — Phase 0 code done.** L6, notifications phase 4 and the loose ends are in one PR from `lite-l6-undo`. Also fixed: two tabs refreshing the sign-in at once could sign one out. Still to do, by someone with Railway access and phones: the deploy and the real-phone test ([runbook](./phase-0-runbook.md)).
