import { useEffect, useRef, useState } from "react";
import type { FairValueSignal } from "../../types/api";
import { formatDate } from "../../lib/utils";

function ageLine(signal: FairValueSignal): string {
  const factor = Number(signal.age_factor).toFixed(2);
  if (signal.age == null) return `Age unknown — factor ×${factor}`;
  const age = signal.age;
  const phase =
    age <= 20 ? "development years"
    : age <= 23 ? "approaching peak"
    : age <= 27 ? "peak years"
    : age <= 30 ? "post-peak"
    : "veteran decline";
  return `Age ${age} — ${phase} (×${factor})`;
}

function confidenceLine(signal: FairValueSignal): string {
  const minutes = signal.minutes != null ? `${signal.minutes.toLocaleString("en-GB")} minutes this season` : "limited data";
  return `${signal.confidence} confidence — ${minutes}`;
}

/** Info trigger + popover explaining the model number (TRA-92).
 *  The footer disclaimer is mandatory (D5) — never remove it. */
export default function ValuationBreakdownPopover({ signal }: { signal: FairValueSignal }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, [open]);

  const topDrivers = signal.breakdown.slice(0, 5);

  return (
    <div ref={ref} className="relative inline-flex">
      <button
        onClick={(e) => { e.stopPropagation(); setOpen((o) => !o); }}
        title="How this estimate is built"
        aria-label="Valuation breakdown"
        className="rounded p-0.5 text-slate-600 hover:text-slate-300 transition-colors"
      >
        <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      </button>

      {open && (
        <div className="absolute right-0 top-6 z-50 w-72 rounded-xl bg-slate-900 p-4 shadow-xl ring-1 ring-white/[0.12]">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
            Top drivers
          </p>
          <div className="space-y-1.5">
            {topDrivers.map((row) => (
              <div key={row.label} className="flex items-center justify-between gap-2 text-xs">
                <span className="text-slate-400 truncate">{row.label}</span>
                <span className="shrink-0 tabular-nums text-slate-300">
                  {row.value} <span className="text-slate-600">·</span>{" "}
                  <span className="font-semibold">{Number(row.contribution).toFixed(1)}</span>
                </span>
              </div>
            ))}
          </div>

          <div className="mt-3 space-y-1 border-t border-white/[0.06] pt-2.5 text-xs text-slate-400">
            <p>{ageLine(signal)}</p>
            <p>League tier {signal.league_tier}</p>
            <p>{confidenceLine(signal)}</p>
          </div>

          <p className="mt-3 border-t border-white/[0.06] pt-2.5 text-[10px] leading-relaxed text-slate-600">
            Model {signal.model_version} · as of {formatDate(signal.as_of)} ·{" "}
            Model estimate — not an official valuation.
          </p>
        </div>
      )}
    </div>
  );
}
