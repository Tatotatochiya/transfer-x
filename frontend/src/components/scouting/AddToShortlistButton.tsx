import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { ShortlistSummary } from "../../types/api";
import { useAuthStore } from "../../store/auth";
import { useClubCapabilities } from "../../hooks/useClubCapabilities";

interface Props {
  playerId: string;
  /** compact = small icon only; default = icon + label */
  size?: "compact" | "default";
}

export default function AddToShortlistButton({ playerId, size = "default" }: Props) {
  const { accessToken } = useAuthStore();
  const { membership, can } = useClubCapabilities();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [added, setAdded] = useState<string | null>(null); // shortlist id just added to
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

  const { data: shortlists, isLoading } = useQuery<ShortlistSummary[]>({
    queryKey: ["scouting", "shortlists"],
    queryFn: () => api.get<ShortlistSummary[]>("/scouting/shortlists").then((r) => r.data),
    enabled: !!accessToken && open,
    staleTime: 30_000,
  });

  const addMutation = useMutation({
    mutationFn: (shortlistId: string) =>
      api.post(`/scouting/shortlists/${shortlistId}/items`, { player_id: playerId, priority: 3 }),
    onSuccess: (_, shortlistId) => {
      setAdded(shortlistId);
      qc.invalidateQueries({ queryKey: ["scouting", "shortlists"] });
      setTimeout(() => {
        setOpen(false);
        setAdded(null);
      }, 800);
    },
  });

  // TRA-151: shortlisting is a club scouting write — hidden for read-only
  // staff and for non-club identities (agents/players have no shortlists).
  if (!accessToken || !membership || !can("SCOUTING_WRITE")) return null;

  const isCompact = size === "compact";

  return (
    <div ref={ref} className="relative" onClick={(e) => e.stopPropagation()}>
      <button
        onClick={() => setOpen((o) => !o)}
        title="Add to shortlist"
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
        <div className="absolute right-0 top-full z-50 mt-1.5 w-52 rounded-xl bg-surface py-1.5 shadow-xl ring-1 ring-border">
          <p className="px-3 pb-1.5 pt-1 text-[11px] font-semibold uppercase tracking-wider text-text-muted">
            Add to shortlist
          </p>

          {isLoading && (
            <p className="px-3 py-2 text-xs text-text-muted">Loading…</p>
          )}

          {!isLoading && shortlists?.length === 0 && (
            <div className="px-3 py-2">
              <p className="text-xs text-text-muted">No shortlists yet.</p>
              <button
                onClick={() => { setOpen(false); navigate("/scouting/shortlists"); }}
                className="mt-1 text-xs text-accent hover:underline"
              >
                Create one →
              </button>
            </div>
          )}

          {shortlists && shortlists.length > 0 && (
            <div className="max-h-48 overflow-y-auto">
              {shortlists.map((sl) => {
                const justAdded = added === sl.id;
                return (
                  <button
                    key={sl.id}
                    onClick={() => addMutation.mutate(sl.id)}
                    disabled={addMutation.isPending}
                    className="flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-surface-inset transition-colors disabled:opacity-50"
                  >
                    <span className={justAdded ? "text-success-text" : "text-text-secondary"}>{sl.name}</span>
                    <span className="text-xs text-text-muted">{sl.item_count}</span>
                    {justAdded && (
                      <svg className="ml-1 h-3.5 w-3.5 text-success-text" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                      </svg>
                    )}
                  </button>
                );
              })}
            </div>
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
