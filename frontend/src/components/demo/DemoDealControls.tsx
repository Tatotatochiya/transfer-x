import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import api from "../../lib/api";
import { useAuth } from "../../hooks/useAuth";
import { useToast } from "../../context/ToastContext";
import { getApiError } from "../../lib/utils";

/**
 * Demo mode: on a deal in your own demo that's waiting on the other side,
 * make its next move now (the house club's, the agent's or the player's)
 * instead of waiting (backend demo/house.py `make_deal_move`). Hidden on
 * every other deal, and while it's your move.
 */
export default function DemoDealControls({ dealId, waiting, waitingOn }: {
  dealId: string;
  /** The status card's tone is "wait": someone else holds the move. */
  waiting: boolean;
  /** "Waiting on the agent", from the status card. */
  waitingOn: string;
}) {
  const { canDemo } = useAuth();
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const { data } = useQuery<{ in_demo: boolean }>({
    queryKey: ["demo", "deal", dealId],
    queryFn: () => api.get<{ in_demo: boolean }>(`/demo/deals/${dealId}`).then((r) => r.data),
    enabled: canDemo,
  });
  const make = useMutation({
    mutationFn: () => api.post(`/demo/deals/${dealId}/make`),
    onSuccess: () => {
      queryClient.invalidateQueries();
      addToast("Done. They've made their move.", "success");
    },
    onError: (err) => addToast(getApiError(err, "Couldn't make that move."), "error"),
  });
  if (!data?.in_demo || !waiting) return null;
  return (
    <div role="region" aria-label="Demo controls" className="mt-3 flex flex-wrap items-center justify-between gap-x-4 gap-y-2 rounded-xl bg-warning-bg px-4 py-3 text-small ring-1 ring-warning-ring">
      <div className="min-w-0">
        <p className="font-semibold text-text">Demo: {waitingOn.replace(/^Waiting/, "waiting")}</p>
        <p className="mt-0.5 text-text-secondary">Make them move now instead of waiting. Reset undoes it like everything else.</p>
      </div>
      <button
        type="button"
        disabled={make.isPending}
        onClick={() => make.mutate()}
        className="rounded-lg bg-surface px-3 py-1 font-semibold text-text ring-1 ring-border hover:ring-accent disabled:opacity-60"
      >
        Make them move now
      </button>
    </div>
  );
}
