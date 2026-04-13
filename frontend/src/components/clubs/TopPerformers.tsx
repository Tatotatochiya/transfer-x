import { Link } from "react-router-dom";
import type { PlayerDetail } from "../../types/api";
import FormBadge from "../players/FormBadge";

export default function TopPerformers({
  players,
  formScores,
}: {
  players: PlayerDetail[];
  formScores: Record<string, { score: number; trend: number | null }>;
}) {
  const ranked = players
    .filter((p) => formScores[p.id] != null)
    .sort((a, b) => (formScores[b.id]?.score ?? 0) - (formScores[a.id]?.score ?? 0))
    .slice(0, 5);

  if (ranked.length === 0) return null;

  return (
    <div className="mb-6 rounded-xl bg-slate-800/50 px-5 py-4 ring-1 ring-white/[0.06]">
      <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">Top Form</p>
      <div className="flex flex-wrap gap-3">
        {ranked.map((p) => (
          <Link
            key={p.id}
            to={`/players/market/${p.id}`}
            className="flex items-center gap-2 rounded-lg hover:bg-slate-700/50 px-2 py-1 transition-colors"
          >
            {p.photo_url ? (
              <img src={p.photo_url} alt={p.name} loading="lazy" className="h-7 w-7 rounded-full object-cover ring-1 ring-white/10" />
            ) : (
              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-slate-700 text-xs font-bold text-slate-400">
                {p.name[0]?.toUpperCase()}
              </div>
            )}
            <span className="text-sm font-medium text-white hover:text-emerald-400 transition-colors">
              {p.name}
            </span>
            <FormBadge score={formScores[p.id].score} trend={formScores[p.id].trend} />
          </Link>
        ))}
      </div>
    </div>
  );
}
