import { useMutation, useQuery } from "@tanstack/react-query";

import api from "../lib/api";
import type {
  AskAnswer,
  ClubBriefing,
  DealNextSteps,
  ListingAdvice,
  NegotiationSummary,
  OfferAdvice,
  DraftKind,
  OfferCheckResponse,
  SuggestionStat,
  PotentialBuyers,
} from "../types/api";

/**
 * The workflow assistant (backend/app/ai/assist.py). The server caches every
 * answer against the state it describes, so these queries can be generous
 * with staleTime; answers that need a model are fetched only when the user
 * asks (`enabled`), since each fresh one counts against their hourly AI limit.
 */

export function useAIStatus() {
  return useQuery<{ available: boolean }>({
    queryKey: ["ai", "status"],
    queryFn: () => api.get<{ available: boolean }>("/ai/status").then((r) => r.data),
    staleTime: 10 * 60 * 1000,
    retry: false,
  });
}

export function useOfferAdvice(offerId: string, lastActionAt: string, enabled: boolean) {
  return useQuery<OfferAdvice>({
    queryKey: ["ai", "offer-advice", offerId, lastActionAt],
    queryFn: () => api.get<OfferAdvice>(`/ai/offers/${offerId}/advice`).then((r) => r.data),
    enabled,
    staleTime: Infinity,
    retry: false,
  });
}

export function useNegotiationSummary(offerId: string, lastActionAt: string, enabled: boolean) {
  return useQuery<NegotiationSummary>({
    queryKey: ["ai", "negotiation-summary", offerId, lastActionAt],
    queryFn: () => api.get<NegotiationSummary>(`/ai/offers/${offerId}/summary`).then((r) => r.data),
    enabled,
    staleTime: Infinity,
    retry: false,
  });
}

/** Rule-based checks — no model, so safe to run as the user types. */
export function useOfferCheck(body: { offer_id?: string; terms: Record<string, unknown> } | null) {
  return useQuery<OfferCheckResponse>({
    queryKey: ["ai", "offer-check", body],
    queryFn: () => api.post<OfferCheckResponse>("/ai/offer-check", body).then((r) => r.data),
    enabled: body != null,
    staleTime: 60_000,
    retry: false,
    placeholderData: (prev) => prev,
  });
}

export function useDealNextSteps(dealId: string | undefined, version: string) {
  return useQuery<DealNextSteps>({
    queryKey: ["ai", "deal-next-steps", dealId, version],
    queryFn: () => api.get<DealNextSteps>(`/ai/deals/${dealId}/next-steps`).then((r) => r.data),
    enabled: !!dealId,
    staleTime: 60_000,
    retry: false,
  });
}

export function useBriefing(enabled: boolean) {
  return useQuery<ClubBriefing | null>({
    queryKey: ["ai", "briefing"],
    queryFn: () => api.get<ClubBriefing | null>("/ai/briefing").then((r) => r.data),
    enabled,
    staleTime: 30 * 60 * 1000,
    retry: false,
  });
}

export function useListingAdvice(playerId: string | undefined, enabled: boolean) {
  return useQuery<ListingAdvice>({
    queryKey: ["ai", "listing-advice", playerId],
    queryFn: () => api.get<ListingAdvice>(`/ai/listing-advice/${playerId}`).then((r) => r.data),
    enabled: enabled && !!playerId,
    staleTime: 30 * 60 * 1000,
    retry: false,
  });
}

export function usePotentialBuyers(playerId: string, enabled: boolean) {
  return useQuery<PotentialBuyers>({
    queryKey: ["ai", "potential-buyers", playerId],
    queryFn: () => api.get<PotentialBuyers>(`/ai/potential-buyers/${playerId}`).then((r) => r.data),
    enabled,
    staleTime: 60 * 60 * 1000,
    retry: false,
  });
}

export function useAsk() {
  return useMutation<AskAnswer, Error, string>({
    mutationFn: (question: string) => api.post<AskAnswer>("/ai/ask", { question }).then((r) => r.data),
    retry: false,
  });
}

/** Ask in Lite: short answers, Lite links, and checked proposals. */
export function useLiteAsk() {
  return useMutation<AskAnswer, Error, { question: string; input: "text" | "voice" }>({
    mutationFn: (body) => api.post<AskAnswer>("/ai/ask", { ...body, lite: true }).then((r) => r.data),
    retry: false,
  });
}

/** A draft for the user to edit and send themselves (POST /ai/draft). */
export function useDraft() {
  return useMutation<{ kind: DraftKind; text: string }, Error, { kind: DraftKind; id: string; channel?: string; intent?: string }>({
    mutationFn: (body) => api.post<{ kind: DraftKind; text: string }>("/ai/draft", body).then((r) => r.data),
    retry: false,
  });
}

/** Tell TransferX a draft was sent largely as written (suggestion tracking). */
export function reportDraftUsed(kind: DraftKind, ref: string) {
  return api.post("/ai/suggestions/used", { feature: `draft_${kind}`, ref }).catch(() => undefined);
}

export function useSuggestionStats(days: number) {
  return useQuery<{ days: number; features: SuggestionStat[] }>({
    queryKey: ["ai", "suggestion-stats", days],
    queryFn: () => api.get("/ai/suggestions/stats", { params: { days } }).then((r) => r.data),
  });
}
