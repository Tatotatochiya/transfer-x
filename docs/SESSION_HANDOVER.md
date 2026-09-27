---
title: "Session Handover"
last_updated: 2026-09-26
status: Active
owner: "TODO — assign a Documentation Owner"
---

# Session Handover

## Purpose

The single, current handover note between one working session and the next — human or Claude. Read this at the start of every session, right after [`PRODUCT_SPEC.md`](./PRODUCT_SPEC.md).

## Scope

In scope: the most recent session's summary — what's in motion right now.
Out of scope: full project history (see [`CHANGELOG.md`](./CHANGELOG.md)); this file is not a log.

## How this file works

This file is **overwritten**, not appended to, at the end of each session — maintained by the [`session-lifecycle`](../.claude/skills/session-lifecycle/SKILL.md) skill. It should always contain exactly one thing: the latest session's summary. If you want history, `CHANGELOG.md` has it; this file only needs to answer "what does the next session need to know right now."

## Latest Session Summary

## Session Summary — 2026-09-26

**Where the work is.** Branch **`loan-seller-side`**, six commits ahead of `main`, **not pushed**. This machine has no GitHub credentials and no `gh` CLI, so the push has to happen from another machine, or after `gh auth login` here. The working tree is clean. `main` is unchanged and level with `origin/main` at `d5a76c0`.

| Commit | What | Migration | Tests |
|---|---|---|---|
| `07d69e0` | Migration `0060` no longer re-adds `deals.loan_fee`/`option_to_buy`, which `0029` already created (a fresh `alembic upgrade head` failed at `0060`). `entrypoint.sh` made executable. | — | — |
| `789b7b5` | The seller can see and counter a loan; loans are spending-approval gated; the approval replay keeps loan terms and anonymity; the listing order book masks anonymous buyers. | — | 15 new |
| `430c326` | A loan's wage is read from the contract; a permanent offer must name a fee (£0 with a reason); exercising an option needs approval; the buyer's reservation follows a seller's counter at acceptance; `scripts/backfill_contract_wages.py`. | `0071` | 9 new, **526 passed** |
| `93961a1` | A deal's type and loan terms are locked after acceptance, and the deal room shows them all; obligation conditions are agreed on the offer. | `0072` | **none, suite not run** |
| `d9e2d95` | A counter can remove an option; the loans panel shows conditions; the post-counter stale view is fixed. | `0073` | **none, suite not run** |
| `648bc53` | Listings can be for Transfer, Loan or Either, with an "Available for loan" filter. | `0074` | **none, suite not run** |

The last three were built without tests, at the product owner's request. They were checked by `tsc -b` (43-error baseline) and live on the dev stack. Full detail is in [`CHANGELOG.md`](./CHANGELOG.md) and in [`feature_spec/loan-transfers.md`](./feature_spec/loan-transfers.md), deviations 20–29.

**Completed work:**

- Reviewed the loan workflow from both clubs' side. The central finding: a selling club could not see the loan it was being asked to accept. The frontend `Offer` type had no loan fields, and every seller page read `fee_amount`, which a loan never carries. Everything the review found is now built (the commits above).
- **Found and fixed along the way, beyond the review:**
  - An approved **anonymous offer went out with the buyer named**, because the approval replay dropped `is_anonymous`.
  - The listing order book never masked anonymous buyers.
  - Counters were never validated.
  - Approving a fee-less offer crashed.
  - Improving a loan gave it a £0 transfer fee.
  - A manager's offer was captured for approval before it was validated.
  - The deal-room `PATCH` still accepted `deal_type`.
- The session started with the **frontend container serving a bundle from 2026-08-17**. It is a built image with no source mount, so `docker compose up` alone never shows new UI. Rebuilt with `docker compose build frontend`.
- Docs: product ADR **0004** (listing availability); CHANGELOG, IMPLEMENTATION_STATUS, `PRODUCT_SPEC.md` (migration head `0074`), the loan spec (deviations 20–29), the club-roles spec D7 note, and the Railway pending-repairs table.

**Important decisions** (all with the product owner):

