import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { Player, Shortlist } from "../../types/api";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import EmptyState from "../../components/ui/EmptyState";
import PageHeader from "../../components/ui/PageHeader";
import Spinner from "../../components/ui/Spinner";
import { positionVariant } from "../../lib/badges";
import { getApiError } from "../../lib/utils";
import { useConfirm } from "../../context/ConfirmContext";
import type { PlayerPosition } from "../../types/enums";

function useDebounce<T>(value: T, ms: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return debounced;
}

const positionColour: Record<string, string> = {
  GK:  "bg-amber-500/20 text-amber-400",
  DEF: "bg-blue-500/20 text-blue-400",
  MID: "bg-emerald-500/20 text-emerald-400",
  FWD: "bg-red-500/20 text-red-400",
};

// ── Add player form ───────────────────────────────────────────────────────────

function AddPlayerForm({
  shortlistId,
  onDone,
}: {
  shortlistId: string;
  onDone: () => void;
}) {
  const queryClient = useQueryClient();
  const [query, setQuery]           = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedName, setSelectedName] = useState("");
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [priority, setPriority]     = useState("3");
  const [notes, setNotes]           = useState("");
  const [error, setError]           = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const debouncedQ = useDebounce(query, 280);

  const { data: searchData, isFetching } = useQuery<{ players: Player[] }>({
    queryKey: ["shortlist-player-search", debouncedQ],
    queryFn: () =>
      api.get<{ players: Player[] }>("/search", { params: { q: debouncedQ } }).then((r) => r.data),
    enabled: debouncedQ.length >= 2 && !selectedId,
    staleTime: 10_000,
  });

  const mutation = useMutation({
    mutationFn: (body: object) =>
      api.post(`/scouting/shortlists/${shortlistId}/items`, body).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["scouting", "shortlists", shortlistId] });
      onDone();
    },
    onError: (err: unknown) => setError(getApiError(err, "Failed to add player.")),
  });

  function selectPlayer(p: Player) {
    setSelectedId(p.id);
    setSelectedName(p.name);
    setQuery(p.name);
    setDropdownOpen(false);
  }

  function handleQueryChange(e: React.ChangeEvent<HTMLInputElement>) {
    setQuery(e.target.value);
    setSelectedId(null);
    setDropdownOpen(true);
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedId) { setError("Select a player from the search results."); return; }
    mutation.mutate({ player_id: selectedId, priority: parseInt(priority), notes: notes.trim() || undefined });
  }

  const players = searchData?.players ?? [];

  return (
    <div className="rounded-xl bg-slate-800/60 px-4 py-4 ring-1 ring-white/[0.08] mb-6">
      <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">Add player</p>
      <form onSubmit={handleSubmit} className="space-y-3">
        {/* Player search */}
        <div className="relative">
          <label className="mb-1 block text-xs text-slate-400">Player</label>
          <div className="relative">
            <svg className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-500" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-4.35-4.35M17 11A6 6 0 105 11a6 6 0 0012 0z" />
            </svg>
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={handleQueryChange}
              onFocus={() => setDropdownOpen(true)}
              placeholder="Search by name…"
              autoComplete="off"
              className="w-full rounded-lg bg-slate-800 pl-8 pr-3 py-2 text-sm text-white placeholder-slate-500 ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500 transition-colors"
            />
            {isFetching && (
              <svg className="absolute right-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 animate-spin text-slate-500" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
            )}
          </div>

          {/* Dropdown */}
          {dropdownOpen && !selectedId && players.length > 0 && (
            <div className="absolute z-20 mt-1 w-full rounded-lg bg-slate-800 ring-1 ring-white/10 shadow-xl overflow-hidden">
              {players.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  onMouseDown={() => selectPlayer(p)}
                  className="flex w-full items-center gap-3 px-3 py-2.5 hover:bg-slate-700/60 transition-colors text-left"
                >
                  {p.photo_url ? (
                    <img src={p.photo_url} alt={p.name} className="h-7 w-7 shrink-0 rounded-full object-cover ring-1 ring-white/10" />
                  ) : (
                    <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-slate-700 text-xs font-bold text-slate-400">
                      {p.name[0]?.toUpperCase()}
                    </div>
                  )}
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-white">{p.name}</p>
                    <p className="text-xs text-slate-500 truncate">
                      {p.current_club?.name ?? p.team_name ?? "Free Agent"}
                    </p>
                  </div>
                  {p.position && (
                    <span className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-bold ${positionColour[p.position] ?? "bg-slate-700 text-slate-400"}`}>
                      {p.position}
                    </span>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1 block text-xs text-slate-400">Priority (1–5)</label>
            <input
              type="number"
              min="1"
              max="5"
              value={priority}
              onChange={(e) => setPriority(e.target.value)}
              className="w-full rounded-lg bg-slate-800 px-3 py-2 text-sm text-white ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500 transition-colors"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-400">Notes (optional)</label>
            <input
              type="text"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Any notes…"
              className="w-full rounded-lg bg-slate-800 px-3 py-2 text-sm text-white placeholder-slate-500 ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500 transition-colors"
            />
          </div>
        </div>

        {error && <p className="text-xs text-red-400">{error}</p>}
        <div className="flex gap-2">
          <Button type="submit" variant="primary" size="sm" loading={mutation.isPending}
            disabled={!selectedId}>
            Add
          </Button>
          <Button type="button" variant="ghost" size="sm" onClick={onDone}>Cancel</Button>
        </div>
      </form>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function ShortlistDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const confirm = useConfirm();
  const [adding, setAdding] = useState(false);

  const { data: shortlist, isLoading, isError } = useQuery<Shortlist>({
    queryKey: ["scouting", "shortlists", id],
    queryFn: () =>
      api.get<Shortlist>(`/scouting/shortlists/${id}`).then((r) => r.data),
    enabled: !!id,
  });

  const removeMutation = useMutation({
    mutationFn: (playerId: string) =>
      api
        .delete(`/scouting/shortlists/${id}/items/${playerId}`)
        .then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["scouting", "shortlists", id],
      });
    },
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner size="lg" />
      </div>
    );
  }

  if (isError || !shortlist) {
    return (
      <div className="rounded-xl bg-red-500/10 px-5 py-4 text-sm text-red-400 ring-1 ring-red-500/30">
        Shortlist not found.{" "}
        <button onClick={() => navigate(-1)} className="underline">
          Go back
        </button>
      </div>
    );
  }

  return (
    <div>
      <button
        onClick={() => navigate("/scouting/shortlists")}
        className="mb-6 flex items-center gap-1.5 text-sm text-slate-400 hover:text-white transition-colors"
      >
        ← Back to shortlists
      </button>

      <PageHeader
        title={shortlist.name}
        subtitle={shortlist.description ?? `${shortlist.items.length} players`}
        actions={
          !adding && (
            <Button variant="primary" onClick={() => setAdding(true)}>
              + Add player
            </Button>
          )
        }
      />

      {adding && id && (
        <AddPlayerForm shortlistId={id} onDone={() => setAdding(false)} />
      )}

      {shortlist.items.length === 0 && !adding && (
        <EmptyState
          title="No players yet"
          body="Add players to start building your shortlist."
        />
      )}

      {shortlist.items.length > 0 && (
        <div className="overflow-x-auto rounded-xl ring-1 ring-white/[0.08]">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b border-white/[0.08]">
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-400">
                  Player
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-400">
                  Position
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-400">
                  Status
                </th>
                <th className="px-4 py-3 text-center text-xs font-semibold uppercase tracking-wider text-slate-400">
                  Priority
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-400">
                  Notes
                </th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.04]">
              {shortlist.items
                .slice()
                .sort((a, b) => a.priority - b.priority)
                .map((item) => (
                  <tr
                    key={item.id}
                    className="bg-slate-900 hover:bg-slate-800/60 transition-colors"
                  >
                    <td className="px-4 py-3">
                      <button
                        onClick={() =>
                          navigate(`/players/market/${item.player_id}`)
                        }
                        className="font-medium text-white hover:text-emerald-400 transition-colors"
                      >
                        {item.player?.name ?? "Unknown"}
                      </button>
                    </td>
                    <td className="px-4 py-3">
                      {item.player?.position ? (
                        <Badge
                          variant={positionVariant(
                            item.player.position as PlayerPosition
                          )}
                        >
                          {item.player.position}
                        </Badge>
                      ) : (
                        <span className="text-slate-500">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-400">
                      {item.player
                        ? item.player.team_name
                          ? "Contracted"
                          : item.player.status === "FREE_AGENT"
                          ? "Free Agent"
                          : item.player.status === "CONTRACTED"
                          ? "Contracted"
                          : (item.player.status ?? "—")
                        : "—"}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span
                        className={`inline-flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold ${
                          item.priority === 1
                            ? "bg-emerald-500/20 text-emerald-400"
                            : item.priority === 2
                            ? "bg-sky-500/20 text-sky-400"
                            : "bg-slate-700 text-slate-400"
                        }`}
                      >
                        {item.priority}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-400 max-w-[200px] truncate">
                      {item.notes ?? "—"}
                    </td>
                    <td
                      className="px-4 py-3 text-right"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <button
                        onClick={async () => {
                          if (
                            await confirm({
                              message: `Remove ${item.player?.name ?? "player"} from this shortlist?`,
                              confirmLabel: "Remove",
                              variant: "danger",
                            })
                          ) {
                            removeMutation.mutate(item.player_id);
                          }
                        }}
                        className="text-xs text-slate-500 hover:text-red-400 transition-colors"
                      >
                        Remove
                      </button>
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
