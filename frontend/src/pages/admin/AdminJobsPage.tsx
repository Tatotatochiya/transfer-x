import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import { formatDateTime, getApiError } from "../../lib/utils";
import Badge, { type BadgeVariant } from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Modal from "../../components/ui/Modal";
import Spinner from "../../components/ui/Spinner";

/** Admin → Jobs (docs/feature_spec/scheduled-data-refresh.md): every
 *  scheduled job, what's running, recent runs, and each run's log. */

interface ScheduledJob {
  id: string;
  label: string;
  where: "worker" | "web app";
  schedule: string;
  last_run_at: string | null;
  last_status: string | null;
  last_error: string | null;
  next_run_at: string | null;
  running: boolean;
  overdue_since: string | null;
}

interface JobRun {
  id: string | null;
  job: string;
  parent_id?: string | null;
  trigger: string;
  service: string;
  status: string;
  started_at: string;
  finished_at?: string | null;
  duration_ms?: number | null;
  summary?: Record<string, unknown> | null;
  error?: string | null;
  label?: string;
}

interface RunDetail extends JobRun {
  steps: JobRun[];
  log_lines: number;
}

interface LogLine { id: number; at: string; level: string; logger: string; message: string }

const STATUS: Record<string, { label: string; variant: BadgeVariant }> = {
  running:   { label: "Running",   variant: "info" },
  succeeded: { label: "Succeeded", variant: "success" },
  partial:   { label: "Partial",   variant: "warning" },
  failed:    { label: "Failed",    variant: "danger" },
  skipped:   { label: "Skipped",   variant: "neutral" },
  lost:      { label: "Lost",      variant: "danger" },
};

const SUMMARY_LABELS: Record<string, string> = {
  leagues: "Leagues", players_updated: "Players updated", players_created: "New players", snapshots: "Stat snapshots",
  injuries_new: "New injury records", matches_new: "New matches", ratings: "Match ratings",
  fixture_counts: "Club fixture counts", form_updated: "Form scores", valuations: "Valuations",
  valuations_skipped: "Not eligible for a valuation", api_calls: "API calls", api_remaining: "API requests left that day",
};

export function StatusBadge({ status }: { status: string | null }) {
  if (!status) return <span className="text-text-muted">—</span>;
  const s = STATUS[status] ?? { label: status, variant: "neutral" as BadgeVariant };
  return <Badge variant={s.variant}>{s.label}</Badge>;
}

function duration(ms?: number | null): string {
  if (ms == null) return "—";
  const s = Math.round(ms / 1000);
  return s >= 60 ? `${Math.floor(s / 60)}m ${String(s % 60).padStart(2, "0")}s` : `${s}s`;
}

function since(iso: string): string {
  const mins = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  return mins < 60 ? `${mins} min` : `${Math.floor(mins / 60)}h ${mins % 60}m`;
}

const LEVEL_COLOUR: Record<string, string> = {
  ERROR: "text-danger-text", CRITICAL: "text-danger-text", WARNING: "text-warning-text",
};

