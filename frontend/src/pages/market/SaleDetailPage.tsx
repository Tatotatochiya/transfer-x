import type { ReactNode } from "react";
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { Club, Sale } from "../../types/api";
import { useAuthStore } from "../../store/auth";
import FairValueBadge from "../../components/players/FairValueBadge";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Spinner from "../../components/ui/Spinner";
import SellerOrderBook from "../../components/sales/SellerOrderBook";
import BuyerOrderBook from "../../components/sales/BuyerOrderBook";
import {
  dealStageLabel,
  positionVariant,
  saleStatusLabel,
  saleStatusVariant,
  saleTypeLabel,
  availabilityLabel,
  saleTypeVariant,
} from "../../lib/badges";
import { formatCurrency, getApiError } from "../../lib/utils";
import { useConfirm } from "../../context/ConfirmContext";
import { useClubCapabilities } from "../../hooks/useClubCapabilities";
import { useDeadlineCountdown } from "../../hooks/useDeadlineCountdown";
import type { DealStage, PlayerPosition } from "../../types/enums";
import Money from "../../components/ui/Money";
import PlayerLink from "../../components/ui/PlayerLink";
import FallbackImage from "../../components/ui/FallbackImage";

function FigureCard({ label, value, valueColour }: { label: string; value: ReactNode; valueColour?: string }) {
  return (
    <div className="rounded-xl bg-surface ring-1 ring-border px-4 py-3">
      <p className="text-caption font-semibold text-text-secondary">{label}</p>
      <p className={`mt-1 text-headline font-bold ${valueColour ?? "text-text"}`}>{value}</p>
    </div>
  );
}

// A resolved listing reads as stale data unless it says what resolved it: the
// status badge alone can't distinguish "sold" from "withdrawn" or "expired
// unsold", and the order book shows nothing but inactive rows in every case.
function ResolutionNote({ sale, onOpenDeal }: { sale: Sale; onOpenDeal: (dealId: string) => void }) {
  const deal = sale.active_deal ?? null;
  const buyer = deal?.buyer_club?.name ?? "another club";
  const stage = deal?.stage ? dealStageLabel(deal.stage as DealStage) : null;

  let body: string;
  if (deal?.status === "COMPLETED") {
    body = `Sold to ${buyer}. The transfer is complete.`;
  } else if (deal) {
    body = stage
      ? `An offer from ${buyer} was accepted. The transfer is at ${stage}.`
      : `An offer from ${buyer} was accepted and the transfer is in progress.`;
  } else if (sale.status === "WITHDRAWN" && sale.cancelled_by_staff) {
    // The reason comes back for the seller and staff only.
    body = sale.staff_cancel_reason
      ? `TransferX staff cancelled this listing: ${sale.staff_cancel_reason}`
      : "TransferX staff cancelled this listing. No transfer resulted from it.";
  } else if (sale.status === "WITHDRAWN") {
    body = "The seller withdrew this listing. No transfer resulted from it.";
  } else if (sale.status === "EXPIRED") {
    body = "This listing reached its deadline without a sale.";
  } else {
    body = "This listing is closed and is no longer accepting offers.";
  }

  return (
    <div className="rounded-xl bg-surface-quiet px-4 py-3 ring-1 ring-border">
      <p className="text-body text-text-secondary">{body}</p>
      {deal && (
        <button
          onClick={() => onOpenDeal(deal.id)}
          className="mt-1 text-caption font-semibold text-accent hover:underline"
        >
          View the deal →
        </button>
      )}
    </div>
  );
}

