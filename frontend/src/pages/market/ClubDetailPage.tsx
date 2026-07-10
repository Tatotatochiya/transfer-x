import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import api from "../../lib/api";
import type { ClubPublic, FairValueSignal, Paginated, PlayerDetail, PlayerForm, Sale } from "../../types/api";
import { useAuthStore } from "../../store/auth";
import SaleCard from "../../components/sales/SaleCard";
import SquadTable from "../../components/players/SquadTable";
import ClubInfoPanel from "../../components/clubs/ClubInfoPanel";
import TopPerformers from "../../components/clubs/TopPerformers";
import SquadStatsPanel from "../../components/clubs/SquadStatsPanel";
import EmptyState from "../../components/ui/EmptyState";
import Spinner from "../../components/ui/Spinner";
import FixturesPanel from "../../components/fixtures/FixturesPanel";
import VerifiedBadge from "../../components/verification/VerifiedBadge";

type Tab = "squad" | "stats" | "listings" | "fixtures";

export default function ClubDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>("squad");
  const { accessToken, user } = useAuthStore();
  const isAuthenticated = !!accessToken;
  const isPlayerAccount = user?.user_type === "PLAYER";

  // ── Club data ─────────────────────────────────────────────────────────────

  const { data: club, isLoading, isError } = useQuery<ClubPublic>({
    queryKey: ["clubs", id],
    queryFn: () => api.get<ClubPublic>(`/clubs/${id}`).then((r) => r.data),
    enabled: !!id,
  });

  // ── Squad ─────────────────────────────────────────────────────────────────

  const { data: squadData, isLoading: squadLoading } = useQuery<Paginated<PlayerDetail>>({
    queryKey: ["clubs", id, "squad"],
    queryFn: () =>
      api.get<Paginated<PlayerDetail>>(`/clubs/${id}/players`, { params: { page_size: 100 } })
        .then((r) => r.data),
    enabled: !!id && (tab === "squad" || tab === "stats"),
  });

  const { data: formScores = {} } = useQuery<Record<string, { score: number; trend: number | null }>>({
    queryKey: ["clubs", id, "squad", "forms"],
    queryFn: async () => {
      const players = squadData?.items ?? [];
      if (players.length === 0) return {};
      const playerIds = players.map((p) => p.id).join(",");
      const resp = await api
        .get<Record<string, PlayerForm>>("/players/form/batch", { params: { player_ids: playerIds } })
        .catch(() => ({ data: {} as Record<string, PlayerForm> }));
      const map: Record<string, { score: number; trend: number | null }> = {};
      for (const [pid, form] of Object.entries(resp.data)) {
        map[pid] = { score: Number(form.form_score), trend: form.trend != null ? Number(form.trend) : null };
      }
      return map;
    },
    enabled: !!squadData && squadData.items.length > 0,
    staleTime: 60_000,
  });

  // TRA-92: one batch valuation call per squad load, never per row.
  // D6: a player-account or anonymous viewer must not fire the call at all.
  const { data: fairValues = {} } = useQuery<Record<string, FairValueSignal>>({
    queryKey: ["valuation", "batch", "squad", id],
    enabled: isAuthenticated && !isPlayerAccount && !!squadData && squadData.items.length > 0,
    staleTime: 300_000,
    queryFn: async () => {
      const ids = (squadData?.items ?? []).map((p) => p.id).join(",");
      const resp = await api
        .get<{ valuations: Record<string, FairValueSignal> }>("/valuation/players", { params: { ids } })
        .catch(() => ({ data: { valuations: {} as Record<string, FairValueSignal> } }));
      return resp.data.valuations;
    },
  });

  // ── Listings ──────────────────────────────────────────────────────────────

  const { data: salesData, isLoading: salesLoading } = useQuery<Paginated<Sale>>({
    queryKey: ["sales", { sellerClubId: id, status: "OPEN" }],
    queryFn: () =>
      api.get<Paginated<Sale>>("/sales", { params: { seller_club_id: id, status: "OPEN", page_size: 20 } })
        .then((r) => r.data),
    enabled: !!id && tab === "listings",
  });

  const { data: listingsCount } = useQuery<number>({
    queryKey: ["sales-count", id],
    queryFn: () =>
      api.get<Paginated<Sale>>("/sales", { params: { seller_club_id: id, status: "OPEN", page_size: 1 } })
        .then((r) => r.data.total),
    enabled: !!id,
  });

  // ── Render ────────────────────────────────────────────────────────────────

  if (isLoading) {
    return <div className="flex items-center justify-center py-20"><Spinner size="lg" /></div>;
  }

  if (isError || !club) {
    return (
      <div className="rounded-xl bg-red-500/10 px-5 py-4 text-sm text-red-400 ring-1 ring-red-500/30">
        Club not found.{" "}
        <button onClick={() => navigate(-1)} className="underline">Go back</button>
      </div>
    );
  }

  const players = squadData?.items ?? [];

  // Derive vendor team ID from squad — use the most common world_team.vendor_id
  const vendorTeamId: number | null = (() => {
    const ids = players.map((p) => p.world_team?.vendor_id).filter(Boolean) as string[];
    if (ids.length === 0) return null;
    const freq: Record<string, number> = {};
    for (const vid of ids) freq[vid] = (freq[vid] ?? 0) + 1;
    const top = Object.entries(freq).sort((a, b) => b[1] - a[1])[0];
    return top ? Number(top[0]) : null;
  })();

  const tabs: { id: Tab; label: string }[] = [
    { id: "squad",    label: "Squad" },
    { id: "stats",    label: "Stats" },
    { id: "listings", label: "Listings" },
    { id: "fixtures", label: "Fixtures" },
  ];

  return (
    <div>
      {/* Back */}
      <button
        onClick={() => navigate(-1)}
        className="mb-6 flex items-center gap-1.5 text-sm text-slate-400 hover:text-white transition-colors"
      >
        ← Back
      </button>

      {/* ── Header ── */}
      <div className="mb-6 flex items-start gap-5">
        <div className="flex h-20 w-20 shrink-0 items-center justify-center rounded-2xl bg-slate-800 overflow-hidden ring-1 ring-white/[0.08]">
          {club.crest_url ? (
            <img src={club.crest_url} alt={club.name} loading="lazy" className="h-full w-full object-contain p-2" />
          ) : (
            <span className="text-3xl font-bold text-slate-500">{club.name[0]?.toUpperCase()}</span>
          )}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-2xl font-bold text-white">{club.name}</h1>
            {club.verified && <VerifiedBadge />}
          </div>
          <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-slate-400">
            {club.league_name && <span>{club.league_name}</span>}
            {club.city && (
              <>
                {club.league_name && <span className="text-slate-700">·</span>}
                <span>{club.city}</span>
              </>
            )}
            {club.country && (
              <>
                {(club.league_name || club.city) && <span className="text-slate-700">·</span>}
                <span>{club.country}</span>
              </>
            )}
          </div>
          {squadData && (
            <p className="mt-1 text-xs text-slate-600">
              {squadData.total} player{squadData.total !== 1 ? "s" : ""} in squad
            </p>
          )}
        </div>
      </div>

      {/* ── Two-column layout ── */}
      <div className="grid gap-6 lg:grid-cols-[1fr_260px]">
        {/* Main content */}
        <div>
          {/* Tabs */}
          <div className="mb-6 flex gap-1 rounded-xl bg-slate-800/50 p-1 w-fit">
            {tabs.map((t) => (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={`rounded-lg px-4 py-1.5 text-sm font-medium transition-colors ${
                  tab === t.id ? "bg-slate-700 text-white shadow-sm" : "text-slate-400 hover:text-white"
                }`}
              >
                {t.label}
                {t.id === "squad" && squadData && (
                  <span className="ml-1.5 rounded-full bg-slate-600 px-1.5 py-0.5 text-xs text-slate-300">
                    {squadData.total}
                  </span>
                )}
                {t.id === "listings" && (listingsCount ?? 0) > 0 && (
                  <span className="ml-1.5 rounded-full bg-emerald-500/20 px-1.5 py-0.5 text-xs text-emerald-400">
                    {listingsCount}
                  </span>
                )}
              </button>
            ))}
          </div>

          {/* Squad tab */}
          {tab === "squad" && (
            <>
              {squadLoading ? (
                <div className="flex justify-center py-12"><Spinner size="lg" /></div>
              ) : players.length === 0 ? (
                <EmptyState title="Squad not available" body="No players from this club are listed publicly." />
              ) : (
                <>
                  {Object.keys(formScores).length > 0 && (
                    <TopPerformers players={players} formScores={formScores} />
                  )}
                  <SquadTable players={players} formScores={formScores} fairValues={fairValues} />
                </>
              )}
            </>
          )}

          {/* Stats tab */}
          {tab === "stats" && (
            <>
              {squadLoading ? (
                <div className="flex justify-center py-12"><Spinner size="lg" /></div>
              ) : players.length === 0 ? (
                <EmptyState title="No squad data" body="No players from this club are listed publicly." />
              ) : (
                <SquadStatsPanel players={players} />
              )}
            </>
          )}

          {/* Fixtures tab */}
          {tab === "fixtures" && (
            vendorTeamId ? (
              <FixturesPanel vendorTeamId={vendorTeamId} />
            ) : (
              <EmptyState title="No fixture data" body="Squad must be loaded before fixtures can be shown." />
            )
          )}

          {/* Listings tab */}
          {tab === "listings" && (
            <>
              {salesLoading ? (
                <div className="flex justify-center py-12"><Spinner size="lg" /></div>
              ) : !salesData || salesData.items.length === 0 ? (
                <EmptyState title="No open listings" body="This club has no players currently listed for sale." />
              ) : (
                <div className="grid gap-4 sm:grid-cols-2">
                  {salesData.items.map((sale) => (
                    <SaleCard key={sale.id} sale={sale} />
                  ))}
                </div>
              )}
            </>
          )}
        </div>

        {/* Sidebar */}
        <div className="lg:sticky lg:top-6 h-fit">
          <ClubInfoPanel
            club={club}
            squadSize={squadData?.total ?? null}
            openListings={listingsCount ?? null}
          />
        </div>
      </div>
    </div>
  );
}
