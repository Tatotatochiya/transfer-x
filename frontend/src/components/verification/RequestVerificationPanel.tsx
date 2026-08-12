import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { VerificationRequest } from "../../types/api";
import Button from "../ui/Button";
import { formatDate, getApiError } from "../../lib/utils";
import { useToast } from "../../context/ToastContext";

interface RequestVerificationPanelProps {
  /** Whether the underlying entity is already verified — hides the request form when true. */
  verified: boolean;
}

export default function RequestVerificationPanel({ verified }: RequestVerificationPanelProps) {
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const [showForm, setShowForm] = useState(false);
  const [evidenceRef, setEvidenceRef] = useState("");
  const [notes, setNotes] = useState("");

  const { data: requests = [], isLoading } = useQuery<VerificationRequest[]>({
    queryKey: ["verification", "requests", "mine"],
    queryFn: () => api.get<VerificationRequest[]>("/verification/requests/mine").then((r) => r.data),
  });

  const mutation = useMutation({
    mutationFn: () =>
      api.post<VerificationRequest>("/verification/requests", {
        evidence_ref: evidenceRef.trim() || undefined,
        notes: notes.trim() || undefined,
      }).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["verification", "requests", "mine"] });
      setShowForm(false);
      setEvidenceRef("");
      setNotes("");
      addToast("Verification request submitted.", "success");
    },
    onError: (err: unknown) => addToast(getApiError(err, "Failed to submit request."), "error"),
  });

  if (isLoading) return null;
  if (verified) return null;

  const latest = requests[0];
  const isPending = latest?.status === "PENDING";

  return (
    <div className="mt-4 rounded-lg bg-surface-inset px-4 py-3 ring-1 ring-border">
      {isPending ? (
        <div className="flex items-center justify-between gap-3">
          <p className="text-sm text-text-secondary">
            Verification request pending review
            <span className="ml-2 text-xs text-text-muted">submitted {formatDate(latest.created_at)}</span>
          </p>
        </div>
      ) : (
        <>
          {latest?.status === "REJECTED" && (
            <p className="mb-2 text-sm text-danger-text">
              Your last verification request was not approved
              {latest.review_notes ? `: ${latest.review_notes}` : "."}
            </p>
          )}
          {!showForm ? (
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm text-text-muted">Not verified yet.</p>
              <Button variant="secondary" size="sm" onClick={() => setShowForm(true)}>
                Request verification
              </Button>
            </div>
          ) : (
            <div className="space-y-3">
              <div>
                <label className="mb-1 block text-xs font-medium text-text-muted">
                  Evidence link <span className="text-text-muted">(optional)</span>
                </label>
                <input
                  type="text"
                  value={evidenceRef}
                  onChange={(e) => setEvidenceRef(e.target.value)}
                  placeholder="Link to licence, official profile, etc."
                  className="w-full rounded-lg bg-surface px-3 py-2 text-sm text-text placeholder-text-muted ring-1 ring-input-border focus:outline-none focus:ring-accent transition-colors"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-text-muted">
                  Notes <span className="text-text-muted">(optional)</span>
                </label>
                <textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  rows={2}
                  className="w-full rounded-lg bg-surface px-3 py-2 text-sm text-text placeholder-text-muted ring-1 ring-input-border focus:outline-none focus:ring-accent transition-colors"
                />
              </div>
              <div className="flex gap-2">
                <Button variant="primary" size="sm" loading={mutation.isPending} onClick={() => mutation.mutate()}>
                  Submit request
                </Button>
                <Button variant="secondary" size="sm" onClick={() => setShowForm(false)} disabled={mutation.isPending}>
                  Cancel
                </Button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
