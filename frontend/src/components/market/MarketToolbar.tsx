import type { ReactNode } from "react";
import type { PlayerFilterState, ViewMode } from "../players/PlayerFilters";
import MoreMenu from "../transfer/MoreMenu";

type SortBy = PlayerFilterState["sort_by"];
type SortDir = PlayerFilterState["sort_dir"];

/** Every option sorts the whole result set on the server (D6). */
export const SORT_OPTIONS: { label: string; short?: string; sort_by: SortBy; sort_dir: SortDir }[] = [
  { label: "Name (A–Z)", short: "Name", sort_by: "name", sort_dir: "asc" },
  { label: "Best value", sort_by: "value", sort_dir: "desc" },
  { label: "Form", sort_by: "form_score", sort_dir: "desc" },
  { label: "Cheapest", sort_by: "price", sort_dir: "asc" },
  { label: "Youngest", sort_by: "age", sort_dir: "asc" },
];

/** The active sort's label, from the filters (so a saved view's sort shows). */
export function sortLabel(f: Pick<PlayerFilterState, "sort_by" | "sort_dir">, short = false): string {
  const o = SORT_OPTIONS.find((x) => x.sort_by === f.sort_by && x.sort_dir === f.sort_dir);
  return (o && (short ? o.short ?? o.label : o.label))
    // A sort only an older saved view can hold (goals, rating…).
    ?? `${f.sort_by.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase())}`;
}

const BUTTON = "inline-flex min-h-11 items-center justify-center gap-1.5 rounded-lg bg-surface px-3 text-body font-semibold text-text ring-1 ring-inset ring-input-border hover:ring-accent lg:min-h-11";

export function SortMenu({ filters, onSort, className = "" }: {
  filters: PlayerFilterState;
  onSort: (sort_by: SortBy, sort_dir: SortDir) => void;
  className?: string;
}) {
  return (
    <div className={className}>
      <MoreMenu
        label={<><span className="truncate">Sort: {sortLabel(filters, true)}</span><span aria-hidden className="text-text-muted">⌄</span></>}
        menuLabel="Sort players"
        triggerClassName={`${BUTTON} w-full`}
        align="right"
        items={SORT_OPTIONS.map((o) => ({
          label: o.label,
          checked: o.sort_by === filters.sort_by && o.sort_dir === filters.sort_dir,
          onSelect: () => onSort(o.sort_by, o.sort_dir),
        }))}
      />
    </div>
  );
}

/**
 * Filters (n) · Sort · view, pinned under the top bar while the results
 * scroll (browse-players-focus §5.5). Below 1024px only: from 1024px the
 * rail has the filters and the view switch, and Sort sits by the search box.
 * From 640px the search box joins the bar.
 */
export default function MarketToolbar({ filters, onSort, activeCount, view, onViewChange, onOpenFilters, search }: {
  filters: PlayerFilterState;
  onSort: (sort_by: SortBy, sort_dir: SortDir) => void;
  activeCount: number;
  view: ViewMode;
  onViewChange: (v: ViewMode) => void;
  onOpenFilters: () => void;
  /** The search box, shown in the bar from 640px. */
  search?: ReactNode;
}) {
  const next: ViewMode = view === "grid" ? "list" : "grid";
  return (
    <div className="sticky top-14 z-20 -mx-4 bg-page px-4 pb-2 pt-2.5 md:-mx-6 md:px-6">
      <div className="flex items-center gap-2">
        {search && <div className="hidden min-w-0 flex-[2] sm:block">{search}</div>}
        <button type="button" onClick={onOpenFilters} className={`${BUTTON} flex-1 sm:flex-none sm:px-4`} aria-haspopup="dialog">
          <svg aria-hidden className="h-[18px] w-[18px] text-text-secondary" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <path strokeLinecap="round" d="M4 6h16M7 12h10M10 18h4" />
          </svg>
          Filters
          {activeCount > 0 && (
            <span className="ml-0.5 inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-accent px-1.5 text-caption font-bold text-on-accent">
              {activeCount}
              <span className="sr-only"> active</span>
            </span>
          )}
        </button>
        <SortMenu filters={filters} onSort={onSort} className="min-w-0 flex-1 sm:flex-none" />
        <button
          type="button"
          aria-label={`Switch to ${next} view`}
          onClick={() => onViewChange(next)}
          className={`${BUTTON} w-11 shrink-0 px-0`}
        >
          {next === "grid" ? (
            <svg aria-hidden className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M4 5h6v6H4zM14 5h6v6h-6zM4 15h6v6H4zM14 15h6v6h-6z" /></svg>
          ) : (
            <svg aria-hidden className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"><path strokeLinecap="round" d="M4 6h16M4 12h16M4 18h16" /></svg>
          )}
        </button>
      </div>
    </div>
  );
}
