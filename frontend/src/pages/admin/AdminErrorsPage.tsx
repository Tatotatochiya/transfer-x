import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import { formatDateTime } from "../../lib/utils";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Modal from "../../components/ui/Modal";
import Spinner from "../../components/ui/Spinner";

/** Admin → Errors (docs/feature_spec/scheduled-data-refresh.md): warnings
 *  and errors from the web app, the worker and browsers, grouped into issues. */

interface Issue {
  id: string;
  service: "api" | "worker" | "web";
  level: string;
  logger: string;
  title: string;
  status: "open" | "resolved" | "ignored";
  first_seen: string;
  last_seen: string;
  count: number;
  last_24h: number[];
}

interface IssueEvent {
  id: number;
  at: string;
  level: string;
  message: string;
  traceback: string | null;
  context: Record<string, string | number> | null;
}

const SERVICE_LABEL: Record<Issue["service"], string> = { api: "Web app", worker: "Worker", web: "Browser" };
const STATUSES = ["open", "resolved", "ignored", "all"] as const;

function Sparkline({ values }: { values: number[] }) {
  const max = Math.max(1, ...values);
  return (
    <span className="inline-flex h-5 items-end gap-px" aria-label={`${values.reduce((a, b) => a + b, 0)} in the last 24 hours`}>
      {values.map((v, i) => (
        <span key={i} className={`w-1 rounded-sm ${v ? "bg-danger" : "bg-rule"}`} style={{ height: `${v ? Math.max(15, (v / max) * 100) : 10}%` }} />
      ))}
    </span>
  );
}

