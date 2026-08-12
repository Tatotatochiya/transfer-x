import { useState } from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import api from "../../lib/api";
import type { Offer, PlayerDetail } from "../../types/api";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import CurrencyInput from "../../components/ui/CurrencyInput";
import PageHeader from "../../components/ui/PageHeader";
import Spinner from "../../components/ui/Spinner";
import { getApiError } from "../../lib/utils";
import { useAuthStore } from "../../store/auth";
import TransferWindowBanner from "../../components/transfers/TransferWindowBanner";

export default function CreateOfferPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { accessToken } = useAuthStore();

  const playerId = searchParams.get("player_id") ?? "";
  const saleId   = searchParams.get("sale_id")   ?? "";

  const [fee, setFee]         = useState("");
  const [wage, setWage]       = useState("");
  const [years, setYears]     = useState("");
  const [endDate, setEndDate] = useState("");
  const [error, setError]     = useState<string | null>(null);

  // Load player info for display
  const { data: player, isLoading: playerLoading } = useQuery<PlayerDetail>({
    queryKey: ["players", playerId],
    queryFn: () =>
      api.get<PlayerDetail>(`/players/market/${playerId}`).then((r) => r.data),
    enabled: !!playerId,
  });

  // Check whether the club already has an active offer for this player
  const { data: activeOffer, isLoading: checkLoading } = useQuery<Offer | null>({
    queryKey: ["offers", "active-for-player", playerId],
    queryFn: () =>
      api.get<Offer | null>(`/offers/active-for-player/${playerId}`).then((r) => r.data),
    enabled: !!playerId && !!accessToken,
    staleTime: 0,         // always fresh — we don't want a cached "no offer" to let a duplicate through
    retry: false,
  });

  const mutation = useMutation({
    mutationFn: (body: object) =>
      api.post<Offer>("/offers", body).then((r) => r.data),
    onSuccess: (offer) => {
      // Phase 5 (D7): 202 means the offer was captured for approval, not sent.
      if ("approval_id" in (offer as object)) {
        navigate("/club/approvals");
        return;
      }
      navigate(`/offers/${offer.id}`);
    },
    onError: (err: unknown) => {
      // Backend 409: already has an active offer — redirect to it
      const detail = (err as any)?.response?.data?.detail;
      if ((err as any)?.response?.status === 409 && detail?.offer_id) {
        navigate(`/offers/${detail.offer_id}`, { replace: true });
        return;
      }
      setError(getApiError(err, "Failed to create offer."));
    },
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (!playerId) {
      setError("No player specified.");
      return;
    }

    const body: Record<string, unknown> = { player_id: playerId };

    if (saleId) body.sale_id = saleId;

    // Automatically address the offer to the player's current club
    if (player?.current_club?.id) body.to_club_id = player.current_club.id;

    const parsedFee = parseFloat(fee);
    if (fee && !isNaN(parsedFee)) body.fee_amount = parsedFee;

    const parsedWage = parseFloat(wage);
    if (wage && !isNaN(parsedWage)) body.wage_weekly = parsedWage;

    const parsedYears = parseInt(years);
    if (years && !isNaN(parsedYears)) body.contract_years = parsedYears;

    if (endDate) body.contract_end_date = endDate;

    mutation.mutate(body);
  }

  const isLoading = playerLoading || checkLoading;

  // ── Active offer redirect ─────────────────────────────────────────────────

  if (!isLoading && activeOffer) {
    return (
      <div className="max-w-2xl">
        <PageHeader
          title="Make an Offer"
          subtitle="Submit a formal offer to begin negotiations"
        />
        <div className="rounded-xl bg-warning-bg ring-1 ring-warning-fill/25 px-6 py-5 space-y-3">
          <div className="flex items-start gap-3">
            <div className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-warning-fill/20 text-warning-text font-bold text-xs">!</div>
            <div>
              <p className="text-sm font-semibold text-warning-text">
                You already have an active offer for {player?.name ?? "this player"}
              </p>
              <p className="mt-1 text-sm text-text-secondary">
                You can only have one active offer per player at a time. To change your terms,
                use the <span className="text-text font-medium">Counter offer</span> action on your existing offer.
                To start fresh, withdraw the current offer first.
              </p>
            </div>
          </div>
          <div className="flex gap-3 pt-1">
            <Link
              to={`/offers/${activeOffer.id}`}
              className="inline-flex items-center rounded-lg bg-warning-fill/15 px-4 py-2 text-sm font-medium text-warning-text ring-1 ring-warning-fill/30 hover:bg-warning-fill/25 transition-colors"
            >
              View existing offer →
            </Link>
            <button
              onClick={() => navigate(-1)}
              className="text-sm text-text-muted hover:text-text transition-colors"
            >
              Go back
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ── Loading state ─────────────────────────────────────────────────────────

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner size="lg" />
      </div>
    );
  }

  // ── Offer form ────────────────────────────────────────────────────────────

  return (
    <div className="max-w-2xl">
      <PageHeader
        title="Make an Offer"
        subtitle="Submit a formal offer to begin negotiations"
      />

      <TransferWindowBanner />

      {/* Player info */}
      {player && (
        <div className="mb-6 rounded-xl bg-surface px-4 py-3 ring-1 ring-border">
          <p className="text-sm font-semibold text-text">{player.name}</p>
          <p className="text-xs text-text-muted mt-0.5">
            {player.position ?? "No position"} ·{" "}
            {/* Fall through the real-world club signals before concluding "free
                agent" — a vendor-imported player has no TransferX club but is
                under contract elsewhere (ADR 0003). Same chain PlayerCard,
                PlayerListRow and GlobalSearch already use. */}
            {player.current_club?.name ??
              player.world_team?.name ??
              player.team_name ??
              "Free agent"}
          </p>
        </div>
      )}

      <Card>
        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Transfer fee */}
          <div>
            <label className="mb-1.5 block text-sm font-semibold text-text-secondary">
              Transfer fee <span className="text-text-muted font-normal">(optional)</span>
            </label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-text-muted">
                £
              </span>
              <CurrencyInput
                value={fee}
                onChange={setFee}
                placeholder="e.g. 25,000,000"
                className="w-full rounded-lg bg-surface pl-7 pr-3 py-2.5 text-sm text-text placeholder-text-muted ring-1 ring-input-border focus:outline-none focus:ring-accent transition-colors"
              />
            </div>
          </div>

          {/* Weekly wage */}
          <div>
            <label className="mb-1.5 block text-sm font-semibold text-text-secondary">
              Weekly wage <span className="text-text-muted font-normal">(optional)</span>
            </label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-text-muted">
                £
              </span>
              <CurrencyInput
                value={wage}
                onChange={setWage}
                placeholder="e.g. 100,000"
                className="w-full rounded-lg bg-surface pl-7 pr-3 py-2.5 text-sm text-text placeholder-text-muted ring-1 ring-input-border focus:outline-none focus:ring-accent transition-colors"
              />
            </div>
          </div>

          {/* Contract years */}
          <div>
            <label className="mb-1.5 block text-sm font-semibold text-text-secondary">
              Contract length <span className="text-text-muted font-normal">(optional)</span>
            </label>
            <input
              type="number"
              min="1"
              max="10"
              step="1"
              value={years}
              onChange={(e) => setYears(e.target.value)}
              placeholder="Years"
              className="w-full rounded-lg bg-surface px-3 py-2.5 text-sm text-text placeholder-text-muted ring-1 ring-input-border focus:outline-none focus:ring-accent transition-colors"
            />
          </div>

          {/* Contract end date */}
          <div>
            <label className="mb-1.5 block text-sm font-semibold text-text-secondary">
              Contract end date <span className="text-text-muted font-normal">(optional)</span>
            </label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="w-full rounded-lg bg-surface px-3 py-2.5 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-accent transition-colors"
            />
          </div>

          {error && <p className="text-sm text-danger-text">{error}</p>}

          <div className="flex gap-3 pt-2">
            <Button
              type="submit"
              variant="primary"
              size="md"
              loading={mutation.isPending}
            >
              Submit offer
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="md"
              onClick={() => navigate(-1)}
            >
              Cancel
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
