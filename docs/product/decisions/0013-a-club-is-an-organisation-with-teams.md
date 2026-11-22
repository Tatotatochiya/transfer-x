---
title: "ADR 0013: A Club Is an Organisation with Teams"
last_updated: 2026-11-22
status: Proposed
owner: "TODO — assign a Product Owner"
---

# ADR 0013: A Club Is an Organisation with Teams

**Status: Proposed.** It isn't decided until decisions D2 to D6 in the [leagues and club teams spec](../../feature_spec/leagues-and-club-teams/README.md#4-decisions-needed) are made. Nothing is built.

## Context

A TransferX club is one organisation with one team. It has one name, crest and league, one budget, and one set of staff. Players belong to the club through a contract. The club is matched to its real-world team by the team most of its players are registered to, falling back to the club's name.

Real clubs run more than one team. Chelsea's first team and Chelsea Women are one organisation, with one owner and often shared executives. But they have different competitions, budgets, transfer windows and markets, and often separate finances.

Modelling the women's team as a second club would split the customer into two accounts. It would lose the oversight the club owner expects, and break the club-level audit trail. Adding the women's team as a tag on players would mix two markets and two budgets that must stay apart.

## Decision (proposed)

1. **A club is the organisation:** the legal party, the account, the owner, the staff and the audit trail. It is what TransferX bills (D2).
2. **A team is a squad that plays in a competition.** Each team:
   - belongs to one club;
   - has a kind (first team or women's team);
   - links explicitly to its real-world team;
   - has its own league and budget (D3).
3. **Contracts belong to a team.** Offers, deals, listings, loans and enquiries record the team on each side as well as the club. The club stays the party for permissions, notifications and anonymity. The team decides the budget, the transfer window, the market and the squad.
4. **Staff can be limited to teams** (D4). By default a member sees every team at their club, today's behaviour.
5. **Men's and women's markets are separate** (D6). A team makes offers only for players of the same kind.
6. **A club with one team sees no change.** Every existing club becomes a club with one first team.

## Alternatives considered

- **A separate club account for each team, with a "parent" link.**
  - Simpler to migrate, but it splits the customer, its owner and its audit trail.
  - Every permission would need a cross-account rule.
  - Billing would need joining back together.
  - Rejected.
- **A tag on the player (men's, women's), with one club budget.**
  - Mixes two budgets that clubs keep apart.
  - Can't give a women's general manager their own scope.
  - Rejected.
- **Keep one team per club and wait.**
  - Works until the first club with a women's team signs up.
  - Its account would then have to be split after the fact, with live deals.
  - Rejected for any club that has, or plans, a women's team.

## Consequences

- **A significant migration.**
  - A new `teams` table.
  - `team_id` on contracts, offers, deals, listings, loans, enquiries and finance.
  - A FIRST team created for every club.
  - Budget totals checked before and after.
- **Every capability check also considers the team** when a member is limited to some. This needs a permissions sweep test.
- **The real-world check uses each team's explicit link,** and the name matching goes.
- **Transfer windows are keyed by country and team kind,** because women's registration windows can differ.
- **Budgets, approvals and the Finance page work per team,** with a club total.

## Related documents

- [`../../feature_spec/leagues-and-club-teams/README.md`](../../feature_spec/leagues-and-club-teams/README.md): the spec, with the phases, decisions and success criteria
- [`0010-deals-run-all-year-windows-hold-completion.md`](./0010-deals-run-all-year-windows-hold-completion.md): windows hold completion
- [`../../architecture/authentication-and-permissions.md`](../../architecture/authentication-and-permissions.md): club roles and capabilities
