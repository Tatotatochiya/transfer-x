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
    <div className="rounded-xl bg-surface ring-1 ring-border">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-rule">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-text">AI Scout Report</span>
          {result?.cached && <Badge variant="neutral">cached</Badge>}
        </div>
        <button
          onClick={() => start(isDone)}
          disabled={isStreaming}
          className="flex items-center gap-1.5 rounded-lg bg-role-agent-text/15 px-3 py-1.5 text-xs font-semibold text-role-agent-text ring-1 ring-role-agent-text/30 hover:bg-role-agent-text/25 disabled:opacity-50 transition-colors"
        >
          {isStreaming ? <Spinner size="sm" /> : <span>✦</span>}
          {isDone ? "Refresh" : "Generate"}
        </button>
      </div>

      {/* Idle state */}
      {isIdle && (
        <p className="px-5 py-6 text-sm text-text-muted">
          Generate an AI-powered analysis of your squad's gaps, risks, and transfer needs.
        </p>
      )}

      {/* Streaming: show live text */}
      {isStreaming && (
        <div className="px-5 py-4">
          <div className="flex items-center gap-2 mb-3 text-xs text-role-agent-text">
            <Spinner size="sm" />
            Analysing squad…
          </div>
          {streamText && (
            <pre className="text-xs text-text-muted whitespace-pre-wrap font-mono leading-relaxed max-h-48 overflow-y-auto">
              {streamText}
              <span className="animate-pulse">▌</span>
            </pre>
          )}
        </div>
      )}

      {/* Error */}
      {error && (
        <p className="px-5 py-4 text-sm text-danger-text">{error}</p>
      )}

      {/* Done: structured report */}
      {isDone && result && (
        <div className="divide-y divide-rule-faint">
          <div className="px-5 py-4">
            <p className="text-sm text-text-secondary leading-relaxed">{result.summary}</p>
          </div>

          {result.positional_gaps.length > 0 && (
            <ReportSection title="Positional Gaps" icon="⚠">
              <BulletList items={result.positional_gaps} colour="text-warning-text" />
            </ReportSection>
          )}

          {result.age_risks.length > 0 && (
            <ReportSection title="Age Risks" icon="📅">
              <BulletList items={result.age_risks} colour="text-accent" />
            </ReportSection>
          )}

          {result.contract_risks.length > 0 && (
            <ReportSection title="Contract Risks" icon="📋">
              <BulletList items={result.contract_risks} colour="text-danger-text" />
            </ReportSection>
          )}

          {result.recommended_profiles.length > 0 && (
            <ReportSection title="Recommended Transfer Profiles" icon="🎯">
              <ul className="mt-2 space-y-2">
                {result.recommended_profiles.map((p: RecommendedProfile, i: number) => (
                  <li key={i} className="flex items-start gap-2 text-sm">
                    <Badge variant={priorityVariant[p.priority] ?? "neutral"}>{p.priority}</Badge>
                    <span className="text-text-secondary">
                      <span className="font-medium text-text">{p.position}</span> age {p.age_range} —{" "}
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
      <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-text-muted">
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
