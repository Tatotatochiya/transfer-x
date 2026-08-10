export type CardTier = 1 | 2 | 3 | 4;

// The four-tier hierarchy (docs/design_handoff_transferx/README.md). Tier is
// optional — pages not yet migrated to the tier system get the tier-3 (plain
// working-panel) treatment, the closest match to the old single Card look.
const tierClasses: Record<CardTier, string> = {
  1: "bg-surface ring-1 ring-danger-ring shadow-[0_1px_2px_rgba(16,24,40,0.06)]",
  2: "bg-surface ring-1 ring-border",
  3: "bg-surface ring-1 ring-border",
  4: "bg-surface-quiet ring-1 ring-border-quiet",
};

interface CardProps {
  children: React.ReactNode;
  className?: string;
  hover?: boolean;
  noPadding?: boolean;
  tier?: CardTier;
}

export default function Card({ children, className = "", hover = false, noPadding = false, tier = 3 }: CardProps) {
  return (
    <div
      className={`rounded-xl ${tierClasses[tier]} ${hover ? "hover:ring-input-border transition-all duration-200" : ""} ${noPadding ? "" : "px-5 py-4"} ${className}`}
    >
      {children}
    </div>
  );
}
