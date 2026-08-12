import { useQuery } from "@tanstack/react-query";
import api from "../lib/api";
import type { DashboardItem, DashboardResponse } from "../types/api";

/**
 * The club's "waiting on you" aggregate (backend item B2).
 *
 * One server-side call replaces both the War Room's five client-side queries
 * and any per-section counting the sidebar would otherwise have to do — the
 * `kind` on each item is what makes one response serve both. Shared query key
 * so the two consumers hit the same cache entry rather than the endpoint twice.
 */
export const CLUB_DASHBOARD_KEY = ["clubs", "me", "dashboard"] as const;

export function useClubDashboard(enabled: boolean) {
  return useQuery<DashboardResponse>({
    queryKey: CLUB_DASHBOARD_KEY,
    queryFn: () => api.get<DashboardResponse>("/clubs/me/dashboard").then((r) => r.data),
    enabled,
    staleTime: 60_000,
    refetchInterval: 300_000,
  });
}

/** Count of waiting items per `kind`, for the sidebar badges. */
export function countByKind(items: DashboardItem[] | undefined): Record<DashboardItem["kind"], number> {
  const counts: Record<DashboardItem["kind"], number> = { approval: 0, deal: 0, offer: 0, sale: 0 };
  for (const item of items ?? []) counts[item.kind] += 1;
  return counts;
}
