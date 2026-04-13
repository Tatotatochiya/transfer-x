interface Props {
  score: number;
  trend?: number | null;
  size?: "sm" | "md";
}

function formColour(score: number): string {
  if (score >= 75) return "bg-emerald-500/20 text-emerald-300 ring-emerald-500/30";
  if (score >= 55) return "bg-green-500/20 text-green-300 ring-green-500/30";
  if (score >= 35) return "bg-amber-500/20 text-amber-300 ring-amber-500/30";
  return "bg-red-500/20 text-red-300 ring-red-500/30";
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
          ? "px-2.5 py-1 text-sm"
          : "px-1.5 py-0.5 text-xs"
      }`}
      title={`Form score: ${n.toFixed(1)}${t != null ? ` (trend ${t > 0 ? "+" : ""}${t.toFixed(1)})` : ""}`}
    >
      {label}
    </span>
  );
}
