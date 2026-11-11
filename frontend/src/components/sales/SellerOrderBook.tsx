import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import api from "../../lib/api";
import type { OrderBook, OrderBookEntry } from "../../types/api";
import Spinner from "../ui/Spinner";
import { formatCurrency } from "../../lib/utils";
import { isLoan, offerHeadline } from "../../lib/offerTerms";
import FallbackImage from "../ui/FallbackImage";

const STATUS_VARIANT: Record<string, string> = {
  ACTIVE:    "bg-success-bg text-success-text",
  SENT:      "bg-success-bg text-success-text",
  COUNTERED: "bg-warning-bg text-warning-text",
  ACCEPTED:  "bg-accent-bg text-accent",
  REJECTED:  "bg-danger-bg text-danger-text",
  WITHDRAWN: "bg-surface-inset text-text-muted",
  EXPIRED:   "bg-surface-inset text-text-muted",
};

interface Props {
  saleId?: string;
  playerId?: string;
  isOpen: boolean;
  selectedId?: string;
}

/** The offers made for a listed player (or, with `playerId`, every offer for
 *  him), best first. A row opens the offer. */
export default function SellerOrderBook({ saleId, playerId, isOpen, selectedId }: Props) {
  const navigate = useNavigate();

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

  const activeEntries = ob.entries.filter((e) => e.is_active);
  const inactiveEntries = ob.entries.filter((e) => !e.is_active);
  // The depth bar compares transfer fees; a loan's fee is a different figure
  // and gets no bar rather than a misleadingly short one.
  const maxFee = Math.max(...ob.entries.filter((e) => !isLoan(e)).map((e) => Number(e.fee_amount ?? 0)), 1);

  function handleRowClick(entry: OrderBookEntry) {
    navigate(`/offers/${entry.id}`);
  }

  return (
    <div className="flex flex-col h-full">
      {/* Summary strip */}
      <div className="px-4 py-3 border-b border-border bg-surface-inset">
        <p className="text-caption font-semibold text-text-secondary mb-1">
          Offer order book
        </p>
        {ob.summary ? (
          <p className="text-body text-text">{ob.summary}</p>
        ) : (
          <p className="text-small text-text-muted">No activity yet</p>
        )}
      </div>

      {/* Active entries */}
      <div className="flex-1 overflow-y-auto">
        {activeEntries.length === 0 && (
          <div className="px-4 py-8 text-center text-small text-text-muted">
            No active offers yet
          </div>
        )}

        {activeEntries.map((entry) => (
          <div
            key={entry.id}
            onClick={() => handleRowClick(entry)}
            className={`relative group px-4 py-3 border-b border-rule-faint cursor-pointer transition-colors overflow-hidden ${
              selectedId === entry.id
                ? "bg-success-bg ring-inset ring-1 ring-success-ring"
                : "hover:bg-surface-inset"
            }`}
          >
            {/* Depth bar */}
            <div
              className="absolute inset-y-0 left-0 bg-success-bg pointer-events-none"
              style={{ width: isLoan(entry) ? 0 : `${(Number(entry.fee_amount ?? 0) / maxFee) * 100}%` }}
            />

            <div className="relative flex items-center gap-3">
              {/* Rank badge */}
              <div className="w-6 shrink-0 text-center">
                {/* A loan is not ranked against transfer bids; its fee line
                    already says "loan fee". */}
                {!isLoan(entry) && (
                  <span className={`text-caption font-bold ${entry.rank === 1 ? "text-success-text" : "text-text-muted"}`}>
                    #{entry.rank}
                  </span>
                )}
              </div>

              {/* Club crest + name */}
              <div className="flex items-center gap-2 flex-1 min-w-0">
                <FallbackImage src={entry.club?.crest_url} name={entry.club?.name ?? "?"} kind="club" sizeClass="h-6 w-6 text-caption" colorClass="bg-surface-inset text-text-muted" />
                <span className="truncate text-body font-medium text-text">
                  {entry.club?.name ?? "Unknown"}
                </span>
                {entry.is_countered && (
                  <span className="ml-1 text-caption text-warning-text-alt shrink-0">↔</span>
                )}
              </div>

              {/* Fee */}
              <div className="shrink-0 text-right">
                <p className={`text-body font-semibold tabular-nums ${entry.rank === 1 && !isLoan(entry) ? "text-success-text" : "text-text"}`}>
                  {offerHeadline(entry)}
                </p>
                {entry.wage_weekly != null && (
                  <p className="text-caption text-text-muted tabular-nums">
                    {formatCurrency(entry.wage_weekly)}/wk
                  </p>
                )}
              </div>
            </div>

            {/* Status + accept button row */}
            <div className="relative mt-1.5 flex items-center justify-between pl-9">
              <span className={`rounded-full px-2 py-0.5 text-caption font-semibold ${STATUS_VARIANT[entry.status] ?? "bg-surface-inset text-text-muted"}`}>
                {entry.status}
              </span>
              {isOpen && (
                <span className="text-small text-text-muted group-hover:text-text-secondary transition-colors">
                  View →
                </span>
              )}
            </div>
          </div>
        ))}

        {/* Inactive entries — collapsed section */}
        {inactiveEntries.length > 0 && (
          <details className="group">
            <summary className="px-4 py-2 text-caption text-text-muted cursor-pointer hover:text-text-secondary list-none flex items-center gap-1">
              <svg className="h-3 w-3 transition-transform group-open:rotate-90" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
              </svg>
              {inactiveEntries.length} inactive
            </summary>
            {inactiveEntries.map((entry) => (
              <div key={entry.id} className="px-4 py-2.5 border-b border-rule-faint opacity-50">
                <div className="flex items-center gap-3">
                  <div className="w-6 shrink-0" />
                  <div className="flex items-center gap-2 flex-1 min-w-0">
                    <div className="h-5 w-5 rounded bg-surface-inset flex items-center justify-center shrink-0 text-caption font-bold text-text-muted">
                      {entry.club?.name?.[0]?.toUpperCase() ?? "?"}
                    </div>
                    <span className="truncate text-small text-text-muted">{entry.club?.name ?? "Unknown"}</span>
                  </div>
                  <div className="shrink-0 text-right">
                    <p className="text-caption text-text-muted tabular-nums">
                      {offerHeadline(entry)}
                    </p>
                  </div>
                  <span className={`rounded-full px-2 py-0.5 text-caption font-semibold ${STATUS_VARIANT[entry.status] ?? "bg-surface-inset text-text-muted"}`}>
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
