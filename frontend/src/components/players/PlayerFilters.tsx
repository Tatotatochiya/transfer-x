import { useState } from "react";
import type { PlayerPosition, PlayerStatus } from "../../types/enums";

export type ViewMode = "grid" | "list";

export interface PlayerFilterState {
  search: string;
  position: PlayerPosition | "";
  status: PlayerStatus | "";
  open_to_offers: boolean;
  /** Only players a club could actually sign here — on a TransferX club, or
   *  free agents. Most of the catalogue plays for clubs outside the platform. */
  buyable: boolean;
  min_age: string;
  max_age: string;
  nationality: string;
  club_search: string;
  // Stats filters
  min_goals: string;
  min_assists: string;
  min_appearances: string;
  min_avg_rating: string;
  min_form_score: string;
  // What he would cost here, in £ millions: asking price, else the fee model
  min_price: string;
  max_price: string;
  // Enrichment filters (the outside market value, € millions)
  min_value: string;
  max_value: string;
  contract_expiry_months: string;
  sort_by: "name" | "age" | "goals" | "assists" | "appearances" | "avg_rating" | "form_score" | "value" | "price";
  sort_dir: "asc" | "desc";
}

export const DEFAULT_PLAYER_FILTERS: PlayerFilterState = {
  search: "",
  position: "",
  status: "",
  open_to_offers: false,
  buyable: true,
  min_age: "",
  max_age: "",
  nationality: "",
  club_search: "",
  min_goals: "",
  min_assists: "",
  min_appearances: "",
  min_avg_rating: "",
  min_form_score: "",
  min_price: "",
  max_price: "",
  min_value: "",
  max_value: "",
  contract_expiry_months: "",
  sort_by: "name",
  sort_dir: "asc",
};

const POSITIONS: PlayerPosition[] = ["GK", "DEF", "MID", "FWD"];

// The sheet below 1024px grows every control to a 44–48px touch target, in
// 16px text so iOS doesn't zoom into a focused field.
const FIELD = {
  rail: "flex min-w-0 flex-1 items-center justify-between gap-2 rounded-lg bg-surface px-[11px] py-[9px] text-small ring-1 ring-input-border focus-within:ring-accent transition-colors",
  sheet: "flex min-h-12 min-w-0 flex-1 items-center justify-between gap-2 rounded-lg bg-surface px-3 text-body ring-1 ring-input-border focus-within:ring-accent transition-colors",
};
const inputCls = "w-full bg-transparent text-text placeholder-text-muted focus:outline-none";
const numInputCls = `${inputCls} [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none`;

/** The club-name filter: its own field after the filters in the rail and the sheet. */
export function ClubSearchField({ filters, onChange, layout = "rail" }: {
  filters: PlayerFilterState;
  onChange: (f: PlayerFilterState) => void;
  layout?: "rail" | "sheet";
}) {
  // Kept visible, not buried in "More filters": searching for a club by name
  // is common enough that hiding it caused real players to look missing.
  return (
    <div className={FIELD[layout]}>
      <input
        type="text"
        placeholder="Club…"
        aria-label="Club"
        value={filters.club_search}
        onChange={(e) => onChange({ ...filters, club_search: e.target.value })}
        className={inputCls}
      />
    </div>
  );
}

function countActiveFilters(f: PlayerFilterState): number {
  let n = 0;
  if (f.status) n++;
  if (f.open_to_offers) n++;
  if (f.nationality) n++;
  if (f.min_goals) n++;
  if (f.min_assists) n++;
  if (f.min_appearances) n++;
  if (f.min_avg_rating) n++;
  return n;
}

interface Props {
  filters: PlayerFilterState;
  onChange: (f: PlayerFilterState) => void;
  /** Without these there's no view toggle (the toolbar has it below 1024px). */
  view?: ViewMode;
  onViewChange?: (v: ViewMode) => void;
  layout?: "rail" | "sheet";
}

// ── Filter rail: the primary fields as boxed rows, plus a collapsible section
// for the rest. The name search and the club field live outside it
// (MarketSearch, ClubSearchField). ────

