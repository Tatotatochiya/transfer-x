import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import { getApiError } from "../../lib/utils";
import type { ShortlistSummary } from "../../types/api";
import { useAuthStore } from "../../store/auth";
import { useClubCapabilities } from "../../hooks/useClubCapabilities";

interface Props {
  playerId: string;
  /** compact = small icon only; default = icon + label */
  size?: "compact" | "default";
}

/**
 * Add a player to one of the club's shortlists, or to a new one, without
 * leaving the page. Lists he is already on are ticked and can't be picked
 * again; a new list is created and he is added to it in one step.
 */
export default function AddToShortlistButton({ playerId, size = "default" }: Props) {
  const { accessToken } = useAuthStore();
  const { membership, can } = useClubCapabilities();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [added, setAdded] = useState<{ id: string; name: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  // A list created whose add then failed: retry the add, never re-create it.
  const [orphan, setOrphan] = useState<{ id: string; name: string } | null>(null);
  const ref = useRef<HTMLDivElement>(null);
  const qc = useQueryClient();

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  // Fresh state every time the menu opens.
  useEffect(() => {
    if (open) { setError(null); setAdded(null); setNewName(""); setOrphan(null); setCreating(false); }
  }, [open]);

  const { data: shortlists, isLoading } = useQuery<ShortlistSummary[]>({
    queryKey: ["scouting", "shortlists", { player: playerId }],
    queryFn: () =>
      api.get<ShortlistSummary[]>("/scouting/shortlists", { params: { player_id: playerId } }).then((r) => r.data),
    enabled: !!accessToken && open,
    staleTime: 30_000,
  });

  // With no shortlists yet, go straight to naming the first one.
  useEffect(() => {
    if (open && shortlists && shortlists.length === 0) setCreating(true);
  }, [open, shortlists]);

  function done(list: { id: string; name: string }) {
    setAdded(list);
    setError(null);
    setCreating(false);
    setOrphan(null);
    qc.invalidateQueries({ queryKey: ["scouting", "shortlists"] });
    setTimeout(() => { setOpen(false); setAdded(null); }, 1200);
  }

  const addTo = (id: string) => api.post(`/scouting/shortlists/${id}/items`, { player_id: playerId, priority: 3 });

  const addMutation = useMutation({
    mutationFn: async (list: { id: string; name: string }) => { await addTo(list.id); return list; },
    onSuccess: done,
    onError: (err: unknown) => setError(getApiError(err, "Couldn't add him to that shortlist.")),
  });

  const createMutation = useMutation({
    mutationFn: async (name: string) => {
      const { data } = await api.post<{ id: string; name: string }>("/scouting/shortlists", { name });
      const list = { id: data.id, name: data.name };
      try {
        await addTo(list.id);
      } catch (err) {
        setOrphan(list);
        qc.invalidateQueries({ queryKey: ["scouting", "shortlists"] });
        throw new Error(`Created "${list.name}", but couldn't add him: ${getApiError(err, "please try again.")}`);
      }
      return list;
    },
    onSuccess: done,
    onError: (err: unknown) =>
      setError(err instanceof Error && err.message.startsWith("Created") ? err.message : getApiError(err, "Couldn't create the shortlist.")),
  });

  // TRA-151: shortlisting is a club scouting write — hidden for read-only
  // staff and for non-club identities (agents/players have no shortlists).
  if (!accessToken || !membership || !can("SCOUTING_WRITE")) return null;

  const isCompact = size === "compact";
  const busy = addMutation.isPending || createMutation.isPending;

  function submitNew() {
    const name = newName.trim();
    if (!name) { setError("Give the shortlist a name."); return; }
    setError(null);
    createMutation.mutate(name);
  }

  return (
    <div
      ref={ref}
      className="relative"
      onClick={(e) => e.stopPropagation()}
      onKeyDown={(e) => {
        if (e.key !== "Escape") return;
        e.stopPropagation();
        if (creating && shortlists && shortlists.length > 0) { setCreating(false); setError(null); } else setOpen(false);
      }}
    >
      <button
        onClick={() => setOpen((o) => !o)}
        title="Add to shortlist"
        aria-haspopup="menu"
        aria-expanded={open}
        className={`flex items-center gap-1.5 rounded-lg ring-1 transition-colors ${
          isCompact
            ? "p-1.5 bg-surface-inset ring-input-border hover:bg-border hover:ring-input-border text-text-muted hover:text-text"
            : "px-3 py-2 bg-surface-inset ring-input-border hover:bg-border text-sm font-medium text-text-secondary hover:text-text"
        }`}
      >
        {/* Bookmark icon */}
        <svg className={isCompact ? "h-3.5 w-3.5" : "h-4 w-4"} fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
        </svg>
        {!isCompact && <span>Shortlist</span>}
      </button>

      {open && (
        <div className="absolute right-0 top-full z-50 mt-1.5 w-64 rounded-xl bg-surface py-1.5 shadow-xl ring-1 ring-border" role="menu">
          <p className="px-3 pb-1.5 pt-1 text-[11px] font-semibold uppercase tracking-wider text-text-muted">
            Add to shortlist
          </p>

          {isLoading && <p className="px-3 py-2 text-xs text-text-muted">Loading…</p>}

          {added ? (
            <p className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-success-text" role="status">
              <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
              Added to {added.name}
            </p>
          ) : (
            <>
              {shortlists && shortlists.length > 0 && (
                <div className="max-h-48 overflow-y-auto">
                  {shortlists.map((sl) => {
                    const onIt = sl.contains_player === true;
                    return (
                      <button
                        key={sl.id}
                        role="menuitem"
                        onClick={() => { setError(null); addMutation.mutate({ id: sl.id, name: sl.name }); }}
                        disabled={busy || onIt}
                        title={onIt ? "He's already on this shortlist" : undefined}
                        className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm transition-colors hover:bg-surface-inset disabled:cursor-default disabled:hover:bg-transparent"
                      >
                        <span className={`flex h-4 w-4 shrink-0 items-center justify-center ${onIt ? "text-success-text" : "text-transparent"}`} aria-hidden="true">
                          <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                          </svg>
                        </span>
                        <span className={`min-w-0 flex-1 truncate ${onIt ? "text-text-muted" : "text-text-secondary"}`}>{sl.name}</span>
                        <span className="shrink-0 text-xs text-text-muted">{onIt ? "Already on it" : sl.item_count}</span>
                      </button>
                    );
                  })}
                </div>
              )}

              {/* New shortlist, created and added to in one step. */}
              {shortlists && (
                creating ? (
                  <form
                    className="space-y-2 border-t border-rule px-3 pb-1.5 pt-2"
                    onSubmit={(e) => { e.preventDefault(); if (orphan) addMutation.mutate(orphan); else submitNew(); }}
                  >
                    <label htmlFor={`new-shortlist-${playerId}`} className="block text-xs font-semibold text-text-secondary">
                      {shortlists.length === 0 ? "No shortlists yet. Name your first:" : "New shortlist"}
                    </label>
                    <input
                      id={`new-shortlist-${playerId}`}
                      autoFocus
                      value={newName}
                      onChange={(e) => { setNewName(e.target.value); setError(null); }}
                      maxLength={200}
                      disabled={busy || !!orphan}
                      placeholder="e.g. Left-backs for the summer"
                      className="w-full rounded-lg bg-surface px-2.5 py-1.5 text-sm text-text placeholder-text-muted ring-1 ring-input-border focus:outline-none focus:ring-accent disabled:opacity-60"
                    />
                    <div className="flex items-center gap-2">
                      <button
                        type="submit"
                        disabled={busy || (!orphan && !newName.trim())}
                        className="rounded-lg bg-accent px-3 py-1.5 text-xs font-semibold text-white hover:bg-accent-hover disabled:opacity-50"
                      >
                        {busy ? "Adding…" : orphan ? "Try adding again" : "Create and add"}
                      </button>
                      {shortlists.length > 0 && !orphan && (
                        <button
                          type="button"
                          onClick={() => { setCreating(false); setError(null); }}
                          className="text-xs text-text-muted hover:text-text"
                        >
                          Cancel
                        </button>
                      )}
                    </div>
                  </form>
                ) : (
                  <button
                    role="menuitem"
                    onClick={() => { setCreating(true); setError(null); }}
                    className="flex w-full items-center gap-2 border-t border-rule px-3 py-2 text-left text-sm font-medium text-accent hover:bg-surface-inset"
                  >
                    <span className="flex h-4 w-4 items-center justify-center text-base leading-none" aria-hidden="true">+</span>
                    New shortlist
                  </button>
                )
              )}

              {error && <p className="px-3 py-1.5 text-xs text-danger-text" role="alert">{error}</p>}
            </>
          )}

          <div className="mt-1 border-t border-rule px-3 pt-1.5 pb-1">
            <button
              onClick={() => { setOpen(false); navigate("/scouting/shortlists"); }}
              className="text-xs text-text-muted hover:text-text-secondary transition-colors"
            >
              Manage shortlists →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
