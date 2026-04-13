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
  sort_by: "name",
  sort_dir: "asc",
};

const POSITIONS: PlayerPosition[] = ["GK", "DEF", "MID", "FWD"];

const POSITION_COLOUR: Record<string, string> = {
  GK:  "bg-amber-500/20 text-amber-300 ring-amber-500/30",
  DEF: "bg-blue-500/20 text-blue-300 ring-blue-500/30",
  MID: "bg-emerald-500/20 text-emerald-300 ring-emerald-500/30",
  FWD: "bg-red-500/20 text-red-300 ring-red-500/30",
};

const SORT_OPTIONS: { label: string; sort_by: PlayerFilterState["sort_by"]; sort_dir: "asc" | "desc" }[] = [
  { label: "Name A→Z",       sort_by: "name",         sort_dir: "asc" },
  { label: "Name Z→A",       sort_by: "name",         sort_dir: "desc" },
  { label: "Youngest first", sort_by: "age",          sort_dir: "asc" },
  { label: "Oldest first",   sort_by: "age",          sort_dir: "desc" },
  { label: "Most Goals",     sort_by: "goals",        sort_dir: "desc" },
  { label: "Most Assists",   sort_by: "assists",      sort_dir: "desc" },
  { label: "Most Apps",      sort_by: "appearances",  sort_dir: "desc" },
  { label: "Best Rating",    sort_by: "avg_rating",   sort_dir: "desc" },
  { label: "Best Form",      sort_by: "form_score",   sort_dir: "desc" },
];

const inputCls =
  "w-full rounded-lg bg-slate-800/80 px-3 py-1.5 text-sm text-white placeholder-slate-500 ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500/60 transition-colors";

const numInputCls = `${inputCls} [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none`;

function countActiveFilters(f: PlayerFilterState): number {
  let n = 0;
  if (f.status) n++;
  if (f.open_to_offers) n++;
  if (f.nationality) n++;
  if (f.club_search) n++;
  if (f.min_age || f.max_age) n++;
  if (f.min_goals) n++;
  if (f.min_assists) n++;
  if (f.min_appearances) n++;
  if (f.min_avg_rating) n++;
  if (f.min_form_score) n++;
  if (f.sort_by !== "name" || f.sort_dir !== "asc") n++;
  return n;
}

interface Props {
  filters: PlayerFilterState;
  onChange: (f: PlayerFilterState) => void;
  view: ViewMode;
  onViewChange: (v: ViewMode) => void;
}

