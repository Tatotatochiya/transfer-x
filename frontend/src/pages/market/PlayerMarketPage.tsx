import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import { useAuthStore } from "../../store/auth";
import { usePreferencesStore } from "../../store/preferences";
import type { Paginated, Player, PlayerForm, PlayerSearchView, PlayerStats } from "../../types/api";
import PlayerCard from "../../components/players/PlayerCard";
import PlayerListRow from "../../components/players/PlayerListRow";
import PlayerFilters, {
  DEFAULT_PLAYER_FILTERS,
  type PlayerFilterState,
  type ViewMode,
} from "../../components/players/PlayerFilters";
import ViewSwitcher from "../../components/players/ViewSwitcher";
import PageHeader from "../../components/ui/PageHeader";
import Pagination from "../../components/ui/Pagination";
import EmptyState from "../../components/ui/EmptyState";
import Spinner from "../../components/ui/Spinner";
import { MarketRecommendationsPanel } from "../../components/ai/MarketRecommendationsPanel";
import { NLPlayerSearch } from "../../components/ai/NLPlayerSearch";

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
    // Preserve ephemeral fields from current state
    search: current.search,
    club_search: current.club_search,
    // Apply saved fields
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

// ── Page ──────────────────────────────────────────────────────────────────────

export default function PlayerMarketPage() {
  const { accessToken } = useAuthStore();
  const isAuthenticated = !!accessToken;
  const queryClient = useQueryClient();

  const [filters, setFilters] = useState<PlayerFilterState>(DEFAULT_PLAYER_FILTERS);
  const [page, setPage] = useState(1);
  const [view, setView] = useState<ViewMode>(getInitialView);
  const [activeViewId, setActiveViewId] = useState<string | null>(null);
  const defaultApplied = useRef(false);

  // ── Search views ─────────────────────────────────────────────────────────

  const { data: views = [] } = useQuery<PlayerSearchView[]>({
    queryKey: ["search-views"],
    queryFn: () => api.get<PlayerSearchView[]>("/clubs/me/search-views").then((r) => r.data),
    enabled: isAuthenticated,
    staleTime: 60_000,
  });

  // Apply default view on first load (once views arrive)
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

  // ── View selection ────────────────────────────────────────────────────────

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

  // Re-apply view filters when "Discard" is clicked (onSelect called with same id)
  function handleSelectViewOrDiscard(id: string | null) {
    handleSelectView(id);
  }

  const activeView = views.find((v) => v.id === activeViewId) ?? null;
  const isModified = !!(
    activeView && !filtersMatchSaved(filters, activeView.filters)
  );

  // ── Filters ───────────────────────────────────────────────────────────────

  function handleFiltersChange(next: PlayerFilterState) {
    setFilters(next);
    setPage(1);
  }

  function handleViewChange(v: ViewMode) {
    setView(v);
    try { localStorage.setItem("playerMarketView", v); } catch {}
  }

  // ── ViewSwitcher callbacks ────────────────────────────────────────────────

  async function handleCreate(name: string) {
    await createViewMutation.mutateAsync({
      name,
      filters: toSavedFilters(filters),
    });
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
            ...(filters.min_form_score   && { min_form_score: Number(filters.min_form_score) }),
          },
        })
        .then((r) => r.data),
  });

  const players = data?.items ?? [];
  const playerIds = players.map((p) => p.id).join(",");

  const { data: formScores = {} } = useQuery<Record<string, { score: number; trend: number | null }>>({
    queryKey: ["players", "form-batch", playerIds],
    enabled: players.length > 0,
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

  const { data: statsMap = {} } = useQuery<Record<string, PlayerStats | null>>({
    queryKey: ["players", "stats-batch", playerIds],
    enabled: view === "list" && players.length > 0,
    staleTime: 120_000,
    queryFn: async () => {
      const resp = await api.get<Record<string, PlayerStats[]>>("/players/stats/batch", {
        params: { player_ids: playerIds },
      });
      const map: Record<string, PlayerStats | null> = {};
      for (const [id, statsList] of Object.entries(resp.data)) {
        map[id] = statsList.sort((a, b) => b.appearances - a.appearances)[0] ?? null;
      }
      return map;
    },
  });

  return (
    <div>
      <PageHeader title="Player Market" subtitle="Browse available players" />

      {/* View switcher — only for authenticated club users */}
      {isAuthenticated && (
        <ViewSwitcher
          views={views}
          activeViewId={activeViewId}
          isModified={isModified}
          onCreate={handleCreate}
          onUpdate={handleUpdate}
          onDelete={handleDelete}
          onSelect={handleSelectViewOrDiscard}
          onSaveCurrentToView={handleSaveCurrentToView}
          onSaveCurrentAsNew={handleSaveCurrentAsNew}
        />
      )}

      {isAuthenticated && <NLPlayerSearch />}

      <PlayerFilters
        filters={filters}
        onChange={handleFiltersChange}
        view={view}
        onViewChange={handleViewChange}
      />

      {isAuthenticated && (
        <MarketRecommendationsPanel
          positionFilter={filters.position || undefined}
          maxBudget={undefined}
        />
      )}

      {isLoading && (
        <div className="flex justify-center py-16">
          <Spinner size="lg" />
        </div>
      )}

      {isError && (
        <div className="rounded-xl bg-red-500/10 px-5 py-4 text-sm text-red-400 ring-1 ring-red-500/30">
          Failed to load players. Please try again.
        </div>
      )}

      {data && data.items.length === 0 && (
        <EmptyState title="No players found" body="Try adjusting your filters." />
      )}

      {data && data.items.length > 0 && (
        <>
          <p className="mb-3 text-xs text-slate-600">
            {data.total} player{data.total !== 1 ? "s" : ""} found
          </p>

          {view === "grid" && (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6">
              {players.map((player) => (
                <PlayerCard
                  key={player.id}
                  player={player}
                  formScore={formScores[player.id]?.score}
                  formTrend={formScores[player.id]?.trend}
                />
              ))}
            </div>
          )}

          {view === "list" && (
            <div className="rounded-xl ring-1 ring-white/[0.07] overflow-hidden">
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b border-white/[0.06] bg-slate-900/60">
                    <th className="px-3 py-2.5 text-xs font-semibold uppercase tracking-wider text-slate-500">Player</th>
                    <th className="px-3 py-2.5 text-xs font-semibold uppercase tracking-wider text-slate-500 hidden sm:table-cell">Pos</th>
                    <th className="px-3 py-2.5 text-xs font-semibold uppercase tracking-wider text-slate-500 hidden md:table-cell">Club</th>
                    <th className="px-3 py-2.5 text-xs font-semibold uppercase tracking-wider text-slate-500 hidden sm:table-cell">Status</th>
                    <th className="px-3 py-2.5 text-xs font-semibold uppercase tracking-wider text-slate-500">Form</th>
                    <th className="px-3 py-2.5 text-xs font-semibold uppercase tracking-wider text-slate-500 hidden lg:table-cell">G</th>
                    <th className="px-3 py-2.5 text-xs font-semibold uppercase tracking-wider text-slate-500 hidden lg:table-cell">A</th>
                    <th className="px-3 py-2.5 text-xs font-semibold uppercase tracking-wider text-slate-500 hidden xl:table-cell">Apps</th>
                    <th className="px-3 py-2.5 text-xs font-semibold uppercase tracking-wider text-slate-500 hidden xl:table-cell">Rtg</th>
                    <th className="px-2 py-2.5" />
                  </tr>
                </thead>
                <tbody className="bg-slate-900/40">
                  {players.map((player) => (
                    <PlayerListRow
                      key={player.id}
                      player={player}
                      formScore={formScores[player.id]?.score}
                      formTrend={formScores[player.id]?.trend}
                      stats={statsMap[player.id]}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <Pagination
            page={data.page}
            total={data.total}
            pageSize={data.page_size}
            onChange={setPage}
          />
        </>
      )}
    </div>
  );
}
