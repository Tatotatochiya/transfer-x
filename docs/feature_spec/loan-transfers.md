---
title: "Feature Spec: Loan Transfers"
last_updated: 2026-08-24
status: Active
owner: "TODO — assign a Product Owner"
---

# Feature Spec: Loan Transfers

## Purpose

Make a loan a **first-class kind of offer**, negotiated as a loan from the first approach, and make the workflow after acceptance actually execute one — including the part that does not exist today at all: **the player coming back**.

A club should be able to open an approach as *"we want him on loan until May, we'll pay 60% of his wages, £2m fee, with an option to buy at £18m"*, have the selling club negotiate those terms as terms, and have the platform then run the loan for its duration and return the player to his parent club when it ends.

This document is written for an implementer (human or AI agent) with **no access to the conversation that produced it**.

## How to use this document

Read [Current state](#current-state--verified-against-code-2026-08-24) first: loans are **partially built**, and the half that exists is misleading, because a loan can be typed into the deal room today and will then execute as a permanent transfer. Then read [Decisions](#decisions--proposed-needing-sign-off) — several are genuine product calls and are marked as needing sign-off before implementation starts, per [`engineering-standards`](../../.claude/skills/engineering-standards/SKILL.md) §4.

## Product context

A loan is not a discount transfer; it is a different contract shape with a different risk profile, and it is roughly a third of real transfer-window activity. Three parties care about different things:

- **Loanee club** — squad depth now, at a wage cost rather than a fee, with no long-term commitment.
- **Parent club** — development minutes for a player who is not playing, with the wage bill partly or wholly off the books, and the asset retained.
- **Player/agent** — game time.

The platform already models the *money* of a loan (`loan_fee`, `option_to_buy`, `obligation_to_buy`) and none of the *mechanics* (who owns him, who pays his wages, when does he come back).

## Current state — verified against code, 2026-08-24

Read against the working tree at commit `db11731`. Line references are to that commit.

### What already exists

| Thing | Where | State |
|---|---|---|
| `DealType` enum — `PERMANENT`, `LOAN`, `FREE_TRANSFER`, `PRE_CONTRACT` | `backend/app/deals/models.py:29` | Complete |
| Loan fields on `Deal` — `loan_start`, `loan_end`, `loan_fee`, `option_to_buy`, `obligation_to_buy`, `obligation_conditions` | `backend/app/deals/models.py:87-99` (TRA-56) | Columns exist, migration applied |
| Deal-room editor for those fields | `frontend/src/pages/deals/DealDetailPage.tsx:1239-1290` | Works, `AGREEMENT` stage only |
| `update_deal` persists them + versions the change | `backend/app/deals/service.py:1076` | Works |
| Completion prefers `loan_fee` over `agreed_fee` for a `LOAN` | `backend/app/deals/service.py:693-697` | Works |

### What is missing or wrong

**1. An offer cannot be a loan.** `Offer` (`backend/app/offers/models.py:35-86`) has `fee_amount`, `wage_weekly`, `contract_years`, `contract_end_date`, `add_ons` — and no type discriminator and no loan fields. A loan is therefore negotiated as if permanent and **retyped after the seller has already accepted it**, in the deal room. The seller agrees to one thing and gets asked to run another.

**2. Every offer-originated deal is `PERMANENT`.** `accept_offer` constructs `Deal(...)` at `backend/app/offers/service.py:369` without passing `deal_type`, so the column default applies. Even the deliberate "No fee" path added for free transfers produces a deal labelled Permanent.

**3. The frontend `DealType` is missing two values the backend emits.** `frontend/src/types/enums.ts:46` is `"PERMANENT" | "LOAN"`, but `players/service.py:224` and `:284` create `FREE_TRANSFER` and `PRE_CONTRACT` deals. `DealDetailPage.tsx:1148` renders `deal_type === "LOAN" ? "Loan" : "Permanent"`, so **every free-agent signing displays as "Permanent"** in the deal room. This is a live mislabel, independent of loans.

**4. A loan reserves no money.** `backend/app/offers/service.py:173` is `reserve = (fee_amount or Decimal("0")) + _add_ons_total(add_ons)`, guarded by `if reserve > 0`. A loan sent as "No fee" reserves **£0** and, being below any threshold, never escalates for approval either (`approvals/service.py:48` treats a null amount as zero — correct for a real free transfer, wrong for a loan). Separately and more broadly: `reserve_budget` already takes a `wage_weekly` argument (`backend/app/clubs/service.py:396-400`) that **`create_offer` never passes**, so *no* offer of any type has ever reserved wage budget. For a loan the wage *is* the cost.

**5. Completion executes a permanent transfer regardless of `deal_type`.** `_complete_deal` (`backend/app/deals/service.py:682`) unconditionally:

- deactivates the seller's active contract (`:755`),
- calls `players_service.create_contract` for the buyer (`:809`), which itself deactivates **all** remaining active contracts (`players/service.py:602`),
- credits the full fee to the seller's `transfer_budget_total`,
- releases the seller's entire wage commitment for that player.

So a completed loan leaves the parent club with **no contract, no wage liability, and no claim on the player**, and the loanee owning him outright. There is no return, no recall, and no expiry — the loan is a permanent transfer that happens to have dates typed on it.

**6. The data model permits exactly one club relationship per player.** `normalize_player_status` derives `status` and `current_club_id` from a single active contract using `scalar_one_or_none()` (`players/service.py:47`) — two active contracts would raise `MultipleResultsFound`, not merely misbehave. A loan needs two simultaneous relationships (parent owns, loanee registers). **This is the central architectural decision** and is resolved in [D1](#d1--loan-state-lives-in-a-playerloan-row-not-a-second-active-contract).

**7. During a loan, the wrong club could sell the player.** `get_owning_club_id` (`players/service.py:101`) returns `player.current_club_id`, which after a loan completes is the loanee. `sales/router.py:216` and `offers/service.py:350` both gate on it, so the **loanee could list and sell a player they do not own**.

**8. No scheduled job touches loans.** Nine jobs are registered (`backend/app/main.py:173-206`); none expire, return, or convert a loan.

**9. No wage-split field anywhere.** Real loans split the wage between parent and loanee. Neither `Offer` nor `Deal` can express it.

## Scope

### In scope

- Loan as an offer type, chosen at approach time, negotiable through counters.
- Wage split between parent and loanee, budgeted correctly on both sides.
- Loan execution on completion: registration moves, ownership does not.
- Loan **return** at `loan_end`, automated.
- Early **recall** by the parent club, when the agreed terms allow it.
- **Option to buy** exercised by the loanee before expiry; **obligation to buy** executed automatically at expiry.
- Fixing gaps 2, 3, 4 and 7 above, which loans expose but which are not loan-specific.

### Out of scope (v1)

- **Loan-specific transfer windows.** Real football has separate domestic loan windows; TransferX has one window model (`transfer_window/service.py:48`). Loans use the same gate. Revisit when windows are per-competition.
- **Sub-loans** (loanee loaning the player on again). Explicitly rejected: the ownership chain gets ambiguous and no user has asked.
- **Recall clauses tied to appearance counts.** `recall_allowed` is a boolean in v1, not a condition engine. The existing `DealClause` machinery is the natural home if this is ever wanted.
- **Wage split changing mid-loan.**
- **Loan-to-loan conversion** (converting a permanent deal in progress into a loan) — the offer carries the type from the start.

## Decisions — proposed, needing sign-off

Marked **[SIGN-OFF]** where the call is genuinely the product owner's and the implementation should not start until it is made. Marked **[PROPOSED]** where I am confident enough to build it unless told otherwise.

### D1 — Loan state lives in a `PlayerLoan` row, not a second active contract
**[PROPOSED]**

The alternative — two simultaneous active `Contract` rows, one flagged as a loan — breaks `normalize_player_status`'s `scalar_one_or_none()` (`players/service.py:47`) into a hard exception, and every query in the codebase that assumes one active contract would need auditing. That is a large, high-risk change to the most load-bearing invariant in the player model.

Instead: **the single-active-contract invariant is preserved exactly as it is.** A new `player_loans` row is the record of the loan, and it holds the pointer back to the parent's suspended contract so the return is a restore, not a reconstruction.

During a loan: the **loanee** holds the one active contract, so `current_club_id` is the loanee and the player correctly appears in their squad, in their wage bill, and in their team sheet. **Ownership is answered by the loan row, not the contract** — `get_owning_club_id` gains a loan check ahead of its existing logic (see [D3](#d3--ownership-during-a-loan-is-the-parent-club)).

### D2 — The offer reuses `DealType`, restricted to `{PERMANENT, LOAN}` at the schema boundary
**[PROPOSED]**

A dedicated two-value `OfferType` would make the invalid states unrepresentable, which is the stronger typing argument. Reusing `DealType` wins on a different axis: `accept_offer` copies the value straight onto the `Deal` with no mapping table to drift out of sync, and the deal room's existing PERMANENT/LOAN toggle already speaks `DealType`. One enum, one migration, no translation layer.

The cost is that `OfferCreateRequest` must reject `FREE_TRANSFER` and `PRE_CONTRACT` explicitly — those are *derived* deal types created by the free-agent and pre-contract paths (`players/service.py:224`, `:284`), never offered. A validator, not a type.

### D3 — Ownership during a loan is the parent club
**[PROPOSED]**

`get_owning_club_id` returns the **parent** club for the duration. Consequences, all intended:

- The loanee **cannot** list, sell, or accept offers for the player. Closes gap 7.
- The parent **can** — a club may sell a player who is out on loan, which is realistic. Doing so triggers loan termination (see [D6](#d6--selling-a-player-who-is-out-on-loan-terminates-the-loan)).
- `MyClubPage` shows the player under an **"Out on loan"** group for the parent and in the normal squad for the loanee.

### D4 — Wage split is a single percentage, loanee's share, `0.0`–`1.0`
**[SIGN-OFF]**

`wage_split_pct = 0.60` means the loanee pays 60% of the player's weekly wage and the parent keeps 40%. Default `1.00` (loanee pays all), which is the common case and matches today's implicit behaviour.

**Needs sign-off because the alternative is materially different:** an absolute weekly figure (`loanee_wage_weekly = £45,000`) rather than a percentage. A percentage automatically tracks a wage renegotiation mid-loan; an absolute figure is what clubs actually agree in the room and is unambiguous when the wage is itself uncertain. I recommend the **percentage** for consistency with `sell_on_pct` and `agent_commission_pct`, which are both already fractions (see the carried-forward gotcha: *`commission_pct` is a fraction, not a percentage*).

### D5 — The loan fee is reserved and committed like a transfer fee; the wage share is reserved as wage budget
**[PROPOSED]**

On send: `reserve_budget(transfer_amount = loan_fee + add_ons, wage_weekly = wage_weekly * wage_split_pct)`. On accept: `commit_budget` with the same two figures. On completion: transfer moves committed → spent, wage moves committed → reserved for the loan's duration.

This also fixes gap 4's second half for **permanent** offers, which have never reserved wage budget either. That is a behaviour change to existing permanent offers and should land as its own commit with its own note — a club with a full wage bill will start being correctly refused offers it could previously send.

### D6 — Selling a player who is out on loan terminates the loan
**[SIGN-OFF]**

If the parent club completes a permanent sale of a loaned-out player, the loan ends at the moment the sale completes and the player moves to the new owner.

**Needs sign-off** because the fair alternative is to block the sale outright until the loan expires, and the realistic third option — the loan survives and the new owner inherits it — is a much larger build (the loan's parent club changes mid-flight). I recommend **terminate**, with the loanee notified, because blocking makes a loaned player unsellable for up to a year and inheriting is out of proportion to the demand.

### D7 — Obligation-to-buy executes automatically; option-to-buy does not
**[PROPOSED]**

At `loan_end`, if `obligation_to_buy` is true, the platform creates a `PERMANENT` deal at `option_to_buy` between the same two clubs and runs it through the normal deal flow — it was already agreed, so it does not need re-negotiating, but it **does** need the normal budget checks, medical, and paperwork stages. If the loanee cannot fund it at that point, the deal collapses like any other and is a matter between the clubs.

An **option** is exercised by an explicit loanee action before `loan_end`, never automatically.

### D8 — A loan return is not a transfer and is not window-gated
**[PROPOSED]**

`is_transfer_allowed` gates loan *creation*, exactly as it gates offers and sales today. It does **not** gate the return, recall, or expiry: a loan ending is the contract running its course, and blocking it outside a window would strand players at the wrong club indefinitely.

## Data model

Three migrations' worth of change; no existing column is dropped or repurposed.

### New table: `player_loans`

```
id                   uuid PK
player_id            uuid FK players    NOT NULL  index
deal_id              uuid FK deals      NOT NULL  index   -- the LOAN deal that created it
parent_club_id       uuid FK clubs      NOT NULL  index
loanee_club_id       uuid FK clubs      NOT NULL  index
parent_contract_id   uuid FK contracts  NULL              -- the contract suspended at loan start, restored at end
loanee_contract_id   uuid FK contracts  NULL              -- the contract created for the loanee
start_date           date               NOT NULL
end_date             date               NOT NULL  index   -- the expiry job keys off this
loan_fee             numeric(15,2)      NULL
wage_split_pct       numeric(5,4)       NOT NULL  default 1.0000
option_to_buy        numeric(15,2)      NULL
obligation_to_buy    boolean            NOT NULL  default false
recall_allowed       boolean            NOT NULL  default false
status               loanstatus         NOT NULL  index
ended_at             timestamptz        NULL
end_reason           varchar(30)        NULL              -- EXPIRED | RECALLED | OPTION_EXERCISED | OBLIGATION | PARENT_SOLD
created_at           timestamptz        NOT NULL
```

`loanstatus` enum: `ACTIVE`, `COMPLETED`, `RECALLED`, `CONVERTED`.

`parent_contract_id` is the load-bearing field: it is what makes the return a **restore** of the agreement the parent already had, rather than an invented new one with guessed wage and end date.

### `offers` — new columns

```
deal_type            dealtype           NOT NULL  default 'PERMANENT'  server_default 'PERMANENT'
loan_start           date               NULL
loan_end             date               NULL
loan_fee             numeric(15,2)      NULL
wage_split_pct       numeric(5,4)       NULL
option_to_buy        numeric(15,2)      NULL
obligation_to_buy    boolean            NOT NULL  default false
recall_allowed       boolean            NOT NULL  default false
```

Backfill: every existing offer is `PERMANENT`, which is what they all were.

### `deals` — new columns

```
wage_split_pct       numeric(5,4)       NULL
recall_allowed       boolean            NOT NULL  default false
```

The other loan fields already exist (TRA-56).

### Validation rules

Enforced in `OfferCreateRequest`/`OfferCounterRequest` **and** re-checked in `offers/service.py`, per the house pattern of never trusting the schema layer alone:

| Rule | Applies to |
|---|---|
| `deal_type` ∈ {`PERMANENT`, `LOAN`} | all offers |
| `loan_start`, `loan_end` required and `loan_end > loan_start` | `LOAN` |
| `loan_end` ≤ 18 months from `loan_start` | `LOAN` |
| `wage_split_pct` ∈ [0, 1] | `LOAN` |
| `fee_amount` must be null | `LOAN` — the loan's money is `loan_fee` |
| `loan_*`, `option_to_buy`, `obligation_to_buy`, `recall_allowed` must be null/false | `PERMANENT` |
| `obligation_to_buy = true` requires `option_to_buy` set | `LOAN` — an obligation needs a price |
| `loan_end` must not exceed the player's parent contract `end_date` | `LOAN` — you cannot loan a player past the point you control him |

That last rule is the one most likely to surprise: it needs the parent's active contract read at offer-creation time, and it should produce a specific error message naming the contract end date, not a generic 422.

## Lifecycle

```
                 OFFER (deal_type = LOAN)
                        │  reserve: loan_fee + add_ons  |  wage_weekly x wage_split_pct
                        ▼
                   negotiate / counter        ── terms stay a loan throughout ──
                        │
                        ▼  accept  → commit_budget, Deal(deal_type=LOAN) created
                   DEAL: AGREEMENT → …existing stages… → CONFIRMED
                        │
                        ▼  complete
        ┌───────────────────────────────────────────────────────┐
        │ _complete_deal branches on deal_type                  │
        │  LOAN:  suspend parent contract (record its id)       │
        │         create loanee contract, end_date = loan_end   │
        │         create player_loans row, status ACTIVE        │
        │         loanee wage: committed → reserved (share)     │
        │         parent wage: reduced by the share ONLY        │
        │         loan_fee: buyer committed → spent,            │
        │                   credited to parent's budget         │
        └───────────────────────────────────────────────────────┘
                        │
                   LOAN ACTIVE  ── player in loanee squad, owned by parent ──
                        │
        ┌───────────────┼────────────────┬──────────────────────┐
        ▼               ▼                ▼                      ▼
   end_date reached  parent recalls  loanee exercises      parent sells him
   (nightly job)     (if allowed)    option (before end)   (D6)
        │               │                │                      │
        ▼               ▼                ▼                      ▼
    EXPIRED         RECALLED       CONVERTED →           CONVERTED /
        │               │          new PERMANENT deal     loan terminated
        └───────┬───────┘                │                      │
                ▼                        ▼                      ▼
        RETURN TO PARENT           normal deal flow      normal deal flow
   deactivate loanee contract
   reactivate parent contract (or free agent if it expired)
   wage: loanee releases share, parent restores full
```

### The return, precisely

`return_player_from_loan(db, loan, *, reason)` — one function, called by the expiry job, the recall endpoint, and the sale path:

1. Deactivate the loanee's contract (`loanee_contract_id`).
2. Loanee finance: `wage_reserved_weekly -= wage_weekly * wage_split_pct`, clamped at zero.
3. Parent contract: if `parent_contract_id` still has `end_date >= today` (or null), set `is_active = True` and restore `wage_reserved_weekly += the parent's own wage` on the parent's finance. **If the parent contract expired during the loan**, do not resurrect it — the player becomes a free agent, which is correct and is a real outcome clubs need to see coming.
4. `normalize_player_status(db, player)` — one active contract again, invariant intact.
5. `loan.status`, `loan.ended_at`, `loan.end_reason`.
6. Notify both clubs. New `NotificationType` values: `LOAN_STARTED`, `LOAN_ENDING_SOON`, `LOAN_ENDED`, `LOAN_RECALLED`. Per the carried-forward gotcha, a new `NotificationType` has several touchpoints — check them all.

**Step 3's expiry case is the one to write a test for first.** It is the only path that can silently turn a squad player into a free agent, and it is reachable whenever `loan_end` is close to the parent contract's end.

### Scheduled job

`_loan_lifecycle_job`, registered in `backend/app/main.py` alongside the existing nine, `interval, hours=24`, with the `next_run_time` offset the others use so it runs on boot rather than 24 hours later — the comment at `main.py:170` explains why that matters here.

Per run:
- `end_date <= today` and `status = ACTIVE` → return, unless `obligation_to_buy`, in which case convert (D7).
- `end_date` within 14 days → `LOAN_ENDING_SOON` to both clubs, once (guard on a notification already existing, the way `_notify_upcoming_events_job` does).

## API

All routes club-scoped to the authenticated caller's own club, reusing `clubs_service.get_club_for_user`.

**Changed — `POST /offers`** gains the fields in [Data model](#offers--new-columns). Response gains them too.

**Changed — `PATCH /offers/{id}/counter`** may change loan terms but **not** `deal_type`. Countering a loan with a permanent offer is a different offer; the seller should reject and the buyer re-approach. Stated explicitly because the temptation to allow it is real and it makes the audit trail incoherent.

**New — `GET /clubs/me/loans?direction=out|in&status=`** — loans where this club is parent (`out`) or loanee (`in`). Feeds the "Out on loan" squad group and the loanee's own view.

**New — `POST /loans/{id}/recall`** — parent club only, `recall_allowed` must be true, `status` must be `ACTIVE`. Calls the return path with `RECALLED`. Not window-gated (D8).

**New — `POST /loans/{id}/exercise-option`** — loanee club only, `option_to_buy` must be set, before `end_date`. Creates a `PERMANENT` deal at `option_to_buy` and marks the loan `CONVERTED`. Budget is checked at creation like any deal; failure returns 400 with the shortfall, and the loan stays `ACTIVE`.

**New — `GET /loans/{id}`** — either party or staff.

Permission-boundary tests for every one of these: a third club gets 404, the loanee gets 403 on recall, the parent gets 403 on exercise-option.

## UI

### Create Offer page (`frontend/src/pages/offers/CreateOfferPage.tsx`)

The existing **Transfer fee / No fee** control (added when the blank-fee 500 was fixed) becomes a three-way **deal type** choice at the top of the form, because it is the same decision:

```
  What are you proposing?
  ( ) Permanent transfer     ( ) Loan
```

Choosing **Permanent** shows today's form unchanged, including the existing Transfer fee / No fee sub-choice.

Choosing **Loan** swaps the fee block for: loan start, loan end, loan fee (optional), wage split (a percentage input defaulting to 100%, with the resulting weekly figure shown live beneath it — *"You pay £54,000/wk of £90,000"*), option to buy (optional), obligation to buy (checkbox, disabled until an option price is entered, per the validation rule), recall allowed (checkbox).

The live weekly figure matters: a percentage is an abstraction and clubs budget in pounds. Follow `formatCurrency`, and note that its full-precision output is a single unbreakable token — the recently-fixed tier-2 overflow was exactly this.

### Deal room (`DealDetailPage.tsx`)

The existing loan editor stays but becomes **read-only for `deal_type`** — the type now arrives from the offer and must not be mutated post-acceptance, which is the defect that motivated this spec. The loan *terms* remain editable at `AGREEMENT` stage as they are today.

**Fix the enum drift while here** (gap 3): `frontend/src/types/enums.ts:46` gains `FREE_TRANSFER` and `PRE_CONTRACT`, and `DealDetailPage.tsx:1148`'s ternary becomes a lookup so a free-agent signing stops rendering as "Permanent". This is a one-line-each fix to a live mislabel and does not depend on the rest of this spec — **it can and should ship first, on its own.**

### My Club (`MyClubPage.tsx`)

- Parent: an **"Out on loan"** group below the squad — player, loanee club, return date, wage share retained, and a **Recall** button when `recall_allowed`.
- Loanee: loaned players appear in the normal squad with a **"On loan"** chip and the return date, and **no** sell/list affordances (the server already refuses; the UI should not offer it).

### Player market

A player out on loan shows an "On loan at X until May 2027" line on his detail page. He remains searchable — a club may legitimately want to approach his parent about next season.

## Worked examples

### A — Straight loan, runs to term

Chelsea loan A. Garnacho (wage £90,000/wk) from Man Utd. Terms: 2026-08-24 → 2027-05-31, loan fee £2,000,000, wage split 60%, no option, no recall.

| Point | Chelsea (loanee) | Man Utd (parent) |
|---|---|---|
| Offer sent | `transfer_reserved += 2,000,000`; `wage_reserved_weekly += 54,000` | — |
| Accepted | reserved → committed, both figures | — |
| Completed | `transfer_committed -= 2,000,000`, `transfer_spent += 2,000,000`; wage committed → reserved (54,000) | `transfer_budget_total += 2,000,000`; `wage_reserved_weekly` drops by 54,000 to 36,000 |
| During | Garnacho in Chelsea squad, `current_club_id` = Chelsea, **owned by Man Utd** | Shows under "Out on loan" |
| 2027-05-17 | `LOAN_ENDING_SOON` | `LOAN_ENDING_SOON` |
| 2027-05-31 | contract deactivated, `wage_reserved_weekly -= 54,000` | parent contract reactivated, `wage_reserved_weekly += 54,000` back to 90,000 |

### B — Obligation to buy

Same, plus `option_to_buy = £18,000,000`, `obligation_to_buy = true`. At `loan_end` the job creates a `PERMANENT` deal, Chelsea → Man Utd, agreed fee £18m, and the loan goes `CONVERTED`. The player does **not** return to Man Utd in the interim; he stays registered at Chelsea while that deal runs, and the deal's own collapse path handles a Chelsea that cannot fund it.

### C — Parent contract expires mid-loan

R. Calafiori's Arsenal contract ends 2027-06-30. A loan to 2027-05-31 is fine. A loan to 2027-08-31 is **rejected at offer creation** by the last validation rule, naming the contract end date. Without that rule the return path at step 3 would find an expired parent contract and correctly — but very surprisingly — make him a free agent.

## Success criteria

Backend:

1. An offer with `deal_type=LOAN` and no `loan_start`/`loan_end` is rejected 422 with a message naming the missing field.
2. A loan offer for a player whose parent contract ends before `loan_end` is rejected 422 naming the contract end date.
3. Sending a loan offer reserves `loan_fee + add_ons` transfer **and** `wage_weekly × wage_split_pct` weekly wage; a club without the wage room is refused.
4. A permanent offer now also reserves wage — with a test asserting the previously-unreserved case is now reserved (the D5 behaviour change).
5. Accepting a loan offer produces a `Deal` with `deal_type = LOAN` and the terms copied across. Accepting a permanent offer produces `PERMANENT`, and the free-agent path still produces `FREE_TRANSFER`.
6. Completing a loan deal creates a `player_loans` row, leaves the parent contract row present-but-inactive with its id recorded, creates a loanee contract ending at `loan_end`, and leaves exactly **one** active contract (assert `normalize_player_status` does not raise).
7. During an active loan, `get_owning_club_id` returns the parent; the loanee gets 400 on `POST /sales` and on accepting an offer for that player.
8. The expiry job returns a player whose `end_date` has passed: loanee contract inactive, parent contract active again, both wage figures restored, `status = COMPLETED`.
9. A loan whose parent contract expired during it leaves the player a `FREE_AGENT`, not a crash and not a resurrected contract.
10. Recall works for the parent when `recall_allowed`, 403 for the loanee, 400 when not allowed.
11. `obligation_to_buy` creates a `PERMANENT` deal at expiry; `option_to_buy` alone does not.
12. Permission boundaries on all four new endpoints.
13. Full backend suite still passes — currently **455**.

Frontend:

14. The offer form cannot submit a loan without dates; the wage-split percentage renders its pound figure live.
15. A `FREE_TRANSFER` deal renders "Free transfer", not "Permanent" (gap 3).
16. `tsc -b --noEmit --force` stays at **44** or lower; `vitest` failures stay within the `BASELINE.md` list of 23 (currently 16).

## Phasing

Each phase is independently shippable and leaves the app coherent.

| Phase | Content | Why this order |
|---|---|---|
| **0** | Frontend `DealType` enum drift (gap 3) | One line each, fixes a live mislabel, zero dependencies. Ship today. |
| **1** | `deal_type` on `Offer` + copy it in `accept_offer` + wage reservation for all offers (gaps 2, 4) | Makes the existing model honest before adding to it. No loan mechanics yet — a `LOAN` offer at this point still completes as a permanent transfer, so **do not expose the UI toggle until phase 3.** |
| **2** | `player_loans` table, `_complete_deal` branch, `get_owning_club_id` (gaps 5, 6, 7) | The mechanics. Loans now execute correctly but only end manually. |
| **3** | Expiry job, return path, recall, notifications (gap 8) + the Create Offer UI | The loan now runs to term on its own. Safe to expose. |
| **4** | Option to buy, obligation to buy (D7) | Genuinely optional; a loan is complete and useful without it. |

## Open questions for sign-off

1. **D4** — wage split as a percentage, or an absolute weekly figure?
2. **D6** — selling a loaned-out player: terminate the loan (recommended), or block the sale?
3. Should a loan offer be possible for a player **not** flagged `open_to_offers`? Today an offer can be sent to any owned player; loans are often speculative, so I have assumed **yes, unchanged**, but it is worth confirming this does not open a spam vector.
4. Is 18 months the right maximum loan length? It is a guess at a sensible bound, not a rule taken from anywhere.

## Related documents

- [`../architecture/backend-architecture.md`](../architecture/backend-architecture.md) — module boundaries this spec adds to
- [`fair-value-vs-asking-signal.md`](./fair-value-vs-asking-signal.md) — sibling spec; its D5/D7 copy and confidentiality rules apply to any loan figures shown
- [`club-team-roles-and-onboarding.md`](./club-team-roles-and-onboarding.md) — D7 approval thresholds, which loan money must respect
- [`../CHANGELOG.md`](../CHANGELOG.md) — the blank-fee 500 fix and the Transfer fee / No fee control this spec's offer form builds on