function IssueModal({ id, onClose }: { id: string; onClose: () => void }) {
  const queryClient = useQueryClient();
  const { data } = useQuery<Issue & { events: IssueEvent[] }>({
    queryKey: ["admin", "error", id],
    queryFn: () => api.get(`/admin/errors/${id}`).then((r) => r.data),
  });
  const setStatus = useMutation({
    mutationFn: (status: Issue["status"]) => api.patch(`/admin/errors/${id}`, { status }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin"] }),
  });
  return (
    <Modal open onClose={onClose} title={data?.title ?? "Issue"} size="xl">
      {!data ? (
        <div className="flex justify-center py-10"><Spinner /></div>
      ) : (
        <div className="space-y-4 px-6 py-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-xs text-text-muted">
              {SERVICE_LABEL[data.service]} · {data.logger} · {data.count.toLocaleString("en-GB")} times ·
              first {formatDateTime(data.first_seen)} · last {formatDateTime(data.last_seen)}
            </p>
            <div className="flex gap-2">
              {data.status !== "resolved" && (
                <Button size="sm" loading={setStatus.isPending} onClick={() => setStatus.mutate("resolved")}>Resolve</Button>
              )}
              {data.status !== "ignored" && (
                <Button size="sm" variant="secondary" onClick={() => setStatus.mutate("ignored")}>Ignore</Button>
              )}
              {data.status !== "open" && (
                <Button size="sm" variant="secondary" onClick={() => setStatus.mutate("open")}>Reopen</Button>
              )}
            </div>
          </div>
          <p className="text-xs text-text-muted">
            A resolved issue that happens again reopens. Ignored issues are still counted, but never alert.
          </p>
          <div className="space-y-3">
            {data.events.map((e) => (
              <div key={e.id} className="rounded-lg ring-1 ring-border">
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-rule-faint px-3 py-1.5 text-xs">
                  <span className="font-semibold text-text">{formatDateTime(e.at)}</span>
                  <span className="text-text-muted">
                    {e.context
                      ? Object.entries(e.context).map(([k, v]) => `${k.replace("_", " ")} ${v}`).join(" · ")
                      : "no request"}
                  </span>
                </div>
                <p className="whitespace-pre-wrap break-words px-3 py-2 text-xs text-text">{e.message}</p>
                {e.traceback && (
                  <details className="px-3 pb-2">
                    <summary className="cursor-pointer text-xs font-semibold text-accent">Traceback</summary>
                    <pre className="mt-1 max-h-64 overflow-auto rounded bg-surface-inset p-2 text-[11px] leading-snug">{e.traceback}</pre>
                  </details>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </Modal>
  );
}

export default function AdminErrorsPage() {
  const [params, setParams] = useSearchParams();
  const [status, setStatus] = useState<(typeof STATUSES)[number]>("open");
  const [service, setService] = useState("");
  const [level, setLevel] = useState("");
  const [search, setSearch] = useState("");
  const opened = params.get("issue");

  const { data, isLoading } = useQuery<{ items: Issue[]; total: number; counts: Record<string, number> }>({
    queryKey: ["admin", "errors", status, service, level, search],
    queryFn: () => api.get("/admin/errors", {
      params: { status, ...(service && { service }), ...(level && { level }), ...(search.trim() && { q: search.trim() }) },
    }).then((r) => r.data),
    refetchInterval: 30_000,
  });

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-text">Errors</h1>
        <p className="mt-1 text-sm text-text-muted">
          Warnings and errors from the web app, the stats-worker and people's browsers, grouped into issues.
          Kept 30 days (issues 90 days after they were last seen). Full logs stay in Railway.
        </p>
      </div>

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <div role="tablist" aria-label="Status" className="flex rounded-lg bg-surface-inset p-0.5 ring-1 ring-border">
          {STATUSES.map((s) => (
            <button
              key={s}
              role="tab"
              aria-selected={status === s}
              onClick={() => setStatus(s)}
              className={`rounded-md px-3 py-1 text-sm font-medium capitalize ${status === s ? "bg-surface text-text shadow-sm" : "text-text-secondary"}`}
            >
              {s}{s !== "all" && data?.counts[s] ? ` ${data.counts[s]}` : ""}
            </button>
          ))}
        </div>
        <select aria-label="Service" value={service} onChange={(e) => setService(e.target.value)}
          className="rounded-lg bg-surface px-2 py-1.5 text-sm ring-1 ring-input-border">
          <option value="">All services</option>
          <option value="api">Web app</option>
          <option value="worker">Worker</option>
          <option value="web">Browser</option>
        </select>
        <select aria-label="Level" value={level} onChange={(e) => setLevel(e.target.value)}
          className="rounded-lg bg-surface px-2 py-1.5 text-sm ring-1 ring-input-border">
          <option value="">Warnings and errors</option>
          <option value="ERROR">Errors</option>
          <option value="WARNING">Warnings</option>
        </select>
        <input type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search issues"
          aria-label="Search issues" className="min-w-0 flex-1 rounded-lg bg-surface px-3 py-1.5 text-sm ring-1 ring-input-border" />
      </div>

      <div className="overflow-x-auto rounded-xl bg-surface ring-1 ring-border">
        {isLoading ? (
          <div className="flex justify-center py-10"><Spinner /></div>
        ) : !data?.items.length ? (
          <p className="px-5 py-8 text-center text-sm text-text-muted">
            {status === "open" ? "No open issues." : "Nothing here."}
          </p>
        ) : (
          <table className="w-full min-w-[760px] text-sm">
            <thead>
              <tr className="border-b border-rule text-left text-[11px] font-semibold uppercase tracking-wider text-text-muted">
                <th className="px-4 py-2">Issue</th><th className="px-4 py-2">Where</th><th className="px-4 py-2">Last 24h</th>
                <th className="px-4 py-2 text-right">Count</th><th className="px-4 py-2">Last seen</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-rule-faint">
              {data.items.map((i) => (
                <tr key={i.id} className="cursor-pointer hover:bg-surface-inset" onClick={() => setParams({ issue: i.id })}>
                  <td className="max-w-[420px] px-4 py-2">
                    <button type="button" className="block w-full truncate text-left font-semibold text-text hover:underline" title={i.title}>
                      {i.title}
                    </button>
                    <span className="text-xs text-text-muted">{i.logger}</span>
                  </td>
                  <td className="px-4 py-2">
                    <span className="flex items-center gap-1.5">
                      <Badge variant={i.level === "WARNING" ? "warning" : "danger"}>{i.level === "WARNING" ? "Warning" : "Error"}</Badge>
                      <span className="text-xs text-text-muted">{SERVICE_LABEL[i.service]}</span>
                    </span>
                  </td>
                  <td className="px-4 py-2"><Sparkline values={i.last_24h} /></td>
                  <td className="px-4 py-2 text-right tabular-nums text-text">{i.count.toLocaleString("en-GB")}</td>
                  <td className="px-4 py-2 text-xs text-text-muted">{formatDateTime(i.last_seen)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {opened && <IssueModal id={opened} onClose={() => setParams({})} />}
    </div>
  );
}
