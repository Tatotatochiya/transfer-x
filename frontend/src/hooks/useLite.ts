import { useQuery } from "@tanstack/react-query";

import api from "../lib/api";

export interface LiteTile {
  key: string;
  style: "accent" | "plain" | "offers" | "ai";
  title: string;
  subtitle: string;
  href: string;
  badge: string | null;
  disabled_reason: string | null;
}

export interface LiteHome {
  club_name: string;
  window: { state: "open" | "closed" | "none"; closes_at: string | null; next_opens_at: string | null; days: number | null };
  money: { transfer_remaining: number; transfer_budget: number; wage_remaining_weekly: number; as_of: string } | null;
  waiting: { count: number; club_names: string[] };
  tiles: LiteTile[];
  resume: { title: string; href: string } | null;
  briefing_headline: string | null;
}

/** Everything the Lite home shows, in one request. Never uses the AI allowance. */
export function useLiteHome() {
  return useQuery<LiteHome>({
    queryKey: ["lite", "home"],
    queryFn: () => api.get<LiteHome>("/lite/home").then((r) => r.data),
    staleTime: 60_000,
    refetchInterval: 300_000,
  });
}

// ── Buy flow (L3) ────────────────────────────────────────────────────────────

export type LitePosition = "GK" | "DEF" | "MID" | "FWD" | "ANY";
export type LiteBand = "0-5" | "5-10" | "10-20" | "free";

export interface LiteCandidate {
  player_id: string;
  name: string;
  age: number | null;
  position: string | null;
  club: string | null;
  free_agent: boolean;
  price: number;
  price_basis: string;
  sale_id: string | null;
  wage_weekly: number | null;
  reason: string;
}

export function useLiteSquadCounts() {
  return useQuery<{ counts: Record<string, number> }>({
    queryKey: ["lite", "buy", "squad"],
    queryFn: () => api.get("/lite/buy/squad").then((r) => r.data),
    staleTime: 5 * 60_000,
  });
}

export function useLiteCandidates(position: LitePosition | null, band: LiteBand | null) {
  return useQuery<{ players: LiteCandidate[]; squad_counts: Record<string, number> }>({
    queryKey: ["lite", "buy", "candidates", position, band],
    queryFn: () => api.get("/lite/buy/candidates", { params: { position, band } }).then((r) => r.data),
    enabled: !!position && !!band,
    staleTime: 10 * 60_000,
  });
}

// ── Action cards (L4) ────────────────────────────────────────────────────────

export interface LiteOfferDraft {
  player_id: string;
  name: string;
  age: number | null;
  position: string | null;
  to_club_id: string;
  to_club_name: string | null;
  sale_id: string | null;
  fee: number | null;
  fee_basis: string | null;
  asking_price: number | null;
  wage_weekly: number | null;
  contract_years: number;
  existing_offer_id: string | null;
  disabled_reason: string | null;
}

export function useLiteOfferDraft(playerId: string | null) {
  return useQuery<LiteOfferDraft>({
    queryKey: ["lite", "offer-draft", playerId],
    queryFn: () => api.get<LiteOfferDraft>("/lite/offer-draft", { params: { player_id: playerId } }).then((r) => r.data),
    enabled: !!playerId,
    retry: false,
  });
}

export interface LiteOfferCard {
  offer_id: string;
  side: "buyer" | "seller";
  status: string;
  player_id: string;
  player_name: string | null;
  other_club: string;
  deal_type: "PERMANENT" | "LOAN";
  fee: number;
  wage_weekly: number | null;
  wage_split_pct: number | null;
  contract_years: number | null;
  loan_start: string | null;
  loan_end: string | null;
  has_add_ons: boolean;
  your_move: boolean;
  counter_suggestion: number | null;
  disabled_reason: string | null;
  expires_at: string | null;
}

export function useLiteOfferCard(offerId: string | undefined) {
  return useQuery<LiteOfferCard>({
    queryKey: ["lite", "offer-card", offerId],
    queryFn: () => api.get<LiteOfferCard>(`/lite/offers/${offerId}`).then((r) => r.data),
    enabled: !!offerId,
    retry: false,
  });
}