function RunLog({ runId }: { runId: string }) {
  const [level, setLevel] = useState<"" | "WARNING" | "ERROR">("");
  const [search, setSearch] = useState("");
  const [lines, setLines] = useState<LogLine[]>([]);
  const [running, setRunning] = useState(false);
  const [loading, setLoading] = useState(true);
  const lastId = useRef(0);

  // Load from the start whenever the filters change; then, while the run is
  // going, poll for new lines every 3 seconds (the live tail).
  useEffect(() => {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    lastId.current = 0;
    setLines([]);
    setLoading(true);
    const load = async () => {
      try {
        const { data } = await api.get<{ lines: LogLine[]; running: boolean }>(`/admin/jobs/runs/${runId}/logs`, {
          params: { after: lastId.current, ...(level && { level }), ...(search.trim() && { q: search.trim() }) },
        });
        if (stopped) return;
        if (data.lines.length) {
          lastId.current = data.lines[data.lines.length - 1].id;
          setLines((prev) => [...prev, ...data.lines]);
        }
        setRunning(data.running);
        setLoading(false);
        if (data.running) timer = setTimeout(load, 3000);
      } catch {
        if (!stopped) setLoading(false);
      }
    };
    const debounce = setTimeout(load, search ? 300 : 0);
    return () => { stopped = true; clearTimeout(debounce); if (timer) clearTimeout(timer); };
  }, [runId, level, search]);

  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <select
          aria-label="Log level"
          value={level}
          onChange={(e) => setLevel(e.target.value as "" | "WARNING" | "ERROR")}
          className="rounded-lg bg-surface px-2 py-1 text-xs ring-1 ring-input-border"
        >
          <option value="">All lines</option>
          <option value="WARNING">Warnings and errors</option>
          <option value="ERROR">Errors only</option>
        </select>
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search the log"
          aria-label="Search the log"
          className="min-w-0 flex-1 rounded-lg bg-surface px-2 py-1 text-xs ring-1 ring-input-border"
        />
        {running && <span className="text-xs font-semibold text-accent">● Live</span>}
      </div>
      <div className="max-h-80 overflow-y-auto rounded-lg bg-surface-inset p-2 font-mono text-[11px] leading-relaxed">
        {loading ? (
          <Spinner size="sm" />
        ) : lines.length === 0 ? (
          <p className="text-text-muted">No log lines{level || search ? " match" : ""}.</p>
        ) : (
          lines.map((l) => (
            <div key={l.id} className="whitespace-pre-wrap break-words">
              <span className="text-text-muted">{new Date(l.at).toLocaleTimeString("en-GB")}</span>{" "}
              <span className={LEVEL_COLOUR[l.level] ?? "text-text-secondary"}>{l.level.padEnd(7)}</span>{" "}
              <span className="text-text">{l.message}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function RunDetailModal({ runId, onClose }: { runId: string; onClose: () => void }) {
  const { data } = useQuery<RunDetail>({
    queryKey: ["admin", "job-run", runId],
    queryFn: () => api.get<RunDetail>(`/admin/jobs/runs/${runId}`).then((r) => r.data),
    refetchInterval: (q) => (q.state.data?.status === "running" ? 5000 : false),
  });
  const summary = Object.entries(data?.summary ?? {}).filter(([k]) => SUMMARY_LABELS[k]);
  const failures = (data?.summary?.failures as string[] | undefined) ?? [];
  const moved = (data?.summary?.seasons_moved as string[] | undefined) ?? [];
  return (
    <Modal open onClose={onClose} title={data ? `${data.job} · ${formatDateTime(data.started_at)}` : "Run"} size="xl">
      {!data ? (
        <div className="flex justify-center py-10"><Spinner /></div>
      ) : (
        <div className="space-y-4 px-6 py-5">
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <StatusBadge status={data.status} />
            <span className="text-text-muted">{data.trigger} · {data.service} · {duration(data.duration_ms)}</span>
          </div>
          {data.error && (
            <p className="rounded-lg bg-danger-bg px-3 py-2 text-xs text-danger-text ring-1 ring-danger-border">{data.error}</p>
          )}
          {summary.length > 0 && (
            <dl className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm sm:grid-cols-3">
              {summary.map(([k, v]) => (
                <div key={k}>
                  <dt className="text-xs text-text-muted">{SUMMARY_LABELS[k]}</dt>
                  <dd className="font-semibold tabular-nums text-text">{typeof v === "number" ? v.toLocaleString("en-GB") : String(v)}</dd>
                </div>
              ))}
            </dl>
          )}
          {moved.length > 0 && <p className="text-xs text-text-secondary">New season: {moved.join(", ")}</p>}
          {failures.length > 0 && (
            <div>
              <h3 className="mb-1 text-xs font-bold uppercase tracking-[0.06em] text-text-muted">Not done</h3>
              <ul className="list-disc pl-5 text-xs text-warning-text">{failures.map((f) => <li key={f}>{f}</li>)}</ul>
            </div>
          )}
          {data.steps.length > 0 && (
            <div>
              <h3 className="mb-1 text-xs font-bold uppercase tracking-[0.06em] text-text-muted">Steps</h3>
              <div className="divide-y divide-rule-faint rounded-lg ring-1 ring-border">
                {data.steps.map((s) => (
                  <div key={s.id} className="flex items-center justify-between gap-3 px-3 py-1.5 text-sm">
                    <span className="text-text">{s.job.replace(/^.*\./, "")}</span>
                    <span className="flex items-center gap-3">
                      <span className="text-xs text-text-muted">{duration(s.duration_ms)}</span>
                      <StatusBadge status={s.status} />
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
          <div>
            <h3 className="mb-1 text-xs font-bold uppercase tracking-[0.06em] text-text-muted">Log</h3>
            {data.log_lines === 0 && data.status !== "running" ? (
              <p className="text-xs text-text-muted">This run kept no log.</p>
            ) : (
              <RunLog runId={runId} />
            )}
          </div>
        </div>
      )}
    </Modal>
  );
}

export default function AdminJobsPage() {
  const queryClient = useQueryClient();
  const [job, setJob] = useState("");
  const [status, setStatus] = useState("");
  const [opened, setOpened] = useState<string | null>(null);
  const [confirmRefresh, setConfirmRefresh] = useState(false);
  const [withValuations, setWithValuations] = useState(false);

  const overview = useQuery<{ scheduled: ScheduledJob[]; running: JobRun[] }>({
    queryKey: ["admin", "jobs"],
    queryFn: () => api.get("/admin/jobs").then((r) => r.data),
    refetchInterval: 15_000,
  });
  const runs = useQuery<{ items: JobRun[]; total: number; jobs: string[] }>({
    queryKey: ["admin", "job-runs", job, status],
    queryFn: () => api.get("/admin/jobs/runs", { params: { ...(job && { job }), ...(status && { status }) } }).then((r) => r.data),
    refetchInterval: 15_000,
  });
  const refresh = useMutation({
    mutationFn: () => api.post("/admin/jobs/refresh", { valuations: withValuations }),
    onSuccess: () => {
      setConfirmRefresh(false);
      setTimeout(() => queryClient.invalidateQueries({ queryKey: ["admin"] }), 1500);
    },
  });

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-text">Jobs</h1>
          <p className="mt-1 text-sm text-text-muted">
            Scheduled work in the stats-worker and the web app: when each runs, what's running now, and what each run did.
          </p>
        </div>
        <Button size="sm" onClick={() => { refresh.reset(); setConfirmRefresh(true); }}>Run refresh now</Button>
      </div>

      {overview.isLoading ? (
        <div className="flex justify-center py-16"><Spinner size="lg" /></div>
      ) : overview.data && (
        <>
          {overview.data.running.length > 0 && (
            <section className="mb-6">
              <h2 className="mb-2 text-sm font-semibold text-text">Running now</h2>
              <div className="divide-y divide-rule-faint rounded-xl bg-surface ring-1 ring-border">
                {overview.data.running.map((r, i) => (
                  <div key={r.id ?? `${r.job}-${i}`} className="flex items-center justify-between gap-3 px-5 py-2.5 text-sm">
                    <span className="text-text">{r.label ?? r.job}</span>
                    <span className="flex items-center gap-3 text-xs text-text-muted">
                      {r.status === "lost" ? "stopped reporting" : `for ${since(r.started_at)}`}
                      {r.id && <button type="button" onClick={() => setOpened(r.id)} className="font-semibold text-accent hover:underline">Open</button>}
                    </span>
                  </div>
                ))}
              </div>
            </section>
          )}

          <section className="mb-6">
            <h2 className="mb-2 text-sm font-semibold text-text">Scheduled</h2>
            <div className="overflow-x-auto rounded-xl bg-surface ring-1 ring-border">
              <table className="w-full min-w-[760px] text-sm">
                <thead>
                  <tr className="border-b border-rule text-left text-[11px] font-semibold uppercase tracking-wider text-text-muted">
                    <th className="px-4 py-2">Job</th><th className="px-4 py-2">Runs in</th><th className="px-4 py-2">Schedule</th>
                    <th className="px-4 py-2">Last run</th><th className="px-4 py-2">Next run</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-rule-faint">
                  {overview.data.scheduled.map((j) => (
                    <tr key={j.id}>
                      <td className="px-4 py-2 text-text">
                        {j.label}
                        {j.overdue_since && (
                          <p className="text-xs font-semibold text-danger-text">Didn't run at {formatDateTime(j.overdue_since)}</p>
                        )}
                      </td>
                      <td className="px-4 py-2 text-text-muted">{j.where}</td>
                      <td className="px-4 py-2 text-text-muted">{j.schedule}</td>
                      <td className="px-4 py-2">
                        {j.running ? <StatusBadge status="running" /> : j.last_run_at ? (
                          <span className="flex items-center gap-2" title={j.last_error ?? undefined}>
                            <StatusBadge status={j.last_status} />
                            <span className="text-xs text-text-muted">{formatDateTime(j.last_run_at)}</span>
                          </span>
                        ) : <span className="text-text-muted">Not yet</span>}
                      </td>
                      <td className="px-4 py-2 text-text-muted">{j.next_run_at ? formatDateTime(j.next_run_at) : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}

      <section>
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-semibold text-text">Recent runs</h2>
          <div className="flex gap-2">
            <select aria-label="Job" value={job} onChange={(e) => setJob(e.target.value)}
              className="rounded-lg bg-surface px-2 py-1 text-xs ring-1 ring-input-border">
              <option value="">All jobs</option>
              {(runs.data?.jobs ?? []).map((j) => <option key={j} value={j}>{j}</option>)}
            </select>
            <select aria-label="Status" value={status} onChange={(e) => setStatus(e.target.value)}
              className="rounded-lg bg-surface px-2 py-1 text-xs ring-1 ring-input-border">
              <option value="">Any status</option>
              {Object.entries(STATUS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
            </select>
          </div>
        </div>
        <div className="overflow-x-auto rounded-xl bg-surface ring-1 ring-border">
          {runs.isLoading ? (
            <div className="flex justify-center py-8"><Spinner /></div>
          ) : !runs.data?.items.length ? (
            <p className="px-5 py-6 text-sm text-text-muted">No runs recorded yet.</p>
          ) : (
            <table className="w-full min-w-[720px] text-sm">
              <thead>
                <tr className="border-b border-rule text-left text-[11px] font-semibold uppercase tracking-wider text-text-muted">
                  <th className="px-4 py-2">Job</th><th className="px-4 py-2">Started</th><th className="px-4 py-2">Took</th>
                  <th className="px-4 py-2">Trigger</th><th className="px-4 py-2">Status</th><th className="px-4 py-2" />
                </tr>
              </thead>
              <tbody className="divide-y divide-rule-faint">
                {runs.data.items.map((r) => (
                  <tr key={r.id}>
                    <td className="px-4 py-2 text-text">{r.job}</td>
                    <td className="px-4 py-2 text-text-muted">{formatDateTime(r.started_at)}</td>
                    <td className="px-4 py-2 tabular-nums text-text-muted">{duration(r.duration_ms)}</td>
                    <td className="px-4 py-2 text-text-muted">{r.trigger}</td>
                    <td className="px-4 py-2"><StatusBadge status={r.status} /></td>
                    <td className="px-4 py-2 text-right">
                      <button type="button" onClick={() => setOpened(r.id)} className="text-xs font-semibold text-accent hover:underline">
                        Details
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>

      {opened && <RunDetailModal runId={opened} onClose={() => setOpened(null)} />}

      <Modal open={confirmRefresh} onClose={() => setConfirmRefresh(false)} title="Run the data refresh now?" size="sm">
        <div className="space-y-3 px-6 py-5 text-sm">
          <p className="text-text-secondary">
            Fetches current-season stats, injuries and recent match ratings from API-Football, then updates form.
            It takes a few minutes and uses a few hundred API requests. The scheduled runs carry on as normal.
          </p>
          <label className="flex items-center gap-2 text-text">
            <input type="checkbox" checked={withValuations} onChange={(e) => setWithValuations(e.target.checked)} />
            Also recompute valuations (normally after the 22:00 run)
          </label>
          {refresh.isError && <p className="text-xs text-danger-text">{getApiError(refresh.error, "Couldn't start the refresh.")}</p>}
          <div className="flex justify-end gap-2">
            <Button variant="secondary" size="sm" onClick={() => setConfirmRefresh(false)}>Cancel</Button>
            <Button size="sm" loading={refresh.isPending} onClick={() => refresh.mutate()}>Start refresh</Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
