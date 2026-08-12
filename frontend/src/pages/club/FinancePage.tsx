import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { ApprovalPolicy, Club, Deal, Offer, Paginated } from "../../types/api";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import PageHeader from "../../components/ui/PageHeader";
import ResponsiveTable, { type ResponsiveColumn } from "../../components/ui/ResponsiveTable";
import Spinner from "../../components/ui/Spinner";
import { useClubCapabilities } from "../../hooks/useClubCapabilities";
import { useToast } from "../../context/ToastContext";
import { formatCurrency, formatWage, getApiError } from "../../lib/utils";

// ── Budget card — four-segment bar (spent / committed / reserved / free) ─────

interface FinanceSectionProps {
  title: string;
  total: number;
  remaining: number;
  reserved: number;
  committed: number;
  spent?: number;
  formatFn: (v: number) => string;
}

function FinanceSection({ title, total, remaining, reserved, committed, spent, formatFn }: FinanceSectionProps) {
  const pct = (v: number) => (total > 0 ? Math.min((v / total) * 100, 100) : 0);
  const legend = [
    ...(spent !== undefined ? [{ label: "Spent", value: spent, swatch: "bg-text-secondary" }] : []),
    { label: "Committed", value: committed, swatch: "bg-accent-soft" },
    { label: "Reserved", value: reserved, swatch: "bg-warning-fill" },
  ];

  return (
    <Card>
      <p className="text-xs font-semibold uppercase tracking-wider text-text-secondary">{title}</p>
      <p className="mt-2 text-[34px] font-bold text-text tabular-nums">{formatFn(remaining)}</p>
      <p className="text-[13px] text-text-muted">remaining of {formatFn(total)}</p>

      <div className="mt-3 flex h-2.5 w-full overflow-hidden rounded-full bg-border-quiet">
        {spent !== undefined && <div className="h-full bg-text-secondary" style={{ width: `${pct(spent)}%` }} />}
        <div className="h-full bg-accent-soft" style={{ width: `${pct(committed)}%` }} />
        <div className="h-full bg-warning-fill" style={{ width: `${pct(reserved)}%` }} />
      </div>

      <div className="mt-4 space-y-2 border-t border-rule pt-4">
        {legend.map((row) => (
          <div key={row.label} className="flex items-center justify-between text-[13px]">
            <span className="flex items-center gap-2 text-text-secondary">
              <span className={`h-[9px] w-[9px] rounded-[2px] ${row.swatch}`} />
              {row.label}
            </span>
            <span className="font-semibold text-text">{formatFn(row.value)}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}

// ── Approval threshold card ───────────────────────────────────────────────────

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
      <div className="flex flex-wrap items-start justify-between gap-6">
        <p className="max-w-[560px] text-sm leading-[1.6] text-text-secondary">
          A manager's bid, offer or acceptance at or above this amount waits for sign-off from you
          or a sporting director instead of executing.
        </p>
        {!editing ? (
          <div className="shrink-0 text-right">
            <p className="text-[11px] text-text-muted">Threshold</p>
            <p className="text-[30px] font-bold text-text tabular-nums">
              {threshold != null ? formatCurrency(Number(threshold)) : "Off"}
            </p>
            <div className="mt-2 flex justify-end gap-2">
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
                <Button variant="ghost" size="sm" loading={mutation.isPending} onClick={() => mutation.mutate(null)}>
                  Turn off
                </Button>
              )}
            </div>
          </div>
        ) : (
          <form
            className="flex shrink-0 flex-wrap items-center gap-2"
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
              className="w-44 rounded-lg bg-surface px-3 py-2 text-sm text-text placeholder-text-muted ring-1 ring-input-border focus:outline-none focus:ring-accent"
            />
            <Button type="submit" variant="primary" size="sm" loading={mutation.isPending}>Save</Button>
            <Button type="button" variant="ghost" size="sm" onClick={() => setEditing(false)}>Cancel</Button>
          </form>
        )}
      </div>
    </Card>
  );
}

// ── Commitments table ──────────────────────────────────────────────────────────
// Built from real, already-fetched deal/offer data — the backend doesn't yet
// expose a row-level breakdown of what's committing the budget totals above
// (B5, docs/design_handoff_transferx/SESSIONS.md → "Backend work"), so this
// reconstructs the transfer-budget half from what IS available: in-progress
// deals where this club is buying (committed) and active sent offers (reserved).
// It is a real, honest breakdown — just not guaranteed to sum to the exact
// backend "committed"/"reserved" totals above, which may see more than this.

interface CommitmentRow {
  key: string;
  name: string;
  type: "Deal" | "Offer";
  amount: number;
  releasesWhen: string;
  onClick: () => void;
}

