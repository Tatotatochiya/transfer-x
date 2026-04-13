import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { AdminClubDetail, Paginated, WorldTeam } from "../../types/api";
import Button from "../../components/ui/Button";
import Pagination from "../../components/ui/Pagination";
import Spinner from "../../components/ui/Spinner";
import { formatCurrency, getApiError } from "../../lib/utils";

const ROLES = ["BUYER", "SELLER", "BOTH"];

// ── Import form for a single world team ──────────────────────────────────────

function ImportPanel({
  team,
  onImported,
}: {
  team: WorldTeam;
  onImported: (club: AdminClubDetail) => void;
}) {
  const [userId,   setUserId]   = useState("");
  const [role,     setRole]     = useState("BOTH");
  const [transfer, setTransfer] = useState("0");
  const [wage,     setWage]     = useState("0");

  const importClub = useMutation({
    mutationFn: () =>
      api
        .post<AdminClubDetail>(`/admin/world/teams/${team.id}/import-club`, {
          user_id:         userId,
          role,
          transfer_budget: parseFloat(transfer) || 0,
          wage_budget:     parseFloat(wage)     || 0,
        })
        .then((r) => r.data),
    onSuccess: (data) => {
      setUserId(""); setTransfer("0"); setWage("0");
      onImported(data);
    },
  });

  return (
    <form
      onSubmit={(e) => { e.preventDefault(); importClub.mutate(); }}
      className="space-y-3"
    >
      <div>
        <label className="mb-1 block text-xs text-slate-400">Assign to User (UUID)</label>
        <input
          value={userId}
          onChange={(e) => setUserId(e.target.value)}
          placeholder="paste user UUID…"
          required
          className="w-full rounded-lg bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-amber-500"
        />
      </div>
      <div className="grid grid-cols-2 gap-3">
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
        <div>
          <label className="mb-1 block text-xs text-slate-400">Transfer budget (£)</label>
          <input
            type="number"
            value={transfer}
            onChange={(e) => setTransfer(e.target.value)}
            className="w-full rounded-lg bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-amber-500"
          />
        </div>
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
      <div className="flex items-center gap-3 pt-1">
        <Button type="submit" variant="primary" size="sm" loading={importClub.isPending}>
          Import as Club
        </Button>
        {importClub.isError && (
          <p className="text-xs text-red-400">{getApiError(importClub.error, "Import failed.")}</p>
        )}
      </div>
    </form>
  );
}

// ── Squad import section (shown after club is created) ───────────────────────

