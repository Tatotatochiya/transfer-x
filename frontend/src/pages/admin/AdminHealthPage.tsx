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
  critical: "bg-red-500/10 ring-red-500/20",
  warning:  "bg-amber-500/10 ring-amber-500/20",
  info:     "bg-sky-500/10 ring-sky-500/20",
};

const CATEGORY_LINK: Record<string, (id: string) => string> = {
  deals:     (id) => `/deals/${id}`,
  sales:     (id) => `/market/sales/${id}`,
  players:   (id) => `/market/players/${id}`,
  contracts: (id) => `/market/players/${id}`,
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
            <p className="text-sm font-medium text-white">{issue.message}</p>
            <p className="mt-0.5 text-xs text-slate-500 capitalize">{issue.category}</p>
          </div>
        </div>
        {issue.details.length > 0 && (
          <button
            onClick={() => setExpanded((v) => !v)}
            className="shrink-0 text-xs text-slate-400 hover:text-white transition-colors"
          >
            {expanded ? "Hide" : `Show ${issue.count}`}
          </button>
        )}
      </div>

      {expanded && issue.details.length > 0 && (
        <div className="mt-3 space-y-1.5 border-t border-white/[0.06] pt-3">
          {issue.details.map((d) => (
            <div key={d.id} className="flex items-center justify-between">
              <p className="text-xs text-slate-300">{d.label}</p>
              {linkFn && (
                <Link
                  to={linkFn(d.id)}
                  className="text-xs text-sky-400 hover:text-sky-300 transition-colors"
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
          <h1 className="text-2xl font-bold text-white">System Health</h1>
          <p className="mt-1 text-sm text-slate-400">
            Data integrity checks across deals, sales, and contracts
          </p>
          {dataUpdatedAt > 0 && (
            <p className="mt-0.5 text-xs text-slate-600">
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
        <div className="rounded-xl bg-red-500/10 px-5 py-4 text-sm text-red-400 ring-1 ring-red-500/30">
          Failed to load health report.
        </div>
      ) : (
        <>
          {/* Summary banner */}
          {data.healthy ? (
            <div className="mb-6 rounded-xl bg-emerald-500/10 ring-1 ring-emerald-500/20 px-6 py-4 flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-emerald-500/20 text-emerald-400 font-bold">
                ✓
              </div>
              <div>
                <p className="text-sm font-semibold text-emerald-400">All checks passed</p>
                <p className="mt-0.5 text-xs text-slate-500">No data integrity issues detected</p>
              </div>
            </div>
          ) : (
            <div className="mb-6 grid gap-3 sm:grid-cols-3">
              {[
                { label: "Critical", count: critical.length, variant: "danger" as const,   color: "text-red-400"    },
                { label: "Warnings", count: warnings.length, variant: "warning" as const,  color: "text-amber-400"  },
                { label: "Info",     count: infos.length,    variant: "info" as const,      color: "text-sky-400"    },
              ].map(({ label, count, color }) => (
                <div key={label} className="rounded-xl bg-slate-900 ring-1 ring-white/[0.08] px-5 py-4">
                  <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">{label}</p>
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
