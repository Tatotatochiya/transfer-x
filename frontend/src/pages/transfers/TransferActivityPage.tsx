import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import api from "../../lib/api";
import type { Paginated, TransferActivity, TransferAnalytics } from "../../types/api";
import Badge from "../../components/ui/Badge";
import PageHeader from "../../components/ui/PageHeader";
import Pagination from "../../components/ui/Pagination";
import Spinner from "../../components/ui/Spinner";
import EmptyState from "../../components/ui/EmptyState";
import ClubLink from "../../components/ui/ClubLink";
import { formatCurrency, formatDate } from "../../lib/utils";
import { positionVariant } from "../../lib/badges";
import type { PlayerPosition } from "../../types/enums";

const PAGE_SIZE = 30;

const POSITIONS = ["GK", "DEF", "MID", "FWD"];

// ── Shared tab nav ────────────────────────────────────────────────────────────

type Tab = "feed" | "analytics";

function TabNav({ active, onChange }: { active: Tab; onChange: (t: Tab) => void }) {
  const tabs: { id: Tab; label: string }[] = [
    { id: "feed",      label: "Transfer Feed" },
    { id: "analytics", label: "Analytics" },
  ];
  return (
    <div className="mb-6 flex gap-1 rounded-xl bg-surface-inset p-1 ring-1 ring-border w-fit">
      {tabs.map((t) => (
        <button
          key={t.id}
          onClick={() => onChange(t.id)}
          className={`rounded-lg px-5 py-2 text-sm font-medium transition-colors ${
            active === t.id
              ? "bg-surface text-text shadow-sm"
              : "text-text-muted hover:text-text"
          }`}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

// ── Feed tab ──────────────────────────────────────────────────────────────────

function TransferRow({ t }: { t: TransferActivity }) {
  return (
    <tr className="border-b border-rule-faint transition-colors hover:bg-surface-inset">
      <td className="px-4 py-3">
        {t.player ? (
          <Link
            to={`/players/market/${t.player.id}`}
            className="font-medium text-text hover:text-accent transition-colors"
          >
            {t.player.name}
          </Link>
        ) : (
          <span className="text-text-muted">Unknown</span>
        )}
        {t.player?.position && (
          <Badge
            variant={positionVariant(t.player.position as PlayerPosition)}
            className="ml-2 text-[10px]"
          >
            {t.player.position}
          </Badge>
        )}
      </td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-2 text-sm flex-wrap">
          <span className="text-text-muted">
            {t.seller_club ? (
              <ClubLink id={t.seller_club.id} name={t.seller_club.name} />
            ) : (
              <span className="italic text-text-muted">Free Agent</span>
            )}
          </span>
          <span className="text-text-muted">→</span>
          <span className="text-text-secondary">
            {t.buyer_club ? (
              <ClubLink id={t.buyer_club.id} name={t.buyer_club.name} />
            ) : (
              <span className="text-text-muted">—</span>
            )}
          </span>
        </div>
      </td>
      <td className="px-4 py-3 text-right font-semibold text-text tabular-nums">
        {formatCurrency(t.agreed_fee)}
      </td>
      <td className="px-4 py-3">
        <Badge variant={t.is_auction_deal ? "warning" : "info"}>
          {t.is_auction_deal ? "Auction" : "Offer"}
        </Badge>
      </td>
      <td className="px-4 py-3 text-sm text-text-muted">
        {t.completed_at ? formatDate(t.completed_at) : "—"}
      </td>
    </tr>
  );
}

function FeedTab() {
  const [page, setPage]           = useState(1);
  const [position, setPosition]   = useState("");
  const [dealType, setDealType]   = useState("");   // "" | "auction" | "offer"

  const isAuction = dealType === "auction" ? true : dealType === "offer" ? false : undefined;

  const { data, isLoading, isError } = useQuery<Paginated<TransferActivity>>({
    queryKey: ["transfers", { page, position, dealType }],
    queryFn: () =>
      api
        .get<Paginated<TransferActivity>>("/transfers", {
          params: {
            page,
            page_size: PAGE_SIZE,
            ...(position && { position }),
            ...(isAuction !== undefined && { is_auction: isAuction }),
          },
        })
        .then((r) => r.data),
    staleTime: 60_000,
  });

  function handleFilterChange() {
    setPage(1);
  }

  return (
    <div>
      {/* Filter bar */}
      <div className="mb-5 flex flex-wrap gap-3">
        <select
          value={position}
          onChange={(e) => { setPosition(e.target.value); handleFilterChange(); }}
          className="rounded-lg bg-surface px-3 py-2 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-accent"
        >
          <option value="">All positions</option>
          {POSITIONS.map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
        <select
          value={dealType}
          onChange={(e) => { setDealType(e.target.value); handleFilterChange(); }}
          className="rounded-lg bg-surface px-3 py-2 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-accent"
        >
          <option value="">All types</option>
          <option value="offer">Direct offer</option>
          <option value="auction">Auction</option>
        </select>
        {(position || dealType) && (
          <button
            onClick={() => { setPosition(""); setDealType(""); setPage(1); }}
            className="rounded-lg bg-surface-inset px-3 py-2 text-sm text-text-muted hover:text-text ring-1 ring-input-border transition-colors"
          >
            Clear filters
          </button>
        )}
      </div>

      {isLoading && <div className="flex justify-center py-16"><Spinner size="lg" /></div>}

      {isError && (
        <div className="rounded-xl bg-danger-bg px-5 py-4 text-sm text-danger-text ring-1 ring-danger-border">
          Failed to load transfer activity.
        </div>
      )}

      {data && data.items.length === 0 && (
        <EmptyState title="No transfers" body="No completed transfers match the selected filters." />
      )}

      {data && data.items.length > 0 && (
        <>
          <div className="overflow-x-auto rounded-xl ring-1 ring-border">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-rule text-xs font-semibold uppercase tracking-wider text-text-muted">
                  <th className="px-4 py-3 text-left">Player</th>
                  <th className="px-4 py-3 text-left">Movement</th>
                  <th className="px-4 py-3 text-right">Fee</th>
                  <th className="px-4 py-3 text-left">Type</th>
                  <th className="px-4 py-3 text-left">Date</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((t) => <TransferRow key={t.id} t={t} />)}
              </tbody>
            </table>
          </div>
          <div className="mt-4">
            <Pagination page={page} total={data.total} pageSize={PAGE_SIZE} onChange={setPage} />
          </div>
        </>
      )}
    </div>
  );
}

// ── Analytics tab ─────────────────────────────────────────────────────────────

function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-xl bg-surface px-5 py-4 ring-1 ring-border">
      <p className="text-xs font-semibold uppercase tracking-wider text-text-muted">{label}</p>
      <p className="mt-1.5 text-2xl font-bold text-text tabular-nums">{value}</p>
      {sub && <p className="mt-0.5 text-xs text-text-muted">{sub}</p>}
    </div>
  );
}

function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="mb-4 text-xs font-semibold uppercase tracking-wider text-text-muted">
      {children}
    </h2>
  );
}

function TopTransferRow({ t, rank }: { t: TransferActivity; rank: number }) {
  return (
    <div className="flex items-center gap-3 py-2.5 border-b border-rule-faint last:border-0">
      <span className="w-5 text-center text-sm font-bold text-text-muted tabular-nums shrink-0">{rank}</span>
      <div className="flex-1 min-w-0">
        {t.player ? (
          <Link
            to={`/players/market/${t.player.id}`}
            className="text-sm font-medium text-text hover:text-accent transition-colors"
          >
            {t.player.name}
          </Link>
        ) : (
          <span className="text-sm text-text-muted">Unknown</span>
        )}
        {t.player?.position && (
          <Badge variant={positionVariant(t.player.position as PlayerPosition)} className="ml-1.5 text-[10px]">
            {t.player.position}
          </Badge>
        )}
        <div className="mt-0.5 text-xs text-text-muted flex items-center gap-1.5">
          <span>{t.seller_club?.name ?? "Free Agent"}</span>
          <span>→</span>
          <span>{t.buyer_club?.name ?? "—"}</span>
        </div>
      </div>
      <span className="text-sm font-semibold text-text tabular-nums shrink-0">
        {formatCurrency(t.agreed_fee)}
      </span>
    </div>
  );
}

function PositionBar({ position, count, total, spend }: { position: string; count: number; total: number; spend: number }) {
  const pct = total > 0 ? Math.round((count / total) * 100) : 0;
  const COLORS: Record<string, string> = {
    GK: "bg-pos-gk-text",
    DEF: "bg-pos-def-text",
    MID: "bg-pos-mid-text",
    FWD: "bg-pos-fwd-text",
  };
  return (
    <div className="py-2">
      <div className="mb-1.5 flex items-center justify-between text-xs">
        <span className="font-medium text-text-secondary">{position}</span>
        <span className="tabular-nums text-text-muted">{count} · {formatCurrency(spend)}</span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-border">
        <div
          className={`h-1.5 rounded-full ${COLORS[position] ?? "bg-text-muted"} transition-all`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

const STAGE_LABELS: Record<string, string> = {
  AGREEMENT: "Agreement",
  PAPERWORK: "Paperwork",
  CONFIRMED: "Ready to Execute",
};

const STAGE_COLOR: Record<string, string> = {
  AGREEMENT: "text-warning-text bg-warning-fill/10 ring-warning-fill/20",
  PAPERWORK: "text-accent bg-accent/10 ring-accent/20",
  CONFIRMED: "text-success-text bg-success/10 ring-success/20",
};

function AnalyticsTab() {
  const { data, isLoading, isError } = useQuery<TransferAnalytics>({
    queryKey: ["transfers", "analytics"],
    queryFn: () => api.get<TransferAnalytics>("/transfers/analytics").then((r) => r.data),
    staleTime: 5 * 60_000,
  });

  if (isLoading) return <div className="flex justify-center py-16"><Spinner size="lg" /></div>;
  if (isError || !data) return (
    <div className="rounded-xl bg-danger-bg px-5 py-4 text-sm text-danger-text ring-1 ring-danger-border">
      Failed to load analytics.
    </div>
  );

  const { completed: c, ongoing: o } = data;
  const totalPositions = c.by_position.reduce((s, p) => s + p.count, 0);

  return (
    <div className="space-y-10">

      {/* ── Market Summary ── */}
      <section>
        <SectionHeading>Market Summary</SectionHeading>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatCard label="Total Transfers" value={c.total_count.toString()} />
          <StatCard label="Total Spend" value={formatCurrency(c.total_spend)} />
          <StatCard label="Avg Fee" value={c.avg_fee != null ? formatCurrency(c.avg_fee) : "—"} />
          <StatCard
            label="Last 30 Days"
            value={c.recent_30d_count.toString()}
            sub={formatCurrency(c.recent_30d_spend) + " spent"}
          />
        </div>
      </section>

      {/* ── Top Clubs + Deal Types ── */}
      <section>
        <SectionHeading>Club Activity</SectionHeading>
        <div className="grid gap-4 sm:grid-cols-3">
          {/* Most active buyer */}
          <div className="rounded-xl bg-surface px-5 py-4 ring-1 ring-border">
            <p className="text-xs font-semibold uppercase tracking-wider text-text-muted mb-3">Most Active Buyer</p>
            {c.most_active_buyer ? (
              <>
                <p className="text-base font-bold text-text">{c.most_active_buyer.club.name}</p>
                <p className="mt-0.5 text-sm text-text-muted">{c.most_active_buyer.count} purchase{c.most_active_buyer.count !== 1 ? "s" : ""}</p>
                <p className="mt-0.5 text-xs text-text-muted">{formatCurrency(c.most_active_buyer.total_spend)} spent</p>
              </>
            ) : <p className="text-sm text-text-muted">No data</p>}
          </div>

          {/* Most active seller */}
          <div className="rounded-xl bg-surface px-5 py-4 ring-1 ring-border">
            <p className="text-xs font-semibold uppercase tracking-wider text-text-muted mb-3">Most Active Seller</p>
            {c.most_active_seller ? (
              <>
                <p className="text-base font-bold text-text">{c.most_active_seller.club.name}</p>
                <p className="mt-0.5 text-sm text-text-muted">{c.most_active_seller.count} sale{c.most_active_seller.count !== 1 ? "s" : ""}</p>
                <p className="mt-0.5 text-xs text-text-muted">{formatCurrency(c.most_active_seller.total_spend)} earned</p>
              </>
            ) : <p className="text-sm text-text-muted">No data</p>}
          </div>

          {/* Deal types */}
          <div className="rounded-xl bg-surface px-5 py-4 ring-1 ring-border">
            <p className="text-xs font-semibold uppercase tracking-wider text-text-muted mb-3">Deal Types</p>
            <div className="space-y-2">
              {[
                { label: "Direct Offer", count: c.offer_count, color: "bg-accent" },
                { label: "Auction",      count: c.auction_count, color: "bg-warning-fill" },
              ].map(({ label, count, color }) => {
                const total = c.offer_count + c.auction_count;
                const pct = total > 0 ? Math.round((count / total) * 100) : 0;
                return (
                  <div key={label}>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-text-secondary">{label}</span>
                      <span className="text-text-muted tabular-nums">{count} ({pct}%)</span>
                    </div>
                    <div className="h-1.5 w-full rounded-full bg-border">
                      <div className={`h-1.5 rounded-full ${color}`} style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </section>

      {/* ── Top Transfers + Position Breakdown ── */}
      <section>
        <div className="grid gap-6 lg:grid-cols-2">
          {/* Top 5 transfers */}
          <div className="rounded-xl bg-surface px-5 py-4 ring-1 ring-border">
            <p className="text-xs font-semibold uppercase tracking-wider text-text-muted mb-3">
              Biggest Transfers
            </p>
            {c.top_transfers.length === 0 ? (
              <p className="text-sm text-text-muted">No completed transfers yet.</p>
            ) : (
              c.top_transfers.map((t, i) => <TopTransferRow key={t.id} t={t} rank={i + 1} />)
            )}
          </div>

          {/* By position */}
          <div className="rounded-xl bg-surface px-5 py-4 ring-1 ring-border">
            <p className="text-xs font-semibold uppercase tracking-wider text-text-muted mb-3">
              Activity by Position
            </p>
            {c.by_position.length === 0 ? (
              <p className="text-sm text-text-muted">No data.</p>
            ) : (
              c.by_position.map((p) => (
                <PositionBar
                  key={p.position}
                  position={p.position}
                  count={p.count}
                  total={totalPositions}
                  spend={p.total_spend}
                />
              ))
            )}
          </div>
        </div>
      </section>

      {/* ── Ongoing Transfers ── */}
      <section>
        <SectionHeading>Ongoing Transfers</SectionHeading>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-xl bg-surface px-5 py-4 ring-1 ring-border sm:col-span-1">
            <p className="text-xs font-semibold uppercase tracking-wider text-text-muted">Active Deals</p>
            <p className="mt-1.5 text-2xl font-bold text-text tabular-nums">{o.total_count}</p>
            <p className="mt-0.5 text-xs text-text-muted">{formatCurrency(o.total_committed_fees)} in committed fees</p>
          </div>
          {Object.entries(o.by_stage).length === 0 ? (
            <div className="rounded-xl bg-surface-inset px-5 py-4 ring-1 ring-border sm:col-span-3 flex items-center">
              <p className="text-sm text-text-muted">No active deals in progress.</p>
            </div>
          ) : (
            Object.entries(o.by_stage).map(([stage, count]) => (
              <div
                key={stage}
                className={`rounded-xl px-5 py-4 ring-1 ${STAGE_COLOR[stage] ?? "text-text-muted bg-surface ring-border"}`}
              >
                <p className="text-xs font-semibold uppercase tracking-wider opacity-70">
                  {STAGE_LABELS[stage] ?? stage}
                </p>
                <p className="mt-1.5 text-2xl font-bold tabular-nums">{count}</p>
                <p className="mt-0.5 text-xs opacity-60">deal{count !== 1 ? "s" : ""}</p>
              </div>
            ))
          )}
        </div>
      </section>

      {/* ── Transfer Rumors ── */}
      <section>
        <SectionHeading>Transfer Rumors</SectionHeading>
        <div className="rounded-xl bg-surface-inset px-6 py-8 ring-1 ring-border ring-dashed text-center">
          <p className="text-sm font-medium text-text-muted">Rumors coming soon</p>
          <p className="mt-1 text-xs text-text-muted">
            Unconfirmed transfer links and market speculation will appear here.
          </p>
        </div>
      </section>

    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function TransferActivityPage() {
  const [tab, setTab] = useState<Tab>("feed");

  return (
    <div>
      <PageHeader
        title="Transfers"
        subtitle={tab === "feed" ? "All completed transfers on the platform" : "Market-wide transfer analytics"}
      />
      <TabNav active={tab} onChange={setTab} />
      {tab === "feed"      && <FeedTab />}
      {tab === "analytics" && <AnalyticsTab />}
    </div>
  );
}
