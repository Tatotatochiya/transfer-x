import { useStreamingSquadAnalysis } from "../../hooks/useStreamingSquadAnalysis";
import type { RecommendedProfile } from "../../types/api";
import Badge from "../ui/Badge";
import Spinner from "../ui/Spinner";

const priorityVariant: Record<string, "danger" | "warning" | "info"> = {
  high: "danger",
  medium: "warning",
  low: "info",
};

export function ScoutReportPanel() {
  const { state, streamText, result, error, start } = useStreamingSquadAnalysis();

  const isIdle = state === "idle";
  const isStreaming = state === "streaming";
  const isDone = state === "done";

  return (
    <div className="rounded-xl bg-slate-900 ring-1 ring-white/[0.08]">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-white/[0.06]">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-white">AI Scout Report</span>
          {result?.cached && <Badge variant="neutral">cached</Badge>}
        </div>
        <button
          onClick={() => start(isDone)}
          disabled={isStreaming}
          className="flex items-center gap-1.5 rounded-lg bg-violet-500/15 px-3 py-1.5 text-xs font-semibold text-violet-400 ring-1 ring-violet-500/30 hover:bg-violet-500/25 disabled:opacity-50 transition-colors"
        >
          {isStreaming ? <Spinner size="sm" /> : <span>✦</span>}
          {isDone ? "Refresh" : "Generate"}
        </button>
      </div>

      {/* Idle state */}
      {isIdle && (
        <p className="px-5 py-6 text-sm text-slate-500">
          Generate an AI-powered analysis of your squad's gaps, risks, and transfer needs.
        </p>
      )}

      {/* Streaming: show live text */}
      {isStreaming && (
        <div className="px-5 py-4">
          <div className="flex items-center gap-2 mb-3 text-xs text-violet-400">
            <Spinner size="sm" />
            Analysing squad…
          </div>
          {streamText && (
            <pre className="text-xs text-slate-400 whitespace-pre-wrap font-mono leading-relaxed max-h-48 overflow-y-auto">
              {streamText}
              <span className="animate-pulse">▌</span>
            </pre>
          )}
        </div>
      )}

      {/* Error */}
      {error && (
        <p className="px-5 py-4 text-sm text-red-400">{error}</p>
      )}

      {/* Done: structured report */}
      {isDone && result && (
        <div className="divide-y divide-white/[0.05]">
          <div className="px-5 py-4">
            <p className="text-sm text-slate-300 leading-relaxed">{result.summary}</p>
          </div>

          {result.positional_gaps.length > 0 && (
            <ReportSection title="Positional Gaps" icon="⚠">
              <BulletList items={result.positional_gaps} colour="text-amber-300" />
            </ReportSection>
          )}

          {result.age_risks.length > 0 && (
            <ReportSection title="Age Risks" icon="📅">
              <BulletList items={result.age_risks} colour="text-sky-300" />
            </ReportSection>
          )}

          {result.contract_risks.length > 0 && (
            <ReportSection title="Contract Risks" icon="📋">
              <BulletList items={result.contract_risks} colour="text-red-300" />
            </ReportSection>
          )}

          {result.recommended_profiles.length > 0 && (
            <ReportSection title="Recommended Transfer Profiles" icon="🎯">
              <ul className="mt-2 space-y-2">
                {result.recommended_profiles.map((p: RecommendedProfile, i: number) => (
                  <li key={i} className="flex items-start gap-2 text-sm">
                    <Badge variant={priorityVariant[p.priority] ?? "neutral"}>{p.priority}</Badge>
                    <span className="text-slate-300">
                      <span className="font-medium text-white">{p.position}</span> age {p.age_range} —{" "}
                      {p.reason}
                    </span>
                  </li>
                ))}
              </ul>
            </ReportSection>
          )}
        </div>
      )}
    </div>
  );
}

function ReportSection({
  title,
  icon,
  children,
}: {
  title: string;
  icon: string;
  children: React.ReactNode;
}) {
  return (
    <div className="px-5 py-3">
      <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
        {icon} {title}
      </p>
      {children}
    </div>
  );
}

function BulletList({ items, colour }: { items: string[]; colour: string }) {
  return (
    <ul className="space-y-1">
      {items.map((item, i) => (
        <li key={i} className={`text-sm ${colour}`}>
          · {item}
        </li>
      ))}
    </ul>
  );
}
