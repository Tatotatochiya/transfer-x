import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { AdminDeal, Paginated } from "../../types/api";
import Badge from "../../components/ui/Badge";
import DateRangeFilter, { EMPTY_DATE_RANGE, type DateRange } from "../../components/ui/DateRangeFilter";
import Pagination from "../../components/ui/Pagination";
import Spinner from "../../components/ui/Spinner";
import { formatCurrency, formatDate, getApiError } from "../../lib/utils";

const DEAL_STATUSES = ["IN_PROGRESS", "PENDING_COMPLETION", "COMPLETED", "COLLAPSED"];

const STATUS_VARIANT: Record<string, "success" | "info" | "warning" | "neutral" | "danger"> = {
  IN_PROGRESS:         "warning",
  PENDING_COMPLETION:  "info",
  COMPLETED:           "success",
  COLLAPSED:           "danger",
};

const STAGE_VARIANT: Record<string, "success" | "info" | "warning" | "neutral"> = {
  AGREEMENT:  "warning",
  PAPERWORK:  "info",
  CONFIRMED:  "info",
  COMPLETED:  "success",
};

// ── Action buttons (shared between views) ─────────────────────────────────────

function DealActions({
  deal,
  onAdvance,
  onComplete,
  onCollapse,
  isPending,
}: {
  deal: AdminDeal;
  onAdvance: (id: string) => void;
  onComplete: (id: string) => void;
  onCollapse: (id: string) => void;
  isPending: boolean;
}) {
  const isActive = deal.status === "IN_PROGRESS" || deal.status === "PENDING_COMPLETION";
  if (!isActive) return null;
  return (
    <div className="flex gap-1.5 flex-wrap">
      {deal.stage === "PAPERWORK" && (
        <button
          disabled={isPending}
          onClick={(e) => { e.stopPropagation(); onAdvance(deal.id); }}
          className="rounded bg-sky-500/10 px-2 py-1 text-xs text-sky-400 hover:bg-sky-500/20 transition-colors disabled:opacity-40"
        >
          Advance
        </button>
      )}
      <button
        disabled={isPending}
        onClick={(e) => { e.stopPropagation(); onComplete(deal.id); }}
        className="rounded bg-emerald-500/10 px-2 py-1 text-xs text-emerald-400 hover:bg-emerald-500/20 transition-colors disabled:opacity-40"
        title="Force complete"
      >
        Complete
      </button>
      <button
        disabled={isPending}
        onClick={(e) => { e.stopPropagation(); onCollapse(deal.id); }}
        className="rounded bg-red-500/10 px-2 py-1 text-xs text-red-400 hover:bg-red-500/20 transition-colors disabled:opacity-40"
      >
        Collapse
      </button>
    </div>
  );
}

// ── Pipeline card ──────────────────────────────────────────────────────────────

function PipelineCard({
  deal,
  onAdvance,
  onComplete,
  onCollapse,
  isPending,
}: {
  deal: AdminDeal;
  onAdvance: (id: string) => void;
  onComplete: (id: string) => void;
  onCollapse: (id: string) => void;
  isPending: boolean;
}) {
  const now = Date.now();
  const ageDays = Math.floor((now - new Date(deal.updated_at ?? deal.created_at).getTime()) / 86_400_000);
  const isStale = ageDays > (deal.stage === "AGREEMENT" ? 3 : 7);

  return (
    <Link
      to={`/deals/${deal.id}`}
      onClick={(e) => e.stopPropagation()}
      className="block rounded-xl bg-slate-800 ring-1 ring-white/[0.06] p-4 hover:ring-white/[0.18] transition-all space-y-2"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-white">
            {deal.player?.name ?? "Unknown"}
            {deal.player?.position && (
              <span className="ml-1.5 text-xs font-normal text-slate-500">{deal.player.position}</span>
            )}
          </p>
          <p className="mt-0.5 text-xs text-slate-400">
            {deal.buyer_club?.name ?? "?"} ← {deal.seller_club?.name ?? "?"}
          </p>
        </div>
        <p className="shrink-0 text-sm font-semibold text-slate-200">{formatCurrency(deal.agreed_fee)}</p>
      </div>

      <div className="flex items-center gap-2">
        <Badge variant={STATUS_VARIANT[deal.status] ?? "neutral"}>{deal.status.replace("_", " ")}</Badge>
        {isStale && (
          <span className="rounded-full bg-amber-500/15 px-2 py-0.5 text-[10px] font-semibold text-amber-400 ring-1 ring-amber-500/30">
            {ageDays}d stale
          </span>
        )}
      </div>

      <p className="text-xs text-slate-500">{formatDate(deal.created_at)}</p>

      <div onClick={(e) => e.preventDefault()}>
        <DealActions
          deal={deal}
          onAdvance={onAdvance}
          onComplete={onComplete}
          onCollapse={onCollapse}
          isPending={isPending}
        />
      </div>
    </Link>
  );
}