- **A loan's approval amount is its loan fee plus any obligation price.** An option is not counted at offer time, because the club may never use it. **Exercising** an option is approval-gated instead.
- **A loan's wage is read from the player's contract, and shown to both clubs once a loan offer exists.** Hiding it from the buyer is not possible: their per-offer wage reservation (share × wage) appears on `GET /clubs/me/commitments`. A contract with no wage **refuses** the loan rather than proceeding on £0.
- **The buyer's reservation is squared at acceptance, not when the seller counters.** Refusing a seller's counter because the buyer is short would reveal the buyer's budget to the seller.
- **A permanent offer always names a fee.** "No fee — free transfer or swap" is gone: out-of-contract players are signed, not offered for, and swaps cannot be recorded. £0 needs a reason, which is posted to the thread.
- **A deal's type and loan terms are fixed once the offer is accepted.** To change them, the clubs collapse the deal and re-approach.
- **A conditional obligation still starts the purchase at expiry.** The platform cannot evaluate "if promoted", so the clubs collapse the purchase if the condition was not met. *Open:* whether both clubs should confirm the conditions instead.
- **Listing availability is a field separate from the sale type** ([product ADR 0004](./product/decisions/0004-listing-availability-transfer-loan-or-either.md)). Auction is transfer-only; a loan-only listing has no asking price; an offer must match its listing.

**Outstanding work:**

- **Run the backend suite once before merging.** The last three commits tightened behaviour that older tests may exercise: offers against a closed or mismatched listing are now refused, as are deal-room loan edits. It takes about 6 minutes: `docker compose exec -T api python -m pytest tests -q`.
- **Push `loan-seller-side` and open the PR against `main`.**
- **Railway:**
  - Deploy migrations `0071`–`0074`. Railway does not auto-deploy; check the live `alembic_version`.
  - Run `backend/scripts/backfill_contract_wages.py` there, `--dry-run` first. **Until then every loan on Railway is refused**, because its contracts have no wages either. See [`operations/environments-and-deployment.md`](./operations/environments-and-deployment.md#pending-data-repairs-on-railway).
- **The player-level `open_to_offers` flag versus listings** (deferred in product ADR 0003) now has a third dimension, loan availability. The player page can still show "Closed to offers" beside "View listing".
- A player out on loan cannot be listed from the "Out on loan" panel.
- Still from the previous handover:
  - 43 TypeScript errors and 16 failing frontend tests (audit H9/M11).
  - The dead `sort_by=value` market sort.
  - The demo generator's unbuilt M1–M4/S1–S2 scenarios.

**Risks:**

- **Three commits are untested.** See the first outstanding item.
- **The deal-room lock (`93961a1`) was never exercised live.** This machine's database has no deals: the demo data lives on the other development machine. It was checked only by review and `tsc`.
- **Machine-specific state.** On *this* machine's database, `backfill_contract_wages.py` has been run (106 contracts, about £1.2–1.6m/wk per club). On the other machine it has not, so loans will be refused there until it is run. The same applies to the four new migrations, which apply on the next `docker compose up`.
- **Concurrency on money (audit H3):** there are still no row locks on offer accept, deal completion or instalment payment. Accepting an offer now also adjusts the buyer's reservation, so two simultaneous accepts are a real way for the budget to go wrong.
- Commits here are authored per command as `Tatotatochiya <aashishpradhan@outlook.com>`, because this machine has no git identity configured.

**Recommended next task:**

1. From a machine that can push, run the backend suite on `loan-seller-side`, fix anything the last three commits broke, then push and open the PR. The PR text is not in the repo; the commit messages carry the detail.
2. Then **row locks on offer accept and deal completion (audit H3)**. That is the gap most likely to corrupt money now that acceptance moves reservations.

**Suggested Linear updates** (not made; for the product owner to confirm):

- Close or annotate any loan-transfer tickets covering seller visibility, counters and approvals, and reference `loan-seller-side`.
- New ticket: "Conditional obligation to buy: decide automatic start vs. both-club confirmation".
- New ticket: "Merge player open-to-offers flag with listing availability" (follows ADR 0003 and ADR 0004).
- Ensure audit H3 (row locks on money paths) has a ticket, raised in priority.

## Related documents

- [`PRODUCT_SPEC.md`](./PRODUCT_SPEC.md) — read this first, then this file
- [`CHANGELOG.md`](./CHANGELOG.md) — full change history
- [`IMPLEMENTATION_STATUS.md`](./IMPLEMENTATION_STATUS.md) — current verified build status
