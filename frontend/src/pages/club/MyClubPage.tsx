import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { Club, FairValueSignal, Loan, Paginated, PlayerDetail, PlayerForm, Sale } from "../../types/api";
import Button from "../../components/ui/Button";
import Badge from "../../components/ui/Badge";
import Card from "../../components/ui/Card";
import EmptyState from "../../components/ui/EmptyState";
import Spinner from "../../components/ui/Spinner";
import SaleCard from "../../components/sales/SaleCard";
import SquadTable from "../../components/players/SquadTable";
import LoansPanel from "../../components/players/LoansPanel";
import SquadRail from "../../components/clubs/SquadRail";
import ClubInfoPanel from "../../components/clubs/ClubInfoPanel";
import FinanceSummaryPanel from "../../components/clubs/FinanceSummaryPanel";
import TopPerformers from "../../components/clubs/TopPerformers";
import SquadStatsPanel from "../../components/clubs/SquadStatsPanel";
import FixturesPanel from "../../components/fixtures/FixturesPanel";
import VerifiedBadge from "../../components/verification/VerifiedBadge";
import RequestVerificationPanel from "../../components/verification/RequestVerificationPanel";
import { formatCurrency, getApiError } from "../../lib/utils";
import { useClubCapabilities } from "../../hooks/useClubCapabilities";

type Tab = "squad" | "stats" | "listings" | "fixtures";

// ── Tier-2 squad figures ──────────────────────────────────────────────────────

function FigureCard({ label, value, note, warn }: { label: string; value: string; note?: string; warn?: boolean }) {
  return (
    <Card tier={2}>
      <p className="text-xs font-semibold text-text-secondary">{label}</p>
      <p className={`mt-1.5 text-[28px] font-bold tracking-[-0.01em] ${warn ? "text-warning-text" : "text-text"}`}>{value}</p>
      {note && <p className="mt-[3px] text-xs text-text-muted">{note}</p>}
    </Card>
  );
}

