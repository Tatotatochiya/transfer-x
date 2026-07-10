import { useQuery } from "@tanstack/react-query";
import api from "../lib/api";
import { useAuth } from "./useAuth";
import type { AgentProfileResponse, Club, PlayerDetail } from "../types/api";

export type IdentityRole = "CLUB" | "AGENT" | "PLAYER";

export interface Identity {
  role: IdentityRole | null;
  name: string | null;
  subLabel: string | null;
  crestUrl: string | null;
  isSuperuser: boolean;
  isLoading: boolean;
}

/**
 * Who the current user actually is, normalized across the three account
 * types — one shared fetch (cached by React Query, same keys the dedicated
 * profile pages already use) instead of every screen that needs identity
 * re-deriving it from scratch.
 */
export function useIdentity(): Identity {
  const { isAuthenticated, isSuperuser, isClub, isAgent, isPlayer } = useAuth();

  const clubQuery = useQuery<Club>({
    queryKey: ["clubs", "me"],
    queryFn: () => api.get<Club>("/clubs/me").then((r) => r.data),
    enabled: isAuthenticated && isClub,
    staleTime: 60_000,
  });

  const agentQuery = useQuery<AgentProfileResponse>({
    queryKey: ["agents", "me"],
    queryFn: () => api.get<AgentProfileResponse>("/agents/me").then((r) => r.data),
    enabled: isAuthenticated && isAgent,
    staleTime: 60_000,
  });

  const playerQuery = useQuery<PlayerDetail>({
    queryKey: ["players", "me"],
    queryFn: () => api.get<PlayerDetail>("/players/me").then((r) => r.data),
    enabled: isAuthenticated && isPlayer,
    staleTime: 60_000,
  });

  if (isClub) {
    // TRA-151: staff members see their role in the identity footer —
    // "Staff: Sporting Director" — the owner keeps a clean club label.
    const myRole = clubQuery.data?.my_role;
    const staffLabel =
      myRole && myRole !== "OWNER"
        ? `Staff: ${myRole.replace(/_/g, " ").toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase())}`
        : null;
    return {
      role: "CLUB",
      name: clubQuery.data?.name ?? null,
      subLabel: staffLabel,
      crestUrl: clubQuery.data?.crest_url ?? null,
      isSuperuser,
      isLoading: clubQuery.isLoading,
    };
  }
  if (isAgent) {
    return {
      role: "AGENT",
      name: agentQuery.data?.display_name ?? null,
      subLabel: agentQuery.data?.agency_name ?? null,
      crestUrl: null,
      isSuperuser,
      isLoading: agentQuery.isLoading,
    };
  }
  if (isPlayer) {
    return {
      role: "PLAYER",
      name: playerQuery.data?.name ?? null,
      subLabel: null,
      crestUrl: null,
      isSuperuser,
      isLoading: playerQuery.isLoading,
    };
  }
  return { role: null, name: null, subLabel: null, crestUrl: null, isSuperuser, isLoading: false };
}
