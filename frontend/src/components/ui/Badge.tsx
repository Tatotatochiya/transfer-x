export type BadgeVariant =
  | "success" | "warning" | "danger" | "neutral" | "info"
  | "move-your" | "move-their" | "move-neither";

const variantClasses: Record<BadgeVariant, string> = {
  success: "bg-success/15 text-success-text ring-success/30",
  warning: "bg-warning-fill/15 text-warning-text ring-warning-fill/30",
  danger:  "bg-danger/15 text-danger-text ring-danger/30",
  info:    "bg-accent/15 text-accent ring-accent/30",
  neutral: "bg-text-muted/15 text-text-muted ring-text-muted/30",
  // "Whose move" states (docs/design_handoff_transferx/README.md) — plain
  // coloured text, no pill background/ring, per SCREENS.md's row treatment.
  "move-your":     "text-danger-text font-semibold",
  "move-their":    "text-text-secondary font-semibold",
  "move-neither":  "text-text-muted font-semibold",
};

const PILL_VARIANTS = new Set<BadgeVariant>(["success", "warning", "danger", "info", "neutral"]);

interface BadgeProps {
  variant?: BadgeVariant;
  children: React.ReactNode;
  className?: string;
}

export default function Badge({ variant = "neutral", children, className = "" }: BadgeProps) {
  const pill = PILL_VARIANTS.has(variant);
  return (
    <span
      className={`inline-flex items-center text-xs ${
        pill ? "rounded-full px-2.5 py-0.5 font-semibold ring-1" : ""
      } ${variantClasses[variant]} ${className}`}
    >
      {children}
    </span>
  );
}
