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

interface VendorSyncRun {
  id: string;
  vendor: string;
  operation: string;
  params: Record<string, unknown> | null;
  success: boolean;
  result: Record<string, unknown> | null;
  error: string | null;
  triggered_by_user_id: string | null;
  triggered_by_email: string | null;
  started_at: string;
  finished_at: string;
  duration_ms: number;
}

function ResultBox({ data }: { data: unknown }) {
  return (
    <pre className="mt-3 rounded-lg bg-surface-inset px-4 py-3 text-xs text-success-text overflow-x-auto ring-1 ring-border">
      {JSON.stringify(data, null, 2)}
    </pre>
  );
}

const OPERATION_LABELS: Record<string, string> = {
  sync_league: "Sync League",
  sync_team: "Sync Team",
  sync_player: "Sync Player",
  compute_form: "Compute Form",
};

function formatOperation(op: string): string {
  return OPERATION_LABELS[op] ?? op;
}

function formatParams(op: string, params: Record<string, unknown> | null): string {
  if (!params) return "—";
  switch (op) {
    case "sync_league":
      return `league ${params.league_id}, season ${params.season}`;
    case "sync_team":
      return `team ${params.team_id}, season ${params.season}`;
    case "sync_player":
      return `player ${String(params.player_id).slice(0, 8)}…, season ${params.season}`;
    case "compute_form":
      return params.season ? `season ${params.season}` : "all seasons";
    default:
      return "—";
  }
}

function formatResult(op: string, result: Record<string, unknown> | null): string {
  if (!result) return "—";
  switch (op) {
    case "sync_league":
    case "sync_team":
      return `${result.players_created ?? 0} created, ${result.players_updated ?? 0} updated, ${result.snapshots_created ?? 0} snapshots`;
    case "sync_player":
      return `${result.snapshots_created ?? 0} snapshots`;
    case "compute_form":
      return `${result.players_updated ?? 0} players updated`;
    default:
      return "—";
  }
}

