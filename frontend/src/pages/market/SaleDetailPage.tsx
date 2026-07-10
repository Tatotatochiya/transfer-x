import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { Bid, Club, Sale } from "../../types/api";
import { useAuthStore } from "../../store/auth";
import FairValueBadge from "../../components/players/FairValueBadge";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Spinner from "../../components/ui/Spinner";
import BidForm from "../../components/sales/BidForm";
import SellerOrderBook from "../../components/sales/SellerOrderBook";
import BuyerOrderBook from "../../components/sales/BuyerOrderBook";
import {
  positionVariant,
  saleStatusVariant,
  saleTypeLabel,
  saleTypeVariant,
} from "../../lib/badges";
import { formatCurrency, getApiError } from "../../lib/utils";
import { useConfirm } from "../../context/ConfirmContext";
import { useToast } from "../../context/ToastContext";
import { useClubCapabilities } from "../../hooks/useClubCapabilities";

const BID_STATUS_STYLES: Record<string, string> = {
  ACTIVE:    "bg-emerald-500/20 text-emerald-400",
  OUTBID:    "bg-slate-600/60 text-slate-400",
  ACCEPTED:  "bg-sky-500/20 text-sky-400",
  REJECTED:  "bg-red-500/20 text-red-400",
  WITHDRAWN: "bg-slate-700 text-slate-500",
};

