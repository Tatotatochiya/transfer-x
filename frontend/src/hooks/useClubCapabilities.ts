import { useQuery } from "@tanstack/react-query";
import api from "../lib/api";
import { useAuth } from "./useAuth";
import type { ClubMembership } from "../types/api";
import type { ClubCapability, ClubMemberRole } from "../types/enums";

export interface ClubCapabilities {
  membership: ClubMembership | null;
  role: ClubMemberRole | null;
  /** True while the membership is still loading — callers that gate
   * destructive-looking UI should treat loading as "hidden". */
  isLoading: boolean;
  can: (cap: ClubCapability) => boolean;
}

/**
 * TRA-151 (D3): the server capability matrix is the only truth — this hook
 * consumes GET /clubs/me/membership and never re-derives capability logic
 * client-side. Superusers bypass every check, mirroring the backend order.
 */
export function useClubCapabilities(): ClubCapabilities {
  const { isAuthenticated, isClub, isSuperuser } = useAuth();

  const query = useQuery<ClubMembership | null>({
    queryKey: ["clubs", "me", "membership"],
    queryFn: () =>
      api
        .get<ClubMembership>("/clubs/me/membership")
        .then((r) => r.data)
        .catch(() => null), // 404 = no club membership; never blocks a page
    enabled: isAuthenticated && isClub,
    staleTime: 60_000,
  });

  const membership = query.data ?? null;
  return {
    membership,
    role: membership?.role ?? null,
    isLoading: query.isLoading,
    can: (cap: ClubCapability) =>
      isSuperuser || (membership?.capabilities ?? []).includes(cap),
  };
}
