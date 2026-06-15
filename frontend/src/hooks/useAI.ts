import { useMutation, useQuery } from "@tanstack/react-query";

import api from "../lib/api";
import type {
  MarketRecommendationsResponse,
  NLSearchResponse,
  PlayerFitResponse,
  ShortlistReviewResponse,
  SquadAnalysisResponse,
} from "../types/api";

export function useSquadAnalysis(enabled: boolean, forceRefresh = false) {
  return useQuery<SquadAnalysisResponse>({
    queryKey: ["ai", "squad-analysis", forceRefresh],
    queryFn: () =>
      api
        .post<SquadAnalysisResponse>(
          "/ai/squad-analysis",
          null,
          forceRefresh ? { params: { force_refresh: true } } : {},
        )
        .then((r) => r.data),
    enabled,
    staleTime: 60 * 60 * 1000,
    retry: false,
  });
}

export function usePlayerFit(playerId: string, enabled: boolean) {
  return useQuery<PlayerFitResponse>({
    queryKey: ["ai", "player-fit", playerId],
    queryFn: () =>
      api.get<PlayerFitResponse>(`/ai/player-fit/${playerId}`).then((r) => r.data),
    enabled,
    staleTime: 60 * 60 * 1000,
    retry: false,
  });
}

export function useShortlistReview(shortlistId: string, enabled: boolean, forceRefresh = false) {
  return useQuery<ShortlistReviewResponse>({
    queryKey: ["ai", "shortlist-review", shortlistId, forceRefresh],
    queryFn: () =>
      api
        .get<ShortlistReviewResponse>(`/ai/shortlist-review/${shortlistId}`, {
          params: forceRefresh ? { force_refresh: true } : {},
        })
        .then((r) => r.data),
    enabled: enabled && !!shortlistId,
    staleTime: 30 * 60 * 1000,
    retry: false,
  });
}

export function useNLPlayerSearch() {
  return useMutation<NLSearchResponse, Error, string>({
    mutationFn: (query: string) =>
      api.post<NLSearchResponse>("/ai/player-search", { query }).then((r) => r.data),
    retry: false,
  });
}

export function useMarketRecommendations(
  filters: {
    position?: string;
    max_budget?: number;
    min_age?: number;
    max_age?: number;
  },
  enabled: boolean,
) {
  return useQuery<MarketRecommendationsResponse>({
    queryKey: ["ai", "recommendations", filters],
    queryFn: () =>
      api
        .get<MarketRecommendationsResponse>("/ai/recommendations", {
          params: {
            ...(filters.position && { position: filters.position }),
            ...(filters.max_budget && { max_budget: filters.max_budget }),
            ...(filters.min_age && { min_age: filters.min_age }),
            ...(filters.max_age && { max_age: filters.max_age }),
          },
        })
        .then((r) => r.data),
    enabled,
    staleTime: 30 * 60 * 1000,
    retry: false,
  });
}
