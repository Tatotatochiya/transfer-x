import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import api from "../../lib/api";
import type { OrderBook, OrderBookEntry } from "../../types/api";
import type { SaleType } from "../../types/enums";
import Spinner from "../ui/Spinner";
import { formatCurrency } from "../../lib/utils";

const STATUS_VARIANT: Record<string, string> = {
  ACTIVE:    "bg-emerald-500/20 text-emerald-400",
  SENT:      "bg-emerald-500/20 text-emerald-400",
  COUNTERED: "bg-amber-500/20 text-amber-400",
  ACCEPTED:  "bg-sky-500/20 text-sky-400",
  REJECTED:  "bg-red-500/20 text-red-400",
  WITHDRAWN: "bg-slate-700 text-slate-500",
  EXPIRED:   "bg-slate-700 text-slate-500",
  OUTBID:    "bg-slate-600/60 text-slate-400",
};

interface Props {
  saleId?: string;
  playerId?: string;
  saleType: SaleType;
  isOpen: boolean;
  selectedId?: string;
  onSelectBid?: (bidId: string) => void; // AUCTION only
}

export default function SellerOrderBook({ saleId, playerId, saleType, isOpen, selectedId, onSelectBid }: Props) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const queryKey = saleId ? ["sales", saleId, "order-book"] : ["offers", "competition", playerId];
  const queryFn = saleId
    ? () => api.get<OrderBook>(`/sales/${saleId}/order-book`).then((r) => r.data)
    : () => api.get<OrderBook>(`/offers/competition/${playerId}`).then((r) => r.data);

  const { data: ob, isLoading } = useQuery<OrderBook>({
    queryKey,
    queryFn,
    refetchInterval: 300_000,  // fallback; WS OFFER_UPDATED / BID_PLACED events drive real-time updates
    enabled: !!(saleId || playerId),
  });

  const acceptBidMutation = useMutation({
    mutationFn: (bidId: string) =>
      api.post(`/sales/${saleId}/bids/${bidId}/accept`).then((r) => r.data),
    onSuccess: (deal: { id: string }) => {
      queryClient.invalidateQueries({ queryKey: ["sales", saleId] });
      queryClient.invalidateQueries({ queryKey });
      navigate(`/deals/${deal.id}`);
    },
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-10">
        <Spinner size="md" />
      </div>
    );
  }

  if (!ob) return null;

  const activeEntries = ob.entries.filter((e) => e.is_active);
  const inactiveEntries = ob.entries.filter((e) => !e.is_active);
  const maxFee = Math.max(...ob.entries.map((e) => e.fee_amount ?? 0), 1);

  function handleRowClick(entry: OrderBookEntry) {
    if (saleType === "AUCTION") {
      onSelectBid?.(entry.id);
    } else {
      navigate(`/offers/${entry.id}`);
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Summary strip */}
      <div className="px-4 py-3 border-b border-white/[0.08] bg-slate-800/40">
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1">
          {saleType === "AUCTION" ? "Bid Order Book" : "Offer Order Book"}
        </p>
        {ob.summary ? (
          <p className="text-sm text-white">{ob.summary}</p>
        ) : (
          <p className="text-sm text-slate-500">No activity yet</p>
        )}
      </div>

      {/* Active entries */}
      <div className="flex-1 overflow-y-auto">
        {activeEntries.length === 0 && (
          <div className="px-4 py-8 text-center text-sm text-slate-500">
            No active {saleType === "AUCTION" ? "bids" : "offers"} yet
          </div>
        )}

        {activeEntries.map((entry) => (
          <div
            key={entry.id}
            onClick={() => handleRowClick(entry)}
            className={`relative group px-4 py-3 border-b border-white/[0.04] cursor-pointer transition-colors overflow-hidden ${
              selectedId === entry.id
                ? "bg-emerald-500/10 ring-inset ring-1 ring-emerald-500/30"
                : "hover:bg-slate-800/60"
            }`}
          >
            {/* Depth bar */}
            <div
              className="absolute inset-y-0 left-0 bg-emerald-500/[0.06] pointer-events-none"
              style={{ width: `${((entry.fee_amount ?? 0) / maxFee) * 100}%` }}
            />

            <div className="relative flex items-center gap-3">
              {/* Rank badge */}
              <div className="w-6 shrink-0 text-center">
                <span className={`text-xs font-bold ${entry.rank === 1 ? "text-emerald-400" : "text-slate-500"}`}>
                  #{entry.rank}
                </span>
              </div>

              {/* Club crest + name */}
              <div className="flex items-center gap-2 flex-1 min-w-0">
                {entry.club?.crest_url ? (
                  <img
                    src={entry.club.crest_url}
                    alt={entry.club.name}
                    className="h-6 w-6 rounded object-contain shrink-0"
                  />
                ) : (
                  <div className="h-6 w-6 rounded bg-slate-700 flex items-center justify-center shrink-0 text-xs font-bold text-slate-400">
                    {entry.club?.name?.[0]?.toUpperCase() ?? "?"}
                  </div>
                )}
                <span className="truncate text-sm font-medium text-white">
                  {entry.club?.name ?? "Unknown"}
                </span>
                {entry.is_countered && (
                  <span className="ml-1 text-xs text-amber-400/70 shrink-0">↔</span>
                )}
              </div>

              {/* Fee */}
              <div className="shrink-0 text-right">
                <p className={`text-sm font-semibold tabular-nums ${entry.rank === 1 ? "text-emerald-400" : "text-white"}`}>
                  {entry.fee_amount != null ? formatCurrency(entry.fee_amount) : "TBD"}
                </p>
                {entry.wage_weekly != null && (
                  <p className="text-xs text-slate-500 tabular-nums">
                    {formatCurrency(entry.wage_weekly)}/wk
                  </p>
                )}
              </div>
            </div>

            {/* Status + accept button row */}
            <div className="relative mt-1.5 flex items-center justify-between pl-9">
              <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${STATUS_VARIANT[entry.status] ?? "bg-slate-700 text-slate-400"}`}>
                {entry.status}
              </span>
              {isOpen && saleType === "AUCTION" && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    acceptBidMutation.mutate(entry.id);
                  }}
                  disabled={acceptBidMutation.isPending}
                  className="text-xs px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-400 ring-1 ring-emerald-500/30 hover:bg-emerald-500/25 transition-colors disabled:opacity-50"
                >
                  Accept
                </button>
              )}
              {isOpen && saleType !== "AUCTION" && (
                <span className="text-xs text-slate-600 group-hover:text-slate-400 transition-colors">
                  View →
                </span>
              )}
            </div>
          </div>
        ))}

        {/* Inactive entries — collapsed section */}
        {inactiveEntries.length > 0 && (
          <details className="group">
            <summary className="px-4 py-2 text-xs text-slate-600 cursor-pointer hover:text-slate-400 list-none flex items-center gap-1">
              <svg className="h-3 w-3 transition-transform group-open:rotate-90" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
              </svg>
              {inactiveEntries.length} inactive
            </summary>
            {inactiveEntries.map((entry) => (
              <div key={entry.id} className="px-4 py-2.5 border-b border-white/[0.04] opacity-50">
                <div className="flex items-center gap-3">
                  <div className="w-6 shrink-0" />
                  <div className="flex items-center gap-2 flex-1 min-w-0">
                    <div className="h-5 w-5 rounded bg-slate-800 flex items-center justify-center shrink-0 text-xs font-bold text-slate-600">
                      {entry.club?.name?.[0]?.toUpperCase() ?? "?"}
                    </div>
                    <span className="truncate text-xs text-slate-500">{entry.club?.name ?? "Unknown"}</span>
                  </div>
                  <div className="shrink-0 text-right">
                    <p className="text-xs text-slate-600 tabular-nums">
                      {entry.fee_amount != null ? formatCurrency(entry.fee_amount) : "TBD"}
                    </p>
                  </div>
                  <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${STATUS_VARIANT[entry.status] ?? "bg-slate-700 text-slate-400"}`}>
                    {entry.status}
                  </span>
                </div>
              </div>
            ))}
          </details>
        )}
      </div>
    </div>
  );
}
