import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { ApprovalPolicy, Club } from "../../types/api";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import PageHeader from "../../components/ui/PageHeader";
import Spinner from "../../components/ui/Spinner";
import { useClubCapabilities } from "../../hooks/useClubCapabilities";
import { useToast } from "../../context/ToastContext";
import { formatCurrency, formatWage, getApiError } from "../../lib/utils";

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
  spent?: number;
  formatFn: (v: number) => string;
}

function FinanceSection({
  title,
  total,
  remaining,
  reserved,
  committed,
  spent,
  formatFn,
}: FinanceSectionProps) {
  return (
    <Card>
      <p className="mb-4 text-xs font-semibold uppercase tracking-wider text-slate-400">
        {title}
      </p>

      <p className="text-3xl font-bold text-white tabular-nums">
        {formatFn(remaining)}
      </p>
      <p className="mt-0.5 text-xs text-slate-500">remaining</p>

      <BudgetBar used={total - remaining} total={total} />

      <div className="mt-4 space-y-2 border-t border-white/[0.06] pt-4">
        <div className="flex items-center justify-between text-sm">
          <span className="text-slate-400">Total budget</span>
          <span className="font-semibold text-white tabular-nums">
            {formatFn(total)}
          </span>
        </div>
        {spent !== undefined && (
          <div className="flex items-center justify-between text-sm">
            <span className="text-slate-400">Spent</span>
            <span className="text-emerald-400 tabular-nums">{formatFn(spent)}</span>
          </div>
        )}
        <div className="flex items-center justify-between text-sm">
          <span className="text-slate-400">Committed</span>
          <span className="text-sky-400 tabular-nums">{formatFn(committed)}</span>
        </div>
        <div className="flex items-center justify-between text-sm">
          <span className="text-slate-400">Reserved</span>
          <span className="text-amber-400 tabular-nums">{formatFn(reserved)}</span>
        </div>
      </div>
    </Card>
  );
}

// Phase 5 (D7): the club's single spending-approval threshold — owner-only.
function ApprovalPolicyCard() {
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState("");

  const { data: policy } = useQuery<ApprovalPolicy>({
    queryKey: ["clubs", "me", "approval-policy"],
    queryFn: () => api.get<ApprovalPolicy>("/clubs/me/approval-policy").then((r) => r.data),
  });

  const mutation = useMutation({
    mutationFn: (approval_threshold: number | null) =>
      api.patch<ApprovalPolicy>("/clubs/me/approval-policy", { approval_threshold }).then((r) => r.data),
    onSuccess: (data) => {
      queryClient.setQueryData(["clubs", "me", "approval-policy"], data);
      queryClient.invalidateQueries({ queryKey: ["clubs", "me"] });
      setEditing(false);
      addToast(
        data.approval_threshold != null
          ? `Approval threshold set to ${formatCurrency(Number(data.approval_threshold))}`
          : "Approval threshold cleared — manager actions execute directly",
        "success",
      );
    },
    onError: (err: unknown) => addToast(getApiError(err, "Failed to update policy."), "error"),
  });

  const threshold = policy?.approval_threshold;

  return (
    <Card>
      <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
        Spending approvals
      </p>
      <p className="text-sm text-slate-400 leading-relaxed">
        When set, a manager's market action (bid, offer, acceptance) at or above this
        amount waits for sign-off from you or a sporting director instead of executing.
      </p>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        {!editing ? (
          <>
            <p className="text-2xl font-bold text-white tabular-nums">
              {threshold != null ? formatCurrency(Number(threshold)) : "Off"}
            </p>
            <div className="flex gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => {
                  setValue(threshold != null ? String(Number(threshold)) : "");
                  setEditing(true);
                }}
              >
                {threshold != null ? "Change" : "Set threshold"}
              </Button>
              {threshold != null && (
                <Button
                  variant="ghost"
                  size="sm"
                  loading={mutation.isPending}
                  onClick={() => mutation.mutate(null)}
                >
                  Turn off
                </Button>
              )}
            </div>
          </>
        ) : (
          <form
            className="flex flex-wrap items-center gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              const parsed = Number(value);
              if (!Number.isFinite(parsed) || parsed < 0) {
                addToast("Enter a valid amount", "warning");
                return;
              }
              mutation.mutate(parsed);
            }}
          >
            <input
              type="number"
              min="0"
              step="100000"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder="e.g. 5000000"
              className="w-44 rounded-lg bg-slate-950 px-3 py-2 text-sm text-white placeholder-slate-600 ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500"
            />
            <Button type="submit" variant="primary" size="sm" loading={mutation.isPending}>
              Save
            </Button>
            <Button type="button" variant="ghost" size="sm" onClick={() => setEditing(false)}>
              Cancel
            </Button>
          </form>
        )}
      </div>
    </Card>
  );
}

export default function FinancePage() {
  const { can } = useClubCapabilities();
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
            spent={Number(finance.transfer_spent)}
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
          {can("TEAM_MANAGE") && <ApprovalPolicyCard />}
        </div>
      )}
    </div>
  );
}
