import { useQuery } from "@tanstack/react-query";
import api from "../../lib/api";
import type { Club } from "../../types/api";
import Card from "../../components/ui/Card";
import PageHeader from "../../components/ui/PageHeader";
import Spinner from "../../components/ui/Spinner";
import { formatCurrency, formatWage } from "../../lib/utils";

interface BudgetBarProps {
  used: number;
  total: number;
}

function BudgetBar({ used, total }: BudgetBarProps) {
  const pct = total > 0 ? Math.min((used / total) * 100, 100) : 0;
  const colour =
    pct > 85 ? "bg-red-500" : pct > 60 ? "bg-amber-500" : "bg-emerald-500";
  return (
    <div className="mt-2 h-2 w-full rounded-full bg-slate-800">
      <div
        className={`h-2 rounded-full transition-all ${colour}`}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

interface FinanceSectionProps {
  title: string;
  total: number;
  remaining: number;
  reserved: number;
  committed: number;
  formatFn: (v: number) => string;
}

function FinanceSection({
  title,
  total,
  remaining,
  reserved,
  committed,
  formatFn,
}: FinanceSectionProps) {
  const spent = total - remaining;
  return (
    <Card>
      <p className="mb-4 text-xs font-semibold uppercase tracking-wider text-slate-400">
        {title}
      </p>

      {/* Big remaining figure */}
      <p className="text-3xl font-bold text-white tabular-nums">
        {formatFn(remaining)}
      </p>
      <p className="mt-0.5 text-xs text-slate-500">remaining</p>

      <BudgetBar used={spent} total={total} />

      <div className="mt-4 space-y-2 border-t border-white/[0.06] pt-4">
        <div className="flex items-center justify-between text-sm">
          <span className="text-slate-400">Total budget</span>
          <span className="font-semibold text-white tabular-nums">
            {formatFn(total)}
          </span>
        </div>
        <div className="flex items-center justify-between text-sm">
          <span className="text-slate-400">Reserved</span>
          <span className="text-amber-400 tabular-nums">{formatFn(reserved)}</span>
        </div>
        <div className="flex items-center justify-between text-sm">
          <span className="text-slate-400">Committed</span>
          <span className="text-sky-400 tabular-nums">{formatFn(committed)}</span>
        </div>
        <div className="flex items-center justify-between text-sm border-t border-white/[0.06] pt-2">
          <span className="text-slate-400">Spent / reserved / committed</span>
          <span className="text-slate-300 tabular-nums">{formatFn(spent)}</span>
        </div>
      </div>
    </Card>
  );
}

export default function FinancePage() {
  const { data: club, isLoading } = useQuery<Club>({
    queryKey: ["clubs", "me"],
    queryFn: () => api.get<Club>("/clubs/me").then((r) => r.data),
    staleTime: 60_000,
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner size="lg" />
      </div>
    );
  }

  const finance = club?.finance;

  return (
    <div className="max-w-2xl">
      <PageHeader
        title="Finance"
        subtitle="Transfer and wage budget overview"
      />

      {!finance ? (
        <div className="rounded-xl bg-slate-900 px-5 py-8 text-center ring-1 ring-white/[0.08]">
          <p className="text-slate-400 text-sm">
            No finance data available. Contact TransferX staff.
          </p>
        </div>
      ) : (
        <div className="space-y-6">
          <FinanceSection
            title="Transfer Budget"
            total={Number(finance.transfer_budget_total)}
            remaining={Number(finance.transfer_remaining)}
            reserved={Number(finance.transfer_reserved)}
            committed={Number(finance.transfer_committed)}
            formatFn={formatCurrency}
          />
          <FinanceSection
            title="Wage Budget (per week)"
            total={Number(finance.wage_budget_total_weekly)}
            remaining={Number(finance.wage_remaining_weekly)}
            reserved={Number(finance.wage_reserved_weekly)}
            committed={Number(finance.wage_committed_weekly)}
            formatFn={formatWage}
          />
        </div>
      )}
    </div>
  );
}
