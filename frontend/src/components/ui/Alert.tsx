export type AlertVariant = "danger" | "warning" | "success" | "info";

const variantClasses: Record<AlertVariant, string> = {
  danger:  "bg-danger-bg text-danger-text-alt ring-1 ring-danger-border",
  warning: "bg-warning-bg text-warning-text ring-1 ring-warning-ring",
  success: "bg-success-bg text-success-text ring-1 ring-success-ring",
  info:    "bg-accent-bg text-text ring-1 ring-accent-ring",
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
    <div className={`rounded-lg px-4 py-3 text-body ${variantClasses[variant]} ${className}`}>
      {children}
    </div>
  );
}
