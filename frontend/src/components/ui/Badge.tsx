export type BadgeVariant =
  | "success" | "warning" | "danger" | "neutral" | "ai"
  /** @deprecated An alias of `neutral`: blue is only for things you can tap. */
  | "info"
  | "move-your" | "move-their" | "move-neither";

const variantClasses: Record<BadgeVariant, string> = {
  success: "bg-success-bg text-success-text ring-success-ring",
  warning: "bg-warning-bg text-warning-text ring-warning-ring",
  danger:  "bg-danger-bg text-danger-text ring-danger-ring",
  neutral: "bg-surface-inset text-text-secondary ring-border",
  info:    "bg-surface-inset text-text-secondary ring-border",
  // Everything TransferX's AI writes or suggests.
  ai:      "bg-ai-bg text-ai-text ring-ai-ring",
  // "Whose move" states (docs/design-system/README.md) — plain
  // coloured text, no pill background/ring, per SCREENS.md's row treatment.
  "move-your":     "text-danger-text font-semibold",
  "move-their":    "text-text-secondary font-semibold",
  "move-neither":  "text-text-muted font-semibold",
};

const PILL_VARIANTS = new Set<BadgeVariant>(["success", "warning", "danger", "info", "neutral", "ai"]);

interface BadgeProps {
  variant?: BadgeVariant;
  children: React.ReactNode;
  className?: string;
}

export default function Badge({ variant = "neutral", children, className = "" }: BadgeProps) {
  const pill = PILL_VARIANTS.has(variant);
  return (
    <span
      className={`inline-flex items-center text-caption ${
        pill ? "rounded-full px-2 py-0.5 font-semibold ring-1" : ""
      } ${variantClasses[variant]} ${className}`}
    >
      {children}
    </span>
  );
}
