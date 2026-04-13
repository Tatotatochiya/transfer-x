import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import api from "../../lib/api";
import type { Paginated, Player } from "../../types/api";
import Badge from "../../components/ui/Badge";
import Pagination from "../../components/ui/Pagination";
import Spinner from "../../components/ui/Spinner";
import { positionVariant } from "../../lib/badges";
import type { PlayerPosition } from "../../types/enums";

const POSITIONS = ["GK", "DEF", "MID", "FWD"];
const STATUSES  = ["CONTRACTED", "FREE_AGENT"];

const VISIBILITY_STYLE: Record<string, string> = {
  PUBLIC:     "text-emerald-400",
  CLUBS_ONLY: "text-sky-400",
  PRIVATE:    "text-slate-500",
};

export default function AdminPlayersPage() {
  const navigate = useNavigate();
  const [search,   setSearch]   = useState("");
  const [position, setPosition] = useState("");
  const [status,   setStatus]   = useState("");
  const [page,     setPage]     = useState(1);

  const { data, isLoading } = useQuery<Paginated<Player>>({
    queryKey: ["admin", "players", { search, position, status, page }],
    queryFn: () =>
      api
        .get<Paginated<Player>>("/admin/players", {
          params: {
            page, page_size: 20,
            ...(search   && { search }),
            ...(position && { position }),
            ...(status   && { status }),
          },
        })
        .then((r) => r.data),
  });

  function handleFilter(field: string, val: string) {
    if (field === "search")   setSearch(val);
    if (field === "position") setPosition(val);
    if (field === "status")   setStatus(val);
    setPage(1);
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white">Players</h1>
        <p className="mt-1 text-sm text-slate-400">
          All players — no visibility filter {data ? `· ${data.total} total` : ""}
        </p>
      </div>

      {/* Filters */}
      <div className="mb-5 flex flex-wrap gap-3">
        <input
          type="text"
          placeholder="Search name…"
          value={search}
          onChange={(e) => handleFilter("search", e.target.value)}
          className="rounded-lg bg-slate-800 px-3 py-2 text-sm text-white placeholder-slate-500 ring-1 ring-white/10 focus:outline-none focus:ring-amber-500 w-48"
        />
        <select
          value={position}
          onChange={(e) => handleFilter("position", e.target.value)}
          className="rounded-lg bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-amber-500"
        >
          <option value="">All positions</option>
          {POSITIONS.map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
        <select
          value={status}
          onChange={(e) => handleFilter("status", e.target.value)}
          className="rounded-lg bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-amber-500"
        >
          <option value="">All statuses</option>
          {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      {isLoading && <div className="flex justify-center py-12"><Spinner size="lg" /></div>}

      {data && (
        <>
          <div className="overflow-x-auto rounded-xl ring-1 ring-white/[0.08]">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-white/[0.08] text-left text-xs font-semibold uppercase tracking-wider text-slate-500">
                  <th className="px-4 py-3">Name</th>
                  <th className="px-4 py-3">Pos</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Visibility</th>
                  <th className="px-4 py-3">Club / Team</th>
                  <th className="px-4 py-3">Age</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.04]">
                {data.items.map((p) => (
                  <tr
                    key={p.id}
                    onClick={() => navigate(`/admin/players/${p.id}`)}
                    className="cursor-pointer bg-slate-900 hover:bg-slate-800/40 transition-colors"
                  >
                    <td className="px-4 py-3 font-medium text-white">{p.name}</td>
                    <td className="px-4 py-3">
                      {p.position ? (
                        <Badge variant={positionVariant(p.position as PlayerPosition)}>
                          {p.position}
                        </Badge>
                      ) : <span className="text-slate-500">—</span>}
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={p.status === "FREE_AGENT" ? "warning" : "info"}>
                        {p.status === "FREE_AGENT" ? "Free Agent" : "Contracted"}
                      </Badge>
                    </td>
                    <td className={`px-4 py-3 text-xs font-medium ${VISIBILITY_STYLE[p.visibility] ?? "text-slate-400"}`}>
                      {p.visibility}
                    </td>
                    <td className="px-4 py-3 text-xs">
                      {p.current_club ? (
                        <span className="font-medium text-white">{p.current_club.name}</span>
                      ) : p.world_team ? (
                        <span className="text-slate-500" title="Vendor world team (no TransferX club)">{p.world_team.name} <span className="text-slate-600">(world)</span></span>
                      ) : p.team_name ? (
                        <span className="text-slate-500">{p.team_name}</span>
                      ) : (
                        <span className="text-slate-600">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-slate-400">{p.age ?? "—"}</td>
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
