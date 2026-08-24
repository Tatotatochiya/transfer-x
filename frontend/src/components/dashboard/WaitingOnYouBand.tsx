import Card from "../ui/Card";
import { formatCurrency } from "../../lib/utils";
import { useDeadlineCountdown } from "../../hooks/useDeadlineCountdown";

export interface WaitingItem {
  key: string;
  title: string;
  description: string;
  amount: number | null;
  deadline: string | null;
  actionLabel: string;
  onClick: () => void;
}

function DeadlineValue({ deadline }: { deadline: string | null }) {
  const result = useDeadlineCountdown(deadline);
  if (!deadline) {
    // Every item in this band is already "your move" — no hard deadline is
    // still success-coloured, per SCREENS.md, never the neutral/muted case.
    return <span className="text-success-text">—</span>;
  }
  const urgent = result.state === "danger";
  return (
    <span className={`tabular-nums font-bold ${urgent ? "text-danger-text" : "text-text-secondary"}`}>
      {result.state === "expired" ? "Expired" : result.label}
    </span>
  );
}

/**
 * Tier-1 "waiting on you" band — same treatment on every club-facing screen
 * per docs/design_handoff_transferx/CLAUDE.md rule 2. Shared by the club and
 * agent dashboards; screens whose Tier-1 row shape differs (e.g. Offer inbox's
 * dual offer/valuation amounts) build their own row but should still open with
 * this same header-bar + empty-state chrome.
 */
export default function WaitingOnYouBand({
  items,
  heading = "Waiting on you",
  emptyText = "Nothing is waiting on you.",
}: {
  items: WaitingItem[];
  heading?: string;
  emptyText?: string;
}) {
  const sorted = [...items].sort((a, b) => {
    if (!a.deadline && !b.deadline) return 0;
    if (!a.deadline) return 1;
    if (!b.deadline) return -1;
    return new Date(a.deadline).getTime() - new Date(b.deadline).getTime();
  });
  const shown = sorted.slice(0, 5);

  if (shown.length === 0) {
    return <p className="mb-[18px] text-sm text-text-secondary">{emptyText}</p>;
  }

  return (
    <Card tier={1} noPadding className="mb-[18px]">
      <div className="flex items-center justify-between border-b border-danger-border bg-danger-bg px-4 py-3 rounded-t-xl sm:px-5">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-danger" />
          <span className="text-[13px] font-bold text-danger-heading">{heading} — {items.length}</span>
        </div>
        <span className="text-xs text-text-muted">Sorted by deadline</span>
      </div>
      <div>
        {shown.map((item) => (
          <div key={item.key} className="flex flex-wrap items-center gap-4 border-b border-rule px-4 py-4 last:border-b-0 sm:px-5 sm:py-3.5">
            <div className="flex-1 basis-full sm:basis-[300px]">
              <p className="text-[17px] font-bold text-text sm:text-[15px] sm:font-semibold">{item.title}</p>
              <p className="line-clamp-2 text-[13px] text-text-muted sm:line-clamp-none">{item.description}</p>
            </div>
            <div className="basis-[130px] shrink">
              <p className="text-[11px] text-text-muted">Amount</p>
              <p className="text-base font-bold text-text">{item.amount != null ? formatCurrency(item.amount) : "—"}</p>
            </div>
            <div className="basis-[130px] shrink">
              <p className="text-[11px] text-text-muted">Deadline</p>
              <DeadlineValue deadline={item.deadline} />
            </div>
            <button
              onClick={item.onClick}
              className="inline-flex w-full min-h-12 items-center justify-center whitespace-nowrap rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white hover:bg-accent-hover transition-colors sm:w-auto sm:min-h-0"
            >
              {item.actionLabel}
            </button>
          </div>
        ))}
      </div>
      {items.length > 5 && (
        <div className="border-t border-rule px-4 py-2.5 sm:px-5">
          <button className="text-xs font-semibold text-accent hover:text-accent-hover">
            View all {items.length} →
          </button>
        </div>
      )}
    </Card>
  );
}
