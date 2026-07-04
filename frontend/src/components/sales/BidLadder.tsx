import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import api from "../../lib/api";
import type { Bid, DealStub, Sale } from "../../types/api";
import { useAuthStore } from "../../store/auth";
import Badge from "../ui/Badge";
import Button from "../ui/Button";
import ClubLink from "../ui/ClubLink";
import EmptyState from "../ui/EmptyState";
import Spinner from "../ui/Spinner";
import { bidStatusVariant } from "../../lib/badges";
import { formatCurrency, formatDateTime, getApiError } from "../../lib/utils";
import { useToast } from "../../context/ToastContext";
import { useDeadlineCountdown } from "../../hooks/useDeadlineCountdown";

interface BidLadderProps {
  sale: Sale;
  isSeller: boolean;
}

export default function BidLadder({ sale, isSeller }: BidLadderProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const { accessToken } = useAuthStore();
  const isAuthenticated = !!accessToken;

  const deadline = useDeadlineCountdown(sale.deadline);

  const deadlineColour =
    deadline.state === "danger"  ? "text-red-400" :
    deadline.state === "warning" ? "text-amber-400" :
    deadline.state === "expired" ? "text-slate-500" :
    "text-slate-300";

  const { data: bids, isLoading } = useQuery<Bid[]>({
    queryKey: ["sales", sale.id, "bids"],
    queryFn: () => api.get<Bid[]>(`/sales/${sale.id}/bids`).then((r) => r.data),
    enabled: isAuthenticated,
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

  // ── Header summary ────────────────────────────────────────────────────────

  return (
    <div>
      {/* Stats row */}
      <div className="mb-4 flex flex-wrap items-center gap-4 text-sm">
        {sale.bid_count != null && (
          <span className="text-slate-400">
            <span className="font-semibold text-white">{sale.bid_count}</span>{" "}
            bid{sale.bid_count !== 1 ? "s" : ""}
          </span>
        )}

        {sale.best_bid != null && (
          <span className="text-slate-400">
            Best: <span className="font-semibold text-white">{formatCurrency(sale.best_bid)}</span>
          </span>
        )}

        {sale.minimum_next_bid != null && sale.status === "OPEN" && (
          <span className="text-slate-400">
            Min next: <span className="font-semibold text-white">{formatCurrency(sale.minimum_next_bid)}</span>
          </span>
        )}

        {!sale.reserve_met && sale.reserve_price != null && (
          <Badge variant="warning">Reserve not met</Badge>
        )}

        {sale.reserve_met && <Badge variant="success">Reserve met</Badge>}

        {sale.deadline && (
          <span className={`font-semibold tabular-nums ${deadlineColour}`}>
            {deadline.state === "expired" ? "Expired" : `⏱ ${deadline.label}`}
          </span>
        )}
      </div>

      {/* Gate: must be logged in to see bids */}
      {!isAuthenticated && (
        <div className="rounded-xl bg-slate-800/50 px-5 py-8 text-center ring-1 ring-white/[0.08]">
          <p className="text-sm text-slate-400">
            <button onClick={() => navigate("/login")} className="text-emerald-400 hover:underline">
              Sign in
            </button>{" "}
            to view the bid ladder.
          </p>
        </div>
      )}

      {isAuthenticated && isLoading && (
        <div className="flex items-center justify-center py-10">
          <Spinner />
        </div>
      )}

      {isAuthenticated && !isLoading && (!bids || bids.length === 0) && (
        <EmptyState
          title="No bids yet"
          body={
            sale.status === "OPEN"
              ? `Be the first — minimum bid ${formatCurrency(sale.minimum_next_bid ?? sale.min_increment)}`
              : undefined
          }
        />
      )}

      {isAuthenticated && bids && bids.length > 0 && (
        <div className="overflow-x-auto rounded-xl ring-1 ring-white/[0.08]">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b border-white/[0.08]">
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-400">#</th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-400">Club</th>
                <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-slate-400">Amount</th>
                {isSeller && (
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-400">Wage offer</th>
                )}
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-400">Status</th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-400">Placed</th>
                {isSeller && sale.status === "OPEN" && (
                  <th className="px-4 py-3" />
                )}
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.04]">
              {bids.map((bid, i) => {
                const isLeading = bid.amount === sale.best_bid || (i === 0 && isSeller);
                return (
                  <tr
                    key={bid.id}
                    className={`${isLeading ? "bg-emerald-500/5" : "bg-slate-900"} transition-colors`}
                  >
                    <td className="px-4 py-3 text-slate-500">{i + 1}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <span className="text-slate-200">
                          <ClubLink id={bid.buyer_club?.id} name={bid.buyer_club?.name} />
                        </span>
                        {isLeading && !isSeller && (
                          <Badge variant="success">Leading</Badge>
                        )}
                        {!isLeading && !isSeller && (
                          <Badge variant="danger">Outbid</Badge>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right font-semibold text-white tabular-nums">
                      {formatCurrency(bid.amount)}
                    </td>
                    {isSeller && (
                      <td className="px-4 py-3 text-slate-400">
                        {bid.wage_offer_weekly != null
                          ? `£${Math.round(bid.wage_offer_weekly).toLocaleString("en-GB")}/wk`
                          : "—"}
                      </td>
                    )}
                    <td className="px-4 py-3">
                      <Badge variant={bidStatusVariant(bid.status)}>{bid.status}</Badge>
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-500">
                      {formatDateTime(bid.created_at)}
                    </td>
                    {isSeller && sale.status === "OPEN" && (
                      <td className="px-4 py-3">
                        <Button
                          variant="primary"
                          size="sm"
                          loading={
                            acceptMutation.isPending &&
                            acceptMutation.variables === bid.id
                          }
                          onClick={() => acceptMutation.mutate(bid.id)}
                        >
                          Accept
                        </Button>
                      </td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Accept error */}
      {acceptMutation.isError && (
        <p className="mt-3 text-sm text-red-400">
          {getApiError(acceptMutation.error, "Failed to accept bid.")}
        </p>
      )}
    </div>
  );
}
