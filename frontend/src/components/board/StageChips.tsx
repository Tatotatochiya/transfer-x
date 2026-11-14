/**
 * Stage filter chips (README_TRANSFERS §4.2): "All" and each stage with at
 * least one transfer, in one row that scrolls sideways if it must.
 */
export default function StageChips({ total, stages, selected, onSelect }: {
  total: number;
  stages: { key: string; label: string; count: number }[];
  /** The stage key, or null for All. */
  selected: string | null;
  onSelect: (key: string | null) => void;
}) {
  const chips = [{ key: null as string | null, label: "All", count: total }, ...stages];
  return (
    <div role="radiogroup" aria-label="Stage"
      className="-mx-4 flex gap-2 overflow-x-auto px-4 [scrollbar-width:none] sm:mx-0 sm:px-0 [&::-webkit-scrollbar]:hidden">
      {chips.map((c) => {
        const on = c.key === selected;
        return (
          <button
            key={c.key ?? "all"}
            type="button"
            role="radio"
            aria-checked={on}
            onClick={() => onSelect(c.key)}
            className={`inline-flex min-h-9 shrink-0 items-center gap-1.5 rounded-full px-3 text-small font-semibold ring-1 ${
              on ? "bg-accent-bg text-text ring-accent-ring" : "bg-surface text-text-secondary ring-input-border"
            }`}
          >
            {c.label}
            <span className={`tabular-nums ${on ? "text-accent" : "text-text-muted"}`}>{c.count}</span>
          </button>
        );
      })}
    </div>
  );
}