// ── Pipeline view ─────────────────────────────────────────────────────────────

const PIPELINE_STAGES = [
  { key: "AGREEMENT", label: "Agreement",          color: "text-amber-400",   border: "border-amber-500/30"  },
  { key: "PAPERWORK", label: "Paperwork",          color: "text-sky-400",     border: "border-sky-500/30"    },
  { key: "CONFIRMED", label: "Ready to Execute",   color: "text-emerald-400", border: "border-emerald-500/30" },
];

function PipelineView({
  onAdvance, onComplete, onCollapse, isPending,
}: {
  onAdvance: (id: string) => void;
  onComplete: (id: string) => void;
  onCollapse: (id: string) => void;
  isPending: boolean;
}) {
  const { data, isLoading } = useQuery<Paginated<AdminDeal>>({
    queryKey: ["admin", "deals", "pipeline"],
    queryFn: () =>
      api
        .get<Paginated<AdminDeal>>("/admin/deals", { params: { status: "IN_PROGRESS", page: 1, page_size: 200 } })
        .then((r) => r.data),
  });

  if (isLoading) return <div className="flex justify-center py-12"><Spinner size="lg" /></div>;

  const byStage: Record<string, AdminDeal[]> = { AGREEMENT: [], PAPERWORK: [], CONFIRMED: [] };
  for (const d of data?.items ?? []) {
    if (d.stage in byStage) byStage[d.stage].push(d);
  }

  return (
    <div className="grid gap-4 lg:grid-cols-3">
      {PIPELINE_STAGES.map(({ key, label, color, border }) => (
        <div key={key} className={`rounded-xl bg-slate-900 ring-1 ring-white/[0.08] overflow-hidden`}>
          <div className={`border-b ${border} px-4 py-3 flex items-center justify-between`}>
            <p className={`text-xs font-semibold uppercase tracking-wider ${color}`}>{label}</p>
            <span className="rounded-full bg-slate-800 px-2 py-0.5 text-xs font-bold text-white">
              {byStage[key].length}
            </span>
          </div>
          <div className="p-3 space-y-3 min-h-[200px]">
            {byStage[key].length === 0 ? (
              <p className="py-8 text-center text-xs text-slate-600">No deals in this stage</p>
            ) : (
              byStage[key].map((d) => (
                <PipelineCard
                  key={d.id}
                  deal={d}
                  onAdvance={onAdvance}
                  onComplete={onComplete}
                  onCollapse={onCollapse}
                  isPending={isPending}
                />
              ))
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function AdminDealsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [status, setStatus] = useState("");
  const [dateRange, setDateRange] = useState<DateRange>(EMPTY_DATE_RANGE);
  const [page, setPage] = useState(1);
  const [view, setView] = useState<"table" | "pipeline">("table");

  const { data, isLoading } = useQuery<Paginated<AdminDeal>>({
    queryKey: ["admin", "deals", { status, ...dateRange, page }],
    queryFn: () =>
      api
        .get<Paginated<AdminDeal>>("/admin/deals", {
          params: {
            page, page_size: 30,
            ...(status && { status }),
            ...(dateRange.dateFrom && { date_from: dateRange.dateFrom }),
            ...(dateRange.dateTo && { date_to: dateRange.dateTo }),
          },
        })
        .then((r) => r.data),
    enabled: view === "table",
  });

  function handleDateRangeChange(range: DateRange) {
    setDateRange(range);
    setPage(1);
  }

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["admin", "deals"] });
    queryClient.invalidateQueries({ queryKey: ["admin", "stats"] });
  };

  const advanceMutation  = useMutation({ mutationFn: (id: string) => api.post(`/deals/${id}/advance`),          onSuccess: invalidate });
  const completeMutation = useMutation({ mutationFn: (id: string) => api.post(`/deals/${id}/staff/complete`),   onSuccess: invalidate });
  const collapseMutation = useMutation({ mutationFn: (id: string) => api.post(`/deals/${id}/staff/collapse`),   onSuccess: invalidate });

  const isPending = advanceMutation.isPending || completeMutation.isPending || collapseMutation.isPending;

  return (
    <div>
      {/* Header */}
      <div className="mb-6 flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold text-white">Deals</h1>
          {view === "table" && data && (
            <p className="mt-1 text-sm text-slate-400">{data.total} total</p>
          )}
        </div>
        <div className="flex items-center gap-3">
          {/* View toggle */}
          <div className="flex rounded-lg bg-slate-800 p-0.5 ring-1 ring-white/[0.06]">
            {(["table", "pipeline"] as const).map((v) => (
              <button
                key={v}
                onClick={() => setView(v)}
                className={`rounded-md px-3 py-1.5 text-xs font-medium capitalize transition-colors ${
                  view === v ? "bg-slate-700 text-white shadow-sm" : "text-slate-400 hover:text-slate-200"
                }`}
              >
                {v}
              </button>
            ))}
          </div>
          {/* Status filter (table only) */}
          {view === "table" && (
            <select
              value={status}
              onChange={(e) => { setStatus(e.target.value); setPage(1); }}
              className="rounded-lg bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-amber-500"
            >
              <option value="">All statuses</option>
              {DEAL_STATUSES.map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}
            </select>
          )}
        </div>
      </div>

      {view === "table" && (
        <div className="mb-6">
          <DateRangeFilter value={dateRange} onChange={handleDateRangeChange} accent="amber" />
        </div>
      )}

      {/* Error banners */}
      {(advanceMutation.isError || completeMutation.isError || collapseMutation.isError) && (
        <div className="mb-4 rounded-lg bg-red-500/10 px-4 py-2 text-xs text-red-400 ring-1 ring-red-500/20">
          {getApiError(advanceMutation.error ?? completeMutation.error ?? collapseMutation.error, "Action failed.")}
        </div>
      )}

      {/* Pipeline view */}
      {view === "pipeline" && (
        <PipelineView
          onAdvance={(id) => advanceMutation.mutate(id)}
          onComplete={(id) => completeMutation.mutate(id)}
          onCollapse={(id) => collapseMutation.mutate(id)}
          isPending={isPending}
        />
      )}

      {/* Table view */}
      {view === "table" && (
        <>
          {isLoading && <div className="flex justify-center py-12"><Spinner size="lg" /></div>}
          {data && (
            <>
              <div className="overflow-x-auto rounded-xl ring-1 ring-white/[0.08]">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="border-b border-white/[0.08] text-left text-xs font-semibold uppercase tracking-wider text-slate-500">
                      <th className="px-4 py-3">Player</th>
                      <th className="px-4 py-3">Buyer</th>
                      <th className="px-4 py-3">Seller</th>
                      <th className="px-4 py-3">Fee</th>
                      <th className="px-4 py-3">Status</th>
                      <th className="px-4 py-3">Stage</th>
                      <th className="px-4 py-3">Created</th>
                      <th className="px-4 py-3 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/[0.04]">
                    {data.items.map((d) => (
                      <tr
                        key={d.id}
                        onClick={() => navigate(`/deals/${d.id}`)}
                        className="cursor-pointer bg-slate-900 hover:bg-slate-800/40 transition-colors"
                      >
                        <td className="px-4 py-3 font-medium text-white">
                          {d.player?.name ?? "—"}
                          {d.player?.position && (
                            <span className="ml-1.5 text-xs text-slate-500">{d.player.position}</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-xs text-slate-400">{d.buyer_club?.name ?? "—"}</td>
                        <td className="px-4 py-3 text-xs text-slate-400">{d.seller_club?.name ?? "—"}</td>
                        <td className="px-4 py-3 text-slate-300">{formatCurrency(d.agreed_fee)}</td>
                        <td className="px-4 py-3">
                          <Badge variant={STATUS_VARIANT[d.status] ?? "neutral"}>
                            {d.status.replace("_", " ")}
                          </Badge>
                        </td>
                        <td className="px-4 py-3">
                          <Badge variant={STAGE_VARIANT[d.stage] ?? "neutral"}>{d.stage}</Badge>
                        </td>
                        <td className="px-4 py-3 text-xs text-slate-500">{formatDate(d.created_at)}</td>
                        <td className="px-4 py-3 text-right" onClick={(e) => e.stopPropagation()}>
                          <DealActions
                            deal={d}
                            onAdvance={(id) => advanceMutation.mutate(id)}
                            onComplete={(id) => completeMutation.mutate(id)}
                            onCollapse={(id) => collapseMutation.mutate(id)}
                            isPending={isPending}
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Pagination page={data.page} total={data.total} pageSize={data.page_size} onChange={setPage} />
            </>
          )}
        </>
      )}
    </div>
  );
}
