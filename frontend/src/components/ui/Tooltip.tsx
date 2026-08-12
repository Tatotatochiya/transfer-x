interface TooltipProps {
  content: string;
  children: React.ReactNode;
  side?: "top" | "bottom";
  className?: string;
}

const SIDE_CLASSES: Record<"top" | "bottom", string> = {
  top: "bottom-full left-1/2 -translate-x-1/2 mb-1.5",
  bottom: "top-full left-1/2 -translate-x-1/2 mt-1.5",
};

/**
 * Hover/focus tooltip. CSS-only (group-hover / group-focus-within), no
 * positioning library — didn't exist anywhere in the app before this.
 * bg-text/text-page inverts against the page in both themes, so it reads as
 * a floating high-contrast label regardless of light or dark mode.
 */
export default function Tooltip({ content, children, side = "top", className = "" }: TooltipProps) {
  return (
    <span className={`group relative inline-flex ${className}`}>
      {children}
      <span
        role="tooltip"
        className={`pointer-events-none absolute z-50 whitespace-nowrap rounded-md bg-text px-2 py-1 text-xs font-medium text-page opacity-0 transition-opacity duration-150 group-hover:opacity-100 group-focus-within:opacity-100 ${SIDE_CLASSES[side]}`}
      >
        {content}
      </span>
    </span>
  );
}