export default function PlayerFilters({ filters, onChange, view, onViewChange, layout = "rail" }: Props) {
  const [moreOpen, setMoreOpen] = useState(false);
  const fieldCls = FIELD[layout];
  const sheet = layout === "sheet";

  function set<K extends keyof PlayerFilterState>(key: K, value: PlayerFilterState[K]) {
    onChange({ ...filters, [key]: value });
  }

  const moreCount = countActiveFilters(filters);

  return (
    <div className="space-y-3">
      {/* Buyable — kept visible: whether a player can be signed here at all is
          the first thing a buying club needs to know, and most of the market
          plays for clubs that are not on TransferX. */}
      <label className={`flex min-h-11 cursor-pointer items-center justify-between gap-3 ${sheet ? "" : "lg:min-h-0"}`}>
        <span className="text-small text-text-secondary">
          Buyable on TransferX only
          <span className="block text-caption text-text-muted">
            Clubs on TransferX, and free agents
          </span>
        </span>
        <button
          type="button"
          role="switch"
          aria-checked={filters.buyable}
          aria-label="Buyable on TransferX only"
          onClick={() => set("buyable", !filters.buyable)}
          className={`relative h-4 w-8 shrink-0 rounded-full transition-colors ${filters.buyable ? "bg-accent" : "bg-border"}`}
        >
          <span className={`absolute top-0.5 left-0.5 h-3 w-3 rounded-full bg-white shadow transition-transform ${filters.buyable ? "translate-x-4" : ""}`} />
        </button>
      </label>

      {/* Position */}
      <div>
        <p className="mb-1.5 text-caption font-semibold text-text-secondary">Position</p>
        <div className="flex gap-1.5">
          {POSITIONS.map((pos) => {
            const active = filters.position === pos;
            return (
              <button
                key={pos}
                type="button"
                aria-pressed={active}
                onClick={() => set("position", active ? "" : pos)}
                className={`flex-1 rounded-lg px-2 font-bold ring-1 transition-colors ${sheet ? "min-h-11 text-body" : "py-1.5 text-caption"} ${
                  active ? "bg-accent-bg text-accent-active ring-accent" : "bg-surface text-text-muted ring-input-border hover:ring-accent"
                }`}
              >
                {pos}
              </button>
            );
          })}
        </div>
      </div>

      {/* What he would cost here: the asking price, else the fee model (the Cheapest sort's rule). */}
      <div>
        <p className="mb-1.5 text-caption font-semibold text-text-secondary">Price (£ millions)</p>
        <div className="flex items-center gap-1.5">
          <div className={fieldCls}><input type="number" min={0} placeholder="Min" aria-label="Minimum price, £ millions" value={filters.min_price} onChange={(e) => set("min_price", e.target.value)} className={numInputCls} /></div>
          <span className="text-text-muted text-caption shrink-0">–</span>
          <div className={fieldCls}><input type="number" min={0} placeholder="Max" aria-label="Maximum price, £ millions" value={filters.max_price} onChange={(e) => set("max_price", e.target.value)} className={numInputCls} /></div>
        </div>
      </div>

      {/* The outside market estimate, stored in euros; not the asking price. */}
      <div>
        <p className="mb-1.5 text-caption font-semibold text-text-secondary">Market value (€ millions)</p>
        <div className="flex items-center gap-1.5">
          <div className={fieldCls}><input type="number" min={0} placeholder="Min" aria-label="Minimum market value, € millions" value={filters.min_value} onChange={(e) => set("min_value", e.target.value)} className={numInputCls} /></div>
          <span className="text-text-muted text-caption shrink-0">–</span>
          <div className={fieldCls}><input type="number" min={0} placeholder="Max" aria-label="Maximum market value, € millions" value={filters.max_value} onChange={(e) => set("max_value", e.target.value)} className={numInputCls} /></div>
        </div>
      </div>

      {/* Age */}
      <div>
        <p className="mb-1.5 text-caption font-semibold text-text-secondary">Age</p>
        <div className="flex items-center gap-1.5">
          <div className={fieldCls}><input type="number" min={14} max={50} placeholder="Min age" value={filters.min_age} onChange={(e) => set("min_age", e.target.value)} className={numInputCls} /></div>
          <span className="text-text-muted text-caption shrink-0">–</span>
          <div className={fieldCls}><input type="number" min={14} max={50} placeholder="Max age" value={filters.max_age} onChange={(e) => set("max_age", e.target.value)} className={numInputCls} /></div>
        </div>
      </div>

      {/* Contract ends within */}
      <div>
        <p className="mb-1.5 text-caption font-semibold text-text-secondary">Contract ends within</p>
        <div className={fieldCls}>
          <input type="number" min={1} max={36} placeholder="Any" value={filters.contract_expiry_months} onChange={(e) => set("contract_expiry_months", e.target.value)} className={numInputCls} />
          <span className="shrink-0 text-caption text-text-muted">months</span>
        </div>
      </div>

      {/* Form score */}
      <div>
        <p className="mb-1.5 text-caption font-semibold text-text-secondary">Form score</p>
        <div className={fieldCls}>
          <input type="number" min={0} max={100} placeholder="Min" value={filters.min_form_score} onChange={(e) => set("min_form_score", e.target.value)} className={numInputCls} />
          <span className="shrink-0 text-caption text-text-muted">and above</span>
        </div>
      </div>

      {/* More filters toggle */}
      <button
        type="button"
        aria-expanded={moreOpen}
        onClick={() => setMoreOpen((o) => !o)}
        className={`flex w-full items-center justify-between font-semibold text-text-muted hover:text-text transition-colors ${sheet ? "min-h-11 text-body" : "text-caption"}`}
      >
        <span>More filters{moreCount > 0 ? ` (${moreCount})` : ""}</span>
        <svg className={`h-3.5 w-3.5 transition-transform ${moreOpen ? "rotate-180" : ""}`} fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {moreOpen && (
        <div className="space-y-3 border-t border-rule pt-3">
          <div className={fieldCls}>
            <select value={filters.status} onChange={(e) => set("status", e.target.value as PlayerStatus | "")} className={inputCls}>
              <option value="">Any status</option>
              <option value="CONTRACTED">Contracted (on TransferX)</option>
              <option value="EXTERNAL">Contracted (external club)</option>
              <option value="FREE_AGENT">Free Agent</option>
            </select>
          </div>
          <label className={`flex items-center justify-between rounded-lg bg-surface ring-1 ring-input-border cursor-pointer ${sheet ? "min-h-12 px-3" : "px-[11px] py-[9px]"}`}>
            <span className="text-small text-text-secondary">Listed only</span>
            <div
              onClick={(e) => { e.preventDefault(); set("open_to_offers", !filters.open_to_offers); }}
              className={`relative h-4 w-8 shrink-0 rounded-full transition-colors ${filters.open_to_offers ? "bg-accent" : "bg-border"}`}
            >
              <span className={`absolute top-0.5 left-0.5 h-3 w-3 rounded-full bg-white shadow transition-transform ${filters.open_to_offers ? "translate-x-4" : ""}`} />
            </div>
          </label>
          <div className={fieldCls}><input type="text" placeholder="Nationality…" value={filters.nationality} onChange={(e) => set("nationality", e.target.value)} className={inputCls} /></div>
          <div className="grid grid-cols-2 gap-1.5">
            <div className={fieldCls}><input type="number" min={0} placeholder="Goals ≥" value={filters.min_goals} onChange={(e) => set("min_goals", e.target.value)} className={numInputCls} /></div>
            <div className={fieldCls}><input type="number" min={0} placeholder="Assists ≥" value={filters.min_assists} onChange={(e) => set("min_assists", e.target.value)} className={numInputCls} /></div>
            <div className={fieldCls}><input type="number" min={0} placeholder="Apps ≥" value={filters.min_appearances} onChange={(e) => set("min_appearances", e.target.value)} className={numInputCls} /></div>
            <div className={fieldCls}><input type="number" min={0} max={10} step={0.1} placeholder="Rating ≥" value={filters.min_avg_rating} onChange={(e) => set("min_avg_rating", e.target.value)} className={numInputCls} /></div>
          </div>
        </div>
      )}

      {/* The sheet has its own "Clear all" in the header. */}
      {!sheet && (moreCount > 0 || filters.position || filters.club_search || filters.min_age || filters.max_age || filters.min_price || filters.max_price || filters.min_value || filters.max_value || filters.contract_expiry_months || filters.min_form_score) && (
        <button
          type="button"
          onClick={() => onChange({ ...DEFAULT_PLAYER_FILTERS, search: filters.search, sort_by: filters.sort_by, sort_dir: filters.sort_dir })}
          className="text-caption text-text-muted hover:text-text-secondary transition-colors"
        >
          Clear all filters
        </button>
      )}

      {view && onViewChange && <ViewToggle view={view} onViewChange={onViewChange} />}
    </div>
  );
}

