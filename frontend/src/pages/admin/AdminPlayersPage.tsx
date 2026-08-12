import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import api from "../../lib/api";
import type { Paginated, Player } from "../../types/api";
import Badge from "../../components/ui/Badge";
import DateRangeFilter, { EMPTY_DATE_RANGE, type DateRange } from "../../components/ui/DateRangeFilter";
import Pagination from "../../components/ui/Pagination";
import Spinner from "../../components/ui/Spinner";
import { positionVariant } from "../../lib/badges";
import type { PlayerPosition } from "../../types/enums";

const POSITIONS = ["GK", "DEF", "MID", "FWD"];
const STATUSES  = ["CONTRACTED", "EXTERNAL", "FREE_AGENT"];

const VISIBILITY_STYLE: Record<string, string> = {
  PUBLIC:     "text-success-text",
  CLUBS_ONLY: "text-accent",
  PRIVATE:    "text-text-muted",
};

export default function AdminPlayersPage() {
  const navigate = useNavigate();
  const [search,   setSearch]   = useState("");
  const [position, setPosition] = useState("");
  const [status,   setStatus]   = useState("");
  const [dateRange, setDateRange] = useState<DateRange>(EMPTY_DATE_RANGE);
  const [page,     setPage]     = useState(1);

  const { data, isLoading } = useQuery<Paginated<Player>>({
    queryKey: ["admin", "players", { search, position, status, ...dateRange, page }],
    queryFn: () =>
      api
        .get<Paginated<Player>>("/admin/players", {
          params: {
            page, page_size: 30,
            ...(search   && { search }),
            ...(position && { position }),
            ...(status   && { status }),
            ...(dateRange.dateFrom && { date_from: dateRange.dateFrom }),
            ...(dateRange.dateTo && { date_to: dateRange.dateTo }),
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

  function handleDateRangeChange(range: DateRange) {
    setDateRange(range);
    setPage(1);
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-text">Players</h1>
        <p className="mt-1 text-sm text-text-muted">
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
          className="rounded-lg bg-surface px-3 py-2 text-sm text-text placeholder-text-muted ring-1 ring-input-border focus:outline-none focus:ring-warning-fill w-48"
        />
        <select
          value={position}
          onChange={(e) => handleFilter("position", e.target.value)}
          className="rounded-lg bg-surface px-3 py-2 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-warning-fill"
        >
          <option value="">All positions</option>
          {POSITIONS.map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
        <select
          value={status}
          onChange={(e) => handleFilter("status", e.target.value)}
          className="rounded-lg bg-surface px-3 py-2 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-warning-fill"
        >
          <option value="">All statuses</option>
          {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      <div className="mb-5">
        <DateRangeFilter value={dateRange} onChange={handleDateRangeChange} accent="amber" />
      </div>

      {isLoading && <div className="flex justify-center py-12"><Spinner size="lg" /></div>}

      {data && (
        <>
          <div className="overflow-x-auto rounded-xl ring-1 ring-border">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-rule bg-surface-header text-left text-xs font-semibold uppercase tracking-wider text-text-muted">
                  <th className="px-4 py-3">Name</th>
                  <th className="px-4 py-3">Pos</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Visibility</th>
                  <th className="px-4 py-3">Club / Team</th>
                  <th className="px-4 py-3">Age</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-rule-faint">
                {data.items.map((p) => (
                  <tr
                    key={p.id}
                    onClick={() => navigate(`/admin/players/${p.id}`)}
                    className="cursor-pointer bg-surface hover:bg-surface-inset transition-colors"
                  >
                    <td className="px-4 py-3 font-medium text-text">{p.name}</td>
                    <td className="px-4 py-3">
                      {p.position ? (
                        <Badge variant={positionVariant(p.position as PlayerPosition)}>
                          {p.position}
                        </Badge>
                      ) : <span className="text-text-muted">—</span>}
                    </td>
                    <td className="px-4 py-3">
                      {/* Admin sees the three real states, not the buyer-facing
                          collapse of EXTERNAL into "Contracted" (ADR 0003). */}
                      <Badge variant={p.status === "FREE_AGENT" ? "warning" : "info"}>
                        {p.status === "FREE_AGENT" ? "Free Agent"
                          : p.status === "EXTERNAL" ? "External"
                          : "Contracted"}
                      </Badge>
                    </td>
                    <td className={`px-4 py-3 text-xs font-medium ${VISIBILITY_STYLE[p.visibility] ?? "text-text-muted"}`}>
                      {p.visibility}
                    </td>
                    <td className="px-4 py-3 text-xs">
                      {p.current_club ? (
                        <span className="font-medium text-text">{p.current_club.name}</span>
                      ) : p.world_team ? (
                        <span className="text-text-muted" title="Vendor world team (no TransferX club)">{p.world_team.name} <span className="text-text-muted">(world)</span></span>
                      ) : p.team_name ? (
                        <span className="text-text-muted">{p.team_name}</span>
                      ) : (
                        <span className="text-text-muted">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-text-muted">{p.age ?? "—"}</td>
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
