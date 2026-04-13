import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { Sale } from "../../types/api";
import Badge from "../ui/Badge";
import ClubLink from "../ui/ClubLink";
import { saleStatusVariant, saleTypeLabel, saleTypeVariant } from "../../lib/badges";
import { formatCurrency, formatDeadline } from "../../lib/utils";

interface SaleCardProps {
  sale: Sale;
}

export default function SaleCard({ sale }: SaleCardProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const deadline = sale.deadline ? formatDeadline(sale.deadline) : null;

  function prefetch() {
    queryClient.prefetchQuery({
      queryKey: ["sales", sale.id],
      queryFn: () => api.get<Sale>(`/sales/${sale.id}`).then((r) => r.data),
      staleTime: 60_000,
    });
  }

  const deadlineColour =
    deadline?.state === "danger"  ? "text-red-400" :
    deadline?.state === "warning" ? "text-amber-400" :
    deadline?.state === "expired" ? "text-slate-500" :
    "text-slate-400";

  return (
    <div
      onMouseEnter={prefetch}
      onClick={() => navigate(`/sales/${sale.id}`)}
      className="cursor-pointer rounded-xl bg-slate-900 ring-1 ring-white/[0.08] hover:ring-white/[0.18] hover:-translate-y-0.5 transition-all duration-200 px-5 py-4"
    >
      {/* Header row */}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate font-semibold text-white">
            {sale.player?.name ?? "Unknown Player"}
          </p>
          <p className="mt-0.5 text-xs text-slate-400 truncate">
            <ClubLink id={sale.seller_club?.id} name={sale.seller_club?.name} />
            {sale.player?.position ? ` · ${sale.player.position}` : ""}
          </p>
        </div>
        <div className="flex flex-col items-end gap-1 shrink-0">
          <Badge variant={saleTypeVariant(sale.sale_type)}>
            {saleTypeLabel(sale.sale_type)}
          </Badge>
          <Badge variant={saleStatusVariant(sale.status)}>{sale.status}</Badge>
        </div>
      </div>

      {/* Price + deadline */}
      <div className="mt-3 flex items-center justify-between text-sm">
        <span className="font-semibold text-white">
          {sale.sale_type === "AUCTION" && sale.best_bid
            ? formatCurrency(sale.best_bid)
            : sale.asking_price
            ? formatCurrency(sale.asking_price)
            : "Price TBD"}
        </span>
        {deadline && (
          <span className={`text-xs font-medium ${deadlineColour}`}>
            {deadline.state === "expired" ? "Expired" : `⏱ ${deadline.label}`}
          </span>
        )}
      </div>

      {/* Auction stats */}
      {sale.sale_type === "AUCTION" && (
        <div className="mt-2 flex items-center gap-3 text-xs text-slate-500">
          <span>{sale.bid_count} bid{sale.bid_count !== 1 ? "s" : ""}</span>
          {!sale.reserve_met && sale.reserve_price && (
            <span className="text-amber-400/80">Reserve not met</span>
          )}
        </div>
      )}
    </div>
  );
}
