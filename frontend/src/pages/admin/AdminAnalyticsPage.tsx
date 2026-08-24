import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import api from "../../lib/api";
import Spinner from "../../components/ui/Spinner";

// ── Types ─────────────────────────────────────────────────────────────────────

interface AnalyticsOverview {
  total_events_today: number;
  total_events_7d: number;
  total_events_30d: number;
  unique_sessions_today: number;
  unique_sessions_7d: number;
  dau_today: number;
  dau_7d: number;
  page_views_today: number;
  page_views_7d: number;
}

interface TopPage {
  path: string;
  views: number;
  unique_sessions: number;
  avg_duration_ms: number | null;
}

interface UserActivityRow {
  user_id: string;
  email: string | null;
  page_views: number;
  sessions: number;
  last_seen: string;
}

interface SessionRow {
  session_id: string;
  user_id: string | null;
  email: string | null;
  ip_address: string | null;
  user_agent: string | null;
  pages_visited: number;
  first_seen: string;
  last_seen: string;
}

interface DailyCount {
  date: string;
  page_views: number;
  unique_sessions: number;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtDuration(ms: number | null | undefined): string {
  if (ms == null) return "—";
  if (ms < 1000) return `${Math.round(ms)}ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60_000)}m ${Math.round((ms % 60_000) / 1000)}s`;
}

function fmtDate(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function shortenUA(ua: string | null): string {
  if (!ua) return "—";
  // Extract browser name
  if (ua.includes("Firefox/")) return "Firefox";
  if (ua.includes("Edg/")) return "Edge";
  if (ua.includes("Chrome/")) return ua.includes("Mobile") ? "Chrome Mobile" : "Chrome";
  if (ua.includes("Safari/")) return ua.includes("Mobile") ? "Safari Mobile" : "Safari";
  return ua.slice(0, 30);
}

// ── Sub-components ────────────────────────────────────────────────────────────

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="rounded-xl bg-surface ring-1 ring-border px-5 py-4">
      <p className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">{label}</p>
      <p className="mt-1.5 text-2xl font-bold text-text">{typeof value === "number" ? value.toLocaleString() : value}</p>
      {sub && <p className="mt-0.5 text-xs text-text-muted">{sub}</p>}
    </div>
  );
}

