import { useState } from "react";

import { useShortlistReview } from "../../hooks/useAI";
import type { ShortlistPlayerAssessment } from "../../types/api";
import Spinner from "../ui/Spinner";

const VERDICT_STYLES = {
  strong:   { label: "Strong shortlist",   cls: "bg-success-bg text-success-text ring-success-ring" },
  adequate: { label: "Adequate shortlist", cls: "bg-warning-bg text-warning-text ring-warning-ring" },
  weak:     { label: "Weak shortlist",     cls: "bg-danger-bg text-danger-text ring-danger-ring" },
};

const PRIORITY_STYLES = {
  high:   { dot: "bg-success", label: "High priority" },
  medium: { dot: "bg-warning-fill",   label: "Medium priority" },
  low:    { dot: "bg-text-muted",   label: "Low priority" },
};

function AssessmentRow({ a }: { a: ShortlistPlayerAssessment }) {
  const p = PRIORITY_STYLES[a.fit_priority] ?? PRIORITY_STYLES.low;
  return (
    <li className="flex items-start gap-3 px-4 py-3">
      <div className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${p.dot}`} />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-body font-semibold text-text">{a.name}</span>
          {a.addresses_gap && (
            <span className="rounded-md bg-ai-bg px-1.5 py-0.5 text-caption font-semibold text-ai-text ring-1 ring-ai-ring">
              fills gap
            </span>
          )}
          <span className="text-caption text-text-muted">{p.label}</span>
        </div>
        <p className="mt-0.5 text-caption text-text-muted leading-snug">{a.reason}</p>
      </div>
    </li>
  );
}

interface ShortlistReviewPanelProps {
  shortlistId: string;
  itemCount: number;
}

export function ShortlistReviewPanel({ shortlistId, itemCount }: ShortlistReviewPanelProps) {
  const [enabled, setEnabled] = useState(false);
  const [forceRefresh, setForceRefresh] = useState(false);
  const { data, isFetching, error } = useShortlistReview(shortlistId, enabled, forceRefresh);

  const verdict = data ? (VERDICT_STYLES[data.overall_verdict] ?? VERDICT_STYLES.adequate) : null;

  if (!enabled) {
    return (
      <div className="mb-6 flex items-center justify-between rounded-xl bg-surface px-4 py-3 ring-1 ring-ai-ring">
        <div>
          <p className="text-body font-semibold text-text">✦ AI Shortlist Review</p>
          <p className="text-caption text-text-muted">Get an AI assessment of your {itemCount} scouted player{itemCount !== 1 ? "s" : ""}</p>
        </div>
        <button
          onClick={() => setEnabled(true)}
          className="shrink-0 rounded-lg bg-ai-bg px-3 py-1.5 text-caption font-semibold text-ai-text ring-1 ring-ai-ring hover:brightness-95 transition-colors"
        >
          Generate
        </button>
      </div>
    );
  }

  return (
    <div className="mb-6 rounded-xl bg-surface ring-1 ring-ai-ring overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-rule">
        <p className="text-body font-semibold text-text">✦ AI Shortlist Review</p>
        <div className="flex items-center gap-2">
          {data && !isFetching && (
            <button
              onClick={() => { setForceRefresh(true); setEnabled(true); }}
              className="text-caption text-text-muted hover:text-text-secondary transition-colors"
            >
              Refresh
            </button>
          )}
          {verdict && (
            <span className={`rounded-full px-2.5 py-0.5 text-caption font-semibold ring-1 ${verdict.cls}`}>
              {verdict.label}
            </span>
          )}
        </div>
      </div>

      {isFetching && (
        <div className="flex items-center gap-2 px-4 py-4 text-small text-text-muted">
          <Spinner size="sm" />
          Reviewing shortlist…
        </div>
      )}

      {error && !isFetching && (
        <p className="px-4 py-3 text-caption text-danger-text">
          {(error as { response?: { data?: { detail?: string } } }).response?.data?.detail ??
            "Review failed. Please try again."}
        </p>
      )}

      {data && !isFetching && (
        <div className="divide-y divide-rule-faint">
          {/* Summary */}
          <div className="px-4 py-3">
            <p className="text-caption leading-relaxed text-text-muted">{data.summary}</p>
          </div>

          {/* Top picks + missing positions */}
          {(data.top_picks.length > 0 || data.missing_positions.length > 0) && (
            <div className="flex flex-wrap gap-6 px-4 py-3">
              {data.top_picks.length > 0 && (
                <div>
                  <p className="mb-1.5 text-caption font-semibold text-ai-text">
                    Top picks
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {data.top_picks.map((name) => (
                      <span
                        key={name}
                        className="rounded-md bg-ai-bg px-2 py-0.5 text-caption font-medium text-ai-text ring-1 ring-ai-ring"
                      >
                        {name}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {data.missing_positions.length > 0 && (
                <div>
                  <p className="mb-1.5 text-caption font-semibold text-warning-text">
                    Still needed
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {data.missing_positions.map((pos) => (
                      <span
                        key={pos}
                        className="rounded-md bg-warning-bg px-2 py-0.5 text-caption font-medium text-warning-text ring-1 ring-warning-ring"
                      >
                        {pos}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Per-player assessments */}
          {data.player_assessments.length > 0 && (
            <div>
              <p className="px-4 pt-3 pb-1 text-caption font-semibold text-text-secondary">
                Player assessments
              </p>
              <ul className="divide-y divide-rule-faint">
                {data.player_assessments.map((a) => (
                  <AssessmentRow key={a.player_id} a={a} />
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