function formatDuration(ms: number): string {
  return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(1)}s`;
}

export default function AdminVendorPage() {
  // Sync status
  const { data: states, isLoading: statesLoading, refetch: refetchStates } = useQuery<VendorSyncState[]>({
    queryKey: ["vendor", "status"],
    queryFn: () => api.get<VendorSyncState[]>("/vendor/status").then((r) => r.data),
  });

  // Recent sync runs (per-run breakdown)
  const { data: runs, isLoading: runsLoading, refetch: refetchRuns } = useQuery<VendorSyncRun[]>({
    queryKey: ["vendor", "runs"],
    queryFn: () => api.get<VendorSyncRun[]>("/vendor/runs?limit=50").then((r) => r.data),
  });
  const [expandedRunId, setExpandedRunId] = useState<string | null>(null);

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
    onSettled: () => refetchRuns(),
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
    onSettled: () => refetchRuns(),
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
    onSettled: () => refetchRuns(),
  });

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-text">Vendor Sync</h1>
        <p className="mt-1 text-sm text-text-muted">
          API-Football data sync controls — superuser only
        </p>
      </div>

      {/* Sync state */}
      <Card className="mb-6">
        <div className="mb-3 flex items-center justify-between">
          <p className="text-xs font-semibold uppercase tracking-wider text-text-muted">Sync Status</p>
          <button
            onClick={() => refetchStates()}
            className="text-xs text-text-muted hover:text-text transition-colors"
          >
            Refresh
          </button>
        </div>
        {statesLoading ? (
          <div className="flex justify-center py-4"><Spinner size="sm" /></div>
        ) : !states?.length ? (
          <p className="text-sm text-text-muted">No sync history.</p>
        ) : (
          <div className="space-y-2">
            {states.map((s) => (
              <div key={s.vendor} className="flex items-center justify-between rounded-lg bg-surface-inset px-3 py-2">
                <div>
                  <span className="text-sm font-medium text-text">{s.vendor}</span>
                  <span className={`ml-3 text-xs font-medium ${s.last_success ? "text-success-text" : s.last_success === false ? "text-danger-text" : "text-text-muted"}`}>
                    {s.last_success === true ? "OK" : s.last_success === false ? "FAILED" : "Never synced"}
                  </span>
                </div>
                <div className="text-right">
                  <p className="text-xs text-text-muted">
                    {s.last_synced_at ? formatDate(s.last_synced_at) : "—"}
                  </p>
                  {s.last_error && (
                    <p className="text-xs text-danger-text truncate max-w-xs" title={s.last_error}>
                      {s.last_error}
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Recent sync runs — per-run breakdown */}
      <Card className="mb-6">
        <div className="mb-3 flex items-center justify-between">
          <p className="text-xs font-semibold uppercase tracking-wider text-text-muted">Recent Syncs</p>
          <button
            onClick={() => refetchRuns()}
            className="text-xs text-text-muted hover:text-text transition-colors"
          >
            Refresh
          </button>
        </div>
        {runsLoading ? (
          <div className="flex justify-center py-4"><Spinner size="sm" /></div>
        ) : !runs?.length ? (
          <p className="text-sm text-text-muted">No sync runs yet.</p>
        ) : (
          <div className="space-y-1">
            {runs.map((run) => (
              <div key={run.id}>
                <button
                  type="button"
                  onClick={() => setExpandedRunId(expandedRunId === run.id ? null : run.id)}
                  className="w-full flex flex-wrap items-center justify-between gap-2 rounded-lg bg-surface-inset px-3 py-2 text-left hover:bg-border transition-colors"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <span className={`text-xs font-medium ${run.success ? "text-success-text" : "text-danger-text"}`}>
                      {run.success ? "OK" : "FAILED"}
                    </span>
                    <span className="text-sm font-medium text-text shrink-0">{formatOperation(run.operation)}</span>
                    <span className="text-xs text-text-muted truncate">{formatParams(run.operation, run.params)}</span>
                  </div>
                  <div className="flex max-w-full flex-wrap items-center justify-end gap-x-3 gap-y-0.5 text-right">
                    <span className="text-xs text-text-muted">{formatResult(run.operation, run.result)}</span>
                    <span className="text-xs text-text-muted">{formatDuration(run.duration_ms)}</span>
                    <span className="text-xs text-text-muted">{formatDate(run.started_at)}</span>
                  </div>
                </button>
                {expandedRunId === run.id && (
                  <div className="ml-3 mt-1 mb-2 rounded-lg bg-surface-inset px-4 py-3 ring-1 ring-border">
                    <p className="text-xs text-text-muted">
                      Triggered by {run.triggered_by_email ?? "unknown"} · started {formatDate(run.started_at)} · took {formatDuration(run.duration_ms)}
                    </p>
                    {run.params && (
                      <>
                        <p className="mb-1 mt-3 text-xs font-semibold uppercase tracking-wider text-text-muted">Params</p>
                        <ResultBox data={run.params} />
                      </>
                    )}
                    {run.result && (
                      <>
                        <p className="mb-1 mt-3 text-xs font-semibold uppercase tracking-wider text-text-muted">Result</p>
                        <ResultBox data={run.result} />
                      </>
                    )}
                    {run.error && (
                      <>
                        <p className="mb-1 mt-3 text-xs font-semibold uppercase tracking-wider text-danger-text">Error</p>
                        <p className="whitespace-pre-wrap break-words text-xs text-danger-text">{run.error}</p>
                      </>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* ── Sync League ── */}
        <Card>
          <p className="mb-4 text-xs font-semibold uppercase tracking-wider text-text-muted">
            Sync League
          </p>
          <p className="mb-4 text-xs text-text-muted">
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
              <label className="mb-1 block text-xs text-text-muted">League ID (API-Football)</label>
              <input
                type="number"
                value={leagueId}
                onChange={(e) => setLeagueId(e.target.value)}
                placeholder="e.g. 39 = Premier League"
                className="w-full rounded-lg bg-surface px-3 py-2 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-warning-fill"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-text-muted">Season</label>
              <input
                type="number"
                value={season}
                onChange={(e) => setSeason(e.target.value)}
                placeholder="e.g. 2024"
                className="w-full rounded-lg bg-surface px-3 py-2 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-warning-fill"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-text-muted">Sleep between requests (ms)</label>
              <input
                type="number"
                value={sleepMs}
                onChange={(e) => setSleepMs(e.target.value)}
                className="w-full rounded-lg bg-surface px-3 py-2 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-warning-fill"
              />
            </div>
            {leagueMutation.isError && (
              <p className="text-xs text-danger-text">{getApiError(leagueMutation.error, "Sync failed.")}</p>
            )}
            <Button type="submit" variant="primary" size="sm" loading={leagueMutation.isPending}>
              Run League Sync
            </Button>
          </form>
          {leagueResult && <ResultBox data={leagueResult} />}
        </Card>

        {/* ── Sync Team ── */}
        <Card>
          <p className="mb-4 text-xs font-semibold uppercase tracking-wider text-text-muted">
            Sync Team
          </p>
          <p className="mb-4 text-xs text-text-muted">
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
              <label className="mb-1 block text-xs text-text-muted">Team ID (API-Football)</label>
              <input
                type="number"
                value={teamId}
                onChange={(e) => setTeamId(e.target.value)}
                placeholder="e.g. 33 = Man Utd"
                className="w-full rounded-lg bg-surface px-3 py-2 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-warning-fill"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-text-muted">Season</label>
              <input
                type="number"
                value={teamSeason}
                onChange={(e) => setTeamSeason(e.target.value)}
                placeholder="e.g. 2024"
                className="w-full rounded-lg bg-surface px-3 py-2 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-warning-fill"
              />
            </div>
            {teamMutation.isError && (
              <p className="text-xs text-danger-text">{getApiError(teamMutation.error, "Sync failed.")}</p>
            )}
            <Button type="submit" variant="primary" size="sm" loading={teamMutation.isPending}>
              Run Team Sync
            </Button>
          </form>
          {teamResult && <ResultBox data={teamResult} />}
        </Card>

        {/* ── Compute Form ── */}
        <Card>
          <p className="mb-4 text-xs font-semibold uppercase tracking-wider text-text-muted">
            Compute Player Form
          </p>
          <p className="mb-4 text-xs text-text-muted">
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
              <label className="mb-1 block text-xs text-text-muted">Season (blank = all)</label>
              <input
                type="text"
                value={formSeason}
                onChange={(e) => setFormSeason(e.target.value)}
                placeholder="e.g. 2024/2025"
                className="w-full rounded-lg bg-surface px-3 py-2 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-warning-fill"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-text-muted">Window (last N games)</label>
              <input
                type="number"
                value={windowGames}
                onChange={(e) => setWindowGames(e.target.value)}
                className="w-full rounded-lg bg-surface px-3 py-2 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-warning-fill"
              />
            </div>
            {formMutation.isError && (
              <p className="text-xs text-danger-text">{getApiError(formMutation.error, "Compute failed.")}</p>
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
