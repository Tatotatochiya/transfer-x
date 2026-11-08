---
title: "ADR 0011: Auctions Are Retired; Clubs Choose Among Offers"
last_updated: 2026-11-08
status: Accepted
owner: "TODO — assign a Product Owner"
---

# ADR 0011: Auctions Are Retired; Clubs Choose Among Offers

## Context

A listing could be run as an auction: clubs bid against each other until a deadline, and the seller accepted the best bid above a reserve. Since [ADR 0008](./0008-transfers-board-one-way-to-buy-lite-decides.md) it sat under "Advanced" on the listing form, behind the main path (enquiry → offer → deal).

Real clubs don't sell players by auction. A selling club hears offers from several clubs, plays them against each other, and chooses. That choice isn't always the highest fee: the payment schedule, add-ons, sell-on, the wage the player is offered and where he wants to go all count. An auction sells to the highest bidder and can't weigh any of that. "Open to offers" already does what clubs do, with the seller's order book comparing every offer.

Clubs weren't using auctions: every auction on the local data was withdrawn. Yet about 50 files carried them (bidding, reserves, increments, outbid notices, auction reminders, the board and dashboard, approvals of bids, the demo house clubs' bidding), and every new feature had to cover them.

## Decision

1. **No new auctions.** `POST /sales` refuses `sale_type: AUCTION` with a message pointing to open to offers. The listing form no longer offers it.
2. **"Offers by" covers "best offers by Friday".** An open-to-offers listing already takes an optional date, now labelled "Offers by": clubs see it, the listing closes then, and the seller chooses from the offers made. Rival offers stay confidential, as before.
3. **Bidding is removed:** placing, accepting and listing bids; the auction order book; outbid and auction-ending notifications; auction cards on the board and dashboard; bids in the budget commitments list; bid approvals; the demo house clubs' auction bidding.
4. **History stays.** Past auction listings, bids and the deals they produced remain in the database. Deals still show "Auction deal", and Transfer Activity still filters and counts them. The `AUCTION` sale type, the bid tables and the bid approval and notification types are kept so old rows still read.
5. **What was live is wound down** (migration `0109`): an auction still open becomes open to offers, keeping its deadline; every active bid is turned down and its budget given back; a bid or bid acceptance waiting for approval is cancelled. A collapsed deal from an old auction re-lists the player open to offers, and the clubs that made offers on that listing are told.

## Alternatives considered

- **Keep auctions under "Advanced".** Cheap to leave, but it kept the cost on every feature for something clubs don't do, and invited a consumer-marketplace habit into a professional workflow.
- **Sealed bids by a date.** Closer to a real "best offers by Friday" process, but that is what an open-to-offers listing with an "Offers by" date already is, without a second mechanism.

## Consequences

- One way to sell: list open to offers (optionally with an "Offers by" date and a guide price), then compare and answer offers.
- Bidders on an auction still open at deploy aren't notified by the migration; their budget is released. On local data there were none open.
- Approvals are now only for offers, accepting offers and exercising loan options.
- Superseded: the auction parts of [ADR 0003](./0003-listing-a-player.md), [ADR 0004](./0004-listing-availability-transfer-loan-or-either.md) and [ADR 0008](./0008-transfers-board-one-way-to-buy-lite-decides.md) (auction under "Advanced").

## Related

- [Negotiation and offers](../workflows/negotiation-and-offers.md)
- [ADR 0008: Transfers board, one way to buy](./0008-transfers-board-one-way-to-buy-lite-decides.md)
