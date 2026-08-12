import { useState } from "react";
import type { PlayerPosition, PlayerStatus } from "../../types/enums";

export type ViewMode = "grid" | "list";

export interface PlayerFilterState {
  search: string;
  position: PlayerPosition | "";
  status: PlayerStatus | "";
  open_to_offers: boolean;
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
  // Enrichment filters
  min_value: string;
  max_value: string;
  contract_expiry_months: string;
  sort_by: "name" | "age" | "goals" | "assists" | "appearances" | "avg_rating" | "form_score";
  sort_dir: "asc" | "desc";
}

export const DEFAULT_PLAYER_FILTERS: PlayerFilterState = {
  search: "",
  position: "",
  status: "",
  open_to_offers: false,
  min_age: "",
  max_age: "",
  nationality: "",
  club_search: "",
  min_goals: "",
  min_assists: "",
  min_appearances: "",
  min_avg_rating: "",
  min_form_score: "",
  min_value: "",
  max_value: "",
  contract_expiry_months: "",
  sort_by: "name",
  sort_dir: "asc",
};

const POSITIONS: PlayerPosition[] = ["GK", "DEF", "MID", "FWD"];

const fieldCls = "flex items-center justify-between gap-2 rounded-lg bg-surface px-[11px] py-[9px] text-sm ring-1 ring-input-border focus-within:ring-accent transition-colors";
const inputCls = "w-full bg-transparent text-text placeholder-text-muted focus:outline-none";
const numInputCls = `${inputCls} [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none`;

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
  view: ViewMode;
  onViewChange: (v: ViewMode) => void;
}

// ── Filter rail: the six primary spec'd fields as boxed rows, plus a
// collapsible section for the rest of the existing (working) filter set. ────

export default function PlayerFilters({ filters, onChange, view, onViewChange }: Props) {
  const [moreOpen, setMoreOpen] = useState(false);

  function set<K extends keyof PlayerFilterState>(key: K, value: PlayerFilterState[K]) {
    onChange({ ...filters, [key]: value });
  }

  const moreCount = countActiveFilters(filters);

  return (
    <div className="space-y-3">
      {/* Search */}
      <div className={fieldCls}>
        <input
          type="text"
          placeholder="Search players…"
          value={filters.search}
          onChange={(e) => set("search", e.target.value)}
          className={inputCls}
        />
      </div>

      {/* Club — kept visible, not buried in "More filters": searching for a
          club by name is common enough (and easy to mistake for the player
          search above) that hiding it caused real players to look missing. */}
      <div className={fieldCls}>
        <input
          type="text"
          placeholder="Club…"
          value={filters.club_search}
          onChange={(e) => set("club_search", e.target.value)}
          className={inputCls}
        />
      </div>

      {/* Position */}
      <div>
        <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-text-muted">Position</p>
        <div className="flex gap-1.5">
          {POSITIONS.map((pos) => {
            const active = filters.position === pos;
            return (
              <button
                key={pos}
                onClick={() => set("position", active ? "" : pos)}
                className={`flex-1 rounded-lg px-2 py-1.5 text-xs font-bold ring-1 transition-colors ${
                  active ? "bg-accent-bg text-accent-active ring-accent" : "bg-surface text-text-muted ring-input-border hover:ring-accent"
                }`}
              >
                {pos}
              </button>
            );
          })}
        </div>
      </div>

      {/* Asking price (maps to market-value filter) */}
      <div>
        <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-text-muted">Asking price</p>
        <div className="flex items-center gap-1.5">
          <div className={fieldCls}><input type="number" min={0} placeholder="Min €M" value={filters.min_value} onChange={(e) => set("min_value", e.target.value)} className={numInputCls} /></div>
          <span className="text-text-muted text-xs shrink-0">–</span>
          <div className={fieldCls}><input type="number" min={0} placeholder="Max €M" value={filters.max_value} onChange={(e) => set("max_value", e.target.value)} className={numInputCls} /></div>
        </div>
      </div>

      {/* Age */}
      <div>
        <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-text-muted">Age</p>
        <div className="flex items-center gap-1.5">
          <div className={fieldCls}><input type="number" min={14} max={50} placeholder="Min age" value={filters.min_age} onChange={(e) => set("min_age", e.target.value)} className={numInputCls} /></div>
          <span className="text-text-muted text-xs shrink-0">–</span>
          <div className={fieldCls}><input type="number" min={14} max={50} placeholder="Max age" value={filters.max_age} onChange={(e) => set("max_age", e.target.value)} className={numInputCls} /></div>
        </div>
      </div>

      {/* Contract ends within */}
      <div>
        <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-text-muted">Contract ends within</p>
        <div className={fieldCls}>
          <input type="number" min={1} max={36} placeholder="Any" value={filters.contract_expiry_months} onChange={(e) => set("contract_expiry_months", e.target.value)} className={numInputCls} />
          <span className="shrink-0 text-[11px] text-text-muted">months</span>
        </div>
      </div>

      {/* Form score */}
      <div>
        <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-text-muted">Form score</p>
        <div className={fieldCls}>
          <input type="number" min={0} max={100} placeholder="Min" value={filters.min_form_score} onChange={(e) => set("min_form_score", e.target.value)} className={numInputCls} />
          <span className="shrink-0 text-[11px] text-text-muted">and above</span>
        </div>
      </div>

      {/* More filters toggle */}
      <button
        onClick={() => setMoreOpen((o) => !o)}
        className="flex w-full items-center justify-between text-xs font-semibold text-text-muted hover:text-text transition-colors"
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
          <label className="flex items-center justify-between rounded-lg bg-surface px-[11px] py-[9px] ring-1 ring-input-border cursor-pointer">
            <span className="text-sm text-text-secondary">Open to offers only</span>
            <div
              onClick={(e) => { e.preventDefault(); set("open_to_offers", !filters.open_to_offers); }}
              className={`relative h-4 w-8 shrink-0 rounded-full transition-colors ${filters.open_to_offers ? "bg-success" : "bg-border"}`}
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

      {(moreCount > 0 || filters.min_age || filters.max_age || filters.min_value || filters.max_value || filters.contract_expiry_months || filters.min_form_score) && (
        <button
          onClick={() => onChange(DEFAULT_PLAYER_FILTERS)}
          className="text-xs text-text-muted hover:text-text-secondary transition-colors"
        >
          Clear all filters
        </button>
      )}

      {/* View toggle (grid/list) — kept as an existing, working feature */}
      <div className="flex rounded-lg ring-1 ring-input-border overflow-hidden w-fit">
        <button
          onClick={() => onViewChange("grid")}
          title="Grid view"
          className={`px-2.5 py-1.5 transition-colors ${view === "grid" ? "bg-accent-bg text-accent-active" : "bg-surface text-text-muted hover:text-text"}`}
        >
          <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M4 5h4v4H4zM10 5h4v4h-4zM16 5h4v4h-4zM4 11h4v4H4zM10 11h4v4h-4zM16 11h4v4h-4zM4 17h4v4H4zM10 17h4v4h-4zM16 17h4v4h-4z" /></svg>
        </button>
        <button
          onClick={() => onViewChange("list")}
          title="List view"
          className={`px-2.5 py-1.5 transition-colors ${view === "list" ? "bg-accent-bg text-accent-active" : "bg-surface text-text-muted hover:text-text"}`}
        >
          <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 10h16M4 14h16M4 18h16" /></svg>
        </button>
      </div>
    </div>
  );
}
