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
      <div className="px-4 py-3 border-b border-border bg-surface-inset">
        <p className="text-xs font-semibold uppercase tracking-wider text-text-muted mb-2">
          Competition
        </p>

        {/* Active count — prominent */}
        <div className="flex items-baseline gap-1.5">
          <span className="text-2xl font-bold text-text tabular-nums">{ob.active_count}</span>
          <span className="text-sm text-text-muted">
            {ob.active_count === 1 ? "club" : "clubs"} {saleType === "AUCTION" ? "bidding" : "have made offers"}
          </span>
        </div>

        {/* Rank */}
        {hasParticipated && ob.your_rank != null && (
          <div className="mt-2">
            {ob.is_leading ? (
              <div className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-success animate-pulse" />
                <span className="text-sm font-semibold text-success-text">You have the leading {saleType === "AUCTION" ? "bid" : "offer"}</span>
              </div>
            ) : (
              <p className="text-sm text-text-secondary">
                You are ranked <span className="font-bold text-text">#{ob.your_rank}</span> of {ob.active_count}
              </p>
            )}
          </div>
        )}

        {!hasParticipated && ob.active_count > 0 && (
          <p className="mt-1 text-xs text-text-muted">Submit an offer to see your ranking</p>
        )}
      </div>

      {/* Tier breakdown */}
      {hasParticipated && ob.tiers && ob.tiers.length > 0 && (
        <div className="px-4 py-3 border-b border-border">
          <p className="text-xs font-semibold uppercase tracking-wider text-text-muted mb-3">
            Market depth
          </p>
          <div className="space-y-2">
            {ob.tiers.map((tier) => (
              <div key={tier.label} className={`rounded-lg px-3 py-2 ${tier.includes_yours ? "ring-1 ring-success/40 bg-success/[0.06]" : "bg-surface-inset"}`}>
                <div className="flex items-center justify-between mb-1.5">
                  <span className={`text-xs font-medium tabular-nums ${tier.includes_yours ? "text-success-text" : "text-text-secondary"}`}>
                    {tier.label}
                    {tier.includes_yours && <span className="ml-1.5 text-success-text-alt">← your range</span>}
                  </span>
                  <span className="text-xs text-text-muted tabular-nums">
                    {tier.count} {tier.count === 1 ? "offer" : "offers"}
                  </span>
                </div>
                {/* Bar */}
                <div className="h-1.5 rounded-full bg-border overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all ${tier.includes_yours ? "bg-success" : "bg-text-muted"}`}
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
          <p className="text-xs font-semibold uppercase tracking-wider text-text-muted mb-2">
            Your {saleType === "AUCTION" ? "bid" : "offer"}
          </p>
          <div className="rounded-lg bg-surface-inset ring-1 ring-success/20 px-3 py-2.5">
            <div className="flex items-center justify-between">
              <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                ob.your_entry.status === "ACTIVE" || ob.your_entry.status === "SENT"
                  ? "bg-success/20 text-success-text"
                  : ob.your_entry.status === "COUNTERED"
                  ? "bg-warning-fill/20 text-warning-text"
                  : "bg-text-muted/15 text-text-muted"
              }`}>
                {ob.your_entry.status}
              </span>
              <div className="text-right">
                <p className="text-sm font-bold text-text tabular-nums">
                  {ob.your_entry.fee_amount != null ? formatCurrency(ob.your_entry.fee_amount) : "TBD"}
                </p>
                {ob.your_entry.wage_weekly != null && (
                  <p className="text-xs text-text-muted tabular-nums">
                    {formatCurrency(ob.your_entry.wage_weekly)}/wk
                  </p>
                )}
              </div>
            </div>
            {ob.your_entry.is_countered && (
              <p className="mt-1 text-xs text-warning-text-alt">Countered — awaiting response</p>
            )}
          </div>
        </div>
      )}

      {/* No participation yet */}
      {!hasParticipated && (
        <div className="px-4 py-6 text-center text-xs text-text-muted">
          Competition details visible after submitting {saleType === "AUCTION" ? "a bid" : "an offer"}
        </div>
      )}
    </div>
  );
}
