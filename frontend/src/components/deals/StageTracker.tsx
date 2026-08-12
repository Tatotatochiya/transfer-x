import type { DealStage, DealStatus } from "../../types/enums";

// Full ordered pipeline; AGENT_NEGOTIATION and PERSONAL_TERMS are conditional stages
// inserted when a deal has an agent mandate. We display them when present.
const BASE_STAGES: DealStage[] = ["AGREEMENT", "PAPERWORK", "CONFIRMED", "COMPLETED"];
const EXTENDED_STAGES: DealStage[] = [
  "AGREEMENT",
  "AGENT_NEGOTIATION",
  "PERSONAL_TERMS",
  "PAPERWORK",
  "CONFIRMED",
  "COMPLETED",
];

const STAGE_LABELS: Record<DealStage, string> = {
  AGREEMENT:         "Agreement",
  AGENT_NEGOTIATION: "Agent Nego.",
  PERSONAL_TERMS:    "Personal Terms",
  PAPERWORK:         "Paperwork",
  CONFIRMED:         "Confirmed",
  COMPLETED:         "Completed",
};

interface StageTrackerProps {
  stage: DealStage;
  status: DealStatus;
}

export default function StageTracker({ stage, status }: StageTrackerProps) {
  const isAgentFlow =
    stage === "AGENT_NEGOTIATION" || stage === "PERSONAL_TERMS";
  const STAGES = isAgentFlow ? EXTENDED_STAGES : BASE_STAGES;
  const currentIdx = STAGES.indexOf(stage);
  const isCollapsed = status === "COLLAPSED";

  return (
    <>
      {/* Mobile: compact step count + progress bar */}
      <div className="sm:hidden">
        <p className="text-sm font-semibold text-text">
          Step {currentIdx + 1} of {STAGES.length} · {isCollapsed ? "Collapsed" : STAGE_LABELS[stage]}
        </p>
        <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-border-quiet">
          <div
            className={`h-full ${isCollapsed ? "bg-text-muted" : "bg-success-dot"}`}
            style={{ width: `${((currentIdx + 1) / STAGES.length) * 100}%` }}
          />
        </div>
      </div>

      {/* Tablet/desktop: six-pill row */}
      <div className="hidden sm:flex items-center gap-0">
        {STAGES.map((s, idx) => {
          const isPast    = idx < currentIdx;
          const isCurrent = idx === currentIdx && !isCollapsed;
          const isFuture  = idx > currentIdx;

          const pillClass = isCollapsed
            ? "text-text-muted"
            : isPast
            ? "text-text-secondary"
            : isCurrent
            ? "bg-accent-bg-strong text-accent-active font-semibold"
            : "text-text-muted";

          const dotClass = isCollapsed
            ? "bg-input-border"
            : isPast
            ? "bg-success-dot"
            : isCurrent
            ? "bg-accent"
            : "bg-input-border";

          return (
            <div key={s} className="flex flex-1 items-center">
              <span className={`inline-flex shrink-0 items-center gap-1.5 rounded-full px-[11px] py-[5px] text-xs ${pillClass}`}>
                <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${dotClass}`} />
                {STAGE_LABELS[s]}
              </span>
              {idx < STAGES.length - 1 && (
                <div className="mx-3 h-px min-w-[12px] flex-1 bg-border" />
              )}
            </div>
          );
        })}
      </div>
    </>
  );
}