export default function PlayerFilters({ filters, onChange, view, onViewChange }: Props) {
  const [panelOpen, setPanelOpen] = useState(false);

  function set<K extends keyof PlayerFilterState>(key: K, value: PlayerFilterState[K]) {
    onChange({ ...filters, [key]: value });
  }

  function setSort(value: string) {
    const opt = SORT_OPTIONS.find((o) => `${o.sort_by}_${o.sort_dir}` === value);
    if (opt) onChange({ ...filters, sort_by: opt.sort_by, sort_dir: opt.sort_dir });
  }

  const activeCount = countActiveFilters(filters);
  const sortValue = `${filters.sort_by}_${filters.sort_dir}`;

  // Build active filter chips
  const chips: { label: string; clear: () => void }[] = [];
  if (filters.status) chips.push({ label: filters.status === "FREE_AGENT" ? "Free Agent" : "Contracted", clear: () => set("status", "") });
  if (filters.open_to_offers) chips.push({ label: "Open to offers", clear: () => set("open_to_offers", false) });
  if (filters.nationality) chips.push({ label: `Nat: ${filters.nationality}`, clear: () => set("nationality", "") });
  if (filters.club_search) chips.push({ label: `Club: ${filters.club_search}`, clear: () => set("club_search", "") });
  if (filters.min_age || filters.max_age) chips.push({ label: `Age: ${filters.min_age || "?"} – ${filters.max_age || "?"}`, clear: () => onChange({ ...filters, min_age: "", max_age: "" }) });
  if (filters.min_goals) chips.push({ label: `Goals ≥ ${filters.min_goals}`, clear: () => set("min_goals", "") });
  if (filters.min_assists) chips.push({ label: `Assists ≥ ${filters.min_assists}`, clear: () => set("min_assists", "") });
  if (filters.min_appearances) chips.push({ label: `Apps ≥ ${filters.min_appearances}`, clear: () => set("min_appearances", "") });
  if (filters.min_avg_rating) chips.push({ label: `Rating ≥ ${filters.min_avg_rating}`, clear: () => set("min_avg_rating", "") });
  if (filters.min_form_score) chips.push({ label: `Form ≥ ${filters.min_form_score}`, clear: () => set("min_form_score", "") });

  return (
    <div className="mb-5 space-y-2">
      {/* ── Toolbar row ─────────────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-center gap-2">

        {/* Search */}
        <div className="relative">
          <svg className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-500" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-4.35-4.35M17 11A6 6 0 105 11a6 6 0 0012 0z" /></svg>
          <input
            type="text"
            placeholder="Search players…"
            value={filters.search}
            onChange={(e) => set("search", e.target.value)}
            className="rounded-lg bg-slate-800/80 py-1.5 pl-8 pr-3 text-sm text-white placeholder-slate-500 ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500/60 transition-colors w-44"
          />
        </div>

        {/* Position pills */}
        <div className="flex gap-1">
          {POSITIONS.map((pos) => {
            const active = filters.position === pos;
            return (
              <button
                key={pos}
                onClick={() => set("position", active ? "" : pos)}
                className={`rounded-md px-2.5 py-1 text-xs font-bold ring-1 transition-all ${
                  active ? POSITION_COLOUR[pos] : "bg-slate-800/60 text-slate-500 ring-white/10 hover:text-white"
                }`}
              >
                {pos}
              </button>
            );
          })}
        </div>

        {/* Divider */}
        <span className="h-5 w-px bg-white/10 shrink-0" />

        {/* Availability quick-picks */}
        <div className="flex gap-1">
          <button
            onClick={() => set("status", filters.status === "FREE_AGENT" ? "" : "FREE_AGENT")}
            className={`rounded-md px-2.5 py-1 text-xs font-bold ring-1 transition-all ${
              filters.status === "FREE_AGENT"
                ? "bg-emerald-500/20 text-emerald-300 ring-emerald-500/30"
                : "bg-slate-800/60 text-slate-500 ring-white/10 hover:text-white"
            }`}
          >
            Free Agent
          </button>
          <button
            onClick={() => set("open_to_offers", !filters.open_to_offers)}
            className={`flex items-center gap-1 rounded-md px-2.5 py-1 text-xs font-bold ring-1 transition-all ${
              filters.open_to_offers
                ? "bg-emerald-500/20 text-emerald-300 ring-emerald-500/30"
                : "bg-slate-800/60 text-slate-500 ring-white/10 hover:text-white"
            }`}
          >
            {filters.open_to_offers && (
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
            )}
            Open
          </button>
        </div>

        {/* Spacer */}
        <div className="flex-1" />

        {/* Sort */}
        <select
          value={sortValue}
          onChange={(e) => setSort(e.target.value)}
          className="rounded-lg bg-slate-800/80 px-2.5 py-1.5 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500/60 transition-colors"
        >
          {SORT_OPTIONS.map((o) => (
            <option key={`${o.sort_by}_${o.sort_dir}`} value={`${o.sort_by}_${o.sort_dir}`}>
              {o.label}
            </option>
          ))}
        </select>

        {/* More filters toggle */}
        <button
          onClick={() => setPanelOpen((o) => !o)}
          className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium ring-1 transition-colors ${
            panelOpen || activeCount > 0
              ? "bg-emerald-500/15 text-emerald-400 ring-emerald-500/30"
              : "bg-slate-800/80 text-slate-400 ring-white/10 hover:text-white"
          }`}
        >
          <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M3 4h18M7 12h10M11 20h2" /></svg>
          Filters
          {activeCount > 0 && (
            <span className="flex h-4 w-4 items-center justify-center rounded-full bg-emerald-500 text-[10px] font-bold text-white">
              {activeCount}
            </span>
          )}
        </button>

        {/* View toggle */}
        <div className="flex rounded-lg ring-1 ring-white/10 overflow-hidden">
          <button
            onClick={() => onViewChange("grid")}
            title="Grid view"
            className={`px-2.5 py-1.5 transition-colors ${view === "grid" ? "bg-emerald-500/20 text-emerald-400" : "bg-slate-800/80 text-slate-500 hover:text-white"}`}
          >
            <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M4 5h4v4H4zM10 5h4v4h-4zM16 5h4v4h-4zM4 11h4v4H4zM10 11h4v4h-4zM16 11h4v4h-4zM4 17h4v4H4zM10 17h4v4h-4zM16 17h4v4h-4z" /></svg>
          </button>
          <button
            onClick={() => onViewChange("list")}
            title="List view"
            className={`px-2.5 py-1.5 transition-colors ${view === "list" ? "bg-emerald-500/20 text-emerald-400" : "bg-slate-800/80 text-slate-500 hover:text-white"}`}
          >
            <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 10h16M4 14h16M4 18h16" /></svg>
          </button>
        </div>
      </div>

      {/* ── Expandable advanced panel ─────────────────────────────────────────── */}
      {panelOpen && (
        <div className="rounded-xl bg-slate-900/80 ring-1 ring-white/[0.06] p-4 grid grid-cols-1 gap-x-6 gap-y-4 sm:grid-cols-3">

          {/* Availability */}
          <div>
            <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-500">Availability</p>
            <div className="space-y-2">
              <select
                value={filters.status}
                onChange={(e) => set("status", e.target.value as PlayerStatus | "")}
                className={inputCls}
              >
                <option value="">Any status</option>
                <option value="CONTRACTED">Contracted</option>
                <option value="FREE_AGENT">Free Agent</option>
              </select>
              <label className="flex items-center gap-2 cursor-pointer">
                <div
                  onClick={() => set("open_to_offers", !filters.open_to_offers)}
                  className={`relative h-4 w-8 rounded-full transition-colors ${filters.open_to_offers ? "bg-emerald-500" : "bg-slate-700"}`}
                >
                  <span className={`absolute top-0.5 left-0.5 h-3 w-3 rounded-full bg-white shadow transition-transform ${filters.open_to_offers ? "translate-x-4" : ""}`} />
                </div>
                <span className="text-xs text-slate-400">Open to offers only</span>
              </label>
            </div>
          </div>

          {/* Personal */}
          <div>
            <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-500">Personal</p>
            <div className="space-y-2">
              <input type="text" placeholder="Club…" value={filters.club_search} onChange={(e) => set("club_search", e.target.value)} className={inputCls} />
              <input type="text" placeholder="Nationality…" value={filters.nationality} onChange={(e) => set("nationality", e.target.value)} className={inputCls} />
              <div className="flex items-center gap-1.5">
                <input type="number" placeholder="Min age" min={14} max={50} value={filters.min_age} onChange={(e) => set("min_age", e.target.value)} className={numInputCls} />
                <span className="text-slate-600 text-xs shrink-0">–</span>
                <input type="number" placeholder="Max age" min={14} max={50} value={filters.max_age} onChange={(e) => set("max_age", e.target.value)} className={numInputCls} />
              </div>
            </div>
          </div>

          {/* Performance */}
          <div>
            <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-500">Performance</p>
            <div className="space-y-2">
              <div className="grid grid-cols-2 gap-1.5">
                <div className="relative">
                  <span className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-[10px] text-slate-500">G≥</span>
                  <input type="number" placeholder="0" min={0} value={filters.min_goals} onChange={(e) => set("min_goals", e.target.value)} className={`${numInputCls} pl-7`} />
                </div>
                <div className="relative">
                  <span className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-[10px] text-slate-500">A≥</span>
                  <input type="number" placeholder="0" min={0} value={filters.min_assists} onChange={(e) => set("min_assists", e.target.value)} className={`${numInputCls} pl-7`} />
                </div>
                <div className="relative">
                  <span className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-[10px] text-slate-500">Apps≥</span>
                  <input type="number" placeholder="0" min={0} value={filters.min_appearances} onChange={(e) => set("min_appearances", e.target.value)} className={`${numInputCls} pl-10`} />
                </div>
                <div className="relative">
                  <span className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-[10px] text-slate-500">Rtg≥</span>
                  <input type="number" placeholder="0.0" min={0} max={10} step={0.1} value={filters.min_avg_rating} onChange={(e) => set("min_avg_rating", e.target.value)} className={`${numInputCls} pl-10`} />
                </div>
              </div>
              <div className="relative">
                <span className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-[10px] text-slate-500">Form≥</span>
                <input type="number" placeholder="0" min={0} max={100} value={filters.min_form_score} onChange={(e) => set("min_form_score", e.target.value)} className={`${numInputCls} pl-12`} />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Active filter chips ───────────────────────────────────────────────── */}
      {chips.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5">
          {chips.map((chip) => (
            <button
              key={chip.label}
              onClick={chip.clear}
              className="flex items-center gap-1 rounded-full bg-slate-800 px-2.5 py-0.5 text-xs text-slate-300 ring-1 ring-white/10 hover:bg-slate-700 hover:text-white transition-colors"
            >
              {chip.label}
              <svg className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>
            </button>
          ))}
          <button
            onClick={() => onChange(DEFAULT_PLAYER_FILTERS)}
            className="text-xs text-slate-500 hover:text-slate-300 transition-colors ml-1"
          >
            Clear all
          </button>
        </div>
      )}
    </div>
  );
}
