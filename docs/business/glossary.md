---
title: "Glossary"
last_updated: 2026-10-11
status: Active
owner: "TODO — assign a Documentation Owner"
---

# Glossary

## Purpose

The single canonical place domain terms are defined. Every other document should **link here** rather than redefining a term — this is how the documentation set avoids duplicate (and eventually contradictory) definitions.

## Scope

In scope: domain/business terms used across TransferX's product and documentation.
Out of scope: pure engineering jargon (framework names, library names) — those are explained where used, not here.

## Table of Contents

- [Actors](#actors)
- [Listings & bidding](#listings--bidding)
- [Negotiation](#negotiation)
- [Deals](#deals)
- [Finance](#finance)
- [Product surfaces](#product-surfaces)
- [Related documents](#related-documents)

## Actors

| Term | Definition |
|---|---|
| **Club** | An organization account that can buy and/or sell players. Has a role: buyer, seller, or both. |
| **Agent** | Represents one or more players under a mandate; can negotiate commission and personal terms on a player's behalf. |
| **Player** | The individual being transferred. Can hold an account, by invitation from his club (or from staff or his agent if a free agent), to see his profile and answer personal terms. |
| **Club staff role** | The scoped role a non-owner club member holds: Sporting Director (deal authority + approvals), Manager (day-to-day market/deals), Scout (shortlists only), or Read-only (oversight). Each maps to a fixed capability set — see [`../architecture/authentication-and-permissions.md`](../architecture/authentication-and-permissions.md#club-roles). Distinct from platform (TransferX) staff. |
| **Invitation** | The owner-issued, emailed single-use link through which a new staff member joins a club and sets their own password. Expires after 7 days; can be revoked; the link is shown exactly once. |
| **Mandate** | The formal representation relationship between an agent and a player; can be exclusive or non-exclusive, and has a validity period. |

## Listings & bidding

| Term | Definition |
|---|---|
| **Sale / listing** | A player listing created by the club that owns him. **Open to Offers** is the default, **Auction** is an advanced option, and **Fixed Price** is no longer offered (existing ones still work). A listing can be for transfer, loan or either. |
| **Listed (available)** | A player is available exactly when he has an open listing. There's no separate "open to offers" switch for club players (product ADR 0005). |
| **Bid** | An amount placed by a buying club against an auction-type Sale. |
| **Reserve price** | The minimum amount a seller will accept in an auction; visible only to the seller. |
| **Order book** | The ranked view of active bids/offers on a Sale. |
| **Fair value (model)** | TransferX's own estimate of a player's transfer value, with a confidence range. Since 2026-10-07 it's the `market-v2` model: up to three seasons of stats, age and potential, form, contract length, availability, league, and comparable transfers ([spec](../feature_spec/valuation-model-v2.md)). An estimate, never an official valuation. Not shown to player accounts. |
| **Divergence** | How far a reference price (asking price or agreed fee) sits from the model fair value, as a percentage with a band from "Well below model" to "Well above model". Never computed against a hidden reserve price. |

## Negotiation

| Term | Definition |
|---|---|
| **Enquiry** | A question about a player before any offer, open or anonymous; one open thread per club per player. |
| **Offer** | A direct proposal from a buying club to a selling club, outside the auction mechanism: permanent or loan, with the fee, wage, payment schedule, add-ons and sell-on. Can be countered by either side. |
| **Anonymous buyer** | A buying club shown to the seller only as "A {league} club" until its offer is accepted ([ADR 0004](../architecture/decisions/0004-anonymous-buyer-masked-server-side.md)). |
| **Whose move** | Which side has to act next on an offer, enquiry or deal: yours, theirs, or neither. It drives "waiting on you" on the dashboard, board, sidebar and daily digest. |
| **Counter** | A revised Offer responding to a previous one. |

## Deals

| Term | Definition |
|---|---|
| **Deal** | Created once a Bid or Offer is accepted; tracks the transfer through to completion. |
| **Deal stage** | Where a Deal currently sits in its lifecycle. See [`../product/workflows/transfer-lifecycle.md`](../product/workflows/transfer-lifecycle.md) for the full stage list. |
| **Agent negotiation** | The stage where a mandated agent negotiates commission with the buying club. Personal terms come next, in their own stage. |
| **Personal terms** | The wage, signing bonus, and contract length proposed to the player. They need consent from the player, his mandated agent, or, with neither, the buying club recording it with the signed terms. Once consented, they become the deal's contract terms. |
| **Paperwork checklist** | The steps that confirm a deal: both clubs sign the agreement, and the buying club records a passed medical and submits the registration. |
| **Medical check** | A pass/fail check on the player, recorded by the buying club during paperwork (or by staff). A failed medical blocks the deal. |
| **Loan** | A temporary move: the registration goes to the loanee, the parent club keeps ownership, and the player returns at the end. Can carry a loan fee, a wage share, an **option to buy** (the loanee may) or an **obligation to buy** (converts at the end, after both clubs confirm any conditions). |
| **Transfers board** | The page (`/board`) showing every player a club is buying or selling, once each, at its furthest stage, with buying and selling lanes. |
| **Sell-on clause** | A percentage of a future resale fee owed back to a previous selling club. |
| **Instalment** | A scheduled partial payment of the agreed transfer fee. |

## Finance

| Term | Definition |
|---|---|
| **Transfer budget** | A club's total available funds for transfer fees. |
| **Approval threshold** | An optional per-club amount at or above which a Manager's money action (bid, offer, acceptance) waits as a pending approval for the owner or a Sporting Director to sign off, instead of executing. Nothing is reserved while pending; execution re-checks everything fresh. |
| **Reserved** | Funds provisionally held against an active bid/offer. |
| **Committed** | Funds locked in once a deal is agreed but not yet completed. |
| **Spent** | Funds actually paid out on a completed deal. |
| **Wage budget** | A club's total available weekly wage capacity, tracked in parallel to the transfer budget. |

## Product surfaces

| Term | Definition |
|---|---|
| **Lite mode** | A big-type interface for directors, opt-in per person. They decide on offers, approvals and bids with a 10-second undo; the full app is where people operate (product ADR 0008). |
| **Held send / undo** | A Lite action waits briefly before it's sent so it can be undone ([ADR 0007](../architecture/decisions/0007-held-sends-for-undo.md)). |
| **Ask TransferX** | The assistant's question box (⌘K and `/ask`). It answers from TransferX's data through read-only, club-scoped tools, and never acts on its own ([ADR 0006](../architecture/decisions/0006-ai-assistant-advises-from-scoped-facts.md)). |
| **Data refresh** | The twice-daily update of players, stats, injuries and form from API-Football, with valuations recomputed after the 22:00 run. |

## Related documents

- [`../product/workflows/transfer-lifecycle.md`](../product/workflows/transfer-lifecycle.md) — how these terms fit into the end-to-end flow
- [`../architecture/data-model.md`](../architecture/data-model.md) — how these concepts map to database entities
