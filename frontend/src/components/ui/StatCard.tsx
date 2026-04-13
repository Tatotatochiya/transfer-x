type Trend = "up" | "down" | "neutral";

interface StatCardProps {
  label: string;
  value: string;
  subtext?: string;
  trend?: Trend;
}

export default function StatCard({ label, value, subtext, trend }: StatCardProps) {
  return (
    <div className="bg-slate-900 rounded-xl p-5 ring-1 ring-white/[0.08]">
      <p className="text-xs font-medium uppercase tracking-wider text-slate-400">{label}</p>
      <p className="mt-2 text-2xl font-bold text-white">{value}</p>
      {subtext && (
        <div className="mt-1.5 flex items-center gap-1.5 text-sm">
          {trend === "up" && <span className="text-emerald-400">{subtext}</span>}
          {trend === "down" && <span className="text-red-400">{subtext}</span>}
          {(!trend || trend === "neutral") && <span className="text-slate-500">{subtext}</span>}
        </div>
      )}
    </div>
  );
}
