export type AlertVariant = "danger" | "warning" | "success" | "info";

const variantClasses: Record<AlertVariant, string> = {
  danger:  "bg-danger-bg text-danger-text-alt ring-1 ring-danger-border",
  warning: "bg-warning-fill/10 text-warning-text ring-1 ring-warning-fill/30",
  success: "bg-success/10 text-success-text ring-1 ring-success/30",
  info:    "bg-accent-bg text-accent ring-1 ring-accent/30",
};

interface AlertProps {
  variant?: AlertVariant;
  children: React.ReactNode;
  className?: string;
}

/** Inline banner — replaces the hand-rolled colour-div pattern repeated
 * throughout the app (LoginPage's error banner is the reference case). */
export default function Alert({ variant = "info", children, className = "" }: AlertProps) {
  return (
    <div className={`rounded-lg px-4 py-3 text-sm ${variantClasses[variant]} ${className}`}>
      {children}
    </div>
  );
}
