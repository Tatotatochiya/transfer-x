import { useState, type ReactNode } from "react";
import type { Offer, SuggestedTerms } from "../../types/api";
import { Estimate } from "../ui/Money";
import { NegotiationSummaryPanel, OfferAdvisor } from "../ai/Assistant";
import { useAIStatus } from "../../hooks/useAssistant";
import { lastChange } from "../../lib/offerChanges";
import { isLoan, loanPeriod, offerHeadline, purchaseClause, wageSharePct } from "../../lib/offerTerms";
import { formatCurrency, formatDate, formatDatePref, formatWage } from "../../lib/utils";

interface Row {
  label: string;
  value: ReactNode;
  /** lastChange's labels for this row, for its "Changed" note. */
  keys: string[];
  detail?: ReactNode;
}

function TermRow({ row, change, open, onToggle }: {
  row: Row;
  change: { was: string } | null;
  open: boolean;
  onToggle: () => void;
}) {
  const id = `offer-term-${row.label.toLowerCase().replace(/\W+/g, "-")}`;
  return (
    <div className="border-t border-rule py-3">
      <dt className="text-[15px] text-text-secondary">{row.label}</dt>
      <dd className="mt-0.5">
        <span className="text-base font-semibold text-text">{row.value}</span>
        {change && (
          <span className="block text-[13px] font-semibold text-accent-active">
            {change.was === "None" ? "New" : `Changed · was ${change.was}`}
          </span>
        )}
        {row.detail && (
          <>
            <button type="button" aria-expanded={open} aria-controls={id} onClick={onToggle}
              className="block min-h-11 text-sm font-semibold text-accent lg:min-h-8">
              {open ? "Hide" : "Show"}
            </button>
            {open && <div id={id}>{row.detail}</div>}
          </>
        )}
      </dd>
    </div>
  );
}

/**
 * Everything the offer proposes (offer-room-focus §5.9), restyled to match
 * the deal room's terms card. A loan shows as a loan. Rows the latest
 * counter or raise changed say what they were, whichever side changed them.
 */
