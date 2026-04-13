export type BadgeVariant = "success" | "warning" | "danger" | "neutral" | "info";

const variantClasses: Record<BadgeVariant, string> = {
  success: "bg-emerald-500/15 text-emerald-400 ring-emerald-500/30",
  warning: "bg-amber-400/15 text-amber-400 ring-amber-400/30",
  danger:  "bg-red-500/15 text-red-400 ring-red-500/30",
  info:    "bg-sky-500/15 text-sky-400 ring-sky-500/30",
  neutral: "bg-slate-500/15 text-slate-400 ring-slate-500/30",
};

interface BadgeProps {
  variant?: BadgeVariant;
  children: React.ReactNode;
  className?: string;
}

export default function Badge({ variant = "neutral", children, className = "" }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ${variantClasses[variant]} ${className}`}
    >
      {children}
    </span>
  );
}
