export type ClubRole = "SELLER" | "BUYER" | "BOTH" | "ADMIN";

export type PlayerPosition = "GK" | "DEF" | "MID" | "FWD";
export type PlayerVisibility = "PUBLIC" | "CLUBS_ONLY" | "PRIVATE";
// EXTERNAL = under contract to a real-world club that isn't on TransferX
// (ADR 0003). Not signable; never presented as an available player.
export type PlayerStatus = "CONTRACTED" | "EXTERNAL" | "FREE_AGENT";

export type SaleType = "AUCTION" | "OPEN_TO_OFFERS" | "FIXED_PRICE";
export type SaleStatus = "OPEN" | "CLOSED" | "WITHDRAWN" | "EXPIRED";
export type BidStatus = "ACTIVE" | "WITHDRAWN" | "ACCEPTED" | "REJECTED";

export type OfferStatus =
  | "DRAFT"
  | "SENT"
  | "COUNTERED"
  | "ACCEPTED"
  | "REJECTED"
  | "WITHDRAWN"
  | "EXPIRED";

export type OfferEventType =
  | "CREATED"
  | "SENT"
  | "COUNTERED"
  | "ACCEPTED"
  | "REJECTED"
  | "WITHDRAWN"
  | "EXPIRED"
  | "MESSAGE";

export type DealStatus =
  | "IN_PROGRESS"
  | "PENDING_COMPLETION"
  | "COMPLETED"
  | "COLLAPSED";

export type DealStage =
  | "AGREEMENT"
  | "AGENT_NEGOTIATION"
  | "PERSONAL_TERMS"
  | "PAPERWORK"
  | "CONFIRMED"
  | "COMPLETED";

export type DealType = "PERMANENT" | "LOAN";
export type ClauseType = "APPEARANCES" | "GOALS" | "PROMOTION" | "RESALE" | "OTHER";
export type ClauseStatus = "PENDING" | "TRIGGERED" | "PAID";
export type MedicalStatus = "PENDING" | "PASSED" | "FAILED";
export type AgreementStatus = "PENDING" | "AGREED" | "DECLINED";
export type NegotiationStatus = "IN_PROGRESS" | "TERMS_AGREED" | "COLLAPSED";
export type CommissionPayer = "BUYER" | "SELLER" | "PLAYER";

export type NotificationType =
  | "OUTBID"
  | "OFFER_RECEIVED"
  | "OFFER_ACCEPTED"
  | "OFFER_REJECTED"
  | "OFFER_COUNTERED"
  | "OFFER_WITHDRAWN"
  | "OFFER_EXPIRING"
  | "OFFER_MESSAGE"
  | "AUCTION_BID_RECEIVED"
  | "AUCTION_ENDING"
  | "AUCTION_BID_ACCEPTED"
  | "DEAL_COMPLETED"
  | "DEAL_COLLAPSED"
  | "DEAL_SELL_ON"
  | "DEAL_AGENT_INVITED"
  | "DEAL_PERSONAL_TERMS_SENT"
  | "PLAYER_AVAILABLE"
  | "VERIFICATION_APPROVED"
  | "VERIFICATION_REJECTED"
  | "REPRESENTATION_STARTED"
  | "REPRESENTATION_REVOKED"
  | "PERSONAL_TERMS_DECISION"
  | "INSTALMENT_DUE"
  | "DEAL_CLAUSE_TRIGGERED"
  | "NEGOTIATION_MESSAGE"
  | "CLIENT_ALERT"
  | "STAFF_INVITATION"
  | "APPROVAL_REQUESTED"
  | "APPROVAL_DECIDED";

// TRA-151 — club roles & capabilities (server matrix is the only truth; the
// UI only ever consumes the capability list from GET /clubs/me/membership)
export type StaffRole = "SPORTING_DIRECTOR" | "MANAGER" | "SCOUT" | "READONLY";
export type ClubMemberRole = "OWNER" | StaffRole;
export type ClubCapability =
  | "SCOUTING_WRITE"
  | "MARKET_WRITE"
  | "DEAL_WRITE"
  | "CLUB_ADMIN"
  | "TEAM_MANAGE"
  | "APPROVE_ACTIONS";

// Phase 5 — spending-authority approvals
export type ApprovalActionType = "PLACE_BID" | "CREATE_OFFER" | "ACCEPT_OFFER" | "ACCEPT_BID";
export type ApprovalStatus =
  | "PENDING"
  | "APPROVED_EXECUTED"
  | "APPROVED_FAILED"
  | "REJECTED"
  | "EXPIRED"
  | "CANCELLED";

export type ValuationSource = "ETV" | "TRANSFERMARKT" | "MANUAL";
export type WageSource = "CAPOLOGY" | "ESTIMATED" | "MANUAL";

// TRA-91/92 — fair-value model signal
export type ValuationConfidence = "HIGH" | "MEDIUM" | "LOW";
export type ValuationBand = "WELL_BELOW" | "BELOW" | "IN_LINE" | "ABOVE" | "WELL_ABOVE";

export type InterestLevel = "WATCHING" | "INTERESTED" | "PRIORITY";
export type InterestStage = "SCOUTED" | "CONTACTED" | "NEGOTIATING" | "DROPPED";
