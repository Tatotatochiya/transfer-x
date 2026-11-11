/**
 * "✦ Picks for your squad gaps" (browse-players-focus D7): one row in the
 * results that opens the recommendations. No count until they've loaded.
 */
export default function RecommendationsRow({ clubName, onOpen, expanded, variant = "row" }: {
  clubName?: string | null;
  onOpen: () => void;
  /** From 1024px it expands the panel in place. */
  expanded?: boolean;
  /** "row" in the results; "link" in the chip row on laptops. */
  variant?: "row" | "link";
}) {
  if (variant === "link") {
    return (
      <button
        type="button"
        onClick={onOpen}
        aria-expanded={expanded}
        className="inline-flex h-9 items-center gap-1 whitespace-nowrap rounded-lg px-2 text-body font-semibold text-ai-text hover:brightness-95"
      >
        <span aria-hidden>✦</span> Picks for your squad gaps <span aria-hidden>{expanded ? "⌃" : "›"}</span>
      </button>
    );
  }
  return (
    <button
      type="button"
      onClick={onOpen}
      aria-haspopup="dialog"
      className="flex min-h-[60px] w-full items-center gap-3 bg-ai-bg px-3.5 py-2 text-left ring-1 ring-inset ring-ai-ring hover:brightness-95"
    >
      <span className="min-w-0 flex-1">
        <span className="block text-body font-semibold text-ai-text"><span aria-hidden>✦</span> Picks for your squad gaps</span>
        {clubName && <span className="block truncate text-small text-text-muted">Recommended for {clubName}</span>}
      </span>
      <span aria-hidden className="text-section text-ai-text">›</span>
    </button>
  );
}
