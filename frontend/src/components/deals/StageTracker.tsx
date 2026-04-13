import type { DealStage, DealStatus } from "../../types/enums";

const STAGES: DealStage[] = ["AGREEMENT", "PAPERWORK", "CONFIRMED", "COMPLETED"];

const STAGE_LABELS: Record<DealStage, string> = {
  AGREEMENT: "Agreement",
  PAPERWORK: "Paperwork",
  CONFIRMED: "Confirmed",
  COMPLETED: "Completed",
};

interface StageTrackerProps {
  stage: DealStage;
  status: DealStatus;
}

export default function StageTracker({ stage, status }: StageTrackerProps) {
  const currentIdx = STAGES.indexOf(stage);
  const isCollapsed = status === "COLLAPSED";

  return (
    <div className="flex items-center gap-0">
      {STAGES.map((s, idx) => {
        const isPast    = idx < currentIdx;
        const isCurrent = idx === currentIdx && !isCollapsed;
        const isFuture  = idx > currentIdx;

        const circleClass = isCollapsed
          ? "bg-slate-800 text-slate-600 ring-1 ring-white/10"
          : isPast
          ? "bg-emerald-500 text-white"
          : isCurrent
          ? "bg-emerald-500/20 text-emerald-400 ring-1 ring-emerald-500/50"
          : "bg-slate-800 text-slate-500 ring-1 ring-white/10";

        const labelClass = isCollapsed
          ? "text-slate-600"
          : isPast
          ? "text-slate-300"
          : isCurrent
          ? "text-white font-semibold"
          : "text-slate-500";

        return (
          <div key={s} className="flex flex-1 items-center">
            {/* Step */}
            <div className="flex flex-col items-center gap-1.5 shrink-0">
              <div
                className={`flex h-8 w-8 items-center justify-center rounded-full text-xs font-bold transition-colors ${circleClass}`}
              >
                {isPast && !isCollapsed ? (
                  <svg
                    className="h-4 w-4"
                    fill="none"
                    viewBox="0 0 24 24"
                    strokeWidth={2.5}
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M4.5 12.75l6 6 9-13.5"
                    />
                  </svg>
                ) : (
                  idx + 1
                )}
              </div>
              <span className={`text-[11px] text-center ${labelClass}`}>
                {isFuture && !isCollapsed ? (
                  <span className="opacity-50">{STAGE_LABELS[s]}</span>
                ) : (
                  STAGE_LABELS[s]
                )}
              </span>
            </div>

            {/* Connector line */}
            {idx < STAGES.length - 1 && (
              <div
                className={`h-px flex-1 mx-1 transition-colors ${
                  isPast && !isCollapsed ? "bg-emerald-500/50" : "bg-white/[0.08]"
                }`}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
