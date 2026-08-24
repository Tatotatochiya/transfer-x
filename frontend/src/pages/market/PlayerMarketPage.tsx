import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import { useAuth } from "../../hooks/useAuth";
import { usePreferencesStore } from "../../store/preferences";
import type { Club, FairValueSignal, Paginated, Player, PlayerForm, PlayerSearchView, PlayerStats } from "../../types/api";
import PlayerCard from "../../components/players/PlayerCard";
import PlayerListRow from "../../components/players/PlayerListRow";
import PlayerFilters, {
  DEFAULT_PLAYER_FILTERS,
  type PlayerFilterState,
  type ViewMode,
} from "../../components/players/PlayerFilters";
import ViewSwitcher from "../../components/players/ViewSwitcher";
import Card from "../../components/ui/Card";
import Pagination from "../../components/ui/Pagination";
import EmptyState from "../../components/ui/EmptyState";
import Spinner from "../../components/ui/Spinner";
import { MarketRecommendationsPanel } from "../../components/ai/MarketRecommendationsPanel";
import { NLPlayerSearch } from "../../components/ai/NLPlayerSearch";
import { useCompare } from "../../context/CompareContext";
import { formatCurrency } from "../../lib/utils";

// ── Saveable filter keys (search + club_search are intentionally excluded) ────

type SavedFilters = Omit<PlayerFilterState, "search" | "club_search">;

function toSavedFilters(f: PlayerFilterState): SavedFilters {
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const { search: _s, club_search: _c, ...rest } = f;
  return rest;
}

function applySavedFilters(saved: Record<string, unknown>, current: PlayerFilterState): PlayerFilterState {
  return {
    ...DEFAULT_PLAYER_FILTERS,
    search: current.search,
    club_search: current.club_search,
    position: (saved.position as PlayerFilterState["position"]) ?? "",
    status: (saved.status as PlayerFilterState["status"]) ?? "",
    open_to_offers: (saved.open_to_offers as boolean) ?? false,
    min_age: (saved.min_age as string) ?? "",
    max_age: (saved.max_age as string) ?? "",
    nationality: (saved.nationality as string) ?? "",
    min_goals: (saved.min_goals as string) ?? "",
    min_assists: (saved.min_assists as string) ?? "",
    min_appearances: (saved.min_appearances as string) ?? "",
    min_avg_rating: (saved.min_avg_rating as string) ?? "",
    min_form_score: (saved.min_form_score as string) ?? "",
    min_value: (saved.min_value as string) ?? "",
    max_value: (saved.max_value as string) ?? "",
    contract_expiry_months: (saved.contract_expiry_months as string) ?? "",
    sort_by: (saved.sort_by as PlayerFilterState["sort_by"]) ?? "name",
    sort_dir: (saved.sort_dir as PlayerFilterState["sort_dir"]) ?? "asc",
  };
}

function filtersMatchSaved(f: PlayerFilterState, saved: Record<string, unknown>): boolean {
  const s = toSavedFilters(f);
  const keys = Object.keys(s) as (keyof SavedFilters)[];
  for (const key of keys) {
    const savedVal = (saved[key] ?? DEFAULT_PLAYER_FILTERS[key]) as unknown;
    if (s[key] !== savedVal) return false;
  }
  return true;
}

function getInitialView(): ViewMode {
  return usePreferencesStore.getState().defaultMarketView as ViewMode;
}

// ── Sort chips ─────────────────────────────────────────────────────────────────
// "Form" and "Youngest" map onto real server sort_by values, so they trigger a
// real re-fetch (sorted across every page). "Best value" and "Cheapest" have no
// server-side equivalent — the /players/market endpoint only accepts
// name|age|goals|assists|appearances|avg_rating|form_score — so those two sort
// only the current page, using the fair-value/market-value data already on
// screen. Documented rather than silently wrong.

type SortChip = "value" | "form" | "cheapest" | "youngest";

const SORT_CHIPS: { key: SortChip; label: string }[] = [
  { key: "value", label: "Best value first" },
  { key: "form", label: "Form" },
  { key: "cheapest", label: "Cheapest" },
  { key: "youngest", label: "Youngest" },
];

// ── Page ──────────────────────────────────────────────────────────────────────

