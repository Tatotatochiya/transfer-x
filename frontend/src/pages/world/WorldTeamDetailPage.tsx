import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { Club, Paginated, Player, PlayerForm, PlayerStats, WorldTeam } from "../../types/api";
import { useAuthStore } from "../../store/auth";
import SquadTable from "../../components/players/SquadTable";
import FormBadge from "../../components/players/FormBadge";
import StatsPanel from "../../components/players/StatsPanel";
import Spinner from "../../components/ui/Spinner";
import EmptyState from "../../components/ui/EmptyState";
import SectionHeader from "../../components/ui/SectionHeader";
import Badge from "../../components/ui/Badge";
import FixturesPanel from "../../components/fixtures/FixturesPanel";

// ── Top performers ─────────────────────────────────────────────────────────────

function TopPerformers({
  players,
  formScores,
}: {
  players: Player[];
  formScores: Record<string, { score: number; trend: number | null }>;
}) {
  const ranked = players
    .filter((p) => formScores[p.id] != null)
    .sort((a, b) => (formScores[b.id]?.score ?? 0) - (formScores[a.id]?.score ?? 0))
    .slice(0, 5);

  if (ranked.length === 0) return null;

  return (
    <div className="mb-6 rounded-xl bg-slate-800/50 px-5 py-4 ring-1 ring-white/[0.06]">
      <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">
        Top Form
      </p>
      <div className="flex flex-wrap gap-2">
        {ranked.map((p) => (
          <Link key={p.id} to={`/players/market/${p.id}`} className="flex items-center gap-2 rounded-lg px-2 py-1 hover:bg-slate-700/50 transition-colors group">
            {p.photo_url ? (
              <img
                src={p.photo_url}
                alt={p.name}
                className="h-7 w-7 rounded-full object-cover ring-1 ring-white/10"
              />
            ) : (
              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-slate-700 text-xs font-bold text-slate-400">
                {p.name[0]?.toUpperCase()}
              </div>
            )}
            <span className="text-sm font-medium text-white group-hover:text-emerald-400 transition-colors">{p.name}</span>
            <FormBadge score={formScores[p.id].score} trend={formScores[p.id].trend} />
          </Link>
        ))}
      </div>
    </div>
  );
}

// ── Squad aggregate stats ──────────────────────────────────────────────────────

