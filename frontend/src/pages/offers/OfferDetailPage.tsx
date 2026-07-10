import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { Club, Offer } from "../../types/api";
import type { DealStub } from "../../types/api";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import CurrencyInput from "../../components/ui/CurrencyInput";
import Card from "../../components/ui/Card";
import ClubLink from "../../components/ui/ClubLink";
import Metric from "../../components/ui/Metric";
import Spinner from "../../components/ui/Spinner";
import OfferThread from "../../components/offers/OfferThread";
import SellerOrderBook from "../../components/sales/SellerOrderBook";
import BuyerOrderBook from "../../components/sales/BuyerOrderBook";
import { offerStatusVariant } from "../../lib/badges";
import { formatCurrency, formatDate, formatWage, getApiError } from "../../lib/utils";
import { useConfirm } from "../../context/ConfirmContext";
import { useClubCapabilities } from "../../hooks/useClubCapabilities";
import { useToast } from "../../context/ToastContext";

// ── Counter form ─────────────────────────────────────────────────────────────

function CounterForm({
  offer,
  onSuccess,
}: {
  offer: Offer;
  onSuccess: () => void;
}) {
  const queryClient = useQueryClient();
  const [fee, setFee] = useState(String(offer.fee_amount ?? ""));
  const [wage, setWage] = useState(String(offer.wage_weekly ?? ""));
  const [years, setYears] = useState(String(offer.contract_years ?? ""));
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: (body: object) =>
      api.post<Offer>(`/offers/${offer.id}/counter`, body).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["offers", offer.id] });
      queryClient.invalidateQueries({ queryKey: ["offers", "received"] });
      queryClient.invalidateQueries({ queryKey: ["offers", "sent"] });
      queryClient.invalidateQueries({ queryKey: ["offers", "competition", offer.player_id] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      if (offer.sale_id) {
        queryClient.invalidateQueries({ queryKey: ["sales", offer.sale_id, "order-book"] });
      }
      onSuccess();
    },
    onError: (err: unknown) => {
      setError(getApiError(err, "Failed to submit counter."));
    },
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const body: Record<string, unknown> = {};
    const parsedFee = parseFloat(fee);
    if (fee && !isNaN(parsedFee)) body.fee_amount = parsedFee;
    const parsedWage = parseFloat(wage);
    if (wage && !isNaN(parsedWage)) body.wage_weekly = parsedWage;
    const parsedYears = parseInt(years);
    if (years && !isNaN(parsedYears)) body.contract_years = parsedYears;
    mutation.mutate(body);
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3 pt-3 border-t border-white/[0.06]">
      <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Counter Offer</p>
      <div className="grid grid-cols-3 gap-3">
        <div>
          <label className="mb-1 block text-xs text-slate-400">Fee (£)</label>
          <CurrencyInput value={fee} onChange={setFee} placeholder="Transfer fee"
            className="w-full rounded-lg bg-slate-800 px-3 py-2 text-sm text-white placeholder-slate-500 ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500 transition-colors" />
        </div>
        <div>
          <label className="mb-1 block text-xs text-slate-400">Wage/wk (£)</label>
          <CurrencyInput value={wage} onChange={setWage} placeholder="Weekly wage"
            className="w-full rounded-lg bg-slate-800 px-3 py-2 text-sm text-white placeholder-slate-500 ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500 transition-colors" />
        </div>
        <div>
          <label className="mb-1 block text-xs text-slate-400">Contract yrs</label>
          <input type="number" min="1" max="10" step="1" value={years} onChange={(e) => setYears(e.target.value)} placeholder="Years"
            className="w-full rounded-lg bg-slate-800 px-3 py-2 text-sm text-white placeholder-slate-500 ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500 transition-colors" />
        </div>
      </div>
      {error && <p className="text-xs text-red-400">{error}</p>}
      <div className="flex gap-2">
        <Button type="submit" variant="primary" size="sm" loading={mutation.isPending}>Submit counter</Button>
        <Button type="button" variant="ghost" size="sm" onClick={onSuccess}>Cancel</Button>
      </div>
    </form>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function OfferDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const confirm = useConfirm();
  const { addToast } = useToast();
  const { can } = useClubCapabilities();
  const [showCounter, setShowCounter] = useState(false);

  const { data: offer, isLoading, isError } = useQuery<Offer>({
    queryKey: ["offers", id],
    queryFn: () => api.get<Offer>(`/offers/${id}`).then((r) => r.data),
    enabled: !!id,
  });

  const { data: myClub } = useQuery<Club>({
    queryKey: ["clubs", "me"],
    queryFn: () => api.get<Club>("/clubs/me").then((r) => r.data),
    staleTime: 60_000,
  });

  const acceptMutation = useMutation({
    mutationFn: () => api.post<DealStub>(`/offers/${id}/accept`).then((r) => r.data),
    onSuccess: (deal) => {
      queryClient.invalidateQueries({ queryKey: ["offers"] });
      queryClient.invalidateQueries({ queryKey: ["deals"] });
      queryClient.invalidateQueries({ queryKey: ["offers", "competition", offer?.player_id] });
      if (offer?.sale_id) queryClient.invalidateQueries({ queryKey: ["sales", offer.sale_id, "order-book"] });
      // Phase 5 (D7): 202 means the acceptance was captured for approval.
      if ("approval_id" in (deal as object)) {
        addToast("Acceptance sent for approval — an approver at your club must sign it off.", "info");
        queryClient.invalidateQueries({ queryKey: ["clubs", "me", "approvals"] });
        return;
      }
      addToast("Offer accepted — deal created!", "success");
      navigate(`/deals/${deal.id}`);
    },
    onError: (err) => addToast(getApiError(err, "Failed to accept offer."), "error"),
  });

  const rejectMutation = useMutation({
    mutationFn: () => api.post<Offer>(`/offers/${id}/reject`).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["offers", id] });
      queryClient.invalidateQueries({ queryKey: ["offers", "received"] });
      queryClient.invalidateQueries({ queryKey: ["offers", "competition", offer?.player_id] });
      if (offer?.sale_id) queryClient.invalidateQueries({ queryKey: ["sales", offer.sale_id, "order-book"] });
      addToast("Offer rejected.", "info");
    },
    onError: (err) => addToast(getApiError(err, "Failed to reject offer."), "error"),
  });

  const withdrawMutation = useMutation({
    mutationFn: () => api.post<Offer>(`/offers/${id}/withdraw`).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["offers", id] });
      queryClient.invalidateQueries({ queryKey: ["offers", "sent"] });
      queryClient.invalidateQueries({ queryKey: ["offers", "competition", offer?.player_id] });
      if (offer?.sale_id) queryClient.invalidateQueries({ queryKey: ["sales", offer.sale_id, "order-book"] });
      addToast("Offer withdrawn.", "info");
    },
    onError: (err) => addToast(getApiError(err, "Failed to withdraw offer."), "error"),
  });

  if (isLoading) {
    return <div className="flex items-center justify-center py-20"><Spinner size="lg" /></div>;
  }

  if (isError || !offer) {
    return (
      <div className="rounded-xl bg-red-500/10 px-5 py-4 text-sm text-red-400 ring-1 ring-red-500/30">
        Offer not found.{" "}
        <button onClick={() => navigate(-1)} className="underline">Go back</button>
      </div>
    );
  }

  const myClubId = myClub?.id;
  const isBuyer  = myClubId === offer.from_club_id;
  const isSeller = myClubId === offer.to_club_id;
  const isParty  = isBuyer || isSeller;
  const isActive = offer.status === "SENT" || offer.status === "COUNTERED";

  // Whose turn: the party who did NOT last act can respond.
  // last_actor_club_id is null only for legacy offers — fall back to seller's turn for SENT.
  const isMyTurn: boolean = offer.last_actor_club_id != null
    ? offer.last_actor_club_id !== myClubId
    : offer.status === "SENT" ? isSeller : false;

  const canMarketWrite = can("MARKET_WRITE");
  const canAct      = isParty && isActive && isMyTurn && canMarketWrite;
  const canWithdraw = isBuyer && isActive && canMarketWrite;  // buyer can always pull out regardless of turn
  const canMessage  = isParty && isActive && canMarketWrite;

  const waitingFor = !isMyTurn && isActive && isParty
    ? (isBuyer ? offer.to_club?.name : offer.from_club?.name) ?? "other party"
    : null;

  const mutError =
    acceptMutation.isError ? getApiError(acceptMutation.error, "Failed.")
    : rejectMutation.isError ? getApiError(rejectMutation.error, "Failed.")
    : withdrawMutation.isError ? getApiError(withdrawMutation.error, "Failed.")
    : null;

  // ── Offer detail panel (shared between layouts) ─────────────────────────────
  const offerDetailPanel = (
    <div className="space-y-4">
      {/* Player + status */}
      <Card>
        <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">Offer</p>
        <p className="text-lg font-semibold text-white">{offer.player?.name ?? "Unknown player"}</p>
        {offer.player?.position && <p className="text-xs text-slate-500 mt-0.5">{offer.player.position}</p>}
        <div className="mt-3 flex items-center gap-2">
          <Badge variant={offerStatusVariant(offer.status)}>{offer.status}</Badge>
          {offer.sale_id && (
            <button
              onClick={() => navigate(`/sales/${offer.sale_id}`)}
              className="text-xs text-slate-500 hover:text-emerald-400 transition-colors"
            >
              View listing →
            </button>
          )}
        </div>
      </Card>

      {/* Parties */}
      <Card>
        <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">Parties</p>
        <div className="space-y-2">
          <Metric label="Buying club"  valueNode={<ClubLink id={offer.from_club?.id} name={offer.from_club?.name} />} />
          <Metric label="Selling club" valueNode={<ClubLink id={offer.to_club?.id}   name={offer.to_club?.name} />} />
          <Metric label="Date"         value={formatDate(offer.created_at)} />
        </div>
      </Card>

      {/* Terms */}
      <Card>
        <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">Terms</p>
        <div className="space-y-2">
          {offer.fee_amount != null && <Metric label="Transfer fee" value={formatCurrency(offer.fee_amount)} />}
          {offer.wage_weekly != null && <Metric label="Wage"         value={formatWage(offer.wage_weekly)} />}
          {offer.contract_years != null && <Metric label="Contract"  value={`${offer.contract_years} years`} />}
          {offer.contract_end_date != null && <Metric label="Ends"   value={formatDate(offer.contract_end_date)} />}
          {offer.fee_amount == null && offer.wage_weekly == null && (
            <p className="text-sm text-slate-500">No terms specified yet.</p>
          )}
        </div>
      </Card>

      {/* Actions */}
      {(canAct || canWithdraw || waitingFor) && (
        <Card>
          <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">Actions</p>
          <div className="space-y-2">
            {/* Waiting indicator — shown to whichever party just acted */}
            {waitingFor && (
              <div className="flex items-center gap-2 rounded-lg bg-slate-800/60 px-3 py-2.5">
                <svg className="h-3.5 w-3.5 shrink-0 animate-spin text-slate-500" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                </svg>
                <p className="text-xs text-slate-400">
                  Waiting for <span className="font-medium text-white">{waitingFor}</span> to respond…
                </p>
              </div>
            )}

            {/* Respond buttons — only shown on your turn */}
            {canAct && (
              <>
                <Button variant="primary" size="sm" className="w-full" loading={acceptMutation.isPending}
                  onClick={async () => {
                    if (await confirm({ title: "Accept offer", message: "Accept this offer and create a deal?", confirmLabel: "Accept" })) {
                      acceptMutation.mutate();
                    }
                  }}>
                  Accept offer
                </Button>
                <Button variant="secondary" size="sm" className="w-full" onClick={() => setShowCounter((v) => !v)}>
                  {showCounter ? "Cancel counter" : "Counter offer"}
                </Button>
                <Button variant="danger" size="sm" className="w-full" loading={rejectMutation.isPending}
                  onClick={async () => {
                    if (await confirm({ message: "Reject this offer?", confirmLabel: "Reject", variant: "danger" })) {
                      rejectMutation.mutate();
                    }
                  }}>
                  Reject
                </Button>
              </>
            )}

            {/* Withdraw — buyer only, always available while active */}
            {canWithdraw && (
              <Button variant="danger" size="sm" className="w-full" loading={withdrawMutation.isPending}
                onClick={async () => {
                  if (await confirm({ message: "Withdraw this offer?", confirmLabel: "Withdraw", variant: "danger" })) {
                    withdrawMutation.mutate();
                  }
                }}>
                Withdraw offer
              </Button>
            )}
            {mutError && <p className="text-xs text-red-400">{mutError}</p>}
          </div>
        </Card>
      )}

      {/* Negotiation thread */}
      <div className="rounded-xl bg-slate-900 ring-1 ring-white/[0.08] p-4">
        <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">Negotiations</p>
        <OfferThread offer={offer} myClubId={myClubId} canMessage={canMessage} />
        {showCounter && canAct && <CounterForm offer={offer} onSuccess={() => setShowCounter(false)} />}
      </div>
    </div>
  );

  return (
    <div>
      <button onClick={() => navigate(-1)} className="mb-6 flex items-center gap-1.5 text-sm text-slate-400 hover:text-white transition-colors">
        ← Back
      </button>

      {isParty ? (
        /* ── Two-panel layout for parties to the offer ── */
        <div className="flex flex-col lg:flex-row gap-0 rounded-xl overflow-hidden ring-1 ring-white/[0.08] bg-slate-900">
          {/* Left: order book */}
          <div className="w-full lg:w-80 xl:w-96 shrink-0 border-b lg:border-b-0 lg:border-r border-white/[0.08] lg:max-h-[calc(100vh-10rem)] overflow-y-auto">
            {isSeller ? (
              <SellerOrderBook
                saleId={offer.sale_id ?? undefined}
                playerId={offer.sale_id ? undefined : offer.player_id}
                saleType="OPEN_TO_OFFERS"
                isOpen={isActive}
                selectedId={offer.id}
                onSelectBid={undefined}
              />
            ) : (
              <BuyerOrderBook
                saleId={offer.sale_id ?? undefined}
                playerId={offer.sale_id ? undefined : offer.player_id}
                saleType="OPEN_TO_OFFERS"
              />
            )}
          </div>
          {/* Right: offer detail */}
          <div className="flex-1 min-w-0 p-5">
            {offerDetailPanel}
          </div>
        </div>
      ) : (
        /* ── Read-only view for non-parties ── */
        <div className="max-w-lg">
          {offerDetailPanel}
        </div>
      )}
    </div>
  );
}