/** Grid or list, as two pressed-state buttons (the rail's view switch). */
export function ViewToggle({ view, onViewChange }: { view: ViewMode; onViewChange: (v: ViewMode) => void }) {
  return (
    <div className="flex rounded-lg ring-1 ring-input-border overflow-hidden w-fit">
      <button
        type="button"
        onClick={() => onViewChange("grid")}
        title="Grid view"
        aria-label="Grid view"
        aria-pressed={view === "grid"}
        className={`px-2.5 py-1.5 transition-colors ${view === "grid" ? "bg-accent-bg text-accent-active" : "bg-surface text-text-muted hover:text-text"}`}
      >
        <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M4 5h4v4H4zM10 5h4v4h-4zM16 5h4v4h-4zM4 11h4v4H4zM10 11h4v4h-4zM16 11h4v4h-4zM4 17h4v4H4zM10 17h4v4h-4zM16 17h4v4h-4z" /></svg>
      </button>
      <button
        type="button"
        onClick={() => onViewChange("list")}
        title="List view"
        aria-label="List view"
        aria-pressed={view === "list"}
        className={`px-2.5 py-1.5 transition-colors ${view === "list" ? "bg-accent-bg text-accent-active" : "bg-surface text-text-muted hover:text-text"}`}
      >
        <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 10h16M4 14h16M4 18h16" /></svg>
      </button>
    </div>
  );
}
