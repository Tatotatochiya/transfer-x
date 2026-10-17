import { useQuery } from "@tanstack/react-query";

import api from "../lib/api";

export interface DeadlineItem {
  kind: "offer" | "deal" | "bid";
  id: string;
  side: "BUYING" | "SELLING";
  player_id: string;
  player_name: string;
  player_photo_url: string | null;
  counterparty: string | null;
  amount: number | null;
  stage: string;
  detail: string;
  /** The next step and who owns it: you | them | either | player | agent | staff. */
  next_step: { label: string; owner: string } | null;
  steps_left: number;
  needs_you: boolean;
  at_risk: boolean;
  link: string;
}

export interface DeadlineView {
  window: {
    state: "open" | "closed" | "none";
    name: string | null;
    closes_at: string | null;
    opens_at?: string | null;
    hours_left: number | null;
    deadline_mode: boolean;
  };
  items: DeadlineItem[];
  counts: { open: number; needs_you: number; at_risk: number; talking: number };
  hours_per_step: number;
}

/** Deadline-day mode: the club's open transfers against the window's close. */
export function useDeadline(enabled = true) {
  return useQuery<DeadlineView>({
    queryKey: ["deadline"],
    queryFn: () => api.get<DeadlineView>("/deadline").then((r) => r.data),
    enabled,
    staleTime: 30_000,
    refetchInterval: 60_000,
  });
}

/** "5h 12m", "2 days 4h", "under a minute": time left until `iso`. */
export function timeUntil(iso: string, now = Date.now()): string {
  const ms = new Date(iso).getTime() - now;
  if (ms <= 60_000) return ms <= 0 ? "closed" : "under a minute";
  const mins = Math.floor(ms / 60_000);
  const days = Math.floor(mins / 1440);
  const hours = Math.floor((mins % 1440) / 60);
  const m = mins % 60;
  if (days) return `${days} day${days === 1 ? "" : "s"} ${hours}h`;
  return hours ? `${hours}h ${m}m` : `${m}m`;
}
