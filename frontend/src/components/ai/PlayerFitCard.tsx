import { useState } from "react";

import { usePlayerFit } from "../../hooks/useAI";
import Spinner from "../ui/Spinner";

const SCORE_RING_R = 28;
const SCORE_RING_CIRC = 2 * Math.PI * SCORE_RING_R;

function ScoreRing({ score }: { score: number }) {
  const filled = (score / 100) * SCORE_RING_CIRC;
  const colour =
    score >= 70 ? "#34d399" : score >= 45 ? "#fbbf24" : "#f87171";
  const label =
    score >= 70 ? "Good fit" : score >= 45 ? "Possible fit" : "Poor fit";
  const labelColour =
    score >= 70 ? "text-emerald-400" : score >= 45 ? "text-amber-400" : "text-red-400";

  return (
    <div className="flex items-center gap-4">
      <div className="relative shrink-0">
        <svg width="72" height="72" className="-rotate-90">
          <circle cx="36" cy="36" r={SCORE_RING_R} fill="none" stroke="#1e293b" strokeWidth="6" />
          <circle
            cx="36" cy="36" r={SCORE_RING_R}
            fill="none"
            stroke={colour}
            strokeWidth="6"
            strokeLinecap="round"
            strokeDasharray={`${filled} ${SCORE_RING_CIRC}`}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-xl font-black text-white leading-none">{score}</span>
          <span className="text-[9px] text-slate-500 leading-none mt-0.5">/ 100</span>
        </div>
      </div>
      <div>
        <p className={`text-sm font-bold ${labelColour}`}>{label}</p>
        <p className="text-xs text-slate-500 mt-0.5">Squad fit score</p>
      </div>
    </div>
  );
}

interface PlayerFitCardProps {
  playerId: string;
}

export function PlayerFitCard({ playerId }: PlayerFitCardProps) {
  const [enabled, setEnabled] = useState(false);
  const { data, isFetching, error } = usePlayerFit(playerId, enabled);

  if (!enabled) {
    return (
      <div className="rounded-xl bg-slate-900 ring-1 ring-white/[0.08] px-4 py-3">
        <div className="flex items-center justify-between">
          <span className="text-sm font-semibold text-white">AI Fit Score</span>
          <button
            onClick={() => setEnabled(true)}
            className="rounded-lg bg-violet-500/15 px-2.5 py-1 text-xs font-semibold text-violet-400 ring-1 ring-violet-500/30 hover:bg-violet-500/25 transition-colors"
          >
            ✦ Analyse
          </button>
        </div>
        <p className="mt-1 text-xs text-slate-500">Check how well this player fits your squad.</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl bg-slate-900 ring-1 ring-white/[0.08] overflow-hidden">
      <div className="px-4 py-3 border-b border-white/[0.06]">
        <span className="text-sm font-semibold text-white">✦ AI Fit Score</span>
      </div>

      {isFetching && (
        <div className="flex items-center gap-2 px-4 py-4 text-sm text-slate-400">
          <Spinner size="sm" />
          Analysing fit…
        </div>
      )}

      {error && !isFetching && (
        <p className="px-4 py-3 text-xs text-red-400">
          {(error as { response?: { data?: { detail?: string } } }).response?.data?.detail ??
            "Analysis failed."}
        </p>
      )}

      {data && !isFetching && (
        <div className="divide-y divide-white/[0.05]">
          {/* Score + verdict */}
          <div className="px-4 py-4">
            <ScoreRing score={data.fit_score} />
          </div>

          {/* Summary */}
          <div className="px-4 py-3">
            <p className="text-xs leading-relaxed text-slate-400">{data.summary}</p>
          </div>

          {/* Strengths */}
          {data.strengths.length > 0 && (
            <div className="px-4 py-3">
              <p className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-emerald-500">
                Strengths
              </p>
              <ul className="space-y-1.5">
                {data.strengths.map((s, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <span className="mt-0.5 shrink-0 text-emerald-500">✓</span>
                    <span className="text-xs text-slate-300 leading-snug">{s}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Concerns */}
          {data.concerns.length > 0 && (
            <div className="px-4 py-3">
              <p className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-amber-500">
                Concerns
              </p>
              <ul className="space-y-1.5">
                {data.concerns.map((c, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <span className="mt-0.5 shrink-0 text-amber-500">⚠</span>
                    <span className="text-xs text-slate-300 leading-snug">{c}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
