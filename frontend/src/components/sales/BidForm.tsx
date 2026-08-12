import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../lib/api";
import type { Bid, Club, PendingApprovalCaptured, Sale } from "../../types/api";
import Button from "../ui/Button";
import CurrencyInput from "../ui/CurrencyInput";
import { formatCurrency, getApiError } from "../../lib/utils";
import { useToast } from "../../context/ToastContext";

interface BidFormProps {
  sale: Sale;
  /** The buyer's own existing active bid, if any (used to show "Replace" UI). */
  existingBid?: Bid;
}

export default function BidForm({ sale, existingBid }: BidFormProps) {
  const queryClient = useQueryClient();
  const { addToast } = useToast();

  const [amount, setAmount] = useState(
    existingBid ? String(Math.round(existingBid.amount)) : ""
  );
  const [notes, setNotes] = useState(existingBid?.notes ?? "");
  const [fieldError, setFieldError] = useState<string | null>(null);

  const { data: club } = useQuery<Club>({
    queryKey: ["clubs", "me"],
    queryFn: () => api.get<Club>("/clubs/me").then((r) => r.data),
    staleTime: 60_000,
  });

  const minBid = sale.minimum_next_bid ?? sale.min_increment;
  const valuation = sale.fair_value_signal?.fair_value ?? null;
  const parsedAmount = parseFloat(amount.replace(/,/g, ""));
  const threshold = club?.finance?.approval_threshold != null ? Number(club.finance.approval_threshold) : null;
  const needsApproval = threshold != null && !isNaN(parsedAmount) && parsedAmount >= threshold;

  const budgetRemaining = club?.finance ? Number(club.finance.transfer_remaining) : null;
  const committedElsewhere = club?.finance ? Number(club.finance.transfer_committed) : 0;
  const thisBid = !isNaN(parsedAmount) ? parsedAmount : 0;
  const freeAfter = budgetRemaining != null ? budgetRemaining - thisBid : null;

  const [pendingApproval, setPendingApproval] = useState(false);

  const mutation = useMutation({
    mutationFn: (body: { amount: number; notes?: string }) =>
      api
        .post<Bid | PendingApprovalCaptured>(`/sales/${sale.id}/bids`, {
          amount: body.amount,
          ...(body.notes && { notes: body.notes }),
        })
        .then((r) => r.data),
    onSuccess: (data) => {
      if ("approval_id" in data) {
        setPendingApproval(true);
        addToast("Bid sent for approval — an approver at your club must sign it off.", "info");
        queryClient.invalidateQueries({ queryKey: ["clubs", "me", "approvals"] });
        return;
      }
      queryClient.invalidateQueries({ queryKey: ["sales", sale.id] });
      queryClient.invalidateQueries({ queryKey: ["sales", sale.id, "bids"] });
      addToast(existingBid ? "Bid updated." : "Bid placed successfully.", "success");
      if (!existingBid) {
        setAmount("");
        setNotes("");
      }
    },
    onError: (err) => addToast(getApiError(err, "Failed to place bid."), "error"),
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFieldError(null);

    const parsed = parseFloat(amount.replace(/,/g, ""));
    if (isNaN(parsed) || parsed <= 0) {
      setFieldError("Enter a valid bid amount.");
      return;
    }
    if (parsed < minBid) {
      setFieldError(`Minimum bid is ${formatCurrency(minBid)}.`);
      return;
    }
    if (budgetRemaining != null && parsed > budgetRemaining) {
      setFieldError(`Insufficient budget. You have ${formatCurrency(budgetRemaining)} remaining.`);
      return;
    }

    mutation.mutate({ amount: parsed, notes: notes || undefined });
  }

  const serverError = mutation.isError ? getApiError(mutation.error, "Failed to place bid.") : null;

  const shortcuts = [
    { label: `Min ${formatCurrency(minBid)}`, value: minBid },
    { label: `+${formatCurrency(sale.min_increment)}`, value: (sale.best_bid ?? minBid) + sale.min_increment },
    ...(valuation != null ? [{ label: `Match valuation ${formatCurrency(valuation)}`, value: valuation }] : []),
  ];

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <p className="text-xs font-semibold uppercase tracking-wider text-text-muted mb-3">
        {existingBid ? "Replace Your Bid" : "Place a Bid"}
      </p>

      {/* Amount composer + shortcuts */}
      <div className="flex flex-wrap items-start gap-3">
        <div className="rounded-lg border-2 border-accent px-3 py-2" style={{ minWidth: 220 }}>
          <label htmlFor="bid-amount" className="block text-[11px] text-text-muted">Bid amount (£)</label>
          <CurrencyInput
            id="bid-amount"
            required
            value={amount}
            onChange={(raw) => { setAmount(raw); setFieldError(null); }}
            placeholder={minBid.toLocaleString("en-GB")}
            className="w-full bg-transparent text-[26px] font-bold text-text placeholder-text-muted focus:outline-none"
          />
        </div>
        <div className="flex flex-1 flex-wrap items-center gap-1.5 pt-1">
          {shortcuts.map((s) => (
            <button
              key={s.label}
              type="button"
              onClick={() => { setAmount(String(Math.round(s.value))); setFieldError(null); }}
              className="rounded-lg bg-surface-inset px-2.5 py-1 text-xs font-medium text-text-secondary ring-1 ring-input-border hover:ring-accent transition-colors"
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>

      {/* Budget-after bar */}
      {budgetRemaining != null && (
        <div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-border-quiet flex">
            <div className="h-full bg-warning-fill" style={{ width: `${Math.min(100, (committedElsewhere / (budgetRemaining + committedElsewhere)) * 100)}%` }} />
            <div className="h-full bg-accent" style={{ width: `${Math.min(100, (thisBid / (budgetRemaining + committedElsewhere)) * 100)}%` }} />
          </div>
          <p className="mt-1 text-[11px] text-text-muted">
            Committed elsewhere {formatCurrency(committedElsewhere)} · this bid {formatCurrency(thisBid)} · free after {freeAfter != null ? formatCurrency(freeAfter) : "—"}
          </p>
        </div>
      )}

      {/* Notes */}
      <div>
        <label htmlFor="bid-notes" className="mb-1.5 block text-sm font-medium text-text-secondary">
          Message <span className="text-text-muted">(optional)</span>
        </label>
        <input
          id="bid-notes"
          type="text"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Any message for the seller…"
          className="w-full rounded-lg bg-surface px-3 py-2.5 text-sm text-text placeholder-text-muted ring-1 ring-input-border focus:outline-none focus:ring-accent transition-colors"
        />
      </div>

      {(fieldError || serverError) && (
        <p className="text-sm text-danger-text">{fieldError ?? serverError}</p>
      )}

      {/* Approval notice — shown BEFORE submit, not after (SCREENS.md's ordering fix) */}
      {needsApproval && !pendingApproval && (
        <div className="rounded-xl bg-warning-bg px-4 py-3">
          <p className="text-sm font-semibold text-warning-text">This bid needs approval before it is placed</p>
          <p className="mt-1 text-xs text-warning-text/80">
            Bids at or above {formatCurrency(threshold!)} wait for sign-off from your club's owner or sporting director before they're placed.
          </p>
        </div>
      )}

      {pendingApproval ? (
        <p className="text-sm text-warning-text">
          Pending approval — this bid is waiting for sign-off from your club's owner
          or sporting director. Track it on the Approvals page.
        </p>
      ) : (
        mutation.isSuccess && (
          <p className="text-sm text-success-text">
            {existingBid ? "Bid updated successfully." : "Bid placed successfully."}
          </p>
        )
      )}

      {/* SCREENS.md also specs a "Withdraw current bid" secondary action here —
          no per-bid withdraw endpoint exists on the backend (only create/list/
          accept), so it isn't wired. Not invented. */}
      <Button type="submit" variant="primary" size="md" loading={mutation.isPending} className="w-full">
        {needsApproval ? `Send ${!isNaN(parsedAmount) ? formatCurrency(parsedAmount) : ""} for approval` : existingBid ? "Replace bid" : "Place bid"}
      </Button>
    </form>
  );
}
