import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import api from "../../lib/api";
import type { AgentDealInvitation, AgentPipelineResponse, AgentProfileResponse, PipelineDealItem, RepresentedPlayerItem } from "../../types/api";
import Card from "../../components/ui/Card";
import PageHeader from "../../components/ui/PageHeader";
import Spinner from "../../components/ui/Spinner";
import Badge from "../../components/ui/Badge";
import { formatCurrency, formatDate } from "../../lib/utils";

const CLIENT_STATUS_COLORS: Record<string, string> = {
  ACTIVE:             "text-emerald-400",
  SEEKING_MOVE:       "text-sky-400",
  LOAN_AVAILABLE:     "text-purple-400",
  CONTRACT_EXTENSION: "text-amber-400",
  UNAVAILABLE:        "text-slate-500",
};

const CLIENT_STATUS_LABELS: Record<string, string> = {
  ACTIVE:             "Active",
  SEEKING_MOVE:       "Seeking move",
  LOAN_AVAILABLE:     "Loan available",
  CONTRACT_EXTENSION: "Contract extension",
  UNAVAILABLE:        "Unavailable",
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
      <Card>
        <div className="flex items-center justify-between gap-4">
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-white hover:text-emerald-400 transition-colors">
              {client.player_name}
            </p>
            <div className="mt-0.5 flex items-center gap-2 text-xs">
              {client.player_position && (
                <span className="text-slate-400">{client.player_position}</span>
              )}
              <span className={CLIENT_STATUS_COLORS[client.client_status] ?? "text-slate-500"}>
                · {CLIENT_STATUS_LABELS[client.client_status] ?? client.client_status}
              </span>
            </div>
          </div>
          <div className="flex items-center gap-2 text-xs shrink-0">
            {client.exclusive && (
              <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-emerald-400 font-medium">
                Exclusive
              </span>
            )}
            {client.end_date && (
              <span className="text-slate-500">Until {client.end_date}</span>
            )}
            <button
              onClick={handleRevoke}
              disabled={revoking}
              className="rounded-lg bg-red-500/10 px-2.5 py-1 text-xs font-medium text-red-400 ring-1 ring-red-500/30 hover:bg-red-500/20 transition-colors disabled:opacity-50"
            >
              {revoking ? "…" : "Revoke"}
            </button>
          </div>
        </div>
      </Card>
    </Link>
  );
}

const STAGE_LABELS: Record<string, string> = {
  AGREEMENT: "Agreement",
  AGENT_NEGOTIATION: "Agent Negotiation",
  PERSONAL_TERMS: "Personal Terms",
  PAPERWORK: "Paperwork",
  CONFIRMED: "Confirmed",
  COMPLETED: "Completed",
};

