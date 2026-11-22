import { Link } from "react-router-dom";

import Money from "../ui/Money";
import { formatCompact } from "../../lib/utils";
import type { ClubFinance } from "../../types/api";

/** Remaining, then the committed part, on a neutral track; warning under 10% left. */
function Bar({ remaining, committed, total, label }: { remaining: number; committed: number; total: number; label: string }) {
  const pct = (v: number) => (total > 0 ? Math.max(0, Math.min(100, (v / total) * 100)) : 0);
  const low = total > 0 && remaining / total < 0.1;
  return (
    <div role="img" aria-label={`${label}: ${Math.round(pct(remaining))}% left`}
      className="mt-2 flex h-1.5 overflow-hidden rounded-full bg-surface-inset">
      <span data-testid={`${label}-remaining`} className={low ? "bg-warning-fill" : "bg-text"} style={{ width: `${pct(remaining)}%` }} />
      <span className="bg-text-muted" style={{ width: `${pct(committed)}%` }} />
    </div>
  );
}

function Figure({ label, value, of, bar, className = "" }: {
  label: string; value: number; of?: number; bar?: React.ReactNode; className?: string;
}) {
  return (
    <div className={`min-w-0 rounded-2xl bg-surface p-4 ring-1 ring-border xl:rounded-none xl:bg-transparent xl:p-0 xl:ring-0 ${className}`}>
      <p className="text-caption font-semibold text-text-secondary">{label}</p>
      <p className="text-headline font-bold tabular-nums text-text xl:text-title"><Money value={value} compact /></p>
      {of != null && <p className="text-small text-text-muted">of {formatCompact(of)}</p>}
      {bar}
    </div>
  );
}

/**
 * The club's money at a glance (feature_spec/club-dashboard §4.3): transfer
 * budget free, wage room a week, and what's held in open offers and deals.
 * Laptop: one card. Tablet: three tiles. Phone: the first two.
 */
export default function MoneyCard({ finance, committedNames = [] }: {
  finance: ClubFinance | null;
  /** Players the held money is for, from the board (up to 3 shown, laptop only). */
  committedNames?: string[];
}) {
  if (!finance) return null;
  const n = (v: number | string) => Number(v) || 0;
  const transferTotal = n(finance.transfer_budget_total);
  const transferFree = n(finance.transfer_remaining);
  const held = n(finance.transfer_reserved) + n(finance.transfer_committed);
  const wageTotal = n(finance.wage_budget_total_weekly);
  const wageFree = n(finance.wage_remaining_weekly);
  const wageHeld = n(finance.wage_reserved_weekly) + n(finance.wage_committed_weekly);

  return (
    <section aria-labelledby="money-heading"
      className="xl:rounded-2xl xl:bg-surface xl:p-5 xl:ring-1 xl:ring-border">
      <div className="mb-2 flex items-center justify-between xl:mb-3">
        <h2 id="money-heading" className="text-section font-bold text-text">Money</h2>
        <Link to="/club/finance" className="text-small font-semibold text-accent hover:underline">Finance →</Link>
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-2 xl:gap-5">
        <Figure label="Transfer budget free" value={transferFree} of={transferTotal}
          bar={<Bar label="Transfer budget" remaining={transferFree} committed={held} total={transferTotal} />} />
        <Figure label="Wage room a week" value={wageFree} of={wageTotal}
          bar={<Bar label="Wage room" remaining={wageFree} committed={wageHeld} total={wageTotal} />} />
        <Figure label="In open offers and deals" value={held} className="hidden sm:block xl:hidden" />
      </div>
      <div className="mt-4 hidden items-baseline justify-between gap-3 border-t border-rule pt-3 xl:flex">
        <span className="min-w-0">
          <span className="block text-small text-text-secondary">In open offers and deals</span>
          {committedNames.length > 0 && (
            <span className="block truncate text-small text-text-muted">{committedNames.slice(0, 3).join(", ")}</span>
          )}
        </span>
        <span className="shrink-0 text-body font-semibold tabular-nums text-text"><Money value={held} compact /></span>
      </div>
    </section>
  );
}
