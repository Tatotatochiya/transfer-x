import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { Club, Paginated, PlayerDetail, PlayerForm, Sale } from "../../types/api";
import Button from "../../components/ui/Button";
import Badge from "../../components/ui/Badge";
import EmptyState from "../../components/ui/EmptyState";
import Spinner from "../../components/ui/Spinner";
import SaleCard from "../../components/sales/SaleCard";
import SquadTable from "../../components/players/SquadTable";
import ClubInfoPanel from "../../components/clubs/ClubInfoPanel";
import FinanceSummaryPanel from "../../components/clubs/FinanceSummaryPanel";
import TopPerformers from "../../components/clubs/TopPerformers";
import SquadStatsPanel from "../../components/clubs/SquadStatsPanel";
import FixturesPanel from "../../components/fixtures/FixturesPanel";
import VerifiedBadge from "../../components/verification/VerifiedBadge";
import RequestVerificationPanel from "../../components/verification/RequestVerificationPanel";
import { getApiError } from "../../lib/utils";

type Tab = "squad" | "stats" | "listings" | "fixtures";

export default function MyClubPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<Tab>("squad");
  const [editing, setEditing] = useState(false);

  // ── Club data ─────────────────────────────────────────────────────────────

  const { data: club, isLoading } = useQuery<Club>({
    queryKey: ["clubs", "me"],
    queryFn: () => api.get<Club>("/clubs/me").then((r) => r.data),
    staleTime: 60_000,
  });

  // ── Squad ─────────────────────────────────────────────────────────────────

  const { data: squadData, isLoading: squadLoading } = useQuery<Paginated<PlayerDetail>>({
    queryKey: ["clubs", club?.id, "squad"],
    queryFn: () =>
      api.get<Paginated<PlayerDetail>>(`/clubs/${club!.id}/players`, { params: { page_size: 100 } })
        .then((r) => r.data),
    enabled: !!club?.id,
  });

  const { data: formScores = {} } = useQuery<Record<string, { score: number; trend: number | null }>>({
    queryKey: ["clubs", club?.id, "squad", "forms"],
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

  // ── Listings ──────────────────────────────────────────────────────────────

  const { data: salesData, isLoading: salesLoading } = useQuery<Paginated<Sale>>({
    queryKey: ["sales", { sellerClubId: club?.id, status: "OPEN" }],
    queryFn: () =>
      api.get<Paginated<Sale>>("/sales", { params: { seller_club_id: club!.id, status: "OPEN", page_size: 20 } })
        .then((r) => r.data),
    enabled: !!club?.id && tab === "listings",
  });

  // ── Edit form ─────────────────────────────────────────────────────────────

  const [name, setName]       = useState("");
  const [country, setCountry] = useState("");
  const [city, setCity]       = useState("");
  const [league, setLeague]   = useState("");
  const [crestUrl, setCrestUrl] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  function openEdit() {
    if (!club) return;
    setName(club.name);
    setCountry(club.country ?? "");
    setCity(club.city ?? "");
    setLeague(club.league_name ?? "");
    setCrestUrl(club.crest_url ?? "");
    setFormError(null);
    setEditing(true);
  }

  const updateMutation = useMutation({
    mutationFn: (body: object) => api.patch<Club>("/clubs/me", body).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["clubs", "me"] });
      setEditing(false);
    },
    onError: (err: unknown) => setFormError(getApiError(err, "Failed to update.")),
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);
    const body: Record<string, string | null> = {};
    if (name)     body.name         = name;
    if (country)  body.country      = country;
    if (city)     body.city         = city;
    if (league)   body.league_name  = league;
    if (crestUrl) body.crest_url    = crestUrl;
    updateMutation.mutate(body);
  }

  // ── Open to offers toggle (optimistic) ───────────────────────────────────

  const squadQueryKey = ["clubs", club?.id, "squad"] as const;

  const toggleOTOMutation = useMutation({
    mutationFn: ({ playerId, next }: { playerId: string; next: boolean }) =>
      api.patch(`/clubs/me/players/${playerId}`, { open_to_offers: next }),
    onMutate: async ({ playerId, next }) => {
      await queryClient.cancelQueries({ queryKey: squadQueryKey });
      const prev = queryClient.getQueryData<Paginated<PlayerDetail>>(squadQueryKey);
      if (prev) {
        queryClient.setQueryData<Paginated<PlayerDetail>>(squadQueryKey, {
          ...prev,
          items: prev.items.map((p) =>
            p.id === playerId ? { ...p, open_to_offers: next } : p
          ),
        });
      }
      return { prev };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev) queryClient.setQueryData(squadQueryKey, ctx.prev);
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: squadQueryKey });
    },
  });

  function toggleOpenToOffers(playerId: string, next: boolean) {
    toggleOTOMutation.mutate({ playerId, next });
  }

  // ── Valuation ─────────────────────────────────────────────────────────────

  const valuationMutation = useMutation({
    mutationFn: ({ playerId, value }: { playerId: string; value: number | null }) =>
      api.patch(`/clubs/me/players/${playerId}`, { club_valuation: value }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: squadQueryKey });
    },
  });

  function setValuation(playerId: string, value: number | null) {
    valuationMutation.mutate({ playerId, value });
  }

  // ── Render ────────────────────────────────────────────────────────────────

  if (isLoading) {
    return <div className="flex items-center justify-center py-20"><Spinner size="lg" /></div>;
  }
  if (!club) return null;

  const isReadOnly = club.my_role === "READONLY";
  const isStaff    = club.my_role === "MANAGER" || club.my_role === "READONLY";
  const players    = squadData?.items ?? [];

  // Derive vendor team ID from the squad's world_team links
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
      {/* ── Header ── */}
      <div className="mb-6 flex items-start gap-5">
        <div className="flex h-20 w-20 shrink-0 items-center justify-center rounded-2xl bg-slate-800 overflow-hidden ring-1 ring-white/[0.08]">
          {club.crest_url ? (
            <img src={club.crest_url} alt={club.name} className="h-full w-full object-contain p-2" />
          ) : (
            <span className="text-3xl font-bold text-slate-500">{club.name[0]?.toUpperCase()}</span>
          )}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-2xl font-bold text-white">{club.name}</h1>
            <Badge variant="neutral">{club.role}</Badge>
            {club.verified && <VerifiedBadge />}
            {isStaff && (
              <Badge variant={isReadOnly ? "neutral" : "info"}>{club.my_role}</Badge>
            )}
          </div>
          <p className="mt-1 text-sm text-slate-400">
            {[club.league_name, club.city, club.country].filter(Boolean).join(" · ") || "—"}
          </p>
          {squadData && (
            <p className="mt-1 text-xs text-slate-600">
              {squadData.total} player{squadData.total !== 1 ? "s" : ""} in squad
            </p>
          )}
        </div>
        {!isReadOnly && (
          <div className="flex shrink-0 gap-2">
            {!editing && (
              <Button variant="secondary" size="sm" onClick={openEdit}>
                Edit profile
              </Button>
            )}
          </div>
        )}
      </div>

      {/* ── Inline edit form ── */}
      {editing && (
        <div className="mb-6 rounded-xl bg-slate-800/60 ring-1 ring-white/[0.08] px-6 py-5">
          <p className="mb-4 text-sm font-semibold text-white">Edit Club Profile</p>
          <form onSubmit={handleSubmit} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {[
              { label: "Club name",  value: name,     set: setName,     placeholder: "e.g. Arsenal FC" },
              { label: "Country",    value: country,  set: setCountry,  placeholder: "e.g. England" },
              { label: "City",       value: city,     set: setCity,     placeholder: "e.g. London" },
              { label: "League",     value: league,   set: setLeague,   placeholder: "e.g. Premier League" },
              { label: "Crest URL",  value: crestUrl, set: setCrestUrl, placeholder: "https://..." },
            ].map(({ label, value, set, placeholder }) => (
              <div key={label}>
                <label className="mb-1.5 block text-xs font-medium text-slate-400">{label}</label>
                <input
                  type="text"
                  value={value}
                  onChange={(e) => set(e.target.value)}
                  placeholder={placeholder}
                  className="w-full rounded-lg bg-slate-900 px-3 py-2 text-sm text-white placeholder-slate-600 ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500 transition-colors"
                />
              </div>
            ))}
            <div className="sm:col-span-2 lg:col-span-3">
              {formError && <p className="mb-3 text-sm text-red-400">{formError}</p>}
              <div className="flex gap-3">
                <Button type="submit" variant="primary" size="sm" loading={updateMutation.isPending}>
                  Save changes
                </Button>
                <Button type="button" variant="ghost" size="sm" onClick={() => setEditing(false)}>
                  Cancel
                </Button>
              </div>
            </div>
          </form>
        </div>
      )}

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
                {t.id === "listings" && salesData && salesData.total > 0 && (
                  <span className="ml-1.5 rounded-full bg-emerald-500/20 px-1.5 py-0.5 text-xs text-emerald-400">
                    {salesData.total}
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
                <EmptyState
                  title="No players in squad"
                  body="Add players to your squad to see them here."
                  action={
                    <Button variant="primary" onClick={() => navigate("/players/market")}>
                      Browse players
                    </Button>
                  }
                />
              ) : (
                <>
                  {Object.keys(formScores).length > 0 && (
                    <TopPerformers players={players} formScores={formScores} />
                  )}
                  <SquadTable
                    players={players}
                    showContractDetails
                    formScores={formScores}
                    onToggleOpenToOffers={isReadOnly ? undefined : toggleOpenToOffers}
                    onSetValuation={isReadOnly ? undefined : setValuation}
                  />
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
                <EmptyState title="No squad data" body="Add players to your squad to see statistics." />
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
              <EmptyState
                title="No fixture data"
                body="Squad must be loaded and linked to a world team before fixtures can be shown."
              />
            )
          )}

          {/* Listings tab */}
          {tab === "listings" && (
            <>
              {salesLoading ? (
                <div className="flex justify-center py-12"><Spinner size="lg" /></div>
              ) : !salesData || salesData.items.length === 0 ? (
                <EmptyState
                  title="No active listings"
                  body="You have no players currently listed for sale or auction."
                  action={
                    !isReadOnly ? (
                      <Button variant="primary" onClick={() => navigate("/sales/new")}>
                        Create listing
                      </Button>
                    ) : undefined
                  }
                />
              ) : (
                <>
                  <div className="mb-4 flex items-center justify-between">
                    <p className="text-sm text-slate-400">
                      {salesData.total} active listing{salesData.total !== 1 ? "s" : ""}
                    </p>
                    <div className="flex gap-2">
                      <Button variant="secondary" size="sm" onClick={() => navigate("/sales/mine")}>
                        View all
                      </Button>
                      {!isReadOnly && (
                        <Button variant="primary" size="sm" onClick={() => navigate("/sales/new")}>
                          + New listing
                        </Button>
                      )}
                    </div>
                  </div>
                  <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    {salesData.items.map((sale) => (
                      <SaleCard key={sale.id} sale={sale} />
                    ))}
                  </div>
                </>
              )}
            </>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-4 lg:sticky lg:top-6 h-fit">
          <ClubInfoPanel
            club={club}
            squadSize={squadData?.total ?? null}
            openListings={null}
          />
          {club.finance && <FinanceSummaryPanel finance={club.finance} />}
          {!isReadOnly && <RequestVerificationPanel verified={club.verified} />}
        </div>
      </div>
    </div>
  );
}
