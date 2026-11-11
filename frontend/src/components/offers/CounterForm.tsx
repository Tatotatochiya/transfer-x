import { useEffect, useMemo, useRef, useState } from "react";
import type { Offer, SuggestedTerms } from "../../types/api";
import type { LiteOfferCard } from "../../hooks/useLite";
import type { OfferActions } from "../../hooks/useOfferActions";
import Button from "../ui/Button";
import CurrencyInput from "../ui/CurrencyInput";
import Sheet from "../ui/Sheet";
import DealStructureFields, { structureBody, structureError, structureFromOffer, type StructureDraft } from "./DealStructureFields";
import { TermsWarnings } from "../ai/Assistant";
import { useOfferCheck } from "../../hooks/useAssistant";
import { useConfirm } from "../../context/ConfirmContext";
import { diffDraft } from "../../lib/offerChanges";
import { isLoan, offerHeadline, wageSharePct } from "../../lib/offerTerms";
import { formatCurrency, getApiError } from "../../lib/utils";

/** The value after it has stopped changing for `ms` — for the live terms check. */
function useDebounced<T>(value: T, ms = 400): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

/** "2 instalments · 10% sell-on · no add-ons". */
export function structureSummary(d: StructureDraft): string {
  const n = d.instalments.length;
  const a = d.clauses.length;
  return [
    n === 0 ? "On completion" : `${n} instalment${n === 1 ? "" : "s"}`,
    d.sellOn ? `${d.sellOn}% sell-on` : "no sell-on",
    a === 0 ? "no add-ons" : `${a} add-on${a === 1 ? "" : "s"}`,
  ].join(" · ");
}

export interface SuggestState {
  onClick: () => void;
  loading: boolean;
  /** The advice's summary, shown when it came back without terms. */
  summary?: string | null;
}

interface Props {
  offer: Offer;
  side: "buyer" | "seller";
  /** The other club as this viewer may name it (masked when anonymous). */
  other: string;
  /** "reply by 18:00 today", for the inline header. */
  replyBy?: string;
  /** Terms from the offer advisor; the counter is then audited as AI-assisted. */
  prefill?: SuggestedTerms | null;
  /** The fee from a push's "Ask for £21m" button: a starting point, not AI. */
  startFee?: string | null;
  card?: LiteOfferCard;
  /** My side's latest fee, from the rounds. */
  myLastFee?: number | null;
  layout: "sheet" | "inline";
  counter: OfferActions["counter"];
  /** Sent, or closed without sending. */
  onDone: (sent: boolean) => void;
  /** "✦ Suggest a counter"; omitted when the AI is unavailable. */
  suggest?: SuggestState;
  formId: string;
}

const LABEL = "mb-1 block text-[15px] font-semibold text-text lg:text-sm";
const INPUT = "w-full min-h-12 lg:min-h-10 rounded-lg bg-surface px-3 py-2 text-[15px] text-text placeholder-text-muted ring-1 ring-input-border focus:outline-none focus:ring-accent transition-colors lg:text-sm";
const BIG = "w-full min-h-14 lg:min-h-12 rounded-lg bg-surface px-3 py-2 text-[22px] font-bold text-text ring-2 ring-accent focus:outline-none lg:text-lg";

/**
 * Countering an offer (offer-room-focus §5.6). The submit logic — what it
 * sends, and its diffing against the current offer — is moved unchanged from
 * the page; only the layout is new. Below 1024px it is a Sheet with Send
 * pinned to the footer; from 1024px it replaces the status card's content.
 */
