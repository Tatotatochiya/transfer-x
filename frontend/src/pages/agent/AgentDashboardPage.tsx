import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type {
  AgentDealInvitation,
  AgentPipelineResponse,
  AgentProfileResponse,
  PipelineDealItem,
  RepresentedPlayerItem,
} from "../../types/api";
import Badge from "../../components/ui/Badge";
import Card from "../../components/ui/Card";
import PageHeader from "../../components/ui/PageHeader";
import Spinner from "../../components/ui/Spinner";
import { formatCurrency, formatDate } from "../../lib/utils";
import IntelligenceFeed from "../../components/agent/IntelligenceFeed";
import WaitingOnYouBand, { type WaitingItem } from "../../components/dashboard/WaitingOnYouBand";
import FigureCard from "../../components/dashboard/FigureCard";
import WorkingPanel from "../../components/dashboard/WorkingPanel";
import ReferencePanel from "../../components/dashboard/ReferencePanel";

// ── Client roster (full list, this page's core purpose — never capped) ───────

const CLIENT_STATUS_LABEL: Record<string, string> = {
  ACTIVE: "Active",
  SEEKING_MOVE: "Seeking move",
  LOAN_AVAILABLE: "Loan available",
  CONTRACT_EXTENSION: "Contract extension",
  UNAVAILABLE: "Unavailable",
};

const CLIENT_STATUS_COLOUR: Record<string, string> = {
  ACTIVE: "text-success-text",
  SEEKING_MOVE: "text-accent",
  LOAN_AVAILABLE: "text-accent",
  CONTRACT_EXTENSION: "text-warning-text",
  UNAVAILABLE: "text-text-muted",
};

