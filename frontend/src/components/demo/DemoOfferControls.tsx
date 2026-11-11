import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import api from "../../lib/api";
import { useAuth } from "../../hooks/useAuth";
import { useToast } from "../../context/ToastContext";
import { getApiError } from "../../lib/utils";

interface Controls {
  in_demo: boolean;
  house_club?: string;
  side?: "seller" | "buyer";
  house_move?: boolean;
  actions?: ("accept" | "counter" | "reject" | "withdraw")[];
}

const LABEL: Record<string, string> = { accept: "Accept", counter: "Counter", reject: "Reject", withdraw: "Walk away" };

/**
 * Demo mode: on an offer in your own demo where it's the house club's move,
 * make it accept, counter or reject now instead of waiting for its rules
 * (backend demo/house.py `make`). Hidden on every other offer.
 */
export default function DemoOfferControls({ offerId }: { offerId: string }) {
  const { canDemo } = useAuth();
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const [fee, setFee] = useState("");
  const { data } = useQuery<Controls>({
    queryKey: ["demo", "offer", offerId],
    queryFn: () => api.get<Controls>(`/demo/offers/${offerId}`).then((r) => r.data),
    enabled: canDemo,
    refetchInterval: 10_000,
  });
  const make = useMutation({
    mutationFn: (body: { action: string; fee_amount?: number }) => api.post(`/demo/offers/${offerId}/make`, body),
    onSuccess: () => {
      setFee("");
      queryClient.invalidateQueries();
      addToast(`${data?.house_club ?? "The house club"} has answered.`, "success");
    },
    onError: (err) => addToast(getApiError(err, "Couldn't make that move."), "error"),
  });
  if (!data?.in_demo || !data.house_move || !data.actions?.length) return null;
  const amount = Number(fee) > 0 ? Math.round(Number(fee) * 1_000_000) : undefined;
  return (
    <div role="region" aria-label="Demo controls" className="mb-4 rounded-xl bg-warning-bg px-4 py-3 text-small ring-1 ring-warning-ring">
      <p className="font-semibold text-text">Demo: make {data.house_club} answer now</p>
      <p className="mt-0.5 text-text-secondary">Instead of waiting for its rules. Reset undoes it like everything else.</p>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        {data.actions.map((a) =>
          a === "counter" ? (
            <span key={a} className="flex items-center gap-1">
              <input
                type="number"
                min="0"
                step="0.5"
                value={fee}
                onChange={(e) => setFee(e.target.value)}
                placeholder="£m"
                aria-label="Counter fee in millions of pounds"
                className="w-20 rounded-lg bg-surface px-2 py-1 text-input lg:text-body text-text ring-1 ring-input-border"
              />
              <button
                type="button"
                disabled={make.isPending}
                onClick={() => make.mutate({ action: "counter", fee_amount: amount })}
                className="rounded-lg bg-surface px-3 py-1 font-semibold text-text ring-1 ring-border hover:ring-accent disabled:opacity-60"
              >
                Counter{amount ? "" : " (its price)"}
              </button>
            </span>
          ) : (
            <button
              key={a}
              type="button"
              disabled={make.isPending}
              onClick={() => make.mutate({ action: a })}
              className="rounded-lg bg-surface px-3 py-1 font-semibold text-text ring-1 ring-border hover:ring-accent disabled:opacity-60"
            >
              {LABEL[a]}
            </button>
          ),
        )}
      </div>
    </div>
  );
}
