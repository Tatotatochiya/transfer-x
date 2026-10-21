---
title: "Implementation Status"
last_updated: 2026-10-12
status: Active
owner: "TODO — assign a Documentation Owner"
---

# Implementation Status

## Purpose

What's actually built in TransferX right now, **verified against the code**: not what tickets claim, and not a history. [`CHANGELOG.md`](./CHANGELOG.md) has the history, including the detail this page used to carry.

## Scope

In scope: current build state by area, known gaps, test totals.
Out of scope: the plan ([`product/roadmap.md`](./product/roadmap.md)), ticket detail (Linear), change history (the CHANGELOG).

Maintained by the [`documentation-standards`](../.claude/skills/documentation-standards/SKILL.md) skill. When you change an area, re-check the code and update its row and date; don't copy a ticket's status.

## Status by area

Rewritten on 2026-10-11 from the code, the CHANGELOG and read-only checks of the Railway database. "Verified" is the date the row was last checked against the code.

| Area | Status | Verified | What's there |
|---|---|---|---|
| Listings | Built | 2026-10-11 | Open to Offers by default, auction under "Advanced", fixed price for existing listings only. Transfer, loan or either. One open listing per player (unique index). Listed means available (product ADR 0005). List from the squad, the player page or the dashboard |
| Enquiries | Built | 2026-09-27 | Pre-offer threads, open or anonymous, one per club per player, "your move" everywhere. Swaps deferred |
| Offers | Built | 2026-10-11 | Permanent and loan offers with the fee, wage, payment schedule, add-ons, sell-on and expiry. Fee and wage reserved; counters validated like new offers; anonymous buyers masked server-side (ADR 0004); rivals released on acceptance; no offers for players at clubs outside TransferX. Logic in `offers/actions.py` |
| Deals | Built | 2026-10-11 | AGREEMENT → (AGENT_NEGOTIATION) → PERSONAL_TERMS → PAPERWORK → CONFIRMED → COMPLETED. Terms fixed from the offer; consented personal terms become the contract; the club-run paperwork checklist with buyer-recorded medical; row locks on every money path. Clause status is tracked, but marking an add-on paid moves no money |
| Loans | Built | 2026-09-28 | Registration separate from ownership (ADR 0005), wage split, recall, expiry job, option and obligation, conditional obligations confirmed by both clubs with staff settling disputes, approval-gated loan fees and options |
| Transfers board and conversation | Built | 2026-10-11 | `/board`: every player bought or sold, once, at its furthest point, with Buying and Selling lanes. One conversation per transfer across the message stores (ADR 0008). The classic list pages are retired and redirect to the board |
| Clubs, roles and approvals | Built | 2026-07-10, rows since | Owner and four staff roles with one capability matrix; invitations for clubs, staff and players; spending approvals above a threshold with the decision sheet; "Check your squad"; people's names; "in play" status on the squad |
| Agents and mandates | Built | 2026-10-11 | Mandates, agent negotiation of commission, agent answering personal terms (ADR 0007), the Pipeline start page, client alerts. Mandates need no player confirmation (gap below) |
| Players | Built | 2026-10-01 | Profile v2 season ledger, career and injuries (P1–P4); player accounts by club invitation only; free agents invited by staff or their agent |
| Lite mode | Built | 2026-10-18 | L1–L8: home, Buy page (search by name, and the club's shortlist and players of interest, with a Shortlist button on each row; the guided position/budget path was removed 2026-10-18), action cards with the money effect, Ask anything, held sends with a 10-second undo (ADR 0007), team contact, decisions from email. The default for club members since 2026-10-13, with a visible "Switch to full app" button; the choice is remembered. Loans in the Buy flow are a to-do |
| Notifications | Built | 2026-10-04 | In-app with live refresh; email per type and the daily digest; Web Push with tiers, quiet hours, the morning summary, decision sheets and a 30-minute email fallback. Railway has push keys but no SMTP (gap below) |
| AI assistant | Built | 2026-10-06 | Advises, never acts (ADR 0006): offer advisor, terms checks, summaries, deal steps, briefing, pricing, "Who might want him?", drafts, Ask TransferX (⌘K). The analyst (`/ask`): 17 read-only, club-scoped tools, tables, charts, Excel, "Ask about this"; eval 71/72. Cache and rate limit are in memory |
| Valuation | Built, calibrated | 2026-10-17 | `market-v2` (multi-season, age and potential, form, contract, availability, comparables). Recomputed daily by the `stats-worker`. Calibrated on 2026-10-17 against production fees: within ±25% of the fee for 31% of transfers (was 12%), median bias −9% (was −64%); the market-rate ceiling binds for 33% of players (was 53%) ([calibration](./feature_spec/valuation-model-v2.md#calibration-archetypes-not-a-backtest)) |
| Data from API-Football | Built | 2026-10-12 | Admin-triggered syncs plus the scheduled refresh (17:00 and 22:00 UK): stats (with each competition's name and logos, fixed 2026-10-12), injuries, ratings for new matches, form; follows each competition's current season. Production refreshes all 11 competitions in `world_leagues` |
| Deadline day | Built | 2026-10-17 | `/deadline` (Lite or full app, by the person's mode): every open offer and deal against the window's close, with the next step, whose move, steps left and an "at risk" flag (under 6 hours per step). Banner on the Lite home and dashboard in the last 72 hours; pushes at 24, 6 and 2 hours. Windows are still global, not per federation |
| Real-world moves | Built | 2026-10-21 | Contracted players whose API-Football club differs from their TransferX registration: a "Moved in real life" note on the player page, and Admin → Real-world moves to apply (bulk, with a reason; offers and listings close, contract moves, no money) or dismiss; the club gets one notification listing its moved players. Transfer histories refresh nightly. Never automatic ([product ADR 0009](./product/decisions/0009-real-world-moves-flagged-applied-by-staff.md)). Since 2026-10-21 TransferX's own deals count: games before a TransferX move are ignored, a player playing on for the club TransferX moved him from is shown to staff only and can't be applied, and an open deal for a player who has moved can't complete until staff confirm his registration or collapse the deal and apply the move in one step. On dev data: 204 of 680 contracted players |
| Monitoring and admin | Built | 2026-10-17 | Admin panel with every change audited and a reason; staff tools for a stuck deal (move on, record paperwork or the medical, move the completion deadline, complete, collapse; each with a reason both clubs see); audit log page; read-only "view as this club"; Admin Jobs (runs, steps, live logs, Run refresh now), Errors (grouped issues from API, worker and browsers), Health (services, requests, jobs, integrity). Slack alerts once the webhook is set |
| Accounts and privacy | Built | 2026-10-11 | Sign-in by email or username; sessions and signed-in devices with "sign out everywhere"; password reset links; GDPR export and account deletion; invitation-only accounts |
| Money display | Built | 2026-10-04 | Amounts in pounds; a chosen EUR or USD adds an estimate at the ECB rate |
| Frontend | Built | 2026-10-11 | The design system ([`design-system/`](./design-system/README.md)) across every screen, light and dark, responsive to 375px; compact sidebar and squad table; `tsc -b` at 0 errors; browser errors reported to Admin → Errors |
| Demo data | Built | 2026-10-11 | 20 Premier League clubs, agents for every contracted player, deals at every stage (`seed_demo.py`, phase 1), mock contract end dates. Railway checked by read-only queries: every repair script applied |
| Deployment | Built | 2026-10-11 | Railway (`backend`, `frontend`, `Postgres`, `stats-worker`), deploying `main` automatically, at migration `0100`. A demo environment, not production ([operations](./operations/environments-and-deployment.md)) |

## Known gaps

Each item was checked against the code on 2026-10-11 unless it says otherwise.

**Security and trust**
- **Two-factor sign-in** isn't built (deferred in the Q4 plan).
- **Agent mandates** are active as soon as an agent creates them; the player doesn't confirm (TRA-144).
- **Verification** gives a badge but gates no action.
- **Shared password on Railway:** every Railway account shares one password. Acceptable for a demo, not for real clubs.

**Operations**
- **No email on Railway:** there's no SMTP, so invitations, digests and reset links aren't emailed there.
- **Slack:** `SLACK_WEBHOOK_URL` isn't set yet, so there are no run messages or alerts.
- **Phone test:** the real-phone notification test (Phase 0) hasn't been done.
- **AI state in memory:** the assistant's cache and rate limit live in memory. They need a shared store before running more than one API process.

**Product and data**
- **Valuation, after calibration:** small fees (under £5m) are over-predicted and £25m+ fees still under; smaller leagues' coefficients look low but rest on 2–4 transfers each. Needs more fees to fit.
- **Contract end dates are mock data** for demos.
- **Money not moved:** add-on and clause payments are tracked by status only. Present-value figures on instalments aren't shown (no discount rate).
- **Not built:**
  - the injury risk score (`injury-availability-risk-profile.md`);
  - demo scenarios M1–M4 and S1–S2;
  - analyst Phase C (reminders and saved questions);
  - the rest of Phase 2 of the Q4 plan (registration, windows by federation, the medical), and Phases 4 and 5.
- **Anti-sniping** settings exist but aren't used.
- **Lite can't make loan offers** (a to-do, [Lite spec](./feature_spec/lite-mode/README.md#to-do)). Its bid card is permanent only, so a player listed for loan only gets a permanent bid from Lite, which is refused.

**Left over from the August demo audit** (the audit was removed on 2026-10-11; these were still open)
- A "Rumors coming soon" placeholder on the public transfers page.
- `console.log` / `console.error` at sign-in and in the API client.
- **Not re-checked since August:**
  - list pages showing an empty state when the backend is down;
  - no WebSocket reconnect indicator;
  - the player profile save giving no error feedback.

## Test totals

As of 2026-10-12:

- **Backend:** 900 passed (full suite, SQLite).
- **Frontend:** vitest 266 passed.

- **Type check:** `tsc -b` has 0 errors.

## Related documents

- [`CHANGELOG.md`](./CHANGELOG.md): history
- [`PRODUCT_SPEC.md`](./PRODUCT_SPEC.md): master index
- [`product/roadmap.md`](./product/roadmap.md): the plan
