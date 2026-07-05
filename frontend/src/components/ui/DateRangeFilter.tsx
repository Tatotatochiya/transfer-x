import { useState } from "react";

export interface DateRange {
  dateFrom: string; // "" | "YYYY-MM-DD"
  dateTo: string;   // "" | "YYYY-MM-DD"
}

export const EMPTY_DATE_RANGE: DateRange = { dateFrom: "", dateTo: "" };

interface DateRangeFilterProps {
  value: DateRange;
  onChange: (range: DateRange) => void;
  accent?: "emerald" | "amber";
}

const CURRENT_YEAR = new Date().getFullYear();
const YEAR_OPTIONS = [CURRENT_YEAR, CURRENT_YEAR - 1, CURRENT_YEAR - 2, CURRENT_YEAR - 3];

function yearRange(year: number): DateRange {
  return { dateFrom: `${year}-01-01`, dateTo: `${year}-12-31` };
}

const ACCENT = {
  emerald: {
    active: "bg-emerald-500/15 text-emerald-400 ring-1 ring-emerald-500/30",
    ring: "focus:ring-emerald-500",
  },
  amber: {
    active: "bg-amber-500/15 text-amber-400 ring-1 ring-amber-500/30",
    ring: "focus:ring-amber-500",
  },
};

/** Quick date-range picker: all time / a recent year / a custom range. Used
 * across every filterable list page so "last 30 rows" (the backend default)
 * can be narrowed consistently instead of each page inventing its own UI. */
export default function DateRangeFilter({ value, onChange, accent = "emerald" }: DateRangeFilterProps) {
  const [customOpen, setCustomOpen] = useState(false);
  const colors = ACCENT[accent];

  const activeYear = YEAR_OPTIONS.find(
    (y) => value.dateFrom === `${y}-01-01` && value.dateTo === `${y}-12-31`
  );
  const isAllTime = !value.dateFrom && !value.dateTo;
  const isCustomActive = !isAllTime && activeYear === undefined;

  function pill(active: boolean) {
    return `rounded-lg px-3 py-1.5 text-sm transition-colors ${
      active ? colors.active : "bg-slate-800 text-slate-400 hover:text-white"
    }`;
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <button
        type="button"
        onClick={() => { onChange(EMPTY_DATE_RANGE); setCustomOpen(false); }}
        className={pill(isAllTime)}
      >
        All time
      </button>
      {YEAR_OPTIONS.map((y) => (
        <button
          key={y}
          type="button"
          onClick={() => { onChange(yearRange(y)); setCustomOpen(false); }}
          className={pill(activeYear === y)}
        >
          {y}
        </button>
      ))}
      <button
        type="button"
        onClick={() => setCustomOpen((v) => !v)}
        className={pill(isCustomActive || customOpen)}
      >
        Custom range
      </button>
      {(customOpen || isCustomActive) && (
        <div className="flex items-center gap-1.5">
          <input
            type="date"
            value={value.dateFrom}
            onChange={(e) => onChange({ ...value, dateFrom: e.target.value })}
            className={`rounded-lg bg-slate-800 px-2.5 py-1.5 text-xs text-white ring-1 ring-white/10 focus:outline-none ${colors.ring}`}
          />
          <span className="text-xs text-slate-500">to</span>
          <input
            type="date"
            value={value.dateTo}
            onChange={(e) => onChange({ ...value, dateTo: e.target.value })}
            className={`rounded-lg bg-slate-800 px-2.5 py-1.5 text-xs text-white ring-1 ring-white/10 focus:outline-none ${colors.ring}`}
          />
        </div>
      )}
    </div>
  );
}
