import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import api from "../../lib/api";
import type { PlayerDetail, PlayerStats } from "../../types/api";
import SectionHeader from "../ui/SectionHeader";
import Spinner from "../ui/Spinner";

export default function SquadStatsPanel({ players }: { players: PlayerDetail[] }) {
  const playerIds = players.map((p) => p.id).join(",");

  const { data: allStats } = useQuery<Record<string, PlayerStats | null>>({
    queryKey: ["squad-stats-batch", playerIds],
    queryFn: async () => {
      const resp = await api.get<Record<string, PlayerStats[]>>("/players/stats/batch", {
        params: { player_ids: playerIds },
      });
      const map: Record<string, PlayerStats | null> = {};
      for (const [id, statsList] of Object.entries(resp.data)) {
        map[id] = statsList.sort((a, b) => b.appearances - a.appearances)[0] ?? null;
      }
      return map;
    },
    enabled: players.length > 0,
    staleTime: 120_000,
  });

  if (players.length === 0) return null;

  if (!allStats) {
    return (
      <div className="flex justify-center py-8">
        <Spinner size="lg" />
      </div>
    );
  }

  const statsArr = Object.values(allStats).filter((s): s is PlayerStats => s != null);
  const totalGoals   = statsArr.reduce((sum, s) => sum + (s.goals ?? 0), 0);
  const totalAssists = statsArr.reduce((sum, s) => sum + (s.assists ?? 0), 0);
  const totalApps    = statsArr.reduce((sum, s) => sum + (s.appearances ?? 0), 0);
  const ratings      = statsArr.map((s) => s.avg_rating).filter((r): r is number => r != null && r > 0);
  const avgRating    = ratings.length > 0
    ? (ratings.reduce((a, b) => a + b, 0) / ratings.length).toFixed(2)
    : null;

  const topScorers = players
    .filter((p) => allStats[p.id] && (allStats[p.id]!.goals ?? 0) > 0)
    .sort((a, b) => (allStats[b.id]?.goals ?? 0) - (allStats[a.id]?.goals ?? 0))
    .slice(0, 5);

  const topAssisters = players
    .filter((p) => allStats[p.id] && (allStats[p.id]!.assists ?? 0) > 0)
    .sort((a, b) => (allStats[b.id]?.assists ?? 0) - (allStats[a.id]?.assists ?? 0))
    .slice(0, 5);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[
          { label: "Goals",       value: totalGoals,       colour: "text-emerald-400" },
          { label: "Assists",     value: totalAssists,     colour: "text-blue-400" },
          { label: "Appearances", value: totalApps,        colour: "text-white" },
          { label: "Avg Rating",  value: avgRating ?? "—", colour: "text-amber-400" },
        ].map(({ label, value, colour }) => (
          <div key={label} className="flex flex-col items-center rounded-xl bg-slate-800/70 px-4 py-4">
            <span className={`text-2xl font-bold tabular-nums ${colour}`}>{value}</span>
            <span className="mt-1 text-xs text-slate-500">{label}</span>
          </div>
        ))}
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        {topScorers.length > 0 && (
          <div className="rounded-xl bg-slate-800/40 px-4 py-3 ring-1 ring-white/[0.06]">
            <SectionHeader title="Top Scorers" />
            <div className="mt-2 space-y-1">
              {topScorers.map((p, i) => (
                <Link
                  key={p.id}
                  to={`/players/market/${p.id}`}
                  className="flex items-center gap-2.5 rounded-lg px-2 py-1.5 hover:bg-slate-700/50 transition-colors group"
                >
                  <span className="w-4 shrink-0 text-xs font-bold text-slate-600 tabular-nums">{i + 1}</span>
                  {p.photo_url ? (
                    <img src={p.photo_url} alt={p.name} className="h-7 w-7 shrink-0 rounded-full object-cover ring-1 ring-white/10" />
                  ) : (
                    <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-slate-700 text-xs font-bold text-slate-400">
                      {p.name[0]?.toUpperCase()}
                    </div>
                  )}
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-white group-hover:text-emerald-400 transition-colors">{p.name}</p>
                    {p.position && <p className="text-xs text-slate-600">{p.position}</p>}
                  </div>
                  <span className="shrink-0 text-sm font-bold text-emerald-400 tabular-nums">
                    {allStats[p.id]?.goals}g
                  </span>
                </Link>
              ))}
            </div>
          </div>
        )}

        {topAssisters.length > 0 && (
          <div className="rounded-xl bg-slate-800/40 px-4 py-3 ring-1 ring-white/[0.06]">
            <SectionHeader title="Top Assisters" />
            <div className="mt-2 space-y-1">
              {topAssisters.map((p, i) => (
                <Link
                  key={p.id}
                  to={`/players/market/${p.id}`}
                  className="flex items-center gap-2.5 rounded-lg px-2 py-1.5 hover:bg-slate-700/50 transition-colors group"
                >
                  <span className="w-4 shrink-0 text-xs font-bold text-slate-600 tabular-nums">{i + 1}</span>
                  {p.photo_url ? (
                    <img src={p.photo_url} alt={p.name} className="h-7 w-7 shrink-0 rounded-full object-cover ring-1 ring-white/10" />
                  ) : (
                    <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-slate-700 text-xs font-bold text-slate-400">
                      {p.name[0]?.toUpperCase()}
                    </div>
                  )}
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-white group-hover:text-emerald-400 transition-colors">{p.name}</p>
                    {p.position && <p className="text-xs text-slate-600">{p.position}</p>}
                  </div>
                  <span className="shrink-0 text-sm font-bold text-blue-400 tabular-nums">
                    {allStats[p.id]?.assists}a
                  </span>
                </Link>
              ))}
            </div>
          </div>
        )}
      </div>

      {statsArr.length === 0 && (
        <p className="py-4 text-center text-sm text-slate-500">No statistics available for this squad.</p>
      )}
    </div>
  );
}
