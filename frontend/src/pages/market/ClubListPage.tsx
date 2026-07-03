import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { ClubPublic, Paginated } from "../../types/api";
import PageHeader from "../../components/ui/PageHeader";
import Pagination from "../../components/ui/Pagination";
import Spinner from "../../components/ui/Spinner";
import EmptyState from "../../components/ui/EmptyState";
import Icon from "../../components/layout/Icon";

const SORT_OPTIONS = [
  { value: "name|asc",         label: "Name (A–Z)" },
  { value: "name|desc",        label: "Name (Z–A)" },
  { value: "country|asc",      label: "Country (A–Z)" },
  { value: "league_name|asc",  label: "League (A–Z)" },
  { value: "created_at|desc",  label: "Newest first" },
];

export default function ClubListPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  function prefetchClub(id: string) {
    queryClient.prefetchQuery({
      queryKey: ["clubs", id],
      queryFn: () => api.get<ClubPublic>(`/clubs/${id}`).then((r) => r.data),
      staleTime: 60_000,
    });
  }
  const [search,     setSearch]     = useState("");
  const [country,    setCountry]    = useState("");
  const [league,     setLeague]     = useState("");
  const [sort,       setSort]       = useState("name|asc");
  const [page,       setPage]       = useState(1);

  const [sortBy, sortDir] = sort.split("|");

  function handleFilter(field: "search" | "country" | "league", val: string) {
    if (field === "search")  setSearch(val);
    if (field === "country") setCountry(val);
    if (field === "league")  setLeague(val);
    setPage(1);
  }

  const { data, isLoading, isError } = useQuery<Paginated<ClubPublic>>({
    queryKey: ["clubs", { search, country, league, sortBy, sortDir, page }],
    queryFn: () =>
      api
        .get<Paginated<ClubPublic>>("/clubs", {
          params: {
            page,
            page_size: 25,
            ...(search  && { search }),
            ...(country && { country }),
            ...(league  && { league_name: league }),
            sort_by:  sortBy,
            sort_dir: sortDir,
          },
        })
        .then((r) => r.data),
  });

  return (
    <div>
      <PageHeader title="Clubs" subtitle="Browse all registered clubs" />

      {/* Filters */}
      <div className="mb-6 flex flex-wrap gap-3">
        <input
          type="text"
          placeholder="Search clubs…"
          value={search}
          onChange={(e) => handleFilter("search", e.target.value)}
          className="rounded-lg bg-slate-800 px-3 py-2 text-sm text-white placeholder-slate-500 ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500 transition-colors w-48"
        />
        <input
          type="text"
          placeholder="Country…"
          value={country}
          onChange={(e) => handleFilter("country", e.target.value)}
          className="rounded-lg bg-slate-800 px-3 py-2 text-sm text-white placeholder-slate-500 ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500 transition-colors w-36"
        />
        <input
          type="text"
          placeholder="League…"
          value={league}
          onChange={(e) => handleFilter("league", e.target.value)}
          className="rounded-lg bg-slate-800 px-3 py-2 text-sm text-white placeholder-slate-500 ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500 transition-colors w-40"
        />
        <select
          value={sort}
          onChange={(e) => { setSort(e.target.value); setPage(1); }}
          className="rounded-lg bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500 transition-colors"
        >
          {SORT_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-20">
          <Spinner size="lg" />
        </div>
      )}

      {isError && (
        <div className="rounded-xl bg-red-500/10 px-5 py-4 text-sm text-red-400 ring-1 ring-red-500/30">
          Failed to load clubs.
        </div>
      )}

      {data && data.items.length === 0 && (
        <EmptyState title="No clubs found" body="Try adjusting your search or filters." />
      )}

      {data && data.items.length > 0 && (
        <>
          <p className="mb-4 text-xs text-slate-500">{data.total} club{data.total !== 1 ? "s" : ""}</p>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {data.items.map((club) => (
              <div
                key={club.id}
                onMouseEnter={() => prefetchClub(club.id)}
                onClick={() => navigate(`/clubs/${club.id}`)}
                className="cursor-pointer rounded-xl bg-slate-900 ring-1 ring-white/[0.08] hover:ring-white/[0.18] hover:-translate-y-0.5 transition-all duration-200 px-5 py-4"
              >
                <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-slate-800 overflow-hidden">
                  {club.crest_url ? (
                    <img src={club.crest_url} alt={club.name} loading="lazy" className="h-full w-full object-contain p-1" />
                  ) : (
                    <span className="text-xl font-bold text-slate-500">
                      {club.name[0]?.toUpperCase()}
                    </span>
                  )}
                </div>
                <p className="flex items-center gap-1 font-semibold text-white truncate">
                  <span className="truncate">{club.name}</span>
                  {club.verified && (
                    <Icon name="check" className="h-3.5 w-3.5 shrink-0 text-sky-400" />
                  )}
                </p>
                <p className="mt-0.5 text-xs text-slate-400 truncate">
                  {[club.league_name, club.country].filter(Boolean).join(" · ") || "—"}
                </p>
              </div>
            ))}
          </div>
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
