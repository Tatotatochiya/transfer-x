---
title: "ADR 0008: One Transfers Board, One Main Way to Buy, Lite Decides and the Full App Operates"
last_updated: 2026-10-04
status: Accepted
owner: "TODO — assign a Product Owner"
---

# ADR 0008: One Transfers Board, One Main Way to Buy, Lite Decides and the Full App Operates

## Context

A club's transfers were spread over six pages: Listings, My Listings, Offers sent, Offers received, Transfers in progress and Enquiries. The same player could appear on three of them at once, as an enquiry, an offer and a deal. There were three ways to sell (open to offers, auction, fixed price) and two apps (Lite and full) with no stated split between them. Phase 3 of the [Q4 plan](../../feature_spec/phased-plan-2026-q4/README.md) simplifies this. These are the four decisions it rests on.

## Decision

1. **One Transfers board.** Each card is one player the club is buying or selling, shown once, at its furthest point. Six columns:

   | Column | What's in it |
   |---|---|
   | Talking | Open enquiries; the club's listed players with no offer yet |
   | Offers | Offers sent or received that are still open; auction bids |
   | Fee agreed | Deals at the agreement stage |
   | Personal terms | Deals at agent negotiation or personal terms |
   | Paperwork | Deals at paperwork or confirmed (signature), with the medical and registration |
   | Done | Completed transfers |

   Filter by Buying, Selling or Both. Collapsed deals, rejected, withdrawn or expired offers, and ended listings go in a Closed drawer, not a column.

   The plan's draft called the fourth column "Terms & medical". The medical is a paperwork step in the stage machine, so the column is named Personal terms and the medical shows on the Paperwork card.
2. **One main way to buy: enquiry → offer → deal.** A new listing is open to offers by default. Auction and fixed price stay available, under "Advanced" when listing. Existing auctions keep working and appear on the board like any other listing.
3. **Lite decides; the full app operates.** Lite is the phone-first place to decide: offer cards, accept or counter with undo, approvals, the morning summary. The board, conversations and paperwork live in the full app. Lite links there for anything beyond a decision.
4. **The board ships alongside the old pages, which are retired once it covers everything.** It becomes the first item in the sidebar, and the six pages move under "Classic views". When the board and one-conversation-per-transfer cover what they did, the pages are removed and their URLs redirect to the board.

## Consequences

- A club sees each transfer once, with whose move it is, instead of piecing it together from six lists.
- The anonymous-buyer rules apply on the board exactly as elsewhere: a masked buyer shows as "A {league} club" until acceptance.
- Lite stays small. Features that operate a transfer (paperwork, documents, the conversation) are built for the full app.
- Retiring the old pages waits on the single conversation (Phase 3, item 2). Until then both exist.
