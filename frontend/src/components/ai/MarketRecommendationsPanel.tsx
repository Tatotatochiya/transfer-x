import { useState } from "react";
import { Link } from "react-router-dom";

import { useMarketRecommendations } from "../../hooks/useAI";
import { positionVariant } from "../../lib/badges";
import type { PlayerPosition } from "../../types/enums";
import Badge from "../ui/Badge";
import Spinner from "../ui/Spinner";

function FitBar({ score }: { score: number }) {
  const colour =
    score >= 70 ? "bg-success" : score >= 45 ? "bg-warning-fill" : "bg-danger";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 flex-1 rounded-full bg-border overflow-hidden">
        <div className={`h-full rounded-full ${colour}`} style={{ width: `${score}%` }} />
      </div>
      <span className="w-6 text-right text-caption font-bold text-text">{score}</span>
    </div>
  );
}

interface MarketRecommendationsPanelProps {
  positionFilter?: string;
  maxBudget?: number;
}

export function MarketRecommendationsPanel({
  positionFilter,
  maxBudget,
}: MarketRecommendationsPanelProps) {
  const [open, setOpen] = useState(true);
  const [enabled, setEnabled] = useState(false);

  const { data, isFetching, error } = useMarketRecommendations(
    { position: positionFilter, max_budget: maxBudget },
    enabled,
  );

  return (
    <div className="mb-4 rounded-xl bg-surface ring-1 ring-ai-ring">
      <div className="flex items-center justify-between px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="text-body font-semibold text-text">✦ Recommended for You</span>
          {data && (
            <span className="text-small text-text-muted">{data.total_candidates} candidates scanned</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {!enabled ? (
            <button
              onClick={() => setEnabled(true)}
              className="rounded-lg bg-ai-bg px-3 py-1 text-caption font-semibold text-ai-text ring-1 ring-ai-ring hover:brightness-95 transition-colors"
            >
              Generate
            </button>
          ) : (
            <button
              onClick={() => setOpen((v) => !v)}
              className="text-small text-text-muted hover:text-text-secondary transition-colors"
            >
              {open ? "Hide" : "Show"}
            </button>
          )}
        </div>
      </div>

      {enabled && open && (
        <div className="border-t border-rule">
          {isFetching && (
            <div className="flex items-center gap-2 px-4 py-4 text-small text-text-muted">
              <Spinner size="sm" />
              Finding best fits for your squad…
            </div>
          )}

          {error && !isFetching && (
            <p className="px-4 py-3 text-body text-danger-text">
              {(error as { response?: { data?: { detail?: string } } }).response?.data?.detail ??
                "Failed to fetch recommendations."}
            </p>
          )}

          {data && !isFetching && data.recommendations.length === 0 && (
            <p className="px-4 py-4 text-small text-text-muted">
              No matching players on the market right now.
            </p>
          )}

          {data && !isFetching && data.recommendations.length > 0 && (
            <ul className="divide-y divide-rule-faint">
              {data.recommendations.map((rec) => (
                <li key={rec.player_id} className="flex items-center gap-3 px-4 py-3">
                  <div className="min-w-0 flex-1">
                    <div className="mb-0.5 flex items-center gap-2">
                      <Link
                        to={`/players/market/${rec.player_id}`}
                        className="truncate text-body font-semibold text-text hover:text-ai-text transition-colors"
                      >
                        {rec.name}
                      </Link>
                      {rec.position && (
                        <Badge variant={positionVariant(rec.position as PlayerPosition)}>
                          {rec.position}
                        </Badge>
                      )}
                    </div>
                    <p className="text-small text-text-muted leading-relaxed">{rec.reason}</p>
                  </div>
                  <div className="w-24 shrink-0">
                    <FitBar score={rec.fit_score} />
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