export default function OfferTermsCard({ offer, heading }: { offer: Offer; heading: string }) {
  const [open, setOpen] = useState<Set<string>>(new Set());
  const toggle = (k: string) => setOpen((s) => { const n = new Set(s); if (n.has(k)) n.delete(k); else n.add(k); return n; });
  const changes = lastChange(offer)?.changes ?? [];
  const changeFor = (keys: string[]) => changes.find((c) => keys.includes(c.label)) ?? null;
  const rows: Row[] = [];

  if (!isLoan(offer)) {
    const instalments = offer.instalments ?? [];
    const clauses = offer.clauses ?? [];
    rows.push({ label: "Fee", keys: ["Transfer fee"], value: <>{offerHeadline(offer)}<Estimate value={offer.fee_amount} /></> });
    rows.push({
      label: "Payment", keys: ["Payment"],
      value: instalments.length === 0 ? "On completion" : `${instalments.length} instalments`,
      detail: instalments.length > 0 && (
        <ul className="text-sm text-text-secondary">
          {instalments.map((i, n) => (
            <li key={n} className="flex justify-between gap-3 py-0.5"><span>{formatDate(i.due_date)}</span><span>{formatCurrency(Number(i.amount))}</span></li>
          ))}
        </ul>
      ),
    });
    if (clauses.length > 0) {
      rows.push({
        label: "Add-ons", keys: ["Add-ons"], value: `${clauses.length} add-on${clauses.length === 1 ? "" : "s"}`,
        detail: (
          <ul className="text-sm text-text-secondary">
            {clauses.map((c, n) => (
              <li key={n} className="py-0.5">
                {c.trigger_description}: {formatCurrency(Number(c.amount))}{c.cap != null ? ` (cap ${formatCurrency(Number(c.cap))})` : ""}
              </li>
            ))}
          </ul>
        ),
      });
    }
    if (offer.sell_on_pct != null) rows.push({ label: "Sell-on", keys: ["Sell-on"], value: `${Math.round(Number(offer.sell_on_pct) * 1000) / 10}%` });
    if (offer.wage_weekly != null) rows.push({ label: "Wage", keys: ["Wage"], value: formatWage(Number(offer.wage_weekly)) });
    if (offer.contract_years != null) rows.push({ label: "Contract", keys: ["Contract"], value: `${offer.contract_years} years` });
    if (offer.contract_end_date != null) rows.push({ label: "Ends", keys: ["Ends"], value: formatDate(offer.contract_end_date) });
  } else {
    const pct = wageSharePct(offer);
    const wage = offer.wage_weekly != null ? Number(offer.wage_weekly) : null;
    const clause = purchaseClause(offer);
    rows.push({ label: "Period", keys: ["Loan starts", "Loan ends"], value: loanPeriod(offer) });
    rows.push({ label: "Loan fee", keys: ["Loan fee"], value: offer.loan_fee != null && Number(offer.loan_fee) > 0 ? formatCurrency(Number(offer.loan_fee)) : "None" });
    rows.push({
      label: "Wage share", keys: ["Wage share"],
      value: wage != null ? `${pct}% — ${formatWage(Math.round(wage * pct / 100))} of ${formatWage(wage)}` : `${pct}% of his wage`,
    });
    rows.push({ label: "Purchase", keys: ["Purchase price", "Obligation to buy"], value: clause ?? "None — he returns at the end" });
    if (offer.obligation_to_buy && offer.obligation_conditions) rows.push({ label: "Conditional on", keys: [], value: offer.obligation_conditions });
    rows.push({ label: "Early recall", keys: ["Early recall"], value: offer.recall_allowed ? "His club may recall him" : "Not allowed" });
  }

  const clause = isLoan(offer) ? purchaseClause(offer) : null;
  return (
    <section aria-labelledby="offer-terms-heading" className="rounded-xl bg-surface p-4 ring-1 ring-border sm:p-5">
      <h3 id="offer-terms-heading" className="text-[17px] font-bold text-text">{heading}</h3>
      <dl className="mt-2 grid sm:grid-cols-2 sm:gap-x-8">
        {rows.map((r) => (
          <TermRow key={r.label} row={r} change={changeFor(r.keys)} open={open.has(r.label)} onToggle={() => toggle(r.label)} />
        ))}
      </dl>
      {isLoan(offer) && offer.obligation_to_buy && clause && (
        <p className="mt-3 rounded-lg bg-warning-bg px-3 py-2 text-sm text-warning-text ring-1 ring-warning-fill/25">
          Binding: when the loan ends he transfers permanently at {formatCurrency(Number(offer.option_to_buy))}
          {offer.obligation_conditions ? ", if the conditions above are met" : ""}.
        </p>
      )}
      <p className="mt-3 border-t border-rule pt-3 text-sm text-text-muted">
        Offer made {formatDate(offer.created_at)} · changed {formatDatePref(offer.last_action_at)}
      </p>
    </section>
  );
}

/**
 * "✦ Advice on this offer" (D8): the offer advisor and where the negotiation
 * stands, unchanged inside, behind one disclosure.
 */
export function OfferAdvice({ offer, canCounter, onUseTerms }: {
  offer: Offer;
  canCounter: boolean;
  onUseTerms: (terms: SuggestedTerms) => void;
}) {
  const { data: status } = useAIStatus();
  const [open, setOpen] = useState(false);
  if (!status?.available) return null;
  return (
    <div className="rounded-xl bg-surface ring-1 ring-border">
      <button
        type="button"
        aria-expanded={open}
        aria-controls="offer-advice"
        onClick={() => setOpen((v) => !v)}
        className="flex min-h-16 w-full items-center justify-between gap-3 px-4 text-left"
      >
        <span>
          <span className="block text-[15px] font-semibold text-text"><span className="text-role-agent-text" aria-hidden>✦</span> Advice on this offer</span>
          <span className="block text-sm text-text-muted">A suggested next move, and where the negotiation stands</span>
        </span>
        <span aria-hidden className={`text-text-muted transition-transform ${open ? "rotate-90" : ""}`}>›</span>
      </button>
      {open && (
        <div id="offer-advice" className="space-y-4 border-t border-rule p-4">
          <OfferAdvisor offer={offer} canCounter={canCounter} onUseTerms={onUseTerms} />
          <NegotiationSummaryPanel offer={offer} />
        </div>
      )}
    </div>
  );
}
