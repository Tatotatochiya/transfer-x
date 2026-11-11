import { useQuery } from "@tanstack/react-query";
import api from "../../lib/api";
import type { OrderBook } from "../../types/api";
import Spinner from "../ui/Spinner";
import { formatCurrency } from "../../lib/utils";
import { offerHeadline } from "../../lib/offerTerms";

interface Props {
  saleId?: string;
  playerId?: string;
}

export default function BuyerOrderBook({ saleId, playerId }: Props) {
  const queryKey = saleId ? ["sales", saleId, "order-book"] : ["offers", "competition", playerId];
  const queryFn = saleId
    ? () => api.get<OrderBook>(`/sales/${saleId}/order-book`).then((r) => r.data)
    : () => api.get<OrderBook>(`/offers/competition/${playerId}`).then((r) => r.data);

  const { data: ob, isLoading } = useQuery<OrderBook>({
    queryKey,
    queryFn,
    refetchInterval: 300_000,  // fallback; WS OFFER_UPDATED events drive real-time updates
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
        <p className="text-caption font-semibold text-text-secondary mb-2">
          Competition
        </p>

        {/* Active count — prominent */}
        <div className="flex items-baseline gap-1.5">
          <span className="text-headline sm:text-title font-bold text-text tabular-nums">{ob.active_count}</span>
          <span className="text-small text-text-muted">
            {ob.active_count === 1 ? "club" : "clubs"} have made offers
          </span>
        </div>

        {/* Rank */}
        {hasParticipated && ob.your_rank != null && (
          <div className="mt-2">
            {ob.is_leading ? (
              <div className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-success animate-pulse" />
                <span className="text-body font-semibold text-success-text">You have the leading offer</span>
              </div>
            ) : (
              <p className="text-body text-text-secondary">
                You are ranked <span className="font-bold text-text">#{ob.your_rank}</span> of {ob.active_count}
              </p>
            )}
          </div>
        )}

        {!hasParticipated && ob.active_count > 0 && (
          <p className="mt-1 text-caption text-text-muted">Submit an offer to see your ranking</p>
        )}
      </div>

      {/* Tier breakdown */}
      {hasParticipated && ob.tiers && ob.tiers.length > 0 && (
        <div className="px-4 py-3 border-b border-border">
          <p className="text-caption font-semibold text-text-secondary mb-3">
            Market depth
          </p>
          <div className="space-y-2">
            {ob.tiers.map((tier) => (
              <div key={tier.label} className={`rounded-lg px-3 py-2 ${tier.includes_yours ? "ring-1 ring-success-ring bg-success-bg" : "bg-surface-inset"}`}>
                <div className="flex items-center justify-between mb-1.5">
                  <span className={`text-caption font-medium tabular-nums ${tier.includes_yours ? "text-success-text" : "text-text-secondary"}`}>
                    {tier.label}
                    {tier.includes_yours && <span className="ml-1.5 text-success-text-alt">← your range</span>}
                  </span>
                  <span className="text-caption text-text-muted tabular-nums">
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
          <p className="text-caption font-semibold text-text-secondary mb-2">
            Your offer
          </p>
          <div className="rounded-lg bg-surface-inset ring-1 ring-success-ring px-3 py-2.5">
            <div className="flex items-center justify-between">
              <span className={`rounded-full px-2 py-0.5 text-caption font-semibold ${
                ob.your_entry.status === "ACTIVE" || ob.your_entry.status === "SENT"
                  ? "bg-success-bg text-success-text"
                  : ob.your_entry.status === "COUNTERED"
                  ? "bg-warning-bg text-warning-text"
                  : "bg-surface-inset text-text-muted"
              }`}>
                {ob.your_entry.status}
              </span>
              <div className="text-right">
                <p className="text-body font-bold text-text tabular-nums">
                  {offerHeadline(ob.your_entry)}
                </p>
                {ob.your_entry.wage_weekly != null && (
                  <p className="text-caption text-text-muted tabular-nums">
                    {formatCurrency(ob.your_entry.wage_weekly)}/wk
                  </p>
                )}
              </div>
            </div>
            {ob.your_entry.is_countered && (
              <p className="mt-1 text-caption text-warning-text-alt">Countered — awaiting response</p>
            )}
          </div>
        </div>
      )}

      {/* No participation yet */}
      {!hasParticipated && (
        <div className="px-4 py-6 text-center text-caption text-text-muted">
          Competition details visible after submitting an offer
        </div>
      )}
    </div>
  );
}
