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
      <p className="text-xs font-medium uppercase tracking-wider text-text-muted">{label}</p>
      <p className="mt-2 text-2xl font-bold text-text break-words">{value}</p>
      {subtext && (
        <div className="mt-1.5 flex items-center gap-1.5 text-sm">
          {trend === "up" && <span className="text-success-text">{subtext}</span>}
          {trend === "down" && <span className="text-danger-text">{subtext}</span>}
          {(!trend || trend === "neutral") && <span className="text-text-muted">{subtext}</span>}
        </div>
      )}
    </div>
  );
}
