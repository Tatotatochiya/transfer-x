import type { Offer } from "../types/api";

/**
 * How to name the buying club on an offer.
 *
 * A buyer can approach without disclosing who they are, in which case the
 * server strips their name *and* id and hands back only their league — so
 * there is nothing here to un-hide, and nothing a caller can get wrong by
 * forgetting to check a flag. This exists so the wording stays identical
 * everywhere a masked buyer appears, not to enforce the masking itself.
 */
export function buyerLabel(offer: Offer, fallback = "?"): string {
  if (offer.from_club?.name) return offer.from_club.name;
  if (offer.is_anonymous) {
    return offer.buyer_league_name ? `A ${offer.buyer_league_name} club` : "An undisclosed club";
  }
  return fallback;
}

/** True when this viewer is being kept from the buyer's identity — for the
 *  "Anonymous" marker, which is shown to *both* parties: a seller has to know
 *  they're dealing with an undisclosed club even before they know which one. */
export function isBuyerMasked(offer: Offer): boolean {
  return offer.is_anonymous && !offer.from_club;
}
