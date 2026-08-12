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
        <label className="mb-1 block text-xs text-text-muted">Assign to User (UUID)</label>
        <input
          value={userId}
          onChange={(e) => setUserId(e.target.value)}
          placeholder="paste user UUID…"
          required
          className="w-full rounded-lg bg-surface px-3 py-2 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-warning-fill"
        />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="mb-1 block text-xs text-text-muted">Role</label>
          <select
            value={role}
            onChange={(e) => setRole(e.target.value)}
            className="w-full rounded-lg bg-surface px-3 py-2 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-warning-fill"
          >
            {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
        </div>
        <div>
          <label className="mb-1 block text-xs text-text-muted">Transfer budget (£)</label>
          <input
            type="number"
            value={transfer}
            onChange={(e) => setTransfer(e.target.value)}
            className="w-full rounded-lg bg-surface px-3 py-2 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-warning-fill"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs text-text-muted">Weekly wage budget (£)</label>
          <input
            type="number"
            value={wage}
            onChange={(e) => setWage(e.target.value)}
            className="w-full rounded-lg bg-surface px-3 py-2 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-warning-fill"
          />
        </div>
      </div>
      <div className="flex items-center gap-3 pt-1">
        <Button type="submit" variant="primary" size="sm" loading={importClub.isPending}>
          Import as Club
        </Button>
        {importClub.isError && (
          <p className="text-xs text-danger-text">{getApiError(importClub.error, "Import failed.")}</p>
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
      <div className="rounded-lg bg-success/10 px-4 py-3 ring-1 ring-success/20">
        <p className="text-sm font-semibold text-success-text">
          Squad imported: {imported} player{imported !== 1 ? "s" : ""} assigned
          {skipped > 0 && `, ${skipped} skipped (already at another club)`}
        </p>
        <button
          onClick={() => navigate(`/admin/clubs/${club.id}`)}
          className="mt-1 text-xs text-success-text-alt hover:text-success-text transition-colors"
        >
          View club →
        </button>
      </div>
    );
  }

  return (
    <div className="rounded-lg bg-surface-inset px-4 py-3 ring-1 ring-border">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-text">
            Club created: <span className="text-success-text">{club.name}</span>
          </p>
          <p className="mt-0.5 text-xs text-text-muted">
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
            className="text-xs text-text-muted hover:text-text transition-colors"
          >
            Skip →
          </button>
        </div>
      </div>
      {importSquad.isError && (
        <p className="mt-2 text-xs text-danger-text">{getApiError(importSquad.error, "Import failed.")}</p>
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
        <h1 className="text-2xl font-bold text-text">World Import</h1>
        <p className="mt-1 text-sm text-text-muted">
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
              className="flex-1 rounded-lg bg-surface px-3 py-2 text-sm text-text placeholder-text-muted ring-1 ring-input-border focus:outline-none focus:ring-warning-fill"
            />
          </div>

          {isLoading && <div className="flex justify-center py-10"><Spinner size="lg" /></div>}

          {data && (
            <>
              <div className="rounded-xl ring-1 ring-border overflow-hidden">
                {data.items.map((team) => (
                  <button
                    key={team.id}
                    onClick={() => selectTeam(team)}
                    className={`w-full flex items-center gap-3 px-4 py-3 text-left text-sm border-b border-rule-faint last:border-0 transition-colors ${
                      selected?.id === team.id
                        ? "bg-warning-fill/10 ring-inset ring-1 ring-warning-fill/20"
                        : "bg-surface hover:bg-surface-inset"
                    }`}
                  >
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-surface-inset overflow-hidden">
                      {team.crest_url ? (
                        <img src={team.crest_url} alt={team.name} className="h-full w-full object-contain p-0.5" />
                      ) : (
                        <span className="text-xs font-bold text-text-muted">{team.name[0]}</span>
                      )}
                    </div>
                    <div className="min-w-0">
                      <p className="font-medium text-text truncate">{team.name}</p>
                      <p className="text-xs text-text-muted truncate">
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
            <div className="flex h-48 items-center justify-center rounded-xl ring-1 ring-border">
              <p className="text-sm text-text-muted">Select a team to import</p>
            </div>
          ) : (
            <div className="rounded-xl bg-surface ring-1 ring-border p-5 space-y-5">
              {/* Team header */}
              <div className="flex items-center gap-3">
                <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-surface-inset overflow-hidden">
                  {selected.crest_url ? (
                    <img src={selected.crest_url} alt={selected.name} className="h-full w-full object-contain" />
                  ) : (
                    <span className="text-sm font-bold text-text-muted">{selected.name[0]}</span>
                  )}
                </div>
                <div>
                  <p className="font-semibold text-text">{selected.name}</p>
                  <p className="text-xs text-text-muted">
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
                  <div className="border-t border-rule pt-4">
                    <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-text-muted">
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
