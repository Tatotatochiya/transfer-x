import type { Offer } from "../types/api";

export type WhoseMove = "your" | "their" | "neither";

/**
 * "Whose move" labels, and the offer rule for offers listed without the
 * server's field. Deals read `whose_move` from the server
 * (compute_deal_whose_move), the one place that rule lives
 * (docs/design-system/README.md, "Whose move").
 */

const OFFER_TERMINAL_STATUSES = new Set(["ACCEPTED", "REJECTED", "WITHDRAWN", "EXPIRED"]);

/** Offer where status = COUNTERED/SENT and the other club acted last → your
 * move. Offer where this club acted last → their move. Terminal → neither. */
export function offerWhoseMove(offer: Offer, myClubId: string): WhoseMove {
  if (OFFER_TERMINAL_STATUSES.has(offer.status)) return "neither";
  return offer.last_actor_club_id === myClubId ? "their" : "your";
}

export const WHOSE_MOVE_LABEL: Record<WhoseMove, string> = {
  your: "Your move",
  their: "Their move",
  neither: "—",
};
