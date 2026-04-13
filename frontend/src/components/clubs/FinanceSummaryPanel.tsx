import { Link } from "react-router-dom";
import type { ClubFinance } from "../../types/api";
import { formatCurrency, formatWage } from "../../lib/utils";

function MiniBar({ used, total }: { used: number; total: number }) {
  const pct = total > 0 ? Math.min((used / total) * 100, 100) : 0;
  const colour = pct > 85 ? "bg-red-500" : pct > 60 ? "bg-amber-500" : "bg-emerald-500";
  return (
    <div className="mt-1.5 h-1.5 w-full rounded-full bg-slate-800">
      <div className={`h-1.5 rounded-full transition-all ${colour}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

export default function FinanceSummaryPanel({ finance }: { finance: ClubFinance }) {
  const transferSpent = finance.transfer_budget_total - finance.transfer_remaining;
  const wageSpent = finance.wage_budget_total_weekly - finance.wage_remaining_weekly;

  return (
    <div className="rounded-xl bg-slate-900/60 ring-1 ring-white/[0.06] px-5 py-4">
      <div className="mb-3 flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Finances</p>
        <Link
          to="/club/finance"
          className="text-xs text-slate-500 hover:text-emerald-400 transition-colors"
        >
          Full view →
        </Link>
      </div>
      <div className="space-y-4">
        <div>
          <div className="flex items-baseline justify-between">
            <span className="text-xs text-slate-400">Transfer budget</span>
            <span className="text-sm font-semibold text-white tabular-nums">
              {formatCurrency(finance.transfer_remaining)}
            </span>
          </div>
          <MiniBar used={transferSpent} total={finance.transfer_budget_total} />
          <p className="mt-1 text-xs text-slate-600">
            of {formatCurrency(finance.transfer_budget_total)} total
          </p>
        </div>
        <div>
          <div className="flex items-baseline justify-between">
            <span className="text-xs text-slate-400">Wage budget / wk</span>
            <span className="text-sm font-semibold text-white tabular-nums">
              {formatWage(finance.wage_remaining_weekly)}
            </span>
          </div>
          <MiniBar used={wageSpent} total={finance.wage_budget_total_weekly} />
          <p className="mt-1 text-xs text-slate-600">
            of {formatWage(finance.wage_budget_total_weekly)} total
          </p>
        </div>
      </div>
    </div>
  );
}
