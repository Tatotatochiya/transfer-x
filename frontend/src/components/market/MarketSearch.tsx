import { useEffect, useId, useRef, useState } from "react";
import Spinner from "../ui/Spinner";

/**
 * Browse Players' one search box (browse-players-focus §5.7). By name, the
 * default, it sets the name filter 300ms after typing stops. "✦ Describe"
 * switches it to the AI player search, which runs on submit.
 */
export default function MarketSearch({
  search,
  onSearch,
  describe,
  onDescribeChange,
  onDescribeSubmit,
  describePending = false,
  canDescribe,
}: {
  search: string;
  onSearch: (text: string) => void;
  describe: boolean;
  onDescribeChange: (on: boolean) => void;
  onDescribeSubmit: (query: string) => void;
  describePending?: boolean;
  /** The AI search needs a signed-in account. */
  canDescribe: boolean;
}) {
  const id = useId();
  const [name, setName] = useState(search);
  const [query, setQuery] = useState("");
  const sent = useRef(search);
  const inputRef = useRef<HTMLInputElement>(null);

  // Follow the filter when something else changes it (a saved view, Clear).
  useEffect(() => {
    if (search !== sent.current) {
      sent.current = search;
      setName(search);
    }
  }, [search]);

  useEffect(() => {
    if (describe || name === sent.current) return;
    const t = setTimeout(() => { sent.current = name; onSearch(name); }, 300);
    return () => clearTimeout(t);
  }, [name, describe, onSearch]);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (describe) {
      const q = query.trim();
      if (q) onDescribeSubmit(q);
    } else if (name !== sent.current) {
      sent.current = name;
      onSearch(name);
    }
  }

  function toggle() {
    onDescribeChange(!describe);
    inputRef.current?.focus();
  }

  return (
    <form role="search" onSubmit={submit} className="min-w-0 flex-1">
      <label htmlFor={id} className="sr-only">Search players</label>
      <div className="flex min-h-12 items-center gap-2 rounded-xl bg-surface pl-3 pr-1.5 ring-1 ring-input-border focus-within:ring-2 focus-within:ring-accent lg:min-h-11">
        <svg aria-hidden className="h-[18px] w-[18px] shrink-0 text-text-muted" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
          <circle cx="11" cy="11" r="7" />
          <path strokeLinecap="round" d="m20 20-3.5-3.5" />
        </svg>
        <input
          ref={inputRef}
          id={id}
          type="search"
          enterKeyHint="search"
          value={describe ? query : name}
          onChange={(e) => (describe ? setQuery(e.target.value) : setName(e.target.value))}
          placeholder={describe ? 'Describe a player, e.g. "young left-back with good form"' : canDescribe ? "Name, or describe a player" : "Search by name"}
          className="min-w-0 flex-1 bg-transparent text-input lg:text-body text-text placeholder-text-muted focus:outline-none [&::-webkit-search-cancel-button]:hidden"
        />
        {describe && describePending && <Spinner size="sm" />}
        {describe && (
          <button
            type="submit"
            disabled={!query.trim() || describePending}
            className="min-h-9 shrink-0 rounded-lg bg-ai-bg px-3 text-body font-semibold text-ai-text disabled:opacity-40"
          >
            Search
          </button>
        )}
        {canDescribe && (
          <button
            type="button"
            aria-pressed={describe}
            onClick={toggle}
            className={`min-h-9 shrink-0 rounded-lg px-2.5 text-body font-semibold transition-colors ${
              describe ? "bg-ai-bg text-ai-text ring-1 ring-ai-ring" : "text-ai-text hover:brightness-95"
            }`}
          >
            ✦ Describe
          </button>
        )}
      </div>
    </form>
  );
}
