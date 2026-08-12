import { useState } from "react";
import { Link } from "react-router-dom";

import { useNLPlayerSearch } from "../../hooks/useAI";
import { positionVariant } from "../../lib/badges";
import type { NLParsedFilters, NLPlayerSearchResult } from "../../types/api";
import type { PlayerPosition } from "../../types/enums";
import Badge from "../ui/Badge";
import Spinner from "../ui/Spinner";

function FormPip({ score }: { score: number | null }) {
  if (score == null) return <span className="text-xs text-text-muted">—</span>;
  const colour =
    score >= 75 ? "text-success-text" : score >= 60 ? "text-success-text-alt" : score >= 40 ? "text-warning-text" : "text-danger-text";
  return <span className={`text-xs font-bold tabular-nums ${colour}`}>{score.toFixed(1)}</span>;
}

function FilterChips({ filters }: { filters: NLParsedFilters }) {
  const chips: string[] = [];
  if (filters.position) chips.push(filters.position);
  if (filters.min_age != null && filters.max_age != null)
    chips.push(`age ${filters.min_age}–${filters.max_age}`);
  else if (filters.min_age != null) chips.push(`age ≥${filters.min_age}`);
  else if (filters.max_age != null) chips.push(`age ≤${filters.max_age}`);
  if (filters.min_height_cm != null) chips.push(`≥${filters.min_height_cm}cm`);
  if (filters.min_form_score != null) chips.push(`form ≥${filters.min_form_score}`);
  if (filters.nationalities?.length) chips.push(filters.nationalities.join(" / "));
  if (filters.open_to_offers) chips.push("open to offers");

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span className="text-xs text-text-muted italic">"{filters.interpreted_as}"</span>
      {chips.map((c) => (
        <span
          key={c}
          className="rounded-md bg-role-agent-text/10 px-2 py-0.5 text-xs font-medium text-role-agent-text ring-1 ring-role-agent-text/20"
        >
          {c}
        </span>
      ))}
    </div>
  );
}

function PlayerRow({ player }: { player: NLPlayerSearchResult }) {
  return (
    <li>
      <Link
        to={`/market/players/${player.player_id}`}
        className="flex items-center gap-3 px-4 py-2.5 hover:bg-surface-inset transition-colors"
      >
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-text truncate">{player.name}</span>
            {player.position && (
              <Badge variant={positionVariant(player.position as PlayerPosition)}>
                {player.position}
              </Badge>
            )}
            {player.open_to_offers && (
              <Badge variant="success">open</Badge>
            )}
          </div>
          <p className="text-xs text-text-muted truncate">
            {[player.current_club, player.nationality, player.age ? `${player.age}y` : null]
              .filter(Boolean)
              .join(" · ")}
          </p>
        </div>
        <FormPip score={player.form_score} />
      </Link>
    </li>
  );
}

export function NLPlayerSearch() {
  const [query, setQuery] = useState("");
  const { mutate, data, isPending, error, reset } = useNLPlayerSearch();

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) return;
    mutate(trimmed);
  }

  return (
    <div className="mb-4 rounded-xl bg-surface ring-1 ring-role-agent-text/20">
      <div className="px-4 pt-3 pb-2">
        <p className="text-sm font-semibold text-text">✦ AI Player Search</p>
        <p className="text-xs text-text-muted">Describe what you're looking for in plain English</p>
      </div>

      <form onSubmit={handleSubmit} className="flex gap-2 px-4 pb-3">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder='e.g. "young left-back with good form" or "experienced goalkeeper"'
          className="min-w-0 flex-1 rounded-lg bg-surface px-3 py-2 text-sm text-text placeholder-text-muted ring-1 ring-input-border focus:outline-none focus:ring-role-agent-text/50"
        />
        <button
          type="submit"
          disabled={!query.trim() || isPending}
          className="shrink-0 rounded-lg bg-role-agent-text/15 px-4 py-2 text-xs font-semibold text-role-agent-text ring-1 ring-role-agent-text/30 hover:bg-role-agent-text/25 disabled:opacity-40 transition-colors"
        >
          {isPending ? <Spinner size="sm" /> : "Search"}
        </button>
        {(data || error) && (
          <button
            type="button"
            onClick={() => { reset(); setQuery(""); }}
            className="shrink-0 text-xs text-text-muted hover:text-text-secondary transition-colors"
          >
            Clear
          </button>
        )}
      </form>

      {isPending && (
        <div className="flex items-center gap-2 border-t border-rule px-4 py-3 text-xs text-text-muted">
          <Spinner size="sm" />
          Parsing query and searching…
        </div>
      )}

      {error && !isPending && (
        <p className="border-t border-rule px-4 py-3 text-xs text-danger-text">
          {(error as { response?: { data?: { detail?: string } } }).response?.data?.detail ??
            "Search failed. Please try again."}
        </p>
      )}

      {data && !isPending && (
        <div className="border-t border-rule">
          <div className="px-4 py-2">
            <FilterChips filters={data.filters} />
          </div>

          {data.players.length === 0 ? (
            <p className="px-4 py-3 text-xs text-text-muted">No players matched these filters.</p>
          ) : (
            <>
              <ul className="divide-y divide-rule-faint">
                {data.players.map((p) => (
                  <PlayerRow key={p.player_id} player={p} />
                ))}
              </ul>
              <p className="px-4 py-2 text-xs text-text-muted">
                {data.total} player{data.total !== 1 ? "s" : ""} found
              </p>
            </>
          )}
        </div>
      )}
    </div>
  );
}
