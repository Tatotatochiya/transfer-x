import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import api from "../../lib/api";
import type { Club, Paginated, Player, Sale } from "../../types/api";
import type { SaleType } from "../../types/enums";
import Button from "../../components/ui/Button";
import PageHeader from "../../components/ui/PageHeader";
import Card from "../../components/ui/Card";
import CurrencyInput from "../../components/ui/CurrencyInput";
import { getApiError } from "../../lib/utils";
import TransferWindowBanner from "../../components/transfers/TransferWindowBanner";

// Convert local datetime-input value to UTC ISO string
function localDatetimeToISO(value: string): string {
  // value is like "2026-03-20T14:30" — treat as local time
  return new Date(value).toISOString();
}

export default function CreateSalePage() {
  const navigate = useNavigate();

  const [playerId, setPlayerId] = useState("");
  const [saleType, setSaleType] = useState<SaleType>("AUCTION");
  const [askingPrice, setAskingPrice] = useState("");
  const [reservePrice, setReservePrice] = useState("");
  const [minIncrement, setMinIncrement] = useState("500000");
  const [deadline, setDeadline] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);

  // Fetch current club to get its ID
  const { data: club } = useQuery<Club>({
    queryKey: ["clubs", "me"],
    queryFn: () => api.get<Club>("/clubs/me").then((r) => r.data),
    staleTime: 60_000,
  });

  // Fetch squad players for the club (same source as squad view)
  const { data: playersData, isLoading: playersLoading } = useQuery<Paginated<Player>>({
    queryKey: ["clubs", club?.id, "squad", "sale-picker"],
    queryFn: () =>
      api
        .get<Paginated<Player>>(`/clubs/${club!.id}/players`, { params: { page_size: 100 } })
        .then((r) => r.data),
    enabled: !!club?.id,
  });

  const mutation = useMutation({
    mutationFn: (body: object) =>
      api.post<Sale>("/sales", body).then((r) => r.data),
    onSuccess: () => navigate("/sales/mine"),
    onError: (err: unknown) => {
      setError(getApiError(err, "Failed to create listing."));
    },
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (!playerId) { setError("Select a player."); return; }

    const body: Record<string, unknown> = {
      player_id: playerId,
      sale_type: saleType,
      ...(notes && { notes }),
    };

    const parsedAsking = parseFloat(askingPrice);
    if (askingPrice && !isNaN(parsedAsking)) body.asking_price = parsedAsking;

    if (saleType === "AUCTION") {
      const parsedReserve = parseFloat(reservePrice);
      if (reservePrice && !isNaN(parsedReserve)) body.reserve_price = parsedReserve;

      const parsedIncrement = parseFloat(minIncrement);
      if (!isNaN(parsedIncrement) && parsedIncrement > 0) body.min_increment = parsedIncrement;

      if (!deadline) { setError("Auctions require a deadline."); return; }
      body.deadline = localDatetimeToISO(deadline);
    }

    mutation.mutate(body);
  }

  const players = playersData?.items ?? [];
  const isAuction = saleType === "AUCTION";

  return (
    <div className="max-w-2xl">
      <PageHeader title="New Listing" subtitle="List a player for sale or auction" />

      <TransferWindowBanner />

      <Card>
        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Player */}
          <div>
            <label className="mb-1.5 block text-sm font-medium text-slate-300">Player</label>
            <select
              value={playerId}
              onChange={(e) => setPlayerId(e.target.value)}
              required
              disabled={playersLoading}
              className="w-full rounded-lg bg-slate-800 px-3 py-2.5 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500 transition-colors disabled:opacity-50"
            >
              <option value="">
                {playersLoading ? "Loading players…" : "Select a player"}
              </option>
              {players.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}{p.position ? ` (${p.position})` : ""}
                </option>
              ))}
            </select>
            {players.length === 0 && !playersLoading && (
              <p className="mt-1.5 text-xs text-slate-500">
                No players found.{" "}
                <button
                  type="button"
                  onClick={() => navigate("/players")}
                  className="text-emerald-400 hover:underline"
                >
                  Add players first
                </button>
              </p>
            )}
          </div>

          {/* Sale type */}
          <div>
            <label className="mb-1.5 block text-sm font-medium text-slate-300">Sale type</label>
            <div className="flex gap-2">
              {(["AUCTION", "OPEN_TO_OFFERS", "FIXED_PRICE"] as SaleType[]).map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setSaleType(t)}
                  className={`flex-1 rounded-lg py-2 text-sm transition-colors ${
                    saleType === t
                      ? "bg-emerald-500/15 text-emerald-400 ring-1 ring-emerald-500/30"
                      : "bg-slate-800 text-slate-400 hover:text-white"
                  }`}
                >
                  {t === "AUCTION" ? "Auction" : t === "OPEN_TO_OFFERS" ? "Open to Offers" : "Fixed Price"}
                </button>
              ))}
            </div>
          </div>

          {/* Asking price */}
          <div>
            <label className="mb-1.5 block text-sm font-medium text-slate-300">
              {isAuction ? "Starting price" : "Asking price"}{" "}
              <span className="text-slate-500">(optional)</span>
            </label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-slate-500">£</span>
              <CurrencyInput
                value={askingPrice}
                onChange={setAskingPrice}
                placeholder="e.g. 25,000,000"
                className="w-full rounded-lg bg-slate-800 pl-7 pr-3 py-2.5 text-sm text-white placeholder-slate-500 ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500 transition-colors"
              />
            </div>
          </div>

          {/* Auction-specific fields */}
          {isAuction && (
            <>
              <div>
                <label className="mb-1.5 block text-sm font-medium text-slate-300">
                  Reserve price <span className="text-slate-500">(optional)</span>
                </label>
                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-slate-500">£</span>
                  <CurrencyInput
                    value={reservePrice}
                    onChange={setReservePrice}
                    placeholder="Minimum to sell"
                    className="w-full rounded-lg bg-slate-800 pl-7 pr-3 py-2.5 text-sm text-white placeholder-slate-500 ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500 transition-colors"
                  />
                </div>
              </div>

              <div>
                <label className="mb-1.5 block text-sm font-medium text-slate-300">
                  Minimum bid increment
                </label>
                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-slate-500">£</span>
                  <CurrencyInput
                    value={minIncrement}
                    onChange={setMinIncrement}
                    className="w-full rounded-lg bg-slate-800 pl-7 pr-3 py-2.5 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500 transition-colors"
                  />
                </div>
              </div>

              <div>
                <label className="mb-1.5 block text-sm font-medium text-slate-300">
                  Auction deadline
                </label>
                <input
                  type="datetime-local"
                  required
                  value={deadline}
                  onChange={(e) => setDeadline(e.target.value)}
                  min={new Date(Date.now() + 60 * 60 * 1000).toISOString().slice(0, 16)}
                  className="w-full rounded-lg bg-slate-800 px-3 py-2.5 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500 transition-colors"
                />
              </div>
            </>
          )}

          {/* Notes */}
          <div>
            <label className="mb-1.5 block text-sm font-medium text-slate-300">
              Notes <span className="text-slate-500">(optional)</span>
            </label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
              placeholder="Any additional information for prospective buyers…"
              className="w-full rounded-lg bg-slate-800 px-3 py-2.5 text-sm text-white placeholder-slate-500 ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500 transition-colors resize-none"
            />
          </div>

          {error && (
            <p className="text-sm text-red-400">{error}</p>
          )}

          <div className="flex gap-3 pt-2">
            <Button type="submit" variant="primary" size="md" loading={mutation.isPending}>
              Create listing
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="md"
              onClick={() => navigate("/sales/mine")}
            >
              Cancel
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
