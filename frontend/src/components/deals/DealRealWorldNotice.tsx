import { useQuery } from "@tanstack/react-query";

import api from "../../lib/api";

export interface DealRealWorld {
  /** The deal can't complete until TransferX staff check his registration. */
  hold: string | null;
  /** A loan elsewhere in real life: worth knowing, nothing waits. */
  note: string | null;
  /** The buying club's transfer window is closed: it completes once it opens. */
  window: string | null;
  window_opens_at: string | null;
}

/**
 * What completion waits on besides the deal's own steps, for an open deal:
 * API-Football has the player at another club than the selling one
 * (players/real_world.deal_notice), or the buying club's transfer window is
 * closed (transfer_window/service.completion_hold). Completion is refused
 * while either holds; talks and paperwork carry on. The deal room's status
 * card says so (deal-room-focus §5.2, row 3 and R-e).
 */
export function useDealRealWorld(dealId: string | undefined, open: boolean) {
  return useQuery<DealRealWorld>({
    queryKey: ["deals", dealId, "real-world"],
    queryFn: () => api.get<DealRealWorld>(`/deals/${dealId}/real-world`).then((r) => r.data),
    enabled: open && !!dealId,
    staleTime: 5 * 60_000,
  });
}
