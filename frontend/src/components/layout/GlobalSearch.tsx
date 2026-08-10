import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import api from "../../lib/api";
import Modal from "../ui/Modal";
import type { ClubPublic, Player } from "../../types/api";

interface SearchResults {
  players: Player[];
  clubs: ClubPublic[];
}

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

export default function GlobalSearch() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();
  const debouncedQ = useDebounce(query, 280);

  // Ctrl+K / ⌘K to open. Escape-to-close is now Modal's job.
  useEffect(() => {
    function handler(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
    }
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, []);

  // Focus input when opened
  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 50);
    } else {
      setQuery("");
    }
  }, [open]);

  const { data, isFetching } = useQuery<SearchResults>({
    queryKey: ["search", debouncedQ],
    queryFn: () => api.get<SearchResults>("/search", { params: { q: debouncedQ } }).then((r) => r.data),
    enabled: debouncedQ.length >= 2,
    staleTime: 10_000,
  });

  function go(path: string) {
    setOpen(false);
    navigate(path);
  }

  const hasResults = (data?.players.length ?? 0) + (data?.clubs.length ?? 0) > 0;

  return (
    <>
      {/* Trigger button in header */}
      <button
        onClick={() => setOpen(true)}
        className="flex items-center gap-2 rounded-lg bg-surface px-3 py-1.5 text-sm text-text-muted ring-1 ring-input-border hover:ring-accent hover:text-text transition-colors"
      >
        <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-4.35-4.35M17 11A6 6 0 105 11a6 6 0 0012 0z" />
        </svg>
        <span className="hidden sm:inline">Search…</span>
        <kbd className="hidden sm:inline rounded bg-surface-inset px-1.5 py-0.5 text-[10px] font-mono text-text-muted">⌘K</kbd>
      </button>

      <Modal open={open} onClose={() => setOpen(false)} size="xl" className="overflow-hidden">
        {/* Input */}
        <div className="flex items-center gap-3 border-b border-rule px-4 py-3">
          <svg className="h-4 w-4 shrink-0 text-text-muted" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-4.35-4.35M17 11A6 6 0 105 11a6 6 0 0012 0z" />
          </svg>
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search players and clubs…"
            className="flex-1 bg-transparent text-sm text-text placeholder:text-text-muted focus:outline-none"
          />
          {isFetching && (
            <svg className="h-4 w-4 animate-spin text-text-muted" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
          )}
          <kbd className="rounded bg-surface-inset px-1.5 py-0.5 text-[10px] font-mono text-text-muted">Esc</kbd>
        </div>

        {/* Results */}
        <div className="max-h-[400px] overflow-y-auto">
          {debouncedQ.length < 2 && (
            <p className="px-4 py-8 text-center text-sm text-text-muted">Type at least 2 characters to search</p>
          )}

          {debouncedQ.length >= 2 && !isFetching && !hasResults && (
            <p className="px-4 py-8 text-center text-sm text-text-muted">No results for "{debouncedQ}"</p>
          )}

          {/* Players */}
          {(data?.players.length ?? 0) > 0 && (
            <div>
              <p className="px-4 pt-3 pb-1 text-[10px] font-semibold uppercase tracking-wider text-text-muted">Players</p>
              {data!.players.map((p) => (
                <button
                  key={p.id}
                  onClick={() => go(`/players/market/${p.id}`)}
                  className="flex w-full items-center gap-3 px-4 py-2.5 hover:bg-surface-inset transition-colors text-left"
                >
                  {p.photo_url ? (
                    <img src={p.photo_url} alt={p.name} loading="lazy" className="h-8 w-8 shrink-0 rounded-full object-cover ring-1 ring-border" />
                  ) : (
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-surface-inset text-xs font-bold text-text-muted">
                      {p.name[0]?.toUpperCase()}
                    </div>
                  )}
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-text">{p.name}</p>
                    <p className="text-xs text-text-muted truncate">
                      {p.current_club?.name ?? p.world_team?.name ?? p.team_name ?? "Free Agent"}
                    </p>
                  </div>
                  {p.position && (
                    <span className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-bold ${positionColour[p.position] ?? "bg-surface-inset text-text-muted"}`}>
                      {p.position}
                    </span>
                  )}
                </button>
              ))}
            </div>
          )}

          {/* Clubs */}
          {(data?.clubs.length ?? 0) > 0 && (
            <div>
              <p className="px-4 pt-3 pb-1 text-[10px] font-semibold uppercase tracking-wider text-text-muted">Clubs</p>
              {data!.clubs.map((c) => (
                <button
                  key={c.id}
                  onClick={() => go(`/clubs/${c.id}`)}
                  className="flex w-full items-center gap-3 px-4 py-2.5 hover:bg-surface-inset transition-colors text-left"
                >
                  {c.crest_url ? (
                    <img src={c.crest_url} alt={c.name} loading="lazy" className="h-8 w-8 shrink-0 object-contain" />
                  ) : (
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-surface-inset text-sm font-bold text-text-muted">
                      {c.name[0]?.toUpperCase()}
                    </div>
                  )}
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-text">{c.name}</p>
                    <p className="text-xs text-text-muted truncate">
                      {[c.league_name, c.country].filter(Boolean).join(" · ")}
                    </p>
                  </div>
                </button>
              ))}
            </div>
          )}

          <div className="h-2" />
        </div>
      </Modal>
    </>
  );
}
