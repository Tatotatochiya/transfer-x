import { useId, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import api from "../../lib/api";
import type { ClubPublic, Paginated } from "../../types/api";

export interface Exclusions {
  clubs: { id: string; name: string }[];
  leagues: string[];
}

export const NO_EXCLUSIONS: Exclusions = { clubs: [], leagues: [] };

const INPUT_CLASS =
  "w-full rounded-lg bg-surface px-3 py-2.5 text-small text-text placeholder-text-muted ring-1 ring-input-border focus:outline-none focus:ring-accent transition-colors";

function Chip({ label, onRemove }: { label: string; onRemove: () => void }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-surface-inset py-1 pl-3 pr-1 text-small text-text ring-1 ring-border">
      {label}
      <button
        type="button"
        onClick={onRemove}
        aria-label={`Remove ${label}`}
        className="rounded-full px-1.5 text-text-muted hover:text-text"
      >
        ×
      </button>
    </span>
  );
}

/**
 * Clubs and domestic leagues a listing shuts out. While he is listed they
 * can't make an offer for him, and they aren't told why. Closed until asked
 * for: most listings exclude no one.
 */
export default function ExclusionsField({
  value, onChange, ownClubId,
}: {
  value: Exclusions;
  onChange: (v: Exclusions) => void;
  ownClubId?: string;
}) {
  const ids = useId();
  const count = value.clubs.length + value.leagues.length;
  const [open, setOpen] = useState(count > 0);
  const [search, setSearch] = useState("");
  const term = search.trim();

  const { data: found } = useQuery<Paginated<ClubPublic>>({
    queryKey: ["clubs", "search", term],
    queryFn: () => api.get<Paginated<ClubPublic>>("/clubs", { params: { search: term, page_size: 8 } }).then((r) => r.data),
    enabled: open && term.length >= 2,
    staleTime: 60_000,
  });
  const { data: leagues = [] } = useQuery<string[]>({
    queryKey: ["clubs", "leagues"],
    queryFn: () => api.get<string[]>("/clubs/leagues").then((r) => r.data),
    enabled: open,
    staleTime: 300_000,
  });

  const chosen = new Set(value.clubs.map((c) => c.id));
  const matches = (found?.items ?? []).filter((c) => c.id !== ownClubId && !chosen.has(c.id));
  const leagueOptions = leagues.filter((l) => !value.leagues.includes(l));

  if (!open) {
    return (
      <button type="button" onClick={() => setOpen(true)} className="self-start text-small font-semibold text-accent hover:underline">
        Keep him from certain clubs or leagues
      </button>
    );
  }

  return (
    <fieldset className="rounded-xl bg-surface p-3.5 ring-1 ring-border">
      <legend className="px-1 text-body font-semibold text-text-secondary">
        Not available to <span className="font-normal text-text-muted">(optional)</span>
      </legend>
      <p className="mb-3 text-small text-text-muted">
        While he's listed, these clubs can't make an offer for him. They aren't told why, and only your club sees this list.
      </p>

      <label htmlFor={`${ids}-club`} className="mb-1.5 block text-small font-semibold text-text-secondary">Clubs</label>
      <input
        id={`${ids}-club`}
        type="search"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Search for a club"
        autoComplete="off"
        className={INPUT_CLASS}
      />
      {term.length >= 2 && (
        <ul aria-label="Matching clubs" className="mt-1 max-h-48 overflow-y-auto rounded-lg ring-1 ring-border">
          {matches.length === 0 && <li className="px-3 py-2 text-small text-text-muted">No other club matches.</li>}
          {matches.map((c) => (
            <li key={c.id}>
              <button
                type="button"
                onClick={() => { onChange({ ...value, clubs: [...value.clubs, { id: c.id, name: c.name }] }); setSearch(""); }}
                className="flex w-full items-baseline justify-between gap-3 px-3 py-2 text-left text-small text-text hover:bg-surface-inset"
              >
                <span>{c.name}</span>
                {c.league_name && <span className="text-caption text-text-muted">{c.league_name}</span>}
              </button>
            </li>
          ))}
        </ul>
      )}
      {value.clubs.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {value.clubs.map((c) => (
            <Chip key={c.id} label={c.name} onRemove={() => onChange({ ...value, clubs: value.clubs.filter((x) => x.id !== c.id) })} />
          ))}
        </div>
      )}

      <label htmlFor={`${ids}-league`} className="mb-1.5 mt-4 block text-small font-semibold text-text-secondary">Leagues</label>
      <select
        id={`${ids}-league`}
        value=""
        onChange={(e) => e.target.value && onChange({ ...value, leagues: [...value.leagues, e.target.value] })}
        className={INPUT_CLASS}
      >
        <option value="">{leagueOptions.length ? "Add a league…" : "No more leagues"}</option>
        {leagueOptions.map((l) => <option key={l} value={l}>{l}</option>)}
      </select>
      {value.leagues.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {value.leagues.map((l) => (
            <Chip key={l} label={l} onRemove={() => onChange({ ...value, leagues: value.leagues.filter((x) => x !== l) })} />
          ))}
        </div>
      )}
    </fieldset>
  );
}
