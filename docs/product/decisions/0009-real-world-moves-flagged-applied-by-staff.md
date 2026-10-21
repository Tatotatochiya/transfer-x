---
title: "ADR 0009: Real-World Moves Are Flagged, and Applied Only by TransferX Staff"
last_updated: 2026-10-21
status: Accepted
owner: "TODO — assign a Product Owner"
---

# ADR 0009: Real-World Moves Are Flagged, and Applied Only by TransferX Staff

## Context

On TransferX a player's club changes only through a deal. But the demo clubs mirror the real Premier League, and real football moves on: by October 2026, 204 of the 680 contracted players had joined another club, gone out on loan or come back from one, according to API-Football. Their TransferX contracts still had them where they were. The product owner noticed it on M. Senesi, whose profile showed this season's games for Tottenham while TransferX still had him at Bournemouth.

Three options were weighed: flag the difference and change nothing; flag it and let staff apply it; or apply it automatically in the nightly data refresh.

## Decision

1. **Flag every real-world move.** TransferX compares each contracted player's registration with API-Football: his latest transfer this season, and who he has played for this season, with the newest piece of evidence winning. A difference shows on the player's page ("Moved in real life: …") and in Admin → Real-world moves. Code: `backend/app/players/real_world.py`.
2. **Only TransferX staff apply a move, one at a time or in bulk, with a reason.** Applying closes his open offers, listings and enquiries (releasing the budget offers held), ends his TransferX contract, and either starts a contract at the TransferX club he joined (unconfirmed, for that club's "Check your squad") or makes him a player at a club outside TransferX. Both clubs are told, and the change is in the admin audit log. No money moves: a correction to the records isn't a transfer.
3. **Some moves can't be applied:** a player in a TransferX deal, or on a TransferX loan, until that's finished; and a real-world loan. A loan to a club outside TransferX doesn't change who owns him. A loan between TransferX clubs needs terms API-Football doesn't have (dates, wage split, options), so it's recorded as a loan deal between the clubs instead.
4. **Staff can dismiss a move** (with a reason, audited). It stops being reported until the evidence points at a different club.
5. **Never automatically.** The nightly refresh doesn't change registrations.

## Consequences

- A club's squad never changes behind its back, including players it is negotiating over. Every change has a named person and a reason.
- The demo can be brought in line with the real league after each window in one bulk apply.
- Until staff act, a club's squad can include players who have left in real life; the flag makes that visible.
- Evidence is only as fresh as the stored data. Appearances are refreshed twice a day, and since 2026-10-17 the 22:00 refresh also re-fetches the transfer histories of players at TransferX clubs, so a move is seen before his first game.

## Update, 2026-10-17: the club is told

The club itself now hears, not only TransferX staff: an hourly job sends each club one notification ("Players moved in real life", `REAL_WORLD_MOVES`, migration `0103`) naming its players API-Football has at other clubs, and saying staff will update the squad. It's sent again only when the list gains a player; moves staff apply or dismiss drop out on their own.

## Update, 2026-10-21: TransferX's own deals count

The check compared a player's registration with API-Football and nothing else, so it couldn't tell real football being ahead of TransferX from TransferX being ahead of the data. The product owner raised two cases: Saka, in an open Liverpool → Chelsea deal while playing for Arsenal; and Rice, whom a TransferX deal had moved from Arsenal to Liverpool, flagged "Moved in real life" because API-Football still had him at Arsenal. Decided with the product owner:

1. **Evidence from before a completed TransferX deal into his club is the data catching up,** not a move: it is ignored.
2. **A game for the club TransferX moved him from, after the deal, is a contradiction** (`case` "behind_transferx"). Only TransferX staff see it: the clubs aren't told, since it is usually a data error and would alarm the club that has just paid for him. Staff can confirm his registration, never apply it: applying would undo a paid transfer with no money returned. Undoing a completed transfer is out of scope; in real football it is a dispute between the clubs.
3. **A player in an open TransferX deal who has moved holds the deal's completion** until staff confirm his registration (dismiss) or collapse the deal and apply the move in one step. Talks and paperwork carry on; the staff Complete tool can still override, with a reason. Held rather than collapsed, because API-Football is sometimes wrong. Both clubs are told on the deal.
4. **No hold when he is at the buying club in real life** (the deal is catching up; nothing is reported), **nor for a real-world loan** (his registration hasn't changed; the buying club is told).