export default function MyClubPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { can } = useClubCapabilities();
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

  // TRA-92: one batch valuation call per squad load, never per row. This page
  // is club-only (ClubRoute) so no D6 player-account check is needed here.
  const { data: fairValues = {} } = useQuery<Record<string, FairValueSignal>>({
    queryKey: ["valuation", "batch", "squad", club?.id],
    enabled: !!squadData && squadData.items.length > 0,
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
  // Fetched unconditionally (not gated to the listings tab) — the squad tab's
  // "Listed" chip and per-row flag both need this to cross-reference players.

  const { data: salesData, isLoading: salesLoading } = useQuery<Paginated<Sale>>({
    queryKey: ["sales", { sellerClubId: club?.id, status: "OPEN" }],
    queryFn: () =>
      api.get<Paginated<Sale>>("/sales", { params: { seller_club_id: club!.id, status: "OPEN", page_size: 20 } })
        .then((r) => r.data),
    enabled: !!club?.id,
  });

  const listedPlayerIds = useMemo(
    () => new Set((salesData?.items ?? []).map((s) => s.player_id)),
    [salesData]
  );

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

  // Players we have borrowed. They are in the squad (we hold their
  // registration) but we do not own them, so the row must not offer to list
  // or sell them — the server already refuses.
  const { data: loansIn = [] } = useQuery<Loan[]>({
    queryKey: ["clubs", "me", "loans", "in"],
    queryFn: () => api.get<Loan[]>("/clubs/me/loans?direction=in").then((r) => r.data),
    staleTime: 60_000,
  });
  const loanedIn = useMemo(
    () =>
      new Map(
        loansIn.map((l) => [
          l.player_id,
          { endDate: l.end_date, parentClubName: l.parent_club?.name ?? null },
        ]),
      ),
    [loansIn],
  );

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

  const canClubAdmin   = can("CLUB_ADMIN");
  const canMarketWrite = can("MARKET_WRITE");
  const isStaff        = !!club.my_role && club.my_role !== "OWNER";
  const players        = squadData?.items ?? [];

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

  const contractsUnder12mo = players.filter((p) => {
    const end = p.active_contract?.end_date;
    if (!end) return false;
    return (new Date(end).getTime() - Date.now()) / (30 * 86_400_000) < 12;
  }).length;
  const agesKnown = players.filter((p) => p.age != null);
  const averageAge = agesKnown.length > 0 ? agesKnown.reduce((s, p) => s + (p.age ?? 0), 0) / agesKnown.length : null;

  return (
    <div>
      {/* ── Header ── */}
      <div className="mb-6 flex items-start gap-5">
        <div className="flex h-20 w-20 shrink-0 items-center justify-center rounded-2xl bg-surface-inset overflow-hidden ring-1 ring-border">
          {club.crest_url ? (
            <img src={club.crest_url} alt={club.name} className="h-full w-full object-contain p-2" />
          ) : (
            <span className="text-3xl font-bold text-text-muted">{club.name[0]?.toUpperCase()}</span>
          )}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-2xl font-bold text-text">{club.name}</h1>
            <Badge variant="neutral">{club.role}</Badge>
            {club.verified && <VerifiedBadge />}
            {isStaff && (
              <Badge variant={club.my_role === "READONLY" ? "neutral" : "info"}>
                {club.my_role?.replace(/_/g, " ")}
              </Badge>
            )}
          </div>
          <p className="mt-1 text-sm text-text-muted">
            {[club.league_name, club.city, club.country].filter(Boolean).join(" · ") || "—"}
          </p>
          {squadData && (
            <p className="mt-1 text-xs text-text-muted">
              {squadData.total} player{squadData.total !== 1 ? "s" : ""} in squad
            </p>
          )}
        </div>
        <div className="flex shrink-0 gap-2">
          {can("TEAM_MANAGE") && (
            <Button variant="secondary" size="sm" onClick={() => navigate("/club/team")}>
              Team
            </Button>
          )}
          {canClubAdmin && !editing && (
            <Button variant="secondary" size="sm" onClick={openEdit}>
              Edit profile
            </Button>
          )}
        </div>
      </div>

      {/* ── Inline edit form ── */}
      {editing && (
        <div className="mb-6 rounded-xl bg-surface-inset ring-1 ring-border px-6 py-5">
          <p className="mb-4 text-sm font-semibold text-text">Edit Club Profile</p>
          <form onSubmit={handleSubmit} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {[
              { label: "Club name",  value: name,     set: setName,     placeholder: "e.g. Arsenal FC" },
              { label: "Country",    value: country,  set: setCountry,  placeholder: "e.g. England" },
              { label: "City",       value: city,     set: setCity,     placeholder: "e.g. London" },
              { label: "League",     value: league,   set: setLeague,   placeholder: "e.g. Premier League" },
              { label: "Crest URL",  value: crestUrl, set: setCrestUrl, placeholder: "https://..." },
            ].map(({ label, value, set, placeholder }) => (
              <div key={label}>
                <label className="mb-1.5 block text-xs font-medium text-text-muted">{label}</label>
                <input
                  type="text"
                  value={value}
                  onChange={(e) => set(e.target.value)}
                  placeholder={placeholder}
                  className="w-full rounded-lg bg-surface px-3 py-2 text-sm text-text placeholder-text-muted ring-1 ring-input-border focus:outline-none focus:ring-accent transition-colors"
                />
              </div>
            ))}
            <div className="sm:col-span-2 lg:col-span-3">
              {formError && <p className="mb-3 text-sm text-danger-text">{formError}</p>}
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
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_260px]">
        {/* Main content */}
        <div>
          {/* Tabs */}
          <div className="mb-6 flex w-fit max-w-full gap-1 overflow-x-auto rounded-xl bg-surface-inset p-1">
            {tabs.map((t) => (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={`rounded-lg px-4 py-1.5 text-sm font-medium transition-colors ${
                  tab === t.id ? "bg-surface text-text shadow-sm" : "text-text-muted hover:text-text"
                }`}
              >
                {t.label}
                {t.id === "squad" && squadData && (
                  <span className="ml-1.5 rounded-full bg-surface-inset px-1.5 py-0.5 text-xs text-text-secondary">
                    {squadData.total}
                  </span>
                )}
                {t.id === "listings" && salesData && salesData.total > 0 && (
                  <span className="ml-1.5 rounded-full bg-accent-bg px-1.5 py-0.5 text-xs text-accent-active">
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
                  <div className="mb-5 grid gap-3.5" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(230px, 1fr))" }}>
                    <FigureCard label="Contracts < 12mo" value={String(contractsUnder12mo)} warn={contractsUnder12mo > 0} />
                    <FigureCard label="Listed" value={String(listedPlayerIds.size)} />
                    <FigureCard label="Average age" value={averageAge != null ? averageAge.toFixed(1) : "—"} />
                    <FigureCard label="Wage room" value={club.finance ? formatCurrency(Number(club.finance.wage_remaining_weekly)) : "—"} note="per week" />
                  </div>

                  {Object.keys(formScores).length > 0 && (
                    <TopPerformers players={players} formScores={formScores} />
                  )}
                  <SquadTable
                    players={players}
                    showContractDetails
                    formScores={formScores}
                    fairValues={fairValues}
                    onToggleOpenToOffers={canMarketWrite ? toggleOpenToOffers : undefined}
                    onSetValuation={canMarketWrite ? setValuation : undefined}
                    listedPlayerIds={listedPlayerIds}
                    loanedIn={loanedIn}
                  />
                </>
              )}
              {/* Outside the empty-squad branch on purpose: a club can have
                  every player out on loan and an otherwise empty squad, and
                  that is exactly when it most needs to see them. */}
              {!squadLoading && <LoansPanel canAct={canMarketWrite} />}
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
                    canMarketWrite ? (
                      <Button variant="primary" onClick={() => navigate("/sales/new")}>
                        Create listing
                      </Button>
                    ) : undefined
                  }
                />
              ) : (
                <>
                  <div className="mb-4 flex items-center justify-between">
                    <p className="text-sm text-text-muted">
                      {salesData.total} active listing{salesData.total !== 1 ? "s" : ""}
                    </p>
                    <div className="flex gap-2">
                      <Button variant="secondary" size="sm" onClick={() => navigate("/sales/mine")}>
                        View all
                      </Button>
                      {canMarketWrite && (
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
          {tab === "squad" && players.length > 0 && <SquadRail players={players} />}
          <ClubInfoPanel
            club={club}
            squadSize={squadData?.total ?? null}
            openListings={null}
          />
          {club.finance && <FinanceSummaryPanel finance={club.finance} />}
          {canClubAdmin && <RequestVerificationPanel verified={club.verified} />}
        </div>
      </div>
    </div>
  );
}
