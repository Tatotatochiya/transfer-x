import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import api from "../../lib/api";
import type { AgentPipelineResponse, PipelineDealItem } from "../../types/api";
import Spinner from "../../components/ui/Spinner";
import PageHeader from "../../components/ui/PageHeader";
import { formatCurrency } from "../../lib/utils";

// ── Stage config ──────────────────────────────────────────────────────────────

const PIPELINE_STAGES = [
  { key: "AGENT_NEGOTIATION", label: "Agent Negotiation" },
  { key: "PERSONAL_TERMS",    label: "Personal Terms"    },
  { key: "PAPERWORK",         label: "Paperwork"         },
  { key: "CONFIRMED",         label: "Confirmed"         },
  { key: "COMPLETED",         label: "Completed"         },
] as const;

type StageKey = typeof PIPELINE_STAGES[number]["key"];

const COLUMN_HEADER: Record<StageKey, string> = {
  AGENT_NEGOTIATION: "text-purple-400",
  PERSONAL_TERMS:    "text-amber-400",
  PAPERWORK:         "text-sky-400",
  CONFIRMED:         "text-emerald-400",
  COMPLETED:         "text-slate-400",
};

const COLUMN_CARD: Record<StageKey, string> = {
  AGENT_NEGOTIATION: "ring-purple-500/20 bg-purple-500/[0.04]",
  PERSONAL_TERMS:    "ring-amber-500/20 bg-amber-500/[0.04]",
  PAPERWORK:         "ring-sky-500/20 bg-sky-500/[0.04]",
  CONFIRMED:         "ring-emerald-500/20 bg-emerald-500/[0.04]",
  COMPLETED:         "ring-white/[0.07] bg-slate-900",
};

// ── Kanban card ───────────────────────────────────────────────────────────────

