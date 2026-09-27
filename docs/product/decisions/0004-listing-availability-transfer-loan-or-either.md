---
title: "ADR 0004: A Listing Says Whether the Player Is for Transfer, Loan, or Either"
last_updated: 2026-09-26
status: Accepted
owner: "TODO — assign a Product Owner"
---

# ADR 0004: A Listing Says Whether the Player Is for Transfer, Loan, or Either

## Context

A club could only list a player for sale. Clubs often make young or surplus players available **on loan** instead, and a buying club had no way to know who was loanable, so it sent loan offers blind. Worse, a loan offer made against a sale listing could be accepted, and accepting it closed the listing: the seller had wanted to sell and got a loan instead.

## Decision

1. **A listing has an `availability`: Transfer, Loan, or Either.** Transfer is the default, and every listing made before this backfilled to it. This is a separate field from the sale type, because the sale type says *how* offers arrive and availability says *what* the club will consider.
2. **Availability limits the sale type.**
   - An **auction** is transfer-only: it sells to the highest bidder, and a loan cannot be auctioned.
   - A **fixed price** is a transfer price. A fixed-price listing may welcome loans too (Either), but cannot be loan-only.
   - A **loan-only** listing is Open to Offers.
3. **A loan-only listing carries no asking price.** A figure there reads as the player's price, both to buyers and to the fair-value signal, which compares an asking price with the model's valuation of the player. Clubs propose the loan fee and wage share in their offers instead.
4. **An offer against a listing must be one the listing invites.** A permanent offer on a loan-only listing is refused, and so is a loan offer on a transfer-only listing. The offer form offers only the invited type, and starts on Loan for a loan-only listing.
5. **"Available for loan" on the listings page means loan-only *or* either**, because both answer the buyer's actual question: could I loan him?

## Alternatives considered

- **A fourth sale type, `LOAN`.** Rejected: loan versus transfer and auction versus offers are independent choices. As one enum, "either" would need its own value per sale type, and an auction loan would be expressible.
- **Let any listing take any offer, and label only.** Rejected: that keeps the defect where a loan quietly closes a sale listing.
- **An asking loan fee on loan-only listings.** Deferred. It would need its own field and must stay out of the fair-value comparison. Nothing asked for it, and the offer is where loan terms are proposed.

## Consequences

- Accepting any offer still closes its listing, including a loan offer on an Either listing. Once the loan completes, the parent can list him again.
- The player-level `open_to_offers` flag is unchanged and still says nothing about loans. ADR 0003's deferred merge of the flag and listings now has a third dimension to consider.
- Migration `0074`.

## Related documents

- [`0003-listing-a-player.md`](./0003-listing-a-player.md) — where and how a player is listed
- [`../../feature_spec/loan-transfers.md`](../../feature_spec/loan-transfers.md) — the loan feature this completes
