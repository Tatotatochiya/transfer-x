import { useId, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { Club, FairValueSignal, Loan, Paginated, PlayerDetail, Sale } from "../../types/api";
import type { ListingAvailability, SaleType } from "../../types/enums";
import Button from "../ui/Button";
import CurrencyInput from "../ui/CurrencyInput";
import Modal from "../ui/Modal";
import TransferWindowBanner from "../transfers/TransferWindowBanner";
import { useToast } from "../../context/ToastContext";
import { useOpenListings } from "../../hooks/useListing";
import { formatCompactCurrency, getApiError } from "../../lib/utils";

// Open to offers first: it is the default, and the listing that asks least of
// the seller — no price, no deadline.
const SALE_TYPES: { value: SaleType; label: string }[] = [
  { value: "OPEN_TO_OFFERS", label: "Open to offers" },
  { value: "FIXED_PRICE", label: "Fixed price" },
  { value: "AUCTION", label: "Auction" },
];

// What the club will consider. Transfer first: it is what a listing always
// meant before loans could be listed.
const AVAILABILITY: { value: ListingAvailability; label: string; hint: string }[] = [
  { value: "TRANSFER", label: "Transfer", hint: "Sell him" },
  { value: "LOAN", label: "Loan", hint: "Loan him out" },
  { value: "EITHER", label: "Either", hint: "Hear both" },
];

/** Why a sale type does not fit what is on offer, or null. The server holds
 *  the same rules (sales/service.validate_listing_terms). */
function saleTypeBlocked(t: SaleType, a: ListingAvailability): string | null {
  if (t === "AUCTION" && a !== "TRANSFER") return "An auction is for a transfer";
  if (t === "FIXED_PRICE" && a === "LOAN") return "A fixed price is a transfer price";
  return null;
}

const INPUT_CLASS =
  "w-full rounded-lg bg-surface px-3 py-2.5 text-sm text-text placeholder-text-muted ring-1 ring-input-border focus:outline-none focus:ring-accent transition-colors";

// datetime-local holds local wall-clock time with no zone, and toISOString()
// is UTC — shift by the offset first or the value is hours out.
function toLocalInputValue(d: Date): string {
  return new Date(d.getTime() - d.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
}

interface ListPlayerFormProps {
  /** The player being listed. Omit to pick from the squad instead. */
  player?: { id: string; name: string };
  /** The picker's starting selection — the `/sales/new?player_id=` deep link. */
  defaultPlayerId?: string;
  onDone: (sale: Sale) => void;
  onCancel: () => void;
}

/**
 * Lists one of the club's players. Used by the squad rows and the player page
 * (player fixed, in a modal) and by /sales/new and the listings pages (picker).
 */
export function ListPlayerForm({ player, defaultPlayerId, onDone, onCancel }: ListPlayerFormProps) {
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const ids = useId();

  const [playerId, setPlayerId] = useState(player?.id ?? defaultPlayerId ?? "");
  const [availability, setAvailability] = useState<ListingAvailability>("TRANSFER");
  const [saleType, setSaleType] = useState<SaleType>("OPEN_TO_OFFERS");

  function chooseAvailability(a: ListingAvailability) {
    setAvailability(a);
    // Keep the sale type valid for it rather than leaving a blocked choice selected.
    if (saleTypeBlocked(saleType, a)) setSaleType("OPEN_TO_OFFERS");
  }
  const [askingPrice, setAskingPrice] = useState("");
  const [reservePrice, setReservePrice] = useState("");
  const [minIncrement, setMinIncrement] = useState("500000");
  const [deadline, setDeadline] = useState(() => toLocalInputValue(new Date(Date.now() + 7 * 86_400_000)));
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);

  // ── Picker data — only when no player was given ────────────────────────────

  const picking = !player;

  const { data: club } = useQuery<Club>({
    queryKey: ["clubs", "me"],
    queryFn: () => api.get<Club>("/clubs/me").then((r) => r.data),
    staleTime: 60_000,
    enabled: picking,
  });

  const { data: squad, isLoading: squadLoading } = useQuery<Paginated<PlayerDetail>>({
    queryKey: ["clubs", club?.id, "squad", "sale-picker"],
    queryFn: () =>
      api.get<Paginated<PlayerDetail>>(`/clubs/${club!.id}/players`, { params: { page_size: 100 } })
        .then((r) => r.data),
    enabled: picking && !!club?.id,
  });

  const { byPlayer: listed } = useOpenListings(club?.id, picking);

  // Borrowed players are registered to us but not ours to sell.
  const { data: loansIn = [] } = useQuery<Loan[]>({
    queryKey: ["clubs", "me", "loans", "in"],
    queryFn: () => api.get<Loan[]>("/clubs/me/loans?direction=in").then((r) => r.data),
    staleTime: 60_000,
    enabled: picking,
  });

  function unavailable(p: PlayerDetail): string | null {
    if (listed.has(p.id)) return "already listed";
    if (loansIn.some((l) => l.player_id === p.id)) return "on loan here";
    if (p.active_deal?.status === "IN_PROGRESS") return "transfer pending";
    return null;
  }

  // ── Model estimate — a hint beside the price, never pre-filled (D5) ───────

  // Same key and shape as the player page's query, so opening this from there
  // costs no request.
  const { data: fairValue = null } = useQuery<FairValueSignal | null>({
    queryKey: ["valuation", playerId],
    queryFn: () =>
      api.get<FairValueSignal>(`/valuation/players/${playerId}`).then((r) => r.data).catch(() => null),
    enabled: !!playerId,
    staleTime: 300_000,
  });

  const model = fairValue ? Number(fairValue.fair_value) : null;
  // "Use £23.5m" must put £23,500,000 in the box, not the model's unrounded
  // figure — the chip says what it does.
  const suggested =
    model == null ? null : model >= 1_000_000 ? Math.round(model / 100_000) * 100_000 : Math.round(model / 1_000) * 1_000;

  // ── Submit ─────────────────────────────────────────────────────────────────

  const mutation = useMutation({
    mutationFn: (body: object) => api.post<Sale>("/sales", body).then((r) => r.data),
    onSuccess: (sale) => {
      queryClient.invalidateQueries({ queryKey: ["sales"] });
      const type = SALE_TYPES.find((t) => t.value === sale.sale_type)?.label.toLowerCase();
      const what = sale.availability === "LOAN" ? "for loan" : sale.availability === "EITHER" ? "for transfer or loan" : type;
      addToast(`${sale.player?.name ?? player?.name ?? "Player"} is listed — ${what}.`, "success");
      onDone(sale);
    },
    onError: (err: unknown) => setError(getApiError(err, "Failed to create listing.")),
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (!playerId) { setError("Select a player."); return; }

    const body: Record<string, unknown> = {
      player_id: playerId,
      sale_type: saleType,
      availability,
      ...(notes && { notes }),
    };

    // A loan-only listing has no asking price: clubs propose the loan terms.
    const parsedAsking = parseFloat(askingPrice);
    if (!loanOnly && askingPrice && !isNaN(parsedAsking)) body.asking_price = parsedAsking;

    if (saleType === "AUCTION") {
      const parsedReserve = parseFloat(reservePrice);
      if (reservePrice && !isNaN(parsedReserve)) body.reserve_price = parsedReserve;

      const parsedIncrement = parseFloat(minIncrement);
      if (!isNaN(parsedIncrement) && parsedIncrement > 0) body.min_increment = parsedIncrement;

      if (!deadline) { setError("Auctions require a deadline."); return; }
      body.deadline = new Date(deadline).toISOString();
    }

    mutation.mutate(body);
  }

  const isAuction = saleType === "AUCTION";
  const loanOnly = availability === "LOAN";
  const players = squad?.items ?? [];

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-5">
      {picking && (
        <div>
          <label htmlFor={`${ids}-player`} className="mb-1.5 block text-sm font-semibold text-text-secondary">Player</label>
          <select
            id={`${ids}-player`}
            value={playerId}
            onChange={(e) => setPlayerId(e.target.value)}
            required
            disabled={squadLoading}
            className={`${INPUT_CLASS} disabled:opacity-50`}
          >
            <option value="">{squadLoading ? "Loading players…" : "Select a player"}</option>
            {players.map((p) => {
              const reason = unavailable(p);
              return (
                <option key={p.id} value={p.id} disabled={!!reason}>
                  {p.name}{p.position ? ` (${p.position})` : ""}{reason ? ` — ${reason}` : ""}
                </option>
              );
            })}
          </select>
          {players.length === 0 && !squadLoading && (
            <p className="mt-1.5 text-[13px] text-text-muted">
              No players in your squad.{" "}
              <Link to="/players/market" className="text-accent hover:underline">Browse the market</Link>
            </p>
          )}
        </div>
      )}

      {/* Available for — what the club will consider. First, because it
          decides which sale types make sense. */}
      <div>
        <p className="mb-1.5 text-sm font-semibold text-text-secondary">Available for</p>
        <div className="flex gap-2">
          {AVAILABILITY.map((a) => (
            <button
              key={a.value}
              type="button"
              aria-pressed={availability === a.value}
              onClick={() => chooseAvailability(a.value)}
              className={`min-h-11 flex-1 rounded-lg px-2 py-2 text-sm leading-tight transition-colors lg:min-h-0 ${
                availability === a.value
                  ? "bg-accent-bg text-accent-active ring-1 ring-accent"
                  : "bg-surface-inset text-text-muted hover:text-text ring-1 ring-input-border"
              }`}
            >
              <span className="block font-semibold">{a.label}</span>
              <span className="block text-[11px] opacity-80">{a.hint}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Sale type */}
      <div>
        <p className="mb-1.5 text-sm font-semibold text-text-secondary">How offers arrive</p>
        <div className="flex gap-2">
          {SALE_TYPES.map((t) => {
            const blocked = saleTypeBlocked(t.value, availability);
            return (
              <button
                key={t.value}
                type="button"
                aria-pressed={saleType === t.value}
                disabled={!!blocked}
                title={blocked ?? undefined}
                onClick={() => setSaleType(t.value)}
                className={`min-h-11 flex-1 rounded-lg px-2 py-2 text-sm leading-tight transition-colors disabled:cursor-not-allowed disabled:opacity-40 lg:min-h-0 ${
                  saleType === t.value
                    ? "bg-accent-bg text-accent-active ring-1 ring-accent"
                    : "bg-surface-inset text-text-muted hover:text-text ring-1 ring-input-border"
                }`}
              >
                {t.label}
              </button>
            );
          })}
        </div>
        {/* Tooltips never show on touch, so the reason is stated too. */}
        {availability !== "TRANSFER" && (
          <p className="mt-1.5 text-[13px] text-text-muted">
            {availability === "LOAN"
              ? "A loan is open to offers: clubs propose the dates, loan fee and wage share."
              : "No auction: a loan cannot be auctioned."}
          </p>
        )}
      </div>

      {/* Price — none on a loan-only listing: a figure there would read as his
          price, to buyers and to the fair-value signal. */}
      {!loanOnly && (
      <div>
        <label htmlFor={`${ids}-price`} className="mb-1.5 block text-sm font-semibold text-text-secondary">
          {isAuction ? "Starting price" : availability === "EITHER" ? "Asking price for a transfer" : "Asking price"}{" "}
          <span className="text-text-muted font-normal">(optional)</span>
        </label>
        <div className="relative">
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-text-muted">£</span>
          <CurrencyInput
            id={`${ids}-price`}
            value={askingPrice}
            onChange={setAskingPrice}
            placeholder="e.g. 25,000,000"
            className={`${INPUT_CLASS} pl-7`}
          />
        </div>
        {/* Not on auctions: the bidding sets that price, and the market never
            shows the model against an auction either (D7). */}
        {fairValue && suggested != null && !isAuction && (
          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1">
            <span
              className="text-[13px] text-text-muted"
              title={`${fairValue.confidence.toLowerCase()} confidence`}
            >
              Model {formatCompactCurrency(model)} · range {formatCompactCurrency(Number(fairValue.fair_value_low))}–{formatCompactCurrency(Number(fairValue.fair_value_high))}
            </span>
            <Button type="button" variant="secondary" size="sm" onClick={() => setAskingPrice(String(suggested))}>
              Use {formatCompactCurrency(suggested)}
            </Button>
          </div>
        )}
      </div>

      )}

      {isAuction && (
        <>
          <div>
            <label htmlFor={`${ids}-reserve`} className="mb-1.5 block text-sm font-semibold text-text-secondary">
              Reserve price <span className="text-text-muted font-normal">(optional)</span>
            </label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-text-muted">£</span>
              <CurrencyInput
                id={`${ids}-reserve`}
                value={reservePrice}
                onChange={setReservePrice}
                placeholder="Minimum to sell"
                className={`${INPUT_CLASS} pl-7`}
              />
            </div>
          </div>

          <div>
            <label htmlFor={`${ids}-increment`} className="mb-1.5 block text-sm font-semibold text-text-secondary">
              Minimum bid increment
            </label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-text-muted">£</span>
              <CurrencyInput
                id={`${ids}-increment`}
                value={minIncrement}
                onChange={setMinIncrement}
                className={`${INPUT_CLASS} pl-7`}
              />
            </div>
          </div>

          <div>
            <label htmlFor={`${ids}-deadline`} className="mb-1.5 block text-sm font-semibold text-text-secondary">
              Auction deadline
            </label>
            <input
              id={`${ids}-deadline`}
              type="datetime-local"
              required
              value={deadline}
              onChange={(e) => setDeadline(e.target.value)}
              min={toLocalInputValue(new Date(Date.now() + 60 * 60 * 1000))}
              className={INPUT_CLASS}
            />
          </div>
        </>
      )}

      <div>
        <label htmlFor={`${ids}-notes`} className="mb-1.5 block text-sm font-semibold text-text-secondary">
          Notes <span className="text-text-muted font-normal">(optional)</span>
        </label>
        <textarea
          id={`${ids}-notes`}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={2}
          placeholder="Anything prospective buyers should know…"
          className={`${INPUT_CLASS} resize-none`}
        />
      </div>

      {error && <p className="text-sm text-danger-text">{error}</p>}

      <div className="flex gap-3">
        <Button type="submit" variant="primary" size="md" loading={mutation.isPending}>
          List player
        </Button>
        <Button type="button" variant="ghost" size="md" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

/**
 * The form in a modal, so listing happens where the player is — the squad row,
 * his own page, the listings pages — and the user stays there afterwards.
 * `onClose` should be stable (useCallback): the modal's focus trap re-runs
 * whenever it changes, which would pull focus out of a field mid-typing.
 */
export default function ListPlayerModal({
  open, onClose, player,
}: {
  open: boolean;
  onClose: () => void;
  player?: { id: string; name: string };
}) {
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={player ? `List ${player.name}` : "List a player"}
      className="max-h-[calc(100dvh-2rem)] overflow-y-auto"
    >
      <div className="px-6 py-5">
        <TransferWindowBanner />
        <ListPlayerForm player={player} onDone={onClose} onCancel={onClose} />
      </div>
    </Modal>
  );
}
