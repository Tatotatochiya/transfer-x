import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { Sale } from "../../types/api";
import Badge from "../ui/Badge";
import ClubLink from "../ui/ClubLink";
import PlayerLink from "../ui/PlayerLink";
import { availabilityLabel, saleStatusLabel, saleStatusVariant, saleTypeLabel, saleTypeVariant } from "../../lib/badges";
import { formatCompact, formatDeadline } from "../../lib/utils";

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
    deadline?.state === "danger"  ? "text-danger-text" :
    deadline?.state === "warning" ? "text-warning-text" :
    deadline?.state === "expired" ? "text-text-muted" :
    "text-text-secondary";

  return (
    <div
      onMouseEnter={prefetch}
      onClick={() => navigate(`/sales/${sale.id}`)}
      className="cursor-pointer rounded-xl bg-surface ring-1 ring-border hover:ring-accent transition-all duration-200 px-5 py-4"
    >
      {/* Header row */}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          {/* His photo and name link to his profile; the rest of the card opens the listing. */}
          <PlayerLink id={sale.player?.id ?? sale.player_id} name={sale.player?.name} fallback="Unknown Player"
            photoUrl={sale.player?.photo_url ?? null} size="lg" className="max-w-full font-semibold text-text" />
          <p className="mt-0.5 truncate pl-14 text-xs text-text-muted">
            <ClubLink id={sale.seller_club?.id} name={sale.seller_club?.name} />
            {sale.player?.position ? ` · ${sale.player.position}` : ""}
          </p>
        </div>
        <div className="flex flex-col items-end gap-1 shrink-0">
          <Badge variant={sale.status === "OPEN" ? saleTypeVariant(sale.sale_type) : "neutral"}>
            {saleTypeLabel(sale.sale_type)}
          </Badge>
          {availabilityLabel(sale.availability) && (
            <Badge variant="neutral">{availabilityLabel(sale.availability)}</Badge>
          )}
          <Badge variant={saleStatusVariant(sale.status)}>{saleStatusLabel(sale.status)}</Badge>
        </div>
      </div>

      {/* Price + deadline */}
      <div className="mt-3 flex items-center justify-between text-sm">
        <span className="font-semibold text-text">
          {sale.asking_price
            ? formatCompact(sale.asking_price)
            : sale.availability === "LOAN"
            ? "Loan terms open"
            : "Open to offers"}
        </span>
        {deadline && (
          <span className={`text-xs font-medium ${deadlineColour}`}>
            {deadline.state === "expired" ? "Expired" : deadline.label}
          </span>
        )}
      </div>
    </div>
  );
}
