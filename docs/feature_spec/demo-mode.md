---
title: "Demo Mode"
last_updated: 2026-11-03
status: Built (runs, journal, reset, play-as; demo and test deals kept out of shared figures; house clubs sell, buy and bid as rivals on their own); auctions and "make them…" buttons not built
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

## House clubs answer on their own

Added 2026-11-02 (`backend/app/demo/house.py`, job `demo_house_clubs`, every 5 seconds with `DEMO_ENABLED`). When it's a house club's move on an offer or deal an open demo made, the club makes it, as its owner, through the same actions a person uses. Every move is journaled under the run (Reset undoes it) and says "Automated (demo): …" in the offer's messages or the deal's notes.

**An offer for one of its players.** Priced against the listing's asking price, else the model's value, else his last transfer fee, else his market value:

| Personality | Accepts at | Counters at | Turns down below |
|---|---|---|---|
| Hard-nosed | 110% | 120% | 80% |
| Fair (default) | 95% | 100% | 70% |
| Eager to sell | 85% | 95% | 60% |

A counter is always above the offer and rounded to £0.5m. After two counters the club takes anything above the midpoint and walks away otherwise. A loan offer is accepted. With no price to judge by, a hard or fair club counters once (130% / 115%), then accepts; an eager one accepts.

**Its side of the deal.** The player's agent, if nobody uses the agent's account, proposes a 5% commission paid by the buying club. The player, if he has no account in use, agrees personal terms. The club signs its side of the transfer agreement. The buying club's own steps (agreeing commission, proposing terms, the medical, registration, completing) stay with the tester.

**A player the tester lists** (added 2026-11-03; not auctions). Two house clubs bid, each at its opening share of his price (asking price, model value, last fee or market value), a little apart: hard-nosed 85%, fair 95%, eager 105%, give or take 4%. On a fixed-price listing they offer the asking price. A tester's counter is accepted up to the club's top (95% / 105% / 115%), met halfway otherwise ("Our best is £…"), and after two counters the club walks away. Once a deal starts, the buying house club does every buyer's step: moves it on, agrees the agent's commission, proposes personal terms (four years, 10% over his current wage), signs, records a passed medical, submits the registration and completes. The tester signs their side as the seller.

**Rival bidders** (added 2026-11-03). When the tester bids for a house club's player, another house club bids too, at 95–115% of his price: **sometimes** (about one offer in three, the default), **always** or **never**, set in the Demo pill (`PATCH /demo/run {"rivals": …}`, migration `0107`). The seller weighs the best offer. If the rival's is higher it says only "We have a better offer on the table. Can you improve?" (never naming the club or the figure) and counters just above it; after two counters it takes the rival's and tells the tester "We've accepted another club's offer." If the tester's offer wins, the rival's is turned down.

**One player, one demo.** A tester can't bid for a player who is in another tester's open demo: "He's in another tester's demo right now."

**Speed.** In the Demo pill, house clubs answer **Straight away** (the next tick) or **After a few minutes** (3 minutes after the tester's last move, as a real club would take its time). `PATCH /demo/run {"speed": "instant" | "realistic"}`, migration `0106`.

## Kept out of shared figures

Added 2026-10-29. While a run is open, the deals it made don't count in what everyone sees: valuations (including the 22:00 refresh), Ask TransferX's comparable transfers and recent-transfers answers, Recent Transfers and its analytics. A player in an open demo's deal isn't checked for real-world moves either: the demo moved him, not real football. Keeping a run makes its deals count; resetting removes them. All of these use one filter, `demo.service.shared_deals`.

**Test transfers.** Transfers made while trying TransferX before demo mode existed can't be reset, but staff can mark one as a test in Admin → Deals (with a reason, audited: `deals.is_test`, migration `0105`). A test transfer is left out of the same figures. Nothing else changes: the player, the money and the clubs' records stay as they are. On 2026-10-29 production had four completed transfers, all between the clubs the team tests with: Saka and Rice (Arsenal → Liverpool), Havertz (Arsenal → Chelsea) and Acheampong (Chelsea → Liverpool).

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
| `POST /admin/deals/{id}/test` | Mark a deal as a test transfer, or not. Reason required |

Code: `backend/app/demo/` (`journal.py`, `service.py`, `router.py`), migration `0104`.

## Not built yet

1. **Auctions:** house clubs don't bid in auctions yet, only on open-to-offers and fixed-price listings.
2. **"Make them accept / counter / reject" buttons** on a demo offer, to force a path without waiting for the rules.

> **TODO:** a real club can still make an offer *to a tester's club* during a demo, outside it; only bids on demo listings are refused. Fine while testers' clubs aren't used by anyone else.
