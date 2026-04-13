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
    AGREEMENT: "Agreement",
    PAPERWORK: "Paperwork",
    CONFIRMED: "Ready to Execute",
    COMPLETED: "Completed",
  };
  return map[s];
}
