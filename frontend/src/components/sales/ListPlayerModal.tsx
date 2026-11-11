import { useId, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { Club, FairValueSignal, Loan, Paginated, PlayerDetail, Sale } from "../../types/api";
import type { ListingAvailability } from "../../types/enums";
import Button from "../ui/Button";
import CurrencyInput from "../ui/CurrencyInput";
import Modal from "../ui/Modal";
import TransferWindowBanner from "../transfers/TransferWindowBanner";
import { useToast } from "../../context/ToastContext";
import { useOpenListings } from "../../hooks/useListing";
import { formatCompactCurrency, getApiError } from "../../lib/utils";
import { useListingAdvice } from "../../hooks/useAssistant";
import Spinner from "../ui/Spinner";

// What the club will consider. Transfer first: it is what a listing always
// meant before loans could be listed.
const AVAILABILITY: { value: ListingAvailability; label: string; hint: string }[] = [
  { value: "TRANSFER", label: "Transfer", hint: "Sell him" },
  { value: "LOAN", label: "Loan", hint: "Loan him out" },
  { value: "EITHER", label: "Either", hint: "Hear both" },
];

const INPUT_CLASS =
  "w-full rounded-lg bg-surface px-3 py-2.5 text-small text-text placeholder-text-muted ring-1 ring-input-border focus:outline-none focus:ring-accent transition-colors";

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
  // One kind of listing: open to offers, with an optional guide price and an
  // optional date. "Fixed price" was that with a firmer label, so it is
  // folded in. Auctions are retired (product ADR 0011): the club chooses
  // among the offers, and "Offers by" covers "best bids by Friday".
  const [askingPrice, setAskingPrice] = useState("");
  // "Offers by": optional; the listing expires then.
  const [offersUntil, setOffersUntil] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);
  // The pricing assistant: asked for on demand, and remembered if the club
  // takes its price, so the listing is audited as AI-assisted.
  const [adviceAsked, setAdviceAsked] = useState(false);
  const [aiPrice, setAiPrice] = useState<string | null>(null);
  const { data: advice, isFetching: adviceLoading, error: adviceError } = useListingAdvice(playerId, adviceAsked);

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
  // "Use £23.5M" must put £23,500,000 in the box, not the model's unrounded
  // figure — the chip says what it does.
  const suggested =
    model == null ? null : model >= 1_000_000 ? Math.round(model / 100_000) * 100_000 : Math.round(model / 1_000) * 1_000;

  // ── Submit ─────────────────────────────────────────────────────────────────

  const mutation = useMutation({
    mutationFn: (body: object) => api.post<Sale>("/sales", body).then((r) => r.data),
    onSuccess: (sale) => {
      queryClient.invalidateQueries({ queryKey: ["sales"] });
      const what =
        sale.availability === "LOAN" ? "for loan"
        : sale.availability === "EITHER" ? "for transfer or loan"
        : "for transfer";
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
      sale_type: "OPEN_TO_OFFERS",
      availability,
      ...(notes && { notes }),
    };

    // A loan-only listing has no asking price: clubs propose the loan terms.
    const parsedAsking = parseFloat(askingPrice);
    if (!loanOnly && askingPrice && !isNaN(parsedAsking)) body.asking_price = parsedAsking;
    if (aiPrice != null && aiPrice === askingPrice) body.ai_assisted = true;

    if (offersUntil) body.deadline = new Date(offersUntil).toISOString();

    mutation.mutate(body);
  }

  const loanOnly = availability === "LOAN";
  const players = squad?.items ?? [];

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-5">
      {picking && (
        <div>
          <label htmlFor={`${ids}-player`} className="mb-1.5 block text-small font-semibold text-text-secondary">Player</label>
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
            <p className="mt-1.5 text-caption text-text-muted">
              No players in your squad.{" "}
              <Link to="/players/market" className="text-accent hover:underline">Browse the market</Link>
            </p>
          )}
        </div>
      )}

      {/* Available for — what the club will consider. First, because it
          decides which sale types make sense. */}
      <div>
        <p className="mb-1.5 text-body font-semibold text-text-secondary">Available for</p>
        <div className="flex gap-2">
          {AVAILABILITY.map((a) => (
            <button
              key={a.value}
              type="button"
              aria-pressed={availability === a.value}
              onClick={() => setAvailability(a.value)}
              className={`min-h-11 flex-1 rounded-lg px-2 py-2 text-body leading-tight transition-colors lg:min-h-0 ${
                availability === a.value
                  ? "bg-accent-bg text-accent-active ring-1 ring-accent"
                  : "bg-surface-inset text-text-muted hover:text-text ring-1 ring-input-border"
              }`}
            >
              <span className="block font-semibold">{a.label}</span>
              <span className="block text-caption opacity-80">{a.hint}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Pricing assistant — a guide price from the model and comparable
          completed transfers, and whether to open him to loans. Advice only:
          "Use" fills the fields below, which the club still reviews. */}
      {playerId && (
        <div className="rounded-xl bg-surface p-3.5 ring-1 ring-ai-ring">
          <div className="flex items-center justify-between gap-3">
            <p className="text-body font-semibold text-text"><span className="text-ai-text">✦</span> Pricing assistant</p>
            {!advice && (
              <button
                type="button"
                onClick={() => setAdviceAsked(true)}
                disabled={adviceLoading}
                className="rounded-lg bg-ai-bg px-3 py-1.5 text-caption font-semibold text-ai-text ring-1 ring-ai-ring hover:brightness-95 disabled:opacity-50"
              >
                {adviceLoading ? <Spinner size="sm" /> : "Suggest a price"}
              </button>
            )}
          </div>
          {adviceError != null && <p className="mt-2 text-caption text-danger-text">{getApiError(adviceError, "No suggestion just now.")}</p>}
          {advice && (
            <div className="mt-2 space-y-2 text-caption leading-snug">
              {advice.guide_price != null ? (
                <p className="text-text">
                  Guide <span className="font-semibold">{formatCompactCurrency(advice.guide_price)}</span>
                  <span className="text-text-muted"> · from the {advice.guide_basis}</span>
                  {advice.comparables.length > 0 && (
                    <span className="text-text-muted"> ({advice.comparables.length} comparable{advice.comparables.length === 1 ? "" : "s"})</span>
                  )}
                </p>
              ) : (
                <p className="text-text-muted">No model valuation or comparable transfers for him yet — set the price from your own view.</p>
              )}
              {advice.summary && <p className="text-text-secondary">{advice.summary}</p>}
              {advice.reasons.length > 0 && (
                <ul className="list-disc space-y-0.5 pl-4 text-text-secondary">
                  {advice.reasons.map((r, i) => <li key={i}>{r}</li>)}
                </ul>
              )}
              {advice.tips.length > 0 && (
                <ul className="list-disc space-y-0.5 pl-4 text-text-muted">
                  {advice.tips.map((r, i) => <li key={i}>{r}</li>)}
                </ul>
              )}
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => {
                  setAvailability(advice.availability);
                  if (advice.guide_price != null && advice.availability !== "LOAN") {
                    const v = String(advice.guide_price);
                    setAskingPrice(v);
                    setAiPrice(v);
                  }
                }}
              >
                Use {advice.guide_price != null && advice.availability !== "LOAN" ? `${formatCompactCurrency(advice.guide_price)}, ` : ""}
                {advice.availability === "EITHER" ? "transfer or loan" : advice.availability.toLowerCase()}
              </Button>
            </div>
          )}
        </div>
      )}

      {/* Price — none on a loan-only listing: a figure there would read as his
          price, to buyers and to the fair-value signal. */}
      {!loanOnly && (
      <div>
        <label htmlFor={`${ids}-price`} className="mb-1.5 block text-small font-semibold text-text-secondary">
          {availability === "EITHER" ? "Guide price for a transfer" : "Guide price"}{" "}
          <span className="text-text-muted font-normal">(optional)</span>
        </label>
        <div className="relative">
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-small text-text-muted">£</span>
          <CurrencyInput
            id={`${ids}-price`}
            value={askingPrice}
            onChange={setAskingPrice}
            placeholder="e.g. 25,000,000"
            className={`${INPUT_CLASS} pl-7`}
          />
        </div>
        {fairValue && suggested != null && (
          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1">
            <span
              className="text-caption text-text-muted"
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

      {/* Offers by — optional. The "best offers by Friday" a club would set
          when several want him; a loan listing needs no end. */}
      <div>
        <label htmlFor={`${ids}-until`} className="mb-1.5 block text-small font-semibold text-text-secondary">
          Offers by <span className="text-text-muted font-normal">(optional)</span>
        </label>
        <input
          id={`${ids}-until`}
          type="datetime-local"
          value={offersUntil}
          onChange={(e) => setOffersUntil(e.target.value)}
          min={toLocalInputValue(new Date(Date.now() + 60 * 60 * 1000))}
          className={INPUT_CLASS}
        />
        <p className="mt-1 text-caption text-text-muted">
          Clubs see this date. The listing closes then, and you choose from the offers you have. Leave it
          empty to keep hearing offers until you withdraw it.
        </p>
      </div>

      <div>
        <label htmlFor={`${ids}-notes`} className="mb-1.5 block text-small font-semibold text-text-secondary">
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

      {error && <p className="text-body text-danger-text">{error}</p>}

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
