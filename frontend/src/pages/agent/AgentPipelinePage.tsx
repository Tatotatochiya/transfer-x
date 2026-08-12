import { useState } from "react";
import OnboardingChecklist from "../../components/OnboardingChecklist";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type {
  AgentCommission,
  AgentCommissionsResponse,
  AgentPipelineResponse,
  CommissionStatus,
  PipelineDealItem,
} from "../../types/api";
import Spinner from "../../components/ui/Spinner";
import PageHeader from "../../components/ui/PageHeader";
import { formatCurrency } from "../../lib/utils";
import { useToast } from "../../context/ToastContext";

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
  AGENT_NEGOTIATION: "text-role-agent-text",
  PERSONAL_TERMS:    "text-warning-text",
  PAPERWORK:         "text-accent",
  CONFIRMED:         "text-success-text",
  COMPLETED:         "text-text-muted",
};

const COLUMN_CARD: Record<StageKey, string> = {
  AGENT_NEGOTIATION: "ring-role-agent-text/20 bg-role-agent-text/[0.04]",
  PERSONAL_TERMS:    "ring-warning-fill/20 bg-warning-fill/[0.04]",
  PAPERWORK:         "ring-accent/20 bg-accent/[0.04]",
  CONFIRMED:         "ring-success/20 bg-success/[0.04]",
  COMPLETED:         "ring-border bg-surface",
};

// ── Kanban card ───────────────────────────────────────────────────────────────

function DealCard({ item, stageKey }: { item: PipelineDealItem; stageKey: StageKey }) {
  return (
    <Link to={`/deals/${item.deal_id}`} className="block">
      <div
        className={`rounded-xl px-4 py-3 ring-1 transition-all hover:ring-success/30 ${
          item.action_required
            ? "ring-danger/40 bg-danger/[0.04]"
            : COLUMN_CARD[stageKey]
        }`}
      >
        <div className="flex items-start justify-between gap-2 mb-1.5">
          <p className="flex items-center gap-1.5 text-sm font-semibold text-text truncate">
            <span className="truncate">{item.player_name}</span>
            {item.has_unread_messages && (
              <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-accent" title="New messages" />
            )}
          </p>
          {item.action_required && (
            <span className="shrink-0 rounded-full bg-danger/20 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-danger-text">
              Action needed
            </span>
          )}
        </div>
        <p className="text-xs text-text-muted truncate">
          {item.seller_club_name ?? "?"} → {item.buyer_club_name ?? "?"}
        </p>
        {item.agreed_fee != null && (
          <p className="mt-1.5 text-xs font-semibold text-text tabular-nums">
            {formatCurrency(item.agreed_fee)}
          </p>
        )}
        {item.commission_amount != null && (
          <p className="text-[10px] text-success-text tabular-nums mt-0.5">
            Commission: {formatCurrency(item.commission_amount)}
          </p>
        )}
      </div>
    </Link>
  );
}

// ── Commission status config ───────────────────────────────────────────────────

const COMMISSION_STATUS_COLORS: Record<CommissionStatus, string> = {
  PENDING:   "bg-text-muted/15 text-text-muted",
  CONFIRMED: "bg-success/15 text-success-text",
  INVOICED:  "bg-warning-fill/15 text-warning-text",
  PAID:      "bg-accent/15 text-accent",
};

const NEXT_STATUS: Partial<Record<CommissionStatus, CommissionStatus>> = {
  CONFIRMED: "INVOICED",
  INVOICED:  "PAID",
};

const NEXT_STATUS_LABEL: Partial<Record<CommissionStatus, string>> = {
  CONFIRMED: "Mark Invoiced",
  INVOICED:  "Mark Paid",
};

// ── Commission row ─────────────────────────────────────────────────────────────

