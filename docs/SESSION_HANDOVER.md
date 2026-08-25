---
title: "Session Handover"
last_updated: 2026-08-25
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

**Session date:** 2026-08-25

**The working tree is clean and pushed.** `main` is level with `origin/main`. Everything below is committed. Full per-change detail in [`CHANGELOG.md`](./CHANGELOG.md).

Not committed, deliberately: three `claude-*.bat` launcher scripts in the repo root. They are per-machine Claude Code wrappers (one sets `DEEPSEEK_API_KEY`), not project code — either add them to `.gitignore` or move them outside the repo. Carried from the last session; still untracked.

**Completed work:**

- **Loan transfers, phases 0–4 — the feature is complete.** Five commits, one per phase. A loan is now chosen when the offer is made, executes as a loan (registration moves, ownership does not), runs to term on its own, and can turn permanent by option or obligation. Backend 499 tests pass. Spec, decisions log and per-phase deviations: [`feature_spec/loan-transfers.md`](./feature_spec/loan-transfers.md); the architecture call is [ADR 0005](./architecture/decisions/0005-loan-registration-separate-from-ownership.md).
  - Phase 0 — `DealType` enum drift: the frontend union was missing `FREE_TRANSFER`/`PRE_CONTRACT`, so **every free-agent signing displayed as "Permanent"**, and the terms-diff spine printed the raw enum.
  - Phase 1 — `deal_type` and loan terms on `Offer`, carried onto the `Deal`. Plus the wage-reservation hole below.
  - Phase 2 — `player_loans`, the `_complete_deal` branch, and `get_owning_club_id` returning the parent.
  - Phase 3 — expiry job, recall, notifications, read endpoints, and all four UI surfaces.
  - Phase 4 — option to buy (exercised by the loanee) and obligation to buy (fires automatically at expiry).
- **Offers now reserve wage budget.** Independent of loans and older: `reserve_budget` always took a `wage_weekly` argument with a real affordability check, and **none of the six budget calls in the offers module ever passed one**. A club could commit to wages it had no room for and only discover it at completion.
- **Market fair-value signal fixed** (earlier in the session): the batch valuation endpoint never passed a `reference_price`, so `divergence` was null for all 7,914 players — which silently emptied the "asking vs fair value" cell, made the "Best value first" sort a no-op, and pinned the "Under fair value" counter to 0. Extended to `OPEN_TO_OFFERS` listings with the product owner, and to the `market_value` fallback on the sale-detail embed.
- **Railway demo data.** All seven deal stages now live there, matching local. Required mirroring local's 16 agent mandates across first — Railway had none on Arsenal, and scenario `D3` needs a mandated Arsenal player. Credentials and gotchas: [`operations/environments-and-deployment.md`](./operations/environments-and-deployment.md).
- **Docs**: ADR 0005; `PRODUCT_SPEC.md` current-state facts (migrations `0069`, deal types, Railway); `transfer-lifecycle.md` gained *Deal types* and *Loans* sections and its `COMPLETED` row corrected; `IMPLEMENTATION_STATUS.md` three new rows plus corrected test totals; `environments-and-deployment.md` a Railway demo section.

**Important decisions:**

- **A loan does not use a second active contract** ([ADR 0005](./architecture/decisions/0005-loan-registration-separate-from-ownership.md)). `normalize_player_status` resolves the active contract with `scalar_one_or_none()`, so two active rows *raise* rather than misbehave, and that assumption runs through the whole player model. The loanee holds the one active contract; a `player_loans` row answers ownership. Do not "simplify" this into two contracts.
- **Wage split is a fraction, 0.0–1.0** (product owner, D4), matching `sell_on_pct` and `agent_commission_pct` rather than introducing a third convention.
- **Selling a loaned-out player terminates the loan** (product owner, D6). Blocking the sale would make a loaned player unsellable for up to a year.
- **`deal_type` is fixed at offer time and is not counterable.** Countering a loan with a permanent offer is a different proposal. The deal room shows it read-only — retyping it after acceptance was the original defect the whole spec exists to fix.
- **`agreed_fee` mirrors `loan_fee` on a loan deal.** Deliberate duplication: `collapse_deal`, approval thresholds and agent commission all read `agreed_fee` and would otherwise see zero.
- **Divergence is computed against any non-auction listing**, reversing spec line 382 with the product owner. D7's exclusion is about auctions, whose reserve and bids are hidden; an `OPEN_TO_OFFERS` asking price is already public.

**Outstanding work:**

- **`docker compose build frontend`** — the frontend container is a built image with no source mount, so `:5173` still serves a pre-loan bundle. None of this session's UI (nor the earlier redesign work) is visible there until rebuilt. All UI verification this session was done against a temporary Vite dev server on `:5174`.
- **The seller-counter reservation gap.** When the *seller* counters at a higher fee, the buyer's reservation is never recomputed — `counter_offer` adjusts it only when the buyer is the actor — so accepting a raised counter commits the original, lower figure while the deal records the higher `agreed_fee`. Pre-existing; the wage reservation added this session inherits the same asymmetry. **Left deliberately: it needs a product call**, because refusing an acceptance the buyer can no longer afford is a behaviour change, not a bug fix.
- `players/service.py`'s server-side `sort_by=value` orders by `fair_value - Player.market_value` and is dead, because `market_value` is 0% populated. Unused by the frontend today; B3's to fix.
- The demo generator's catalogue lists twelve scenarios; only the six deal-stage ones (`D1`–`D6`) appear to be built. The four live-market (`M1`–`M4`) and two supporting (`S1`–`S2`) scenarios look unimplemented — confirm against `seed_demo.py` before relying on them.
- 44 TypeScript errors and 16 frontend test failures, both long-standing baselines, still untriaged (audit `H9` / `M11`).

**Risks:**

- **Railway does not auto-deploy on push.** It sat at `0064` for hours after `0065`–`0069` were pushed and only caught up on the next deploy. Anything that assumes "main is deployed" will be wrong sometimes — check `railway deployment list` and the live `alembic_version`.
- **Every Railway account shares the password `password123`**, including the superuser. Fine for a demo nobody depends on; not fine the moment Railway's role is settled as anything more.
- **Deleting loan rows with raw SQL strands budget**, exactly as deleting an offer row does. This bit twice this session — a manual cleanup left a club carrying a stale £54,000 wage reservation. Unwind through the API, or fix the finance rows in the same statement.
- The loan return path is the **only** thing in the product that can turn a squad player into a free agent (when the parent contract expired mid-loan). Offer validation refuses a loan that outlasts the parent contract specifically to keep it unreachable — don't relax that rule without replacing the protection.

**Recommended next task:**

1. **`docker compose build frontend`, then look at the loan UI on a real device.** It is the only way to see any of this session's or the previous session's frontend work, and it also settles the unconfirmed iPadOS ≤ 16.1 assumption behind the `color-mix` fallback.
2. **Then decide the seller-counter reservation question** — it is the one open item that is genuinely about money and genuinely blocked on a product call rather than on effort.

## Related documents

- [`PRODUCT_SPEC.md`](./PRODUCT_SPEC.md) — read this first, then this file
- [`CHANGELOG.md`](./CHANGELOG.md) — full change history
- [`IMPLEMENTATION_STATUS.md`](./IMPLEMENTATION_STATUS.md) — current verified build status
