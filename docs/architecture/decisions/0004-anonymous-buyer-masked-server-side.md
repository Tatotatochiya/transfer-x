---
title: "ADR 0004: An Anonymous Buyer Is Masked Server-Side, Not Hidden In The UI"
last_updated: 2026-08-13
status: Accepted
owner: "TODO — assign a Technical Lead"
---

# ADR 0004: An Anonymous Buyer Is Masked Server-Side, Not Hidden In The UI

## Context

Clubs routinely approach for a player without wanting the interest known — it moves the price, alerts rivals, and unsettles the player. TransferX had no way to express that: every offer named its buying club to the seller, permanently and unconditionally.

The obvious implementation — return the club as normal and have the frontend not render the name — would have been wrong in a way that is easy to miss and hard to detect afterwards. `OfferResponse` identifies the buying club through **five** separate fields:

| Field | How it identifies the buyer |
|---|---|
| `from_club` | the name, directly |
| `from_club_id` | resolves via `GET /clubs/{id}` |
| `last_actor_club_id` | is the buyer's id whenever the buyer acted last |
| `messages[].sender_club_id` / `sender_club` | every message the buyer sent |
| `events[].actor_club_id` | every negotiation event the buyer caused |

Four of those five are ids rather than names. A UI that hides the name leaves the identity one `GET /clubs/{id}` away for anyone who opens developer tools — while looking, to everyone reviewing it, entirely correct.

The competition order book (`GET /offers/competition/{player_id}`) is a sixth surface: it names every club bidding for a player, which is precisely what an anonymous buyer is paying to avoid.

## Decision

**Anonymity is enforced server-side, in one place.** `offers/router.py::_offer_response` is the single function every offer response is built through, and it is where masking happens — `_buyer_is_masked` decides, `_mask_buyer` strips. No endpoint serialises an offer any other way, so no endpoint can forget.

Supporting decisions:

- **The ids are stripped alongside the name.** `from_club_id` is nulled, and `last_actor_club_id` / message senders / event actors are nulled *only where they hold the buyer's id* — the seller's own actions are untouched, because the seller is not the one being concealed.
- **Per offer, not per club.** A club may be open about one target and discreet about another; anonymity is a property of an approach, not a standing preference. Stored as `offers.is_anonymous`.
- **The fact of anonymity is never hidden — only the identity.** The seller always sees `is_anonymous: true` and an explicit "Anonymous" marker. Accepting an offer is binding, and a seller has to know they are agreeing with an undisclosed counterparty before they decide, even if they cannot know which one.
- **Acceptance reveals; nothing else does.** Rejection, withdrawal and expiry leave the buyer permanently undisclosed. This is the feature working, not a gap in the reveal: interest that came to nothing was never disclosed.
- **The order book masks anonymous rivals too**, showing `A {league} club` with a null id. `OrderBookClubSummary.id` became nullable rather than carrying a placeholder that looks resolvable but isn't.
- **Administrators are not special-cased in the mask.** They never reach that path — `admin/router.py` validates `OfferResponse` straight off the ORM row, so staff see the real club. This is recorded in `_buyer_is_masked`'s docstring so a future refactor has to opt out deliberately rather than inherit access by accident.

## Alternatives considered

- **Hide the name in the frontend.** Cheapest, no migration, no API change. Rejected: it does not hide anything. Four of the five identifying fields are ids that resolve through an endpoint the seller is already authorised to call, so the anonymity would be decorative — and decorative privacy is worse than none, because the buyer would act on a guarantee that does not hold.
- **Mask at each endpoint.** Rejected for the reason [ADR 0003](./0003-player-status-distinguishes-external-clubs.md) documents at length: that codebase already had four independent copies of a display-layer override for player status, every one of which patched a read path while the write path stayed open. Repeating the shape here would mean one forgotten endpoint silently voids the guarantee.
- **Hide the buyer permanently, never revealing.** Rejected: a completed transfer has a real counterparty with contractual obligations, a registration, and a payment schedule. Anonymity that survives acceptance is not deliverable.
- **Anonymity as a club-wide setting.** Rejected: it conflates two different decisions and would make a club either always-visible or always-hidden, when the useful case is being discreet about one specific target.

## Consequences

- `OfferResponse.from_club_id` is now nullable. Callers that assumed a buying-club id is always present must handle its absence — in the frontend this is benign, since `from_club_id === myClubId` (the direction check) is false either way for a seller.
- **Auction bids are unchanged.** `Bid` is a separate model with its own order book, and carries no anonymity. A buyer can therefore be anonymous on an offer and named on a bid for the same player. Extending it is a contained follow-up, not an oversight to be discovered later.
- Tests assert the buyer's club id appears **nowhere in the serialised payload**, rather than that the name is hidden — the weaker assertion would pass against the broken UI-only implementation this ADR rejects.
- Anything added to `OfferResponse` later that carries club identity must be masked in `_mask_buyer` too. The five current fields are enumerated there; a sixth would not mask itself.

## Related documents

- [`0003-player-status-distinguishes-external-clubs.md`](./0003-player-status-distinguishes-external-clubs.md) — the display-layer-override failure mode this decision deliberately avoids repeating
- [`../../security-and-compliance/permissions-model.md`](../../security-and-compliance/permissions-model.md) — who may see what, more broadly
- [`../../CHANGELOG.md`](../../CHANGELOG.md)
