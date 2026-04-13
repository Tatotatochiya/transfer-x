import { useQuery } from "@tanstack/react-query";
import api from "../../lib/api";
import type { OrderBook } from "../../types/api";
import type { SaleType } from "../../types/enums";
import Spinner from "../ui/Spinner";
import { formatCurrency } from "../../lib/utils";

interface Props {
  saleId?: string;
  playerId?: string;
  saleType: SaleType;
}

export default function BuyerOrderBook({ saleId, playerId, saleType }: Props) {
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

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-10">
        <Spinner size="md" />
      </div>
    );
  }

  if (!ob) return null;

  const hasParticipated = ob.your_entry !== null || ob.your_rank !== null;
  const maxTierCount = Math.max(...(ob.tiers?.map((t) => t.count) ?? []), 1);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-4 py-3 border-b border-white/[0.08] bg-slate-800/40">
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
          Competition
        </p>

        {/* Active count — prominent */}
        <div className="flex items-baseline gap-1.5">
          <span className="text-2xl font-bold text-white tabular-nums">{ob.active_count}</span>
          <span className="text-sm text-slate-400">
            {ob.active_count === 1 ? "club" : "clubs"} {saleType === "AUCTION" ? "bidding" : "have made offers"}
          </span>
        </div>

        {/* Rank */}
        {hasParticipated && ob.your_rank != null && (
          <div className="mt-2">
            {ob.is_leading ? (
              <div className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
                <span className="text-sm font-semibold text-emerald-400">You have the leading {saleType === "AUCTION" ? "bid" : "offer"}</span>
              </div>
            ) : (
              <p className="text-sm text-slate-300">
                You are ranked <span className="font-bold text-white">#{ob.your_rank}</span> of {ob.active_count}
              </p>
            )}
          </div>
        )}

        {!hasParticipated && ob.active_count > 0 && (
          <p className="mt-1 text-xs text-slate-500">Submit an offer to see your ranking</p>
        )}
      </div>

      {/* Tier breakdown */}
      {hasParticipated && ob.tiers && ob.tiers.length > 0 && (
        <div className="px-4 py-3 border-b border-white/[0.08]">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-3">
            Market depth
          </p>
          <div className="space-y-2">
            {ob.tiers.map((tier) => (
              <div key={tier.label} className={`rounded-lg px-3 py-2 ${tier.includes_yours ? "ring-1 ring-emerald-500/40 bg-emerald-500/[0.06]" : "bg-slate-800/60"}`}>
                <div className="flex items-center justify-between mb-1.5">
                  <span className={`text-xs font-medium tabular-nums ${tier.includes_yours ? "text-emerald-400" : "text-slate-300"}`}>
                    {tier.label}
                    {tier.includes_yours && <span className="ml-1.5 text-emerald-500/70">← your range</span>}
                  </span>
                  <span className="text-xs text-slate-500 tabular-nums">
                    {tier.count} {tier.count === 1 ? "offer" : "offers"}
                  </span>
                </div>
                {/* Bar */}
                <div className="h-1.5 rounded-full bg-slate-700 overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all ${tier.includes_yours ? "bg-emerald-500" : "bg-slate-500"}`}
                    style={{ width: `${(tier.count / maxTierCount) * 100}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Your own entry */}
      {ob.your_entry && (
        <div className="px-4 py-3">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">
            Your {saleType === "AUCTION" ? "bid" : "offer"}
          </p>
          <div className="rounded-lg bg-slate-800 ring-1 ring-emerald-500/20 px-3 py-2.5">
            <div className="flex items-center justify-between">
              <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                ob.your_entry.status === "ACTIVE" || ob.your_entry.status === "SENT"
                  ? "bg-emerald-500/20 text-emerald-400"
                  : ob.your_entry.status === "COUNTERED"
                  ? "bg-amber-500/20 text-amber-400"
                  : "bg-slate-700 text-slate-400"
              }`}>
                {ob.your_entry.status}
              </span>
              <div className="text-right">
                <p className="text-sm font-bold text-white tabular-nums">
                  {ob.your_entry.fee_amount != null ? formatCurrency(ob.your_entry.fee_amount) : "TBD"}
                </p>
                {ob.your_entry.wage_weekly != null && (
                  <p className="text-xs text-slate-500 tabular-nums">
                    {formatCurrency(ob.your_entry.wage_weekly)}/wk
                  </p>
                )}
              </div>
            </div>
            {ob.your_entry.is_countered && (
              <p className="mt-1 text-xs text-amber-400/70">Countered — awaiting response</p>
            )}
          </div>
        </div>
      )}

      {/* No participation yet */}
      {!hasParticipated && (
        <div className="px-4 py-6 text-center text-xs text-slate-600">
          Competition details visible after submitting {saleType === "AUCTION" ? "a bid" : "an offer"}
        </div>
      )}
    </div>
  );
}
