import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import api from "../../lib/api";
import type { AgentProfileResponse, RepresentedPlayerItem } from "../../types/api";
import Card from "../../components/ui/Card";
import PageHeader from "../../components/ui/PageHeader";
import Spinner from "../../components/ui/Spinner";
import Badge from "../../components/ui/Badge";

function ClientCard({ client }: { client: RepresentedPlayerItem }) {
  return (
    <Card>
      <div className="flex items-center justify-between">
        <div>
          <Link
            to={`/players/market/${client.player_id}`}
            className="text-sm font-semibold text-white hover:text-emerald-400 transition-colors"
          >
            {client.player_name}
          </Link>
          {client.player_position && (
            <p className="text-xs text-slate-400 mt-0.5">{client.player_position}</p>
          )}
        </div>
        <div className="flex items-center gap-2 text-xs">
          {client.exclusive && (
            <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-emerald-400 font-medium">
              Exclusive
            </span>
          )}
          {client.end_date && (
            <span className="text-slate-500">Until {client.end_date}</span>
          )}
        </div>
      </div>
    </Card>
  );
}

export default function AgentDashboardPage() {
  const { data: profile, isLoading: profileLoading } = useQuery<AgentProfileResponse>({
    queryKey: ["agents", "me"],
    queryFn: () => api.get<AgentProfileResponse>("/agents/me").then((r) => r.data),
  });

  const { data: clients = [], isLoading: clientsLoading } = useQuery<RepresentedPlayerItem[]>({
    queryKey: ["agents", "me", "players"],
    queryFn: () => api.get<RepresentedPlayerItem[]>("/agents/me/players").then((r) => r.data),
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

      {/* Clients */}
      <div className="mt-6">
        {clients.length === 0 ? (
          <div className="rounded-xl bg-slate-900 px-5 py-10 text-center ring-1 ring-white/[0.08]">
            <p className="text-sm font-medium text-white">No represented players yet</p>
            <p className="mt-1 text-sm text-slate-500">
              Browse the market to find players to represent.
            </p>
            <Link
              to="/players/market"
              className="mt-4 inline-block rounded-lg bg-emerald-500 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-400 transition-colors"
            >
              Browse players
            </Link>
          </div>
        ) : (
          <div className="space-y-3">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              {clients.length} active mandate{clients.length !== 1 ? "s" : ""}
            </p>
            {clients.map((c) => (
              <ClientCard key={c.mandate_id} client={c} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
