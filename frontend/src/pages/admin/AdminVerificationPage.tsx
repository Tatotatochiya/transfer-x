import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { VerificationRequest, VerificationStatus } from "../../types/api";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import PageHeader from "../../components/ui/PageHeader";
import Spinner from "../../components/ui/Spinner";
import { formatDate, getApiError } from "../../lib/utils";
import { useToast } from "../../context/ToastContext";

const STATUS_TABS: { value: VerificationStatus | "ALL"; label: string }[] = [
  { value: "PENDING",  label: "Pending" },
  { value: "APPROVED", label: "Approved" },
  { value: "REJECTED", label: "Rejected" },
  { value: "ALL",      label: "All" },
];

const STATUS_VARIANT: Record<VerificationStatus, "warning" | "success" | "danger"> = {
  PENDING: "warning",
  APPROVED: "success",
  REJECTED: "danger",
};

function RequestRow({ req }: { req: VerificationRequest }) {
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const [rejecting, setRejecting] = useState(false);
  const [reviewNotes, setReviewNotes] = useState("");

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["admin", "verification", "requests"] });

  const approveMutation = useMutation({
    mutationFn: () => api.post(`/verification/requests/${req.id}/approve`).then((r) => r.data),
    onSuccess: () => {
      invalidate();
      addToast("Verification approved.", "success");
    },
    onError: (err: unknown) => addToast(getApiError(err, "Failed to approve."), "error"),
  });

  const rejectMutation = useMutation({
    mutationFn: () =>
      api.post(`/verification/requests/${req.id}/reject`, { review_notes: reviewNotes.trim() || undefined }).then((r) => r.data),
    onSuccess: () => {
      invalidate();
      setRejecting(false);
      addToast("Verification rejected.", "success");
    },
    onError: (err: unknown) => addToast(getApiError(err, "Failed to reject."), "error"),
  });

  return (
    <tr className="border-t border-white/[0.05] align-top">
      <td className="px-4 py-3">
        <Badge variant="neutral">{req.entity_type}</Badge>
      </td>
      <td className="px-4 py-3 text-white font-medium">{req.entity_name ?? "—"}</td>
      <td className="px-4 py-3 text-slate-400">{req.requested_by_email ?? "—"}</td>
      <td className="px-4 py-3 text-slate-400">
        {req.evidence_ref ? (
          <span className="break-all">{req.evidence_ref}</span>
        ) : "—"}
        {req.notes && <p className="mt-1 text-xs text-slate-500">{req.notes}</p>}
      </td>
      <td className="px-4 py-3">
        <Badge variant={STATUS_VARIANT[req.status]}>{req.status}</Badge>
        {req.status !== "PENDING" && req.review_notes && (
          <p className="mt-1 text-xs text-slate-500">{req.review_notes}</p>
        )}
      </td>
      <td className="px-4 py-3 text-xs text-slate-500">{formatDate(req.created_at)}</td>
      <td className="px-4 py-3">
        {req.status === "PENDING" && (
          rejecting ? (
            <div className="flex flex-col gap-2 min-w-[180px]">
              <input
                type="text"
                value={reviewNotes}
                onChange={(e) => setReviewNotes(e.target.value)}
                placeholder="Reason (optional)"
                className="rounded-lg bg-slate-900 px-2 py-1.5 text-xs text-white placeholder-slate-600 ring-1 ring-white/10 focus:outline-none focus:ring-red-500"
              />
              <div className="flex gap-2">
                <Button variant="danger" size="sm" loading={rejectMutation.isPending} onClick={() => rejectMutation.mutate()}>
                  Confirm
                </Button>
                <Button variant="ghost" size="sm" onClick={() => setRejecting(false)} disabled={rejectMutation.isPending}>
                  Cancel
                </Button>
              </div>
            </div>
          ) : (
            <div className="flex gap-2">
              <Button variant="primary" size="sm" loading={approveMutation.isPending} onClick={() => approveMutation.mutate()}>
                Approve
              </Button>
              <Button variant="danger" size="sm" onClick={() => setRejecting(true)}>
                Reject
              </Button>
            </div>
          )
        )}
      </td>
    </tr>
  );
}

export default function AdminVerificationPage() {
  const [tab, setTab] = useState<VerificationStatus | "ALL">("PENDING");

  const { data: requests = [], isLoading } = useQuery<VerificationRequest[]>({
    queryKey: ["admin", "verification", "requests", tab],
    queryFn: () =>
      api
        .get<VerificationRequest[]>("/verification/requests", {
          params: tab === "ALL" ? {} : { request_status: tab },
        })
        .then((r) => r.data),
  });

  return (
    <div>
      <PageHeader title="Verification Requests" subtitle="Review and action verification requests from clubs, agents, and players" />

      <div className="mb-4 flex gap-1 rounded-xl bg-slate-800/50 p-1 w-fit">
        {STATUS_TABS.map((t) => (
          <button
            key={t.value}
            onClick={() => setTab(t.value)}
            className={`rounded-lg px-4 py-1.5 text-sm font-medium transition-colors ${
              tab === t.value ? "bg-slate-700 text-white shadow-sm" : "text-slate-400 hover:text-white"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="flex justify-center py-12"><Spinner size="lg" /></div>
      ) : requests.length === 0 ? (
        <div className="rounded-xl bg-slate-900 px-5 py-12 text-center ring-1 ring-white/[0.08]">
          <p className="text-sm font-medium text-white">No requests</p>
          <p className="mt-1 text-sm text-slate-500">Nothing to review in this filter.</p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl ring-1 ring-white/[0.08]">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b border-white/[0.08] text-left text-xs font-semibold uppercase tracking-wider text-slate-500">
                <th className="px-4 py-3">Type</th>
                <th className="px-4 py-3">Entity</th>
                <th className="px-4 py-3">Requested by</th>
                <th className="px-4 py-3">Evidence / notes</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Submitted</th>
                <th className="px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {requests.map((r) => (
                <RequestRow key={r.id} req={r} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
