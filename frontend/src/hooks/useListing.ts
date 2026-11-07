import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import api from "../lib/api";
import type { Paginated, Sale } from "../types/api";

/**
 * The club's open listings, plus who is listed (player id → listing id).
 *
 * My Club, the player page and the listing form all ask "is he already
 * listed?", and they share this one query so they agree. Keep the key and the
 * params here only: two callers on the same key with different params would
 * silently share whichever response landed first. page_size is 100 because an
 * incomplete list shows a List button for a player who is already listed.
 */
export function useOpenListings(clubId: string | undefined, enabled = true) {
  const query = useQuery<Paginated<Sale>>({
    queryKey: ["sales", { sellerClubId: clubId, status: "OPEN" }],
    queryFn: () =>
      api.get<Paginated<Sale>>("/sales", { params: { seller_club_id: clubId, status: "OPEN", page_size: 100 } })
        .then((r) => r.data),
    enabled: !!clubId && enabled,
  });

  const byPlayer = useMemo(
    () => new Map((query.data?.items ?? []).map((s) => [s.player_id, s.id])),
    [query.data],
  );

  return { ...query, byPlayer };
}
