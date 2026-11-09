import type { Club } from "../../types/api";
import { formatCompact } from "../../lib/utils";

/** "£232.5M to spend · £49.9M a week in wages": the club's own room, from /clubs/me. */
export function BudgetLine({ club, className = "" }: { club?: Club | null; className?: string }) {
  const f = club?.finance;
  if (!f) return null;
  return (
    <p className={`text-sm text-text-secondary ${className}`}>
      <span className="font-semibold text-text">{formatCompact(Number(f.transfer_remaining))}</span> to spend
      {" · "}
      <span className="font-semibold text-text">{formatCompact(Number(f.wage_remaining_weekly))}</span> a week in wages
    </p>
  );
}

/**
 * The page's title row (browse-players-focus §5.10): "Browse players" and the
 * result count, with the budget on the right. Below 640px the page passes no
 * club and shows the budget under the filter chips instead.
 */
export default function MarketHeader({ total, club, subtitle }: {
  total?: number;
  /** A club's own finance; absent for anyone else. */
  club?: Club | null;
  subtitle?: string;
}) {
  return (
    <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
      <div className="flex min-w-0 items-baseline gap-3">
        <h1 className="text-[22px] font-bold tracking-[-0.01em] text-text lg:text-2xl">Browse players</h1>
        {total != null && (
          <span className="shrink-0 text-sm text-text-muted" aria-live="polite">
            {total.toLocaleString("en-GB")} player{total === 1 ? "" : "s"}
          </span>
        )}
      </div>
      <BudgetLine club={club} />
      {subtitle && <p className="w-full text-sm text-text-muted">{subtitle}</p>}
    </div>
  );
}
