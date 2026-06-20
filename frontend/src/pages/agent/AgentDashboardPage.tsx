import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import api from "../../lib/api";
import type { AgentDealInvitation, AgentProfileResponse, RepresentedPlayerItem } from "../../types/api";
import Card from "../../components/ui/Card";
import PageHeader from "../../components/ui/PageHeader";
import Spinner from "../../components/ui/Spinner";
import Badge from "../../components/ui/Badge";
import { formatCurrency } from "../../lib/utils";

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
        title="My Clients"
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

      {/* Pending deal invitations (TRA-74) */}
      {invitations.length > 0 && (
        <div className="mt-6">
          <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-purple-400">
            Pending invitations · {invitations.length}
          </p>
          <div className="space-y-3">
            {invitations.map((inv) => (
              <Link key={inv.id} to={`/deals/${inv.deal_id}`} className="block">
                <div className="rounded-xl bg-purple-500/5 ring-1 ring-purple-500/20 px-4 py-3 hover:ring-purple-500/40 transition-all">
                  <div className="flex items-center justify-between gap-4">
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-white truncate">
                        {inv.deal?.player_name ?? "Unknown player"}
                      </p>
                      <p className="text-xs text-slate-400 mt-0.5 truncate">
                        {inv.deal?.buyer_club_name ?? "Unknown buyer"} ← {inv.deal?.seller_club_name ?? "Unknown seller"}
                      </p>
                    </div>
                    <div className="text-right shrink-0">
                      {inv.deal?.agreed_fee != null && (
                        <p className="text-sm font-semibold text-white">
                          {formatCurrency(inv.deal.agreed_fee)}
                        </p>
                      )}
                      <p className="text-[10px] text-purple-400 font-medium mt-0.5">View deal →</p>
                    </div>
                  </div>
                </div>
              </Link>
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
