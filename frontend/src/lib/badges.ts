import type { BadgeVariant } from "../components/ui/Badge";
import type {
  BidStatus,
  DealStage,
  DealStatus,
  OfferStatus,
  PlayerPosition,
  PlayerStatus,
  SaleStatus,
  SaleType,
} from "../types/enums";
import type { AlertSeverity, AlertType } from "../types/api";

export function positionVariant(_pos: PlayerPosition): BadgeVariant {
  // GK amber, DEF blue, MID emerald, FWD red
  const map: Record<PlayerPosition, BadgeVariant> = {
    GK:  "warning",
    DEF: "info",
    MID: "success",
    FWD: "danger",
  };
  return map[_pos];
}

export function playerStatusVariant(s: PlayerStatus): BadgeVariant {
  return s === "FREE_AGENT" ? "success" : "info";
}

export function playerStatusLabel(s: PlayerStatus): string {
  return s === "FREE_AGENT" ? "Free Agent" : "Contracted";
}

export function saleTypeVariant(t: SaleType): BadgeVariant {
  const map: Record<SaleType, BadgeVariant> = {
    AUCTION:        "warning",
    OPEN_TO_OFFERS: "info",
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

export function saleStatusVariant(s: SaleStatus): BadgeVariant {
  const map: Record<SaleStatus, BadgeVariant> = {
    OPEN:      "success",
    CLOSED:    "neutral",
    WITHDRAWN: "danger",
    EXPIRED:   "neutral",
  };
  return map[s];
}

export function offerStatusVariant(s: OfferStatus): BadgeVariant {
  const map: Record<OfferStatus, BadgeVariant> = {
    DRAFT:     "neutral",
    SENT:      "info",
    COUNTERED: "warning",
    ACCEPTED:  "success",
    REJECTED:  "danger",
    WITHDRAWN: "neutral",
    EXPIRED:   "neutral",
  };
  return map[s];
}

export function bidStatusVariant(s: BidStatus): BadgeVariant {
  const map: Record<BidStatus, BadgeVariant> = {
    ACTIVE:   "success",
    WITHDRAWN:"neutral",
    ACCEPTED: "success",
    REJECTED: "danger",
  };
  return map[s];
}

export function dealStatusVariant(s: DealStatus): BadgeVariant {
  const map: Record<DealStatus, BadgeVariant> = {
    IN_PROGRESS:        "info",
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

// ── TRA-134/135: client-roster alerts ─────────────────────────────────────────

export const ALERT_SEVERITY_COLORS: Record<AlertSeverity, string> = {
  RED:   "bg-red-500/15 text-red-400 ring-red-500/30",
  AMBER: "bg-amber-500/15 text-amber-400 ring-amber-500/30",
  GREEN: "bg-emerald-500/15 text-emerald-400 ring-emerald-500/30",
};

export const ALERT_SEVERITY_DOT: Record<AlertSeverity, string> = {
  RED:   "bg-red-400",
  AMBER: "bg-amber-400",
  GREEN: "bg-emerald-400",
};

export const ALERT_TYPE_LABELS: Record<AlertType, string> = {
  CONTRACT_EXPIRY:  "Contract expiry",
  VALUATION_CHANGE: "Valuation change",
  CLUB_INTEREST:    "Club interest",
};
