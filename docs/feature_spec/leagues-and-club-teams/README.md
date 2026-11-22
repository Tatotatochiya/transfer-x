---
title: "Leagues and club teams: the EFL, and a club's first and women's teams"
last_updated: 2026-11-22
status: Draft
owner: "TODO — assign a Product Owner"
---

# Leagues and club teams

## Purpose

This spec covers two related changes:

1. **The rest of the English pyramid.** It adds the Championship, League One and League Two to TransferX.
2. **One club, several teams.** A club such as Chelsea is one organisation, with its first team and its women's team under it.

It also lays out the business decisions these changes depend on, with a recommendation for each.

**Status: Draft.** Nothing here is built. Sections 3 and 4 list the decisions to make before Phase B starts. Phase A can start once decision D1 is made.

## Scope

**In scope:**
- the Championship, League One and League Two as data and as a market;
- a club as an organisation with teams;
- the first team and the women's team.

**Out of scope:**
- other leagues and countries (the same approach would apply);
- pricing and billing implementation;
- loans between a club's own teams.

## Table of Contents

1. [Summary](#1-summary)
2. [How TransferX works today](#2-how-transferx-works-today)
3. [Fit with the business model](#3-fit-with-the-business-model)
4. [Decisions needed](#4-decisions-needed)
5. [Phase A: the EFL leagues](#5-phase-a-the-efl-leagues)
6. [Phase B: a club has teams](#6-phase-b-a-club-has-teams)
7. [Phase C: women's teams](#7-phase-c-womens-teams)
8. [What stays the same](#8-what-stays-the-same)
9. [Risks](#9-risks)
10. [Success criteria](#10-success-criteria)
11. [Related documents](#11-related-documents)

---

## 1. Summary

| Phase | What | Changes the data model? | Size |
|---|---|---|---|
| **A** | Championship, League One and League Two: data, valuation, market | No | Small to medium |
| **B** | A club is an organisation with **teams**. Every existing club gets one first team. Contracts, deals and budgets belong to a team. Each team has an explicit link to its real-world team | Yes (significant migration) | Large |
| **C** | **Women's teams** on that model, with their own competitions, windows, valuation and market | Small additions on top of B | Medium to large |

**Order.** Phase A doesn't depend on B. Phase C depends on B. B is worth doing before any club with a women's team signs up, so that club's account doesn't have to be split later.

The model decision is recorded as a proposal in [product ADR 0013](../../product/decisions/0013-a-club-is-an-organisation-with-teams.md).

---

## 2. How TransferX works today

Verified in the code on 22 November 2026.

| Area | Today | Where |
|---|---|---|
| **Club** | One organisation with one team. It has one name, crest and `league_name`, one budget (`ClubFinance`), and one set of staff and roles | `backend/app/clubs/models.py` |
| **Players** | A player belongs to a club through an active contract (`Player.current_club_id`). An active loan gives ownership to the parent club. There is no "team" level | `players/service.get_owning_club_id` |
| **Club and real-world team** | No explicit link. The real-world check works out a club's team from the team most of its players are registered to, then falls back to matching names (`lower(Club.name)`) | `players/real_world.py` |
| **Leagues synced** | Whatever is in `world_leagues`: today the top five leagues plus the Champions League and Europa League. The refresh runs at 17:00 and 22:00 UK | `jobs/daily_refresh.py` |
| **Valuation (`market-v2`)** | A coefficient per API-Football league id. The Championship (40) is 0.36. League One and League Two aren't listed, so they get the default of 0.13, the same as any unknown league. Comparable sales start at £500k (`COMPS_MIN_FEE_GBP`). The v1 model has a £100k minimum (`MIN_FAIR_VALUE_GBP`) | `valuation/constants_v2.py`, `valuation/constants.py` |
| **Transfer windows** | Keyed by the buying club's **country**. A window holds completion only ([product ADR 0010](../../product/decisions/0010-deals-run-all-year-windows-hold-completion.md)) | `transfer_window/service.py` |
| **Anonymous buyer** | Shown as "A {league} club", from the club's domestic `league_name` | `clubs/models.Club.masking_league` |
| **Players' gender** | Not recorded | `players/models.py` |

---

## 3. Fit with the business model

[`business-model.md`](../../business/business-model.md) and [`target-users-and-market.md`](../../business/target-users-and-market.md) both still list pricing and the target segment as open decisions. This section doesn't make those decisions. It shows how each change affects them, so whoever does decide can see the knock-on effects.

### 3.1 Why the EFL matters to a transfer marketplace

- **TransferX is only useful when the other side of a transfer is on it as well.** Today a player at a club that isn't on TransferX can't receive an offer ([15 November review, §5.1](../../reviews/2026-11-15-product-and-readiness-review.md)).
- **Much of an English club's market activity involves EFL clubs.** Premier League clubs:
  - loan young players to the EFL;
  - sell squad players down the divisions;
  - buy the Championship's best players.

  A Premier League pilot club will want to deal with EFL clubs from the first window.
- **EFL clubs have the most to gain from a structured process.** They have small staffs, run many low-value deals and loans, and depend more on add-ons and sell-on clauses. These are the workflows TransferX already models: offers with full terms, loans, sell-ons, add-ons and approvals.
- **But the money is very different.** A League Two club's turnover is typically a few million pounds, and many of its moves are free transfers or loans. A price that suits a Premier League club won't suit a League Two club.

### 3.2 Where the women's game fits

- **A smaller market, but growing.** The women's transfer market is much smaller than the men's but growing. It mostly runs at the same organisations, often through a separate company and budget.
- **Sold as part of the club's account.** If a women's team can sit inside the club's account, the club gets more from one subscription and TransferX reaches the women's game through clubs it already serves. That's an argument for Phase B before Phase C.

### 3.3 What this means for pricing (for the pricing decision)

- **The organisation is the customer; teams are what it uses.** A club is billed once. A second team (the women's team) is either included or an add-on. Either way it's one contract, one owner and one audit trail.
- **Price by division.** Premier League, Championship, League One and Two, and the WSL can't carry the same price. The division comes from the first team's league, which Phase A makes available.
- **EFL clubs as counterparties before customers.** Through the "guest counterparty" or "bring them in" options in the review (§5.1), a non-paying EFL club can answer a transfer. That's the cheapest way to get them onto the platform, and it shows sales which clubs Premier League clubs want to deal with. Phase A makes their players visible and valued, which is what those options need.

---

## 4. Decisions needed

| # | Decision | Options | Recommendation |
|---|---|---|---|
| **D1** | Are EFL clubs customers, or only data and counterparties at first? | (a) Data only: their players appear, are valued and can be shortlisted; offers still need the club on TransferX. (b) Customers: EFL clubs are invited like any club | **(a) for Phase A**, with the "bring them in" option from the review. Invite EFL clubs as customers once pricing by division exists |
| **D2** | What is billed: the club or the team? | Per organisation (teams included or as add-ons); per team | **Per organisation.** The club is the legal and contractual party; teams are what it uses |
| **D3** | Budgets: one per club, or one per team? | One shared budget; one per team, reported together at club level | **One per team, plus a club total.** A women's signing must not use the men's transfer budget, and women's teams often have separate finances. The club owner and Finance see both and the total |
| **D4** | Can staff be limited to one team? | Everyone sees every team; staff can be limited to teams | **Staff can be limited to teams.** The default is all teams, which keeps today's behaviour. A women's general manager sees and acts for the women's team only. The club owner and read-only oversight see all teams |
| **D5** | Women's teams: transact, or scouting only at first? | Full transfers; scouting and data only | **Full transfers in Phase C.** The deal workflow is the same, and scouting-only would sell short the clubs that sign up for it |
| **D6** | One marketplace, or a separate women's market? | Mixed with a filter; separate markets in the same app | **Separate markets in the same app.** Men's and women's players never appear in the same search, valuation or comparison by default, and a team can only make an offer for a player of the same kind |

---

## 5. Phase A: the EFL leagues

No data model change. These leagues are added as data, with valuation and market support.

### 5.1 Data

- **Add the three leagues to `world_leagues`.**
  - The API-Football ids are believed to be 40 (Championship), 41 (League One) and 42 (League Two).
  - Verify each id against API-Football's `/leagues` before seeding, as `valuation/constants.py` already warns.
  - The refresh then syncs them like any other league: squads, stats, injuries, fixtures and transfers.
- **Volume.** That's 72 teams and roughly 1,800 to 2,200 more players.
  - Measure one refresh's request count against the plan's daily limit and the reserve (`APISPORTS_RESERVE`, 500) before turning them on in production.
  - Run the backfill as a one-off, outside the twice-daily refresh.
- **Coverage.** API-Football's lineups, per-player stats and injuries are thinner in League One and League Two.
  - Record what was actually received for one week before trusting it.
  - The valuation's confidence rating already drops when data is thin. Check that it does for these players.
- **Promotion and relegation.** `world_leagues` keeps a season per league, and `update_seasons` moves to the current one. At the end of a season:
  - a club's `league_name` changes;
  - players move between the three leagues;
  - the valuation's league for each player follows the season played.

  Test this with last season's data (the 2025 to 2026 promoted and relegated clubs) before the first real change.

### 5.2 Valuation

- **Add coefficients for League One and League Two.** Today they fall to the default (0.13), which puts League Two on a par with any unlisted league worldwide.
  - Starting values are a judgement until checked against real fees. For example, League One about half the Championship and League Two about half of League One.
  - Calibrate them with the existing backtest scripts once fees for these leagues are available.
- **Lower the floor for these leagues.**
  - Comparable sales start at £500k, and v1's minimum value is £100k.
  - Many League One and League Two players move for less, or on a free.
  - Allow a value below £100k for players whose latest league is League One or Two, and show "free transfer likely" when the model's value is below a set amount and the contract has under a year to run.
- **Show less certainty, not invented precision.** Where data is thin, show the value as a range with low confidence, as the model already does elsewhere.

### 5.3 Market and product

- **Filters.**
  - The market and search gain a division filter: Premier League, Championship, League One, League Two, and other.
  - The default for a club is its own division and the ones either side.
  - "Browse all" stays one click away.
- **Anonymous buyer.** "A League Two club" narrows the field to 24 clubs. That's acceptable (the same as a Premier League club today, from 20), but show the buying club, before it sends anonymously, which league will be shown.
- **Players at EFL clubs not on TransferX.** Their page says their club isn't on TransferX, as now. Add the review's "Ask TransferX to bring them in" button (§5.1, option 1). It records the interest and shows staff the demand for each club.
- **Demo mode.** No change. The house clubs stay as they are. An EFL house club can be added later if demos need one.

### 5.4 Not in Phase A

- EFL clubs signing up as customers (decision D1).
- EFL-specific rules: League Two's salary cap, the EFL's own registration steps, and solidarity payments. These belong with Phase 2 and Phase 4 of the [phased plan](../phased-plan-2026-q4/README.md).

---

## 6. Phase B: a club has teams

### 6.1 The model

```
Club (organisation)                 Team (squad that plays in a competition)
  name, crest, country                club_id → Club
  owner, staff, audit                 kind: FIRST | WOMEN
  subscription (when billing          name ("Chelsea", "Chelsea Women")
  exists)                             world_team_id → WorldTeam  (explicit link)
                                      league_name, crest (defaults to the club's)
                                      finance (D3)
```

- **Every existing club gets one FIRST team** in the migration. It carries over the club's `league_name`, crest and finance.
- **Contracts point at a team** (`contracts.team_id`). `Player.current_club_id` stays, derived from the team's club, so the code that asks "which club" keeps working.
- **Offers, deals, listings, loans and enquiries record the team** on each side (`buying_team_id`, `selling_team_id`) as well as the club. The club stays the party for permissions, notifications and anonymity. The team decides the budget, the window, the valuation's market and the squad the player joins.
- **One active contract per player** still holds. A player is at one team at a time.

### 6.2 Things this replaces or fixes

- **Matching clubs to real-world teams by name.** Each team links explicitly to its `WorldTeam`, set by staff when a club joins.
  - The real-world check then compares each player against their own team's real-world team.
  - Today's majority vote would get a club with both men's and women's players wrong: the women's players would always look mismatched.
- **The world team directory.** It shows which TransferX club a team belongs to, through the explicit link.

### 6.3 Budgets (D3, recommended: per team plus a club total)

- **Every money path names the team.** That covers reserve, commit, release and spend (`clubs/service.py`) and the commitments view. The figures are worked out per team, with the same formula as today: total − reserved − committed − spent.
- **The Finance page** shows each team and the club total.
- **Approvals** are set per team (thresholds differ hugely), with the club owner able to approve any team.
- **The migration** puts today's club finance on the FIRST team, so nothing changes for existing clubs.

### 6.4 Staff (D4, recommended: can be limited to teams)

- **`club_staff` gains an optional list of teams.** An empty list means all teams, today's behaviour.
- **Capabilities stay as they are,** and are checked against the team of the thing being acted on. A Sporting Director limited to the women's team can approve a women's signing and can't see a men's offer.
- **The owner, and anyone not limited to a team,** sees every team.
- **This is a permissions change.** Every endpoint that checks a club capability needs the team check too, and the permissions sweep test in the [17 November fix spec](../../reviews/2026-11-17-code-review-fix-spec.md#9-testing-notes) should cover it.

### 6.5 Surfaces

- **Team switcher.** Shown only when a club has more than one team: in the top bar, with "All teams" for those who can see more than one. Lite mode, the Transfers board, the Dashboard, My Club (squad), Finance and the AI analyst all follow it.
- **A club with one team sees no change.** That's every club today, and every EFL club in Phase A.
- **Notifications and reminders** say the team when the club has more than one: "Chelsea Women: Arsenal Women countered…"

### 6.6 Migration and rollout

- One Alembic migration creates `teams` and moves club fields and finance onto each club's FIRST team. It then backfills `team_id` on contracts, offers, deals, listings, loans and enquiries.
- It runs in one transaction, and a repair script checks the totals before and after (the budget invariant test in the fix spec).
- The demo journal (`demo/journal.py`) and its skip list need the new table and columns.
- Ship behind no flag: with one team per club, behaviour is the same.

---

## 7. Phase C: women's teams

Built on Phase B. A club adds a WOMEN team. Staff link it to its real-world team and set its budget.

### 7.1 Players and the market

- **Players gain a gender field**, set from the vendor's competition (a women's league's squads are women's players) and editable by staff.
- **Separate markets (D6).** The market, search, shortlists, comparisons and the AI analyst show one kind at a time, following the team switcher. A men's and a women's player never appear in one list or chart by default.
- **Offers stay within one kind.** A team can make an offer only for a player of the same kind, and the backend refuses otherwise. Loans follow the same rule.

### 7.2 Competitions and windows

- **Leagues.** Add the WSL and the Women's Championship to `world_leagues`. Verify the API-Football ids before seeding (WSL is believed to be 44), and check coverage as for Phase A.
- **Windows.**
  - Keyed today by country alone. They become keyed by country and kind, because the women's registration windows and deadlines in England are set separately and can differ.
  - Windows without a kind apply to both, which keeps today's data valid.
  - Staff enter the women's dates each season, as for men's windows today.

### 7.3 Valuation

- **The men's model doesn't apply.** The fee and wage scales differ by orders of magnitude (the women's record fee is around £1m), and the league coefficients mean nothing across them.
- **First version: no fair value for women's players.** Show the data (minutes, form, contract, injuries) without one.
- **Add a model only once fees can be checked.** A separate women's model (own coefficients, own scale, own comparable sales) can follow once there are enough recorded fees to check it against. A fair value that can't be checked would hurt trust more than having none.

### 7.4 Terms and money

- **Same deal stages and personal terms** as the men's game. The flow is the same.
- **Salary rules differ.** The WSL has its own salary rules. Recording them belongs with full personal terms in Phase 4 of the phased plan, not here.
- **The women's team's budget is its own (D3).** Approvals are set for that team.

### 7.5 Wording

- Product docs use "his" for a player in places, for example in ADRs 0006 and 0007. New wording in the app says "the player" or uses the player's name, and the women's team's screens must not inherit "his". Search the frontend's text for "his" and "he" before Phase C ships.

---

## 8. What stays the same

- **One account per club, one owner, one audit trail.**
- **The deal workflow.** Stages, consent, approvals, the Transfers board and Lite mode.
- **A club with one team.** No new screens, no switcher, no change in behaviour.
- **Anonymity.** An anonymous buyer is the club, shown by the team's league: "A Women's Super League club".

---

## 9. Risks

| Risk | Phase | Mitigation |
|---|---|---|
| The API-Football plan can't carry three more leagues (and the women's leagues) twice a day | A, C | Measure one refresh before turning them on. If needed, refresh lower divisions once a day |
| Thin data in League One and Two gives values a club disagrees with | A | Show ranges and low confidence. Calibrate against real fees before showing a single figure |
| Promotion and relegation leave clubs or players in the wrong league for a while | A | Test the season change with last season's data. Show staff a list of clubs whose league changed |
| The teams migration gets a club's budget figures wrong | B | One transaction, a before-and-after totals check, and the budget invariant test |
| A team-scoped staff member sees another team's offer through an endpoint that checks only the club | B | Make the team check part of the capability dependency, not something each endpoint remembers. Cover it in the permissions sweep test |
| A men's and a women's valuation appear side by side | C | Separate markets by default, and no women's fair value until there's a checked model |
| Pricing isn't decided when EFL or women's teams arrive | All | Phase A and data-only EFL (D1) don't need pricing. Inviting EFL clubs as customers and selling the women's team does |

---

## 10. Success criteria

**Phase A**
- The three leagues refresh twice daily within the API quota, with request counts recorded on the Admin Jobs page.
- League One and League Two players have values, with confidence shown, and no value is floored at £100k for those leagues.
- The market's division filter defaults to the club's own division and the ones either side.
- A season change moves promoted and relegated clubs and players, shown by a test run on last season's data.
- A buyer can ask TransferX to bring in an EFL club, and staff see the requests.

**Phase B**
- Every club has exactly one FIRST team after the migration. Every club's budget totals are the same before and after.
- The real-world check uses each team's explicit link, and no longer falls back to names.
- A staff member limited to one team gets 403 on any other team's offer, deal, listing and finance. A test covers every capability-checked endpoint.
- A club with one team sees no change anywhere (screenshots before and after).

**Phase C**
- A club can add a women's team with its own budget, squad and staff.
- A men's team can't make an offer or loan for a women's player, and the reverse, enforced by the backend.
- No list, chart, comparison or analyst answer mixes men's and women's players by default.
- Women's windows can differ from men's in the same country, and hold completion correctly.
- No fair value is shown for a women's player until a checked model exists.

---

## 11. Related documents

- [Product ADR 0013 (proposed): a club is an organisation with teams](../../product/decisions/0013-a-club-is-an-organisation-with-teams.md)
- [`../../business/business-model.md`](../../business/business-model.md), [`../../business/target-users-and-market.md`](../../business/target-users-and-market.md): the open pricing and segment decisions that §3 informs
- [`../../reviews/2026-11-15-product-and-readiness-review.md`](../../reviews/2026-11-15-product-and-readiness-review.md): §5.1, working with clubs that aren't on TransferX; §8, data vendors
- [`../valuation/model.md`](../valuation/model.md): the model whose coefficients and floor Phase A changes
- [`../scheduled-data-refresh.md`](../scheduled-data-refresh.md): the refresh that Phase A extends
- [`../club-team-roles-and-onboarding.md`](../club-team-roles-and-onboarding.md): club roles, which Phase B scopes to teams
- [Product ADR 0010](../../product/decisions/0010-deals-run-all-year-windows-hold-completion.md): windows hold completion, which Phase C keys by country and kind