function SquadImportRow({
  team,
  club,
}: {
  team: WorldTeam;
  club: AdminClubDetail;
}) {
  const navigate = useNavigate();
  const importSquad = useMutation({
    mutationFn: () =>
      api
        .post<{ imported: number; skipped: number }>(
          `/admin/world/teams/${team.id}/import-squad`,
          { club_id: club.id }
        )
        .then((r) => r.data),
  });

  if (importSquad.isSuccess) {
    const { imported, skipped } = importSquad.data;
    return (
      <div className="rounded-lg bg-emerald-500/10 px-4 py-3 ring-1 ring-emerald-500/20">
        <p className="text-sm font-semibold text-emerald-400">
          Squad imported: {imported} player{imported !== 1 ? "s" : ""} assigned
          {skipped > 0 && `, ${skipped} skipped (already at another club)`}
        </p>
        <button
          onClick={() => navigate(`/admin/clubs/${club.id}`)}
          className="mt-1 text-xs text-emerald-400/70 hover:text-emerald-400 transition-colors"
        >
          View club →
        </button>
      </div>
    );
  }

  return (
    <div className="rounded-lg bg-slate-800/60 px-4 py-3 ring-1 ring-white/[0.06]">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-white">
            Club created: <span className="text-emerald-400">{club.name}</span>
          </p>
          <p className="mt-0.5 text-xs text-slate-400">
            Optionally bulk-assign this team's players to the new club
          </p>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <Button
            variant="primary"
            size="sm"
            loading={importSquad.isPending}
            onClick={() => importSquad.mutate()}
          >
            Import squad
          </Button>
          <button
            onClick={() => navigate(`/admin/clubs/${club.id}`)}
            className="text-xs text-slate-400 hover:text-white transition-colors"
          >
            Skip →
          </button>
        </div>
      </div>
      {importSquad.isError && (
        <p className="mt-2 text-xs text-red-400">{getApiError(importSquad.error, "Import failed.")}</p>
      )}
    </div>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function AdminWorldImportPage() {
  const queryClient = useQueryClient();
  const [search,       setSearch]       = useState("");
  const [page,         setPage]         = useState(1);
  const [selected,     setSelected]     = useState<WorldTeam | null>(null);
  const [importedClub, setImportedClub] = useState<AdminClubDetail | null>(null);

  const { data, isLoading } = useQuery<Paginated<WorldTeam>>({
    queryKey: ["world", "teams", { search, page }],
    queryFn: () =>
      api
        .get<Paginated<WorldTeam>>("/world/teams", {
          params: { page, page_size: 20, ...(search && { search }) },
        })
        .then((r) => r.data),
  });

  function selectTeam(team: WorldTeam) {
    setSelected(team);
    setImportedClub(null);
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white">World Import</h1>
        <p className="mt-1 text-sm text-slate-400">
          Promote a world team and its players into TransferX
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Left — world team browser */}
        <div>
          <div className="mb-3 flex items-center gap-3">
            <input
              type="text"
              placeholder="Search teams…"
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1); }}
              className="flex-1 rounded-lg bg-slate-800 px-3 py-2 text-sm text-white placeholder-slate-500 ring-1 ring-white/10 focus:outline-none focus:ring-amber-500"
            />
          </div>

          {isLoading && <div className="flex justify-center py-10"><Spinner size="lg" /></div>}

          {data && (
            <>
              <div className="rounded-xl ring-1 ring-white/[0.08] overflow-hidden">
                {data.items.map((team) => (
                  <button
                    key={team.id}
                    onClick={() => selectTeam(team)}
                    className={`w-full flex items-center gap-3 px-4 py-3 text-left text-sm border-b border-white/[0.04] last:border-0 transition-colors ${
                      selected?.id === team.id
                        ? "bg-amber-500/10 ring-inset ring-1 ring-amber-500/20"
                        : "bg-slate-900 hover:bg-slate-800/60"
                    }`}
                  >
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-slate-800 overflow-hidden">
                      {team.crest_url ? (
                        <img src={team.crest_url} alt={team.name} className="h-full w-full object-contain p-0.5" />
                      ) : (
                        <span className="text-xs font-bold text-slate-400">{team.name[0]}</span>
                      )}
                    </div>
                    <div className="min-w-0">
                      <p className="font-medium text-white truncate">{team.name}</p>
                      <p className="text-xs text-slate-500 truncate">
                        {[team.league_name, team.country].filter(Boolean).join(" · ") || "—"}
                      </p>
                    </div>
                  </button>
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

        {/* Right — import panel */}
        <div>
          {!selected ? (
            <div className="flex h-48 items-center justify-center rounded-xl ring-1 ring-white/[0.06]">
              <p className="text-sm text-slate-500">Select a team to import</p>
            </div>
          ) : (
            <div className="rounded-xl bg-slate-900 ring-1 ring-white/[0.08] p-5 space-y-5">
              {/* Team header */}
              <div className="flex items-center gap-3">
                <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-slate-800 overflow-hidden">
                  {selected.crest_url ? (
                    <img src={selected.crest_url} alt={selected.name} className="h-full w-full object-contain" />
                  ) : (
                    <span className="text-sm font-bold text-slate-400">{selected.name[0]}</span>
                  )}
                </div>
                <div>
                  <p className="font-semibold text-white">{selected.name}</p>
                  <p className="text-xs text-slate-400">
                    {[selected.league_name, selected.country].filter(Boolean).join(" · ") || "—"}
                  </p>
                </div>
              </div>

              {/* Squad import result (shown after club created) */}
              {importedClub && (
                <SquadImportRow team={selected} club={importedClub} />
              )}

              {/* Import form (hidden once club is created) */}
              {!importedClub && (
                <>
                  <div className="border-t border-white/[0.06] pt-4">
                    <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">
                      Import as Club
                    </p>
                    <ImportPanel
                      team={selected}
                      onImported={(club) => {
                        setImportedClub(club);
                        queryClient.invalidateQueries({ queryKey: ["admin", "clubs"] });
                      }}
                    />
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