function CommitmentsTable({ clubId }: { clubId: string }) {
  const navigate = useNavigate();

  const { data: deals } = useQuery<Paginated<Deal>>({
    queryKey: ["finance", "commitments", "deals"],
    queryFn: () => api.get<Paginated<Deal>>("/deals", { params: { deal_status: "IN_PROGRESS", page_size: 30 } }).then((r) => r.data),
  });

  const { data: offers } = useQuery<Paginated<Offer>>({
    queryKey: ["finance", "commitments", "offers"],
    queryFn: () => api.get<Paginated<Offer>>("/offers/sent", { params: { page_size: 30 } }).then((r) => r.data),
  });

  const rows: CommitmentRow[] = useMemo(() => {
    // Number(...): agreed_fee/fee_amount can arrive Decimal-serialized as a
    // string — harmless for the per-row formatCurrency() call below (which
    // coerces internally) but "+" on two numeric strings concatenates instead
    // of adding, which is what was producing "£NaN" in the total.
    const dealRows: CommitmentRow[] = (deals?.items ?? [])
      .filter((d) => d.buyer_club_id === clubId && Number(d.agreed_fee) > 0)
      .map((d) => ({
        key: `deal-${d.id}`,
        name: d.player?.name ?? "Deal",
        type: "Deal",
        amount: Number(d.agreed_fee),
        releasesWhen: "Deal completes or collapses",
        onClick: () => navigate(`/deals/${d.id}`),
      }));
    const offerRows: CommitmentRow[] = (offers?.items ?? [])
      .filter((o) => (o.status === "SENT" || o.status === "COUNTERED") && o.fee_amount != null)
      .map((o) => ({
        key: `offer-${o.id}`,
        name: o.player?.name ?? "Offer",
        type: "Offer",
        amount: Number(o.fee_amount),
        releasesWhen: "Offer resolves",
        onClick: () => navigate(`/offers/${o.id}`),
      }));
    return [...dealRows, ...offerRows].sort((a, b) => b.amount - a.amount);
  }, [deals, offers, clubId, navigate]);

  if (deals === undefined || offers === undefined) return null;
  if (rows.length === 0) return null;

  const totalCommitted = rows.reduce((sum, r) => sum + r.amount, 0);

  const columns: ResponsiveColumn<CommitmentRow>[] = [
    { key: "name", header: "Commitment", priority: 1, render: (r) => <span className="font-medium text-text">{r.name}</span> },
    { key: "type", header: "Type", priority: 3, render: (r) => <span className="text-text-muted">{r.type}</span> },
    { key: "amount", header: "Amount", priority: 2, className: "text-right", render: (r) => <span className="font-bold text-text">{formatCurrency(r.amount)}</span> },
    { key: "releases", header: "Releases when", priority: 4, render: (r) => <span className="text-text-muted">{r.releasesWhen}</span> },
  ];

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-bold text-text">Where the money is committed</h2>
        <span className="text-xs text-text-muted">{formatCurrency(totalCommitted)} across {rows.length} commitment{rows.length === 1 ? "" : "s"}</span>
      </div>
      <ResponsiveTable
        columns={columns}
        rows={rows}
        rowKey={(r) => r.key}
        onRowClick={(r) => r.onClick()}
        renderCard={(r) => (
          <div className="px-4 py-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold text-text">{r.name}</span>
              <span className="text-sm font-bold text-text">{formatCurrency(r.amount)}</span>
            </div>
            <div className="mt-0.5 flex items-center justify-between text-xs text-text-muted">
              <span>{r.type}</span>
              <span>{r.releasesWhen}</span>
            </div>
          </div>
        )}
      />
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function FinancePage() {
  const { can } = useClubCapabilities();
  const { data: club, isLoading } = useQuery<Club>({
    queryKey: ["clubs", "me"],
    queryFn: () => api.get<Club>("/clubs/me").then((r) => r.data),
    staleTime: 60_000,
  });

  if (isLoading) {
    return <div className="flex items-center justify-center py-20"><Spinner size="lg" /></div>;
  }

  const finance = club?.finance;

  return (
    <div>
      <PageHeader title="Finance" subtitle="Transfer and wage budget overview" />

      {!finance ? (
        <Card tier={4} className="text-center py-8">
          <p className="text-sm text-text-muted">No finance data available. Contact TransferX staff.</p>
        </Card>
      ) : (
        <div className="space-y-6">
          <div className="grid gap-4" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))" }}>
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
              title="Wage Budget (weekly)"
              total={Number(finance.wage_budget_total_weekly)}
              remaining={Number(finance.wage_remaining_weekly)}
              reserved={Number(finance.wage_reserved_weekly)}
              committed={Number(finance.wage_committed_weekly)}
              formatFn={formatWage}
            />
          </div>

          {can("TEAM_MANAGE") && <ApprovalPolicyCard />}

          {club && <CommitmentsTable clubId={club.id} />}
        </div>
      )}
    </div>
  );
}