function PipelineRow({ item }: { item: PipelineDealItem }) {
  return (
    <Link to={`/deals/${item.deal_id}`} className="block">
      <div
        className={`rounded-xl px-4 py-3 ring-1 transition-all hover:ring-emerald-500/30 ${
          item.action_required
            ? "bg-amber-500/5 ring-amber-500/20 hover:ring-amber-500/40"
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
                <span className="shrink-0 rounded-full bg-amber-500/20 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-amber-400">
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
              {STAGE_LABELS[item.stage] ?? item.stage}
            </p>
            {item.commission_amount != null && (
              <p className="text-[11px] text-emerald-400 tabular-nums mt-0.5">
                {formatCurrency(item.commission_amount)}
              </p>
            )}
          </div>
        </div>
      </div>
    </Link>
  );
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
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner size="lg" />
      </div>
    );
  }

  return (
    <div className="max-w-3xl">
      <PageHeader
        title="My Roster"
        subtitle={profile ? `${profile.agency_name} · ${profile.country}` : ""}
      />

      {/* Profile summary */}
      {profile && (
        <Card>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-base font-semibold text-white">{profile.display_name}</p>
              <p className="text-sm text-slate-400 mt-0.5">{profile.agency_name}</p>
            </div>
            <div className="flex items-center gap-2">
              {profile.verified && <Badge variant="success">Verified</Badge>}
              <Link
                to="/agent/profile"
                className="text-xs text-slate-400 hover:text-white transition-colors"
              >
                Edit profile →
              </Link>
            </div>
          </div>
        </Card>
      )}

      {/* Deal invitations — prominent banner (TRA-126) */}
      {invitations.length > 0 && (
        <div className="mt-6 rounded-xl bg-purple-500/10 ring-2 ring-purple-500/40 overflow-hidden">
          {/* Header */}
          <div className="flex items-center gap-3 bg-purple-500/15 px-5 py-3">
            <span className="flex h-5 w-5 items-center justify-center rounded-full bg-purple-500 text-[10px] font-bold text-white">
              {invitations.length}
            </span>
            <p className="text-sm font-bold text-purple-300">
              {invitations.length === 1 ? "New deal invitation" : `${invitations.length} new deal invitations`} — action required
            </p>
          </div>
          {/* Cards */}
          <div className="divide-y divide-purple-500/10">
            {invitations.map((inv) => {
              const daysSince = Math.floor(
                (Date.now() - new Date(inv.created_at).getTime()) / (1000 * 60 * 60 * 24)
              );
              return (
                <div key={inv.id} className="px-5 py-4">
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0 flex-1">
                      <p className="text-base font-bold text-white truncate">
                        {inv.deal?.player_name ?? "Unknown player"}
                      </p>
                      <p className="text-sm text-slate-400 mt-0.5 truncate">
                        {inv.deal?.seller_club_name ?? "?"} → {inv.deal?.buyer_club_name ?? "?"}
                      </p>
                      <div className="mt-2 flex flex-wrap items-center gap-3 text-xs">
                        {inv.deal?.agreed_fee != null && (
                          <span className="font-semibold text-white">
                            {formatCurrency(inv.deal.agreed_fee)} agreed fee
                          </span>
                        )}
                        <span className={`font-medium ${daysSince === 0 ? "text-red-400" : daysSince <= 2 ? "text-amber-400" : "text-slate-400"}`}>
                          {daysSince === 0 ? "Today" : `${daysSince}d ago`}
                        </span>
                        <span className="text-slate-500">Invited {formatDate(inv.created_at)}</span>
                      </div>
                    </div>
                    <Link
                      to={`/deals/${inv.deal_id}`}
                      className="shrink-0 rounded-lg bg-purple-500 px-4 py-2 text-sm font-bold text-white hover:bg-purple-400 transition-colors"
                    >
                      Enter deal room →
                    </Link>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Pipeline (TRA-130) */}
      {pipeline && pipeline.items.length > 0 && (
        <div className="mt-6">
          <div className="mb-3 flex items-center justify-between">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Deal pipeline
            </p>
            <div className="flex items-center gap-4 text-xs text-slate-500">
              <span>
                <span className="text-white font-semibold">{pipeline.deals_in_progress}</span> active
              </span>
              <span>
                <span className="text-white font-semibold">{pipeline.deals_completed_this_window}</span> completed
              </span>
              {pipeline.total_commission_pipeline > 0 && (
                <span className="text-emerald-400 font-semibold">
                  {formatCurrency(pipeline.total_commission_pipeline)} pipeline
                </span>
              )}
            </div>
          </div>
          <div className="space-y-2">
            {pipeline.items.map((item) => (
              <PipelineRow key={item.deal_id} item={item} />
            ))}
          </div>
        </div>
      )}

      {/* Clients */}
      <div className="mt-6">
        {clients.length === 0 ? (
          <div className="rounded-xl bg-slate-900 px-5 py-10 text-center ring-1 ring-white/[0.08]">
            <p className="text-sm font-medium text-white">No represented players yet</p>
            <p className="mt-1 text-sm text-slate-500">
              Browse the market or import your existing roster.
            </p>
            <div className="mt-4 flex justify-center gap-3">
              <Link
                to="/players/market"
                className="rounded-lg bg-emerald-500 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-400 transition-colors"
              >
                Browse players
              </Link>
              <button
                onClick={() => navigate("/agent/roster/import")}
                className="rounded-lg bg-slate-800 px-4 py-2 text-sm font-semibold text-white ring-1 ring-white/10 hover:ring-white/20 transition-colors"
              >
                Import roster
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                {clients.length} active mandate{clients.length !== 1 ? "s" : ""}
              </p>
              <button
                onClick={() => navigate("/agent/roster/import")}
                className="text-xs text-slate-400 hover:text-white transition-colors"
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