function SquadStatsPanel({ players }: { players: Player[] }) {
  const playerIds = players.map((p) => p.id).join(",");

  const { data: allStats } = useQuery<Record<string, PlayerStats | null>>({
    queryKey: ["squad-stats", playerIds],
    enabled: players.length > 0,
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
  });

  if (!allStats) {
    return (
      <div className="flex justify-center py-10">
        <Spinner />
      </div>
    );
  }

  const stats = Object.values(allStats).filter(Boolean) as PlayerStats[];
  if (stats.length === 0) {
    return <EmptyState title="No stats data" body="No performance stats available for this squad." />;
  }

  const totalGoals = stats.reduce((s, r) => s + (r.goals ?? 0), 0);
  const totalAssists = stats.reduce((s, r) => s + (r.assists ?? 0), 0);
  const totalApps = stats.reduce((s, r) => s + (r.appearances ?? 0), 0);
  const ratings = stats.map((r) => Number(r.avg_rating)).filter((v) => v > 0);
  const avgRating = ratings.length > 0 ? (ratings.reduce((a, b) => a + b, 0) / ratings.length).toFixed(2) : null;

  const topScorers = players
    .map((p) => ({ player: p, goals: allStats[p.id]?.goals ?? 0 }))
    .filter((e) => e.goals > 0)
    .sort((a, b) => b.goals - a.goals)
    .slice(0, 5);

  const topAssisters = players
    .map((p) => ({ player: p, assists: allStats[p.id]?.assists ?? 0 }))
    .filter((e) => e.assists > 0)
    .sort((a, b) => b.assists - a.assists)
    .slice(0, 5);

  return (
    <div className="space-y-6">
      {/* Squad aggregate */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[
          { label: "Goals", value: totalGoals },
          { label: "Assists", value: totalAssists },
          { label: "Appearances", value: totalApps },
          { label: "Avg Rating", value: avgRating ?? "—" },
        ].map((m) => (
          <div key={m.label} className="rounded-xl bg-slate-800/70 px-4 py-3 text-center">
            <p className="text-2xl font-bold text-white tabular-nums">{m.value}</p>
            <p className="mt-1 text-xs text-slate-500">{m.label}</p>
          </div>
        ))}
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {/* Top scorers */}
        {topScorers.length > 0 && (
          <div className="rounded-xl bg-slate-800/40 px-4 py-3 ring-1 ring-white/[0.06]">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">Top Scorers</p>
            {topScorers.map(({ player, goals }, i) => (
              <Link
                key={player.id}
                to={`/players/market/${player.id}`}
                className="flex items-center gap-2.5 rounded-lg px-1 py-1.5 hover:bg-slate-700/50 transition-colors group"
              >
                <span className="w-4 shrink-0 text-xs font-bold text-slate-600 tabular-nums">{i + 1}</span>
                {player.photo_url ? (
                  <img src={player.photo_url} alt={player.name} className="h-7 w-7 shrink-0 rounded-full object-cover ring-1 ring-white/10" />
                ) : (
                  <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-slate-700 text-xs font-bold text-slate-400">
                    {player.name[0]?.toUpperCase()}
                  </div>
                )}
                <span className="flex-1 truncate text-sm text-slate-300 group-hover:text-emerald-400 transition-colors">{player.name}</span>
                <span className="shrink-0 text-sm font-bold text-emerald-400 tabular-nums">{goals}g</span>
              </Link>
            ))}
          </div>
        )}

        {/* Top assisters */}
        {topAssisters.length > 0 && (
          <div className="rounded-xl bg-slate-800/40 px-4 py-3 ring-1 ring-white/[0.06]">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">Top Assisters</p>
            {topAssisters.map(({ player, assists }, i) => (
              <Link
                key={player.id}
                to={`/players/market/${player.id}`}
                className="flex items-center gap-2.5 rounded-lg px-1 py-1.5 hover:bg-slate-700/50 transition-colors group"
              >
                <span className="w-4 shrink-0 text-xs font-bold text-slate-600 tabular-nums">{i + 1}</span>
                {player.photo_url ? (
                  <img src={player.photo_url} alt={player.name} className="h-7 w-7 shrink-0 rounded-full object-cover ring-1 ring-white/10" />
                ) : (
                  <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-slate-700 text-xs font-bold text-slate-400">
                    {player.name[0]?.toUpperCase()}
                  </div>
                )}
                <span className="flex-1 truncate text-sm text-slate-300 group-hover:text-emerald-400 transition-colors">{player.name}</span>
                <span className="shrink-0 text-sm font-bold text-blue-400 tabular-nums">{assists}a</span>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────────

type Tab = "squad" | "stats" | "fixtures";

export default function WorldTeamDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { accessToken } = useAuthStore();
  const isAuthenticated = !!accessToken;

  const [claimError, setClaimError] = useState<string | null>(null);

  // Check if the current user already has a club
  const { data: myClub, isLoading: myClubLoading } = useQuery<Club>({
    queryKey: ["clubs", "me"],
    queryFn: () => api.get<Club>("/clubs/me").then((r) => r.data),
    enabled: isAuthenticated,
    retry: false,
    staleTime: 60_000,
  });

  const claimMutation = useMutation({
    mutationFn: (worldTeamId: string) =>
      api.post<Club>(`/clubs/from-world-team/${worldTeamId}`).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["clubs", "me"] });
      navigate("/club");
    },
    onError: (err: unknown) => {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Failed to claim club.";
      setClaimError(msg);
    },
  });

  const { data: team, isLoading, isError } = useQuery<WorldTeam>({
    queryKey: ["world-teams", id],
    queryFn: () => api.get<WorldTeam>(`/world/teams/${id}`).then((r) => r.data),
    enabled: !!id,
  });

  const [tab, setTab] = useState<Tab>("squad");
  const [page, setPage] = useState(1);

  const { data: squadData, isLoading: squadLoading } = useQuery<Paginated<Player>>({
    queryKey: ["world-teams", id, "players", page],
    queryFn: () =>
      api.get<Paginated<Player>>(`/world/teams/${id}/players`, { params: { page, page_size: 50 } }).then((r) => r.data),
    enabled: !!id,
  });

  const players = squadData?.items ?? [];

  // Fetch form scores for all squad players in a single batch request
  const playerIds = players.map((p) => p.id).join(",");
  const { data: formScores = {} } = useQuery<Record<string, { score: number; trend: number | null }>>({
    queryKey: ["world-teams", id, "form-scores", playerIds],
    enabled: players.length > 0,
    queryFn: async () => {
      const resp = await api
        .get<Record<string, PlayerForm>>("/players/form/batch", { params: { player_ids: playerIds } })
        .catch(() => ({ data: {} as Record<string, PlayerForm> }));
      const map: Record<string, { score: number; trend: number | null }> = {};
      for (const [pid, form] of Object.entries(resp.data)) {
        map[pid] = {
          score: Number(form.form_score),
          trend: form.trend != null ? Number(form.trend) : null,
        };
      }
      return map;
    },
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner size="lg" />
      </div>
    );
  }

  if (isError || !team) {
    return (
      <div className="rounded-xl bg-red-500/10 px-5 py-4 text-sm text-red-400 ring-1 ring-red-500/30">
        Team not found.{" "}
        <button onClick={() => navigate(-1)} className="underline">Go back</button>
      </div>
    );
  }

  const TABS: { label: string; value: Tab }[] = [
    { label: "Squad", value: "squad" },
    { label: "Squad Stats", value: "stats" },
    { label: "Fixtures", value: "fixtures" },
  ];

  return (
    <div>
      <button
        onClick={() => navigate(-1)}
        className="mb-6 flex items-center gap-1.5 text-sm text-slate-400 hover:text-white transition-colors"
      >
        ← Back
      </button>

      {/* Team header */}
      <div className="mb-8 flex items-start gap-5">
        {team.crest_url ? (
          <img
            src={team.crest_url}
            alt={team.name}
            className="h-20 w-20 shrink-0 object-contain drop-shadow-lg"
          />
        ) : (
          <div className="flex h-20 w-20 shrink-0 items-center justify-center rounded-2xl bg-slate-800 text-3xl font-black text-slate-600 ring-1 ring-white/[0.08]">
            {team.name[0]?.toUpperCase()}
          </div>
        )}

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h1 className="text-3xl font-bold text-white">{team.name}</h1>
              <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-slate-400">
                {team.country && <span>{team.country}</span>}
                {team.league_name && (
                  <>
                    {team.country && <span className="text-slate-600">·</span>}
                    <Badge variant="neutral">{team.league_name}</Badge>
                  </>
                )}
                {team.season && (
                  <>
                    <span className="text-slate-600">·</span>
                    <span>Season {team.season}</span>
                  </>
                )}
                {players.length > 0 && (
                  <>
                    <span className="text-slate-600">·</span>
                    <span>{squadData?.total ?? players.length} players</span>
                  </>
                )}
              </div>
            </div>

            {/* Claim button — only for authenticated users without a club */}
            {isAuthenticated && !myClubLoading && !myClub && id && (
              <div className="shrink-0">
                <button
                  disabled={claimMutation.isPending}
                  onClick={() => { setClaimError(null); claimMutation.mutate(id); }}
                  className="flex items-center gap-2 rounded-lg bg-emerald-500/15 px-4 py-2 text-sm font-semibold text-emerald-400 ring-1 ring-emerald-500/30 hover:bg-emerald-500/25 transition-colors disabled:opacity-50"
                >
                  {claimMutation.isPending ? "Registering…" : "Register as my club"}
                </button>
                {claimError && (
                  <p className="mt-1.5 text-xs text-red-400">{claimError}</p>
                )}
              </div>
            )}

            {/* Already has a club — can't claim */}
            {isAuthenticated && myClub && (
              <span className="shrink-0 rounded-lg bg-slate-800 px-3 py-2 text-xs text-slate-500 ring-1 ring-white/[0.06]">
                Your club: {myClub.name}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="mb-6 flex gap-2">
        {TABS.map((t) => (
          <button
            key={t.value}
            onClick={() => setTab(t.value)}
            className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
              tab === t.value
                ? "bg-emerald-500/15 text-emerald-400 ring-1 ring-emerald-500/30"
                : "bg-slate-800 text-slate-400 hover:text-white"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Squad tab */}
      {tab === "squad" && (
        <div>
          {players.length > 0 && (
            <TopPerformers players={players} formScores={formScores} />
          )}

          {squadLoading && (
            <div className="flex justify-center py-10">
              <Spinner />
            </div>
          )}

          {!squadLoading && players.length === 0 && (
            <EmptyState
              title="No squad data"
              body="No players linked to this team yet."
            />
          )}

          {!squadLoading && players.length > 0 && (
            <SquadTable players={players} formScores={formScores} />
          )}

          {/* Pagination */}
          {squadData && squadData.total > 50 && (
            <div className="mt-4 flex justify-center gap-2">
              <button
                disabled={page === 1}
                onClick={() => setPage((p) => p - 1)}
                className="rounded-lg bg-slate-800 px-3 py-1.5 text-sm text-slate-400 hover:text-white disabled:opacity-30 transition-colors"
              >
                ← Prev
              </button>
              <span className="px-3 py-1.5 text-sm text-slate-500">
                {page} / {Math.ceil(squadData.total / 50)}
              </span>
              <button
                disabled={page * 50 >= squadData.total}
                onClick={() => setPage((p) => p + 1)}
                className="rounded-lg bg-slate-800 px-3 py-1.5 text-sm text-slate-400 hover:text-white disabled:opacity-30 transition-colors"
              >
                Next →
              </button>
            </div>
          )}
        </div>
      )}

      {/* Stats tab */}
      {tab === "stats" && (
        <SquadStatsPanel players={players} />
      )}

      {/* Fixtures tab */}
      {tab === "fixtures" && (
        team.vendor_id ? (
          <FixturesPanel vendorTeamId={Number(team.vendor_id)} />
        ) : (
          <EmptyState title="No fixture data" body="This team has no vendor ID linked." />
        )
      )}
    </div>
  );
}

