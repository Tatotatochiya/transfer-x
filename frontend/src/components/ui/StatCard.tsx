type Trend = "up" | "down" | "neutral";

interface StatCardProps {
  label: string;
  value: string;
  subtext?: string;
  trend?: Trend;
}

export default function StatCard({ label, value, subtext, trend }: StatCardProps) {
  return (
    <div className="bg-surface rounded-xl p-5 ring-1 ring-border">
      <p className="text-caption font-semibold text-text-secondary">{label}</p>
      <p className="mt-2 text-headline font-bold tabular-nums text-text break-words sm:text-title">{value}</p>
      {subtext && (
        <div className="mt-1.5 flex items-center gap-1.5 text-small">
          {trend === "up" && <span className="text-success-text">{subtext}</span>}
          {trend === "down" && <span className="text-danger-text">{subtext}</span>}
          {(!trend || trend === "neutral") && <span className="text-text-muted">{subtext}</span>}
        </div>
      )}
    </div>
  );
}
