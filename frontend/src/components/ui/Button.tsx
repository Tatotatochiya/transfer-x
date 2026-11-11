import Spinner from "./Spinner";

export type ButtonVariant = "primary" | "primary-success" | "secondary" | "danger" | "ghost";
export type ButtonSize = "sm" | "md" | "lg";

const variantClasses: Record<ButtonVariant, string> = {
  primary:         "bg-accent hover:bg-accent-hover text-on-accent font-semibold shadow-sm",
  "primary-success": "bg-success hover:bg-success-text-alt text-white font-semibold shadow-sm",
  secondary:       "bg-surface hover:bg-surface-inset text-text-secondary font-semibold ring-1 ring-input-border",
  danger:          "bg-surface hover:bg-danger-bg text-danger-text-alt font-semibold ring-1 ring-danger-border",
  ghost:           "text-text-muted hover:text-text hover:bg-surface-inset font-semibold",
};

// Base sizing matches TOKENS.md (radius 8px, 15px/600 label, 10px/18px
// padding for the standard size). Below 1024px every size gets a min-height
// floor per RESPONSIVE.md's 44px touch-target rule (48px for `lg`, used for
// full-width/tier-1 actions) — shed at the lg: breakpoint back to the desktop
// spec, which doesn't need the floor since pointer input isn't touch.
const sizeClasses: Record<ButtonSize, string> = {
  sm: "min-h-11 lg:min-h-0 px-3 py-1.5 text-small rounded-lg",
  md: "min-h-11 lg:min-h-0 px-[18px] py-2.5 text-body rounded-lg",
  lg: "min-h-12 lg:min-h-0 px-5 py-2.5 text-body rounded-xl",
};

/** A Button's look for something that isn't a <button>, e.g. a router Link. */
export function buttonClasses(variant: ButtonVariant = "primary", size: ButtonSize = "md"): string {
  return `inline-flex items-center justify-center gap-2 no-underline transition-all duration-150 ${variantClasses[variant]} ${sizeClasses[size]}`;
}

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  children: React.ReactNode;
}

export default function Button({
  variant = "primary",
  size = "md",
  loading = false,
  disabled,
  children,
  className = "",
  ...props
}: ButtonProps) {
  return (
    <button
      disabled={disabled || loading}
      className={`inline-flex items-center justify-center gap-2 transition-all duration-150 disabled:opacity-50 disabled:cursor-not-allowed ${variantClasses[variant]} ${sizeClasses[size]} ${className}`}
      {...props}
    >
      {loading && <Spinner size="sm" />}
      {children}
    </button>
  );
}