export default function CounterForm({
  offer, side, other, replyBy, prefill, startFee, card, myLastFee, layout, counter, onDone, suggest, formId,
}: Props) {
  const confirm = useConfirm();
  const loan = isLoan(offer);
  // Number(): money arrives Decimal-serialised ("90000.00"), which the input
  // would otherwise display with its trailing zeros.
  const pick = (suggested: number | undefined, current: number | string | null | undefined) =>
    suggested != null ? String(suggested) : current != null ? String(Number(current)) : "";
  const [fee, setFee] = useState(prefill ? pick(prefill.fee_amount, offer.fee_amount) : startFee ?? pick(undefined, offer.fee_amount));
  const [wage, setWage] = useState(pick(prefill?.wage_weekly, offer.wage_weekly));
  const [years, setYears] = useState(String(prefill?.contract_years ?? offer.contract_years ?? ""));
  const [structure, setStructure] = useState(() => {
    const base = structureFromOffer(offer);
    return prefill?.sell_on_pct != null ? { ...base, sellOn: String(Math.round(prefill.sell_on_pct * 100)) } : base;
  });
  // Loan terms — the counter negotiates the loan, never converts it into a
  // permanent offer (deal_type is fixed at offer time).
  const [loanFee, setLoanFee] = useState(pick(prefill?.loan_fee, offer.loan_fee));
  const [split, setSplit] = useState(
    prefill?.wage_split_pct != null ? String(Math.round(prefill.wage_split_pct * 100)) : String(wageSharePct(offer)),
  );
  const [loanStart, setLoanStart] = useState(offer.loan_start ?? "");
  const [loanEnd, setLoanEnd] = useState(offer.loan_end ?? "");
  const [option, setOption] = useState(pick(prefill?.option_to_buy, offer.option_to_buy));
  const [obligation, setObligation] = useState(offer.obligation_to_buy);
  const [conditions, setConditions] = useState(offer.obligation_conditions ?? "");
  const [recall, setRecall] = useState(offer.recall_allowed);
  const [error, setError] = useState<string | null>(null);
  const [structureOpen, setStructureOpen] = useState(false);

  // For the discard check: what the form opened with.
  const snapshot = JSON.stringify([fee, wage, years, structure, loanFee, split, loanStart, loanEnd, option, obligation, conditions, recall]);
  const opening = useRef(snapshot);
  const dirty = snapshot !== opening.current;

  // The draft's full terms in the offer's field names: read by the rule check
  // and the "What {Other} will see" panel.
  const draftTerms = useMemo(() => loan
    ? { deal_type: "LOAN", loan_fee: parseFloat(loanFee) || null, wage_split_pct: (parseFloat(split) || 0) / 100,
        loan_start: loanStart || null, loan_end: loanEnd || null, option_to_buy: parseFloat(option) || null,
        obligation_to_buy: obligation, obligation_conditions: conditions }
    : { deal_type: "PERMANENT", fee_amount: parseFloat(fee) || null, wage_weekly: parseFloat(wage) || null,
        contract_years: parseInt(years) || null, sell_on_pct: structureBody(structure).sell_on_pct,
        instalments: structureBody(structure).instalments, clauses: structureBody(structure).clauses },
  [loan, loanFee, split, loanStart, loanEnd, option, obligation, conditions, fee, wage, years, structure]);

  // Rule checks on the draft as it is edited (no AI model involved).
  // Debounced as a string: an object would be a new value every render.
  const draftJson = useDebounced(JSON.stringify(draftTerms));
  const checkBody = useMemo(() => ({ offer_id: offer.id, terms: JSON.parse(draftJson) }), [offer.id, draftJson]);
  const { data: check } = useOfferCheck(checkBody);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const body: Record<string, unknown> = {};

    if (loan) {
      // Only what changed, so the counter's audit entry names the terms that
      // actually moved rather than restating the whole loan.
      const parsedFee = parseFloat(loanFee);
      if (loanFee && !isNaN(parsedFee) && parsedFee !== Number(offer.loan_fee ?? NaN)) body.loan_fee = parsedFee;
      const parsedSplit = parseFloat(split);
      if (isNaN(parsedSplit) || parsedSplit < 0 || parsedSplit > 100) {
        setError("The wage share must be between 0 and 100%.");
        return;
      }
      if (parsedSplit !== wageSharePct(offer)) body.wage_split_pct = parsedSplit / 100;
      if (loanStart && loanStart !== offer.loan_start) body.loan_start = loanStart;
      if (loanEnd && loanEnd !== offer.loan_end) body.loan_end = loanEnd;
      const parsedOption = parseFloat(option);
      if (!option.trim() && offer.option_to_buy != null) {
        // An explicit null removes the option — and the server drops any
        // obligation and conditions with it, since an obligation needs a price.
        body.option_to_buy = null;
      } else if (option && !isNaN(parsedOption) && parsedOption !== Number(offer.option_to_buy ?? NaN)) {
        body.option_to_buy = parsedOption;
      }
      const keepsObligation = obligation && !!option.trim();
      if (keepsObligation !== offer.obligation_to_buy && body.option_to_buy !== null) {
        body.obligation_to_buy = keepsObligation;
      }
      // "" clears them; the server also drops them when the obligation goes.
      if (keepsObligation && conditions.trim() !== (offer.obligation_conditions ?? "")) {
        body.obligation_conditions = conditions.trim();
      }
      if (recall !== offer.recall_allowed) body.recall_allowed = recall;
    } else {
      const parsedFee = parseFloat(fee);
      if (fee && !isNaN(parsedFee)) body.fee_amount = parsedFee;
      // A loan's wage is his contract wage, not a term to counter.
      const parsedWage = parseFloat(wage);
      if (wage && !isNaN(parsedWage)) body.wage_weekly = parsedWage;
      const parsedYears = parseInt(years);
      if (years && !isNaN(parsedYears)) body.contract_years = parsedYears;

      // Structure: send only what moved. A schedule tied to the old fee has
      // to move with a new one, and the server refuses it otherwise.
      const newFee = fee && !isNaN(parsedFee) ? parsedFee : offer.fee_amount != null ? Number(offer.fee_amount) : null;
      const problem = structureError(structure, newFee);
      if (problem) {
        setError(problem);
        setStructureOpen(true);
        return;
      }
      const next = structureBody(structure);
      const prev = structureBody(structureFromOffer(offer));
      if (JSON.stringify(next.instalments) !== JSON.stringify(prev.instalments)) body.instalments = next.instalments;
      if (JSON.stringify(next.clauses) !== JSON.stringify(prev.clauses)) body.clauses = next.clauses;
      // null removes the sell-on (as distinct from leaving it out).
      if (next.sell_on_pct !== prev.sell_on_pct) body.sell_on_pct = next.sell_on_pct;
    }

    if (Object.keys(body).length === 0) {
      setError("Change at least one term to counter.");
      return;
    }
    if (prefill) body.ai_assisted = true;
    counter.mutate(body, {
      onSuccess: () => onDone(true),
      onError: (err: unknown) => setError(getApiError(err, "Failed to submit counter.")),
    });
  }

  async function close() {
    if (dirty && !(await confirm({ title: "Discard your counter?", message: "What you've changed here won't be sent.", confirmLabel: "Discard", variant: "danger" }))) return;
    onDone(false);
  }

  // ── One-tap amounts (permanent only): suggested, asking, valuation, my last
  const theirFee = offer.fee_amount != null ? Number(offer.fee_amount) : null;
  const valuation = side === "seller" ? card?.your_valuation ?? null : null;
  const asking = side === "seller" ? card?.your_asking_price ?? null : null;
  const amounts: { amount: number; label: string }[] = [];
  if (!loan) {
    for (const [amount, label] of [
      [card?.counter_suggestion ?? null, "Suggested"],
      [asking, "Your asking price"],
      [valuation, "Your valuation"],
      [myLastFee ?? null, side === "seller" ? "Your last ask" : "Your last offer"],
    ] as [number | null, string][]) {
      if (amount != null && !amounts.some((a) => a.amount === amount)) amounts.push({ amount, label });
    }
  }
  const feeNum = parseFloat(fee);

  // ── The footer's comparison ───────────────────────────────────────────────
  let comparison: string | null = null;
  if (!loan && !isNaN(feeNum) && theirFee != null) {
    const d = feeNum - theirFee;
    comparison = `${formatCurrency(feeNum)}: ${d === 0 ? "the same as their offer" : `${formatCurrency(Math.abs(d))} ${d > 0 ? "more" : "less"} than their offer`}`;
    if (valuation != null && feeNum !== valuation) {
      comparison += `, ${formatCurrency(Math.abs(valuation - feeNum))} ${feeNum < valuation ? "under" : "over"} your valuation`;
    } else if (valuation != null) {
      comparison += ", at your valuation";
    }
  }

  const inline = layout === "inline";
  const id = (k: string) => `${formId}-${k}`;

  const wageYears = (
    <div className={inline ? "contents" : "grid grid-cols-2 gap-3"}>
      <div>
        <label htmlFor={id("wage")} className={LABEL}>Wage a week</label>
        <CurrencyInput id={id("wage")} value={wage} onChange={setWage} placeholder="Weekly wage" className={INPUT} />
      </div>
      <div>
        <label htmlFor={id("years")} className={LABEL}>Contract years</label>
        <input id={id("years")} type="number" min="1" max="10" step="1" value={years} onChange={(e) => setYears(e.target.value)} placeholder="Years" className={INPUT} />
      </div>
    </div>
  );

  const permanentFields = (
    <>
      <div className={inline ? "grid grid-cols-[2fr_1fr_1fr] gap-3" : ""}>
        <div>
          <label htmlFor={id("fee")} className={LABEL}>{side === "seller" ? "Fee you'll accept" : "Fee you'll pay"}</label>
          <CurrencyInput id={id("fee")} data-autofocus value={fee} onChange={setFee} placeholder="Transfer fee" className={BIG} />
        </div>
        {inline && wageYears}
      </div>
      {amounts.length > 0 && (
        <div className={inline ? "mt-2 flex flex-wrap gap-2" : "mt-2 space-y-2"} role="group" aria-label="Amounts to use">
          {amounts.map((a) => {
            const on = feeNum === a.amount;
            return (
              <button
                key={a.label}
                type="button"
                aria-pressed={on}
                onClick={() => setFee(String(a.amount))}
                className={inline
                  ? `h-9 rounded-full px-3.5 text-sm ring-1 ${on ? "bg-accent-bg-strong font-semibold text-accent-active ring-accent" : "bg-surface text-text-secondary ring-input-border hover:ring-accent"}`
                  : `flex min-h-11 w-full items-center justify-between rounded-lg px-3.5 text-[15px] ring-1 ${on ? "bg-accent-bg-strong text-accent-active ring-accent" : "bg-surface text-text ring-input-border"}`}
              >
                {inline ? <><strong>{formatCurrency(a.amount)}</strong> · {a.label}</> : (
                  <><strong>{formatCurrency(a.amount)}</strong><span className="text-text-secondary">{a.label}</span></>
                )}
              </button>
            );
          })}
        </div>
      )}
      {!inline && <div className="mt-4">{wageYears}</div>}
      <div className="mt-4 rounded-lg ring-1 ring-border">
        <button
          type="button"
          aria-expanded={structureOpen}
          aria-controls={id("structure")}
          onClick={() => setStructureOpen((v) => !v)}
          className={`flex w-full items-center justify-between gap-3 px-4 text-left ${inline ? "min-h-[52px]" : "min-h-16"}`}
        >
          <span>
            <span className="block text-[15px] font-semibold text-text lg:text-sm">Payment, add-ons and sell-on</span>
            <span className="block text-sm text-text-muted">{structureSummary(structure)}</span>
          </span>
          <span aria-hidden className={`text-text-muted transition-transform ${structureOpen ? "rotate-90" : ""}`}>›</span>
        </button>
        {structureOpen && (
          <div id={id("structure")} className="border-t border-rule px-4 py-4">
            <DealStructureFields bare value={structure} onChange={setStructure} fee={isNaN(feeNum) ? null : feeNum} />
          </div>
        )}
      </div>
    </>
  );


  const checkRow = "flex min-h-11 items-start gap-2.5 lg:min-h-0";
  const loanFields = (
    <div className="space-y-4">
      <div>
        <label htmlFor={id("loan-fee")} className={LABEL}>Loan fee</label>
        <CurrencyInput id={id("loan-fee")} data-autofocus value={loanFee} onChange={setLoanFee} placeholder="0 for none" className={BIG} />
      </div>
      <div>
        <label htmlFor={id("split")} className={LABEL}>Borrowing club pays (% of wage)</label>
        <input id={id("split")} type="number" min={0} max={100} value={split} onChange={(e) => setSplit(e.target.value)} className={INPUT} />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label htmlFor={id("start")} className={LABEL}>Loan starts</label>
          <input id={id("start")} type="date" value={loanStart} onChange={(e) => setLoanStart(e.target.value)} className={INPUT} />
        </div>
        <div>
          <label htmlFor={id("end")} className={LABEL}>Loan ends</label>
          <input id={id("end")} type="date" value={loanEnd} onChange={(e) => setLoanEnd(e.target.value)} className={INPUT} />
        </div>
      </div>
      <div>
        <label htmlFor={id("option")} className={LABEL}>Purchase price</label>
        <CurrencyInput id={id("option")} value={option} onChange={setOption} placeholder="No option to buy — clear to remove" className={INPUT} />
      </div>
      <label className={checkRow}>
        <input type="checkbox" checked={obligation} disabled={!option} onChange={(e) => setObligation(e.target.checked)}
          className="mt-1 h-4 w-4 shrink-0 rounded accent-accent disabled:opacity-40" />
        <span className="text-[15px] text-text-secondary lg:text-sm">
          <span className="font-semibold">Obligation</span> — the purchase happens at that price when the
          loan ends, rather than being the borrowing club's option.
        </span>
      </label>
      {obligation && option.trim() && (
        <div className="pl-6">
          <label htmlFor={id("conditions")} className={LABEL}>Obligation conditions (optional)</label>
          <textarea id={id("conditions")} value={conditions} onChange={(e) => setConditions(e.target.value)} rows={2} maxLength={1000}
            placeholder="e.g. If promoted, or 20 league games" className={`${INPUT} resize-none`} />
        </div>
      )}
      <label className={checkRow}>
        <input type="checkbox" checked={recall} onChange={(e) => setRecall(e.target.checked)} className="mt-1 h-4 w-4 shrink-0 rounded accent-accent" />
        <span className="text-[15px] text-text-secondary lg:text-sm">His club may <span className="font-semibold">recall him early</span>.</span>
      </label>
    </div>
  );

  const suggestButton = suggest && (
    <div>
      <button
        type="button"
        onClick={suggest.onClick}
        disabled={suggest.loading}
        className="inline-flex min-h-11 items-center gap-2 rounded-lg px-3 text-[15px] font-semibold text-ai-text ring-1 ring-border hover:bg-surface-inset disabled:opacity-60 lg:min-h-9 lg:text-sm"
      >
        <span aria-hidden>✦</span> {suggest.loading ? "Thinking…" : "Suggest a counter"}
      </button>
      {suggest.summary && <p className="mt-1.5 text-sm text-text-muted">{suggest.summary}</p>}
    </div>
  );

  const notes = (
    <div className="mt-4 space-y-2">
      <TermsWarnings warnings={check?.warnings} />
      {prefill && (
        <p className="text-sm text-text-muted">
          <span className="text-ai-text">✦</span> Pre-filled from the advisor's suggestion — review before you send.
        </p>
      )}
      {error && <p role="alert" className="text-sm text-danger-text">{error}</p>}
    </div>
  );

  const form = (
    <form id={formId} onSubmit={handleSubmit} noValidate>
      {loan ? loanFields : permanentFields}
      {notes}
      {!inline && suggestButton && <div className="mt-4">{suggestButton}</div>}
    </form>
  );

  const send = (
    <Button type="submit" form={formId} variant="primary" size="lg" loading={counter.isPending} className={inline ? "" : "w-full"}>
      Send counter
    </Button>
  );

  if (!inline) {
    const sellOn = offer.sell_on_pct != null ? `${Math.round(Number(offer.sell_on_pct) * 1000) / 10}% sell-on` : null;
    const pay = loan ? null : (offer.instalments ?? []).length > 0 ? `${offer.instalments.length} instalments` : "on completion";
    return (
      <Sheet
        open
        onClose={close}
        title={`Counter ${other}`}
        subtitle={`Their offer: ${[offerHeadline(offer), pay, sellOn].filter(Boolean).join(" · ")}`}
        footer={
          <>
            {comparison && <p className="mb-2 text-sm text-text-secondary" aria-live="polite">{comparison}</p>}
            {send}
          </>
        }
      >
        {form}
      </Sheet>
    );
  }

  const changes = diffDraft(offer, draftTerms);
  return (
    <>
      <div className="flex items-baseline justify-between gap-4">
        <h2 id="offer-status-headline" tabIndex={-1} className="text-xl font-bold text-text focus:outline-none">Counter {other}</h2>
        {replyBy && <p className="text-sm text-text-muted">{replyBy}</p>}
      </div>
      <div className="mt-4 flex gap-8">
        <div className="min-w-0 flex-1">{form}</div>
        <div className="w-[330px] shrink-0 self-start rounded-xl bg-surface-inset p-4">
          <h3 className="text-sm font-semibold text-text">What {other} will see</h3>
          {changes.length === 0 ? (
            <p className="mt-2 text-sm text-text-muted">Change a term to see it here.</p>
          ) : (
            <>
              <ul className="mt-2">
                {changes.map((c) => (
                  <li key={c.label} className="flex justify-between gap-2.5 border-t border-rule py-2 text-sm first:border-t-0">
                    <span className="text-text-secondary">{c.label}</span>
                    <span className="text-right">
                      <s className="text-text-muted">{c.was}</s> <span aria-hidden>→</span>
                      <span className="sr-only">changed to</span> <strong className="text-text">{c.now}</strong>
                    </span>
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-sm text-text-muted">Everything else stays as they offered it.</p>
            </>
          )}
          {comparison && <p className="mt-3 border-t border-rule pt-3 text-sm text-text-secondary">{comparison}</p>}
        </div>
      </div>
      <div className="mt-4 flex items-center gap-3 border-t border-rule pt-3.5">
        {send}
        <Button type="button" variant="secondary" size="lg" onClick={close}>Cancel</Button>
        {suggestButton && <div className="ml-auto">{suggestButton}</div>}
      </div>
    </>
  );
}