function CommissionRow({
  commission,
  onAdvance,
  advancing,
}: {
  commission: AgentCommission;
  onAdvance: (id: string, status: CommissionStatus) => void;
  advancing: boolean;
}) {
  const next = NEXT_STATUS[commission.status];
  return (
    <tr className="border-t border-rule-faint hover:bg-surface-inset">
      <td className="px-4 py-3">
        <Link to={`/deals/${commission.deal_id}`} className="text-sm font-medium text-text hover:text-accent transition-colors">
          {commission.deal_id.slice(0, 8)}…
        </Link>
      </td>
      <td className="px-4 py-3 text-right text-sm font-semibold text-text tabular-nums">
        {formatCurrency(commission.amount)}
      </td>
      <td className="px-4 py-3 text-right text-xs text-text-muted tabular-nums">
        {commission.pct != null ? `${(commission.pct * 100).toFixed(2)}%` : "—"}
      </td>
      <td className="px-4 py-3 text-xs text-text-muted">
        {commission.payer ?? "—"}
      </td>
      <td className="px-4 py-3 text-xs text-text-muted">
        {commission.window_label ?? "—"}
      </td>
      <td className="px-4 py-3">
        <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${COMMISSION_STATUS_COLORS[commission.status]}`}>
          {commission.status}
        </span>
      </td>
      <td className="px-4 py-3 text-right">
        {next && (
          <button
            onClick={() => onAdvance(commission.id, next)}
            disabled={advancing}
            className="rounded-lg bg-surface-inset px-2.5 py-1 text-[10px] font-medium text-text-secondary hover:bg-border hover:text-text transition-colors disabled:opacity-40"
          >
            {NEXT_STATUS_LABEL[commission.status]}
          </button>
        )}
      </td>
    </tr>
  );
}

// ── Commissions tab ────────────────────────────────────────────────────────────

function CommissionsTab() {
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const [advancing, setAdvancing] = useState<string | null>(null);

  const { data, isLoading } = useQuery<AgentCommissionsResponse>({
    queryKey: ["agents", "me", "commissions"],
    queryFn: () => api.get<AgentCommissionsResponse>("/agents/me/commissions").then((r) => r.data),
  });

  const advanceMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: CommissionStatus }) =>
      api.patch(`/agents/me/commissions/${id}/status`, { status }).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["agents", "me", "commissions"] });
      addToast("Commission status updated.", "success");
      setAdvancing(null);
    },
    onError: () => {
      addToast("Failed to update status.", "error");
      setAdvancing(null);
    },
  });

  const handleAdvance = (id: string, status: CommissionStatus) => {
    setAdvancing(id);
    advanceMutation.mutate({ id, status });
  };

  if (isLoading) return <div className="flex justify-center py-10"><Spinner size="lg" /></div>;

  const summary = data?.summary;
  const commissions = data?.commissions ?? [];

  return (
    <div>
      {/* First-run checklist (Phase 6) */}
      <OnboardingChecklist />

      {/* Summary cards */}
      <div className="mb-6 grid grid-cols-3 gap-3">
        <div className="rounded-xl bg-surface px-4 py-3 text-center ring-1 ring-border">
          <p className="text-2xl font-bold text-success-text tabular-nums break-words">
            {summary ? formatCurrency(summary.earned) : "—"}
          </p>
          <p className="mt-0.5 text-xs text-text-muted">Earned (paid)</p>
        </div>
        <div className="rounded-xl bg-surface px-4 py-3 text-center ring-1 ring-border">
          <p className="text-2xl font-bold text-warning-text tabular-nums break-words">
            {summary ? formatCurrency(summary.outstanding) : "—"}
          </p>
          <p className="mt-0.5 text-xs text-text-muted">Outstanding (invoiced)</p>
        </div>
        <div className="rounded-xl bg-surface px-4 py-3 text-center ring-1 ring-border">
          <p className="text-2xl font-bold text-text tabular-nums break-words">
            {summary ? formatCurrency(summary.pipeline) : "—"}
          </p>
          <p className="mt-0.5 text-xs text-text-muted">Pipeline (pending)</p>
        </div>
      </div>

      {commissions.length === 0 ? (
        <div className="rounded-xl bg-surface px-5 py-12 text-center ring-1 ring-border">
          <p className="text-sm font-medium text-text">No commissions yet</p>
          <p className="mt-1 text-sm text-text-muted">
            Commission records appear when agent negotiation terms are agreed.
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl ring-1 ring-border">
          <table className="w-full text-sm">
            <thead className="bg-surface-header">
              <tr>
                <th className="px-4 py-2.5 text-left text-[10px] font-semibold uppercase tracking-wider text-text-muted">Deal</th>
                <th className="px-4 py-2.5 text-right text-[10px] font-semibold uppercase tracking-wider text-text-muted">Amount</th>
                <th className="px-4 py-2.5 text-right text-[10px] font-semibold uppercase tracking-wider text-text-muted">%</th>
                <th className="px-4 py-2.5 text-[10px] font-semibold uppercase tracking-wider text-text-muted">Payer</th>
                <th className="px-4 py-2.5 text-[10px] font-semibold uppercase tracking-wider text-text-muted">Window</th>
                <th className="px-4 py-2.5 text-[10px] font-semibold uppercase tracking-wider text-text-muted">Status</th>
                <th className="px-4 py-2.5 text-right text-[10px] font-semibold uppercase tracking-wider text-text-muted">Action</th>
              </tr>
            </thead>
            <tbody>
              {commissions.map((c) => (
                <CommissionRow
                  key={c.id}
                  commission={c}
                  onAdvance={handleAdvance}
                  advancing={advancing === c.id}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function AgentPipelinePage() {
  const [tab, setTab] = useState<"pipeline" | "commissions">("pipeline");
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
      {/* Header */}
      <div className="mb-4 flex items-start justify-between gap-4">
        <PageHeader
          title="Deal Pipeline"
          subtitle="All active and recent deals across your client roster"
        />
        {tab === "pipeline" && (
          <div className="flex shrink-0 items-center gap-1 rounded-lg bg-surface-inset p-1 ring-1 ring-border">
            <button
              onClick={() => setView("kanban")}
              className={`rounded px-3 py-1.5 text-xs font-medium transition-colors ${
                view === "kanban" ? "bg-surface text-text" : "text-text-muted hover:text-text"
              }`}
            >
              Kanban
            </button>
            <button
              onClick={() => setView("list")}
              className={`rounded px-3 py-1.5 text-xs font-medium transition-colors ${
                view === "list" ? "bg-surface text-text" : "text-text-muted hover:text-text"
              }`}
            >
              List
            </button>
          </div>
        )}
      </div>

      {/* Tab nav */}
      <div className="mb-6 flex gap-1 border-b border-rule pb-0">
        {(["pipeline", "commissions"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium capitalize transition-colors border-b-2 -mb-px ${
              tab === t
                ? "border-accent text-text"
                : "border-transparent text-text-muted hover:text-text"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "commissions" ? (
        <CommissionsTab />
      ) : (
      <>

      {/* Summary strip */}
      {pipeline && (
        <div className="mb-6 grid grid-cols-3 gap-3">
          <div className="rounded-xl bg-surface px-4 py-3 text-center ring-1 ring-border">
            <p className="text-2xl font-bold text-text tabular-nums">
              {pipeline.deals_in_progress}
            </p>
            <p className="mt-0.5 text-xs text-text-muted">Active deals</p>
          </div>
          <div className="rounded-xl bg-surface px-4 py-3 text-center ring-1 ring-border">
            <p className="text-2xl font-bold text-text tabular-nums">
              {pipeline.deals_completed_this_window}
            </p>
            <p className="mt-0.5 text-xs text-text-muted">Completed (90 days)</p>
          </div>
          <div className="rounded-xl bg-surface px-4 py-3 text-center ring-1 ring-border">
            <p className="text-2xl font-bold text-success-text tabular-nums break-words">
              {pipeline.total_commission_pipeline > 0
                ? formatCurrency(pipeline.total_commission_pipeline)
                : "—"}
            </p>
            <p className="mt-0.5 text-xs text-text-muted">Commission pipeline</p>
          </div>
        </div>
      )}

      {items.length === 0 ? (
        <div className="rounded-xl bg-surface px-5 py-12 text-center ring-1 ring-border">
          <p className="text-sm font-medium text-text">No active deals</p>
          <p className="mt-1 text-sm text-text-muted">
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
                      <span className="rounded-full bg-text-muted/15 px-1.5 py-0.5 text-[9px] font-bold tabular-nums text-text-muted">
                        {colItems.length}
                      </span>
                    )}
                  </div>
                  <div className="space-y-2">
                    {colItems.length === 0 ? (
                      <div className="rounded-xl border border-dashed border-border px-3 py-5 text-center">
                        <p className="text-[10px] text-text-muted">—</p>
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
                className={`rounded-xl px-4 py-3 ring-1 transition-all hover:ring-success/30 ${
                  item.action_required
                    ? "bg-danger/[0.04] ring-danger/20"
                    : "bg-surface ring-border"
                }`}
              >
                <div className="flex items-center justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <p className="truncate text-sm font-semibold text-text">
                        {item.player_name}
                      </p>
                      {item.has_unread_messages && (
                        <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-accent" title="New messages" />
                      )}
                      {item.action_required && (
                        <span className="shrink-0 rounded-full bg-danger/20 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-danger-text">
                          Action needed
                        </span>
                      )}
                    </div>
                    <p className="mt-0.5 truncate text-xs text-text-muted">
                      {item.seller_club_name ?? "?"} → {item.buyer_club_name ?? "?"}
                    </p>
                  </div>
                  <div className="shrink-0 text-right">
                    <p className="text-xs font-medium text-text-muted">
                      {item.stage.replace(/_/g, " ")}
                    </p>
                    {item.agreed_fee != null && (
                      <p className="mt-0.5 text-sm font-semibold text-text tabular-nums">
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
      </>
      )}
    </div>
  );
}
