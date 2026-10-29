---
title: "Demo Mode"
last_updated: 2026-10-27
status: Step 1 built 2026-10-27 (runs, journal, reset, house-club switch, play-as); house clubs acting on their own not built
owner: "TODO — assign a Product Owner"
---

# Demo Mode

## Purpose

Let a tester try TransferX end to end on the real data (bid on a player, take a deal to completion) without signing in as the other club, and then put everything back. Decided with the product owner on 2026-10-27: in the same app and database as everything else, not a separate demo copy ([ADR 0009](../architecture/decisions/0009-demo-runs-journal-changes-reset-plays-them-back.md)).

Not the same as the [demo scenario generator](./demo-scenario-generator.md), which seeds fixed deals at every stage from a script.

## How it works

- **A demo run.** A tester presses **Start demo** (bottom-right of every page, full app and Lite). Everything they change from then on, and everything that sets off, belongs to the run. The pill shows "Demo · N changes"; **Reset demo** puts it all back, **End, keep changes** keeps it. A run left open resets itself after 14 days.
- **The journal** records each change as it's saved: a new row (deleted on reset), a changed row (only the columns that changed, before and after), a deleted row (put back). A change made in the same database step as a demo change is demo too, so a job expiring a demo offer and releasing its budget is recorded without that job knowing about demos.
- **The safety check.** Reset sets a column back only if it still holds the value the demo left. A column something real changed since is left as it is and listed in the report (Admin → Demo), as is a row real data now depends on.
- **House clubs.** Clubs TransferX plays in demos. In a tester's own run, the other side of an offer, bid or enquiry must be a house club, so no real club is drawn into a demo; and nobody outside a demo can bid on a listing made in one. Only a club nobody uses (its owner has never been active, and it has no staff) can be a house club.
- **Play as a house club.** From the Demo pill, a tester opens a house club in its own tab and plays the other side by hand: accept, counter, sign. That tab belongs to the run, says so in a banner, and stops working when the run ends.

## Who can do what

| Who | Can |
|---|---|
| TransferX staff | Start a demo; choose house clubs and testers in Admin → Demo (with a reason, audited); reset anyone's demo |
| Testers (`users.can_demo`, set by staff) | Start, reset and keep their own demo; play house clubs in it |
| Everyone else | Nothing: no Demo pill |

The whole feature is off unless the server sets `DEMO_ENABLED=true`. Off, nobody can start a demo and nothing is journaled; open runs wait to be reset.

## What reset can't undo

- Emails and pushes already delivered.
- Audit log entries, monitoring and analytics: append-only, so they keep what happened.
- Model calls already made.

## API

| Endpoint | What |
|---|---|
| `GET /demo/run` | Your active run (changes, auto-reset date) and whether you may start one |
| `POST /demo/run`, `/demo/run/reset`, `/demo/run/keep` | Start, reset, keep |
| `GET /demo/house-clubs`, `POST /demo/house-clubs/{id}/play-as` | House clubs; a two-hour token to play one inside your run |
| `GET /admin/demo` | Runs with their reports, testers, every club and whether it's in use |
| `PATCH /admin/demo/clubs/{id}`, `PATCH /admin/demo/testers/{id}` | House club on or off (and personality); tester on or off. Reason required |
| `POST /admin/demo/runs/{id}/reset` | Reset anyone's run |

Code: `backend/app/demo/` (`journal.py`, `service.py`, `router.py`), migration `0104`.

## Not built yet

1. **Demo data kept out of shared figures** while a run is open: valuations (including the 22:00 refresh), Ask TransferX's comparable transfers, the real-world moves check, market activity. Until then, a completed demo transfer counts in them until it's reset.
2. **House clubs acting on their own:** answering bids by our valuation and their personality, and doing their side of a deal, at an instant or realistic speed.
3. **House clubs as buyers** of what a tester lists, and "make them accept / counter / reject" buttons.
4. **Production's earlier test transfers** (e.g. Rice to Liverpool) predate the journal and can't be reset; they're to be listed and marked.

> **TODO:** a real club can still make an offer *to a tester's club* during a demo, outside it; only bids on demo listings are refused. Fine while testers' clubs aren't used by anyone else.
