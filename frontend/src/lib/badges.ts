import type { BadgeVariant } from "../components/ui/Badge";
import type {
  DealStage,
  DealStatus,
  DealType,
  ListingAvailability,
  OfferStatus,
  PlayerPosition,
  PlayerStatus,
  SaleStatus,
  SaleType,
} from "../types/enums";
import type { AlertSeverity, AlertType } from "../types/api";

/** Positions are categories, so neutral: never a status colour (TOKENS.md). */
export function positionVariant(_pos: PlayerPosition): BadgeVariant {
  return "neutral";
}

// EXTERNAL reads as "Contracted" to a buyer — the actionable fact is identical
// (this player belongs to someone), and the club name shown alongside already
// says who. It must never get FREE_AGENT's green "opportunity" styling: that
// combination is exactly what made ~7.8k contracted professionals look
// available. See ADR 0003.
const PLAYER_STATUS_VARIANT: Record<PlayerStatus, BadgeVariant> = {
  CONTRACTED: "neutral",
  EXTERNAL:   "neutral",
  FREE_AGENT: "success",
};

const PLAYER_STATUS_LABEL: Record<PlayerStatus, string> = {
  CONTRACTED: "Contracted",
  EXTERNAL:   "Contracted",
  FREE_AGENT: "Free Agent",
};

export function playerStatusVariant(s: PlayerStatus): BadgeVariant {
  return PLAYER_STATUS_VARIANT[s] ?? "neutral";
}

export function playerStatusLabel(s: PlayerStatus): string {
  return PLAYER_STATUS_LABEL[s] ?? "Contracted";
}

export function saleTypeVariant(t: SaleType): BadgeVariant {
  const map: Record<SaleType, BadgeVariant> = {
    AUCTION:        "warning",
    OPEN_TO_OFFERS: "neutral",
    FIXED_PRICE:    "neutral",
  };
  return map[t];
}

export function saleTypeLabel(t: SaleType): string {
  const map: Record<SaleType, string> = {
    AUCTION:        "Auction",
    OPEN_TO_OFFERS: "Open to Offers",
    FIXED_PRICE:    "Fixed Price",
  };
  return map[t];
}

/** Null for a transfer-only listing: that is what every listing was before
 *  loans could be listed, so it needs no badge. */
export function availabilityLabel(a: ListingAvailability | undefined): string | null {
  if (a === "LOAN") return "Loan only";
  if (a === "EITHER") return "Transfer or loan";
  return null;
}

export function saleStatusVariant(s: SaleStatus): BadgeVariant {
  const map: Record<SaleStatus, BadgeVariant> = {
    OPEN:      "success",
    CLOSED:    "neutral",
    WITHDRAWN: "danger",
    EXPIRED:   "neutral",
  };
  return map[s];
}

export function saleStatusLabel(s: SaleStatus): string {
  const map: Record<SaleStatus, string> = {
    OPEN:      "Open",
    CLOSED:    "Closed",
    WITHDRAWN: "Withdrawn",
    EXPIRED:   "Expired",
  };
  return map[s] ?? s;
}

export function offerStatusVariant(s: OfferStatus): BadgeVariant {
  const map: Record<OfferStatus, BadgeVariant> = {
    DRAFT:     "neutral",
    SENT:      "neutral",
    COUNTERED: "warning",
    ACCEPTED:  "success",
    REJECTED:  "danger",
    WITHDRAWN: "neutral",
    EXPIRED:   "neutral",
  };
  return map[s];
}

export function offerStatusLabel(s: OfferStatus): string {
  const map: Record<OfferStatus, string> = {
    DRAFT:     "Draft",
    SENT:      "Sent",
    COUNTERED: "Countered",
    ACCEPTED:  "Accepted",
    REJECTED:  "Rejected",
    WITHDRAWN: "Withdrawn",
    EXPIRED:   "Expired",
  };
  return map[s] ?? s;
}

/**
 * What actually became of an offer.
 *
 * `Offer.status` is truthful but stops early: it says ACCEPTED — in the green
 * `success` badge — whether the deal then completed or collapsed at personal
 * terms. Once a deal exists it owns the outcome, so the deal's state is what
 * gets shown, with the offer status demoted to `note`.
 */
export function offerOutcome(
  status: OfferStatus,
  deal?: { status: DealStatus; stage: string | null } | null,
): { label: string; variant: BadgeVariant; note?: string } {
  if (!deal) return { label: offerStatusLabel(status), variant: offerStatusVariant(status) };

  if (deal.status === "COLLAPSED") {
    const where = deal.stage ? dealStageLabel(deal.stage as DealStage).toLowerCase() : null;
    return {
      label: "Collapsed",
      variant: "danger",
      note: where ? `at ${where}` : "after acceptance",
    };
  }
  if (deal.status === "COMPLETED") {
    return { label: "Completed", variant: "success", note: "transfer done" };
  }
  // IN_PROGRESS / PENDING_COMPLETION — the live stage is the useful fact
  return {
    label: deal.stage ? dealStageLabel(deal.stage as DealStage) : "In progress",
    variant: "neutral",
    note: "deal in progress",
  };
}

export function dealStatusVariant(s: DealStatus): BadgeVariant {
  const map: Record<DealStatus, BadgeVariant> = {
    IN_PROGRESS:        "neutral",
    PENDING_COMPLETION: "warning",
    COMPLETED:          "success",
    COLLAPSED:          "danger",
  };
  return map[s];
}

export function dealStageLabel(s: DealStage): string {
  const map: Record<DealStage, string> = {
    AGREEMENT:          "Agreement",
    AGENT_NEGOTIATION:  "Agent Negotiation",
    PERSONAL_TERMS:     "Personal Terms",
    PAPERWORK:          "Paperwork",
    CONFIRMED:          "Ready to Execute",
    COMPLETED:          "Completed",
  };
  return map[s] ?? s;
}

export function dealTypeLabel(t: DealType): string {
  const map: Record<DealType, string> = {
    PERMANENT:      "Permanent",
    LOAN:           "Loan",
    FREE_TRANSFER:  "Free transfer",
    PRE_CONTRACT:   "Pre-contract",
  };
  return map[t] ?? t;
}

// ── TRA-134/135: client-roster alerts ─────────────────────────────────────────

export const ALERT_SEVERITY_COLORS: Record<AlertSeverity, string> = {
  RED:   "bg-danger-bg text-danger-text ring-danger-ring",
  AMBER: "bg-warning-bg text-warning-text ring-warning-ring",
  GREEN: "bg-success-bg text-success-text ring-success-ring",
};

export const ALERT_SEVERITY_DOT: Record<AlertSeverity, string> = {
  RED:   "bg-danger-text",
  AMBER: "bg-warning-text",
  GREEN: "bg-success-text",
};

export const ALERT_TYPE_LABELS: Record<AlertType, string> = {
  CONTRACT_EXPIRY:  "Contract expiry",
  VALUATION_CHANGE: "Valuation change",
  CLUB_INTEREST:    "Club interest",
};
