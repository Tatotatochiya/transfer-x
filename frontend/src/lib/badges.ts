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
  StaffRole,
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

// ── Admin deal-pipeline monitoring ──────────────────────────────────────────
// H2 (admin audit): every stage a deal can sit in while IN_PROGRESS, in order —
// single source of truth for the dashboard pipeline bar, the admin deals
// kanban board, and staleness detection, so AGENT_NEGOTIATION/PERSONAL_TERMS
// can't quietly drop out of one surface while staying in another.

export type ActiveDealStage = Exclude<DealStage, "COMPLETED">;

export const ACTIVE_DEAL_STAGES: ActiveDealStage[] = [
  "AGREEMENT", "AGENT_NEGOTIATION", "PERSONAL_TERMS", "PAPERWORK", "CONFIRMED",
];

// Days a deal can sit in a stage before it's flagged stale. Early negotiation
// stages get the tighter 3-day bar; paperwork/execution get a week.
export const DEAL_STAGE_STALE_DAYS: Record<ActiveDealStage, number> = {
  AGREEMENT:         3,
  AGENT_NEGOTIATION: 3,
  PERSONAL_TERMS:    3,
  PAPERWORK:         7,
  CONFIRMED:         7,
};

export const DEAL_STAGE_COLOR: Record<ActiveDealStage, { text: string; bg: string; border: string }> = {
  AGREEMENT:         { text: "text-amber-400",   bg: "bg-amber-500",   border: "border-amber-500/30" },
  AGENT_NEGOTIATION: { text: "text-violet-400",  bg: "bg-violet-500",  border: "border-violet-500/30" },
  PERSONAL_TERMS:    { text: "text-pink-400",    bg: "bg-pink-500",    border: "border-pink-500/30" },
  PAPERWORK:         { text: "text-sky-400",     bg: "bg-sky-500",     border: "border-sky-500/30" },
  CONFIRMED:         { text: "text-emerald-400", bg: "bg-emerald-500", border: "border-emerald-500/30" },
};

// ── Club staff roles ─────────────────────────────────────────────────────────
// Single source of truth for the four StaffRole values and their plain-language
// descriptions (straight from the D1 capability matrix) — shared between the
// club's own team page and the admin staff panel, so the two surfaces can't
// drift into showing different roles or different explanations of the same role.

export const STAFF_ROLE_INFO: Record<StaffRole, { label: string; description: string; badge: BadgeVariant }> = {
  SPORTING_DIRECTOR: {
    label: "Sporting Director",
    description: "Full deal authority: market, deals, club profile, and deciding spending approvals. Cannot manage the team itself.",
    badge: "success",
  },
  MANAGER: {
    label: "Manager",
    description: "Runs the market and deals day to day: listings, bids, offers, deal-room actions. Large spends can require approval.",
    badge: "info",
  },
  SCOUT: {
    label: "Scout",
    description: "Scouting only: shortlists, player interest, and market views. Cannot bid, offer, or touch deals.",
    badge: "warning",
  },
  READONLY: {
    label: "Read-only",
    description: "Sees everything the club sees — squad, finance, listings, deals — and can change nothing.",
    badge: "neutral",
  },
};

export const STAFF_ROLE_ORDER: StaffRole[] = ["SPORTING_DIRECTOR", "MANAGER", "SCOUT", "READONLY"];

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
