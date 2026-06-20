export type ClubRole = "SELLER" | "BUYER" | "BOTH" | "ADMIN";

export type PlayerPosition = "GK" | "DEF" | "MID" | "FWD";
export type PlayerVisibility = "PUBLIC" | "CLUBS_ONLY" | "PRIVATE";
export type PlayerStatus = "CONTRACTED" | "FREE_AGENT";

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
  | "PLAYER_AVAILABLE";

export type InterestLevel = "WATCHING" | "INTERESTED" | "PRIORITY";
export type InterestStage = "SCOUTED" | "CONTACTED" | "NEGOTIATING" | "DROPPED";
