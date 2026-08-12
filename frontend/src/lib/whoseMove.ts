import type { Deal, Offer, Sale } from "../types/api";

export type WhoseMove = "your" | "their" | "neither";

/**
 * Client-side "whose move" derivation — a stand-in for the backend
 * `whose_move` field (B1) proposed in docs/design_handoff_transferx/README.md,
 * which doesn't exist yet. Every rule here is the literal rule from that
 * doc; this is real logic against the real API shapes, not a placeholder.
 *
 * TODO(B1): once the backend field ships, every call site should read it
 * directly and this whole file can be deleted — that's the point of having
 * exactly one place this logic lives, per README.md's own instruction.
 */

const AGENT_SILENCE_HOURS = 72;
const AUCTION_CLOSING_SOON_HOURS = 48;

function hoursSince(iso: string): number {
  return (Date.now() - new Date(iso).getTime()) / 3_600_000;
}

const OFFER_TERMINAL_STATUSES = new Set(["ACCEPTED", "REJECTED", "WITHDRAWN", "EXPIRED"]);

/** Offer where status = COUNTERED/SENT and the other club acted last → your
 * move. Offer where this club acted last → their move. Terminal → neither. */
export function offerWhoseMove(offer: Offer, myClubId: string): WhoseMove {
  if (OFFER_TERMINAL_STATUSES.has(offer.status)) return "neither";
  return offer.last_actor_club_id === myClubId ? "their" : "your";
}

/** Deal at CONFIRMED (either participant can execute) → your move. Deal at
 * AGENT_NEGOTIATION with the agent silent >=72h → your move (chasing is an
 * action — the resolved DECISIONS.md default). PERSONAL_TERMS/PAPERWORK
 * wait on the player or on staff, not on either club → neither. AGREEMENT
 * has no per-club "last actor" signal available on this shape → neither,
 * rather than guessing. */
export function dealWhoseMove(deal: Deal, myClubId: string): WhoseMove {
  if (deal.status === "COMPLETED" || deal.status === "COLLAPSED") return "neither";

  switch (deal.stage) {
    case "CONFIRMED":
      return "your";
    case "AGENT_NEGOTIATION":
      // No agent-response timestamp on this shape (list responses don't
      // embed AgentNegotiation) — updated_at is the best available proxy
      // for "how long has this state persisted".
      return hoursSince(deal.updated_at) >= AGENT_SILENCE_HOURS ? "your" : "their";
    case "PERSONAL_TERMS":
    case "PAPERWORK":
      return "neither";
    default:
      return "neither";
  }
}

/** Human-readable reason to sit beside a deal's whose-move label on the
 * deals list (SCREENS.md: "You — signature", "Agent — 4 days idle"). Mirrors
 * dealWhoseMove's own stage/threshold logic exactly — kept as a second
 * function rather than a tuple return so existing dealWhoseMove call sites
 * (badges, filters) don't have to unpack a reason they don't use. */
export function dealWhoseMoveReason(deal: Deal): string {
  if (deal.status === "COMPLETED" || deal.status === "COLLAPSED") return "";

  switch (deal.stage) {
    case "CONFIRMED":
      return "You — signature";
    case "AGENT_NEGOTIATION": {
      const days = Math.floor(hoursSince(deal.updated_at) / 24);
      return hoursSince(deal.updated_at) >= AGENT_SILENCE_HOURS
        ? `Agent — ${days} day${days === 1 ? "" : "s"} idle`
        : "Agent — negotiating";
    }
    case "PERSONAL_TERMS":
      return "Player — consent pending";
    case "PAPERWORK":
      return "TransferX — processing";
    default:
      return "Clubs — agreeing terms";
  }
}

/** Listing with no bids → neither. Auction with a bid meeting reserve and
 * the deadline inside 48h → your move (the seller needs to decide before
 * it closes on its own). Reserve/bid data is only ever populated for the
 * seller/staff viewer to begin with (TRA-139), so this is inherently
 * seller-side — exactly the dashboard's own context. */
export function saleWhoseMove(sale: Sale): WhoseMove {
  if (!sale.bid_count) return "neither";
  if (sale.reserve_met && sale.deadline) {
    const hoursUntilClose = -hoursSince(sale.deadline); // positive while still open
    if (hoursUntilClose >= 0 && hoursUntilClose <= AUCTION_CLOSING_SOON_HOURS) return "your";
  }
  return "neither";
}

export const WHOSE_MOVE_LABEL: Record<WhoseMove, string> = {
  your: "Your move",
  their: "Their move",
  neither: "—",
};
