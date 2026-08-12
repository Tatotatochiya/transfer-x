import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import api from "../../lib/api";
import type { Bid, DealStub, Sale } from "../../types/api";
import Button from "../ui/Button";
import ClubLink from "../ui/ClubLink";
import EmptyState from "../ui/EmptyState";
import Spinner from "../ui/Spinner";
import { formatCurrency, formatDateTime, getApiError } from "../../lib/utils";
import { useToast } from "../../context/ToastContext";

interface BidLadderProps {
  sale: Sale;
  isSeller: boolean;
}

/**
 * The bid ladder — SCREENS.md "Sale detail / bidding". The bar is the point
 * of the screen: every bid painted to a shared scale, with reserve and your
 * valuation marked as reference lines, so a decision reads at a glance
 * instead of requiring a mental comparison across table rows.
 */
export default function BidLadder({ sale, isSeller }: BidLadderProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { addToast } = useToast();

  const { data: bids, isLoading } = useQuery<Bid[]>({
    queryKey: ["sales", sale.id, "bids"],
    queryFn: () => api.get<Bid[]>(`/sales/${sale.id}/bids`).then((r) => r.data),
  });

  const acceptMutation = useMutation({
    mutationFn: (bidId: string) =>
      api.post<DealStub>(`/sales/${sale.id}/bids/${bidId}/accept`).then((r) => r.data),
    onSuccess: (deal) => {
      queryClient.invalidateQueries({ queryKey: ["sales", sale.id] });
      queryClient.invalidateQueries({ queryKey: ["sales", sale.id, "bids"] });
      addToast("Bid accepted — deal created!", "success");
      navigate(`/deals/${deal.id}`);
    },
    onError: (err) => addToast(getApiError(err, "Failed to accept bid."), "error"),
  });

  if (isLoading) {
    return <div className="flex justify-center py-10"><Spinner /></div>;
  }

  if (!bids || bids.length === 0) {
    return (
      <EmptyState
        title="No bids yet"
        body={sale.status === "OPEN" ? `Be the first — minimum bid ${formatCurrency(sale.minimum_next_bid ?? sale.min_increment)}` : undefined}
      />
    );
  }

  const valuation = sale.fair_value_signal?.fair_value ?? null;
  const reserve = isSeller ? sale.reserve_price : null;
  const highestBid = Math.max(...bids.map((b) => b.amount));
  const scaleMax = Math.max(highestBid, valuation ?? 0) * 1.03;
  const reservePct = reserve != null ? (reserve / scaleMax) * 100 : null;
  const valuationPct = valuation != null ? (valuation / scaleMax) * 100 : null;

  const sorted = [...bids].sort((a, b) => b.amount - a.amount);

  return (
    <div>
      {/* Legend */}
      <div className="mb-4 flex flex-wrap items-center gap-[22px] text-xs text-text-muted">
        <span className="flex items-center gap-1.5"><span className="h-[3px] w-[14px] rounded-full bg-ink" /> Bid</span>
        {reserve != null && <span className="flex items-center gap-1.5"><span className="h-[3px] w-[14px] rounded-full bg-danger" /> Reserve</span>}
        {valuation != null && <span className="flex items-center gap-1.5"><span className="h-[3px] w-[14px] rounded-full bg-accent" /> Your valuation</span>}
      </div>

      <div className="space-y-3.5">
        {sorted.map((bid, i) => {
          const isLeading = bid.amount === highestBid && bid.status === "ACTIVE";
          const belowReserve = reserve != null && bid.amount < reserve;
          const barPct = Math.min(100, (bid.amount / scaleMax) * 100);
          const barColour = isLeading ? "bg-ink" : belowReserve ? "bg-border" : "bg-text-muted/40";
          const statusText = bid.status !== "ACTIVE" ? bid.status
            : isLeading ? "Leading"
            : belowReserve ? "Below reserve"
            : "Outbid";
          const statusColour = bid.status !== "ACTIVE" ? "text-text-muted"
            : isLeading ? "text-success-text"
            : "text-danger-text";

          return (
            <div key={bid.id} className="flex flex-wrap items-center gap-3.5">
              <span className="w-[26px] shrink-0 text-[13px] font-bold text-text-muted">#{i + 1}</span>

              <div className="basis-[190px] shrink-0 min-w-0">
                <p className="truncate text-[15px] font-semibold text-text">
                  <ClubLink id={bid.buyer_club?.id} name={bid.buyer_club?.name} />
                </p>
                <p className="truncate text-xs text-text-muted">
                  {formatDateTime(bid.created_at)}
                  {bid.wage_offer_weekly != null && ` · wage offer ${formatCurrency(bid.wage_offer_weekly)}`}
                </p>
              </div>

              {/* The bar */}
              <div className="relative h-[26px] flex-1 basis-[260px] min-w-[120px] overflow-hidden rounded bg-surface-inset">
                <div className={`h-full ${barColour} transition-all`} style={{ width: `${barPct}%` }} />
                {reservePct != null && reservePct <= 100 && (
                  <div className="absolute inset-y-0 w-0.5 bg-danger/55" style={{ left: `${reservePct}%` }} />
                )}
                {valuationPct != null && valuationPct <= 100 && (
                  <div className="absolute inset-y-0 w-0.5 bg-accent/55" style={{ left: `${valuationPct}%` }} />
                )}
              </div>

              <div className="basis-[120px] shrink-0 text-right">
                <p className="text-[17px] font-bold text-text tabular-nums">{formatCurrency(bid.amount)}</p>
                <p className={`text-xs font-semibold ${statusColour}`}>{statusText}</p>
              </div>

              {isSeller && sale.status === "OPEN" && bid.status === "ACTIVE" && (
                <Button
                  variant="primary"
                  size="sm"
                  loading={acceptMutation.isPending && acceptMutation.variables === bid.id}
                  onClick={() => acceptMutation.mutate(bid.id)}
                >
                  Accept
                </Button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