function ClientCard({ client }: { client: RepresentedPlayerItem }) {
  const queryClient = useQueryClient();
  const [revoking, setRevoking] = useState(false);

  async function handleRevoke(e: React.MouseEvent) {
    e.preventDefault();
    setRevoking(true);
    try {
      await api.post(`/mandates/${client.mandate_id}/revoke`);
      queryClient.invalidateQueries({ queryKey: ["agents", "me", "players"] });
      queryClient.invalidateQueries({ queryKey: ["players", client.player_id, "representation"] });
    } finally {
      setRevoking(false);
    }
  }

  return (
    <Link to={`/agent/clients/${client.mandate_id}`} className="block">
      <Card hover>
        <div className="flex items-center justify-between gap-4">
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-text">{client.player_name}</p>
            <div className="mt-0.5 flex items-center gap-2 text-xs">
              {client.player_position && <span className="text-text-muted">{client.player_position}</span>}
              <span className={CLIENT_STATUS_COLOUR[client.client_status] ?? "text-text-muted"}>
                · {CLIENT_STATUS_LABEL[client.client_status] ?? client.client_status}
              </span>
            </div>
          </div>
          <div className="flex items-center gap-2 text-xs shrink-0">
            {client.exclusive && <Badge variant="info">Exclusive</Badge>}
            {client.end_date && <span className="text-text-muted">Until {formatDate(client.end_date)}</span>}
            <button
              onClick={handleRevoke}
              disabled={revoking}
              className="rounded-lg bg-danger-bg px-2.5 py-1 text-xs font-medium text-danger-text ring-1 ring-danger-border hover:bg-danger/15 transition-colors disabled:opacity-50"
            >
              {revoking ? "…" : "Revoke"}
            </button>
          </div>
        </div>
      </Card>
    </Link>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

const STAGE_LABEL: Record<string, string> = {
  AGREEMENT: "agreement",
  AGENT_NEGOTIATION: "agent negotiation",
  PERSONAL_TERMS: "personal terms",
  PAPERWORK: "paperwork",
  CONFIRMED: "confirmed",
  COMPLETED: "completed",
};

const EXPIRING_MANDATE_WITHIN_DAYS = 90;

function daysUntil(iso: string): number {
  return Math.ceil((new Date(iso).getTime() - Date.now()) / 86_400_000);
}

export default function AgentDashboardPage() {
  const navigate = useNavigate();

  const { data: profile, isLoading: profileLoading } = useQuery<AgentProfileResponse>({
    queryKey: ["agents", "me"],
    queryFn: () => api.get<AgentProfileResponse>("/agents/me").then((r) => r.data),
  });

  const { data: clients = [], isLoading: clientsLoading } = useQuery<RepresentedPlayerItem[]>({
    queryKey: ["agents", "me", "players"],
    queryFn: () => api.get<RepresentedPlayerItem[]>("/agents/me/players").then((r) => r.data),
  });

  const { data: invitations = [] } = useQuery<AgentDealInvitation[]>({
    queryKey: ["agents", "me", "invitations"],
    queryFn: () => api.get<AgentDealInvitation[]>("/agents/me/invitations").then((r) => r.data),
  });

  const { data: pipeline } = useQuery<AgentPipelineResponse>({
    queryKey: ["agents", "me", "pipeline"],
    queryFn: () => api.get<AgentPipelineResponse>("/agents/me/pipeline").then((r) => r.data),
  });

  if (profileLoading || clientsLoading) {
    return <div className="flex items-center justify-center py-20"><Spinner size="lg" /></div>;
  }

  const pipelineItems = pipeline?.items ?? [];
  const pendingInvitations = invitations.filter((inv) => inv.status === "PENDING");

  // ── Tier 1 ──
  const waitingItems: WaitingItem[] = [
    ...pendingInvitations.map((inv): WaitingItem => ({
      key: `invitation-${inv.id}`,
      title: inv.deal?.player_name ?? "Deal invitation",
      description: `${inv.deal?.seller_club_name ?? "?"} → ${inv.deal?.buyer_club_name ?? "?"}`,
      amount: inv.deal?.agreed_fee ?? null,
      deadline: null,
      actionLabel: "Enter deal room",
      onClick: () => navigate(`/deals/${inv.deal_id}`),
    })),
    ...pipelineItems
      .filter((item) => item.action_required)
      .map((item): WaitingItem => ({
        key: `pipeline-${item.deal_id}`,
        title: item.player_name,
        description: `${item.seller_club_name ?? "?"} → ${item.buyer_club_name ?? "?"} · ${STAGE_LABEL[item.stage] ?? item.stage}`,
        amount: item.agreed_fee,
        deadline: null,
        actionLabel: "Open",
        onClick: () => navigate(`/deals/${item.deal_id}`),
      })),
  ];

  // ── Tier 3 ──
  const pipelineRows = pipelineItems.slice(0, 3).map((item: PipelineDealItem) => ({
    key: item.deal_id,
    onClick: () => navigate(`/deals/${item.deal_id}`),
    name: item.player_name,
    sub: `${item.seller_club_name ?? "?"} → ${item.buyer_club_name ?? "?"}`,
    value: item.agreed_fee != null ? formatCurrency(item.agreed_fee) : "—",
    move: item.action_required ? ("your" as const) : ("neither" as const),
  }));

  // ── Tier 4 ──
  const expiringMandateRows = clients
    .filter((c) => c.end_date && daysUntil(c.end_date) >= 0 && daysUntil(c.end_date) <= EXPIRING_MANDATE_WITHIN_DAYS)
    .sort((a, b) => new Date(a.end_date!).getTime() - new Date(b.end_date!).getTime())
    .slice(0, 5)
    .map((c) => {
      const days = daysUntil(c.end_date!);
      return {
        key: c.mandate_id,
        onClick: () => navigate(`/agent/clients/${c.mandate_id}`),
        label: c.player_name,
        sub: formatDate(c.end_date),
        value: `${days}d`,
        valueColour: days <= 30 ? "text-danger-text" : days <= 60 ? "text-warning-text" : "text-text-secondary",
      };
    });

  return (
    <div>
      <PageHeader
        title="My Roster"
        subtitle={profile ? `${profile.agency_name} · ${profile.country}` : ""}
      />

      <WaitingOnYouBand items={waitingItems} />

      <div className="mb-[18px] grid gap-3.5" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(230px, 1fr))" }}>
        <FigureCard label="Active deals" value={String(pipeline?.deals_in_progress ?? 0)} />
        <FigureCard label="Completed (90d)" value={String(pipeline?.deals_completed_this_window ?? 0)} />
        <FigureCard
          label="Commission pipeline"
          value={pipeline && pipeline.total_commission_pipeline > 0 ? formatCurrency(pipeline.total_commission_pipeline) : "—"}
        />
        <FigureCard label="Active mandates" value={String(clients.length)} />
      </div>

      <div className="mb-[18px] grid gap-4" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))" }}>
        <WorkingPanel title="Deal pipeline" linkTo="/agent/pipeline" rows={pipelineRows} />
        <ReferencePanel title="Expiring mandates" rows={expiringMandateRows} />
      </div>

      <div className="mb-[18px]">
        <IntelligenceFeed />
      </div>

      {/* Client roster — this page's core purpose, always shown in full */}
      <div>
        {clients.length === 0 ? (
          <Card tier={4} className="text-center py-10">
            <p className="text-sm font-medium text-text">No represented players yet</p>
            <p className="mt-1 text-sm text-text-muted">Browse the market or import your existing roster.</p>
            <div className="mt-4 flex justify-center gap-3">
              <Link
                to="/players/market"
                className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white hover:bg-accent-hover transition-colors"
              >
                Browse players
              </Link>
              <button
                onClick={() => navigate("/agent/roster/import")}
                className="rounded-lg bg-surface-inset px-4 py-2 text-sm font-semibold text-text ring-1 ring-border hover:ring-input-border transition-colors"
              >
                Import roster
              </button>
            </div>
          </Card>
        ) : (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold uppercase tracking-wider text-text-muted">
                {clients.length} active mandate{clients.length !== 1 ? "s" : ""}
              </p>
              <button
                onClick={() => navigate("/agent/roster/import")}
                className="text-xs text-text-muted hover:text-text-secondary transition-colors"
              >
                + Import more
              </button>
            </div>
            {clients.map((c) => (
              <ClientCard key={c.mandate_id} client={c} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
