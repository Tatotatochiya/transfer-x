import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import api from "../../lib/api";
import type { Bid, Club, DealStub, PlayerDetail, Sale } from "../../types/api";
import Button from "../ui/Button";
import { formatCurrency, formatWage } from "../../lib/utils";
import { useConfirm } from "../../context/ConfirmContext";
import { useToast } from "../../context/ToastContext";

export default function SellerConsequenceCard({ sale, bid, myClub }: { sale: Sale; bid: Bid; myClub: Club }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const confirm = useConfirm();
  const { addToast } = useToast();

  const { data: player } = useQuery<PlayerDetail>({
    queryKey: ["players", "market", sale.player_id],
    queryFn: () => api.get<PlayerDetail>(`/players/market/${sale.player_id}`).then((r) => r.data),
    enabled: !!sale.player_id,
    staleTime: 60_000,
  });

  const acceptMutation = useMutation({
    mutationFn: () => api.post<DealStub>(`/sales/${sale.id}/bids/${bid.id}/accept`).then((r) => r.data),
    onSuccess: (deal) => {
      queryClient.invalidateQueries({ queryKey: ["sales", sale.id] });
      addToast("Bid accepted — deal created!", "success");
      navigate(`/deals/${deal.id}`);
    },
  });

  const valuation = sale.fair_value_signal?.fair_value ?? null;
  const budgetAfter = myClub.finance ? Number(myClub.finance.transfer_remaining) + bid.amount : null;
  const wageFreed = player?.active_contract?.wage_weekly ?? null;
  const otherBidders = (sale.bid_count ?? 1) - 1;

  const daysEarly = sale.deadline
    ? Math.max(0, Math.ceil((new Date(sale.deadline).getTime() - Date.now()) / 86_400_000))
    : null;

  return (
    <div className="rounded-xl bg-surface ring-1 ring-border px-5 py-4">
      <div className="flex items-center justify-between">
        <p className="text-sm font-bold text-text">
          If you accept {bid.buyer_club?.name ?? "this club"}'s {formatCurrency(bid.amount)} now
        </p>
        {daysEarly != null && (
          <span className="shrink-0 text-xs text-text-muted">Reserve met · {daysEarly}d early</span>
        )}
      </div>

      <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div>
          <p className="text-[11px] text-text-muted">Fee received</p>
          <p className="text-base font-bold text-text">{formatCurrency(bid.amount)}</p>
          {valuation != null && <p className="text-[11px] text-text-muted">vs {formatCurrency(valuation)} valuation</p>}
        </div>
        {budgetAfter != null && (
          <div>
            <p className="text-[11px] text-text-muted">Budget after</p>
            <p className="text-base font-bold text-success-text">{formatCurrency(budgetAfter)}</p>
          </div>
        )}
        {wageFreed != null && (
          <div>
            <p className="text-[11px] text-text-muted">Wage freed</p>
            <p className="text-base font-bold text-text">{formatWage(wageFreed)}</p>
          </div>
        )}
        {sale.player?.position && (
          <div>
            <p className="text-[11px] text-text-muted">Squad effect</p>
            <p className="text-base font-bold text-text">−1 {sale.player.position}</p>
          </div>
        )}
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <Button
          variant="primary-success"
          size="sm"
          loading={acceptMutation.isPending}
          onClick={async () => {
            if (await confirm({
              title: "Accept bid",
              message: `Accept ${bid.buyer_club?.name ?? "this"}'s bid of ${formatCurrency(bid.amount)}?`,
              confirmLabel: "Accept",
            })) {
              acceptMutation.mutate();
            }
          }}
        >
          Accept {formatCurrency(bid.amount)} and open deal
        </Button>
        <Button variant="secondary" size="sm">Hold until deadline</Button>
      </div>
      {otherBidders > 0 && (
        <p className="mt-2 text-xs text-text-muted">
          Accepting closes the auction to the other {otherBidders} bidder{otherBidders === 1 ? "" : "s"} and creates a deal at the Agreement stage.
        </p>
      )}
    </div>
  );
}
