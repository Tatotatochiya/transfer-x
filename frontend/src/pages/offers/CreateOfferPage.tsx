import { useEffect, useState } from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import api from "../../lib/api";
import type { Offer, PlayerDetail, Sale } from "../../types/api";
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

  const [dealType, setDealType] = useState<"PERMANENT" | "LOAN">("PERMANENT");
  const [fee, setFee]         = useState("");
  // Required when the fee is £0, and posted to the thread for the seller.
  const [noFeeReason, setNoFeeReason] = useState("");
  // Loan terms. Held separately from the permanent fields rather than reusing
  // them, because a loan's money is loan_fee and the server rejects an offer
  // that carries both.
  const [loanStart, setLoanStart]   = useState("");
  const [loanEnd, setLoanEnd]       = useState("");
  const [loanFee, setLoanFee]       = useState("");
  const [wageSplit, setWageSplit]   = useState("100");
  const [optionToBuy, setOptionToBuy] = useState("");
  const [obligation, setObligation] = useState(false);
  const [conditions, setConditions] = useState("");
  const [recallAllowed, setRecallAllowed] = useState(false);
  const [wage, setWage]       = useState("");
  const [years, setYears]     = useState("");
  const [endDate, setEndDate] = useState("");
  const [anonymous, setAnonymous] = useState(false);
  const [error, setError]     = useState<string | null>(null);

  // Load player info for display
  const { data: player, isLoading: playerLoading } = useQuery<PlayerDetail>({
    queryKey: ["players", playerId],
    queryFn: () =>
      api.get<PlayerDetail>(`/players/market/${playerId}`).then((r) => r.data),
    enabled: !!playerId,
  });

  // Made from a listing: the listing says what its club will consider, and an
  // offer it does not invite is refused by the server — so only offer those.
  const { data: sale } = useQuery<Sale>({
    queryKey: ["sales", saleId],
    queryFn: () => api.get<Sale>(`/sales/${saleId}`).then((r) => r.data),
    enabled: !!saleId,
  });
  const blockedType = (t: "PERMANENT" | "LOAN"): string | null => {
    if (!sale) return null;
    if (t === "LOAN" && sale.availability === "TRANSFER") return "Listed for a transfer only";
    if (t === "PERMANENT" && sale.availability === "LOAN") return "Listed for loan only";
    return null;
  };
  useEffect(() => {
    if (sale?.availability === "LOAN") setDealType("LOAN");
  }, [sale?.availability]);

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

    // Address the offer to whoever actually owns him. During a loan the
    // *loanee* holds the registration and so appears as current_club, but they
    // cannot accept — the server rejects an offer naming a club that does not
    // own the player, so this would fail only at acceptance.
    const owningClubId =
      player?.active_loan?.parent_club?.id ?? player?.current_club?.id;
    if (owningClubId) body.to_club_id = owningClubId;

    if (dealType === "LOAN") {
      body.deal_type = "LOAN";
      if (!loanStart || !loanEnd) {
        setError("A loan needs both a start and an end date.");
        return;
      }
      if (loanEnd <= loanStart) {
        setError("The loan must end after it starts.");
        return;
      }
      body.loan_start = loanStart;
      body.loan_end = loanEnd;
      const parsedLoanFee = parseFloat(loanFee);
      if (loanFee && !isNaN(parsedLoanFee)) body.loan_fee = parsedLoanFee;
      const parsedSplit = parseFloat(wageSplit);
      if (isNaN(parsedSplit) || parsedSplit < 0 || parsedSplit > 100) {
        setError("The wage split must be between 0 and 100%.");
        return;
      }
      // The API takes a fraction, matching sell_on_pct and commission_pct.
      body.wage_split_pct = parsedSplit / 100;
      const parsedOption = parseFloat(optionToBuy);
      if (optionToBuy && !isNaN(parsedOption)) body.option_to_buy = parsedOption;
      if (obligation) {
        if (!optionToBuy || isNaN(parsedOption)) {
          setError("An obligation to buy needs a price — set the option-to-buy amount.");
          return;
        }
        body.obligation_to_buy = true;
        if (conditions.trim()) body.obligation_conditions = conditions.trim();
      }
      if (recallAllowed) body.recall_allowed = true;
    } else {
      // A permanent transfer always names a fee. £0 is a real term — a club
      // releasing a player to clear his wages — but it has to say why.
      const parsedFee = parseFloat(fee);
      if (!fee || isNaN(parsedFee)) {
        setError("Enter a transfer fee. Use £0 only if his club is releasing him for nothing.");
        return;
      }
      body.fee_amount = parsedFee;
      if (parsedFee === 0) {
        if (!noFeeReason.trim()) {
          setError("Say why the fee is £0 — his club will read this with the offer.");
          return;
        }
        body.no_fee_reason = noFeeReason.trim();
      }

      // His new contract with you. A loan has none of these: he stays on his
      // own contract, and the loan's wage is read from it.
      const parsedWage = parseFloat(wage);
      if (wage && !isNaN(parsedWage)) body.wage_weekly = parsedWage;
      const parsedYears = parseInt(years);
      if (years && !isNaN(parsedYears)) body.contract_years = parsedYears;
      if (endDate) body.contract_end_date = endDate;
    }
    if (anonymous) body.is_anonymous = true;

    mutation.mutate(body);
  }

  const parsedFeeValue = fee && !isNaN(parseFloat(fee)) ? parseFloat(fee) : null;

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
          {/* What kind of deal. This is the first decision, not a detail: it
              changes what the rest of the form even asks for, and it cannot be
              changed after the seller accepts — countering a loan with a
              permanent offer is a different proposal, so the server refuses to
              swap it. */}
          <div>
            <label className="mb-1.5 block text-sm font-semibold text-text-secondary">
              What are you proposing?
            </label>
            <div className="grid grid-cols-2 gap-2">
              {([
                ["PERMANENT", "Permanent transfer", "He joins you outright."],
                ["LOAN", "Loan", "He plays for you for a fixed spell, then goes back."],
              ] as const).map(([value, label, hint]) => {
                const blocked = blockedType(value);
                return (
                  <button
                    key={value}
                    type="button"
                    disabled={!!blocked}
                    // An error about the other form's fields no longer applies.
                    onClick={() => { setDealType(value); setError(null); }}
                    className={`rounded-lg px-3.5 py-2.5 text-left ring-1 transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
                      dealType === value
                        ? "bg-accent-bg text-accent-active ring-accent/40"
                        : "bg-surface-inset text-text-secondary ring-border hover:ring-input-border"
                    }`}
                  >
                    <span className="block text-sm font-semibold">{label}</span>
                    {/* The reason as text, not a tooltip — touch never shows one. */}
                    <span className="mt-0.5 block text-[13px] text-text-muted">{blocked ?? hint}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {dealType === "LOAN" ? (
            <>
              {/* Dates. Both required — a loan with no end is a transfer. */}
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div>
                  <label className="mb-1.5 block text-sm font-semibold text-text-secondary">
                    Loan starts
                  </label>
                  <input
                    type="date"
                    value={loanStart}
                    onChange={(e) => setLoanStart(e.target.value)}
                    className="w-full rounded-lg bg-surface px-3 py-2.5 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-accent transition-colors"
                  />
                </div>
                <div>
                  <label className="mb-1.5 block text-sm font-semibold text-text-secondary">
                    Loan ends
                  </label>
                  <input
                    type="date"
                    value={loanEnd}
                    onChange={(e) => setLoanEnd(e.target.value)}
                    className="w-full rounded-lg bg-surface px-3 py-2.5 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-accent transition-colors"
                  />
                  <p className="mt-1 text-[13px] text-text-muted">
                    Cannot run past his contract with his current club, or past 18 months.
                  </p>
                </div>
              </div>

              {/* Loan fee */}
              <div>
                <label className="mb-1.5 block text-sm font-semibold text-text-secondary">
                  Loan fee <span className="font-normal text-text-muted">(optional)</span>
                </label>
                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-text-muted">£</span>
                  <CurrencyInput
                    value={loanFee}
                    onChange={setLoanFee}
                    placeholder="e.g. 2,000,000"
                    className="w-full rounded-lg bg-surface pl-7 pr-3 py-2.5 text-sm text-text placeholder-text-muted ring-1 ring-input-border focus:outline-none focus:ring-accent transition-colors"
                  />
                </div>
                <p className="mt-1 text-[13px] text-text-muted">
                  Paid to his club for the spell. Many loans have none — the wage is the cost.
                </p>
              </div>

              {/* Wage split. A percentage is what clubs agree, but they budget
                  in pounds, so the weekly figure is shown live rather than left
                  as an arithmetic exercise. */}
              <div>
                <label className="mb-1.5 block text-sm font-semibold text-text-secondary">
                  Share of his wage you pay
                </label>
                <div className="relative max-w-[160px]">
                  <input
                    type="number"
                    min={0}
                    max={100}
                    value={wageSplit}
                    onChange={(e) => setWageSplit(e.target.value)}
                    className="w-full rounded-lg bg-surface px-3 py-2.5 pr-8 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-accent transition-colors"
                  />
                  <span className="absolute right-3 top-1/2 -translate-y-1/2 text-sm text-text-muted">%</span>
                </div>
                {/* The wage is his contract wage, read by the server — not a
                    figure to type. A blank used to mean you paid £0. The pound
                    figure appears on the offer once it is sent. */}
                <p className="mt-1 text-[13px] text-text-muted">
                  A share of his current contract wage. The weekly figure is shown on the offer once
                  it is sent, and is reserved from your wage budget.
                </p>
              </div>

              {/* Option / obligation */}
              <div>
                <label className="mb-1.5 block text-sm font-semibold text-text-secondary">
                  Option to buy <span className="font-normal text-text-muted">(optional)</span>
                </label>
                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-text-muted">£</span>
                  <CurrencyInput
                    value={optionToBuy}
                    onChange={setOptionToBuy}
                    placeholder="e.g. 18,000,000"
                    className="w-full rounded-lg bg-surface pl-7 pr-3 py-2.5 text-sm text-text placeholder-text-muted ring-1 ring-input-border focus:outline-none focus:ring-accent transition-colors"
                  />
                </div>
                <label className="mt-2.5 flex items-start gap-2.5">
                  <input
                    type="checkbox"
                    checked={obligation}
                    disabled={!optionToBuy}
                    onChange={(e) => setObligation(e.target.checked)}
                    className="mt-0.5 h-4 w-4 shrink-0 rounded accent-accent disabled:opacity-40"
                  />
                  <span className={`text-[13px] ${optionToBuy ? "text-text-secondary" : "text-text-muted"}`}>
                    Make it an <span className="font-semibold">obligation</span> — you must buy him at
                    that price when the loan ends, not merely may.
                    {!optionToBuy && " Set a price first."}
                  </span>
                </label>
                {obligation && (
                  <div className="mt-2.5 pl-6">
                    <label className="mb-1.5 block text-[13px] font-semibold text-text-secondary">
                      Conditions <span className="font-normal text-text-muted">(optional)</span>
                    </label>
                    <textarea
                      value={conditions}
                      onChange={(e) => setConditions(e.target.value)}
                      rows={2}
                      maxLength={1000}
                      placeholder="e.g. If we are promoted, or he plays 20 league games"
                      className="w-full resize-none rounded-lg bg-surface px-3 py-2.5 text-sm text-text placeholder-text-muted ring-1 ring-input-border focus:outline-none focus:ring-accent transition-colors"
                    />
                    <p className="mt-1 text-[13px] text-text-muted">
                      The platform cannot check these. At the end of the loan the purchase starts
                      either way, and either club can collapse it if they were not met.
                    </p>
                  </div>
                )}
              </div>

              <label className="flex items-start gap-2.5">
                <input
                  type="checkbox"
                  checked={recallAllowed}
                  onChange={(e) => setRecallAllowed(e.target.checked)}
                  className="mt-0.5 h-4 w-4 shrink-0 rounded accent-accent"
                />
                <span className="text-[13px] text-text-secondary">
                  His club may <span className="font-semibold">recall him early</span>. Without this the
                  loan runs to its end date whatever happens.
                </span>
              </label>
            </>
          ) : (
            /* Transfer fee — required. "No fee — a free transfer or a swap"
               described neither: an out-of-contract player is signed from his
               page, not offered for, and a swap cannot be recorded here. */
            <div>
              <label className="mb-1.5 block text-sm font-semibold text-text-secondary">
                Transfer fee
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
              {parsedFeeValue === 0 && (
                <div className="mt-2.5">
                  <label className="mb-1.5 block text-sm font-semibold text-text-secondary">
                    Why £0?
                  </label>
                  <textarea
                    value={noFeeReason}
                    onChange={(e) => setNoFeeReason(e.target.value)}
                    rows={2}
                    maxLength={500}
                    placeholder="e.g. We take on his full wage so you can clear it from your books"
                    className="w-full resize-none rounded-lg bg-surface px-3 py-2.5 text-sm text-text placeholder-text-muted ring-1 ring-input-border focus:outline-none focus:ring-accent transition-colors"
                  />
                  <p className="mt-1 text-[13px] text-text-muted">
                    Sent to his club with the offer. Out of contract? Sign him from his page instead.
                  </p>
                </div>
              )}
            </div>
          )}

          {dealType === "PERMANENT" && (<>
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
          </>)}

          {/* Approach anonymously. Deliberately spells out when the reveal
              happens — a buyer choosing this needs to know it isn't permanent,
              and a buyer who assumed it was would be badly surprised. */}
          <div className="rounded-lg bg-surface-inset px-4 py-3 ring-1 ring-border">
            <label className="flex cursor-pointer items-start gap-3">
              <input
                type="checkbox"
                checked={anonymous}
                onChange={(e) => setAnonymous(e.target.checked)}
                className="mt-0.5 h-4 w-4 shrink-0 cursor-pointer accent-accent"
              />
              <span>
                <span className="block text-sm font-semibold text-text-secondary">
                  Approach anonymously
                </span>
                <span className="mt-0.5 block text-xs text-text-muted">
                  {player?.current_club?.name ?? "The selling club"} sees only your league until
                  they accept — accepting reveals you. If they reject or it expires, you're never
                  named.
                </span>
              </span>
            </label>
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
