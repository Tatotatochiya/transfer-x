import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { Player, Shortlist } from "../../types/api";
import { ShortlistReviewPanel } from "../../components/ai/ShortlistReviewPanel";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import EmptyState from "../../components/ui/EmptyState";
import PageHeader from "../../components/ui/PageHeader";
import ResponsiveTable, { type ResponsiveColumn } from "../../components/ui/ResponsiveTable";
import Spinner from "../../components/ui/Spinner";
import { positionVariant } from "../../lib/badges";
import { formatCurrency, getApiError } from "../../lib/utils";
import { useConfirm } from "../../context/ConfirmContext";
import type { PlayerPosition } from "../../types/enums";
import type { ShortlistItem } from "../../types/api";

function useDebounce<T>(value: T, ms: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return debounced;
}

const positionColour: Record<string, string> = {
  GK:  "bg-pos-gk-bg text-pos-gk-text",
  DEF: "bg-pos-def-bg text-pos-def-text",
  MID: "bg-pos-mid-bg text-pos-mid-text",
  FWD: "bg-pos-fwd-bg text-pos-fwd-text",
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
    <div className="rounded-xl bg-surface-inset px-4 py-4 ring-1 ring-border mb-6">
      <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-text-muted">Add player</p>
      <form onSubmit={handleSubmit} className="space-y-3">
        {/* Player search */}
        <div className="relative">
          <label className="mb-1 block text-xs text-text-muted">Player</label>
          <div className="relative">
            <svg className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-text-muted" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
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
              className="w-full rounded-lg bg-surface pl-8 pr-3 py-2 text-sm text-text placeholder-text-muted ring-1 ring-input-border focus:outline-none focus:ring-accent transition-colors"
            />
            {isFetching && (
              <svg className="absolute right-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 animate-spin text-text-muted" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
            )}
          </div>

          {/* Dropdown */}
          {dropdownOpen && !selectedId && players.length > 0 && (
            <div className="absolute z-20 mt-1 w-full rounded-lg bg-surface ring-1 ring-border shadow-xl overflow-hidden">
              {players.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  onMouseDown={() => selectPlayer(p)}
                  className="flex w-full items-center gap-3 px-3 py-2.5 hover:bg-surface-inset transition-colors text-left"
                >
                  {p.photo_url ? (
                    <img src={p.photo_url} alt={p.name} className="h-7 w-7 shrink-0 rounded-full object-cover ring-1 ring-border" />
                  ) : (
                    <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-surface-inset text-xs font-bold text-text-muted">
                      {p.name[0]?.toUpperCase()}
                    </div>
                  )}
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-text">{p.name}</p>
                    <p className="text-xs text-text-muted truncate">
                      {p.current_club?.name ?? p.team_name ?? "Free Agent"}
                    </p>
                  </div>
                  {p.position && (
                    <span className={`shrink-0 rounded px-1.5 py-0.5 text-[11px] font-bold ${positionColour[p.position] ?? "bg-surface-inset text-text-muted"}`}>
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
            <label className="mb-1 block text-xs text-text-muted">Priority (1–5)</label>
            <input
              type="number"
              min="1"
              max="5"
              value={priority}
              onChange={(e) => setPriority(e.target.value)}
              className="w-full rounded-lg bg-surface px-3 py-2 text-sm text-text ring-1 ring-input-border focus:outline-none focus:ring-accent transition-colors"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-text-muted">Notes (optional)</label>
            <input
              type="text"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Any notes…"
              className="w-full rounded-lg bg-surface px-3 py-2 text-sm text-text placeholder-text-muted ring-1 ring-input-border focus:outline-none focus:ring-accent transition-colors"
            />
          </div>
        </div>

        {error && <p className="text-xs text-danger-text">{error}</p>}
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
      <div className="rounded-xl bg-danger-bg px-5 py-4 text-sm text-danger-text ring-1 ring-danger-border">
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
        className="mb-6 flex items-center gap-1.5 text-sm text-text-muted hover:text-text transition-colors"
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

      {!adding && shortlist.items.length > 0 && id && (
        <ShortlistReviewPanel shortlistId={id} itemCount={shortlist.items.length} />
      )}

      {shortlist.items.length === 0 && !adding && (
        <EmptyState
          title="No players yet"
          body="Add players to start building your shortlist."
        />
      )}

      {shortlist.items.length > 0 && (
        <ShortlistItemsTable
          items={shortlist.items.slice().sort((a, b) => a.priority - b.priority)}
          onOpenPlayer={(playerId) => navigate(`/players/market/${playerId}`)}
          onRemove={async (item) => {
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
        />
      )}
    </div>
  );
}

// ── Items table ───────────────────────────────────────────────────────────────

const PRIORITY_DOT_CLS: Record<number, string> = {
  1: "bg-success/15 text-success-text",
  2: "bg-accent/15 text-accent",
};

function statusLabel(item: ShortlistItem): string {
  if (!item.player) return "—";
  if (item.player.team_name) return "Contracted";
  if (item.player.status === "FREE_AGENT") return "Free Agent";
  if (item.player.status === "CONTRACTED") return "Contracted";
  return item.player.status ?? "—";
}

function ShortlistItemsTable({
  items, onOpenPlayer, onRemove,
}: {
  items: ShortlistItem[];
  onOpenPlayer: (playerId: string) => void;
  onRemove: (item: ShortlistItem) => void;
}) {
  const columns: ResponsiveColumn<ShortlistItem>[] = [
    { key: "player", header: "Player", priority: 1, render: (item) => (
      <button
        onClick={() => onOpenPlayer(item.player_id)}
        className="font-medium text-text hover:text-accent transition-colors"
      >
        {item.player?.name ?? "Unknown"}
      </button>
    ) },
    { key: "position", header: "Position", priority: 3, render: (item) =>
      item.player?.position ? (
        <Badge variant={positionVariant(item.player.position as PlayerPosition)}>
          {item.player.position}
        </Badge>
      ) : (
        <span className="text-text-muted">—</span>
      ) },
    { key: "status", header: "Status", priority: 4, render: (item) => (
      <span className="text-xs text-text-muted">{statusLabel(item)}</span>
    ) },
    { key: "value", header: "Market Value", priority: 2, className: "text-right", render: (item) => (
      <span className="text-sm font-semibold text-text-secondary tabular-nums">
        {item.player?.market_value != null
          ? formatCurrency(item.player.market_value)
          : <span className="text-text-muted font-normal">—</span>}
      </span>
    ) },
    { key: "priority", header: "Priority", priority: 5, className: "text-center", render: (item) => (
      <span className={`inline-flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold ${PRIORITY_DOT_CLS[item.priority] ?? "bg-text-muted/15 text-text-muted"}`}>
        {item.priority}
      </span>
    ) },
    { key: "notes", header: "Notes", priority: 6, render: (item) => (
      <span className="text-xs text-text-muted max-w-[200px] truncate block">{item.notes ?? "—"}</span>
    ) },
    { key: "actions", header: "", className: "text-right", render: (item) => (
      <button
        onClick={(e) => { e.stopPropagation(); onRemove(item); }}
        className="text-xs text-text-muted hover:text-danger-text transition-colors"
      >
        Remove
      </button>
    ) },
  ];

  return (
    <ResponsiveTable
      columns={columns}
      rows={items}
      rowKey={(item) => item.id}
      renderCard={(item) => (
        <div className="px-4 py-3">
          <div className="flex items-center justify-between gap-3">
            <button
              onClick={() => onOpenPlayer(item.player_id)}
              className="text-sm font-semibold text-text hover:text-accent transition-colors"
            >
              {item.player?.name ?? "Unknown"}
            </button>
            <span className={`inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold ${PRIORITY_DOT_CLS[item.priority] ?? "bg-text-muted/15 text-text-muted"}`}>
              {item.priority}
            </span>
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-text-muted">
            {item.player?.position && (
              <Badge variant={positionVariant(item.player.position as PlayerPosition)}>
                {item.player.position}
              </Badge>
            )}
            <span>{statusLabel(item)}</span>
            {item.player?.market_value != null && <span>{formatCurrency(item.player.market_value)}</span>}
          </div>
          {item.notes && <p className="mt-1 text-xs text-text-muted truncate">{item.notes}</p>}
          <button
            onClick={() => onRemove(item)}
            className="mt-2 text-xs text-text-muted hover:text-danger-text transition-colors"
          >
            Remove
          </button>
        </div>
      )}
    />
  );
}
