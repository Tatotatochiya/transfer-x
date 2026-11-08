import { useState } from "react";
import type { AgentNegotiation, Deal } from "../../types/api";
import { STAGE_LONG, STAGE_SHORT, dealStages, stageNote, stageState } from "./dealStatus";

/**
 * How far along the deal is (deal-room-focus §5.4): every stage, always
 * including personal terms (D7). Phones get "Step n of N" and a bar, with the
 * stages one tap away; wider screens the pill row and a summary sentence.
 */
export default function DealProgress({ deal, negotiation }: { deal: Deal; negotiation: AgentNegotiation | null | undefined }) {
  const [open, setOpen] = useState(false);
  const stages = dealStages(deal, negotiation);
  const collapsed = deal.status === "COLLAPSED";
  const completed = deal.status === "COMPLETED";
  const current = Math.max(0, stages.indexOf(deal.stage));
  const step = completed ? stages.length : current + 1;
  const states = stages.map((s) => (collapsed ? "next" : stageState(deal, stages, s)));
  const notes = stages.map((s, i) => stageNote(deal, negotiation, s, states[i]));
  const summary = stages
    .map((_, i) => (states[i] === "done" || states[i] === "now" ? notes[i] : null))
    .filter(Boolean)
    .join(" · ");
  const label = collapsed ? `Collapsed at ${STAGE_LONG[deal.stage].toLowerCase()}` : `Step ${step} of ${stages.length} · ${STAGE_LONG[stages[step - 1] ?? deal.stage]}`;

  return (
    <section aria-label="Progress" className="rounded-xl bg-surface px-4 py-3.5 ring-1 ring-border">
      {/* Phone */}
      <div className="sm:hidden">
        <p className="text-[15px] font-semibold text-text">{label}</p>
        <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-border-quiet">
          <div className={`h-full ${collapsed ? "bg-text-muted" : "bg-success-dot"}`} style={{ width: `${(step / stages.length) * 100}%` }} />
        </div>
        <button
          type="button"
          aria-expanded={open}
          aria-controls="deal-progress-stages"
          onClick={() => setOpen((o) => !o)}
          className="mt-1 min-h-11 text-[15px] font-semibold text-accent"
        >
          {open ? "Hide stages" : "Show all stages"}
        </button>
        {open && (
          <ol id="deal-progress-stages" className="mt-1 space-y-3">
            {stages.map((s, i) => (
              <li key={s} className="flex items-start gap-3">
                <span
                  aria-hidden
                  className={`mt-0.5 flex h-[22px] w-[22px] shrink-0 items-center justify-center rounded-full text-[13px] font-bold ${
                    states[i] === "done" ? "bg-success text-white" : states[i] === "now" ? "bg-accent text-white" : "bg-surface ring-2 ring-input-border"
                  }`}
                >
                  {states[i] === "done" ? "✓" : ""}
                </span>
                <div className="min-w-0">
                  <p className={`text-[15px] ${states[i] === "now" ? "font-bold text-text" : "font-medium text-text-secondary"}`}>
                    {STAGE_LONG[s]}
                    <span className="sr-only">{states[i] === "done" ? ", done" : states[i] === "now" ? ", now" : ""}</span>
                  </p>
                  {notes[i] && <p className="text-sm text-text-muted">{notes[i]}</p>}
                </div>
              </li>
            ))}
          </ol>
        )}
      </div>

      {/* Tablet and desktop */}
      <div className="hidden sm:block">
        <ol className="flex flex-wrap items-center gap-y-1">
          {stages.map((s, i) => {
            const st = states[i];
            const pill = collapsed ? "text-text-muted"
              : st === "done" ? "text-text-secondary"
              : st === "now" ? "bg-accent-bg-strong text-accent-active font-semibold"
              : "text-text-muted";
            const dot = collapsed ? "bg-input-border" : st === "done" ? "bg-success-dot" : st === "now" ? "bg-accent" : "bg-input-border";
            return (
              <li key={s} className="flex flex-auto items-center last:flex-none" aria-current={st === "now" ? "step" : undefined}>
                <span className={`inline-flex shrink-0 items-center gap-1.5 rounded-full px-[11px] py-[5px] text-[13px] ${pill}`}>
                  <span aria-hidden className={`h-1.5 w-1.5 shrink-0 rounded-full ${dot}`} />
                  {STAGE_SHORT[s]}
                </span>
                {i < stages.length - 1 && <span aria-hidden className="mx-1 h-px min-w-[6px] flex-1 bg-border lg:mx-2" />}
              </li>
            );
          })}
        </ol>
        {(summary || collapsed) && (
          <p className="mt-2.5 text-sm text-text-secondary lg:truncate" title={collapsed ? label : summary}>
            {collapsed ? label : summary}
          </p>
        )}
      </div>
    </section>
  );
}
