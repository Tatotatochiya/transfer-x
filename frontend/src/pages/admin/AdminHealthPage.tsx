import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import api from "../../lib/api";
import type { HealthIssue, HealthReport } from "../../types/api";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Spinner from "../../components/ui/Spinner";
import { formatDateTime } from "../../lib/utils";

// ── Severity helpers ──────────────────────────────────────────────────────────

const SEVERITY_VARIANT: Record<string, "danger" | "warning" | "info"> = {
  critical: "danger",
  warning:  "warning",
  info:     "info",
};

const SEVERITY_BG: Record<string, string> = {
  critical: "bg-danger/10 ring-danger/20",
  warning:  "bg-warning-fill/10 ring-warning-fill/20",
  info:     "bg-accent/10 ring-accent/20",
};

const CATEGORY_LINK: Record<string, (id: string) => string> = {
  deals:     (id) => `/deals/${id}`,
  sales:     (id) => `/sales/${id}`,
  players:   (id) => `/players/market/${id}`,
  contracts: (id) => `/players/market/${id}`,
};

// ── Issue card ─────────────────────────────────────────────────────────────────

function IssueCard({ issue }: { issue: HealthIssue }) {
  const [expanded, setExpanded] = useState(false);
  const linkFn = CATEGORY_LINK[issue.category];

  return (
    <div className={`rounded-xl ring-1 px-5 py-4 ${SEVERITY_BG[issue.severity]}`}>
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <Badge variant={SEVERITY_VARIANT[issue.severity]}>
            {issue.severity}
          </Badge>
          <div>
            <p className="text-sm font-medium text-text">{issue.message}</p>
            <p className="mt-0.5 text-xs text-text-muted capitalize">{issue.category}</p>
          </div>
        </div>
        {issue.details.length > 0 && (
          <button
            onClick={() => setExpanded((v) => !v)}
            className="shrink-0 text-xs text-text-muted hover:text-text transition-colors"
          >
            {expanded ? "Hide" : `Show ${issue.count}`}
          </button>
        )}
      </div>

      {expanded && issue.details.length > 0 && (
        <div className="mt-3 space-y-1.5 border-t border-rule pt-3">
          {issue.details.map((d) => (
            <div key={d.id} className="flex items-center justify-between">
              <p className="text-xs text-text-secondary">{d.label}</p>
              {linkFn && (
                <Link
                  to={linkFn(d.id)}
                  className="text-xs text-accent hover:text-accent-hover transition-colors"
                >
                  Open →
                </Link>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

import { useState } from "react";

export default function AdminHealthPage() {
  const queryClient = useQueryClient();

  const { data, isLoading, isFetching, dataUpdatedAt } = useQuery<HealthReport>({
    queryKey: ["admin", "health"],
    queryFn: () => api.get<HealthReport>("/admin/health").then((r) => r.data),
    staleTime: 60_000,
  });

  const critical = data?.issues.filter((i) => i.severity === "critical") ?? [];
  const warnings = data?.issues.filter((i) => i.severity === "warning")  ?? [];
  const infos    = data?.issues.filter((i) => i.severity === "info")     ?? [];

  return (
    <div>
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-text">System Health</h1>
          <p className="mt-1 text-sm text-text-muted">
            Services, scheduled jobs, and data integrity checks across deals, sales and contracts
          </p>
          {dataUpdatedAt > 0 && (
            <p className="mt-0.5 text-xs text-text-muted">
              Last checked {formatDateTime(new Date(dataUpdatedAt).toISOString())}
            </p>
          )}
        </div>
        <Button
          variant="secondary"
          size="sm"
          loading={isFetching}
          onClick={() => queryClient.invalidateQueries({ queryKey: ["admin", "health"] })}
        >
          Re-run checks
        </Button>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-20"><Spinner size="lg" /></div>
      ) : !data ? (
        <div className="rounded-xl bg-danger-bg px-5 py-4 text-sm text-danger-text ring-1 ring-danger-border">
          Failed to load health report.
        </div>
      ) : (
        <>
          {/* Services: what the platform depends on */}
          {data.services && data.services.length > 0 && (
            <section className="mb-6">
              <h2 className="mb-2 text-sm font-semibold text-text">Services</h2>
              <div className="divide-y divide-rule-faint rounded-xl bg-surface ring-1 ring-border">
                {data.services.map((s) => (
                  <div key={s.key} className="flex items-start gap-3 px-5 py-3">
                    <span aria-hidden className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${s.ok ? "bg-success" : "bg-warning-fill"}`} />
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-text">
                        {s.label} <span className="sr-only">{s.ok ? "working" : "needs attention"}</span>
                      </p>
                      <p className="text-xs text-text-muted">{s.detail}</p>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Scheduled jobs */}
          {data.jobs && data.jobs.length > 0 && (
            <section className="mb-6">
              <h2 className="mb-1 text-sm font-semibold text-text">Scheduled jobs</h2>
              <p className="mb-2 text-xs text-text-muted">Last runs are counted since the API last restarted.</p>
              <div className="overflow-x-auto rounded-xl bg-surface ring-1 ring-border">
                <table className="w-full min-w-[640px] text-sm">
                  <thead>
                    <tr className="border-b border-rule text-left text-[11px] font-semibold uppercase tracking-wider text-text-muted">
                      <th className="px-4 py-2">Job</th><th className="px-4 py-2">Every</th>
                      <th className="px-4 py-2">Last run</th><th className="px-4 py-2">Next run</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-rule-faint">
                    {data.jobs.map((j) => (
                      <tr key={j.id}>
                        <td className="px-4 py-2 text-text">{j.label}</td>
                        <td className="px-4 py-2 text-text-muted">{j.every}</td>
                        <td className="px-4 py-2">
                          {j.last_run_at ? (
                            <span className={j.last_ok === false ? "text-danger-text" : "text-text-secondary"} title={j.last_error ?? undefined}>
                              {formatDateTime(j.last_run_at)}{j.last_ok === false ? " · failed" : ""}
                            </span>
                          ) : <span className="text-text-muted">Not since restart</span>}
                        </td>
                        <td className="px-4 py-2 text-text-muted">{j.next_run_at ? formatDateTime(j.next_run_at) : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          <h2 className="mb-2 text-sm font-semibold text-text">Data integrity</h2>
          {/* Summary banner */}
          {data.healthy ? (
            <div className="mb-6 rounded-xl bg-success/10 ring-1 ring-success/20 px-6 py-4 flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-success/20 text-success-text font-bold">
                ✓
              </div>
              <div>
                <p className="text-sm font-semibold text-success-text">All checks passed</p>
                <p className="mt-0.5 text-xs text-text-muted">No data integrity issues detected</p>
              </div>
            </div>
          ) : (
            <div className="mb-6 grid gap-3 sm:grid-cols-3">
              {[
                { label: "Critical", count: critical.length, variant: "danger" as const,   color: "text-danger-text"  },
                { label: "Warnings", count: warnings.length, variant: "warning" as const,  color: "text-warning-text" },
                { label: "Info",     count: infos.length,    variant: "info" as const,      color: "text-accent"      },
              ].map(({ label, count, color }) => (
                <div key={label} className="rounded-xl bg-surface ring-1 ring-border px-5 py-4">
                  <p className="text-xs font-semibold uppercase tracking-wider text-text-muted">{label}</p>
                  <p className={`mt-1 text-3xl font-bold ${color}`}>{count}</p>
                </div>
              ))}
            </div>
          )}

          {/* Issues */}
          {data.issues.length > 0 && (
            <div className="space-y-3">
              {[...critical, ...warnings, ...infos].map((issue, i) => (
                <IssueCard key={i} issue={issue} />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