export default function SaleDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const confirm = useConfirm();
  const { can } = useClubCapabilities();
  const { accessToken, user } = useAuthStore();
  const isAuthenticated = !!accessToken;
  const isPlayerAccount = user?.user_type === "PLAYER";
  const [mobileSection, setMobileSection] = useState<"detail" | "context">("detail");

  const { data: sale, isLoading, isError } = useQuery<Sale>({
    queryKey: ["sales", id],
    queryFn: () => api.get<Sale>(`/sales/${id}`).then((r) => r.data),
    enabled: !!id,
  });

  const { data: myClub } = useQuery<Club>({
    queryKey: ["clubs", "me"],
    queryFn: () => api.get<Club>("/clubs/me").then((r) => r.data),
    enabled: isAuthenticated,
    staleTime: 60_000,
  });

  const withdrawMutation = useMutation({
    mutationFn: () => api.post<Sale>(`/sales/${id}/withdraw`).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sales", id] });
      queryClient.invalidateQueries({ queryKey: ["sales", "mine"] });
    },
  });

  const deadline = useDeadlineCountdown(sale?.deadline ?? null);

  if (isLoading) {
    return <div className="flex items-center justify-center py-20"><Spinner size="lg" /></div>;
  }

  if (isError || !sale) {
    return (
      <div className="rounded-xl bg-danger-bg px-5 py-4 text-small text-danger-text ring-1 ring-danger-border">
        Listing not found.{" "}
        <button onClick={() => navigate(-1)} className="underline">Go back</button>
      </div>
    );
  }

  const canMarketWrite = can("MARKET_WRITE");
  const isSeller = !!myClub && myClub.id === sale.seller_club_id;
  const isBuyer  = !!myClub && myClub.id !== sale.seller_club_id;
  const isOpen   = sale.status === "OPEN";
  // The order book beside the listing. Auctions are retired (ADR 0011): an
  // old auction listing shows on its own, as history.
  const showRail = sale.sale_type === "OPEN_TO_OFFERS" && (isSeller || isBuyer);

  const detailContent = (
    <div className="space-y-4">
      {/* Player header */}
      <div className="flex items-center gap-3">
        <FallbackImage src={sale.player?.photo_url} name={sale.player?.name ?? "?"} sizeClass="h-11 w-11 text-body" colorClass="bg-surface-inset text-text-muted" />
        <div className="min-w-0">
          <PlayerLink id={sale.player_id} name={sale.player?.name} fallback="Unknown" className="block truncate font-semibold text-text" />
          <div className="flex items-center gap-2 mt-0.5">
            {sale.player?.position && (
              <Badge variant={positionVariant(sale.player.position as PlayerPosition)}>{sale.player.position}</Badge>
            )}
            <Badge variant={saleStatusVariant(sale.status)}>{saleStatusLabel(sale.status)}</Badge>
            {/* The type badge names the listing format, which reads as a live
                invitation ("Open to Offers") once the listing is resolved. Keep
                the information, drop the colour that implies it's still live. */}
            <Badge variant={isOpen ? saleTypeVariant(sale.sale_type) : "neutral"}>
              {saleTypeLabel(sale.sale_type)}
            </Badge>
            {availabilityLabel(sale.availability) && (
              <Badge variant={isOpen ? "info" : "neutral"}>{availabilityLabel(sale.availability)}</Badge>
            )}
          </div>
        </div>
        {sale.seller_club && (
          <button
            onClick={() => navigate(`/clubs/${sale.seller_club_id}`)}
            className="ml-auto shrink-0 text-caption text-text-muted hover:text-text transition-colors"
          >
            {sale.seller_club.name}
          </button>
        )}
      </div>

      {!isOpen && <ResolutionNote sale={sale} onOpenDeal={(id) => navigate(`/deals/${id}`)} />}

      {/* Tier-2 figures */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {sale.deadline && (
          <FigureCard
            label="Offers close in"
            value={deadline.state === "expired" ? "Expired" : deadline.label}
            valueColour={deadline.state === "danger" ? "text-danger-text" : undefined}
          />
        )}
        {isSeller && sale.reserve_price != null && (
          <FigureCard label="Your reserve" value={formatCurrency(sale.reserve_price)} />
        )}
        {sale.asking_price != null && sale.sale_type !== "AUCTION" && (
          <FigureCard label="Asking price" value={<Money value={sale.asking_price} stacked />} />
        )}
      </div>

      {isAuthenticated && !isPlayerAccount && (
        sale.fair_value_signal ? (
          <div className="rounded-lg bg-surface-inset px-3 py-2">
            <FairValueBadge signal={sale.fair_value_signal} />
          </div>
        ) : (
          <p className="text-caption text-text-muted">No model valuation — insufficient recent data.</p>
        )
      )}

      {sale.notes && (
        <p className="text-caption text-text-secondary border-t border-rule pt-3">{sale.notes}</p>
      )}

      {/* Seller actions */}
      {isSeller && isOpen && canMarketWrite && (
        <div className="border-t border-rule pt-3">
          <Button
            variant="danger"
            size="sm"
            loading={withdrawMutation.isPending}
            onClick={async () => {
              if (await confirm({ title: "Withdraw listing", message: "Withdraw this listing? This cannot be undone.", confirmLabel: "Withdraw", variant: "danger" })) {
                withdrawMutation.mutate();
              }
            }}
          >
            Withdraw listing
          </Button>
          {withdrawMutation.isError && (
            <p className="mt-2 text-caption text-danger-text">{getApiError(withdrawMutation.error, "Failed to withdraw.")}</p>
          )}
        </div>
      )}

      {/* OPEN_TO_OFFERS: Make offer (buyer) */}
      {sale.sale_type === "OPEN_TO_OFFERS" && isBuyer && canMarketWrite && (
        <div className="border-t border-rule pt-3">
          <Button variant="primary" onClick={() => navigate(`/offers/new?player_id=${sale.player_id}&sale_id=${sale.id}`)}>
            {sale.availability === "LOAN" ? "Make a loan offer" : "Make Offer"}
          </Button>
        </div>
      )}

      {sale.sale_type === "OPEN_TO_OFFERS" && isSeller && (
        <div className="border-t border-rule pt-3">
          <p className="text-small text-text-muted">Select an offer from the order book to view details.</p>
        </div>
      )}

      {/* FIXED_PRICE */}
      {sale.sale_type === "FIXED_PRICE" && (
        <div className="border-t border-rule pt-3">
          {sale.asking_price != null && (
            <p className="text-headline sm:text-title font-bold text-text mb-3"><Money value={sale.asking_price} stacked /></p>
          )}
          {isAuthenticated && canMarketWrite ? (
            <Button variant="primary" onClick={() => navigate(`/offers/new?player_id=${sale.player_id}&sale_id=${sale.id}`)}>
              Make Offer
            </Button>
          ) : isAuthenticated ? null : (
            <Button variant="secondary" onClick={() => navigate("/login")}>Sign in to make offer</Button>
          )}
        </div>
      )}

      {(sale.sale_type === "OPEN_TO_OFFERS" || sale.sale_type === "FIXED_PRICE") && !isAuthenticated && isOpen && (
        <p className="text-body text-text-secondary">
          <button onClick={() => navigate("/login")} className="text-accent hover:underline">Sign in</button>{" "}to make an offer.
        </p>
      )}
    </div>
  );

  const contextContent = isSeller
    ? <SellerOrderBook saleId={sale.id} isOpen={isOpen} />
    : <BuyerOrderBook saleId={sale.id} />;

  return (
    <div>
      <button
        onClick={() => navigate(-1)}
        className="mb-4 flex items-center gap-1.5 text-body text-text-muted hover:text-text transition-colors"
      >
        ← Back to listings
      </button>

      {showRail ? (
        <div className="rounded-xl ring-1 ring-border overflow-hidden">
          <div className="sm:hidden flex border-b border-rule">
            {(["detail", "context"] as const).map((section) => (
              <button
                key={section}
                onClick={() => setMobileSection(section)}
                className={`flex-1 py-2.5 text-body font-semibold transition-colors ${
                  mobileSection === section
                    ? "text-accent border-b-2 border-accent"
                    : "text-text-muted border-b-2 border-transparent"
                }`}
              >
                {section === "detail" ? "Detail" : "Order book"}
              </button>
            ))}
          </div>

          <div className="flex flex-col lg:flex-row">
            <div className={`flex-1 min-w-0 p-5 bg-page ${mobileSection === "context" ? "hidden sm:block" : ""}`}>
              {detailContent}
            </div>
            <div
              className={`w-full lg:w-80 shrink-0 border-t lg:border-t-0 lg:border-l border-rule bg-surface-quiet lg:sticky lg:top-6 lg:self-start lg:max-h-[calc(100vh-3rem)] overflow-y-auto ${
                mobileSection === "detail" ? "hidden sm:block" : ""
              }`}
            >
              {contextContent}
            </div>
          </div>
        </div>
      ) : (
        <div className="max-w-2xl">{detailContent}</div>
      )}
    </div>
  );
}
