---
title: "ADR 0005: A Loan Separates Registration From Ownership, Without A Second Active Contract"
last_updated: 2026-08-25
status: Accepted
owner: "TODO — assign a Technical Lead"
---

# ADR 0005: A Loan Separates Registration From Ownership, Without A Second Active Contract

## Context

A loan needs two simultaneous club relationships for one player: the **parent** club still owns him, and the **loanee** club registers and plays him. Every other transfer TransferX models has exactly one.

The obvious implementation — two active `Contract` rows, one per club, distinguished by a type flag — collides with an invariant that runs through the whole player model. `normalize_player_status` resolves the active contract with `scalar_one_or_none()` (`players/service.py:47`):

```python
active = result.scalar_one_or_none()
```

Two active rows do not merely produce an ambiguous answer there — they raise `MultipleResultsFound`. And that function is called after **every** contract change, so the failure would surface far from the loan code that caused it. `Player.current_club_id`, `PlayerStatus`, the squad endpoint, wage aggregation and the contract-cliff report all derive from that single-active-contract assumption.

Before this work, loans were half-built: `Deal` had carried `loan_start`, `loan_end`, `loan_fee`, `option_to_buy` and `obligation_to_buy` since TRA-56, and the deal room could edit them — but `_complete_deal` never branched on `deal_type`. A "loan" completing therefore deactivated the seller's contract for good, created one for the buyer, credited the full fee, and released the seller's whole wage commitment. The parent club was left with no contract, no wage liability and no claim on a player they still owned, and nothing anywhere could return him.

## Decision

**The single-active-contract invariant is preserved exactly as it is. A new `player_loans` row is what says who owns the player.**

During a loan:

- the **loanee** holds the one active `Contract`, ending on the loan's end date — so `current_club_id`, the squad list, and the wage bill are all correctly theirs, with no changes to any of those code paths;
- the parent's contract is **suspended** (`is_active = false`), not deleted, and its id is recorded on the loan as `parent_contract_id`;
- `get_owning_club_id` checks for an active loan **before** falling back to `current_club_id`, and returns the parent.

That last point is load-bearing rather than cosmetic. `sales/router.py` and `offers/service.py` both gate on `get_owning_club_id`, so without it the club a player is on loan at could list and sell a player they do not own.

`parent_contract_id` is what makes the return a **restore** of the agreement the parent already had — its real wage and its real end date — rather than a new contract with guessed terms.

## Alternatives considered

**Two active contracts with a `contract_type` discriminator.** Rejected: it turns `scalar_one_or_none()` into a hard exception and forces an audit of every query that assumes one active contract. A large, high-risk change to the most load-bearing invariant in the player model, in exchange for a marginally more "natural" data shape.

**A `parent_club_id` column on `Player`.** Simpler, but it records only the fact of a loan, not its terms, dates, wage split, or the contract to restore — all of which have to live somewhere, and a loan is a real entity with a lifecycle rather than an attribute of a player.

**Keeping the loan's state on the `Deal`.** The deal is the *agreement*; the loan is the *ongoing state* that agreement produced, and it outlives the deal reaching `COMPLETED`. Conflating them would mean querying completed deals to answer "who is out on loan right now".

## Consequences

- Loans are invisible to any code that only reads contracts — which is most of the app, and is the point. Squad views, wage aggregation and the contract cliff needed no changes.
- A player out on loan **disappears from his parent's squad endpoint**, because he genuinely is not registered there. `MyClubPage`'s "Out on loan" panel exists to compensate, reading `GET /clubs/me/loans` rather than the squad.
- Ending a loan is a single function (`end_loan`) with a reason, because running to term, an early recall, the parent selling him, and the loanee buying him all unwind the same finance and the same contracts. Its `restore_parent=False` mode covers the cases where the player is *not* going home and the caller is about to create the new owner's contract — restoring the parent's there would briefly produce the two-active-contract state this ADR exists to avoid.
- **If the parent's contract expires during the loan, the player becomes a free agent on return** rather than having a dead contract resurrected. This is the only path in the feature that can turn a squad player into a free agent, which is why offer validation refuses a loan that outlasts the parent contract — the rule exists specifically to keep this path unreachable in normal use.

## Related documents

- [`../../feature_spec/loan-transfers.md`](../../feature_spec/loan-transfers.md) — the full specification, including the decisions log (D1–D8) and the per-phase deviations
- [`0001-vendor-data-never-overrides-transferx-contract.md`](./0001-vendor-data-never-overrides-transferx-contract.md) — the related invariant that `current_club_id` is only ever derived from an active contract
- [`../data-model.md`](../data-model.md) — entity definitions