// Simple sparkline bar chart
function TrendChart({ data }: { data: DailyCount[] }) {
  if (!data.length) return null;
  const max = Math.max(...data.map((d) => d.page_views), 1);
  return (
    <div className="rounded-xl bg-surface ring-1 ring-border px-5 py-4">
      <p className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-text-muted">
        Daily Page Views (last {data.length} days)
      </p>
      <div className="flex items-end gap-0.5 h-16">
        {data.map((d) => (
          <div
            key={d.date}
            className="flex-1 min-w-0 rounded-sm bg-success/60 hover:bg-success transition-colors"
            style={{ height: `${(d.page_views / max) * 100}%` }}
            title={`${d.date}: ${d.page_views} views, ${d.unique_sessions} sessions`}
          />
        ))}
      </div>
      <div className="mt-1 flex justify-between text-[13px] text-text-muted">
        <span>{data[0]?.date}</span>
        <span>{data[data.length - 1]?.date}</span>
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function AdminAnalyticsPage() {
  const [pagesDays, setPagesDays] = useState(7);
  const [usersDays, setUsersDays] = useState(7);
  const [activeTab, setActiveTab] = useState<"pages" | "users" | "sessions">("pages");

  const { data: overview, isLoading: ovLoading } = useQuery<AnalyticsOverview>({
    queryKey: ["admin", "analytics", "overview"],
    queryFn: () => api.get<AnalyticsOverview>("/analytics/overview").then((r) => r.data),
    refetchInterval: 30_000,
  });

  const { data: topPages, isLoading: pagesLoading } = useQuery<TopPage[]>({
    queryKey: ["admin", "analytics", "pages", pagesDays],
    queryFn: () =>
      api.get<TopPage[]>("/analytics/pages", { params: { days: pagesDays, limit: 25 } }).then((r) => r.data),
  });

  const { data: userActivity, isLoading: usersLoading } = useQuery<UserActivityRow[]>({
    queryKey: ["admin", "analytics", "users", usersDays],
    queryFn: () =>
      api.get<UserActivityRow[]>("/analytics/users", { params: { days: usersDays, limit: 50 } }).then((r) => r.data),
  });

  const { data: sessions, isLoading: sessionsLoading } = useQuery<SessionRow[]>({
    queryKey: ["admin", "analytics", "sessions"],
    queryFn: () =>
      api.get<SessionRow[]>("/analytics/sessions", { params: { limit: 50 } }).then((r) => r.data),
  });

  const { data: trend } = useQuery<DailyCount[]>({
    queryKey: ["admin", "analytics", "trend"],
    queryFn: () =>
      api.get<DailyCount[]>("/analytics/trend", { params: { days: 30 } }).then((r) => r.data),
  });

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-text">Analytics</h1>
        <p className="mt-1 text-sm text-text-muted">Usage stats — page views, sessions, time on page, user activity</p>
      </div>

      {/* Overview cards */}
      {ovLoading ? (
        <div className="flex justify-center py-10"><Spinner size="lg" /></div>
      ) : overview ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 mb-6">
          <StatCard label="Page Views Today" value={overview.page_views_today} sub={`${overview.page_views_7d.toLocaleString()} last 7d`} />
          <StatCard label="Sessions Today" value={overview.unique_sessions_today} sub={`${overview.unique_sessions_7d.toLocaleString()} last 7d`} />
          <StatCard label="DAU Today" value={overview.dau_today} sub={`Avg ${overview.dau_7d} / day last 7d`} />
          <StatCard label="Total Events Today" value={overview.total_events_today} sub={`${overview.total_events_7d.toLocaleString()} last 7d`} />
        </div>
      ) : null}

      {/* Trend chart */}
      {trend && trend.length > 0 && (
        <div className="mb-6">
          <TrendChart data={trend} />
        </div>
      )}

      {/* Tabs */}
      <div className="mb-4 flex gap-2 border-b border-rule pb-0">
        {(["pages", "users", "sessions"] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-sm font-medium capitalize transition-colors border-b-2 -mb-px ${
              activeTab === tab
                ? "border-success text-success-text"
                : "border-transparent text-text-muted hover:text-text-secondary"
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* ── Top Pages ── */}
      {activeTab === "pages" && (
        <div>
          <div className="mb-3 flex items-center gap-3">
            <p className="text-sm text-text-muted">Last</p>
            {[7, 14, 30].map((d) => (
              <button
                key={d}
                onClick={() => setPagesDays(d)}
                className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${
                  pagesDays === d
                    ? "bg-success/20 text-success-text ring-1 ring-success/30"
                    : "text-text-muted hover:text-text-secondary"
                }`}
              >
                {d}d
              </button>
            ))}
          </div>

          {pagesLoading ? (
            <div className="flex justify-center py-10"><Spinner /></div>
          ) : (
            <div className="rounded-xl bg-surface ring-1 ring-border overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-rule">
                    <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-text-muted">Path</th>
                    <th className="px-4 py-3 text-right text-[11px] font-semibold uppercase tracking-wider text-text-muted">Views</th>
                    <th className="px-4 py-3 text-right text-[11px] font-semibold uppercase tracking-wider text-text-muted">Sessions</th>
                    <th className="px-4 py-3 text-right text-[11px] font-semibold uppercase tracking-wider text-text-muted">Avg Time</th>
                  </tr>
                </thead>
                <tbody>
                  {(topPages ?? []).map((p, i) => (
                    <tr key={p.path} className={i % 2 === 0 ? "" : "bg-surface-inset"}>
                      <td className="px-4 py-2.5 font-mono text-xs text-text-secondary">{p.path}</td>
                      <td className="px-4 py-2.5 text-right text-text">{p.views.toLocaleString()}</td>
                      <td className="px-4 py-2.5 text-right text-text-muted">{p.unique_sessions.toLocaleString()}</td>
                      <td className="px-4 py-2.5 text-right text-text-muted">{fmtDuration(p.avg_duration_ms)}</td>
                    </tr>
                  ))}
                  {(topPages ?? []).length === 0 && (
                    <tr>
                      <td colSpan={4} className="px-4 py-8 text-center text-sm text-text-muted">No data yet</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ── User Activity ── */}
      {activeTab === "users" && (
        <div>
          <div className="mb-3 flex items-center gap-3">
            <p className="text-sm text-text-muted">Last</p>
            {[7, 14, 30].map((d) => (
              <button
                key={d}
                onClick={() => setUsersDays(d)}
                className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${
                  usersDays === d
                    ? "bg-success/20 text-success-text ring-1 ring-success/30"
                    : "text-text-muted hover:text-text-secondary"
                }`}
              >
                {d}d
              </button>
            ))}
          </div>

          {usersLoading ? (
            <div className="flex justify-center py-10"><Spinner /></div>
          ) : (
            <div className="rounded-xl bg-surface ring-1 ring-border overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-rule">
                    <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-text-muted">User</th>
                    <th className="px-4 py-3 text-right text-[11px] font-semibold uppercase tracking-wider text-text-muted">Page Views</th>
                    <th className="px-4 py-3 text-right text-[11px] font-semibold uppercase tracking-wider text-text-muted">Sessions</th>
                    <th className="px-4 py-3 text-right text-[11px] font-semibold uppercase tracking-wider text-text-muted">Last Seen</th>
                  </tr>
                </thead>
                <tbody>
                  {(userActivity ?? []).map((u, i) => (
                    <tr key={u.user_id} className={i % 2 === 0 ? "" : "bg-surface-inset"}>
                      <td className="px-4 py-2.5 text-text-secondary">{u.email ?? <span className="text-text-muted">anonymous</span>}</td>
                      <td className="px-4 py-2.5 text-right text-text">{u.page_views.toLocaleString()}</td>
                      <td className="px-4 py-2.5 text-right text-text-muted">{u.sessions}</td>
                      <td className="px-4 py-2.5 text-right text-text-muted">{fmtDate(u.last_seen)}</td>
                    </tr>
                  ))}
                  {(userActivity ?? []).length === 0 && (
                    <tr>
                      <td colSpan={4} className="px-4 py-8 text-center text-sm text-text-muted">No logged-in user activity yet</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ── Sessions ── */}
      {activeTab === "sessions" && (
        <div>
          {sessionsLoading ? (
            <div className="flex justify-center py-10"><Spinner /></div>
          ) : (
            <div className="rounded-xl bg-surface ring-1 ring-border overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-rule">
                    <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-text-muted">Session</th>
                    <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-text-muted">User</th>
                    <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-text-muted">IP</th>
                    <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-text-muted">Browser</th>
                    <th className="px-4 py-3 text-right text-[11px] font-semibold uppercase tracking-wider text-text-muted">Pages</th>
                    <th className="px-4 py-3 text-right text-[11px] font-semibold uppercase tracking-wider text-text-muted">Last Seen</th>
                  </tr>
                </thead>
                <tbody>
                  {(sessions ?? []).map((s, i) => (
                    <tr key={s.session_id} className={i % 2 === 0 ? "" : "bg-surface-inset"}>
                      <td className="px-4 py-2.5 font-mono text-[11px] text-text-muted">
                        {s.session_id.slice(0, 8)}…
                      </td>
                      <td className="px-4 py-2.5 text-text-secondary">
                        {s.email ?? <span className="text-text-muted">anon</span>}
                      </td>
                      <td className="px-4 py-2.5 font-mono text-xs text-text-muted">{s.ip_address ?? "—"}</td>
                      <td className="px-4 py-2.5 text-xs text-text-muted">{shortenUA(s.user_agent)}</td>
                      <td className="px-4 py-2.5 text-right text-text">{s.pages_visited}</td>
                      <td className="px-4 py-2.5 text-right text-text-muted">{fmtDate(s.last_seen)}</td>
                    </tr>
                  ))}
                  {(sessions ?? []).length === 0 && (
                    <tr>
                      <td colSpan={6} className="px-4 py-8 text-center text-sm text-text-muted">No sessions recorded yet</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
