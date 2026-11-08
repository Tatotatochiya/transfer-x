import { useRef } from "react";

export interface SegmentItem { key: string; label: string }

interface SegmentedControlProps {
  items: SegmentItem[];
  active: string;
  onChange: (key: string) => void;
  size?: "md" | "sm";
  ariaLabel: string;
  /** Prefix for tab and panel ids: tab `${idPrefix}-tab-${key}` controls `${idPrefix}-panel-${key}`. */
  idPrefix: string;
}

/**
 * A row of equal segments with tab semantics (Left/Right move between them).
 * The deal room's sections on phones and tablets, and its rail on desktop.
 */
export default function SegmentedControl({ items, active, onChange, size = "md", ariaLabel, idPrefix }: SegmentedControlProps) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);

  function onKeyDown(e: React.KeyboardEvent, i: number) {
    const step = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
    if (!step) return;
    e.preventDefault();
    const next = (i + step + items.length) % items.length;
    onChange(items[next].key);
    refs.current[next]?.focus();
  }

  const sizing = size === "sm" ? "min-h-9 text-sm" : "min-h-12 text-[15px]";
  return (
    <div role="tablist" aria-label={ariaLabel} className="grid grid-flow-col auto-cols-fr gap-1 rounded-xl bg-border-quiet p-1">
      {items.map((item, i) => {
        const selected = item.key === active;
        return (
          <button
            key={item.key}
            ref={(el) => { refs.current[i] = el; }}
            id={`${idPrefix}-tab-${item.key}`}
            type="button"
            role="tab"
            aria-selected={selected}
            aria-controls={`${idPrefix}-panel-${item.key}`}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(item.key)}
            onKeyDown={(e) => onKeyDown(e, i)}
            className={`${sizing} rounded-[9px] px-2 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-accent ${
              selected
                ? "bg-surface font-semibold text-text shadow-[0_1px_2px_rgba(16,24,40,0.1)]"
                : "font-medium text-text-secondary hover:text-text"
            }`}
          >
            {item.label}
          </button>
        );
      })}
    </div>
  );
}
