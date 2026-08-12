import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import { useAuth } from "../../hooks/useAuth";
import { useClubCapabilities } from "../../hooks/useClubCapabilities";
import type { ApprovalPolicy, Club, PendingApproval } from "../../types/api";
import type { ApprovalStatus } from "../../types/enums";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import EmptyState from "../../components/ui/EmptyState";
import PageHeader from "../../components/ui/PageHeader";
import ResponsiveTable, { type ResponsiveColumn } from "../../components/ui/ResponsiveTable";
import Spinner from "../../components/ui/Spinner";
import { useToast } from "../../context/ToastContext";
import { formatCurrency, formatDateTime, getApiError } from "../../lib/utils";

const STATUS_BADGE: Record<ApprovalStatus, { label: string; variant: "info" | "success" | "danger" | "neutral" | "warning" }> = {
  PENDING:           { label: "Pending",  variant: "warning" },
  APPROVED_EXECUTED: { label: "Approved", variant: "success" },
  APPROVED_FAILED:   { label: "Approved — failed", variant: "danger" },
  REJECTED:          { label: "Rejected", variant: "danger" },
  EXPIRED:           { label: "Expired",  variant: "neutral" },
  CANCELLED:         { label: "Cancelled", variant: "neutral" },
};

function elapsed(iso: string): string {
  const hours = (Date.now() - new Date(iso).getTime()) / 3_600_000;
  if (hours < 1) return "just now";
  if (hours < 24) return `${Math.floor(hours)}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

// ── Tier 1 — waiting on your decision ─────────────────────────────────────────

function DecisionRow({
  approval, transferRemaining, onApprove, onReject, approving, isRejectPending,
}: {
  approval: PendingApproval;
  transferRemaining: number | null;
  onApprove: () => void;
  onReject: (reason: string | null) => void;
  approving: boolean;
  isRejectPending: boolean;
}) {
  const [showRejectForm, setShowRejectForm] = useState(false);
  const [reason, setReason] = useState("");
  const budgetAfter = transferRemaining != null ? transferRemaining - approval.amount : null;

  return (
    <div className="border-b border-rule px-5 py-[18px] last:border-b-0">
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex-1 basis-[260px]">
          <p className="text-base font-bold text-text">{approval.summary ?? approval.action_type.replace(/_/g, " ")}</p>
          <p className="text-[13px] text-text-secondary">
            {approval.requested_by_email ?? "Unknown requester"} · {elapsed(approval.created_at)}
            {approval.expires_at && ` · expires ${formatDateTime(approval.expires_at)}`}
          </p>
        </div>
        <div className="basis-[150px] shrink">
          <p className="text-[11px] text-text-muted">Amount</p>
          <p className="text-[17px] font-bold text-text">{formatCurrency(approval.amount)}</p>
        </div>
        {budgetAfter != null && (
          <div className="basis-[150px] shrink">
            <p className="text-[11px] text-text-muted">Budget after</p>
            <p className="text-[17px] font-bold text-success-text">{formatCurrency(budgetAfter)}</p>
          </div>
        )}
        <div className="flex shrink-0 gap-2">
          <Button variant="primary" size="sm" loading={approving} onClick={onApprove}>Approve</Button>
          <Button variant="danger" size="sm" loading={isRejectPending} onClick={() => setShowRejectForm((v) => !v)}>Reject</Button>
        </div>
      </div>
      {showRejectForm && (
        <div className="mt-3 flex items-center gap-2 border-t border-rule-faint pt-3">
          <input
            type="text"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Reason (optional)"
            className="min-w-0 flex-1 rounded-lg bg-surface px-3 py-2 text-sm text-text placeholder-text-muted ring-1 ring-input-border focus:outline-none focus:ring-accent"
          />
          <Button variant="danger" size="sm" loading={isRejectPending} onClick={() => onReject(reason || null)}>Confirm reject</Button>
          <Button variant="ghost" size="sm" onClick={() => setShowRejectForm(false)}>Cancel</Button>
        </div>
      )}
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────────

type Filter = "PENDING" | "ALL";

export default function ApprovalsPage() {
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const { user } = useAuth();
  const { can, isLoading: capsLoading } = useClubCapabilities();
  const [filter, setFilter] = useState<Filter>("PENDING");
  const [decidingId, setDecidingId] = useState<string | null>(null);

  const canDecide = can("APPROVE_ACTIONS");

  const { data: club } = useQuery<Club>({
    queryKey: ["clubs", "me"],
    queryFn: () => api.get<Club>("/clubs/me").then((r) => r.data),
    staleTime: 60_000,
  });

  const { data: approvals, isLoading } = useQuery<PendingApproval[]>({
    queryKey: ["clubs", "me", "approvals", filter],
    queryFn: () =>
      api
        .get<PendingApproval[]>("/clubs/me/approvals", {
          params: filter === "PENDING" ? { approval_status: "PENDING" } : {},
        })
        .then((r) => r.data),
  });

  const { data: policy } = useQuery<ApprovalPolicy>({
    queryKey: ["clubs", "me", "approval-policy"],
    queryFn: () => api.get<ApprovalPolicy>("/clubs/me/approval-policy").then((r) => r.data),
    enabled: can("TEAM_MANAGE"),
  });

  function invalidate() {
    queryClient.invalidateQueries({ queryKey: ["clubs", "me", "approvals"] });
  }

  const approveMutation = useMutation({
    mutationFn: (id: string) => api.post<PendingApproval>(`/clubs/me/approvals/${id}/approve`).then((r) => r.data),
    onSuccess: (data) => {
      invalidate();
      setDecidingId(null);
      if (data.status === "APPROVED_EXECUTED") {
        addToast("Approved and executed", "success");
      } else {
        addToast(`Approved, but execution failed: ${data.failure_reason ?? "unknown reason"}`, "warning");
      }
    },
    onError: (err: unknown) => { setDecidingId(null); addToast(getApiError(err, "Failed to approve."), "error"); },
  });

  const rejectMutation = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string | null }) =>
      api.post<PendingApproval>(`/clubs/me/approvals/${id}/reject`, { reason }).then((r) => r.data),
    onSuccess: () => {
      invalidate();
      setDecidingId(null);
      addToast("Request rejected", "info");
    },
    onError: (err: unknown) => { setDecidingId(null); addToast(getApiError(err, "Failed to reject."), "error"); },
  });

  const cancelMutation = useMutation({
    mutationFn: (id: string) => api.post<PendingApproval>(`/clubs/me/approvals/${id}/cancel`).then((r) => r.data),
    onSuccess: () => {
      invalidate();
      addToast("Request cancelled", "info");
    },
    onError: (err: unknown) => addToast(getApiError(err, "Failed to cancel."), "error"),
  });

  if (capsLoading || isLoading) {
    return <div className="flex items-center justify-center py-20"><Spinner size="lg" /></div>;
  }

  const rows = approvals ?? [];
  const pending = rows.filter((a) => a.status === "PENDING");
  const decided = rows.filter((a) => a.status !== "PENDING");
  const transferRemaining = club?.finance ? Number(club.finance.transfer_remaining) : null;

  const decidedColumns: ResponsiveColumn<PendingApproval>[] = [
    { key: "request", header: "Request", priority: 1, render: (a) => (
      <span className="font-medium text-text">{a.summary ?? a.action_type.replace(/_/g, " ")}</span>
    ) },
    { key: "requester", header: "Requested by", priority: 3, render: (a) => <span className="text-text-muted">{a.requested_by_email ?? "—"}</span> },
    { key: "amount", header: "Amount", priority: 2, className: "text-right", render: (a) => <span className="font-bold text-text">{formatCurrency(a.amount)}</span> },
    { key: "outcome", header: "Outcome", priority: 4, render: (a) => <Badge variant={STATUS_BADGE[a.status].variant}>{STATUS_BADGE[a.status].label}</Badge> },
    { key: "decided", header: "Decided", priority: 5, className: "text-right", render: (a) => <span className="text-xs text-text-muted">{a.decided_at ? formatDateTime(a.decided_at) : "—"}</span> },
  ];

  return (
    <div>
      <PageHeader
        title="Approvals"
        subtitle={canDecide ? "Spending requests from your team that need a decision" : "Your spending requests awaiting a decision"}
      />

      {can("TEAM_MANAGE") && (
        <p className="mb-5 text-[13px] text-text-secondary">
          {policy?.approval_threshold != null
            ? <>Manager actions at or above <span className="font-semibold text-text">{formatCurrency(policy.approval_threshold)}</span> require your approval. Change this on the Finance page.</>
            : "No approval threshold is set — manager actions execute directly. Set one on the Finance page."}
        </p>
      )}

      <div className="mb-5 flex w-fit gap-1 rounded-xl bg-surface-inset p-1">
        {(["PENDING", "ALL"] as Filter[]).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`rounded-lg px-4 py-1.5 text-sm font-medium transition-colors ${
              filter === f ? "bg-surface text-text shadow-sm" : "text-text-muted hover:text-text"
            }`}
          >
            {f === "PENDING" ? "Pending" : "All"}
          </button>
        ))}
      </div>

      {rows.length === 0 ? (
        <EmptyState
          title={filter === "PENDING" ? "Nothing waiting" : "No approval history"}
          body={
            canDecide
              ? "When a manager commits money at or above your club's threshold, the request lands here."
              : "When one of your actions needs sign-off, it will appear here."
          }
        />
      ) : (
        <>
          {canDecide && pending.length > 0 && (
            <Card tier={1} noPadding className="mb-6">
              <div className="flex items-center justify-between border-b border-danger-border bg-danger-bg px-5 py-3 rounded-t-xl">
                <div className="flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-danger" />
                  <span className="text-[13px] font-bold text-danger-heading">Waiting on your decision — {pending.length}</span>
                </div>
              </div>
              <div>
                {pending.map((a) => (
                  <DecisionRow
                    key={a.id}
                    approval={a}
                    transferRemaining={transferRemaining}
                    onApprove={() => { setDecidingId(a.id); approveMutation.mutate(a.id); }}
                    onReject={(reason) => { setDecidingId(a.id); rejectMutation.mutate({ id: a.id, reason }); }}
                    approving={decidingId === a.id && approveMutation.isPending}
                    isRejectPending={decidingId === a.id && rejectMutation.isPending}
                  />
                ))}
              </div>
            </Card>
          )}

          {!canDecide && pending.length > 0 && (
            <div className="mb-6 space-y-3">
              {pending.map((a) => (
                <Card key={a.id}>
                  <div className="flex flex-wrap items-center gap-4">
                    <div className="flex-1 basis-[240px]">
                      <p className="text-sm font-semibold text-text">{a.summary ?? a.action_type.replace(/_/g, " ")}</p>
                      <p className="text-xs text-text-muted">{elapsed(a.created_at)} · expires {formatDateTime(a.expires_at)}</p>
                    </div>
                    <span className="text-sm font-bold text-text">{formatCurrency(a.amount)}</span>
                    <Badge variant="warning">Pending</Badge>
                    {a.requested_by_user_id === user?.id && (
                      <Button variant="ghost" size="sm" loading={cancelMutation.isPending} onClick={() => cancelMutation.mutate(a.id)}>
                        <span className="text-danger-text">Cancel</span>
                      </Button>
                    )}
                  </div>
                </Card>
              ))}
            </div>
          )}

          {decided.length > 0 && (
            <div>
              {filter === "PENDING" ? null : <h2 className="mb-3 text-sm font-bold text-text">Decided</h2>}
              <ResponsiveTable
                columns={decidedColumns}
                rows={decided}
                rowKey={(a) => a.id}
                renderCard={(a) => (
                  <div className="px-4 py-3">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-semibold text-text">{a.summary ?? a.action_type.replace(/_/g, " ")}</span>
                      <span className="text-sm font-bold text-text">{formatCurrency(a.amount)}</span>
                    </div>
                    <div className="mt-1 flex items-center justify-between">
                      <Badge variant={STATUS_BADGE[a.status].variant}>{STATUS_BADGE[a.status].label}</Badge>
                      <span className="text-xs text-text-muted">{a.decided_at ? formatDateTime(a.decided_at) : "—"}</span>
                    </div>
                  </div>
                )}
              />
            </div>
          )}
        </>
      )}
    </div>
  );
}
