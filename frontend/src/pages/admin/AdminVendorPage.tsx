import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import api from "../../lib/api";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import Spinner from "../../components/ui/Spinner";
import { formatDate, getApiError } from "../../lib/utils";

interface VendorSyncState {
  vendor: string;
  last_synced_at: string | null;
  last_success: boolean | null;
  last_error: string | null;
}

interface SyncLeagueResult {
  players_upserted?: number;
  [key: string]: unknown;
}

interface ComputeFormResult {
  players_updated: number;
}

function ResultBox({ data }: { data: unknown }) {
  return (
    <pre className="mt-3 rounded-lg bg-slate-950 px-4 py-3 text-xs text-emerald-400 overflow-x-auto ring-1 ring-white/[0.06]">
      {JSON.stringify(data, null, 2)}
    </pre>
  );
}

export default function AdminVendorPage() {
  // Sync status
  const { data: states, isLoading: statesLoading, refetch: refetchStates } = useQuery<VendorSyncState[]>({
    queryKey: ["vendor", "status"],
    queryFn: () => api.get<VendorSyncState[]>("/vendor/status").then((r) => r.data),
  });

  // Sync league form
  const [leagueId, setLeagueId]   = useState("39");
  const [season,   setSeason]     = useState("2024");
  const [sleepMs,  setSleepMs]    = useState("0");
  const [leagueResult, setLeagueResult] = useState<unknown>(null);

  const leagueMutation = useMutation({
    mutationFn: (body: object) =>
      api.post<SyncLeagueResult>("/vendor/sync/league", body).then((r) => r.data),
    onSuccess: (data) => {
      setLeagueResult(data);
      refetchStates();
    },
  });

  // Sync team form
  const [teamId,    setTeamId]    = useState("");
  const [teamSeason, setTeamSeason] = useState("2024");
  const [teamResult, setTeamResult] = useState<unknown>(null);

  const teamMutation = useMutation({
    mutationFn: (body: object) =>
      api.post("/vendor/sync/team", body).then((r) => r.data),
    onSuccess: (data) => {
      setTeamResult(data);
      refetchStates();
    },
  });

  // Compute form
  const [formSeason, setFormSeason]   = useState("");
  const [windowGames, setWindowGames] = useState("5");
  const [formResult, setFormResult]   = useState<unknown>(null);

  const formMutation = useMutation({
    mutationFn: (body: object) =>
      api.post<ComputeFormResult>("/vendor/compute-form", body).then((r) => r.data),
    onSuccess: (data) => {
      setFormResult(data);
    },
  });

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white">Vendor Sync</h1>
        <p className="mt-1 text-sm text-slate-400">
          API-Football data sync controls — superuser only
        </p>
      </div>

      {/* Sync state */}
      <Card className="mb-6">
        <div className="mb-3 flex items-center justify-between">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Sync Status</p>
          <button
            onClick={() => refetchStates()}
            className="text-xs text-slate-500 hover:text-white transition-colors"
          >
            Refresh
          </button>
        </div>
        {statesLoading ? (
          <div className="flex justify-center py-4"><Spinner size="sm" /></div>
        ) : !states?.length ? (
          <p className="text-sm text-slate-500">No sync history.</p>
        ) : (
          <div className="space-y-2">
            {states.map((s) => (
              <div key={s.vendor} className="flex items-center justify-between rounded-lg bg-slate-800/60 px-3 py-2">
                <div>
                  <span className="text-sm font-medium text-white">{s.vendor}</span>
                  <span className={`ml-3 text-xs font-medium ${s.last_success ? "text-emerald-400" : s.last_success === false ? "text-red-400" : "text-slate-500"}`}>
                    {s.last_success === true ? "OK" : s.last_success === false ? "FAILED" : "Never synced"}
                  </span>
                </div>
                <div className="text-right">
                  <p className="text-xs text-slate-500">
                    {s.last_synced_at ? formatDate(s.last_synced_at) : "—"}
                  </p>
                  {s.last_error && (
                    <p className="text-xs text-red-400 truncate max-w-xs" title={s.last_error}>
                      {s.last_error}
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* ── Sync League ── */}
        <Card>
          <p className="mb-4 text-xs font-semibold uppercase tracking-wider text-slate-400">
            Sync League
          </p>
          <p className="mb-4 text-xs text-slate-500">
            Fetches all teams + players for a league/season from API-Football. Can take several minutes on large leagues.
          </p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              leagueMutation.mutate({
                league_id: parseInt(leagueId),
                season: parseInt(season),
                sleep_ms: parseInt(sleepMs),
              });
            }}
            className="space-y-3"
          >
            <div>
              <label className="mb-1 block text-xs text-slate-400">League ID (API-Football)</label>
              <input
                type="number"
                value={leagueId}
                onChange={(e) => setLeagueId(e.target.value)}
                placeholder="e.g. 39 = Premier League"
                className="w-full rounded-lg bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-amber-500"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-slate-400">Season</label>
              <input
                type="number"
                value={season}
                onChange={(e) => setSeason(e.target.value)}
                placeholder="e.g. 2024"
                className="w-full rounded-lg bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-amber-500"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-slate-400">Sleep between requests (ms)</label>
              <input
                type="number"
                value={sleepMs}
                onChange={(e) => setSleepMs(e.target.value)}
                className="w-full rounded-lg bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-amber-500"
              />
            </div>
            {leagueMutation.isError && (
              <p className="text-xs text-red-400">{getApiError(leagueMutation.error, "Sync failed.")}</p>
            )}
            <Button type="submit" variant="primary" size="sm" loading={leagueMutation.isPending}>
              Run League Sync
            </Button>
          </form>
          {leagueResult && <ResultBox data={leagueResult} />}
        </Card>

        {/* ── Sync Team ── */}
        <Card>
          <p className="mb-4 text-xs font-semibold uppercase tracking-wider text-slate-400">
            Sync Team
          </p>
          <p className="mb-4 text-xs text-slate-500">
            Fetches stats for all players of a single team. Faster than a full league sync.
          </p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              teamMutation.mutate({
                team_id: parseInt(teamId),
                season: parseInt(teamSeason),
              });
            }}
            className="space-y-3"
          >
            <div>
              <label className="mb-1 block text-xs text-slate-400">Team ID (API-Football)</label>
              <input
                type="number"
                value={teamId}
                onChange={(e) => setTeamId(e.target.value)}
                placeholder="e.g. 33 = Man Utd"
                className="w-full rounded-lg bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-amber-500"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-slate-400">Season</label>
              <input
                type="number"
                value={teamSeason}
                onChange={(e) => setTeamSeason(e.target.value)}
                placeholder="e.g. 2024"
                className="w-full rounded-lg bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-amber-500"
              />
            </div>
            {teamMutation.isError && (
              <p className="text-xs text-red-400">{getApiError(teamMutation.error, "Sync failed.")}</p>
            )}
            <Button type="submit" variant="primary" size="sm" loading={teamMutation.isPending}>
              Run Team Sync
            </Button>
          </form>
          {teamResult && <ResultBox data={teamResult} />}
        </Card>

        {/* ── Compute Form ── */}
        <Card>
          <p className="mb-4 text-xs font-semibold uppercase tracking-wider text-slate-400">
            Compute Player Form
          </p>
          <p className="mb-4 text-xs text-slate-500">
            Recalculates form scores for all players based on existing stats snapshots. No API calls made.
          </p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              formMutation.mutate({
                ...(formSeason && { season: formSeason }),
                window_games: parseInt(windowGames),
              });
            }}
            className="space-y-3"
          >
            <div>
              <label className="mb-1 block text-xs text-slate-400">Season (blank = all)</label>
              <input
                type="text"
                value={formSeason}
                onChange={(e) => setFormSeason(e.target.value)}
                placeholder="e.g. 2024/2025"
                className="w-full rounded-lg bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-amber-500"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-slate-400">Window (last N games)</label>
              <input
                type="number"
                value={windowGames}
                onChange={(e) => setWindowGames(e.target.value)}
                className="w-full rounded-lg bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-amber-500"
              />
            </div>
            {formMutation.isError && (
              <p className="text-xs text-red-400">{getApiError(formMutation.error, "Compute failed.")}</p>
            )}
            <Button type="submit" variant="primary" size="sm" loading={formMutation.isPending}>
              Compute Form
            </Button>
          </form>
          {formResult && <ResultBox data={formResult} />}
        </Card>
      </div>
    </div>
  );
}
