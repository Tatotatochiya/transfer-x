import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { useInfiniteQuery, useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import { useAuth } from "../../hooks/useAuth";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import { useNLPlayerSearch } from "../../hooks/useAI";
import { usePreferencesStore } from "../../store/preferences";
import type { Club, FairValueSignal, Paginated, Player, PlayerForm, PlayerSearchView } from "../../types/api";
import PlayerCard from "../../components/players/PlayerCard";
import PlayerListRow from "../../components/players/PlayerListRow";
import PlayerRow, { rowFromPlayer, rowFromSearchResult } from "../../components/players/PlayerRow";
import PlayerFilters, {
  ClubSearchField,
  DEFAULT_PLAYER_FILTERS,
  ViewToggle,
  type PlayerFilterState,
  type ViewMode,
} from "../../components/players/PlayerFilters";
import ViewSwitcher from "../../components/players/ViewSwitcher";
import Card from "../../components/ui/Card";
import Pagination from "../../components/ui/Pagination";
import EmptyState from "../../components/ui/EmptyState";
import Sheet from "../../components/ui/Sheet";
import Spinner from "../../components/ui/Spinner";
import { MarketRecommendationsPanel } from "../../components/ai/MarketRecommendationsPanel";
import { FilterChips } from "../../components/ai/NLPlayerSearch";
import MarketHeader, { BudgetLine } from "../../components/market/MarketHeader";
import MarketSearch from "../../components/market/MarketSearch";
import MarketToolbar, { SortMenu } from "../../components/market/MarketToolbar";
import ActiveFilterChips, { activeFilterCount } from "../../components/market/ActiveFilterChips";
import FiltersSheet from "../../components/market/FiltersSheet";
import RecommendationsRow from "../../components/market/RecommendationsRow";
import { useCompare } from "../../context/CompareContext";
import { fetchMarket } from "../../lib/marketQuery";

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
    buyable: (saved.buyable as boolean) ?? DEFAULT_PLAYER_FILTERS.buyable,
    min_age: (saved.min_age as string) ?? "",
    max_age: (saved.max_age as string) ?? "",
    nationality: (saved.nationality as string) ?? "",
    min_goals: (saved.min_goals as string) ?? "",
    min_assists: (saved.min_assists as string) ?? "",
    min_appearances: (saved.min_appearances as string) ?? "",
    min_avg_rating: (saved.min_avg_rating as string) ?? "",
    min_form_score: (saved.min_form_score as string) ?? "",
    min_price: (saved.min_price as string) ?? "",
    max_price: (saved.max_price as string) ?? "",
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

// Below 640px the page opens in list view unless the person picked grid here,
// on this device (D5). From 640px the account preference applies as before.
const PHONE_VIEW_KEY = "playerMarketView.phone";

function getPhoneView(): ViewMode {
  try {
    return localStorage.getItem(PHONE_VIEW_KEY) === "grid" ? "grid" : "list";
  } catch {
    return "list";
  }
}

/** How many columns an auto-fill grid is showing, so a full-width row can follow the first row. */
function useGridColumns(el: HTMLElement | null): number {
  const [cols, setCols] = useState(1);
  useEffect(() => {
    if (!el || typeof ResizeObserver === "undefined") return;
    const measure = () => setCols(Math.max(1, getComputedStyle(el).gridTemplateColumns.split(" ").filter(Boolean).length));
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    measure();
    return () => ro.disconnect();
  }, [el]);
  return cols;
}

type FormMap = Record<string, { score: number; trend: number | null }>;

// ── Page ──────────────────────────────────────────────────────────────────────

/**
 * Browse Players, players first (browse-players-focus): four short rows above
 * the results (title and count, one search box, Filters · Sort · view, the
 * active filters as chips). Below 1024px the filters are a sheet and the list
 * grows with "Show n more"; from 1024px a sticky rail and pagination.
 */
export default function PlayerMarketPage() {
  const { accessToken, user, isClub } = useAuth();
  const isAuthenticated = !!accessToken;
  const isPlayerAccount = user?.user_type === "PLAYER";
  const queryClient = useQueryClient();
  const { compareIds } = useCompare();
  const isDesktop = useMediaQuery("(min-width: 1024px)");
  const isWide = useMediaQuery("(min-width: 640px)");

  const [filters, setFilters] = useState<PlayerFilterState>(DEFAULT_PLAYER_FILTERS);
  const [page, setPage] = useState(1);
  const [wideView, setWideView] = useState<ViewMode>(getInitialView);
  const [phoneView, setPhoneView] = useState<ViewMode>(getPhoneView);
  const view = isWide ? wideView : phoneView;
  const [activeViewId, setActiveViewId] = useState<string | null>(null);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [recsOpen, setRecsOpen] = useState(false);
  const [describe, setDescribe] = useState(false);
  const nl = useNLPlayerSearch();
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

  /** Applies a saved view (or "All players") and returns the filters it set. */
  function handleSelectView(id: string | null): PlayerFilterState {
    setActiveViewId(id);
    const v = id === null ? null : views.find((x) => x.id === id);
    const next = id === null ? DEFAULT_PLAYER_FILTERS : v ? applySavedFilters(v.filters, filters) : filters;
    setFilters(next);
    setPage(1);
    return next;
  }

  const activeView = views.find((v) => v.id === activeViewId) ?? null;
  const isModifiedFor = (f: PlayerFilterState) => !!(activeView && !filtersMatchSaved(f, activeView.filters));

  function handleFiltersChange(next: PlayerFilterState) {
    setFilters(next);
    setPage(1);
  }

  const handleSearch = useCallback((search: string) => {
    setFilters((f) => ({ ...f, search }));
    setPage(1);
  }, []);

  function handleSort(sort_by: PlayerFilterState["sort_by"], sort_dir: PlayerFilterState["sort_dir"]) {
    handleFiltersChange({ ...filters, sort_by, sort_dir });
  }

  function handleViewChange(v: ViewMode) {
    if (isWide) {
      setWideView(v);
      try { localStorage.setItem("playerMarketView", v); } catch { /* storage unavailable */ }
    } else {
      setPhoneView(v);
      try { localStorage.setItem(PHONE_VIEW_KEY, v); } catch { /* storage unavailable */ }
    }
  }

  async function handleCreate(name: string, f: PlayerFilterState = filters) {
    await createViewMutation.mutateAsync({ name, filters: toSavedFilters(f) });
  }
  async function handleUpdate(id: string, patch: { name?: string; filters?: Record<string, unknown>; is_default?: boolean }) {
    await updateViewMutation.mutateAsync({ id, patch });
  }
  async function handleDelete(id: string) {
    await deleteViewMutation.mutateAsync(id);
  }
  async function handleSaveToView(id: string, f: PlayerFilterState = filters) {
    await updateViewMutation.mutateAsync({ id, patch: { filters: toSavedFilters(f) } });
  }

  // ── Player queries ────────────────────────────────────────────────────────
  // From 1024px one page at a time with pagination; below, pages append.

  const pageSize = view === "list" ? 40 : 24;

  const paged = useQuery<Paginated<Player>>({
    queryKey: ["players", "market", { ...filters, page, pageSize }],
    queryFn: () => fetchMarket(filters, page, pageSize),
    enabled: isDesktop,
  });

  const infinite = useInfiniteQuery({
    queryKey: ["players", "market", "infinite", { ...filters, pageSize }],
    queryFn: ({ pageParam }) => fetchMarket(filters, pageParam, pageSize),
    initialPageParam: 1,
    getNextPageParam: (last: Paginated<Player>) => (last.page * last.page_size < last.total ? last.page + 1 : undefined),
    enabled: !isDesktop,
  });

  const pages: Paginated<Player>[] = isDesktop ? (paged.data ? [paged.data] : []) : (infinite.data?.pages ?? []);
  const players = pages.flatMap((p) => p.items);
  const total = pages[0]?.total;
  const isLoading = isDesktop ? paged.isLoading : infinite.isLoading;
  const isError = isDesktop ? paged.isError : infinite.isError;

  // Form and valuation: one batch call per loaded page, keyed by that page's
  // ids, never per card (TRA-92). A player account never fires the valuation
  // call (D6).
  const pageIds = pages.map((p) => p.items.map((x) => x.id).join(",")).filter(Boolean);

  const formQueries = useQueries({
    queries: pageIds.map((ids) => ({
      queryKey: ["players", "form-batch", ids],
      staleTime: 60_000,
      queryFn: async (): Promise<FormMap> => {
        const resp = await api
          .get<Record<string, PlayerForm>>("/players/form/batch", { params: { player_ids: ids } })
          .catch(() => ({ data: {} as Record<string, PlayerForm> }));
        const map: FormMap = {};
        for (const [pid, form] of Object.entries(resp.data)) {
          map[pid] = { score: Number(form.form_score), trend: form.trend != null ? Number(form.trend) : null };
        }
        return map;
      },
    })),
  });
  const formScores: FormMap = Object.assign({}, ...formQueries.map((q) => q.data ?? {}));

  const valuationQueries = useQueries({
    queries: pageIds.map((ids) => ({
      queryKey: ["valuation", "batch", ids],
      enabled: isAuthenticated && !isPlayerAccount,
      staleTime: 300_000,
      queryFn: async (): Promise<Record<string, FairValueSignal>> => {
        const resp = await api
          .get<{ valuations: Record<string, FairValueSignal> }>("/valuation/players", { params: { ids } })
          .catch(() => ({ data: { valuations: {} as Record<string, FairValueSignal> } }));
        return resp.data.valuations;
      },
    })),
  });
  const fairValues: Record<string, FairValueSignal> = Object.assign({}, ...valuationQueries.map((q) => q.data ?? {}));

  // Club-only budget line.
  const { data: myClub } = useQuery<Club>({
    queryKey: ["clubs", "me"],
    queryFn: () => api.get<Club>("/clubs/me").then((r) => r.data),
    enabled: isClub,
    staleTime: 60_000,
  });

  // ── "Show n more": focus the first new row once it lands ─────────────────

  const rowRefs = useRef<(HTMLElement | null)[]>([]);
  const focusFrom = useRef<number | null>(null);
  function loadMore() {
    focusFrom.current = players.length;
    infinite.fetchNextPage();
  }
  useLayoutEffect(() => {
    const i = focusFrom.current;
    if (i != null && players.length > i) {
      focusFrom.current = null;
      rowRefs.current[i]?.focus();
    }
  }, [players.length]);

  const [gridEl, setGridEl] = useState<HTMLElement | null>(null);
  const gridCols = useGridColumns(gridEl);

  // ── Layout ────────────────────────────────────────────────────────────────

  const describing = describe && (nl.data || nl.isPending || nl.error);
  const showRecs = isClub;
  const filterCount = activeFilterCount(filters);

  function leaveDescribe() {
    setDescribe(false);
    nl.reset();
  }

  const search = (
    <MarketSearch
      search={filters.search}
      onSearch={handleSearch}
      describe={describe}
      onDescribeChange={(on) => (on ? setDescribe(true) : leaveDescribe())}
      onDescribeSubmit={(query) => nl.mutate({ query, buyable: filters.buyable })}
      describePending={nl.isPending}
      canDescribe={isAuthenticated}
    />
  );

  const recsRow = showRecs && (
    <RecommendationsRow clubName={myClub?.name} onOpen={() => setRecsOpen(true)} />
  );

  const results = describing ? (
    <DescribeResults nl={nl} onBack={leaveDescribe} />
  ) : (
    <>
      {isLoading && <div className="flex justify-center py-16"><Spinner size="lg" /></div>}

      {isError && (
        <div className="rounded-xl bg-danger-bg px-5 py-4 text-sm text-danger-text ring-1 ring-danger-border">
          Failed to load players. Please try again.
        </div>
      )}

      {!isLoading && !isError && total === 0 && (
        <EmptyState title="No players found" body="Try adjusting your filters." />
      )}

      {players.length > 0 && (
        <>
          {view === "grid" && (
            <ul ref={setGridEl} className="grid grid-cols-[repeat(auto-fill,minmax(220px,1fr))] gap-3">
              {players.map((player, i) => (
                <GridItem key={player.id} index={i} rowRefs={rowRefs} after={!isDesktop && i === gridCols - 1 ? recsRow : null}>
                  <PlayerCard
                    player={player}
                    formScore={formScores[player.id]?.score}
                    formTrend={formScores[player.id]?.trend}
                    fairValueSignal={fairValues[player.id]}
                  />
                </GridItem>
              ))}
            </ul>
          )}

          {view === "list" && !isWide && (
            <ul className="overflow-hidden rounded-xl bg-surface ring-1 ring-border">
              {players.map((player, i) => (
                <ListItem key={player.id} after={i === 4 ? recsRow : null}>
                  <PlayerRow
                    ref={(el) => { rowRefs.current[i] = el; }}
                    row={rowFromPlayer(player, fairValues[player.id], formScores[player.id]?.score)}
                  />
                </ListItem>
              ))}
            </ul>
          )}

          {view === "list" && isWide && (
            <ul className="space-y-2.5">
              {players.map((player, i) => (
                <li key={player.id} ref={(el) => { rowRefs.current[i] = el; }} tabIndex={-1} className="focus:outline-none">
                  <PlayerListRow
                    player={player}
                    formScore={formScores[player.id]?.score}
                    formTrend={formScores[player.id]?.trend}
                    fairValueSignal={fairValues[player.id]}
                    canAct={isClub}
                  />
                </li>
              ))}
            </ul>
          )}

          {isDesktop && paged.data && (
            <div className="mt-6">
              <Pagination page={paged.data.page} total={paged.data.total} pageSize={paged.data.page_size} onChange={setPage} />
            </div>
          )}

          {!isDesktop && total != null && (
            <div className="mt-4 flex flex-col items-center gap-2">
              {infinite.hasNextPage && (
                <button
                  type="button"
                  onClick={loadMore}
                  disabled={infinite.isFetchingNextPage}
                  className="min-h-12 w-full rounded-xl bg-surface text-base font-semibold text-text ring-1 ring-inset ring-input-border hover:ring-accent disabled:opacity-60"
                >
                  {infinite.isFetchingNextPage ? "Loading…" : `Show ${Math.min(pageSize, total - players.length)} more`}
                </button>
              )}
              <p className="text-sm text-text-muted">Showing {players.length.toLocaleString("en-GB")} of {total.toLocaleString("en-GB")}</p>
            </div>
          )}
        </>
      )}
    </>
  );

  return (
    // On phones the compare bar is fixed at the bottom: leave room for it so
    // it never covers "Show n more".
    <div className={compareIds.length > 0 ? "pb-24 lg:pb-0" : ""}>
      <MarketHeader total={describing ? undefined : total} club={isClub && isWide ? myClub : null} />

      {!isDesktop && (
        <>
          <div className="mt-3 sm:hidden">{search}</div>
          <MarketToolbar
            filters={filters}
            onSort={handleSort}
            activeCount={filterCount}
            view={view}
            onViewChange={handleViewChange}
            onOpenFilters={() => setFiltersOpen(true)}
            search={isWide ? search : undefined}
          />
          <div className="mt-1 space-y-2">
            <ActiveFilterChips filters={filters} onChange={handleFiltersChange} />
            {isClub && !isWide && <BudgetLine club={myClub} />}
          </div>
          <div className="mt-3">{results}</div>

          <FiltersSheet
            open={filtersOpen}
            onClose={() => setFiltersOpen(false)}
            filters={filters}
            onApply={handleFiltersChange}
            saved={isAuthenticated ? {
              views,
              activeViewId,
              isModified: isModifiedFor,
              onSelect: handleSelectView,
              onCreate: handleCreate,
              onUpdate: handleUpdate,
              onDelete: handleDelete,
              onSaveToView: handleSaveToView,
            } : undefined}
          />
          {showRecs && (
            <Sheet
              open={recsOpen}
              onClose={() => setRecsOpen(false)}
              title="Picks for your squad gaps"
              subtitle={myClub ? `Recommended for ${myClub.name}` : undefined}
              closeLabel="Close"
              footer={
                <button type="button" onClick={() => setRecsOpen(false)} className="min-h-12 w-full rounded-xl bg-surface text-base font-semibold text-text ring-1 ring-inset ring-input-border">
                  Back to players
                </button>
              }
            >
              <MarketRecommendationsPanel positionFilter={filters.position || undefined} maxBudget={undefined} />
            </Sheet>
          )}
        </>
      )}

      {isDesktop && (
        <div className="mt-4 grid grid-cols-[250px_1fr] gap-6">
          <aside aria-label="Filters" className="sticky top-20 h-fit max-h-[calc(100vh-6rem)] space-y-5 overflow-y-auto pb-2 [scrollbar-width:thin]">
            {isAuthenticated && (
              <Card>
                <ViewSwitcher
                  views={views}
                  activeViewId={activeViewId}
                  isModified={isModifiedFor(filters)}
                  onCreate={(name) => handleCreate(name)}
                  onUpdate={handleUpdate}
                  onDelete={handleDelete}
                  onSelect={handleSelectView}
                  onSaveCurrentToView={(id) => handleSaveToView(id)}
                  onSaveCurrentAsNew={(name) => handleCreate(name)}
                />
              </Card>
            )}
            <Card>
              <div className="space-y-3">
                <PlayerFilters filters={filters} onChange={handleFiltersChange} />
                <ClubSearchField filters={filters} onChange={handleFiltersChange} />
                <ViewToggle view={view} onViewChange={handleViewChange} />
              </div>
            </Card>
          </aside>

          <div className="min-w-0 space-y-3">
            <div className="flex items-center gap-2">
              {search}
              <SortMenu filters={filters} onSort={handleSort} className="shrink-0" />
            </div>
            <ActiveFilterChips
              filters={filters}
              onChange={handleFiltersChange}
              trailing={showRecs ? <RecommendationsRow variant="link" expanded={recsOpen} onOpen={() => setRecsOpen((o) => !o)} /> : undefined}
            />
            {showRecs && recsOpen && (
              <MarketRecommendationsPanel positionFilter={filters.position || undefined} maxBudget={undefined} />
            )}
            {results}
          </div>
        </div>
      )}
    </div>
  );
}

function ListItem({ children, after }: { children: React.ReactNode; after: React.ReactNode }) {
  return (
    <>
      {children}
      {after && <li className="border-t border-rule">{after}</li>}
    </>
  );
}

function GridItem({ children, after, index, rowRefs }: {
  children: React.ReactNode;
  after: React.ReactNode;
  index: number;
  rowRefs: React.MutableRefObject<(HTMLElement | null)[]>;
}) {
  return (
    <>
      <li ref={(el) => { rowRefs.current[index] = el; }} tabIndex={-1} className="min-w-0 focus:outline-none">{children}</li>
      {after && <li className="col-span-full overflow-hidden rounded-xl">{after}</li>}
    </>
  );
}

/** The AI search's results in place of the list (browse-players-focus §5.7). */
function DescribeResults({ nl, onBack }: { nl: ReturnType<typeof useNLPlayerSearch>; onBack: () => void }) {
  const back = (
    <button type="button" onClick={onBack} className="min-h-11 text-[15px] font-semibold text-accent hover:text-accent-hover">
      ← Back to all players
    </button>
  );
  if (nl.isPending) {
    return (
      <div className="flex items-center gap-2 py-8 text-sm text-text-muted">
        <Spinner size="sm" /> Reading your description and searching…
      </div>
    );
  }
  if (nl.error) {
    return (
      <div className="space-y-2">
        <p className="rounded-xl bg-danger-bg px-4 py-3 text-sm text-danger-text ring-1 ring-danger-border">
          {(nl.error as { response?: { data?: { detail?: string } } }).response?.data?.detail ?? "Search failed. Please try again."}
        </p>
        {back}
      </div>
    );
  }
  const data = nl.data!;
  return (
    <div className="space-y-3">
      <div className="space-y-1.5">
        <p className="text-sm font-semibold text-text-secondary">Interpreted as:</p>
        <FilterChips filters={data.filters} />
      </div>
      {data.players.length === 0 ? (
        <EmptyState title="No players matched" body="Try describing him another way." />
      ) : (
        <ul className="overflow-hidden rounded-xl bg-surface ring-1 ring-border">
          {data.players.map((p) => <PlayerRow key={p.player_id} row={rowFromSearchResult(p)} />)}
        </ul>
      )}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-text-muted">{data.total} player{data.total === 1 ? "" : "s"} found</p>
        {back}
      </div>
    </div>
  );
}