export default function SaleDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const confirm = useConfirm();
  const { addToast } = useToast();
  const { can } = useClubCapabilities();
  const { accessToken, user } = useAuthStore();
  const isAuthenticated = !!accessToken;
  const isPlayerAccount = user?.user_type === "PLAYER";

  // For auction seller: which bid is selected in the order book
  const [selectedBidId, setSelectedBidId] = useState<string | undefined>();

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

  // Buyer's bids — used to determine if they have an active bid
  const { data: myBids } = useQuery<Bid[]>({
    queryKey: ["sales", id, "bids"],
    queryFn: () => api.get<Bid[]>(`/sales/${id}/bids`).then((r) => r.data),
    enabled: isAuthenticated && !!id && sale?.sale_type === "AUCTION",
  });

  // Selected bid detail for seller in AUCTION order book
  const { data: selectedBid } = useQuery<Bid>({
    queryKey: ["sales", id, "bids", selectedBidId],
    queryFn: () =>
      api
        .get<Bid[]>(`/sales/${id}/bids`, { params: { include_inactive: true } })
        .then((r) => r.data.find((b) => b.id === selectedBidId) ?? Promise.reject("not found")),
    enabled: !!selectedBidId,
  });

  const withdrawMutation = useMutation({
    mutationFn: () => api.post<Sale>(`/sales/${id}/withdraw`).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sales", id] });
      queryClient.invalidateQueries({ queryKey: ["sales", "mine"] });
    },
  });

  const acceptBidMutation = useMutation({
    mutationFn: (bidId: string) =>
      api.post(`/sales/${id}/bids/${bidId}/accept`).then((r) => r.data),
    onSuccess: (data: { id: string } | { status: string; approval_id: string }) => {
      queryClient.invalidateQueries({ queryKey: ["sales", id] });
      // Phase 5 (D7): 202 means the acceptance was captured for approval.
      if ("approval_id" in data) {
        addToast("Acceptance sent for approval — an approver at your club must sign it off.", "info");
        queryClient.invalidateQueries({ queryKey: ["clubs", "me", "approvals"] });
        return;
      }
      navigate(`/deals/${data.id}`);
    },
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner size="lg" />
      </div>
    );
  }

  if (isError || !sale) {
    return (
      <div className="rounded-xl bg-red-500/10 px-5 py-4 text-sm text-red-400 ring-1 ring-red-500/30">
        Listing not found.{" "}
        <button onClick={() => navigate(-1)} className="underline">Go back</button>
      </div>
    );
  }

  const canMarketWrite = can("MARKET_WRITE");
  const isSeller = !!myClub && myClub.id === sale.seller_club_id;
  const isBuyer  = !!myClub && myClub.id !== sale.seller_club_id;
  const isOpen   = sale.status === "OPEN";
  const myActiveBid = isBuyer ? myBids?.find((b) => b.status === "ACTIVE") : undefined;
  const showOrderBook = sale.sale_type !== "FIXED_PRICE" && (isSeller || isBuyer);

  return (
    <div className="flex flex-col min-h-0">
      <button
        onClick={() => navigate(-1)}
        className="mb-4 flex items-center gap-1.5 text-sm text-slate-400 hover:text-white transition-colors"
      >
        ← Back to listings
      </button>

      <div className={`flex flex-col ${showOrderBook ? "lg:flex-row" : ""} gap-0 min-h-0 rounded-xl overflow-hidden ring-1 ring-white/[0.08] bg-slate-900`}>

        {/* ── Left panel: order book ── */}
        {showOrderBook && (
          <div className="w-full lg:w-80 xl:w-96 shrink-0 border-b lg:border-b-0 lg:border-r border-white/[0.08] lg:max-h-[calc(100vh-10rem)] overflow-y-auto">
            {isSeller ? (
              <SellerOrderBook
                saleId={sale.id}
                saleType={sale.sale_type}
                isOpen={isOpen}
                selectedId={selectedBidId}
                onSelectBid={sale.sale_type === "AUCTION" ? setSelectedBidId : undefined}
              />
            ) : (
              <BuyerOrderBook
                saleId={sale.id}
                saleType={sale.sale_type}
              />
            )}
          </div>
        )}

        {/* ── Right panel: sale detail + action area ── */}
        <div className="flex-1 min-w-0 p-5 space-y-4">

          {/* Player header */}
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-slate-800 text-base font-bold text-slate-500">
              {sale.player?.name?.[0]?.toUpperCase() ?? "?"}
            </div>
            <div className="min-w-0">
              <button
                onClick={() => sale.player_id && navigate(`/players/market/${sale.player_id}`)}
                className="truncate font-semibold text-white hover:text-emerald-400 transition-colors text-left"
              >
                {sale.player?.name ?? "Unknown"}
              </button>
              <div className="flex items-center gap-2 mt-0.5">
                {sale.player?.position && (
                  <Badge variant={positionVariant(sale.player.position as any)}>
                    {sale.player.position}
                  </Badge>
                )}
                <Badge variant={saleStatusVariant(sale.status)}>{sale.status}</Badge>
                <Badge variant={saleTypeVariant(sale.sale_type)}>{saleTypeLabel(sale.sale_type)}</Badge>
              </div>
            </div>
            {sale.seller_club && (
              <button
                onClick={() => navigate(`/clubs/${sale.seller_club_id}`)}
                className="ml-auto shrink-0 text-xs text-slate-400 hover:text-white transition-colors"
              >
                {sale.seller_club.name}
              </button>
            )}
          </div>

          {/* Sale metrics */}
          <div className="grid grid-cols-2 gap-3">
            {sale.asking_price != null && (
              <div className="rounded-lg bg-slate-800 px-3 py-2">
                <p className="text-xs text-slate-500">Asking price</p>
                <p className="text-sm font-semibold text-white tabular-nums">{formatCurrency(sale.asking_price)}</p>
              </div>
            )}
            {sale.reserve_price != null && isSeller && (
              <div className="rounded-lg bg-slate-800 px-3 py-2">
                <p className="text-xs text-slate-500">Reserve</p>
                <p className="text-sm font-semibold text-white tabular-nums">{formatCurrency(sale.reserve_price)}</p>
              </div>
            )}
            {sale.deadline != null && (
              <div className="rounded-lg bg-slate-800 px-3 py-2">
                <p className="text-xs text-slate-500">Deadline</p>
                <p className="text-sm font-semibold text-white">
                  {new Date(sale.deadline).toLocaleDateString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}
                </p>
              </div>
            )}
          </div>

          {/* Fair-value signal (TRA-92) — embedded server-side; divergence only
              on FIXED_PRICE (D7), null for player accounts (D6) */}
          {isAuthenticated && !isPlayerAccount && (
            sale.fair_value_signal ? (
              <div className="rounded-lg bg-slate-800/60 px-3 py-2">
                <FairValueBadge signal={sale.fair_value_signal} />
              </div>
            ) : (
              <p className="text-xs text-slate-600">
                No model valuation — insufficient recent data.
              </p>
            )
          )}

          {sale.notes && (
            <p className="text-xs text-slate-400 border-t border-white/[0.06] pt-3">{sale.notes}</p>
          )}

          {/* ── Seller actions ── */}
          {isSeller && isOpen && canMarketWrite && (
            <div className="border-t border-white/[0.06] pt-3">
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
                <p className="mt-2 text-xs text-red-400">{getApiError(withdrawMutation.error, "Failed to withdraw.")}</p>
              )}
            </div>
          )}

          {/* ── AUCTION: selected bid detail (seller) ── */}
          {sale.sale_type === "AUCTION" && isSeller && selectedBidId && selectedBid && (
            <div className="border-t border-white/[0.06] pt-3">
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3">Selected Bid</p>
              <div className="rounded-lg bg-slate-800 ring-1 ring-emerald-500/20 p-4 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-white">{selectedBid.buyer_club?.name ?? "Unknown"}</span>
                  <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${BID_STATUS_STYLES[selectedBid.status] ?? "bg-slate-700 text-slate-400"}`}>
                    {selectedBid.status}
                  </span>
                </div>
                <p className="text-xl font-bold text-white tabular-nums">{formatCurrency(selectedBid.amount)}</p>
                {selectedBid.wage_offer_weekly != null && (
                  <p className="text-xs text-slate-400">{formatCurrency(selectedBid.wage_offer_weekly)}/wk wage offer</p>
                )}
                {selectedBid.notes && (
                  <p className="text-xs text-slate-400 border-t border-white/[0.06] pt-2">{selectedBid.notes}</p>
                )}
                {isOpen && selectedBid.status === "ACTIVE" && canMarketWrite && (
                  <Button
                    variant="primary"
                    size="sm"
                    className="w-full mt-2"
                    loading={acceptBidMutation.isPending}
                    onClick={async () => {
                      if (await confirm({ title: "Accept bid", message: `Accept bid of ${formatCurrency(selectedBid.amount)} from ${selectedBid.buyer_club?.name}?`, confirmLabel: "Accept" })) {
                        acceptBidMutation.mutate(selectedBid.id);
                      }
                    }}
                  >
                    Accept bid
                  </Button>
                )}
              </div>
            </div>
          )}

          {/* ── AUCTION: bid form (buyer) ── */}
          {sale.sale_type === "AUCTION" && isBuyer && isOpen && canMarketWrite && (
            <div className="border-t border-white/[0.06] pt-3">
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3">
                {myActiveBid ? "Your Bid" : "Place a Bid"}
              </p>
              <BidForm sale={sale} existingBid={myActiveBid} />
            </div>
          )}

          {/* ── AUCTION: not logged in ── */}
          {sale.sale_type === "AUCTION" && !isAuthenticated && isOpen && (
            <p className="text-sm text-slate-400">
              <button onClick={() => navigate("/login")} className="text-emerald-400 hover:underline">Sign in</button>{" "}to place a bid.
            </p>
          )}

          {/* ── OPEN_TO_OFFERS: Make offer (buyer) ── */}
          {sale.sale_type === "OPEN_TO_OFFERS" && isBuyer && canMarketWrite && (
            <div className="border-t border-white/[0.06] pt-3">
              <Button
                variant="primary"
                onClick={() => navigate(`/offers/new?player_id=${sale.player_id}&sale_id=${sale.id}`)}
              >
                Make Offer
              </Button>
            </div>
          )}

          {/* ── OPEN_TO_OFFERS: seller placeholder ── */}
          {sale.sale_type === "OPEN_TO_OFFERS" && isSeller && (
            <div className="border-t border-white/[0.06] pt-3">
              <p className="text-sm text-slate-500">
                Select an offer from the order book to view details.
              </p>
            </div>
          )}

          {/* ── FIXED_PRICE ── */}
          {sale.sale_type === "FIXED_PRICE" && (
            <div className="border-t border-white/[0.06] pt-3">
              {sale.asking_price != null && (
                <p className="text-2xl font-bold text-white mb-3 tabular-nums">{formatCurrency(sale.asking_price)}</p>
              )}
              {isAuthenticated && canMarketWrite ? (
                <Button
                  variant="primary"
                  onClick={() => navigate(`/offers/new?player_id=${sale.player_id}&sale_id=${sale.id}`)}
                >
                  Make Offer
                </Button>
              ) : isAuthenticated ? null : (
                <Button variant="secondary" onClick={() => navigate("/login")}>
                  Sign in to make offer
                </Button>
              )}
            </div>
          )}

          {/* ── OPEN_TO_OFFERS / FIXED_PRICE: not logged in ── */}
          {(sale.sale_type === "OPEN_TO_OFFERS" || sale.sale_type === "FIXED_PRICE") && !isAuthenticated && isOpen && (
            <p className="text-sm text-slate-400">
              <button onClick={() => navigate("/login")} className="text-emerald-400 hover:underline">Sign in</button>{" "}to make an offer.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