export default function PlayerMarketPage() {
  const { accessToken, user, isClub } = useAuth();
  const isAuthenticated = !!accessToken;
  const isPlayerAccount = user?.user_type === "PLAYER";
  const queryClient = useQueryClient();
  const { compareIds } = useCompare();

  const [filters, setFilters] = useState<PlayerFilterState>(DEFAULT_PLAYER_FILTERS);
  const [page, setPage] = useState(1);
  const [view, setView] = useState<ViewMode>(getInitialView);
  const [activeViewId, setActiveViewId] = useState<string | null>(null);
  const [sortChip, setSortChip] = useState<SortChip | null>(null);
  const defaultApplied = useRef(false);

  // ── Search views ─────────────────────────────────────────────────────────

  const { data: views = [] } = useQuery<PlayerSearchView[]>({
    queryKey: ["search-views"],
    queryFn: () => api.get<PlayerSearchView[]>("/clubs/me/search-views").then((r) => r.data),
    enabled: isAuthenticated,
    staleTime: 60_000,
  });

  useEffect(() => {
    if (defaultApplied.current || views.length === 0) return;
    defaultApplied.current = true;
    const def = views.find((v) => v.is_default);
    if (def) {
      setFilters((f) => applySavedFilters(def.filters, f));
      setActiveViewId(def.id);
    }
  }, [views]);

  const createViewMutation = useMutation({
    mutationFn: (body: { name: string; filters: SavedFilters; is_default?: boolean }) =>
      api.post<PlayerSearchView>("/clubs/me/search-views", body).then((r) => r.data),
    onSuccess: (created) => {
      queryClient.invalidateQueries({ queryKey: ["search-views"] });
      setActiveViewId(created.id);
    },
  });

  const updateViewMutation = useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: object }) =>
      api.patch<PlayerSearchView>(`/clubs/me/search-views/${id}`, patch).then((r) => r.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["search-views"] }),
  });

  const deleteViewMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/clubs/me/search-views/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["search-views"] }),
  });

  function handleSelectView(id: string | null) {
    setActiveViewId(id);
    if (id === null) {
      setFilters(DEFAULT_PLAYER_FILTERS);
    } else {
      const v = views.find((v) => v.id === id);
      if (v) setFilters((f) => applySavedFilters(v.filters, f));
    }
    setPage(1);
  }

  const activeView = views.find((v) => v.id === activeViewId) ?? null;
  const isModified = !!(activeView && !filtersMatchSaved(filters, activeView.filters));

  function handleFiltersChange(next: PlayerFilterState) {
    setFilters(next);
    setPage(1);
  }

  function handleViewChange(v: ViewMode) {
    setView(v);
    try { localStorage.setItem("playerMarketView", v); } catch {}
  }

  async function handleCreate(name: string) {
    await createViewMutation.mutateAsync({ name, filters: toSavedFilters(filters) });
  }
  async function handleUpdate(id: string, patch: { name?: string; filters?: Record<string, unknown>; is_default?: boolean }) {
    await updateViewMutation.mutateAsync({ id, patch });
  }
  async function handleDelete(id: string) {
    await deleteViewMutation.mutateAsync(id);
  }
  async function handleSaveCurrentToView(id: string) {
    await updateViewMutation.mutateAsync({ id, patch: { filters: toSavedFilters(filters) } });
  }
  async function handleSaveCurrentAsNew(name: string) {
    await createViewMutation.mutateAsync({ name, filters: toSavedFilters(filters) });
  }

  // ── Sort chip handling ───────────────────────────────────────────────────

  function handleSortChip(chip: SortChip) {
    setSortChip(chip);
    if (chip === "form") { setFilters((f) => ({ ...f, sort_by: "form_score", sort_dir: "desc" })); setPage(1); }
    if (chip === "youngest") { setFilters((f) => ({ ...f, sort_by: "age", sort_dir: "asc" })); setPage(1); }
    // "value" and "cheapest" are applied client-side below — no re-fetch.
  }

  // ── Player query ──────────────────────────────────────────────────────────

  const pageSize = view === "list" ? 40 : 24;

  const { data, isLoading, isError } = useQuery<Paginated<Player>>({
    queryKey: ["players", "market", { ...filters, page, pageSize }],
    queryFn: () =>
      api
        .get<Paginated<Player>>("/players/market", {
          params: {
            page,
            page_size: pageSize,
            sort_by: filters.sort_by,
            sort_dir: filters.sort_dir,
            ...(filters.search         && { search: filters.search }),
            ...(filters.position       && { position: filters.position }),
            ...(filters.status         && { status: filters.status }),
            ...(filters.open_to_offers && { open_to_offers: true }),
            ...(filters.min_age        && { min_age: Number(filters.min_age) }),
            ...(filters.max_age        && { max_age: Number(filters.max_age) }),
            ...(filters.nationality    && { nationality: filters.nationality }),
            ...(filters.club_search    && { club_search: filters.club_search }),
            ...(filters.min_goals        && { min_goals: Number(filters.min_goals) }),
            ...(filters.min_assists      && { min_assists: Number(filters.min_assists) }),
            ...(filters.min_appearances  && { min_appearances: Number(filters.min_appearances) }),
            ...(filters.min_avg_rating   && { min_avg_rating: Number(filters.min_avg_rating) }),
            ...(filters.min_value        && { min_market_value: Number(filters.min_value) * 1_000_000 }),
            ...(filters.max_value        && { max_market_value: Number(filters.max_value) * 1_000_000 }),
            ...(filters.contract_expiry_months && { contract_expiry_within_months: Number(filters.contract_expiry_months) }),
            ...(filters.min_form_score   && { min_form_score: Number(filters.min_form_score) }),
          },
        })
        .then((r) => r.data),
  });

  const fetchedPlayers = data?.items ?? [];
  const playerIds = fetchedPlayers.map((p) => p.id).join(",");

  const { data: formScores = {} } = useQuery<Record<string, { score: number; trend: number | null }>>({
    queryKey: ["players", "form-batch", playerIds],
    enabled: fetchedPlayers.length > 0,
    staleTime: 60_000,
    queryFn: async () => {
      const resp = await api
        .get<Record<string, PlayerForm>>("/players/form/batch", { params: { player_ids: playerIds } })
        .catch(() => ({ data: {} as Record<string, PlayerForm> }));
      const map: Record<string, { score: number; trend: number | null }> = {};
      for (const [pid, form] of Object.entries(resp.data)) {
        map[pid] = { score: Number(form.form_score), trend: form.trend != null ? Number(form.trend) : null };
      }
      return map;
    },
  });

  // TRA-92: one batch valuation call per page of cards, never per card.
  // D6: a player-account identity must not fire the call at all.
  const { data: fairValues = {} } = useQuery<Record<string, FairValueSignal>>({
    queryKey: ["valuation", "batch", playerIds],
    enabled: isAuthenticated && !isPlayerAccount && fetchedPlayers.length > 0,
    staleTime: 300_000,
    queryFn: async () => {
      const resp = await api
        .get<{ valuations: Record<string, FairValueSignal> }>("/valuation/players", { params: { ids: playerIds } })
        .catch(() => ({ data: { valuations: {} as Record<string, FairValueSignal> } }));
      return resp.data.valuations;
    },
  });

  const { data: statsMap = {} } = useQuery<Record<string, PlayerStats | null>>({
    queryKey: ["players", "stats-batch", playerIds],
    enabled: view === "list" && fetchedPlayers.length > 0,
    staleTime: 120_000,
    queryFn: async () => {
      const resp = await api.get<Record<string, PlayerStats[]>>("/players/stats/batch", { params: { player_ids: playerIds } });
      const map: Record<string, PlayerStats | null> = {};
      for (const [id, statsList] of Object.entries(resp.data)) {
        map[id] = statsList.sort((a, b) => b.appearances - a.appearances)[0] ?? null;
      }
      return map;
    },
  });

  // Club-only budget context for the tier-2 figures.
  const { data: myClub } = useQuery<Club>({
    queryKey: ["clubs", "me"],
    queryFn: () => api.get<Club>("/clubs/me").then((r) => r.data),
    enabled: isClub,
    staleTime: 60_000,
  });

  // Client-side sort for the two chips with no server equivalent — page-local only.
  const players = useMemo(() => {
    if (sortChip === "cheapest") {
      return [...fetchedPlayers].sort((a, b) => (a.market_value ?? Infinity) - (b.market_value ?? Infinity));
    }
    if (sortChip === "value") {
      return [...fetchedPlayers].sort((a, b) => {
        const da = fairValues[a.id]?.divergence?.pct ?? Infinity;
        const db = fairValues[b.id]?.divergence?.pct ?? Infinity;
        return da - db;
      });
    }
    return fetchedPlayers;
  }, [fetchedPlayers, sortChip, fairValues]);

  const underFairValueCount = fetchedPlayers.filter(
    (p) => fairValues[p.id]?.divergence?.band === "BELOW" || fairValues[p.id]?.divergence?.band === "WELL_BELOW"
  ).length;

  return (
    <div>
      <div className="mb-5">
        <h1 className="text-2xl font-bold tracking-[-0.01em] text-text">Player Market</h1>
        <p className="mt-[3px] text-sm text-text-muted">
          {activeView
            ? `Search view: ${activeView.name} · ${data?.total ?? 0} matches`
            : "Browse available players"}
        </p>
      </div>

      {isClub && myClub?.finance && (
        <div className="mb-5 grid gap-3.5" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(230px, 1fr))" }}>
          <Card tier={2}>
            <p className="text-xs font-semibold text-text-secondary">Budget free</p>
            <p className="mt-1.5 text-[28px] font-bold text-text">{formatCurrency(Number(myClub.finance.transfer_remaining))}</p>
          </Card>
          <Card tier={2}>
            <p className="text-xs font-semibold text-text-secondary">Wage room</p>
            <p className="mt-1.5 text-[28px] font-bold text-text">{formatCurrency(Number(myClub.finance.wage_remaining_weekly))}</p>
            <p className="mt-[3px] text-xs text-text-muted">per week</p>
          </Card>
          <Card tier={2}>
            <p className="text-xs font-semibold text-text-secondary">Under fair value</p>
            <p className="mt-1.5 text-[28px] font-bold text-text">{underFairValueCount}</p>
            <p className="mt-[3px] text-xs text-text-muted">on this page</p>
          </Card>
        </div>
      )}

      {isAuthenticated && <NLPlayerSearch />}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[250px_1fr]">
        {/* Filter rail */}
        <div className="lg:sticky lg:top-6 h-fit space-y-5">
          <Card>
            <PlayerFilters filters={filters} onChange={handleFiltersChange} view={view} onViewChange={handleViewChange} />
          </Card>
          {isAuthenticated && (
            <Card>
              <ViewSwitcher
                views={views}
                activeViewId={activeViewId}
                isModified={isModified}
                onCreate={handleCreate}
                onUpdate={handleUpdate}
                onDelete={handleDelete}
                onSelect={handleSelectView}
                onSaveCurrentToView={handleSaveCurrentToView}
                onSaveCurrentAsNew={handleSaveCurrentAsNew}
              />
            </Card>
          )}
        </div>

        {/* Results */}
        <div className="min-w-0">
          {isAuthenticated && (
            <div className="mb-4">
              <MarketRecommendationsPanel positionFilter={filters.position || undefined} maxBudget={undefined} />
            </div>
          )}

          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap gap-2">
              {SORT_CHIPS.map((c) => (
                <button
                  key={c.key}
                  onClick={() => handleSortChip(c.key)}
                  className={`rounded-lg px-3.5 py-1.5 text-[13px] font-semibold transition-colors ${
                    sortChip === c.key ? "bg-ink text-white" : "bg-surface text-text-secondary ring-1 ring-input-border hover:ring-accent"
                  }`}
                >
                  {c.label}
                </button>
              ))}
            </div>
            {data && (
              <span className="text-[13px] text-text-muted">
                {data.total} player{data.total !== 1 ? "s" : ""}
                {compareIds.length > 0 && ` · ${compareIds.length} selected to compare`}
              </span>
            )}
          </div>

          {isLoading && (
            <div className="flex justify-center py-16"><Spinner size="lg" /></div>
          )}

          {isError && (
            <div className="rounded-xl bg-danger-bg px-5 py-4 text-sm text-danger-text ring-1 ring-danger-border">
              Failed to load players. Please try again.
            </div>
          )}

          {data && data.items.length === 0 && (
            <EmptyState title="No players found" body="Try adjusting your filters." />
          )}

          {data && data.items.length > 0 && (
            <>
              {view === "grid" && (
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-3 xl:grid-cols-4">
                  {players.map((player) => (
                    <PlayerCard
                      key={player.id}
                      player={player}
                      formScore={formScores[player.id]?.score}
                      formTrend={formScores[player.id]?.trend}
                      fairValueSignal={fairValues[player.id]}
                    />
                  ))}
                </div>
              )}

              {view === "list" && (
                <div className="space-y-2.5">
                  {players.map((player) => (
                    <PlayerListRow
                      key={player.id}
                      player={player}
                      formScore={formScores[player.id]?.score}
                      formTrend={formScores[player.id]?.trend}
                      fairValueSignal={fairValues[player.id]}
                      canAct={isClub}
                    />
                  ))}
                </div>
              )}

              <div className="mt-6">
                <Pagination page={data.page} total={data.total} pageSize={data.page_size} onChange={setPage} />
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
