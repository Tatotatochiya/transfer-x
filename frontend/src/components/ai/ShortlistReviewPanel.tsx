import { useState } from "react";

import { useShortlistReview } from "../../hooks/useAI";
import type { ShortlistPlayerAssessment } from "../../types/api";
import Spinner from "../ui/Spinner";

const VERDICT_STYLES = {
  strong:   { label: "Strong shortlist",   cls: "bg-emerald-500/15 text-emerald-400 ring-emerald-500/30" },
  adequate: { label: "Adequate shortlist", cls: "bg-amber-500/15 text-amber-400 ring-amber-500/30" },
  weak:     { label: "Weak shortlist",     cls: "bg-red-500/15 text-red-400 ring-red-500/30" },
};

const PRIORITY_STYLES = {
  high:   { dot: "bg-emerald-400", label: "High priority" },
  medium: { dot: "bg-amber-400",   label: "Medium priority" },
  low:    { dot: "bg-slate-500",   label: "Low priority" },
};

function AssessmentRow({ a }: { a: ShortlistPlayerAssessment }) {
  const p = PRIORITY_STYLES[a.fit_priority] ?? PRIORITY_STYLES.low;
  return (
    <li className="flex items-start gap-3 px-4 py-3">
      <div className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${p.dot}`} />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-semibold text-white">{a.name}</span>
          {a.addresses_gap && (
            <span className="rounded-md bg-violet-500/10 px-1.5 py-0.5 text-[10px] font-semibold text-violet-400 ring-1 ring-violet-500/20">
              fills gap
            </span>
          )}
          <span className="text-[10px] text-slate-500">{p.label}</span>
        </div>
        <p className="mt-0.5 text-xs text-slate-400 leading-snug">{a.reason}</p>
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
      <div className="mb-6 flex items-center justify-between rounded-xl bg-slate-900 px-4 py-3 ring-1 ring-violet-500/20">
        <div>
          <p className="text-sm font-semibold text-white">✦ AI Shortlist Review</p>
          <p className="text-xs text-slate-500">Get an AI assessment of your {itemCount} scouted player{itemCount !== 1 ? "s" : ""}</p>
        </div>
        <button
          onClick={() => setEnabled(true)}
          className="shrink-0 rounded-lg bg-violet-500/15 px-3 py-1.5 text-xs font-semibold text-violet-400 ring-1 ring-violet-500/30 hover:bg-violet-500/25 transition-colors"
        >
          Generate
        </button>
      </div>
    );
  }

  return (
    <div className="mb-6 rounded-xl bg-slate-900 ring-1 ring-violet-500/20 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.06]">
        <p className="text-sm font-semibold text-white">✦ AI Shortlist Review</p>
        <div className="flex items-center gap-2">
          {data && !isFetching && (
            <button
              onClick={() => { setForceRefresh(true); setEnabled(true); }}
              className="text-xs text-slate-600 hover:text-slate-400 transition-colors"
            >
              Refresh
            </button>
          )}
          {verdict && (
            <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ${verdict.cls}`}>
              {verdict.label}
            </span>
          )}
        </div>
      </div>

      {isFetching && (
        <div className="flex items-center gap-2 px-4 py-4 text-sm text-slate-400">
          <Spinner size="sm" />
          Reviewing shortlist…
        </div>
      )}

      {error && !isFetching && (
        <p className="px-4 py-3 text-xs text-red-400">
          {(error as { response?: { data?: { detail?: string } } }).response?.data?.detail ??
            "Review failed. Please try again."}
        </p>
      )}

      {data && !isFetching && (
        <div className="divide-y divide-white/[0.05]">
          {/* Summary */}
          <div className="px-4 py-3">
            <p className="text-xs leading-relaxed text-slate-400">{data.summary}</p>
          </div>

          {/* Top picks + missing positions */}
          {(data.top_picks.length > 0 || data.missing_positions.length > 0) && (
            <div className="flex flex-wrap gap-6 px-4 py-3">
              {data.top_picks.length > 0 && (
                <div>
                  <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-widest text-violet-400">
                    Top picks
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {data.top_picks.map((name) => (
                      <span
                        key={name}
                        className="rounded-md bg-violet-500/10 px-2 py-0.5 text-xs font-medium text-violet-300 ring-1 ring-violet-500/20"
                      >
                        {name}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {data.missing_positions.length > 0 && (
                <div>
                  <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-widest text-amber-500">
                    Still needed
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {data.missing_positions.map((pos) => (
                      <span
                        key={pos}
                        className="rounded-md bg-amber-500/10 px-2 py-0.5 text-xs font-medium text-amber-400 ring-1 ring-amber-500/20"
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
              <p className="px-4 pt-3 pb-1 text-[10px] font-semibold uppercase tracking-widest text-slate-500">
                Player assessments
              </p>
              <ul className="divide-y divide-white/[0.04]">
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
