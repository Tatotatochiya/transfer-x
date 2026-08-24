import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { ActivityItem, AdminStats } from "../../types/api";
import Spinner from "../../components/ui/Spinner";
import Button from "../../components/ui/Button";
import { formatDateTime, getApiError } from "../../lib/utils";

// ── Stat card ─────────────────────────────────────────────────────────────────

function StatCard({
  label, value, accent = "text-text", sub, onClick,
}: {
  label: string; value: number; accent?: string; sub?: string; onClick?: () => void;
}) {
  return (
    <div
      onClick={onClick}
      className={`rounded-xl bg-surface ring-1 ring-border px-6 py-5 ${
        onClick ? "cursor-pointer hover:ring-input-border transition-all" : ""
      }`}
    >
      <p className="text-xs font-semibold uppercase tracking-wider text-text-muted">{label}</p>
      <p className={`mt-2 text-3xl font-bold ${accent}`}>{value.toLocaleString()}</p>
      {sub && <p className="mt-1 text-xs text-text-muted">{sub}</p>}
    </div>
  );
}

// ── Pipeline mini-bar ─────────────────────────────────────────────────────────

function PipelineBar({ byStage }: { byStage: Record<string, number> }) {
  const stages = [
    { key: "AGREEMENT",  label: "Agreement",  color: "bg-warning-fill" },
    { key: "PAPERWORK",  label: "Paperwork",  color: "bg-accent"       },
    { key: "CONFIRMED",  label: "Confirmed",  color: "bg-success"      },
  ];
  const total = stages.reduce((s, st) => s + (byStage[st.key] ?? 0), 0);

  return (
    <div className="rounded-xl bg-surface ring-1 ring-border px-6 py-5">
      <p className="mb-4 text-xs font-semibold uppercase tracking-wider text-text-muted">
        Active Deals by Stage
      </p>
      <div className="flex gap-4">
        {stages.map(({ key, label, color }) => {
          const count = byStage[key] ?? 0;
          const pct = total > 0 ? (count / total) * 100 : 0;
          return (
            <div key={key} className="flex-1">
              <div className="mb-1.5 flex items-end justify-between">
                <span className="text-xs text-text-muted">{label}</span>
                <span className="text-lg font-bold text-text">{count}</span>
              </div>
              <div className="h-1.5 w-full rounded-full bg-border">
                <div
                  className={`h-1.5 rounded-full ${color} transition-all`}
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Needs Attention ───────────────────────────────────────────────────────────

function NeedsAttentionPanel({ byStage }: { byStage: Record<string, number> }) {
  const navigate = useNavigate();

  const { data: stalledDeals } = useQuery({
    queryKey: ["admin", "deals", { status: "IN_PROGRESS", page: 1, page_size: 50 }],
    queryFn: () =>
      api
        .get<{ items: { id: string; player: { name: string } | null; stage: string; buyer_club: { name: string } | null; seller_club: { name: string } | null; created_at: string; updated_at: string }[]; total: number }>("/admin/deals", {
          params: { status: "IN_PROGRESS", page: 1, page_size: 50 },
        })
        .then((r) => r.data),
  });

  const STALE_DAYS = { AGREEMENT: 3, PAPERWORK: 7, CONFIRMED: 7 };
  const now = Date.now();

  const stalled = (stalledDeals?.items ?? []).filter((d) => {
    const threshold = STALE_DAYS[d.stage as keyof typeof STALE_DAYS];
    if (!threshold) return false;
    const ageDays = (now - new Date(d.updated_at).getTime()) / 86_400_000;
    return ageDays > threshold;
  });

  const confirmedCount = byStage["CONFIRMED"] ?? 0;

  if (stalled.length === 0 && confirmedCount === 0) {
    return (
      <div className="rounded-xl bg-success/10 ring-1 ring-success/20 px-6 py-4">
        <p className="text-sm font-semibold text-success-text">All clear — no items need attention</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl bg-surface ring-1 ring-border overflow-hidden">
      <div className="border-b border-rule px-6 py-3">
        <p className="text-sm font-semibold text-warning-text">Needs Attention</p>
      </div>
      <div className="divide-y divide-rule-faint">
        {confirmedCount > 0 && (
          <div className="flex items-center justify-between px-6 py-3">
            <div>
              <p className="text-sm text-text">
                {confirmedCount} deal{confirmedCount !== 1 ? "s" : ""} ready to execute
              </p>
              <p className="mt-0.5 text-xs text-text-muted">Waiting for final transfer execution</p>
            </div>
            <button
              onClick={() => navigate("/admin/deals")}
              className="text-xs text-success-text hover:text-success-text-alt transition-colors"
            >
              View →
            </button>
          </div>
        )}
        {stalled.map((d) => {
          const ageDays = Math.floor((now - new Date(d.updated_at).getTime()) / 86_400_000);
          return (
            <div key={d.id} className="flex items-center justify-between px-6 py-3">
              <div>
                <p className="text-sm text-text">
                  {d.player?.name ?? "Unknown"} — stuck in{" "}
                  <span className="text-warning-text">{d.stage}</span>
                </p>
                <p className="mt-0.5 text-xs text-text-muted">
                  {d.buyer_club?.name ?? "?"} ↔ {d.seller_club?.name ?? "?"} · {ageDays}d without update
                </p>
              </div>
              <Link
                to={`/deals/${d.id}`}
                className="text-xs text-accent hover:text-accent-hover transition-colors"
              >
                Open →
              </Link>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Activity feed ─────────────────────────────────────────────────────────────

const EVENT_COLORS: Record<string, string> = {
  DEAL_COMPLETED: "bg-success",
  DEAL_COLLAPSED: "bg-danger",
  SALE_CREATED:   "bg-accent",
  USER_JOINED:    "bg-role-agent-text",
};

const EVENT_ICONS: Record<string, string> = {
  DEAL_COMPLETED: "✓",
  DEAL_COLLAPSED: "✕",
  SALE_CREATED:   "↑",
  USER_JOINED:    "+",
};

function ActivityFeed() {
  const { data: items = [], isLoading } = useQuery<ActivityItem[]>({
    queryKey: ["admin", "activity"],
    queryFn: () => api.get<ActivityItem[]>("/admin/activity", { params: { limit: 30 } }).then((r) => r.data),
    refetchInterval: 60_000,
  });

  return (
    <div className="rounded-xl bg-surface ring-1 ring-border overflow-hidden">
      <div className="border-b border-rule px-6 py-3">
        <p className="text-sm font-semibold text-text">Recent Activity</p>
        <p className="mt-0.5 text-xs text-text-muted">Last 30 days</p>
      </div>
      {isLoading ? (
        <div className="flex justify-center py-8"><Spinner /></div>
      ) : items.length === 0 ? (
        <p className="px-6 py-8 text-center text-sm text-text-muted">No recent activity</p>
      ) : (
        <div className="divide-y divide-rule-faint max-h-96 overflow-y-auto">
          {items.map((item, i) => {
            const dot = EVENT_COLORS[item.event_type] ?? "bg-text-muted";
            const icon = EVENT_ICONS[item.event_type] ?? "·";
            const content = (
              <div className="flex items-start gap-3 px-6 py-3">
                <div className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[11px] font-bold text-white ${dot}`}>
                  {icon}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-text-secondary">{item.message}</p>
                  <p className="mt-0.5 text-xs text-text-muted">{formatDateTime(item.occurred_at)}</p>
                </div>
              </div>
            );
            return item.link ? (
              <Link key={i} to={item.link} className="block hover:bg-surface-inset transition-colors">
                {content}
              </Link>
            ) : (
              <div key={i}>{content}</div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Broadcast form ─────────────────────────────────────────────────────────────

function BroadcastPanel() {
  const queryClient = useQueryClient();
  const [message, setMessage] = useState("");
  const [link, setLink]       = useState("");
  const [open, setOpen]       = useState(false);

  const mutation = useMutation({
    mutationFn: () =>
      api.post<{ recipients: number }>("/admin/notifications/broadcast", {
        message: message.trim(),
        link: link.trim() || null,
      }).then((r) => r.data),
    onSuccess: () => {
      setMessage(""); setLink(""); setOpen(false);
      queryClient.invalidateQueries({ queryKey: ["admin", "activity"] });
    },
  });

  return (
    <div className="rounded-xl bg-surface ring-1 ring-border overflow-hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-6 py-4 text-left"
      >
        <div>
          <p className="text-sm font-semibold text-text">Broadcast Notification</p>
          <p className="mt-0.5 text-xs text-text-muted">Send a system message to all active users</p>
        </div>
        <span className="text-text-muted text-sm">{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div className="border-t border-rule px-6 py-4">
          <form
            onSubmit={(e) => { e.preventDefault(); mutation.mutate(); }}
            className="space-y-3"
          >
            <div>
              <label className="mb-1 block text-xs text-text-muted">Message</label>
              <textarea
                required
                rows={3}
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder="e.g. Scheduled maintenance tonight at 10pm UTC"
                className="w-full rounded-lg bg-surface px-3 py-2 text-sm text-text placeholder-text-muted ring-1 ring-input-border focus:outline-none focus:ring-warning-fill resize-none"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-text-muted">Link <span className="text-text-muted">(optional)</span></label>
              <input
                type="text"
                value={link}
                onChange={(e) => setLink(e.target.value)}
                placeholder="/transfers or https://..."
                className="w-full rounded-lg bg-surface px-3 py-2 text-sm text-text placeholder-text-muted ring-1 ring-input-border focus:outline-none focus:ring-warning-fill"
              />
            </div>
            <div className="flex items-center gap-3">
              <Button
                type="submit"
                variant="primary"
                size="sm"
                loading={mutation.isPending}
                disabled={!message.trim()}
              >
                Send to all users
              </Button>
              {mutation.isSuccess && (
                <p className="text-xs text-success-text">
                  Sent to {(mutation.data as { recipients: number }).recipients} users.
                </p>
              )}
              {mutation.isError && (
                <p className="text-xs text-danger-text">{getApiError(mutation.error, "Failed to send.")}</p>
              )}
            </div>
          </form>
        </div>
      )}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function AdminDashboardPage() {
  const navigate = useNavigate();

  const { data: stats, isLoading, isError } = useQuery<AdminStats>({
    queryKey: ["admin", "stats"],
    queryFn: () => api.get<AdminStats>("/admin/stats").then((r) => r.data),
    refetchInterval: 30_000,
  });

  if (isLoading) {
    return <div className="flex items-center justify-center py-20"><Spinner size="lg" /></div>;
  }

  if (isError || !stats) {
    return (
      <div className="rounded-xl bg-danger-bg px-5 py-4 text-sm text-danger-text ring-1 ring-danger-border">
        Failed to load system stats.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-text">Admin Dashboard</h1>
        <p className="mt-1 text-sm text-text-muted">System overview — refreshes every 30s</p>
      </div>

      {/* Row 1 — entity counts */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <StatCard label="Total Users"   value={stats.total_users}   onClick={() => navigate("/admin/users")} />
        <StatCard label="Total Clubs"   value={stats.total_clubs}   onClick={() => navigate("/admin/clubs")} />
        <StatCard label="Total Players" value={stats.total_players} onClick={() => navigate("/admin/players")} />
      </div>

      {/* Row 2 — live transaction counts */}
      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard
          label="Active Sales"
          value={stats.active_sales}
          accent={stats.active_sales > 0 ? "text-success-text" : "text-text"}
          onClick={() => navigate("/admin/sales")}
        />
        <StatCard
          label="Open Offers"
          value={stats.open_offers}
          accent={stats.open_offers > 0 ? "text-accent" : "text-text"}
          onClick={() => navigate("/admin/offers")}
        />
        <StatCard
          label="Active Deals"
          value={stats.active_deals}
          accent={stats.active_deals > 0 ? "text-warning-text" : "text-text"}
          sub={`${stats.deals_by_stage["CONFIRMED"] ?? 0} ready to execute`}
          onClick={() => navigate("/admin/deals")}
        />
      </div>

      {/* Deal pipeline bar */}
      <PipelineBar byStage={stats.deals_by_stage} />

      {/* Needs Attention */}
      <NeedsAttentionPanel byStage={stats.deals_by_stage} />

      {/* Bottom two-col: activity + broadcast */}
      <div className="grid gap-6 lg:grid-cols-2">
        <ActivityFeed />
        <div className="space-y-4">
          <BroadcastPanel />
          {/* Quick actions */}
          <div className="rounded-xl bg-surface ring-1 ring-border px-6 py-5">
            <p className="mb-4 text-xs font-semibold uppercase tracking-wider text-text-muted">
              Quick Actions
            </p>
            <div className="flex flex-wrap gap-2">
              {[
                { label: "Manage users",    to: "/admin/users"     },
                { label: "Manage clubs",    to: "/admin/clubs"     },
                { label: "Vendor sync",     to: "/admin/vendor"    },
                { label: "Health check",    to: "/admin/health"    },
                { label: "TW Windows",      to: "/admin/windows"   },
              ].map(({ label, to }) => (
                <button
                  key={to}
                  onClick={() => navigate(to)}
                  className="rounded-lg bg-surface-inset px-3 py-1.5 text-sm text-text-secondary ring-1 ring-input-border hover:bg-border hover:text-text transition-colors"
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
