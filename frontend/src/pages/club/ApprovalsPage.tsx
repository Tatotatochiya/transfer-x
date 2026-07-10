import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import { useAuth } from "../../hooks/useAuth";
import { useClubCapabilities } from "../../hooks/useClubCapabilities";
import type { ApprovalPolicy, PendingApproval } from "../../types/api";
import type { ApprovalStatus } from "../../types/enums";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import EmptyState from "../../components/ui/EmptyState";
import PageHeader from "../../components/ui/PageHeader";
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

type Filter = "PENDING" | "ALL";

export default function ApprovalsPage() {
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const { user } = useAuth();
  const { can, isLoading: capsLoading } = useClubCapabilities();
  const [filter, setFilter] = useState<Filter>("PENDING");
  const [rejectingId, setRejectingId] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState("");

  const canDecide = can("APPROVE_ACTIONS");

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
      if (data.status === "APPROVED_EXECUTED") {
        addToast("Approved and executed", "success");
      } else {
        addToast(`Approved, but execution failed: ${data.failure_reason ?? "unknown reason"}`, "warning");
      }
    },
    onError: (err: unknown) => addToast(getApiError(err, "Failed to approve."), "error"),
  });

  const rejectMutation = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string | null }) =>
      api.post<PendingApproval>(`/clubs/me/approvals/${id}/reject`, { reason }).then((r) => r.data),
    onSuccess: () => {
      invalidate();
      setRejectingId(null);
      setRejectReason("");
      addToast("Request rejected", "info");
    },
    onError: (err: unknown) => addToast(getApiError(err, "Failed to reject."), "error"),
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

  return (
    <div>
      <PageHeader
        title="Approvals"
        subtitle={
          canDecide
            ? "Spending requests from your team that need a decision"
            : "Your spending requests awaiting a decision"
        }
      />

      {can("TEAM_MANAGE") && (
        <p className="mb-5 text-xs text-slate-500">
          {policy?.approval_threshold != null
            ? <>Manager actions at or above <span className="text-slate-300">{formatCurrency(policy.approval_threshold)}</span> require approval. Change this on the Finance page.</>
            : "No approval threshold is set — manager actions execute directly. Set one on the Finance page."}
        </p>
      )}

      <div className="mb-5 flex gap-1 rounded-xl bg-slate-800/50 p-1 w-fit">
        {(["PENDING", "ALL"] as Filter[]).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`rounded-lg px-4 py-1.5 text-sm font-medium transition-colors ${
              filter === f ? "bg-slate-700 text-white shadow-sm" : "text-slate-400 hover:text-white"
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
        <div className="rounded-xl bg-slate-900 ring-1 ring-white/[0.08] overflow-hidden divide-y divide-white/[0.04]">
          {rows.map((a) => {
            const isMine = a.requested_by_user_id === user?.id;
            const pending = a.status === "PENDING";
            return (
              <div key={a.id} className="px-5 py-4">
                <div className="flex flex-wrap items-center gap-3">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-white">
                      {a.summary ?? a.action_type.replace(/_/g, " ")}
                    </p>
                    <p className="mt-0.5 text-xs text-slate-500">
                      {a.requested_by_email ?? "Unknown requester"} · {formatDateTime(a.created_at)}
                      {pending && <> · expires {formatDateTime(a.expires_at)}</>}
                    </p>
                    {a.failure_reason && a.status !== "PENDING" && (
                      <p className="mt-1 text-xs text-amber-400/80">{a.failure_reason}</p>
                    )}
                  </div>
                  <span className="text-sm font-semibold text-white">{formatCurrency(a.amount)}</span>
                  <Badge variant={STATUS_BADGE[a.status].variant}>{STATUS_BADGE[a.status].label}</Badge>
                  {pending && canDecide && (
                    <div className="flex gap-2">
                      <Button
                        variant="primary"
                        size="sm"
                        onClick={() => approveMutation.mutate(a.id)}
                        loading={approveMutation.isPending}
                      >
                        Approve
                      </Button>
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => setRejectingId(rejectingId === a.id ? null : a.id)}
                      >
                        Reject
                      </Button>
                    </div>
                  )}
                  {pending && isMine && !canDecide && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => cancelMutation.mutate(a.id)}
                      loading={cancelMutation.isPending}
                    >
                      <span className="text-red-400">Cancel</span>
                    </Button>
                  )}
                </div>
                {rejectingId === a.id && (
                  <div className="mt-3 flex items-center gap-2">
                    <input
                      type="text"
                      value={rejectReason}
                      onChange={(e) => setRejectReason(e.target.value)}
                      placeholder="Reason (optional)"
                      className="min-w-0 flex-1 rounded-lg bg-slate-950 px-3 py-2 text-sm text-white placeholder-slate-600 ring-1 ring-white/10 focus:outline-none focus:ring-emerald-500"
                    />
                    <Button
                      variant="danger"
                      size="sm"
                      onClick={() => rejectMutation.mutate({ id: a.id, reason: rejectReason || null })}
                      loading={rejectMutation.isPending}
                    >
                      Confirm reject
                    </Button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