function DealCard({ item, stageKey }: { item: PipelineDealItem; stageKey: StageKey }) {
  return (
    <Link to={`/deals/${item.deal_id}`} className="block">
      <div
        className={`rounded-xl px-4 py-3 ring-1 transition-all hover:ring-emerald-500/30 ${
          item.action_required
            ? "ring-red-500/40 bg-red-500/[0.04]"
            : COLUMN_CARD[stageKey]
        }`}
      >
        <div className="flex items-start justify-between gap-2 mb-1.5">
          <p className="text-sm font-semibold text-white truncate">{item.player_name}</p>
          {item.action_required && (
            <span className="shrink-0 rounded-full bg-red-500/20 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-red-400">
              Action needed
            </span>
          )}
        </div>
        <p className="text-xs text-slate-500 truncate">
          {item.seller_club_name ?? "?"} → {item.buyer_club_name ?? "?"}
        </p>
        {item.agreed_fee != null && (
          <p className="mt-1.5 text-xs font-semibold text-white tabular-nums">
            {formatCurrency(item.agreed_fee)}
          </p>
        )}
        {item.commission_amount != null && (
          <p className="text-[10px] text-emerald-400 tabular-nums mt-0.5">
            Commission: {formatCurrency(item.commission_amount)}
          </p>
        )}
      </div>
    </Link>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function AgentPipelinePage() {
  const [view, setView] = useState<"kanban" | "list">("kanban");

  const { data: pipeline, isLoading } = useQuery<AgentPipelineResponse>({
    queryKey: ["agents", "me", "pipeline"],
    queryFn: () => api.get<AgentPipelineResponse>("/agents/me/pipeline").then((r) => r.data),
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner size="lg" />
      </div>
    );
  }

  const items = pipeline?.items ?? [];
  const grouped = Object.fromEntries(
    PIPELINE_STAGES.map((s) => [s.key, items.filter((i) => i.stage === s.key)])
  ) as Record<StageKey, PipelineDealItem[]>;

  return (
    <div>
      {/* Header + view toggle */}
      <div className="mb-6 flex items-start justify-between gap-4">
        <PageHeader
          title="Deal Pipeline"
          subtitle="All active and recent deals across your client roster"
        />
        <div className="flex shrink-0 items-center gap-1 rounded-lg bg-slate-800 p-1 ring-1 ring-white/[0.06]">
          <button
            onClick={() => setView("kanban")}
            className={`rounded px-3 py-1.5 text-xs font-medium transition-colors ${
              view === "kanban" ? "bg-slate-700 text-white" : "text-slate-400 hover:text-white"
            }`}
          >
            Kanban
          </button>
          <button
            onClick={() => setView("list")}
            className={`rounded px-3 py-1.5 text-xs font-medium transition-colors ${
              view === "list" ? "bg-slate-700 text-white" : "text-slate-400 hover:text-white"
            }`}
          >
            List
          </button>
        </div>
      </div>

      {/* Summary strip */}
      {pipeline && (
        <div className="mb-6 grid grid-cols-3 gap-3">
          <div className="rounded-xl bg-slate-900 px-4 py-3 text-center ring-1 ring-white/[0.07]">
            <p className="text-2xl font-bold text-white tabular-nums">
              {pipeline.deals_in_progress}
            </p>
            <p className="mt-0.5 text-xs text-slate-500">Active deals</p>
          </div>
          <div className="rounded-xl bg-slate-900 px-4 py-3 text-center ring-1 ring-white/[0.07]">
            <p className="text-2xl font-bold text-white tabular-nums">
              {pipeline.deals_completed_this_window}
            </p>
            <p className="mt-0.5 text-xs text-slate-500">Completed (90 days)</p>
          </div>
          <div className="rounded-xl bg-slate-900 px-4 py-3 text-center ring-1 ring-white/[0.07]">
            <p className="text-2xl font-bold text-emerald-400 tabular-nums">
              {pipeline.total_commission_pipeline > 0
                ? formatCurrency(pipeline.total_commission_pipeline)
                : "—"}
            </p>
            <p className="mt-0.5 text-xs text-slate-500">Commission pipeline</p>
          </div>
        </div>
      )}

      {items.length === 0 ? (
        <div className="rounded-xl bg-slate-900 px-5 py-12 text-center ring-1 ring-white/[0.08]">
          <p className="text-sm font-medium text-white">No active deals</p>
          <p className="mt-1 text-sm text-slate-500">
            Deals for your clients will appear here once clubs make offers.
          </p>
        </div>
      ) : view === "kanban" ? (
        /* Kanban */
        <div className="overflow-x-auto pb-4">
          <div className="grid min-w-[900px] gap-4" style={{ gridTemplateColumns: `repeat(${PIPELINE_STAGES.length}, 1fr)` }}>
            {PIPELINE_STAGES.map(({ key, label }) => {
              const colItems = grouped[key];
              return (
                <div key={key}>
                  <div className="mb-2 flex items-center justify-between">
                    <p className={`text-[11px] font-bold uppercase tracking-wider ${COLUMN_HEADER[key]}`}>
                      {label}
                    </p>
                    {colItems.length > 0 && (
                      <span className="rounded-full bg-slate-700 px-1.5 py-0.5 text-[9px] font-bold tabular-nums text-slate-400">
                        {colItems.length}
                      </span>
                    )}
                  </div>
                  <div className="space-y-2">
                    {colItems.length === 0 ? (
                      <div className="rounded-xl border border-dashed border-white/[0.06] px-3 py-5 text-center">
                        <p className="text-[10px] text-slate-600">—</p>
                      </div>
                    ) : (
                      colItems.map((item) => (
                        <DealCard key={item.deal_id} item={item} stageKey={key} />
                      ))
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ) : (
        /* List */
        <div className="space-y-2">
          {items.map((item) => (
            <Link key={item.deal_id} to={`/deals/${item.deal_id}`} className="block">
              <div
                className={`rounded-xl px-4 py-3 ring-1 transition-all hover:ring-emerald-500/30 ${
                  item.action_required
                    ? "bg-red-500/[0.04] ring-red-500/20"
                    : "bg-slate-900 ring-white/[0.07]"
                }`}
              >
                <div className="flex items-center justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <p className="truncate text-sm font-semibold text-white">
                        {item.player_name}
                      </p>
                      {item.action_required && (
                        <span className="shrink-0 rounded-full bg-red-500/20 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-red-400">
                          Action needed
                        </span>
                      )}
                    </div>
                    <p className="mt-0.5 truncate text-xs text-slate-500">
                      {item.seller_club_name ?? "?"} → {item.buyer_club_name ?? "?"}
                    </p>
                  </div>
                  <div className="shrink-0 text-right">
                    <p className="text-xs font-medium text-slate-400">
                      {item.stage.replace(/_/g, " ")}
                    </p>
                    {item.agreed_fee != null && (
                      <p className="mt-0.5 text-sm font-semibold text-white tabular-nums">
                        {formatCurrency(item.agreed_fee)}
                      </p>
                    )}
                  </div>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
