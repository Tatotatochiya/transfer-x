import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { NotificationPreferencesResponse } from "../../types/api";
import PageHeader from "../../components/ui/PageHeader";
import Spinner from "../../components/ui/Spinner";
import { getApiError } from "../../lib/utils";

const TYPE_LABELS: Record<string, string> = {
  OUTBID:               "Outbid on an auction",
  OFFER_RECEIVED:       "Offer received",
  OFFER_ACCEPTED:       "Offer accepted",
  OFFER_REJECTED:       "Offer rejected",
  OFFER_COUNTERED:      "Counter-offer received",
  OFFER_WITHDRAWN:      "Offer withdrawn by other party",
  OFFER_EXPIRING:       "Offer expiring soon",
  OFFER_MESSAGE:        "New message in a negotiation",
  AUCTION_BID_RECEIVED: "Bid received on your auction",
  AUCTION_ENDING:       "Auction ending soon",
  AUCTION_BID_ACCEPTED: "Your auction bid accepted",
  DEAL_COMPLETED:       "Deal completed",
  DEAL_COLLAPSED:       "Deal collapsed",
  PLAYER_AVAILABLE:     "Shortlisted player becomes available",
};

const TYPE_GROUPS: { label: string; types: string[] }[] = [
  {
    label: "Auctions",
    types: ["AUCTION_BID_RECEIVED", "AUCTION_ENDING", "AUCTION_BID_ACCEPTED", "OUTBID"],
  },
  {
    label: "Offers",
    types: ["OFFER_RECEIVED", "OFFER_ACCEPTED", "OFFER_REJECTED", "OFFER_COUNTERED", "OFFER_WITHDRAWN", "OFFER_EXPIRING", "OFFER_MESSAGE"],
  },
  {
    label: "Deals",
    types: ["DEAL_COMPLETED", "DEAL_COLLAPSED"],
  },
  {
    label: "Scouting",
    types: ["PLAYER_AVAILABLE"],
  },
];

export default function NotificationPreferencesPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data, isLoading, isError } = useQuery<NotificationPreferencesResponse>({
    queryKey: ["notifications", "preferences"],
    queryFn: () =>
      api.get<NotificationPreferencesResponse>("/notifications/preferences").then((r) => r.data),
  });

  const mutation = useMutation({
    mutationFn: ({ type, enabled }: { type: string; enabled: boolean }) =>
      api
        .patch<NotificationPreferencesResponse>(`/notifications/preferences/${type}`, { enabled })
        .then((r) => r.data),
    onSuccess: (newData) => {
      queryClient.setQueryData(["notifications", "preferences"], newData);
    },
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner size="lg" />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="rounded-xl bg-red-500/10 px-5 py-4 text-sm text-red-400 ring-1 ring-red-500/30">
        Failed to load preferences.
      </div>
    );
  }

  const prefMap = Object.fromEntries(data.preferences.map((p) => [p.type, p.enabled]));

  return (
    <div>
      <button
        onClick={() => navigate("/notifications")}
        className="mb-6 flex items-center gap-1.5 text-sm text-slate-400 hover:text-white transition-colors"
      >
        ← Back to notifications
      </button>

      <PageHeader
        title="Notification preferences"
        subtitle="Choose which notifications you want to receive"
      />

      <div className="space-y-6 max-w-xl">
        {TYPE_GROUPS.map((group) => (
          <div key={group.label} className="rounded-xl bg-slate-900 ring-1 ring-white/[0.08] overflow-hidden">
            <div className="border-b border-white/[0.06] px-5 py-3">
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                {group.label}
              </p>
            </div>
            <div className="divide-y divide-white/[0.04]">
              {group.types.map((type) => {
                const enabled = prefMap[type] ?? true;
                const isPending = mutation.isPending && (mutation.variables as any)?.type === type;
                return (
                  <div key={type} className="flex items-center justify-between px-5 py-3.5">
                    <span className="text-sm text-slate-200">
                      {TYPE_LABELS[type] ?? type}
                    </span>
                    <button
                      disabled={isPending}
                      onClick={() => mutation.mutate({ type, enabled: !enabled })}
                      className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus:outline-none disabled:opacity-50 ${
                        enabled ? "bg-emerald-500" : "bg-slate-600"
                      }`}
                      aria-label={enabled ? `Disable ${type}` : `Enable ${type}`}
                    >
                      <span
                        className={`pointer-events-none inline-block h-4 w-4 rounded-full bg-white shadow ring-0 transition-transform ${
                          enabled ? "translate-x-4" : "translate-x-0"
                        }`}
                      />
                    </button>
                  </div>
                );
              })}
            </div>
          </div>
        ))}

        {mutation.isError && (
          <p className="text-sm text-red-400">
            {getApiError(mutation.error, "Failed to save preference.")}
          </p>
        )}
      </div>
    </div>
  );
}
