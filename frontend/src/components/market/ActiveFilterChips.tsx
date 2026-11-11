import { DEFAULT_PLAYER_FILTERS, type PlayerFilterState } from "../players/PlayerFilters";

export interface ActiveFilterChip {
  key: string;
  label: string;
  /** The filters with this one removed. */
  remove: (f: PlayerFilterState) => PlayerFilterState;
}

const STATUS_LABEL: Record<string, string> = {
  CONTRACTED: "On TransferX clubs",
  EXTERNAL: "At clubs outside TransferX",
  FREE_AGENT: "Free agents",
};

const reset = (...keys: (keyof PlayerFilterState)[]) => (f: PlayerFilterState): PlayerFilterState => {
  const next = { ...f };
  for (const k of keys) (next as Record<string, unknown>)[k] = DEFAULT_PLAYER_FILTERS[k];
  return next;
};

/**
 * A chip for every filter that differs from the defaults, plus "On TransferX"
 * (on by default, but it changes the results more than any other). The name
 * search and the sort never make a chip: the search box and the Sort menu
 * already show them.
 */
export function activeFilterChips(f: PlayerFilterState): ActiveFilterChip[] {
  const chips: ActiveFilterChip[] = [];
  // "On TransferX" is the default, so removing it turns it off rather than
  // resetting it.
  if (f.buyable) chips.push({ key: "buyable", label: "On TransferX", remove: (x) => ({ ...x, buyable: false }) });
  if (f.position) chips.push({ key: "position", label: f.position, remove: reset("position") });
  if (f.status) chips.push({ key: "status", label: STATUS_LABEL[f.status] ?? f.status, remove: reset("status") });
  if (f.min_age || f.max_age) {
    const label = f.min_age && f.max_age ? `Age ${f.min_age}–${f.max_age}`
      : f.max_age ? `Under ${Number(f.max_age) + 1}`
      : `${f.min_age} and over`;
    chips.push({ key: "age", label, remove: reset("min_age", "max_age") });
  }
  if (f.min_price || f.max_price) {
    const label = f.min_price && f.max_price ? `£${f.min_price}–${f.max_price}M price`
      : f.min_price ? `£${f.min_price}M+ price`
      : `Up to £${f.max_price}M price`;
    chips.push({ key: "price", label, remove: reset("min_price", "max_price") });
  }
  if (f.min_value || f.max_value) {
    const label = f.min_value && f.max_value ? `€${f.min_value}–${f.max_value}M market value`
      : f.min_value ? `€${f.min_value}M+ market value`
      : `Up to €${f.max_value}M market value`;
    chips.push({ key: "value", label, remove: reset("min_value", "max_value") });
  }
  if (f.contract_expiry_months) {
    chips.push({ key: "contract", label: `Contract ends within ${f.contract_expiry_months} months`, remove: reset("contract_expiry_months") });
  }
  if (f.min_form_score) chips.push({ key: "form", label: `Form ${f.min_form_score}+`, remove: reset("min_form_score") });
  if (f.open_to_offers) chips.push({ key: "listed", label: "Listed", remove: reset("open_to_offers") });
  if (f.nationality) chips.push({ key: "nationality", label: f.nationality, remove: reset("nationality") });
  if (f.club_search) chips.push({ key: "club", label: `Club: ${f.club_search}`, remove: reset("club_search") });
  if (f.min_goals) chips.push({ key: "goals", label: `Goals ${f.min_goals}+`, remove: reset("min_goals") });
  if (f.min_assists) chips.push({ key: "assists", label: `Assists ${f.min_assists}+`, remove: reset("min_assists") });
  if (f.min_appearances) chips.push({ key: "apps", label: `Apps ${f.min_appearances}+`, remove: reset("min_appearances") });
  if (f.min_avg_rating) chips.push({ key: "rating", label: `Rating ${Number(f.min_avg_rating).toFixed(1)}+`, remove: reset("min_avg_rating") });
  return chips;
}

/** Every filter back to its default, keeping the name search and the sort. */
export function clearFilters(f: PlayerFilterState): PlayerFilterState {
  return { ...DEFAULT_PLAYER_FILTERS, search: f.search, sort_by: f.sort_by, sort_dir: f.sort_dir };
}

/** How many filters are on, for the Filters (n) badge. */
export function activeFilterCount(f: PlayerFilterState): number {
  return activeFilterChips(f).length;
}

/**
 * The active filters as removable chips (browse-players-focus §5.5): one
 * sideways-scrolling row below 1024px, wrapping from 1024px.
 */
export default function ActiveFilterChips({ filters, onChange, trailing }: {
  filters: PlayerFilterState;
  onChange: (f: PlayerFilterState) => void;
  /** Shown at the end of the row (the recommendations link on laptops). */
  trailing?: React.ReactNode;
}) {
  const chips = activeFilterChips(filters);
  const cleared = clearFilters(filters);
  const canClear = JSON.stringify(cleared) !== JSON.stringify(filters);
  if (chips.length === 0 && !trailing) return null;
  return (
    <div className="-mx-4 flex items-center gap-2 overflow-x-auto px-4 [scrollbar-width:none] md:-mx-6 md:px-6 lg:mx-0 lg:flex-wrap lg:overflow-visible lg:px-0">
      {chips.map((c) => (
        <button
          key={c.key}
          type="button"
          aria-label={`Remove filter ${c.label}`}
          onClick={() => onChange(c.remove(filters))}
          className="inline-flex h-9 shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full bg-accent-bg pl-3 pr-2.5 text-body font-semibold text-accent-active hover:ring-1 hover:ring-accent"
        >
          {c.label}
          <span aria-hidden className="text-body leading-none">×</span>
        </button>
      ))}
      {canClear && (
        <button
          type="button"
          onClick={() => onChange(cleared)}
          className="inline-flex h-9 shrink-0 items-center px-2 text-body font-semibold text-text-secondary hover:text-text"
        >
          Clear
        </button>
      )}
      {trailing && <div className="ml-auto shrink-0">{trailing}</div>}
    </div>
  );
}
