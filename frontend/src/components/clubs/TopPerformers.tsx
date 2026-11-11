import { Link } from "react-router-dom";
import type { PlayerDetail } from "../../types/api";
import FormBadge from "../players/FormBadge";
import FallbackImage from "../ui/FallbackImage";

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
    <div className="mb-6 rounded-xl bg-surface px-5 py-4 ring-1 ring-border">
      <p className="mb-3 text-caption font-semibold text-text-secondary">Top form</p>
      <div className="flex flex-wrap gap-3">
        {ranked.map((p) => (
          <Link
            key={p.id}
            to={`/players/market/${p.id}`}
            className="flex items-center gap-2 rounded-lg hover:bg-surface-inset px-2 py-1 transition-colors"
          >
            <FallbackImage src={p.photo_url} name={p.name} sizeClass="h-7 w-7 text-caption" colorClass="bg-surface-inset text-text-muted" className={p.photo_url ? "ring-1 ring-border" : ""} />
            <span className="text-body font-medium text-text hover:text-accent transition-colors">
              {p.name}
            </span>
            <FormBadge score={formScores[p.id].score} trend={formScores[p.id].trend} />
          </Link>
        ))}
      </div>
    </div>
  );
}
