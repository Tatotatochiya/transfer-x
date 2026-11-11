interface Props {
  score: number;
  trend?: number | null;
  size?: "sm" | "md";
}

function formColour(score: number): string {
  if (score >= 75) return "bg-success-bg text-success-text ring-success-ring";
  if (score >= 55) return "bg-success-bg text-success-text-alt ring-success-ring";
  if (score >= 35) return "bg-warning-bg text-warning-text ring-warning-ring";
  return "bg-danger-bg text-danger-text ring-danger-ring";
}

function trendArrow(trend: number | null | undefined): string {
  if (trend == null) return "";
  if (trend > 5) return " ↑";
  if (trend < -5) return " ↓";
  return " →";
}

export default function FormBadge({ score, trend, size = "sm" }: Props) {
  const n = Number(score); // guard: API may serialize Decimal as string
  const t = trend != null ? Number(trend) : null;
  const colour = formColour(n);
  const arrow = trendArrow(t);
  const label = `${Math.round(n)}${arrow}`;

  return (
    <span
      className={`inline-flex items-center rounded-full ring-1 font-semibold tabular-nums ${colour} ${
        size === "md"
          ? "px-2.5 py-1 text-body"
          : "px-1.5 py-0.5 text-caption"
      }`}
      title={`Form score: ${n.toFixed(1)}${t != null ? ` (trend ${t > 0 ? "+" : ""}${t.toFixed(1)})` : ""}`}
    >
      {label}
    </span>
  );
}
