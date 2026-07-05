import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { AdminClub, AdminClubDetail, Paginated, WorldTeam } from "../../types/api";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import DateRangeFilter, { EMPTY_DATE_RANGE, type DateRange } from "../../components/ui/DateRangeFilter";
import Pagination from "../../components/ui/Pagination";
import Spinner from "../../components/ui/Spinner";
import { formatDate, getApiError } from "../../lib/utils";

const ROLE_VARIANT: Record<string, "success" | "info" | "warning" | "neutral"> = {
  BOTH:   "success",
  SELLER: "warning",
  BUYER:  "info",
  ADMIN:  "neutral",
};

const ROLES = ["BUYER", "SELLER", "BOTH", "ADMIN"];

// ── World team picker ─────────────────────────────────────────────────────────

function WorldTeamPicker({
  onSelect,
}: {
  onSelect: (team: WorldTeam) => void;
}) {
  const [q, setQ]           = useState("");
  const [open, setOpen]     = useState(false);
  const ref                 = useRef<HTMLDivElement>(null);

  const { data } = useQuery<Paginated<WorldTeam>>({
    queryKey: ["world", "teams", "picker", q],
    queryFn: () =>
      api.get<Paginated<WorldTeam>>("/world/teams", { params: { search: q, page_size: 8 } })
         .then((r) => r.data),
    enabled: open,
  });

  // Close on outside click
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  return (
    <div ref={ref} className="relative">
      <label className="mb-1 block text-xs text-slate-400">Search world team to prefill</label>
      <input
        value={q}
        onChange={(e) => { setQ(e.target.value); setOpen(true); }}
        onFocus={() => setOpen(true)}
        placeholder="e.g. Arsenal, Chelsea…"
        className="w-full rounded-lg bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-amber-500"
      />
      {open && data && data.items.length > 0 && (
        <div className="absolute top-full left-0 right-0 z-50 mt-1 rounded-xl bg-slate-800 ring-1 ring-white/10 shadow-xl overflow-hidden">
          {data.items.map((team) => (
            <button
              key={team.id}
              type="button"
              onClick={() => { onSelect(team); setQ(""); setOpen(false); }}
              className="flex w-full items-center gap-3 px-3 py-2 text-left text-sm hover:bg-slate-700 transition-colors"
            >
              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-slate-700 overflow-hidden">
                {team.crest_url
                  ? <img src={team.crest_url} alt={team.name} className="h-full w-full object-contain p-0.5" />
                  : <span className="text-xs font-bold text-slate-400">{team.name[0]}</span>}
              </div>
              <div>
                <p className="font-medium text-white">{team.name}</p>
                <p className="text-xs text-slate-500">
                  {[team.league_name, team.country].filter(Boolean).join(" · ") || "—"}
                </p>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Create club panel ─────────────────────────────────────────────────────────

function CreateClubPanel({ onCreated }: { onCreated: (club: AdminClubDetail) => void }) {
  const [userId,    setUserId]    = useState("");
  const [name,      setName]      = useState("");
  const [role,      setRole]      = useState("BOTH");
  const [country,   setCountry]   = useState("");
  const [league,    setLeague]    = useState("");
  const [crestUrl,  setCrestUrl]  = useState("");
  const [transfer,  setTransfer]  = useState("0");
  const [wage,      setWage]      = useState("0");
  const [prefilled, setPrefilled] = useState<WorldTeam | null>(null);

  function handleWorldTeamSelect(team: WorldTeam) {
    setName(team.name);
    setCountry(team.country ?? "");
    setLeague(team.league_name ?? "");
    setCrestUrl(team.crest_url ?? "");
    setPrefilled(team);
  }

  function clearPrefill() {
    setName(""); setCountry(""); setLeague(""); setCrestUrl("");
    setPrefilled(null);
  }

  const mutation = useMutation({
    mutationFn: () =>
      api.post<AdminClubDetail>("/admin/clubs", {
        user_id:         userId,
        name,
        role,
        country:         country    || undefined,
        league_name:     league     || undefined,
        crest_url:       crestUrl   || undefined,
        transfer_budget: parseFloat(transfer) || 0,
        wage_budget:     parseFloat(wage)     || 0,
      }).then((r) => r.data),
    onSuccess: (data) => {
      setUserId(""); setName(""); setRole("BOTH");
      setCountry(""); setLeague(""); setCrestUrl("");
      setTransfer("0"); setWage("0"); setPrefilled(null);
      onCreated(data);
    },
  });

  return (
    <form
      onSubmit={(e) => { e.preventDefault(); mutation.mutate(); }}
      className="space-y-4"
    >
      {/* World team prefill picker */}
      {!prefilled ? (
        <WorldTeamPicker onSelect={handleWorldTeamSelect} />
      ) : (
        <div className="flex items-center gap-3 rounded-lg bg-slate-800/60 px-3 py-2 ring-1 ring-white/[0.06]">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-slate-700 overflow-hidden">
            {prefilled.crest_url
              ? <img src={prefilled.crest_url} alt={prefilled.name} className="h-full w-full object-contain p-0.5" />
              : <span className="text-xs font-bold text-slate-400">{prefilled.name[0]}</span>}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-white truncate">{prefilled.name}</p>
            <p className="text-xs text-slate-500">
              {[prefilled.league_name, prefilled.country].filter(Boolean).join(" · ") || "—"}
            </p>
          </div>
          <button
            type="button"
            onClick={clearPrefill}
            className="text-xs text-slate-500 hover:text-white transition-colors shrink-0"
          >
            ✕ Clear
          </button>
        </div>
      )}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {/* User ID — always manual */}
        <div>
          <label className="mb-1 block text-xs text-slate-400">User ID (UUID)</label>
          <input
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            placeholder="paste user UUID…"
            required
            className="w-full rounded-lg bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-amber-500"
          />
        </div>

        {/* Name — only shown when not prefilled */}
        {!prefilled && (
          <div>
            <label className="mb-1 block text-xs text-slate-400">Club name</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Arsenal FC"
              required
              className="w-full rounded-lg bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-amber-500"
            />
          </div>
        )}

        {/* Role */}
        <div>
          <label className="mb-1 block text-xs text-slate-400">Role</label>
          <select
            value={role}
            onChange={(e) => setRole(e.target.value)}
            className="w-full rounded-lg bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-amber-500"
          >
            {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
        </div>

        {/* Country + League — only shown when not prefilled */}
        {!prefilled && (
          <>
            <div>
              <label className="mb-1 block text-xs text-slate-400">Country</label>
              <input
                value={country}
                onChange={(e) => setCountry(e.target.value)}
                placeholder="e.g. England"
                className="w-full rounded-lg bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-amber-500"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-slate-400">League</label>
              <input
                value={league}
                onChange={(e) => setLeague(e.target.value)}
                placeholder="e.g. Premier League"
                className="w-full rounded-lg bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-amber-500"
              />
            </div>
          </>
        )}

        {/* Transfer budget */}
        <div>
          <label className="mb-1 block text-xs text-slate-400">Transfer budget (£)</label>
          <input
            type="number"
            value={transfer}
            onChange={(e) => setTransfer(e.target.value)}
            className="w-full rounded-lg bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-amber-500"
          />
        </div>

        {/* Wage budget */}
        <div>
          <label className="mb-1 block text-xs text-slate-400">Weekly wage budget (£)</label>
          <input
            type="number"
            value={wage}
            onChange={(e) => setWage(e.target.value)}
            className="w-full rounded-lg bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-amber-500"
          />
        </div>
      </div>

      <div className="flex items-center gap-3">
        <Button type="submit" variant="primary" size="sm" loading={mutation.isPending}>
          Create club
        </Button>
        {mutation.isError && (
          <p className="text-xs text-red-400">{getApiError(mutation.error, "Create failed.")}</p>
        )}
        {mutation.isSuccess && (
          <p className="text-xs text-emerald-400">Club created.</p>
        )}
      </div>
    </form>
  );
}

export default function AdminClubsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [search,     setSearch]     = useState("");
  const [dateRange,  setDateRange]  = useState<DateRange>(EMPTY_DATE_RANGE);
  const [page,       setPage]       = useState(1);
  const [showCreate, setShowCreate] = useState(false);

  const { data, isLoading } = useQuery<Paginated<AdminClub>>({
    queryKey: ["admin", "clubs", { search, ...dateRange, page }],
    queryFn: () =>
      api
        .get<Paginated<AdminClub>>("/admin/clubs", {
          params: {
            page, page_size: 30,
            ...(search && { search }),
            ...(dateRange.dateFrom && { date_from: dateRange.dateFrom }),
            ...(dateRange.dateTo && { date_to: dateRange.dateTo }),
          },
        })
        .then((r) => r.data),
  });

  function handleDateRangeChange(range: DateRange) {
    setDateRange(range);
    setPage(1);
  }

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Clubs</h1>
          <p className="mt-1 text-sm text-slate-400">{data ? `${data.total} total` : ""}</p>
        </div>
        <div className="flex items-center gap-3">
          <input
            type="text"
            placeholder="Search clubs…"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            className="rounded-lg bg-slate-800 px-3 py-2 text-sm text-white placeholder-slate-500 ring-1 ring-white/10 focus:outline-none focus:ring-amber-500 transition-colors w-56"
          />
          <Button variant="primary" size="sm" onClick={() => setShowCreate((v) => !v)}>
            {showCreate ? "Hide" : "Create club"}
          </Button>
        </div>
      </div>

      <div className="mb-6">
        <DateRangeFilter value={dateRange} onChange={handleDateRangeChange} accent="amber" />
      </div>

      {showCreate && (
        <div className="mb-6 rounded-xl bg-slate-900 ring-1 ring-white/[0.08] px-5 py-4">
          <p className="mb-4 text-xs font-semibold uppercase tracking-wider text-slate-400">New club</p>
          <CreateClubPanel onCreated={(club) => {
            queryClient.invalidateQueries({ queryKey: ["admin", "clubs"] });
            navigate(`/admin/clubs/${club.id}`);
          }} />
        </div>
      )}

      {isLoading && <div className="flex justify-center py-12"><Spinner size="lg" /></div>}

      {data && (
        <>
          <div className="overflow-x-auto rounded-xl ring-1 ring-white/[0.08]">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-white/[0.08] text-left text-xs font-semibold uppercase tracking-wider text-slate-500">
                  <th className="px-4 py-3">Name</th>
                  <th className="px-4 py-3">Role</th>
                  <th className="px-4 py-3">League</th>
                  <th className="px-4 py-3">Country</th>
                  <th className="px-4 py-3">Registered</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.04]">
                {data.items.map((club) => (
                  <tr
                    key={club.id}
                    onClick={() => navigate(`/admin/clubs/${club.id}`)}
                    className="cursor-pointer bg-slate-900 hover:bg-slate-800/40 transition-colors"
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2.5">
                        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-slate-800 text-xs font-bold text-slate-400 overflow-hidden">
                          {club.crest_url ? (
                            <img src={club.crest_url} alt={club.name} className="h-full w-full object-contain p-0.5" />
                          ) : (
                            club.name[0]?.toUpperCase()
                          )}
                        </div>
                        <span className="font-medium text-white">{club.name}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={ROLE_VARIANT[club.role] ?? "neutral"}>{club.role}</Badge>
                    </td>
                    <td className="px-4 py-3 text-slate-400">{club.league_name ?? "—"}</td>
                    <td className="px-4 py-3 text-slate-400">{club.country ?? "—"}</td>
                    <td className="px-4 py-3 text-xs text-slate-500">{formatDate(club.created_at)}</td>
                    <td className="px-4 py-3 text-xs text-slate-600">{club.id.slice(0, 8)}…</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination page={data.page} total={data.total} pageSize={data.page_size} onChange={setPage} />
        </>
      )}
    </div>
  );
}
